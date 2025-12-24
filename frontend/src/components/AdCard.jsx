import PropTypes from 'prop-types'
import AccountBalanceIcon from '@mui/icons-material/AccountBalance'
import StraightenIcon from '@mui/icons-material/Straighten'
import TimelineIcon from '@mui/icons-material/Timeline'
import { IconButton, Stack, Switch, Tooltip, Typography } from '@mui/material'
import CloseIcon from '@mui/icons-material/Close'
import RefreshIcon from '@mui/icons-material/Refresh'
import TradingCard from './TradingCard'
import { formatDateTime, formatNumber } from '../utils/formatters'

const isActiveAd = (ad) => ad.status_code === 10

const formatPriceGroup = (group, side) => {
  if (!group) return null
  const min = formatNumber(group.min_price, 4)
  const max = formatNumber(group.max_price, 4)
  if (min === '-' && max === '-') {
    return null
  }
  const isBuy = String(side || '').toUpperCase() === 'BUY'
  const first = isBuy ? max : min
  const second = isBuy ? min : max
  if (first === second || second === '-') {
    return `[${first}]`
  }
  if (first === '-') {
    return `[${second}]`
  }
  return `[${first}-${second}]`
}

const formatSpot = (automation) => {
  if (!automation) return '-'
  const bid = formatNumber(automation.spot_bid, 4)
  const ask = formatNumber(automation.spot_ask, 4)
  if (bid === '-' && ask === '-') return '-'
  return `Spot ${bid} / ${ask}`
}

const formatTarget = (automation) => {
  if (!automation) return '-'
  const target = formatNumber(automation.target_price, 4)
  return target === '-' ? '-' : `Target ${target}`
}

const formatGuardrail = (automation) => {
  if (!automation) return '-'
  const guardrail = formatNumber(automation.guardrail_price, 4)
  return guardrail === '-' ? '-' : `Guardrail ${guardrail}`
}

const formatBalance = (automation, token) => {
  if (!automation) return '-'
  const bal = formatNumber(automation.available_balance, 6)
  return bal === '-' ? '-' : `${bal} ${token || ''}`.trim()
}

const formatSuggestedBuy = (automation, token) => {
  if (!automation) return '-'
  const qty = formatNumber(automation.suggested_buy_qty, 6)
  return qty === '-' ? '-' : `Buy qty: ${qty} ${token || ''}`.trim()
}

function AdCard({ ad, automation, onToggleAuto, onOffline, onActivate, actionBusy }) {
  const limits =
    ad.min_amount != null || ad.max_amount != null
      ? `${formatNumber(ad.min_amount)} - ${formatNumber(ad.max_amount)} ${
          ad.fiat_currency || ''
        }`
      : '-'

  const payments =
    ad.payment_methods && ad.payment_methods.length > 0
      ? ad.payment_methods.join(', ')
      : '-'

  const formattedGroups =
    automation?.groups && automation.groups.length > 0
      ? automation.groups
          .map((group) => formatPriceGroup(group, ad.side))
          .filter(Boolean)
          .join(' ')
      : '-'

  const detailRows = [
    {
      value: limits,
      icon: <StraightenIcon fontSize="small" />,
      key: 'limits',
    },
    {
      value: payments,
      icon: <AccountBalanceIcon fontSize="small" />,
      key: 'payments',
    },
  ]

  detailRows.push({
    value: formattedGroups,
    icon: <TimelineIcon fontSize="small" />,
    key: 'price-groups',
  })

  detailRows.push({
    value: formatSpot(automation),
    icon: <TimelineIcon fontSize="small" />,
    key: 'spot-quote',
  })

  detailRows.push({
    value: (
      <Typography variant="body2" sx={{ fontWeight: 700, color: 'primary.main' }}>
        {formatTarget(automation)}
      </Typography>
    ),
    icon: <TimelineIcon fontSize="small" color="primary" />,
    key: 'target-price',
  })

  detailRows.push({
    value: formatGuardrail(automation),
    icon: <TimelineIcon fontSize="small" />,
    key: 'guardrail-price',
  })

  detailRows.push({
    value: formatBalance(automation, ad.token),
    icon: <TimelineIcon fontSize="small" />,
    key: 'balance',
  })

  if (String(ad.side || '').toUpperCase() === 'BUY') {
    detailRows.push({
      value: formatSuggestedBuy(automation, ad.token),
      icon: <TimelineIcon fontSize="small" />,
      key: 'suggested-buy',
    })
  }

  const cornerActions = isActiveAd(ad) ? (
    <>
      <Stack direction="row" spacing={0.5} alignItems="center">
        <Typography variant="caption">Manual</Typography>
        <Switch
          size="small"
          checked={!!automation?.isAutoEnabled}
          onChange={onToggleAuto}
          disabled={!onToggleAuto || actionBusy}
        />
        <Typography variant="caption">Auto</Typography>
      </Stack>
      <Tooltip title="Set offline">
        <span>
          <IconButton
            size="small"
            color="warning"
            onClick={onOffline}
            disabled={!onOffline || actionBusy}
          >
            <CloseIcon fontSize="small" />
          </IconButton>
        </span>
      </Tooltip>
    </>
  ) : (
    <Tooltip title="Activate online">
      <span>
        <IconButton
          size="small"
          color="primary"
          onClick={onActivate}
          disabled={!onActivate || actionBusy}
          sx={{ opacity: 1 }}
        >
          <RefreshIcon fontSize="small" />
        </IconButton>
      </span>
    </Tooltip>
  )

  return (
    <TradingCard
      typeLabel="Ad"
      entityId={ad.ad_id}
      side={ad.side}
      token={ad.token}
      fiatCurrency={ad.fiat_currency}
      price={ad.price}
      cryptoAmount={ad.crypto_amount}
      fiatAmount={ad.fiat_amount}
      statusLabel={ad.status_label}
      statusColor={isActiveAd(ad) ? 'success' : 'default'}
      detailRows={detailRows}
      actions={null}
      cornerActions={cornerActions}
      dimmed={!isActiveAd(ad)}
      footer={`Updated: ${formatDateTime(ad.updated_at)}`}
    />
  )
}

AdCard.propTypes = {
  ad: PropTypes.shape({
    ad_id: PropTypes.string,
    side: PropTypes.string,
    token: PropTypes.string,
    fiat_currency: PropTypes.string,
    price: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    crypto_amount: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    fiat_amount: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    min_amount: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    max_amount: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    payment_methods: PropTypes.arrayOf(PropTypes.string),
    status_code: PropTypes.number,
    status_label: PropTypes.string,
    updated_at: PropTypes.oneOfType([PropTypes.string, PropTypes.instanceOf(Date)]),
    fee: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    remark: PropTypes.string,
  }).isRequired,
  automation: PropTypes.shape({
    isAutoEnabled: PropTypes.bool,
    isAutoPaused: PropTypes.bool,
    groups: PropTypes.arrayOf(
      PropTypes.shape({
        min_price: PropTypes.number,
        max_price: PropTypes.number,
        competitor_count: PropTypes.number,
      }),
    ),
    competitor_groups_full: PropTypes.arrayOf(
      PropTypes.shape({
        min_price: PropTypes.number,
        max_price: PropTypes.number,
        competitor_count: PropTypes.number,
      }),
    ),
    spot_bid: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
    spot_ask: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
    target_price: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
    guardrail_price: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
    available_balance: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
    suggested_buy_qty: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  }),
  onToggleAuto: PropTypes.func,
  onOffline: PropTypes.func,
  onActivate: PropTypes.func,
  actionBusy: PropTypes.bool,
}

AdCard.defaultProps = {
  automation: {
    isAutoEnabled: false,
    isAutoPaused: false,
    groups: [],
  },
  onToggleAuto: undefined,
  onOffline: undefined,
  onActivate: undefined,
  actionBusy: false,
}

export default AdCard
