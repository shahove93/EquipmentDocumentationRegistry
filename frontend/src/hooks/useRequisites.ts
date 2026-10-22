import { useCallback, useState } from 'react'

import { useSubmit, type Submission } from './useSubmit'
import type { RequisiteErrors, RequisiteValues } from '../utils/forms'

export interface RequisitesForm {
  values: RequisiteValues
  errors: RequisiteErrors
  change: (patch: Partial<RequisiteValues>) => void
  setErrors: (errors: RequisiteErrors) => void
  submission: Submission
}

/**
 * The state of one requisites form: what is typed, what was refused, and
 * whether a write is running.
 *
 * The create screen and the edit screen behave identically here on purpose. A
 * field whose message is on screen stops being the field that was refused the
 * moment its value changes, so the message goes with it; and editing anything
 * clears the previous request's failure, because a message about the last
 * attempt must not outlive the change that answers it.
 *
 * `initial` is read once, when the form mounts. A caller whose underlying record
 * can change underneath — the edit form, after the card reloads — is expected to
 * close or remount the form rather than reuse it with new values.
 */
export function useRequisites(initial: RequisiteValues): RequisitesForm {
  const [values, setValues] = useState(initial)
  const [errors, setErrors] = useState<RequisiteErrors>({})
  const submission = useSubmit()
  const { reset } = submission

  const change = useCallback(
    (patch: Partial<RequisiteValues>) => {
      setValues((current) => ({ ...current, ...patch }))
      setErrors((current) => {
        const touched = Object.keys(patch).filter((key) => key in current)
        if (touched.length === 0) {
          return current
        }
        const next = { ...current }
        for (const key of touched) {
          delete next[key as keyof RequisiteValues]
        }
        return next
      })
      reset()
    },
    [reset],
  )

  return { values, errors, change, setErrors, submission }
}
