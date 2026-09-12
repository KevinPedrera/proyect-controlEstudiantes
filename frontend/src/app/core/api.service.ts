import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, timeout } from 'rxjs';
import { Availability, Department } from './department.model';

export interface HealthResponse {
  status: 'ok';
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);

  health(): Observable<HealthResponse> {
    return this.http.get<HealthResponse>('/api/health').pipe(timeout(5000));
  }

  departments(): Observable<Department[]> {
    return this.http.get<Department[]>('/api/departments').pipe(timeout(5000));
  }

  setAvailability(id: number, availability: Availability, counts?: { en_camino: number; en_atencion: number }): Observable<Department> {
    return this.http.put<Department>(`/api/departments/${id}/availability`,
      { availability, ...(counts ? { confirmed_active_counts: counts } : {}) })
      .pipe(timeout(10000));
  }
}
