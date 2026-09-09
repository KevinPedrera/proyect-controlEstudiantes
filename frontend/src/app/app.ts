import { Component, computed, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { finalize } from 'rxjs';
import { ApiService } from './core/api.service';
import { DepartmentGroup } from './core/department.model';
import { DepartmentsService } from './core/departments.service';
import { SocketService } from './core/socket.service';
import { ImportPreview } from './imports/import-preview';

type HealthState = 'checking' | 'connected' | 'error';

@Component({ selector: 'app-root', imports: [ImportPreview], templateUrl: './app.html', styleUrl: './app.css' })
export class App implements OnInit {
  private readonly api = inject(ApiService);
  private readonly destroyRef = inject(DestroyRef);
  protected readonly socket = inject(SocketService);
  protected readonly data = inject(DepartmentsService);
  protected readonly health = signal<HealthState>('checking');
  private checking = false;
  protected readonly groups: { key: DepartmentGroup; label: string }[] = [
    { key: 'INSPECCION', label: 'Inspección' }, { key: 'DECE', label: 'DECE' },
    { key: 'SALUD', label: 'Salud' },
  ];
  protected readonly grouped = computed(() => this.groups.map(group => ({
    ...group, departments: this.data.departments().filter(item => item.group === group.key),
  })));
  protected readonly healthLabel = computed(() => ({
    checking: 'Comprobando…', connected: 'Conectado', error: 'Error de conexión',
  })[this.health()]);
  protected readonly socketLabel = computed(() => ({
    connecting: 'Conectando…', connected: 'Conectado',
    disconnected: 'Desconectado', reconnecting: 'Desconectado · Reconectando…',
  })[this.socket.state()]);

  constructor() { this.destroyRef.onDestroy(() => this.socket.disconnect()); }

  ngOnInit(): void {
    this.data.start();
    this.checkHealth();
  }

  protected retry(): void {
    this.data.refresh();
    this.socket.connect();
    this.checkHealth();
  }

  private checkHealth(): void {
    if (this.checking) return;
    this.checking = true;
    this.health.set('checking');
    this.api.health().pipe(
      takeUntilDestroyed(this.destroyRef),
      finalize(() => { this.checking = false; }),
    ).subscribe({
      next: response => this.health.set(response.status === 'ok' ? 'connected' : 'error'),
      error: () => this.health.set('error'),
    });
  }
}
