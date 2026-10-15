import { useEffect, useMemo, useRef, useState } from "react";
import { apiFetch } from "./api";
import GenerationReview, { type GenerationRequest } from "./GenerationReview";
import useActivity, { type ActivityItem } from "./useActivity";

type OptionSpec = {
  values?: (string | number)[];
  default?: string | number;
  min?: number;
  max?: number;
};
type Spec = {
  kind: string;
  launch_enabled?: boolean;
  prompt_only?: boolean;
  options?: Record<string, OptionSpec>;
  variants?: Record<string, unknown>;
  api_refs?: number;
};
type LibAsset = {
  id: string;
  url: string;
  thumbnail_url: string | null;
  provider_reference_url?: string | null;
  metadata: { kind?: string; favorite?: boolean };
};
type Hero = { id: string; name: string };

const LABELS: Record<string, string> = {
  "seedream-5-pro": "Seedream 5 Pro",
  "seedream-5-lite": "Seedream 5 Fast",
  "gpt-image-2": "GPT Image 2.0",
  "gpt-image-2.5": "GPT Image 2.5",
  "nano-banana-2.1": "Nano Banana 2.1",
  "qwen-image-2.1": "Qwen Image 2.1",
};
const ORDER = Object.keys(LABELS);

async function json(r: Response) {
  const d = await r.json().catch(() => ({}));
  if (!r.ok)
    throw Error(typeof d.detail === "string" ? d.detail : "Запрос не выполнен");
  return d;
}

export default function CreateScreen({
  projectId,
  heroes,
}: {
  projectId: string;
  heroes: Hero[];
}) {
  const { items, error: feedError, reset } = useActivity(projectId);
  const [specs, setSpecs] = useState<Record<string, Spec>>({});
  const [library, setLibrary] = useState<LibAsset[]>([]);
  const [prompt, setPrompt] = useState("");
  const [selected, setSelected] = useState<string[]>(["seedream-5-lite"]);
  const [options, setOptions] = useState<
    Record<string, Record<string, string | number>>
  >({});
  const [refs, setRefs] = useState<string[]>([]);
  const [queue, setQueue] = useState<GenerationRequest[]>([]);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const [pasteFor, setPasteFor] = useState("");

  const loadLibrary = async () => {
    if (projectId)
      setLibrary(
        await json(
          await apiFetch(
            "/api/library?project_id=" + encodeURIComponent(projectId),
          ),
        ),
      );
  };
  useEffect(() => {
    void (async () => {
      try {
        setSpecs(await json(await apiFetch("/api/model-specs")));
      } catch (e) {
        setError(String(e));
      }
    })();
  }, []);
  useEffect(() => {
    void loadLibrary().catch((e) => setError(String(e)));
  }, [projectId, items.length]);

  const models = ORDER.filter((id) => specs[id]);
  const optionValue = (model: string, key: string, spec: OptionSpec) =>
    options[model]?.[key] ?? (spec.default as string | number);
  const byId = useMemo(
    () => Object.fromEntries(library.map((a) => [a.id, a])),
    [library],
  );
  const images = library.filter(
    (a) => (a.metadata.kind || "image") === "image",
  );

  const toggle = (id: string) =>
    setSelected((s) =>
      s.includes(id) ? s.filter((x) => x !== id) : [...s, id],
    );

  const ensureCloudUrl = async (assetId: string) => {
    const a = byId[assetId];
    if (a?.provider_reference_url) return a.provider_reference_url;
    const r = await json(
      await apiFetch(`/api/library/${assetId}/upload-reference`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved: true, provider: "tempfile" }),
      }),
    );
    return r.url as string;
  };

  const start = async () => {
    setError("");
    if (!prompt.trim()) return setError("Напиши промпт");
    const apiModels = selected;
    if (!apiModels.length) return setError("Выбери хотя бы одну модель");
    setBusy(true);
    try {
      const urls = await Promise.all(refs.map(ensureCloudUrl));
      setQueue(
        apiModels.map((model) => ({
          project_id: projectId,
          model_id: model,
          prompt,
          options: Object.fromEntries(
            Object.entries(specs[model]?.options || {}).map(([k, s]) => [
              k,
              optionValue(model, k, s),
            ]),
          ) as Record<string, string | number>,
          reference_urls: urls,
        })),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const external = async () => {
    setError("");
    if (!prompt.trim()) return setError("Напиши промпт");
    try {
      const target = selected.find((id) => specs[id]) || "gpt-image-2.5";
      const job = await json(
        await apiFetch("/api/external-jobs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            project_id: projectId,
            request_id: crypto.randomUUID().replace(/-/g, ""),
            target,
            prompt,
            service: "chatgpt",
            references: refs.map((asset_id, i) => ({
              asset_id,
              role: i === 0 ? "главный референс" : "референс",
            })),
          }),
        }),
      );
      await navigator.clipboard
        .writeText(job.copy_text || prompt)
        .catch(() => undefined);
      setNotice(
        "Промпт скопирован. Сгенерируй в ChatGPT и верни картинку кнопкой «Вставить результат».",
      );
      reset();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const attach = async (jobId: string, file: File) => {
    try {
      const form = new FormData();
      form.append("file", file);
      await json(
        await apiFetch(`/api/external-jobs/${jobId}/result`, {
          method: "POST",
          body: form,
        }),
      );
      setPasteFor("");
      reset();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  useEffect(() => {
    if (!pasteFor) return;
    const onPaste = (ev: ClipboardEvent) => {
      const file = Array.from(ev.clipboardData?.files || []).find((f) =>
        f.type.startsWith("image/"),
      );
      if (file) void attach(pasteFor, file);
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [pasteFor]);

  const favorite = async (id: string, on: boolean) => {
    try {
      await json(
        await apiFetch(`/api/library/${id}/favorite`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ favorite: on }),
        }),
      );
      await loadLibrary();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const toHero = async (assetId: string, characterId: string) => {
    try {
      await json(
        await apiFetch(`/api/library/${assetId}/to-character`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            project_id: projectId,
            character_id: characterId,
          }),
        }),
      );
      setNotice("Добавлено в референсы персонажа");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const regenerate = (item: ActivityItem) => {
    setPrompt(item.prompt);
    if (specs[item.model]) setSelected([item.model]);
    setNotice(
      "Промпт и модель подставлены. Нажми «Создать», чтобы отправить повторно.",
    );
  };

  const waiting = items.filter((i) => i.status === "waiting_external");
  const results = items.filter(
    (i) => i.kind === "image" && i.status !== "waiting_external",
  );

  return (
    <section className="panel create-screen">
      <h2>Создать</h2>
      {notice && (
        <div className="notice" role="status">
          {notice}
        </div>
      )}
      {(error || feedError) && (
        <div className="alert" role="alert">
          {error || feedError}
        </div>
      )}

      <label>
        Промпт
        <textarea
          rows={4}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />
      </label>

      <h3>Референсы из библиотеки</h3>
      <div className="chips">
        {images.slice(0, 40).map((a) => (
          <button
            key={a.id}
            className={refs.includes(a.id) ? "active" : ""}
            onClick={() =>
              setRefs((r) =>
                r.includes(a.id) ? r.filter((x) => x !== a.id) : [...r, a.id],
              )
            }
            title={a.id}
          >
            <img src={a.thumbnail_url || a.url} alt="" width={56} height={56} />
          </button>
        ))}
        {!images.length && (
          <span className="muted">В библиотеке пока нет изображений</span>
        )}
      </div>

      <h3>Модели</h3>
      <div className="chips">
        {models.map((id) => (
          <label key={id} className="inline-checkbox">
            <input
              type="checkbox"
              checked={selected.includes(id)}
              onChange={() => toggle(id)}
            />{" "}
            {LABELS[id]}
            {specs[id].launch_enabled === false && (
              <span className="muted"> · проверяется</span>
            )}
          </label>
        ))}
      </div>
      {selected.map((id) => {
        const o = specs[id]?.options;
        if (!o) return null;
        return (
          <fieldset key={id}>
            <legend>{LABELS[id]}</legend>
            {Object.entries(o).map(([key, s]) =>
              s.values ? (
                <label key={key}>
                  {key}
                  <select
                    value={String(optionValue(id, key, s))}
                    onChange={(e) =>
                      setOptions((p) => ({
                        ...p,
                        [id]: { ...p[id], [key]: e.target.value },
                      }))
                    }
                  >
                    {s.values.map((v) => (
                      <option key={String(v)} value={String(v)}>
                        {String(v)}
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <label key={key}>
                  {key}
                  <input
                    type="number"
                    min={s.min}
                    max={s.max}
                    value={Number(optionValue(id, key, s))}
                    onChange={(e) =>
                      setOptions((p) => ({
                        ...p,
                        [id]: { ...p[id], [key]: Number(e.target.value) },
                      }))
                    }
                  />
                </label>
              ),
            )}
          </fieldset>
        );
      })}

      <div className="chips">
        <button
          className="primary"
          disabled={busy || !projectId}
          onClick={start}
        >
          {busy ? "Готовлю…" : "Создать"}
        </button>
        <button disabled={!projectId} onClick={external}>
          Скопировать для ChatGPT
        </button>
      </div>

      {waiting.length > 0 && (
        <>
          <h3>Ждут картинку из ChatGPT</h3>
          {waiting.map((j) => (
            <div key={j.id} className="chips">
              <span>{j.prompt.slice(0, 60)}…</span>
              <button
                onClick={() => {
                  setPasteFor(j.id);
                  fileInput.current?.click();
                }}
              >
                Выбрать файл
              </button>
              <button
                className={pasteFor === j.id ? "active" : ""}
                onClick={() => setPasteFor(j.id)}
              >
                {pasteFor === j.id
                  ? "Ctrl+V — вставь картинку"
                  : "Вставить результат"}
              </button>
            </div>
          ))}
          <input
            ref={fileInput}
            type="file"
            accept="image/*"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f && pasteFor) void attach(pasteFor, f);
              e.target.value = "";
            }}
          />
        </>
      )}

      <h3>Результаты</h3>
      <div className="create-grid">
        {results.map((item) => (
          <article key={item.id} className="panel">
            <b>{LABELS[item.model] || item.model}</b>{" "}
            <span className="muted">{item.status}</span>
            <div>
              {item.asset_ids.map((aid) => {
                const a = byId[aid];
                return a ? (
                  <div key={aid}>
                    <img
                      src={a.thumbnail_url || a.url}
                      alt=""
                      style={{ maxWidth: "100%" }}
                    />
                    <div className="chips">
                      <button onClick={() => regenerate(item)}>
                        ↻ Перегенерировать
                      </button>
                      <button
                        onClick={() => favorite(aid, !a.metadata.favorite)}
                      >
                        {a.metadata.favorite ? "♥" : "♡"}
                      </button>
                      <select
                        value=""
                        onChange={(e) =>
                          e.target.value && toHero(aid, e.target.value)
                        }
                      >
                        <option value="">В референсы ▾</option>
                        {heroes.map((h) => (
                          <option key={h.id} value={h.id}>
                            {h.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                ) : null;
              })}
            </div>
          </article>
        ))}
        {!results.length && (
          <span className="muted">Здесь появятся результаты</span>
        )}
      </div>

      {queue[0] && (
        <GenerationReview
          request={queue[0]}
          onClose={() => setQueue([])}
          onSubmitted={() => {
            setQueue((q) => q.slice(1));
            reset();
          }}
        />
      )}
    </section>
  );
}
