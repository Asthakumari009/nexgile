import { Routes } from '@angular/router';
import { InviteComponent } from './invite.component';
import { StatusComponent } from './status.component';
import { SubmissionComponent } from './submission.component';

export const routes: Routes = [
  { path: '', component: InviteComponent, title: 'Nexgile Supplier Portal' },
  { path: 'submit/:supplierId', component: SubmissionComponent, title: 'Submit emissions data' },
  { path: 'status/:supplierId', component: StatusComponent, title: 'Submission status' },
  { path: '**', redirectTo: '' },
];
