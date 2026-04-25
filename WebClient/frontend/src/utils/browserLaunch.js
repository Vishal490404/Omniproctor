export function isSafeTestUrl(value) {
  if (typeof value !== 'string') return false

  try {
    const parsed = new URL(normalizeTestUrl(value))
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    return false
  }
}

export function normalizeTestUrl(value) {
  if (typeof value !== 'string') return ''

  const cleaned = value.trim()
  if (!cleaned) return ''

  return cleaned.includes('://') ? cleaned : `https://${cleaned}`
}

export function buildKioskLaunchUrl(value) {
  if (!isSafeTestUrl(value)) return ''

  const normalizedUrl = new URL(normalizeTestUrl(value)).toString()
  return `omniproctor-browser://open?url=${encodeURIComponent(normalizedUrl)}`
}