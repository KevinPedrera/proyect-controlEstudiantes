from io import BytesIO
from zipfile import ZipFile

import pytest

from app.import_parser import ImportFormatError, parse_xlsx
from import_fixtures import binary, workbook


@pytest.mark.parametrize('shift', [0, 1, 5])
def test_profile_recognizes_shifted_merged_headers(shift):
    data = parse_xlsx(binary(workbook(shift=shift)))
    assert data.institution == 'Colegio de prueba'
    assert data.period_key == '2026-2027'
    assert len(data.rows) == 1
    assert data.rows[0]['row_number'] == 8 + shift
    assert data.rows[0]['student']['document'] == '0123456789'


def test_homonymous_columns_two_emergencies_and_incomplete_contact():
    data = parse_xlsx(binary(workbook([{'N': 'Representante', 'T': 'Padre', 'Z': 'Madre', 'AE': 'Emergencia Uno', 'AK': 'Emergencia Dos', 'AM': '(+593) 991111111'}])))
    row = data.rows[0]
    assert row['student']['first_name'] == 'Ana'
    assert [c['first_name'] for c in row['contacts']] == ['Representante', 'Padre', 'Madre', 'Emergencia Uno', 'Emergencia Dos']
    assert [c['source_slot'] for c in row['contacts'][-2:]] == [1, 2]
    assert row['contacts'][-1]['mobile_phone'] == '(+593) 991111111'
    assert any(w['code'] == 'INCOMPLETE_CONTACT' for w in row['warnings'])


def test_null_empty_trim_and_literal_dash_are_distinct():
    row = parse_xlsx(binary(workbook([{'C': None, 'D': '', 'G': ' Ana ', 'F': '  ', 'H': '-'}]))).rows[0]
    assert row['student']['document'] is None
    assert row['student']['second_last_name'] is None
    assert row['student']['first_name'] == 'Ana'
    assert row['student']['middle_name'] == '-'
    assert row['contacts'] == []
    assert row['warnings'][0]['code'] == 'LITERAL_DASH'


@pytest.mark.parametrize('document', ['123456789', 'AB123456'])
def test_passport_is_text(document):
    row = parse_xlsx(binary(workbook([{'C': document, 'D': 'Pasaporte'}]))).rows[0]
    assert row['student']['document'] == document


@pytest.mark.parametrize('field', ['E', 'G', 'I', 'J'])
def test_incomplete_rows_are_kept_for_review(field):
    row = parse_xlsx(binary(workbook([{field: None}]))).rows[0]
    assert row['errors']


def test_numeric_document_warns_without_padding():
    row = parse_xlsx(binary(workbook([{'C': 123}]))).rows[0]
    assert row['student']['document'] == '123'
    assert row['warnings'][0]['code'] == 'NUMERIC_CELL'


@pytest.mark.parametrize('change', ['heading', 'group', 'merge', 'formula', 'extra', 'duplicate_sheet', 'institution', 'period'])
def test_incompatible_structures_rejected(change):
    book = workbook()
    sheet = book.active
    if change == 'heading': sheet['G6'] = 'Desconocido'
    if change == 'group': sheet['K5'] = 'Otro grupo'
    if change == 'merge': sheet.unmerge_cells('C5:J5')
    if change == 'formula': sheet['C8'] = '=1+2'
    if change == 'extra': sheet['AP8'] = 'Extra'
    if change == 'duplicate_sheet': book.copy_worksheet(sheet)
    if change == 'institution': sheet['B1'] = None
    if change == 'period': sheet['B3'] = 'Periodo desconocido'
    with pytest.raises(ImportFormatError): parse_xlsx(binary(book))


def test_empty_rows_skipped_but_footer_kept_as_invalid_row():
    book = workbook()
    book.active['B10'] = 'Total'
    data = parse_xlsx(binary(book))
    assert data.skipped_empty_rows == 1
    assert len(data.rows) == 2 and data.rows[1]['errors']


@pytest.mark.parametrize('content', [b'not a zip', b'x' * (5 * 1024 * 1024 + 1)], ids=['invalid', 'oversize'])
def test_bad_or_oversize_content(content):
    with pytest.raises(ImportFormatError): parse_xlsx(content)


def test_xml_entity_rejected_before_loading():
    stream = BytesIO()
    with ZipFile(stream, 'w') as archive:
        archive.writestr('xl/test.xml', '<!DOCTYPE a [<!ENTITY x "danger">]><a/>')
    with pytest.raises(ImportFormatError): parse_xlsx(stream.getvalue())


def test_oversize_merge_rejected_before_openpyxl_expands_it():
    content = binary(workbook())
    source, destination = BytesIO(content), BytesIO()
    with ZipFile(source) as original, ZipFile(destination, 'w') as changed:
        for info in original.infolist():
            data = original.read(info)
            if info.filename == 'xl/worksheets/sheet1.xml':
                data = data.replace(b'ref="C5:J5"', b'ref="C5:XFD1048576"')
            changed.writestr(info.filename, data)
    with pytest.raises(ImportFormatError): parse_xlsx(destination.getvalue())
