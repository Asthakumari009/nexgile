import { AsyncPipe, NgFor, NgIf } from '@angular/common';
import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { catchError, map, of } from 'rxjs';
import { SupplierApi } from './api.service';

@Component({
  standalone: true,
  imports: [AsyncPipe, NgFor, NgIf, RouterLink],
  template: `
    <section class="hero"><p class="eyebrow">Nexgile supplier reporting</p><h1>Report your value-chain emissions with a clear audit trail.</h1><p>Provide your latest Scope 1, 2, and 3 inventory, attach supporting evidence, and attest before submitting it to Nexgile.</p></section>
    <section class="panel"><div class="panel-head"><div><h2>Choose your organisation</h2><p>Demo access identifies the invited supplier before data entry.</p></div><span class="year">2025 reporting</span></div><ng-container *ngIf="suppliers$ | async as state"><p *ngIf="state.error" class="error">{{ state.error }}</p><div *ngIf="!state.error" class="supplier-list"><a *ngFor="let supplier of state.rows" [routerLink]="['/submit', supplier.id]" class="supplier-row"><span><strong>{{ supplier.name }}</strong><small>{{ supplier.category }} · Tier {{ supplier.tier }} · {{ supplier.country }}</small></span><span class="status">{{ supplier.engagement_status.replace('_', ' ') }}</span></a></div></ng-container></section>
  `,
})
export class InviteComponent {
  private readonly api = inject(SupplierApi);
  readonly suppliers$ = this.api.list().pipe(map((result) => ({ rows: result.rows, error: '' })), catchError(() => of({ rows: [], error: 'The supplier directory is unavailable. Please try again shortly.' })));
}
