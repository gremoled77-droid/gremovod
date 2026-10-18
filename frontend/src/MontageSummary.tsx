import {useEffect, useState} from 'react';
import {apiFetch} from './api';
import type {Mode} from './screens';

/** Сколько в библиотеке проекта картинок, клипов и звуковых дорожек. */
export function useCounts(projectId: string) {
  const [counts, setCounts] = useState({images: 0, videos: 0, audio: 0});
  useEffect(() => {
    setCounts({images: 0, videos: 0, audio: 0});
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
export function MontageSummary({onMode}: {onMode: (m: Mode) => void}) {
  const cards: {mode: Mode; title: string; hint: string}[] = [
    {mode: 'create', title: 'Кадры', hint: 'основа клипов'},
    {mode: 'video', title: 'Видео', hint: 'оживлённые кадры'},
    {mode: 'audio', title: 'Звук', hint: 'голос и музыка'},
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
            <small>Открыть этап</small>
            <b>{c.title}</b>
            <span>{c.hint}</span>
          </button>
        ))}
      </div>
      <p className="ss-note">
        Выбери серию ниже: скачай ZIP с клипами, звуком и монтажным списком для импорта в CapCut.
      </p>
    </section>
  );
}
