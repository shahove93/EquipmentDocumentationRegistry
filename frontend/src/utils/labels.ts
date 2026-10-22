/**
 * Russian wording for the closed vocabularies the API returns.
 *
 * Every function here falls back to the value it was given. The vocabularies
 * are enforced by database check constraints, so an unknown member would mean
 * the backend grew a value this file has not learned yet — and showing the raw
 * code is honest, where inventing a plausible translation would not be. Nothing
 * in this module invents a value that was not returned.
 */

const STATUS_LABELS: Record<string, string> = {
  pending: 'На проверке',
  verified: 'Подтверждён',
  rejected: 'Отклонён',
}

/** `ck_document_verification_events_event_type`: why a transition happened. */
const EVENT_LABELS: Record<string, string> = {
  verified: 'Подтверждение',
  rejected: 'Отклонение',
  reopened: 'Возврат на проверку',
}

/**
 * The closed set of machine codes a `reopened` event carries
 * (`app/services/verification_history.py`). A `rejected` event puts human text
 * in the same column, so an unrecognised value is passed through untouched
 * rather than guessed at.
 */
const REOPEN_REASON_LABELS: Record<string, string> = {
  significant_fields_changed: 'Изменены значимые реквизиты',
  file_added: 'Добавлено вложение',
  file_deleted: 'Удалено вложение',
}

/** The MIME types the upload route accepts, with a short human name. */
const MIME_LABELS: Record<string, string> = {
  'application/pdf': 'PDF',
  'image/jpeg': 'JPEG',
  'image/png': 'PNG',
}

export function labelForStatus(status: string): string {
  return STATUS_LABELS[status] ?? status
}

export function labelForEventType(eventType: string): string {
  return EVENT_LABELS[eventType] ?? eventType
}

/**
 * Translate a recorded reason, or return `null` when there is none.
 *
 * `null` and the empty string both mean "nothing was recorded", which the
 * caller renders as an em dash. A reason that is not a known machine code is
 * returned as-is: it is the auditor's own wording and must not be replaced.
 */
export function labelForReason(reason: string | null): string | null {
  if (reason === null || reason === '') {
    return null
  }
  return REOPEN_REASON_LABELS[reason] ?? reason
}

export function labelForMimeType(mimeType: string): string {
  return MIME_LABELS[mimeType] ?? mimeType
}
