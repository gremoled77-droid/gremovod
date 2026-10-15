import {useEffect, useState} from 'react';
import {apiFetch} from './api';

type Connection = {
  id: string;
  name: string;
  filename: string;
  configured: boolean;
  source?: string;
  status: string;
  message: string;
  checked_at: string | null;
  docs: string;
};
const statuses: Record<string, string> = {
  not_configured: 'Ключ не настроен',
  unverified: 'Не проверено',
  connected: 'Подключено',
  blocked: 'Заблокировано',
  denied: 'Доступ отклонён',
  rate_limited: 'Лимит запросов',
  unreachable: 'Нет соединения',
  error: 'Ошибка',
};
export default function ConnectionsPanel() {
  const [items, setItems] = useState<Connection[]>([]);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const load = async () => {
    try {
      const r = await apiFetch('/api/connections');
      if (!r.ok) throw Error('Не удалось получить подключения');
      setItems(await r.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };
  useEffect(() => {
    void load();
  }, []);
  const check = async (id: string) => {
    setBusy(id);
    setError('');
    try {
      const r = await apiFetch(`/api/connections/${id}/check`, {method: 'POST'});
      if (!r.ok) throw Error('Не удалось проверить подключение');
      const d: Connection = await r.json();
      setItems(a => a.map(x => (x.id === id ? d : x)));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy('');
    }
  };
  return (
    <section className="panel">
      <div className="panel-title">
        <h2>Подключения</h2>
        <button onClick={load} disabled={!!busy}>
          Обновить
        </button>
      </div>
      <p className="muted">
        Ключи читает сервер из файлов в папке студии или переменных окружения. Вставь только ключ одной
        строкой и сохрани файл. Перезапуск не требуется. Проверка читает сведения аккаунта и не запускает
        генерации.
      </p>
      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}
      <div className="connections-grid">
        {items.map(p => (
          <article className="connection-card" key={p.id}>
            <div className="panel-title">
              <h3>{p.name}</h3>
              <span className={'connection-status ' + p.status}>{statuses[p.status] || p.status}</span>
            </div>
            <p>{p.message}</p>
            <small>
              Файл: {p.filename}
              {p.source && ` · Источник: ${p.source}`}
            </small>
            {p.checked_at && (
              <small>
                Последняя проверка:{' '}
                {new Date(p.checked_at).toLocaleString('ru-RU', {timeZone: 'Europe/Moscow'}) + ' МСК'}
              </small>
            )}
            <div className="chips">
              <button disabled={!!busy || !p.configured} onClick={() => check(p.id)}>
                {busy === p.id ? 'Проверяется…' : 'Проверить доступ'}
              </button>
              <a href={p.docs} target="_blank" rel="noreferrer">
                Документация ↗
              </a>
            </div>
          </article>
        ))}
      </div>
      <p className="muted">
        Для ElevenLabs также учитывается найденный файл ключа проекта «Гремовод». Доступ к аккаунту и
        готовность генерации проверяются отдельно.
      </p>
    </section>
  );
}
