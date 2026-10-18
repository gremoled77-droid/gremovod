/** Невидимые линии-магниты: при перетаскивании узел притягивается к выравниванию с соседями (линии не рисуются). */
export type Box = {x: number; y: number; w: number; h: number};

/** Зазор между колонками и между узлами в колонке: тот же, что у расстановки новых узлов. */
export const SNAP_GAP_X = 70;
export const SNAP_GAP_Y = 40;

function nearest(value: number, candidates: number[], threshold: number): number {
  let best = value;
  let bestDist = threshold + 1e-9;
  for (const c of candidates) {
    const d = Math.abs(c - value);
    if (d < bestDist) {
      best = c;
      bestDist = d;
    }
  }
  return best;
}

/** Притягивает позицию узла к краям, центрам и «соседним» местам других узлов, если ближе порога (в единицах схемы). */
export function snapPosition(
  pos: {x: number; y: number},
  size: {w: number; h: number},
  others: Box[],
  threshold: number
): {x: number; y: number} {
  const xs: number[] = [];
  const ys: number[] = [];
  for (const o of others) {
    xs.push(
      o.x,
      o.x + o.w - size.w,
      o.x + (o.w - size.w) / 2,
      o.x + o.w + SNAP_GAP_X,
      o.x - size.w - SNAP_GAP_X
    );
    ys.push(
      o.y,
      o.y + o.h - size.h,
      o.y + (o.h - size.h) / 2,
      o.y + o.h + SNAP_GAP_Y,
      o.y - size.h - SNAP_GAP_Y
    );
  }
  return {x: nearest(pos.x, xs, threshold), y: nearest(pos.y, ys, threshold)};
}
