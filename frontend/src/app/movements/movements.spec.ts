import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Subject } from 'rxjs';
import { DepartmentsService } from '../core/departments.service';
import { Department } from '../core/department.model';
import { DialogService } from '../core/dialog';
import { SocketEvent, SocketService } from '../core/socket.service';
import { StudentSearchResult } from '../students/student-search.service';
import { Movement, MovementsService, elapsedTime } from './movements.service';
import { Operations } from './operations';
import { MovementPanel } from './movement-panel';

const department: Department = { id: 7, name: 'Área sintética', group: 'SALUD', active: true, availability: 'DISPONIBLE' };
const student: StudentSearchResult = { student_id: 45, first_name:'Alumno', middle_name:null, last_name:'Sintético', second_last_name:null, display_name:'Alumno Sintético', course:'Octavo', parallel:'B' };
const movement: Movement = { id:99, student_id:45, destination_department_id:7, destination_name:department.name,
  display_name:student.display_name, course:'Octavo', parallel:'B', status:'EN_CAMINO', sent_at:'2030-01-01T10:00:00Z', arrived_at:null };
const now = '2030-01-01T10:02:00Z';

describe('Movimientos y recuperación', () => {
  let http: HttpTestingController;
  let service: MovementsService;
  let dialog: DialogService;
  let events: Subject<SocketEvent>;
  const state = signal('connected');
  const departments = signal<Department[]>([department]);
  beforeEach(() => {
    events = new Subject(); state.set('connected'); departments.set([department]);
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(),
      { provide: SocketService, useValue: { events, state } },
      { provide: DepartmentsService, useValue: { departments } },
    ] });
    http=TestBed.inject(HttpTestingController); service=TestBed.inject(MovementsService); dialog=TestBed.inject(DialogService);
    TestBed.tick(); flush();
  });
  afterEach(() => { TestBed.resetTestingModule(); http.verify({ignoreCancelled:true}); });
  function flush(items: Movement[] = [], active: StudentSearchResult['active_movement'] = null) {
    http.expectOne('/api/departments/7/active-movements').flush({items, server_now:now});
    if (service.selected()) http.expectOne('/api/students/45/operational-status').flush({active_movement:active});
  }
  function select() { service.select(student); flush(); }

  it('reconstruye panel y reloj del servidor al abrir sin escribir', () => {
    service.refresh(); flush([movement]);
    expect(service.panels()[7]).toEqual([movement]); expect(service.timer(movement)).toBe('02:00');
    expect(service.canAct()).toBe(true); http.expectNone(r=>r.method!=='GET');
  });
  it('envía con origen y bloquea doble pulsación hasta recuperar el estado', () => {
    select(); service.context.set(department); service.create(department); service.create(department);
    const req=http.expectOne('/api/movements');
    expect(req.request.body).toEqual({student_id:45,destination_department_id:7,origin_department_id:7});
    expect(service.canAct()).toBe(false); req.flush(movement);
    expect(service.canAct()).toBe(false); flush([movement], {status:'EN_CAMINO',destination_name:department.name});
    expect(service.message()).toContain('Estudiante enviado'); expect(service.active()?.status).toBe('EN_CAMINO');
    service.create(department); http.expectNone('/api/movements');
  });
  it('atención directa envía solo estudiante y destino', () => {
    select(); service.context.set(department); service.create(department,true);
    const req=http.expectOne('/api/movements/direct');
    expect(req.request.body).toEqual({student_id:45,destination_department_id:7}); req.flush({...movement,status:'EN_ATENCION'});
    flush([], {status:'EN_ATENCION',destination_name:department.name});
  });
  it('no inicia un movimiento para alumno activo ni destino cerrado', () => {
    service.select(student); flush([], {status:'EN_CAMINO',destination_name:department.name});
    service.create(department); http.expectNone('/api/movements');
    service.active.set(null); service.create({...department,availability:'NO_DISPONIBLE'}); http.expectNone('/api/movements');
  });
  it('Llegó no pide modal y evita doble petición', async () => {
    await service.transition(movement,'arrive'); await service.transition(movement,'arrive');
    expect(dialog.prompt()).toBeNull(); http.expectOne('/api/movements/99/arrive').flush({...movement,status:'EN_ATENCION'});
    flush([{...movement,status:'EN_ATENCION',arrived_at:now}]); expect(service.timer(service.panels()[7]![0])).toBe('00:00');
  });
  for (const action of ['finish','cancel'] as const) {
    it(`${action} requiere confirmación; cancelar el diálogo no escribe`, async () => {
      const pending=service.transition(movement,action); expect(dialog.prompt()).not.toBeNull();
      dialog.answer(false); await pending; http.expectNone(r=>r.method==='POST');
      const accepted=service.transition(movement,action); dialog.answer(true); await accepted;
      http.expectOne(`/api/movements/99/${action}`).flush({...movement,status:action==='finish'?'FINALIZADO':'CANCELADO'});
      flush(); expect(service.panels()[7]).toEqual([]);
    });
  }
  it('desconexión bloquea; reconexión recupera panel y alumno seleccionado', () => {
    select(); state.set('reconnecting'); events.next('disconnected'); expect(service.canAct()).toBe(false);
    state.set('connected'); events.next('connected'); expect(service.canAct()).toBe(false);
    flush([movement], {status:'EN_CAMINO',destination_name:department.name}); expect(service.canAct()).toBe(true);
    events.next('movements_changed'); flush([],null); expect(service.active()).toBeNull();
  });
  it('un evento cancela lecturas anteriores y no permite estado viejo', () => {
    service.refresh(); const old=http.expectOne('/api/departments/7/active-movements');
    events.next('movements_changed'); expect(old.cancelled).toBe(true); flush([movement]);
    expect(()=>old.flush({items:[],server_now:now})).toThrow(); expect(service.panels()[7]).toHaveLength(1);
  });
  for (const kind of ['active','closed','network']) {
    it(`recupera por API y muestra diálogo seguro ante ${kind}`, () => {
      select(); service.create(department); const req=http.expectOne('/api/movements');
      if(kind==='network') req.error(new ProgressEvent('error'));
      else req.flush({detail:kind==='active'?{active_movement:{status:'EN_ATENCION',destination_name:'Área sintética'}}:{message:'Departamento no disponible'}}, {status:409,statusText:'Conflict'});
      flush(); expect(dialog.prompt()).not.toBeNull(); expect(service.saving()).toBe(false);
      expect(dialog.prompt()?.message).not.toMatch(/IntegrityError|409|constraint/);
    });
  }
  it('consulta fallida mantiene acciones bloqueadas hasta reintentar', () => {
    service.refresh(); http.expectOne('/api/departments/7/active-movements').error(new ProgressEvent('error'));
    expect(service.canAct()).toBe(false); expect(service.error()).not.toBe(''); service.refresh(); flush(); expect(service.canAct()).toBe(true);
  });
  it('destinos usan botones grandes, grupos y disponibilidad visible', () => {
    select(); departments.set([department,{...department,id:8,name:'Cerrado',availability:'NO_DISPONIBLE'}]);
    const fixture=TestBed.createComponent(Operations); fixture.detectChanges();
    // The department update causes a fresh authoritative read.
    http.match(r=>r.url.endsWith('/active-movements')).forEach(r=>r.flush({items:[],server_now:now}));
    http.match('/api/students/45/operational-status').forEach(r=>r.flush({active_movement:null})); fixture.detectChanges();
    const buttons=fixture.nativeElement.querySelectorAll('.destination') as NodeListOf<HTMLButtonElement>;
    expect(buttons).toHaveLength(2); expect(buttons[1].disabled).toBe(true);
    expect(buttons[1].classList.contains('unavailable')).toBe(true); expect(buttons[1].textContent).toContain('No disponible');
    buttons[0].click(); fixture.detectChanges(); expect(fixture.nativeElement.textContent).toContain('Enviar a Área sintética');
  });
  it('panel presenta solo su destino y acciones de cada estado en orden recibido', () => {
    service.panels.set({7:[{...movement,id:100,status:'EN_ATENCION',arrived_at:now},movement],8:[{...movement,id:101}]});
    const fixture=TestBed.createComponent(MovementPanel); fixture.componentRef.setInput('departmentId',7); fixture.detectChanges();
    expect(fixture.nativeElement.querySelectorAll('.movement')).toHaveLength(2);
    expect(fixture.nativeElement.querySelectorAll('.state')[0].textContent).toContain('EN ATENCIÓN');
    expect(Array.from(fixture.nativeElement.querySelectorAll('button')).map((b:any)=>b.textContent.trim())).toEqual(['Finalizar','Llegó','Cancelar envío']);
  });
});

describe('Formato de cronómetros', () => {
  for(const [seconds,expected] of [[0,'00:00'],[59,'00:59'],[3599,'59:59'],[3600,'01:00:00'],[3661,'01:01:01']] as const) {
    it(`reconstruye ${seconds} segundos`,()=>expect(elapsedTime('2030-01-01T00:00:00Z',Date.parse('2030-01-01T00:00:00Z')+seconds*1000)).toBe(expected));
  }
});
