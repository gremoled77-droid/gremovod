import {useEffect, useState} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
import CinemaInfo from './CinemaInfo';
import {LINE_LABELS, SHAPE_LABELS, SPACE_LABELS, TONE_LABELS, type VisualRules} from './visualPlan';
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
});

type Response = {rules: VisualRules; editable: boolean; prompt: string};

/** Визуальные правила серии, сцены, локации или героя; английский текст уходит в задания ChatGPT. */
export default function VisualRulesForm({pid, nid}: {pid: string; nid: string}) {
  const url = `/api/productions/${pid}/nodes/${nid}/visual-rules`;
  const [draft, setDraft] = useState<VisualRules>(empty),
    [prompt, setPrompt] = useState(''),
    [editable, setEditable] = useState(false),
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
