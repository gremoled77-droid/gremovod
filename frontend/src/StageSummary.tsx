import {useCallback, useEffect, useRef, useState} from 'react';
import {apiFetch} from './api';
import {
  approveBlockReason,
  approveBody,
  errorText,
  qcManifest,
  rejectBlockReason,
  rejectBody,
  releaseCounts,
  shortSha,
  stateText,
  verdictText,
  type Gate,
} from './releaseGate';
import type {Mode} from './StageNav';

type Budget = {
  project_limit_usd: number;
  daily_limit_usd: number;
  project_reserved_usd: number;
  daily_reserved_usd: number;
};
type ReleaseArtifact = {
  id: string;
  title: string;
  project_revision: number;
  version_id: string | null;
  file_url: string;
  status: string;
  created_at: string;
};
const money = (v: number | undefined) => '$' + (v ?? 0).toFixed(2);

/** Сколько в библиотеке проекта картинок, клипов и звуковых дорожек. */
function useCounts(projectId: string) {
  const [counts, setCounts] = useState({images: 0, videos: 0, audio: 0});
  useEffect(() => {
    if (!projectId) return;
    let live = true;
    void apiFetch('/api/library?project_id=' + encodeURIComponent(projectId))
      .then(r => (r.ok ? r.json() : []))
      .then((list: {metadata?: {kind?: string}}[]) => {
        const count = (kind: string) => list.filter(a => a.metadata?.kind === kind).length;
        if (live) setCounts({images: count('image'), videos: count('video'), audio: count('audio')});
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [projectId]);
  return counts;
}

/** MP4, загруженные в выпуск (это ещё не финальные: итог решает серверный gate). */
function useReleaseArtifacts(projectId: string) {
  const [artifacts, setArtifacts] = useState<ReleaseArtifact[]>([]);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!projectId) return;
    let live = true;
    void apiFetch('/api/projects/' + encodeURIComponent(projectId) + '/release-artifacts')
      .then(r => (r.ok ? r.json() : []))
      .then((list: ReleaseArtifact[]) => {
        if (live) setArtifacts(list);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [projectId, tick]);
  const reload = useCallback(() => setTick(n => n + 1), []);
  return {artifacts, reload};
}

/** Шапка «Монтажа»: что готово к выгрузке в CapCut по этапам. */
export function MontageSummary({projectId, onMode}: {projectId: string; onMode: (m: Mode) => void}) {
  const {images, videos, audio} = useCounts(projectId);
  const cards: {mode: Mode; title: string; count: number; unit: string; hint: string}[] = [
    {mode: 'create', title: 'Кадры', count: images, unit: 'картинок', hint: 'основа клипов'},
    {mode: 'video', title: 'Видео', count: videos, unit: 'клипов', hint: 'оживлённые кадры'},
    {mode: 'audio', title: 'Звук', count: audio, unit: 'дорожек', hint: 'голос и музыка'},
  ];
  return (
    <section className="ss">
      <div className="ss-head">
        <span className="ss-eyebrow">Монтаж · CapCut</span>
        <h2>Что готово к выгрузке</h2>
        <p className="muted">
          Студия соберёт клипы и звук в порядке кадров раскадровки, а монтаж делается в CapCut на компьютере.
        </p>
      </div>
      <div className="ss-cards">
        {cards.map(c => (
          <button key={c.mode} className="ss-card" onClick={() => onMode(c.mode)}>
            <small>{c.title}</small>
            <b>{c.count}</b>
            <span>
              {c.unit} · {c.hint}
            </span>
          </button>
        ))}
      </div>
      <p className="ss-note">
        Кнопка «Выгрузить в CapCut» появится, когда будем настраивать выгрузку на компьютере.
      </p>
    </section>
  );
}

function Gauge({label, used, limit}: {label: string; used?: number; limit?: number}) {
  const p = limit ? Math.min(1, (used ?? 0) / limit) : 0;
  const R = 34;
  const C = 2 * Math.PI * R;
  return (
    <div className="hg">
      <svg viewBox="0 0 84 84" aria-hidden="true">
        <circle cx="42" cy="42" r={R} className="hg-bg" />
        <circle
          cx="42"
          cy="42"
          r={R}
          className="hg-fg"
          strokeDasharray={`${C * p} ${C}`}
          transform="rotate(-90 42 42)"
        />
      </svg>
      <div className="hg-t">
        <b>{money(used)}</b>
        <small>из {money(limit)}</small>
      </div>
      <span>{label}</span>
    </div>
  );
}

const ownerKey = 'gremovod.release.owner_id';
function storedOwner() {
  try {
    return window.localStorage.getItem(ownerKey) ?? '';
  } catch {
    return '';
  }
}
const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString('ru-RU') : '');

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

/** Приёмка итогового MP4: загрузка → N34 → решение владельца. Допуск решает сервер (`/gate`), экран только показывает. */
function ReleasePanel({
  projectId,
  artifacts,
  reload,
}: {
  projectId: string;
  artifacts: ReleaseArtifact[];
  reload: () => void;
}) {
  const [selectedId, setSelectedId] = useState('');
  const [gates, setGates] = useState<Record<string, Gate | undefined>>({});
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [ownerId, setOwnerId] = useState(storedOwner);
  const [rights, setRights] = useState(false);
  const [requireAudio, setRequireAudio] = useState(true);
  const [rejectNote, setRejectNote] = useState('');
  const [title, setTitle] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [fileKey, setFileKey] = useState(0);
  const busyRef = useRef(false); // синхронный замок: двойной клик не отправит запрос дважды
  const loadedRef = useRef(new Set<string>()); // уже запрошенные в этом проекте gate: остальные не пересчитываем
  const pendingSelectRef = useRef(''); // только что загруженный MP4: выбрать, когда он появится в списке
  const epochRef = useRef(0); // смена проекта обесценивает ответы на старые запросы

  useEffect(() => {
    epochRef.current += 1;
    busyRef.current = false;
    pendingSelectRef.current = '';
    setBusy('');
    loadedRef.current = new Set();
    setSelectedId('');
    setGates({});
    setError('');
    setNotice('');
    setRights(false);
    setRejectNote('');
  }, [projectId]);

  const base = '/api/projects/' + encodeURIComponent(projectId) + '/release-artifacts';

  const loadGate = useCallback(
    async (id: string) => {
      const epoch = epochRef.current;
      try {
        const response = await apiFetch(base + '/' + encodeURIComponent(id) + '/gate');
        const body = await readJson(response);
        if (epoch !== epochRef.current) return;
        if (!response.ok) {
          setError(errorText(response.status, body));
          return;
        }
        setGates(prev => ({...prev, [id]: body as Gate}));
      } catch (e) {
        if (epoch === epochRef.current)
          setError(e instanceof Error ? e.message : 'Не удалось получить состояние выпуска');
      }
    },
    [base]
  );

  // выбранный артефакт: первый в списке, пока выбор не сделан или артефакт пропал
  useEffect(() => {
    const pending = pendingSelectRef.current;
    if (pending) {
      if (!artifacts.some(a => a.id === pending)) return; // список ещё не обновился
      pendingSelectRef.current = '';
      setSelectedId(pending);
      return;
    }
    if (artifacts.length && !artifacts.some(a => a.id === selectedId)) setSelectedId(artifacts[0].id);
  }, [artifacts, selectedId]);

  // Хеш считается на сервере при каждом /gate: сначала выбранный, остальные — по одному, один раз.
  const idsKey = artifacts.map(a => a.id).join(',');
  useEffect(() => {
    if (!projectId || !selectedId) return;
    const epoch = epochRef.current;
    void (async () => {
      if (!loadedRef.current.has(selectedId)) await loadGate(selectedId);
      loadedRef.current.add(selectedId);
      for (const artifact of artifacts) {
        if (epoch !== epochRef.current) return;
        if (loadedRef.current.has(artifact.id)) continue;
        loadedRef.current.add(artifact.id);
        await loadGate(artifact.id);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, selectedId, idsKey, loadGate]);

  async function run(kind: string, action: (epoch: number) => Promise<void>) {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(kind);
    setError('');
    setNotice('');
    const epoch = epochRef.current;
    try {
      await action(epoch);
    } catch (e) {
      if (epoch === epochRef.current) setError(e instanceof Error ? e.message : 'Действие не выполнено');
    } finally {
      busyRef.current = false;
      if (epoch === epochRef.current) setBusy('');
    }
  }

  const upload = () =>
    run('upload', async epoch => {
      if (!file) return;
      // актуальная ревизия берётся у проекта в момент загрузки, не из старого артефакта
      const project = await apiFetch('/api/projects/' + encodeURIComponent(projectId));
      const projectBody = (await readJson(project)) as {revision?: number} | null;
      if (!project.ok || typeof projectBody?.revision !== 'number') {
        setError(errorText(project.status, projectBody));
        return;
      }
      const form = new FormData();
      form.set('file', file);
      form.set('project_revision', String(projectBody.revision));
      form.set('title', title.trim() || file.name.replace(/\.[^.]+$/, ''));
      const response = await apiFetch(base, {method: 'POST', body: form});
      const body = await readJson(response);
      if (epoch !== epochRef.current) return;
      if (!response.ok) {
        setError(errorText(response.status, body, true));
        return;
      }
      setFile(null);
      setTitle('');
      setFileKey(n => n + 1);
      setNotice('MP4 загружен. Это ещё не выпуск: запустите техническую проверку.');
      pendingSelectRef.current = (body as ReleaseArtifact).id;
      reload();
    });

  const measure = (id: string) =>
    run('qc', async epoch => {
      const response = await apiFetch(base + '/' + encodeURIComponent(id) + '/qc/measure', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({manifest: qcManifest(requireAudio)}),
      });
      const body = await readJson(response);
      if (epoch !== epochRef.current) return;
      if (!response.ok) setError(errorText(response.status, body));
      await loadGate(id);
    });

  const decide = (id: string, payload: Record<string, unknown>) =>
    run('decision', async epoch => {
      try {
        window.localStorage.setItem(ownerKey, ownerId.trim());
      } catch {
        /* хранилище недоступно — не страшно */
      }
      const response = await apiFetch(base + '/' + encodeURIComponent(id) + '/decision', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload),
      });
      const body = await readJson(response);
      if (epoch !== epochRef.current) return;
      if (!response.ok) setError(errorText(response.status, body));
      else {
        const done = body as {duplicate?: boolean};
        setNotice(done.duplicate ? 'Это решение уже было записано.' : 'Решение записано.');
        setRejectNote('');
      }
      await loadGate(id); // при любом исходе читаем состояние заново
    });

  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setNotice('SHA-256 скопирован.');
    } catch {
      setNotice('Не удалось скопировать: выделите хеш вручную.');
    }
  };

  const selected = artifacts.find(a => a.id === selectedId);
  const gate = selected ? gates[selected.id] : undefined;
  const counts = releaseCounts(
    artifacts.map(a => a.id),
    gates
  );
  const approveInput = {ownerId, rights, busy: !!busy};
  const approveBlock = approveBlockReason(gate, approveInput);
  const rejectInput = {ownerId, note: rejectNote, busy: !!busy};
  const rejectBlock = rejectBlockReason(gate, rejectInput);

  return (
    <div className="rg">
      <ul className="ss-totals rg-counts">
        <li>
          <b data-testid="final-count">{counts.final}</b> финальных MP4 (утверждены владельцем)
        </li>
        <li>
          <b>{counts.pending}</b> ожидают приёмки
          {counts.unknown ? ` · ещё не проверено сервером: ${counts.unknown}` : ''}
        </li>
      </ul>

      <div className="rg-upload">
        <input
          key={fileKey}
          type="file"
          accept="video/mp4,.mp4"
          disabled={!!busy}
          onChange={e => setFile(e.target.files?.[0] ?? null)}
        />
        <input
          type="text"
          value={title}
          placeholder="Название (необязательно)"
          maxLength={200}
          disabled={!!busy}
          onChange={e => setTitle(e.target.value)}
        />
        <button disabled={!file || !!busy} onClick={() => void upload()}>
          {busy === 'upload' ? 'Загрузка…' : 'Загрузить MP4'}
        </button>
      </div>

      {error && (
        <p className="rg-error" role="alert">
          {error}
        </p>
      )}
      {notice && !error && (
        <p className="ss-note" role="status">
          {notice}
        </p>
      )}

      {artifacts.length === 0 && <p className="ss-note">MP4 ещё не загружены.</p>}
      {artifacts.length > 0 && (
        <select
          className="rg-select"
          value={selectedId}
          aria-label="Версия выпуска"
          onChange={e => {
            setSelectedId(e.target.value);
            setError('');
            setNotice('');
            setRights(false);
          }}
        >
          {artifacts.map(a => (
            <option key={a.id} value={a.id}>
              {a.title} · {when(a.created_at)}
              {gates[a.id] ? ' · ' + stateText(gates[a.id]?.state) : ''}
            </option>
          ))}
        </select>
      )}

      {selected && (
        <div className="rg-card">
          <div className="rg-row">
            <a href={selected.file_url} download>
              {selected.title}
            </a>
            <span className={'rg-state rg-' + (gate?.state ?? 'none')}>
              {gate ? stateText(gate.state) : 'Загрузка состояния…'}
            </span>
            <button disabled={!!busy} onClick={() => void loadGate(selected.id)}>
              Обновить
            </button>
          </div>
          <p className="ss-note">
            Ревизия проекта {selected.project_revision}
            {selected.version_id ? ' · версия ' + selected.version_id : ''}
          </p>
          {gate && (
            <>
              <p className="ss-note rg-sha">
                SHA-256: <code>{gate.master_sha256 || 'файл не найден'}</code>{' '}
                {gate.master_sha256 && (
                  <button onClick={() => void copy(gate.master_sha256)}>Копировать</button>
                )}
              </p>
              <p>
                Техническая проверка N34: <b>{verdictText(gate.qc_verdict)}</b>
                {gate.qc_reason ? ' — ' + gate.qc_reason : ''}
              </p>
              {gate.qc_stale && (
                <p className="rg-error">Файл изменён после проверки: нужна новая проверка N34.</p>
              )}
              <div className="rg-row">
                <label>
                  <input
                    type="checkbox"
                    checked={requireAudio}
                    onChange={e => setRequireAudio(e.target.checked)}
                  />{' '}
                  требовать аудиодорожку
                </label>
                <button disabled={!!busy} onClick={() => void measure(selected.id)}>
                  {busy === 'qc' ? 'Проверка…' : 'Проверить N34'}
                </button>
              </div>

              <details>
                <summary>N35: покрытие мастера (только чтение)</summary>
                <p className="ss-note">
                  Статус: {gate.n35_evidence.coverage_status || '—'}
                  {gate.n35_evidence.reason ? ' — ' + gate.n35_evidence.reason : ''}
                </p>
                <ul className="ss-note">
                  {Object.entries(gate.n35_evidence.coverage).map(([name, item]) => (
                    <li key={name}>
                      {name}: {item.status}
                      {item.reason ? ' — ' + item.reason : ''}
                    </li>
                  ))}
                  <li>
                    Право на обработку в записи решения:{' '}
                    {gate.n35_evidence.processing_rights_confirmed ? 'подтверждено' : 'нет'}
                  </li>
                </ul>
              </details>

              {gate.decision_stale && (
                <p className="rg-error">
                  Прежнее решение не действует:{' '}
                  {gate.decision_stale_reason || 'файл или содержимое изменились'}
                </p>
              )}
              {gate.decided_at && (
                <p>
                  Решение: <b>{gate.decision === 'APPROVED' ? 'утверждено' : 'отклонено'}</b>,{' '}
                  {when(gate.decided_at)}, владелец «{gate.owner_id}»
                </p>
              )}

              <p className="ss-note">
                Идентификатор владельца сверяется с настройкой сервера (<code>GREMOVOD_OWNER_ID</code>). Это
                не вход в систему и не защита от других пользователей этого компьютера.
              </p>
              <div className="rg-row">
                <input
                  type="text"
                  value={ownerId}
                  placeholder="Идентификатор владельца"
                  aria-label="Идентификатор владельца"
                  onChange={e => setOwnerId(e.target.value)}
                />
                <label>
                  <input type="checkbox" checked={rights} onChange={e => setRights(e.target.checked)} />{' '}
                  подтверждаю право на обработку
                </label>
              </div>
              <div className="rg-row">
                <button
                  disabled={!!approveBlock}
                  title={approveBlock}
                  onClick={() => {
                    const payload = approveBody(gate, approveInput);
                    if (payload) void decide(selected.id, payload);
                  }}
                >
                  {busy === 'decision' ? 'Отправка…' : 'Утвердить эту версию'}
                </button>
                {approveBlock && <span className="ss-note">{approveBlock}</span>}
              </div>
              <div className="rg-row">
                <input
                  type="text"
                  value={rejectNote}
                  placeholder="Причина отклонения"
                  aria-label="Причина отклонения"
                  maxLength={2000}
                  onChange={e => setRejectNote(e.target.value)}
                />
                <button
                  disabled={!!rejectBlock}
                  title={rejectBlock}
                  onClick={() => {
                    const payload = rejectBody(gate, rejectInput);
                    if (payload) void decide(selected.id, payload);
                  }}
                >
                  Отклонить
                </button>
              </div>

              {gate.history.length > 0 && (
                <details>
                  <summary>Последние решения ({gate.history.length})</summary>
                  <ul className="ss-note">
                    {gate.history.map(item => (
                      <li key={item.decision_id}>
                        {when(item.created_at)} · {item.decision === 'APPROVED' ? 'утверждено' : 'отклонено'}{' '}
                        · {item.owner_id} · {shortSha(item.master_sha256)}
                        {item.note ? ' · ' + item.note : ''}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

/** Шапка «Выпуска»: бюджет проекта и дня, приёмка итогового MP4. */
export function ReleaseSummary({projectId}: {projectId: string}) {
  const {images, videos, audio} = useCounts(projectId);
  const {artifacts, reload} = useReleaseArtifacts(projectId);
  const [budget, setBudget] = useState<Budget | null>(null);
  useEffect(() => {
    if (!projectId) return;
    let live = true;
    void apiFetch('/api/budgets/' + encodeURIComponent(projectId))
      .then(r => (r.ok ? r.json() : null))
      .then(d => live && setBudget(d))
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [projectId]);
  return (
    <section className="ss">
      <div className="ss-head">
        <span className="ss-eyebrow">Выпуск · итоги серии</span>
        <h2>Сколько потрачено и что получено</h2>
      </div>
      <div className="ss-release">
        <div className="ss-gauges">
          <Gauge label="Проект" used={budget?.project_reserved_usd} limit={budget?.project_limit_usd} />
          <Gauge label="Сегодня" used={budget?.daily_reserved_usd} limit={budget?.daily_limit_usd} />
        </div>
        <ul className="ss-totals">
          <li>
            <b>{images}</b> картинок
          </li>
          <li>
            <b>{videos}</b> клипов
          </li>
          <li>
            <b>{audio}</b> звуковых дорожек
          </li>
        </ul>
      </div>
      <ReleasePanel projectId={projectId} artifacts={artifacts} reload={reload} />
    </section>
  );
}
