import {useEffect, useState} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
import {budgetLines, type BudgetSummary} from './llmDisplay';
import {smallUsd} from './usdFormat';
type Budget = {
  project_limit_usd: number;
  daily_limit_usd: number;
  project_reserved_usd: number;
  daily_reserved_usd: number;
  day_moscow: string;
  llm_project_usd?: number;
  llm_daily_usd?: number;
  llm_calls_project?: number;
  actual_cost_usd?: number;
  reserved_usd?: number;
  unknown_cost_usd?: number;
  reference_cost_usd?: number;
};
export default function BudgetPanel({projectId}: {projectId: string}) {
  const [data, setData] = useState<Budget | null>(null),
    [project, setProject] = useState(''),
    [daily, setDaily] = useState(''),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState('');
  useEffect(() => {
    let active = true;
    setData(null);
    setError('');
    if (projectId)
      void apiFetch('/api/budgets/' + encodeURIComponent(projectId))
        .then(responseJson)
        .then(d => {
          if (active) {
            setData(d);
            setProject(String(d.project_limit_usd));
            setDaily(String(d.daily_limit_usd));
          }
        })
        .catch(e => {
          if (active) setError(String(e));
        });
    return () => {
      active = false;
    };
  }, [projectId]);
  // Та же сводка, что отдаёт API: факт, резерв, неизвестные списания и неденежный ориентир.
  const llm: BudgetSummary = {
    actual_cost_usd: data?.actual_cost_usd ?? 0,
    reserved_usd: data?.reserved_usd ?? 0,
    unknown_cost_usd: data?.unknown_cost_usd ?? 0,
    reference_cost_usd: data?.reference_cost_usd ?? 0,
    calls: data?.llm_calls_project ?? 0,
  };
  const save = async () => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await responseJson(
        await apiFetch('/api/budgets/limits', {
          method: 'PUT',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({project_usd: Number(project), daily_usd: Number(daily)}),
        })
      );
      setData(d => (d ? {...d, project_limit_usd: Number(project), daily_limit_usd: Number(daily)} : d));
      setNotice('Серверные лимиты сохранены. Генерации не запускались.');
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="panel">
      <h3>Лимиты платных генераций</h3>
      {data && (
        <>
          <p>
            Зарезервировано: ${data.project_reserved_usd.toFixed(3)} в проекте; $
            {data.daily_reserved_usd.toFixed(3)} за {data.day_moscow} (МСК).
          </p>
          <p>
            LLM в проекте ({data.llm_calls_project ?? 0} вызовов) — разбивка та же, что в API:
          </p>
          <ul style={{margin: '4px 0 8px', paddingLeft: 18}}>
            {budgetLines(llm).map(line => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <p className="muted">
            Экспозиция LLM (факт + удерживаемые резервы + неизвестные списания):{' '}
            {smallUsd(data.llm_project_usd ?? 0)} в проекте; {smallUsd(data.llm_daily_usd ?? 0)} за сутки по всей
            студии. В лимитах учтена дополнительно к генерациям.
          </p>
          <div className="param-grid">
            <label>
              Лимит каждого проекта, USD
              <input
                type="number"
                min="0"
                max="1000"
                step="0.01"
                value={project}
                onChange={e => setProject(e.target.value)}
              />
            </label>
            <label>
              Общий лимит в сутки, USD
              <input
                type="number"
                min="0"
                max="1000"
                step="0.01"
                value={daily}
                onChange={e => setDaily(e.target.value)}
              />
            </label>
          </div>
          <button
            disabled={
              busy ||
              !project.trim() ||
              !daily.trim() ||
              !Number.isFinite(Number(project)) ||
              !Number.isFinite(Number(daily))
            }
            onClick={() => void save()}
          >
            Сохранить лимиты
          </button>
          <p className="muted">
            Лимиты общие для студии и проверяются сервером. Учёт идёт по оценкам до отправки, включая
            неопределённые и неудачные запросы; это не подтверждение списаний провайдера. Чат Codex не
            расходует эти API-бюджеты. Ноль запрещает новые платные генерации.
          </p>
        </>
      )}
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
    </section>
  );
}
