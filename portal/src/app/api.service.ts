import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';

export interface Supplier {
  id: number;
  name: string;
  country: string;
  tier: number;
  category: string;
  engagement_status: string;
}

export interface Submission {
  id: number;
  period: string;
  reported_scope1: number;
  reported_scope2: number;
  reported_scope3: number;
  evidence_id: number | null;
  validation_state: string;
  submitted_at: string;
}

export interface SupplierDetail { supplier: Supplier; latest_submission: Submission | null; }

@Injectable({ providedIn: 'root' })
export class SupplierApi {
  private readonly http = inject(HttpClient);
  list() { return this.http.get<{ count: number; rows: Supplier[] }>('/api/v1/suppliers'); }
  detail(supplierId: number) { return this.http.get<SupplierDetail>(`/api/v1/suppliers/${supplierId}`); }
  uploadEvidence(supplierId: number, file: File) {
    const body = new FormData();
    body.append('file', file);
    return this.http.post<{ id: number; filename: string }>(`/api/v1/suppliers/${supplierId}/evidence`, body);
  }
  submit(supplierId: number, body: { period: string; reported_scope1: number; reported_scope2: number; reported_scope3: number; evidence_id: number | null; attested: boolean; }) {
    return this.http.post(`/api/v1/suppliers/${supplierId}/submissions`, body);
  }
}
