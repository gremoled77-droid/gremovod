import {useState} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';

/** Размеры картинки без обращения к серверу: браузер сам читает их из файла. */
function imageSize(url: string): Promise<{w: number; h: number}> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve({w: img.naturalWidth, h: img.naturalHeight});
    img.onerror = () => reject(Error('Не удалось прочитать размер картинки'));
    img.src = url;
  });
}

type Preview = {estimated_usd: number; launch_enabled: boolean; note: string};

/** Апскейл главного фото. Пока только сухой прогон: цена по документации PiAPI, запуск включится после живой проверки. */
export default function UpscaleButton({fileId}: {fileId: string}) {
  const [open, setOpen] = useState(false),
    [scale, setScale] = useState(2),
    [size, setSize] = useState<{w: number; h: number} | null>(null),
    [preview, setPreview] = useState<Preview | null>(null),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  const check = async (nextScale: number) => {
    setBusy(true);
    setError('');
    try {
      const dims = size || (await imageSize(`/api/production-files/${fileId}`));
      setSize(dims);
      // Dry run: в тело подставляется нерабочий адрес-заглушка, ничего не загружается и не отправляется.
      const result = await responseJson(
        await apiFetch('/api/model-jobs/preview', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            model_id: 'image-upscale',
            prompt: 'Upscale',
            options: {scale: nextScale, in_width: Math.min(2048, dims.w), in_height: Math.min(2048, dims.h)},
            reference_urls: ['https://upscale-preview.invalid/frame.png'],
          }),
        })
      );
      setPreview(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="ps-upscale">
      <button
        type="button"
        disabled={busy}
        onClick={() => {
          setOpen(o => !o);
          if (!open) void check(scale);
        }}
      >
        Апскейл
      </button>
      {open && (
        <div role="group" aria-label="Апскейл главного фото">
          <label>
            Увеличить
            <select
              value={scale}
              disabled={busy}
              onChange={e => {
                const next = Number(e.target.value);
                setScale(next);
                void check(next);
              }}
            >
              <option value={2}>×2</option>
              <option value={4}>×4</option>
            </select>
          </label>
          {size && (
            <small>
              {size.w}×{size.h} → {size.w * scale}×{size.h * scale}
              {size.w > 2048 || size.h > 2048 ? ' · вход больше 2048 px, апскейл его не примет' : ''}
            </small>
          )}
          {preview && (
            <p>
              Оценка по документации: <b>${preview.estimated_usd.toFixed(3)}</b>
            </p>
          )}
          <small className="muted">
            Запуск выключен: цена и ответ провайдера ещё не проверены живым вызовом.
          </small>
          {error && <p role="alert">{error}</p>}
        </div>
      )}
    </div>
  );
}
