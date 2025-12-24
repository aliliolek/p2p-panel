const DATE_FORMAT = {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
}

const MS_IN_DAY = 24 * 60 * 60 * 1000

const toNumber = (value) => {
  if (typeof value === 'number') {
    return value
  }
  if (typeof value === 'string') {
    const parsed = Number(value)
    return Number.isNaN(parsed) ? null : parsed
  }
  return null
}

export const formatNumber = (value, fractionDigits = 2) => {
  const numeric = toNumber(value)
  if (numeric == null) {
    return '-'
  }
  return numeric.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: fractionDigits,
  })
}

export const formatDateTime = (value) => {
  if (!value) return '-'
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return new Intl.DateTimeFormat('uk-UA', DATE_FORMAT).format(date)
}

export const formatRelativeDays = (timestamp) => {
  if (timestamp == null) return '-'
  const numeric = toNumber(timestamp)
  if (numeric == null) return '-'
  const normalized = numeric > 10 ** 12 ? numeric : numeric * 1000
  const diff = Math.floor((Date.now() - normalized) / MS_IN_DAY)
  if (!Number.isFinite(diff) || diff < 0) return '-'
  return `${diff}d`
}
