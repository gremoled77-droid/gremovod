import {useEffect, useState} from 'react';
import {apiFetch, responseJson} from './api';
import {clearLocal, readLocal, writeLocal} from './localDrafts';
import {LLM_MODELS} from './llmPricing';
import type {WorkspaceLocation} from './WorkspaceTrail';
import './storyPlan.css';

type Node = {id: string; title: string; kind: string; parent_id: string | null; notes: string};
type Card = {
  id: string;
  scene_id: string | null;
  title: string;
  summary: string;
  character_ids: string[];
  location_id: string | null;
  stage: string;
  change: string;
};
type Draft = {base_revision: number; source: string; source_kind: 'idea' | 'script'; cards: Card[]};
type Suggestion = {
  request_id: string;
  plan_revision: number;
  status: string;
  data: {cards?: Card[]; raw?: string; error?: string; cost_usd?: number; model?: string};
};
type Saved = Omit<Draft, 'base_revision'> & {revision: number; suggestions?: Suggestion[]};
type Preview = {
  plan_revision: number;
  board_revision: string;
  order: {card_id: string; scene_id: string | null; title: string; new: boolean}[];
  remaining: {id: string; title: string}[];
};
const stages = {
  '': 'Без отметки',
  setup: 'Завязка',
  development: 'Развитие',
  climax: 'Кульминация',
  ending: 'Финал',
};
const call = async (url: string, body?: unknown, method = 'POST') =>
  responseJson(
    await apiFetch(
      url,
      body === undefined
        ? undefined
        : {method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}
    )
  );
const draftOf = (s: Saved): Draft => ({
  base_revision: s.revision,
  source: s.source,
  source_kind: s.source_kind,
  cards: s.cards,
});
const blankCard = (): Card => ({
  id: crypto.randomUUID(),
  scene_id: null,
  title: 'Новая сцена',
  summary: '',
  character_ids: [],
  location_id: null,
  stage: '',
  change: '',
});

export default function StoryPlanBoard({
  location,
  brief,
}: {
  location: WorkspaceLocation | null;
  brief: string;
}) {
  const remembered = readLocal<{pid: string; sid: string}>('studio:story-plan-location', {pid: '', sid: ''});
  const [productions, setProductions] = useState<Node[]>([]);
  const [pid, setPid] = useState(location?.production_id || remembered.pid);
  const [sid, setSid] = useState(location?.series?.id || remembered.sid);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [error, setError] = useState('');
  const [name, setName] = useState('');
  const [creating, setCreating] = useState(false);
  const [treeTick, setTreeTick] = useState(0);
  useEffect(() => {
    let live = true;
    void call('/api/productions')
      .then((items: Node[]) => {
        if (live) {
          setProductions(items);
          setPid(p => (items.some(x => x.id === p) ? p : items[0]?.id || ''));
        }
      })
      .catch(e => {
        if (live) setError(String(e));
      });
    return () => {
      live = false;
    };
  }, []);
  useEffect(() => {
    let live = true;
    setNodes([]);
    if (pid)
      void call('/api/productions/' + pid)
        .then(t => {
          if (live) {
            setNodes(t.nodes);
            setSid(s =>
              t.nodes.some((n: Node) => n.id === s && n.kind === 'series')
                ? s
                : t.nodes.find((n: Node) => n.kind === 'series')?.id || ''
            );
          }
        })
        .catch(e => {
          if (live) setError(String(e));
        });
    return () => {
      live = false;
    };
  }, [pid, creating, treeTick]);
  useEffect(() => {
    writeLocal('studio:story-plan-location', {pid, sid});
  }, [pid, sid]);
  return (
    <section className="panel story-plan">
      <h2>Сюжет серии</h2>
      <p>Одна карточка — одна сцена. Порядок плана переносится в раскадровку после просмотра изменений.</p>
      {error && <p role="alert">{error}</p>}
      <div className="story-plan-toolbar">
        <label>
          Проект
          <select
            aria-label="Проект сюжета"
            value={pid}
            onChange={e => {
              setPid(e.target.value);
              setSid('');
            }}
          >
            {!productions.length && <option value="">Нет проектов постановки</option>}
            {productions.map(p => (
              <option key={p.id} value={p.id}>
                {p.title}
              </option>
            ))}
          </select>
        </label>
        <label>
          Серия
          <select aria-label="Серия сюжета" value={sid} onChange={e => setSid(e.target.value)}>
            {!nodes.some(n => n.kind === 'series') && <option value="">Создай серию</option>}
            {nodes
              .filter(n => n.kind === 'series')
              .map(n => (
                <option key={n.id} value={n.id}>
                  {n.title}
                </option>
              ))}
          </select>
        </label>
        <label>
          Новая серия
          <input value={name} maxLength={75} onChange={e => setName(e.target.value)} />
        </label>
        <button
          disabled={!pid || !name.trim() || creating}
          onClick={async () => {
            setCreating(true);
            setError('');
            try {
              const n = await call(`/api/productions/${pid}/nodes`, {kind: 'series', title: name});
              setSid(n.id);
              setName('');
            } catch (e) {
              setError(String(e));
            } finally {
              setCreating(false);
            }
          }}
        >
          Создать серию
        </button>
      </div>
      {!pid && <p>Сначала создай проект раскадровки на экране «Раскадровка».</p>}
      {pid && sid && nodes.some(n => n.id === sid) && (
        <EpisodePlan
          key={pid + '/' + sid}
          pid={pid}
          sid={sid}
          nodes={nodes}
          brief={brief}
          onApplied={() => setTreeTick(t => t + 1)}
        />
      )}
    </section>
  );
}

function EpisodePlan({
  pid,
  sid,
  nodes,
  brief,
  onApplied,
}: {
  pid: string;
  sid: string;
  nodes: Node[];
  brief: string;
  onApplied: () => void;
}) {
  const path = `/api/productions/${pid}/series/${sid}/story-plan`;
  const localKey = `studio:story-plan-draft:${pid}:${sid}`;
  const [draft, setDraft] = useState<Draft | null>(null);
  const [saved, setSaved] = useState<Saved | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [notice, setNotice] = useState('');
  const [storageOK, setStorageOK] = useState(true);
  const [preview, setPreview] = useState<Preview | null>(null),
    [keep, setKeep] = useState(false);
  const [model, setModel] = useState('gpt-5.6-luna');
  const [quote, setQuote] = useState<{estimated_usd: number; quote_token: string} | null>(null);
  const [approved, setApproved] = useState(false);
  const scenes = nodes.filter(n => n.kind === 'episode' && n.parent_id === sid);
  const dirty = !!draft && !!saved && JSON.stringify(draft) !== JSON.stringify(draftOf(saved));
  const perform = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    let live = true;
    void call(path)
      .then((s: Saved) => {
        if (!live) return;
        setSaved(s);
        setSuggestions(s.suggestions || []);
        const local = readLocal<Draft | null>(localKey, null);
        setDraft(local || {...draftOf(s), source: s.revision ? s.source : brief});
        if (local)
          setNotice(
            local.base_revision === s.revision
              ? 'Восстановлен местный черновик.'
              : 'Есть конфликт версий. Экспортируй черновик и загрузи сохранённый план.'
          );
      })
      .catch(e => {
        if (live) setError(String(e));
      });
    return () => {
      live = false;
    };
  }, [path, localKey]);
  const edit = (next: Draft) => {
    setDraft(next);
    setStorageOK(writeLocal(localKey, next));
    setQuote(null);
    setApproved(false);
    setPreview(null);
  };
  const patch = (id: string, data: Partial<Card>) => {
    if (draft) edit({...draft, cards: draft.cards.map(c => (c.id === id ? {...c, ...data} : c))});
  };
  const store = async () => {
    if (!draft) return;
    const s: Saved = await call(path, draft, 'PUT');
    setSaved(s);
    setDraft(draftOf(s));
    clearLocal(localKey);
    setQuote(null);
    setPreview(null);
    setNotice('План сохранён. Раскадровка не изменена.');
  };
  if (!draft || !saved) return <p>{error || 'Загрузка плана…'}</p>;
  return (
    <div>
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {!storageOK && (
        <p role="alert">Браузер не сохранил черновик. Сохрани план на сервере или выгрузи JSON.</p>
      )}
      <fieldset disabled={busy}>
        <label>
          Начать с
          <select
            value={draft.source_kind}
            onChange={e => edit({...draft, source_kind: e.target.value as Draft['source_kind']})}
          >
            <option value="idea">Идеи</option>
            <option value="script">Готового сценария</option>
          </select>
        </label>
        <label>
          {draft.source_kind === 'idea'
            ? 'Замысел серии'
            : 'Исходный сценарий — сохраняется отдельно от кратких описаний'}
          <textarea
            rows={5}
            maxLength={200000}
            value={draft.source}
            onChange={e => edit({...draft, source: e.target.value})}
          />
        </label>
        <div className="story-plan-toolbar">
          <button
            onClick={() => edit({...draft, cards: [...draft.cards, blankCard()]})}
            disabled={draft.cards.length >= 100}
          >
            Добавить сцену
          </button>
          <button
            disabled={!scenes.length || draft.cards.length > 0}
            onClick={() =>
              void perform(async () => {
                const board = await call(`/api/productions/${pid}/series/${sid}/storyboard`);
                edit({
                  ...draft,
                  cards: board.scenes.map(
                    (
                      n: Node & {selection: {character_node_ids: string[]; location_node_id: string | null}}
                    ) => ({
                      ...blankCard(),
                      scene_id: n.id,
                      title: n.title,
                      summary: n.notes.slice(0, 4000),
                      character_ids: n.selection.character_node_ids,
                      location_id: n.selection.location_node_id,
                    })
                  ),
                });
              })
            }
          >
            Взять существующие сцены
          </button>
          <button onClick={() => void perform(store)} disabled={!dirty}>
            Сохранить план
          </button>
          <button
            onClick={() => {
              const blob = new Blob([JSON.stringify(draft, null, 2)], {type: 'application/json'});
              const url = URL.createObjectURL(blob),
                a = document.createElement('a');
              a.href = url;
              a.download = 'story-plan-draft.json';
              a.click();
              URL.revokeObjectURL(url);
            }}
          >
            Выгрузить черновик JSON
          </button>
          <button
            onClick={() =>
              void perform(async () => {
                const s: Saved = await call(path);
                setSaved(s);
                setSuggestions(s.suggestions || []);
                setNotice(
                  'Серверная версия обновлена. Черновик сохранён; можно отдельно загрузить план с сервера.'
                );
              })
            }
          >
            Обновить версии и предложения
          </button>
          <button
            disabled={dirty}
            onClick={() => {
              setDraft(draftOf(saved));
              clearLocal(localKey);
            }}
          >
            Загрузить сохранённый план
          </button>
        </div>
        {draft.base_revision !== saved.revision && (
          <p role="alert">План изменён в другом окне. Выгрузи черновик, затем загрузи сохранённый план.</p>
        )}
        {draft.base_revision !== saved.revision && (
          <button
            onClick={() => {
              setDraft(draftOf(saved));
              clearLocal(localKey);
              setQuote(null);
              setPreview(null);
            }}
          >
            Заменить черновик сохранённым планом
          </button>
        )}
        <ol className="story-plan-cards">
          {draft.cards.map((c, i) => (
            <li key={c.id} className="story-plan-card">
              <div className="story-plan-toolbar">
                <b>Сцена {i + 1}</b>
                <button
                  aria-label={`Сцену ${i + 1} выше`}
                  disabled={!i}
                  onClick={() => {
                    const cards = [...draft.cards];
                    [cards[i - 1], cards[i]] = [cards[i], cards[i - 1]];
                    edit({...draft, cards});
                  }}
                >
                  ↑
                </button>
                <button
                  aria-label={`Сцену ${i + 1} ниже`}
                  disabled={i === draft.cards.length - 1}
                  onClick={() => {
                    const cards = [...draft.cards];
                    [cards[i + 1], cards[i]] = [cards[i], cards[i + 1]];
                    edit({...draft, cards});
                  }}
                >
                  ↓
                </button>
                <button onClick={() => edit({...draft, cards: draft.cards.filter(x => x.id !== c.id)})}>
                  Убрать из плана
                </button>
              </div>
              <label>
                Название
                <input maxLength={75} value={c.title} onChange={e => patch(c.id, {title: e.target.value})} />
              </label>
              <label>
                Краткое содержание
                <textarea
                  maxLength={4000}
                  value={c.summary}
                  onChange={e => patch(c.id, {summary: e.target.value})}
                />
              </label>
              <label>
                Связь со сценой
                <select
                  value={c.scene_id || ''}
                  onChange={e => patch(c.id, {scene_id: e.target.value || null})}
                >
                  <option value="">Создать новую при применении</option>
                  {scenes.map(n => (
                    <option key={n.id} value={n.id}>
                      {n.title}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Этап истории
                <select value={c.stage} onChange={e => patch(c.id, {stage: e.target.value})}>
                  {Object.entries(stages).map(([v, label]) => (
                    <option key={v} value={v}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Что меняется в сцене
                <textarea
                  maxLength={2000}
                  value={c.change}
                  onChange={e => patch(c.id, {change: e.target.value})}
                  placeholder="Например: доверие → подозрение"
                />
              </label>
              <label>
                Персонажи
                <select
                  multiple
                  value={c.character_ids}
                  onChange={e =>
                    patch(c.id, {character_ids: Array.from(e.target.selectedOptions, o => o.value)})
                  }
                >
                  {nodes
                    .filter(n => n.kind === 'character')
                    .map(n => (
                      <option key={n.id} value={n.id}>
                        {n.title}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                Локация
                <select
                  value={c.location_id || ''}
                  onChange={e => patch(c.id, {location_id: e.target.value || null})}
                >
                  <option value="">Пока не выбрана</option>
                  {nodes
                    .filter(n => n.kind === 'location')
                    .map(n => (
                      <option key={n.id} value={n.id}>
                        {n.title}
                      </option>
                    ))}
                </select>
              </label>
            </li>
          ))}
        </ol>
        <h3>Предложения ИИ</h3>
        <p>
          До 6 сцен за запрос. Сохрани исходник и план перед оценкой. Текст длиннее лимита будет отклонён до
          оплаты.
        </p>
        <label>
          Модель
          <select
            value={model}
            onChange={e => {
              setModel(e.target.value);
              setQuote(null);
              setApproved(false);
            }}
          >
            {Object.entries(LLM_MODELS).map(([v, m]) => (
              <option key={v} value={v}>
                {m.label}
              </option>
            ))}
          </select>
        </label>
        <button
          disabled={dirty || !saved.revision || !draft.source.trim()}
          onClick={() =>
            void perform(async () => {
              setQuote(await call(path + '/estimate', {plan_revision: saved.revision, model}));
              setApproved(false);
            })
          }
        >
          Оценить стоимость
        </button>
        {quote && (
          <div className="story-plan-quote">
            <p>
              PiAPI · {LLM_MODELS[model].label} · верхняя оценка ${quote.estimated_usd.toFixed(6)} · до 2000
              выходных токенов.
            </p>
            <label>
              <input type="checkbox" checked={approved} onChange={e => setApproved(e.target.checked)} />
              Подтверждаю платный запрос в пределах указанной оценки
            </label>
            <button
              disabled={!approved || dirty}
              onClick={() =>
                void perform(async () => {
                  const confirmed = quote;
                  setQuote(null);
                  setApproved(false);
                  const result: Suggestion = await call(path + '/suggest', {
                    plan_revision: saved.revision,
                    model,
                    approved: true,
                    quote_token: confirmed.quote_token,
                    max_cost_usd: confirmed.estimated_usd,
                    request_id: crypto.randomUUID(),
                  });
                  setSuggestions(s => [result, ...s]);
                  setNotice('Ответ сохранён. Выбери карточки для добавления в план.');
                })
              }
            >
              Оплатить и получить предложения
            </button>
          </div>
        )}
        {suggestions.map(s => (
          <div key={s.request_id} className="story-plan-suggestion">
            <p>
              Запрос {s.request_id.slice(0, 8)} · версия плана {s.plan_revision} ·{' '}
              {s.status === 'pending'
                ? 'Ожидается ответ; повтор не отправляй'
                : s.status === 'done'
                  ? 'Предложения готовы'
                  : 'Требуется проверка'}
              {s.data.cost_usd !== undefined && ` · $${s.data.cost_usd.toFixed(6)}`}
            </p>
            {s.data.error && <p role="alert">{s.data.error}</p>}
            {s.data.cards?.map(c => (
              <label key={c.id} className="story-plan-proposal">
                <input
                  type="checkbox"
                  checked={selected.includes(c.id)}
                  onChange={e =>
                    setSelected(old => (e.target.checked ? [...old, c.id] : old.filter(id => id !== c.id)))
                  }
                />
                <span>
                  <b>{c.title}</b>
                  <br />
                  {c.summary}
                  {c.change && (
                    <>
                      <br />
                      Изменение: {c.change}
                    </>
                  )}
                </span>
              </label>
            ))}
            {s.data.cards && (
              <button
                disabled={
                  !s.data.cards.some(c => selected.includes(c.id)) ||
                  draft.cards.length + s.data.cards.filter(c => selected.includes(c.id)).length > 100
                }
                onClick={() => {
                  const cards = s.data.cards!.filter(
                    c => selected.includes(c.id) && !draft.cards.some(old => old.id === c.id)
                  );
                  edit({...draft, cards: [...draft.cards, ...cards]});
                  setSelected(old => old.filter(id => !cards.some(c => c.id === id)));
                }}
              >
                Добавить выбранные в план
              </button>
            )}
            {s.data.raw && (
              <details>
                <summary>Исходный ответ ИИ</summary>
                <pre>{s.data.raw}</pre>
              </details>
            )}
          </div>
        ))}
        <h3>Передать порядок в раскадровку</h3>
        <p>
          Для связанных сцен меняется только порядок. Полный сценарный текст, название и состав существующей
          сцены сохраняются. Для новых сцен используются поля карточки.
        </p>
        <button
          disabled={dirty || !draft.cards.length || !saved.revision}
          onClick={() =>
            void perform(async () => {
              setPreview(await call(path + '/preview', {plan_revision: saved.revision, board_revision: ''}));
              setKeep(false);
            })
          }
        >
          Посмотреть изменения
        </button>
        {preview && (
          <div className="story-plan-quote">
            <ol>
              {preview.order.map(c => (
                <li key={c.card_id}>
                  {c.title} · {c.new ? 'новая сцена' : 'сохранить сцену и её кадры'}
                </li>
              ))}
            </ol>
            {!!preview.remaining.length && (
              <label>
                <input type="checkbox" checked={keep} onChange={e => setKeep(e.target.checked)} />
                Оставить в конце сцены вне плана: {preview.remaining.map(s => s.title).join(', ')}
              </label>
            )}
            <button
              disabled={dirty || (!!preview.remaining.length && !keep)}
              onClick={() =>
                void perform(async () => {
                  const s: Saved = await call(path + '/apply', {...preview, keep_unplanned: keep});
                  setSaved(s);
                  setDraft(draftOf(s));
                  clearLocal(localKey);
                  setPreview(null);
                  setQuote(null);
                  setNotice('Порядок применён. Сцены и кадры доступны в раскадровке.');
                  onApplied();
                })
              }
            >
              Применить к раскадровке
            </button>
          </div>
        )}
      </fieldset>
    </div>
  );
}
