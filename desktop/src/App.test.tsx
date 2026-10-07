import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { invoke, isTauri } from '@tauri-apps/api/core';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import type { Approval, AuditEvent, Message, Session, Settings } from './types';

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
  model: 'gpt-4.1-mini',
  api_key_configured: true,
  application_allowlist: [{ id: 'notepad', label: 'Notepad' }],
  require_approval_for_low_risk: false,
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
let fetchMock: ReturnType<typeof vi.fn>;

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
    if (url.pathname === '/health')
      return response({ status: 'ok', version: '0.1.0', provider_ready: state.ready });
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
      return response(state.approvals[0]);
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
  it('restores persisted history, creates sessions, and sends a text conversation', async () => {
    const user = await connect();
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
