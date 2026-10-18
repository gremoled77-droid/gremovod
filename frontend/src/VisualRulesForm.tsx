import {useEffect, useState} from 'react';
import {apiFetch, responseJson} from './api';
import CinemaInfo from './CinemaInfo';
import {
  HERO_FRAME_FIELDS,
  HERO_FRAME_PRESETS,
  LINE_LABELS,
  MAX_HERO_FRAMES,
  NORM_FIELDS,
  SHAPE_LABELS,
  SPACE_LABELS,
  TONE_LABELS,
  type HeroFrame,
  type VisualRules,
} from './visualPlan';
import './visualPlan.css';

const empty = (): VisualRules => ({
  space: '',
  line: '',
  shape: '',
  tone: '',
  palette: '',
  camera: '',
  rhythm: '',
  note: '',
  norm: {format: '', normal_lens: '', angle_rules: '', color_rules: ''},
  hero_frames: [],
});

const emptyFrame = (): HeroFrame => ({state: '', size: '', angle: '', lens: '', looking_room: ''});

type Response = {rules: VisualRules; kind?: string; editable: boolean; prompt: string};

/** Визуальные правила серии, сцены, локации или героя; английский текст уходит в задания ChatGPT. */
export default function VisualRulesForm({pid, nid}: {pid: string; nid: string}) {
  const url = `/api/productions/${pid}/nodes/${nid}/visual-rules`;
  const [draft, setDraft] = useState<VisualRules>(empty),
    [prompt, setPrompt] = useState(''),
    [editable, setEditable] = useState(false),
    [kind, setKind] = useState(''),
    [state, setState] = useState<'' | 'saving' | 'saved' | 'error'>(''),
    [message, setMessage] = useState('');
  useEffect(() => {
    let live = true;
    setState('');
    void apiFetch(url)
      .then(responseJson)
      .then((d: Response) => {
        if (!live) return;
        setDraft(d.rules);
        setPrompt(d.prompt);
        setEditable(d.editable);
        setKind(d.kind || '');
      })
      .catch(e => {
        if (live) setMessage(e instanceof Error ? e.message : String(e));
      });
    return () => {
      live = false;
    };
  }, [url]);
  const set = <K extends keyof VisualRules>(key: K, value: VisualRules[K]) => {
    setDraft(d => ({...d, [key]: value}));
    setState('');
  };
  const select = (
    key: 'space' | 'line' | 'shape' | 'tone',
    label: string,
    labels: Record<string, string>
  ) => (
    <label>
      {label}
      <select value={draft[key]} onChange={e => set(key, e.target.value as never)}>
        {Object.entries(labels).map(([value, text]) => (
          <option key={value} value={value}>
            {text}
          </option>
        ))}
      </select>
    </label>
  );
  const text = (key: 'palette' | 'camera' | 'rhythm', label: string, hint: string) => (
    <label className="vp-wide">
      {label}
      <input maxLength={300} value={draft[key]} onChange={e => set(key, e.target.value)} placeholder={hint} />
    </label>
  );
  const setFrame = (i: number, key: keyof HeroFrame, value: string) =>
    set(
      'hero_frames',
      draft.hero_frames.map((f, j) => (j === i ? {...f, [key]: value} : f))
    );
  if (!editable) return null;
  return (
    <details className="vp-form">
      <summary>
        Визуальные правила <CinemaInfo topic="visual" />
      </summary>
      <p className="muted">
        Правила наследуются: серия → сцена → локация → герои → план кадра. Всё заданное попадает в задания
        ChatGPT этой карточки и её кадров.
      </p>
      <div className="vp-fields">
        {select('space', 'Пространство', SPACE_LABELS)}
        {select('line', 'Линейный мотив', LINE_LABELS)}
        {select('shape', 'Форма', SHAPE_LABELS)}
        {select('tone', 'Тон', TONE_LABELS)}
      </div>
      {text(
        'palette',
        'Палитра (3–5 цветов словами или образцами)',
        'охра, выцветший бирюзовый, красный акцент'
      )}
      {text('camera', 'Камера', 'камера жёстко в салоне, фон скользит за окнами')}
      {text('rhythm', 'Ритм', 'медленный равномерный; резкие склейки только в кульминации')}
      {kind === 'series' && (
        <fieldset className="vp-norm">
          <legend>
            Норма серии <CinemaInfo topic="world" />
          </legend>
          {NORM_FIELDS.map(([key, label, hint]) => (
            <label key={key} className="vp-wide">
              {label}
              <input
                maxLength={key === 'format' ? 100 : key === 'normal_lens' ? 200 : 300}
                value={draft.norm[key]}
                placeholder={hint}
                onChange={e => set('norm', {...draft.norm, [key]: e.target.value})}
              />
            </label>
          ))}
        </fieldset>
      )}
      {kind === 'character' && (
        <fieldset className="vp-norm">
          <legend>
            Рамка героя <CinemaInfo topic="character" />
          </legend>
          {draft.hero_frames.map((f, i) => (
            <div key={i} className="vp-hero-row">
              {HERO_FRAME_FIELDS.map(([key, label]) => (
                <input
                  key={key}
                  aria-label={label}
                  placeholder={label}
                  maxLength={100}
                  list={key === 'state' ? 'vp-hero-states' : undefined}
                  value={f[key]}
                  onChange={e => setFrame(i, key, e.target.value)}
                />
              ))}
              <button
                type="button"
                aria-label="Убрать состояние"
                onClick={() =>
                  set(
                    'hero_frames',
                    draft.hero_frames.filter((_, j) => j !== i)
                  )
                }
              >
                ×
              </button>
            </div>
          ))}
          <datalist id="vp-hero-states">
            {HERO_FRAME_PRESETS.map(p => (
              <option key={p} value={p} />
            ))}
          </datalist>
          <button
            type="button"
            disabled={draft.hero_frames.length >= MAX_HERO_FRAMES}
            onClick={() => set('hero_frames', [...draft.hero_frames, emptyFrame()])}
          >
            ＋ Состояние
          </button>
        </fieldset>
      )}
      <label className="vp-wide">
        Заметка
        <input maxLength={500} value={draft.note} onChange={e => set('note', e.target.value)} />
      </label>
      <button
        type="button"
        disabled={state === 'saving'}
        onClick={async () => {
          setState('saving');
          setMessage('');
          try {
            const d: Response = await responseJson(
              await apiFetch(url, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(draft),
              })
            );
            setDraft(d.rules);
            setPrompt(d.prompt);
            setState('saved');
          } catch (e) {
            setState('error');
            setMessage(e instanceof Error ? e.message : String(e));
          }
        }}
      >
        {state === 'saving' ? 'Сохраняю…' : 'Сохранить правила'}
      </button>
      {state === 'saved' && <span className="vp-ok"> сохранено</span>}
      {state === 'error' && (
        <span role="alert" className="vp-err">
          {' '}
          {message}
        </span>
      )}
      {prompt && (
        <details>
          <summary>Что получит ChatGPT</summary>
          <pre className="vp-prompt">{prompt}</pre>
        </details>
      )}
    </details>
  );
}
