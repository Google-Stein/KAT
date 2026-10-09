import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { invoke, isTauri } from '@tauri-apps/api/core';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import type {
  Approval,
  AuditEvent,
  Message,
  ProviderCredentialsChange,
  ProviderCredentialsStatus,
  Session,
  Settings,
} from './types';

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn(), isTauri: vi.fn(() => false) }));

const timestamp = '2026-10-07T12:00:00Z';
const firstSession: Session = {
  id: 'session-1',
  title: 'A thoughtful question',
  created_at: timestamp,
  updated_at: timestamp,
};
const savedMessage: Message = {
  id: 'message-1',
  session_id: firstSession.id,
  role: 'assistant',
  content: 'Your saved conversation is here.',
  created_at: timestamp,
};
const pendingApproval: Approval = {
  id: 'approval-1',
  session_id: firstSession.id,
  tool_name: 'open_application',
  arguments: { application_id: 'notepad' },
  risk: 'medium',
  status: 'pending',
  created_at: timestamp,
};
const defaultSettings: Settings = {
  provider: 'openai',
  local_endpoint: 'http://127.0.0.1:11434',
  model: 'gpt-4.1-mini',
  api_key_configured: true,
  application_allowlist: [{ id: 'notepad', label: 'Notepad' }],
  require_approval_for_low_risk: false,
  memory_enabled: false,
};

interface MockState {
  sessions: Session[];
  messages: Record<string, Message[]>;
  approvals: Approval[];
  settings: Settings;
  ready: boolean;
  chatFailure: boolean;
  failSessionRefresh: boolean;
  chatApproval: boolean;
  events: AuditEvent[];
}
let state: MockState;
let fetchMock: ReturnType<typeof vi.fn<(input: string, init?: RequestInit) => Promise<Response>>>;

function response(data: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => data } as Response;
}

beforeEach(() => {
  vi.mocked(invoke).mockReset();
  vi.mocked(isTauri).mockReturnValue(false);
  state = {
    sessions: [firstSession],
    messages: { 'session-1': [savedMessage] },
    approvals: [],
    settings: { ...defaultSettings },
    ready: true,
    chatFailure: false,
    failSessionRefresh: false,
    chatApproval: false,
    events: [],
  };
  fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
    const url = new URL(input);
    const method = init?.method ?? 'GET';
    if (url.pathname === '/projects' || url.pathname.endsWith('/memory-usage')) return response([]);
    if (url.pathname === '/memories' && method === 'POST')
      return response({ ...JSON.parse(init?.body as string), id: 'explicit-memory' }, 201);
    if (url.pathname === '/health')
      return response({ status: 'ok', version: '0.1.0', provider_ready: state.ready });
    if (url.pathname === '/providers/probe')
      return response({
        provider: state.settings.provider,
        status: 'configured',
        message: 'Provider configured.',
        models: [],
        tool_calling: true,
        error_code: null,
      });
    if (url.pathname === '/settings' && method === 'GET') return response(state.settings);
    if (url.pathname === '/settings' && method === 'PUT') {
      state.settings = { ...state.settings, ...JSON.parse(init?.body as string) };
      return response(state.settings);
    }
    if (url.pathname === '/sessions' && method === 'GET') {
      if (state.failSessionRefresh) throw new TypeError('Failed to fetch');
      return response(state.sessions);
    }
    if (url.pathname === '/sessions' && method === 'POST') {
      const session = {
        ...firstSession,
        id: `session-${state.sessions.length + 1}`,
        title: 'New conversation',
      };
      state.sessions = [session, ...state.sessions];
      state.messages[session.id] = [];
      return response(session);
    }
    if (url.pathname.endsWith('/messages')) {
      const sessionId = url.pathname.split('/')[2];
      if (method === 'GET') return response(state.messages[sessionId] ?? []);
      if (state.chatFailure)
        return response(
          {
            error: { code: 'provider_error', message: 'The provider is temporarily unavailable. Try again.' },
          },
          502,
        );
      const content = (JSON.parse(init?.body as string) as { content: string }).content;
      const user_message: Message = {
        ...savedMessage,
        id: 'new-user',
        session_id: sessionId,
        role: 'user',
        content,
      };
      const assistant_message: Message = {
        ...savedMessage,
        id: 'new-assistant',
        session_id: sessionId,
        content: state.chatApproval ? 'May I open Notepad?' : 'Let’s think about this together.',
      };
      state.messages[sessionId] = [...state.messages[sessionId], user_message, assistant_message];
      if (state.chatApproval) state.approvals = [{ ...pendingApproval, session_id: sessionId }];
      return response({ user_message, assistant_message, approvals: state.approvals });
    }
    if (url.pathname === '/approvals')
      return response(
        state.approvals.filter((approval) => approval.session_id === url.searchParams.get('session_id')),
      );
    if (url.pathname.endsWith('/decision')) {
      const approved = (JSON.parse(init?.body as string) as { approved: boolean }).approved;
      const approval = state.approvals[0];
      state.approvals = [{ ...approval, status: approved ? 'completed' : 'denied' }];
      state.messages[approval.session_id] = [
        ...state.messages[approval.session_id],
        {
          ...savedMessage,
          id: 'tool-result',
          role: 'tool',
          content: approved ? 'Notepad opened successfully.' : 'The request was denied.',
        },
      ];
      return response({ ...state.approvals[0], assistant_message: null, new_approvals: [] });
    }
    if (url.pathname === '/audit') return response(state.events);
    throw new Error(`Unhandled request ${method} ${url.pathname}`);
  });
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

async function connect() {
  const user = userEvent.setup();
  render(<App />);
  await user.type(screen.getByLabelText('Core access token'), 'memory-only-token');
  await user.click(screen.getByRole('button', { name: 'Connect to KAT' }));
  await screen.findByText('Your saved conversation is here.');
  return user;
}

describe('KAT desktop workflow', () => {
  it('shows reading/thinking and the automatic local answer without another owner message', async () => {
    state.settings.provider = 'ollama';
    const read: Approval = {
      ...pendingApproval,
      tool_name: 'read_text_file',
      arguments: { root_id: 'root-registered', relative_path: 'briefing.txt' },
      continuation_policy: 'local_result',
      continuation: {
        origin_user_message_id: 'original-user',
        provider: 'ollama',
        state: 'waiting',
        reason: null,
        count: 0,
        assistant_message_id: null,
      },
    };
    state.approvals = [read];
    const original = fetchMock.getMockImplementation()!;
    let release: (() => void) | undefined;
    fetchMock.mockImplementation(async (input, init) => {
      if (!input.endsWith('/decision')) return original(input, init);
      state.approvals = [{ ...read, status: 'approved' }];
      await new Promise<void>((resolve) => {
        release = resolve;
      });
      const assistant = { ...savedMessage, id: 'continued', content: 'Copper Falcon; November 12.' };
      const result = {
        ...read,
        status: 'completed' as const,
        continuation: {
          ...read.continuation!,
          state: 'completed' as const,
          count: 1,
          assistant_message_id: assistant.id,
        },
      };
      state.approvals = [result];
      state.messages[firstSession.id].push(assistant);
      return response({ ...result, assistant_message: assistant, new_approvals: [] });
    });
    const user = await connect();
    await user.click(await screen.findByRole('button', { name: 'Allow once' }));
    await screen.findByText('Reading…');
    state.approvals = [
      {
        ...read,
        status: 'completed',
        continuation: {
          ...read.continuation!,
          state: 'running',
          count: 1,
        },
      },
    ];
    await screen.findByText('Thinking…');
    release!();
    await screen.findByText('Copper Falcon; November 12.');
    await waitFor(() => expect(screen.getByLabelText('Message KAT')).toBeEnabled());
    expect(
      fetchMock.mock.calls.filter(([url, init]) => url.endsWith('/messages') && init?.method === 'POST'),
    ).toHaveLength(0);
  });

  it('shows a new chained approval and keeps the composer blocked until it is resolved', async () => {
    const first: Approval = {
      ...pendingApproval,
      tool_name: 'read_text_file',
      arguments: { relative_path: 'a.txt' },
    };
    state.approvals = [first];
    const original = fetchMock.getMockImplementation()!;
    fetchMock.mockImplementation(async (input, init) => {
      if (!input.endsWith('/decision')) return original(input, init);
      const next: Approval = { ...first, id: 'second-read', arguments: { relative_path: 'b.txt' } };
      state.approvals = [{ ...first, status: 'completed' }, next];
      const assistant = { ...savedMessage, id: 'next-approval-reply', content: 'Please approve b.txt.' };
      state.messages[firstSession.id].push(assistant);
      return response({ ...state.approvals[0], assistant_message: assistant, new_approvals: [next] });
    });
    const user = await connect();
    await user.click(await screen.findByRole('button', { name: 'Allow once' }));
    await screen.findByText('Please approve b.txt.');
    const card = await screen.findByRole('region', { name: 'Approval for read_text_file' });
    expect(within(card).getByText(/"relative_path": "b.txt"/)).toBeVisible();
    expect(screen.getByLabelText('Message KAT')).toBeDisabled();
  });

  it('resolves simultaneous file approvals one at a time before showing the final answer', async () => {
    const first: Approval = {
      ...pendingApproval,
      id: 'read-a',
      tool_name: 'read_text_file',
      arguments: { relative_path: 'a.txt' },
    };
    const second: Approval = { ...first, id: 'read-b', arguments: { relative_path: 'b.txt' } };
    state.approvals = [first, second];
    const original = fetchMock.getMockImplementation()!;
    fetchMock.mockImplementation(async (input, init) => {
      if (!input.endsWith('/decision')) return original(input, init);
      const id = input.includes('/read-a/') ? first.id : second.id;
      state.approvals = state.approvals.map((a) => (a.id === id ? { ...a, status: 'completed' } : a));
      const pending = state.approvals.filter((a) => a.status === 'pending');
      const assistant = pending.length
        ? null
        : { ...savedMessage, id: 'comparison', content: 'Two approved files compared.' };
      if (assistant) state.messages[firstSession.id].push(assistant);
      return response({
        ...state.approvals.find((a) => a.id === id)!,
        assistant_message: assistant,
        new_approvals: pending,
      });
    });
    const user = await connect();
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'Allow once' })).toHaveLength(2));
    await user.click(screen.getAllByRole('button', { name: 'Allow once' })[0]);
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'Allow once' })).toHaveLength(1));
    expect(screen.getByLabelText('Message KAT')).toBeDisabled();
    expect(screen.queryByText('Two approved files compared.')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Allow once' }));
    await screen.findByText('Two approved files compared.');
    await waitFor(() => expect(screen.getByLabelText('Message KAT')).toBeEnabled());
    expect(fetchMock.mock.calls.filter(([url]) => url.endsWith('/decision'))).toHaveLength(2);
  });

  it('explains cloud suppression while preserving the locally completed read', async () => {
    state.approvals = [
      {
        ...pendingApproval,
        tool_name: 'read_text_file',
        status: 'completed',
        continuation_policy: 'local_result',
        continuation: {
          origin_user_message_id: 'cloud-user',
          provider: 'openai',
          state: 'suppressed',
          reason: 'cloud_policy',
          count: 0,
          assistant_message_id: null,
        },
      },
    ];
    await connect();
    expect(await screen.findByText(/file contents were not sent to the cloud provider/)).toBeVisible();
    expect(screen.getByLabelText('Message KAT')).toBeEnabled();
  });

  it('shows exact inserted memory evidence without interpreting its wording as markup', async () => {
    const original = fetchMock.getMockImplementation()!;
    const evidence = 'KAT should prefer local models. <img src=x onerror=alert(1)>';
    fetchMock.mockImplementation(async (input, init) =>
      input.includes('/memory-usage')
        ? response([
            {
              memory_id: 'reviewed-memory',
              revision: 2,
              session_id: firstSession.id,
              assistant_message_id: savedMessage.id,
              provider: 'ollama',
              used_at: timestamp,
              content: evidence,
              forgotten: false,
            },
          ])
        : original(input, init),
    );
    const user = await connect();
    await user.click(await screen.findByText('Memories used · 1'));
    expect(screen.getByText(evidence)).toBeVisible();
    expect(screen.getByText('Revision 2 · local')).toBeInTheDocument();
    expect(document.querySelector('.memory-inspector img')).toBeNull();
  });
  it('Remember reviews a selected message before explicitly saving provenance', async () => {
    const user = await connect();
    await user.click(screen.getByRole('button', { name: 'Remember' }));
    const review = screen.getByRole('dialog');
    expect(within(review).getByLabelText('Memory wording')).toHaveValue(savedMessage.content);
    expect(
      fetchMock.mock.calls.filter(
        ([, init]) => init?.method === 'POST' && String(init?.body).includes('confirmed'),
      ),
    ).toHaveLength(0);
    await user.click(within(review).getByRole('button', { name: 'Confirm & save memory' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/memories'),
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"source_message_id":"message-1"'),
      }),
    );
    const call = fetchMock.mock.calls.find(
      ([path, init]) => path.endsWith('/memories') && init?.method === 'POST',
    );
    expect(JSON.parse(call![1]!.body as string)).toMatchObject({
      confirmed: true,
      origin: 'conversation_selection',
      source_session_id: 'session-1',
      content: savedMessage.content,
    });
  });
  it('restores persisted history, creates sessions, and sends a text conversation', async () => {
    const user = await connect();
    expect(screen.getByLabelText('KAT version')).toHaveTextContent('0.1.0');
    expect(screen.getByLabelText('Selected inference provider')).toHaveTextContent('OpenAI · cloud');
    await user.click(screen.getByRole('button', { name: /New conversation/ }));
    await screen.findByRole('heading', { name: 'Hello. I’m KAT.' });
    await user.type(screen.getByLabelText('Message KAT'), 'Can you help me plan today?');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    await screen.findByText('Let’s think about this together.');
    expect(screen.getByText('Can you help me plan today?')).toBeVisible();
    expect(state.sessions).toHaveLength(2);
    await user.click(screen.getByRole('button', { name: firstSession.title }));
    await screen.findByText('Your saved conversation is here.');
    expect(screen.queryByText('Can you help me plan today?')).not.toBeInTheDocument();
    expect(localStorage.length).toBe(0);
  });

  it('loads pending approvals after restart and allows one validated request', async () => {
    state.approvals = [pendingApproval];
    const user = await connect();
    const card = await screen.findByRole('region', { name: 'Approval for open_application' });
    expect(within(card).getByText('medium risk')).toBeVisible();
    expect(within(card).getByText(/"application_id": "notepad"/)).toBeVisible();
    expect(screen.getByLabelText('Message KAT')).toBeDisabled();
    await user.click(within(card).getByRole('button', { name: 'Allow once' }));
    await screen.findByText('Notepad opened successfully.');
    expect(screen.queryByRole('region', { name: 'Approval for open_application' })).not.toBeInTheDocument();
    expect(screen.getByLabelText('Message KAT')).toBeEnabled();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/approvals/approval-1/decision'),
      expect.objectContaining({ body: '{"approved":true}' }),
    );
  });

  it('shows new tool requests from chat and records a denial', async () => {
    state.chatApproval = true;
    const user = await connect();
    await user.type(screen.getByLabelText('Message KAT'), 'Open Notepad.');
    await user.keyboard('{Enter}');
    const card = await screen.findByRole('region', { name: 'Approval for open_application' });
    await user.click(within(card).getByRole('button', { name: 'Deny' }));
    await screen.findByText('The request was denied.');
    expect(state.approvals[0].status).toBe('denied');
  });

  it('surfaces provider errors and keeps the draft available for retry', async () => {
    state.chatFailure = true;
    const user = await connect();
    await user.type(screen.getByLabelText('Message KAT'), 'A message to retry');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    await screen.findByRole('alert');
    expect(screen.getByRole('alert')).toHaveTextContent(
      'The provider is temporarily unavailable. Try again.',
    );
    await waitFor(() => expect(screen.getByLabelText('Message KAT')).toHaveValue('A message to retry'));
    state.chatFailure = false;
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    await screen.findByText('Let’s think about this together.');
  });

  it('does not offer to resend a successful message when the sidebar refresh fails', async () => {
    const user = await connect();
    state.failSessionRefresh = true;
    await user.type(screen.getByLabelText('Message KAT'), 'A saved message');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    await screen.findByText('Let’s think about this together.');
    expect(await screen.findByRole('alert')).toHaveTextContent('Your message was saved.');
    expect(screen.getByLabelText('Message KAT')).toHaveValue('');
    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled();
  });

  it('saves model and permission preferences without requesting an API key', async () => {
    const user = await connect();
    await user.click(screen.getByRole('button', { name: 'Settings' }));
    expect(screen.getByText('API key configured')).toBeVisible();
    expect(screen.getByText('Notepad')).toBeVisible();
    await user.clear(screen.getByLabelText('Model'));
    await user.type(screen.getByLabelText('Model'), 'gpt-4.1');
    await user.click(screen.getByLabelText(/Ask before low-risk tools/));
    await user.click(screen.getByRole('button', { name: 'Save settings' }));
    await screen.findByText('Settings saved');
    expect(state.settings.model).toBe('gpt-4.1');
    expect(state.settings.require_approval_for_low_risk).toBe(true);
    expect(screen.queryByLabelText(/API key/)).not.toBeInTheDocument();
  });

  it('renders audit evidence and untrusted model text without evaluating HTML', async () => {
    state.messages[firstSession.id] = [{ ...savedMessage, content: '<script>alert("untrusted")</script>' }];
    state.events = [
      {
        id: 'audit-1',
        timestamp,
        event: 'tool_requested',
        session_id: firstSession.id,
        tool_name: 'open_application',
        approval_id: 'approval-1',
        details: { application_id: 'notepad' },
      },
    ];
    const user = userEvent.setup();
    const { container } = render(<App />);
    await user.type(screen.getByLabelText('Core access token'), 'token');
    await user.click(screen.getByRole('button', { name: 'Connect to KAT' }));
    await screen.findByText('<script>alert("untrusted")</script>');
    expect(container.querySelector('script')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Activity & approvals' }));
    await screen.findByText('tool requested');
    await user.click(screen.getByText('View event details'));
    expect(screen.getByText(/"application_id": "notepad"/)).toBeVisible();
  });

  it('explains missing provider credentials and disables chat', async () => {
    state.ready = false;
    state.settings.api_key_configured = false;
    const user = await connect();
    expect(screen.getByLabelText('Message KAT')).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'View settings' }));
    expect(screen.getByText('API key required')).toBeVisible();
    expect(screen.getByText(/Set OPENAI_API_KEY/)).toBeVisible();
  });

  it('connects through the native launcher and forgets connection state on disconnect', async () => {
    vi.mocked(isTauri).mockReturnValue(true);
    vi.mocked(invoke).mockResolvedValue({ base_url: 'http://127.0.0.1:42800', token: 'native-token' });
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('Your saved conversation is here.');
    expect(invoke).toHaveBeenCalledWith('core_connection');
    expect(screen.queryByLabelText('Core access token')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Local Core connected/ }));
    expect(screen.getByRole('heading', { name: 'Welcome to KAT.' })).toBeVisible();
    expect(localStorage.length).toBe(0);
  });

  it('restarts a failed native Core only when the user retries', async () => {
    vi.mocked(isTauri).mockReturnValue(true);
    vi.mocked(invoke)
      .mockRejectedValueOnce(new Error('Core could not start. Check the local log.'))
      .mockResolvedValueOnce({ base_url: 'http://127.0.0.1:42800', token: 'restarted-token' });
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Core could not start.');
    expect(vi.mocked(invoke).mock.calls.map(([command]) => command)).toEqual(['core_connection']);
    await user.click(screen.getByRole('button', { name: 'Retry local connection' }));
    await screen.findByText('Your saved conversation is here.');
    expect(vi.mocked(invoke).mock.calls.map(([command]) => command)).toEqual([
      'core_connection',
      'restart_core',
    ]);
  });
});

describe('Windows provider credential controls', () => {
  const oldConnection = { base_url: 'http://127.0.0.1:42800', token: 'initial-native-token' };
  const restartedConnection = { ...oldConnection, token: 'rotated-native-token' };
  let credentials: ProviderCredentialsStatus;
  let configure: () => Promise<ProviderCredentialsChange>;
  let remove: () => Promise<ProviderCredentialsChange>;

  beforeEach(() => {
    vi.mocked(isTauri).mockReturnValue(true);
    credentials = { supported: true, stored: false, environment_configured: false };
    configure = async () => ({ changed: false, connection: null, status: credentials });
    remove = async () => ({ changed: false, connection: null, status: credentials });
    vi.mocked(invoke).mockImplementation(async (command) => {
      switch (command) {
        case 'core_connection':
          return oldConnection;
        case 'provider_credentials_status':
          return credentials;
        case 'configure_provider_credentials':
          return configure();
        case 'remove_provider_credentials':
          return remove();
        default:
          throw new Error(`Unexpected native command ${command}`);
      }
    });
  });

  async function openSettings() {
    const user = userEvent.setup();
    const rendered = render(<App />);
    await screen.findByText('Your saved conversation is here.');
    await user.click(screen.getByRole('button', { name: 'Settings' }));
    await waitFor(() => expect(invoke).toHaveBeenCalledWith('provider_credentials_status'));
    return { user, ...rendered };
  }

  it('sets a key through Windows and refreshes configuration using the rotated runtime token', async () => {
    state.ready = false;
    state.settings.api_key_configured = false;
    configure = async () => {
      credentials = { ...credentials, stored: true };
      state.ready = true;
      state.settings = { ...state.settings, api_key_configured: true };
      return { changed: true, connection: restartedConnection, status: credentials };
    };
    const { user, container } = await openSettings();
    await user.clear(screen.getByLabelText('Model'));
    await user.type(screen.getByLabelText('Model'), 'gpt-4.1');
    await user.click(screen.getByLabelText(/Ask before low-risk tools/));
    await user.click(screen.getByRole('button', { name: 'Set API key' }));
    await screen.findByText('API key saved. Local Core restarted.');
    expect(screen.getByText('API key configured')).toBeVisible();
    expect(screen.getByText(/Windows saved key: present/)).toBeVisible();
    expect(screen.getByLabelText('Model')).toHaveValue('gpt-4.1');
    expect(screen.getByLabelText(/Ask before low-risk tools/)).toBeChecked();
    expect(container.querySelector('input[type="password"]')).toBeNull();
    expect(screen.queryByLabelText(/API key/)).not.toBeInTheDocument();
    expect(invoke).toHaveBeenCalledWith('configure_provider_credentials');
    const restartedCalls = fetchMock.mock.calls.filter(
      ([, init]) => (init?.headers as Record<string, string>).Authorization === 'Bearer rotated-native-token',
    );
    expect(restartedCalls.map(([url]) => new URL(url).pathname)).toEqual(
      expect.arrayContaining(['/health', '/settings', '/sessions']),
    );
    await user.click(screen.getByRole('button', { name: firstSession.title }));
    await screen.findByText('Your saved conversation is here.');
    expect(screen.getByLabelText('Message KAT')).toBeEnabled();
    expect(localStorage.length).toBe(0);
  });

  it('keeps the selected conversation and unsent chat draft after replacing the key', async () => {
    const secondSession = { ...firstSession, id: 'session-2', title: 'A second conversation' };
    state.sessions.push(secondSession);
    state.messages[secondSession.id] = [{ ...savedMessage, id: 'message-2', content: 'Second history.' }];
    credentials = { ...credentials, stored: true };
    configure = async () => ({ changed: true, connection: restartedConnection, status: credentials });
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('Your saved conversation is here.');
    await user.click(screen.getByRole('button', { name: secondSession.title }));
    await screen.findByText('Second history.');
    await user.type(screen.getByLabelText('Message KAT'), 'An unsent thought');
    await user.click(screen.getByRole('button', { name: 'Settings' }));
    await user.click(await screen.findByRole('button', { name: 'Replace saved key' }));
    await screen.findByText('API key saved. Local Core restarted.');
    await user.click(screen.getByRole('button', { name: secondSession.title }));
    await screen.findByText('Second history.');
    expect(screen.getByLabelText('Message KAT')).toHaveValue('An unsent thought');
    expect(screen.queryByText('Your saved conversation is here.')).not.toBeInTheDocument();
  });

  it('treats cancelling the Windows dialog as neutral and does not restart or refresh Core', async () => {
    const { user } = await openSettings();
    const initialHealthCalls = fetchMock.mock.calls.filter(([url]) => new URL(url).pathname === '/health');
    await user.click(screen.getByRole('button', { name: 'Set API key' }));
    await screen.findByText('API key setup cancelled.');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Set API key' })).toBeEnabled();
    expect(fetchMock.mock.calls.filter(([url]) => new URL(url).pathname === '/health')).toHaveLength(
      initialHealthCalls.length,
    );
    expect(invoke).not.toHaveBeenCalledWith('restart_core');
  });

  it('removes only the saved key and explains when an environment key still configures Core', async () => {
    credentials = { ...credentials, stored: true, environment_configured: true };
    remove = async () => {
      credentials = { ...credentials, stored: false };
      return { changed: true, connection: restartedConnection, status: credentials };
    };
    const { user } = await openSettings();
    await user.click(await screen.findByRole('button', { name: 'Remove saved key' }));
    await screen.findByText('Saved key removed. Local Core restarted.');
    expect(screen.getByText('API key configured')).toBeVisible();
    expect(screen.getByText(/Windows saved key: not set/)).toBeVisible();
    expect(screen.getByText(/process environment key is configured and takes precedence/)).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Remove saved key' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Set API key' })).toBeEnabled();
  });

  it('disables model conversation after removing the only configured key', async () => {
    credentials = { ...credentials, stored: true };
    remove = async () => {
      credentials = { ...credentials, stored: false };
      state.ready = false;
      state.settings = { ...state.settings, api_key_configured: false };
      return { changed: true, connection: restartedConnection, status: credentials };
    };
    const { user } = await openSettings();
    await user.click(await screen.findByRole('button', { name: 'Remove saved key' }));
    await screen.findByText('Saved key removed. Local Core restarted.');
    expect(screen.getByText('API key required')).toBeVisible();
    await user.click(screen.getByRole('button', { name: firstSession.title }));
    await screen.findByText('Your saved conversation is here.');
    expect(screen.getByLabelText('Message KAT')).toBeDisabled();
  });

  it('refreshes credential status after a native failure without exposing its raw diagnostic', async () => {
    configure = async () => {
      credentials = { ...credentials, stored: true };
      throw new Error('Sensitive diagnostic: sk-test-never-display-this');
    };
    const { user } = await openSettings();
    await user.click(screen.getByRole('button', { name: 'Set API key' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not complete the key configuration');
    await screen.findByRole('button', { name: 'Replace saved key' });
    expect(screen.queryByText(/sk-test-never-display-this/)).not.toBeInTheDocument();
    expect(
      vi.mocked(invoke).mock.calls.filter(([name]) => name === 'provider_credentials_status'),
    ).toHaveLength(2);
    expect(screen.getByRole('button', { name: /Local Core connected/ })).toBeEnabled();
  });

  it('prevents duplicate native actions while a dialog or restart is pending', async () => {
    let finish: ((result: ProviderCredentialsChange) => void) | undefined;
    configure = () =>
      new Promise((resolve) => {
        finish = resolve;
      });
    const { user } = await openSettings();
    await user.click(screen.getByRole('button', { name: 'Set API key' }));
    expect(screen.getByRole('button', { name: 'Set API key' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Please wait…' })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Local Core connected/ })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Set API key' }));
    expect(
      vi.mocked(invoke).mock.calls.filter(([name]) => name === 'configure_provider_credentials'),
    ).toHaveLength(1);
    finish?.({ changed: false, connection: null, status: credentials });
    await screen.findByText('API key setup cancelled.');
  });

  it('offers a retry when credential status cannot be read', async () => {
    const originalInvoke = vi.mocked(invoke).getMockImplementation();
    vi.mocked(invoke).mockImplementationOnce(() => Promise.resolve(oldConnection));
    vi.mocked(invoke).mockImplementationOnce(() => Promise.reject(new Error('Credential store unavailable')));
    const { user } = await openSettings();
    expect(await screen.findByText('Could not check Windows credentials. Try again.')).toBeVisible();
    vi.mocked(invoke).mockImplementation(originalInvoke!);
    await user.click(screen.getByRole('button', { name: 'Retry credential check' }));
    await screen.findByRole('button', { name: 'Set API key' });
    expect(screen.queryByText('Could not check Windows credentials. Try again.')).not.toBeInTheDocument();
  });

  it('shows environment setup on non-Windows without offering credential commands', async () => {
    credentials = { ...credentials, supported: false };
    const { container } = await openSettings();
    await screen.findByText('Saved key management is available in the Windows desktop application.');
    expect(screen.getByText(/Set OPENAI_API_KEY/)).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Set API key' })).not.toBeInTheDocument();
    expect(container.querySelector('input[type="password"]')).toBeNull();
    expect(invoke).not.toHaveBeenCalledWith('configure_provider_credentials');
    expect(invoke).not.toHaveBeenCalledWith('remove_provider_credentials');
  });

  it('never calls native credential commands from the browser development interface', async () => {
    vi.mocked(isTauri).mockReturnValue(false);
    const user = await connect();
    await user.click(screen.getByRole('button', { name: 'Settings' }));
    expect(screen.getByText(/Set OPENAI_API_KEY/)).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Set API key' })).not.toBeInTheDocument();
    expect(invoke).not.toHaveBeenCalled();
    expect(screen.queryByLabelText(/API key/)).not.toBeInTheDocument();
  });
});

describe('Local provider selection', () => {
  it('saves local routing and endpoint without asking for a cloud key', async () => {
    state.settings.api_key_configured = false;
    const user = await connect();
    await user.click(screen.getByRole('button', { name: 'Settings' }));
    await user.selectOptions(screen.getByLabelText('Provider'), 'ollama');
    expect(screen.queryByRole('button', { name: 'Set API key' })).not.toBeInTheDocument();
    expect(screen.getByLabelText('Model')).toHaveValue('qwen3:8b');
    expect(screen.getByLabelText('Local backend address')).toHaveValue('http://127.0.0.1:11434');
    await user.click(screen.getByRole('button', { name: 'Save settings' }));
    await screen.findByText('Settings saved');
    expect(state.settings.provider).toBe('ollama');
    expect(state.settings.local_endpoint).toBe('http://127.0.0.1:11434');
    expect(screen.getByText(/inference stay on this computer/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: firstSession.title }));
    expect(screen.getByLabelText('Selected inference provider')).toHaveTextContent('Ollama · local');
  });
});
