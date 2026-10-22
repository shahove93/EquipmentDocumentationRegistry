import { useCallback, useEffect, useState } from 'react'

import { loadAllDocumentTypes, loadAllIssuers } from '../api/references'
import type { DocumentTypeRead, IssuerRead } from '../types/api'

export interface ReferenceLists {
  documentTypes: DocumentTypeRead[]
  /**
   * True once the type list has been asked for, whether or not it answered.
   * The create form uses it to tell "the reference is empty" — which it can
   * fill — apart from "the reference has not been read yet".
   */
  documentTypesLoaded: boolean
  documentTypesTruncated: boolean
  documentTypesFailed: boolean
  issuers: IssuerRead[]
  issuersTruncated: boolean
  issuersFailed: boolean
  /** Record a row created from this form, so it becomes selectable at once. */
  addDocumentType: (type: DocumentTypeRead) => void
  addIssuer: (issuer: IssuerRead) => void
}

/**
 * The two reference lists a document form needs.
 *
 * Both are read completely, in pages, so a type on the second page is still
 * selectable; a list that was cut short by the page cap says so instead of
 * passing a prefix off as the whole reference.
 *
 * A failure is not fatal and is not thrown: the form can still be filled in, a
 * missing reference can still be created, and the stored foreign key is still
 * shown as itself. The two requests settle independently, so an unreachable
 * issuer list does not take the type list down with it.
 */
export function useReferences(): ReferenceLists {
  const [documentTypes, setDocumentTypes] = useState<DocumentTypeRead[]>([])
  const [issuers, setIssuers] = useState<IssuerRead[]>([])
  const [documentTypesLoaded, setDocumentTypesLoaded] = useState(false)
  const [documentTypesTruncated, setDocumentTypesTruncated] = useState(false)
  const [documentTypesFailed, setDocumentTypesFailed] = useState(false)
  const [issuersTruncated, setIssuersTruncated] = useState(false)
  const [issuersFailed, setIssuersFailed] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    Promise.allSettled([
      loadAllDocumentTypes(controller.signal),
      loadAllIssuers(controller.signal),
    ]).then(([typesResult, issuersResult]) => {
      if (controller.signal.aborted) {
        return
      }
      if (typesResult.status === 'fulfilled') {
        setDocumentTypes(typesResult.value.items)
        setDocumentTypesTruncated(typesResult.value.truncated)
      } else {
        setDocumentTypesFailed(true)
      }
      setDocumentTypesLoaded(true)

      if (issuersResult.status === 'fulfilled') {
        setIssuers(issuersResult.value.items)
        setIssuersTruncated(issuersResult.value.truncated)
      } else {
        setIssuersFailed(true)
      }
    })
    return () => controller.abort()
  }, [])

  const addDocumentType = useCallback((type: DocumentTypeRead) => {
    setDocumentTypes((current) =>
      current.some((row) => row.id === type.id) ? current : [...current, type],
    )
    setDocumentTypesFailed(false)
    setDocumentTypesLoaded(true)
  }, [])

  const addIssuer = useCallback((issuer: IssuerRead) => {
    setIssuers((current) =>
      current.some((row) => row.id === issuer.id) ? current : [...current, issuer],
    )
    setIssuersFailed(false)
  }, [])

  return {
    documentTypes,
    documentTypesLoaded,
    documentTypesTruncated,
    documentTypesFailed,
    issuers,
    issuersTruncated,
    issuersFailed,
    addDocumentType,
    addIssuer,
  }
}
