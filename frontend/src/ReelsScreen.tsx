import {useEffect, useMemo, useState} from 'react';
import {apiFetch} from './api';
import {
  KIND_LABEL,
  defaultValues,
  filterRecipes,
  fillPrompt,
  money,
  type Look,
  type Recipe,
  type RecipeStep,
} from './reelRecipes';

export type ReelUse = {prompt: string; duration: number; aspect_ratio: string; resolution: string};

const EMPTY_FORM = {
  title: '',
  family: 'Свои',
  hook: '',
  duration: 10,
  aspect_ratio: '9:16',
  resolution: '720p',
  audio: false,
  prompt: '',
  notes: '',
  slots: '',
  based_on: '',
};
type Form = typeof EMPTY_FORM;

function RecipeDetail({
  recipe,
  looks,
  onClose,
  onUse,
  onCopy,
  onRemove,
}: {
  recipe: Recipe;
  looks: Record<string, Look>;
  onClose: () => void;
  onUse: (u: ReelUse) => void;
  onCopy: (form: Form) => void;
  onRemove: (id: string) => void;
}) {
  const [values, setValues] = useState(() => defaultValues(recipe));
  const [edited, setEdited] = useState<Record<number, string>>({});
  const [copied, setCopied] = useState(-1);
  const text = (step: RecipeStep, i: number) => edited[i] ?? fillPrompt(step.prompt, values, looks);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  const copy = async (i: number, value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(i);
      window.setTimeout(() => setCopied(c => (c === i ? -1 : c)), 1600);
    } catch {
      setCopied(-2);
    }
  };
  const asForm = (): Form => {
    const video = recipe.steps.findIndex(s => s.kind === 'video');
    const step = recipe.steps[video];
    return {
      ...EMPTY_FORM,
      title: recipe.title + ' (моя версия)',
      hook: recipe.hook,
      duration: step?.duration ?? recipe.duration,
      aspect_ratio: recipe.aspect_ratio,
      resolution: recipe.resolution,
      audio: recipe.audio,
      prompt: step ? text(step, video) : '',
      notes: recipe.pitfalls.join('\n'),
      slots: recipe.ref_slots.map(s => (s.note ? `${s.role} — ${s.note}` : s.role)).join('\n'),
      based_on: recipe.id,
    };
  };
  const hasEdits = Object.keys(edited).length > 0;
  return (
    <div className="reels-backdrop" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="reels-detail" role="dialog" aria-modal="true" aria-label={recipe.title}>
        <header className="reels-detail-head">
          <div>
            <small>
              {recipe.emoji} {recipe.family} · {KIND_LABEL[recipe.kind] || recipe.kind}
            </small>
            <h2>{recipe.title}</h2>
            <p>{recipe.hook}</p>
          </div>
          <button onClick={onClose} aria-label="Закрыть">
            ✕
          </button>
        </header>
        <div className="reels-detail-body">
          <section>
            <h3>Цена одной попытки</h3>
            <div className="reels-prices">
              {Object.entries(recipe.estimate_usd).map(([res, usd]) => (
                <span key={res} className={res === recipe.resolution ? 'on' : ''}>
                  {res} <b>{money(usd)}</b>
                </span>
              ))}
            </div>
            <p className="muted">
              {recipe.duration} с · {recipe.aspect_ratio} ·{' '}
              {recipe.audio ? 'нужен звук' : 'звук не обязателен'}. Рецепт ещё не запускался вживую: сначала
              проверь идею на 480p, финал делай на {recipe.resolution}. Запуск всегда идёт через оценку цены и
              подтверждение.
            </p>
          </section>

          {(recipe.fields.length > 0 || recipe.looks.length > 1) && (
            <section>
              <h3>Что подставить</h3>
              <div className="reels-fields">
                {recipe.looks.length > 0 && (
                  <label>
                    Стиль изображения
                    <select
                      value={values.look}
                      onChange={e => setValues(v => ({...v, look: e.target.value}))}
                    >
                      {recipe.looks.map(k => (
                        <option key={k} value={k}>
                          {looks[k]?.label || k}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                {recipe.fields.map(f => (
                  <label key={f.key}>
                    {f.label}
                    <input
                      value={values[f.key] ?? ''}
                      placeholder={f.hint}
                      onChange={e => setValues(v => ({...v, [f.key]: e.target.value}))}
                    />
                  </label>
                ))}
              </div>
              {hasEdits && (
                <p className="muted">
                  Текст промпта правили вручную, поля формы на него уже не влияют.{' '}
                  <button type="button" className="link" onClick={() => setEdited({})}>
                    Сбросить правки
                  </button>
                </p>
              )}
            </section>
          )}

          {recipe.ref_slots.length > 0 && (
            <section>
              <h3>Референсы по слотам</h3>
              <ol className="reels-slots">
                {recipe.ref_slots.map(s => (
                  <li key={s.n}>
                    <b>@Image{s.n}</b> {s.role}
                    {!s.required && <em> · по желанию</em>}
                    {s.note && <small>{s.note}</small>}
                  </li>
                ))}
              </ol>
            </section>
          )}

          {recipe.beats.length > 0 && (
            <section>
              <h3>Раскадровка по битам</h3>
              <ol className="reels-beats">
                {recipe.beats.map((b, i) => (
                  <li key={i}>
                    <b>{b.t}</b>
                    <span>{b.text}</span>
                  </li>
                ))}
              </ol>
            </section>
          )}

          <section>
            <h3>Промпты</h3>
            {recipe.steps.map((step, i) => {
              const value = text(step, i);
              return (
                <div className="reels-step" key={i}>
                  <div className="reels-step-head">
                    <b>{step.title}</b>
                    <small>
                      {step.model}
                      {step.duration ? ` · ${step.duration} с` : ''}
                      {step.aspect_ratio ? ` · ${step.aspect_ratio}` : ''}
                    </small>
                  </div>
                  <textarea
                    rows={Math.min(18, Math.max(6, value.split('\n').length + 1))}
                    value={value}
                    onChange={e => setEdited(x => ({...x, [i]: e.target.value}))}
                    aria-label={step.title}
                  />
                  <div className="reels-step-actions">
                    <button onClick={() => void copy(i, value)}>
                      {copied === i ? 'Скопировано' : copied === -2 ? 'Не вышло скопировать' : 'Скопировать'}
                    </button>
                    {step.kind === 'video' && (
                      <button
                        className="primary"
                        onClick={() =>
                          onUse({
                            prompt: value,
                            duration: step.duration ?? recipe.duration,
                            aspect_ratio: recipe.aspect_ratio,
                            resolution: recipe.resolution,
                          })
                        }
                      >
                        Взять в «Видео»
                      </button>
                    )}
                    {step.kind === 'image' && (
                      <small className="muted">вставь в «Кадры» и сгенерируй картинку</small>
                    )}
                  </div>
                </div>
              );
            })}
          </section>

          {recipe.why.length > 0 && (
            <section>
              <h3>На чём держится</h3>
              <ul>
                {recipe.why.map((t, i) => (
                  <li key={i}>{t}</li>
                ))}
              </ul>
            </section>
          )}
          {recipe.pitfalls.length > 0 && (
            <section>
              <h3>Грабли</h3>
              <ul>
                {recipe.pitfalls.map((t, i) => (
                  <li key={i}>{t}</li>
                ))}
              </ul>
            </section>
          )}
          <footer className="reels-detail-foot">
            <small className="muted">{recipe.source}</small>
            <span>
              <button onClick={() => onCopy(asForm())}>Сохранить как свой рецепт</button>
              {!recipe.builtin && (
                <button onClick={() => onRemove(recipe.id)} className="danger">
                  Убрать из меню
                </button>
              )}
            </span>
          </footer>
        </div>
      </div>
    </div>
  );
}

function CreateForm({
  initial,
  busy,
  error,
  onSave,
  onClose,
}: {
  initial: Form;
  busy: boolean;
  error: string;
  onSave: (f: Form) => void;
  onClose: () => void;
}) {
  const [f, setF] = useState(initial);
  const set = <K extends keyof Form>(k: K, v: Form[K]) => setF(x => ({...x, [k]: v}));
  return (
    <div className="reels-backdrop" onClick={e => e.target === e.currentTarget && onClose()}>
      <form
        className="reels-detail reels-form"
        role="dialog"
        aria-modal="true"
        aria-label="Свой рецепт"
        onSubmit={e => {
          e.preventDefault();
          onSave(f);
        }}
      >
        <header className="reels-detail-head">
          <div>
            <small>СВОЙ РЕЦЕПТ</small>
            <h2>Новый сценарий для рилса</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Закрыть">
            ✕
          </button>
        </header>
        <div className="reels-detail-body">
          <label>
            Название
            <input required maxLength={80} value={f.title} onChange={e => set('title', e.target.value)} />
          </label>
          <label>
            Рубрика
            <input maxLength={40} value={f.family} onChange={e => set('family', e.target.value)} />
          </label>
          <label>
            Одной фразой: про что ролик
            <textarea rows={2} maxLength={500} value={f.hook} onChange={e => set('hook', e.target.value)} />
          </label>
          <div className="reels-fields">
            <label>
              Длительность, с
              <input
                type="number"
                min={4}
                max={30}
                value={f.duration}
                onChange={e => set('duration', Number(e.target.value))}
              />
            </label>
            <label>
              Формат
              <select value={f.aspect_ratio} onChange={e => set('aspect_ratio', e.target.value)}>
                {['9:16', '16:9', '1:1', '4:3', '3:4', '21:9'].map(v => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
            <label>
              Разрешение
              <select value={f.resolution} onChange={e => set('resolution', e.target.value)}>
                {['480p', '720p', '1080p'].map(v => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
          </div>
          <label>
            Промпт для Seedance 2.5
            <textarea
              required
              rows={12}
              maxLength={8000}
              value={f.prompt}
              onChange={e => set('prompt', e.target.value)}
            />
          </label>
          <label>
            Референсы по слотам (по строке на слот: «роль — заметка»)
            <textarea rows={4} value={f.slots} onChange={e => set('slots', e.target.value)} />
          </label>
          <label>
            Грабли и заметки (по строке)
            <textarea
              rows={3}
              maxLength={2000}
              value={f.notes}
              onChange={e => set('notes', e.target.value)}
            />
          </label>
          <label className="reels-check">
            <input type="checkbox" checked={f.audio} onChange={e => set('audio', e.target.checked)} />
            Ролику нужен звук или речь
          </label>
          {error && (
            <p role="alert" className="reels-error">
              {error}
            </p>
          )}
          <div className="reels-step-actions">
            <button className="primary" type="submit" disabled={busy}>
              Сохранить рецепт
            </button>
            <button type="button" onClick={onClose}>
              Отмена
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}

export default function ReelsScreen({onUse}: {onUse: (u: ReelUse) => void}) {
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [looks, setLooks] = useState<Record<string, Look>>({});
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [family, setFamily] = useState('all');
  const [query, setQuery] = useState('');
  const [openId, setOpenId] = useState('');
  const [form, setForm] = useState<Form | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = async () => {
    try {
      const r = await apiFetch('/api/reel-recipes');
      if (!r.ok) throw new Error();
      const data = await r.json();
      setRecipes(data.recipes);
      setLooks(data.looks);
      setState('ready');
    } catch {
      setState('error');
    }
  };
  useEffect(() => {
    void load();
  }, []);

  const families = useMemo(() => ['all', ...Array.from(new Set(recipes.map(r => r.family)))], [recipes]);
  const shown = filterRecipes(recipes, family, query);
  const open = recipes.find(r => r.id === openId);

  const save = async (f: Form) => {
    setBusy(true);
    setError('');
    try {
      const r = await apiFetch('/api/reel-recipes', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          title: f.title,
          family: f.family,
          hook: f.hook,
          duration: f.duration,
          aspect_ratio: f.aspect_ratio,
          resolution: f.resolution,
          audio: f.audio,
          prompt: f.prompt,
          notes: f.notes,
          based_on: f.based_on || null,
          ref_slots: f.slots
            .split('\n')
            .map(l => l.trim())
            .filter(Boolean)
            .slice(0, 30)
            .map(line => {
              const [role, ...rest] = line.split(/\s+[—-]\s+/);
              return {role: role.slice(0, 80), note: rest.join(' — ').slice(0, 300), required: false};
            }),
        }),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => null);
        throw new Error(typeof body?.detail === 'string' ? body.detail : 'Проверь поля рецепта');
      }
      const created: Recipe = await r.json();
      setForm(null);
      await load();
      setFamily('all');
      setOpenId(created.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось сохранить');
    } finally {
      setBusy(false);
    }
  };
  const remove = async (id: string) => {
    if (!window.confirm('Убрать рецепт из меню? Он уйдёт в архив базы, файлы не удаляются.')) return;
    const r = await apiFetch('/api/reel-recipes/' + encodeURIComponent(id), {method: 'DELETE'});
    if (r.ok) {
      setOpenId('');
      await load();
    }
  };

  return (
    <section className="reels">
      <header className="reels-hero">
        <div>
          <small>РЕЦЕПТЫ РИЛСОВ</small>
          <h1>Выбери сценарий для рилса</h1>
          <p>
            Готовая схема ролика на 10–30 секунд: идея, биты по таймкодам, референсы по слотам и промпт для
            Seedance 2.5. Подставь героя и место, возьми в «Видео» и проверь цену перед запуском.
          </p>
        </div>
        <button
          className="primary"
          onClick={() => {
            setError('');
            setForm(EMPTY_FORM);
          }}
        >
          ＋ Свой рецепт
        </button>
      </header>
      <div className="reels-filters">
        <div className="reels-chips" role="tablist" aria-label="Рубрики">
          {families.map(f => (
            <button
              key={f}
              role="tab"
              aria-selected={family === f}
              className={family === f ? 'on' : ''}
              onClick={() => setFamily(f)}
            >
              {f === 'all' ? 'Все' : f}
            </button>
          ))}
        </div>
        <input
          type="search"
          placeholder="Поиск по названию и идее"
          value={query}
          onChange={e => setQuery(e.target.value)}
          aria-label="Поиск рецептов"
        />
      </div>
      {state === 'loading' && <p className="muted">Загружаем рецепты…</p>}
      {state === 'error' && (
        <p role="alert">
          Не удалось загрузить рецепты. Перезапусти бэкенд и нажми{' '}
          <button onClick={() => void load()}>Повторить</button>
        </p>
      )}
      {state === 'ready' && shown.length === 0 && <p className="muted">Ничего не найдено. Сбрось фильтр.</p>}
      <div className="reels-grid">
        {shown.map(r => (
          <button className="reels-card" key={r.id} onClick={() => setOpenId(r.id)}>
            <span className="reels-card-top">
              <span className="reels-emoji" aria-hidden="true">
                {r.emoji}
              </span>
              <span className="reels-family">{r.family}</span>
            </span>
            <b>{r.title}</b>
            <span className="reels-hook">{r.hook}</span>
            <span className="reels-meta">
              <i>
                {r.duration} с · {r.aspect_ratio}
              </i>
              <i>{KIND_LABEL[r.kind] || r.kind}</i>
              {r.difficulty && <i>{r.difficulty}</i>}
              <i>
                ≈ {money(r.estimate_usd[r.resolution])} · {r.resolution}
              </i>
            </span>
          </button>
        ))}
      </div>
      {open && (
        <RecipeDetail
          key={open.id}
          recipe={open}
          looks={looks}
          onClose={() => setOpenId('')}
          onUse={u => {
            setOpenId('');
            onUse(u);
          }}
          onCopy={f => {
            setOpenId('');
            setError('');
            setForm(f);
          }}
          onRemove={id => void remove(id)}
        />
      )}
      {form && (
        <CreateForm
          initial={form}
          busy={busy}
          error={error}
          onSave={f => void save(f)}
          onClose={() => setForm(null)}
        />
      )}
    </section>
  );
}
