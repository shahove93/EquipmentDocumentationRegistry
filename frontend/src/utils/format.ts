/**
 * Format an ISO date (`YYYY-MM-DD`) as `DD.MM.YYYY`.
 *
 * The backend serialises `date` columns without a time zone, so the value is
 * taken literally and no timezone conversion is applied. A missing value — an
 * open-ended validity window is legitimate — renders as an em dash.
 */
export function formatDate(value: string | null): string {
  if (!value) {
    return '—'
  }
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value)
  if (match === null) {
    return value
  }
  const [, year, month, day] = match
  return `${day}.${month}.${year}`
}

const DATE_TIME_FORMATTER = new Intl.DateTimeFormat('ru-RU', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

/**
 * Format a timestamp as `DD.MM.YYYY, HH:MM` in the reader's zone.
 *
 * Unlike `formatDate`, these values are instants: the history and upload
 * timestamps come from `DateTime(timezone=True)` columns, so they arrive as
 * ISO-8601 with an offset. Rendering them in local time is deliberate — the
 * offset makes the instant unambiguous either way. A value the runtime cannot
 * parse is shown untouched rather than replaced by a plausible-looking date.
 */
export function formatDateTime(value: string | null): string {
  if (!value) {
    return '—'
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return DATE_TIME_FORMATTER.format(parsed)
}

const BYTE_UNITS = ['КБ', 'МБ', 'ГБ', 'ТБ']

/**
 * Format a byte count for humans.
 *
 * Binary multiples (1024) rather than decimal ones, because that is what the
 * stored sizes and every file manager on the machine mean. A negative or
 * non-finite value cannot describe a stored blob and is shown as an em dash
 * instead of a nonsense size.
 */
export function formatBytes(value: number | null): string {
  if (value === null || !Number.isFinite(value) || value < 0) {
    return '—'
  }
  if (value < 1024) {
    return `${value} Б`
  }
  let scaled = value / 1024
  let unit = 0
  while (scaled >= 1024 && unit < BYTE_UNITS.length - 1) {
    scaled /= 1024
    unit += 1
  }
  return `${scaled.toLocaleString('ru-RU', { maximumFractionDigits: 1 })} ${BYTE_UNITS[unit]}`
}
