import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { ImportPreview } from './import-preview';
import { Preview, PreviewRow } from './imports.service';

const id = '11111111-1111-4111-8111-111111111111';
const batch: Preview = { id, status:'PREVIEW', scope:'SUBCONJUNTO', institution:'Colegio sintético', academic_period:'Año Lectivo 2026 - 2027', expires_at:'2099-01-01T00:00:00Z', total:11, counts:{NUEVO:10,SIN_CAMBIOS:0,ACTUALIZACION:0,REQUIERE_REVISION:1}, warnings:[], quality_warning_count:1, absence_count:0, absences_calculated:false };
const row: PreviewRow = { row_number:8, sheet:'Listado', student:{first_name:'Ana',middle_name:null,last_name:'Pérez',course:'Séptimo',parallel:'A',document:null},contacts:[],category:'NUEVO',tags:[],warnings:[{code:'LITERAL_DASH',cell:'H8',message:'Guion literal "-" conservado como dato recibido.'}],errors:[],conflicts:[],candidates:[],differences:[] };

describe('Previsualización de importación', () => {
  let http: HttpTestingController;
  beforeEach(() => { TestBed.configureTestingModule({imports:[ImportPreview],providers:[provideHttpClient(),provideHttpClientTesting()]}); http=TestBed.inject(HttpTestingController); });
  afterEach(() => { http.verify(); TestBed.resetTestingModule(); });
  function setup() { const fixture=TestBed.createComponent(ImportPreview); fixture.detectChanges(); return fixture; }
  function choose(fixture: ReturnType<typeof setup>, scope='SUBCONJUNTO', name='test.xlsx') {
    const input=fixture.nativeElement.querySelector('input[type=file]') as HTMLInputElement;
    Object.defineProperty(input,'files',{value:[new File(['synthetic'],name)],configurable:true});input.dispatchEvent(new Event('change'));
    const select=fixture.nativeElement.querySelector('select') as HTMLSelectElement;select.value=scope;select.dispatchEvent(new Event('change'));fixture.detectChanges();
  }
  function create(fixture: ReturnType<typeof setup>, data=batch, previewRow=row) {
    choose(fixture); fixture.nativeElement.querySelector('button').click(); fixture.detectChanges();
    const request=http.expectOne('/api/student-imports/preview');
    expect(request.request.method).toBe('POST');expect(request.request.body.get('scope')).toBe('SUBCONJUNTO');
    request.flush({...data,expires_at:new Date(Date.now()+86400000).toISOString()});
    http.expectOne(`/api/student-imports/${id}/rows?page=1&page_size=10`).flush({items:[previewRow],total:11,page:1,page_size:10});fixture.detectChanges();
  }
  const confirmableBatch: Preview = {
    ...batch, counts:{NUEVO:10,SIN_CAMBIOS:0,ACTUALIZACION:0,REQUIERE_REVISION:0}, contract_version:'3B-1', confirmable:true,
    configuration:{institution:'Colegio sintético',academic_period:{label:'Año Lectivo 2026 - 2027',period_key:'2026-2027'},action:'NONE',requires_acceptance:false},
  };
  function actionButton(fixture: ReturnType<typeof setup>, text: string) {
    return Array.from(fixture.nativeElement.querySelectorAll('button')).find(item => (item as HTMLButtonElement).textContent?.includes(text)) as HTMLButtonElement;
  }
  function acceptConfirmation(fixture: ReturnType<typeof setup>) {
    const checkbox = fixture.nativeElement.querySelector('.confirmation input[type=checkbox]') as HTMLInputElement;
    checkbox.checked=true; checkbox.dispatchEvent(new Event('change')); fixture.detectChanges();
  }
  it('exige archivo y alcance explícito; no muestra resolución individual', () => {
    const fixture=setup(); expect(fixture.nativeElement.querySelector('button').disabled).toBe(true);
    expect(fixture.nativeElement.textContent).toContain('todavía no se han aplicado cambios');
    const buttons=Array.from(fixture.nativeElement.querySelectorAll('button')) as HTMLButtonElement[];
    expect(buttons.some(b=>/vincular|resolver/i.test(b.textContent ?? ''))).toBe(false);
  });
  it('muestra loading, metadatos, categorías, advertencias y NULL amigable', () => {
    const fixture=setup();create(fixture);
    const text=fixture.nativeElement.textContent;
    expect(text).toContain('Colegio sintético');expect(text).toContain('2026 - 2027');
    expect(text).toContain('Requiere revisión');expect(text).toContain('Sin registrar');
    expect(text).not.toContain('NULL');expect(text).not.toContain('Ana Sin registrar Pérez');
  });
  it('pagina mediante backend y no descarga todo el alumnado', () => {
    const fixture=setup();create(fixture);
    const next=Array.from(fixture.nativeElement.querySelectorAll('button')).find(b=>(b as HTMLButtonElement).textContent==='Siguiente') as HTMLButtonElement;
    next.click();fixture.detectChanges();expect(fixture.nativeElement.textContent).toContain('Procesando');
    http.expectOne(`/api/student-imports/${id}/rows?page=2&page_size=10`).flush({items:[],total:11,page:2,page_size:10});fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Página 2');
  });
  it('muestra Nuevo y advertencias sin inventar razones bloqueantes', () => {
    const fixture=setup();
    create(fixture, {...batch,rows_with_warnings:1,rows_with_blocking_reasons:0}, {...row,blocking_review_reasons:[],contacts:[{type:'REPRESENTANTE_LEGAL',middle_name:'-'}]});
    const article=fixture.nativeElement.querySelector('article');
    expect(article.textContent).toContain('Nuevo');
    expect(article.textContent).toContain('Advertencias de calidad');
    expect(article.textContent).toContain('Segundo nombre: -');
    expect(article.textContent).not.toContain('Requiere revisión');
    expect(article.textContent).not.toContain('Razones que requieren una decisión');
    expect(fixture.nativeElement.textContent).toContain('Registros con razones bloqueantes: 0');
  });
  it('separa advertencias y razones bloqueantes recibidas del backend', () => {
    const fixture=setup();
    create(fixture,batch,{...row,category:'REQUIERE_REVISION',tags:['REQUIERE_REVISION_IDENTIDAD'],blocking_review_reasons:['Correspondencia ambigua.'],differences:[
      {field:'contacts',current:'Actual 1',incoming:'Recibido 1',action:'REVISAR_CONTACTOS_SIN_BORRAR_VACIOS'},
      {field:'contacts',current:'Actual 2',incoming:'Recibido 2',action:'REVISAR_CONTACTOS_SIN_BORRAR_VACIOS'},
    ]});
    const article=fixture.nativeElement.querySelector('article');
    expect(article.textContent).toContain('Requiere revisión');
    expect(article.textContent).toContain('Advertencias de calidad');
    expect(article.textContent).toContain('Razones que requieren una decisión');
    expect(article.textContent).toContain('Correspondencia ambigua.');
    expect(article.textContent).toContain('Requiere revisión de identidad');
    expect(article.querySelectorAll('.difference').length).toBe(2);
  });
  it('recupera un borrador por ID y muestra vencimiento sin datos antiguos', () => {
    const fixture=setup(); const input=fixture.nativeElement.querySelector('input[type=text]') as HTMLInputElement;
    input.value=id;input.dispatchEvent(new Event('input'));fixture.detectChanges();
    const button=Array.from(fixture.nativeElement.querySelectorAll('button')).find(b=>(b as HTMLButtonElement).textContent==='Recuperar') as HTMLButtonElement;
    button.click();http.expectOne(`/api/student-imports/${id}`).flush({detail:'La previsualización venció.'},{status:410,statusText:'Gone'});fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Genera una nueva');expect(fixture.nativeElement.textContent).not.toContain('Colegio sintético');
  });
  it('muestra errores sin repetir automáticamente el envío', () => {
    const fixture=setup();choose(fixture);fixture.nativeElement.querySelector('button').click();fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('button').disabled).toBe(true);
    http.expectOne('/api/student-imports/preview').flush({detail:'Estructura incompatible.'},{status:422,statusText:'Invalid'});fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Estructura incompatible.');http.expectNone('/api/student-imports/preview');
  });
  it('rechaza extensión inválida antes de enviar', () => {
    const fixture=setup();choose(fixture,'SUBCONJUNTO','test.xls');fixture.nativeElement.querySelector('button').click();fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Selecciona un archivo .xlsx');http.expectNone('/api/student-imports/preview');
  });
  it('muestra ausencias separadas cuando el backend las calcula', () => {
    const fixture=setup();create(fixture,{...batch,scope:'PADRON_COMPLETO',absences_calculated:true,absence_count:1});
    const button=Array.from(fixture.nativeElement.querySelectorAll('button')).find(b=>(b as HTMLButtonElement).textContent?.includes('No encontrados')) as HTMLButtonElement;
    button.click();http.expectOne(`/api/student-imports/${id}/absences?page=1&page_size=10`).flush({items:[{student_id:3,name:'Otra Persona',course:'Octavo',parallel:'B'}],total:1,page:1,page_size:10});fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Otra Persona');expect(fixture.nativeElement.textContent).toContain('no significa retiro');
  });
  it('muestra el resumen y exige una aceptación explícita antes de confirmar', () => {
    const fixture=setup(); create(fixture,confirmableBatch);
    const confirm=actionButton(fixture,'Confirmar y aplicar cambios');
    expect(fixture.nativeElement.textContent).toContain('Esta acción modificará los datos operativos');
    expect(fixture.nativeElement.textContent).toContain('Colegio sintético');
    expect(confirm.disabled).toBe(true);
    acceptConfirmation(fixture); expect(confirm.disabled).toBe(false);
  });
  it('deshabilita confirmación cuando el backend informa bloqueos', () => {
    const fixture=setup(); create(fixture,{...confirmableBatch,counts:{...confirmableBatch.counts!,REQUIERE_REVISION:1},rows_with_blocking_reasons:1});
    acceptConfirmation(fixture);
    expect(actionButton(fixture,'Confirmar y aplicar cambios').disabled).toBe(true);
    expect(fixture.nativeElement.textContent).toContain('conflictos bloqueantes');
  });
  it('requiere aceptar explícitamente la configuración inicial cuando el backend lo indica', () => {
    const fixture=setup();create(fixture,{...confirmableBatch,configuration:{...confirmableBatch.configuration!,action:'ACTIVATE_PERIOD',requires_acceptance:true}});
    const boxes=Array.from(fixture.nativeElement.querySelectorAll('.confirmation input[type=checkbox]')) as HTMLInputElement[];
    boxes[0].checked=true;boxes[0].dispatchEvent(new Event('change'));fixture.detectChanges();
    expect(actionButton(fixture,'Confirmar y aplicar cambios').disabled).toBe(true);
    boxes[1].checked=true;boxes[1].dispatchEvent(new Event('change'));fixture.detectChanges();
    actionButton(fixture,'Confirmar y aplicar cambios').click();
    const request=http.expectOne(`/api/student-imports/${id}/confirm`);expect(request.request.body).toEqual({confirm:true,accept_configuration:true});
    request.flush({...confirmableBatch,status:'APPLIED',confirmable:false,applied_receipt:{import_id:id,status:'APPLIED',applied_at:'2099-01-02T00:00:00Z',counts:confirmableBatch.counts!}});
  });
  it('confirma una vez, muestra estado en curso y después el comprobante', () => {
    const fixture=setup(); create(fixture,confirmableBatch); acceptConfirmation(fixture);
    const confirm=actionButton(fixture,'Confirmar y aplicar cambios'); confirm.click(); fixture.detectChanges();
    const request=http.expectOne(`/api/student-imports/${id}/confirm`);
    expect(request.request.method).toBe('POST');expect(request.request.body).toEqual({confirm:true,accept_configuration:false});
    expect(fixture.nativeElement.textContent).toContain('Confirmando');
    confirm.click(); http.expectNone(`/api/student-imports/${id}/confirm`);
    request.flush({...confirmableBatch,status:'APPLIED',confirmable:false,applied_receipt:{import_id:id,status:'APPLIED',applied_at:'2099-01-02T00:00:00Z',counts:{NUEVO:10,SIN_CAMBIOS:0,ACTUALIZACION:0,REQUIERE_REVISION:0}}}); fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Comprobante de aplicación');
    expect(fixture.nativeElement.textContent).toContain('La importación fue aplicada');
    expect(fixture.nativeElement.textContent).not.toContain('todavía no se han aplicado cambios');
  });
  it('muestra el error de dominio sin repetir la confirmación', () => {
    const fixture=setup();create(fixture,confirmableBatch);acceptConfirmation(fixture);actionButton(fixture,'Confirmar y aplicar cambios').click();
    http.expectOne(`/api/student-imports/${id}/confirm`).flush({detail:{code:'PREVIEW_OBSOLETE',message:'El borrador ya no representa el estado actual.'}},{status:409,statusText:'Conflict'});fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('El borrador ya no representa el estado actual.');
    expect(actionButton(fixture,'Confirmar y aplicar cambios').disabled).toBe(true);
    expect((fixture.nativeElement.querySelector('.confirmation input[type=checkbox]') as HTMLInputElement).checked).toBe(false);
    http.expectNone(`/api/student-imports/${id}/confirm`);
  });
  it('si vence durante la confirmación, no cancela la aplicación y muestra el comprobante recibido', () => {
    const fixture=setup();create(fixture,confirmableBatch);acceptConfirmation(fixture);actionButton(fixture,'Confirmar y aplicar cambios').click();
    const request=http.expectOne(`/api/student-imports/${id}/confirm`);
    (fixture.componentInstance as any).expire(); fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('venció mientras se confirmaba');
    request.flush({...confirmableBatch,status:'APPLIED',confirmable:false,applied_receipt:{import_id:id,status:'APPLIED',applied_at:'2099-01-02T00:00:00Z',counts:confirmableBatch.counts!}});fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Comprobante de aplicación');
    expect(fixture.nativeElement.textContent).not.toContain('venció mientras se confirmaba');
  });
  it('ante resultado incierto no reintenta y permite recuperar el comprobante', () => {
    const fixture=setup();create(fixture,confirmableBatch);acceptConfirmation(fixture);actionButton(fixture,'Confirmar y aplicar cambios').click();
    http.expectOne(`/api/student-imports/${id}/confirm`).flush({}, {status:0,statusText:'Unknown Error'});fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Se consultará el ID');http.expectNone(`/api/student-imports/${id}/confirm`);
    http.expectOne(`/api/student-imports/${id}`).flush({...confirmableBatch,status:'APPLIED',confirmable:false,applied_receipt:{import_id:id,status:'APPLIED',applied_at:'2099-01-02T00:00:00Z',counts:batch.counts!}});fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Comprobante de aplicación');
  });
  it('recupera un batch aplicado incluso después del TTL sin volver a confirmarlo', () => {
    const fixture=setup(); const input=fixture.nativeElement.querySelector('input[type=text]') as HTMLInputElement;
    input.value=id;input.dispatchEvent(new Event('input'));fixture.detectChanges();actionButton(fixture,'Recuperar').click();
    http.expectOne(`/api/student-imports/${id}`).flush({...confirmableBatch,status:'APPLIED',confirmable:false,expires_at:'2000-01-01T00:00:00Z',applied_receipt:{import_id:id,status:'APPLIED',applied_at:'2099-01-02T00:00:00Z',counts:batch.counts!}});fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Esta importación ya fue aplicada');
    expect(fixture.nativeElement.textContent).not.toContain('Confirmar y aplicar cambios');
  });
  it('no deja que el temporizador original borre un comprobante recuperado', () => {
    vi.useFakeTimers();
    try {
      const fixture=setup();create(fixture,confirmableBatch);acceptConfirmation(fixture);actionButton(fixture,'Confirmar y aplicar cambios').click();
      http.expectOne(`/api/student-imports/${id}/confirm`).flush({}, {status:0,statusText:'Unknown Error'});
      http.expectOne(`/api/student-imports/${id}`).flush({...confirmableBatch,status:'APPLIED',confirmable:false,applied_receipt:{import_id:id,status:'APPLIED',applied_at:'2099-01-02T00:00:00Z',counts:confirmableBatch.counts!}});fixture.detectChanges();
      vi.advanceTimersByTime(24 * 60 * 60 * 1000 + 1);fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain('Comprobante de aplicación');
    } finally { vi.useRealTimers(); }
  });
  it('muestra preview incompatible sin permitir confirmarlo', () => {
    const fixture=setup();create(fixture,{...batch,contract_version:'3A-1',confirmable:false});
    expect(actionButton(fixture,'Confirmar y aplicar cambios').disabled).toBe(true);
    expect(fixture.nativeElement.textContent).toContain('no es compatible para confirmar');
  });
});
