import {useEffect, useRef, useState} from 'react';
import {Info, Mic, Paperclip, RotateCw, Send, Square, X} from 'lucide-react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
import LlmApprovalDialog from './LlmApprovalDialog';
import LlmCostCard from './LlmCostCard';
import {cardOf, estimateLlm, runLlm, type LlmQuote, type Msg} from './llmAsk';
import type {LlmCard} from './llmDisplay';
import {IDEA_LLM_MODELS, ideaEstimate} from './llmPricing';
import {initialLimit} from './spendLimit';

type Asset = {id: string; url: string; thumbnail_url?: string | null; metadata?: {original_name?: string}};

const SYSTEM =
  'Ты сценарист-помощник мультсериала про таксиста Грэма (ВАЗ-2106, Минск). По заданию режиссёра составь компактный план ролика на русском: логлайн, настроение, 4-6 кадров (что в кадре, камера, свет), реплики героев. Без вступлений и пояснений.';

/** Сценарный фон: выжимка из skills/gremovod-screenplay, её отдаёт бэкенд. */
type Background = {text: string; chars: number; topics: string[]};
const BACKGROUND_KEY = 'studio:idea-background:v1';
const backgroundOn = () => {
  try {
    return localStorage.getItem(BACKGROUND_KEY) !== 'off';
  } catch {
    return true;
  }
};

type Recognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((e: any) => void) | null;
  onerror: ((e: any) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};
const speechCtor = (): (new () => Recognition) | null => {
  const w = window as any;
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
};

/** Экран «Идея»: задание, отправка в LLM, голосовой ввод, результат с перегенерацией и референсами. */
export default function IdeaBrief({
  projectId,
  brief,
  onBrief,
  result,
  onResult,
  model,
  onModel,
  refs,
  onRefs,
  world,
  onNext,
  onScene,
}: {
  projectId: string;
  brief: string;
  onBrief: (v: string) => void;
  result: string;
  onResult: (v: string) => void;
  model: string;
  onModel: (v: string) => void;
  refs: string[];
  onRefs: (ids: string[]) => void;
  world: string;
  onNext: () => void;
  onScene: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [listening, setListening] = useState(false);
  const [quote, setQuote] = useState<LlmQuote | null>(null);
  const [card, setCard] = useState<LlmCard | null>(null);
  const [approved, setApproved] = useState(false);
  const [limit, setLimit] = useState('');
  const [highOk, setHighOk] = useState(false);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [background, setBackground] = useState<Background | null>(null);
  const [useBackground, setUseBackground] = useState(backgroundOn);
  const [bgInfo, setBgInfo] = useState(false);
  const area = useRef<HTMLTextAreaElement>(null);
  const resultArea = useRef<HTMLTextAreaElement>(null);
  const files = useRef<HTMLInputElement>(null);
  const rec = useRef<Recognition | null>(null);
  const base = useRef('');
  const Speech = speechCtor();
  const micOk = !!Speech && window.isSecureContext;

  const grow = (el: HTMLTextAreaElement | null) => {
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = el.scrollHeight + (el.offsetHeight - el.clientHeight) + 'px';
  };
  useEffect(() => grow(area.current), [brief]);
  useEffect(() => grow(resultArea.current), [result, busy]);
  useEffect(() => {
    if (!refs.length || !projectId) return setAssets([]);
    void apiFetch('/api/library?project_id=' + encodeURIComponent(projectId))
      .then(r => (r.ok ? r.json() : []))
      .then((list: Asset[]) => setAssets(list.filter(a => refs.includes(a.id))))
      .catch(() => undefined);
  }, [refs, projectId]);
  useEffect(() => () => rec.current?.stop(), []);
  useEffect(() => {
    void apiFetch('/api/idea/background')
      .then(r => (r.ok ? r.json() : null))
      .then((v: Background | null) => setBackground(v && v.text ? v : null))
      .catch(() => setBackground(null));
  }, []);
  const withBackground = useBackground && !!background;
  const toggleBackground = (on: boolean) => {
    setUseBackground(on);
    try {
      localStorage.setItem(BACKGROUND_KEY, on ? 'on' : 'off');
    } catch {
      /* настройка живёт до перезагрузки */
    }
  };

  const messages = (): Msg[] => [
    {
      role: 'system',
      content:
        SYSTEM +
        (withBackground ? '\n\n' + background!.text : '') +
        (world.trim() ? '\nМир проекта: ' + world.trim() : ''),
    },
    {role: 'user', content: brief.trim()},
  ];
  const chars = messages().reduce((n, m) => n + m.content.length, 0);
  const price = ideaEstimate(model, chars);
  const backgroundCost = background ? ideaEstimate(model, background.chars + 2) - ideaEstimate(model, 2) : 0;

  /** Шаг 1: оценка с сервера — она же карточка и основа окна подтверждения. */
  const prepare = async () => {
    setError('');
    if (!brief.trim()) return setError('Сначала напиши задание ролика');
    if (!projectId) return setError('Сначала сохрани проект');
    setBusy(true);
    try {
      const q = await estimateLlm(projectId, model, messages(), 'editorial');
      setQuote(q);
      setCard(null);
      setApproved(false);
      setHighOk(false);
      setLimit(initialLimit(q.actual.max_cost_usd ?? q.usd));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  /** Шаг 2: запуск после согласия владельца. Итог — карточка от сервера. */
  const generate = async () => {
    if (!quote) return;
    setBusy(true);
    setError('');
    try {
      const result = await runLlm(quote, Number(limit) || undefined);
      const text = result.text.trim();
      if (!text) throw new Error('LLM вернул пустой ответ');
      setCard(result.card);
      setQuote(null);
      onResult(text);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const toggleMic = () => {
    if (listening) return rec.current?.stop();
    if (!Speech) return;
    const r = new Speech();
    r.lang = 'ru-RU';
    r.continuous = true;
    r.interimResults = true;
    base.current = brief ? brief.replace(/\s+$/, '') + ' ' : '';
    r.onresult = e => {
      let text = '';
      for (let i = 0; i < e.results.length; i++) text += e.results[i][0].transcript;
      onBrief(base.current + text);
    };
    r.onerror = e => {
      setError(
        e.error === 'not-allowed' ? 'Нет доступа к микрофону' : 'Не удалось распознать речь: ' + e.error
      );
      setListening(false);
    };
    r.onend = () => setListening(false);
    rec.current = r;
    setListening(true);
    r.start();
  };

  const attach = async (list: FileList | null) => {
    if (!list?.length || !projectId) return;
    setError('');
    try {
      const ids: string[] = [];
      for (const file of Array.from(list)) {
        const form = new FormData();
        form.append('project_id', projectId);
        form.append('file', file);
        const asset: Asset = await responseJson(
          await apiFetch('/api/library/import-reference', {method: 'POST', body: form})
        );
        ids.push(asset.id);
      }
      onRefs([...refs, ...ids]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const actions = (
    <div className="idea-brief-actions">
      {result && <button onClick={() => onBrief(result)}>Принять как задание</button>}
      {result && (
        <button onClick={() => void prepare()} disabled={busy} title="Повторный запрос в LLM">
          <RotateCw size={14} /> Обновить
        </button>
      )}
      <button className="primary" onClick={onNext}>
        Дальше: мир и герои →
      </button>
      <button onClick={onScene}>Собрать сцену из исходников</button>
    </div>
  );

  return (
    <section className="idea-brief">
      <div className="idea-head">
        <span className="idea-n">1</span>
        <div>
          <h2>Задание ролика</h2>
          <small>Кто, где, что происходит и какое настроение. Можно надиктовать голосом.</small>
        </div>
      </div>
      <textarea
        ref={area}
        rows={3}
        value={brief}
        placeholder="Например: тизер про Грэма, первые кадры рядом с авто"
        onChange={e => onBrief(e.target.value)}
      />
      <div className="idea-send">
        <small className="muted">
          {brief.trim() ? `≈ до $${price.toFixed(4)} (предпросмотр, итог — с сервера)` : ''}
        </small>
        <label
          className={'idea-bg' + (withBackground ? ' on' : '')}
          title={background ? 'Сценарные правила уходят в LLM скрытым фоном' : 'Сценарный фон недоступен'}
        >
          <input
            type="checkbox"
            checked={withBackground}
            disabled={!background}
            onChange={e => toggleBackground(e.target.checked)}
          />
          Сценарный фон
        </label>
        <button
          type="button"
          className="idea-bg-info"
          aria-expanded={bgInfo}
          aria-label="Что входит в сценарный фон"
          onClick={() => setBgInfo(v => !v)}
        >
          <Info size={15} />
        </button>
        <select value={model} onChange={e => onModel(e.target.value)} aria-label="Модель LLM">
          {Object.entries(IDEA_LLM_MODELS).map(([id, m]) => (
            <option key={id} value={id}>
              {m.label}
            </option>
          ))}
        </select>
        <button
          className={'idea-mic' + (listening ? ' on' : '')}
          onClick={toggleMic}
          disabled={!micOk}
          aria-label={listening ? 'Остановить запись' : 'Надиктовать голосом'}
          title={
            micOk
              ? listening
                ? 'Остановить запись'
                : 'Надиктовать голосом (русский)'
              : 'Голосовой ввод работает в Chrome/Safari на localhost или по https'
          }
        >
          {listening ? <Square size={16} /> : <Mic size={18} />}
        </button>
        <button className="primary idea-go" onClick={() => void prepare()} disabled={busy}>
          <Send size={15} /> {busy ? 'Думаю…' : 'Отправить в LLM'}
        </button>
      </div>
      {bgInfo && background && (
        <p className="idea-bg-note muted">
          Учтено: {background.topics.join(' · ')}. Выжимка из skills/gremovod-screenplay, {background.chars}{' '}
          символов
          {withBackground
            ? `, добавляет к запросу ≈ $${backgroundCost.toFixed(4)}.`
            : `; выключена, добавила бы ≈ $${backgroundCost.toFixed(4)}.`}
        </p>
      )}
      {error && !quote && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}

      {result || busy ? (
        <div className="idea-result">
          <div className="idea-result-bar">
            <b>Результат</b>
            <div>
              <button
                onClick={() => files.current?.click()}
                title="Файл уйдёт на экраны «Мир» и «Раскадровка»"
              >
                <Paperclip size={14} /> Прикрепить референс
              </button>
              <input
                ref={files}
                type="file"
                accept="image/*"
                multiple
                hidden
                onChange={e => {
                  void attach(e.target.files);
                  e.target.value = '';
                }}
              />
            </div>
          </div>
          <textarea
            ref={resultArea}
            value={busy ? 'LLM пишет план…' : result}
            readOnly={busy}
            onChange={e => onResult(e.target.value)}
          />
          {assets.length > 0 && (
            <div className="idea-refs" aria-label="Референсы">
              {assets.map(a => (
                <span key={a.id}>
                  <img src={a.thumbnail_url || a.url} alt={a.metadata?.original_name || 'Референс'} />
                  <button aria-label="Открепить" onClick={() => onRefs(refs.filter(x => x !== a.id))}>
                    <X size={12} />
                  </button>
                </span>
              ))}
              <small className="muted">Уйдут на «Мир» и «Раскадровку»</small>
            </div>
          )}
          {card && <LlmCostCard card={card} title="Вызов LLM" />}
          {actions}
        </div>
      ) : (
        actions
      )}
      {quote && (
        <LlmApprovalDialog
          card={cardOf(quote)}
          title="Подтверждение платного вызова LLM"
          total={quote.actual.max_cost_usd ?? quote.usd}
          limit={limit}
          onLimit={setLimit}
          highConfirmed={highOk}
          onHighConfirmed={setHighOk}
          approved={approved}
          onApproved={setApproved}
          busy={busy}
          error={error}
          onConfirm={() => void generate()}
          onClose={() => setQuote(null)}
        />
      )}
    </section>
  );
}
