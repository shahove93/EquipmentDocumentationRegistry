import type { FormEvent } from 'react'

import type { ManufacturerRead } from '../types/api'

/**
 * Filter fields as raw strings, because they are bound to text and select
 * inputs. `manufacturerId` is the string value of the `<select>`: `''` means
 * "any" and is not the same as `0` or an absent id. Conversion to typed query
 * parameters happens when the search is applied.
 */
export interface FilterValues {
  number: string
  material: string
  size_text: string
  standard: string
  manufacturerId: string
  status: string
}

export const EMPTY_FILTERS: FilterValues = {
  number: '',
  material: '',
  size_text: '',
  standard: '',
  manufacturerId: '',
  status: '',
}

interface DocumentFiltersProps {
  value: FilterValues
  manufacturers: ManufacturerRead[]
  onChange: (value: FilterValues) => void
  onSubmit: () => void
  onReset: () => void
}

/**
 * Search form for the registry.
 *
 * It is controlled and does not search as you type: a request goes out on
 * submit only, so the backend is not queried on every keystroke of a Cyrillic
 * word. Pressing Enter in any text field submits the form.
 */
export default function DocumentFilters({
  value,
  manufacturers,
  onChange,
  onSubmit,
  onReset,
}: DocumentFiltersProps) {
  const setField = (patch: Partial<FilterValues>) => {
    onChange({ ...value, ...patch })
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    onSubmit()
  }

  return (
    <form className="filters" onSubmit={handleSubmit} role="search">
      <div className="filters__grid">
        <label className="field">
          <span className="field__label">Номер документа</span>
          <input
            className="field__input"
            type="search"
            value={value.number}
            placeholder="Например, CERT-2026-063"
            onChange={(event) => setField({ number: event.target.value })}
          />
        </label>

        <label className="field">
          <span className="field__label">Материал (название изделия)</span>
          <input
            className="field__input"
            type="text"
            value={value.material}
            placeholder="Например, Труба ПЭ100"
            onChange={(event) => setField({ material: event.target.value })}
          />
        </label>

        <label className="field">
          <span className="field__label">Типоразмер</span>
          <input
            className="field__input"
            type="text"
            value={value.size_text}
            placeholder="Например, Ø63"
            aria-describedby="filter-size-hint"
            onChange={(event) => setField({ size_text: event.target.value })}
          />
          <span className="field__hint" id="filter-size-hint">
            Совпадение точное: «Ø63» и «Ø 63» — разные значения.
          </span>
        </label>

        <label className="field">
          <span className="field__label">ГОСТ / ТУ</span>
          <input
            className="field__input"
            type="text"
            value={value.standard}
            placeholder="Например, ГОСТ 58121.2"
            onChange={(event) => setField({ standard: event.target.value })}
          />
        </label>

        <label className="field">
          <span className="field__label">Производитель</span>
          <select
            className="field__input"
            value={value.manufacturerId}
            onChange={(event) => setField({ manufacturerId: event.target.value })}
          >
            <option value="">Все производители</option>
            {manufacturers.map((manufacturer) => (
              <option key={manufacturer.id} value={String(manufacturer.id)}>
                {manufacturer.name}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span className="field__label">Статус проверки</span>
          <select
            className="field__input"
            value={value.status}
            onChange={(event) => setField({ status: event.target.value })}
          >
            <option value="">Любой статус</option>
            <option value="pending">На проверке</option>
            <option value="verified">Подтверждён</option>
            <option value="rejected">Отклонён</option>
          </select>
        </label>
      </div>

      <div className="filters__actions">
        <button type="submit" className="button button--primary">
          Найти
        </button>
        <button type="button" className="button" onClick={onReset}>
          Сбросить
        </button>
      </div>
    </form>
  )
}
