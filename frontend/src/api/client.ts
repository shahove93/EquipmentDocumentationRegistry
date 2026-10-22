/**
 * Thin typed wrapper around `fetch` for the relative API URLs the dev server
 * proxies to FastAPI.
 *
 * Three rules shape it. First, a response body is never shown to the user: the
 * backend's error `detail` can echo request data, and a proxy or server failure
 * can echo something worse, so the UI shows its own short message keyed by the
 * status code instead. Second, an aborted request is rethrown untouched — the
 * caller uses the abort to drop stale results, not to report an error. Third,
 * the request keeps one shape for every verb, so the JSON, multipart and
 * body-less calls cannot drift apart in how they treat failures.
 */

export class ApiError extends Error {
  /** HTTP status, or 0 when the request never reached the server. */
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

const NETWORK_MESSAGE =
  'Сервер недоступен. Убедитесь, что backend запущен на 127.0.0.1:8000.'

const STATUS_MESSAGES: Record<number, string> = {
  400: 'Некорректный запрос.',
  404: 'Запись не найдена.',
  409: 'Конфликт: запись уже изменена или занята.',
  413: 'Файл больше допустимого размера.',
  415: 'Такой тип файла не поддерживается.',
  422: 'Данные не приняты сервером. Проверьте заполненные поля.',
  500: 'Ошибка на сервере. Попробуйте позже.',
}

/** True when the request was cancelled rather than failed. */
export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

/** Turn any thrown value into a short, safe message for the interface. */
export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 0) {
      return NETWORK_MESSAGE
    }
    return STATUS_MESSAGES[error.status] ?? `Ошибка запроса (код ${error.status}).`
  }
  return NETWORK_MESSAGE
}

interface RequestOptions {
  method: string
  /** JSON body. Mutually exclusive with `form`. */
  json?: unknown
  /** Multipart body. Mutually exclusive with `json`. */
  form?: FormData
  signal?: AbortSignal
}

async function send(
  path: string,
  init: RequestInit,
  signal: AbortSignal | undefined,
): Promise<Response> {
  try {
    return await fetch(path, { ...init, signal })
  } catch (error) {
    if (isAbortError(error)) {
      throw error
    }
    throw new ApiError(0, 'network')
  }
}

/**
 * Read a successful response, tolerating the verbs that have no body.
 *
 * `DELETE` answers `204`, and a `204` has nothing to parse. Anything that is not
 * JSON is treated the same way rather than being force-parsed, so a proxy or a
 * stub answering an empty body cannot turn a success into a parse exception.
 */
async function readBody<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return undefined as T
  }
  const contentType = response.headers.get('Content-Type') ?? ''
  if (!contentType.includes('json')) {
    return undefined as T
  }
  return (await response.json()) as T
}

/** Issue one request against a relative API path. */
export async function apiRequest<T>(path: string, options: RequestOptions): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  let body: BodyInit | undefined

  if (options.form !== undefined) {
    // The header is deliberately not set: the browser has to add
    // `multipart/form-data` together with the boundary it generated, and a
    // hand-written value would omit that boundary and break the parse.
    body = options.form
  } else if (options.json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.json)
  }

  const response = await send(
    path,
    { method: options.method, headers, body },
    options.signal,
  )
  if (!response.ok) {
    throw new ApiError(response.status, `HTTP ${response.status}`)
  }
  return readBody<T>(response)
}

/** GET `path` and parse the JSON body. `path` must start with `/`. */
export function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  return apiRequest<T>(path, { method: 'GET', signal })
}

export function apiPost<T>(path: string, json: unknown, signal?: AbortSignal): Promise<T> {
  return apiRequest<T>(path, { method: 'POST', json, signal })
}

export function apiPatch<T>(path: string, json: unknown, signal?: AbortSignal): Promise<T> {
  return apiRequest<T>(path, { method: 'PATCH', json, signal })
}

export function apiPut<T>(path: string, json: unknown, signal?: AbortSignal): Promise<T> {
  return apiRequest<T>(path, { method: 'PUT', json, signal })
}

/** POST a multipart body. The `Content-Type` is left to the browser. */
export function apiPostForm<T>(path: string, form: FormData, signal?: AbortSignal): Promise<T> {
  return apiRequest<T>(path, { method: 'POST', form, signal })
}

/** DELETE `path`. The backend answers `204`, so there is no body to return. */
export function apiDelete(path: string, signal?: AbortSignal): Promise<void> {
  return apiRequest<void>(path, { method: 'DELETE', signal })
}
