import { useState } from 'react'

import type { DocumentTypeRead, IssuerRead } from '../types/api'
import { NUMBER_MAX_LENGTH, type RequisiteErrors, type RequisiteValues } from '../utils/forms'
import ReferenceCreator from './ReferenceCreator'

interface DocumentRequisitesFormProps {
  /** Prefix for the error-element ids, so two forms on a page stay distinct. */
  idPrefix: string
  values: RequisiteValues
  errors: RequisiteErrors
  disabled: boolean
  documentTypes: DocumentTypeRead[]
  /** True once the type list has been asked for, whether or not it answered. */
  documentTypesLoaded: boolean
  documentTypesTruncated: boolean
  issuers: IssuerRead[]
  issuersTruncated: boolean
  onChange: (patch: Partial<RequisiteValues>) => void
  onCreateDocumentType: (name: string) => Promise<void>
  onCreateIssuer: (name: string) => Promise<void>
}

/** The message under a field, or nothing at all when the field is fine. */
function FieldError({ id, message }: { id: string; message?: string }) {
  if (message === undefined) {
    return null
  }
  return (
    <span className="field__error" id={id}>
      {message}
    </span>
  )
}

/**
 * The document's own fields, shared by the create and edit screens.
 *
 * It renders inputs and nothing else: no value is derived here, no request is
 * made here, and the two buttons only say that the user wants to add a
 * reference row. That is deliberate — the create and edit paths differ in what
 * they send and in what they warn about, and that difference belongs to the two
 * callers, not to the fields they have in common.
 *
 * A select can only offer what it was given. When the value in hand is not in
 * the loaded list — the type list is loaded in pages, so a stored id can sit
 * beyond the cap, and a failed load leaves the list empty — the current value is
 * added as an option of its own rather than dropped. A select whose value is
 * absent from its options renders as the first option, which would silently
 * rewrite a foreign key the user never touched.
 */
export default function DocumentRequisitesForm({
  idPrefix,
  values,
  errors,
  disabled,
  documentTypes,
  documentTypesLoaded,
  documentTypesTruncated,
  issuers,
  issuersTruncated,
  onChange,
  onCreateDocumentType,
  onCreateIssuer,
}: DocumentRequisitesFormProps) {
  const [typeCreatorOpen, setTypeCreatorOpen] = useState(false)
  const [issuerCreatorOpen, setIssuerCreatorOpen] = useState(false)

  // An empty reference is a dead end until something is in it, so the form that
  // fills it opens itself. It closes on its own once the list is no longer
  // empty, because the created row is appended and immediately selected.
  const showTypeCreator =
    typeCreatorOpen || (documentTypesLoaded && documentTypes.length === 0)

  const typeListed = documentTypes.some((type) => String(type.id) === values.documentTypeId)
  const issuerListed = issuers.some((issuer) => String(issuer.id) === values.issuerId)

  return (
    <div className="form__fields">
      <div className="form__grid">
        <label className="field">
          <span className="field__label">Тип документа *</span>
          <select
            className="field__input"
            value={values.documentTypeId}
            disabled={disabled}
            aria-invalid={errors.documentTypeId !== undefined}
            aria-describedby={
              errors.documentTypeId ? `${idPrefix}-documentTypeId-error` : undefined
            }
            onChange={(event) => onChange({ documentTypeId: event.target.value })}
          >
            <option value="">Выберите тип</option>
            {documentTypes.map((type) => (
              <option key={type.id} value={String(type.id)}>
                {type.name}
              </option>
            ))}
            {values.documentTypeId !== '' && !typeListed && (
              <option value={values.documentTypeId}>
                Тип №{values.documentTypeId} (нет в загруженном списке)
              </option>
            )}
          </select>
          <FieldError id={`${idPrefix}-documentTypeId-error`} message={errors.documentTypeId} />
          {documentTypesTruncated && (
            <span className="field__hint">
              Список типов загружен частично — отсутствующий тип можно создать.
            </span>
          )}
        </label>

        <label className="field">
          <span className="field__label">Номер *</span>
          <input
            className="field__input"
            type="text"
            value={values.number}
            maxLength={NUMBER_MAX_LENGTH}
            disabled={disabled}
            placeholder="Например, CERT-2026-063"
            aria-invalid={errors.number !== undefined}
            aria-describedby={errors.number ? `${idPrefix}-number-error` : undefined}
            onChange={(event) => onChange({ number: event.target.value })}
          />
          <FieldError id={`${idPrefix}-number-error`} message={errors.number} />
        </label>

        <label className="field">
          <span className="field__label">Дата выдачи</span>
          <input
            className="field__input"
            type="date"
            value={values.issueDate}
            disabled={disabled}
            onChange={(event) => onChange({ issueDate: event.target.value })}
          />
        </label>

        <label className="field">
          <span className="field__label">Действует с</span>
          <input
            className="field__input"
            type="date"
            value={values.validFrom}
            disabled={disabled}
            onChange={(event) => onChange({ validFrom: event.target.value })}
          />
        </label>

        <label className="field">
          <span className="field__label">Действует до</span>
          <input
            className="field__input"
            type="date"
            value={values.validTo}
            disabled={disabled}
            aria-invalid={errors.validTo !== undefined}
            aria-describedby={errors.validTo ? `${idPrefix}-validTo-error` : undefined}
            onChange={(event) => onChange({ validTo: event.target.value })}
          />
          <FieldError id={`${idPrefix}-validTo-error`} message={errors.validTo} />
        </label>

        <label className="field">
          <span className="field__label">Кем выдан документ</span>
          <select
            className="field__input"
            value={values.issuerId}
            disabled={disabled}
            onChange={(event) => onChange({ issuerId: event.target.value })}
          >
            <option value="">Не указан</option>
            {issuers.map((issuer) => (
              <option key={issuer.id} value={String(issuer.id)}>
                {issuer.name}
              </option>
            ))}
            {values.issuerId !== '' && !issuerListed && (
              <option value={values.issuerId}>
                Организация №{values.issuerId} (нет в загруженном списке)
              </option>
            )}
          </select>
          {issuersTruncated && (
            <span className="field__hint">
              Список организаций загружен частично — отсутствующую можно создать.
            </span>
          )}
        </label>

        <label className="field field--wide">
          <span className="field__label">Примечания</span>
          <textarea
            className="field__input"
            rows={3}
            value={values.notes}
            disabled={disabled}
            onChange={(event) => onChange({ notes: event.target.value })}
          />
        </label>
      </div>

      <div className="form__references">
        {showTypeCreator ? (
          <ReferenceCreator
            title="Новый тип документа"
            placeholder="Например, Сертификат соответствия"
            maxLength={100}
            submitLabel="Создать тип"
            onCreate={onCreateDocumentType}
            onClose={() => setTypeCreatorOpen(false)}
          />
        ) : (
          <button
            type="button"
            className="button"
            disabled={disabled}
            onClick={() => setTypeCreatorOpen(true)}
          >
            Новый тип документа
          </button>
        )}

        {issuerCreatorOpen ? (
          <ReferenceCreator
            title="Новая организация"
            fieldLabel="Наименование организации"
            placeholder="Например, ФБУ «Ростест-Москва»"
            maxLength={255}
            submitLabel="Создать организацию"
            onCreate={onCreateIssuer}
            onClose={() => setIssuerCreatorOpen(false)}
          />
        ) : (
          <button
            type="button"
            className="button"
            disabled={disabled}
            onClick={() => setIssuerCreatorOpen(true)}
          >
            Добавить организацию
          </button>
        )}
      </div>

      <p className="field__hint">
        Поля со звёздочкой обязательны. Организация, выдавшая документ, не создаётся
        автоматически: её добавляют отдельным действием.
      </p>
    </div>
  )
}
