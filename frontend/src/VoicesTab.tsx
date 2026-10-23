import {useEffect, useRef, useState} from 'react';
import {Plus, Square, Trash2, Play} from 'lucide-react';
import {
  addVoice,
  archiveVoice,
  assignVoice,
  MODELS,
  PROVIDER_LABEL,
  type Hero,
  type Provider,
  type Voice,
  voicePreview,
} from './soundApi';
import {voiceIdOk} from './soundCues';

const MODEL_LABEL: Record<string, string> = {
  eleven_v4: 'Eleven v4',
  eleven_v3: 'Eleven v3',
  eleven_multilingual_v2: 'Eleven v2',
  's2.1-pro': 'Fish s2.1',
  's2.1-pro-free': 'Fish free',
};
const PLACEHOLDER: Record<Provider, string> = {
  elevenlabs: 'Например: Xb7hH8MSUJpSbSDYk0k2',
  fish: 'Например: 8c2a1f0b3e4d4b8a9c7d6e5f4a3b2c1d',
};

/** Окно «Добавить голос»: сначала герой, затем данные голоса. Правка уже добавленного голоса здесь не предусмотрена. */
function AddVoiceDialog({
  pid,
  heroes,
  onClose,
  onChanged,
  run,
}: {
  pid: string;
  heroes: Hero[];
  onClose: () => void;
  onChanged: () => void;
  run: (fn: () => Promise<void>) => void;
}) {
  const [hero, setHero] = useState(''),
    [provider, setProvider] = useState<Provider>('elevenlabs'),
    [name, setName] = useState(''),
    [voiceId, setVoiceId] = useState(''),
    [model, setModel] = useState(MODELS.elevenlabs[0]),
    [note, setNote] = useState(''),
    [withNote, setWithNote] = useState(false);
  const idBad = voiceId.trim() !== '' && !voiceIdOk(voiceId);
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Добавить голос">
      <section className="panel snd-dialog">
        <h3>Добавить голос</h3>
        <label>
          Персонаж
          <select value={hero} onChange={e => setHero(e.target.value)}>
            <option value="">Без привязки к персонажу</option>
            {heroes.map(h => (
              <option key={h.id} value={h.id}>
                {h.title}
              </option>
            ))}
          </select>
        </label>
        <label>
          Сервис и модель
          <select
            value={`${provider}|${model}`}
            onChange={e => {
              const [p, m] = e.target.value.split('|');
              setProvider(p as Provider);
              setModel(m);
            }}
          >
            {(['elevenlabs', 'fish'] as const).map(p => (
              <optgroup key={p} label={PROVIDER_LABEL[p]}>
                {MODELS[p].map(m => (
                  <option key={m} value={`${p}|${m}`}>
                    {m}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>
        <label>
          Название голоса
          <input
            value={name}
            placeholder="Например: Грэм, спокойный"
            onChange={e => setName(e.target.value)}
          />
        </label>
        <label>
          Voice ID
          <input
            value={voiceId}
            placeholder={PLACEHOLDER[provider]}
            aria-invalid={idBad}
            onChange={e => setVoiceId(e.target.value)}
          />
        </label>
        {idBad && <small role="alert">Только латиница, цифры, «_» и «-»</small>}
        {withNote ? (
          <label>
            Заметка
            <input
              autoFocus
              value={note}
              placeholder="Например: для спокойных сцен"
              onChange={e => setNote(e.target.value)}
            />
          </label>
        ) : (
          <button type="button" onClick={() => setWithNote(true)}>
            ＋ Заметка
          </button>
        )}
        <div className="chips">
          <button
            className="primary"
            disabled={!name.trim() || !voiceIdOk(voiceId)}
            onClick={() =>
              run(async () => {
                const added = await addVoice(pid, {
                  provider,
                  name: name.trim(),
                  voice_id: voiceId.trim(),
                  model,
                  url: '',
                  note: note.trim(),
                });
                if (hero) await assignVoice(pid, added.id, hero);
                onChanged();
                onClose();
              })
            }
          >
            Добавить голос
          </button>
          <button onClick={onClose}>Отмена</button>
        </div>
      </section>
    </div>
  );
}

/** Библиотека голосов карточками: у героя может быть несколько голосов (разные тембры). */
export default function VoicesTab({
  pid,
  voices,
  heroes,
  onChanged,
  run,
}: {
  pid: string;
  voices: Voice[];
  heroes: Hero[];
  onChanged: () => void;
  run: (fn: () => Promise<void>) => void;
}) {
  const audio = useRef<HTMLAudioElement | null>(null),
    [playing, setPlaying] = useState(''),
    [previewError, setPreviewError] = useState(''),
    [noteOpen, setNoteOpen] = useState(''),
    [menuFor, setMenuFor] = useState('');
  useEffect(() => () => audio.current?.pause(), []);
  const preview = async (v: Voice) => {
    setPreviewError('');
    if (playing === v.id) {
      audio.current?.pause();
      return setPlaying('');
    }
    audio.current?.pause();
    setPlaying(v.id);
    try {
      const player = new Audio(await voicePreview(pid, v.id));
      player.onended = () => setPlaying(p => (p === v.id ? '' : p));
      audio.current = player;
      await player.play();
    } catch (e) {
      setPlaying('');
      setPreviewError(`${v.name}: ${e instanceof Error ? e.message : String(e)}`);
    }
  };
  const [adding, setAdding] = useState(false),
    [filter, setFilter] = useState('');
  const order = (['elevenlabs', 'fish'] as const).flatMap(p => MODELS[p]);
  const present = order.filter(m => voices.some(v => v.model === m));
  const shown = voices.filter(v => !filter || v.model === filter);
  return (
    <div className="snd-voices">
      <div className="chips snd-filter" aria-label="Фильтр по модели">
        {[['', 'Все'], ...present.map(m => [m, MODEL_LABEL[m] || m])].map(([id, label]) => (
          <button
            key={id}
            className={filter === id ? 'primary' : ''}
            aria-pressed={filter === id}
            onClick={() => setFilter(id)}
          >
            {label}
          </button>
        ))}
      </div>
      {previewError && <p role="alert">{previewError}</p>}
      <div className="chars-grid">
        <button className="chars-tile chars-new" onClick={() => setAdding(true)}>
          <span>＋</span>
          <b>Добавить голос</b>
        </button>
        {shown.map(v => (
          <article key={v.id} className="snd-card">
            <div className="snd-cover">
              <span>{v.name.slice(0, 1).toUpperCase()}</span>
            </div>
            <div className="snd-body">
              <div className="snd-title">
                <b>{v.name}</b>
                {v.provider === 'elevenlabs' && (
                  <button
                    className="snd-play"
                    aria-label={playing === v.id ? 'Стоп' : 'Прослушать'}
                    aria-pressed={playing === v.id}
                    data-tip={playing === v.id ? 'Стоп' : 'Прослушать'}
                    onClick={() => void preview(v)}
                  >
                    {playing === v.id ? <Square size={14} /> : <Play size={14} />}
                  </button>
                )}
              </div>
              {(v.assigned.length > 0 || v.note) && (
                <div className="snd-tags">
                  {v.assigned.map(a => (
                    <button
                      key={a.node_id}
                      title="Снять голос с героя"
                      onClick={() =>
                        run(async () => {
                          await assignVoice(pid, v.id, a.node_id, true);
                          onChanged();
                        })
                      }
                    >
                      {a.title} ×
                    </button>
                  ))}
                  {v.note && (
                    <button
                      type="button"
                      className="snd-info"
                      aria-label="Заметка к голосу"
                      aria-expanded={noteOpen === v.id}
                      onClick={() => setNoteOpen(noteOpen === v.id ? '' : v.id)}
                    >
                      И
                    </button>
                  )}
                </div>
              )}
              {noteOpen === v.id && <small role="note">{v.note}</small>}
            </div>
            <div className="snd-actions">
              <div className="snd-menu-wrap">
                <button
                  className="snd-btn"
                  aria-label="Добавить персонажа"
                  aria-expanded={menuFor === v.id}
                  data-tip="Добавить персонажа"
                  onClick={() => setMenuFor(menuFor === v.id ? '' : v.id)}
                >
                  <Plus size={16} />
                </button>
                {menuFor === v.id && (
                  <div className="snd-menu" role="menu">
                    {heroes.filter(h => !v.assigned.some(a => a.node_id === h.id)).length === 0 && (
                      <small>Нет свободных персонажей</small>
                    )}
                    {heroes
                      .filter(h => !v.assigned.some(a => a.node_id === h.id))
                      .map(h => (
                        <button
                          key={h.id}
                          role="menuitem"
                          onClick={() => {
                            setMenuFor('');
                            run(async () => {
                              await assignVoice(pid, v.id, h.id);
                              onChanged();
                            });
                          }}
                        >
                          {h.title}
                        </button>
                      ))}
                  </div>
                )}
              </div>
              <button
                className="snd-btn"
                aria-label="Удалить"
                data-tip="Удалить"
                onClick={() => {
                  if (
                    !window.confirm(
                      `Удалить голос «${v.name}»? Он исчезнет из списка, привязки к героям останутся.`
                    )
                  )
                    return;
                  run(async () => {
                    await archiveVoice(pid, v.id);
                    onChanged();
                  });
                }}
              >
                <Trash2 size={16} />
              </button>
            </div>
          </article>
        ))}
      </div>
      <p className="muted snd-note">
        Ключи ElevenLabs и Fish Audio хранятся в «Подключениях». Герою можно привязать несколько голосов
        (разные тембры): последний привязанный становится голосом по умолчанию, при озвучке реплики можно
        выбрать другой. Правка голоса будет в отдельной вкладке.
      </p>
      {adding && (
        <AddVoiceDialog
          pid={pid}
          heroes={heroes}
          onClose={() => setAdding(false)}
          onChanged={onChanged}
          run={run}
        />
      )}
    </div>
  );
}
