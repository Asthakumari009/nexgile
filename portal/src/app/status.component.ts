import { AsyncPipe, DatePipe, DecimalPipe, NgIf } from '@angular/common';
import { Component, inject } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { SupplierApi } from './api.service';

@Component({
  standalone: true,
  imports: [AsyncPipe, DatePipe, DecimalPipe, NgIf, RouterLink],
  template: `
    <a routerLink="/" class="back">← Supplier directory</a><ng-container *ngIf="detail$ | async as detail; else loading"><section class="page-title"><p class="eyebrow">Submission status</p><h1>{{ detail.supplier.name }}</h1><p>{{ detail.supplier.category }} · 2025 reporting year</p></section><section *ngIf="detail.latest_submission as submission; else empty" class="panel status-panel"><div class="review-state"><span class="state pending">{{ submission.validation_state }}</span><h2>Submitted for Nexgile review</h2><p>Received {{ submission.submitted_at | date:'medium' }}. We will validate the reported values and evidence before updating your supplier scorecard.</p></div><div class="submitted-values"><div><span>Scope 1</span><strong>{{ submission.reported_scope1 | number:'1.1-1' }} tCO₂e</strong></div><div><span>Scope 2</span><strong>{{ submission.reported_scope2 | number:'1.1-1' }} tCO₂e</strong></div><div><span>Scope 3</span><strong>{{ submission.reported_scope3 | number:'1.1-1' }} tCO₂e</strong></div></div><p class="attested">Authorised representative attestation recorded{{ submission.evidence_id ? ' · Evidence attached' : '' }}.</p></section><ng-template #empty><section class="panel empty"><h2>No submission yet</h2><p>Start your 2025 disclosure when your inventory and supporting evidence are ready.</p><a [routerLink]="['/submit', detail.supplier.id]" class="button-link">Start submission</a></section></ng-template></ng-container><ng-template #loading><p class="loading">Loading submission status…</p></ng-template>
  `,
})
export class StatusComponent {
  private readonly api = inject(SupplierApi);
  private readonly route = inject(ActivatedRoute);
  readonly detail$ = this.api.detail(Number(this.route.snapshot.paramMap.get('supplierId')));
}
