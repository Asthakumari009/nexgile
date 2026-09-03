import { Component } from '@angular/core';
import { RouterLink, RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterLink, RouterOutlet],
  template: `
    <header class="topbar">
      <a routerLink="/" class="brand"><strong>NEXGILE</strong><span>Supplier Portal</span></a>
      <span class="secure">Secure reporting workspace</span>
    </header>
    <main class="shell"><router-outlet /></main>
  `,
})
export class AppComponent {}
