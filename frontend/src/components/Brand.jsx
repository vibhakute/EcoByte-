/* EcoByte brand: leaf + fork mark, two-tone wordmark, canteen scene (all inline SVG). */

export function BrandMark({ size = 56, ...p }) {
  return (
    <svg viewBox="0 0 120 112" width={size} height={size * 112 / 120} aria-hidden="true" {...p}>
      <defs>
        <linearGradient id="bm-big" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stopColor="#15803d" /><stop offset="1" stopColor="#6cc04a" /></linearGradient>
        <linearGradient id="bm-left" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#0c4a24" /><stop offset="1" stopColor="#1e8a43" /></linearGradient>
      </defs>
      <path d="M6 70C12 42 38 32 60 42 51 66 30 80 6 70Z" fill="url(#bm-left)" />
      <path d="M45 36C40 20 47 7 62 2c5 14-2 27-17 34Z" fill="#2c9c4c" />
      <path d="M38 108C31 72 50 26 114 6c5 50-22 88-76 102Z" fill="url(#bm-big)" />
      <g transform="rotate(34 77 60)" fill="#fff">
        <rect x="74" y="54" width="6.5" height="40" rx="3.2" />
        <rect x="67.5" y="20" width="3.6" height="18" rx="1.8" />
        <rect x="75.4" y="18" width="3.6" height="20" rx="1.8" />
        <rect x="83.3" y="20" width="3.6" height="18" rx="1.8" />
        <path d="M67.5 34h19.4c0 10-4.4 18-9.7 20.5C71.9 52 67.5 44 67.5 34Z" />
      </g>
    </svg>
  )
}

export function Wordmark({ size = 40, tagline = true, light = false }) {
  return (
    <div style={{ lineHeight: 1 }}>
      <div style={{ fontSize: size, fontWeight: 800, letterSpacing: '-0.035em' }}>
        <span style={{ color: light ? '#fff' : '#14532d' }}>Eco</span><span style={{ color: light ? '#9be07a' : '#4caf32' }}>Byte</span>
      </div>
      {tagline && (
        <div style={{ position: 'relative', display: 'inline-block', marginTop: size * 0.16 }}>
          <span style={{ fontStyle: 'italic', fontSize: Math.max(12, size * 0.4), color: light ? '#cfe8d8' : '#1d3b26', fontWeight: 500 }}>Reduce Waste. Feed Better.</span>
          <svg viewBox="0 0 160 14" style={{ position: 'absolute', right: -6, bottom: -size * 0.32, width: '62%', height: size * 0.3 }} aria-hidden="true">
            <path d="M4 11C50 2 110 1 156 4" fill="none" stroke="#3fae3a" strokeWidth="3" strokeLinecap="round" />
          </svg>
        </div>
      )}
    </div>
  )
}

export function BrandLogo({ size = 40, tagline = true, light = false }) {
  return (
    <div className="row" style={{ gap: size * 0.3, alignItems: 'center' }}>
      <BrandMark size={size * 1.9} />
      <Wordmark size={size} tagline={tagline} light={light} />
    </div>
  )
}

/** Canteen building with trees and lawn, used on the login page. */
export function CanteenScene(props) {
  return (
    <svg viewBox="0 0 640 300" preserveAspectRatio="xMidYMax slice" aria-hidden="true" {...props}>
      <defs>
        <linearGradient id="cs-sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#ffffff" stopOpacity="0" /><stop offset="1" stopColor="#e6f5e9" /></linearGradient>
        <linearGradient id="cs-wall" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#efe4d2" /><stop offset="1" stopColor="#dccbb0" /></linearGradient>
        <linearGradient id="cs-glass" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#3d4a44" /><stop offset="1" stopColor="#1f2a25" /></linearGradient>
        <linearGradient id="cs-lawn" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#6cc04a" /><stop offset="1" stopColor="#2f8f3c" /></linearGradient>
      </defs>
      <rect width="640" height="300" fill="url(#cs-sky)" />
      {/* background trees */}
      {[[470, 120, 46], [520, 110, 40], [575, 128, 44], [612, 118, 36]].map(([x, y, r], i) => (
        <g key={i}><rect x={x - 3} y={y + r * 0.6} width="6" height="40" fill="#6b4f2a" /><circle cx={x} cy={y} r={r} fill={i % 2 ? '#3f9f45' : '#58b24c'} /></g>
      ))}
      {/* building */}
      <path d="M120 112L455 86v118H120Z" fill="url(#cs-wall)" />
      <path d="M110 108L465 80l2 10-357 28Z" fill="#cbb999" />
      <path d="M150 122L420 101v34L150 154Z" fill="#3f4643" />
      <text x="0" y="0" transform="translate(196 146) rotate(-4.4)" fill="#f4f1ea" fontFamily="Inter, Arial, sans-serif" fontWeight="800" fontSize="25" letterSpacing="4">CANTEEN</text>
      <path d="M150 160L420 142v62H150Z" fill="url(#cs-glass)" />
      {[0, 1, 2, 3, 4, 5, 6].map(i => <rect key={i} x={160 + i * 37} y={156 - i * 2.4} width="3" height={50 + i * 2.4} fill="#c9b796" />)}
      {[0, 1, 2, 3, 4, 5].map(i => <rect key={i} x={170 + i * 37} y={175 - i * 2.4} width="22" height="6" rx="2" fill="#e9d9b8" opacity=".55" />)}
      <rect x="100" y="204" width="380" height="8" fill="#e7dcc8" />
      <rect x="90" y="212" width="400" height="7" fill="#d8ccb4" />
      {/* lawn & hedges */}
      <path d="M0 230C120 214 260 220 380 226s200 2 260-6V300H0Z" fill="url(#cs-lawn)" />
      {[[40, 206, 34], [80, 214, 28], [118, 216, 22], [500, 214, 26], [540, 210, 30]].map(([x, y, r], i) => (
        <ellipse key={i} cx={x} cy={y} rx={r} ry={r * 0.7} fill={i % 2 ? '#2f8f3c' : '#3fa34a'} />
      ))}
      {/* foreground tree */}
      <rect x="44" y="120" width="10" height="100" fill="#5b4122" />
      <circle cx="50" cy="104" r="48" fill="#3c9a43" /><circle cx="22" cy="128" r="30" fill="#4caf50" /><circle cx="84" cy="124" r="32" fill="#2f8a3b" />
      {[[30, 92], [62, 80], [72, 110], [40, 120]].map(([x, y], i) => <circle key={i} cx={x} cy={y} r="4" fill="#f4f7f2" opacity=".85" />)}
    </svg>
  )
}

/** Soft green waves for page corners. */
export function Waves(props) {
  return (
    <svg viewBox="0 0 600 300" preserveAspectRatio="none" aria-hidden="true" {...props}>
      <path d="M0 260C160 230 300 120 600 90V300H0Z" fill="#cdebd4" opacity=".55" />
      <path d="M120 300C260 250 400 170 600 160V300Z" fill="#7fc98f" opacity=".45" />
      <path d="M300 300C400 270 500 240 600 236V300Z" fill="#2f8f4e" opacity=".75" />
    </svg>
  )
}
