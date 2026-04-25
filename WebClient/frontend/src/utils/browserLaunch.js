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

export function buildKioskLaunchUrl(value, telemetry = {}) {
  if (!isSafeTestUrl(value)) return ''

  const normalizedUrl = new URL(normalizeTestUrl(value)).toString()
  const params = new URLSearchParams({ url: normalizedUrl })

  // Telemetry config (all optional; the kiosk silently no-ops if any
  // required field is missing). When provided, the kiosk batch-posts
  // proctoring events and polls for teacher warnings.
  if (telemetry.apiBase) params.set('api_base', telemetry.apiBase)
  if (telemetry.attemptId) params.set('attempt_id', String(telemetry.attemptId))
  if (telemetry.token) params.set('token', telemetry.token)
  if (telemetry.testId) params.set('test_id', String(telemetry.testId))
  if (telemetry.studentId) params.set('student_id', String(telemetry.studentId))

  return `omniproctor-browser://open?${params.toString()}`
}