import { useId, useState, type FormEvent } from 'react'

import { ApiError, describeError } from '../api/client'
import { createManufacturer, createProduct } from '../api/references'
import { useSubmit } from '../hooks/useSubmit'
import type { ManufacturerRead, ProductRead } from '../types/api'
import {
  EMPTY_PRODUCT,
  PRODUCT_TEXT_MAX_LENGTH,
  PRODUCT_TYPE_MAX_LENGTH,
  type ProductFormErrors,
  type ProductFormValues,
  toProductBody,
  validateProduct,
} from '../utils/catalog'
import Notice from './Notice'
import ReferenceCreator from './ReferenceCreator'

interface ProductFormProps {
  manufacturers: ManufacturerRead[]
  /** True once the manufacturer list was asked for, whether or not it answered. */
  manufacturersLoaded: boolean
  manufacturersTruncated: boolean
  /** Record a manufacturer created from this form so the parent list has it. */
  onManufacturerCreated: (manufacturer: ManufacturerRead) => void
  onCreated: (product: ProductRead) => void
  onCancel: () => void
}

/** A failure in the product form's own terms. Only the status is read. */
function describeProductError(error: unknown): string {
  if (error instanceof ApiError && error.status === 404) {
    return 'Производитель не найден — возможно, запись удалена. Выберите другого и повторите.'
  }
  if (error instanceof ApiError && error.status === 422) {
    return 'Сервер не принял данные изделия. Проверьте название, ГОСТ/ТУ и производителя.'
  }
  return describeError(error)
}

/**
 * Create one product: a pipe, a valve, a fitting — the interface does not
 * distinguish them, because the model does not either. What is being created is
 * the thing a certificate is issued for, and its kind is up to the name and the
 * optional `product_type`.
 *
 * The SDR is not a field. ADR-005 puts it in the name ("Труба ПЭ100 SDR11"), so
 * the form says so instead of offering a column that does not exist.
 *
 * `standard` is required by `ProductCreate`. It is asked for rather than
 * derived or left blank, because a product without its ГОСТ/ТУ would be a record
 * that cannot be checked against anything, and a placeholder would be a value
 * nobody chose.
 *
 * A manufacturer is never invented from typed text: the nested creator is a
 * separate, visible act that writes to the manufacturer reference, and only then
 * becomes selectable here. It opens by itself when the reference is empty,
 * because an empty `<select>` is a dead end rather than a choice.
 *
 * One submit creates one product. `useSubmit`'s guard is set synchronously, so a
 * second click in the same tick cannot issue a second `POST`.
 */
export default function ProductForm({
  manufacturers,
  manufacturersLoaded,
  manufacturersTruncated,
  onManufacturerCreated,
  onCreated,
  onCancel,
}: ProductFormProps) {
  const idPrefix = useId()
  const submission = useSubmit()
  const [values, setValues] = useState<ProductFormValues>(EMPTY_PRODUCT)
  const [errors, setErrors] = useState<ProductFormErrors>({})
  const [creatorOpen, setCreatorOpen] = useState(false)

  const showCreator = creatorOpen || (manufacturersLoaded && manufacturers.length === 0)

  const change = (patch: Partial<ProductFormValues>) => {
    setValues((current) => ({ ...current, ...patch }))
    setErrors((current) => {
      const next = { ...current }
      for (const key of Object.keys(patch) as Array<keyof ProductFormValues>) {
        delete next[key as keyof ProductFormErrors]
      }
      return next
    })
    if (submission.error !== null) {
      submission.reset()
    }
  }

  const handleCreateManufacturer = async (name: string) => {
    const created = await createManufacturer(name)
    onManufacturerCreated(created)
    change({ manufacturerId: String(created.id) })
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const validation = validateProduct(values)
    setErrors(validation)
    if (Object.keys(validation).length > 0) {
      return
    }
    const body = toProductBody(values)
    if (body === null) {
      // Unreachable: the validation above refuses exactly what makes this null.
      return
    }
    await submission.run(async () => {
      const created = await createProduct(body)
      onCreated(created)
    })
  }

  return (
    <form className="form" onSubmit={handleSubmit} noValidate>
      <div className="form__grid">
        <label className="field">
          <span className="field__label">Наименование изделия *</span>
          <input
            className="field__input"
            type="text"
            value={values.name}
            maxLength={PRODUCT_TEXT_MAX_LENGTH}
            disabled={submission.pending}
            aria-invalid={errors.name !== undefined}
            aria-describedby={errors.name ? `${idPrefix}-name-error` : undefined}
            placeholder="Например, Труба ПЭ100 SDR11"
            onChange={(event) => change({ name: event.target.value })}
          />
          {errors.name !== undefined && (
            <span className="field__error" id={`${idPrefix}-name-error`}>
              {errors.name}
            </span>
          )}
          <span className="field__hint">
            SDR — часть названия изделия, отдельного поля для него нет.
          </span>
        </label>

        <label className="field">
          <span className="field__label">ГОСТ/ТУ *</span>
          <input
            className="field__input"
            type="text"
            value={values.standard}
            maxLength={PRODUCT_TEXT_MAX_LENGTH}
            disabled={submission.pending}
            aria-invalid={errors.standard !== undefined}
            aria-describedby={errors.standard ? `${idPrefix}-standard-error` : undefined}
            placeholder="Например, ГОСТ 18599-2001"
            onChange={(event) => change({ standard: event.target.value })}
          />
          {errors.standard !== undefined && (
            <span className="field__error" id={`${idPrefix}-standard-error`}>
              {errors.standard}
            </span>
          )}
        </label>

        <label className="field">
          <span className="field__label">Производитель *</span>
          <select
            className="field__input"
            value={values.manufacturerId}
            disabled={submission.pending}
            aria-invalid={errors.manufacturerId !== undefined}
            aria-describedby={
              errors.manufacturerId ? `${idPrefix}-manufacturer-error` : undefined
            }
            onChange={(event) => change({ manufacturerId: event.target.value })}
          >
            <option value="">Выберите производителя</option>
            {manufacturers.map((manufacturer) => (
              <option key={manufacturer.id} value={String(manufacturer.id)}>
                {manufacturer.name}
              </option>
            ))}
          </select>
          {errors.manufacturerId !== undefined && (
            <span className="field__error" id={`${idPrefix}-manufacturer-error`}>
              {errors.manufacturerId}
            </span>
          )}
          <span className="field__hint">
            Производитель — изготовитель изделия, а не организация, выдавшая документ.
          </span>
        </label>

        <label className="field">
          <span className="field__label">Обозначение</span>
          <input
            className="field__input"
            type="text"
            value={values.designation}
            maxLength={PRODUCT_TEXT_MAX_LENGTH}
            disabled={submission.pending}
            placeholder="Необязательно"
            onChange={(event) => change({ designation: event.target.value })}
          />
        </label>

        <label className="field">
          <span className="field__label">Тип изделия</span>
          <input
            className="field__input"
            type="text"
            value={values.productType}
            maxLength={PRODUCT_TYPE_MAX_LENGTH}
            disabled={submission.pending}
            placeholder="Например, труба, кран, отвод"
            onChange={(event) => change({ productType: event.target.value })}
          />
        </label>
      </div>

      <div className="form__references">
        {showCreator ? (
          <ReferenceCreator
            title="Новый производитель"
            fieldLabel="Наименование производителя"
            placeholder="Например, ООО «Полипласт»"
            maxLength={PRODUCT_TEXT_MAX_LENGTH}
            submitLabel="Создать производителя"
            onCreate={handleCreateManufacturer}
            onClose={() => setCreatorOpen(false)}
          />
        ) : (
          <button
            type="button"
            className="button"
            disabled={submission.pending}
            onClick={() => setCreatorOpen(true)}
          >
            Новый производитель
          </button>
        )}
      </div>

      {manufacturersTruncated && (
        <span className="field__hint">
          Список производителей загружен частично — отсутствующего можно создать.
        </span>
      )}

      {submission.error !== null && (
        <Notice tone="error">{describeProductError(submission.error)}</Notice>
      )}

      <div className="form__actions">
        <button
          type="submit"
          className="button button--primary"
          disabled={submission.pending}
        >
          {submission.pending ? 'Сохранение…' : 'Сохранить изделие'}
        </button>
        <button
          type="button"
          className="button"
          disabled={submission.pending}
          onClick={onCancel}
        >
          Отмена
        </button>
      </div>
    </form>
  )
}
