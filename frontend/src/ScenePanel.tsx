import {useEffect, useState} from 'react';
import {apiFetch} from './api';
import ChatGPTPanel, {responseJson} from './ChatGPTPanel';
import {
  CameraSelector,
  cameraBasis,
  cameraOutdated,
  type CameraPreset,
  type CameraSelection,
} from './CameraPanel';
import {
  FrameSelector,
  frameBasis,
  frameOutdated,
  type FrameCatalogue,
  type FrameSelection,
} from './FramePanel';
import CinemaInfo from './CinemaInfo';

export type Scene = {
  brief: string;
  assets: {asset_id: string; role: string; note: string}[];
  target: string;
  prompts: Record<string, string>;
  cameraPromptBasis?: Record<string, string>;
  compositionPromptBasis?: Record<string, string>;
};
export const EMPTY_SCENE: Scene = {brief: '', assets: [], target: 'gpt-image-2.5', prompts: {}};
type Asset = {id: string; url: string; metadata: {kind?: string; width: number; height: number}};
export default function ScenePanel({
  scene,
  onChange,
  projectId,
  revision,
  models,
  ensureProject,
  onAsset,
  onGenerate,
  cameraPresets,
  camera,
  onCamera,
  frameCatalogue,
  composition,
  onComposition,
  onFrameCatalogue,
  onCameraCatalogue,
}: {
  scene: Scene;
  onChange: (scene: Scene) => void;
  projectId: string;
  revision: number;
  models: {id: string; kind: string; enabled: boolean}[];
  ensureProject: () => Promise<string>;
  onAsset: () => void;
  onGenerate: (target: string, prompt: string) => void;
  cameraPresets: CameraPreset[];
  camera?: CameraSelection;
  onCamera: (camera: CameraSelection) => void;
  frameCatalogue: FrameCatalogue;
  composition?: FrameSelection;
  onComposition: (value: FrameSelection) => void;
  onFrameCatalogue: () => void;
  onCameraCatalogue: () => void;
}) {
  const [assets, setAssets] = useState<Asset[]>([]),
    [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setAssets([]);
    if (projectId)
      void apiFetch('/api/library?project_id=' + encodeURIComponent(projectId))
        .then(responseJson)
        .then(items => {
          if (active)
            setAssets(items.filter((x: Asset) => !['video', 'audio'].includes(x.metadata.kind || 'image')));
        })
        .catch(e => {
          if (active) setError(String(e));
        });
    return () => {
      active = false;
    };
  }, [projectId, revision]);
  const selected = new Set(scene.assets.map(x => x.asset_id));
  const model = models.find(x => x.id === scene.target);
  const ROLES: {id: string; label: string}[] = [
    {id: 'character', label: 'Герой'},
    {id: 'location', label: 'Локация'},
    {id: 'object', label: 'Предмет'},
    {id: 'style', label: 'Стиль / свет'},
    {id: 'composition', label: 'Композиция'},
  ];
  const countBy = (role: string) => scene.assets.filter(x => x.role === role).length;
  const plural = (n: number, forms: [string, string, string]) =>
    n % 10 === 1 && n % 100 !== 11
      ? forms[0]
      : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20)
        ? forms[1]
        : forms[2];
  const summary = (
    [
      ['character', ['герой', 'героя', 'героев']],
      ['location', ['локация', 'локации', 'локаций']],
      ['object', ['предмет', 'предмета', 'предметов']],
    ] as [string, [string, string, string]][]
  )
    .filter(([role]) => countBy(role) > 0)
    .map(([role, forms]) => `${countBy(role)} ${plural(countBy(role), forms)}`)
    .join(' · ');
  const setItem = (index: number, patch: Partial<Scene['assets'][number]>) =>
    onChange({...scene, assets: scene.assets.map((x, i) => (i === index ? {...x, ...patch} : x))});
  const available = assets.filter(x => !selected.has(x.id));
  const step = (n: number, title: string, hint: string, extra?: string) => (
    <div className="rf-head">
      <span className="rf-step">{n}</span>
      <div>
        <h3>{title}</h3>
        <small>{hint}</small>
      </div>
      {extra && <span className="sc-count">{extra}</span>}
    </div>
  );
  const outdated =
    (model?.kind === 'video' &&
      cameraOutdated(camera, scene.cameraPromptBasis?.[scene.target], scene.prompts[scene.target] || '')) ||
    (model?.kind === 'image' &&
      frameOutdated(
        composition,
        scene.compositionPromptBasis?.[scene.target],
        scene.prompts[scene.target] || ''
      ));
  return (
    <section className="sc">
      <div className="sc-bar">
        <p className="muted">
          Соедини героя, локацию и предметы в одном кадре. Роли исходников и инструкция сохраняются вместе с
          проектом ролика.
        </p>
        <CinemaInfo topic="mise" />
      </div>
      {error && <div className="alert">{error}</div>}
      <article className="sc-step">
        {step(1, 'Исходники кадра', 'Герои, локация и предметы, из которых собираем сцену', summary)}
        {scene.assets.length > 0 && (
          <div className="sc-cards">
            {scene.assets.map((item, index) => {
              const asset = assets.find(x => x.id === item.asset_id);
              return (
                <div className="sc-card" key={item.asset_id}>
                  <div className="sc-thumb">
                    {asset ? (
                      <img src={asset.url} alt={'Исходник ' + (index + 1)} />
                    ) : (
                      <span>нет превью</span>
                    )}
                    <button
                      className="sc-x"
                      aria-label="Убрать из сцены"
                      title="Убрать из сцены"
                      onClick={() =>
                        onChange({...scene, assets: scene.assets.filter(x => x.asset_id !== item.asset_id)})
                      }
                    >
                      ×
                    </button>
                    <span className="sc-num">{index + 1}</span>
                  </div>
                  <div className="sc-roles" role="group" aria-label="Роль исходника">
                    {ROLES.map(r => (
                      <button
                        key={r.id}
                        className={item.role === r.id ? 'on' : ''}
                        aria-pressed={item.role === r.id}
                        onClick={() => setItem(index, {role: r.id})}
                      >
                        {r.label}
                      </button>
                    ))}
                  </div>
                  <input
                    value={item.note}
                    placeholder="Что взять из изображения"
                    onChange={e => setItem(index, {note: e.target.value})}
                  />
                </div>
              );
            })}
          </div>
        )}
        <div className="sc-pick">
          <small>{scene.assets.length ? 'Добавить ещё из библиотеки' : 'Выбери из библиотеки'}</small>
          {available.length ? (
            <div className="sc-strip">
              {available.map(x => (
                <button
                  key={x.id}
                  className="sc-add"
                  title={`${x.id.slice(0, 8)} · ${x.metadata.width}×${x.metadata.height}`}
                  onClick={() =>
                    onChange({
                      ...scene,
                      assets: [
                        ...scene.assets,
                        {asset_id: x.id, role: scene.assets.length ? 'location' : 'character', note: ''},
                      ],
                    })
                  }
                >
                  <img src={x.url} alt="" loading="lazy" />
                  <span>＋</span>
                </button>
              ))}
            </div>
          ) : (
            <p className="muted">
              {assets.length
                ? 'Все картинки библиотеки уже в сцене.'
                : 'Сначала сохрани изображения в библиотеку и нажми «Отправить в сцену».'}
            </p>
          )}
        </div>
      </article>
      <article className="sc-step">
        {step(2, 'Постановка сцены', 'Кто и где, действие, камера, свет')}
        <textarea
          rows={5}
          value={scene.brief}
          onChange={e => onChange({...scene, brief: e.target.value})}
          placeholder="Кто и где находится, масштаб и расположение, действие, камера, свет. Для видео — что меняется во времени."
        />
      </article>
      <article className="sc-step">
        {step(3, 'Модель и ракурс', 'Фото или видео, ракурс, свет и камера')}
        <label>
          Целевая модель
          <select value={scene.target} onChange={e => onChange({...scene, target: e.target.value})}>
            {models.map(x => (
              <option key={x.id} value={x.id}>
                {x.kind === 'video' ? 'Видео' : 'Фото'} · {x.id}
              </option>
            ))}
          </select>
        </label>
        {model?.kind === 'video' && (
          <CameraSelector
            setupEnabled={!!frameCatalogue.capabilities?.prompt_setup}
            presets={cameraPresets}
            value={camera}
            onChange={onCamera}
            onCatalogue={onCameraCatalogue}
          />
        )}
        {model?.kind === 'image' && (
          <FrameSelector
            catalogue={frameCatalogue}
            value={composition}
            onChange={onComposition}
            onCatalogue={onFrameCatalogue}
          />
        )}
      </article>
      <article className="sc-step">
        {step(4, 'Промпт и запуск', 'GPT улучшит описание; его можно поправить руками')}
        <ChatGPTPanel
          projectId={projectId}
          target={scene.target}
          useScene
          ensureProject={ensureProject}
          onAsset={onAsset}
          onPrompt={(prompt, target, movement, frame) =>
            onChange({
              ...scene,
              prompts: {...scene.prompts, [target]: prompt},
              cameraPromptBasis: {...scene.cameraPromptBasis, [target]: cameraBasis(movement)},
              compositionPromptBasis: {...scene.compositionPromptBasis, [target]: frameBasis(frame)},
            })
          }
        />
        <label>
          Улучшенный промпт · {scene.target}
          <textarea
            rows={6}
            value={scene.prompts[scene.target] || ''}
            onChange={e => onChange({...scene, prompts: {...scene.prompts, [scene.target]: e.target.value}})}
          />
        </label>
        {model?.kind === 'video' &&
          cameraOutdated(
            camera,
            scene.cameraPromptBasis?.[scene.target],
            scene.prompts[scene.target] || ''
          ) && (
            <div className="notice" role="status">
              <p>Камера изменена. Пересобери промпт или проверь его вручную.</p>
              <button
                onClick={() =>
                  onChange({
                    ...scene,
                    cameraPromptBasis: {...scene.cameraPromptBasis, [scene.target]: cameraBasis(camera)},
                  })
                }
              >
                Камера учтена в этом промпте
              </button>
            </div>
          )}
        {model?.kind === 'image' &&
          frameOutdated(
            composition,
            scene.compositionPromptBasis?.[scene.target],
            scene.prompts[scene.target] || ''
          ) && (
            <div className="notice" role="status">
              <p>Ракурс или свет изменены. Подготовь новый фотопромпт либо проверь его вручную.</p>
              <button
                onClick={() =>
                  onChange({
                    ...scene,
                    compositionPromptBasis: {
                      ...scene.compositionPromptBasis,
                      [scene.target]: frameBasis(composition),
                    },
                  })
                }
              >
                Ракурс и свет учтены в промпте
              </button>
            </div>
          )}
        {!scene.target.startsWith('gpt-image-') && (
          <>
            <button
              className="primary"
              disabled={!scene.prompts[scene.target]?.trim() || !model?.enabled || !!outdated}
              onClick={() => onGenerate(scene.target, scene.prompts[scene.target])}
            >
              Проверить стоимость и создать {model?.kind === 'video' ? 'видео' : 'фото'} через API
            </button>
            {!model?.enabled && (
              <p className="muted">Промпт доступен; запуск провайдера этой модели пока не подключён.</p>
            )}
          </>
        )}
      </article>
    </section>
  );
}
