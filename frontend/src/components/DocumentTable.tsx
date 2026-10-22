import { Link } from 'react-router-dom'

import StatusBadge from './StatusBadge'
import type { DocumentOut } from '../types/api'
import { formatDate } from '../utils/format'

interface DocumentTableProps {
  documents: DocumentOut[]
  typeNames: Map<number, string>
}

/**
 * The registry table.
 *
 * `DocumentOut` carries only `document_type_id`, not the type name, so the
 * caller passes a resolved id-to-name map. When an id has no entry the cell
 * shows `№<id>` rather than a guessed name: an empty or unreachable reference
 * list must not turn into invented type labels.
 */
export default function DocumentTable({ documents, typeNames }: DocumentTableProps) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th scope="col">Номер</th>
            <th scope="col">Тип документа</th>
            <th scope="col">Дата выдачи</th>
            <th scope="col">Действует до</th>
            <th scope="col">Статус</th>
            <th scope="col" className="table__action-col">
              Действие
            </th>
          </tr>
        </thead>
        <tbody>
          {documents.map((document) => {
            const typeName = typeNames.get(document.document_type_id)
            return (
              <tr key={document.id}>
                <td className="table__number">{document.number}</td>
                <td>
                  {typeName ?? (
                    <span className="muted" title={`ID типа документа: ${document.document_type_id}`}>
                      №{document.document_type_id}
                    </span>
                  )}
                </td>
                <td>{formatDate(document.issue_date)}</td>
                <td>{formatDate(document.valid_to)}</td>
                <td>
                  <StatusBadge status={document.verification_status} />
                </td>
                <td className="table__action-col">
                  <Link className="link" to={`/documents/${document.id}`}>
                    Открыть
                  </Link>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
