import { Button } from '../components/ui';
import type { Citation } from './types';

export function AnswerSources({
  sources,
  onSource,
}: {
  sources: Citation[];
  onSource: (source?: Citation) => void;
}) {
  if (!sources.length) return null;
  return (
    <div className="answer-sources" aria-label="Cited passages">
      {sources.slice(0, 5).map((source, index) => {
        const text = source.text.replace(/\s+/g, ' ').trim();
        const preview = text.length > 90 ? `${text.slice(0, 89).trimEnd()}…` : text;
        return (
          <Button
            key={source.source_id}
            variant="outline"
            className="source-chip"
            onClick={() => onSource(source)}
            aria-label={`Source ${source.source_id}, page ${source.pages[0]}: ${preview}`}
          >
            <span className="source-chip-number">{index + 1}</span>
            <span className="source-chip-preview">{preview}</span>
            <span className="source-chip-page">p. {source.pages[0]}</span>
          </Button>
        );
      })}
      {sources.length > 5 && (
        <Button variant="ghost" size="sm" onClick={() => onSource()}>
          {sources.length - 5} more {sources.length === 6 ? 'source' : 'sources'}
        </Button>
      )}
    </div>
  );
}
