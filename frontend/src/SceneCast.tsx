import {toggleId} from './boardOrder';

type Entry = {id: string; kind: string; title: string};

/** Состав сцены (герои) и локация: правка прямо на доске, сохраняется сразу. */
export default function SceneCast({
  catalogue,
  characterIds,
  locationId,
  busy,
  onChange,
  onOpen,
}: {
  catalogue: Entry[];
  characterIds: string[];
  locationId: string | null;
  busy: boolean;
  onChange: (patch: {character_node_ids?: string[]; location_node_id?: string | null}) => void;
  onOpen: (id: string) => void;
}) {
  const characters = catalogue.filter(n => n.kind === 'character'),
    locations = catalogue.filter(n => n.kind === 'location'),
    title = (id: string, fallback: string) => catalogue.find(n => n.id === id)?.title || fallback;
  return (
    <div className="ps-cast">
      {characterIds.map(id => (
        <button key={id} onClick={() => onOpen(id)}>
          {title(id, 'Персонаж')} ↗
        </button>
      ))}
      {locationId && <button onClick={() => onOpen(locationId)}>{title(locationId, 'Локация')} ↗</button>}
      {!characterIds.length && !locationId && (
        <span className="ps-cast-empty">состав и локация не выбраны</span>
      )}
      <details className="ps-cast-edit">
        <summary>Изменить состав и локацию</summary>
        <fieldset disabled={busy}>
          <legend>Герои сцены</legend>
          {characters.length === 0 && <small>В проекте пока нет персонажей</small>}
          {characters.map(c => (
            <label key={c.id}>
              <input
                type="checkbox"
                checked={characterIds.includes(c.id)}
                onChange={e => onChange({character_node_ids: toggleId(characterIds, c.id, e.target.checked)})}
              />
              {c.title}
            </label>
          ))}
        </fieldset>
        <label className="ps-cast-location">
          Локация
          <select
            value={locationId || ''}
            disabled={busy}
            onChange={e => onChange({location_node_id: e.target.value || null})}
          >
            <option value="">Не выбрана</option>
            {locations.map(l => (
              <option key={l.id} value={l.id}>
                {l.title}
              </option>
            ))}
          </select>
        </label>
      </details>
    </div>
  );
}
