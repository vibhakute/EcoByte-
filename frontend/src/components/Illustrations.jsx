/* Lightweight inline SVG illustrations (no external images needed). */

export function Leaf({ color = '#22a052', vein = '#0f4d2a', ...p }) {
  return (
    <svg viewBox="0 0 40 40" {...p}>
      <path d="M6 34C6 16 16 6 34 6c0 18-10 28-28 28z" fill={color} />
      <path d="M8 32 28 12" stroke={vein} strokeWidth="1.6" strokeLinecap="round" opacity=".45" />
    </svg>
  )
}

export function Globe(props) {
  return (
    <svg viewBox="0 0 220 150" {...props}>
      <defs>
        <radialGradient id="gl-sea" cx="40%" cy="35%" r="70%"><stop offset="0" stopColor="#3fbf74" /><stop offset="1" stopColor="#11663a" /></radialGradient>
      </defs>
      <ellipse cx="110" cy="140" rx="80" ry="8" fill="#0f4d2a" opacity=".12" />
      <path d="M36 128c10-30 26-40 40-38-4 14-18 30-40 38z" fill="#4cc27a" />
      <path d="M184 128c-10-30-26-40-40-38 4 14 18 30 40 38z" fill="#2f9e58" />
      <circle cx="110" cy="78" r="56" fill="url(#gl-sea)" />
      <path d="M78 44c10-6 22-4 26 4s-6 12-2 20-10 14-20 8-14-22-4-32zM120 60c8-8 26-6 30 6s-4 22-14 24-20-4-22-12 0-12 6-18zM96 108c6-4 16-2 18 4s-6 10-12 8-10-8-6-12z" fill="#a7e8bd" opacity=".9" />
      <path d="M110 22c0-12 8-20 22-20 0 12-8 20-22 20z" fill="#4cc27a" />
      <path d="M110 22c0-10-6-16-16-16 0 10 6 16 16 16z" fill="#2f9e58" />
      <path d="M110 22v-8" stroke="#0f4d2a" strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}

export function Sprout(props) {
  return (
    <svg viewBox="0 0 120 120" {...props}>
      <path d="M60 110V58" stroke="#2f9e58" strokeWidth="5" strokeLinecap="round" />
      <path d="M60 62c-2-26-18-40-44-40 0 26 16 40 44 40z" fill="#4cc27a" />
      <path d="M60 52c2-24 18-38 44-38 0 24-16 38-44 38z" fill="#22a052" />
      <ellipse cx="60" cy="112" rx="30" ry="5" fill="#0f4d2a" opacity=".15" />
    </svg>
  )
}

const BOWL = {
  breakfast: { food: '#f6c453', top: '#e9a23b', garnish: '#4cc27a' },
  lunch: { food: '#f0b45c', top: '#d9862f', garnish: '#2f9e58' },
  dinner: { food: '#e7d1a5', top: '#c9a26a', garnish: '#2f9e58' },
}

/** Default food art when a meal has no uploaded photo. */
export function FoodBowl({ meal = 'lunch', ...props }) {
  const c = BOWL[meal] || BOWL.lunch
  return (
    <svg viewBox="0 0 200 150" {...props}>
      <defs>
        <linearGradient id={`bg-${meal}`} x1="0" x2="1" y1="0" y2="1"><stop offset="0" stopColor="#f1faf3" /><stop offset="1" stopColor="#dff3e5" /></linearGradient>
        <linearGradient id={`bw-${meal}`} x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#8a5a2b" /><stop offset="1" stopColor="#5e3a18" /></linearGradient>
      </defs>
      <rect width="200" height="150" fill={`url(#bg-${meal})`} />
      <circle cx="170" cy="22" r="26" fill="#ffffff" opacity=".6" />
      <ellipse cx="100" cy="126" rx="70" ry="8" fill="#0f4d2a" opacity=".12" />
      <path d="M38 78c0 26 28 44 62 44s62-18 62-44z" fill={`url(#bw-${meal})`} />
      <ellipse cx="100" cy="78" rx="62" ry="14" fill="#6e4520" />
      <path d="M44 78c4-20 30-32 56-32s52 12 56 32c-14 8-34 11-56 11s-42-3-56-11z" fill={c.food} />
      {[[70, 66], [86, 60], [104, 58], [122, 63], [136, 70], [78, 74], [98, 70], [116, 74], [92, 80], [128, 79]].map(([x, y], i) => (
        <ellipse key={i} cx={x} cy={y} rx="5" ry="2.6" fill={c.top} transform={`rotate(${(i * 37) % 60 - 30} ${x} ${y})`} />
      ))}
      <path d="M92 52c4-10 14-14 22-12-2 9-12 14-22 12z" fill={c.garnish} />
      <path d="M108 50c6-6 14-6 18-2-5 5-13 6-18 2z" fill="#4cc27a" />
      <circle cx="76" cy="64" r="3" fill="#e5484d" /><circle cx="130" cy="66" r="3" fill="#e5484d" />
      <path d="M78 30c-4 6 4 8 0 14M100 24c-4 6 4 8 0 14M122 30c-4 6 4 8 0 14" stroke="#b8c9bd" strokeWidth="2.4" fill="none" strokeLinecap="round" opacity=".8" />
    </svg>
  )
}

export function GiftBox(props) {
  return (
    <svg viewBox="0 0 120 120" {...props}>
      <ellipse cx="60" cy="110" rx="38" ry="5" fill="#0f4d2a" opacity=".12" />
      <rect x="22" y="52" width="76" height="54" rx="6" fill="#f97316" />
      <rect x="16" y="38" width="88" height="20" rx="5" fill="#fb923c" />
      <rect x="53" y="38" width="14" height="68" fill="#fde047" />
      <path d="M60 38c-10-18-30-16-26-4 3 8 18 6 26 4zM60 38c10-18 30-16 26-4-3 8-18 6-26 4z" fill="#facc15" />
      <path d="M96 20l3 6 6 3-6 3-3 6-3-6-6-3 6-3zM24 24l2 4 4 2-4 2-2 4-2-4-4-2 4-2z" fill="#facc15" />
    </svg>
  )
}

/** Meal image with graceful fallback to the illustration. */
export function MealImage({ src, meal, className = 'food-thumb', alt = '' }) {
  if (src) return <img className={className} src={src} alt={alt} loading="lazy" />
  return <FoodBowl meal={meal} className={className} role="img" aria-label={alt || `${meal} illustration`} />
}

const BG = { beverage: ['#fff4e5', '#fde2bf'], snack: ['#eaf7ee', '#d3eedb'], meal: ['#eaf2fd', '#d6e5fa'], dessert: ['#fdeef3', '#f8d6e3'] }

/** Category art for store items without a photo. */
export function ProductArt({ category = 'snack', name = '', ...props }) {
  const [a, b] = BG[category] || BG.snack
  const id = `pa-${category}`
  const tea = /tea|coffee|chai/i.test(name)
  return (
    <svg viewBox="0 0 200 130" {...props}>
      <defs><linearGradient id={id} x1="0" x2="1" y1="0" y2="1"><stop offset="0" stopColor={a} /><stop offset="1" stopColor={b} /></linearGradient></defs>
      <rect width="200" height="130" fill={`url(#${id})`} />
      <ellipse cx="100" cy="112" rx="56" ry="6" fill="#0f4d2a" opacity=".1" />
      {category === 'beverage' && (tea || !/drink|lassi/i.test(name) ? (
        <g>
          <path d="M66 52h58l-6 50a8 8 0 0 1-8 7H80a8 8 0 0 1-8-7Z" fill="#fff" stroke="#d9c7a8" strokeWidth="2" />
          <path d="M70 60h50l-1 8H71Z" fill={/coffee/i.test(name) ? '#6b3f1f' : '#b8743a'} />
          <path d="M124 62c14 0 16 22 0 24" fill="none" stroke="#d9c7a8" strokeWidth="5" strokeLinecap="round" />
          <path d="M84 30c-5 7 5 9 0 16M96 26c-5 7 5 9 0 16M108 30c-5 7 5 9 0 16" stroke="#b8c9bd" strokeWidth="3" fill="none" strokeLinecap="round" />
        </g>
      ) : (
        <g>
          <path d="M82 28h36l-4 80H86Z" fill={/lassi/i.test(name) ? '#fffbe9' : '#e5484d'} stroke="#e7d9c4" strokeWidth="2" />
          <rect x="84" y="50" width="32" height="18" fill="#fff" opacity=".7" />
          <path d="M104 14l-2 16" stroke="#2f9e58" strokeWidth="4" strokeLinecap="round" />
        </g>
      ))}
      {category === 'snack' && (/samosa/i.test(name) ? (
        <g><path d="M60 100L100 30l40 70Z" fill="#e9a23b" /><path d="M75 100L100 52l25 48Z" fill="#f2bd5e" /><circle cx="148" cy="96" r="10" fill="#2f9e58" /></g>
      ) : /maggi|noodle/i.test(name) ? (
        <g><path d="M54 66h92c0 26-20 42-46 42s-46-16-46-42Z" fill="#f97316" />
          {[0, 1, 2, 3, 4].map(i => <path key={i} d={`M${66 + i * 16} 66c6-14 10 6 16-10`} stroke="#fde047" strokeWidth="4" fill="none" strokeLinecap="round" />)}</g>
      ) : /sandwich/i.test(name) ? (
        <g><path d="M50 98L150 98 100 40Z" fill="#f5d18e" /><path d="M58 92h84" stroke="#4caf50" strokeWidth="6" /><path d="M64 84h72" stroke="#e5484d" strokeWidth="4" /></g>
      ) : (
        <g><ellipse cx="100" cy="86" rx="52" ry="18" fill="#fff" stroke="#e7d9c4" strokeWidth="2" />
          <ellipse cx="100" cy="80" rx="40" ry="12" fill="#f6c453" />{[0, 1, 2, 3].map(i => <circle key={i} cx={80 + i * 13} cy={78 + (i % 2) * 4} r="3" fill="#2f9e58" />)}</g>
      ))}
      {category === 'meal' && <FoodBowlInline />}
      {category === 'dessert' && (
        <g><ellipse cx="100" cy="92" rx="50" ry="14" fill="#fff" stroke="#e7d9c4" strokeWidth="2" />
          <circle cx="86" cy="80" r="15" fill="#8b3a1a" /><circle cx="114" cy="80" r="15" fill="#9c4520" /><path d="M76 74c8-4 18-4 24 0" stroke="#fff" strokeOpacity=".4" strokeWidth="3" fill="none" /></g>
      )}
    </svg>
  )
}

function FoodBowlInline() {
  return (
    <g><path d="M52 66c0 24 22 40 48 40s48-16 48-40Z" fill="#7a4a22" /><ellipse cx="100" cy="66" rx="48" ry="11" fill="#5e3a18" />
      <path d="M56 66c4-15 24-24 44-24s40 9 44 24c-12 6-28 8-44 8s-32-2-44-8Z" fill="#f0b45c" />
      <path d="M92 44c4-8 12-10 18-8-2 7-10 10-18 8Z" fill="#2f9e58" /></g>
  )
}

export function ProductImage({ src, category, name }) {
  if (src) return <img className="food-thumb" style={{ aspectRatio: '200 / 130', borderRadius: 0 }} src={src} alt={name} loading="lazy" />
  return <ProductArt category={category} name={name} style={{ width: '100%', display: 'block', aspectRatio: '200 / 130' }} role="img" aria-label={name} />
}
