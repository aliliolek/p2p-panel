export const getSideColor = (side) => {
  if (side === 'BUY') return 'success'
  if (side === 'SELL') return 'error'
  return 'default'
}

export const getStatusColor = (statusCode) => {
  if (statusCode === 10) return 'info'
  if (statusCode === 20) return 'warning'
  if (statusCode === 30 || statusCode === 100 || statusCode === 110) return 'error'
  return 'default'
}
