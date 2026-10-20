import type {CSSProperties} from 'react';
import {cardLines, referenceNote, type LlmCard} from './llmDisplay';

/** Карточка вызова LLM. Порядок строк зафиксирован в llmDisplay.cardLines:
 * тарифный ориентир → кто выполнил → статус → фактический платёж. */
const box: CSSProperties = {
  border: '1px solid var(--border)',
  background: 'var(--surface-2)',
  borderRadius: 10,
  padding: 12,
  display: 'grid',
  gap: 6,
  fontSize: 12,
};
const row: CSSProperties = {display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'baseline'};
const label: CSSProperties = {color: 'var(--muted)', minWidth: 150};

export default function LlmCostCard({card, title}: {card: LlmCard | null; title?: string}) {
  if (!card) return null;
  const lines = cardLines(card);
  const note = referenceNote(card);
  const rows: {label: string; value: string}[] = [
    {label: 'Ценовой ориентир', value: lines[0]},
    {label: 'Кто выполнил', value: lines[1]},
    {label: 'Статус', value: lines[2]},
    {label: 'Фактический платёж', value: lines[3]},
  ];
  return (
    <div className="llm-cost-card" style={box} aria-label="Карточка вызова LLM">
      {title && <b>{title}</b>}
      {rows.map((item, index) => (
        <div key={item.label} style={row}>
          <span style={label}>{item.label}</span>
          <span>{item.value}</span>
          {index === 0 && note && <small>{note}</small>}
        </div>
      ))}
    </div>
  );
}
