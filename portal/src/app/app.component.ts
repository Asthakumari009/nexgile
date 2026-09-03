import { Component, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { RouterOutlet } from '@angular/router';

// Phase 0 hello world: proves the Angular -> FastAPI proxy is wired.
// The three portal routes land here in Phase 4.
@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  template: `
    <header class="bar">
      <strong>Nexgile</strong> Supplier Portal
    </header>
    <main>
      <p>backend <b>{{ health() }}</b></p>
      <router-outlet />
    </main>
  `,
  styles: [
    `
      .bar {
        background: #1e293b;
        color: #fff;
        padding: 14px 20px;
        font-size: 15px;
      }
      main {
        padding: 24px 20px;
        font: 14px/1.5 system-ui, sans-serif;
      }
    `,
  ],
})
export class AppComponent {
  private http = inject(HttpClient);
  health = signal('checking...');

  constructor() {
    this.http.get<{ app: string; status: string }>('/api/v1/health').subscribe({
      next: (d) => this.health.set(`${d.app}: ${d.status}`),
      error: (e) => this.health.set(`unreachable (${e.message})`),
    });
  }
}
