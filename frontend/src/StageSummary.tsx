import {useEffect, useState} from 'react';
import {apiFetch} from './api';
import type {Mode} from './StageNav';

type Budget = {
  project_limit_usd: number;
  daily_limit_usd: number;
  project_reserved_usd: number;
  daily_reserved_usd: number;
};
type ReleaseArtifact = {
  id: string;
  title: string;
  project_revision: number;
  version_id: string | null;
  file_url: string;
};
const money = (v: number | undefined) => '$' + (v ?? 0).toFixed(2);

/** Сколько в библиотеке проекта картинок, клипов и звуковых дорожек. */
function useCounts(projectId: string) {
  const [counts, setCounts] = useState({images: 0, videos: 0, audio: 0});
  useEffect(() => {
    if (!projectId) return;
    let live = true;
    void apiFetch('/api/library?project_id=' + encodeURIComponent(projectId))
      .then(r => (r.ok ? r.json() : []))
      .then((list: {metadata?: {kind?: string}}[]) => {
        const count = (kind: string) => list.filter(a => a.metadata?.kind === kind).length;
        if (live) setCounts({images: count('image'), videos: count('video'), audio: count('audio')});
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [projectId]);
  return counts;
}

/** Шапка «Монтажа»: что готово к выгрузке в CapCut по этапам. */
export function MontageSummary({projectId, onMode}: {projectId: string; onMode: (m: Mode) => void}) {
  const {images, videos, audio} = useCounts(projectId);
  const cards: {mode: Mode; title: string; count: number; unit: string; hint: string}[] = [
    {mode: 'create', title: 'Кадры', count: images, unit: 'картинок', hint: 'основа клипов'},
    {mode: 'video', title: 'Видео', count: videos, unit: 'клипов', hint: 'оживлённые кадры'},
    {mode: 'audio', title: 'Звук', count: audio, unit: 'дорожек', hint: 'голос и музыка'},
  ];
  return (
    <section className="ss">
      <div className="ss-head">
        <span className="ss-eyebrow">Монтаж · CapCut</span>
        <h2>Что готово к выгрузке</h2>
        <p className="muted">
          Студия соберёт клипы и звук в порядке кадров раскадровки, а монтаж делается в CapCut на компьютере.
        </p>
      </div>
      <div className="ss-cards">
        {cards.map(c => (
          <button key={c.mode} className="ss-card" onClick={() => onMode(c.mode)}>
            <small>{c.title}</small>
            <b>{c.count}</b>
            <span>
              {c.unit} · {c.hint}
            </span>
          </button>
        ))}
      </div>
      <p className="ss-note">
        Кнопка «Выгрузить в CapCut» появится, когда будем настраивать выгрузку на компьютере.
      </p>
    </section>
  );
}

function Gauge({label, used, limit}: {label: string; used?: number; limit?: number}) {
  const p = limit ? Math.min(1, (used ?? 0) / limit) : 0;
  const R = 34;
  const C = 2 * Math.PI * R;
  return (
    <div className="hg">
      <svg viewBox="0 0 84 84" aria-hidden="true">
        <circle cx="42" cy="42" r={R} className="hg-bg" />
        <circle
          cx="42"
          cy="42"
          r={R}
          className="hg-fg"
          strokeDasharray={`${C * p} ${C}`}
          transform="rotate(-90 42 42)"
        />
      </svg>
      <div className="hg-t">
        <b>{money(used)}</b>
        <small>из {money(limit)}</small>
      </div>
      <span>{label}</span>
    </div>
  );
}

/** Шапка «Выпуска»: бюджет проекта и дня, количество результатов. */
export function ReleaseSummary({projectId}: {projectId: string}) {
  const {images, videos, audio} = useCounts(projectId);
  const releaseArtifacts = useReleaseArtifacts(projectId);
  const [budget, setBudget] = useState<Budget | null>(null);
  useEffect(() => {
    if (!projectId) return;
    let live = true;
    void apiFetch('/api/budgets/' + encodeURIComponent(projectId))
      .then(r => (r.ok ? r.json() : null))
      .then(d => live && setBudget(d))
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [projectId]);
  return (
    <section className="ss">
      <div className="ss-head">
        <span className="ss-eyebrow">Выпуск · итоги серии</span>
        <h2>Сколько потрачено и что получено</h2>
      </div>
      <div className="ss-release">
        <div className="ss-gauges">
          <Gauge label="Проект" used={budget?.project_reserved_usd} limit={budget?.project_limit_usd} />
          <Gauge label="Сегодня" used={budget?.daily_reserved_usd} limit={budget?.daily_limit_usd} />
        </div>
        <ul className="ss-totals">
          <li>
            <b>{images}</b> картинок
          </li>
          <li>
            <b>{videos}</b> клипов
          </li>
          <li>
            <b>{audio}</b> звуковых дорожек
          </li>
          <li>
            <b>{releaseArtifacts.length}</b> финальных MP4
          </li>
        </ul>
      </div>
      {releaseArtifacts.map(artifact => (
        <p className="ss-note" key={artifact.id}>
          <a href={artifact.file_url} download>{artifact.title}</a>
          {' · ревизия проекта ' + artifact.project_revision}
          {artifact.version_id ? ' · версия ' + artifact.version_id : ''}
        </p>
      ))}
    </section>
  );
}
