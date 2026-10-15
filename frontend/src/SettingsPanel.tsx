import type {ReactNode} from 'react';
import {Settings} from 'lucide-react';
import {PAID_LLM_ENABLED} from './api';

type Props = {
  children?: ReactNode;
  provider: 'openai' | 'piapi';
  model: string;
  busy: boolean;
  diagnostics: unknown;
  onProvider: (provider: 'openai' | 'piapi') => void;
  onModel: (model: string) => void;
  onConnections: () => void;
  onDiagnose: () => void;
};

export default function SettingsPanel({
  provider,
  model,
  busy,
  diagnostics,
  onProvider,
  onModel,
  onConnections,
  onDiagnose,
  children,
}: Props) {
  return (
    <section className="panel settings-panel">
      <div className="panel-title">
        <h2>
          <Settings size={21} /> Настройки
        </h2>
      </div>
      <h3>Резервный API</h3>
      <p className="muted">Провайдер и модель для подготовки промптов через резервный API.</p>
      {!PAID_LLM_ENABLED && (
        <p className="notice">
          Платный LLM-резерв временно отключён до настройки оценки стоимости. Основной чат доступен в студии.
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
              : ['gpt-5.6-luna', 'gpt-5.6-terra', 'gpt-5.6-sol']
            ).map(item => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </label>
      </div>
      <p className="muted">Ключи настраиваются на сервере.</p>
      <button onClick={onConnections}>Открыть подключения</button>
      {children && (
        <details className="reserve-tools">
          <summary>Резервные инструменты · промпты и фото</summary>
          <div>{children}</div>
        </details>
      )}
      <hr />
      <h3>Окружение студии</h3>
      <button className="secondary" disabled={busy} onClick={onDiagnose}>
        Проверить окружение
      </button>
      {diagnostics !== null && (
        <pre className="settings-diagnostics">{JSON.stringify(diagnostics, null, 2)}</pre>
      )}
    </section>
  );
}
