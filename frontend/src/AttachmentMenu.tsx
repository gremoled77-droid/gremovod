import {useEffect, useRef, useState} from 'react';
import {apiFetch, responseJson} from './api';
import {
  addAttachment,
  ATTACHMENT_ROLES,
  removeAttachment,
  roleLabel,
  setAttachmentRole,
  type Attachment,
} from './attachments';

type Hero = {id: string; name: string; working_asset_id?: string};
type Asset = {id: string; metadata: {kind?: string}};
const thumb = (id: string) => `/api/library/${id}/thumbnail`;

/** Вложения ролика: меню «Добавить» (герой, локация из библиотеки, загрузка файла) и ряд карточек с ролью. */
export default function AttachmentMenu({
  projectId,
  ensureProject,
  heroes,
  items,
  revision,
  onChange,
  onAsset,
}: {
  projectId: string;
  ensureProject?: () => Promise<string>;
  heroes: Hero[];
  items: Attachment[];
  revision: number;
  onChange: (items: Attachment[]) => void;
  onAsset?: () => void;
}) {
  const [open, setOpen] = useState<'' | 'menu' | 'hero' | 'location'>(''),
    [library, setLibrary] = useState<Asset[]>([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    file = useRef<HTMLInputElement>(null);
  useEffect(() => {
    let active = true;
    if (open === 'location' && projectId)
      void apiFetch('/api/library?project_id=' + encodeURIComponent(projectId))
        .then(responseJson)
        .then((rows: Asset[]) => {
          if (active) setLibrary(rows.filter(x => !['video', 'audio'].includes(x.metadata.kind || 'image')));
        })
        .catch(e => active && setError(String(e)));
    return () => {
      active = false;
    };
  }, [open, projectId, revision]);
  const add = (id: string, role: string) => {
    onChange(addAttachment(items, id, role));
    setOpen('');
  };
  const upload = async (f: File) => {
    setBusy(true);
    setError('');
    setOpen('');
    try {
      const pid = projectId || (ensureProject ? await ensureProject() : '');
      if (!pid) throw Error('Нет проекта для загрузки');
      const form = new FormData();
      form.append('project_id', pid);
      form.append('file', f);
      const asset = await responseJson(
        await apiFetch('/api/library/import-image', {method: 'POST', body: form})
      );
      onAsset?.();
      onChange(addAttachment(items, asset.id, 'reference'));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  const withImage = heroes.filter(h => h.working_asset_id);
  return (
    <div className="att">
      <div className="att-bar">
        <button type="button" aria-expanded={open !== ''} onClick={() => setOpen(open ? '' : 'menu')}>
          ＋ Добавить вложение
        </button>
        {open === 'menu' && (
          <div className="att-menu" role="menu">
            <button role="menuitem" onClick={() => setOpen('hero')}>
              Добавить персонажа
            </button>
            <button role="menuitem" onClick={() => setOpen('location')}>
              Добавить локацию
            </button>
            <button role="menuitem" disabled={busy} onClick={() => file.current?.click()}>
              Загрузить файл
            </button>
          </div>
        )}
        <input
          ref={file}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          hidden
          onChange={e => {
            const f = e.target.files?.[0];
            e.target.value = '';
            if (f) void upload(f);
          }}
        />
        {busy && <small>Загружаю…</small>}
      </div>
      {open === 'hero' && (
        <div className="att-pick" aria-label="Выбор персонажа">
          {withImage.length ? (
            withImage.map(h => (
              <button key={h.id} className="att-tile" onClick={() => add(h.working_asset_id!, 'character')}>
                <img src={thumb(h.working_asset_id!)} alt="" loading="lazy" />
                <span>{h.name}</span>
              </button>
            ))
          ) : (
            <p className="muted">
              У героев пока нет рабочего изображения. Загрузи файл или создай героя на экране «Персонажи».
            </p>
          )}
        </div>
      )}
      {open === 'location' && (
        <div className="att-pick" aria-label="Выбор локации из библиотеки">
          {library.length ? (
            library.map(a => (
              <button key={a.id} className="att-tile" onClick={() => add(a.id, 'location')}>
                <img src={thumb(a.id)} alt="" loading="lazy" />
              </button>
            ))
          ) : (
            <p className="muted">В библиотеке пока нет картинок. Нажми «Загрузить файл».</p>
          )}
        </div>
      )}
      {error && <p role="alert">{error}</p>}
      {items.length > 0 && (
        <ul className="att-list">
          {items.map(a => (
            <li key={a.asset_id} className="att-chip">
              <img src={thumb(a.asset_id)} alt={roleLabel(a.role)} loading="lazy" />
              <select
                aria-label="Роль вложения"
                value={a.role}
                onChange={e => onChange(setAttachmentRole(items, a.asset_id, e.target.value))}
              >
                {ATTACHMENT_ROLES.map(r => (
                  <option key={r.id} value={r.id}>
                    {r.label}
                  </option>
                ))}
              </select>
              <button
                type="button"
                aria-label="Убрать вложение"
                onClick={() => onChange(removeAttachment(items, a.asset_id))}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Те же вложения только для просмотра (экран «Мир»). */
export function AttachmentStrip({items}: {items: Attachment[]}) {
  if (!items.length) return null;
  return (
    <div className="att">
      <small>Исходники ролика (меняются на экране «Идея»)</small>
      <ul className="att-list att-ro" aria-label="Исходники ролика">
        {items.map(a => (
          <li key={a.asset_id} className="att-chip">
            <img src={thumb(a.asset_id)} alt="" loading="lazy" />
            <span>{roleLabel(a.role)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
