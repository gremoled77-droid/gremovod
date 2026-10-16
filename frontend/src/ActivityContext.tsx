import {createContext, useContext, type ReactNode} from 'react';
import type {ActivityItem} from './useActivity';

type Value = {items: ActivityItem[]; error: string; reset: () => void};
export const ActivityContext = createContext<Value | null>(null);
const Ctx = ActivityContext;

/** Одна общая лента заданий на всё приложение (один долгий запрос вместо нескольких). */
export function ActivityProvider({value, children}: {value: Value; children: ReactNode}) {
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSharedActivity(): Value {
  const value = useContext(Ctx);
  if (!value) throw new Error('ActivityProvider отсутствует');
  return value;
}
