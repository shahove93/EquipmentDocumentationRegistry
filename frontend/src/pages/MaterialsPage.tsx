import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { describeError } from '../api/client'
import {
  createManufacturer,
  fetchProductsPage,
  loadAllProductVariants,
} from '../api/references'
import Notice from '../components/Notice'
import Pagination from '../components/Pagination'
import ProductForm from '../components/ProductForm'
import ReferenceCreator from '../components/ReferenceCreator'
import VariantForm from '../components/VariantForm'
import { useManufacturers } from '../hooks/useManufacturers'
import type { ManufacturerRead, ProductRead, ProductVariantRead } from '../types/api'
import { measurementText, productLabel } from '../utils/catalog'

/**
 * The backend returns a bare array, so "is there a next page?" is answered by
 * asking for one row past the page and looking at whether it arrived. 26 is
 * within the endpoint's `1..100` limit.
 */
const PAGE_SIZE = 25
const PAGE_FETCH = PAGE_SIZE + 1

type ProductsState =
  | { status: 'loading' }
  | { status: 'ready'; items: ProductRead[]; hasNext: boolean }
  | { status: 'error'; error: unknown }

type VariantsState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; items: ProductVariantRead[]; truncated: boolean }
  | { status: 'error'; error: unknown }

/** Which creation form is open below the header. Only one at a time. */
type OpenForm = 'none' | 'manufacturer' | 'product' | 'variant'

/**
 * Materials and equipment — the catalog a certificate is issued against.
 *
 * There is one entity here, `Product`, and no attempt is made to split it into
 * "materials" and "equipment" in the interface: the model does not distinguish
 * them, and inventing the distinction would create a choice the user cannot
 * verify. What varies is the name, the ГОСТ/ТУ and the sizes, which is exactly
 * what the table shows.
 *
 * The product list is paged on the server, one page at a time, because
 * `GET /products` has no search and no total: reading everything and cutting it
 * down would hide rows behind a filter nobody can see. A page that looks empty
 * because the catalog is empty is told apart from one that only failed to load.
 *
 * Manufacturers are read from their own reference, walked to the end, so a name
 * is never invented from an id and a picker does not silently stop at row one
 * hundred.
 */
export default function MaterialsPage() {
  const [offset, setOffset] = useState(0)
  const [list, setList] = useState<ProductsState>({ status: 'loading' })
  const [listAttempt, setListAttempt] = useState(0)

  const [selected, setSelected] = useState<ProductRead | null>(null)
  const [variants, setVariants] = useState<VariantsState>({ status: 'idle' })
  const [variantsAttempt, setVariantsAttempt] = useState(0)

  const [form, setForm] = useState<OpenForm>('none')
  const [notice, setNotice] = useState<string | null>(null)

  const manufacturers = useManufacturers(true)

  useEffect(() => {
    const controller = new AbortController()
    setList({ status: 'loading' })
    fetchProductsPage(PAGE_FETCH, offset, controller.signal)
      .then((rows) => {
        if (controller.signal.aborted) {
          return
        }
        const hasNext = rows.length > PAGE_SIZE
        setList({ status: 'ready', items: hasNext ? rows.slice(0, PAGE_SIZE) : rows, hasNext })
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return
        }
        setList({ status: 'error', error })
      })
    return () => controller.abort()
  }, [offset, listAttempt])

  const selectedId = selected === null ? null : selected.id

  useEffect(() => {
    if (selectedId === null) {
      setVariants({ status: 'idle' })
      return undefined
    }
    const controller = new AbortController()
    setVariants({ status: 'loading' })
    loadAllProductVariants(selectedId, controller.signal)
      .then((page) => {
        if (controller.signal.aborted) {
          return
        }
        setVariants({ status: 'ready', items: page.items, truncated: page.truncated })
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return
        }
        setVariants({ status: 'error', error })
      })
    return () => controller.abort()
  }, [selectedId, variantsAttempt])

  const manufacturerNames = useMemo(() => {
    const names = new Map<number, string>()
    for (const manufacturer of manufacturers.items) {
      names.set(manufacturer.id, manufacturer.name)
    }
    return names
  }, [manufacturers.items])

  /** The product's maker by name, or `null` when the name is not available. */
  const manufacturerOf = (product: ProductRead): string | null =>
    manufacturerNames.get(product.manufacturer_id) ?? null

  const selectProduct = (product: ProductRead) => {
    if (selected !== null && selected.id === product.id) {
      setSelected(null)
      setForm('none')
      return
    }
    setSelected(product)
    setForm('none')
  }

  const handleManufacturerCreated = (manufacturer: ManufacturerRead) => {
    manufacturers.add(manufacturer)
    setNotice(`Производитель «${manufacturer.name}» добавлен — его можно выбрать у изделия.`)
    setForm('none')
  }

  const handleProductCreated = (product: ProductRead) => {
    setNotice(
      `Изделие «${product.name}» добавлено. Добавьте его типоразмеры — сертификат привязывается к ним.`,
    )
    setSelected(product)
    setForm('variant')
    setOffset(0)
    setListAttempt((current) => current + 1)
  }

  const handleVariantCreated = (variant: ProductVariantRead) => {
    setNotice(`Типоразмер «${variant.size_text}» добавлен в изделие.`)
    setVariants((current) => {
      if (current.status !== 'ready') {
        return current
      }
      return { ...current, items: [...current.items, variant] }
    })
  }

  const retryVariants = useCallback(() => {
    setVariantsAttempt((current) => current + 1)
  }, [])

  const openManufacturerForm = () => {
    setNotice(null)
    setForm(form === 'manufacturer' ? 'none' : 'manufacturer')
  }

  const openProductForm = () => {
    setNotice(null)
    setForm(form === 'product' ? 'none' : 'product')
  }

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1 className="page__title">Материалы и оборудование</h1>
          <p className="page__subtitle">
            Изделия, их производители и типоразмеры. Сертификат привязывается к конкретным
            типоразмерам изделия.
          </p>
        </div>
        <div className="page__header-actions">
          <button type="button" className="button" onClick={openManufacturerForm}>
            Добавить производителя
          </button>
          <button
            type="button"
            className="button button--primary"
            onClick={openProductForm}
          >
            Добавить изделие
          </button>
        </div>
      </header>

      {notice !== null && (
        <div className="catalog__notice" role="status">
          <Notice tone="success">{notice}</Notice>
        </div>
      )}

      {form === 'manufacturer' && (
        <section className="panel panel--form catalog__form">
          <ReferenceCreator
            title="Новый производитель"
            fieldLabel="Наименование производителя"
            placeholder="Например, ООО «Полипласт»"
            maxLength={255}
            submitLabel="Создать производителя"
            onCreate={async (name) => {
              const created = await createManufacturer(name)
              handleManufacturerCreated(created)
            }}
            onClose={() => setForm('none')}
          />
        </section>
      )}

      {form === 'product' && (
        <section className="panel panel--form catalog__form">
          <h2 className="section-title">Новое изделие</h2>
          <ProductForm
            manufacturers={manufacturers.items}
            manufacturersLoaded={manufacturers.loaded}
            manufacturersTruncated={manufacturers.truncated}
            onManufacturerCreated={manufacturers.add}
            onCreated={handleProductCreated}
            onCancel={() => setForm('none')}
          />
        </section>
      )}

      <section className="panel catalog__list">
        <div className="catalog__head">
          <h2 className="section-title">Изделия</h2>
          <span className="muted">
            {list.status === 'ready'
              ? `на странице ${list.items.length}`
              : ''}
          </span>
        </div>

        {manufacturers.failed && (
          <div className="catalog__inline">
            <Notice tone="error">
              Не удалось загрузить справочник производителей — показаны их номера.{' '}
              <button type="button" className="link" onClick={manufacturers.reload}>
                Повторить
              </button>
            </Notice>
          </div>
        )}
        {manufacturers.truncated && (
          <div className="catalog__inline">
            <Notice tone="warning">
              Справочник производителей загружен частично — названия из его конца не показаны.
            </Notice>
          </div>
        )}

        {list.status === 'loading' && (
          <p className="muted catalog__inline" role="status">
            Загрузка изделий…
          </p>
        )}

        {list.status === 'error' && (
          <div className="catalog__inline">
            <div className="block-error" role="alert">
              <p>{describeError(list.error)}</p>
              <button
                type="button"
                className="button"
                onClick={() => setListAttempt((current) => current + 1)}
              >
                Повторить
              </button>
            </div>
          </div>
        )}

        {list.status === 'ready' && list.items.length === 0 && (
          <div className="catalog__inline">
            <p className="muted">
              {offset === 0
                ? 'Каталог пуст. Добавьте производителя, затем изделие — и его типоразмеры.'
                : 'На этой странице записей нет.'}
            </p>
          </div>
        )}

        {list.status === 'ready' && list.items.length > 0 && (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Изделие</th>
                    <th scope="col">Производитель</th>
                    <th scope="col">ГОСТ/ТУ</th>
                    <th scope="col">Обозначение</th>
                    <th scope="col">Тип</th>
                    <th scope="col" className="table__action-col">
                      Действие
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {list.items.map((product) => {
                    const maker = manufacturerOf(product)
                    const isSelected = selected !== null && selected.id === product.id
                    return (
                      <tr key={product.id} className={isSelected ? 'table__row--selected' : undefined}>
                        <td className="table__name">{product.name}</td>
                        <td>
                          {maker ?? (
                            <span
                              className="muted"
                              title="Название производителя недоступно"
                            >
                              №{product.manufacturer_id}
                            </span>
                          )}
                        </td>
                        <td>{product.standard}</td>
                        <td>{product.designation ?? <span className="muted">—</span>}</td>
                        <td>{product.product_type ?? <span className="muted">—</span>}</td>
                        <td className="table__action-col">
                          <button
                            type="button"
                            className="link link--button"
                            aria-expanded={isSelected}
                            onClick={() => selectProduct(product)}
                          >
                            {isSelected ? 'Свернуть' : 'Типоразмеры'}
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            <Pagination
              offset={offset}
              pageSize={PAGE_SIZE}
              count={list.items.length}
              hasNext={list.hasNext}
              onPrev={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}
              onNext={() => setOffset((current) => current + PAGE_SIZE)}
            />
          </>
        )}

        {list.status === 'ready' && list.items.length === 0 && offset > 0 && (
          <Pagination
            offset={offset}
            pageSize={PAGE_SIZE}
            count={0}
            hasNext={false}
            onPrev={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}
            onNext={() => undefined}
          />
        )}
      </section>

      {selected !== null && (
        <section className="panel catalog__item">
          <div className="catalog__head">
            <div>
              <h2 className="section-title">{selected.name}</h2>
              <p className="muted">
                {selected.standard}
                {selected.designation === null ? '' : ` · обозначение ${selected.designation}`}
                {selected.product_type === null ? '' : ` · ${selected.product_type}`}
              </p>
              <p className="muted">
                Производитель:{' '}
                {manufacturerOf(selected) ?? (
                  <span title="Название производителя недоступно">
                    №{selected.manufacturer_id}
                  </span>
                )}
              </p>
            </div>
            <div className="page__header-actions">
              <button
                type="button"
                className="button button--primary"
                disabled={form === 'variant'}
                onClick={() => {
                  setNotice(null)
                  setForm('variant')
                }}
              >
                Добавить типоразмер
              </button>
              <button
                type="button"
                className="button"
                onClick={() => {
                  setSelected(null)
                  setForm('none')
                }}
              >
                Закрыть
              </button>
            </div>
          </div>

          {form === 'variant' && (
            <div className="catalog__inline">
              <VariantForm
                productId={selected.id}
                productLabel={productLabel(selected)}
                onCreated={handleVariantCreated}
                onClose={() => setForm('none')}
              />
            </div>
          )}

          {variants.status === 'loading' && (
            <p className="muted catalog__inline" role="status">
              Загрузка типоразмеров…
            </p>
          )}

          {variants.status === 'error' && (
            <div className="catalog__inline">
              <div className="block-error" role="alert">
                <p>{describeError(variants.error)}</p>
                <button type="button" className="button" onClick={retryVariants}>
                  Повторить
                </button>
              </div>
            </div>
          )}

          {variants.status === 'ready' && variants.items.length === 0 && (
            <div className="catalog__inline">
              <p className="muted">
                У изделия пока нет типоразмеров. Сертификат привязывается к типоразмеру, поэтому
                добавьте хотя бы один.
              </p>
            </div>
          )}

          {variants.status === 'ready' && variants.items.length > 0 && (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Типоразмер</th>
                    <th scope="col">Диаметр</th>
                    <th scope="col">Номинальный диаметр</th>
                    <th scope="col">Толщина стенки</th>
                    <th scope="col" className="table__action-col">
                      Действие
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {variants.items.map((variant) => (
                    <tr key={variant.id}>
                      <td className="table__number">{variant.size_text}</td>
                      <td>{measurementText(variant.diameter) || <span className="muted">—</span>}</td>
                      <td>
                        {measurementText(variant.nominal_diameter) || (
                          <span className="muted">—</span>
                        )}
                      </td>
                      <td>
                        {measurementText(variant.wall_thickness) || (
                          <span className="muted">—</span>
                        )}
                      </td>
                      <td className="table__action-col">
                        <Link
                          className="link"
                          to={`/documents/new?variant_id=${variant.id}`}
                        >
                          Добавить сертификат
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {variants.status === 'ready' && variants.truncated && (
            <div className="catalog__inline">
              <Notice tone="warning">
                Загружены не все типоразмеры изделия (первые {variants.items.length}).
              </Notice>
            </div>
          )}

          <p className="field__hint catalog__inline">
            «Добавить сертификат» открывает форму нового документа с уже выбранным
            типоразмером; привязка сохраняется после создания документа.
          </p>
        </section>
      )}

      {selected === null && list.status === 'ready' && list.items.length > 0 && (
        <p className="field__hint">
          Выберите изделие в таблице, чтобы увидеть его типоразмеры, добавить новые или создать
          сертификат.
        </p>
      )}
    </div>
  )
}
