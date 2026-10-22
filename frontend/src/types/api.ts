/**
 * Types mirroring the FastAPI response schemas the registry screen consumes.
 *
 * They are written by hand rather than generated: the surface is small and the
 * backend already publishes its own OpenAPI document, so a generator would add
 * a build step for very little. Field names match the JSON exactly, which is
 * what `from_attributes` schemas emit.
 */

/** `ck_documents_verification_status` allows exactly these three values. */
export type VerificationStatus = 'pending' | 'verified' | 'rejected'

/** `DocumentOut` — a stored document, as returned by `GET /documents`. */
export interface DocumentOut {
  id: number
  document_type_id: number
  number: string
  issue_date: string | null
  valid_from: string | null
  valid_to: string | null
  issuer_id: number | null
  verification_status: VerificationStatus
  notes: string | null
}

/** `DocumentTypeRead` — one entry of the editable document-type reference. */
export interface DocumentTypeRead {
  id: number
  name: string
}

/** `IssuerRead` — one entry of the issuing-authority reference. */
export interface IssuerRead {
  id: number
  name: string
}

/** `ProductRead` — a product, as returned by `GET /products/{product_id}`. */
export interface ProductRead {
  id: number
  name: string
  standard: string
  manufacturer_id: number
  designation: string | null
  product_type: string | null
}

/**
 * `ProductVariantRead` — one covered size of a covered product.
 *
 * It carries `product_id` only: the product's name and standard live behind
 * `GET /products/{product_id}`, which is why a reader of these rows has to
 * resolve them separately.
 */
export interface ProductVariantRead {
  id: number
  product_id: number
  size_text: string
  diameter: string | null
  nominal_diameter: string | null
  wall_thickness: string | null
}

/**
 * `FileOut` — attachment metadata. The bytes are not part of this shape; they
 * come from a separate route that returns the stored content.
 */
export interface FileOut {
  id: number
  document_id: number
  original_filename: string
  mime_type: string
  size_bytes: number
  sha256: string
  uploaded_at: string
}

/**
 * `ck_document_verification_events_event_type` allows exactly these three.
 *
 * `event_type` states why a transition happened rather than restating the
 * target, so `reopened` is a distinct outcome and not another name for
 * "pending".
 */
export type VerificationEventType = 'verified' | 'rejected' | 'reopened'

/**
 * `DocumentVerificationEventOut` — one recorded verification transition.
 *
 * `reason` has two meanings sharing one column: for `rejected` it is a human
 * explanation, for `reopened` one of the closed machine codes
 * (`significant_fields_changed`, `file_added`, `file_deleted`). It is `null`
 * when nothing was recorded. The statuses are kept as plain strings because the
 * interface must still render a value the vocabulary does not know.
 */
export interface DocumentVerificationEventOut {
  id: number
  document_id: number
  from_status: string
  to_status: string
  event_type: string
  reason: string | null
  created_at: string
}

/** `ManufacturerRead` — one entry of the manufacturer reference. */
export interface ManufacturerRead {
  id: number
  name: string
}

/**
 * Query parameters accepted by `GET /documents`.
 *
 * `limit` and `offset` are always sent; the rest are omitted when empty, because
 * the backend refuses a blank text filter with 422 instead of reading it as "no
 * filter". `size_text` is an exact match; the other strings are
 * case-insensitive substrings.
 */
export interface DocumentSearchParams {
  number?: string
  material?: string
  size_text?: string
  standard?: string
  manufacturer_id?: number
  status?: VerificationStatus
  limit: number
  offset: number
}

/**
 * Body of `POST /documents` (`DocumentCreate`).
 *
 * `document_type_id` and `number` are the only required members, so the optional
 * ones are left out entirely when the user did not fill them in — an absent key
 * means "not provided" and lets the column's own default apply, which is not the
 * same statement as sending `null`.
 */
export interface DocumentCreateBody {
  document_type_id: number
  number: string
  issue_date?: string
  valid_from?: string
  valid_to?: string
  issuer_id?: number
  notes?: string
}

/**
 * Body of `PATCH /documents/{document_id}` (`DocumentUpdate`).
 *
 * Every member is optional and the endpoint applies only the keys present, so a
 * patch is built from the fields that actually changed. Here `null` is
 * meaningful: it is how a stored value is cleared.
 *
 * `verification_status` is deliberately absent — the schema does not accept it,
 * and the status is only ever moved by the backend as a consequence of a data
 * change.
 */
export interface DocumentUpdateBody {
  document_type_id?: number
  number?: string
  issue_date?: string | null
  valid_from?: string | null
  valid_to?: string | null
  issuer_id?: number | null
  notes?: string | null
}

/**
 * The two decisions `POST /documents/{document_id}/verification` accepts.
 *
 * `DocumentVerificationRequest` is a closed literal, so anything else is a
 * `422` — the interface never needs to invent a third outcome.
 */
export type VerificationDecision = 'verified' | 'rejected'

/**
 * Body of `POST /documents/{document_id}/verification`.
 *
 * One route carries both verdicts. `reason` is the auditor's explanation for a
 * rejection and is required there; when confirming it carries no meaning and is
 * sent as `null` so both decisions produce the same body shape. The backend
 * passes the text through unchanged, so what is typed is what gets recorded.
 *
 * The schema is `extra="forbid"` and has no status field: the target status is
 * expressed by `decision` alone and never requested directly.
 */
export interface DocumentVerificationBody {
  decision: VerificationDecision
  reason: string | null
}

/** `ManufacturerCreate` — the only field the reference accepts. */
export interface ManufacturerCreateBody {
  name: string
}

/**
 * `ProductCreate` — a product as the create form sends it.
 *
 * Per ADR-005 the SDR belongs to `name` ("Труба ПЭ100 SDR11"), so there is no
 * SDR field to fill in. `standard` is the ГОСТ/ТУ and is required by the schema,
 * not merely by the form. The two optional members are omitted when blank rather
 * than sent as `null`: the column keeps its own default and nothing invents a
 * value.
 */
export interface ProductCreateBody {
  name: string
  standard: string
  manufacturer_id: number
  designation?: string
  product_type?: string
}

/**
 * `ProductVariantCreateBody` — one size of a product.
 *
 * `product_id` comes from the path. `size_text` is the designation and the only
 * required member; the measurements are optional because ADR-006 makes
 * `(product_id, size_text)` the identity, not a numeric diameter. The backend
 * stores them as `NUMERIC(10, 2)` and refuses more than two decimal places
 * instead of rounding, so they are sent as numbers and validated before sending.
 */
export interface ProductVariantCreateBody {
  size_text: string
  diameter?: number
  nominal_diameter?: number
  wall_thickness?: number
}
