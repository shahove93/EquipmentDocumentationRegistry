import { useEffect, useMemo, useRef, useState } from 'react'
import { describeError } from '../api/client'
import { createBatch, updateBatch } from '../api/batches'
import { loadAllProductVariants, loadAllProducts } from '../api/references'
import type { BatchCreateBody, BatchRead, ProductRead, ProductVariantRead } from '../types/api'
import { measurementText, productLabel } from '../utils/catalog'

interface Props { batch: BatchRead | null; onSaved: (batch: BatchRead) => void; onCancel: () => void }
export default function BatchForm({ batch, onSaved, onCancel }: Props) {
  const [variants, setVariants] = useState<ProductVariantRead[]>([])
  const [products, setProducts] = useState<ProductRead[]>([])
  const [variantError, setVariantError] = useState<string | null>(null)
  const [variantId, setVariantId] = useState(String(batch?.variant_id ?? ''))
  const [fields, setFields] = useState({ batch_number: batch?.batch_number ?? '', manufacture_date: batch?.manufacture_date ?? '', quantity: batch?.quantity ?? '', quantity_unit: batch?.quantity_unit ?? '' })
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const submission = useRef(0)
  const mounted = useRef(true)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; submission.current += 1 } }, [])
  useEffect(() => {
    const controller = new AbortController()
    loadAllProducts(controller.signal).then(async (result) => {
      if (!controller.signal.aborted) setProducts(result.items)
      const pages = await Promise.all(result.items.map((product) => loadAllProductVariants(product.id, controller.signal)))
      return pages.flatMap((page) => page.items)
    }).then((rows) => { if (!controller.signal.aborted) setVariants(rows) }).catch((reason) => { if (!controller.signal.aborted) setVariantError(describeError(reason)) })
    return () => controller.abort()
  }, [])
  const labels = useMemo(() => {
    const productNames = new Map(products.map((product) => [product.id, productLabel(product)]))
    return new Map(variants.map((item) => [item.id, `${productNames.get(item.product_id) || `Продукт #${item.product_id}`} · ${item.size_text || measurementText(item.diameter)}`]))
  }, [products, variants])
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setError(null)
    const parsed = Number(variantId)
    if (!Number.isInteger(parsed) || parsed <= 0) { setError('Выберите типоразмер.'); return }
    if (fields.manufacture_date && !/^\d{4}-\d{2}-\d{2}$/.test(fields.manufacture_date)) { setError('Укажите корректную дату.'); return }
    const nullable = (value: string) => value === '' ? null : value
    const currentSubmission = ++submission.current
    const isCurrent = () => mounted.current && submission.current === currentSubmission
    setPending(true)
    try {
      let saved: BatchRead
      if (batch) {
        const patch: Record<string, unknown> = {}
        if (parsed !== batch.variant_id) patch.variant_id = parsed
        for (const key of ['batch_number', 'manufacture_date', 'quantity', 'quantity_unit'] as const) {
          const next = nullable(fields[key]); if (next !== batch[key]) patch[key] = next
        }
        saved = Object.keys(patch).length ? await updateBatch(batch.id, patch as Parameters<typeof updateBatch>[1]) : batch
      } else {
        const body: BatchCreateBody = { variant_id: parsed, batch_number: nullable(fields.batch_number), manufacture_date: nullable(fields.manufacture_date), quantity: nullable(fields.quantity), quantity_unit: nullable(fields.quantity_unit) }
        saved = await createBatch(body)
      }
      if (isCurrent()) onSaved(saved)
    } catch (reason) { if (isCurrent()) setError(describeError(reason)) } finally { if (isCurrent()) setPending(false) }
  }
  const invalidateSubmission = () => { submission.current += 1; setPending(false) }
  const updateField = (key: keyof typeof fields, value: string) => { invalidateSubmission(); setFields((current) => ({ ...current, [key]: value })) }
  const updateVariant = (value: string) => { invalidateSubmission(); setVariantId(value) }
  return <form className="batch-form" onSubmit={submit}>
    <label>Типоразмер<select required value={variantId} onChange={(e) => updateVariant(e.target.value)}><option value="">Выберите типоразмер</option>{variants.map((v) => <option key={v.id} value={v.id}>#{v.id} · {labels.get(v.id) || `типоразмер #${v.id}`}</option>)}{batch && !variants.some((v) => v.id === batch.variant_id) && <option value={batch.variant_id}>Типоразмер #{batch.variant_id}</option>}</select></label>
    {variantError && <p className="notice notice--error" role="alert">Список типоразмеров недоступен: {variantError}</p>}
    <label>Номер партии<input value={fields.batch_number} onChange={(e) => updateField('batch_number', e.target.value)} /></label>
    <label>Дата изготовления<input type="date" value={fields.manufacture_date} onChange={(e) => updateField('manufacture_date', e.target.value)} /></label>
    <label>Количество<input inputMode="decimal" value={fields.quantity} onChange={(e) => updateField('quantity', e.target.value)} /></label>
    <label>Единица измерения<input value={fields.quantity_unit} onChange={(e) => updateField('quantity_unit', e.target.value)} /></label>
    {error && <p className="notice notice--error" role="alert">{error}</p>}
    <div className="form-actions"><button className="button button--primary" disabled={pending} type="submit">{pending ? 'Сохранение…' : 'Сохранить'}</button><button className="button" disabled={pending} type="button" onClick={onCancel}>Отмена</button></div>
  </form>
}
