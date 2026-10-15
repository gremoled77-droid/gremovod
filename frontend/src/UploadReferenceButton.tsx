import {useState} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
export default function UploadReferenceButton({
  assetId,
  onReady,
}: {
  assetId: string;
  onReady: (url: string) => void;
}) {
  const [review, setReview] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [provider, setProvider] = useState('tempfile'),
    [notice, setNotice] = useState('');
  const upload = async () => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const result = await responseJson(
        await apiFetch(`/api/library/${assetId}/upload-reference`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({approved: true, provider}),
        })
      );
      onReady(result.url);
      setNotice(
        'Референс выбран для видео. Ссылка доступна до ' +
          new Date(result.expires_at * 1000).toLocaleString('ru-RU', {timeZone: 'Europe/Moscow'}) +
          ' МСК.'
      );
      setReview(false);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div>
      <button onClick={() => setReview(!review)} disabled={busy}>
        Подготовить для видео · облако
      </button>
      {review && (
        <div>
          <label>
            Временное хранилище
            <select value={provider} disabled={busy} onChange={e => setProvider(e.target.value)}>
              <option value="tempfile">TempFile.org · бесплатно · 24 часа</option>
              <option value="piapi">PiAPI · резерв · Creator/Pro</option>
            </select>
          </label>
          <p>
            Оригинал будет передан в{' '}
            {provider === 'tempfile'
              ? 'TempFile.org без регистрации и API-ключа'
              : 'PiAPI (требуется Creator/Pro)'}
            . Ссылка публичная и действует около суток, затем файл удаляется сервисом. Локальный оригинал
            сохранится. Видео этим действием не создаётся.
          </p>
          <a
            href={
              provider === 'tempfile'
                ? 'https://tempfile.org/api'
                : 'https://app.piapi.ai/docs/tools/file-upload'
            }
            target="_blank"
            rel="noreferrer"
          >
            Условия загрузки
          </a>
          <button disabled={busy} onClick={() => void upload()}>
            {busy ? 'Загрузка…' : 'Загрузить оригинал и выбрать для видео'}
          </button>
        </div>
      )}
      {notice && <p role="status">{notice}</p>}
      {error && <p role="alert">{error}</p>}
    </div>
  );
}
