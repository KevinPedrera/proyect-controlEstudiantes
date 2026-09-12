"""Read-only, accent-insensitive name search over the active academic period."""

from heapq import nsmallest
import unicodedata

from pydantic import BaseModel
from sqlalchemy import select

from app.student_models import Institution, Student, StudentAcademicPlacement
from app.movements import active_summary

MAX_RESULTS = 5
MAX_QUERY_LENGTH = 120
NAME_FIELDS = ('first_name', 'middle_name', 'last_name', 'second_last_name')


class ActivePeriodMissing(Exception):
    pass


class StudentSearchResult(BaseModel):
    student_id: int
    first_name: str
    middle_name: str | None
    last_name: str
    second_last_name: str | None
    display_name: str
    course: str
    parallel: str
    active_movement: dict | None = None


def name_words(value: str) -> tuple[str, ...]:
    """Search only: never reuse this normalization as an identity decision."""
    decomposed = unicodedata.normalize('NFKD', value)
    folded = ''.join(c for c in decomposed if not unicodedata.combining(c)).casefold()
    return tuple(''.join(c if c.isalpha() else ' ' for c in folded).split())


def _rank(terms: tuple[str, ...], words: tuple[str, ...]):
    if not all(any(term in word for word in words) for term in terms):
        return None
    exact = sum(term in words for term in terms)
    prefixes = sum(any(word.startswith(term) for word in words) for term in terms)
    if sorted(terms) == sorted(words):
        tier = 0
    elif exact == len(terms):
        tier = 1
    elif prefixes == len(terms):
        tier = 2
    else:
        tier = 3
    return tier, -exact, -prefixes


def search_students(factory, query: str, limit: int) -> list[StudentSearchResult]:
    words = name_words(query)
    if sum(map(len, words)) < 2:
        return []
    terms = tuple(dict.fromkeys(words))
    with factory() as session:
        period_id = session.scalar(select(Institution.active_academic_period_id).where(Institution.id == 1))
        if period_id is None:
            raise ActivePeriodMissing()
        # Select no documents, contacts, provenance or import data. No ORM entities
        # containing extra PII are loaded. The read transaction gives one snapshot.
        statement = select(
            Student.id.label('student_id'), *(getattr(Student, field) for field in NAME_FIELDS),
            StudentAcademicPlacement.course, StudentAcademicPlacement.parallel,
        ).join(StudentAcademicPlacement, StudentAcademicPlacement.student_id == Student.id).where(
            Student.active.is_(True),
            StudentAcademicPlacement.academic_period_id == period_id,
            StudentAcademicPlacement.recorded_to.is_(None),
        )

        def matches():
            for item in session.execute(statement).mappings():
                display_name = ' '.join(item[field] for field in NAME_FIELDS if item[field])
                rank = _rank(terms, name_words(display_name))
                if rank is not None:
                    alphabetical = tuple(name_words(item[field] or '') for field in
                                         ('last_name', 'second_last_name', 'first_name', 'middle_name'))
                    yield (*rank, alphabetical, item['student_id']), dict(item, display_name=display_name)

        best = nsmallest(limit, matches(), key=lambda match: match[0])
        return [StudentSearchResult(**item, active_movement=active_summary(session, item['student_id'])) for _, item in best]
