import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * The state of one independently-loaded region of a screen.
 *
 * `idle` exists for the case where there is nothing to ask for at all — an
 * address whose id is not a document id. It is kept apart from `loading` so a
 * malformed URL does not look like a request in flight.
 */
export type Section<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; data: T }
  | { status: 'error'; error: unknown }

export type SectionLoader<T> = (id: number, signal: AbortSignal) => Promise<T>

/**
 * Load one region of the card for one document id.
 *
 * Two properties matter and both come from the abort, not from the promise.
 * A reply for an id that is no longer on screen is dropped rather than written
 * into state, so a slow response cannot paint one document's data over another
 * during a fast route change. And each region owns its own state, so a failure
 * in one — the history, say — leaves the regions that already answered intact.
 *
 * A reload of the region already on screen keeps its rows visible while the
 * fresh answer is in flight; only an id change clears them. Without that, saving
 * a form would blank the block it just changed and the user would be reading
 * «Загрузка…» instead of the result of their own edit. The distinction is kept
 * by remembering which id the visible state was loaded for, not by trusting
 * `documentId` to differ from it.
 *
 * `load` is expected to be a module-level function so that its identity is
 * stable; it is in the dependency list so a deliberate change of loader is
 * honoured, not because a component would normally pass a new one each render.
 */
export function useSection<T>(
  documentId: number | null,
  load: SectionLoader<T>,
): [Section<T>, () => void] {
  const [state, setState] = useState<Section<T>>(
    documentId === null ? { status: 'idle' } : { status: 'loading' },
  )
  const [attempt, setAttempt] = useState(0)

  /** The id the visible state describes, or `null` when nothing is shown. */
  const loadedIdRef = useRef<number | null>(null)

  useEffect(() => {
    if (documentId === null) {
      loadedIdRef.current = null
      setState({ status: 'idle' })
      return
    }
    const controller = new AbortController()

    // Same id as the visible state: a reload, so what is on screen stays until
    // it is replaced. Different id: different document, so nothing may survive.
    if (loadedIdRef.current !== documentId) {
      setState({ status: 'loading' })
    }

    load(documentId, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          loadedIdRef.current = documentId
          setState({ status: 'ready', data })
        }
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return
        }
        // Nothing is shown any more, so there is no id the visible state
        // describes; a retry then has to go through `loading` again.
        loadedIdRef.current = null
        setState({ status: 'error', error })
      })
    return () => controller.abort()
  }, [documentId, load, attempt])

  const reload = useCallback(() => {
    setAttempt((current) => current + 1)
  }, [])

  return [state, reload]
}
