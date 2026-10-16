import type {ReactNode} from 'react';

/** Сворачиваемый раздел экрана: тяжёлое содержимое не мешает основному действию, но остаётся под рукой. */
export default function Collapsible({
  title,
  hint,
  open = false,
  children,
}: {
  title: string;
  hint?: string;
  open?: boolean;
  children: ReactNode;
}) {
  return (
    <details className="collapsible panel" open={open}>
      <summary>
        <b>{title}</b>
        {hint && <small>{hint}</small>}
      </summary>
      <div className="collapsible-body">{children}</div>
    </details>
  );
}
