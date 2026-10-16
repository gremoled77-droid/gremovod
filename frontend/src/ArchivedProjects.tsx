import {useEffect, useState} from 'react';
import {apiFetch} from './api';

type Archived = {id: string; title: string; reason: string};
export default function ArchivedProjects({onRestored}: {onRestored: () => void}) {
  const [items, setItems] = useState<Archived[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  useEffect(() => {
    let active = true;
    void apiFetch('/api/archived-projects')
      .then(async r => {
        if (!r.ok) throw Error('Не удалось загрузить архив проектов');
        const data = await r.json();
        if (active) setItems(data);
      })
      .catch(e => {
        if (active) setError(String(e));
      });
    return () => {
      active = false;
    };
  }, []);
  const restore = async (id: string) => {
    setBusy(id);
    setError('');
    try {
      const r = await apiFetch(`/api/projects/${encodeURIComponent(id)}/restore`, {method: 'POST'});
      if (!r.ok) throw Error('Не удалось восстановить проект');
      setItems(current => current.filter(item => item.id !== id));
      onRestored();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy('');
    }
  };
  return (
    <section className="panel">
      <h3>Архив проектов</h3>
      <p className="muted">Архивные тесты скрыты из рабочего списка. Файлы и история расходов сохранены.</p>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {!items.length && !error && <p className="muted">Архив пуст.</p>}
      {items.map(item => (
        <div key={item.id}>
          <strong>{item.title}</strong>
          <p>{item.reason}</p>
          <button disabled={!!busy} onClick={() => void restore(item.id)}>
            Восстановить проект
          </button>
        </div>
      ))}
    </section>
  );
}
