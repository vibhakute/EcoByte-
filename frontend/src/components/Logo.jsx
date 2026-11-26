export function LeafIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M5 19c0-8 5-13 14-13 0 9-5 14-13 14l-1-1z" />
      <path d="M5 19l7-7" />
    </svg>
  )
}

export default function Logo({ sub }) {
  return (
    <div className="logo">
      <span className="logo-mark"><LeafIcon /></span>
      <span>EcoByte{sub && <small>{sub}</small>}</span>
    </div>
  )
}
