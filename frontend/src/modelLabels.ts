/** Человеческие названия моделей и видов заданий для очередей и карточек. */
export const LABELS: Record<string, string> = {
  'seedream-5-pro': 'Seedream 5 Pro',
  'seedream-5-lite': 'Seedream 5 Lite',
  'seedream-5-lite-less-restriction': 'Seedream 5 Lite · less restriction',
  'seedream-5-pro-less-restriction': 'Seedream 5 Pro · less restriction',
  'gpt-image-2': 'GPT Image 2.0',
  'gpt-image-2.5': 'GPT Image 2.5',
  'nano-banana-2.1': 'Nano Banana 2.1',
  'qwen-image-2.1': 'Qwen Image 2.1',
};

export const KIND_LABELS: Record<string, string> = {image: 'Картинка', video: 'Видео', audio: 'Звук'};

export const modelLabel = (id: string) => LABELS[id] || id;
