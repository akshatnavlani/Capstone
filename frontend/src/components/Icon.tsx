// Simple line icons (23 Nov 2026): replace the emoji used across the brand pages with one consistent, quieter style.
// 24x24 strokes in the current text colour. Works inside HTML and inside an SVG (pass x / y to place it there).

const PATHS: Record<string, string> = {
  dumbbell: "M6 7v10M18 7v10M3 9.5v5M21 9.5v5M6 12h12",
  shake: "M7 4h10l-1.2 16H8.2L7 4zM7.4 9h9.2M12 4V2",
  bar: "M3 9.5h18v5H3zM7.5 9.5v5M12 9.5v5M16.5 9.5v5",
  bolt: "M13 2 4 14h7l-1 8 9-12h-7l1-8z",
  shoe: "M3 17v-5l4-1 3-4 2.5 1-1 3 4 1c3 .6 6 1.8 6 4.5V17H3zM3 20h18",
  shirt: "M8.5 3 3 6l2 4 3-1v12h8V9l3 1 2-4-5.5-3c-.8 1.8-2.2 3-3.5 3S9.3 4.8 8.5 3z",
  home: "M3 11 12 4l9 7v9h-6v-6H9v6H3z",
  yoga: "M12 3.5a1.6 1.6 0 1 1 0 3.2 1.6 1.6 0 0 1 0-3.2zM12 8.5v5M6.5 11.5l5.5 2 5.5-2M4.5 19c2.2-2.8 4.8-4 7.5-4s5.3 1.2 7.5 4",
  stethoscope: "M5 3v5a4 4 0 0 0 8 0V3M9 12v3a5 5 0 0 0 10 0v-2M19 13a2 2 0 1 0 0-4 2 2 0 0 0 0 4z",
  bat: "M15 3.5l5.5 5.5-9.5 9.5H8.5L5.5 15.5V13zM5.5 18.5 3 21",
  ball: "M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18zM5.5 6c3 2.5 3 9.5 0 12M18.5 6c-3 2.5-3 9.5 0 12",
  leaf: "M5 19C5 10 11 5 19 5c0 8-5 14-14 14zM5 19l8-8",
  bike: "M6 13.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7zM18 13.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7zM6 17l4-7h5l3 7M9 10 8 7H6M15 10l-1.5-3H16",
  run: "M14 3.5a1.6 1.6 0 1 1 0 3.2 1.6 1.6 0 0 1 0-3.2zM8 21l3-6-2.5-3 3-4 3 3h3M5 11l3-3h3",
  sparkle: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z",
  pen: "M4 20l4-1 11-11-3-3L5 16l-1 4z",
  help: "M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18zM9.5 9.3a2.6 2.6 0 1 1 3.6 2.4c-.7.3-1.1.9-1.1 1.7v.4M12 17h.01",
  wallet: "M3 7.5h15a3 3 0 0 1 3 3V17a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7.5zM3 7.5 15 4v3.5M16 13.3h2",
  youtube: "M3 8a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v8a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3zM10 9.2l5 2.8-5 2.8z",
  instagram: "M8 3h8a5 5 0 0 1 5 5v8a5 5 0 0 1-5 5H8a5 5 0 0 1-5-5V8a5 5 0 0 1 5-5zM12 8.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7zM17.3 6.7h.01",
  layers: "M12 3 3 8l9 5 9-5-9-5zM3 13l9 5 9-5",
  repeat: "M4 9h14l-3.5-3.5M20 15H6l3.5 3.5",
  phone: "M7 2.5h10v19H7zM11 18h2",
  cart: "M3 4h2.2l2.3 11h10.3L20 7.5H6.2M9 20h.01M17 20h.01",
  trend: "M3 7l6 6 4-4 8 8M15.5 17H21v-5.5",
  sliders: "M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1M15 4v4M9 10v4M17 16v4",
  bulb: "M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10.4c.7.7 1 1.6 1 2.6h6c0-1 .3-1.9 1-2.6A6 6 0 0 0 12 3z",
  chat: "M4 5h16v11H9.5L4 20z",
  pin: "M12 21s-7-6.4-7-12a7 7 0 0 1 14 0c0 5.6-7 12-7 12zM12 11.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z",
  shield: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z",
  megaphone: "M3 10v4h4l8 5V5l-8 5H3zM18.5 9a4 4 0 0 1 0 6",
  target: "M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18zM12 7a5 5 0 1 1 0 10 5 5 0 0 1 0-10zM12 11a1 1 0 1 1 0 2 1 1 0 0 1 0-2z",
  screen: "M3 5h18v12H3zM8 21h8M12 17v4",
  smile: "M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18zM8 14.5s1.5 2 4 2 4-2 4-2M9 9.5h.01M15 9.5h.01",
  network: "M5 6.5a2 2 0 1 1 0-.01M19 6.5a2 2 0 1 1 0-.01M12 18.5a2 2 0 1 1 0-.01M7 6.5h10M6 8.3l5 8.4M18 8.3l-5 8.4",
  star: "M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z",
};

export type IconName = keyof typeof PATHS;

export default function Icon({ name, size = 20, className, x, y, strokeWidth = 1.75 }: { name: string; size?: number; className?: string; x?: number; y?: number; strokeWidth?: number }) {
  return (
    <svg
      x={x}
      y={y}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d={PATHS[name] ?? PATHS.star} />
    </svg>
  );
}
