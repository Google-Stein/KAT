import type { MemoryKind, MemoryRecord } from './memory-types';

export const KIND_LABELS: Record<MemoryKind, string> = {
  semantic: 'Fact or preference',
  episodic: 'Event',
  project_state: 'Project state',
  commitment: 'Goal or commitment',
  procedure: 'Working preference',
};
export const MEMORY_NOTICE =
  'Stored in local SQLite, not encrypted by KAT. Never save credentials or highly sensitive information.';
export const FORGET_NOTICE =
  'Forgetting this memory does not automatically delete the original conversation or older database backups that may contain the original text.';

export function memoryStatusLabel(record: MemoryRecord): string {
  if (
    record.status === 'confirmed' &&
    record.expires_at &&
    new Date(record.expires_at).getTime() <= Date.now()
  )
    return 'expired by date';
  if (
    record.status === 'confirmed' &&
    record.effective_at &&
    new Date(record.effective_at).getTime() > Date.now()
  )
    return 'future effective date';
  return record.status === 'disputed' ? 'needs review' : record.status;
}
