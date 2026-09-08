import { TestBed } from '@angular/core/testing';
import { SOCKET_FACTORY, SocketService } from './socket.service';

class FakeSocket extends EventTarget {
  close = vi.fn();
}

describe('SocketService', () => {
  let sockets: FakeSocket[];
  let factory: ReturnType<typeof vi.fn>;
  let service: SocketService;

  beforeEach(() => {
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

  it('conecta una sola vez, detecta desconexión y permite reconectar', () => {
    service.connect();
    service.connect();
    expect(factory).toHaveBeenCalledOnce();
    expect(factory.mock.calls[0]?.[0]).toMatch(/^ws:\/\/[^/]+\/ws$/);
    expect(service.state()).toBe('connecting');
    sockets[0].dispatchEvent(new Event('open'));
    expect(service.state()).toBe('connected');
    sockets[0].dispatchEvent(new Event('close'));
    expect(service.state()).toBe('disconnected');
    service.connect();
    expect(factory).toHaveBeenCalledTimes(2);
  });

  it('conserva error de conexión y cierra limpiamente al destruirse', () => {
    service.connect();
    sockets[0].dispatchEvent(new Event('error'));
    sockets[0].dispatchEvent(new Event('close'));
    expect(service.state()).toBe('error');
    service.connect();
    service.ngOnDestroy();
    expect(sockets[1].close).toHaveBeenCalledWith(1000, 'Cierre del cliente');
    expect(service.state()).toBe('disconnected');
  });

  it('ignora eventos tardíos de una conexión cerrada por el cliente', () => {
    service.connect();
    service.disconnect();
    service.connect();
    sockets[0].dispatchEvent(new Event('close'));
    sockets[0].dispatchEvent(new Event('open'));
    expect(service.state()).toBe('connecting');
    sockets[1].dispatchEvent(new Event('open'));
    expect(service.state()).toBe('connected');
  });
});
