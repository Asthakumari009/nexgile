import { AsyncPipe, NgIf } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { SupplierApi } from './api.service';

@Component({
  standalone: true,
  imports: [AsyncPipe, NgIf, ReactiveFormsModule, RouterLink],
  template: `
    <a routerLink="/" class="back">← Change organisation</a><ng-container *ngIf="supplier$ | async as detail; else loading"><section class="page-title"><p class="eyebrow">2025 disclosure</p><h1>Submit emissions data</h1><p>{{ detail.supplier.name }} · {{ detail.supplier.category }} · {{ detail.supplier.country }}</p></section><form class="panel form" [formGroup]="form" (ngSubmit)="submit()"><div class="notice"><strong>Before you submit</strong><span>All values are in tCO₂e for the 2025 reporting year. The submission remains pending until Nexgile reviews it.</span></div><div class="scope-grid"><label><span>Scope 1</span><small>Direct fuel and process emissions</small><input type="number" min="0" step="0.1" formControlName="scope1"><em>tCO₂e</em></label><label><span>Scope 2</span><small>Purchased electricity and energy</small><input type="number" min="0" step="0.1" formControlName="scope2"><em>tCO₂e</em></label><label><span>Scope 3</span><small>Other value-chain emissions</small><input type="number" min="0" step="0.1" formControlName="scope3"><em>tCO₂e</em></label></div><section class="evidence"><div><h2>Supporting evidence</h2><p>Attach an emissions inventory, attestation, or methodology document (maximum 10 MB).</p></div><label class="upload"><input type="file" accept=".pdf,.xlsx,.xls,.csv,.doc,.docx" (change)="upload($event)"><span>{{ evidenceName() || 'Choose evidence file' }}</span></label><p *ngIf="uploading()" class="muted">Uploading evidence…</p></section><label class="attestation"><input type="checkbox" formControlName="attested"><span>I am authorised to submit this information for {{ detail.supplier.name }} and attest that it is complete and accurate to the best of my knowledge.</span></label><p *ngIf="error()" class="error">{{ error() }}</p><div class="actions"><button type="submit" [disabled]="form.invalid || submitting()">{{ submitting() ? 'Submitting…' : 'Submit for review' }}</button><span>Submission creates an auditable record. Approved reported actuals are not changed.</span></div></form></ng-container><ng-template #loading><p class="loading">Loading supplier workspace…</p></ng-template>
  `,
})
export class SubmissionComponent {
  private readonly api = inject(SupplierApi);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly supplierId = Number(this.route.snapshot.paramMap.get('supplierId'));
  private readonly formBuilder = inject(FormBuilder);
  readonly error = signal('');
  readonly evidenceId = signal<number | null>(null);
  readonly evidenceName = signal('');
  readonly submitting = signal(false);
  readonly uploading = signal(false);
  readonly supplier$ = this.api.detail(this.supplierId);
  readonly form = this.formBuilder.group({ scope1: [null as number | null, [Validators.required, Validators.min(0)]], scope2: [null as number | null, [Validators.required, Validators.min(0)]], scope3: [null as number | null, [Validators.required, Validators.min(0)]], attested: [false, Validators.requiredTrue] });

  upload(event: Event) {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file) return;
    this.uploading.set(true); this.error.set('');
    this.api.uploadEvidence(this.supplierId, file).subscribe({ next: (result) => { this.evidenceId.set(result.id); this.evidenceName.set(result.filename); this.uploading.set(false); }, error: () => { this.error.set('Evidence could not be uploaded. Please use a file smaller than 10 MB.'); this.uploading.set(false); } });
  }

  submit() {
    if (this.form.invalid) return;
    const value = this.form.getRawValue(); this.submitting.set(true); this.error.set('');
    this.api.submit(this.supplierId, { period: '2025', reported_scope1: value.scope1 ?? 0, reported_scope2: value.scope2 ?? 0, reported_scope3: value.scope3 ?? 0, evidence_id: this.evidenceId(), attested: value.attested ?? false }).subscribe({ next: () => this.router.navigate(['/status', this.supplierId]), error: (response) => { this.error.set(response.error?.detail ?? 'Your submission could not be saved.'); this.submitting.set(false); } });
  }
}
