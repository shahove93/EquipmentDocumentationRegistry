import { useEffect, useRef, useState, type FormEvent } from 'react'

import { describeVerdictError, useVerificationDecision } from '../hooks/useVerificationDecision'
import type { DocumentOut } from '../types/api'
import { labelForStatus } from '../utils/labels'
import Notice from './Notice'

interface DocumentVerdictPanelProps {
  document: DocumentOut
  /** Called with the document the server returned, so the card can reload. */
  onDecided: (stored: DocumentOut) => void
  /** Called to drop the panel without recording anything. */
  onClose: () => void
}

/**
 * The rejection panel: the reason, and what the current decision means.
 *
 * Rejecting is not a two-button confirmation. It has a required reason that is
 * recorded verbatim for an auditor, and it has two states worth explaining — a
 * document that is already rejected is not re-rejected as far as the backend is
 * concerned, and a confirmed document may be rejected directly. That is why this
 * one keeps a panel of its own instead of the compact shape used next to the
 * header's «Подтвердить».
 *
 * Nothing is written until the server answers. The panel keeps no shadow copy of
 * the status and never writes a history event of its own — the card reloads the
 * document and its history afterwards, so what is displayed is always what was
 * stored, including the idempotent case where a repeated rejection changes
 * nothing at all.
 *
 * A reason made only of whitespace is refused locally so an obviously empty form
 * does not travel, but the text is then sent exactly as typed, without trimming,
 * because the backend records it verbatim. A failure leaves the text in place so
 * it can be sent again.
 */
export default function DocumentVerdictPanel({
  document,
  onDecided,
  onClose,
}: DocumentVerdictPanelProps) {
  const decision = useVerificationDecision(document.id, 'rejected', onDecided)
  const [reason, setReason] = useState('')
  const [reasonError, setReasonError] = useState<string | null>(null)
  const reasonRef = useRef<HTMLTextAreaElement>(null)

  const currentStatus = labelForStatus(document.verification_status)
  const alreadyRejected = document.verification_status === 'rejected'
  const alreadyVerified = document.verification_status === 'verified'

  useEffect(() => {
    reasonRef.current?.focus()
  }, [])

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    if (reason.trim() === '') {
      setReasonError('Укажите причину отклонения — пустая причина не принимается.')
      decision.reset()
      return
    }
    setReasonError(null)

    await decision.submit(reason)
  }

  return (
    <form className="form" onSubmit={handleSubmit} noValidate>
      <h2 className="verdict__title">Отклонение документа</h2>

      {alreadyRejected && (
        <Notice tone="info">
          Документ уже отклонён. Повторное отклонение идемпотентно: статус не изменится,
          прежняя причина останется в истории, а введённая сейчас не сохранится.
        </Notice>
      )}

      {alreadyVerified && (
        <Notice tone="info">
          Документ имеет статус «{currentStatus}». Отклонение разрешено напрямую и заменит
          решение на «Отклонён».
        </Notice>
      )}

      <div className="field">
        <label className="field__label" htmlFor="rejection-reason">
          Причина отклонения
        </label>
        <textarea
          id="rejection-reason"
          ref={reasonRef}
          className="field__input"
          rows={3}
          value={reason}
          disabled={decision.pending}
          aria-invalid={reasonError !== null}
          onChange={(event) => {
            setReason(event.target.value)
            setReasonError(null)
            if (decision.error !== null) {
              decision.reset()
            }
          }}
        />
        <p className="field__hint">
          Причина сохраняется в истории проверок как введена и видна тому, кто откроет
          документ.
        </p>
        {reasonError !== null && <p className="field__error">{reasonError}</p>}
      </div>

      {decision.error !== null && (
        <Notice tone="error">{describeVerdictError('rejected', decision.error)}</Notice>
      )}

      <div className="form__actions">
        <button
          type="submit"
          className="button button--danger"
          disabled={decision.pending}
        >
          {decision.pending ? 'Отправка…' : 'Отклонить документ'}
        </button>
        <button
          type="button"
          className="button"
          disabled={decision.pending}
          onClick={onClose}
        >
          Отмена
        </button>
      </div>
    </form>
  )
}
