/** Сцена проекта: исходники (герой, локация, предметы) и промпты по моделям. Хранится в состоянии проекта. */
export type Scene = {
  brief: string;
  assets: {asset_id: string; role: string; note: string}[];
  target: string;
  prompts: Record<string, string>;
  cameraPromptBasis?: Record<string, string>;
  compositionPromptBasis?: Record<string, string>;
};
export const EMPTY_SCENE: Scene = {brief: '', assets: [], target: 'gpt-image-2.5', prompts: {}};
