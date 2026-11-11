import type { FailureDiagnostics } from './types';

export function FailureDetails({ diagnostics }: { diagnostics?: FailureDiagnostics | null }) {
  if (!diagnostics) return null;
  return (
    <>
      <dt>Exception</dt>
      <dd>
        <code>{diagnostics.error_type}</code>
      </dd>
      {diagnostics.errno !== undefined && (
        <>
          <dt>System error</dt>
          <dd>{diagnostics.errno}</dd>
        </>
      )}
      {!!diagnostics.error_frames.length && (
        <>
          <dt>Code locations</dt>
          <dd>
            <ul className="failure-locations">
              {diagnostics.error_frames.map((frame, index) => (
                <li key={index}>
                  <code>
                    {frame.module}.{frame.function}:{frame.line}
                  </code>
                </li>
              ))}
            </ul>
          </dd>
        </>
      )}
    </>
  );
}
