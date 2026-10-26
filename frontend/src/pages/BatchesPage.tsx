import { useCallback, useEffect, useRef, useState } from 'react'
import { describeError } from '../api/client'
import { fetchBatch, fetchBatches } from '../api/batches'
import BatchForm from '../components/BatchForm'
import Notice from '../components/Notice'
import Pagination from '../components/Pagination'
import type { BatchRead } from '../types/api'
import { formatDate } from '../utils/format'

const PAGE_SIZE = 25
type LoadState =
  | { status: 'loading' }
  | { status: 'ready'; rows: BatchRead[]; hasNext: boolean }
  | { status: 'error'; message: string }

export default function BatchesPage() {
  const [offset, setOffset] = useState(0)
  const [attempt, setAttempt] = useState(0)
  const [list, setList] = useState<LoadState>({ status: 'loading' })
  const [selected, setSelected] = useState<BatchRead | null>(null)
  const [requestedId, setRequestedId] = useState<number | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [creating, setCreating] = useState(false)
  const selectionEpoch = useRef(0)
  const retry = useCallback(() => setAttempt((value) => value + 1), [])

  useEffect(() => {
    const controller = new AbortController()
    setList({ status: 'loading' })
    fetchBatches(PAGE_SIZE + 1, offset, controller.signal)
      .then((rows) => {
        if (!controller.signal.aborted) setList({ status: 'ready', rows: rows.slice(0, PAGE_SIZE), hasNext: rows.length > PAGE_SIZE })
      })
      .catch((error) => {
        if (!controller.signal.aborted) setList({ status: 'error', message: describeError(error) })
      })
    return () => controller.abort()
  }, [offset, attempt])

  useEffect(() => {
    if (requestedId === null) return
    const controller = new AbortController()
    setSelected(null)
    setDetailError(null)
    fetchBatch(requestedId, controller.signal)
      .then((row) => { if (!controller.signal.aborted) setSelected(row) })
      .catch((error) => { if (!controller.signal.aborted) setDetailError(describeError(error)) })
    return () => controller.abort()
  }, [requestedId])

  function choose(row: BatchRead) {
    selectionEpoch.current += 1
    setDetailError(null)
    setEditing(false)
    setRequestedId(row.id)
  }

  function saved(row: BatchRead) {
    setSelected(row)
    setRequestedId(row.id)
    setCreating(false)
    setEditing(false)
    retry()
    if (offset !== 0) setOffset(0)
  }

  const createFormEpoch = selectionEpoch.current

  return (
    <main className="page">
      <header className="page__header">
        <div><h1 className="page__title">Партии</h1><p className="page__subtitle">Список и реквизиты партий продукции</p></div>
        <button className="button button--primary" onClick={() => { selectionEpoch.current += 1; setCreating(true); setEditing(false) }}>Новая партия</button>
      </header>
      {creating && <section className="panel batch-panel"><h2>Создание партии</h2><BatchForm batch={null} onSaved={(row) => { if (selectionEpoch.current === createFormEpoch) saved(row) }} onCancel={() => { selectionEpoch.current += 1; setCreating(false) }} /></section>}
      {list.status === 'loading' && <p role="status">Загрузка партий…</p>}
      {list.status === 'error' && <Notice tone="error"><p>Не удалось загрузить партии. {list.message}</p><button className="button" onClick={retry}>Повторить</button></Notice>}
      {list.status === 'ready' && (
        <>
          <div className="panel table-wrap">
            <table><thead><tr><th>ID</th><th>Типоразмер</th><th>Номер партии</th><th>Дата изготовления</th><th>Количество</th><th>Единица</th></tr></thead>
              <tbody>{list.rows.map((row) => <tr key={row.id}><td><button className="text-button" onClick={() => void choose(row)}>{row.id}</button></td><td>{row.variant_id}</td><td>{row.batch_number ?? '—'}</td><td>{formatDate(row.manufacture_date)}</td><td>{row.quantity ?? '—'}</td><td>{row.quantity_unit ?? '—'}</td></tr>)}</tbody>
            </table>
            {list.rows.length === 0 && <p className="empty-state">На этой странице партий нет.</p>}
          </div>
          <Pagination offset={offset} pageSize={PAGE_SIZE} count={list.rows.length} hasNext={list.hasNext} onPrev={() => setOffset(Math.max(0, offset - PAGE_SIZE))} onNext={() => setOffset(offset + PAGE_SIZE)} />
        </>
      )}
      {(selected || detailError) && (
        <section className="panel batch-panel">
          <h2>Партия {selected ? `#${selected.id}` : requestedId ? `#${requestedId}` : ''}</h2>
          {detailError && <Notice tone="error"><p>Не удалось открыть партию. {detailError}</p></Notice>}
          {selected && (editing
            ? <BatchForm key={selected.id} batch={selected} onSaved={saved} onCancel={() => setEditing(false)} />
            : <><dl className="batch-details">{[
              ['ID', String(selected.id)], ['ID типоразмера', String(selected.variant_id)], ['Номер партии', selected.batch_number ?? '—'],
              ['Дата изготовления', formatDate(selected.manufacture_date)], ['Количество', selected.quantity ?? '—'], ['Единица измерения', selected.quantity_unit ?? '—'],
            ].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl><button className="button" onClick={() => setEditing(true)}>Изменить</button></>
          )}
        </section>
      )}
    </main>
  )
}
