import {useEffect, useState} from 'react';
import {screenOf, type Mode} from './screens';
import {apiFetch, responseJson} from './api';
export type WorkspaceLocation = {
  production_id: string;
  production_title: string;
  source_project_id: string;
  series: {id: string; title: string} | null;
  scene: {id: string; title: string} | null;
  frame: {id: string; title: string} | null;
};
export default function WorkspaceTrail({
  projectId,
  mode,
  onMode,
  onLocation,
  onOpenProject,
}: {
  projectId: string;
  mode: Mode;
  onMode: (mode: Mode) => void;
  onLocation: (location: WorkspaceLocation | null) => void;
  onOpenProject: (id: string) => void;
}) {
  const [context, setContext] = useState<{project: string; location: WorkspaceLocation | null} | null>(null),
    [error, setError] = useState('');
  useEffect(() => {
    let live = true;
    setContext(null);
    setError('');
    onLocation(null);
    if (projectId)
      void apiFetch(`/api/projects/${encodeURIComponent(projectId)}/workspace-location`)
        .then(responseJson)
        .then(location => {
          if (live) {
            setContext({project: projectId, location});
            onLocation(location);
          }
        })
        .catch(e => {
          if (live) setError(String(e));
        });
    return () => {
      live = false;
    };
  }, [projectId, onLocation]);
  const location = context?.project === projectId ? context.location : null;
  const screen = screenOf(mode);
  return (
    <div className="workspace-trail">
      <div>
        <small>
          {location
            ? [
                location.production_title,
                location.series?.title,
                location.scene?.title,
                location.frame?.title,
              ]
                .filter(Boolean)
                .join(' / ')
            : 'Рабочее пространство проекта'}
        </small>
        <h1>{screen.title}</h1>
        {screen.lede && <p className="trail-lede">{screen.lede}</p>}
        {error && <small role="alert">Не удалось загрузить связь с доской. {error}</small>}
      </div>
      {location && location.source_project_id !== projectId && (
        <button onClick={() => onOpenProject(location.source_project_id)}>
          К проекту {location.production_title}
        </button>
      )}
      {location?.frame && mode !== 'storyboard' && (
        <button onClick={() => onMode('storyboard')}>← К раскадровке</button>
      )}
    </div>
  );
}
