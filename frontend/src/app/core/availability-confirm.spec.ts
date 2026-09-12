import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Subject } from 'rxjs';
import { DepartmentsService } from './departments.service';
import { Department } from './department.model';
import { DialogService } from './dialog';
import { SocketService } from './socket.service';

describe('Disponibilidad y confirmación autoritativa',()=>{
  const department: Department={id:1,name:'Área sintética',group:'DECE',active:true,availability:'DISPONIBLE'};
  let http:HttpTestingController; let service:DepartmentsService; let dialog:DialogService;
  beforeEach(()=>{
    TestBed.configureTestingModule({providers:[provideHttpClient(),provideHttpClientTesting(),
      {provide:SocketService,useValue:{state:signal('connected'),events:new Subject(),connect:vi.fn()}}]});
    http=TestBed.inject(HttpTestingController); service=TestBed.inject(DepartmentsService); dialog=TestBed.inject(DialogService);
    service.start(); http.expectOne('/api/departments').flush([department]);
  });
  afterEach(()=>{http.verify();TestBed.resetTestingModule();});
  function warn(counts={en_camino:2,en_atencion:1}) {
    http.expectOne('/api/departments/1/availability').flush({detail:{code:'CONFIRMAR_ACTIVOS',active_counts:counts}}, {status:409,statusText:'Conflict'});
  }
  it('bloquea doble clic, pide confirmar recuentos y repite si cambian',async()=>{
    service.change(department,'NO_DISPONIBLE'); service.change(department,'NO_DISPONIBLE'); warn();
    expect(dialog.prompt()?.message).toContain('2 en camino'); expect(service.canChange()).toBe(false);
    dialog.answer(true); await Promise.resolve();
    const req=http.expectOne('/api/departments/1/availability');
    expect(req.request.body.confirmed_active_counts).toEqual({en_camino:2,en_atencion:1});
    req.flush({detail:{code:'CONFIRMAR_ACTIVOS',active_counts:{en_camino:1,en_atencion:2}}},{status:409,statusText:'Conflict'});
    expect(dialog.prompt()?.message).toContain('2 en atención'); dialog.answer(true); await Promise.resolve();
    const last=http.expectOne('/api/departments/1/availability'); expect(last.request.body.confirmed_active_counts.en_atencion).toBe(2);
    last.flush({...department,availability:'NO_DISPONIBLE'}); http.expectOne('/api/departments').flush([{...department,availability:'NO_DISPONIBLE'}]);
    expect(service.departments()[0].availability).toBe('NO_DISPONIBLE');
  });
  it('cancelar advertencia conserva disponibilidad y consulta estado',async()=>{
    service.change(department,'NO_DISPONIBLE'); warn(); dialog.answer(false); await Promise.resolve();
    http.expectOne('/api/departments').flush([department]); expect(service.departments()[0].availability).toBe('DISPONIBLE');
  });
});
