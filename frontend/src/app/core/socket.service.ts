import { DOCUMENT } from '@angular/common';
import { inject, Injectable, InjectionToken, OnDestroy, signal } from '@angular/core';
import { Subject } from 'rxjs';

type SocketState = 'disconnected' | 'connecting' | 'connected' | 'reconnecting';
export type SocketEvent = 'connected' | 'disconnected' | 'departments_changed';

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
  private readonly notifications = new Subject<SocketEvent>();
  readonly events = this.notifications.asObservable();
  private socket: WebSocket | null = null;
  private retryTimer: ReturnType<typeof setTimeout> | undefined;
  private connectionTimer: ReturnType<typeof setTimeout> | undefined;
  private retryDelay = 1000;
  private stopped = true;

  connect(): void {
    if (this.socket) return;
    this.stopped = false;
    clearTimeout(this.retryTimer);
    this.retryTimer = undefined;
    this.open();
  }

  private open(): void {
    if (this.stopped || this.socket) return;
    const url = new URL('/ws', this.document.baseURI);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    this.connectionState.set(this.retryDelay === 1000 ? 'connecting' : 'reconnecting');
    try {
      const socket = this.createSocket(url.href);
      this.socket = socket;
      this.connectionTimer = setTimeout(() => this.failed(socket), 5000);
      socket.addEventListener('open', () => {
        if (this.socket !== socket) return;
        clearTimeout(this.connectionTimer);
        this.retryDelay = 1000;
        this.connectionState.set('connected');
        this.notifications.next('connected');
      });
      socket.addEventListener('message', (event) => {
        if (this.socket !== socket) return;
        try {
          const message: unknown = JSON.parse(event.data);
          if (message && typeof message === 'object' && 'type' in message &&
              message.type === 'departments_changed') {
            this.notifications.next('departments_changed');
          }
        } catch { /* Los mensajes ajenos al contrato no alteran el estado. */ }
      });
      socket.addEventListener('error', () => this.failed(socket));
      socket.addEventListener('close', () => this.failed(socket));
    } catch {
      this.scheduleRetry();
    }
  }

  private failed(socket: WebSocket): void {
    if (this.socket !== socket) return;
    this.socket = null;
    clearTimeout(this.connectionTimer);
    socket.close();
    this.scheduleRetry();
  }

  private scheduleRetry(): void {
    if (this.stopped || this.retryTimer !== undefined) return;
    this.connectionState.set('reconnecting');
    this.notifications.next('disconnected');
    this.retryTimer = setTimeout(() => {
      this.retryTimer = undefined;
      this.open();
    }, this.retryDelay);
    this.retryDelay = Math.min(this.retryDelay * 2, 10000);
  }

  disconnect(): void {
    this.stopped = true;
    clearTimeout(this.retryTimer);
    clearTimeout(this.connectionTimer);
    this.retryTimer = undefined;
    const socket = this.socket;
    this.socket = null;
    this.connectionState.set('disconnected');
    this.notifications.next('disconnected');
    socket?.close(1000, 'Cierre del cliente');
  }

  ngOnDestroy(): void {
    this.disconnect();
    this.notifications.complete();
  }
}
