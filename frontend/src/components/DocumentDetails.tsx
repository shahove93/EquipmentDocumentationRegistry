import StatusBadge from './StatusBadge'
import type { DocumentOut } from '../types/api'
import { formatDate } from '../utils/format'

interface DocumentDetailsProps {
  document: DocumentOut
  /** Resolved from `document_type_id`; `null` when the lookup failed. */
  typeName: string | null
  /** Resolved from `issuer_id`; `null` when there is none or the lookup failed. */
  issuerName: string | null
}

const NOT_SPECIFIED = 'Не указано'

/** An id shown on its own, for a reference that could not be resolved. */
function UnresolvedId({ id }: { id: number }) {
  return (
    <span className="muted" title="Название справочника недоступно">
      №{id}
    </span>
  )
}

/**
 * The document's own requisites.
 *
 * `DocumentOut` carries foreign keys, not names, so the type and the issuer are
 * resolved by the page and passed in already resolved or already failed. When a
 * lookup fails the cell shows the id that is actually stored — never a made-up
 * name — and a genuinely empty reference shows «Не указано», which is a fact
 * about the record rather than a failure to display it.
 */
export default function DocumentDetails({
  document,
  typeName,
  issuerName,
}: DocumentDetailsProps) {
  const hasNotes = document.notes !== null && document.notes !== ''

  return (
    <dl className="defs">
      <div className="defs__row">
        <dt className="defs__term">Тип документа</dt>
        <dd className="defs__value">
          {typeName ?? <UnresolvedId id={document.document_type_id} />}
        </dd>
      </div>

      <div className="defs__row">
        <dt className="defs__term">Номер</dt>
        <dd className="defs__value">{document.number}</dd>
      </div>

      <div className="defs__row">
        <dt className="defs__term">Дата выдачи</dt>
        <dd className="defs__value">{formatDate(document.issue_date)}</dd>
      </div>

      <div className="defs__row">
        <dt className="defs__term">Действует с</dt>
        <dd className="defs__value">{formatDate(document.valid_from)}</dd>
      </div>

      <div className="defs__row">
        <dt className="defs__term">Действует до</dt>
        <dd className="defs__value">{formatDate(document.valid_to)}</dd>
      </div>

      <div className="defs__row">
        <dt className="defs__term">Кем выдан документ</dt>
        <dd className="defs__value">
          {document.issuer_id === null ? (
            <span className="muted">{NOT_SPECIFIED}</span>
          ) : (
            (issuerName ?? <UnresolvedId id={document.issuer_id} />)
          )}
        </dd>
      </div>

      <div className="defs__row">
        <dt className="defs__term">Статус проверки</dt>
        <dd className="defs__value">
          <StatusBadge status={document.verification_status} />
        </dd>
      </div>

      <div className="defs__row defs__row--wide">
        <dt className="defs__term">Примечания</dt>
        <dd className="defs__value">
          {hasNotes ? document.notes : <span className="muted">{NOT_SPECIFIED}</span>}
        </dd>
      </div>
    </dl>
  )
}
