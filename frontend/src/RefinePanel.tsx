import ReplaceCharacterButton, {type ReplacementControls} from './ReplaceCharacterButton';
import {useEffect, useRef, useState} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';

export type RefineDraft = {source_asset_id: string; reference_asset_id: string; instruction: string};
export const EMPTY_REFINE: RefineDraft = {source_asset_id: '', reference_asset_id: '', instruction: ''};
type Asset = {
  id: string;
  url: string;
  metadata: {
    kind?: string;
    width: number;
    height: number;
    provider: string;
    original_name?: string;
    character_status?: string;
  };
};
type EditJob = {
  id: string;
  operation: string;
  status: string;
  prompt: string;
  message: string;
  source_asset_id: string;
  reference_asset_id: string | null;
  edit_instruction: string;
  asset_id: string;
  image_url: string | null;
};
type Status = {worker_online: boolean; worker_busy: boolean; note: string; chat_url: string};

export default function RefinePanel({
  projectId,
  draft,
  onChange,
  ensureProject,
  onAsset,
  revision,
  character,
  onReplaced,
}: {
  projectId: string;
  draft: RefineDraft;
  onChange: (draft: RefineDraft) => void;
  ensureProject: () => Promise<string>;
  onAsset: () => void;
  revision: number;
} & ReplacementControls) {
  const [assets, setAssets] = useState<Asset[]>([]),
    [jobs, setJobs] = useState<EditJob[]>([]),
    [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState(''),
    [notice, setNotice] = useState(''),
    [busy, setBusy] = useState('');
  const received = useRef(new Set<string>());
  const pending = useRef<{id: string; signature: string} | null>(null);
  useEffect(() => {
    let active = true;
    setAssets([]);
    setError('');
    if (projectId)
      void apiFetch('/api/library?project_id=' + encodeURIComponent(projectId))
        .then(responseJson)
        .then(items => {
          if (active)
            setAssets(items.filter((a: Asset) => !['video', 'audio'].includes(a.metadata.kind || 'image')));
        })
        .catch(e => {
          if (active) setError(String(e));
        });
    return () => {
      active = false;
    };
  }, [projectId, revision]);
  useEffect(() => {
    let active = true;
    setJobs([]);
    const refresh = async () => {
      try {
        const s = await responseJson(await apiFetch('/api/chatgpt/status'));
        const items: EditJob[] = projectId
          ? await responseJson(
              await apiFetch('/api/chatgpt/jobs?project_id=' + encodeURIComponent(projectId))
            )
          : [];
        if (active) {
          setStatus(s);
          setJobs(items);
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
  useEffect(() => {
    for (const job of jobs)
      if (job.operation === 'edit' && job.asset_id && !received.current.has(job.asset_id)) {
        received.current.add(job.asset_id);
        onAsset();
      }
  }, [jobs, onAsset]);
  const upload = async (file: File, role: 'source_asset_id' | 'reference_asset_id') => {
    setBusy(role);
    setError('');
    setNotice('');
    try {
      const pid = await ensureProject();
      const form = new FormData();
      form.append('project_id', pid);
      form.append('file', file);
      const asset: Asset = await responseJson(
        await apiFetch('/api/library/import-image', {method: 'POST', body: form})
      );
      setAssets(items => [asset, ...items]);
      onChange({...draft, [role]: asset.id});
      onAsset();
      setNotice('Изображение прикреплено; генерация ещё не запускалась.');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy('');
    }
  };
  const submit = async () => {
    setBusy('submit');
    setError('');
    setNotice('');
    try {
      const pid = await ensureProject();
      const body = {
        project_id: pid,
        target: 'gpt-image-2.5',
        operation: 'edit',
        source_asset_id: draft.source_asset_id,
        reference_asset_id: draft.reference_asset_id || null,
        edit_instruction: draft.instruction,
      };
      const signature = JSON.stringify(body);
      if (!pending.current || pending.current.signature !== signature)
        pending.current = {id: crypto.randomUUID(), signature};
      const job = await responseJson(
        await apiFetch('/api/chatgpt/jobs', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({...body, request_id: pending.current.id}),
        })
      );
      pending.current = null;
      setJobs(items => [job, ...items.filter(j => j.id !== job.id)]);
      setNotice('Правка в очереди: улучшение промпта → редактирование оригинала → новая версия.');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy('');
    }
  };
  const active = jobs.some(j => ['queued', 'preparing', 'generating'].includes(j.status));
  const source = assets.find(a => a.id === draft.source_asset_id),
    reference = assets.find(a => a.id === draft.reference_asset_id);
  const name = (a: Asset) =>
    `${a.metadata.original_name || a.id.slice(0, 8)} · ${a.metadata.width}×${a.metadata.height}${a.metadata.character_status === 'approved' ? ' · рабочий образ' : ''}`;
  const slot = (
    n: number,
    title: string,
    hint: string,
    value: string,
    role: 'source_asset_id' | 'reference_asset_id',
    picked: Asset | undefined,
    options: Asset[],
    emptyLabel: string
  ) => (
    <article className={'rf-slot' + (picked ? ' filled' : '')}>
      <div className="rf-head">
        <span className="rf-step">{n}</span>
        <div>
          <h3>{title}</h3>
          <small>{hint}</small>
        </div>
      </div>
      <div className="rf-frame">
        {picked ? (
          <img src={picked.url} alt={title} />
        ) : (
          <div className="rf-empty">
            <b>{emptyLabel}</b>
            <span>Выбери из библиотеки или загрузи файл</span>
          </div>
        )}
      </div>
      <select value={value} onChange={e => onChange({...draft, [role]: e.target.value})}>
        <option value="">
          {role === 'source_asset_id' ? 'Выбери изображение…' : 'Без дополнительного референса'}
        </option>
        {options.map(a => (
          <option key={a.id} value={a.id}>
            {name(a)}
          </option>
        ))}
      </select>
      <div className="rf-slot-actions">
        <label className={'button rf-upload' + (busy || active ? ' disabled' : '')}>
          Загрузить файл
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            disabled={!!busy || active}
            onChange={e => {
              const f = e.target.files?.[0];
              if (f) void upload(f, role);
              e.target.value = '';
            }}
          />
        </label>
        {picked && role === 'reference_asset_id' && (
          <button onClick={() => onChange({...draft, reference_asset_id: ''})}>Убрать</button>
        )}
      </div>
    </article>
  );
  const online = !!status?.worker_online;
  return (
    <section className="rf">
      <div className="rf-bar">
        <p className={'worker-status ' + (online ? 'online' : 'offline')} role="status">
          {online
            ? status?.worker_busy
              ? '● Чат выполняет задание'
              : '● Обработчик чата подключён'
            : '○ Обработчик чата неактивен'}
        </p>
        {status && (
          <a className="button" href={status.chat_url}>
            Открыть чат ↗
          </a>
        )}
      </div>
      {!online && <p className="muted rf-note">{status?.note || 'Проверка связи…'}</p>}
      <div className="rf-slots">
        {slot(
          1,
          'Оригинал для правки',
          'Задаёт внешность и весь визуал',
          draft.source_asset_id,
          'source_asset_id',
          source,
          assets,
          'Нет оригинала'
        )}
        {slot(
          2,
          'Референс детали',
          'Необязательно: берём только нужную деталь',
          draft.reference_asset_id,
          'reference_asset_id',
          reference,
          assets.filter(a => a.id !== draft.source_asset_id),
          'Референса нет'
        )}
      </div>
      <article className="rf-instruction">
        <div className="rf-head">
          <span className="rf-step">3</span>
          <div>
            <h3>Что изменить</h3>
            <small>Одна понятная правка: что поменять и что сохранить</small>
          </div>
        </div>
        <textarea
          rows={4}
          maxLength={4000}
          value={draft.instruction}
          onChange={e => onChange({...draft, instruction: e.target.value})}
          placeholder="Например: заменить только обувь на ботинки с референса. Лицо, кепку, фигуру, одежду, позу, фон и свет сохранить."
        />
        <details>
          <summary>Что будет добавлено в промпт</summary>
          <p className="muted">
            Редактировать исходное изображение. Менять только указанную деталь; сохранять лица, идентичность
            персонажей, остальные предметы, композицию, стиль, свет и цвета. Из дополнительного референса
            брать только то, что указано в правке. Не пересоздавать картинку по старому промпту.
          </p>
        </details>
        <div className="rf-actions">
          <button
            className="primary"
            disabled={
              !!busy ||
              active ||
              !source ||
              !draft.instruction.trim() ||
              draft.source_asset_id === draft.reference_asset_id
            }
            onClick={() => void submit()}
          >
            Улучшить промпт и перегенерировать
          </button>
          <button
            disabled={!!busy}
            onClick={() => {
              setBusy('save');
              void ensureProject()
                .then(() => setNotice('Черновик правки сохранён.'))
                .catch(e => setError(String(e)))
                .finally(() => setBusy(''));
            }}
          >
            Сохранить черновик
          </button>
        </div>
        <small className="muted">
          Сохранение визуала — инструкция модели; абсолютная неизменность остальных пикселей не гарантируется.
          Точный выбор модели и качества встроенный инструмент не раскрывает. API автоматически не
          используется.
        </small>
      </article>
      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <div className="notice" role="status">
          {notice}
        </div>
      )}
      <h3 className="rf-versions">Версии правок</h3>
      <div className="native-results">
        {jobs
          .filter(j => j.operation === 'edit')
          .slice(0, 10)
          .map(j => (
            <article className="job" key={j.id}>
              <div className="jobtop">
                <b>{j.edit_instruction}</b>
                <span>
                  {
                    (
                      {
                        queued: 'В очереди',
                        preparing: 'Улучшение промпта',
                        generating: 'Редактирование',
                        completed: 'Готово',
                        failed: 'Ошибка',
                        cancelled: 'Отменено',
                      } as Record<string, string>
                    )[j.status]
                  }
                </span>
              </div>
              <p className="muted">{j.message}</p>
              {j.prompt && (
                <details>
                  <summary>Улучшенный промпт imagegen</summary>
                  <pre>{j.prompt}</pre>
                </details>
              )}
              {j.image_url && (
                <>
                  <div className="rf-compare">
                    <div>
                      <small>Исходник</small>
                      <img src={`/api/library/${j.source_asset_id}/file`} alt="Исходник версии" />
                    </div>
                    <div>
                      <small>Новая версия</small>
                      <img src={j.image_url} alt="Результат правки" />
                    </div>
                  </div>
                  <div className="chips">
                    <button
                      onClick={() =>
                        onChange({source_asset_id: j.asset_id, reference_asset_id: '', instruction: ''})
                      }
                    >
                      Взять за основу следующей правки
                    </button>
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
              {j.status === 'queued' && (
                <button
                  onClick={() => {
                    void apiFetch(`/api/chatgpt/jobs/${j.id}/cancel`, {method: 'POST'})
                      .then(responseJson)
                      .then(updated => setJobs(items => items.map(x => (x.id === j.id ? updated : x))))
                      .catch(e => setError(String(e)));
                  }}
                >
                  Отменить ожидание
                </button>
              )}
            </article>
          ))}
      </div>
    </section>
  );
}
