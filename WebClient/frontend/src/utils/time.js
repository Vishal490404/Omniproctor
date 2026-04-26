const IST_FORMATTER = new Intl.DateTimeFormat('en-IN', {
  timeZone: 'Asia/Kolkata',
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

export function formatDateIST(value) {
  if (!value) return '—'

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'

  return `${IST_FORMATTER.format(date)} IST`
}

/**
 * Short, human-friendly elapsed time. Returns "just now", "Ns ago",
 * "Nm ago" or "Nh ago". Used by the live monitoring dashboard and the
 * warning composer history list, where absolute timestamps add noise.
 */
export function relativeTime(value) {
  if (!value) return '—'

  const then = new Date(value).getTime()
  if (Number.isNaN(then)) return '—'

  const delta = Math.max(0, Date.now() - then)
  if (delta < 5_000) return 'just now'
  if (delta < 60_000) return `${Math.floor(delta / 1000)}s ago`
  if (delta < 3_600_000) return `${Math.floor(delta / 60_000)}m ago`
  if (delta < 86_400_000) return `${Math.floor(delta / 3_600_000)}h ago`
  return `${Math.floor(delta / 86_400_000)}d ago`
}

export function toUtcIsoFromLocalDateTime(value) {
  if (!value) return ''

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''

  return date.toISOString()
}

export function toLocalDateTimeInputValue(value) {
  if (!value) return ''

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''

  const pad = (number) => String(number).padStart(2, '0')
  const year = date.getFullYear()
  const month = pad(date.getMonth() + 1)
  const day = pad(date.getDate())
  const hours = pad(date.getHours())
  const minutes = pad(date.getMinutes())
  return `${year}-${month}-${day}T${hours}:${minutes}`
}

/**
 * Build a default {start, end} pair for the create-test form.
 *
 * Start = "now" rounded UP to the next 5-minute boundary so the picker
 * never shows a slot that is already in the past by the time the user
 * looks at the form.
 *
 * End = start + ``durationMinutes`` (defaults to 60 i.e. 1 hour).
 *
 * Both values are returned as ``YYYY-MM-DDTHH:MM`` strings suitable for
 * a native ``<input type="datetime-local">`` element.
 */
export function getDefaultTestWindow(durationMinutes = 60) {
  const ROUND_TO_MIN = 5
  const now = new Date()
  const remainder = now.getMinutes() % ROUND_TO_MIN
  if (remainder !== 0 || now.getSeconds() > 0 || now.getMilliseconds() > 0) {
    now.setMinutes(now.getMinutes() + (ROUND_TO_MIN - remainder))
  }
  now.setSeconds(0, 0)

  const end = new Date(now.getTime() + durationMinutes * 60 * 1000)

  return {
    start_time: toLocalDateTimeInputValue(now),
    end_time: toLocalDateTimeInputValue(end),
  }
}

export function getTestStatus(test, currentTime = new Date()) {
  const start = new Date(test?.start_time)
  const end = new Date(test?.end_time)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return 'Unknown'
  if (!test?.is_active) return 'Inactive'
  if (currentTime < start) return 'Upcoming'
  if (currentTime > end) return 'Expired'
  return 'Active'
}