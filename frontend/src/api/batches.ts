import { apiGet, apiPatch, apiPost } from './client'
import type { BatchCreateBody, BatchRead, BatchUpdateBody } from '../types/api'

export function fetchBatches(limit: number, offset: number, signal?: AbortSignal) {
  return apiGet<BatchRead[]>(`/batches?limit=${limit}&offset=${offset}`, signal)
}
export function fetchBatch(id: number, signal?: AbortSignal) {
  return apiGet<BatchRead>(`/batches/${id}`, signal)
}
export function createBatch(body: BatchCreateBody, signal?: AbortSignal) {
  return apiPost<BatchRead>('/batches', body, signal)
}
export function updateBatch(id: number, body: BatchUpdateBody, signal?: AbortSignal) {
  return apiPatch<BatchRead>(`/batches/${id}`, body, signal)
}
