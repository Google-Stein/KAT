export type MemoryKind = 'semantic' | 'episodic' | 'project_state' | 'commitment' | 'procedure';
export type MemoryStatus = 'confirmed' | 'superseded' | 'disputed' | 'expired';
export interface Project {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}
export interface MemoryFields {
  kind: MemoryKind;
  content: string;
  scope: 'personal' | 'project';
  project_id: string | null;
  sensitivity: 'normal';
  pinned: boolean;
  importance: number;
  effective_at: string | null;
  expires_at: string | null;
}
export interface MemoryRecord extends MemoryFields {
  id: string;
  status: MemoryStatus;
  origin: 'owner_explicit' | 'conversation_selection';
  revision: number;
  created_at: string;
  updated_at: string;
  last_reviewed_at: string;
  superseded_by: string | null;
  source_session_id: string | null;
  source_message_id: string | null;
  source_role: 'user' | 'assistant' | null;
  source_available: boolean;
}
export interface MemoryCreate extends MemoryFields {
  confirmed: true;
  origin: MemoryRecord['origin'];
  source_session_id: string | null;
  source_message_id: string | null;
}
export interface MemoryUsage {
  memory_id: string;
  revision: number;
  session_id: string;
  assistant_message_id: string;
  provider: 'ollama';
  used_at: string;
  content: string | null;
  forgotten: boolean;
}
export interface MemoryFilter {
  q?: string;
  kind?: MemoryKind;
  scope?: MemoryFields['scope'];
  project_id?: string;
  status?: MemoryStatus;
  offset?: number;
}
