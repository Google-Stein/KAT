import { afterEach, describe, expect, it, vi } from 'vitest';
import { CoreApi, CoreError, validateConnection } from './api';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe('local Core connection', () => {
  it('allows only loopback HTTP origins with a token', () => {
    expect(validateConnection({ base_url: 'http://127.0.0.1:42800/', token: ' local-token ' })).toEqual({
      base_url: 'http://127.0.0.1:42800',
      token: 'local-token',
    });
    expect(validateConnection({ base_url: 'http://localhost:42800', token: 'token' }).base_url).toBe(
      'http://localhost:42800',
    );
    for (const base_url of [
      'https://example.com',
      'http://127.0.0.1.evil.com',
      'http://192.168.1.1',
      'http://user:password@localhost',
      'http://localhost/api',
      'http://localhost?token=secret',
      'file:///tmp/service',
      'broken',
    ]) {
      expect(() => validateConnection({ base_url, token: 'token' })).toThrow(CoreError);
    }
    expect(() => validateConnection({ base_url: 'http://localhost', token: ' ' })).toThrow(/access token/);
  });

  it('sends bearer authentication without browser credentials and encodes identifiers', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
    vi.stubGlobal('fetch', fetchMock);
    await new CoreApi({ base_url: 'http://localhost:42800', token: 'private-token' }).messages('session/id');
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:42800/sessions/session%2Fid/messages',
      expect.objectContaining({
        credentials: 'omit',
        cache: 'no-store',
        headers: { Authorization: 'Bearer private-token' },
      }),
    );
  });

  it('preserves safe structured server errors and network recovery guidance', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: false,
        status: 503,
        json: async () => ({
          error: { code: 'provider_unavailable', message: 'Configure OPENAI_API_KEY before chatting.' },
        }),
      })
      .mockRejectedValueOnce(new TypeError('Failed to fetch'));
    vi.stubGlobal('fetch', fetchMock);
    const api = new CoreApi({ base_url: 'http://localhost', token: 'token' });
    await expect(api.health()).rejects.toMatchObject({
      code: 'provider_unavailable',
      message: 'Configure OPENAI_API_KEY before chatting.',
    });
    await expect(api.health()).rejects.toMatchObject({ code: 'core_unreachable' });
  });

  it('handles invalid server responses and authentication errors', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => {
          throw new SyntaxError('bad JSON');
        },
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Invalid access token' }),
      });
    vi.stubGlobal('fetch', fetchMock);
    const api = new CoreApi({ base_url: 'http://localhost', token: 'token' });
    await expect(api.health()).rejects.toMatchObject({ code: 'invalid_response' });
    await expect(api.health()).rejects.toThrow('Invalid access token');
  });

  it('bounds stalled requests and provides retry guidance', async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_input: string, init: RequestInit) =>
          new Promise((_resolve, reject) => {
            init.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
          }),
      ),
    );
    const api = new CoreApi({ base_url: 'http://localhost', token: 'token' });
    const failure = expect(api.health()).rejects.toMatchObject({ code: 'request_timeout' });
    await vi.advanceTimersByTimeAsync(15000);
    await failure;
  });
});
