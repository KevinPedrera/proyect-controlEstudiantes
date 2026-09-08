import { DOCUMENT } from '@angular/common';
import { inject, Injectable, InjectionToken, OnDestroy, signal } from '@angular/core';

type SocketState = 'disconnected' | 'connecting' | 'connected' | 'error';

export const SOCKET_FACTORY = new InjectionToken<(url: string) => WebSocket>('SOCKET_FACTORY', {
  providedIn: 'root',
  factory: () => (url: string) => new WebSocket(url),
});

@Injectable({ providedIn: 'root' })
export class SocketService implements OnDestroy {
  private readonly document = inject(DOCUMENT);
  private readonly createSocket = inject(SOCKET_FACTORY);
  private readonly connectionState = signal<SocketState>('disconnected');
  readonly state = this.connectionState.asReadonly();
  private socket: WebSocket | null = null;

  connect(): void {
    if (this.socket) return;
    const url = new URL('/ws', this.document.baseURI);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    this.connectionState.set('connecting');
    try {
      const socket = this.createSocket(url.href);
      this.socket = socket;
      socket.addEventListener('open', () => {
        if (this.socket === socket) this.connectionState.set('connected');
      });
      socket.addEventListener('error', () => {
        if (this.socket === socket) this.connectionState.set('error');
      });
      socket.addEventListener('close', () => {
        if (this.socket !== socket) return;
        this.socket = null;
        if (this.connectionState() !== 'error') this.connectionState.set('disconnected');
      });
    } catch {
      this.socket = null;
      this.connectionState.set('error');
    }
  }

  disconnect(): void {
    const socket = this.socket;
    this.socket = null;
    this.connectionState.set('disconnected');
    socket?.close(1000, 'Cierre del cliente');
  }

  ngOnDestroy(): void {
    this.disconnect();
  }
}
