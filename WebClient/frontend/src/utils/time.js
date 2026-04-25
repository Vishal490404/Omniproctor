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

export function getTestStatus(test, currentTime = new Date()) {
  const start = new Date(test?.start_time)
  const end = new Date(test?.end_time)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return 'Unknown'
  if (!test?.is_active) return 'Inactive'
  if (currentTime < start) return 'Upcoming'
  if (currentTime > end) return 'Expired'
  return 'Active'
}