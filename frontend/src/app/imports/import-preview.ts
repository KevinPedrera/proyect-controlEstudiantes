import { Component, DestroyRef, inject, signal } from '@angular/core';
import { DatePipe, KeyValuePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Observable, Subscription } from 'rxjs';
import { Candidate, Category, ImportsService, Person, Preview, PreviewRow, Scope } from './imports.service';

@Component({
  selector: 'app-import-preview', imports: [DatePipe, KeyValuePipe],
  templateUrl: './import-preview.html', styleUrl: './import-preview.css',
})
export class ImportPreview {
  private readonly api = inject(ImportsService);
  private readonly destroy = inject(DestroyRef);
  private request?: Subscription;
  protected file: File | null = null;
  protected scope: Scope | '' = '';
  protected recoveryId = '';
  protected readonly loading = signal(false);
  protected readonly error = signal('');
  protected readonly preview = signal<Preview | null>(null);
  protected readonly rows = signal<PreviewRow[]>([]);
  protected readonly absences = signal<Candidate[]>([]);
  protected readonly page = signal(1);
  protected readonly mode = signal<'rows' | 'absences'>('rows');
  protected readonly total = signal(0);
  protected readonly categories: Category[] = ['NUEVO','SIN_CAMBIOS','ACTUALIZACION','REQUIERE_REVISION'];
  private expiryTimer?: ReturnType<typeof setTimeout>;
  constructor() { this.destroy.onDestroy(() => { this.request?.unsubscribe(); clearTimeout(this.expiryTimer); }); }

  protected selectFile(event: Event) { this.file = (event.target as HTMLInputElement).files?.[0] ?? null; }
  protected selectScope(event: Event) { this.scope = (event.target as HTMLSelectElement).value as Scope | ''; }
  protected recoveryChanged(event: Event) { this.recoveryId = (event.target as HTMLInputElement).value.trim(); }
  protected create() {
    if (!this.file || !this.scope || this.loading()) return;
    if (!this.file.name.toLowerCase().endsWith('.xlsx')) { this.error.set('Selecciona un archivo .xlsx.'); return; }
    if (this.file.size > 5 * 1024 * 1024) { this.error.set('El archivo supera el límite de 5 MB.'); return; }
    this.loadSummary(this.api.create(this.file, this.scope));
  }
  protected recover() {
    if (!this.recoveryId || this.loading()) return;
    this.loadSummary(this.api.get(this.recoveryId));
  }
  private loadSummary(source: Observable<Preview>) {
    this.request?.unsubscribe(); clearTimeout(this.expiryTimer);
    this.preview.set(null); this.rows.set([]); this.absences.set([]);
    this.loading.set(true); this.error.set('');
    this.request = source.pipe(takeUntilDestroyed(this.destroy)).subscribe({
      next: preview => {
        const remaining = Date.parse(preview.expires_at) - Date.now();
        if (remaining <= 0) { this.expire(); return; }
        this.preview.set(preview); this.recoveryId = preview.id;
        this.expiryTimer = setTimeout(() => this.expire(), remaining);
        this.mode.set('rows'); this.loadPage(1);
      }, error: error => this.fail(error),
    });
  }
  protected switchMode(mode: 'rows' | 'absences') { this.mode.set(mode); this.loadPage(1); }
  protected loadPage(page: number) {
    const preview = this.preview(); if (!preview) return;
    this.request?.unsubscribe(); this.loading.set(true); this.error.set('');
    this.rows.set([]); this.absences.set([]);
    if (this.mode() === 'rows') {
      this.request = this.api.rows(preview.id, page).pipe(takeUntilDestroyed(this.destroy)).subscribe({
        next: result => { this.rows.set(result.items); this.total.set(result.total); this.page.set(result.page); this.loading.set(false); },
        error: error => this.fail(error),
      });
    } else {
      this.request = this.api.absences(preview.id, page).pipe(takeUntilDestroyed(this.destroy)).subscribe({
        next: result => { this.absences.set(result.items); this.total.set(result.total); this.page.set(result.page); this.loading.set(false); },
        error: error => this.fail(error),
      });
    }
  }
  private expire() {
    this.request?.unsubscribe(); this.preview.set(null); this.rows.set([]); this.absences.set([]); this.loading.set(false);
    this.error.set('La previsualización venció. Genera una nueva.');
  }
  private fail(error: HttpErrorResponse) {
    this.loading.set(false);
    if (error.status === 410) { this.expire(); return; }
    const detail = error.error?.detail;
    this.error.set(typeof detail === 'string' ? detail : 'No se pudo completar la consulta. Reintenta cuando se recupere la conexión.');
  }
  protected fullName(person: Person) {
    return ['first_name','middle_name','last_name','second_last_name'].map(k => person[k]).filter(Boolean).join(' ');
  }
  protected label(key: string): string {
    return ({ first_name:'Nombre', middle_name:'Segundo nombre', last_name:'Apellido', second_last_name:'Segundo apellido', document:'Documento', document_type:'Tipo de documento', course:'Curso', parallel:'Paralelo', contacts:'Contactos', relationship:'Parentesco', mobile_phone:'Teléfono celular', home_phone:'Teléfono casa/domicilio', work_phone:'Teléfono trabajo', type:'Función', source_slot:'Bloque de origen', NUEVO:'Nuevo', SIN_CAMBIOS:'Sin cambios', ACTUALIZACION:'Actualización', REQUIERE_REVISION:'Requiere revisión', DATOS_PERSONALES:'Datos personales', DOCUMENTO:'Documento', CURSO:'Curso', PARALELO:'Paralelo', CONTACTOS:'Contactos', REPRESENTANTE_LEGAL:'Representante legal', PADRE:'Padre', MADRE:'Madre', EMERGENCIA:'Emergencia', CONSERVAR_ACTUAL:'Conservar el valor actual; el vacío no lo borra', REVISAR_GUION:'Revisar el guion recibido', PROPONER_NUEVA_VERSION:'Proponer nueva versión académica', PROPONER_ACTUALIZACION:'Proponer actualización', REVISAR_CONTACTOS_SIN_BORRAR_VACIOS:'Revisar contactos; no borrar valores por vacíos' } as Record<string,string>)[key] ?? key;
  }
  protected value(value: unknown): string {
    if (value == null || value === '') return 'Sin registrar';
    if (Array.isArray(value)) return value.length ? value.map(item => this.value(item)).join('\n\n') : 'Sin registrar';
    if (typeof value === 'object') return Object.entries(value).filter(([key]) => key !== 'source_slot').map(([key,v]) => `${this.label(key)}: ${this.value(v)}`).join('\n');
    return this.label(String(value));
  }
}
