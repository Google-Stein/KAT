export interface CoreConnection {
  base_url: string;
  token: string;
}
export interface ProviderCredentialsStatus {
  supported: boolean;
  stored: boolean;
  environment_configured: boolean;
}
export interface ProviderCredentialsChange {
  changed: boolean;
  connection: CoreConnection | null;
  status: ProviderCredentialsStatus;
}
export interface Health {
  status: 'ok';
  version: string;
  provider_ready: boolean;
}
export interface Session {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}
export interface Message {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'tool';
  content: string;
  created_at: string;
}
export interface Approval {
  id: string;
  session_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  risk: 'low' | 'medium' | 'high';
  status: 'pending' | 'approved' | 'denied' | 'completed' | 'failed';
  created_at: string;
  result?: Record<string, unknown> | null;
  error?: string | null;
}
export interface Settings {
  provider: 'openai';
  model: string;
  api_key_configured: boolean;
  application_allowlist: { id: string; label: string }[];
  require_approval_for_low_risk: boolean;
}
export type SettingsUpdate = Pick<Settings, 'provider' | 'model' | 'require_approval_for_low_risk'>;
export interface AuditEvent {
  id: string;
  timestamp: string;
  event: string;
  session_id: string | null;
  tool_name: string | null;
  approval_id?: string | null;
  details: Record<string, unknown>;
  error?: string | null;
}
export interface ChatResponse {
  user_message: Message;
  assistant_message: Message;
  approvals: Approval[];
}
