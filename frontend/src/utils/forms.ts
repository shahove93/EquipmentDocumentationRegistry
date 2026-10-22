import type { DocumentCreateBody, DocumentOut, DocumentUpdateBody } from '../types/api'

/**
 * The requisites form, and the rules for turning it into a request.
 *
 * A form field is always a string, and every conversion between that string and
 * the wire value lives here so the create form, the edit form and the status
 * warning cannot disagree about what "changed" means. That agreement is not
 * cosmetic: the backend re-opens a decided document only when a significant
 * field's value *really differs*, so a warning computed any other way would
 * either stay silent when the status is about to reset or cry wolf when it is
 * not.
 */

/** The fields as bound to inputs. `''` means "not filled in". */
export interface RequisiteValues {
  /** The string value of the type `<select>`; `''` is "nothing chosen". */
  documentTypeId: string
  number: string
  /** `YYYY-MM-DD` from `<input type="date">`, or `''`. */
  issueDate: string
  validFrom: string
  validTo: string
  /** The string value of the issuer `<select>`; `''` is "no issuer". */
  issuerId: string
  notes: string
}

export const EMPTY_REQUISITES: RequisiteValues = {
  documentTypeId: '',
  number: '',
  issueDate: '',
  validFrom: '',
  validTo: '',
  issuerId: '',
  notes: '',
}

/** `DocumentCreate.number` allows at most this many characters. */
export const NUMBER_MAX_LENGTH = 100

/** The stored document as form values, without inventing anything. */
export function requisitesFromDocument(document: DocumentOut): RequisiteValues {
  return {
    documentTypeId: String(document.document_type_id),
    number: document.number,
    issueDate: document.issue_date ?? '',
    validFrom: document.valid_from ?? '',
    validTo: document.valid_to ?? '',
    issuerId: document.issuer_id === null ? '' : String(document.issuer_id),
    notes: document.notes ?? '',
  }
}

/**
 * A value on the wire, where `null` means "no value".
 *
 * A field is blank exactly when it holds nothing but whitespace, and blank maps
 * to `null` — never to an empty string, which the columns would store as a value
 * that looks filled. Anything else is passed through as typed, including inner
 * spacing, because the form is a faithful view of the record.
 */
function blankToNull(value: string): string | null {
  return value.trim() === '' ? null : value
}

function idOrNull(value: string): number | null {
  return value === '' ? null : Number(value)
}

export interface WireRequisites {
  document_type_id: number | null
  number: string
  issue_date: string | null
  valid_from: string | null
  valid_to: string | null
  issuer_id: number | null
  notes: string | null
}

/**
 * The form's values in the shape the API speaks.
 *
 * `number` is the one field that is trimmed: it is an identifier, so leading or
 * trailing spaces are always a slip, and the schema's minimum length would
 * otherwise accept a number made only of spaces.
 */
export function toWire(values: RequisiteValues): WireRequisites {
  return {
    document_type_id: idOrNull(values.documentTypeId),
    number: values.number.trim(),
    issue_date: blankToNull(values.issueDate),
    valid_from: blankToNull(values.validFrom),
    valid_to: blankToNull(values.validTo),
    issuer_id: idOrNull(values.issuerId),
    notes: blankToNull(values.notes),
  }
}

/** The fields the backend treats as significant; `notes` is deliberately not. */
const SIGNIFICANT_FIELDS = [
  'document_type_id',
  'number',
  'issue_date',
  'valid_from',
  'valid_to',
  'issuer_id',
] as const

export type SignificantField = (typeof SIGNIFICANT_FIELDS)[number]

/** Field name → message. A field that is absent is a field that is fine. */
export type RequisiteErrors = Partial<Record<keyof RequisiteValues, string>>

/**
 * What the form can refuse before a request is made.
 *
 * It mirrors the schema rather than redefining it: the type and the number are
 * the required members, the number has a maximum length, and the two bounds must
 * not be inverted. `YYYY-MM-DD` sorts as text in the same order it sorts in
 * time, so the date check is a string comparison and involves no timezone.
 */
export function validateRequisites(values: RequisiteValues): RequisiteErrors {
  const errors: RequisiteErrors = {}

  if (values.documentTypeId === '') {
    errors.documentTypeId = 'Выберите тип документа.'
  }

  const number = values.number.trim()
  if (number === '') {
    errors.number = 'Укажите номер документа.'
  } else if (number.length > NUMBER_MAX_LENGTH) {
    errors.number = `Номер не длиннее ${NUMBER_MAX_LENGTH} символов.`
  }

  if (values.validFrom !== '' && values.validTo !== '' && values.validTo < values.validFrom) {
    errors.validTo = 'Дата окончания раньше даты начала.'
  }

  return errors
}

export function hasErrors(errors: RequisiteErrors): boolean {
  return Object.keys(errors).length > 0
}

/**
 * Body of `POST /documents`.
 *
 * Optional members are left out entirely when the user did not fill them in: an
 * absent key means "not provided" and the column keeps its own default, which is
 * a different statement from sending `null`. `null` is reserved for the patch
 * path, where clearing a stored value is the point.
 *
 * `null` is returned when the required type is missing. The caller validates
 * first, so this is a guard against sending a body the schema would refuse, not
 * a second validation pass.
 */
export function toCreateBody(values: RequisiteValues): DocumentCreateBody | null {
  const wire = toWire(values)
  if (wire.document_type_id === null) {
    return null
  }

  const body: DocumentCreateBody = {
    document_type_id: wire.document_type_id,
    number: wire.number,
  }
  if (wire.issue_date !== null) body.issue_date = wire.issue_date
  if (wire.valid_from !== null) body.valid_from = wire.valid_from
  if (wire.valid_to !== null) body.valid_to = wire.valid_to
  if (wire.issuer_id !== null) body.issuer_id = wire.issuer_id
  if (wire.notes !== null) body.notes = wire.notes
  return body
}

/**
 * Body of `PATCH /documents/{id}`, carrying only what really changed.
 *
 * Sending a field whose value is unchanged is not merely wasteful: repeating a
 * significant field is what the backend takes as a re-assertion, and it treats
 * an identical value as a no-op precisely so that a save that changed nothing
 * cannot reset a decision. Building the body here keeps the request and the
 * warning below derived from the same comparison.
 *
 * `document_type_id` is never sent as `null`: the column is not nullable, so a
 * cleared select would mean "no type", which is not a state a document can have.
 */
export function toUpdateBody(document: DocumentOut, values: RequisiteValues): DocumentUpdateBody {
  const wire = toWire(values)
  const body: DocumentUpdateBody = {}

  if (wire.document_type_id !== null && wire.document_type_id !== document.document_type_id) {
    body.document_type_id = wire.document_type_id
  }
  if (wire.number !== document.number) body.number = wire.number
  if (wire.issue_date !== document.issue_date) body.issue_date = wire.issue_date
  if (wire.valid_from !== document.valid_from) body.valid_from = wire.valid_from
  if (wire.valid_to !== document.valid_to) body.valid_to = wire.valid_to
  if (wire.issuer_id !== document.issuer_id) body.issuer_id = wire.issuer_id
  if (wire.notes !== document.notes) body.notes = wire.notes

  return body
}

/** Which significant fields the patch would actually rewrite. */
export function changedSignificantFields(
  document: DocumentOut,
  values: RequisiteValues,
): SignificantField[] {
  const body = toUpdateBody(document, values)
  return SIGNIFICANT_FIELDS.filter((field) => body[field] !== undefined)
}

/**
 * Whether saving this form would put the document back into verification.
 *
 * Only a decided document can be re-opened, and only by a real change to a
 * significant field: editing the notes of a verified certificate is an ordinary
 * correction and leaves its decision alone. The warning in the edit form is
 * driven by this function, so what it promises is what the backend will do.
 */
export function willResetVerificationStatus(
  document: DocumentOut,
  values: RequisiteValues,
): boolean {
  return (
    document.verification_status !== 'pending' &&
    changedSignificantFields(document, values).length > 0
  )
}

/** True when a name for a new reference row is usable. */
export function isBlankName(value: string): boolean {
  return value.trim() === ''
}
