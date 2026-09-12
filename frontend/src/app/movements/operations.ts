import { Component, computed, inject, signal } from '@angular/core';
import { DepartmentsService } from '../core/departments.service';
import { Department } from '../core/department.model';
import { StudentSearch } from '../students/student-search';
import { MovementsService } from './movements.service';

@Component({
  selector: 'app-operations', imports: [StudentSearch],
  template: `
    <section aria-label="Gestión del estudiante">
      <app-student-search (selectionChange)="data.select($event); destinationId.set(null)" />
      <details><summary>Departamento desde el que operas: {{ data.context()?.name ?? 'Sin origen indicado' }}</summary>
        <p>Opcional para enviar. Selecciónalo para iniciar una atención directa aquí.</p>
        <div class="choices">
          <button type="button" [attr.aria-pressed]="!data.context()" (click)="data.context.set(null)">Sin origen indicado</button>
          @for (department of departments.departments(); track department.id) {
            @if (department.active) { <button type="button" [attr.aria-pressed]="data.context()?.id === department.id"
              (click)="data.context.set(department)">{{ department.name }}</button> }
          }
        </div>
      </details>
      @if (data.selected()) {
        @if (data.active(); as active) {
          <p class="notice" role="status">{{ active.status === 'EN_CAMINO' ? 'En camino' : 'En atención' }} · {{ active.destination_name }}.
            No puede iniciar otro movimiento mientras esté activo.</p>
        } @else {
          <h2>Elegir destino</h2>
          <div class="destinations">
          @for (group of groups; track group.key) {
            <section><h3>{{ group.label }}</h3><div class="choices">
            @for (department of departments.departments(); track department.id) {
              @if (department.group === group.key) {
                <button type="button" class="destination" [class.unavailable]="!available(department)"
                  [disabled]="!available(department) || !data.canAct()"
                  [attr.aria-pressed]="destinationId() === department.id" (click)="destinationId.set(department.id)">
                  <strong>{{ department.name }}</strong><span>{{ available(department) ? 'Disponible' : 'No disponible' }}</span>
                </button>
              }
            }</div></section>
          }</div>
          @if (destination(); as target) {
            <button type="button" class="primary" [disabled]="!data.canAct() || !available(target)" (click)="data.create(target)">
              {{ data.saving() ? 'Guardando…' : 'Enviar a ' + target.name }}</button>
          }
          @if (context(); as current) {
            <button type="button" class="primary" [disabled]="!data.canAct() || !available(current)" (click)="data.create(current, true)">
              Iniciar atención directa en {{ current.name }}</button>
          }
        }
      }
      @if (data.message()) { <p class="notice" role="status">{{ data.message() }}</p> }
      @if (data.error()) { <p role="alert">{{ data.error() }}</p><button type="button" (click)="data.refresh()">Actualizar movimientos</button> }
      @if (!data.synchronized()) { <p role="status">Actualizando estado operativo. Las acciones se habilitarán al recuperar la conexión.</p> }
    </section>`,
  styleUrl: './operations.css',
})
export class Operations {
  readonly data = inject(MovementsService);
  readonly departments = inject(DepartmentsService);
  readonly destinationId = signal<number | null>(null);
  readonly destination = computed(() => this.departments.departments().find(d => d.id === this.destinationId()));
  readonly context = computed(() => this.departments.departments().find(d => d.id === this.data.context()?.id));
  readonly groups = [{ key: 'INSPECCION', label: 'Inspección' }, { key: 'DECE', label: 'DECE' }, { key: 'SALUD', label: 'Salud' }];
  available(department: Department): boolean { return department.active && department.availability === 'DISPONIBLE'; }
}
