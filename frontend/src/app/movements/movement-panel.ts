import { Component, inject, input } from '@angular/core';
import { MovementsService } from './movements.service';

@Component({
  selector: 'app-movement-panel',
  template: `<section aria-label="Estudiantes activos">
    <h4>Estudiantes activos</h4>
    @for (movement of data.panels()[departmentId()] ?? []; track movement.id) {
      <article class="movement">
        <h5>{{ movement.display_name }}</h5>
        <p>{{ movement.course }} · Paralelo {{ movement.parallel }}</p>
        <p class="state">{{ movement.status === 'EN_CAMINO' ? 'EN CAMINO' : 'EN ATENCIÓN' }}</p>
        <p class="timer" [attr.aria-label]="movement.status === 'EN_CAMINO' ? 'Tiempo de traslado' : 'Tiempo de atención'">{{ data.timer(movement) }}</p>
        <div class="actions">
        @if (movement.status === 'EN_CAMINO') {
          <button type="button" [disabled]="!data.canAct()" (click)="data.transition(movement, 'arrive')">Llegó</button>
          <button type="button" class="secondary" [disabled]="!data.canAct()" (click)="data.transition(movement, 'cancel')">Cancelar envío</button>
        } @else {
          <button type="button" [disabled]="!data.canAct()" (click)="data.transition(movement, 'finish')">Finalizar</button>
        }
        </div>
      </article>
    } @empty { <p>{{ data.synchronized() ? 'Sin estudiantes activos' : 'Consultando estado…' }}</p> }
  </section>`,
  styles: `:host { display:block; margin-top:1.5rem; } h4 { font-size:1rem; } h5 { margin:0; font-size:1.05rem; overflow-wrap:anywhere; }
    .movement { margin:.75rem 0; padding:1rem; border:1px solid #afc8bd; border-radius:8px; background:#f4f9f6; }
    p { overflow-wrap:anywhere; line-height:1.5; } .state { font-weight:700; font-size:.85rem; } .timer { font-size:1.7rem; font-variant-numeric:tabular-nums; margin:.5rem 0; }
    .actions { display:grid; gap:1rem; } button { min-height:48px; padding:.75rem; font:inherit; border:1px solid #1c5d4d; border-radius:6px; background:#1c5d4d; color:white; cursor:pointer; }
    button.secondary { background:white; color:#6e302a; border-color:#98574f; } button:disabled { opacity:.55; cursor:default; } button:focus-visible { outline:3px solid #bb720c; outline-offset:3px; }`,
})
export class MovementPanel {
  readonly departmentId = input.required<number>();
  readonly data = inject(MovementsService);
}
