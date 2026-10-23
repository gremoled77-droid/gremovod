import {useEffect, useMemo, useState} from 'react';
import {apiFetch} from './api';
import BatchReview, {type BatchItem} from './BatchReview';
import {responseJson} from './ChatGPTPanel';
import {
  ACTIONS,
  AMPLITUDES,
  buildMotionPrompt,
  CAMERA_MOVES,
  EMPTY_MOTION,
  LIGHT_SHIFT,
  overload,
  SCENERY,
  SPEEDS,
  withFramePrefix,
  type Motion,
} from './motionPrompt';
import {Chips} from './OperatorLayers';

type Media = {id: string; asset_id: string | null; kind: string};
type VideoFrame = {
  id: string;
  title: string;
  project_id: string | null;
  files: Media[];
  selection: {selected_image_file_id: string | null};
};
type Spec = {
  kind: string;
  launch_enabled?: boolean;
  resolution?: string[];
  aspect_ratio?: string[];
  duration_min?: number;
  duration_max?: number;
  options?: Record<
    string,
    {values?: (string | number)[]; min?: number; max?: number; default?: string | number}
  >;
};
const DEFAULT_MODEL = 'seedance-2.5';
const thumb = (id: string) => `/api/library/${id}/thumbnail`;

/** Параметры видеомодели из spec.options или из плоских полей старых спецификаций. */
function params(spec?: Spec) {
  const o = spec?.options;
  return {
    resolutions: (o?.resolution?.values as string[] | undefined) || spec?.resolution || [],
    aspects: (o?.aspect_ratio?.values as string[] | undefined) || spec?.aspect_ratio || [],
    min: o?.duration?.min ?? spec?.duration_min ?? 4,
    max: o?.duration?.max ?? spec?.duration_max ?? 15,
  };
}

/** «Оживить»: формула промпта анимации, минимальное движение, no morphing, число дублей и подтверждение пакета. */
export default function AnimateDialog({
  pid,
  frame,
  heroes,
  onClose,
  onLaunched,
}: {
  pid: string;
  frame: VideoFrame;
  heroes: {name: string; look?: string}[];
  onClose: () => void;
  onLaunched: () => void;
}) {
  const [specs, setSpecs] = useState<Record<string, Spec>>({}),
    [model, setModel] = useState(DEFAULT_MODEL),
    [motion, setMotion] = useState<Motion>(EMPTY_MOTION),
    [prompt, setPrompt] = useState(''),
    [edited, setEdited] = useState(false),
    [resolution, setResolution] = useState('480p'),
    [aspect, setAspect] = useState('16:9'),
    [duration, setDuration] = useState(5),
    [takes, setTakes] = useState(1),
    [seed, setSeed] = useState(''),
    [batch, setBatch] = useState<BatchItem[] | null>(null),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  const mainFile = frame.files.find(f => f.id === frame.selection.selected_image_file_id);
  useEffect(() => {
    let active = true;
    void apiFetch('/api/model-specs')
      .then(responseJson)
      .then(s => active && setSpecs(s))
      .catch(e => active && setError(String(e)));
    return () => {
      active = false;
    };
  }, []);
  const models = useMemo(
    () => Object.entries(specs).filter(([, s]) => s.kind === 'video' && s.launch_enabled),
    [specs]
  );
  const spec = specs[model];
  const p = params(spec);
  useEffect(() => {
    if (models.length && !models.some(([id]) => id === model)) setModel(models[0][0]);
  }, [models, model]);
  useEffect(() => {
    if (p.resolutions.length && !p.resolutions.includes(resolution)) setResolution(p.resolutions[0]);
    if (p.aspects.length && !p.aspects.includes(aspect)) setAspect(p.aspects[0]);
    setDuration(d => Math.min(p.max, Math.max(p.min, d)));
  }, [model, specs]); // eslint-disable-line react-hooks/exhaustive-deps
  const auto = useMemo(() => buildMotionPrompt(motion, {heroes}), [motion, heroes]);
  useEffect(() => {
    if (!edited) setPrompt(auto);
  }, [auto, edited]);
  const hasSeed = !!spec?.options?.seed;
  const warn = overload(motion);
  const set = <K extends keyof Motion>(key: K, value: Motion[K]) => setMotion(m => ({...m, [key]: value}));
  const start = async () => {
    setError('');
    if (!mainFile?.asset_id) return setError('Сначала утверди главное фото кадра');
    if (!prompt.trim()) return setError('Промпт пустой');
    setBusy(true);
    try {
      // Рабочий проект кадра нужен серверу, чтобы проверить, что первым референсом идёт главное фото этого кадра.
      let project = frame.project_id;
      if (!project)
        project = (
          await responseJson(
            await apiFetch(`/api/productions/${pid}/nodes/${frame.id}/open-project`, {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: '{}',
            })
          )
        ).project_id as string;
      const url = (
        await responseJson(
          await apiFetch(`/api/library/${mainFile.asset_id}/upload-reference`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({approved: true, provider: 'tempfile'}),
          })
        )
      ).url as string;
      const options: Record<string, string | number> = {duration};
      if (p.resolutions.length) options.resolution = resolution;
      if (p.aspects.length) options.aspect_ratio = aspect;
      const finalPrompt = withFramePrefix(model, prompt);
      setBatch(
        Array.from({length: takes}, (_, i) => ({
          label: `${frame.title} · ${model} · дубль ${i + 1}`,
          request: {
            project_id: project!,
            model_id: model,
            prompt: finalPrompt,
            // Один seed на все дубли дал бы одинаковые ролики: каждому следующему добавляется единица.
            options: hasSeed && seed.trim() !== '' ? {...options, seed: Number(seed) + i} : options,
            reference_urls: [url],
            node_id: frame.id,
          },
        }))
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Оживить кадр">
      <section className="panel an">
        <h3>Оживить · {frame.title}</h3>
        {mainFile?.asset_id ? (
          <img className="an-photo" src={thumb(mainFile.asset_id)} alt="Главное фото кадра" />
        ) : (
          <p role="alert">У кадра нет утверждённого главного фото.</p>
        )}
        <Chips
          label="Камера"
          options={CAMERA_MOVES}
          value={motion.camera}
          onChange={v => set('camera', (v as string) || 'static')}
        />
        {motion.camera !== 'static' && (
          <>
            <Chips
              label="Скорость"
              options={SPEEDS}
              value={motion.speed}
              onChange={v => set('speed', (v as string) || 'slow')}
            />
            <Chips
              label="Амплитуда"
              options={AMPLITUDES}
              value={motion.amplitude}
              onChange={v => set('amplitude', (v as string) || 'small')}
            />
          </>
        )}
        <Chips
          label="Герой"
          options={ACTIONS}
          multi
          value={motion.action}
          onChange={v => set('action', v as string[])}
        />
        <input
          value={motion.actionNote}
          aria-label="Своё действие героя"
          placeholder="Своё микродвижение, например: slight smile"
          onChange={e => set('actionNote', e.target.value)}
        />
        <Chips
          label="Среда"
          options={SCENERY}
          multi
          value={motion.scenery}
          onChange={v => set('scenery', v as string[])}
        />
        <Chips
          label="Свет"
          options={LIGHT_SHIFT}
          multi
          value={motion.light}
          onChange={v => set('light', v as string[])}
        />
        <div className="an-flags">
          <label>
            <input
              type="checkbox"
              checked={motion.minimal}
              onChange={e => set('minimal', e.target.checked)}
            />
            Минимальное движение
          </label>
          <label>
            <input
              type="checkbox"
              checked={motion.noMorph}
              onChange={e => set('noMorph', e.target.checked)}
            />
            Держать внешность (no morphing)
          </label>
        </div>
        {warn.warn && (
          <div className="an-warn" role="status">
            <b>Слишком много для одного шота.</b> Нейросеть лучше держит состояния и микродвижения. Разбей на
            несколько кадров.
            <ul>
              {warn.reasons.map(r => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </div>
        )}
        <label>
          Итоговый промпт
          <textarea
            rows={5}
            value={prompt}
            onChange={e => {
              setPrompt(e.target.value);
              setEdited(true);
            }}
          />
        </label>
        <div className="an-row">
          <label>
            Модель
            <select value={model} onChange={e => setModel(e.target.value)}>
              {(models.length ? models.map(([id]) => id) : [DEFAULT_MODEL]).map(id => (
                <option key={id} value={id}>
                  {id}
                  {id === DEFAULT_MODEL ? ' (по умолчанию)' : ''}
                </option>
              ))}
            </select>
          </label>
          {p.resolutions.length > 0 && (
            <label>
              Разрешение
              <select value={resolution} onChange={e => setResolution(e.target.value)}>
                {p.resolutions.map(r => (
                  <option key={r}>{r}</option>
                ))}
              </select>
            </label>
          )}
          {p.aspects.length > 0 && (
            <label>
              Формат
              <select value={aspect} onChange={e => setAspect(e.target.value)}>
                {p.aspects.map(r => (
                  <option key={r}>{r}</option>
                ))}
              </select>
            </label>
          )}
          <label>
            Секунд
            <input
              type="number"
              min={p.min}
              max={p.max}
              value={duration}
              onChange={e => setDuration(Math.min(p.max, Math.max(p.min, Number(e.target.value) || p.min)))}
            />
          </label>
          {hasSeed && (
            <label>
              Seed (необязательно)
              <input
                type="number"
                min={0}
                value={seed}
                placeholder="случайный"
                onChange={e => setSeed(e.target.value)}
              />
            </label>
          )}
          <label>
            Дублей
            <select value={takes} onChange={e => setTakes(Number(e.target.value))}>
              {[1, 2, 3].map(n => (
                <option key={n}>{n}</option>
              ))}
            </select>
          </label>
        </div>
        <p className="muted">
          Главное фото уходит моделью как стартовый кадр: его копия загружается во временное хранилище по
          ссылке. Запуск только после оценки цены и подтверждения. Каждый дубль это отдельная платная
          генерация.
        </p>
        {error && <p role="alert">{error}</p>}
        <div className="chips">
          <button className="primary" disabled={busy || !mainFile?.asset_id} onClick={() => void start()}>
            {busy ? 'Готовлю…' : `Дальше: оценка и подтверждение (${takes})`}
          </button>
          <button
            disabled={!edited}
            onClick={() => {
              setEdited(false);
              setPrompt(auto);
            }}
          >
            Собрать промпт заново
          </button>
          <button onClick={onClose}>Закрыть</button>
        </div>
        {batch && (
          <BatchReview
            items={batch}
            onClose={() => setBatch(null)}
            onSubmitted={() => {
              setBatch(null);
              onLaunched();
            }}
          />
        )}
      </section>
    </div>
  );
}
