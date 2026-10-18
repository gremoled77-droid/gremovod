import {useState} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';

type Template = 'intro' | 'lower-third';
const FIELDS: Record<Template, {id: string; label: string; placeholder: string}[]> = {
  intro: [
    {id: 'series', label: 'Название сериала', placeholder: 'ГРЭМ'},
    {id: 'episode', label: 'Серия', placeholder: 'Серия 1 · Ночная смена'},
    {id: 'caption', label: 'Подпись', placeholder: 'ВАЗ-2106 · Минск'},
  ],
  'lower-third': [
    {id: 'name', label: 'Имя', placeholder: 'Грэм'},
    {id: 'role', label: 'Кто это', placeholder: 'таксист, ВАЗ-2106'},
  ],
};

/** Моушн для монтажа: заставка серии (MP4) и плашка с именем (прозрачный MOV) рендерятся локально в 03_Монтаж. */
export default function MotionPanel({pid, sid, onDone}: {pid: string; sid: string; onDone: () => void}) {
  const [template, setTemplate] = useState<Template>('intro'),
    [aspect, setAspect] = useState<'16:9' | '9:16'>('16:9'),
    [values, setValues] = useState<Record<string, string>>({}),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState(''),
    [error, setError] = useState('');
  const render = async () => {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const fields = FIELDS[template].map(f => f.id);
      const body = {template, aspect, values: Object.fromEntries(fields.map(id => [id, values[id] || '']))};
      const result = await responseJson(
        await apiFetch(`/api/productions/${pid}/series/${sid}/motion`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(body),
        })
      );
      setMessage(`Готово: ${result.filename} — лежит в папке «03 Монтаж».`);
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="connection-card" aria-label="Моушн для монтажа">
      <h4>Моушн для CapCut</h4>
      <p className="muted">
        Бесплатно, рендер на этом компьютере (1–3 мин). Заставка — MP4, плашка с именем — MOV с прозрачным
        фоном, кладётся поверх клипа.
      </p>
      <div className="chips" role="group" aria-label="Что рендерить">
        <button className={template === 'intro' ? 'active' : ''} onClick={() => setTemplate('intro')}>
          Заставка серии
        </button>
        <button
          className={template === 'lower-third' ? 'active' : ''}
          onClick={() => setTemplate('lower-third')}
        >
          Плашка с именем
        </button>
      </div>
      <div className="chips" role="group" aria-label="Формат">
        {(['16:9', '9:16'] as const).map(a => (
          <button key={a} className={aspect === a ? 'active' : ''} onClick={() => setAspect(a)}>
            {a}
          </button>
        ))}
      </div>
      {FIELDS[template].map(f => (
        <label key={f.id}>
          {f.label}
          <input
            value={values[f.id] || ''}
            maxLength={80}
            placeholder={f.placeholder}
            onChange={e => setValues(v => ({...v, [f.id]: e.target.value}))}
          />
        </label>
      ))}
      <button className="primary" disabled={busy} onClick={() => void render()}>
        {busy ? 'Рендерю…' : 'Сделать клип'}
      </button>
      {message && <p role="status">{message}</p>}
      {error && (
        <p role="alert" className="vp-err">
          {error}
        </p>
      )}
    </section>
  );
}
