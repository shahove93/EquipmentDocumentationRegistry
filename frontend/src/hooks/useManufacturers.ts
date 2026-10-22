import { useCallback, useEffect, useState } from 'react'

import { loadAllManufacturers } from '../api/references'
import type { ManufacturerRead } from '../types/api'

export interface ManufacturerList {
  items: ManufacturerRead[]
  /** True once a read was attempted and answered; false while it is disabled. */
  loaded: boolean
  /** True when the page cap stopped the walk before the reference was exhausted. */
  truncated: boolean
  failed: boolean
  /** Record a row created from this screen, so it is selectable at once. */
  add: (manufacturer: ManufacturerRead) => void
  reload: () => void
}

/**
 * The manufacturer reference, read in pages.
 *
 * The list is walked to the end, not taken from the first page, because it feeds
 * a `<select>` the user cannot check against a second source: a silently short
 * list would hide a manufacturer that exists. A walk stopped by the cap says so
 * through `truncated`, and the forms say it to the user.
 *
 * `enabled` exists for the screen that only needs the list when a product form is
 * opened — the document card's picker must not read a whole reference on mount
 * for a panel nobody opened yet.
 *
 * A failure is not fatal and is not thrown: the catalog still lists what it has,
 * a missing manufacturer can still be created, and the caller decides what to
 * show. Reading again clears the flag only when it succeeds.
 */
export function useManufacturers(enabled = true): ManufacturerList {
  const [items, setItems] = useState<ManufacturerRead[]>([])
  const [loaded, setLoaded] = useState(false)
  const [truncated, setTruncated] = useState(false)
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (!enabled) {
      return undefined
    }
    const controller = new AbortController()
    loadAllManufacturers(controller.signal)
      .then((page) => {
        if (controller.signal.aborted) {
          return
        }
        setItems(page.items)
        setTruncated(page.truncated)
        setFailed(false)
        setLoaded(true)
      })
      .catch(() => {
        if (controller.signal.aborted) {
          return
        }
        // What was loaded stays usable; the flag only says the reference could
        // not be read this time.
        setFailed(true)
        setLoaded(true)
      })
    return () => controller.abort()
  }, [enabled, attempt])

  const add = useCallback((manufacturer: ManufacturerRead) => {
    setItems((current) =>
      current.some((row) => row.id === manufacturer.id) ? current : [...current, manufacturer],
    )
    setFailed(false)
    setLoaded(true)
  }, [])

  const reload = useCallback(() => {
    setAttempt((current) => current + 1)
  }, [])

  return { items, loaded, truncated, failed, add, reload }
}
