import { Check, Shield, X } from 'lucide-react';
import type { Approval } from './types';

interface Props {
  approval: Approval;
  busy: boolean;
  onDecision: (id: string, approved: boolean) => void;
}

export function ApprovalCard({ approval, busy, onDecision }: Props) {
  return (
    <section className="approval-card" aria-label={`Approval for ${approval.tool_name}`}>
      <div className="approval-heading">
        <span className="approval-icon">
          <Shield size={19} />
        </span>
        <div>
          <strong>Your permission is needed</strong>
          <span>KAT wants to use a tool.</span>
        </div>
        <span className={`risk-badge ${approval.risk}`}>{approval.risk} risk</span>
      </div>
      <div className="approval-details">
        <span>TOOL</span>
        <strong>{approval.tool_name.replaceAll('_', ' ')}</strong>
        <pre>{JSON.stringify(approval.arguments, null, 2)}</pre>
      </div>
      <p className="muted approval-caption">
        Allow this one request. Future requests follow your permission settings.
      </p>
      <div className="approval-actions">
        <button className="secondary-button" disabled={busy} onClick={() => onDecision(approval.id, false)}>
          <X size={15} /> Deny
        </button>
        <button className="primary-button" disabled={busy} onClick={() => onDecision(approval.id, true)}>
          <Check size={15} /> Allow once
        </button>
      </div>
    </section>
  );
}
