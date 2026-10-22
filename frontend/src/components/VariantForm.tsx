import { useEffect, useId, useRef, useState, type FormEvent } from 'react'

import { ApiError, describeError } from '../api/client'
import { createProductVariant } from '../api/references'
import { useSubmit } from '../hooks/useSubmit'
import type { ProductVariantRead } from '../types/api'
import {
  EMPTY_VARIANT,
  SIZE_TEXT_MAX_LENGTH,
  hasVariantErrors,
  toVariantBody,
  validateVariant,
  type VariantFormErrors,
  type VariantFormValues,
} from '../utils/catalog'
import Notice from './Notice'

interface VariantFormProps {
  productId: number
  /** The product as one label, for the heading and the duplicate message. */
  productLabel: string
  onCreated: (variant: ProductVariantRead) => void
  onClose: () => void
}

/**
 * Add the sizes of one product, one after another.
 *
 * `size_text` is the designation and the only required field: a pipe is "Ø63", a
 * valve is "DN15", and neither has to repeat itself as a number to be a size.
 * The three measurements are optional, and a blank one stays blank — sending
 * zero would be a claim about the part that nobody made.
 *
 * A duplicate is a real outcome, not an edge case: ADR-006 makes
 * `(product_id, size_text)` the identity, so the same designation twice is
 * refused with `409`. The form says so in the user's own words, and keeps
 * everything typed, because the fix is the designation, not the whole row.
 *
 * The form stays open after a successful save and clears only its fields, which
 * is what makes "add several sizes in a row" a sequence rather than a chore. The
 * created rows are shown by the caller, which appends what the server returned.
 */
export default function VariantForm({
  productId,
  productLabel,
  onCreated,
  onClose,
}: VariantFormProps) {
  const idPrefix = useId()
  const submission = useSubmit()
  const [values, setValues] = useState<VariantFormValues>(EMPTY_VARIANT)
  const [errors, setErrors] = useState<VariantFormErrors>({})
  const [lastCreated, setLastCreated] = useState<string | null>(null)
  const sizeRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    sizeRef.current?.focus()
  }, [])

  const change = (patch: Partial<VariantFormValues>) => {
    setValues((current) => ({ ...current, ...patch }))
    setErrors((current) => {
      const next = { ...current }
      for (const key of Object.keys(patch) as Array<keyof VariantFormValues>) {
        delete next[key as keyof VariantFormErrors]
      }
      return next
    })
    if (submission.error !== null) {
      submission.reset()
    }
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const validation = validateVariant(values)
    setErrors(validation)
    if (hasVariantErrors(validation)) {
      return
    }
    const body = toVariantBody(values)
    if (body === null) {
      return
    }

    let createdSize: string | null = null
    const saved = await submission.run(async () => {
      const created = await createProductVariant(productId, body)
      createdSize = created.size_text
      onCreated(created)
    })

    if (saved) {
      setValues(EMPTY_VARIANT)
      setErrors({})
      setLastCreated(createdSize)
      sizeRef.current?.focus()
    }
  }

  const duplicate =
    submission.error instanceof ApiError && submission.error.status === 409
      ? `Типоразмер «${values.sizeText.trim()}» уже есть у изделия «${productLabel}». Укажите другое обозначение.`
      : null

  const message =
    submission.error instanceof ApiError && submission.error.status === 404
      ? 'Изделие не найдено — возможно, оно было удалено. Обновите каталог.'
      : duplicate ?? describeError(submission.error)

  return (
    <form className="form" onSubmit={handleSubmit} noValidate>
      <p className="field__hint">
        Типоразмеры изделия «{productLabel}». Обозначение обязательно, размеры можно не
        заполнять.
      </p>

      <div className="form__grid">
        <label className="field">
          <span className="field__label">Обозначение типоразмера *</span>
          <input
            ref={sizeRef}
            className="field__input"
            type="text"
            value={values.sizeText}
            maxLength={SIZE_TEXT_MAX_LENGTH}
            disabled={submission.pending}
            aria-invalid={errors.sizeText !== undefined}
            aria-describedby={errors.sizeText ? `${idPrefix}-size-error` : undefined}
            placeholder="Например, Ø63 или DN15"
            onChange={(event) => change({ sizeText: event.target.value })}
          />
          {errors.sizeText !== undefined && (
            <span className="field__error" id={`${idPrefix}-size-error`}>
              {errors.sizeText}
            </span>
          )}
        </label>

        <label className="field">
          <span className="field__label">Диаметр, мм</span>
          <input
            className="field__input"
            type="text"
            inputMode="decimal"
            value={values.diameter}
            disabled={submission.pending}
            aria-invalid={errors.diameter !== undefined}
            aria-describedby={errors.diameter ? `${idPrefix}-diameter-error` : undefined}
            placeholder="Необязательно"
            onChange={(event) => change({ diameter: event.target.value })}
          />
          {errors.diameter !== undefined && (
            <span className="field__error" id={`${idPrefix}-diameter-error`}>
              {errors.diameter}
            </span>
          )}
        </label>

        <label className="field">
          <span className="field__label">Номинальный диаметр, мм</span>
          <input
            className="field__input"
            type="text"
            inputMode="decimal"
            value={values.nominalDiameter}
            disabled={submission.pending}
            aria-invalid={errors.nominalDiameter !== undefined}
            aria-describedby={
              errors.nominalDiameter ? `${idPrefix}-nominal-error` : undefined
            }
            placeholder="Необязательно"
            onChange={(event) => change({ nominalDiameter: event.target.value })}
          />
          {errors.nominalDiameter !== undefined && (
            <span className="field__error" id={`${idPrefix}-nominal-error`}>
              {errors.nominalDiameter}
            </span>
          )}
        </label>

        <label className="field">
          <span className="field__label">Толщина стенки, мм</span>
          <input
            className="field__input"
            type="text"
            inputMode="decimal"
            value={values.wallThickness}
            disabled={submission.pending}
            aria-invalid={errors.wallThickness !== undefined}
            aria-describedby={errors.wallThickness ? `${idPrefix}-wall-error` : undefined}
            placeholder="Необязательно"
            onChange={(event) => change({ wallThickness: event.target.value })}
          />
          {errors.wallThickness !== undefined && (
            <span className="field__error" id={`${idPrefix}-wall-error`}>
              {errors.wallThickness}
            </span>
          )}
        </label>
      </div>

      {lastCreated !== null && (
        <Notice tone="success">
          Типоразмер «{lastCreated}» добавлен. Можно ввести следующий.
        </Notice>
      )}

      {submission.error !== null && <Notice tone="error">{message}</Notice>}

      <div className="form__actions">
        <button
          type="submit"
          className="button button--primary"
          disabled={submission.pending}
        >
          {submission.pending ? 'Сохранение…' : 'Сохранить типоразмер'}
        </button>
        <button
          type="button"
          className="button"
          disabled={submission.pending}
          onClick={onClose}
        >
          {lastCreated === null ? 'Отмена' : 'Готово'}
        </button>
      </div>
    </form>
  )
}
