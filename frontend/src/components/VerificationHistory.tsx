import StatusBadge from './StatusBadge'
import type { DocumentVerificationEventOut } from '../types/api'
import { formatDateTime } from '../utils/format'
import { labelForEventType, labelForReason, labelForStatus } from '../utils/labels'

interface VerificationHistoryProps {
  events: DocumentVerificationEventOut[]
}

/**
 * Recorded verification transitions, in the order the API returns them —
 * chronological, oldest first, which is how a decision trail is read.
 *
 * `event_type` says why the transition happened, so it is its own column rather
 * than a restatement of the target status. A `reopened` event carries a machine
 * code in `reason` and a `rejected` event carries the auditor's own wording in
 * the same column; the first is translated, the second is shown as written, and
 * a missing reason is shown as an em dash. Nothing here is invented, and the
 * raw value of every translated field stays available on hover.
 *
 * The row carries no per-person data because the table records none: there is
 * no reviewer column to show, and the interface does not imply one.
 */
export default function VerificationHistory({ events }: VerificationHistoryProps) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th scope="col">Когда</th>
            <th scope="col">Событие</th>
            <th scope="col">Статус</th>
            <th scope="col">Причина</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => {
            const reason = labelForReason(event.reason)
            return (
              <tr key={event.id}>
                <td className="table__number">{formatDateTime(event.created_at)}</td>
                <td>
                  <span title={event.event_type}>{labelForEventType(event.event_type)}</span>
                </td>
                <td
                  className="history__status"
                  aria-label={`Статус изменён: ${labelForStatus(event.from_status)} → ${labelForStatus(event.to_status)}`}
                >
                  <StatusBadge status={event.from_status} />
                  <span className="history__arrow" aria-hidden="true">
                    →
                  </span>
                  <StatusBadge status={event.to_status} />
                </td>
                <td>{reason ?? <span className="muted">—</span>}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
