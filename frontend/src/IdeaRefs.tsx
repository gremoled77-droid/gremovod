import {useEffect, useState} from 'react';
import {apiFetch} from './api';

type Asset = {id: string; url: string; thumbnail_url?: string | null; metadata?: {original_name?: string}};

/** Референсы, прикреплённые на экране «Идея»: показываются на «Мире» и «Раскадровке». */
export default function IdeaRefs({projectId, ids}: {projectId: string; ids: string[]}) {
  const [assets, setAssets] = useState<Asset[]>([]);
  useEffect(() => {
    if (!ids.length || !projectId) return setAssets([]);
    void apiFetch('/api/library?project_id=' + encodeURIComponent(projectId))
      .then(r => (r.ok ? r.json() : []))
      .then((list: Asset[]) => setAssets(list.filter(a => ids.includes(a.id))))
      .catch(() => undefined);
  }, [ids, projectId]);
  if (!assets.length) return null;
  return (
    <div className="idea-refs-strip" aria-label="Референсы из Идеи">
      <small>Референсы из «Идеи»</small>
      <div>
        {assets.map(a => (
          <a key={a.id} href={a.url} target="_blank" rel="noreferrer">
            <img src={a.thumbnail_url || a.url} alt={a.metadata?.original_name || 'Референс'} />
          </a>
        ))}
      </div>
    </div>
  );
}
