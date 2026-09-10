import { Component, DestroyRef, ElementRef, HostListener, ViewChild, inject, output, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subject, catchError, map, of, switchMap, tap, timer } from 'rxjs';
import { StudentSearchResult, StudentSearchService } from './student-search.service';

type SearchState = 'initial' | 'short' | 'waiting' | 'loading' | 'results' | 'empty' | 'error';

@Component({
  selector: 'app-student-search',
  templateUrl: './student-search.html',
  styleUrl: './student-search.css',
})
export class StudentSearch {
  private static nextId = 0;
  protected readonly inputId = `student-search-${StudentSearch.nextId++}`;
  private readonly api = inject(StudentSearchService);
  private readonly destroy = inject(DestroyRef);
  private readonly queries = new Subject<string>();
  private focusOnSearch = false;
  private input?: ElementRef<HTMLInputElement>;
  protected readonly query = signal('');
  protected readonly state = signal<SearchState>('initial');
  protected readonly results = signal<StudentSearchResult[]>([]);
  protected readonly selected = signal<StudentSearchResult | null>(null);
  readonly selectionChange = output<StudentSearchResult | null>();

  @ViewChild('searchInput') set searchInput(input: ElementRef<HTMLInputElement> | undefined) {
    this.input = input;
    if (input && this.focusOnSearch) {
      this.focusOnSearch = false;
      input.nativeElement.focus();
    }
  }
  @ViewChild('changeButton') set changeButton(button: ElementRef<HTMLButtonElement> | undefined) {
    button?.nativeElement.focus();
  }

  constructor() {
    // switchMap sees every keystroke immediately: it cancels an in-flight HTTP
    // request even while the next query is still waiting for its debounce.
    this.queries.pipe(
      switchMap(query => {
        const letters = query.normalize('NFKD').replace(/\p{M}/gu, '').match(/\p{L}/gu) ?? [];
        this.results.set([]);
        if (letters.length < 2) {
          this.state.set(query ? 'short' : 'initial');
          return of(null);
        }
        this.state.set('waiting');
        return timer(300).pipe(
          tap(() => this.state.set('loading')),
          switchMap(() => this.api.search(query)),
          map(items => ({ items: items.slice(0, 5), failed: false })),
          catchError(() => of({ items: [], failed: true })),
        );
      }),
      takeUntilDestroyed(this.destroy),
    ).subscribe(result => {
      if (result === null) return;
      this.results.set(result.items);
      this.state.set(result.failed ? 'error' : result.items.length ? 'results' : 'empty');
    });
  }

  protected searchChanged(event: Event): void {
    const query = (event.target as HTMLInputElement).value;
    this.query.set(query);
    this.queries.next(query);
  }

  protected retry(): void { this.queries.next(this.query()); }

  protected select(student: StudentSearchResult): void {
    this.queries.next('');
    this.selected.set(student);
    this.selectionChange.emit(student);
  }

  protected changeStudent(): void {
    this.focusOnSearch = true;
    this.query.set('');
    this.queries.next('');
    this.selected.set(null);
    this.selectionChange.emit(null);
  }

  @HostListener('keydown.escape') protected closeResults(): void {
    if (this.selected()) return;
    this.query.set('');
    this.queries.next('');
    this.input?.nativeElement.focus();
  }
}
