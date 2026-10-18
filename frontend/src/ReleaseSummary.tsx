import {useEffect, useState} from 'react';
import {apiFetch} from './api';
import {useCounts} from './MontageSummary';

type Budget = {
  project_limit_usd: number;
  daily_limit_usd: number;
  project_reserved_usd: number;
  daily_reserved_usd: number;
};
const money = (v: number | undefined) => '$' + (v ?? 0).toFixed(2);

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
  const [budget, setBudget] = useState<Budget | null>(null);
  useEffect(() => {
    setBudget(null);
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
        <h2>Бюджет и библиотека проекта</h2>
      </div>
      <p className="muted">
        Расходы показаны по резервам API, материалы — по библиотеке проекта. Готовность выбранной серии
        проверяется ниже.
      </p>
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
        </ul>
      </div>
    </section>
  );
}
