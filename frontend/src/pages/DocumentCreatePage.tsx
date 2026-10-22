import { useEffect, useState, type FormEvent } from 'react'

import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { describeError } from '../api/client'
import { createDocument, replaceDocumentVariants } from '../api/documents'
import {
  createDocumentType,
  createIssuer,
  fetchProduct,
  fetchVariant,
} from '../api/references'
import DocumentRequisitesForm from '../components/DocumentRequisitesForm'
import Notice from '../components/Notice'
import { useReferences } from '../hooks/useReferences'
import { useRequisites } from '../hooks/useRequisites'
import type { DocumentOut, ProductRead, ProductVariantRead } from '../types/api'
import { EMPTY_REQUISITES, hasErrors, toCreateBody, validateRequisites } from '../utils/forms'

/** The variant a link asked this screen to attach, once it is known. */
type PickedVariant =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; variant: ProductVariantRead; product: ProductRead | null }
  | { status: 'error' }

/**
 * The create screen, at `/documents/new`.
 *
 * Two required members and a handful of optional ones, sent as they were filled
 * in: a field the user left alone is left out of the body, so the column keeps
 * its own default rather than being handed a `null` nobody asked for.
 *
 * A document is created once. The submit handler goes through `useSubmit`, whose
 * guard is set synchronously, so a second click in the same tick is refused
 * before it can issue a second `POST` — the same guard disables the button for
 * everything slower. On success the screen leaves for the new card; the body is
 * never resubmitted from here.
 *
 * The screen can also be reached from the catalog with `?variant_id=N`, which is
 * the other direction of the same relation: start from a size, create the
 * certificate, then link it. Creating and linking are two HTTP operations, so
 * they are handled as such — if the document is stored but the link fails, the
 * screen says so, keeps the document, offers a retry and never creates a second
 * one. The form is replaced by that outcome rather than left on screen, so
 * pressing «Сохранить» again is not even possible.
 *
 * Reference rows are created through their own explicit forms. A type the user
 * needs is created first, selected immediately, and the document then refers to
 * it by id like any other.
 */
export default function DocumentCreatePage() {
  const navigate = useNavigate()
  const { values, errors, change, setErrors, submission } = useRequisites(EMPTY_REQUISITES)
  const references = useReferences()

  const [searchParams] = useSearchParams()
  const rawVariantId = searchParams.get('variant_id')
  const variantId =
    rawVariantId !== null && /^\d+$/.test(rawVariantId) && Number(rawVariantId) > 0
      ? Number(rawVariantId)
      : null
  const invalidVariantParam = rawVariantId !== null && variantId === null

  const [picked, setPicked] = useState<PickedVariant>({ status: 'idle' })

  // What exists after a successful POST, kept only for the case where the link
  // could not be written.
  const [created, setCreated] = useState<DocumentOut | null>(null)
  const [linkError, setLinkError] = useState<unknown>(null)
  const [linking, setLinking] = useState(false)

  useEffect(() => {
    if (variantId === null) {
      setPicked({ status: 'idle' })
      return undefined
    }
    const controller = new AbortController()
    setPicked({ status: 'loading' })
    void (async () => {
      try {
        const variant = await fetchVariant(variantId, controller.signal)
        let product: ProductRead | null = null
        try {
          product = await fetchProduct(variant.product_id, controller.signal)
        } catch {
          // The name is a nicety; the variant itself is what gets linked.
          product = null
        }
        if (!controller.signal.aborted) {
          setPicked({ status: 'ready', variant, product })
        }
      } catch {
        if (!controller.signal.aborted) {
          setPicked({ status: 'error' })
        }
      }
    })()
    return () => controller.abort()
  }, [variantId])

  const handleCreateDocumentType = async (name: string) => {
    const created = await createDocumentType(name)
    references.addDocumentType(created)
    change({ documentTypeId: String(created.id) })
  }

  const handleCreateIssuer = async (name: string) => {
    const created = await createIssuer(name)
    references.addIssuer(created)
    change({ issuerId: String(created.id) })
  }

  // A variant the screen could not read is not worth a doomed `PUT`: the link is
  // skipped and the warning already says the document is created without it.
  const linkVariantId = picked.status === 'error' ? null : variantId

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const validation = validateRequisites(values)
    setErrors(validation)
    if (hasErrors(validation)) {
      return
    }
    const body = toCreateBody(values)
    if (body === null) {
      // Unreachable: the validation above refuses a missing type. Kept as a
      // guard so the form can never send a body the schema would reject.
      return
    }
    await submission.run(async () => {
      const stored = await createDocument(body)
      if (linkVariantId === null) {
        navigate(`/documents/${stored.id}`)
        return
      }
      try {
        await replaceDocumentVariants(stored.id, [linkVariantId])
        navigate(`/documents/${stored.id}`)
      } catch (error: unknown) {
        // The document exists now. Saying otherwise and letting the form run
        // again is the one thing that must not happen here.
        setCreated(stored)
        setLinkError(error)
      }
    })
  }

  const retryLink = async () => {
    if (created === null || linkVariantId === null) {
      return
    }
    setLinking(true)
    setLinkError(null)
    try {
      await replaceDocumentVariants(created.id, [linkVariantId])
      navigate(`/documents/${created.id}`)
    } catch (error: unknown) {
      setLinkError(error)
    } finally {
      setLinking(false)
    }
  }

  return (
    <div className="page">
      <Link className="link backlink" to="/">
        ← Вернуться в реестр
      </Link>

      <header className="page__header">
        <div>
          <h1 className="page__title">Новый документ</h1>
          <p className="page__subtitle">
            Тип и номер обязательны. Вложения и типоразмеры привязываются уже в карточке.
          </p>
        </div>
      </header>

      {created !== null ? (
        <section className="panel panel--form">
          <h2 className="section-title">Документ создан</h2>
          <p>
            Документ{' '}
            <Link className="link" to={`/documents/${created.id}`}>
              №{created.number}
            </Link>{' '}
            сохранён. Привязать к нему типоразмер не удалось.
          </p>

          <Notice tone="error">{describeError(linkError)}</Notice>

          <p className="field__hint">
            Документ уже существует — повторная отправка формы создала бы второй, поэтому
            форма закрыта. Привязку можно повторить здесь или в карточке документа.
          </p>

          <div className="form__actions">
            <button
              type="button"
              className="button button--primary"
              disabled={linking}
              onClick={() => void retryLink()}
            >
              {linking ? 'Привязка…' : 'Повторить привязку'}
            </button>
            <Link className="button" to={`/documents/${created.id}`}>
              Открыть карточку
            </Link>
          </div>
        </section>
      ) : (
        <section className="panel panel--form">
          <form className="form" onSubmit={handleSubmit} noValidate>
            {invalidVariantParam && (
              <Notice tone="warning">
                В ссылке указан некорректный идентификатор типоразмера. Документ будет создан
                без привязки.
              </Notice>
            )}

            {variantId !== null && (
              <div className="picked">
                {picked.status === 'loading' && (
                  <p className="muted" role="status">
                    Загрузка типоразмера…
                  </p>
                )}
                {picked.status === 'ready' && (
                  <p>
                    Документ будет привязан к типоразмеру{' '}
                    <strong>{picked.variant.size_text}</strong>
                    {picked.product !== null && <> изделия «{picked.product.name}»</>}
                    {picked.product !== null && (
                      <span className="muted"> · {picked.product.standard}</span>
                    )}
                    .
                  </p>
                )}
                {picked.status === 'error' && (
                  <Notice tone="warning">
                    Типоразмер из ссылки не найден. Документ будет создан без привязки —
                    привязать его можно в карточке.
                  </Notice>
                )}
              </div>
            )}

            <DocumentRequisitesForm
              idPrefix="create"
              values={values}
              errors={errors}
              disabled={submission.pending}
              documentTypes={references.documentTypes}
              documentTypesLoaded={references.documentTypesLoaded}
              documentTypesTruncated={references.documentTypesTruncated}
              issuers={references.issuers}
              issuersTruncated={references.issuersTruncated}
              onChange={change}
              onCreateDocumentType={handleCreateDocumentType}
              onCreateIssuer={handleCreateIssuer}
            />

            {references.documentTypesFailed && (
              <Notice tone="error">
                Не удалось загрузить справочник типов документов. Можно создать новый тип — он
                появится в списке сразу.
              </Notice>
            )}
            {references.issuersFailed && (
              <Notice tone="error">
                Не удалось загрузить справочник организаций, выдавших документы. Организацию
                можно создать отдельно или оставить поле пустым.
              </Notice>
            )}

            {submission.error !== null && (
              <Notice tone="error">{describeError(submission.error)}</Notice>
            )}

            <div className="form__actions">
              <button
                type="submit"
                className="button button--primary"
                disabled={submission.pending}
              >
                Сохранить документ
              </button>
              <Link className="button" to="/">
                Отмена
              </Link>
            </div>

            <p className="field__hint">
              После сохранения откроется карточка документа: там прикрепляют скан и выбирают
              типоразмеры.
            </p>
          </form>
        </section>
      )}
    </div>
  )
}
