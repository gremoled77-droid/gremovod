import {useMemo, useState} from 'react';
import {Heart} from 'lucide-react';
import {readLocal, writeLocal} from './localDrafts';

export type TileSort = 'new' | 'alpha' | 'popular';

const usesKey = (storeKey: string) => 'studio:uses:' + storeKey;

/** Счётчик «кого выбирали»: +n за каждую отправку кадров в раскадровку с этим героем или локацией. */
export function bumpUses(storeKey: string, ids: string[], n = 1) {
  const uses = readLocal<Record<string, number>>(usesKey(storeKey), {});
  for (const id of ids) uses[id] = (uses[id] || 0) + n;
  writeLocal(usesKey(storeKey), uses);
}

/** Порядок плиток героев/локаций: новые первыми или по алфавиту, фильтр «Избранные». Избранное хранится в браузере по ключу. */
export function useTileOrder<T extends {id: string}>(storeKey: string, items: T[], nameOf: (i: T) => string) {
  const key = 'studio:favs:' + storeKey;
  const uses = readLocal<Record<string, number>>(usesKey(storeKey), {});
  const [favs, setFavs] = useState<string[]>(() => readLocal<string[]>(key, [])),
    [sort, setSort] = useState<TileSort>('new'),
    [onlyFav, setOnlyFav] = useState(false);
  const toggleFav = (id: string) =>
    setFavs(list => {
      const next = list.includes(id) ? list.filter(x => x !== id) : [...list, id];
      writeLocal(key, next);
      return next;
    });
  // Входной список идёт в порядке создания, поэтому «новые» = обратный порядок.
  const sorted = useMemo(() => {
    const base = onlyFav ? items.filter(i => favs.includes(i.id)) : items;
    const fresh = [...base].reverse();
    if (sort === 'alpha') return [...base].sort((a, b) => nameOf(a).localeCompare(nameOf(b), 'ru'));
    // sort стабилен: при равных счётчиках сохраняется порядок «новые первыми».
    return sort === 'popular' ? fresh.sort((a, b) => (uses[b.id] || 0) - (uses[a.id] || 0)) : fresh;
  }, [items, favs, sort, onlyFav]); // eslint-disable-line react-hooks/exhaustive-deps
  return {sorted, favs, uses, toggleFav, sort, setSort, onlyFav, setOnlyFav};
}

export function TileToolbar({
  sort,
  onSort,
  onlyFav,
  onOnlyFav,
}: {
  sort: TileSort;
  onSort: (s: TileSort) => void;
  onlyFav: boolean;
  onOnlyFav: (v: boolean) => void;
}) {
  return (
    <div className="chips" aria-label="Порядок и фильтр">
      <button
        className={sort === 'new' ? 'primary' : ''}
        aria-pressed={sort === 'new'}
        onClick={() => onSort('new')}
      >
        Новые
      </button>
      <button
        className={sort === 'alpha' ? 'primary' : ''}
        aria-pressed={sort === 'alpha'}
        onClick={() => onSort('alpha')}
      >
        По алфавиту
      </button>
      <button
        className={sort === 'popular' ? 'primary' : ''}
        aria-pressed={sort === 'popular'}
        onClick={() => onSort('popular')}
      >
        Частые
      </button>
      <button className={onlyFav ? 'primary' : ''} aria-pressed={onlyFav} onClick={() => onOnlyFav(!onlyFav)}>
        <Heart size={14} /> Избранные
      </button>
    </div>
  );
}

export function FavButton({on, onToggle}: {on: boolean; onToggle: () => void}) {
  return (
    <button
      type="button"
      className={'tile-fav' + (on ? ' on' : '')}
      aria-pressed={on}
      aria-label={on ? 'Убрать из избранного' : 'В избранное'}
      onClick={e => {
        e.stopPropagation();
        onToggle();
      }}
    >
      <Heart size={16} fill={on ? 'currentColor' : 'none'} />
    </button>
  );
}
