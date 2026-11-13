import { useEffect, useState, type FormEvent } from 'react';
import { errorMessage, request } from '../api';
import { Button, Notice } from '../components/ui';
import { Input } from '../components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { RuntimeDetails } from './RuntimeDetails';
import type { Configuration, Controls } from './types';

function NumberField({
  name,
  label,
  value,
  min = 1,
  max = Number.MAX_SAFE_INTEGER,
}: {
  name: keyof Controls;
  label: string;
  value: number;
  min?: number;
  max?: number;
}) {
  return (
    <label className="settings-field">
      <span>{label}</span>
      <Input name={name} type="number" required step="1" min={min} max={max} defaultValue={value} />
    </label>
  );
}

export function SettingsPage({ onSaved }: { onSaved: () => void }) {
  const [configuration, setConfiguration] = useState<Configuration | null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [reload, setReload] = useState(0);
  const [formReset, setFormReset] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setConfiguration(null);
    setError('');
    setSaved(false);
    request<Configuration>('/development/settings', { signal: controller.signal })
      .then(setConfiguration)
      .catch((e) => {
        if (!controller.signal.aborted) setError(errorMessage(e));
      });
    return () => controller.abort();
  }, [reload]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!configuration || saving) return;
    const form = new FormData(event.currentTarget);
    const values: Controls = {
      max_pages: Number(form.get('max_pages')),
      max_upload_bytes: Number(form.get('max_upload_bytes')),
      parser_timeout_seconds: Number(form.get('parser_timeout_seconds')),
      summary_enabled: form.get('summary_enabled') === 'on',
      summary_input_limit_tokens: Number(form.get('summary_input_limit_tokens')),
      summary_max_output_tokens: Number(form.get('summary_max_output_tokens')),
      summary_reasoning_effort: String(form.get('summary_reasoning_effort')),
    };
    setSaving(true);
    setSaved(false);
    setError('');
    try {
      const result = await request<Configuration>('/development/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'X-Folio-Development': '1' },
        body: JSON.stringify({ revision: configuration.revision, values }),
      });
      setConfiguration(result);
      setSaved(true);
      onSaved();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="settings-page">
      <header className="settings-heading">
        <h1>Development</h1>
        <p className="subtle">
          Changes apply to new uploads. Accepted documents keep their settings.
        </p>
        {configuration && (
          <p className="subtle">
            Revision {configuration.revision} · Saved{' '}
            {new Date(configuration.updated_at).toLocaleString()}
          </p>
        )}
      </header>
      {error && (
        <Notice error>
          {error}{' '}
          <Button variant="outline" disabled={saving} onClick={() => setReload(reload + 1)}>
            Reload settings
          </Button>
        </Notice>
      )}
      {!configuration && !error && <p className="subtle">Loading settings…</p>}
      {configuration && (
        <div className="settings-layout">
          <form
            key={`${configuration.revision}-${reload}-${formReset}`}
            onSubmit={(event) => void save(event)}
            onChange={() => setSaved(false)}
            onReset={() => {
              setFormReset((value) => value + 1);
              setSaved(false);
            }}
          >
            <fieldset disabled={saving}>
              <legend>Ingestion</legend>
              <NumberField
                name="max_pages"
                label="Maximum pages"
                value={configuration.values.max_pages}
              />
              <NumberField
                name="max_upload_bytes"
                label="Maximum upload bytes"
                value={configuration.values.max_upload_bytes}
              />
              <NumberField
                name="parser_timeout_seconds"
                label="Parser timeout (seconds)"
                value={configuration.values.parser_timeout_seconds}
                max={configuration.runtime.job_timeout_seconds - 1}
              />
            </fieldset>
            <fieldset disabled={saving}>
              <legend>Summary</legend>
              <label className="settings-field">
                <span>Automatic summaries</span>
                <input
                  type="checkbox"
                  name="summary_enabled"
                  defaultChecked={configuration.values.summary_enabled}
                />
              </label>
              <NumberField
                name="summary_input_limit_tokens"
                label="Input token limit"
                value={configuration.values.summary_input_limit_tokens}
                min={(configuration.runtime.token_margin ?? 0) + 1}
              />
              <NumberField
                name="summary_max_output_tokens"
                label="Output token limit"
                value={configuration.values.summary_max_output_tokens}
              />
              <div className="settings-field">
                <label htmlFor="reasoning-effort">Reasoning effort</label>
                <Select
                  name="summary_reasoning_effort"
                  defaultValue={configuration.values.summary_reasoning_effort}
                  disabled={saving}
                  onValueChange={() => setSaved(false)}
                >
                  <SelectTrigger id="reasoning-effort">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {!configuration.runtime.reasoning_options.includes(
                      configuration.values.summary_reasoning_effort,
                    ) && (
                      <SelectItem value={configuration.values.summary_reasoning_effort} disabled>
                        {configuration.values.summary_reasoning_effort} (unsupported)
                      </SelectItem>
                    )}
                    {configuration.runtime.reasoning_options.map((value) => (
                      <SelectItem key={value} value={value}>
                        {value}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </fieldset>
            <div className="settings-actions">
              <Button type="submit" disabled={saving}>
                {saving ? 'Saving…' : 'Save settings'}
              </Button>
              <Button
                type="reset"
                variant="ghost"
                disabled={saving}
                onClick={() => setSaved(false)}
              >
                Reset unsaved changes
              </Button>
            </div>
            {saved && (
              <p className="subtle settings-saved" role="status">
                Settings saved.
              </p>
            )}
          </form>
          <RuntimeDetails runtime={configuration.runtime} />
        </div>
      )}
    </div>
  );
}
