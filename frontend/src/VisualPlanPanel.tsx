import {useCallback, useEffect, useState} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
import CinemaInfo from './CinemaInfo';
import {
  describeAnalysis,
  emptyPlan,
  LINE_LABELS,
  planFromAnalysis,
  SHAPE_LABELS,
  SPACE_LABELS,
  TONE_LABELS,
  sectorJumps,
  tensionWarnings,
  type FrameAnalysis,
  type ShotPoint,
  type VisualPlan,
} from './visualPlan';
import './visualPlan.css';

type SceneLike = {id: string; number: number; frames: {id: string; number: number; title: string}[]};

export function useVisualPlans(pid: string, sid: string) {
  const [plans, setPlans] = useState<Record<string, VisualPlan>>({}),
    [error, setError] = useState('');
  useEffect(() => {
    let live = true;
    setPlans({});
    if (pid && sid)
      void apiFetch(`/api/productions/${pid}/series/${sid}/visual-plan`)
        .then(responseJson)
        .then(d => {
          if (live) setPlans(d.plans || {});
        })
        .catch(e => {
          if (live) setError(e instanceof Error ? e.message : String(e));
        });
    return () => {
      live = false;
    };
  }, [pid, sid]);
  const save = useCallback(
    async (nid: string, plan: VisualPlan) => {
      const saved = await responseJson(
        await apiFetch(`/api/productions/${pid}/nodes/${nid}/visual-plan`, {
          method: 'PUT',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(plan),
        })
      );
      setPlans(p => ({...p, [nid]: saved}));
    },
    [pid]
  );
  return {plans, save, error};
}

export function shotPoints(scenes: SceneLike[], plans: Record<string, VisualPlan>): ShotPoint[] {
  return scenes.flatMap(scene =>
    scene.frames.map(frame => {
      const p = plans[frame.id] || emptyPlan();
      return {
        id: frame.id,
        label: `${scene.number}.${frame.number}`,
        space: p.space,
        line: p.line,
        sector_start: p.sector_start,
        sector_end: p.sector_end,
        story: p.story,
        visual: p.visual,
      };
    })
  );
}

const W = 640,
  H = 150,
  PAD = 22;
function path(points: ShotPoint[], key: 'story' | 'visual') {
  const step = points.length > 1 ? (W - PAD * 2) / (points.length - 1) : 0;
  let d = '';
  points.forEach((p, i) => {
    const v = p[key];
    if (v === null) return;
    const x = PAD + i * step,
      y = H - PAD - (v / 10) * (H - PAD * 2);
    d += (d && points[i - 1]?.[key] !== null ? 'L' : 'M') + x.toFixed(1) + ' ' + y.toFixed(1);
  });
  return d;
}

export async function analyzeAsset(assetId: string): Promise<FrameAnalysis> {
  return responseJson(await apiFetch(`/api/library/${assetId}/analysis`));
}

export function TensionGraph({
  points,
  onEstimate,
  estimating,
}: {
  points: ShotPoint[];
  onEstimate?: () => void;
  estimating?: boolean;
}) {
  const warnings = tensionWarnings(points),
    jumps = sectorJumps(points),
    step = points.length > 1 ? (W - PAD * 2) / (points.length - 1) : 0;
  return (
    <section className="vp-graph" aria-label="График напряжения">
      <div className="vp-head">
        <h3>Напряжение: сюжет и картинка</h3>
        <CinemaInfo topic="visual" />
      </div>
      {points.length < 2 ? (
        <p className="muted">
          Нужно хотя бы два кадра. Оценки 0–10 ставятся в блоке «Визуальный план» кадра.
        </p>
      ) : (
        <>
          <svg
            viewBox={`0 0 ${W} ${H}`}
            role="img"
            aria-label="Две линии: напряжение сюжета и визуальное напряжение по кадрам"
          >
            <line x1={PAD} x2={W - PAD} y1={H - PAD} y2={H - PAD} className="vp-axis" />
            {points.map((p, i) => (
              <g key={p.id}>
                <line
                  x1={PAD + i * step}
                  x2={PAD + i * step}
                  y1={H - PAD}
                  y2={H - PAD + 4}
                  className="vp-axis"
                />
                {(points.length <= 14 || i % Math.ceil(points.length / 14) === 0) && (
                  <text x={PAD + i * step} y={H - 4} textAnchor="middle">
                    {p.label}
                  </text>
                )}
              </g>
            ))}
            <path d={path(points, 'story')} className="vp-story" />
            <path d={path(points, 'visual')} className="vp-visual" />
          </svg>
          <p className="vp-legend">
            <i className="vp-story-dot" /> сюжет <i className="vp-visual-dot" /> визуальное напряжение
          </p>
        </>
      )}
      {onEstimate && (
        <button type="button" disabled={estimating} onClick={onEstimate}>
          {estimating ? 'Считаю…' : 'Оценить пустые кадры по картинкам'}
        </button>
      )}
      {warnings.map(w => (
        <p key={w} className="vp-warn" role="status">
          {w}
        </p>
      ))}
      {!!jumps.length && (
        <details>
          <summary>Склейки с прыжком внимания: {jumps.length}</summary>
          <ul className="vp-jumps">
            {jumps.map(j => (
              <li key={j.from + j.to}>
                {j.from} → {j.to}: сектор {j.a} → {j.b}. Прыжок добавляет напряжение; если он не нужен, сдвинь
                объект в том же секторе.
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

const SECTORS = [1, 2, 3, 4, 5, 6, 7, 8, 9];
export function VisualPlanForm({
  kind,
  plan,
  onSave,
  assetId,
  verticalUrl,
}: {
  kind: 'scene' | 'frame';
  plan?: VisualPlan;
  onSave: (plan: VisualPlan) => Promise<void>;
  assetId?: string | null;
  verticalUrl?: string;
}) {
  const [draft, setDraft] = useState<VisualPlan>(() => plan || emptyPlan()),
    [state, setState] = useState<'' | 'saving' | 'saved' | 'error'>(''),
    [message, setMessage] = useState(''),
    [analysis, setAnalysis] = useState<FrameAnalysis | null>(null),
    [showSquint, setShowSquint] = useState(false),
    [vertical, setVertical] = useState('');
  useEffect(() => {
    if (plan) setDraft(plan);
  }, [plan]);
  const set = <K extends keyof VisualPlan>(key: K, value: VisualPlan[K]) => {
    setDraft(d => ({...d, [key]: value}));
    setState('');
  };
  const num = (v: string) => (v === '' ? null : Number(v));
  const options = (labels: Record<string, string>) =>
    Object.entries(labels).map(([value, label]) => (
      <option key={value} value={value}>
        {label}
      </option>
    ));
  const sectorPick = (key: 'sector_start' | 'sector_end', label: string) => (
    <label>
      {label}
      <select value={draft[key] ?? ''} onChange={e => set(key, num(e.target.value))}>
        <option value="">—</option>
        {SECTORS.map(s => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>
    </label>
  );
  const scale = (key: 'story' | 'visual', label: string) => (
    <label>
      {label}
      <select value={draft[key] ?? ''} onChange={e => set(key, num(e.target.value))}>
        <option value="">—</option>
        {Array.from({length: 11}, (_, i) => (
          <option key={i} value={i}>
            {i}
          </option>
        ))}
      </select>
    </label>
  );
  return (
    <details className="vp-form">
      <summary>
        Визуальный план
        {(draft.story !== null || draft.visual !== null) && (
          <small>
            {' '}
            · сюжет {draft.story ?? '—'} / картинка {draft.visual ?? '—'}
          </small>
        )}
      </summary>
      <div className="vp-fields">
        {scale('story', 'Напряжение сюжета 0–10')}
        {scale('visual', 'Визуальное напряжение 0–10')}
        {kind === 'frame' && (
          <label>
            Бит сцены №
            <input
              type="number"
              min={1}
              max={99}
              value={draft.beat ?? ''}
              onChange={e => set('beat', num(e.target.value))}
            />
          </label>
        )}
        <label>
          Пространство
          <select value={draft.space} onChange={e => set('space', e.target.value as VisualPlan['space'])}>
            {options(SPACE_LABELS)}
          </select>
        </label>
        <label>
          Линейный мотив
          <select value={draft.line} onChange={e => set('line', e.target.value as VisualPlan['line'])}>
            {options(LINE_LABELS)}
          </select>
        </label>
        <label>
          Форма героя/кадра
          <select value={draft.shape} onChange={e => set('shape', e.target.value as VisualPlan['shape'])}>
            {options(SHAPE_LABELS)}
          </select>
        </label>
        <label>
          Тон
          <select value={draft.tone} onChange={e => set('tone', e.target.value as VisualPlan['tone'])}>
            {options(TONE_LABELS)}
          </select>
        </label>
        {kind === 'frame' && sectorPick('sector_start', 'Внимание в начале (сектор 1–9)')}
        {kind === 'frame' && sectorPick('sector_end', 'Внимание в конце (сектор 1–9)')}
      </div>
      {kind === 'scene' && (
        <label className="vp-wide">
          Биты сцены (по строке: момент, где меняются отношения героев)
          <textarea
            rows={4}
            maxLength={3000}
            value={draft.beats}
            onChange={e => set('beats', e.target.value)}
          />
        </label>
      )}
      <label className="vp-wide">
        Заметка
        <input maxLength={500} value={draft.note} onChange={e => set('note', e.target.value)} />
      </label>
      <p className="muted">Сетка секторов: 1 2 3 сверху, 4 5 6 в середине, 7 8 9 снизу.</p>
      {kind === 'frame' && verticalUrl && (
        <div className="vp-analysis">
          <button
            type="button"
            onClick={async () => {
              setMessage('');
              try {
                setVertical((await responseJson(await apiFetch(verticalUrl))).prompt);
              } catch (e) {
                setState('error');
                setMessage(e instanceof Error ? e.message : String(e));
              }
            }}
          >
            Промпт для версии 9:16
          </button>
          {vertical && (
            <>
              <textarea readOnly rows={7} value={vertical} onFocus={e => e.currentTarget.select()} />
              <p className="muted">
                Не обрезай 16:9: сгенерируй вертикальный кадр заново с этим текстом и тем же утверждённым
                референсом.
              </p>
            </>
          )}
        </div>
      )}
      {kind === 'frame' && assetId && (
        <div className="vp-analysis">
          <button
            type="button"
            onClick={async () => {
              setMessage('');
              try {
                const result = await analyzeAsset(assetId);
                setAnalysis(result);
                setDraft(d => planFromAnalysis(d, result));
                setState('');
              } catch (e) {
                setState('error');
                setMessage(e instanceof Error ? e.message : String(e));
              }
            }}
          >
            Анализ картинки (бесплатно)
          </button>
          {analysis && (
            <>
              <ul>
                {describeAnalysis(analysis).map(t => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
              <p className="muted">
                Пустые поля заполнены по анализу, уже выбранные не тронуты. Проверь и нажми «Сохранить план».
              </p>
              <button type="button" onClick={() => setShowSquint(v => !v)}>
                {showSquint ? 'Скрыть «прищур»' : 'Показать «прищур» (ч/б, размытие)'}
              </button>
              {showSquint && (
                <img
                  className="vp-squint"
                  src={`/api/library/${assetId}/squint`}
                  alt="Кадр в чёрно-белом размытом виде"
                />
              )}
            </>
          )}
        </div>
      )}
      <button
        type="button"
        disabled={state === 'saving'}
        onClick={async () => {
          setState('saving');
          setMessage('');
          try {
            await onSave(draft);
            setState('saved');
          } catch (e) {
            setState('error');
            setMessage(e instanceof Error ? e.message : String(e));
          }
        }}
      >
        {state === 'saving' ? 'Сохраняю…' : 'Сохранить план'}
      </button>
      {state === 'saved' && <span className="vp-ok"> сохранено</span>}
      {state === 'error' && (
        <span role="alert" className="vp-err">
          {' '}
          {message}
        </span>
      )}
    </details>
  );
}
