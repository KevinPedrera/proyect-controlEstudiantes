import { Component, computed, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { finalize } from 'rxjs';
import { ApiService } from './core/api.service';
import { SocketService } from './core/socket.service';

type HealthState = 'checking' | 'connected' | 'error';

@Component({
  selector: 'app-root',
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App implements OnInit {
  private readonly api = inject(ApiService);
  private readonly destroyRef = inject(DestroyRef);
  protected readonly socket = inject(SocketService);
  protected readonly health = signal<HealthState>('checking');
  private checking = false;

  protected readonly healthLabel = computed(() => ({
    checking: 'Comprobando…', connected: 'Conectado', error: 'Error de conexión',
  })[this.health()]);
  protected readonly socketLabel = computed(() => ({
    connecting: 'Conectando…', connected: 'Conectado',
    disconnected: 'Desconectado', error: 'Error de conexión',
  })[this.socket.state()]);

  constructor() {
    this.destroyRef.onDestroy(() => this.socket.disconnect());
  }

  ngOnInit(): void {
    this.checkConnections();
  }

  protected checkConnections(): void {
    if (this.checking) return;
    this.checking = true;
    this.health.set('checking');
    this.socket.connect();
    this.api.health().pipe(
      takeUntilDestroyed(this.destroyRef),
      finalize(() => { this.checking = false; }),
    ).subscribe({
      next: (response) => this.health.set(response.status === 'ok' ? 'connected' : 'error'),
      error: () => this.health.set('error'),
    });
  }
}
