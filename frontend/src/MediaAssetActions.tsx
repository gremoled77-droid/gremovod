import {useEffect, useRef, useState} from 'react';
import {apiFetch} from './api';
import {
  copyMediaPrompt,
  mediaModel,
  mediaPrompt,
  sourceChat,
  type MediaAsset,
  type MediaChange,
} from './mediaAsset';

async function response(r: Response) {
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw Error(typeof data.detail === 'string' ? data.detail : 'Не удалось выполнить действие');
  return data;
}
export default function MediaAssetActions({
  assetId,
  onChanged,
  onReference,
  onAnimate,
}: {
  assetId: string;
  onChanged?: (id: string, change: MediaChange) => void;
  onReference?: (id: string) => void;
  onAnimate?: (id: string) => void;
}) {
  const [asset, setAsset] = useState<MediaAsset | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [confirmTrash, setConfirmTrash] = useState(false);
  const [manualCopy, setManualCopy] = useState(false);
  const submitting = useRef(false);
  const favoriteButton = useRef<HTMLButtonElement>(null);
  const trashButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const controller = new AbortController();
    void apiFetch(`/api/library/${encodeURIComponent(assetId)}/details`, {signal: controller.signal})
      .then(response)
      .then(data => {
        if (!controller.signal.aborted) setAsset(data);
      })
      .catch(e => {
        if (!controller.signal.aborted) setError(String(e));
      });
    return () => controller.abort();
  }, [assetId]);
  const mutate = async (action: 'favorite' | 'trash') => {
    if (!asset || submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const favorite = !asset.metadata.favorite;
      await response(
        await apiFetch(`/api/library/${encodeURIComponent(assetId)}/${action}`, {
          method: 'POST',
          ...(action === 'favorite'
            ? {
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({favorite}),
              }
            : {}),
        })
      );
      if (action === 'favorite') {
        setAsset({...asset, metadata: {...asset.metadata, favorite}});
        setNotice(favorite ? 'Добавлено в избранное.' : 'Убрано из избранного.');
        onChanged?.(assetId, {favorite});
      } else {
        setConfirmTrash(false);
        setNotice('Файл перемещён в корзину на 30 дней.');
        onChanged?.(assetId, {trashed: true});
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      submitting.current = false;
      setBusy(false);
      requestAnimationFrame(() => {
        const button = action === 'favorite' ? favoriteButton.current : trashButton.current;
        if (button?.isConnected) button.focus();
      });
    }
  };
  const prompt = asset ? mediaPrompt(asset.metadata) : '';
  const chat = asset ? sourceChat(asset.metadata) : null;
  const image = asset && (asset.metadata.kind || 'image') === 'image';
  return (
    <section className="lb-actions" aria-label="Действия с файлом">
      {asset ? (
        <>
          <small>
            {mediaModel(asset.metadata)}
            {typeof asset.metadata.width === 'number' && typeof asset.metadata.height === 'number'
              ? ` · ${asset.metadata.width} × ${asset.metadata.height}`
              : ''}
          </small>
          <div className="lb-action-buttons">
            <button
              disabled={busy}
              ref={favoriteButton}
              aria-pressed={!!asset.metadata.favorite}
              onClick={() => void mutate('favorite')}
            >
              {asset.metadata.favorite ? '♥ В избранном' : '♡ В избранное'}
            </button>
            <a className="lb-action-link" href={`/api/library/${encodeURIComponent(assetId)}/file`} download>
              Скачать оригинал
            </a>
            {prompt && (
              <button
                onClick={async () => {
                  const ok = await copyMediaPrompt(prompt, navigator.clipboard);
                  setManualCopy(!ok);
                  setNotice(ok ? 'Промпт скопирован.' : 'Буфер недоступен. Выдели и скопируй текст ниже.');
                }}
              >
                Копировать промпт
              </button>
            )}
            {image && onReference && (
              <button
                disabled={busy}
                onClick={() => {
                  onReference(assetId);
                  setNotice('Добавлено в референсы кадра.');
                }}
              >
                В референсы
              </button>
            )}
            {image && onAnimate && (
              <button disabled={busy} onClick={() => onAnimate(assetId)}>
                Оживить
              </button>
            )}
            {chat && (
              <a className="lb-action-link" href={chat} target="_blank" rel="noreferrer">
                Править в исходном GPT-чате ↗
              </a>
            )}
            <button ref={trashButton} disabled={busy} onClick={() => setConfirmTrash(true)}>
              В корзину
            </button>
          </div>
          {confirmTrash && (
            <div className="lb-confirm" role="group" aria-label="Подтверждение перемещения в корзину">
              <p>Убрать файл в корзину на 30 дней? Используемые в проекте файлы защищены сервером.</p>
              <button disabled={busy} onClick={() => void mutate('trash')}>
                Подтвердить перемещение
              </button>
              <button
                disabled={busy}
                onClick={() => {
                  setConfirmTrash(false);
                  trashButton.current?.focus();
                }}
              >
                Отмена
              </button>
            </div>
          )}
          {prompt && (
            <details open={manualCopy || undefined}>
              <summary>Промпт</summary>
              <textarea
                aria-label="Промпт изображения"
                readOnly
                value={prompt}
                rows={4}
                onFocus={e => e.currentTarget.select()}
              />
            </details>
          )}
        </>
      ) : (
        !error && <small role="status">Загружаем сведения о файле…</small>
      )}
      {notice && <p role="status">{notice}</p>}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
