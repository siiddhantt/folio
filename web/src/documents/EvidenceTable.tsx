import type { ReactNode } from 'react';
import type { SourceElement, TableCell } from '../types';

export function EvidenceTable({ element }: { element: SourceElement }) {
  const table = element.table_data!;
  const starts = new Map(table.cells.map((cell) => [`${cell.row}:${cell.column}`, cell]));
  const occupied = new Set<string>();
  const rows: ReactNode[] = [];
  for (let row = 0; row < table.row_count; row++) {
    const cells: ReactNode[] = [];
    for (let column = 0; column < table.column_count; column++) {
      const key = `${row}:${column}`;
      if (occupied.has(key)) continue;
      const cell = starts.get(key);
      if (!cell) {
        cells.push(<td key={column} />);
        continue;
      }
      for (let r = row; r < row + cell.row_span; r++) {
        for (let c = column; c < column + cell.column_span; c++) occupied.add(`${r}:${c}`);
      }
      cells.push(<Cell key={column} cell={cell} />);
    }
    rows.push(<tr key={row}>{cells}</tr>);
  }
  return (
    <div
      className="table-scroll"
      role="region"
      aria-label="Scrollable extracted table"
      tabIndex={0}
    >
      <table aria-label={`Extracted table from page ${element.locations[0]?.page_no}`}>
        <tbody>{rows}</tbody>
      </table>
    </div>
  );
}

function Cell({ cell }: { cell: TableCell }) {
  const Tag = cell.column_header || cell.row_header ? 'th' : 'td';
  return (
    <Tag
      rowSpan={cell.row_span}
      colSpan={cell.column_span}
      scope={cell.column_header ? 'col' : cell.row_header ? 'row' : undefined}
    >
      {cell.text}
    </Tag>
  );
}
