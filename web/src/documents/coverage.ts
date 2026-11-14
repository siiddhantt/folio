import type { Diagnostic, Evidence } from '../types';

export function diagnosticText(item: Diagnostic): string {
  if (typeof item.message === 'string' && item.message) return item.message;
  if (typeof item.error_message === 'string' && item.error_message) return item.error_message;
  if (typeof item.code === 'string' && item.code)
    return item.code.replaceAll('_', ' ').toLowerCase();
  return 'The parser reported an extraction limitation';
}

export function describeCoverage(evidence: Evidence) {
  const missing = evidence.pages
    .filter((page) => page.content_observation === 'no_content_recovered')
    .map((page) => page.page_no)
    .sort((a, b) => a - b);
  const ranges: { start: number; end: number }[] = [];
  for (const page of missing) {
    const previous = ranges.at(-1);
    if (previous && page === previous.end + 1) previous.end = page;
    else ranges.push({ start: page, end: page });
  }
  const diagnostics = [
    ...new Map(
      [...evidence.diagnostics, ...evidence.pages.flatMap((page) => page.diagnostics)]
        .filter((item) => item.code !== 'NO_CONTENT_RECOVERED')
        .map((item) => [JSON.stringify(item), item]),
    ).values(),
  ];
  return {
    total: evidence.pages.length,
    recovered: evidence.pages.filter((page) => page.content_observation === 'content_recovered')
      .length,
    partial: missing.length > 0 || diagnostics.length > 0,
    timedOut: diagnostics.some(
      (item) =>
        item.category === 'timeout' ||
        ['DOCUMENT_TIMEOUT', 'PAGE_TIMEOUT', 'PARSER_TIMEOUT'].includes(item.code ?? ''),
    ),
    ranges,
    diagnostics,
  };
}

export function rangeLabel(range: { start: number; end: number }) {
  return range.start === range.end
    ? `page ${range.start.toLocaleString()}`
    : `pages ${range.start.toLocaleString()}–${range.end.toLocaleString()}`;
}
