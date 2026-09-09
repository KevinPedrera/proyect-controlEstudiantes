import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { App } from './app';
import { Department } from './core/department.model';
import { DepartmentsService } from './core/departments.service';
import { SocketService } from './core/socket.service';

const departments: Department[] = [
  { id: 1, name: 'Inspección General', group: 'INSPECCION', active: true, availability: 'DISPONIBLE' },
  { id: 2, name: 'Inspección Primaria', group: 'INSPECCION', active: true, availability: 'DISPONIBLE' },
  { id: 3, name: 'Inspección Bachillerato', group: 'INSPECCION', active: true, availability: 'DISPONIBLE' },
  { id: 4, name: 'DECE Primaria', group: 'DECE', active: true, availability: 'DISPONIBLE' },
  { id: 5, name: 'DECE Secundaria/Bachillerato', group: 'DECE', active: true, availability: 'DISPONIBLE' },
  { id: 6, name: 'Psicopedagogía', group: 'DECE', active: true, availability: 'DISPONIBLE' },
  { id: 7, name: 'Departamento Médico', group: 'SALUD', active: true, availability: 'DISPONIBLE' },
  { id: 8, name: 'Departamento Odontológico', group: 'SALUD', active: false, availability: 'NO_DISPONIBLE' },
];

describe('Arranque y departamentos', () => {
  const socketState = signal<'disconnected' | 'connected'>('disconnected');
  const socket = { state: socketState, connect: vi.fn(), disconnect: vi.fn() };
  const data = {
    departments: signal<Department[]>(departments), loading: signal(false), loaded: signal(true),
    error: signal(''), savingId: signal<number | null>(null), saveError: signal<{ id: number; message: string } | null>(null),
    canChange: signal(true), start: vi.fn(), refresh: vi.fn(), change: vi.fn(),
  };
  let http: HttpTestingController;

  beforeEach(() => {
    socketState.set('disconnected');
    data.departments.set(departments);
    data.loading.set(false); data.loaded.set(true); data.error.set(''); data.savingId.set(null);
    data.saveError.set(null); data.canChange.set(true);
    vi.clearAllMocks();
    TestBed.configureTestingModule({
      imports: [App],
      providers: [
        provideHttpClient(), provideHttpClientTesting(),
        { provide: SocketService, useValue: socket },
        { provide: DepartmentsService, useValue: data },
      ],
    });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('consulta health, inicia departamentos y muestra los ocho en sus tres grupos', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    expect(data.start).toHaveBeenCalledOnce();
    http.expectOne('/api/health').flush({ status: 'ok' });
    socketState.set('connected');
    await fixture.whenStable();
    expect(fixture.nativeElement.querySelector('[data-testid="health"]').textContent).toContain('Conectado');
    expect(fixture.nativeElement.querySelector('[data-testid="websocket"]').textContent).toContain('Conectado');
    expect(fixture.nativeElement.querySelectorAll('.department')).toHaveLength(8);
    expect(fixture.nativeElement.textContent).toContain('Inspección');
    expect(fixture.nativeElement.textContent).toContain('DECE');
    expect(fixture.nativeElement.textContent).toContain('Salud');
    fixture.destroy();
    expect(socket.disconnect).toHaveBeenCalledOnce();
  });

  it('envía la acción concreta, deshabilita mientras guarda y conserva inactivo sin acción', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    http.expectOne('/api/health').flush({ status: 'ok' });
    fixture.detectChanges();
    const first = fixture.nativeElement.querySelector('[data-department-id="1"] button') as HTMLButtonElement;
    first.click();
    expect(data.change).toHaveBeenCalledWith(departments[0], 'NO_DISPONIBLE');
    data.savingId.set(1);
    data.canChange.set(false);
    fixture.detectChanges();
    const saving = fixture.nativeElement.querySelector('[data-department-id="1"] button') as HTMLButtonElement;
    expect(saving.disabled).toBe(true);
    expect(saving.textContent).toContain('Guardando');
    const inactive = fixture.nativeElement.querySelector('[data-department-id="8"] button') as HTMLButtonElement;
    expect(inactive.disabled).toBe(true);
    expect(inactive.textContent).toContain('Marcar disponible');
  });

  it('muestra un error HTTP y permite volver a comprobar', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    http.expectOne('/api/health').error(new ProgressEvent('error'));
    await fixture.whenStable();
    expect(fixture.nativeElement.querySelector('[data-testid="health"]').textContent).toContain('Error de conexión');
    fixture.nativeElement.querySelector('button.secondary').click();
    fixture.detectChanges();
    expect(data.refresh).toHaveBeenCalledOnce();
    expect(socket.connect).toHaveBeenCalledOnce();
    http.expectOne('/api/health').flush({ status: 'ok' });
    await fixture.whenStable();
    expect(fixture.nativeElement.querySelector('[data-testid="health"]').textContent).toContain('Conectado');
  });
});
