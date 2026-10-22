import { labelForStatus } from '../utils/labels'

/** The values `badge--*` has a style for; anything else gets the neutral one. */
const STYLED_STATUSES = new Set(['pending', 'verified', 'rejected'])

/**
 * A verification status as a coloured pill.
 *
 * The prop is a plain `string` on purpose: history rows carry statuses from
 * their own column, and the interface has to render a value it does not know
 * rather than crash or mislabel it. An unknown status is shown verbatim with a
 * grey pill, and the raw value is always available on hover.
 */
export default function StatusBadge({ status }: { status: string }) {
  const modifier = STYLED_STATUSES.has(status) ? status : 'unknown'
  return (
    <span className={`badge badge--${modifier}`} title={status}>
      {labelForStatus(status)}
    </span>
  )
}
