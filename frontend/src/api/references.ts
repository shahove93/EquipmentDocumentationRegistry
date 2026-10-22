import { apiGet, apiPost } from './client'
import type {
  DocumentTypeRead,
  IssuerRead,
  ManufacturerRead,
  ProductCreateBody,
  ProductRead,
  ProductVariantCreateBody,
  ProductVariantRead,
} from '../types/api'

/**
 * Reference data.
 *
 * Every list endpoint is paged and answers with a bare array without a total.
 * The registry asks for the maximum page size the backend allows (100) and uses
 * what comes back; a filter that silently covered only the first hundred rows
 * would be worse than a visibly short dropdown. The pickers, which the user
 * cannot check against a second source, walk the pages instead — see
 * `loadAllPages`.
 *
 * The single-resource reads exist for the card, which knows exactly which ids it
 * needs and must not be limited to the first page of a list. A lookup that fails
 * leaves the caller with the id it already had, so these reject with the usual
 * `ApiError` and the caller decides what to show.
 */

/** The largest page the backend accepts (`MAX_LIMIT` on every list route). */
const PAGE_SIZE = 100

/**
 * How many pages a walk will follow before it stops and says so.
 *
 * A walk is bounded because the endpoints cannot say how many rows exist, so
 * "keep asking until a short page arrives" would loop forever against a full
 * table. Twenty pages is two thousand rows, past any realistic reference list,
 * and a walk that hits the cap reports itself as truncated rather than passing
 * off a prefix as the whole list.
 */
const MAX_PAGES = 20

/** A list that was read completely, or a prefix that says it is one. */
export interface PagedList<T> {
  items: T[]
  /** True when the safety cap stopped the walk before the list was exhausted. */
  truncated: boolean
}

/**
 * Follow the pages of a list endpoint until it is exhausted or the cap is hit.
 *
 * The reply's length is the only termination signal the API offers: a page
 * shorter than the one requested is the last page. An abort rejects the walk
 * midway and the caller's signal decides whether that is an error — the
 * requests already made are discarded with it, because a partial list must not
 * be presented as the list.
 */
async function loadAllPages<T>(
  fetchPage: (limit: number, offset: number, signal?: AbortSignal) => Promise<T[]>,
  signal?: AbortSignal,
): Promise<PagedList<T>> {
  const items: T[] = []
  for (let page = 0; page < MAX_PAGES; page += 1) {
    const chunk = await fetchPage(PAGE_SIZE, page * PAGE_SIZE, signal)
    items.push(...chunk)
    if (chunk.length < PAGE_SIZE) {
      return { items, truncated: false }
    }
  }
  return { items, truncated: true }
}

export function fetchDocumentTypes(signal?: AbortSignal): Promise<DocumentTypeRead[]> {
  return apiGet<DocumentTypeRead[]>('/document-types?limit=100', signal)
}

export function fetchManufacturers(signal?: AbortSignal): Promise<ManufacturerRead[]> {
  return apiGet<ManufacturerRead[]>('/manufacturers?limit=100', signal)
}

/** `GET /document-types/{document_type_id}`. */
export function fetchDocumentType(
  documentTypeId: number,
  signal?: AbortSignal,
): Promise<DocumentTypeRead> {
  return apiGet<DocumentTypeRead>(`/document-types/${documentTypeId}`, signal)
}

/** `GET /issuers/{issuer_id}`. */
export function fetchIssuer(issuerId: number, signal?: AbortSignal): Promise<IssuerRead> {
  return apiGet<IssuerRead>(`/issuers/${issuerId}`, signal)
}

/** `GET /products/{product_id}` — the name and standard a variant does not carry. */
export function fetchProduct(productId: number, signal?: AbortSignal): Promise<ProductRead> {
  return apiGet<ProductRead>(`/products/${productId}`, signal)
}

/** One page of `GET /products`, ordered by id by the backend. */
export function fetchProductsPage(
  limit: number,
  offset: number,
  signal?: AbortSignal,
): Promise<ProductRead[]> {
  return apiGet<ProductRead[]>(`/products?limit=${limit}&offset=${offset}`, signal)
}

/**
 * One page of `GET /products/{product_id}/variants`.
 *
 * A product that does not exist answers `404` here; an existing product with no
 * variants answers `200 []`, which is why the editor tells those two apart.
 */
export function fetchProductVariantsPage(
  productId: number,
  limit: number,
  offset: number,
  signal?: AbortSignal,
): Promise<ProductVariantRead[]> {
  return apiGet<ProductVariantRead[]>(
    `/products/${productId}/variants?limit=${limit}&offset=${offset}`,
    signal,
  )
}

/** Every product, or as many as the cap allows. */
export function loadAllProducts(signal?: AbortSignal): Promise<PagedList<ProductRead>> {
  return loadAllPages<ProductRead>((limit, offset, inner) => fetchProductsPage(limit, offset, inner), signal)
}

/** Every variant of one product, or as many as the cap allows. */
export function loadAllProductVariants(
  productId: number,
  signal?: AbortSignal,
): Promise<PagedList<ProductVariantRead>> {
  return loadAllPages<ProductVariantRead>(
    (limit, offset, inner) => fetchProductVariantsPage(productId, limit, offset, inner),
    signal,
  )
}

/** Every document type, for a picker that must not hide a type behind page one. */
export function loadAllDocumentTypes(signal?: AbortSignal): Promise<PagedList<DocumentTypeRead>> {
  return loadAllPages<DocumentTypeRead>(
    (limit, offset, inner) => apiGet(`/document-types?limit=${limit}&offset=${offset}`, inner),
    signal,
  )
}

/** Every issuer, for the same reason. */
export function loadAllIssuers(signal?: AbortSignal): Promise<PagedList<IssuerRead>> {
  return loadAllPages<IssuerRead>(
    (limit, offset, inner) => apiGet(`/issuers?limit=${limit}&offset=${offset}`, inner),
    signal,
  )
}

/**
 * `POST /document-types` — `201` with the stored type, `409` when the name is
 * already taken.
 *
 * Creating a type is a deliberate, separate act: nothing in the create form
 * invents a reference row behind the user's back, not even when the type they
 * typed cannot be selected.
 */
export function createDocumentType(name: string, signal?: AbortSignal): Promise<DocumentTypeRead> {
  return apiPost<DocumentTypeRead>('/document-types', { name }, signal)
}

/** `POST /issuers` — `201` with the stored issuer, `409` on a duplicate name. */
export function createIssuer(name: string, signal?: AbortSignal): Promise<IssuerRead> {
  return apiPost<IssuerRead>('/issuers', { name }, signal)
}

/**
 * `GET /manufacturers/{manufacturer_id}` — one manufacturer by id.
 *
 * Used where a row carries only `manufacturer_id` (a product, and through it a
 * linked variant) and the whole reference would be a wasteful read. A failed
 * lookup rejects with the usual `ApiError`; the caller keeps showing the id.
 */
export function fetchManufacturer(
  manufacturerId: number,
  signal?: AbortSignal,
): Promise<ManufacturerRead> {
  return apiGet<ManufacturerRead>(`/manufacturers/${manufacturerId}`, signal)
}

/** Every manufacturer, for a picker or a name lookup that must not stop at page one. */
export function loadAllManufacturers(signal?: AbortSignal): Promise<PagedList<ManufacturerRead>> {
  return loadAllPages<ManufacturerRead>(
    (limit, offset, inner) => apiGet(`/manufacturers?limit=${limit}&offset=${offset}`, inner),
    signal,
  )
}

/** `POST /manufacturers` — `201` with the stored row, `409` on a duplicate name. */
export function createManufacturer(
  name: string,
  signal?: AbortSignal,
): Promise<ManufacturerRead> {
  return apiPost<ManufacturerRead>('/manufacturers', { name }, signal)
}

/**
 * `POST /products` — `201` with the stored product.
 *
 * An unknown `manufacturer_id` answers `404`, which is the one failure worth
 * naming in the form: it means the reference changed under the user.
 */
export function createProduct(
  body: ProductCreateBody,
  signal?: AbortSignal,
): Promise<ProductRead> {
  return apiPost<ProductRead>('/products', body, signal)
}

/**
 * `POST /products/{product_id}/variants` — `201` with the stored variant.
 *
 * A size already registered for that product answers `409` (ADR-006), which the
 * form reports as the duplicate it is rather than as a generic conflict.
 */
export function createProductVariant(
  productId: number,
  body: ProductVariantCreateBody,
  signal?: AbortSignal,
): Promise<ProductVariantRead> {
  return apiPost<ProductVariantRead>(`/products/${productId}/variants`, body, signal)
}

/**
 * `GET /variants/{variant_id}` — one variant by id.
 *
 * The create screen needs it to name a variant it was pointed at by id alone,
 * without walking a product's whole list.
 */
export function fetchVariant(
  variantId: number,
  signal?: AbortSignal,
): Promise<ProductVariantRead> {
  return apiGet<ProductVariantRead>(`/variants/${variantId}`, signal)
}
