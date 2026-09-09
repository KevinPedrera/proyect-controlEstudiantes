import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { timeout } from 'rxjs';

export type Scope = 'PADRON_COMPLETO' | 'SUBCONJUNTO';
export type Category = 'NUEVO' | 'SIN_CAMBIOS' | 'ACTUALIZACION' | 'REQUIERE_REVISION';
export interface Preview {
  id: string; status: string; scope: Scope; institution: string; academic_period: string;
  expires_at: string; total: number; counts: Record<Category, number>; warnings: string[];
  quality_warning_count: number; absence_count: number; absences_calculated: boolean;
  rows_with_warnings?: number; rows_with_blocking_reasons?: number;
}
export interface Person { [field: string]: string | null; }
export interface Candidate { student_id: number; name: string; course: string | null; parallel: string | null; reasons: string[]; }
export interface PreviewRow {
  row_number: number; sheet: string; student: Person; contacts: Record<string, unknown>[];
  category: Category; tags: string[]; warnings: { code: string; cell: string; message: string }[];
  errors: string[]; conflicts: string[]; candidates: Candidate[];
  blocking_review_reasons?: string[];
  differences: { field: string; current: unknown; incoming: unknown; action: string }[];
}
export interface Page<T> { items: T[]; total: number; page: number; page_size: number; }

@Injectable({ providedIn: 'root' })
export class ImportsService {
  private readonly http = inject(HttpClient);
  create(file: File, scope: Scope) {
    const form = new FormData(); form.append('file', file); form.append('scope', scope);
    return this.http.post<Preview>('/api/student-imports/preview', form).pipe(timeout(60000));
  }
  get(id: string) { return this.http.get<Preview>(`/api/student-imports/${encodeURIComponent(id)}`).pipe(timeout(10000)); }
  rows(id: string, page: number) { return this.http.get<Page<PreviewRow>>(`/api/student-imports/${encodeURIComponent(id)}/rows`, { params: { page, page_size: 10 } }).pipe(timeout(10000)); }
  absences(id: string, page: number) { return this.http.get<Page<Candidate>>(`/api/student-imports/${encodeURIComponent(id)}/absences`, { params: { page, page_size: 10 } }).pipe(timeout(10000)); }
}
