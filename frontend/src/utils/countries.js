import countries from 'i18n-iso-countries'
import enLocale from 'i18n-iso-countries/langs/en.json'

countries.registerLocale(enLocale)

export const isoCodeToAlpha2 = (code = '') => {
  const normalized = code.trim().toUpperCase()
  if (!normalized) return ''
  if (normalized.length === 2) {
    return normalized
  }
  return countries.alpha3ToAlpha2(normalized) || ''
}

export const getCountryName = (code = '') => {
  const alpha2 = isoCodeToAlpha2(code)
  if (!alpha2) return ''
  return countries.getName(alpha2, 'en') || ''
}

export const getCountryFlag = (code = '') => {
  const alpha2 = isoCodeToAlpha2(code)
  if (!alpha2) return ''
  const base = 0x1f1e6
  return String.fromCodePoint(
    ...alpha2.split('').map((char) => base + char.charCodeAt(0) - 65),
  )
}
