import { useId, type ReactNode } from 'react'

type IconProps = { size?: number; strokeWidth?: number }

function Svg({ size = 20, strokeWidth = 1.9, children }: IconProps & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  )
}

export function LogoMark({ size = 38 }: { size?: number }) {
  const id = useId()
  return (
    <svg width={size} height={size} viewBox="0 0 512 512" aria-hidden="true">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#FFB020" />
          <stop offset="0.55" stopColor="#F58220" />
          <stop offset="1" stopColor="#C96C0A" />
        </linearGradient>
      </defs>
      <rect width="512" height="512" rx="110" fill={`url(#${id})`} />
      <rect x="176" y="90" width="160" height="54" rx="18" fill="#fff" />
      <rect x="152" y="126" width="208" height="240" rx="26" fill="#fff" />
      <rect x="178" y="150" width="76" height="48" rx="10" fill="#E5791B" />
      <rect x="186" y="158" width="14" height="32" rx="4" fill="#fff" />
      <rect x="208" y="158" width="14" height="32" rx="4" fill="#fff" />
      <path
        d="M 360 168 C 430 168 430 268 376 268 L 376 294"
        fill="none"
        stroke="#fff"
        strokeWidth="20"
        strokeLinecap="round"
      />
      <rect x="344" y="294" width="88" height="66" rx="18" fill="#fff" />
      <rect x="352" y="302" width="16" height="6" rx="3" fill="#E5791B" />
      <rect x="352" y="314" width="16" height="6" rx="3" fill="#E5791B" />
      <rect x="352" y="326" width="16" height="6" rx="3" fill="#E5791B" />
    </svg>
  )
}

export function IconDashboard(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="3" y="3" width="7.5" height="7.5" rx="2" />
      <rect x="13.5" y="3" width="7.5" height="7.5" rx="2" />
      <rect x="3" y="13.5" width="7.5" height="7.5" rx="2" />
      <rect x="13.5" y="13.5" width="7.5" height="7.5" rx="2" />
    </Svg>
  )
}

export function IconShifts(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3.2 2" />
    </Svg>
  )
}

export function IconFuel(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M5 5h14v4H5z" />
      <rect x="6" y="9" width="12" height="10" rx="2" />
      <path d="M9.5 12h5" />
      <path d="M18 12.5c2 .6 3 2.2 3 4a2.5 2.5 0 0 1-2.5 2.5H18" />
    </Svg>
  )
}

export function IconCredit(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M7 7h11m0 0-3-3m3 3-3 3" />
      <path d="M17 17H6m0 0 3-3m-3 3 3 3" />
    </Svg>
  )
}

export function IconReports(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M5 20v-6" />
      <path d="M12 20V8" />
      <path d="M19 20V4" />
      <path d="M2 20h20" />
    </Svg>
  )
}

export function IconSettings(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="3.2" />
      <path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M19.1 4.9l-1.8 1.8M6.7 17.3l-1.8 1.8" />
    </Svg>
  )
}
