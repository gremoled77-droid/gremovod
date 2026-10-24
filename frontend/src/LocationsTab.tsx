import {useCallback, useEffect, useRef, useState} from 'react';
import type {WorldFields} from './characterPrompt';
import {
  attachToLocation,
  createLocation,
  findProduction,
  loadLocations,
  saveLocationNotes,
  uploadToLocation,
  type LocationCard,
} from './locations';
import SheetPanel from './SheetPanel';
import CreateEntityDialog from './CreateEntityDialog';
import {usePortraits} from './usePortraits';
import {FavButton, TileToolbar, useTileOrder} from './TileOrder';
import {LOCATION_DEFAULT, LOCATION_SHOTS, locationShotPrompt} from './sheetShots';

const DEFAULT_MODEL = 'seedream-5-pro';

/** Локации проекта: сетка, «Создать локацию», описание, загрузка основы и пакет вариаций ракурсов. */
export default function LocationsTab({
  projectId,
  ensureProject,
  world,
  revision,
  onLibrary,
}: {
  projectId: string;
  ensureProject: () => Promise<string>;
  world?: WorldFields;
  revision: number;
  onLibrary: () => void;
}) {
  const [pid, setPid] = useState<string | null>(null),
    [items, setItems] = useState<LocationCard[]>([]),
    [selected, setSelected] = useState(''),
    [creating, setCreating] = useState(false),
    [notes, setNotes] = useState(''),
    [error, setError] = useState(''),
    [note, setNote] = useState(''),
    [busy, setBusy] = useState(false),
    file = useRef<HTMLInputElement>(null);
  const reload = useCallback(async (production: string) => {
    setItems(await loadLocations(production));
  }, []);
  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const production = projectId ? await findProduction(projectId) : '';
        if (!active) return;
        setPid(production || '');
        if (production) await reload(production);
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      active = false;
    };
  }, [projectId, reload]);
  const portraits = usePortraits(
    projectId,
    revision,
    'location',
    items.map(l => l.title)
  );
  const order = useTileOrder(projectId + ':locations', items, l => l.title);
  const current = items.find(i => i.id === selected) || null;
  useEffect(() => {
    setNotes(current?.notes || '');
  }, [current?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError('');
    setNote('');
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  const baseAssets = (current?.files || []).flatMap(f => (f.asset_id ? [f.asset_id] : []));
  if (pid === null) return <section className="panel">Загружаю локации…</section>;
  if (!pid)
    return (
      <section className="panel" role="status">
        <h2>Локации</h2>
        <p className="muted">
          У проекта нет общего проекта. Создай его в «Раскадровке», тогда здесь появятся общие локации.
        </p>
        {error && <p role="alert">{error}</p>}
      </section>
    );
  return (
    <section className="chars">
      <div className="panel">
        <h2>Локации</h2>
        <p className="muted">
          Места действия проекта. Основа и вариации ракурсов используются в составе кадра.
        </p>
        <TileToolbar
          sort={order.sort}
          onSort={order.setSort}
          onlyFav={order.onlyFav}
          onOnlyFav={order.setOnlyFav}
        />
        <div className="chars-grid">
          <button className="chars-tile chars-new" onClick={() => setCreating(true)}>
            <span>＋</span>
            <b>Создать локацию</b>
          </button>
          {order.sorted.map(l => (
            <div key={l.id} className="chars-cell">
              <button
                className={'chars-tile' + (l.id === selected ? ' on' : '')}
                aria-pressed={l.id === selected}
                onClick={() => setSelected(l.id)}
              >
                {l.files[0] ? (
                  <img src={`/api/production-files/${l.files[0].id}`} alt="" loading="lazy" />
                ) : portraits[l.title] ? (
                  <img src={`/api/library/${portraits[l.title]}/thumbnail`} alt="" loading="lazy" />
                ) : (
                  <span className="chars-empty">нет картинки</span>
                )}
                <b>{l.title}</b>
                <small>
                  ракурсов: {l.files.length}
                  {order.uses[l.id] ? ` · выбрана: ${order.uses[l.id]}` : ''}
                </small>
              </button>
              <FavButton on={order.favs.includes(l.id)} onToggle={() => order.toggleFav(l.id)} />
            </div>
          ))}
        </div>
        {error && <p role="alert">{error}</p>}
        {note && <p className="muted">{note}</p>}
      </div>
      {current && (
        <>
          <div className="panel">
            <h3>{current.title}</h3>
            <label>
              Описание места
              <textarea
                rows={3}
                value={notes}
                onChange={e => setNotes(e.target.value)}
                onBlur={() =>
                  notes !== current.notes &&
                  void run(async () => {
                    await saveLocationNotes(pid, current.id, notes);
                    await reload(pid);
                    setNote('Описание сохранено.');
                  })
                }
              />
            </label>
            <div className="chips">
              <button disabled={busy} onClick={() => file.current?.click()}>
                Загрузить основу
              </button>
              <input
                ref={file}
                type="file"
                accept="image/png,image/jpeg,image/webp"
                hidden
                onChange={e => {
                  const f = e.target.files?.[0];
                  e.target.value = '';
                  if (f)
                    void run(async () => {
                      await uploadToLocation(pid, current.id, f);
                      await reload(pid);
                      onLibrary();
                      setNote('Основа загружена в папку локации.');
                    });
                }}
              />
            </div>
            {current.files.length > 0 && (
              <div className="sheet-results" aria-label="Картинки локации">
                {current.files.map(f => (
                  <div key={f.id} className="sheet-tile">
                    <img src={`/api/production-files/${f.id}`} alt={f.filename} loading="lazy" />
                  </div>
                ))}
              </div>
            )}
          </div>
          <SheetPanel
            key={current.id}
            kind="location"
            name={current.title}
            title="Вариации ракурсов"
            shots={LOCATION_SHOTS}
            defaults={LOCATION_DEFAULT}
            aspect="16:9"
            defaultModel={DEFAULT_MODEL}
            projectId={projectId}
            ensureProject={ensureProject}
            referenceAssetIds={baseAssets}
            buildPrompt={shot => locationShotPrompt(current.title, current.notes, world, shot)}
            revision={revision}
            actions={(selectedIds, done) => (
              <button
                disabled={!selectedIds.length || busy}
                onClick={() =>
                  void run(async () => {
                    await attachToLocation(pid, current.id, selectedIds);
                    await reload(pid);
                    setNote(`В папку локации добавлено: ${selectedIds.length}.`);
                    done();
                  })
                }
              >
                В папку локации ({selectedIds.length})
              </button>
            )}
          />
        </>
      )}
      {creating && (
        <CreateEntityDialog
          title="Создать локацию"
          namePlaceholder="Например: Двор на Немиге"
          aspect="16:9"
          projectId={projectId}
          ensureProject={ensureProject}
          buildPrompt={name => locationShotPrompt(name, '', world, LOCATION_SHOTS[0])}
          create={async name => {
            const node = await createLocation(pid, name);
            await reload(pid);
            setSelected(node.id);
          }}
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
