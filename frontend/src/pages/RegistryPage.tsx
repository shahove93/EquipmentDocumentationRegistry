import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { describeError } from '../api/client'
import { fetchDocuments } from '../api/documents'
import { fetchDocumentTypes, fetchManufacturers } from '../api/references'
import DocumentFilters, {
  EMPTY_FILTERS,
  type FilterValues,
} from '../components/DocumentFilters'
import DocumentTable from '../components/DocumentTable'
import Pagination from '../components/Pagination'
import type {
  DocumentOut,
  DocumentTypeRead,
  ManufacturerRead,
  VerificationStatus,
} from '../types/api'

/**
 * The backend returns a bare array, so "is there a next page?" is answered by
 * asking for one row past the page and looking at whether it arrived. 26 is
 * within the endpoint's `1..100` limit.
 */
const PAGE_SIZE = 25
const PAGE_FETCH = PAGE_SIZE + 1

type ListState =
  | { status: 'loading' }
  | { status: 'ready'; documents: DocumentOut[]; hasNext: boolean }
  | { status: 'error'; message: string }

function hasAnyFilter(values: FilterValues): boolean {
  return (
    values.number !== '' ||
    values.material !== '' ||
    values.size_text !== '' ||
    values.standard !== '' ||
    values.manufacturerId !== '' ||
    values.status !== ''
  )
}

/** Screen `/`: search and browse the document registry. */
export default function RegistryPage() {
  // `filters` is what the inputs show; `applied` is what the running query uses.
  // Keeping them apart means typing does not fire a request, and a request in
  // flight always reflects a submitted state rather than a half-typed one.
  const [filters, setFilters] = useState<FilterValues>(EMPTY_FILTERS)
  const [applied, setApplied] = useState<FilterValues>(EMPTY_FILTERS)
  const [offset, setOffset] = useState(0)
  const [state, setState] = useState<ListState>({ status: 'loading' })

  const [types, setTypes] = useState<DocumentTypeRead[]>([])
  const [manufacturers, setManufacturers] = useState<ManufacturerRead[]>([])

  // Reference data, loaded once. A failure here is not fatal: the table falls
  // back to numeric type ids and the manufacturer list is simply short. There is
  // no option to silently show a name that the server did not give.
  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      fetchDocumentTypes(controller.signal),
      fetchManufacturers(controller.signal),
    ])
      .then(([documentTypes, makerList]) => {
        setTypes(documentTypes)
        setManufacturers(makerList)
      })
      .catch(() => undefined)
    return () => controller.abort()
  }, [])

  // The list query. Re-runs whenever the applied filters or the page change.
  // The cleanup aborts the previous request so a slow, superseded response can
  // never overwrite a newer one.
  useEffect(() => {
    const controller = new AbortController()
    setState({ status: 'loading' })

    fetchDocuments(
      {
        number: applied.number || undefined,
        material: applied.material || undefined,
        size_text: applied.size_text || undefined,
        standard: applied.standard || undefined,
        manufacturer_id:
          applied.manufacturerId === '' ? undefined : Number(applied.manufacturerId),
        status: applied.status === '' ? undefined : (applied.status as VerificationStatus),
        limit: PAGE_FETCH,
        offset,
      },
      controller.signal,
    )
      .then((rows) => {
        const hasNext = rows.length > PAGE_SIZE
        setState({
          status: 'ready',
          documents: hasNext ? rows.slice(0, PAGE_SIZE) : rows,
          hasNext,
        })
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return
        }
        setState({ status: 'error', message: describeError(error) })
      })

    return () => controller.abort()
  }, [applied, offset])

  const typeNames = useMemo(() => {
    const map = new Map<number, string>()
    for (const type of types) {
      map.set(type.id, type.name)
    }
    return map
  }, [types])

  // A fresh object each time, so pressing «Найти» with unchanged fields still
  // re-runs the effect and re-queries.
  const submit = useCallback(() => {
    setApplied({ ...filters })
    setOffset(0)
  }, [filters])

  const reset = useCallback(() => {
    setFilters(EMPTY_FILTERS)
    setApplied({ ...EMPTY_FILTERS })
    setOffset(0)
  }, [])

  const reload = useCallback(() => {
    setApplied((current) => ({ ...current }))
  }, [])

  const filtersActive = hasAnyFilter(applied)

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1 className="page__title">Реестр сертификатов и паспортов</h1>
          <p className="page__subtitle">
            Поиск по номеру, материалу, типоразмеру, ГОСТ/ТУ, производителю и статусу
          </p>
        </div>
        <Link className="button button--primary" to="/documents/new">
          Добавить документ
        </Link>
      </header>

      <DocumentFilters
        value={filters}
        manufacturers={manufacturers}
        onChange={setFilters}
        onSubmit={submit}
        onReset={reset}
      />

      <section className="panel">
        {state.status === 'loading' && (
          <div className="state state--loading" role="status">
            Загрузка…
          </div>
        )}

        {state.status === 'error' && (
          <div className="state state--error" role="alert">
            <p>{state.message}</p>
            <button type="button" className="button" onClick={reload}>
              Повторить
            </button>
          </div>
        )}

        {state.status === 'ready' && state.documents.length === 0 && (
          <div className="state">
            {filtersActive ? (
              <>
                <p>Ничего не найдено по заданным условиям.</p>
                <p className="muted">Измените фильтры или сбросьте их.</p>
              </>
            ) : (
              <p>Документов пока нет.</p>
            )}
          </div>
        )}

        {state.status === 'ready' && state.documents.length > 0 && (
          <>
            <DocumentTable documents={state.documents} typeNames={typeNames} />
            <Pagination
              offset={offset}
              pageSize={PAGE_SIZE}
              count={state.documents.length}
              hasNext={state.hasNext}
              onPrev={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}
              onNext={() => setOffset((current) => current + PAGE_SIZE)}
            />
          </>
        )}
      </section>
    </div>
  )
}
