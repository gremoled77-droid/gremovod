import {useEffect, useRef, useState} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
import {readLocal, writeLocal, clearLocal} from './localDrafts';
import {moveItem, toggleId} from './boardOrder';
import {
  beatFields,
  fromSnapshot,
  keepDraft,
  newBeat,
  validDraft,
  versionsMatch,
  type ActingDraft,
  type ActingSnapshot,
  type Beat,
} from './actingSheet';
import './ActingNotes.css';

export default function ActingNotes({pid, sid, sceneId}: {pid: string; sid: string; sceneId: string}) {
  const url = `/api/productions/${pid}/series/${sid}/scenes/${sceneId}/acting-notes`;
  const key = `studio:acting-notes:${pid}:${sid}:${sceneId}`;
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const [open, setOpen] = useState(false);
  const [server, setServer] = useState<ActingSnapshot | null>(null);
  const [draft, setDraft] = useState<ActingDraft | null>(null);
  const [conflict, setConflict] = useState<ActingSnapshot | null>(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [storageOK, setStorageOK] = useState(true);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    if (!open) return;
    let active = true;
    setBusy(true);
    setError('');
    apiFetch(url)
      .then(responseJson)
      .then((saved: ActingSnapshot) => {
        if (!active) return;
        setServer(saved);
        const local: unknown = readLocal(key, null);
        if (validDraft(local)) {
          setDraft({...local, status: 'draft'});
          setDirty(true);
          setConflict(versionsMatch(local, saved) ? null : saved);
          setNotice('Восстановлен локальный черновик. Проверь его перед сохранением.');
        } else {
          setDraft(fromSnapshot(saved));
          setDirty(false);
          setConflict(null);
          setNotice('');
        }
      })
      .catch(e => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setBusy(false);
      });
    return () => {
      active = false;
    };
  }, [open, url, key, reload]);

  function edit(next: ActingDraft) {
    setDraft({...next, status: next.status === 'approved' ? 'draft' : next.status});
    setDirty(true);
    setNotice('');
    setStorageOK(writeLocal(key, {...next, status: next.status === 'approved' ? 'draft' : next.status}));
  }
  function updateBeat(id: string, patch: Partial<Beat>) {
    if (draft) edit({...draft, beats: draft.beats.map(b => (b.id === id ? {...b, ...patch} : b))});
  }
  async function request(suffix: string, method: string, body: unknown) {
    const r = await apiFetch(url + suffix, {
      method,
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    if (r.status === 409) {
      const latest = await responseJson(await apiFetch(url));
      if (mounted.current) setConflict(latest);
    }
    return responseJson(r);
  }
  async function save(status: ActingDraft['status']) {
    if (!draft) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const saved: ActingSnapshot = await request('', 'PUT', {...draft, status});
      if (!mounted.current) return;
      setServer(saved);
      setDraft(fromSnapshot(saved));
      setConflict(null);
      setDirty(false);
      clearLocal(key);
      setNotice(status === 'approved' ? 'Постановочная заметка утверждена.' : 'Заметка сохранена.');
    } catch (e) {
      if (mounted.current) setError((e as Error).message);
    } finally {
      if (mounted.current) setBusy(false);
    }
  }
  async function download() {
    if (!draft) return;
    setBusy(true);
    setError('');
    try {
      const result = await request('/export', 'POST', {
        base_revision: draft.base_revision,
        source_revision: draft.source_revision,
      });
      if (!mounted.current) return;
      const href = URL.createObjectURL(new Blob([result.text], {type: 'text/plain;charset=utf-8'}));
      const a = document.createElement('a');
      a.href = href;
      a.download = `acting-${sceneId}.txt`;
      a.click();
      window.setTimeout(() => URL.revokeObjectURL(href), 1000);
      setNotice('Постановочная заметка экспортирована.');
    } catch (e) {
      if (mounted.current) setError((e as Error).message);
    } finally {
      if (mounted.current) setBusy(false);
    }
  }
  function useServer() {
    if (!conflict) return;
    setServer(conflict);
    setDraft(fromSnapshot(conflict));
    setConflict(null);
    setDirty(false);
    clearLocal(key);
    setError('');
    setNotice('Загружена серверная версия.');
  }
  function useMine() {
    if (!conflict || !draft) return;
    setServer(conflict);
    edit(keepDraft(draft, conflict));
    setConflict(null);
    setError('');
    setNotice('Черновик привязан к актуальной версии. Проверь состав и сохрани.');
  }

  const actorList = conflict?.actors || server?.actors || [];
  const shots = conflict?.shots || server?.shots || [];
  const status =
    draft?.status === 'approved'
      ? 'Утверждено'
      : draft?.status === 'interpretation'
        ? 'Интерпретация'
        : 'Черновик';
  return (
    <details className="acting-notes" onToggle={e => setOpen(e.currentTarget.open)}>
      <summary
        onClick={e => {
          if (busy) e.preventDefault();
        }}
      >
        Актёрская задача
      </summary>
      {open && (
        <>
          <p>
            Постановочная заметка к сцене. Бит — попытка героя добиться цели, а не отдельный кадр. Реплики и
            канон сохраняются отдельно.
          </p>
          {error && <p role="alert">{error}</p>}
          {!storageOK && (
            <p role="alert">
              Локальный черновик не удалось записать. Сохрани заметку на сервере перед уходом.
            </p>
          )}
          {notice && <p role="status">{notice}</p>}
          {busy && <p role="status">Загрузка…</p>}
          {server?.stale && (
            <p role="alert">
              Сцена, её состав или планы изменились после сохранения заметки. Проверь постановку и сохрани
              новую версию.
            </p>
          )}
          {conflict && (
            <section className="acting-conflict" aria-label="Сравнение версий">
              <h4>Версии различаются. Твой черновик сохранён локально.</h4>
              <p>
                Серверная версия {conflict.revision} · {conflict.scene.title}
              </p>
              <p>Текущий текст сцены: {conflict.scene.notes || 'Нет описания'}</p>
              {conflict.beats.map((b, i) => (
                <details key={b.id}>
                  <summary>
                    {i + 1}. {b.objective || 'Без цели'} → {b.visible_action || 'Без действия'}
                  </summary>
                  <p>Актёр: {conflict.actors.find(a => a.id === b.actor_id)?.title || 'Вне состава'}</p>
                  {b.partner_id && (
                    <p>Партнёр: {conflict.actors.find(a => a.id === b.partner_id)?.title || 'Вне состава'}</p>
                  )}
                  <p>
                    Планы:{' '}
                    {b.shot_ids
                      .map(id => conflict.shots.find(s => s.id === id)?.title || 'Удалённый план')
                      .join(', ') || 'Не указаны'}
                  </p>
                  <dl>
                    {beatFields.map(([field, label]) => (
                      <div key={field}>
                        <dt>{label}</dt>
                        <dd>{b[field] || '—'}</dd>
                      </div>
                    ))}
                  </dl>
                </details>
              ))}
              <button type="button" disabled={busy} onClick={useMine}>
                Оставить мой черновик для новой версии
              </button>
              <button type="button" disabled={busy} onClick={useServer}>
                Заменить мой черновик серверной версией
              </button>
            </section>
          )}
          {draft && (
            <fieldset disabled={busy}>
              <legend>
                {status} · версия {draft.base_revision}
                {dirty ? ' · есть несохранённые правки' : ''}
              </legend>
              {!actorList.length && <p>Сначала добавь героев в состав этой сцены.</p>}
              {draft.beats.map((beat, i) => (
                <section className="acting-beat" key={beat.id} aria-label={`Бит ${i + 1}`}>
                  <h4>Бит {i + 1}</h4>
                  <div className="acting-grid">
                    <label>
                      Актёр
                      <select
                        value={beat.actor_id}
                        onChange={e =>
                          updateBeat(beat.id, {
                            actor_id: e.target.value,
                            partner_id: beat.partner_id === e.target.value ? null : beat.partner_id,
                          })
                        }
                      >
                        {!actorList.some(a => a.id === beat.actor_id) && (
                          <option value={beat.actor_id}>Персонаж вне текущего состава</option>
                        )}
                        {actorList.map(a => (
                          <option key={a.id} value={a.id}>
                            {a.title}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Партнёр
                      <select
                        value={beat.partner_id || ''}
                        onChange={e => updateBeat(beat.id, {partner_id: e.target.value || null})}
                      >
                        <option value="">Не указан</option>
                        {beat.partner_id && !actorList.some(a => a.id === beat.partner_id) && (
                          <option value={beat.partner_id}>Персонаж вне текущего состава</option>
                        )}
                        {actorList
                          .filter(a => a.id !== beat.actor_id)
                          .map(a => (
                            <option key={a.id} value={a.id}>
                              {a.title}
                            </option>
                          ))}
                      </select>
                    </label>
                    {beatFields.slice(0, 7).map(([field, label]) => (
                      <label key={field}>
                        {label}
                        <textarea
                          aria-label={label}
                          rows={2}
                          maxLength={2000}
                          value={beat[field]}
                          onChange={e => updateBeat(beat.id, {[field]: e.target.value})}
                        />
                      </label>
                    ))}
                  </div>
                  <details>
                    <summary>Планы, движение и звук — по необходимости</summary>
                    <div className="acting-grid">
                      {beatFields.slice(7).map(([field, label]) => (
                        <label key={field}>
                          {label}
                          <textarea
                            aria-label={label}
                            rows={2}
                            maxLength={2000}
                            value={beat[field]}
                            onChange={e => updateBeat(beat.id, {[field]: e.target.value})}
                          />
                        </label>
                      ))}
                    </div>
                    <fieldset>
                      <legend>Связанные планы сцены</legend>
                      {shots.map(s => (
                        <label key={s.id}>
                          <input
                            type="checkbox"
                            checked={beat.shot_ids.includes(s.id)}
                            onChange={e =>
                              updateBeat(beat.id, {shot_ids: toggleId(beat.shot_ids, s.id, e.target.checked)})
                            }
                          />
                          {s.title}
                        </label>
                      ))}
                      {beat.shot_ids
                        .filter(id => !shots.some(s => s.id === id))
                        .map(id => (
                          <label key={id}>
                            <input
                              type="checkbox"
                              checked
                              onChange={() =>
                                updateBeat(beat.id, {shot_ids: beat.shot_ids.filter(s => s !== id)})
                              }
                            />
                            План удалён или перемещён — снять связь
                          </label>
                        ))}
                    </fieldset>
                  </details>
                  <div className="acting-actions">
                    {([-1, 1] as const).map(direction => (
                      <button
                        type="button"
                        key={direction}
                        disabled={direction === -1 ? i === 0 : i === draft.beats.length - 1}
                        aria-label={`Бит ${i + 1} ${direction === -1 ? 'выше' : 'ниже'}`}
                        onClick={() => {
                          const ids = moveItem(
                            draft.beats.map(b => b.id),
                            i,
                            direction
                          );
                          if (ids)
                            edit({...draft, beats: ids.map(id => draft.beats.find(b => b.id === id)!)});
                        }}
                      >
                        {direction === -1 ? '↑' : '↓'}
                      </button>
                    ))}
                    <button
                      type="button"
                      onClick={() => edit({...draft, beats: draft.beats.filter(b => b.id !== beat.id)})}
                    >
                      Убрать бит
                    </button>
                  </div>
                </section>
              ))}
              <div className="acting-actions">
                <button
                  type="button"
                  disabled={!actorList.length || draft.beats.length >= 50}
                  onClick={() => edit({...draft, beats: [...draft.beats, newBeat(actorList[0].id)]})}
                >
                  Добавить бит
                </button>
                <button type="button" disabled={!!conflict} onClick={() => save('draft')}>
                  Сохранить черновик
                </button>
                <button type="button" disabled={!!conflict} onClick={() => save('interpretation')}>
                  Сохранить интерпретацию
                </button>
                <button
                  type="button"
                  disabled={!!conflict || !draft.beats.length}
                  onClick={() => save('approved')}
                >
                  Утвердить заметку
                </button>
                <button
                  type="button"
                  disabled={dirty || !!conflict || !draft.base_revision || !!server?.stale}
                  onClick={download}
                >
                  Экспорт .txt
                </button>
              </div>
            </fieldset>
          )}
          <button type="button" disabled={busy} onClick={() => setReload(v => v + 1)}>
            Проверить версии
          </button>
        </>
      )}
    </details>
  );
}
