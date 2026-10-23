import {useEffect, useRef, useState} from 'react';
import {apiFetch} from './api';
import {startActivityFeed} from './activityFeed';

export type ActivityItem = {
  id: string;
  source: 'api' | 'external' | 'native';
  kind: string;
  provider: string;
  model: string;
  status: string;
  raw_status: string;
  created_at: string;
  prompt: string;
  asset_ids: string[];
  node_id?: string | null;
  delivery?: {state: string} | null;
};

const EMPTY: ActivityItem[] = [];
/** One feed scoped to the active project; stale responses never cross project boundaries. */
export default function useActivity(projectId: string) {
  const [snapshot, setSnapshot] = useState<{
    project: string;
    items: ActivityItem[];
    error: string;
    ready: boolean;
  }>({ready: false, project: '', items: EMPTY, error: ''});
  const kick = useRef<{project: string; refresh: () => void} | null>(null);
  useEffect(() => {
    setSnapshot({project: projectId, items: EMPTY, error: '', ready: false});
    if (!projectId) return;
    const feed = startActivityFeed<ActivityItem>(
      `/api/activity?project_id=${encodeURIComponent(projectId)}`,
      apiFetch,
      items => setSnapshot({project: projectId, items, error: '', ready: true}),
      error => setSnapshot(current => (current.project === projectId ? {...current, error} : current))
    );
    kick.current = {project: projectId, refresh: feed.refresh};
    return () => {
      feed.stop();
      if (kick.current?.project === projectId) kick.current = null;
    };
  }, [projectId]);
  return {
    connected: snapshot.project === projectId && snapshot.ready && !snapshot.error,
    items: snapshot.project === projectId ? snapshot.items : EMPTY,
    error: snapshot.project === projectId ? snapshot.error : '',
    reset: () => {
      if (kick.current?.project === projectId) kick.current.refresh();
    },
  };
}
