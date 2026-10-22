import { useEffect, useRef, type KeyboardEvent } from 'react'

import { describeVerdictError, useVerificationDecision } from '../hooks/useVerificationDecision'
import type { DocumentOut } from '../types/api'
import Notice from './Notice'

interface ConfirmDecisionProps {
  documentId: number
  documentNumber: string
  /** Attachments the card has counted, or `null` while that count is unknown. */
  fileCount: number | null
  onDecided: (stored: DocumentOut) => void
  onClose: () => void
}

/**
 * The second step of a confirmation, next to the button that started it.
 *
 * A confirmation is one act with two clicks, and moving the second click to the
 * far side of the page is what made it feel like a different operation. The
 * compact panel therefore lives inside the header's action zone, directly under
 * «Подтвердить», and carries only what the act needs: the question, the two
 * buttons, and the one warning that can change the user's mind.
 *
 * It is not a modal and it does not trap the focus: it is an inline expansion of
 * a button, so `role="group"` is honest about that. The focus moves to
 * «Да, подтвердить» on open — Enter then completes the act — and the caller
 * returns it to the trigger on cancel. Escape closes the panel, but only while
 * nothing is in flight.
 *
 * The count of attachments is advisory. When the card knows there are none, the
 * warning says the server will refuse; the button still sends, because the count
 * can be stale and the rule belongs to the backend. When the count is unknown,
 * the panel says so rather than guessing in either direction.
 *
 * `useSubmit` inside the shared hook refuses a second `POST`, including from a
 * double click that lands before the button renders as disabled.
 */
export default function ConfirmDecision({
  documentId,
  documentNumber,
  fileCount,
  onDecided,
  onClose,
}: ConfirmDecisionProps) {
  const decision = useVerificationDecision(documentId, 'verified', onDecided)
  const confirmRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    confirmRef.current?.focus()
  }, [])

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape' && !decision.pending) {
      event.stopPropagation()
      onClose()
    }
  }

  return (
    <div
      className="verdict-popover"
      role="group"
      aria-label="Подтверждение документа"
      onKeyDown={handleKeyDown}
    >
      <p className="verdict-popover__question">
        Подтвердить документ {documentNumber}?
      </p>

      {fileCount === 0 && (
        <Notice tone="warning">
          У документа нет прикреплённых файлов — сервер откажет. Загрузите скан и повторите.
        </Notice>
      )}

      {fileCount === null && (
        <p className="field__hint">
          Количество вложений сейчас неизвестно — проверит сервер.
        </p>
      )}

      {decision.error !== null && (
        <Notice tone="error">{describeVerdictError('verified', decision.error)}</Notice>
      )}

      <div className="verdict-popover__actions">
        <button
          ref={confirmRef}
          type="button"
          className="button button--primary"
          disabled={decision.pending}
          onClick={() => void decision.submit(null)}
        >
          {decision.pending ? 'Отправка…' : 'Да, подтвердить'}
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
    </div>
  )
}
