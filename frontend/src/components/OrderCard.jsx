import PropTypes from 'prop-types'
import { Stack, Typography } from '@mui/material'
import BadgeOutlinedIcon from '@mui/icons-material/BadgeOutlined'
import PublicOutlinedIcon from '@mui/icons-material/PublicOutlined'
import SwapVertIcon from '@mui/icons-material/SwapVert'
import PaidOutlinedIcon from '@mui/icons-material/PaidOutlined'
import ThumbUpOffAltIcon from '@mui/icons-material/ThumbUpOffAlt'
import ThumbDownOffAltIcon from '@mui/icons-material/ThumbDownOffAlt'
import TradingCard from './TradingCard'
import { formatDateTime, formatNumber, formatRelativeDays } from '../utils/formatters'
import { getStatusColor } from '../utils/trading'
import { getOrderStatusLabel } from '../utils/orders'
import { getCountryName, getCountryFlag } from '../utils/countries'

const pickCounterpartyDetails = (order) => {
  const raw = order.raw || {}
  const counterparty =
    raw.counterparty_info ||
    raw.counterpartyInfo ||
    raw.counterparty ||
    raw.counterpartyDetails ||
    {}
  const oppositeName =
    order.side === 'BUY' ? raw.sellerRealName : raw.buyerRealName
  return {
    userType: counterparty.userType || counterparty.user_type || '-',
    realName:
      counterparty.realNameEn ||
      oppositeName ||
      order.counterparty_name ||
      '-',
    nickname:
      counterparty.nickName ||
      counterparty.nickname ||
      order.counterparty_nickname ||
      order.counterparty_name ||
      '-',
    kycCountryCode: counterparty.kycCountryCode || '-',
    registerTime: counterparty.registerTime,
    accountCreateDays: counterparty.accountCreateDays,
    totalFinishBuyCount: counterparty.totalFinishBuyCount,
    totalFinishSellCount: counterparty.totalFinishSellCount,
    totalTradeAmount: counterparty.totalTradeAmount,
    goodAppraiseCount: counterparty.goodAppraiseCount,
    badAppraiseCount: counterparty.badAppraiseCount,
  }
}

const buildRegistrationText = (details) => {
  if (details.accountCreateDays != null) {
    return `${details.accountCreateDays}d`
  }
  const relative = formatRelativeDays(details.registerTime)
  return relative
}

const buildBuySellValue = (buy, sell) => (
  <Stack direction="row" spacing={1} alignItems="center">
    <Typography variant="body2" sx={{ fontWeight: 600, color: 'success.main' }}>
      BUY {buy ?? 0}
    </Typography>
    <Typography variant="body2" color="text.secondary">
      /
    </Typography>
    <Typography variant="body2" sx={{ fontWeight: 600, color: 'error.main' }}>
      SELL {sell ?? 0}
    </Typography>
  </Stack>
)

const buildFeedbackValue = (good, bad) => (
  <Stack direction="row" spacing={1} alignItems="center">
    <ThumbUpOffAltIcon fontSize="small" color="success" />
    <Typography variant="body2" sx={{ fontWeight: 600 }}>
      {good ?? 0}
    </Typography>
    <ThumbDownOffAltIcon fontSize="small" color="error" />
    <Typography variant="body2" sx={{ fontWeight: 600 }}>
      {bad ?? 0}
    </Typography>
  </Stack>
)

function OrderCard({ order }) {
  const counterparty = pickCounterpartyDetails(order)
  const registrationText = buildRegistrationText(counterparty)
  const nameLine = [
    `${counterparty.realName} - ${counterparty.nickname}`,
    registrationText && registrationText !== '-' ? `(${registrationText})` : '',
  ]
    .filter(Boolean)
    .join(' ')
  const countryCode = counterparty.kycCountryCode || ''
  const countryName = getCountryName(countryCode)
  const countryFlag = getCountryFlag(countryCode)
  const codePart = countryCode ? `(${countryCode})` : ''
  const countryDisplay =
    [countryName, codePart, countryFlag].filter(Boolean).join(' ') || '-'
  const totalVolume = formatNumber(counterparty.totalTradeAmount)
  const detailRows = [
    {
      key: 'name',
      icon: <BadgeOutlinedIcon fontSize="small" />,
      value: nameLine,
    },
    {
      key: 'country',
      icon: <PublicOutlinedIcon fontSize="small" />,
      value: countryDisplay,
    },
    {
      key: 'trades',
      icon: <SwapVertIcon fontSize="small" />,
      value: buildBuySellValue(
        counterparty.totalFinishBuyCount,
        counterparty.totalFinishSellCount,
      ),
    },
    {
      key: 'volume',
      icon: <PaidOutlinedIcon fontSize="small" />,
      value:
        totalVolume && totalVolume !== '-'
          ? `${totalVolume} USDT total`
          : '-',
    },
    {
      key: 'feedback',
      icon: null,
      value: buildFeedbackValue(
        counterparty.goodAppraiseCount,
        counterparty.badAppraiseCount,
      ),
    },
  ]

  return (
    <TradingCard
      typeLabel="Order"
      entityId={order.order_id}
      side={order.side}
      token={order.token}
      fiatCurrency={order.fiat_currency}
      price={order.price}
      cryptoAmount={order.crypto_amount}
      fiatAmount={order.fiat_amount}
      statusLabel={getOrderStatusLabel(order)}
      statusColor={getStatusColor(order.status_code)}
      detailRows={detailRows}
      footer={`Created: ${formatDateTime(order.created_at)}`}
    />
  )
}

OrderCard.propTypes = {
  order: PropTypes.shape({
    order_id: PropTypes.string,
    side: PropTypes.string,
    token: PropTypes.string,
    fiat_currency: PropTypes.string,
    price: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
    crypto_amount: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
    fiat_amount: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
    status_code: PropTypes.number,
    status_label: PropTypes.string,
    counterparty_name: PropTypes.string,
    counterparty_nickname: PropTypes.string,
    created_at: PropTypes.oneOfType([PropTypes.string, PropTypes.instanceOf(Date)]),
    raw: PropTypes.object,
  }).isRequired,
}

export default OrderCard
