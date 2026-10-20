import {useEffect, useState} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
import {smallUsd} from './usdFormat';
import {changedRows, newRoleRow, roleRows, type N8nAllowance, type N8nRoleRow} from './n8nSpend';
type Budget = {
  project_limit_usd: number;
  daily_limit_usd: number;
  project_reserved_usd: number;
  daily_reserved_usd: number;
  day_moscow: string;
  llm_project_usd?: number;
  llm_daily_usd?: number;
  llm_calls_project?: number;
  llm_unknown_calls?: number;
  llm_unknown_usd?: number;
  llm_over_estimate_usd?: number;
  n8n_reserved_usd?: number;
};
export default function BudgetPanel({projectId}: {projectId: string}) {
  const [data, setData] = useState<Budget | null>(null),
    [project, setProject] = useState(''),
    [daily, setDaily] = useState(''),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState(''),
    [allowances, setAllowances] = useState<N8nAllowance[]>([]),
    [rows, setRows] = useState<N8nRoleRow[]>([]),
    [newRole, setNewRole] = useState(''),
    [newCap, setNewCap] = useState(''),
    [capBusy, setCapBusy] = useState(false);
  useEffect(() => {
    let active = true;
    void apiFetch('/api/n8n/allowances')
      .then(responseJson)
      .then(d => {
        if (active) {
          setAllowances(d.allowances ?? []);
          setRows(roleRows(d.allowances ?? []));
        }
      })
      .catch(e => {
        if (active) setError(String(e));
      });
    return () => {
      active = false;
    };
  }, []);
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
  const saveAllowances = async () => {
    const changed = changedRows(rows, allowances);
    if (!changed.length) return;
    setCapBusy(true);
    setError('');
    setNotice('');
    try {
      for (const row of changed) {
        await responseJson(
          await apiFetch('/api/n8n/allowances/' + encodeURIComponent(row.role), {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({cap_usd: row.cap_usd, model: row.model, note: row.note}),
          })
        );
      }
      const fresh = await responseJson(await apiFetch('/api/n8n/allowances'));
      setAllowances(fresh.allowances ?? []);
      setRows(roleRows(fresh.allowances ?? []));
      setNotice('Потолки ролей n8n сохранены. Агент без потолка платить не может.');
    } catch (e) {
      setError(String(e));
    } finally {
      setCapBusy(false);
    }
  };
  const capChanged = changedRows(rows, allowances).length;
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
            LLM-запросы (включены в этот же лимит вместе с генерациями): {smallUsd(data.llm_project_usd ?? 0)} в
            проекте ({data.llm_calls_project ?? 0} вызовов); {smallUsd(data.llm_daily_usd ?? 0)} за сутки по
            всей студии.
          </p>
          {(data.llm_unknown_calls ?? 0) > 0 && (
            <p>
              Неопределённых вызовов ждут сверки: {data.llm_unknown_calls} на {smallUsd(data.llm_unknown_usd ?? 0)}.
              Их резерв удерживается и блокирует новые платные запуски до ручной сверки.
            </p>
          )}
          <p>
            Агенты n8n (в том же лимите вместе с генерациями и LLM): {smallUsd(data.n8n_reserved_usd ?? 0)} в
            проекте. Это их резерв: пока агент не отчитался о факте, деньги считаются занятыми.
          </p>
          <div className="param-grid">
            {rows.map(row => (
              <label key={row.role}>
                Потолок роли {row.role}, USD
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={row.cap}
                  onChange={e => setRows(current => current.map(r => (r.role === row.role ? {...r, cap: e.target.value} : r)))}
                />
              </label>
            ))}
          </div>
          <div className="param-grid">
            <label>
              Новая роль
              <input value={newRole} placeholder="A1" onChange={e => setNewRole(e.target.value)} />
            </label>
            <label>
              Потолок шага, USD
              <input type="number" min="0" step="0.01" value={newCap} onChange={e => setNewCap(e.target.value)} />
            </label>
          </div>
          <button
            disabled={capBusy || !newRole.trim()}
            onClick={() => {
              const row = newRoleRow(rows, newRole, newCap);
              if (!row) return;
              setRows(current => [...current, row]);
              setNewRole('');
              setNewCap('');
            }}
          >
            Добавить роль
          </button>
          {rows.length > 0 && (
            <button disabled={capBusy || capChanged === 0} onClick={() => void saveAllowances()}>
              Сохранить потолки ролей
            </button>
          )}
          <p className="muted">
            Потолок роли — это потолок одного платного шага агента, а не его фактический расход. Пока потолок не
            задан, роль платить не может: резерв не создаётся и шаг останавливается.
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
            Лимиты общие для студии и проверяются сервером. Учёт идёт по оценкам до отправки: отказ провайдера
            резерв освобождает, а неопределённый исход удерживает резерв до ручной сверки. Это не подтверждение
            списаний провайдера. Чат Codex не расходует эти API-бюджеты. Ноль запрещает новые платные генерации.
          </p>
        </>
      )}
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
    </section>
  );
}
