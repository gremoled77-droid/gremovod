// Логика контракта кадра без React: формы, сортировка замечаний, сборка запроса.
// Держится отдельно от компонента, чтобы правила проверялись тестом.
export type IssueSeverity = 'error' | 'warning' | 'info';

export type DirectorIssue = {
  shot_id: string | null;
  code: string;
  severity: IssueSeverity;
  path: string;
  message: string;
};

export type DirectorFact = {
  subject_id: string;
  predicate: string;
  value: string;
  from_value: string | null;
  to_value: string | null;
  action: string;
  event_id: string | null;
};

export type DirectorCamera = {
  framing: string;
  movement: string;
  direction: string;
  coordinate_space: string;
};

export type DirectorState = {
  continuity_mode: string;
  opening: DirectorFact[];
  transitions: DirectorFact[];
  closing: DirectorFact[];
};

export type DirectorContract = {
  shot_id: string;
  scene_id: string;
  source_event_ids: string[];
  duration_sec: number;
  narrative_role: string;
  character_ids: string[];
  asset_reference_ids: string[];
  camera: DirectorCamera;
  physical_state: DirectorState;
  author_lock_version: number;
  status: string;
  locked_paths: string[];
};

export type DirectorEntry = {
  shot_id: string;
  scene_id: string;
  title: string;
  number: string;
  revision: number;
  contract: DirectorContract | null;
};

export type DirectorEvent = {
  event_id: string;
  text: string;
  kind: string;
  timeline_order: number;
  presentation_order: number;
};

export type DirectorBundle = {
  board_revision: string;
  events: DirectorEvent[];
  contracts: DirectorEntry[];
  issues: DirectorIssue[];
  predicates: Record<string, string>;
  locked_predicates: string[];
};

export const NARRATIVE_ROLES = [
  {id: 'setup', title: 'Завязка'},
  {id: 'reveal', title: 'Раскрытие'},
  {id: 'reaction', title: 'Реакция'},
  {id: 'transition', title: 'Переход'},
  {id: 'climax', title: 'Кульминация'},
  {id: 'closing', title: 'Финал'},
];

export const CONTINUITY_MODES = [
  {id: 'continuous', title: 'Непрерывный'},
  {id: 'time_jump', title: 'Скачок времени'},
  {id: 'flashback', title: 'Флешбек'},
];

export const emptyFact = (): DirectorFact => ({
  subject_id: '',
  predicate: '',
  value: '',
  from_value: null,
  to_value: null,
  action: '',
  event_id: null,
});

export const emptyContract = (shotId: string, sceneId: string): DirectorContract => ({
  shot_id: shotId,
  scene_id: sceneId,
  source_event_ids: [],
  duration_sec: 3,
  narrative_role: 'setup',
  character_ids: [],
  asset_reference_ids: [],
  camera: {framing: '', movement: '', direction: '', coordinate_space: 'actor_world'},
  physical_state: {continuity_mode: 'continuous', opening: [], transitions: [], closing: []},
  author_lock_version: 1,
  status: 'draft',
  locked_paths: [],
});

export const cloneContract = (contract: DirectorContract): DirectorContract =>
  JSON.parse(JSON.stringify(contract)) as DirectorContract;

export const addFact = (rows: DirectorFact[]): DirectorFact[] => [...rows, emptyFact()];

export const removeFact = (rows: DirectorFact[], index: number): DirectorFact[] =>
  rows.filter((_, position) => position !== index);

export const updateFact = (
  rows: DirectorFact[],
  index: number,
  patch: Partial<DirectorFact>
): DirectorFact[] => rows.map((row, position) => (position === index ? {...row, ...patch} : row));

export const factHasContent = (fact: DirectorFact): boolean =>
  Boolean(
    fact.subject_id.trim() ||
    fact.predicate.trim() ||
    fact.value.trim() ||
    fact.action.trim() ||
    fact.from_value ||
    fact.to_value ||
    fact.event_id
  );

export const filledFacts = (rows: DirectorFact[]): DirectorFact[] => rows.filter(factHasContent);

export const cleanFact = (fact: DirectorFact): DirectorFact => ({
  ...fact,
  subject_id: fact.subject_id.trim(),
  predicate: fact.predicate.trim(),
  value: fact.value.trim(),
  from_value: fact.from_value ? fact.from_value.trim() : null,
  to_value: fact.to_value ? fact.to_value.trim() : null,
  action: fact.action.trim(),
  event_id: fact.event_id ? fact.event_id.trim() : null,
});

const SEVERITY_RANK: Record<IssueSeverity, number> = {error: 0, warning: 1, info: 2};

export const sortIssues = (issues: DirectorIssue[]): DirectorIssue[] =>
  [...issues].sort(
    (left, right) =>
      (SEVERITY_RANK[left.severity] ?? 9) - (SEVERITY_RANK[right.severity] ?? 9) ||
      left.code.localeCompare(right.code) ||
      left.path.localeCompare(right.path) ||
      left.message.localeCompare(right.message)
  );

export const issueCounts = (issues: DirectorIssue[]): Record<IssueSeverity, number> => ({
  error: issues.filter(issue => issue.severity === 'error').length,
  warning: issues.filter(issue => issue.severity === 'warning').length,
  info: issues.filter(issue => issue.severity === 'info').length,
});

export const shotIssues = (issues: DirectorIssue[], shotId: string): DirectorIssue[] =>
  sortIssues(issues.filter(issue => issue.shot_id === shotId));

export const seriesIssues = (issues: DirectorIssue[], shotId: string): DirectorIssue[] =>
  sortIssues(issues.filter(issue => issue.shot_id !== shotId));

// Проверки формы до отправки: сервер вернёт общие правила, но пустые и
// наполовину заполненные строки он трактует как ошибку схемы.
export const validateDraft = (contract: DirectorContract): string[] => {
  const problems: string[] = [];
  if (!(Number(contract.duration_sec) > 0)) problems.push('Укажи длительность кадра больше нуля');
  const rows = [
    ...contract.physical_state.opening,
    ...contract.physical_state.transitions,
    ...contract.physical_state.closing,
  ];
  const partial = rows.filter(
    fact => factHasContent(fact) && (!fact.subject_id.trim() || !fact.predicate.trim())
  );
  if (partial.length) problems.push('В строках состояния укажи предмет и предикат');
  const transition = contract.physical_state.transitions.find(
    fact => factHasContent(fact) && !fact.from_value && !fact.to_value
  );
  if (transition) problems.push('Переход должен менять состояние: заполни «было» или «стало»');
  return problems;
};

export const contractPayload = (contract: DirectorContract) => ({
  ...contract,
  duration_sec: Number(contract.duration_sec),
  source_event_ids: contract.source_event_ids.filter(Boolean),
  character_ids: contract.character_ids.filter(Boolean),
  asset_reference_ids: contract.asset_reference_ids.filter(Boolean),
  physical_state: {
    continuity_mode: contract.physical_state.continuity_mode,
    opening: filledFacts(contract.physical_state.opening).map(cleanFact),
    transitions: filledFacts(contract.physical_state.transitions).map(cleanFact),
    closing: filledFacts(contract.physical_state.closing).map(cleanFact),
  },
});

export const toggleEvent = (events: string[], eventId: string): string[] =>
  events.includes(eventId) ? events.filter(id => id !== eventId) : [...events, eventId];
