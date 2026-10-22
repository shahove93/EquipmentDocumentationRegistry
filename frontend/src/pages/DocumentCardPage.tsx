import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ApiError, describeError } from '../api/client'
import {
  fetchDocument,
  fetchDocumentFiles,
  fetchDocumentVariants,
  fetchVerificationHistory,
} from '../api/documents'
import { fetchDocumentType, fetchIssuer } from '../api/references'
import AsyncBlock from '../components/AsyncBlock'
import ConfirmDecision from '../components/ConfirmDecision'
import DocumentAttachments from '../components/DocumentAttachments'
import DocumentDetails from '../components/DocumentDetails'
import DocumentEditForm from '../components/DocumentEditForm'
import DocumentVariants from '../components/DocumentVariants'
import DocumentVerdictPanel from '../components/DocumentVerdictPanel'
import Notice from '../components/Notice'
import StatusBadge from '../components/StatusBadge'
import VerificationHistory from '../components/VerificationHistory'
import { useSection } from '../hooks/useSection'
import type { DocumentOut } from '../types/api'
import { labelForStatus } from '../utils/labels'

/**
 * Read the id out of the address, or say that there is not one.
 *
 * `/documents/<anything>` is also a client-side route, so the parameter is
 * whatever was typed or pasted. A parameter that is not a positive integer
 * cannot name a document, and asking the server about it would only produce a
 * validation error, so it is rejected here instead. `idle` sections keep a
 * malformed address from looking like a request in flight.
 */
function parseDocumentId(raw: string | undefined): number | null {
  if (raw === undefined || !/^\d+$/.test(raw)) {
    return null
  }
  const parsed = Number(raw)
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null
}

function isNotFound(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404
}

/**
 * The document card, at `/documents/:id`.
 *
 * Four reads run in parallel and each owns its state: the document itself, its
 * variants, its attachments and its history. Only the first one gates the
 * screen — until it answers there is nothing to label the rest with — while a
 * failure in any of the other three is confined to its own region. That is what
 * keeps a broken history request from hiding requisites that did load.
 *
 * Every read is abortable and keyed by the id in the address, so switching
 * documents quickly cannot leave one document's rows under another's heading:
 * a reply for an id that is no longer current is dropped instead of stored.
 *
 * The three writes below take the opposite approach on purpose: they are not
 * abortable. A cancelled request would still have reached the server, and the
 * screen would have no way to know whether the document was changed. So a write
 * is followed by the reads it invalidated, and the reload is what makes the card
 * show the server's state rather than the click's.
 */
export default function DocumentCardPage() {
  const { id } = useParams<{ id: string }>()
  const documentId = parseDocumentId(id)

  const [documentState, reloadDocument] = useSection(documentId, fetchDocument)
  const [variantsState, reloadVariants] = useSection(documentId, fetchDocumentVariants)
  const [filesState, reloadFiles] = useSection(documentId, fetchDocumentFiles)
  const [historyState, reloadHistory] = useSection(documentId, fetchVerificationHistory)

  const [editing, setEditing] = useState(false)
  // Which decision is being taken. Confirming is a compact confirmation next to
  // its own button; rejecting needs a reason and therefore its own panel.
  const [decision, setDecision] = useState<'confirm' | 'reject' | null>(null)

  // Where focus goes back to. A confirmation is opened from a button that is
  // still on screen when it is cancelled, so cancelling must return the focus
  // there rather than dropping it on the document body.
  const verifyButtonRef = useRef<HTMLButtonElement>(null)
  const rejectButtonRef = useRef<HTMLButtonElement>(null)
  const noticeRef = useRef<HTMLDivElement>(null)
  // What the last accepted decision produced, as the server described it. It is
  // a confirmation of a finished act, so it is dropped as soon as another act
  // begins rather than lingering over a document it no longer describes.
  const [decisionNotice, setDecisionNotice] = useState<string | null>(null)

  // `/documents/1` and `/documents/2` are the same route, so the element is
  // reused and the open form or decision panel would otherwise survive into
  // another document — where it would be recording a verdict on the wrong row.
  useEffect(() => {
    setEditing(false)
    setDecision(null)
    setDecisionNotice(null)
  }, [documentId])

  const document = documentState.status === 'ready' ? documentState.data : null

  // What the card knows about the attachments, for the confirmation's warning.
  // `null` means "unknown" — still loading, or the block failed — and is kept
  // apart from "zero", because only a real zero is worth warning about.
  const fileCount = filesState.status === 'ready' ? filesState.data.length : null

  // Reference names for the two foreign keys the document carries. Resolving
  // them is a nicety, not a requirement: a failure leaves the cell showing the
  // stored id. The effect depends on the document value, so the names are
  // cleared as soon as the document changes and cannot outlive it.
  const [typeName, setTypeName] = useState<string | null>(null)
  const [issuerName, setIssuerName] = useState<string | null>(null)

  useEffect(() => {
    if (document === null) {
      setTypeName(null)
      setIssuerName(null)
      return
    }
    const controller = new AbortController()
    fetchDocumentType(document.document_type_id, controller.signal)
      .then((type) => {
        if (!controller.signal.aborted) setTypeName(type.name)
      })
      .catch(() => {
        if (!controller.signal.aborted) setTypeName(null)
      })
    if (document.issuer_id !== null) {
      fetchIssuer(document.issuer_id, controller.signal)
        .then((issuer) => {
          if (!controller.signal.aborted) setIssuerName(issuer.name)
        })
        .catch(() => {
          if (!controller.signal.aborted) setIssuerName(null)
        })
    } else {
      setIssuerName(null)
    }
    return () => controller.abort()
  }, [document])

  // A requisites patch can change the status as well as the fields, and a
  // verdict changes the status outright. Both add an event, so the history is
  // stale too. Neither touches the attachments or the links, so those blocks
  // are left alone rather than reloaded for nothing.
  const refreshAfterDocumentChange = useCallback(() => {
    reloadDocument()
    reloadHistory()
  }, [reloadDocument, reloadHistory])

  // Adding or removing a file can also move the status, and always adds an
  // event when it does.
  const refreshAfterAttachmentChange = useCallback(() => {
    setDecisionNotice(null)
    reloadFiles()
    reloadDocument()
    reloadHistory()
  }, [reloadFiles, reloadDocument, reloadHistory])

  // The decision itself. The wording comes from the document the server
  // returned, not from the button that was pressed: a repeated rejection is
  // accepted with the status unchanged and nothing added to the history, and
  // saying "rejected" as though it were news would misreport that.
  const handleDecided = useCallback(
    (stored: DocumentOut) => {
      setDecisionNotice(
        `Готово. Текущий статус документа: «${labelForStatus(
          stored.verification_status,
        )}». История проверок обновлена.`,
      )
      refreshAfterDocumentChange()
    },
    [refreshAfterDocumentChange],
  )

  // A finished decision leaves the button that started it disabled or gone, so
  // the outcome takes the focus instead: the next thing a keyboard user needs to
  // read is what the server stored.
  useEffect(() => {
    if (decisionNotice !== null) {
      noticeRef.current?.focus()
    }
  }, [decisionNotice])

  const openDecision = (next: 'confirm' | 'reject') => {
    setDecisionNotice(null)
    setDecision(next)
  }

  const closeDecision = (returnTo: 'confirm' | 'reject' | null) => {
    setDecision(null)
    if (returnTo === 'confirm') {
      verifyButtonRef.current?.focus()
    } else if (returnTo === 'reject') {
      rejectButtonRef.current?.focus()
    }
  }

  const startEditing = () => {
    setDecisionNotice(null)
    setEditing(true)
  }

  const backToRegistry = (
    <Link className="link backlink" to="/">
      ← Вернуться в реестр
    </Link>
  )

  // Nothing was requested, so there is nothing to report as loading or failed.
  if (documentId === null) {
    return (
      <div className="page">
        {backToRegistry}
        <h1 className="page__title">Документ не найден</h1>
        <section className="panel">
          <div className="state">
            <p>В адресе указан некорректный идентификатор документа.</p>
            <p className="muted">Откройте документ из реестра или проверьте ссылку.</p>
          </div>
        </section>
      </div>
    )
  }

  return (
    <div className="page">
      {backToRegistry}

      {documentState.status === 'loading' && (
        <section className="panel">
          <div className="state state--loading" role="status">
            Загрузка документа…
          </div>
        </section>
      )}

      {documentState.status === 'error' && isNotFound(documentState.error) && (
        <section className="panel">
          <div className="state">
            <p>Документ не найден.</p>
            <p className="muted">Возможно, он был удалён или ссылка указана неверно.</p>
          </div>
        </section>
      )}

      {documentState.status === 'error' && !isNotFound(documentState.error) && (
        <section className="panel">
          <div className="state state--error" role="alert">
            <p>{describeError(documentState.error)}</p>
            <button type="button" className="button" onClick={reloadDocument}>
              Повторить
            </button>
          </div>
        </section>
      )}

      {document !== null && (
        <>
          <header className="page__header">
            <div>
              <h1 className="page__title">Документ {document.number}</h1>
              <p className="page__subtitle">
                {typeName ?? `Тип №${document.document_type_id}`}
                <span className="muted"> · запись №{document.id}</span>
              </p>
            </div>
            <div className="page__header-actions">
              <StatusBadge status={document.verification_status} />
              <button
                type="button"
                className="button"
                disabled={editing || decision !== null}
                onClick={startEditing}
              >
                Изменить
              </button>

              {/* A confirmed document cannot be confirmed again — the server
                  would answer `200` without recording anything — so the action
                  is shown as a state instead of a button that does nothing. */}
              {document.verification_status === 'verified' ? (
                <button
                  type="button"
                  className="button"
                  disabled
                  title="Документ уже подтверждён"
                >
                  Подтверждён
                </button>
              ) : (
                <button
                  ref={verifyButtonRef}
                  type="button"
                  className="button button--primary"
                  disabled={editing || decision !== null}
                  aria-expanded={decision === 'confirm'}
                  onClick={() => openDecision('confirm')}
                >
                  Подтвердить
                </button>
              )}

              <button
                ref={rejectButtonRef}
                type="button"
                className="button"
                disabled={editing || decision !== null}
                aria-expanded={decision === 'reject'}
                onClick={() => openDecision('reject')}
              >
                Отклонить
              </button>

              {/* The second step of a confirmation stays in the action zone it
                  belongs to, directly under the button that opened it, instead
                  of moving the final button to another part of the page. */}
              {decision === 'confirm' && (
                <ConfirmDecision
                  documentId={document.id}
                  documentNumber={document.number}
                  fileCount={fileCount}
                  onDecided={handleDecided}
                  onClose={() => closeDecision('confirm')}
                />
              )}
            </div>
          </header>

          {decisionNotice !== null && (
            <div className="verdict-result" role="status" tabIndex={-1} ref={noticeRef}>
              <Notice tone="success">{decisionNotice}</Notice>
            </div>
          )}

          {/* A rejection needs a reason and a warning or two, so it keeps its own
              panel between the header and the card — the compact shape that suits
              a two-button confirmation would not hold a textarea and its errors. */}
          {decision === 'reject' && (
            <section className="panel panel--verdict">
              <DocumentVerdictPanel
                document={document}
                onDecided={handleDecided}
                onClose={() => closeDecision('reject')}
              />
            </section>
          )}

          <div className="card">
            <section className="card__section">
              <h2 className="section-title">Реквизиты</h2>
              {editing ? (
                <DocumentEditForm
                  document={document}
                  onSaved={refreshAfterDocumentChange}
                  onCancel={() => setEditing(false)}
                />
              ) : (
                <DocumentDetails
                  document={document}
                  typeName={typeName}
                  issuerName={issuerName}
                />
              )}
            </section>

            <AsyncBlock title="Типоразмеры" state={variantsState} onRetry={reloadVariants}>
              {(variants) => (
                <DocumentVariants
                  key={documentId}
                  documentId={documentId}
                  variants={variants}
                  onChanged={reloadVariants}
                />
              )}
            </AsyncBlock>

            <AsyncBlock title="Вложения" state={filesState} onRetry={reloadFiles}>
              {(files) => (
                <DocumentAttachments
                  key={documentId}
                  documentId={documentId}
                  files={files}
                  verificationStatus={document.verification_status}
                  onChanged={refreshAfterAttachmentChange}
                />
              )}
            </AsyncBlock>

            <AsyncBlock title="История проверок" state={historyState} onRetry={reloadHistory}>
              {(events) =>
                events.length === 0 ? (
                  <p className="muted">История проверок пока пуста</p>
                ) : (
                  <VerificationHistory events={events} />
                )
              }
            </AsyncBlock>
          </div>
        </>
      )}
    </div>
  )
}
