import logoUrl from '../assets/logo.svg'

/**
 * The single source of truth for the OmniProctor brand mark across the
 * web dashboard. Mirrors ``Browser/browser/assets/icon.svg`` byte-for-byte
 * so the kiosk window icon, tray icon and dashboard header are visibly
 * the same product.
 */
export function BrandLogo({ size = 28, withWordmark = false, className = '' }) {
  const img = (
    <img
      src={logoUrl}
      alt="OmniProctor"
      width={size}
      height={size}
      style={{ display: 'block', borderRadius: 8 }}
    />
  )

  if (!withWordmark) return img

  return (
    <span
      className={className}
      style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}
    >
      {img}
      <span style={{ fontWeight: 700, fontSize: size * 0.6, letterSpacing: 0.2 }}>
        Omniproctor
      </span>
    </span>
  )
}
