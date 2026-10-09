import { useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { CoreApi, errorMessage } from './api';
import type { Capabilities, WeatherLocation } from './capability-types';

export function CapabilitiesView({ api, native }: { api: CoreApi; native: boolean }) {
  const [configuration, setConfiguration] = useState<Capabilities | null>(null);
  const [query, setQuery] = useState('');
  const [locations, setLocations] = useState<WeatherLocation[]>([]);
  const [label, setLabel] = useState('');
  const [path, setPath] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  useEffect(() => {
    let current = true;
    void api
      .capabilities()
      .then((value) => {
        if (current) setConfiguration(value);
      })
      .catch((error) => {
        if (current) setNotice(errorMessage(error));
      });
    return () => {
      current = false;
    };
  }, [api]);
  async function run(action: () => Promise<void>) {
    setBusy(true);
    setNotice('');
    try {
      await action();
    } catch (error) {
      setNotice(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="settings-card" aria-label="Capabilities">
      <div className="card-heading">
        <div>
          <h2>Capabilities</h2>
          <p>Choose what KAT can access.</p>
        </div>
      </div>
      <h3>Weather · external data</h3>
      <p className="field-hint">
        Open-Meteo receives your chosen location. Weather uses the internet even with local AI. No location
        tracking.{' '}
        <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">
          Weather data by Open-Meteo
        </a>
        .
      </p>
      <p role="status">{configuration?.weather_location?.label ?? 'Weather location not configured'}</p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void run(async () => {
            setLocations(await api.weatherLocations(query));
          });
        }}
      >
        <label htmlFor="weather-place">Weather location</label>
        <input
          id="weather-place"
          value={query}
          maxLength={100}
          placeholder="Thornton, Colorado"
          onChange={(e) => setQuery(e.target.value)}
          disabled={busy}
        />
        <button className="secondary-button" disabled={busy || query.trim().length < 2}>
          Find locations
        </button>
      </form>
      {locations.map((location, index) => (
        <button
          key={index}
          className="secondary-button"
          disabled={busy}
          onClick={() =>
            void run(async () => {
              setConfiguration(await api.setWeatherLocation(location));
              setLocations([]);
              setNotice('Weather location saved');
            })
          }
        >
          Use {location.label}
        </button>
      ))}
      {configuration?.weather_location && (
        <button
          className="text-button"
          disabled={busy}
          onClick={() =>
            void run(async () => {
              setConfiguration(await api.setWeatherLocation(null));
            })
          }
        >
          Clear weather location
        </button>
      )}
      <h3>System · read-only local information</h3>
      <p className="field-hint">
        Current CPU, RAM, local disk, Windows and available GPU information. No shell commands or process
        inspection.
      </p>
      <h3>Files · approved read-only folders</h3>
      <p className="field-hint">
        KAT can list filenames here. Every file-content read needs your approval. Returned content is kept in
        the local transcript. Choosing OpenAI can send current authorized tool data to cloud AI. No file
        modification or network folders.
      </p>
      {configuration?.read_roots.map((root) => (
        <div className="read-root" key={root.id}>
          <strong>{root.label}</strong>
          <code>{root.id}</code>
          <span>{root.path}</span>
          <button
            className="text-button"
            disabled={busy}
            onClick={() =>
              void run(async () => {
                await api.removeReadRoot(root.id);
                setConfiguration(await api.capabilities());
              })
            }
          >
            Remove {root.label}
          </button>
        </div>
      ))}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void run(async () => {
            await api.addReadRoot(label, path);
            setConfiguration(await api.capabilities());
            setPath('');
            setLabel('');
            setNotice('Read-only folder added');
          });
        }}
      >
        <label htmlFor="read-root-label">Folder label</label>
        <input
          id="read-root-label"
          value={label}
          maxLength={80}
          onChange={(e) => setLabel(e.target.value)}
          disabled={busy}
        />
        <label htmlFor="read-root-path">Read-only folder</label>
        <input
          id="read-root-path"
          value={path}
          readOnly={native}
          onChange={(e) => setPath(e.target.value)}
          disabled={busy}
        />
        {native && (
          <button
            type="button"
            className="secondary-button"
            disabled={busy}
            onClick={() =>
              void run(async () => {
                const selected = await invoke<string | null>('choose_read_folder');
                if (selected) setPath(selected);
              })
            }
          >
            Choose folder
          </button>
        )}
        <button className="primary-button" disabled={busy || !path || !label.trim()}>
          Add read-only folder
        </button>
      </form>
      <p role="status" className="field-hint">
        {notice}
      </p>
    </section>
  );
}
