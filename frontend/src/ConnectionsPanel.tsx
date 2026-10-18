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
/** Для чего студия использует сервис. */
const ROLES: Record<string, string> = {
  piapi: 'Картинки и видео, LLM для промптов',
  openai: 'Резервный API для текстов',
  elevenlabs: 'Голос персонажей',
  fish: 'Голос персонажей, второй движок',
  kie: 'Картинки от референса (Seedream, Qwen)',
};
/** Цвет статуса: зелёный, янтарный, серый или красный. */
const tone = (status: string) =>
  status === 'connected'
    ? 'ok'
    : status === 'unverified'
      ? 'warn'
      : status === 'not_configured'
        ? 'off'
        : 'bad';

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
  const checkedAt = (value: string) =>
    new Date(value).toLocaleString('ru-RU', {timeZone: 'Europe/Moscow'}) + ' МСК';
  return (
    <section className="cx">
      <div className="cx-bar">
        <p className="muted">
          Ключи читает сервер из файлов в папке студии или переменных окружения: одна строка, без пробелов.
          Перезапуск не нужен. Проверка читает сведения аккаунта и ничего не запускает и не тратит.
        </p>
        <button onClick={load} disabled={!!busy}>
          Обновить
        </button>
      </div>
      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}
      <div className="cx-grid">
        {items.map(p => {
          const role = ROLES[p.id];
          return (
            <article className={'cx-card ' + tone(p.status)} key={p.id}>
              <header className="cx-head">
                <span className="cx-logo" aria-hidden="true">
                  {p.name.slice(0, 1)}
                </span>
                <div>
                  <h3>{p.name}</h3>
                  {role && <small>{role}</small>}
                </div>
                <span className="cx-status">
                  <i aria-hidden="true" />
                  {statuses[p.status] || p.status}
                </span>
              </header>
              <p className="cx-message">{p.message}</p>
              <dl className="cx-meta">
                <div>
                  <dt>Файл ключа</dt>
                  <dd>{p.filename}</dd>
                </div>
                {p.source && (
                  <div>
                    <dt>Источник</dt>
                    <dd>{p.source}</dd>
                  </div>
                )}
                <div>
                  <dt>Проверка</dt>
                  <dd>{p.checked_at ? checkedAt(p.checked_at) : 'ещё не было'}</dd>
                </div>
              </dl>
              <div className="cx-actions">
                <button
                  className={p.configured && p.status !== 'connected' ? 'primary' : ''}
                  disabled={!!busy || !p.configured}
                  onClick={() => check(p.id)}
                >
                  {busy === p.id ? 'Проверяется…' : 'Проверить доступ'}
                </button>
                <a href={p.docs} target="_blank" rel="noreferrer">
                  Документация ↗
                </a>
              </div>
            </article>
          );
        })}
      </div>
      <p className="muted">
        Для ElevenLabs также учитывается найденный файл ключа проекта «Гремовод». Доступ к аккаунту и
        готовность генерации проверяются отдельно.
      </p>
    </section>
  );
}
