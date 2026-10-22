import type { FormEvent } from 'react'

import { describeError } from '../api/client'
import { updateDocument } from '../api/documents'
import { createDocumentType, createIssuer } from '../api/references'
import { useReferences } from '../hooks/useReferences'
import { useRequisites } from '../hooks/useRequisites'
import type { DocumentOut } from '../types/api'
import {
  hasErrors,
  requisitesFromDocument,
  toUpdateBody,
  validateRequisites,
  willResetVerificationStatus,
} from '../utils/forms'
import { labelForStatus } from '../utils/labels'
import DocumentRequisitesForm from './DocumentRequisitesForm'
import Notice from './Notice'

interface DocumentEditFormProps {
  document: DocumentOut
  /** The card reloads the document and its history; the form does not close itself. */
  onSaved: () => void
  onCancel: () => void
}

/**
 * The edit form, replacing the requisites while it is open.
 *
 * The patch is built from the form and the record together, so it carries only
 * what changed. That is not just economy: an unchanged field is a field the
 * backend would read as a re-assertion, and only a real change to a significant
 * field is allowed to re-open a decided document. The warning above the fields
 * is computed from the same comparison, so it appears exactly when the save
 * brings the status back to «На проверке» — and, as the assignment requires,
 * not when only the notes were touched.
 *
 * The status itself is never part of the request. It is not a field of
 * `DocumentUpdate`, and it moves only as a consequence of the data, which is a
 * rule of the backend rather than a convention of this form.
 *
 * A failure leaves the form exactly as it was, values included: `useSubmit`
 * reports the error and returns, and nothing has been written to state.
 */
export default function DocumentEditForm({
  document,
  onSaved,
  onCancel,
}: DocumentEditFormProps) {
  const { values, errors, change, setErrors, submission } = useRequisites(
    requisitesFromDocument(document),
  )
  const references = useReferences()

  const body = toUpdateBody(document, values)
  const unchanged = Object.keys(body).length === 0
  const resetsStatus = willResetVerificationStatus(document, values)

  const handleCreateDocumentType = async (name: string) => {
    const created = await createDocumentType(name)
    references.addDocumentType(created)
    change({ documentTypeId: String(created.id) })
  }

  const handleCreateIssuer = async (name: string) => {
    const created = await createIssuer(name)
    references.addIssuer(created)
    change({ issuerId: String(created.id) })
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const validation = validateRequisites(values)
    setErrors(validation)
    if (hasErrors(validation)) {
      return
    }
    // Nothing to send. The save button is already disabled in this case; the
    // guard is here so a submit from a text field cannot slip past it.
    if (unchanged) {
      return
    }
    const saved = await submission.run(async () => {
      await updateDocument(document.id, body)
    })
    if (saved) {
      onSaved()
      onCancel()
    }
  }

  return (
    <form className="form form--edit" onSubmit={handleSubmit} noValidate>
      {resetsStatus && (
        <Notice tone="warning">
          Изменение значимых реквизитов (тип, номер, даты, кем выдан документ) вернёт документ на
          проверку: статус «{labelForStatus(document.verification_status)}» сменится на «На
          проверке».
        </Notice>
      )}

      <DocumentRequisitesForm
        idPrefix="edit"
        values={values}
        errors={errors}
        disabled={submission.pending}
        documentTypes={references.documentTypes}
        documentTypesLoaded={references.documentTypesLoaded}
        documentTypesTruncated={references.documentTypesTruncated}
        issuers={references.issuers}
        issuersTruncated={references.issuersTruncated}
        onChange={change}
        onCreateDocumentType={handleCreateDocumentType}
        onCreateIssuer={handleCreateIssuer}
      />

      {references.documentTypesFailed && (
        <Notice tone="error">
          Не удалось загрузить справочник типов документов. Текущий тип сохранён в списке, а
          новый тип можно создать.
        </Notice>
      )}
      {references.issuersFailed && (
        <Notice tone="error">
          Не удалось загрузить справочник организаций. Текущая организация сохранена в списке, а
          нового можно создать.
        </Notice>
      )}
      {submission.error !== null && <Notice tone="error">{describeError(submission.error)}</Notice>}

      {unchanged && <Notice tone="info">Изменений нет — сохранять нечего.</Notice>}

      <div className="form__actions">
        <button
          type="submit"
          className="button button--primary"
          disabled={submission.pending || unchanged}
        >
          Сохранить
        </button>
        <button type="button" className="button" disabled={submission.pending} onClick={onCancel}>
          Отмена
        </button>
      </div>

      <p className="field__hint">
        Статус проверки формой не меняется: он переходит сам — по значимым реквизитам или по
        составу вложений.
      </p>
    </form>
  )
}
