import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Subject } from 'rxjs';
import { Department } from './department.model';
import { DepartmentsService } from './departments.service';
import { SocketEvent, SocketService } from './socket.service';

const one: Department = { id: 1, name: 'Inspección General', group: 'INSPECCION', active: true, availability: 'DISPONIBLE' };

describe('DepartmentsService', () => {
  const state = signal<'disconnected' | 'connected'>('disconnected');
  let events: Subject<SocketEvent>;
  let socket: { state: typeof state; events: Subject<SocketEvent>; connect: ReturnType<typeof vi.fn> };
  let service: DepartmentsService;
  let http: HttpTestingController;

  beforeEach(() => {
    events = new Subject<SocketEvent>();
    state.set('disconnected');
    socket = { state, events, connect: vi.fn() };
    TestBed.configureTestingModule({ providers: [
      provideHttpClient(), provideHttpClientTesting(), { provide: SocketService, useValue: socket },
    ] });
    service = TestBed.inject(DepartmentsService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => { http.verify(); TestBed.resetTestingModule(); });

  it('consulta por HTTP aunque tiempo real esté desconectado', () => {
    service.start();
    expect(socket.connect).toHaveBeenCalledOnce();
    const request = http.expectOne('/api/departments');
    expect(request.request.method).toBe('GET');
    request.flush([one]);
    expect(service.departments()).toEqual([one]);
    expect(service.canChange()).toBe(false);
  });

  it('recupera el listado al conectar, recibir un aviso y reconectar', () => {
    service.start();
    http.expectOne('/api/departments').flush([one]);
    state.set('connected'); events.next('connected');
    http.expectOne('/api/departments').flush([one]);
    expect(service.canChange()).toBe(true);
    events.next('departments_changed');
    http.expectOne('/api/departments').flush([{ ...one, availability: 'NO_DISPONIBLE' }]);
    expect(service.departments()[0].availability).toBe('NO_DISPONIBLE');
    events.next('disconnected');
    expect(service.canChange()).toBe(false);
    state.set('connected'); events.next('connected');
    http.expectOne('/api/departments').flush([one]);
  });

  it('envía PUT explícito y recupera el estado confirmado', () => {
    state.set('connected');
    service.start();
    http.expectOne('/api/departments').flush([one]);
    service.change(one, 'NO_DISPONIBLE');
    const request = http.expectOne('/api/departments/1/availability');
    expect(request.request.method).toBe('PUT');
    expect(request.request.body).toEqual({ availability: 'NO_DISPONIBLE' });
    request.flush({ ...one, availability: 'NO_DISPONIBLE' });
    http.expectOne('/api/departments').flush([{ ...one, availability: 'NO_DISPONIBLE' }]);
    expect(service.departments()[0].availability).toBe('NO_DISPONIBLE');
  });

  it('recupera estado y muestra error si la actualización no puede confirmarse', () => {
    state.set('connected');
    service.start();
    http.expectOne('/api/departments').flush([one]);
    service.change(one, 'NO_DISPONIBLE');
    http.expectOne('/api/departments/1/availability').error(new ProgressEvent('error'));
    expect(service.saveError()?.id).toBe(1);
    http.expectOne('/api/departments').flush([{ ...one, availability: 'NO_DISPONIBLE' }]);
    expect(service.departments()[0].availability).toBe('NO_DISPONIBLE');
  });

  it('cancela la lectura antigua antes de aplicar un aviso posterior', () => {
    service.start();
    const stale = http.expectOne('/api/departments');
    events.next('departments_changed');
    expect(stale.cancelled).toBe(true);
    const current = http.expectOne('/api/departments');
    current.flush([{ ...one, availability: 'NO_DISPONIBLE' }]);
    expect(service.departments()[0].availability).toBe('NO_DISPONIBLE');
  });
});
