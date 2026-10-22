import { useCallback, useEffect, useMemo, useState } from 'react'

import { describeError } from '../api/client'
import { replaceDocumentVariants } from '../api/documents'
import {
  createManufacturer,
  loadAllProductVariants,
  loadAllProducts,
} from '../api/references'
import { useManufacturers } from '../hooks/useManufacturers'
import { useSubmit } from '../hooks/useSubmit'
import type {
  ManufacturerRead,
  ProductRead,
  ProductVariantRead,
} from '../types/api'
import { productLabel } from '../utils/catalog'
import Notice from './Notice'
import ProductForm from './ProductForm'
import ReferenceCreator from './ReferenceCreator'
import VariantForm from './VariantForm'

interface DocumentVariantsEditorProps {
  documentId: number
  /** What `GET /documents/{id}/variants` last returned: the starting selection. */
  linkedVariants: ProductVariantRead[]
  onSaved: () => void
  onClose: () => void
}

type ProductsState =
  | { status: 'loading' }
  | { status: 'ready'; items: ProductRead[]; truncated: boolean }
  | { status: 'error'; error: unknown }

type ProductVariantsState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; items: ProductVariantRead[]; truncated: boolean }
  | { status: 'error'; error: unknown }

/** What is known about a variant that was seen, whether or not it is on screen. */
interface KnownVariant {
  productId: number
  sizeText: string
}

/** Which catalog form is open inside the picker. Only one at a time. */
type CatalogForm = 'none' | 'manufacturer' | 'product' | 'variant'

/**
 * Pick the whole set of sizes a document covers, and fill the catalog without
 * leaving the document.
 *
 * The endpoint replaces the set, it does not extend it, so this is not a form
 * that adds links: what is ticked when «Сохранить привязки» is pressed becomes
 * the entire set, and saving with nothing ticked is the way to detach
 * everything. The selection is therefore held as one set of variant ids from the
 * start, seeded from the links that already exist — including links belonging to
 * products this user never opens — which is what makes "tick one size of a
 * second product" an edit of the same set rather than a new one.
 *
 * Choosing another product loads its sizes and never touches what is ticked, so
 * moving between products is not a way to lose work. Creating a product or a
 * size is the same: the catalog is extended, the selection is not. Ids cannot
 * repeat because a set cannot hold one twice, and an id is never shown where a
 * size belongs: a tick always carries `size_text` and the id is labelled as a
 * variant number.
 *
 * The creation forms are the same components the catalog screen uses, not a
 * second implementation: a manufacturer, a product or a size created here is
 * created exactly the way it is created there, and lands in the same lists. A
 * newly created size is appended to the list but not ticked — the user asked to
 * create it, not to attach it — so the last step stays an explicit choice before
 * the single `PUT` that saves the whole set.
 *
 * The whole reference is read in pages, so a size on the second page is still
 * selectable; a list stopped by the page cap says so rather than pretending to
 * be complete.
 */
export default function DocumentVariantsEditor({
  documentId,
  linkedVariants,
  onSaved,
  onClose,
}: DocumentVariantsEditorProps) {
  const submission = useSubmit()

  const [selectedIds, setSelectedIds] = useState<Set<number>>(
    () => new Set(linkedVariants.map((variant) => variant.id)),
  )
  const [known, setKnown] = useState<Map<number, KnownVariant>>(
    () =>
      new Map(
        linkedVariants.map((variant) => [
          variant.id,
          { productId: variant.product_id, sizeText: variant.size_text },
        ]),
      ),
  )

  const [products, setProducts] = useState<ProductsState>({ status: 'loading' })
  const [productFilter, setProductFilter] = useState('')
  const [activeProductId, setActiveProductId] = useState('')
  const [productVariants, setProductVariants] = useState<ProductVariantsState>({ status: 'idle' })
  const [variantsAttempt, setVariantsAttempt] = useState(0)

  const [catalogForm, setCatalogForm] = useState<CatalogForm>('none')
  // The manufacturer reference is read when the catalog is first used, not on
  // mount: a picker that only ticks existing sizes must not walk a reference it
  // never shows.
  const [catalogUsed, setCatalogUsed] = useState(false)
  const manufacturers = useManufacturers(catalogUsed)
  const [catalogNotice, setCatalogNotice] = useState<string | null>(null)

  /** Add what a loaded page taught us, without disturbing anything already known. */
  const remember = useCallback((variants: ProductVariantRead[]) => {
    setKnown((current) => {
      let next = current
      for (const variant of variants) {
        if (next.has(variant.id)) {
          continue
        }
        if (next === current) {
          next = new Map(current)
        }
        next.set(variant.id, { productId: variant.product_id, sizeText: variant.size_text })
      }
      return next
    })
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    loadAllProducts(controller.signal)
      .then((page) => {
        if (!controller.signal.aborted) {
          setProducts({ status: 'ready', items: page.items, truncated: page.truncated })
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setProducts({ status: 'error', error })
        }
      })
    return () => controller.abort()
  }, [])

  const activeProduct = activeProductId === '' ? null : Number(activeProductId)

  useEffect(() => {
    if (activeProduct === null) {
      setProductVariants({ status: 'idle' })
      return
    }
    const controller = new AbortController()
    setProductVariants({ status: 'loading' })
    loadAllProductVariants(activeProduct, controller.signal)
      .then((page) => {
        if (controller.signal.aborted) {
          return
        }
        setProductVariants({ status: 'ready', items: page.items, truncated: page.truncated })
        remember(page.items)
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setProductVariants({ status: 'error', error })
        }
      })
    return () => controller.abort()
  }, [activeProduct, remember, variantsAttempt])

  const productNames = useMemo(() => {
    const names = new Map<number, string>()
    if (products.status === 'ready') {
      for (const product of products.items) {
        names.set(product.id, productLabel(product))
      }
    }
    return names
  }, [products])

  const visibleProducts = useMemo(() => {
    if (products.status !== 'ready') {
      return []
    }
    const needle = productFilter.trim().toLowerCase()
    if (needle === '') {
      return products.items
    }
    return products.items.filter(
      (product) =>
        product.name.toLowerCase().includes(needle) ||
        product.standard.toLowerCase().includes(needle),
    )
  }, [products, productFilter])

  const activeProductRecord =
    products.status === 'ready'
      ? (products.items.find((product) => product.id === activeProduct) ?? null)
      : null

  const toggle = (variant: ProductVariantRead) => {
    remember([variant])
    setSelectedIds((current) => {
      const next = new Set(current)
      if (next.has(variant.id)) {
        next.delete(variant.id)
      } else {
        next.add(variant.id)
      }
      return next
    })
  }

  const drop = (variantId: number) => {
    setSelectedIds((current) => {
      if (!current.has(variantId)) {
        return current
      }
      const next = new Set(current)
      next.delete(variantId)
      return next
    })
  }

  // Ascending ids keep the request body stable no matter what order they were
  // ticked in, so an unchanged selection serialises to an unchanged body.
  const orderedIds = useMemo(
    () => [...selectedIds].sort((left, right) => left - right),
    [selectedIds],
  )

  const save = async () => {
    await submission.run(async () => {
      await replaceDocumentVariants(documentId, orderedIds)
      onSaved()
      onClose()
    })
  }

  const describeProduct = (productId: number): string =>
    productNames.get(productId) ?? `изделие №${productId}`

  const openCatalogForm = (next: Exclude<CatalogForm, 'none'>) => {
    setCatalogUsed(true)
    setCatalogNotice(null)
    setCatalogForm(catalogForm === next ? 'none' : next)
  }

  const handleProductCreated = (product: ProductRead) => {
    setProducts((current) => {
      if (current.status !== 'ready') {
        return current
      }
      if (current.items.some((row) => row.id === product.id)) {
        return current
      }
      return { ...current, items: [...current.items, product] }
    })
    // The filter would hide the product that was just created, and the whole
    // point of creating it here is to select it next.
    setProductFilter('')
    setActiveProductId(String(product.id))
    setCatalogForm('variant')
    setCatalogNotice(
      `Изделие «${product.name}» создано. Добавьте его типоразмер и отметьте его в списке.`,
    )
  }

  const handleVariantCreated = (variant: ProductVariantRead) => {
    remember([variant])
    setProductVariants((current) => {
      if (current.status !== 'ready') {
        return current
      }
      if (current.items.some((row) => row.id === variant.id)) {
        return current
      }
      return { ...current, items: [...current.items, variant] }
    })
    if (productVariants.status !== 'ready') {
      setVariantsAttempt((current) => current + 1)
    }
    setCatalogNotice(
      `Типоразмер «${variant.size_text}» добавлен. Отметьте его в списке, затем сохраните привязки.`,
    )
  }

  const handleManufacturerCreated = (manufacturer: ManufacturerRead) => {
    manufacturers.add(manufacturer)
    setCatalogNotice(`Производитель «${manufacturer.name}» добавлен.`)
  }

  return (
    <div className="picker">
      <p className="field__hint">
        Сохранение записывает ровно отмеченный список: привязки заменяются целиком, а пустой
        список снимает их все. Привязка типоразмеров не меняет статус проверки.
      </p>

      <div className="picker__grid">
        <label className="field">
          <span className="field__label">Изделие</span>
          <input
            className="field__input"
            type="search"
            value={productFilter}
            disabled={products.status !== 'ready'}
            placeholder="Фильтр по названию или ГОСТ/ТУ"
            onChange={(event) => setProductFilter(event.target.value)}
          />
        </label>

        <label className="field">
          <span className="field__label">Типоразмеры изделия</span>
          <select
            className="field__input"
            value={activeProductId}
            disabled={products.status !== 'ready' || visibleProducts.length === 0}
            onChange={(event) => setActiveProductId(event.target.value)}
          >
            <option value="">Выберите изделие</option>
            {visibleProducts.map((product) => (
              <option key={product.id} value={String(product.id)}>
                {productLabel(product)}
              </option>
            ))}
          </select>
          {productFilter.trim() !== '' && visibleProducts.length === 0 && (
            <span className="field__hint">Ни одно изделие не подходит под фильтр.</span>
          )}
        </label>
      </div>

      <div className="picker__catalog">
        <div className="toolbar">
          <button
            type="button"
            className="button"
            aria-expanded={catalogForm === 'manufacturer'}
            disabled={submission.pending}
            onClick={() => openCatalogForm('manufacturer')}
          >
            Добавить производителя
          </button>
          <button
            type="button"
            className="button"
            aria-expanded={catalogForm === 'product'}
            disabled={submission.pending}
            onClick={() => openCatalogForm('product')}
          >
            Добавить изделие
          </button>
          <button
            type="button"
            className="button"
            aria-expanded={catalogForm === 'variant'}
            disabled={submission.pending || activeProduct === null}
            title={
              activeProduct === null
                ? 'Сначала выберите изделие, к которому относится типоразмер'
                : undefined
            }
            onClick={() => openCatalogForm('variant')}
          >
            Добавить типоразмер
          </button>
        </div>

        <p className="field__hint">
          Созданное здесь сразу попадает в справочник. Отмеченные типоразмеры при этом не
          теряются.
        </p>

        {catalogNotice !== null && <Notice tone="success">{catalogNotice}</Notice>}

        {catalogForm === 'manufacturer' && (
          <ReferenceCreator
            title="Новый производитель"
            fieldLabel="Наименование производителя"
            placeholder="Например, ООО «Полипласт»"
            maxLength={255}
            submitLabel="Создать производителя"
            onCreate={async (name) => {
              const created = await createManufacturer(name)
              handleManufacturerCreated(created)
              setCatalogForm('none')
            }}
            onClose={() => setCatalogForm('none')}
          />
        )}

        {catalogForm === 'product' && (
          <ProductForm
            manufacturers={manufacturers.items}
            manufacturersLoaded={manufacturers.loaded}
            manufacturersTruncated={manufacturers.truncated}
            onManufacturerCreated={handleManufacturerCreated}
            onCreated={handleProductCreated}
            onCancel={() => setCatalogForm('none')}
          />
        )}

        {catalogForm === 'variant' && activeProduct !== null && (
          <VariantForm
            productId={activeProduct}
            productLabel={
              activeProductRecord === null
                ? `изделие №${activeProduct}`
                : productLabel(activeProductRecord)
            }
            onCreated={handleVariantCreated}
            onClose={() => setCatalogForm('none')}
          />
        )}
      </div>

      {products.status === 'loading' && (
        <p className="muted" role="status">
          Загрузка изделий…
        </p>
      )}
      {products.status === 'error' && (
        <div className="block-error" role="alert">
          <p>{describeError(products.error)}</p>
          <p className="muted">
            Без списка изделий выбрать типоразмеры нельзя. Уже отмеченные привязки сохранены.
          </p>
        </div>
      )}
      {products.status === 'ready' && products.items.length === 0 && (
        <p className="muted">Справочник изделий пуст — привязывать пока нечего.</p>
      )}
      {products.status === 'ready' && products.truncated && (
        <Notice tone="warning">
          Загружены не все изделия (первые {products.items.length}). Отметить типоразмер
          изделия из незагруженной части этим экраном не получится.
        </Notice>
      )}

      {productVariants.status === 'loading' && (
        <p className="muted" role="status">
          Загрузка типоразмеров…
        </p>
      )}
      {productVariants.status === 'error' && (
        <Notice tone="error">{describeError(productVariants.error)}</Notice>
      )}
      {productVariants.status === 'ready' && productVariants.items.length === 0 && (
        <p className="muted">
          У выбранного изделия нет типоразмеров.
          {activeProduct === null ? '' : ' Добавьте его типоразмер и отметьте его здесь.'}
        </p>
      )}
      {productVariants.status === 'ready' && productVariants.items.length > 0 && (
        <>
          <ul className="checklist">
            {productVariants.items.map((variant) => (
              <li key={variant.id}>
                <label className="checklist__item">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(variant.id)}
                    disabled={submission.pending}
                    onChange={() => toggle(variant)}
                  />
                  <span>
                    {variant.size_text}
                    <span className="muted"> · типоразмер №{variant.id}</span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
          {productVariants.truncated && (
            <Notice tone="warning">
              Загружены не все типоразмеры изделия (первые {productVariants.items.length}).
            </Notice>
          )}
        </>
      )}

      <div className="picker__selection">
        <p className="picker__count">
          Отмечено: <strong>{selectedIds.size}</strong>
        </p>
        {selectedIds.size === 0 ? (
          <p className="muted">Привязок нет. Сохранение снимет все связи документа.</p>
        ) : (
          <ul className="chips">
            {orderedIds.map((variantId) => {
              const info = known.get(variantId)
              return (
                <li key={variantId} className="chip">
                  <span>
                    {info?.sizeText ?? `типоразмер №${variantId}`}
                    {info !== undefined && (
                      <span className="muted"> · {describeProduct(info.productId)}</span>
                    )}
                  </span>
                  <button
                    type="button"
                    className="chip__remove"
                    disabled={submission.pending}
                    aria-label={`Убрать типоразмер ${info?.sizeText ?? variantId}`}
                    onClick={() => drop(variantId)}
                  >
                    ×
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      {submission.error !== null && (
        <Notice tone="error">
          {describeError(submission.error)} Отмеченный набор сохранён в форме — можно
          повторить.
        </Notice>
      )}

      <div className="form__actions">
        <button
          type="button"
          className="button button--primary"
          disabled={submission.pending}
          onClick={save}
        >
          Сохранить привязки
        </button>
        <button
          type="button"
          className="button"
          disabled={submission.pending}
          onClick={onClose}
        >
          Отмена
        </button>
      </div>
    </div>
  )
}
