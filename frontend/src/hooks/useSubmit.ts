import { useCallback, useRef, useState } from 'react'

import { isAbortError } from '../api/client'

export interface Submission {
  /** True while the action is in flight; every submitting control reads it. */
  pending: boolean
  /** The failure to report, or `null`. Never the server's own body. */
  error: unknown
  /**
   * Run one write. Resolves to whether it succeeded, and refuses to start a
   * second time while an earlier call is still running.
   */
  run: (action: () => Promise<void>) => Promise<boolean>
  /** Forget the last failure, for when the user edits the form again. */
  reset: () => void
}

/**
 * One in-flight write for one form.
 *
 * The guard is a ref rather than a check on `pending`, because `pending` only
 * becomes `true` after a re-render and two clicks dispatched in the same tick
 * would both read the old value and both submit — which is exactly the double
 * document the create screen must not produce. The ref is set synchronously, so
 * the second call is refused before it can do anything.
 *
 * The failure is kept as the thrown value and never unwrapped here: the caller
 * turns it into a message through `describeError`, so no component can be
 * tempted to render the response body.
 */
export function useSubmit(): Submission {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const inFlightRef = useRef(false)

  const run = useCallback(async (action: () => Promise<void>): Promise<boolean> => {
    if (inFlightRef.current) {
      return false
    }
    inFlightRef.current = true
    setPending(true)
    setError(null)
    try {
      await action()
      return true
    } catch (caught: unknown) {
      // An abort is a deliberate cancellation, not a failure to report.
      if (!isAbortError(caught)) {
        setError(caught)
      }
      return false
    } finally {
      inFlightRef.current = false
      setPending(false)
    }
  }, [])

  const reset = useCallback(() => {
    setError(null)
  }, [])

  return { pending, error, run, reset }
}
