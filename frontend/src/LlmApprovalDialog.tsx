import LimitPicker from './LimitPicker';
import LlmCostCard from './LlmCostCard';
import {expectedPaymentLine, maxApprovedLine, type LlmCard} from './llmDisplay';
import {limitAllowed} from './spendLimit';

/** Окно подтверждения платного вызова LLM.
 *
 * Ориентир по тарифу Kie/PiAPI идёт первым, но рядом, ДО согласия, видны ожидаемый реальный платёж
 * по тарифу исполнителя и максимальный одобренный расход: низкий ориентир не прячет настоящую сумму. */
export default function LlmApprovalDialog({
  card,
  title,
  total,
  limit,
  onLimit,
  highConfirmed,
  onHighConfirmed,
  approved,
  onApproved,
  busy,
  error,
  onConfirm,
  onClose,
}: {
  card: LlmCard;
  title?: string;
  total: number;
  limit: string;
  onLimit: (value: string) => void;
  highConfirmed: boolean;
  onHighConfirmed: (value: boolean) => void;
  approved: boolean;
  onApproved: (value: boolean) => void;
  busy?: boolean;
  error?: string;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const amount = Number(limit);
  return (
    <div className="modal-backdrop">
      <section
        className="panel generation-review"
        role="dialog"
        aria-modal="true"
        aria-labelledby="llm-approval-title"
      >
        <h2 id="llm-approval-title">{title || 'Подтверждение платного вызова LLM'}</h2>
        <LlmCostCard card={card} />
        <p>
          <b>{expectedPaymentLine(card)}</b>
        </p>
        <p className="muted">
          {maxApprovedLine(Number.isFinite(amount) ? amount : null)} · ориентир по тарифу Kie/PiAPI — сравнение, не деньги
        </p>
        <LimitPicker
          total={total}
          limit={limit}
          onLimit={onLimit}
          highConfirmed={highConfirmed}
          onHighConfirmed={onHighConfirmed}
          disabled={busy}
        />
        <label className="inline-checkbox">
          <input
            type="checkbox"
            checked={approved}
            onChange={e => onApproved(e.target.checked)}
            disabled={busy}
          />{' '}
          Подтверждаю платный вызов LLM в пределах указанного лимита
        </label>
        {error && (
          <div className="alert" role="alert">
            {error}
          </div>
        )}
        <div className="chips">
          <button
            className="primary"
            disabled={busy || !approved || !limitAllowed(total, limit, highConfirmed)}
            onClick={onConfirm}
          >
            {busy ? 'Выполняется…' : 'Подтвердить и запустить'}
          </button>
          <button onClick={onClose} disabled={busy}>
            Отмена
          </button>
        </div>
      </section>
    </div>
  );
}
