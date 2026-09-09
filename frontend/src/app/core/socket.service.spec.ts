import { TestBed } from '@angular/core/testing';
import { SOCKET_FACTORY, SocketService } from './socket.service';

class FakeSocket extends EventTarget { close = vi.fn(); }

describe('SocketService', () => {
  let sockets: FakeSocket[];
  let factory: ReturnType<typeof vi.fn>;
  let service: SocketService;

  beforeEach(() => {
    vi.useFakeTimers();
    sockets = [];
    factory = vi.fn(() => {
      const socket = new FakeSocket();
      sockets.push(socket);
      return socket as unknown as WebSocket;
    });
    TestBed.configureTestingModule({
      providers: [{ provide: SOCKET_FACTORY, useValue: factory }],
    });
    service = TestBed.inject(SocketService);
  });
  afterEach(() => { TestBed.resetTestingModule(); vi.useRealTimers(); });

  it('conecta una sola vez y reconecta automáticamente con un solo temporizador', () => {
    service.connect();
    service.connect();
    expect(factory).toHaveBeenCalledOnce();
    expect(factory.mock.calls[0]?.[0]).toMatch(/^ws:\/\/[^/]+\/ws$/);
    sockets[0].dispatchEvent(new Event('open'));
    expect(service.state()).toBe('connected');
    sockets[0].dispatchEvent(new Event('error'));
    sockets[0].dispatchEvent(new Event('close'));
    expect(service.state()).toBe('reconnecting');
    vi.advanceTimersByTime(1000);
    expect(factory).toHaveBeenCalledTimes(2);
    service.connect();
    expect(factory).toHaveBeenCalledTimes(2);
  });

  it('limita el tiempo de conexión y cancela los reintentos al destruirse', () => {
    service.connect();
    vi.advanceTimersByTime(5000);
    expect(sockets[0].close).toHaveBeenCalledOnce();
    vi.advanceTimersByTime(1000);
    service.ngOnDestroy();
    expect(sockets[1].close).toHaveBeenCalledWith(1000, 'Cierre del cliente');
    vi.advanceTimersByTime(60000);
    expect(factory).toHaveBeenCalledTimes(2);
    expect(service.state()).toBe('disconnected');
  });

  it('ignora eventos tardíos y mensajes ajenos al contrato', () => {
    const events: string[] = [];
    service.events.subscribe(event => events.push(event));
    service.connect();
    service.disconnect();
    service.connect();
    sockets[0].dispatchEvent(new Event('close'));
    sockets[0].dispatchEvent(new Event('open'));
    sockets[0].dispatchEvent(new MessageEvent('message', { data: '{"type":"departments_changed"}' }));
    expect(service.state()).toBe('connecting');
    sockets[1].dispatchEvent(new Event('open'));
    sockets[1].dispatchEvent(new MessageEvent('message', { data: 'invalid' }));
    sockets[1].dispatchEvent(new MessageEvent('message', { data: '{"type":"unknown"}' }));
    sockets[1].dispatchEvent(new MessageEvent('message', { data: '{"type":"departments_changed"}' }));
    expect(events).toEqual(['disconnected', 'connected', 'departments_changed']);
  });

  it('permite reintento manual sin dejar un temporizador automático pendiente', () => {
    service.connect();
    sockets[0].dispatchEvent(new Event('close'));
    service.connect();
    sockets[1].dispatchEvent(new Event('open'));
    vi.advanceTimersByTime(60000);
    expect(factory).toHaveBeenCalledTimes(2);
  });
});
