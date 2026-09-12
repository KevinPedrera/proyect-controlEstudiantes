import { AfterViewInit, Component, ElementRef, Injectable, ViewChild, effect, inject, signal } from '@angular/core';

interface Prompt { title: string; message: string; confirm?: string; }

@Injectable({ providedIn: 'root' })
export class DialogService {
  readonly prompt = signal<Prompt | null>(null);
  private resolve?: (value: boolean) => void;
  ask(prompt: Prompt): Promise<boolean> {
    if (this.prompt()) return Promise.resolve(false);
    this.prompt.set(prompt);
    return new Promise(resolve => { this.resolve = resolve; });
  }
  answer(value: boolean): void {
    this.prompt.set(null);
    this.resolve?.(value);
    this.resolve = undefined;
  }
}

@Component({
  selector: 'app-dialog',
  template: `<dialog #dialog aria-labelledby="dialog-title" aria-describedby="dialog-message"
    (cancel)="cancel($event)">
    @if (service.prompt(); as prompt) {
      <h2 id="dialog-title">{{ prompt.title }}</h2>
      <p id="dialog-message">{{ prompt.message }}</p>
      <div class="actions">
        <button type="button" autofocus (click)="service.answer(false)">{{ prompt.confirm ? 'Cancelar' : 'Entendido' }}</button>
        @if (prompt.confirm) { <button type="button" (click)="service.answer(true)">{{ prompt.confirm }}</button> }
      </div>
    }
  </dialog>`,
  styles: `dialog { box-sizing:border-box; width:min(32rem,calc(100vw - 2rem)); max-height:calc(100dvh - 2rem); overflow:auto; border:1px solid #879c93; border-radius:12px; padding:1.4rem; color:#183e38; }
    dialog::backdrop { background:#152b2580; } h2 { margin-top:0; font-size:1.3rem; overflow-wrap:anywhere; }
    p { white-space:pre-line; line-height:1.6; overflow-wrap:anywhere; } .actions { display:flex; flex-wrap:wrap; gap:1rem; }
    button { flex:1; min-height:48px; padding:.75rem; border:1px solid #1c5d4d; border-radius:6px; background:#1c5d4d; color:white; font:inherit; cursor:pointer; }
    button:focus-visible { outline:3px solid #bb720c; outline-offset:3px; }`,
})
export class DialogHost implements AfterViewInit {
  readonly service = inject(DialogService);
  @ViewChild('dialog') private dialog?: ElementRef<HTMLDialogElement>;
  private readonly ready = signal(false);
  constructor() {
    effect(() => {
      const prompt = this.service.prompt();
      if (!this.ready()) return;
      const dialog = this.dialog!.nativeElement;
      if (prompt && !dialog.open) dialog.showModal();
      if (!prompt && dialog.open) dialog.close();
    });
  }
  ngAfterViewInit(): void { this.ready.set(true); }
  cancel(event: Event): void { event.preventDefault(); this.service.answer(false); }
}
