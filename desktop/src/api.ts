import type {
  Approval,
  ApprovalDecisionResponse,
  AuditEvent,
  ChatResponse,
  CoreConnection,
  Health,
  Message,
  ProviderStatus,
  Session,
  Settings,
  SettingsUpdate,
} from './types';
import type {
  MemoryCreate,
  MemoryFields,
  MemoryFilter,
  MemoryRecord,
  MemoryStatus,
  MemoryUsage,
  Project,
} from './memory-types';
import type { Capabilities, WeatherLocation, ReadRoot } from './capability-types';

export class CoreError extends Error {
  constructor(
    message: string,
    public readonly code: string = 'request_failed',
  ) {
    super(message);
    this.name = 'CoreError';
  }
}

export function validateConnection(connection: CoreConnection): CoreConnection {
  let url: URL;
  try {
    url = new URL(connection.base_url);
  } catch {
    throw new CoreError('Enter a valid local Core URL.', 'invalid_connection');
  }
  if (
    url.protocol !== 'http:' ||
    !['127.0.0.1', 'localhost'].includes(url.hostname) ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    url.pathname !== '/'
  ) {
    throw new CoreError(
      'Core must use http://127.0.0.1 or http://localhost with an optional port.',
      'invalid_connection',
    );
  }
  if (!connection.token.trim())
    throw new CoreError('Enter the Core access token from your local configuration.', 'invalid_connection');
  return { base_url: url.origin, token: connection.token.trim() };
}

export class CoreApi {
  private readonly connection: CoreConnection;
  constructor(connection: CoreConnection) {
    this.connection = validateConnection(connection);
  }

  private async request<T>(
    path: string,
    method = 'GET',
    body?: unknown,
    signal?: AbortSignal,
    timeoutMs = 15000,
  ): Promise<T> {
    const controller = new AbortController();
    let timedOut = false;
    const abort = () => controller.abort();
    if (signal?.aborted) abort();
    else signal?.addEventListener('abort', abort, { once: true });
    const timeout = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);
    let response: Response;
    try {
      response = await fetch(`${this.connection.base_url}${path}`, {
        method,
        headers: {
          Authorization: `Bearer ${this.connection.token}`,
          ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
        credentials: 'omit',
        cache: 'no-store',
        redirect: 'error',
        signal: controller.signal,
      });
    } catch (error) {
      if (timedOut)
        throw new CoreError(
          'Core took too long to respond. Check the service and provider logs, then retry.',
          'request_timeout',
        );
      if (error instanceof Error && error.name === 'AbortError') throw error;
      throw new CoreError(
        'KAT Core is unreachable. Check that the local service is running, then retry.',
        'core_unreachable',
      );
    } finally {
      clearTimeout(timeout);
      signal?.removeEventListener('abort', abort);
    }
    let data: unknown;
    try {
      data = await response.json();
    } catch {
      throw new CoreError(
        'Core returned an unreadable response. Check the service logs.',
        'invalid_response',
      );
    }
    if (!response.ok) {
      const payload = (typeof data === 'object' && data !== null ? data : {}) as {
        error?: { message?: string; code?: string };
        detail?: unknown;
      };
      const message =
        payload.error?.message ??
        (typeof payload.detail === 'string' ? payload.detail : undefined) ??
        (response.status === 401
          ? 'The access token is invalid. Reconnect with the current Core token.'
          : `Core request failed (${response.status}). Check the service logs.`);
      throw new CoreError(message, payload.error?.code ?? 'request_failed');
    }
    return data as T;
  }

  health(signal?: AbortSignal) {
    return this.request<Health>('/health', 'GET', undefined, signal);
  }
  capabilities() {
    return this.request<Capabilities>('/capabilities');
  }
  weatherLocations(query: string) {
    return this.request<WeatherLocation[]>('/capabilities/weather/locations', 'POST', { query });
  }
  setWeatherLocation(location: WeatherLocation | null) {
    return this.request<Capabilities>('/capabilities/weather', 'PUT', { location });
  }
  addReadRoot(label: string, path: string) {
    return this.request<ReadRoot>('/capabilities/roots', 'POST', { label, path });
  }
  removeReadRoot(id: string) {
    return this.request<{ status: string }>(`/capabilities/roots/${encodeURIComponent(id)}`, 'DELETE');
  }
  sessions(signal?: AbortSignal) {
    return this.request<Session[]>('/sessions', 'GET', undefined, signal);
  }
  createSession() {
    return this.request<Session>('/sessions', 'POST', {});
  }
  messages(id: string, signal?: AbortSignal) {
    return this.request<Message[]>(`/sessions/${encodeURIComponent(id)}/messages`, 'GET', undefined, signal);
  }
  sendMessage(id: string, content: string) {
    return this.request<ChatResponse>(
      `/sessions/${encodeURIComponent(id)}/messages`,
      'POST',
      { content },
      undefined,
      180000,
    );
  }
  approvals(id: string, signal?: AbortSignal) {
    return this.request<Approval[]>(
      `/approvals?session_id=${encodeURIComponent(id)}`,
      'GET',
      undefined,
      signal,
    );
  }
  decide(id: string, approved: boolean) {
    return this.request<ApprovalDecisionResponse>(
      `/approvals/${encodeURIComponent(id)}/decision`,
      'POST',
      { approved },
      undefined,
      180000,
    );
  }
  settings(signal?: AbortSignal) {
    return this.request<Settings>('/settings', 'GET', undefined, signal);
  }
  updateSettings(settings: SettingsUpdate) {
    return this.request<Settings>('/settings', 'PUT', settings);
  }
  probeProvider(settings: SettingsUpdate) {
    return this.request<ProviderStatus>('/providers/probe', 'POST', settings);
  }
  audit(signal?: AbortSignal) {
    return this.request<AuditEvent[]>('/audit?limit=100', 'GET', undefined, signal);
  }
  projects(signal?: AbortSignal) {
    return this.request<Project[]>('/projects', 'GET', undefined, signal);
  }
  createProject(name: string) {
    return this.request<Project>('/projects', 'POST', { name });
  }
  setSessionProject(id: string, project_id: string | null) {
    return this.request<Session>(`/sessions/${encodeURIComponent(id)}/scope`, 'PUT', { project_id });
  }
  setMemoryEnabled(enabled: boolean) {
    return this.request<{ enabled: boolean }>('/memory/settings', 'PUT', { enabled });
  }
  memories(filters: MemoryFilter = {}, signal?: AbortSignal) {
    const query = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== '') query.set(key, String(value));
    });
    return this.request<MemoryRecord[]>(`/memories?${query}`, 'GET', undefined, signal);
  }
  createMemory(body: MemoryCreate) {
    return this.request<MemoryRecord>('/memories', 'POST', body);
  }
  editMemory(id: string, body: MemoryFields, expected_revision: number) {
    return this.request<MemoryRecord>(`/memories/${encodeURIComponent(id)}`, 'PUT', {
      ...body,
      expected_revision,
    });
  }
  memoryStatus(id: string, status: Exclude<MemoryStatus, 'superseded'>, expected_revision: number) {
    return this.request<MemoryRecord>(`/memories/${encodeURIComponent(id)}/status`, 'POST', {
      status,
      expected_revision,
    });
  }
  supersedeMemory(id: string, replacement_id: string, expected_revision: number) {
    return this.request<MemoryRecord>(`/memories/${encodeURIComponent(id)}/supersede`, 'POST', {
      replacement_id,
      expected_revision,
    });
  }
  forgetMemory(id: string) {
    return this.request<{ status: 'forgotten' }>(`/memories/${encodeURIComponent(id)}/forget`, 'POST', {});
  }
  memoryRevisions(id: string, signal?: AbortSignal) {
    return this.request<MemoryRecord[]>(
      `/memories/${encodeURIComponent(id)}/revisions`,
      'GET',
      undefined,
      signal,
    );
  }
  memoryUsage(id: string, signal?: AbortSignal) {
    return this.request<MemoryUsage[]>(`/memories/${encodeURIComponent(id)}/usage`, 'GET', undefined, signal);
  }
  sessionMemoryUsage(id: string, signal?: AbortSignal) {
    return this.request<MemoryUsage[]>(
      `/sessions/${encodeURIComponent(id)}/memory-usage`,
      'GET',
      undefined,
      signal,
    );
  }
}

export function errorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : 'An unexpected error occurred. Check the Core logs and retry.';
}
