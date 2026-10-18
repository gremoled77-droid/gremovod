/** Таблица экранов студии: одно место для меню, заголовков, классов <main> и скрытых до беты экранов. */
export type Mode =
  | 'home'
  | 'studio'
  | 'styles'
  | 'characters'
  | 'storyboard'
  | 'create'
  | 'video'
  | 'graph'
  | 'archive'
  | 'connections'
  | 'settings'
  // Скрыты до беты (решение владельца 18.10.2026): код лежит, в меню и маршрутах их нет.
  | 'audio'
  | 'reels'
  | 'files'
  | 'economics'
  | 'scene'
  | 'refine'
  | 'agents';

export type Screen = {
  mode: Mode;
  title: string;
  /** stage — этап ролика в меню; tool — инструмент; service — без пункта в меню; hidden — выключен до беты. */
  group: 'start' | 'stage' | 'tool' | 'service' | 'hidden';
  /** Класс <main>: экраны нового дизайна прячут старую боковую панель. */
  main: string;
  hint?: string;
  icon?: string;
  lede?: string;
};

export const SCREENS: Screen[] = [
  {mode: 'home', title: 'Старт', group: 'start', main: 'home-main', hint: 'обзор проекта', icon: '⌂'},
  {
    mode: 'studio',
    title: 'Идея',
    group: 'stage',
    main: 'idea-main',
    hint: 'задание ролика',
    lede: 'Задание ролика: запиши идею, отправь в LLM, собери мир.',
  },
  {
    mode: 'styles',
    title: 'Мир',
    group: 'stage',
    main: 'world-main',
    hint: 'стиль и персонажи',
    lede: 'Стиль мира и персонажи: общие для всех кадров серии.',
  },
  {mode: 'storyboard', title: 'Раскадровка', group: 'stage', main: 'storyboard-main', hint: 'кадры эпизода'},
  {mode: 'create', title: 'Кадры', group: 'stage', main: 'create-main', hint: 'картинки'},
  {mode: 'video', title: 'Видео', group: 'stage', main: 'create-main video-main', hint: 'оживление кадров'},
  {mode: 'graph', title: 'Узлы', group: 'tool', main: 'workflow-main', icon: '⌁'},
  {
    mode: 'archive',
    title: 'Библиотека',
    group: 'tool',
    main: 'solo-main',
    icon: '▤',
    lede: 'Все картинки и видео проекта.',
  },
  {
    mode: 'characters',
    title: 'Мир',
    group: 'service',
    main: 'world-main',
    lede: 'Стиль мира и персонажи: общие для всех кадров серии.',
  },
  {
    mode: 'connections',
    title: 'Подключения',
    group: 'service',
    main: 'solo-main',
    lede: 'Ключи и доступ к сервисам: PiAPI, OpenAI, голос.',
  },
  {
    mode: 'settings',
    title: 'Настройки',
    group: 'service',
    main: 'solo-main',
    lede: 'Проект, модель для промптов и ссылка на чат.',
  },
  {mode: 'audio', title: 'Звук', group: 'hidden', main: 'media-main'},
  {mode: 'reels', title: 'Рилсы', group: 'hidden', main: 'reels-main'},
  {mode: 'files', title: 'Монтаж', group: 'hidden', main: 'solo-main'},
  {mode: 'economics', title: 'Выпуск', group: 'hidden', main: 'solo-main'},
  {mode: 'scene', title: 'Сцена', group: 'hidden', main: 'solo-main'},
  {mode: 'refine', title: 'Допилить', group: 'hidden', main: 'solo-main'},
  {mode: 'agents', title: 'Агенты', group: 'hidden', main: 'solo-main'},
];

const BY_MODE = new Map(SCREENS.map(s => [s.mode, s]));

export const screenOf = (mode: Mode): Screen => BY_MODE.get(mode) || SCREENS[0];

/** Этапы ролика по порядку; номер этапа — позиция + 1. */
export const STAGES = SCREENS.filter(s => s.group === 'stage').map((s, i) => ({...s, icon: String(i + 1)}));
export const TOOLS = SCREENS.filter(s => s.group === 'tool');

export const isHidden = (mode: Mode) => screenOf(mode).group === 'hidden';

/** Вкладка «Персонажи» живёт внутри «Мира»: в меню подсвечивается «Мир». */
export const navMode = (mode: Mode): Mode => (mode === 'characters' ? 'styles' : mode);
