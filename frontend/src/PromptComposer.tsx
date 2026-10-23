import {useEffect, useState} from 'react';
import {apiFetch, PAID_LLM_ENABLED} from './api';
export type PromptRequest = {project_id: string; target: string; provider: string; model: string};
export default function PromptComposer({
  request,
  onClose,
  onComposed,
}: {
  request: PromptRequest;
  onClose: () => void;
  onComposed: (prompt: string) => void;
}) {
  const [preview, setPreview] = useState<{context: Record<string, unknown>; system_rules: string} | null>(
    null
  );
  const [quote, setQuote] = useState<{estimated_usd: number; quote_token: string; max_tokens: number} | null>(
    null
  );
  const [approved, setApproved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const r = await apiFetch('/api/compose/preview', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(request),
        });
        const d = await r.json();
        if (!r.ok) throw Error(typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail));
        if (active) setPreview(d);
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : String(e));
      }
      try {
        // Шаг 1 платного вызова: бесплатная подписанная оценка цены. Без неё сервер не отправит запрос.
        const r = await apiFetch('/api/compose/estimate', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(request),
        });
        const d = await r.json();
        if (!r.ok) throw Error(typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail));
        if (active) setQuote(d);
      } catch (e) {
        if (active) setQuote(null);
      }
    })();
    return () => {
      active = false;
    };
  }, [request]);
  const compose = async () => {
    setBusy(true);
    setAttempted(true);
    setError('');
    try {
      if (!quote) throw Error('Оценка стоимости недоступна. Получи новую оценку и подтверди запуск.');
      const r = await apiFetch('/api/compose', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          ...request,
          approved: true,
          quote_token: quote.quote_token,
          max_cost_usd: quote.estimated_usd,
          request_id: crypto.randomUUID(),
        }),
      });
      const d = await r.json();
      if (!r.ok) throw Error(typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail));
      onComposed(d.prompt);
    } catch (e) {
      setError(
        (e instanceof Error ? e.message : String(e)) + ' Автоматический платный повтор не выполняется.'
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="modal-backdrop">
      <section
        className="panel generation-review"
        role="dialog"
        aria-modal="true"
        aria-labelledby="compose-title"
      >
        <h2 id="compose-title">Подготовка промпта через API</h2>
        <p className="notice">
          Платный резерв под контролем: сервер сначала считает цену по проверенному тарифу модели, показывает
          оценку и только после твоего подтверждения отправляет запрос. Бюджет проекта и суточный лимит
          проверяются до вызова провайдера.
        </p>
        <p>
          {request.provider} · {request.model} → {request.target}
        </p>
        <p className="muted">
          Сервер собрал задание, библию мира, выбранного персонажа, его профиль для этой модели, настройки и
          описания референсов. Используются правила ai-video и cinematic-studio; LLM получает их вместе с
          контекстом.
        </p>
        {preview && (
          <>
            <details>
              <summary>Контекст проекта</summary>
              <pre>{JSON.stringify(preview.context, null, 2)}</pre>
            </details>
            <details>
              <summary>Инструкции для модели</summary>
              <pre>{preview.system_rules}</pre>
            </details>
          </>
        )}
        <p className="muted">
          {quote
            ? `Один платный LLM-запрос, ответ до ${quote.max_tokens} токенов. Оценка: $${quote.estimated_usd.toFixed(6)}.`
            : 'Оценка стоимости недоступна: платный резерв работает только через PiAPI с моделью из каталога.'}{' '}
          Видео автоматически не запускается. Промпт и фактический usage сохраняются в истории проекта.
        </p>
        <label className="inline-checkbox">
          <input
            type="checkbox"
            checked={approved}
            onChange={e => setApproved(e.target.checked)}
            disabled={attempted}
          />{' '}
          Разрешаю один платный LLM-запрос для подготовки промпта
        </label>
        {error && (
          <div className="alert" role="alert">
            {error}
          </div>
        )}
        <div className="chips">
          <button
            className="primary"
            disabled={!PAID_LLM_ENABLED || !preview || !quote || !approved || busy || attempted}
            onClick={compose}
          >
            {busy ? 'LLM готовит промпт…' : 'Подготовить через API'}
          </button>
          <button disabled={busy} onClick={onClose}>
            Закрыть
          </button>
        </div>
      </section>
    </div>
  );
}
