import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, timeout } from 'rxjs';

export interface HealthResponse {
  status: 'ok';
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);

  health(): Observable<HealthResponse> {
    return this.http.get<HealthResponse>('/api/health').pipe(timeout(5000));
  }
}
