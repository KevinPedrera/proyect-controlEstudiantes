import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { StudentSearch } from './student-search';
import { StudentSearchResult } from './student-search.service';

const student: StudentSearchResult = { student_id:987654, first_name:'José', middle_name:'Juan', last_name:'Pérez', second_last_name:'López', display_name:'José Juan Pérez López', course:'Octavo', parallel:'B' };

describe('Búsqueda y selección de estudiantes', () => {
  let http: HttpTestingController;
  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({imports:[StudentSearch],providers:[provideHttpClient(),provideHttpClientTesting()]});
    http=TestBed.inject(HttpTestingController);
  });
  afterEach(() => { http.verify({ignoreCancelled:true}); TestBed.resetTestingModule(); vi.useRealTimers(); });
  function setup() { const f=TestBed.createComponent(StudentSearch); f.detectChanges(); return f; }
  function type(f:ReturnType<typeof setup>, text:string) {
    const input=f.nativeElement.querySelector('input') as HTMLInputElement;
    input.value=text; input.dispatchEvent(new Event('input')); f.detectChanges(); return input;
  }
  function request(q:string) { return http.expectOne(r => r.url==='/api/students/search' && r.params.get('q')===q && r.params.get('limit')==='5'); }
  function results(f:ReturnType<typeof setup>, rows=[student]) {
    type(f,'jose'); vi.advanceTimersByTime(300); request('jose').flush(rows); f.detectChanges();
  }

  it('no consulta inicialmente ni con menos de dos letras útiles', () => {
    const f=setup();
    for (const value of ['', 'a', ' á ', '  ', '--', '99999']) {
      type(f,value); vi.advanceTimersByTime(500);
      http.expectNone(r=>r.url==='/api/students/search');
    }
    expect(f.nativeElement.textContent).toContain('Escribe al menos 2 caracteres');
  });
  it('espera 300 ms desde la última pulsación y conserva el texto enviado', () => {
    const f=setup(); type(f,'jo'); vi.advanceTimersByTime(299); http.expectNone(r=>true);
    type(f,' JOSÉ '); vi.advanceTimersByTime(299); http.expectNone(r=>true);
    vi.advanceTimersByTime(1); request(' JOSÉ ').flush([]);
  });
  it('cancela HTTP inmediatamente al escribir, antes del nuevo debounce', () => {
    const f=setup(); type(f,'jose'); vi.advanceTimersByTime(300); const old=request('jose');
    type(f,'maria'); expect(old.cancelled).toBe(true);
    vi.advanceTimersByTime(300); request('maria').flush([{...student, display_name:'María Sintética'}]); f.detectChanges();
    expect(()=>old.flush([student])).toThrow();
    expect(f.nativeElement.textContent).toContain('María Sintética');
    expect(f.nativeElement.textContent).not.toContain(student.display_name);
  });
  it('limpiar una consulta cancela la solicitud y retira resultados antiguos', () => {
    const f=setup(); results(f); type(f,'otro'); vi.advanceTimersByTime(300); const old=request('otro');
    type(f,''); expect(old.cancelled).toBe(true); expect(f.nativeElement.querySelectorAll('.result').length).toBe(0);
  });
  it('muestra buscando, resultados y campos mínimos sin ID visible', () => {
    const f=setup(); type(f,'jose'); vi.advanceTimersByTime(300); f.detectChanges();
    expect(f.nativeElement.textContent).toContain('Buscando');
    request('jose').flush([student]); f.detectChanges();
    const text=f.nativeElement.textContent;
    expect(text).toContain(student.display_name); expect(text).toContain('Octavo · Paralelo B');
    expect(text).not.toContain('987654'); expect(text).not.toMatch(/documento|teléfono|representante|contacto/i);
  });
  it('representa consulta sin resultados', () => {
    const f=setup(); results(f,[]); expect(f.nativeElement.textContent).toContain('No encontramos estudiantes');
  });
  it('representa error sin detalles técnicos y permite reintentar', () => {
    const f=setup(); type(f,'jose'); vi.advanceTimersByTime(300);
    request('jose').flush({detail:'INTERNAL PRIVATE DATA'},{status:500,statusText:'Error'}); f.detectChanges();
    expect(f.nativeElement.textContent).toContain('No pudimos realizar la búsqueda');
    expect(f.nativeElement.textContent).not.toContain('INTERNAL');
    f.nativeElement.querySelector('.retry').click(); vi.advanceTimersByTime(300); request('jose').flush([student]); f.detectChanges();
    expect(f.nativeElement.querySelectorAll('.result').length).toBe(1);
  });
  it('muestra error por timeout y puede buscar de nuevo', () => {
    const f=setup(); type(f,'jose'); vi.advanceTimersByTime(300); const pending=request('jose');
    vi.advanceTimersByTime(10000); f.detectChanges(); expect(pending.cancelled).toBe(true);
    expect(f.nativeElement.textContent).toContain('No pudimos realizar la búsqueda');
    type(f,'perez'); vi.advanceTimersByTime(300); request('perez').flush([]);
  });
  it('mantiene un máximo defensivo de cinco resultados visibles', () => {
    const f=setup(); results(f,Array.from({length:8},(_,i)=>({...student,student_id:i+1})));
    expect(f.nativeElement.querySelectorAll('.result').length).toBe(5);
  });
  it('selecciona y emite el estudiante, luego permite cambiar con foco en búsqueda', () => {
    const f=setup(); const selected=vi.fn(); f.componentInstance.selectionChange.subscribe(selected); results(f);
    f.nativeElement.querySelector('.result').click(); f.detectChanges();
    expect(selected).toHaveBeenCalledWith(student);
    expect(f.nativeElement.querySelectorAll('.result').length).toBe(0);
    expect(f.nativeElement.textContent).toContain('Estudiante seleccionado');
    expect(document.activeElement).toBe(f.nativeElement.querySelector('.change'));
    f.nativeElement.querySelector('.change').click(); f.detectChanges();
    expect(selected).toHaveBeenLastCalledWith(null);
    expect(document.activeElement).toBe(f.nativeElement.querySelector('input'));
    expect(f.nativeElement.querySelector('input').value).toBe('');
  });
  it('Escape cierra resultados y devuelve el foco sin acciones operacionales', () => {
    const f=setup(); results(f); const button=f.nativeElement.querySelector('.result') as HTMLButtonElement;
    expect(button.type).toBe('button'); expect(button.tabIndex).toBe(0); button.focus();
    button.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true})); f.detectChanges();
    expect(f.nativeElement.querySelectorAll('.result').length).toBe(0);
    expect(document.activeElement).toBe(f.nativeElement.querySelector('input'));
    expect(f.nativeElement.textContent).not.toMatch(/Enviar|Llegó|Atender|Finalizar/);
  });
  it('usa label y anuncio accesibles, sin tabla ni combobox incompleto', () => {
    const f=setup(); const input=f.nativeElement.querySelector('input') as HTMLInputElement;
    expect(f.nativeElement.querySelector('label').htmlFor).toBe(input.id);
    expect(input.getAttribute('aria-describedby')).toContain('-status');
    expect(f.nativeElement.querySelector('[role=status]')).not.toBeNull();
    expect(f.nativeElement.querySelector('table,[role=combobox]')).toBeNull();
  });
  it('destruir el componente cancela HTTP y los temporizadores', () => {
    const f=setup(); type(f,'jose'); vi.advanceTimersByTime(300); const pending=request('jose');
    f.destroy(); expect(pending.cancelled).toBe(true);
  });
});
