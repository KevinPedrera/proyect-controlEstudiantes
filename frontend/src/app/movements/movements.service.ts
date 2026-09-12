import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { DestroyRef, Injectable, computed, effect, inject, signal, untracked } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subscription, forkJoin, of, timeout } from 'rxjs';
import { DepartmentsService } from '../core/departments.service';
import { Department } from '../core/department.model';
import { DialogService } from '../core/dialog';
import { SocketService } from '../core/socket.service';
import { ActiveMovement, StudentSearchResult } from '../students/student-search.service';

export interface Movement {
  id: number; student_id: number; destination_department_id: number; destination_name: string;
  display_name: string; course: string; parallel: string;
  status: 'EN_CAMINO' | 'EN_ATENCION' | 'FINALIZADO' | 'CANCELADO';
  sent_at: string | null; arrived_at: string | null;
}
interface Panel { items: Movement[]; server_now: string; }

export function elapsedTime(start: string | null, now: number): string {
  const seconds = Math.max(0, Math.floor((now - Date.parse(start ?? '')) / 1000));
  if (!Number.isFinite(seconds)) return '—';
  const pad = (n: number) => String(n).padStart(2, '0');
  return seconds >= 3600 ? `${pad(Math.floor(seconds / 3600))}:${pad(Math.floor(seconds / 60) % 60)}:${pad(seconds % 60)}`
    : `${pad(Math.floor(seconds / 60))}:${pad(seconds % 60)}`;
}

@Injectable({ providedIn: 'root' })
export class MovementsService {
  private readonly http = inject(HttpClient);
  private readonly socket = inject(SocketService);
  private readonly departments = inject(DepartmentsService);
  private readonly dialog = inject(DialogService);
  private readonly destroy = inject(DestroyRef);
  readonly selected = signal<StudentSearchResult | null>(null);
  readonly active = signal<ActiveMovement | null>(null);
  readonly context = signal<Department | null>(null);
  readonly panels = signal<Partial<Record<number, Movement[]>>>({});
  readonly synchronized = signal(false);
  readonly saving = signal(false);
  readonly message = signal('');
  readonly error = signal('');
  readonly now = signal(Date.now());
  readonly canAct = computed(() => this.synchronized() && this.socket.state() === 'connected' && !this.saving());
  private read?: Subscription;
  private serverTime = Date.now();
  private receivedAt = performance.now();

  constructor() {
    effect(() => {
      this.departments.departments();
      untracked(() => this.refresh());
    });
    this.socket.events.pipe(takeUntilDestroyed()).subscribe(event => {
      if (event === 'disconnected') { this.read?.unsubscribe(); this.synchronized.set(false); }
      else this.refresh();
    });
    const tick = setInterval(() => this.now.set(this.serverTime + performance.now() - this.receivedAt), 1000);
    this.destroy.onDestroy(() => { clearInterval(tick); this.read?.unsubscribe(); });
  }

  select(student: StudentSearchResult | null): void {
    this.selected.set(student); this.active.set(student?.active_movement ?? null);
    this.message.set(''); this.refresh();
  }

  refresh(): void {
    this.read?.unsubscribe(); this.synchronized.set(false);
    const departments = this.departments.departments();
    const student = this.selected();
    const panels = departments.length ? forkJoin(departments.map(d =>
      this.http.get<Panel>(`/api/departments/${d.id}/active-movements`).pipe(timeout(10000)))) : of([]);
    const selected = student ? this.http.get<{ active_movement: ActiveMovement | null }>(
      `/api/students/${student.student_id}/operational-status`).pipe(timeout(10000)) : of(null);
    this.read = forkJoin({ panels, selected }).pipe(takeUntilDestroyed(this.destroy)).subscribe({
      next: result => {
        this.panels.set(Object.fromEntries(result.panels.map((panel, i) => [departments[i].id, panel.items])));
        this.active.set(result.selected?.active_movement ?? null);
        if (result.panels.length) {
          this.serverTime = Date.parse(result.panels[0].server_now); this.receivedAt = performance.now();
          this.now.set(this.serverTime);
        }
        this.error.set(''); this.synchronized.set(this.socket.state() === 'connected');
      },
      error: () => { this.error.set('No se pudo actualizar el estado operativo. Reintenta antes de continuar.'); },
    });
  }

  create(destination: Department, direct = false): void {
    const student = this.selected();
    if (!student || this.active() || !this.canAct() || !destination.active || destination.availability !== 'DISPONIBLE') return;
    const body = direct ? { student_id: student.student_id, destination_department_id: destination.id }
      : { student_id: student.student_id, destination_department_id: destination.id, origin_department_id: this.context()?.id ?? null };
    this.write('/api/movements' + (direct ? '/direct' : ''), body,
      direct ? `Atención iniciada en ${destination.name}` : `Estudiante enviado a ${destination.name}`);
  }

  async transition(movement: Movement, action: 'arrive' | 'finish' | 'cancel'): Promise<void> {
    if (!this.canAct()) return;
    if (action !== 'arrive') {
      const accepted = await this.dialog.ask({
        title: action === 'finish' ? 'Finalizar atención' : 'Cancelar envío',
        message: `${action === 'finish' ? '¿Finalizar la atención' : '¿Cancelar el envío'} de ${movement.display_name}?`,
        confirm: action === 'finish' ? 'Finalizar' : 'Cancelar envío',
      });
      if (!accepted || !this.canAct()) return;
    }
    this.write(`/api/movements/${movement.id}/${action}`, {},
      action === 'arrive' ? 'Llegada registrada' : action === 'finish' ? 'Atención finalizada' : 'Envío cancelado');
  }

  timer(movement: Movement): string {
    return elapsedTime(movement.status === 'EN_CAMINO' ? movement.sent_at : movement.arrived_at, this.now());
  }

  private write(url: string, body: object, success: string): void {
    this.saving.set(true); this.message.set('');
    this.http.post<Movement>(url, body).pipe(timeout(10000), takeUntilDestroyed(this.destroy)).subscribe({
      next: () => { this.saving.set(false); this.message.set(success); this.refresh(); },
      error: (error: HttpErrorResponse) => {
        this.saving.set(false); this.refresh();
        const detail = error.error?.detail;
        const active = detail?.active_movement;
        const description = active ? `Actualmente: ${active.status === 'EN_CAMINO' ? 'En camino' : 'En atención'} · ${active.destination_name}. No se creó otro movimiento.`
          : detail?.message ?? 'No se pudo confirmar el resultado. Consulta el estado actualizado antes de reintentar.';
        void this.dialog.ask({ title: active ? 'El estudiante ya tiene un movimiento activo' : 'No se pudo completar la acción', message: description });
      },
    });
  }
}
