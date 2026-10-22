import type {
  ProductCreateBody,
  ProductRead,
  ProductVariantCreateBody,
} from '../types/api'

/**
 * The catalog forms, and the rules for turning them into requests.
 *
 * Everything here mirrors a bound the backend actually enforces, and nothing
 * here invents a rule of its own. The measurements are the delicate part:
 * `product_variants` has `NUMERIC(10, 2)` columns and the API refuses a value it
 * would have to round instead of silently storing an approximation, so the form
 * checks the same shape before sending — and still lets the server be the
 * authority, because a `422` is reported rather than argued with.
 *
 * A measurement is optional. Optional is not the same as zero: a blank field
 * stays blank and the column keeps `NULL`, which is why `size_text` — not a
 * numeric diameter — remains the identity of a variant (ADR-006).
 */

/** `Product.name` / `Product.standard` / `Product.designation` are VARCHAR(255). */
export const PRODUCT_TEXT_MAX_LENGTH = 255

/** `Product.product_type` is VARCHAR(100). */
export const PRODUCT_TYPE_MAX_LENGTH = 100

/** `ProductVariant.size_text` is VARCHAR(100). */
export const SIZE_TEXT_MAX_LENGTH = 100

/** `NUMERIC(10, 2)`: eight digits before the point, two after it. */
export const MEASUREMENT_MAX = 99999999.99

// --- product ----------------------------------------------------------------

/** The product form as bound to inputs. `''` means "not filled in". */
export interface ProductFormValues {
  name: string
  standard: string
  /** The string value of the manufacturer `<select>`; `''` is "nothing chosen". */
  manufacturerId: string
  designation: string
  productType: string
}

export const EMPTY_PRODUCT: ProductFormValues = {
  name: '',
  standard: '',
  manufacturerId: '',
  designation: '',
  productType: '',
}

export interface ProductFormErrors {
  name?: string
  standard?: string
  manufacturerId?: string
}

/**
 * The two required members and the manufacturer.
 *
 * `standard` is required by `ProductCreate`, so the form asks for it instead of
 * inventing a value: a product without a ГОСТ/ТУ cannot be stored, and a
 * placeholder would have to be corrected later by whoever trusts the record.
 */
export function validateProduct(values: ProductFormValues): ProductFormErrors {
  const errors: ProductFormErrors = {}
  if (values.name.trim() === '') {
    errors.name = 'Укажите название изделия.'
  }
  if (values.standard.trim() === '') {
    errors.standard = 'Укажите ГОСТ/ТУ изделия.'
  }
  if (values.manufacturerId === '') {
    errors.manufacturerId = 'Выберите производителя изделия.'
  }
  return errors
}

/**
 * The body, or `null` when a required value is missing.
 *
 * Optional members are omitted rather than sent as `null`: an absent key lets
 * the column keep its default, while an explicit `null` would be a statement the
 * user never made. The strings are trimmed because the schema strips them
 * anyway, and a name made of spaces must not look filled in.
 */
export function toProductBody(values: ProductFormValues): ProductCreateBody | null {
  const name = values.name.trim()
  const standard = values.standard.trim()
  const manufacturerId = values.manufacturerId === '' ? null : Number(values.manufacturerId)
  if (name === '' || standard === '' || manufacturerId === null) {
    return null
  }

  const body: ProductCreateBody = {
    name,
    standard,
    manufacturer_id: manufacturerId,
  }
  const designation = values.designation.trim()
  if (designation !== '') {
    body.designation = designation
  }
  const productType = values.productType.trim()
  if (productType !== '') {
    body.product_type = productType
  }
  return body
}

/** The product as one label: its name, and the standard it is made to. */
export function productLabel(product: ProductRead): string {
  return [product.name, product.standard].filter((part) => part !== '').join(' · ')
}

// --- variant ----------------------------------------------------------------

/** The variant form as bound to inputs. */
export interface VariantFormValues {
  sizeText: string
  diameter: string
  nominalDiameter: string
  wallThickness: string
}

export const EMPTY_VARIANT: VariantFormValues = {
  sizeText: '',
  diameter: '',
  nominalDiameter: '',
  wallThickness: '',
}

export interface VariantFormErrors {
  sizeText?: string
  diameter?: string
  nominalDiameter?: string
  wallThickness?: string
}

export interface MeasurementResult {
  /** The number to send, or `null` for a field left blank. */
  value: number | null
  /** Set when the text is not a usable measurement. */
  error?: string
}

/**
 * Read one measurement the way a person types it.
 *
 * A comma is accepted as the decimal separator alongside the point, because that
 * is how the same number is written in Russian and refusing it would be a
 * spelling test rather than a validation. Anything else that is not a plain
 * positive number with at most two decimal places is refused here — precisely
 * the shapes the API would answer `422` for — and the message says what to type
 * instead of quoting the column type.
 */
export function parseMeasurement(raw: string): MeasurementResult {
  const trimmed = raw.trim()
  if (trimmed === '') {
    return { value: null }
  }
  const normalised = trimmed.replace(',', '.')
  if (!/^\d+(\.\d{1,2})?$/.test(normalised)) {
    return {
      value: null,
      error: 'Введите положительное число не более чем с двумя знаками после запятой, например 63 или 5,8.',
    }
  }
  const value = Number(normalised)
  if (!Number.isFinite(value) || value <= 0) {
    return { value: null, error: 'Значение должно быть больше нуля.' }
  }
  if (value > MEASUREMENT_MAX) {
    return { value: null, error: 'Значение слишком велико для этой колонки.' }
  }
  return { value }
}

export function validateVariant(values: VariantFormValues): VariantFormErrors {
  const errors: VariantFormErrors = {}
  if (values.sizeText.trim() === '') {
    errors.sizeText = 'Укажите обозначение типоразмера.'
  }
  const diameter = parseMeasurement(values.diameter)
  if (diameter.error !== undefined) {
    errors.diameter = diameter.error
  }
  const nominal = parseMeasurement(values.nominalDiameter)
  if (nominal.error !== undefined) {
    errors.nominalDiameter = nominal.error
  }
  const wall = parseMeasurement(values.wallThickness)
  if (wall.error !== undefined) {
    errors.wallThickness = wall.error
  }
  return errors
}

export function hasVariantErrors(errors: VariantFormErrors): boolean {
  return Object.keys(errors).length > 0
}

/**
 * The body, or `null` when the form cannot be sent as it stands.
 *
 * `size_text` is trimmed because it is the identity of the variant: two rows
 * that differ only in padding would be a duplicate the user did not mean to
 * create. A blank measurement is left out entirely rather than sent as `0`,
 * which would be a different claim about the size.
 */
export function toVariantBody(values: VariantFormValues): ProductVariantCreateBody | null {
  const sizeText = values.sizeText.trim()
  if (sizeText === '') {
    return null
  }
  const diameter = parseMeasurement(values.diameter)
  const nominal = parseMeasurement(values.nominalDiameter)
  const wall = parseMeasurement(values.wallThickness)
  if (diameter.error !== undefined || nominal.error !== undefined || wall.error !== undefined) {
    return null
  }

  const body: ProductVariantCreateBody = { size_text: sizeText }
  if (diameter.value !== null) {
    body.diameter = diameter.value
  }
  if (nominal.value !== null) {
    body.nominal_diameter = nominal.value
  }
  if (wall.value !== null) {
    body.wall_thickness = wall.value
  }
  return body
}

/**
 * A stored measurement for display.
 *
 * The API answers with a decimal rendered as text ("63.00"), so the trailing
 * zeros of the column scale are dropped for reading. The stored value is not
 * reformatted any further — no rounding, no unit appended — because the cell is
 * a view of the column, and a null has no text at all rather than a zero.
 */
export function measurementText(value: string | number | null): string {
  if (value === null) {
    return ''
  }
  const text = String(value)
  if (!text.includes('.')) {
    return text
  }
  return text.replace(/0+$/, '').replace(/\.$/, '')
}
