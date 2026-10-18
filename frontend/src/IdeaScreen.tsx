import type {ReactNode} from 'react';
import type {Mode} from './screens';

type Step = {key: string; title: string; done: boolean; note: string; action: string; mode?: Mode};

/**
 * Экран «Идея» в новом дизайне: слева задание ролика и мир из задания, справа «Что дальше»
 * по реальному состоянию проекта. Доска сюжета по карточкам — свёрнутым блоком внизу.
 */
export default function IdeaScreen({
  brief,
  world,
  storyBoard,
  briefText,
  worldFilled,
  worldTotal,
  heroes,
  onMode,
}: {
  /** Карточка «Задание ролика» (IdeaBrief). */
  brief: ReactNode;
  /** Вложения и «Составить мир (GPT)». */
  world: ReactNode;
  /** Доска сюжета серии (нужен проект раскадровки). */
  storyBoard: ReactNode;
  briefText: string;
  worldFilled: number;
  worldTotal: number;
  heroes: number;
  onMode: (m: Mode) => void;
}) {
  const steps: Step[] = [
    {
      key: 'brief',
      title: 'Задание ролика',
      done: briefText.trim().length >= 20,
      note: briefText.trim() ? 'Записано' : 'Кто, где, что происходит, какое настроение',
      action: 'Написать',
    },
    {
      key: 'world',
      title: 'Мир',
      done: worldFilled >= Math.min(4, worldTotal),
      note: `Заполнено полей: ${worldFilled} из ${worldTotal}`,
      action: 'Открыть мир',
      mode: 'styles',
    },
    {
      key: 'heroes',
      title: 'Персонажи',
      done: heroes > 0,
      note: heroes ? `Героев: ${heroes}` : 'Пока нет ни одного героя',
      action: 'К героям',
      mode: 'characters',
    },
    {
      key: 'board',
      title: 'Раскадровка',
      done: false,
      note: 'Сцены и кадры эпизода',
      action: 'К раскадровке',
      mode: 'storyboard',
    },
  ];
  const next = steps.find(s => !s.done) || steps[steps.length - 1];
  const go = (s: Step) =>
    s.mode
      ? onMode(s.mode)
      : (document.querySelector<HTMLTextAreaElement>('[data-prompt]')?.focus(), undefined);
  return (
    <div className="idea-screen">
      <div className="idea-col">
        {brief}
        <section className="idea-card" aria-label="Мир из задания">
          <div className="idea-head">
            <span className="idea-n">2</span>
            <div>
              <h2>Мир из задания</h2>
              <small>Прикрепи героев и референсы, затем LLM составит стиль мира по заданию.</small>
            </div>
          </div>
          {world}
        </section>
        <details className="idea-card idea-story">
          <summary>
            <b>Сюжет серии по карточкам</b>
            <small>одна карточка — одна сцена; переносится в раскадровку</small>
          </summary>
          {storyBoard}
        </details>
      </div>
      <aside className="idea-next" aria-label="Что дальше">
        <h3>Что дальше</h3>
        <ol>
          {steps.map(s => (
            <li key={s.key} className={(s.done ? 'done' : '') + (s === next ? ' now' : '')}>
              <span className="idea-next-mark" aria-hidden="true">
                {s.done ? '✓' : ''}
              </span>
              <span>
                <b>{s.title}</b>
                <small>{s.note}</small>
              </span>
            </li>
          ))}
        </ol>
        <button className="primary" onClick={() => go(next)}>
          {next.action} →
        </button>
        <small className="muted">
          <kbd>/</kbd> — курсор в задание, <kbd>Alt</kbd> + <kbd>2</kbd> — «Мир», <kbd>?</kbd> — все клавиши.
        </small>
      </aside>
    </div>
  );
}
