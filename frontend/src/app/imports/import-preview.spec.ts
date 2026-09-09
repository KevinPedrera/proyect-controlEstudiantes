import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
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
  it('exige archivo y alcance explícito; no hay acciones de aplicación', () => {
    const fixture=setup(); expect(fixture.nativeElement.querySelector('button').disabled).toBe(true);
    expect(fixture.nativeElement.textContent).toContain('todavía no se han aplicado cambios');
    const buttons=Array.from(fixture.nativeElement.querySelectorAll('button')) as HTMLButtonElement[];
    expect(buttons.some(b=>/confirmar|aplicar|vincular|resolver/i.test(b.textContent ?? ''))).toBe(false);
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
    create(fixture,batch,{...row,category:'REQUIERE_REVISION',blocking_review_reasons:['Correspondencia ambigua.']});
    const article=fixture.nativeElement.querySelector('article');
    expect(article.textContent).toContain('Requiere revisión');
    expect(article.textContent).toContain('Advertencias de calidad');
    expect(article.textContent).toContain('Razones que requieren una decisión');
    expect(article.textContent).toContain('Correspondencia ambigua.');
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
});
