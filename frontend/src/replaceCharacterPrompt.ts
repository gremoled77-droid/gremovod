/** Промпты «Заменить героя»: в готовом кадре (картинка) и в видео (Kling Omni).
 * Основа: разбор «Промпты» (GORA ACADEMY), см. skills/video-kling-3-omni и
 * skills/video-seedance-2-0/references/character-sheet-and-storyboard.md. Платный запуск идёт обычным путём
 * «Кадров» (оценка цены и подтверждение), здесь только текст. */

export type ReplaceFrameOptions = {
  /** Оставить одежду из исходного кадра (по умолчанию да); иначе одеть героя как на его референсе. */
  keepClothing?: boolean;
};

export function buildReplaceInFramePrompt({keepClothing = true}: ReplaceFrameOptions = {}): string {
  const clothing = keepClothing
    ? 'clothing as in the original frame'
    : 'the outfit shown on the character reference (Image 2)';
  return [
    'Image 1 is the original frame. Image 2 is the identity reference of the replacement character.',
    'Replace the character in Image 1 with the character from Image 2, using Image 2 as the only source of their identity.',
    `Keep from Image 1 exactly: camera angle, head position, facial expression, gaze direction, body pose, ${clothing}, lighting, shadows, color tone, cinematic atmosphere and the whole background and composition.`,
    'The new character must look naturally integrated, as if originally filmed in this scene: matching light, skin tone and shadows. Do not add new objects or extra characters.',
    'Stable face. No morphing. No deformation.',
  ].join('\n');
}

export type ReplaceVideoTags = {video: string; image: string};
export const KLING_OMNI_TAGS: ReplaceVideoTags = {video: '@VIDEO', image: '@IMAGE'};

export function buildReplaceInVideoPrompt(tags: ReplaceVideoTags = KLING_OMNI_TAGS): string {
  const {video, image} = tags;
  return [
    `Use ${video} as the full source of motion, acting, timing, camera, composition and scene. Use ${image} as the identity reference of the replacement character.`,
    `Replace the original actor in ${video} with the character from ${image}. The replacement fully takes the actor's place and stays visually consistent with ${image}; do not keep the original actor's face, skin or identity. Any visible hands, ears, neck or other exposed body parts belong to the replacement and match ${image}.`,
    `Preserve from ${video} as closely as possible: background, environment, composition, camera angle, framing, perspective, shot scale, lighting, shadows, color and atmosphere.`,
    `Transfer the original performance: body position, head position and rotation, gaze direction, posture, body movement, rhythm, timing and overall acting. Also transfer micro-expressions: blinking, eyelid tension, eyebrow, cheek and nostril motion, small jaw shifts, lip compression, mouth asymmetry, breathing and emotional tension of the face.`,
    `Speech: whenever the original actor speaks, the replacement articulates the same way, matching timing, intensity and rhythm exactly. No weak mouth animation, frozen lips or static acting.`,
    `Do not change the composition or body positions in frame. Do not add new objects or extra characters. The replacement must look naturally filmed in this scene, with realistic lighting, matching shadows, natural motion blur and seamless compositing.`,
    'Consistent identity throughout. No morphing, no deformation, no flickering, no ghosting.',
  ].join('\n');
}

/** Референсы в порядке, который ждёт промпт: Image 1 — исходный кадр, Image 2 — герой. */
export function replacementRefs(frameAssetId: string, heroAssetId: string): string[] {
  return [frameAssetId, heroAssetId];
}
