import {useEffect, useRef, useState} from 'react';
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
          Сервис
          <select
            value={provider}
            onChange={e => {
              const next = e.target.value as Provider;
              setProvider(next);
              setModel(MODELS[next][0]);
            }}
          >
            {(['elevenlabs', 'fish'] as const).map(p => (
              <option key={p} value={p}>
                {PROVIDER_LABEL[p]}
              </option>
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
        <label>
          Модель озвучки
          <select value={model} onChange={e => setModel(e.target.value)}>
            {MODELS[provider].map(m => (
              <option key={m}>{m}</option>
            ))}
          </select>
        </label>
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
    [noteOpen, setNoteOpen] = useState('');
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
    [filter, setFilter] = useState<Provider | ''>('');
  const shown = voices.filter(v => !filter || v.provider === filter);
  return (
    <div className="snd-voices">
      <div className="chips" aria-label="Сервис голоса">
        {(
          [
            ['', 'Все'],
            ['elevenlabs', 'ElevenLabs'],
            ['fish', 'Fish Audio'],
          ] as const
        ).map(([id, label]) => (
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
          <article key={v.id} className="chars-tile snd-card">
            <span className="chars-empty">{v.name.slice(0, 1).toUpperCase()}</span>
            <b>{v.name}</b>
            <small>
              {PROVIDER_LABEL[v.provider]} · {v.model}
            </small>
            <small>ID {v.voice_id}</small>
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
            {noteOpen === v.id && <small role="note">{v.note}</small>}
            {v.provider === 'elevenlabs' && (
              <button aria-pressed={playing === v.id} onClick={() => void preview(v)}>
                {playing === v.id ? '■ Стоп' : '▶ Прослушать'}
              </button>
            )}
            <div className="chips">
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
            </div>
            <select
              aria-label={`Привязать голос ${v.name} к герою`}
              value=""
              onChange={e => {
                const hero = e.target.value;
                if (hero)
                  run(async () => {
                    await assignVoice(pid, v.id, hero);
                    onChanged();
                  });
              }}
            >
              <option value="">Привязать к герою…</option>
              {heroes
                .filter(h => !v.assigned.some(a => a.node_id === h.id))
                .map(h => (
                  <option key={h.id} value={h.id}>
                    {h.title}
                  </option>
                ))}
            </select>
            <button
              onClick={() =>
                run(async () => {
                  await archiveVoice(pid, v.id);
                  onChanged();
                })
              }
            >
              Убрать из списка
            </button>
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
