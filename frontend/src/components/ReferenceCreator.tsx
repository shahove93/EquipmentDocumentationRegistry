import { useState, type KeyboardEvent } from 'react'

import { ApiError, describeError } from '../api/client'
import { useSubmit } from '../hooks/useSubmit'
import Notice from './Notice'

interface ReferenceCreatorProps {
  /** Heading for the small form, e.g. «Новый тип документа». */
  title: string
  placeholder: string
  /** Visible label of the single field. «Название» fits most references. */
  fieldLabel?: string
  /** The schema's maximum for this reference's `name`. */
  maxLength: number
  submitLabel: string
  /**
   * Create the row and select it. Rejecting leaves the form open with the name
   * the user typed; the caller decides what to do with the created row.
   */
  onCreate: (name: string) => Promise<void>
  onClose: () => void
}

/**
 * The explicit "add a reference row" form.
 *
 * Reference rows are never created as a side effect of another action: a name
 * the user typed into a document is not a reason to alter the reference list,
 * so the create is a separate, visible act that says which list it writes to.
 * A duplicate name answers `409`, and that status is reported as what it is —
 * the name is taken — rather than as a generic conflict, because retyping the
 * same name is the obvious mistake here.
 *
 * There is no `<form>` element here, and that is not a shortcut. This control
 * sits inside the document form, and HTML forbids a form inside a form: the
 * inner one is dropped by the parser and its submit would reach the outer
 * handler, which is the very thing that must not happen — a name meant for the
 * reference list must never create a document. Enter is handled on the name
 * field instead, so the keyboard behaves as it would in a real form without
 * letting the keystroke escape to the outer submit.
 */
export default function ReferenceCreator({
  title,
  placeholder,
  fieldLabel = 'Название',
  maxLength,
  submitLabel,
  onCreate,
  onClose,
}: ReferenceCreatorProps) {
  const [name, setName] = useState('')
  const submission = useSubmit()
  const trimmed = name.trim()

  const submit = async () => {
    if (trimmed === '') {
      return
    }
    const created = await submission.run(async () => {
      await onCreate(trimmed)
    })
    if (created) {
      onClose()
    }
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault()
      void submit()
    }
  }

  const message =
    submission.error instanceof ApiError && submission.error.status === 409
      ? 'Такое название уже есть в справочнике.'
      : describeError(submission.error)

  return (
    <div className="creator">
      <p className="creator__title">{title}</p>

      <label className="field">
        <span className="field__label">{fieldLabel}</span>
        <input
          className="field__input"
          type="text"
          value={name}
          maxLength={maxLength}
          placeholder={placeholder}
          onKeyDown={handleKeyDown}
          onChange={(event) => {
            setName(event.target.value)
            submission.reset()
          }}
        />
      </label>

      {submission.error !== null && <Notice tone="error">{message}</Notice>}

      <div className="creator__actions">
        <button
          type="button"
          className="button"
          disabled={submission.pending || trimmed === ''}
          onClick={() => void submit()}
        >
          {submitLabel}
        </button>
        <button type="button" className="button" disabled={submission.pending} onClick={onClose}>
          Отмена
        </button>
      </div>
    </div>
  )
}
