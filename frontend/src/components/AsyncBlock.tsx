import type { ReactNode } from 'react'

import { describeError } from '../api/client'
import type { Section } from '../hooks/useSection'

interface AsyncBlockProps<T> {
  title: string
  state: Section<T>
  onRetry: () => void
  children: (data: T) => ReactNode
}

/**
 * One region of the card: a heading plus that region's own loading and error
 * states.
 *
 * It exists so the blocks cannot drift apart, and so a failure is contained. The
 * error branch is local to the block — it never unmounts the requisites above
 * it, which is the point: a broken history request must not take a successfully
 * loaded document off the screen.
 *
 * What "empty" looks like is left to `children`, not decided here. An empty
 * region is not always a dead end — a document with no variants is exactly the
 * document whose variants someone needs to attach — so the loaded content is
 * handed over whatever it contains and the block itself says "nothing here"
 * only where that is the whole truth.
 *
 * The message is `describeError`, never the server's body, so a failed request
 * cannot surface an internal detail through the interface.
 */
export default function AsyncBlock<T>({ title, state, onRetry, children }: AsyncBlockProps<T>) {
  return (
    <section className="card__section">
      <h2 className="section-title">{title}</h2>

      {state.status === 'loading' && (
        <p className="muted" role="status">
          Загрузка…
        </p>
      )}

      {state.status === 'idle' && <p className="muted">Раздел недоступен.</p>}

      {state.status === 'error' && (
        <div className="block-error" role="alert">
          <p>{describeError(state.error)}</p>
          <button type="button" className="button" onClick={onRetry}>
            Повторить
          </button>
        </div>
      )}

      {state.status === 'ready' && children(state.data)}
    </section>
  )
}
