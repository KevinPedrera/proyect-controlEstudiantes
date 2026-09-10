import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { timeout } from 'rxjs';

export interface StudentSearchResult {
  student_id: number;
  first_name: string;
  middle_name: string | null;
  last_name: string;
  second_last_name: string | null;
  display_name: string;
  course: string;
  parallel: string;
}

@Injectable({ providedIn: 'root' })
export class StudentSearchService {
  private readonly http = inject(HttpClient);

  search(query: string) {
    return this.http.get<StudentSearchResult[]>('/api/students/search', {
      params: { q: query, limit: 5 },
    }).pipe(timeout(10000));
  }
}
