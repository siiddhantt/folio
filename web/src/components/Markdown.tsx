import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ReactNode } from 'react';

export function Markdown({ children, trailing }: { children: string; trailing?: ReactNode }) {
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        disallowedElements={['img']}
        components={{
          a: ({ href, children }) =>
            href ? (
              <a href={href} target="_blank" rel="noopener noreferrer">
                {children}
              </a>
            ) : (
              <span>{children}</span>
            ),
          table: ({ children }) => (
            <div className="markdown-table" role="region" aria-label="Answer table" tabIndex={0}>
              <table>{children}</table>
            </div>
          ),
          pre: ({ children }) => (
            <pre tabIndex={0} aria-label="Code block">
              {children}
            </pre>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
      {trailing && <span className="markdown-trailing">{trailing}</span>}
    </div>
  );
}
