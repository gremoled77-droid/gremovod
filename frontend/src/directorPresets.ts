/** «Режиссёрский каркас» и заготовки для Кадров. Основа: пять столпов киноязыка (композиция, визуальная
 * коммуникация, операторская логика, сценарная механика, ритм). Те же строки FRAME/DOMINANT/SYMBOL/SHIFT/
 * CAMERA/LIGHT разбирает backend/prompt_rules.py (PILLARS_RULES). Идентичность Грэма и машины держат
 * референсы, поэтому внешность в заготовках не описывается. */

export const DIRECTOR_TEMPLATE = ['FRAME: ', 'DOMINANT: ', 'SYMBOL: ', 'SHIFT: ', 'CAMERA: ', 'LIGHT: '].join(
  '\n'
);

export type DirectorGroup = 'frame' | 'camera' | 'story';
export type DirectorPreset = {id: string; group: DirectorGroup; title: string; text: string};

export const DIRECTOR_GROUPS: Record<DirectorGroup, string> = {
  frame: 'Кадр',
  camera: 'Мотивация камеры',
  story: 'История и ритм',
};

const line = (label: string, value: string) => `${label}: ${value}`;
const block = (...lines: string[]) => lines.join('\n');

export const DIRECTOR_PRESETS: DirectorPreset[] = [
  {
    id: 'void',
    group: 'frame',
    title: 'Герой в пустоте',
    text: block(
      line(
        'FRAME',
        'Grem the taxi driver stands alone beside his VAZ-2106 and feels how small he is in a sleeping city.'
      ),
      line(
        'DOMINANT',
        'Grem, pushed to the left third of the frame; the car is a secondary dark shape behind him.'
      ),
      line('SYMBOL', ''),
      line('SHIFT', 'quiet night -> loneliness and pressure.'),
      line(
        'CAMERA',
        'wide shot, static, long empty space on the right; the empty street lines lead past him into the dark.'
      ),
      line('LIGHT', 'one sodium street lamp above and behind him; light mist in the lamp cone.')
    ),
  },
  {
    id: 'symbol',
    group: 'frame',
    title: 'Символический объект',
    text: block(
      line(
        'FRAME',
        'Grem notices an envelope a passenger left on the back seat of the VAZ-2106 and understands it is not his to read.'
      ),
      line('DOMINANT', 'the envelope on the back seat, sharp and brightest in the frame.'),
      line('SYMBOL', 'a wet envelope with a torn corner.'),
      line('SHIFT', 'routine shift -> unease and a question.'),
      line(
        'CAMERA',
        "medium close-up over Grem's shoulder, shallow depth of field, eyeline and seat edge lead to the envelope."
      ),
      line('LIGHT', 'one source: a street lamp through the rear window; drizzle haze on the glass.')
    ),
  },
  {
    id: 'small',
    group: 'frame',
    title: 'Маленький герой (слабость)',
    text: block(
      line(
        'FRAME',
        'Grem is a small figure facing a huge residential block at night, the world is bigger than him.'
      ),
      line('DOMINANT', 'Grem, small and low in the frame, with the lit window he is looking at above him.'),
      line('SYMBOL', ''),
      line('SHIFT', 'confidence -> doubt.'),
      line('CAMERA', 'high angle, wide lens, the facade lines press down on him.'),
      line('LIGHT', 'cold window light from above; fog at street level.')
    ),
  },
  {
    id: 'big',
    group: 'frame',
    title: 'Большой герой (сила)',
    text: block(
      line(
        'FRAME',
        'Grem behind the wheel of the VAZ-2106 decides to take the risky fare and takes control.'
      ),
      line('DOMINANT', "Grem's face and hands on the wheel, close to the camera."),
      line('SYMBOL', ''),
      line('SHIFT', 'hesitation -> decision.'),
      line(
        'CAMERA',
        'low angle, medium close-up, long lens that compresses the dashboard and the street behind.'
      ),
      line(
        'LIGHT',
        'warm dashboard glow from below, cold street light from the side window; dust in the beam.'
      )
    ),
  },
  {
    id: 'reveal',
    group: 'camera',
    title: 'Reveal: открыть информацию',
    text: block(
      line(
        'FRAME',
        'Grem waits in his VAZ-2106 and the camera reveals that the passenger at the curb is not alone.'
      ),
      line('DOMINANT', 'the second figure that appears as the camera moves.'),
      line('SYMBOL', ''),
      line('SHIFT', 'calm pickup -> alarm.'),
      line(
        'CAMERA',
        'reveal: slow lateral move from behind the car pillar until the second figure enters the frame.'
      ),
      line('LIGHT', 'one headlight beam from the car; rain haze in the beam.')
    ),
  },
  {
    id: 'follow',
    group: 'camera',
    title: 'Follow: сопровождать действие',
    text: block(
      line('FRAME', 'Grem hurries across the courtyard to catch the engine of his VAZ-2106 before it dies.'),
      line('DOMINANT', 'Grem in motion, the camera keeps him in the same part of the frame.'),
      line('SYMBOL', ''),
      line('SHIFT', 'panic -> a fragile hope.'),
      line('CAMERA', 'follow: tracking shot behind and slightly to the side, matching his speed.'),
      line('LIGHT', 'courtyard lamp ahead as the source; breath steam and light rain.')
    ),
  },
  {
    id: 'push',
    group: 'camera',
    title: 'Push in: приблизиться к эмоции',
    text: block(
      line(
        'FRAME',
        'Grem listens to the radio in the VAZ-2106 and realises the voice is about his own street.'
      ),
      line('DOMINANT', "Grem's eyes in the rear-view mirror."),
      line('SYMBOL', 'the radio dial glowing in the dark.'),
      line('SHIFT', 'idle shift -> shock.'),
      line('CAMERA', 'push in: slow dolly in from medium to close-up, steady, no shake.'),
      line('LIGHT', 'dashboard and radio glow as the only source; thin haze in the cabin air.')
    ),
  },
  {
    id: 'pull',
    group: 'camera',
    title: 'Pull back: показать масштаб',
    text: block(
      line('FRAME', 'Grem stays in the stopped VAZ-2106 while the whole city goes on without him.'),
      line('DOMINANT', 'the lit cabin of the car with Grem inside, shrinking in the frame.'),
      line('SYMBOL', ''),
      line('SHIFT', 'intimate -> lonely and exposed.'),
      line('CAMERA', 'pull back: slow dolly out to a wide shot, the car becomes a small lit point.'),
      line('LIGHT', 'the cabin dome light as the single warm source; mist over the road.')
    ),
  },
  {
    id: 'five',
    group: 'story',
    title: 'Мини-история из 5 кадров',
    text: block(
      'STORY (5 beats), one frame prompt per beat; each frame answers the question raised by the previous one:',
      '1 who and where: Grem and his VAZ-2106 on a night shift in Minsk.',
      '2 a hint of desire: what Grem wants right now.',
      '3 the obstacle: what stands in his way.',
      '4 the choice: what Grem does about it.',
      '5 the result or the price.',
      'For every beat give FRAME, DOMINANT, SYMBOL, SHIFT, CAMERA, LIGHT, then the finished prompt.'
    ),
  },
  {
    id: 'rhythm',
    group: 'story',
    title: 'Ритм: два быстрых, длиннее, удар',
    text: block(
      'RHYTHM for a sequence of 4 clips: clips 1-2 are short hooks (about 2-3 s each), clip 3 is longer to let the emotion land (about 5-6 s), clip 4 is a short punch to close (about 2 s).',
      'Cut each clip when its shot has answered its question; the next shot asks the next question.',
      'Give the camera motive (reveal, follow, push in or pull back) for each clip.'
    ),
  },
];

export function findDirectorPreset(id: string): DirectorPreset | undefined {
  return DIRECTOR_PRESETS.find(p => p.id === id);
}

/** Добавляет блок в конец промпта; повторно один и тот же блок не вставляется. */
export function appendDirectorBlock(current: string, text: string): string {
  if (current.includes(text)) return current;
  return current.trim() ? current.trimEnd() + '\n\n' + text : text;
}
