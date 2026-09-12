import { computed, DestroyRef, inject, Injectable, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subscription } from 'rxjs';
import { ApiService } from './api.service';
import { Availability, Department } from './department.model';
import { SocketService } from './socket.service';
import { DialogService } from './dialog';

@Injectable({ providedIn: 'root' })
export class DepartmentsService {
  private readonly api = inject(ApiService);
  private readonly dialog = inject(DialogService);
  private readonly socket = inject(SocketService);
  private readonly destroyRef = inject(DestroyRef);
  readonly departments = signal<Department[]>([]);
  readonly loading = signal(false);
  readonly loaded = signal(false);
  readonly error = signal('');
  readonly savingId = signal<number | null>(null);
  readonly saveError = signal<{ id: number; message: string } | null>(null);
  private readonly synchronized = signal(false);
  readonly canChange = computed(() =>
    this.socket.state() === 'connected' && this.synchronized() && !this.loading() &&
    this.savingId() === null);
  private read: Subscription | undefined;
  private started = false;

  constructor() {
    this.socket.events.pipe(takeUntilDestroyed()).subscribe(event => {
      if (!this.started) return;
      if (event === 'disconnected') {
        this.synchronized.set(false);
      } else {
        this.refresh();
      }
    });
    this.destroyRef.onDestroy(() => this.read?.unsubscribe());
  }

  start(): void {
    if (this.started) return;
    this.started = true;
    this.refresh();
    this.socket.connect();
  }

  refresh(): void {
    // Cancelar la lectura anterior impide que una respuesta antigua sobrescriba el estado.
    this.cancelRead();
    if (this.savingId() !== null) return;
    this.loading.set(true);
    this.error.set('');
    this.read = this.api.departments().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: departments => {
        this.departments.set(departments);
        this.loaded.set(true);
        this.loading.set(false);
        this.synchronized.set(this.socket.state() === 'connected');
      },
      error: () => {
        this.loading.set(false);
        this.error.set('No se pudieron actualizar los departamentos. Reintenta la consulta.');
      },
    });
  }

  change(department: Department, availability: Availability): void {
    if (!department.active || !this.canChange()) return;
    this.cancelRead();
    this.savingId.set(department.id);
    this.saveError.set(null);
    this.submit(department, availability);
  }

  private submit(department: Department, availability: Availability, counts?: { en_camino: number; en_atencion: number }): void {
    this.api.setAvailability(department.id, availability, counts)
      .pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
        next: () => {
          this.savingId.set(null);
          this.refresh();
        },
        error: async error => {
          const detail = error.error?.detail;
          if (detail?.code === 'CONFIRMAR_ACTIVOS') {
            const current = detail.active_counts;
            const accepted = await this.dialog.ask({
              title: 'Este departamento tiene estudiantes activos',
              message: `${department.name}\n\n${current.en_atencion} en atención\n${current.en_camino} en camino\n\nContinuarán normalmente, pero no podrán ingresar nuevos estudiantes. ¿Desea continuar?`,
              confirm: 'Cambiar a No disponible',
            });
            if (accepted && this.socket.state() === 'connected') {
              this.submit(department, availability, current);
              return;
            }
            this.savingId.set(null); this.refresh();
            return;
          }
          this.savingId.set(null);
          this.saveError.set({
            id: department.id,
            message: 'No se pudo confirmar el cambio. Comprueba el estado actualizado antes de volver a intentarlo.',
          });
          // Una respuesta perdida puede corresponder a una escritura confirmada.
          this.refresh();
        },
      });
  }

  private cancelRead(): void {
    this.read?.unsubscribe();
    this.loading.set(false);
    this.synchronized.set(false);
  }
}
