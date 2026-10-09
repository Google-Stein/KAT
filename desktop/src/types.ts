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
  project_id?: string | null;
}
export interface Message {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'tool';
  content: string;
  created_at: string;
}
export interface Approval {
  display_context?: string | null;
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
  provider: 'openai' | 'ollama';
  local_endpoint: string;
  model: string;
  api_key_configured: boolean;
  application_allowlist: { id: string; label: string }[];
  require_approval_for_low_risk: boolean;
  memory_enabled: boolean;
}
export type SettingsUpdate = Pick<
  Settings,
  'provider' | 'model' | 'require_approval_for_low_risk' | 'local_endpoint' | 'memory_enabled'
>;
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

export interface ProviderStatus {
  provider: 'openai' | 'ollama';
  status: 'ready' | 'configured' | 'not_configured' | 'model_missing' | 'unreachable' | 'error';
  message: string;
  models: string[];
  tool_calling: boolean;
  error_code: string | null;
}
