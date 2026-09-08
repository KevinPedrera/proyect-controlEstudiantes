import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { App } from './app';
import { SocketService } from './core/socket.service';

describe('Arranque', () => {
  const socketState = signal('disconnected');
  const socket = { state: socketState, connect: vi.fn(), disconnect: vi.fn() };
  let http: HttpTestingController;

  beforeEach(() => {
    socketState.set('disconnected');
    vi.clearAllMocks();
    TestBed.configureTestingModule({
      imports: [App],
      providers: [
        provideHttpClient(), provideHttpClientTesting(),
        { provide: SocketService, useValue: socket },
      ],
    });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('consulta health y representa ambas conexiones', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Comprobando');
    const request = http.expectOne('/api/health');
    expect(request.request.method).toBe('GET');
    request.flush({ status: 'ok' });
    socketState.set('connected');
    await fixture.whenStable();
    expect(fixture.nativeElement.querySelector('[data-testid="health"]').textContent).toContain('Conectado');
    expect(fixture.nativeElement.querySelector('[data-testid="websocket"]').textContent).toContain('Conectado');
    expect(socket.connect).toHaveBeenCalledOnce();
    fixture.destroy();
    expect(socket.disconnect).toHaveBeenCalledOnce();
  });

  it('muestra un error HTTP y permite volver a comprobar', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    http.expectOne('/api/health').error(new ProgressEvent('error'));
    await fixture.whenStable();
    expect(fixture.nativeElement.querySelector('[data-testid="health"]').textContent).toContain('Error de conexión');
    fixture.nativeElement.querySelector('button').click();
    fixture.detectChanges();
    http.expectOne('/api/health').flush({ status: 'ok' });
    await fixture.whenStable();
    expect(fixture.nativeElement.querySelector('[data-testid="health"]').textContent).toContain('Conectado');
  });
});
