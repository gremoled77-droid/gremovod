import {useState} from 'react';
import {
  addVoice,
  archiveVoice,
  assignVoice,
  MODELS,
  PROVIDER_LABEL,
  type Hero,
  type Provider,
  type Voice,
} from './soundApi';
import {voiceIdOk} from './soundCues';

const PLACEHOLDER: Record<Provider, string> = {
  elevenlabs: 'Например: Xb7hH8MSUJpSbSDYk0k2',
  fish: 'Например: 8c2a1f0b3e4d4b8a9c7d6e5f4a3b2c1d',
};

function Column({
  provider,
  pid,
  voices,
  heroes,
  onChanged,
  run,
}: {
  provider: Provider;
  pid: string;
  voices: Voice[];
  heroes: Hero[];
  onChanged: () => void;
  run: (fn: () => Promise<void>) => void;
}) {
  const [name, setName] = useState(''),
    [voiceId, setVoiceId] = useState(''),
    [model, setModel] = useState(MODELS[provider][0]),
    [url, setUrl] = useState(''),
    [note, setNote] = useState('');
  const idBad = voiceId.trim() !== '' && !voiceIdOk(voiceId);
  return (
    <div className="snd-col" aria-label={PROVIDER_LABEL[provider]}>
      <h3>{PROVIDER_LABEL[provider]}</h3>
      {voices.length === 0 && <p className="muted">Голосов пока нет.</p>}
      {voices.map(v => (
        <article key={v.id} className="snd-voice">
          <b>{v.name}</b>
          <small>
            ID {v.voice_id} · {v.model}
          </small>
          {v.note && <small>{v.note}</small>}
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
          <div className="snd-row">
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
          </div>
        </article>
      ))}
      <fieldset className="snd-add">
        <legend>Добавить по ID</legend>
        <input
          value={name}
          placeholder="Название голоса"
          aria-label="Название голоса"
          onChange={e => setName(e.target.value)}
        />
        <input
          value={voiceId}
          placeholder={PLACEHOLDER[provider]}
          aria-label="Voice ID"
          aria-invalid={idBad}
          onChange={e => setVoiceId(e.target.value)}
        />
        {idBad && <small role="alert">Только латиница, цифры, «_» и «-»</small>}
        <select value={model} aria-label="Модель озвучки" onChange={e => setModel(e.target.value)}>
          {MODELS[provider].map(m => (
            <option key={m}>{m}</option>
          ))}
        </select>
        <input
          value={url}
          placeholder="Ссылка на голос (необязательно, https)"
          aria-label="Ссылка"
          onChange={e => setUrl(e.target.value)}
        />
        <input
          value={note}
          placeholder="Заметка"
          aria-label="Заметка"
          onChange={e => setNote(e.target.value)}
        />
        <button
          className="primary"
          disabled={!name.trim() || !voiceIdOk(voiceId)}
          onClick={() =>
            run(async () => {
              await addVoice(pid, {
                provider,
                name: name.trim(),
                voice_id: voiceId.trim(),
                model,
                url: url.trim(),
                note: note.trim(),
              });
              setName('');
              setVoiceId('');
              setUrl('');
              setNote('');
              onChanged();
            })
          }
        >
          Добавить голос
        </button>
      </fieldset>
    </div>
  );
}

/** Библиотека голосов: две колонки по сервисам, добавление по ID и привязка к героям. */
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
  return (
    <div className="snd-voices">
      {(['elevenlabs', 'fish'] as const).map(p => (
        <Column
          key={p}
          provider={p}
          pid={pid}
          voices={voices.filter(v => v.provider === p)}
          heroes={heroes}
          onChanged={onChanged}
          run={run}
        />
      ))}
      <p className="muted snd-note">
        Ключи ElevenLabs и Fish Audio хранятся в «Подключениях». Привязанный голос становится голосом героя:
        реплики озвучиваются им, расход считается до запуска и требует подтверждения.
      </p>
    </div>
  );
}
