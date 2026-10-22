import { ApiError, describeError } from '../api/client'
import { submitDocumentVerification } from '../api/documents'
import type { DocumentOut, VerificationDecision } from '../types/api'
import { useSubmit } from './useSubmit'

/**
 * The failure in words that fit the decision that was attempted.
 *
 * A `422` does not mean the same thing for the two verdicts: on a confirmation
 * it is the backend's "no attachment to verify" refusal, while the generic
 * wording for `422` talks about filled-in fields and would send the user to the
 * wrong place. Everything else — a missing document, a conflict, an unreachable
 * server — is the shared translation. Only the status is read, never the
 * response body.
 */
export function describeVerdictError(decision: VerificationDecision, error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 422) {
      return decision === 'verified'
        ? 'Нельзя подтвердить документ без вложения: решение относится к скану, а его нет. Загрузите файл во вложениях и повторите.'
        : 'Сервер не принял причину отклонения. Проверьте текст и повторите.'
    }
    if (error.status === 404) {
      return 'Документ не найден. Возможно, он был удалён, — обновите страницу.'
    }
  }
  return describeError(error)
}

export interface DecisionSubmission {
  /** True while the request is in flight; every control of the panel reads it. */
  pending: boolean
  /** The failure to report, or `null`. Never the server's own body. */
  error: unknown
  /** Record the verdict, then hand the stored document to the caller. */
  submit: (reason: string | null) => Promise<void>
  /** Forget the last failure, for when the user edits the form again. */
  reset: () => void
}

/**
 * One recorded decision, shared by the two shapes the interface gives it.
 *
 * Confirming is a compact two-button confirmation next to the action that
 * started it; rejecting needs a reason and therefore a panel of its own. Both
 * send the same body to the same route and must report the same failures the
 * same way, so the request lives here and only the two presentations differ.
 *
 * `onDecided` receives the document the server returned, not an assumed status:
 * a repeated rejection is accepted with the status unchanged and nothing added
 * to the history, and the screen has to say exactly that.
 *
 * Double submission is refused by `useSubmit`'s synchronous guard, so neither
 * presentation can send a second `POST` from a fast double click — including a
 * click that lands before the button re-renders as disabled.
 */
export function useVerificationDecision(
  documentId: number,
  decision: VerificationDecision,
  onDecided: (stored: DocumentOut) => void,
): DecisionSubmission {
  const submission = useSubmit()

  const submit = async (reason: string | null): Promise<void> => {
    let stored: DocumentOut | null = null
    const accepted = await submission.run(async () => {
      stored = await submitDocumentVerification(documentId, { decision, reason })
    })
    if (accepted && stored !== null) {
      onDecided(stored)
    }
  }

  return {
    pending: submission.pending,
    error: submission.error,
    submit,
    reset: submission.reset,
  }
}
