import { apiDelete, apiGet, apiPatch, apiPost, apiPostForm, apiPut } from './client'
import type {
  DocumentCreateBody,
  DocumentOut,
  DocumentSearchParams,
  DocumentUpdateBody,
  DocumentVerificationBody,
  DocumentVerificationEventOut,
  FileOut,
  ProductVariantRead,
} from '../types/api'

/**
 * The upload ceiling the backend enforces (`MAX_UPLOAD_SIZE_BYTES`).
 *
 * It is a setting, not a published contract, so this copy is only a courtesy
 * check made before the file is sent; the server stays the authority and its
 * `413` is what the interface actually reports. A file that passes here and is
 * still refused is therefore the expected outcome when the setting is lowered,
 * not a bug.
 */
export const MAX_UPLOAD_SIZE_BYTES = 100 * 1024 * 1024

/**
 * Build the query string for `GET /documents`.
 *
 * Empty strings and `undefined` are dropped rather than sent: the backend
 * rejects a blank text filter with 422 on purpose, so an untouched field must
 * not become a parameter at all. `limit` and `offset` are always present.
 */
export function buildDocumentsQuery(params: DocumentSearchParams): string {
  const search = new URLSearchParams()
  search.set('limit', String(params.limit))
  search.set('offset', String(params.offset))

  if (params.number) search.set('number', params.number)
  if (params.material) search.set('material', params.material)
  if (params.size_text) search.set('size_text', params.size_text)
  if (params.standard) search.set('standard', params.standard)
  if (params.status) search.set('status', params.status)
  if (params.manufacturer_id !== undefined) {
    search.set('manufacturer_id', String(params.manufacturer_id))
  }

  return search.toString()
}

/** Fetch one page of documents. A bare JSON array, `id` ascending. */
export function fetchDocuments(
  params: DocumentSearchParams,
  signal?: AbortSignal,
): Promise<DocumentOut[]> {
  return apiGet<DocumentOut[]>(`/documents?${buildDocumentsQuery(params)}`, signal)
}

/**
 * The document-scoped reads behind the card. Each answers `404` when the
 * document itself does not exist, and an empty array when it exists but has no
 * rows in that collection — an empty collection is not an absent document.
 */

/** `GET /documents/{document_id}`. `404` when the document is unknown. */
export function fetchDocument(documentId: number, signal?: AbortSignal): Promise<DocumentOut> {
  return apiGet<DocumentOut>(`/documents/${documentId}`, signal)
}

/** The covered product variants, ordered by id by the backend. */
export function fetchDocumentVariants(
  documentId: number,
  signal?: AbortSignal,
): Promise<ProductVariantRead[]> {
  return apiGet<ProductVariantRead[]>(`/documents/${documentId}/variants`, signal)
}

/** Attachment metadata only; the bytes come from `attachmentContentUrl`. */
export function fetchDocumentFiles(documentId: number, signal?: AbortSignal): Promise<FileOut[]> {
  return apiGet<FileOut[]>(`/documents/${documentId}/files`, signal)
}

/** The verification transitions, in the chronological order the API returns. */
export function fetchVerificationHistory(
  documentId: number,
  signal?: AbortSignal,
): Promise<DocumentVerificationEventOut[]> {
  return apiGet<DocumentVerificationEventOut[]>(
    `/documents/${documentId}/verification-history`,
    signal,
  )
}

/**
 * The relative URL of one attachment's stored bytes.
 *
 * This is a URL, not a request: downloading is a browser navigation, and the
 * route answers with the raw content type plus a `Content-Disposition` the
 * client must not second-guess. Sending it through the JSON client instead
 * would mean parsing the body as JSON, losing the header, and — for the error
 * cases — showing a blob the UI cannot inspect.
 *
 * The path is left relative so it goes through the dev-server proxy on the same
 * origin. The proxy rule for `/documents` only hands HTML navigations on
 * `/documents/<id>` back to the SPA, so this deeper path reaches the backend.
 */
export function attachmentContentUrl(documentId: number, fileId: number): string {
  return `/documents/${documentId}/files/${fileId}/content`
}

/**
 * The document-scoped writes. Each one leaves the caller's state alone until it
 * resolves: nothing is inserted into a list or written over a row optimistically,
 * because the row that is shown has to be the row the server confirmed.
 */

/** `POST /documents` — `201` with the stored document. */
export function createDocument(
  body: DocumentCreateBody,
  signal?: AbortSignal,
): Promise<DocumentOut> {
  return apiPost<DocumentOut>('/documents', body, signal)
}

/**
 * `PATCH /documents/{document_id}` — `200` with the stored document.
 *
 * The body is built by `toUpdateBody`, which sends only the fields whose value
 * really differs: the backend treats an unchanged value as a no-op and, more
 * importantly, an unchanged *significant* field must not be able to reset the
 * verification status. `null` is sent for a value the user cleared, which is how
 * the patch says "remove this" rather than "leave it alone".
 */
export function updateDocument(
  documentId: number,
  body: DocumentUpdateBody,
  signal?: AbortSignal,
): Promise<DocumentOut> {
  return apiPatch<DocumentOut>(`/documents/${documentId}`, body, signal)
}

/**
 * `POST /documents/{document_id}/verification` — `200` with the stored document.
 *
 * The server is the only judge of whether a decision is allowed, so nothing is
 * pre-decided here: a confirmation without an attachment comes back as `422`,
 * an unknown document as `404`, and a repeated decision as an idempotent `200`
 * that leaves the history alone. The returned document is the one the card
 * shows afterwards — the interface never derives the new status itself, and it
 * writes no history event of its own.
 */
export function submitDocumentVerification(
  documentId: number,
  body: DocumentVerificationBody,
  signal?: AbortSignal,
): Promise<DocumentOut> {
  return apiPost<DocumentOut>(`/documents/${documentId}/verification`, body, signal)
}

/**
 * `POST /documents/{document_id}/files` — `201` with the new attachment.
 *
 * The file goes as multipart under the field name the route declares. The
 * `Content-Type` is not set by hand: only the browser knows the boundary it
 * generated, and a written-out value would leave the server unable to split the
 * parts. A refusal comes back as `413` for size, `422` for a content type the
 * signature check does not recognise, `404` for an unknown document.
 */
export function uploadDocumentFile(
  documentId: number,
  file: File,
  signal?: AbortSignal,
): Promise<FileOut> {
  const form = new FormData()
  form.append('file', file)
  return apiPostForm<FileOut>(`/documents/${documentId}/files`, form, signal)
}

/** `DELETE /documents/{document_id}/files/{file_id}` — `204`, no body. */
export function deleteDocumentFile(
  documentId: number,
  fileId: number,
  signal?: AbortSignal,
): Promise<void> {
  return apiDelete(`/documents/${documentId}/files/${fileId}`, signal)
}

/**
 * `PUT /documents/{document_id}/variants` — `200` with the stored set.
 *
 * This is a replacement, not an addition: the list that is sent becomes the
 * whole set, so an empty list clears every link. Duplicate ids are refused with
 * `422` rather than collapsed, which is why the caller builds the list from a
 * set and can never send one twice.
 */
export function replaceDocumentVariants(
  documentId: number,
  variantIds: number[],
  signal?: AbortSignal,
): Promise<ProductVariantRead[]> {
  return apiPut<ProductVariantRead[]>(`/documents/${documentId}/variants`, { variant_ids: variantIds }, signal)
}
