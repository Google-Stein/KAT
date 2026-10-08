import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { CoreApi } from './api';
import { MemoryView } from './MemoryView';
import { MemoryEditor } from './MemoryEditor';
import { FORGET_NOTICE } from './memory-labels';
import type { MemoryRecord } from './memory-types';

const preference = 'KAT should prefer local models when practical.';
const stamp = '2026-10-08T12:00:00+00:00';
const record: MemoryRecord = {
  id: 'memory-1',
  kind: 'semantic',
  content: preference,
  scope: 'personal',
  project_id: null,
  status: 'confirmed',
  origin: 'owner_explicit',
  sensitivity: 'normal',
  pinned: false,
  importance: 0,
  effective_at: null,
  expires_at: null,
  created_at: stamp,
  updated_at: stamp,
  last_reviewed_at: stamp,
  revision: 1,
  superseded_by: null,
  source_session_id: null,
  source_message_id: null,
  source_role: null,
  source_available: true,
};
let saved: MemoryRecord[];
let versions: MemoryRecord[];
let fetchMock: ReturnType<typeof vi.fn>;
const api = new CoreApi({ base_url: 'http://127.0.0.1:42800', token: 'test-private-token' });

beforeEach(() => {
  saved = [{ ...record }];
  versions = [{ ...record }];
  fetchMock = vi.fn(async (input: string, init: RequestInit) => {
    const path = new URL(input).pathname;
    const body = init.body ? JSON.parse(init.body as string) : {};
    let data: unknown;
    if (path === '/memories' && init.method === 'GET') data = saved;
    else if (path.endsWith('/revisions')) data = versions;
    else if (path.endsWith('/usage')) data = [];
    else if (path === '/memories' && init.method === 'POST') {
      saved.push({ ...record, ...body, id: 'memory-2' });
      data = saved.at(-1);
    } else if (init.method === 'PUT') {
      const next = { ...saved[0], ...body, revision: 2 };
      saved = [next];
      versions.unshift(next);
      data = next;
    } else if (path.endsWith('/forget')) {
      saved = [];
      versions = [];
      data = { status: 'forgotten' };
    } else if (path.endsWith('/status')) {
      saved[0] = { ...saved[0], status: body.status, revision: 2 };
      data = saved[0];
    } else throw new Error(`Unhandled memory test route ${path}`);
    return { ok: true, json: async () => data } as Response;
  });
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());
const show = (enabled = false, onToggle = vi.fn(async () => undefined)) =>
  render(
    <MemoryView
      api={api}
      enabled={enabled}
      projects={[]}
      onToggle={onToggle}
      onProject={vi.fn()}
      onSource={vi.fn()}
    />,
  );

describe('explicit memory workspace', () => {
  it('shows off/privacy state and only toggles on explicit action', async () => {
    const user = userEvent.setup();
    const toggle = vi.fn(async () => undefined);
    show(false, toggle);
    expect(screen.getByRole('checkbox', { name: 'Enable local memory retrieval' })).not.toBeChecked();
    expect(screen.getByText(/not encrypted by KAT/)).toBeInTheDocument();
    expect(screen.getByText(/OpenAI receives no memory records/)).toBeInTheDocument();
    expect(toggle).not.toHaveBeenCalled();
    await user.click(screen.getByRole('checkbox'));
    expect(toggle).toHaveBeenCalledWith(true);
  });
  it('requires review before creating, permits cancel and sends confirmed typed wording', async () => {
    const user = userEvent.setup();
    show();
    await user.click(screen.getByRole('button', { name: 'Add memory' }));
    let dialog = screen.getByRole('dialog');
    await user.type(within(dialog).getByLabelText('Memory wording'), 'My explicit preference');
    expect(fetchMock.mock.calls.filter(([, init]) => init.method === 'POST')).toHaveLength(0);
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Add memory' }));
    dialog = screen.getByRole('dialog');
    await user.type(within(dialog).getByLabelText('Memory wording'), 'My explicit preference');
    await user.click(within(dialog).getByRole('button', { name: 'Confirm & save memory' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    const create = fetchMock.mock.calls.find(([, init]) => init.method === 'POST');
    expect(JSON.parse(create![1].body)).toMatchObject({
      content: 'My explicit preference',
      confirmed: true,
      origin: 'owner_explicit',
      scope: 'personal',
    });
  });
  it('edits with a revision check, shows history, requires forget confirmation and discloses backups', async () => {
    const user = userEvent.setup();
    show();
    await user.click(await screen.findByRole('button', { name: `Inspect memory: ${preference}` }));
    await user.click(screen.getByRole('button', { name: 'Edit memory' }));
    const wording = screen.getByLabelText('Memory wording');
    await user.clear(wording);
    await user.type(wording, 'KAT should prefer cloud models when practical.');
    await user.click(screen.getByRole('button', { name: 'Save revision' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    const update = fetchMock.mock.calls.find(([, init]) => init.method === 'PUT');
    expect(JSON.parse(update![1].body)).toMatchObject({
      expected_revision: 1,
      content: 'KAT should prefer cloud models when practical.',
    });
    await screen.findByText('Revision history · 2');
    await user.click(screen.getByRole('button', { name: 'Forget memory' }));
    expect(screen.getByText(FORGET_NOTICE)).toBeInTheDocument();
    expect(saved).toHaveLength(1);
    await user.click(screen.getByRole('button', { name: 'Confirm forget' }));
    await waitFor(() => expect(saved).toHaveLength(0));
    expect(versions).toHaveLength(0);
  });
  it('does not invent evidence when source is unavailable', async () => {
    saved = [
      {
        ...record,
        origin: 'conversation_selection',
        source_session_id: 'old-session',
        source_message_id: 'old-message',
        source_role: 'user',
        source_available: false,
      },
    ];
    show();
    await userEvent
      .setup()
      .click(await screen.findByRole('button', { name: `Inspect memory: ${preference}` }));
    expect(screen.getByText(/original source is unavailable/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'View source conversation' })).not.toBeInTheDocument();
  });
  it('retains edited wording when a save fails and closes via Escape without saving', async () => {
    const save = vi.fn(async () => {
      throw new Error('Refresh before saving your review.');
    });
    const close = vi.fn();
    render(<MemoryEditor projects={[]} text={preference} source onSave={save} onClose={close} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Confirm & save memory' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Refresh before saving');
    expect(screen.getByLabelText('Memory wording')).toHaveValue(preference);
    expect(close).not.toHaveBeenCalled();
    await user.keyboard('{Escape}');
    expect(close).toHaveBeenCalledOnce();
  });
});
