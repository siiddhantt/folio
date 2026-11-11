import { Notice } from '../components/ui';
import type { Configuration } from './types';

export function RuntimeDetails({ runtime }: Pick<Configuration, 'runtime'>) {
  const dollars = (value: string | null) =>
    value === null ? 'Unavailable' : `$${Number(value).toFixed(4)}`;
  const rows = [
    ['Model', runtime.model_id],
    ['Provider', runtime.provider],
    ['Token safety margin', runtime.token_margin],
    ['Worker time limit', `${runtime.job_timeout_seconds} s`],
    ['Ownership lease', `${runtime.lease_seconds} s`],
    [
      'Summary request timeout',
      runtime.summary_timeout_seconds === null ? null : `${runtime.summary_timeout_seconds} s`,
    ],
    ['Total allowance', dollars(runtime.budget_usd)],
    ['Per-document allowance', dollars(runtime.document_budget_usd)],
    ['Spent', dollars(runtime.spent_usd)],
    ['Reserved / uncertain', dollars(runtime.held_usd)],
    ['Available', dollars(runtime.remaining_usd)],
  ];
  return (
    <aside className="settings-runtime" aria-labelledby="runtime-title">
      <h2 id="runtime-title">Execution & spending</h2>
      <p className="subtle">Read-only</p>
      {runtime.summary_configuration_error && (
        <Notice error>
          Summary configuration needs repair in the environment:{' '}
          {runtime.summary_configuration_error}.
        </Notice>
      )}
      <dl>
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value ?? 'Unavailable'}</dd>
          </div>
        ))}
      </dl>
    </aside>
  );
}
