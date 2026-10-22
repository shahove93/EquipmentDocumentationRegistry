interface PaginationProps {
  offset: number
  pageSize: number
  count: number
  hasNext: boolean
  onPrev: () => void
  onNext: () => void
}

/**
 * Prev/next paging for a collection that carries no total.
 *
 * The backend returns a bare array, so the number of pages is unknown. The page
 * fetch asks for one row more than it shows; `hasNext` is that extra row's
 * presence, decided by the caller. This component only renders the outcome.
 */
export default function Pagination({
  offset,
  pageSize,
  count,
  hasNext,
  onPrev,
  onNext,
}: PaginationProps) {
  const page = Math.floor(offset / pageSize) + 1
  const first = offset + 1
  const last = offset + count

  return (
    <div className="pagination">
      <span className="pagination__info">
        Страница {page} · записи {first}–{last}
      </span>
      <div className="pagination__buttons">
        <button type="button" className="button" onClick={onPrev} disabled={offset === 0}>
          ← Назад
        </button>
        <button type="button" className="button" onClick={onNext} disabled={!hasNext}>
          Вперёд →
        </button>
      </div>
    </div>
  )
}
