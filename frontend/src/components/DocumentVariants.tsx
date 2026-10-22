import { useEffect, useMemo, useState } from 'react'

import { fetchManufacturer, fetchProduct } from '../api/references'
import type { ProductRead, ProductVariantRead } from '../types/api'
import DocumentVariantsEditor from './DocumentVariantsEditor'

interface DocumentVariantsProps {
  documentId: number
  /** The covered variants. An empty list is a document nothing is attached to. */
  variants: ProductVariantRead[]
  /** Called after a successful replacement so the card reloads the set. */
  onChanged: () => void
}

/**
 * What is known about one covered product: either it was read, or the read
 * failed. Failure is a distinct outcome from "not loaded yet" so that a failed
 * product is never shown as a product without a name.
 */
type ProductEntry = { product: ProductRead } | { failed: true }

/**
 * The variants a document covers, with each product's name, standard and maker.
 *
 * A variant row carries only `product_id`, so the product has to be read
 * separately. Every distinct id is requested exactly once — the ids are
 * deduplicated before the requests go out, which is what keeps a document
 * covering twenty sizes of one pipe from issuing twenty identical lookups.
 *
 * The manufacturer is one more hop: `ProductRead` carries `manufacturer_id`, not
 * a name, so the distinct ids are resolved the same way. It is the maker of the
 * product — not the organisation that issued the document, which is a different
 * reference entirely (`Document.issuer_id`).
 *
 * The lookups are settled together, and one of them failing does not remove the
 * row: `size_text` is the variant's own field, so it stays on screen, and the
 * product cell falls back to the id. There is no way to say "this product's name
 * is unavailable" other than by saying exactly that.
 *
 * The button that replaces the set sits outside the emptiness check, because an
 * empty list is not a dead end here: it is the state a document is in just
 * before its first size is attached. While the picker is open it stands in for
 * the table, and the button is disabled rather than removed so the heading does
 * not move around.
 */
export default function DocumentVariants({
  documentId,
  variants,
  onChanged,
}: DocumentVariantsProps) {
  const [editing, setEditing] = useState(false)

  const productIds = useMemo(() => {
    const unique = new Set<number>()
    for (const variant of variants) {
      unique.add(variant.product_id)
    }
    return [...unique].sort((left, right) => left - right)
  }, [variants])

  // A primitive dependency. The id list is derived from the loaded variants, so
  // a new array identity on every render must not restart the requests; the key
  // changes only when the set of products actually changes.
  const productIdsKey = productIds.join(',')

  const [products, setProducts] = useState<Record<number, ProductEntry>>({})
  /** Resolved maker names; `null` for an id that could not be read. */
  const [manufacturers, setManufacturers] = useState<Record<number, string | null>>({})

  useEffect(() => {
    const ids = productIdsKey === '' ? [] : productIdsKey.split(',').map(Number)
    if (ids.length === 0) {
      setProducts({})
      return
    }
    const controller = new AbortController()
    Promise.allSettled(ids.map((id) => fetchProduct(id, controller.signal))).then((results) => {
      if (controller.signal.aborted) {
        return
      }
      const next: Record<number, ProductEntry> = {}
      results.forEach((result, index) => {
        next[ids[index]] =
          result.status === 'fulfilled' ? { product: result.value } : { failed: true }
      })
      setProducts(next)
    })
    return () => controller.abort()
  }, [productIdsKey])

  // The maker ids are derived from what the product lookups actually returned,
  // so this waits for them instead of being tied to the variant list.
  const manufacturerIdsKey = useMemo(() => {
    const ids = new Set<number>()
    for (const entry of Object.values(products)) {
      if ('product' in entry) {
        ids.add(entry.product.manufacturer_id)
      }
    }
    return [...ids].sort((left, right) => left - right).join(',')
  }, [products])

  useEffect(() => {
    const ids = manufacturerIdsKey === '' ? [] : manufacturerIdsKey.split(',').map(Number)
    if (ids.length === 0) {
      setManufacturers({})
      return
    }
    const controller = new AbortController()
    Promise.allSettled(ids.map((id) => fetchManufacturer(id, controller.signal))).then(
      (results) => {
        if (controller.signal.aborted) {
          return
        }
        const next: Record<number, string | null> = {}
        results.forEach((result, index) => {
          next[ids[index]] = result.status === 'fulfilled' ? result.value.name : null
        })
        setManufacturers(next)
      },
    )
    return () => controller.abort()
  }, [manufacturerIdsKey])

  return (
    <div className="stack">
      <div className="toolbar">
        <button
          type="button"
          className="button"
          disabled={editing}
          onClick={() => setEditing(true)}
        >
          Изменить привязки
        </button>
      </div>

      {editing ? (
        <DocumentVariantsEditor
          documentId={documentId}
          linkedVariants={variants}
          onSaved={onChanged}
          onClose={() => setEditing(false)}
        />
      ) : variants.length === 0 ? (
        <p className="muted">Типоразмеры не привязаны</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Типоразмер</th>
                <th scope="col">Изделие</th>
                <th scope="col">Стандарт изделия</th>
                <th scope="col">Производитель</th>
              </tr>
            </thead>
            <tbody>
              {variants.map((variant) => {
                const entry = products[variant.product_id]
                return (
                  <tr key={variant.id}>
                    <td className="table__number">{variant.size_text}</td>
                    <td>
                      {entry === undefined ? (
                        <span className="muted">Загрузка…</span>
                      ) : 'product' in entry ? (
                        entry.product.name
                      ) : (
                        <span
                          className="muted"
                          title="Не удалось загрузить сведения об изделии"
                        >
                          №{variant.product_id}
                        </span>
                      )}
                    </td>
                    <td>
                      {entry !== undefined && 'product' in entry ? (
                        entry.product.standard
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td>
                      {entry === undefined || !('product' in entry) ? (
                        <span className="muted">—</span>
                      ) : manufacturers[entry.product.manufacturer_id] === undefined ? (
                        <span className="muted">Загрузка…</span>
                      ) : manufacturers[entry.product.manufacturer_id] === null ? (
                        <span
                          className="muted"
                          title="Не удалось загрузить производителя"
                        >
                          №{entry.product.manufacturer_id}
                        </span>
                      ) : (
                        manufacturers[entry.product.manufacturer_id]
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
