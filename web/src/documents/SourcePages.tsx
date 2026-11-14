export function SourcePages({
  pages,
  onSourcePage,
}: {
  pages: number[];
  onSourcePage: (page: number) => void;
}) {
  return (
    <span>
      {[...new Set(pages)]
        .sort((a, b) => a - b)
        .map((page) => (
          <button
            key={page}
            className="page-link"
            onClick={() => onSourcePage(page)}
            aria-label={`View page ${page} in original`}
          >
            {page}
          </button>
        ))}
    </span>
  );
}
