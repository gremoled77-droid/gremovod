import {useEffect, useState} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
import {
  addFact,
  cloneContract,
  contractPayload,
  CONTINUITY_MODES,
  DirectorBundle,
  DirectorContract,
  DirectorFact,
  DirectorIssue,
  DirectorState,
  emptyContract,
  NARRATIVE_ROLES,
  removeFact,
  seriesIssues,
  shotIssues,
  toggleEvent,
  updateFact,
  validateDraft,
} from './shotContract';
import './shotContract.css';

const call = async (url: string, body?: unknown, method = 'POST') =>
  responseJson(
    await apiFetch(
      url,
      body === undefined
        ? undefined
        : {method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}
    )
  );

export default function ShotContractInspector({
  pid,
  sid,
  shotId,
  sceneId,
  title,
  onClose,
}: {
  pid: string;
  sid: string;
  shotId: string;
  sceneId: string;
  title: string;
  onClose: () => void;
}) {
  const url = `/api/productions/${pid}/series/${sid}/director/contracts`;
  const [bundle, setBundle] = useState<DirectorBundle | null>(null);
  const [draft, setDraft] = useState<DirectorContract | null>(null);
  const [revision, setRevision] = useState(0);
  const [checked, setChecked] = useState<DirectorIssue[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const take = (data: DirectorBundle) => {
    setBundle(data);
    const entry = data.contracts.find(item => item.shot_id === shotId);
    setRevision(entry?.revision ?? 0);
    setDraft(entry?.contract ? cloneContract(entry.contract) : emptyContract(shotId, sceneId));
  };

  useEffect(() => {
    let live = true;
    setBusy(true);
    setError('');
    call(url)
      .then((data: DirectorBundle) => {
        if (live) take(data);
      })
      .catch(e => {
        if (live) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (live) setBusy(false);
      });
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, shotId, sceneId]);

  if (!draft) {
    return (
      <section className="shot-contract">
        {error && <p role="alert">{error}</p>}
        {!error && <p>Загрузка контракта…</p>}
      </section>
    );
  }

  const problems = validateDraft(draft);
  const state = draft.physical_state;
  const setState = (next: DirectorState) => setDraft({...draft, physical_state: next});
  const locked = bundle?.locked_predicates ?? [];
  const predicates = bundle?.predicates ?? {};

  const save = async () => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const result = await call(
        `${url}/${shotId}`,
        {base_revision: revision, contract: contractPayload(draft)},
        'PUT'
      );
      setChecked(result.issues || []);
      setNotice(
        result.downgraded
          ? 'Контракт сохранён как черновик: устрани ошибки, чтобы утвердить его.'
          : 'Контракт сохранён.'
      );
      take(await call(url));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const check = async () => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const result = await call(`${url}/check`, {contract: contractPayload(draft)});
      setChecked(result.issues || []);
      setNotice(result.ok ? 'Нарушений не найдено.' : 'Найдены замечания — они перечислены ниже.');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const own = shotIssues(bundle?.issues ?? [], shotId);
  const others = seriesIssues(bundle?.issues ?? [], shotId);

  return (
    <section className="shot-contract">
      <header className="sc-head">
        <b>Контракт кадра · {title}</b>
        <button type="button" onClick={onClose}>
          Закрыть
        </button>
      </header>
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      <fieldset disabled={busy}>
        <div className="sc-grid">
          <label>
            Длительность, с
            <input
              type="number"
              min="0.1"
              step="0.1"
              value={draft.duration_sec}
              onChange={e => setDraft({...draft, duration_sec: Number(e.target.value)})}
            />
          </label>
          <label>
            Роль в сюжете
            <select
              value={draft.narrative_role}
              onChange={e => setDraft({...draft, narrative_role: e.target.value})}
            >
              {NARRATIVE_ROLES.map(role => (
                <option key={role.id} value={role.id}>
                  {role.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            Статус
            <select value={draft.status} onChange={e => setDraft({...draft, status: e.target.value})}>
              <option value="draft">Черновик</option>
              <option value="proposed">Предложен</option>
              <option value="approved">Утверждён</option>
            </select>
          </label>
          <label>
            Непрерывность
            <select
              value={state.continuity_mode}
              onChange={e => setState({...state, continuity_mode: e.target.value})}
            >
              {CONTINUITY_MODES.map(mode => (
                <option key={mode.id} value={mode.id}>
                  {mode.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            Кадр
            <input
              maxLength={80}
              value={draft.camera.framing}
              onChange={e => setDraft({...draft, camera: {...draft.camera, framing: e.target.value}})}
            />
          </label>
          <label>
            Движение камеры
            <input
              maxLength={80}
              value={draft.camera.movement}
              onChange={e => setDraft({...draft, camera: {...draft.camera, movement: e.target.value}})}
            />
          </label>
        </div>
        <h4>События сценария</h4>
        {!bundle?.events.length && (
          <p className="sc-muted">
            В плане серии нет событий. Сохрани план сюжета — тогда кадр можно будет привязать к сценарию.
          </p>
        )}
        <div className="sc-events">
          {bundle?.events.map(event => (
            <label key={event.event_id}>
              <input
                type="checkbox"
                checked={draft.source_event_ids.includes(event.event_id)}
                onChange={() =>
                  setDraft({
                    ...draft,
                    source_event_ids: toggleEvent(draft.source_event_ids, event.event_id),
                  })
                }
              />
              {event.text}
            </label>
          ))}
        </div>
        <FactEditor
          title="Состояние в начале кадра"
          rows={state.opening}
          predicates={predicates}
          locked={locked}
          onChange={rows => setState({...state, opening: rows})}
        />
        <FactEditor
          title="Переходы внутри кадра"
          rows={state.transitions}
          predicates={predicates}
          locked={locked}
          transitions
          onChange={rows => setState({...state, transitions: rows})}
        />
        <FactEditor
          title="Состояние в конце кадра"
          rows={state.closing}
          predicates={predicates}
          locked={locked}
          onChange={rows => setState({...state, closing: rows})}
        />
        {problems.length > 0 && (
          <ul className="sc-problems">
            {problems.map(problem => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        )}
        <div className="sc-actions">
          <button type="button" onClick={check} disabled={problems.length > 0}>
            Проверить
          </button>
          <button type="button" onClick={save} disabled={problems.length > 0}>
            Сохранить контракт
          </button>
          <small>Ревизия контракта: {revision}</small>
        </div>
      </fieldset>
      <IssueList title="Замечания по кадру" issues={checked.length ? checked : own} />
      <IssueList title="Замечания серии" issues={others} />
    </section>
  );
}

function FactEditor({
  title,
  rows,
  onChange,
  predicates,
  locked,
  transitions,
}: {
  title: string;
  rows: DirectorFact[];
  onChange: (rows: DirectorFact[]) => void;
  predicates: Record<string, string>;
  locked: string[];
  transitions?: boolean;
}) {
  return (
    <fieldset className="sc-facts">
      <legend>{title}</legend>
      {rows.map((fact, index) => (
        <div className="sc-fact" key={index}>
          <input
            aria-label="Предмет"
            placeholder="предмет"
            maxLength={64}
            value={fact.subject_id}
            onChange={e => onChange(updateFact(rows, index, {subject_id: e.target.value}))}
          />
          <select
            aria-label="Предикат"
            value={fact.predicate}
            onChange={e => onChange(updateFact(rows, index, {predicate: e.target.value}))}
          >
            <option value="">предикат</option>
            {Object.entries(predicates).map(([id, label]) => (
              <option key={id} value={id}>
                {label}
                {locked.includes(id) ? ' · не менять' : ''}
              </option>
            ))}
          </select>
          <input
            aria-label="Значение"
            placeholder="значение"
            maxLength={200}
            value={fact.value}
            onChange={e => onChange(updateFact(rows, index, {value: e.target.value}))}
          />
          {transitions && (
            <>
              <input
                aria-label="Было"
                placeholder="было"
                maxLength={200}
                value={fact.from_value ?? ''}
                onChange={e => onChange(updateFact(rows, index, {from_value: e.target.value}))}
              />
              <input
                aria-label="Стало"
                placeholder="стало"
                maxLength={200}
                value={fact.to_value ?? ''}
                onChange={e => onChange(updateFact(rows, index, {to_value: e.target.value}))}
              />
              <input
                aria-label="Действие"
                placeholder="действие"
                maxLength={300}
                value={fact.action}
                onChange={e => onChange(updateFact(rows, index, {action: e.target.value}))}
              />
              <input
                aria-label="Событие"
                placeholder="событие"
                maxLength={64}
                value={fact.event_id ?? ''}
                onChange={e => onChange(updateFact(rows, index, {event_id: e.target.value}))}
              />
            </>
          )}
          <button type="button" onClick={() => onChange(removeFact(rows, index))}>
            Убрать
          </button>
        </div>
      ))}
      <button type="button" onClick={() => onChange(addFact(rows))}>
        Добавить факт
      </button>
    </fieldset>
  );
}

function IssueList({title, issues}: {title: string; issues: DirectorIssue[]}) {
  return (
    <>
      <h4>{title}</h4>
      {!issues.length && <p className="sc-muted">Замечаний нет.</p>}
      <ul className="sc-issues">
        {issues.map((issue, index) => (
          <li key={index} className={'sc-issue ' + issue.severity}>
            <b>
              {issue.severity === 'error' ? 'Ошибка' : issue.severity === 'warning' ? 'Внимание' : 'Заметка'}
            </b>{' '}
            {issue.message}
          </li>
        ))}
      </ul>
    </>
  );
}
