import type {ReactNode} from 'react';
import type {FrameCat} from './cameraFrameCatalog';

/** Мини-превью карточек «Камера и кадр»: схемы, нарисованные в коде (без генерации и без файлов). */
const ACCENT = 'var(--accent, #f2b134)';

const Person = ({
  x = 40,
  y = 54,
  s = 1,
  fill = 'currentColor',
  opacity = 0.85,
}: {
  x?: number;
  y?: number;
  s?: number;
  fill?: string;
  opacity?: number;
}) => (
  <g transform={`translate(${x} ${y}) scale(${s}) translate(-40 -54)`} fill={fill} opacity={opacity}>
    <circle cx="40" cy="17" r="7" />
    <path d="M27 54V37Q27 27 40 27Q53 27 53 37V54Z" />
  </g>
);

const Cam = ({x, y, tx, ty}: {x: number; y: number; tx: number; ty: number}) => {
  const angle = (Math.atan2(ty - y, tx - x) * 180) / Math.PI;
  return (
    <g>
      <line x1={x} y1={y} x2={tx} y2={ty} stroke={ACCENT} strokeWidth="1" strokeDasharray="2 2" />
      <g transform={`translate(${x} ${y}) rotate(${angle})`} fill={ACCENT}>
        <rect x="-7" y="-5" width="10" height="10" rx="2" />
        <polygon points="3,-3 9,-6 9,6 3,3" />
      </g>
    </g>
  );
};

const Frame = ({x, y, w, h}: {x: number; y: number; w: number; h: number}) => (
  <g>
    <path
      d={`M0 0H80V60H0Z M${x} ${y}V${y + h}H${x + w}V${y}Z`}
      fill="#000"
      opacity="0.5"
      fillRule="evenodd"
    />
    <rect x={x} y={y} width={w} height={h} fill="none" stroke={ACCENT} strokeWidth="1.6" rx="1.5" />
  </g>
);

const SIZES: Record<string, ReactNode> = {
  ecu: (
    <>
      <Person />
      <Frame x={30} y={11} w={20} h={12} />
    </>
  ),
  cu: (
    <>
      <Person />
      <Frame x={26} y={5} w={28} h={26} />
    </>
  ),
  mcu: (
    <>
      <Person />
      <Frame x={20} y={3} w={40} h={36} />
    </>
  ),
  ms: (
    <>
      <Person />
      <Frame x={12} y={3} w={56} h={44} />
    </>
  ),
  ws: (
    <>
      <path d="M6 52H74" stroke="currentColor" opacity="0.4" />
      <rect x="8" y="30" width="14" height="22" fill="currentColor" opacity="0.2" />
      <rect x="58" y="24" width="14" height="28" fill="currentColor" opacity="0.2" />
      <Person x={40} y={52} s={0.8} />
      <Frame x={3} y={3} w={74} h={54} />
    </>
  ),
  ews: (
    <>
      <path d="M0 46L16 30L28 42L44 24L60 42L70 34L80 44V60H0Z" fill="currentColor" opacity="0.2" />
      <path d="M0 46H80" stroke="currentColor" opacity="0.35" />
      <Person x={40} y={50} s={0.32} />
      <Frame x={2} y={2} w={76} h={56} />
    </>
  ),
};

const Move = ({children}: {children: ReactNode}) => <>{children}</>;

const MOVES: Record<string, ReactNode> = {
  static: (
    <Move>
      <Person />
      <Frame x={10} y={4} w={60} h={52} />
      <path d="M36 30H44M40 26V34" stroke={ACCENT} strokeWidth="1.4" />
    </Move>
  ),
  push: (
    <Move>
      <Person />
      <g fill="none" stroke={ACCENT} strokeWidth="1.6">
        <rect x="4" y="3" width="72" height="54" rx="1.5">
          <animate attributeName="x" values="4;20;4" dur="2.4s" repeatCount="indefinite" />
          <animate attributeName="y" values="3;10;3" dur="2.4s" repeatCount="indefinite" />
          <animate attributeName="width" values="72;40;72" dur="2.4s" repeatCount="indefinite" />
          <animate attributeName="height" values="54;30;54" dur="2.4s" repeatCount="indefinite" />
        </rect>
      </g>
      <path d="M8 8L16 14M72 8L64 14M8 52L16 46M72 52L64 46" stroke={ACCENT} strokeWidth="1.2" />
    </Move>
  ),
  pull: (
    <Move>
      <Person s={0.7} y={50} />
      <g fill="none" stroke={ACCENT} strokeWidth="1.6">
        <rect x="20" y="10" width="40" height="30" rx="1.5">
          <animate attributeName="x" values="20;4;20" dur="2.4s" repeatCount="indefinite" />
          <animate attributeName="y" values="10;3;10" dur="2.4s" repeatCount="indefinite" />
          <animate attributeName="width" values="40;72;40" dur="2.4s" repeatCount="indefinite" />
          <animate attributeName="height" values="30;54;30" dur="2.4s" repeatCount="indefinite" />
        </rect>
      </g>
      <path d="M16 14L8 8M64 14L72 8M16 46L8 52M64 46L72 52" stroke={ACCENT} strokeWidth="1.2" />
    </Move>
  ),
  pan: (
    <Move>
      <rect x="6" y="30" width="12" height="22" fill="currentColor" opacity="0.2" />
      <rect x="62" y="24" width="12" height="28" fill="currentColor" opacity="0.2" />
      <Person />
      <rect x="14" y="8" width="36" height="44" rx="1.5" fill="none" stroke={ACCENT} strokeWidth="1.6">
        <animate attributeName="x" values="8;30;8" dur="2.6s" repeatCount="indefinite" />
      </rect>
      <path d="M54 56H74M70 53L74 56L70 59" fill="none" stroke={ACCENT} strokeWidth="1.4" />
    </Move>
  ),
  tilt: (
    <Move>
      <Person />
      <path d="M4 28H76" stroke="currentColor" opacity="0.25" strokeDasharray="2 3" />
      <rect x="18" y="26" width="44" height="30" rx="1.5" fill="none" stroke={ACCENT} strokeWidth="1.6">
        <animate attributeName="y" values="28;2;28" dur="2.6s" repeatCount="indefinite" />
      </rect>
      <path d="M72 20V6M69 10L72 6L75 10" fill="none" stroke={ACCENT} strokeWidth="1.4" />
    </Move>
  ),
  orbit: (
    <Move>
      <Person s={0.8} y={50} />
      <ellipse
        cx="40"
        cy="32"
        rx="30"
        ry="14"
        fill="none"
        stroke={ACCENT}
        strokeDasharray="2 3"
        opacity="0.6"
      />
      <circle r="4" fill={ACCENT}>
        <animateMotion dur="3s" repeatCount="indefinite" path="M10 32A30 14 0 1 1 70 32A30 14 0 1 1 10 32" />
      </circle>
    </Move>
  ),
  track: (
    <Move>
      <path d="M4 52H76" stroke="currentColor" opacity="0.3" />
      <Person x={46} y={50} s={0.75} />
      <path d="M6 14H74" stroke={ACCENT} strokeDasharray="2 3" opacity="0.6" />
      <g fill={ACCENT}>
        <rect x="-7" y="-5" width="10" height="10" rx="2" />
        <polygon points="3,-3 9,-6 9,6 3,3" />
        <animateTransform
          attributeName="transform"
          type="translate"
          values="12 14;62 14;12 14"
          dur="3s"
          repeatCount="indefinite"
        />
      </g>
    </Move>
  ),
  crane: (
    <Move>
      <Person y={56} s={0.8} />
      <path d="M12 52Q30 44 66 10" fill="none" stroke={ACCENT} strokeDasharray="2 3" opacity="0.6" />
      <g fill={ACCENT}>
        <rect x="-7" y="-5" width="10" height="10" rx="2" />
        <polygon points="3,-3 9,-6 9,6 3,3" />
        <animateTransform
          attributeName="transform"
          type="translate"
          values="14 50;62 12;14 50"
          dur="3s"
          repeatCount="indefinite"
        />
      </g>
    </Move>
  ),
  hand: (
    <Move>
      <Person />
      <rect x="10" y="4" width="60" height="52" rx="1.5" fill="none" stroke={ACCENT} strokeWidth="1.6">
        <animateTransform
          attributeName="transform"
          type="translate"
          values="0 0;1.5 -1;-1 1.5;1 1;-1.5 -1;0 0"
          dur="0.9s"
          repeatCount="indefinite"
        />
      </rect>
    </Move>
  ),
};

function Angle({id}: {id: string}) {
  if (id === 'bird')
    return (
      <>
        <ellipse cx="40" cy="38" rx="13" ry="8" fill="currentColor" opacity="0.8" />
        <circle cx="40" cy="38" r="5" fill="currentColor" />
        <Cam x={40} y={9} tx={40} ty={31} />
      </>
    );
  if (id === 'ots')
    return (
      <>
        <path d="M0 60V40Q4 26 22 26Q34 28 36 60Z" fill="currentColor" opacity="0.75" />
        <circle cx="12" cy="20" r="8" fill="currentColor" opacity="0.75" />
        <Person x={62} y={50} s={0.6} opacity={0.5} />
        <rect x="46" y="6" width="30" height="48" rx="2" fill="none" stroke={ACCENT} strokeWidth="1.4" />
      </>
    );
  const cams: Record<string, [number, number, number, number]> = {
    eye: [12, 28, 56, 24],
    low: [12, 52, 56, 22],
    high: [12, 8, 56, 32],
    dutch: [12, 28, 56, 24],
  };
  const [cx, cy, tx, ty] = cams[id] ?? cams.eye;
  const scene = (
    <>
      <path d="M2 54H78" stroke="currentColor" opacity="0.35" />
      <Person x={58} y={54} s={id === 'low' ? 1 : 0.85} />
      <Cam x={cx} y={cy} tx={tx} ty={ty} />
    </>
  );
  return id === 'dutch' ? <g transform="rotate(-14 40 30)">{scene}</g> : scene;
}

const LIGHTS: Record<string, {bg: string[]; fx: ReactNode; edge?: string; fill?: string}> = {
  back: {
    bg: ['#2a2a33', '#14141a'],
    fx: <circle cx="40" cy="22" r="22" fill="url(#cf-glow)" />,
    edge: '#fff2c4',
  },
  side: {bg: ['#1b1d24', '#14151a'], fx: null, fill: 'url(#cf-side)'},
  top: {
    bg: ['#1b1d24', '#101116'],
    fx: <path d="M30 0H50L62 54H18Z" fill="url(#cf-cone)" />,
  },
  window: {
    bg: ['#2b3140', '#1a1d26'],
    fx: <path d="M0 4L28 14V50L0 56Z" fill="#cfe3ff" opacity="0.28" />,
    fill: 'url(#cf-side)',
  },
  golden: {
    bg: ['#f2a03b', '#5a2a52'],
    fx: <circle cx="62" cy="30" r="9" fill="#ffe3a0" opacity="0.9" />,
    fill: '#1a1015',
  },
  neon: {
    bg: ['#1a1038', '#0a0a1c'],
    fx: (
      <>
        <circle cx="12" cy="16" r="16" fill="#ff3da6" opacity="0.5" />
        <circle cx="70" cy="40" r="18" fill="#2ee6ff" opacity="0.45" />
      </>
    ),
    fill: '#0b0b18',
    edge: '#ff5cc0',
  },
  lowkey: {
    bg: ['#0b0b0d', '#050506'],
    fx: <path d="M36 8H44V30H36Z" fill="#fff" opacity="0.5" />,
    fill: '#17171b',
  },
  overcast: {bg: ['#8f96a3', '#656b78'], fx: null, fill: '#3a3f4a'},
};

function Light({id}: {id: string}) {
  const l = LIGHTS[id];
  return (
    <>
      <defs>
        <linearGradient id={`cf-bg-${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={l.bg[0]} />
          <stop offset="1" stopColor={l.bg[1]} />
        </linearGradient>
        <radialGradient id="cf-glow">
          <stop offset="0" stopColor="#fff6d8" stopOpacity="0.95" />
          <stop offset="1" stopColor="#fff6d8" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="cf-side" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#f6e6c0" />
          <stop offset="0.5" stopColor="#6a6558" />
          <stop offset="1" stopColor="#15151a" />
        </linearGradient>
        <linearGradient id="cf-cone" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fff2cc" stopOpacity="0.7" />
          <stop offset="1" stopColor="#fff2cc" stopOpacity="0" />
        </linearGradient>
      </defs>
      <rect width="80" height="60" fill={`url(#cf-bg-${id})`} />
      {l.fx}
      <g stroke={l.edge ?? 'none'} strokeWidth={l.edge ? 1.4 : 0}>
        <Person fill={l.fill ?? '#0d0d10'} opacity={1} />
      </g>
    </>
  );
}

export default function CameraFramePreview({cat, id}: {cat: FrameCat; id: string}) {
  return (
    <svg viewBox="0 0 80 60" className="cf-prev" aria-hidden="true" focusable="false">
      {cat === 'size' && SIZES[id]}
      {cat === 'move' && MOVES[id]}
      {cat === 'angle' && <Angle id={id} />}
      {cat === 'light' && <Light id={id} />}
    </svg>
  );
}
