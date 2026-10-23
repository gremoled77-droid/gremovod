import type {ReactNode} from 'react';
import {PAID_LLM_ENABLED} from './api';
import ArchivedProjects from './ArchivedProjects';
import ChatLinkSetting from './ChatLinkSetting';

type Props = {
  children?: ReactNode;
  service?: ReactNode;
  projectHeader?: ReactNode;
  provider: 'openai' | 'piapi';
  model: string;
  busy: boolean;
  diagnostics: unknown;
  onProvider: (provider: 'openai' | 'piapi') => void;
  onModel: (model: string) => void;
  onConnections: () => void;
  onDiagnose: () => void;
  onProjectsChanged: () => void;
};

export default function SettingsPanel({
  projectHeader,
  provider,
  model,
  busy,
  diagnostics,
  onProvider,
  onModel,
  onConnections,
  onDiagnose,
  onProjectsChanged,
  children,
  service,
}: Props) {
  const card = (icon: string, title: string, hint: string) => (
    <div className="rf-head">
      <span className="stg-ico" aria-hidden="true">
        {icon}
      </span>
      <div>
        <h3>{title}</h3>
        <small>{hint}</small>
      </div>
    </div>
  );
  return (
    <section className="sc stg">
      {projectHeader && (
        <article className="sc-step">
          {card('◆', 'Проект', 'Название и сохранение')}
          {projectHeader}
        </article>
      )}
      <article className="sc-step">
        {card('✎', 'Модель для промптов', 'Резервный API: провайдер и модель')}
        {!PAID_LLM_ENABLED && (
          <p className="notice">
            Платный LLM-резерв временно отключён до настройки оценки стоимости. Основной чат доступен в
            студии.
          </p>
        )}
        <div className="param-grid">
          <label>
            LLM-провайдер
            <select
              value={provider}
              disabled={busy}
              onChange={e => onProvider(e.target.value as 'openai' | 'piapi')}
            >
              <option value="openai">OpenAI напрямую</option>
              <option value="piapi">PiAPI</option>
            </select>
          </label>
          <label>
            LLM
            <select value={model} disabled={busy} onChange={e => onModel(e.target.value)}>
              {(provider === 'openai'
                ? ['gpt-4.1-mini', 'gpt-4.1', 'gpt-5-mini']
                : ['gpt-5.6-luna', 'gpt-5.6-terra', 'gpt-5.6-sol', 'gpt-6-astra']
              ).map(item => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>
        </div>
        <div className="rf-actions">
          <button onClick={onConnections}>Открыть подключения</button>
          <small className="muted">Ключи настраиваются на сервере.</small>
        </div>
      </article>
      <article className="sc-step">
        {card('☁', 'Чат ChatGPT', 'Ссылка для кнопки «Отправить в ChatGPT»')}
        <ChatLinkSetting />
      </article>
      <article className="sc-step">
        {card('▤', 'Архив проектов', 'Убранные проекты можно вернуть')}
        <ArchivedProjects onRestored={onProjectsChanged} />
      </article>
      <article className="sc-step">
        {card('⚙', 'Окружение студии', 'Проверка Python, ffmpeg и базы')}
        <div className="rf-actions">
          <button className="secondary" disabled={busy} onClick={onDiagnose}>
            Проверить окружение
          </button>
        </div>
        {diagnostics !== null && (
          <pre className="settings-diagnostics">{JSON.stringify(diagnostics, null, 2)}</pre>
        )}
      </article>
      {service && (
        <details className="sc-step reserve-tools">
          <summary>Служебное: задания API · повторить скачивание, восстановить задание</summary>
          <div>{service}</div>
        </details>
      )}
      {children && (
        <details className="sc-step reserve-tools">
          <summary>Резервные инструменты · промпты и фото</summary>
          <div>{children}</div>
        </details>
      )}
    </section>
  );
}
