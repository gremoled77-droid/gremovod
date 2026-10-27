import {useRef, useState} from 'react';
import {apiFetch} from './api';
import VoiceLineDialog from './VoiceLineDialog';
import {addCue, archiveCue, saveCue, uploadCueFile, type SoundContext} from './soundApi';
import {DEFAULT_LEVEL, KINDS, kindLabel, levelLabel, soundLabel, type Cue, type CueKind} from './soundCues';

type Run = (fn: () => Promise<void>) => void;

function CueRow({
  ctx,
  cue,
  run,
  onChanged,
  onVoice,
}: {
  ctx: SoundContext;
  cue: Cue;
  run: Run;
  onChanged: () => void;
  onVoice: (cue: Cue) => void;
}) {
  const [text, setText] = useState(cue.text),
    [hero, setHero] = useState(cue.hero_node_id || ''),
    [level, setLevel] = useState(String(cue.level_db)),
    [start, setStart] = useState(String(cue.start_s)),
    [dur, setDur] = useState(cue.duration_s == null ? '' : String(cue.duration_s)),
    file = useRef<HTMLInputElement>(null);
  const dirty =
    text !== cue.text ||
    hero !== (cue.hero_node_id || '') ||
    Number(level) !== cue.level_db ||
    Number(start) !== cue.start_s ||
    (dur === '' ? null : Number(dur)) !== cue.duration_s;
  const voiced = ctx.voices.some(v => v.assigned.some(a => a.node_id === hero));
  const heroName = ctx.heroes.find(h => h.id === hero)?.title || '';
  return (
    <li className="snd-cue" data-kind={cue.kind}>
      <b>{kindLabel(cue.kind)}</b>
      <textarea
        rows={2}
        aria-label={`Текст: ${kindLabel(cue.kind)}`}
        value={text}
        placeholder={cue.kind === 'voice' ? 'Текст реплики' : 'Что слышно'}
        onChange={e => setText(e.target.value)}
      />
      {cue.kind === 'voice' && (
        <select aria-label="Герой реплики" value={hero} onChange={e => setHero(e.target.value)}>
          <option value="">Герой…</option>
          {ctx.heroes.map(h => (
            <option key={h.id} value={h.id}>
              {h.title}
            </option>
          ))}
        </select>
      )}
      <label>
        Уровень, дБ
        <input
          type="number"
          step="0.5"
          min="-60"
          max="12"
          value={level}
          onChange={e => setLevel(e.target.value)}
        />
      </label>
      <label>
        Смещение, с
        <input type="number" step="0.1" min="0" value={start} onChange={e => setStart(e.target.value)} />
      </label>
      <label>
        Длительность, с
        <input type="number" step="0.1" min="0" value={dur} onChange={e => setDur(e.target.value)} />
      </label>
      <small>{levelLabel(Number(level) || 0)}</small>
      {cue.url && <audio controls preload="none" src={cue.url} aria-label={cue.filename || 'Звук'} />}
      <div className="chips">
        <button
          className="primary"
          disabled={!dirty || (cue.kind === 'voice' && !hero)}
          onClick={() =>
            run(async () => {
              await saveCue(ctx.pid, cue, {
                text,
                hero_node_id: cue.kind === 'voice' ? hero || null : null,
                level_db: Number(level),
                start_s: Number(start),
                duration_s: dur === '' ? null : Number(dur),
              });
              onChanged();
            })
          }
        >
          Сохранить
        </button>
        {cue.kind === 'voice' && (
          <button
            disabled={dirty || !cue.text.trim() || !voiced}
            title={voiced ? '' : 'Сначала привяжите голос к герою на вкладке «Голоса»'}
            onClick={() => onVoice({...cue, hero_node_id: hero})}
          >
            Озвучить{heroName ? ` (${heroName})` : ''}
          </button>
        )}
        <button onClick={() => file.current?.click()}>{cue.url ? 'Заменить файл' : 'Загрузить файл'}</button>
        <input
          ref={file}
          type="file"
          accept=".mp3,.wav,.m4a,audio/*"
          hidden
          onChange={e => {
            const f = e.target.files?.[0];
            e.target.value = '';
            if (f)
              run(async () => {
                await uploadCueFile(ctx.pid, cue.id, f);
                onChanged();
              });
          }}
        />
        <button
          onClick={() =>
            run(async () => {
              await archiveCue(ctx.pid, cue.id);
              onChanged();
            })
          }
        >
          Убрать
        </button>
      </div>
    </li>
  );
}

/** Звук по кадрам: реплики, атмосфера, SFX и музыка с рекомендуемыми уровнями, файлами и озвучкой реплик. */
export default function FrameSoundTab({
  ctx,
  onChanged,
  run,
}: {
  ctx: SoundContext;
  onChanged: () => void;
  run: Run;
}) {
  const [voiceCue, setVoiceCue] = useState<Cue | null>(null);
  if (!ctx.sid) return <p className="muted">В проекте ещё нет серии. Отправьте кадры в раскадровку.</p>;
  if (!ctx.frames.length)
    return <p className="muted">В серии нет кадров. Создайте сцены и кадры на экране «Раскадровка».</p>;
  return (
    <div className="snd-frames">
      <div className="chips">
        <button
          onClick={() =>
            run(async () => {
              const response = await apiFetch(`/api/productions/${ctx.pid}/series/${ctx.sid}/sound-list`);
              if (!response.ok) throw new Error(await response.text());
              const link = document.createElement('a');
              link.href = URL.createObjectURL(await response.blob());
              link.download = 'sound-list.csv';
              link.click();
              setTimeout(() => URL.revokeObjectURL(link.href), 5000);
            })
          }
        >
          Звуковой список (CSV)
        </button>
        <small className="muted">
          Таблица дорожек для CapCut: сцена, кадр, тип, текст, уровень, смещение, файл.
        </small>
      </div>
      {ctx.frames.map(f => (
        <article key={f.frame_id} className="snd-frame">
          <header>
            <h3>
              {f.scene_number}. {f.scene} · {f.scene_number}.{f.frame_number} {f.frame}
            </h3>
            <span className="ps-badge">{soundLabel(f.cues)}</span>
          </header>
          <ul>
            {f.cues.map(c => (
              <CueRow key={c.id} ctx={ctx} cue={c} run={run} onChanged={onChanged} onVoice={setVoiceCue} />
            ))}
          </ul>
          <div className="chips" role="group" aria-label="Добавить звук">
            {KINDS.map(k => (
              <button
                key={k.id}
                title={k.hint}
                aria-label={`Добавить: ${k.label}`}
                onClick={() =>
                  run(async () => {
                    const voiced = ctx.heroes.find(h =>
                      ctx.voices.some(v => v.assigned.some(a => a.node_id === h.id))
                    );
                    const hero = k.id === 'voice' ? (voiced || ctx.heroes[0])?.id || null : null;
                    if (k.id === 'voice' && !hero)
                      throw new Error('Сначала создайте героя на экране «Персонажи»');
                    await addCue(ctx.pid, f.frame_id, {
                      kind: k.id as CueKind,
                      text: '',
                      hero_node_id: hero,
                      level_db: DEFAULT_LEVEL[k.id],
                      start_s: 0,
                      duration_s: null,
                    });
                    onChanged();
                  })
                }
              >
                ＋ {k.label}
              </button>
            ))}
          </div>
        </article>
      ))}
      {voiceCue && (
        <VoiceLineDialog
          pid={ctx.pid}
          cue={voiceCue}
          hero={ctx.heroes.find(h => h.id === voiceCue.hero_node_id)?.title || ''}
          onClose={() => setVoiceCue(null)}
          onDone={() => {
            setVoiceCue(null);
            onChanged();
          }}
        />
      )}
    </div>
  );
}
