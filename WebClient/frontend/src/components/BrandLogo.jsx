import logoUrl from '../assets/logo.svg'

/**
 * The single source of truth for the OmniProctor brand mark across the
 * web dashboard. Mirrors ``Browser/browser/assets/icon.svg`` byte-for-byte
 * so the kiosk window icon, tray icon and dashboard header are visibly
 * the same product.
 */
export function BrandLogo({
  size = 28,
  radius = 8,
  withWordmark = false,
  wordmarkColor,
  className = '',
  style,
}) {
  const img = (
    <img
      src={logoUrl}
      alt="OmniProctor"
      width={size}
      height={size}
      className={withWordmark ? undefined : className}
      style={{ display: 'block', borderRadius: radius, flex: '0 0 auto', ...style }}
    />
  )

  if (!withWordmark) return img

  return (
    <span
      className={className}
      style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}
    >
      {img}
      <span
        style={{
          fontWeight: 700,
          fontSize: Math.max(14, size * 0.6),
          letterSpacing: 0.2,
          color: wordmarkColor,
        }}
      >
        OmniProctor
      </span>
    </span>
  )
}
