export const getOrderStatusLabel = (order) => {
  if (order?.status_label) {
    return order.status_label
  }
  if (order?.status_code != null) {
    return `Status ${order.status_code}`
  }
  return '-'
}
