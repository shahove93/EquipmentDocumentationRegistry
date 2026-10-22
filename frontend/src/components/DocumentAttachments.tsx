import { Fragment, useRef, useState, type FormEvent } from 'react'

import { ApiError, describeError } from '../api/client'
import {
  MAX_UPLOAD_SIZE_BYTES,
  attachmentContentUrl,
  deleteDocumentFile,
  uploadDocumentFile,
} from '../api/documents'
import { useSubmit } from '../hooks/useSubmit'
import type { FileOut } from '../types/api'
import { formatBytes, formatDateTime } from '../utils/format'
import { labelForMimeType, labelForStatus } from '../utils/labels'
import Notice from './Notice'

interface DocumentAttachmentsProps {
  documentId: number
  files: FileOut[]
  /** The document's status: a decided document is re-opened by a file change. */
  verificationStatus: string
  /** Called after a successful upload or removal so the card reloads the list. */
  onChanged: () => void
}

/**
 * The upload's failure in the upload's own words.
 *
 * `422` means one thing here and one thing only: the server read the bytes and
 * did not recognise them as PDF, JPEG or PNG, because it checks the signature
 * rather than the extension. The interface's generic wording for `422` is about
 * filled-in fields, which would send the user looking at the wrong thing, so
 * this case is named for what it is. Nothing from the response is repeated: the
 * route's `detail` is not shown, only its status, translated.
 */
function describeUploadError(error: unknown): string {
  if (error instanceof ApiError && error.status === 422) {
    return 'Сервер не распознал файл как PDF, JPEG или PNG. Формат определяется по содержимому, а не по расширению.'
  }
  return describeError(error)
}

/**
 * The document's attachments, with the two actions that change them.
 *
 * "Скачать" is a link, not a button that fetches. The content route answers with
 * the stored bytes and a `Content-Disposition` carrying the real filename —
 * including the RFC 5987 form for a Cyrillic one — so the browser's own
 * navigation is what preserves it; a JSON request would have to discard the
 * header and could not show the bytes at all. It is opened in a new tab so that
 * a link the server has already forgotten (a `404`, or a `500` for a row whose
 * blob is missing) reports itself there instead of replacing the card.
 *
 * Uploading goes out as multipart. `Content-Type` is not set by hand — only the
 * browser knows the boundary it generated, and the server refuses a file whose
 * *content* is not one of the three accepted types, so a renamed extension does
 * not get through.
 *
 * Removal is confirmed before it is attempted, and the row is not taken off the
 * list until the server has answered `204` and the reload has run. A refusal
 * therefore leaves the table exactly as it was, with the reason shown where the
 * confirmation was: hiding a file the server still holds would be a lie, and the
 * reload is what makes the list reflect the server rather than the click.
 *
 * Both actions change what the document contains, so both tell the user, before
 * they act, that a decided document goes back to «На проверке» — that is this
 * screen's job, not the backend's, because the backend only reports it
 * afterwards in the history.
 */
export default function DocumentAttachments({
  documentId,
  files,
  verificationStatus,
  onChanged,
}: DocumentAttachmentsProps) {
  const upload = useSubmit()
  const deletion = useSubmit()

  const [file, setFile] = useState<File | null>(null)
  const [confirmingId, setConfirmingId] = useState<number | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const decided = verificationStatus !== 'pending'
  const statusName = labelForStatus(verificationStatus)
  const tooLarge = file !== null && file.size > MAX_UPLOAD_SIZE_BYTES

  const handleUpload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const selected = file
    if (selected === null || selected.size > MAX_UPLOAD_SIZE_BYTES) {
      return
    }
    const uploaded = await upload.run(async () => {
      await uploadDocumentFile(documentId, selected)
    })
    if (uploaded) {
      setFile(null)
      if (fileInputRef.current !== null) {
        fileInputRef.current.value = ''
      }
      onChanged()
    }
  }

  const handleDelete = async (target: FileOut) => {
    const removed = await deletion.run(async () => {
      await deleteDocumentFile(documentId, target.id)
    })
    if (removed) {
      setConfirmingId(null)
      onChanged()
    }
  }

  const openConfirmation = (fileId: number) => {
    deletion.reset()
    setConfirmingId(fileId)
  }

  const closeConfirmation = () => {
    deletion.reset()
    setConfirmingId(null)
  }

  return (
    <div className="stack">
      <form className="upload" onSubmit={handleUpload}>
        <div className="toolbar">
          <input
            ref={fileInputRef}
            className="field__input upload__input"
            type="file"
            accept="application/pdf,image/jpeg,image/png"
            disabled={upload.pending}
            aria-label="Файл вложения"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null)
              upload.reset()
            }}
          />
          <button
            type="submit"
            className="button button--primary"
            disabled={file === null || tooLarge || upload.pending}
          >
            {upload.pending ? 'Загрузка…' : 'Загрузить файл'}
          </button>
        </div>

        <p className="field__hint">
          PDF, JPEG или PNG, не больше {formatBytes(MAX_UPLOAD_SIZE_BYTES)}. Формат проверяется
          по содержимому файла, а не по расширению.
        </p>

        {tooLarge && file !== null && (
          <Notice tone="error">
            Файл «{file.name}» — {formatBytes(file.size)}, это больше разрешённого. Выберите
            файл меньшего размера.
          </Notice>
        )}

        {file !== null && !tooLarge && decided && (
          <Notice tone="warning">
            Документ имеет статус «{statusName}»: добавление вложения вернёт его на проверку.
          </Notice>
        )}

        {upload.error !== null && (
          <Notice tone="error">{describeUploadError(upload.error)}</Notice>
        )}
      </form>

      {files.length === 0 ? (
        <p className="muted">Прикреплённых файлов нет</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Имя файла</th>
                <th scope="col">Формат</th>
                <th scope="col">Размер</th>
                <th scope="col">Загружен</th>
                <th scope="col" className="table__action-col">
                  Действие
                </th>
              </tr>
            </thead>
            <tbody>
              {files.map((target) => (
                <Fragment key={target.id}>
                  <tr>
                    <td className="table__filename">{target.original_filename}</td>
                    <td>
                      <span title={target.mime_type}>{labelForMimeType(target.mime_type)}</span>
                    </td>
                    <td className="table__number">{formatBytes(target.size_bytes)}</td>
                    <td className="table__number">{formatDateTime(target.uploaded_at)}</td>
                    <td className="table__action-col">
                      <a
                        className="link"
                        href={attachmentContentUrl(documentId, target.id)}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Скачать
                      </a>
                      <button
                        type="button"
                        className="link link--danger"
                        disabled={deletion.pending}
                        onClick={() => openConfirmation(target.id)}
                      >
                        Удалить
                      </button>
                    </td>
                  </tr>

                  {confirmingId === target.id && (
                    <tr className="table__confirm-row">
                      <td colSpan={5}>
                        <div className="confirm">
                          <p className="confirm__question">
                            Удалить файл «{target.original_filename}»?
                          </p>

                          {decided && (
                            <Notice tone="warning">
                              Документ имеет статус «{statusName}»: удаление вложения вернёт его
                              на проверку.
                            </Notice>
                          )}

                          {deletion.error !== null && (
                            <Notice tone="error">
                              {describeError(deletion.error)} Файл остаётся в списке — можно
                              повторить.
                            </Notice>
                          )}

                          <div className="confirm__actions">
                            <button
                              type="button"
                              className="button button--danger"
                              disabled={deletion.pending}
                              onClick={() => handleDelete(target)}
                            >
                              {deletion.pending ? 'Удаление…' : 'Удалить'}
                            </button>
                            <button
                              type="button"
                              className="button"
                              disabled={deletion.pending}
                              onClick={closeConfirmation}
                            >
                              Отмена
                            </button>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
