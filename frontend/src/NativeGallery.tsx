import {useEffect, useState} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
import ReplaceCharacterButton, {type ReplacementControls} from './ReplaceCharacterButton';

type Job = {
  id: string;
  operation: string;
  status: string;
  message: string;
  image_url: string | null;
  asset_id: string;
};
export default function NativeGallery({
  projectId,
  onRefine,
  character,
  onReplaced,
}: {projectId: string; onRefine: (id: string) => void} & ReplacementControls) {
  const [jobs, setJobs] = useState<Job[]>([]),
    [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setJobs([]);
    setError('');
    const refresh = async () => {
      if (!projectId) return;
      try {
        const data = await responseJson(
          await apiFetch('/api/chatgpt/jobs?project_id=' + encodeURIComponent(projectId))
        );
        if (active) {
          setJobs(data);
          setError('');
        }
      } catch (e) {
        if (active) setError(String(e));
      }
    };
    void refresh();
    const timer = window.setInterval(() => {
      if (!document.hidden) void refresh();
    }, 4000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [projectId]);
  return (
    <div className="native-results">
      {error && <p role="alert">{error}</p>}
      {jobs
        .filter(j => ['generate', 'edit'].includes(j.operation) && j.status !== 'cancelled')
        .map(j => (
          <article className="job" key={j.id}>
            <div className="jobtop">
              <b>ChatGPT · {j.operation === 'edit' ? 'Правка персонажа / изображения' : 'Изображение'}</b>
              <span>
                {(
                  {
                    queued: 'В очереди',
                    preparing: 'Улучшение промпта',
                    generating: 'Генерация',
                    completed: 'Готово',
                    failed: 'Ошибка',
                  } as Record<string, string>
                )[j.status] || j.status}
              </span>
            </div>
            <p>{j.message}</p>
            {j.image_url && (
              <>
                <img src={j.image_url} alt="Результат ChatGPT в галерее" />
                <div className="chips">
                  <button onClick={() => onRefine(j.asset_id)}>Допилить</button>
                  <ReplaceCharacterButton
                    projectId={projectId}
                    assetId={j.asset_id}
                    character={character}
                    onReplaced={onReplaced}
                  />
                  <a href={j.image_url} download>
                    Скачать оригинал
                  </a>
                </div>
              </>
            )}
          </article>
        ))}
    </div>
  );
}
