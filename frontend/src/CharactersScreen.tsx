import {useState, type ReactNode} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
import {
  buildCharacterPrompt,
  heroShotPrompt,
  worldFilled,
  type Identity,
  type WorldFields,
} from './characterPrompt';
import LocationsTab from './LocationsTab';
import SheetPanel from './SheetPanel';
import {HERO_DEFAULT, HERO_SHOTS} from './sheetShots';
import CreateEntityDialog from './CreateEntityDialog';
import {usePortraits} from './usePortraits';
import {FavButton, TileToolbar, useTileOrder} from './TileOrder';

type Hero = {
  id: string;
  name: string;
  identity: Identity;
  working_asset_id?: string;
  version_history?: string[];
};
const DEFAULT_MODEL = 'seedream-5-pro';

/** «Персонажи»: сетка героев проекта, «Создать нового» и «Сгенерировать героя» через оценку цены. Правка карточки — справа, в Character Vault. */
export default function CharactersScreen({
  projectId,
  ensureProject,
  heroes,
  selectedId,
  world,
  onSelect,
  onCreate,
  onToWorld,
  onNext,
  onLibrary,
  results,
  revision,
}: {
  projectId: string;
  ensureProject: () => Promise<string>;
  heroes: Hero[];
  selectedId: string;
  world?: WorldFields;
  onSelect: (id: string) => void;
  onCreate: (name: string) => void;
  onToWorld: () => void;
  onNext: () => void;
  onLibrary: () => void;
  results: ReactNode;
  revision: number;
}) {
  const hero = heroes.find(h => h.id === selectedId);
  const [error, setError] = useState(''),
    [note, setNote] = useState(''),
    [creating, setCreating] = useState(false),
    [tab, setTab] = useState<'heroes' | 'locations'>('heroes');
  const portraits = usePortraits(
    projectId,
    revision,
    'hero',
    heroes.map(h => h.name)
  );
  const order = useTileOrder(projectId + ':heroes', heroes, h => h.name);
  const tabs = (
    <div className="chips" role="tablist" aria-label="Раздел">
      {(
        [
          ['heroes', 'Герои'],
          ['locations', 'Локации'],
        ] as const
      ).map(([id, label]) => (
        <button
          key={id}
          role="tab"
          aria-selected={tab === id}
          className={tab === id ? 'primary' : ''}
          onClick={() => setTab(id)}
        >
          {label}
        </button>
      ))}
    </div>
  );
  if (tab === 'locations')
    return (
      <section className="chars">
        {tabs}
        <LocationsTab
          projectId={projectId}
          ensureProject={ensureProject}
          world={world}
          revision={revision}
          onLibrary={onLibrary}
        />
      </section>
    );
  return (
    <section className="chars">
      {tabs}
      <div className="panel">
        <p className="muted">
          Герои проекта. Описание, референсы, голос и версии правятся справа, в Character Vault.
        </p>
        {!worldFilled(world) && (
          <p role="status" className="muted">
            «Мир» пока пуст: стиль попадёт в промпт героя. <button onClick={onToWorld}>Заполнить мир</button>
          </p>
        )}
        {error && <p role="alert">{error}</p>}
        {note && <p className="muted">{note}</p>}
        <div className="chars-actions">
          <button onClick={onNext}>Дальше: раскадровка →</button>
        </div>
        <TileToolbar
          sort={order.sort}
          onSort={order.setSort}
          onlyFav={order.onlyFav}
          onOnlyFav={order.setOnlyFav}
        />
        <div className="chars-grid">
          <button className="chars-tile chars-new" onClick={() => setCreating(true)}>
            <span>＋</span>
            <b>Создать нового</b>
          </button>
          {order.sorted.map(h => (
            <div key={h.id} className="chars-cell">
              <button
                className={'chars-tile' + (h.id === selectedId ? ' on' : '')}
                aria-pressed={h.id === selectedId}
                onClick={() => onSelect(h.id)}
              >
                {h.working_asset_id || portraits[h.name] ? (
                  <img
                    src={`/api/library/${h.working_asset_id || portraits[h.name]}/thumbnail`}
                    alt=""
                    loading="lazy"
                  />
                ) : (
                  <span className="chars-empty">нет образа</span>
                )}
                <b>{h.name}</b>
                <small>
                  {order.uses[h.id] ? `выбран: ${order.uses[h.id]}` : ''}
                  {h.version_history?.length ? ` версий: ${h.version_history.length + 1}` : ''}
                </small>
              </button>
              <FavButton on={order.favs.includes(h.id)} onToggle={() => order.toggleFav(h.id)} />
            </div>
          ))}
        </div>
      </div>
      {hero && (
        <SheetPanel
          key={hero.id}
          kind="hero"
          name={hero.name}
          title="Лист героя"
          shots={HERO_SHOTS}
          defaults={HERO_DEFAULT}
          aspect="3:4"
          defaultModel={DEFAULT_MODEL}
          projectId={projectId}
          ensureProject={ensureProject}
          referenceAssetIds={hero.working_asset_id ? [hero.working_asset_id] : []}
          buildPrompt={shot => heroShotPrompt(hero.name, hero.identity, world, shot)}
          revision={revision}
          actions={(selected, done) => (
            <>
              <button
                disabled={!selected.length}
                onClick={() =>
                  void (async () => {
                    setError('');
                    try {
                      for (const id of selected)
                        await responseJson(
                          await apiFetch(`/api/library/${id}/to-character`, {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({
                              project_id: projectId,
                              character_id: hero.id,
                              category: 'approved_generations',
                            }),
                          })
                        );
                      setNote(`В референсы героя отправлено: ${selected.length}.`);
                      done();
                    } catch (e) {
                      setError(e instanceof Error ? e.message : String(e));
                    }
                  })()
                }
              >
                В референсы героя ({selected.length})
              </button>
              <small className="muted">
                Рабочим образом делай через «Заменить персонажа» в библиотеке ниже.
              </small>
            </>
          )}
        />
      )}
      {results}
      {creating && (
        <CreateEntityDialog
          title="Создать героя"
          namePlaceholder="Например: Грэм"
          aspect="3:4"
          projectId={projectId}
          ensureProject={ensureProject}
          buildPrompt={name => buildCharacterPrompt(name, {}, world)}
          create={async name => onCreate(name)}
          onClose={() => setCreating(false)}
          onStarted={() => {
            setCreating(false);
            setNote('Задание запущено. Результат появится в очереди и в библиотеке.');
          }}
        />
      )}
    </section>
  );
}
