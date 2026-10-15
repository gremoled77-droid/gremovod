import BudgetPanel from './BudgetPanel';
import {useEffect, useState} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
type Entry = {
  id: string;
  target: string;
  provider: string;
  kind: string;
  status: string;
  actual_usd: number | null;
  estimated_usd: number | null;
  cost_note: string;
  used: boolean;
  api_equivalent: {
    usd: number;
    width: number;
    height: number;
    quality_assumption: string;
    assumed_size: boolean;
  } | null;
};
type Report = {
  llm_calls_unpriced: number;
  media_costs_complete: boolean;
  unknown_generation_cost_count: number;
  actual_usd_known: number;
  costs_complete: boolean;
  unknown_cost_count: number;
  estimated_usd: number;
  attempts: number;
  used_generations: number;
  success_percent: number | null;
  cost_per_used_result_known: number | null;
  chat_image_count: number;
  chat_api_equivalent_usd: number;
  jobs: Entry[];
  progress: {
    month: string;
    model: string;
    attempts: number;
    used: number;
    actual_usd: number;
    unknown_costs: number;
  }[];
};
function CostRow({item, onSaved}: {item: Entry; onSaved: () => void}) {
  const [value, setValue] = useState(item.actual_usd === null ? '' : String(item.actual_usd)),
    [note, setNote] = useState(item.cost_note),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    setError('');
    try {
      await responseJson(
        await apiFetch('/api/economics/jobs/' + item.id, {
          method: 'PUT',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({actual_usd: value.trim() === '' ? null : Number(value), note}),
        })
      );
      onSaved();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };
  if (item.provider === 'codex_chat')
    return (
      <tr>
        <td>
          {item.target}
          <small>ChatGPT · {item.status}</small>
        </td>
        <td>{item.api_equivalent ? '≈ $' + item.api_equivalent.usd.toFixed(3) : '—'}</td>
        <td>Через чат</td>
        <td>
          <small>
            {item.api_equivalent
              ? `Сценарий API: ${item.api_equivalent.width}×${item.api_equivalent.height}, ${item.api_equivalent.quality_assumption}${item.api_equivalent.assumed_size ? ' (размер принят для сравнения)' : ''}. Только выходное изображение.`
              : 'Учитывается количество, без списания по API.'}
          </small>
        </td>
      </tr>
    );
  return (
    <tr>
      <td>
        {item.target}
        <small>
          {item.provider} · {item.status}
          <br />
          {item.id.slice(0, 8)}
          {item.used ? ' · В ролике' : ''}
        </small>
      </td>
      <td>{item.estimated_usd === null ? '—' : '$' + item.estimated_usd.toFixed(3)}</td>
      <td>
        <label>
          Подтверждено, USD
          <input
            type="number"
            min="0"
            step="0.001"
            value={value}
            onChange={e => setValue(e.target.value)}
            placeholder="Нет данных"
          />
        </label>
      </td>
      <td>
        <label>
          Основание суммы
          <input value={note} onChange={e => setNote(e.target.value)} />
        </label>
        <button disabled={busy} onClick={() => void save()}>
          Сохранить
        </button>
        {error && <small role="alert">{error}</small>}
      </td>
    </tr>
  );
}
export default function EconomicsPanel({projectId, revision}: {projectId: string; revision: number}) {
  const [data, setData] = useState<Report | null>(null),
    [error, setError] = useState(''),
    [tick, setTick] = useState(0);
  useEffect(() => {
    let active = true;
    setData(null);
    if (projectId)
      void apiFetch('/api/economics?project_id=' + encodeURIComponent(projectId))
        .then(responseJson)
        .then(d => {
          if (active) setData(d);
        })
        .catch(e => {
          if (active) setError(String(e));
        });
    return () => {
      active = false;
    };
  }, [projectId, revision, tick]);
  const money = (n: number | null) => (n === null ? '—' : '$' + n.toFixed(3));
  return (
    <section className="panel">
      <div className="panel-title">
        <h2>Экономика ролика</h2>
        <button onClick={() => setTick(x => x + 1)}>Обновить</button>
      </div>
      <p className="muted">
        Выбранный проект — отдельный ролик. Расходы на неудачные попытки входят в его стоимость. Отмечай
        фактическое использование в библиотеке.
      </p>
      {projectId && <BudgetPanel projectId={projectId} />}
      {!projectId && <p>Выбери или сохрани проект ролика.</p>}
      {error && <div className="alert">{error}</div>}
      {data && (
        <>
          <div className="cost-stats">
            <article>
              <small>Расходы ролика · подтверждено</small>
              <b>{money(data.actual_usd_known)}</b>
              <small>
                {data.costs_complete
                  ? 'Все суммы заполнены'
                  : 'Неполный итог: без цены ' + data.unknown_cost_count + ' задач'}
              </small>
            </article>
            <article>
              <small>Попыток генерации</small>
              <b>{data.attempts}</b>
            </article>
            <article>
              <small>Вошло в ролик</small>
              <b>
                {data.used_generations} · {data.success_percent === null ? '—' : data.success_percent + '%'}
              </b>
            </article>
            <article>
              <small>Расходы на один использованный результат</small>
              <b>{money(data.cost_per_used_result_known)}</b>
              <small>
                {data.costs_complete
                  ? 'По подтверждённым расходам'
                  : 'Предварительно: часть расходов неизвестна'}
              </small>
            </article>
          </div>
          {data.llm_calls_unpriced > 0 && (
            <p className="notice">
              Без цены: генерации — {data.unknown_generation_cost_count}, API-промпты —{' '}
              {data.llm_calls_unpriced}.{' '}
              {data.media_costs_complete
                ? 'Цены генераций заполнены. Полная стоимость ролика остаётся предварительной до учёта API-промптов.'
                : 'Заполни фактические расходы в таблице ниже.'}
            </p>
          )}
          <p className="muted">
            Оценки до запуска: {money(data.estimated_usd)}. Это отдельный показатель, он не подтверждает
            списание. Генерации через чат учитываются количественно. API-эквивалент не добавляется в расходы
            ролика и не означает подтверждённую экономию; подписка не распределяется. Пустая цена означает
            «неизвестно», ноль — подтверждённый нулевой расход.
          </p>
          <div className="cost-stats">
            <article>
              <small>Изображений через ChatGPT</small>
              <b>{data.chat_image_count}</b>
              <small>Эквивалент API: ≈ {money(data.chat_api_equivalent_usd)}</small>
            </article>
          </div>
          <p className="muted">
            API-эквивалент GPT: фактический размер, если он известен; иначе 1536×1024. Для 2.5 принят max, для
            2 — high, независимо от скрытых настроек чата. Входной текст, референсы и промежуточные
            изображения не включены.{' '}
            <a
              href="https://developers.openai.com/api/docs/guides/image-generation"
              target="_blank"
              rel="noreferrer"
            >
              Официальный калькулятор OpenAI
            </a>{' '}
            · тариф проверен 15.10.2026.
          </p>
          <h3>Все попытки и расходы</h3>
          <div className="table-scroll">
            <table className="cost-table">
              <thead>
                <tr>
                  <th>Задание</th>
                  <th>Оценка</th>
                  <th>Факт</th>
                  <th>Основание</th>
                </tr>
              </thead>
              <tbody>
                {data.jobs.map(j => (
                  <CostRow key={j.id} item={j} onSaved={() => setTick(x => x + 1)} />
                ))}
              </tbody>
            </table>
          </div>
          <h3>Прогресс по моделям и месяцам</h3>
          <div className="table-scroll">
            <table className="cost-table">
              <thead>
                <tr>
                  <th>Период</th>
                  <th>Модель</th>
                  <th>Попытки</th>
                  <th>В ролике</th>
                  <th>Выход годных</th>
                  <th>Подтверждено</th>
                </tr>
              </thead>
              <tbody>
                {data.progress.map(p => (
                  <tr key={p.month + p.model}>
                    <td>{p.month}</td>
                    <td>{p.model}</td>
                    <td>{p.attempts}</td>
                    <td>{p.used}</td>
                    <td>{((100 * p.used) / p.attempts).toFixed(1)}%</td>
                    <td>
                      {money(p.actual_usd)}
                      {p.unknown_costs > 0 ? ' *' : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted">
            Выход годных = число попыток, чей результат использован в финальном ролике, / число завершившихся
            попыток, включая ошибки. Ожидающие задачи исключены. Непросмотренные результаты пока не считаются
            годными. Динамика показывает наблюдения; рост навыка требует сравнения похожих сцен и достаточного
            числа попыток.
          </p>
          <button
            onClick={() => {
              const link = document.createElement('a');
              const url = URL.createObjectURL(
                new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'})
              );
              link.href = url;
              link.download = 'clip-economics-' + projectId + '.json';
              link.click();
              URL.revokeObjectURL(url);
            }}
          >
            Скачать отчёт JSON
          </button>
        </>
      )}
    </section>
  );
}
