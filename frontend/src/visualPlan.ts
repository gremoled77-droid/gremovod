/** Visual plan of a scene/frame (Bruce Block components) and checks over the whole series. */
export type VisualPlan = {
  space: '' | 'deep' | 'flat' | 'limited' | 'ambiguous';
  line: '' | 'horizontal' | 'vertical' | 'diagonal' | 'mixed';
  shape: '' | 'circle' | 'square' | 'triangle';
  tone: '' | 'reveal' | 'conceal';
  beat: number | null;
  sector_start: number | null;
  sector_end: number | null;
  story: number | null;
  visual: number | null;
  note: string;
  beats: string;
};
export const emptyPlan = (): VisualPlan => ({
  space: '',
  line: '',
  shape: '',
  tone: '',
  beat: null,
  sector_start: null,
  sector_end: null,
  story: null,
  visual: null,
  note: '',
  beats: '',
});
export const SPACE_LABELS: Record<string, string> = {
  '': 'не задано',
  deep: 'глубокое',
  flat: 'плоское',
  limited: 'ограниченное',
  ambiguous: 'неопределённое',
};
export const LINE_LABELS: Record<string, string> = {
  '': 'не задано',
  horizontal: 'горизонталь (спокойно)',
  vertical: 'вертикаль',
  diagonal: 'диагональ (напряжённо)',
  mixed: 'смесь',
};
export const SHAPE_LABELS: Record<string, string> = {
  '': 'не задано',
  circle: 'круг (мягко)',
  square: 'квадрат (устойчиво)',
  triangle: 'треугольник (угроза)',
};
export const TONE_LABELS: Record<string, string> = {
  '': 'не задано',
  reveal: 'свет показывает',
  conceal: 'тень скрывает',
};
export type ShotPoint = {
  id: string;
  label: string;
  space: VisualPlan['space'];
  line: VisualPlan['line'];
  sector_start: number | null;
  sector_end: number | null;
  story: number | null;
  visual: number | null;
};
const filled = (p: ShotPoint) => p.story !== null && p.visual !== null;

/** Склейка гладкая, если точка внимания кончается и начинается в одном секторе сетки 3x3. */
export function sectorJumps(points: ShotPoint[]): {from: string; to: string; a: number; b: number}[] {
  const out: {from: string; to: string; a: number; b: number}[] = [];
  for (let i = 0; i + 1 < points.length; i++) {
    const a = points[i].sector_end,
      b = points[i + 1].sector_start;
    if (a !== null && b !== null && a !== b) out.push({from: points[i].label, to: points[i + 1].label, a, b});
  }
  return out;
}

/** Предупреждения по графику: пустые данные не ругаем, только то, что видно по заполненным кадрам. */
export function tensionWarnings(points: ShotPoint[]): string[] {
  const out: string[] = [];
  const known = points.filter(filled);
  if (known.length >= 4) {
    const visual = known.map(p => p.visual as number);
    if (Math.max(...visual) - Math.min(...visual) <= 1)
      out.push('Визуальное напряжение почти не меняется: график плоский, кульминация не выделена.');
    const peak = known.reduce((best, p) => ((p.story as number) > (best.story as number) ? p : best));
    const loudest = known.reduce((best, p) => ((p.visual as number) > (best.visual as number) ? p : best));
    if (
      (peak.story as number) - (known[0].story as number) >= 3 &&
      (peak.visual as number) + 2 <= (loudest.visual as number)
    )
      out.push(
        `В кульминации сюжета (кадр ${peak.label}) визуальное напряжение ${peak.visual} ниже, чем в кадре ${loudest.label} (${loudest.visual}).`
      );
    const third = Math.max(1, Math.floor(known.length / 3)),
      head = known.slice(0, third).map(p => p.visual as number),
      headMean = head.reduce((a, b) => a + b, 0) / head.length;
    if (headMean > (peak.visual as number) && known.indexOf(peak) >= third)
      out.push('Экспозиция визуально напряжённее кульминации: начало «перебивает» пик истории.');
    const last = known[known.length - 1];
    if (
      known.length >= 5 &&
      (last.visual as number) >= (peak.visual as number) &&
      (last.story as number) < (peak.story as number) - 2
    )
      out.push(`Развязка (кадр ${last.label}) не успокоена: визуальное напряжение не падает после пика.`);
  }
  for (let i = 0; i + 2 < points.length; i++) {
    const [a, b, c] = [points[i], points[i + 1], points[i + 2]];
    if (
      a.space &&
      a.space === b.space &&
      b.space === c.space &&
      a.line &&
      a.line === b.line &&
      b.line === c.line
    )
      out.push(
        `Кадры ${a.label}, ${b.label}, ${c.label} одинаковы по пространству и линии: зритель получит повтор без роста.`
      );
  }
  return [...new Set(out)];
}

export type FrameAnalysis = {
  tone: {
    range: number;
    mean: number;
    dark_share: number;
    light_share: number;
    hint: '' | 'reveal' | 'conceal';
  };
  color: {saturation: number; warm: number; cool: number; dominant_hue: string};
  lines: {dominant: '' | 'horizontal' | 'vertical' | 'diagonal' | 'mixed'};
  attention: {brightest_sector: number; contrast_sector: number; sector: number};
  focus: {blur_share: number; hint: string};
  visual_intensity: number;
};

/** Предложение плана по анализу: заполняет только пустые поля, чтобы не затирать ручные решения. */
export function planFromAnalysis(current: VisualPlan, a: FrameAnalysis): VisualPlan {
  return {
    ...current,
    line: current.line || a.lines.dominant,
    tone: current.tone || a.tone.hint,
    visual: current.visual ?? a.visual_intensity,
    sector_start: current.sector_start ?? a.attention.sector,
    sector_end: current.sector_end ?? a.attention.sector,
  };
}

/** Короткое описание анализа для человека. */
export function describeAnalysis(a: FrameAnalysis): string[] {
  const pct = (v: number) => Math.round(v * 100) + '%';
  const out = [
    `Тональный диапазон ${pct(a.tone.range)}, тёмных ${pct(a.tone.dark_share)}, светлых ${pct(a.tone.light_share)}`,
    `Насыщенность ${pct(a.color.saturation)}; тёплых ${pct(a.color.warm)}, холодных ${pct(a.color.cool)}` +
      (a.color.dominant_hue ? `; главный оттенок: ${a.color.dominant_hue}` : ''),
    `Линии: ${a.lines.dominant || 'нет выраженных'}; внимание вероятнее в секторе ${a.attention.sector} (самый яркий ${a.attention.brightest_sector}, самый контрастный ${a.attention.contrast_sector})`,
    `Визуальное напряжение по картинке: ${a.visual_intensity} из 10`,
  ];
  if (a.focus.hint) out.push(a.focus.hint);
  return out;
}

export type VisualRules = {
  space: VisualPlan['space'];
  line: VisualPlan['line'];
  shape: VisualPlan['shape'];
  tone: VisualPlan['tone'];
  palette: string;
  camera: string;
  rhythm: string;
  note: string;
};
