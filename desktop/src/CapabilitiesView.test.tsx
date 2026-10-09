import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { invoke } from '@tauri-apps/api/core';
import { CoreApi } from './api';
import { CapabilitiesView } from './CapabilitiesView';
import { ToolResultView } from './ToolResultView';
import type { Capabilities } from './capability-types';

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn() }));
const location = {
  label: 'Thornton, Colorado',
  latitude: 39.868,
  longitude: -104.972,
  timezone: 'America/Denver',
};
const configuration: Capabilities = {
  weather_provider: 'open-meteo',
  weather_location: null,
  system_available: true,
  read_roots: [],
};
const api = new CoreApi({ base_url: 'http://127.0.0.1:42800', token: 'synthetic-test-token' });
beforeEach(() => {
  vi.restoreAllMocks();
  vi.mocked(invoke).mockReset();
  vi.spyOn(api, 'capabilities').mockResolvedValue(configuration);
});

it('explains external weather and confirms a location before saving', async () => {
  const resolve = vi.spyOn(api, 'weatherLocations').mockResolvedValue([location]);
  const save = vi
    .spyOn(api, 'setWeatherLocation')
    .mockResolvedValue({ ...configuration, weather_location: location });
  render(<CapabilitiesView api={api} native />);
  expect(screen.getByText(/weather uses the internet/i)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Weather location'), { target: { value: 'Thornton, Colorado' } });
  fireEvent.click(screen.getByText('Find locations'));
  await screen.findByText('Use Thornton, Colorado');
  expect(resolve).toHaveBeenCalledWith('Thornton, Colorado');
  expect(save).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText('Use Thornton, Colorado'));
  await screen.findByText('Weather location saved');
  expect(save).toHaveBeenCalledWith(location);
});

it('native folder selection needs explicit add and advertises privacy', async () => {
  vi.mocked(invoke).mockResolvedValue('C:\\Fixtures');
  const add = vi
    .spyOn(api, 'addReadRoot')
    .mockResolvedValue({ id: 'root-fixture', label: 'Test folder', path: 'C:\\Fixtures' });
  render(<CapabilitiesView api={api} native />);
  fireEvent.change(screen.getByLabelText('Folder label'), { target: { value: 'Test folder' } });
  expect(screen.getByLabelText('Read-only folder')).toHaveAttribute('readonly');
  fireEvent.click(screen.getByText('Choose folder'));
  await waitFor(() => expect(screen.getByLabelText('Read-only folder')).toHaveValue('C:\\Fixtures'));
  expect(add).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText('Add read-only folder'));
  await screen.findByText('Read-only folder added');
  expect(add).toHaveBeenCalledWith('Test folder', 'C:\\Fixtures');
  expect(screen.getByText(/every file-content read needs your approval/i)).toBeInTheDocument();
});

it('canceling native selection grants no root', async () => {
  vi.mocked(invoke).mockResolvedValue(null);
  const add = vi.spyOn(api, 'addReadRoot');
  render(<CapabilitiesView api={api} native />);
  fireEvent.click(screen.getByText('Choose folder'));
  await waitFor(() => expect(screen.getByText('Choose folder')).toBeEnabled());
  expect(screen.getByLabelText('Read-only folder')).toHaveValue('');
  expect(add).not.toHaveBeenCalled();
});

it('removal is explicit and refreshes the approved root list', async () => {
  vi.spyOn(api, 'capabilities')
    .mockResolvedValueOnce({
      ...configuration,
      read_roots: [{ id: 'root-fixture', label: 'Test folder', path: 'C:\\Fixtures' }],
    })
    .mockResolvedValue(configuration);
  const remove = vi.spyOn(api, 'removeReadRoot').mockResolvedValue({ status: 'removed' });
  render(<CapabilitiesView api={api} native />);
  fireEvent.click(await screen.findByText('Remove Test folder'));
  await waitFor(() => expect(screen.queryByText('Remove Test folder')).not.toBeInTheDocument());
  expect(remove).toHaveBeenCalledWith('root-fixture');
});

it('a configuration error retains the entered draft', async () => {
  vi.spyOn(api, 'weatherLocations').mockRejectedValue(new Error('Weather provider timed out.'));
  render(<CapabilitiesView api={api} native={false} />);
  fireEvent.change(screen.getByLabelText('Weather location'), { target: { value: 'Thornton' } });
  fireEvent.click(screen.getByText('Find locations'));
  await screen.findByText('Weather provider timed out.');
  expect(screen.getByLabelText('Weather location')).toHaveValue('Thornton');
});

it('approved text is readable, escaped, bounded and never executable markup', () => {
  render(
    <ToolResultView
      message={{
        id: 'tool',
        session_id: 'session',
        role: 'tool',
        created_at: 'now',
        content: JSON.stringify({
          tool_name: 'read_text_file',
          result: {
            content: '<script>unsafe</script>\nHello',
            relative_path: 'fixture.txt',
            truncated: true,
          },
        }),
      }}
    />,
  );
  expect(screen.getByLabelText('Approved file contents')).toHaveTextContent('<script>unsafe</script>');
  expect(document.querySelector('script')).toBeNull();
  expect(screen.getByText(/preview truncated/i)).toBeInTheDocument();
});
