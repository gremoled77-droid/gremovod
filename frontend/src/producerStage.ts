/** Этап «Продюсер»: запрос из состояния студии и структура, которая сохраняется в проект.
 *
 * Логика вынесена из компонента, чтобы её можно было проверить без React.
 * Провайдера не прибиваем: у платной модели `provider` пустой, бэкенд берёт его
 * из реестра. Локальный MOCK — единственный режим без запроса к провайдеру.
 */
import {IDEA_LLM_MODELS} from './llmPricing.ts';
import {WORLD_FIELDS} from './worldBible.ts';

export const PRODUCER_MOCK_MODEL = 'mock-producer';
export const PRODUCER_MOCK_PROVIDER = 'mock';
export const PRODUCER_DEFAULT_DURATION = 60;

export type ProducerBeat = {id: string; stage: string; summary: string};
export type ProducerScene = {
  number: number;
  title: string;
  duration_seconds: number;
  summary: string;
  character_ids: string[];
  beat_id: string;
};
export type ProducerPromptVersion = {
  stage: string;
  revision: string;
  rules_version: string;
  background_version: string;
};
export type ProducerModelInfo = {
  id: string;
  label: string;
  provider: string;
  price_in: number;
  price_out: number;
  paid: boolean;
};
export type ProducerScenario = {
  logline: string;
  beats: ProducerBeat[];
  scenes: ProducerScene[];
  assumptions: string[];
  prompt_version: ProducerPromptVersion;
  model: ProducerModelInfo;
  cost_usd: number;
  estimated_usd: number;
  external_calls: number;
  saved_at: string;
};
export type ProducerResult = Omit<ProducerScenario, 'saved_at'>;

/** Модели этапа: локальный MOCK плюс модели реестра, доступные на экране «Идея». */
export const PRODUCER_MODELS: Record<string, {label: string; mock: boolean}> = {
  [PRODUCER_MOCK_MODEL]: {label: 'Локальный MOCK (без API)', mock: true},
  ...Object.fromEntries(
    Object.entries(IDEA_LLM_MODELS).map(([id, model]) => [id, {label: model.label, mock: false}])
  ),
};

export type ProducerOptions = {
  projectId: string;
  characterIds: string[];
  durationSeconds: number;
  constraints: string;
  model: string;
  language?: string;
};
export type ProducerRequestBody = {
  project_id: string;
  idea: string;
  character_ids: string[];
  reference_ids: string[];
  world: Record<string, string>;
  duration_seconds: number;
  language: string;
  constraints: string[];
  provider: string;
  model: string;
};
export type ProducerState = {
  brief: string;
  style: Record<string, string>;
  characters: {id: string; working_asset_id?: string}[];
};

/** Паспорт мира: только заполненные поля, в порядке WORLD_FIELDS. */
export function producerWorld(style: Record<string, string> | undefined): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key] of WORLD_FIELDS) {
    const value = (style?.[key] || '').trim().replace(/\s+/g, ' ');
    if (value) out[key] = value;
  }
  return out;
}

/** Запрос этапа из состояния студии.
 *
 * В пакет уходят только выбранные персонажи и их утверждённые рабочие референсы;
 * остальной проект, картинки и история сообщений не передаются.
 */
export function producerRequest(state: ProducerState, options: ProducerOptions): ProducerRequestBody {
  const chosen = state.characters.filter(item => options.characterIds.includes(item.id));
  const duration = Math.round(options.durationSeconds);
  return {
    project_id: options.projectId,
    idea: state.brief.trim(),
    character_ids: chosen.map(item => item.id),
    reference_ids: chosen.map(item => item.working_asset_id || '').filter(Boolean),
    world: producerWorld(state.style),
    duration_seconds: duration >= 5 && duration <= 3600 ? duration : PRODUCER_DEFAULT_DURATION,
    language: options.language || 'ru',
    constraints: options.constraints
      .split('\n')
      .map(line => line.trim())
      .filter(Boolean),
    provider: options.model === PRODUCER_MOCK_MODEL ? PRODUCER_MOCK_PROVIDER : '',
    model: options.model,
  };
}

/** Ответ этапа в структуру, которая хранится в проекте. */
export function scenarioFromResult(result: ProducerResult, savedAt: string): ProducerScenario {
  return {...result, saved_at: savedAt};
}

/** Новое состояние студии со сценарной структурой: одно и то же идёт в экран и в сохранение. */
export function withScenario<T extends {scenario?: ProducerScenario}>(state: T, scenario: ProducerScenario): T {
  return {...state, scenario};
}

/** Разбор ответа этапа: без логлайна, битов или сцен результат не принимается. */
export function parseScenario(result: unknown, savedAt: string): ProducerScenario {
  const data = result as Partial<ProducerResult> | null;
  if (!data || typeof data.logline !== 'string' || !data.logline.trim())
    throw Error('Ответ этапа без логлайна');
  if (!Array.isArray(data.beats) || !data.beats.length)
    throw Error('Ответ этапа без драматургических битов');
  if (!Array.isArray(data.scenes) || !data.scenes.length) throw Error('Ответ этапа без плана сцен');
  return scenarioFromResult(data as ProducerResult, savedAt);
}
