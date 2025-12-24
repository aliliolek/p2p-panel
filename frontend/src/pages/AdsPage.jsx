import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Divider,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Checkbox,
  FormControlLabel,
  Switch,
  Tab,
  Tabs,
  Typography,
  Grid,
  IconButton,
  Tooltip,
} from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import StopIcon from '@mui/icons-material/Stop'
import { apiGet, apiPost } from '../lib/apiClient'
import { useUserSession } from '../mui-templates/crud-dashboard/context/UserSessionContext'
import AdCard from '../components/AdCard'
import { formatDateTime } from '../utils/formatters'

const STATUS_FILTERS = [
  { value: 'all', label: 'All statuses' },
  { value: 'active', label: 'Active only' },
  { value: 'hidden', label: 'Hidden only' },
]

const AUTO_MARKER = '@@@'
const AUTO_PAUSED_MARKER = '@*@'
const hasAutoRemark = (remark = '') => remark.includes(AUTO_MARKER)
const hasPausedRemark = (remark = '') => remark.includes(AUTO_PAUSED_MARKER)

const isActiveAd = (ad) => ad.status_code === 10
const isFiatBalanceAd = (ad) => {
  const ids = ad.payment_type_ids || []
  return ids.includes(416) || ids.includes('416')
}

function AdsPage() {
  const { accessToken } = useUserSession()
  const [accounts, setAccounts] = useState([])
  const [selectedAccountId, setSelectedAccountId] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [tokenFilter, setTokenFilter] = useState('all')
  const [currencyFilter, setCurrencyFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [autoStatus, setAutoStatus] = useState(null)
  const [autoStatusError, setAutoStatusError] = useState('')
  const [autoBusy, setAutoBusy] = useState(false)
  const [fiatAutoStatus, setFiatAutoStatus] = useState(null)
  const [fiatAutoStatusError, setFiatAutoStatusError] = useState('')
  const [fiatAutoBusy, setFiatAutoBusy] = useState(false)
  const [fiatSellEnabled, setFiatSellEnabled] = useState(true)
  const [fiatBuyEnabled, setFiatBuyEnabled] = useState(true)
  const [adActionBusy, setAdActionBusy] = useState('')
  const [adBulkBusy, setAdBulkBusy] = useState(false)
  const [adBulkSwitchState, setAdBulkSwitchState] = useState(null)
  const [viewMode, setViewMode] = useState('all')

  const selectedAccount = useMemo(() => {
    if (!selectedAccountId) {
      return accounts[0]
    }
    return accounts.find((account) => account.credential_id === selectedAccountId)
  }, [accounts, selectedAccountId])

  const fetchAds = useCallback(async () => {
    if (!accessToken) return
    setError('')
    try {
      const data = await apiGet('/api/ads', accessToken)
      const fetchedAccounts = data.accounts || []
      setAccounts(fetchedAccounts)
      if (fetchedAccounts.length === 0) {
        setSelectedAccountId('')
        return
      }
      const stillExists = fetchedAccounts.some(
        (account) => account.credential_id === selectedAccountId,
      )
      if (!stillExists) {
        setSelectedAccountId(fetchedAccounts[0].credential_id)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [accessToken, selectedAccountId])

  const fetchAutoStatus = useCallback(async () => {
    if (!accessToken) return
    try {
      const data = await apiGet('/api/auto-pricing/status', accessToken)
      setAutoStatus(data)
      setAutoStatusError('')
    } catch (err) {
      setAutoStatusError(err.message)
    }
  }, [accessToken])

  const fetchFiatAutoStatus = useCallback(async () => {
    if (!accessToken) return
    try {
      const data = await apiGet('/api/fiat-balance-auto-pricing/status', accessToken)
      setFiatAutoStatus(data)
      setFiatAutoStatusError('')
      if (data?.sell_enabled !== undefined) {
        setFiatSellEnabled(Boolean(data.sell_enabled))
      }
      if (data?.buy_enabled !== undefined) {
        setFiatBuyEnabled(Boolean(data.buy_enabled))
      }
    } catch (err) {
      setFiatAutoStatusError(err.message)
    }
  }, [accessToken])

  useEffect(() => {
    if (!accessToken) return
    fetchAds()
    fetchAutoStatus()
    fetchFiatAutoStatus()
  }, [accessToken, fetchAds, fetchAutoStatus, fetchFiatAutoStatus])

  useEffect(() => {
    if (viewMode === 'all') {
      fetchAutoStatus()
    } else {
      fetchFiatAutoStatus()
    }
  }, [viewMode, fetchAutoStatus, fetchFiatAutoStatus])

  useEffect(() => {
    if (autoStatus?.running !== true) return undefined
    const id = setInterval(() => {
      fetchAutoStatus()
    }, 10000)
    return () => clearInterval(id)
  }, [autoStatus?.running, fetchAutoStatus])

  useEffect(() => {
    if (fiatAutoStatus?.running !== true) return undefined
    const id = setInterval(() => {
      fetchFiatAutoStatus()
    }, 10000)
    return () => clearInterval(id)
  }, [fiatAutoStatus?.running, fetchFiatAutoStatus])

  const handleRefresh = async () => {
    setRefreshing(true)
    const promises = [fetchAds()]
    if (viewMode === 'all') {
      promises.push(fetchAutoStatus())
    } else {
      promises.push(fetchFiatAutoStatus())
    }
    await Promise.all(promises)
  }

  const handleAutoToggle = async () => {
    if (!accessToken) return
    setAutoBusy(true)
    setAutoStatusError('')
    try {
      const path = autoStatus?.running ? '/api/auto-pricing/stop' : '/api/auto-pricing/start'
      await apiPost(path, {}, accessToken)
      await fetchAutoStatus()
    } catch (err) {
      setAutoStatusError(err.message)
    } finally {
      setAutoBusy(false)
    }
  }

  const handleFiatAutoToggle = async () => {
    if (!accessToken) return
    setFiatAutoBusy(true)
    setFiatAutoStatusError('')
    try {
      const path = fiatAutoStatus?.running
        ? '/api/fiat-balance-auto-pricing/stop'
        : '/api/fiat-balance-auto-pricing/start'
      const payload =
        path === '/api/fiat-balance-auto-pricing/start'
          ? { sell: fiatSellEnabled, buy: fiatBuyEnabled }
          : {}
      await apiPost(path, payload, accessToken)
      await fetchFiatAutoStatus()
    } catch (err) {
      setFiatAutoStatusError(err.message)
    } finally {
      setFiatAutoBusy(false)
    }
  }

  const handleAdAutoToggle = async (ad) => {
    if (!accessToken || !selectedAccount) return
    const remark = ad.remark || ''
    const paused = hasPausedRemark(remark)
    const auto = hasAutoRemark(remark)
    const isCurrentlyAuto = auto && !paused
    const enable = !isCurrentlyAuto
    setAdActionBusy(ad.ad_id)
    setError('')
    try {
      await apiPost('/api/ads/toggle-auto', {
        credential_id: selectedAccount.credential_id,
        ad_id: ad.ad_id,
        enable,
      }, accessToken)
      await fetchAds()
      await fetchAutoStatus()
    } catch (err) {
      setError(err.message)
    } finally {
      setAdActionBusy('')
    }
  }

  const handleAdOffline = async (ad) => {
    if (!accessToken || !selectedAccount) return
    setAdActionBusy(ad.ad_id)
    setError('')
    try {
      await apiPost('/api/ads/offline', {
        credential_id: selectedAccount.credential_id,
        ad_id: ad.ad_id,
      }, accessToken)
      await fetchAds()
      await fetchAutoStatus()
    } catch (err) {
      setError(err.message)
    } finally {
      setAdActionBusy('')
    }
  }

  const handleAdActivate = async (ad) => {
    if (!accessToken || !selectedAccount) return
    setAdActionBusy(ad.ad_id)
    setError('')
    try {
      await apiPost(
        '/api/ads/activate',
        {
          credential_id: selectedAccount.credential_id,
          ad_id: ad.ad_id,
        },
        accessToken,
      )
      await fetchAds()
      await fetchAutoStatus()
    } catch (err) {
      setError(err.message)
    } finally {
      setAdActionBusy('')
    }
  }

  const handleBulkAutoToggle = async (targetEnable) => {
    if (!accessToken || !selectedAccount || viewMode !== 'all') return
    setAdBulkSwitchState(targetEnable)
    const targets = filteredAds.filter((ad) => {
      const remark = ad.remark || ''
      const hasPaused = hasPausedRemark(remark)
      const hasAuto = hasAutoRemark(remark)
      if (!hasPaused && !hasAuto) {
        return false
      }
      if (targetEnable) {
        // Set auto: act only on paused
        return hasPaused
      }
      // Set manual: act only on auto
      return hasAuto
    })
    if (targets.length === 0) return
    setAdBulkBusy(true)
    setError('')
    try {
      for (const ad of targets) {
        await apiPost(
          '/api/ads/toggle-auto',
          {
            credential_id: selectedAccount.credential_id,
            ad_id: ad.ad_id,
            enable: targetEnable,
          },
          accessToken,
        )
      }
      await fetchAds()
      await fetchAutoStatus()
      setAdBulkSwitchState(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setAdBulkBusy(false)
    }
  }

  const baseAds = useMemo(() => {
    if (!selectedAccount) return []
    if (viewMode === 'fiat-balance') {
      return selectedAccount.fiat_balance_ads || []
    }
    const allAds = selectedAccount.ads || []
    return allAds.filter((ad) => !isFiatBalanceAd(ad))
  }, [selectedAccount, viewMode])

  const tokenOptions = useMemo(() => {
    const tokens = new Set(
      baseAds.map((ad) => ad.token).filter(Boolean).map((token) => token.toUpperCase()),
    )
    return Array.from(tokens).sort()
  }, [baseAds])

  const currencyOptions = useMemo(() => {
    const currencies = new Set(baseAds.map((ad) => ad.fiat_currency).filter(Boolean))
    return Array.from(currencies).sort()
  }, [baseAds])

  const filteredAds = useMemo(() => {
    if (!selectedAccount) return []
    return baseAds.filter((ad) => {
      if (tokenFilter !== 'all' && ad.token?.toUpperCase() !== tokenFilter) {
        return false
      }
      if (currencyFilter !== 'all' && ad.fiat_currency !== currencyFilter) {
        return false
      }
      if (statusFilter === 'active' && !isActiveAd(ad)) {
        return false
      }
      if (statusFilter === 'hidden' && isActiveAd(ad)) {
        return false
      }
      return true
    })
  }, [selectedAccount, tokenFilter, currencyFilter, statusFilter, baseAds])

  const groupedAds = useMemo(() => {
    const groups = new Map()
    filteredAds.forEach((ad) => {
      const fiat = ad.fiat_currency || 'UNKNOWN'
      if (!groups.has(fiat)) {
        groups.set(fiat, { fiat, buy: [], sell: [] })
      }
      const group = groups.get(fiat)
      if (ad.side === 'SELL') {
        group.sell.push(ad)
      } else {
        group.buy.push(ad)
      }
    })
    return Array.from(groups.values())
  }, [filteredAds])

  const allAutoEnabled = useMemo(() => {
    if (filteredAds.length === 0) return false
    return filteredAds.every((ad) => {
      const remark = ad.remark || ''
      const hasPausedMarker = hasPausedRemark(remark)
      const hasAutoMarker = hasAutoRemark(remark)
      return hasAutoMarker && !hasPausedMarker
    })
  }, [filteredAds])

  const autoPricingMap = useMemo(() => {
    if (!autoStatus?.ads) return {}
    const entries = {}
    autoStatus.ads.forEach((item) => {
      if (item?.ad_id) {
        entries[item.ad_id] = item
      }
    })
    return entries
  }, [autoStatus])

  const fiatAutoMap = useMemo(() => {
    if (!fiatAutoStatus?.ads) return {}
    const entries = {}
    fiatAutoStatus.ads.forEach((item) => {
      if (item?.ad_id) {
        entries[item.ad_id] = item
      }
    })
    return entries
  }, [fiatAutoStatus])

  const getAutomationInfo = useCallback(
    (ad) => {
      if (viewMode === 'fiat-balance') {
        const entry = fiatAutoMap[ad.ad_id] || {}
        return {
          isAutoEnabled: !!fiatAutoStatus?.running,
          isAutoPaused: false,
          groups: entry.competitor_groups_full || entry.competitor_groups || [],
          spot_symbol: entry.spot_symbol,
          spot_bid: entry.spot_bid,
          spot_ask: entry.spot_ask,
          target_price: entry.target_price,
          guardrail_price: entry.guardrail_price,
          available_balance: entry.available_balance,
          suggested_buy_qty: entry.suggested_buy_qty,
        }
      }
      const remark = ad.remark || ''
      const hasPausedMarker = hasPausedRemark(remark)
      const hasAutoMarker = hasAutoRemark(remark)
      const entry = autoPricingMap[ad.ad_id] || {}
      return {
        isAutoEnabled: hasAutoMarker && !hasPausedMarker,
        isAutoPaused: hasPausedMarker,
        groups: entry.competitor_groups || [],
        spot_symbol: entry.spot_symbol,
        spot_bid: entry.spot_bid,
        spot_ask: entry.spot_ask,
        target_price: entry.target_price,
      }
    },
    [autoPricingMap, fiatAutoMap, fiatAutoStatus?.running, viewMode],
  )

  if (loading) {
    return (
      <Box
        sx={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <CircularProgress />
      </Box>
    )
  }
  return (
    <Box sx={{ p: 3, display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        justifyContent="space-between"
        alignItems={{ xs: 'flex-start', sm: 'center' }}
        spacing={2}
      >
        <Typography variant="h4">My Ads</Typography>
        <Stack direction="row" spacing={1}>
          <Button
            startIcon={<RefreshIcon />}
            onClick={handleRefresh}
            disabled={refreshing}
          >
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </Button>
          <Stack direction="row" spacing={0.5} alignItems="center">
            <Typography variant="caption" color="text.secondary">
              Auto price
            </Typography>
            {viewMode === 'all' ? (
              <Tooltip title={autoStatus?.running ? 'Stop auto pricing' : 'Start auto pricing'}>
                <span>
                  <IconButton
                    size="small"
                    color={autoStatus?.running ? 'warning' : 'primary'}
                    onClick={handleAutoToggle}
                    disabled={autoBusy}
                  >
                    {autoStatus?.running ? <StopIcon /> : <PlayArrowIcon />}
                  </IconButton>
                </span>
              </Tooltip>
            ) : (
              <Tooltip
                title={
                  fiatAutoStatus?.running ? 'Stop fiat balance auto pricing' : 'Start fiat balance auto pricing'
                }
              >
                <span>
                  <IconButton
                    size="small"
                    color={fiatAutoStatus?.running ? 'warning' : 'primary'}
                    onClick={handleFiatAutoToggle}
                    disabled={fiatAutoBusy}
                  >
                    {fiatAutoStatus?.running ? <StopIcon /> : <PlayArrowIcon />}
                  </IconButton>
                </span>
              </Tooltip>
            )}
            {viewMode === 'fiat-balance' ? (
              <Stack direction="row" spacing={1} alignItems="center" sx={{ ml: 1 }}>
                <Tooltip title="Enable SELL auto pricing">
                  <FormControlLabel
                    control={
                      <Checkbox
                        size="small"
                        checked={fiatSellEnabled}
                        onChange={(e) => setFiatSellEnabled(e.target.checked)}
                        disabled={fiatAutoBusy || fiatAutoStatus?.running}
                      />
                    }
                    label="SELL"
                  />
                </Tooltip>
                <Tooltip title="Enable BUY auto pricing">
                  <FormControlLabel
                    control={
                      <Checkbox
                        size="small"
                        checked={fiatBuyEnabled}
                        onChange={(e) => setFiatBuyEnabled(e.target.checked)}
                        disabled={fiatAutoBusy || fiatAutoStatus?.running}
                      />
                    }
                    label="BUY"
                  />
                </Tooltip>
              </Stack>
            ) : null}
          </Stack>
        </Stack>
      </Stack>
      {viewMode === 'all' ? (
        <Typography variant="caption" color="text.secondary">
          Auto pricing status:{' '}
          {autoStatus?.running ? 'Running' : 'Stopped'}{' '}
          {autoStatus?.last_success_at
            ? `• Last update: ${formatDateTime(autoStatus.last_success_at)}`
            : ''}
        </Typography>
      ) : (
        <Typography variant="caption" color="text.secondary">
          Fiat balance auto status:{' '}
          {fiatAutoStatus?.running ? 'Running' : 'Stopped'}{' '}
          {fiatAutoStatus?.last_success_at
            ? `• Last update: ${formatDateTime(fiatAutoStatus.last_success_at)}`
            : ''}
        </Typography>
      )}
      {error ? (
        <Alert severity="error" onClose={() => setError('')}>
          {error}
        </Alert>
      ) : null}
      {autoStatusError ? (
        <Alert severity="error" onClose={() => setAutoStatusError('')}>
          {autoStatusError}
        </Alert>
      ) : null}
      {fiatAutoStatusError ? (
        <Alert severity="error" onClose={() => setFiatAutoStatusError('')}>
          {fiatAutoStatusError}
        </Alert>
      ) : null}

      {accounts.length === 0 ? (
        <Card>
          <CardContent>
            <Typography color="text.secondary">
              No connected accounts with ads yet.
            </Typography>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Tabs
              value={selectedAccount ? selectedAccount.credential_id : false}
              onChange={(_event, value) => setSelectedAccountId(value)}
              variant="scrollable"
              allowScrollButtonsMobile
            >
              {accounts.map((account) => (
                <Tab
                  key={account.credential_id}
                  label={
                    account.account_label
                      ? `${account.account_label} (${account.exchange})`
                      : account.exchange
                  }
                  value={account.credential_id}
                />
              ))}
            </Tabs>

            <Tabs
              value={viewMode}
              onChange={(_event, value) => setViewMode(value)}
              variant="scrollable"
              allowScrollButtonsMobile
            >
              <Tab label="All Ads" value="all" />
              <Tab label="Fiat Balance Ads" value="fiat-balance" />
            </Tabs>

            {selectedAccount ? (
              <>
                {selectedAccount.error ? (
                  <Alert severity="warning">{selectedAccount.error}</Alert>
                ) : null}

                <Stack
                  direction={{ xs: 'column', md: 'row' }}
                  spacing={2}
                  alignItems={{ xs: 'stretch', md: 'center' }}
                >
                  <FormControl fullWidth>
                    <InputLabel id="token-filter-label">Crypto</InputLabel>
                    <Select
                      labelId="token-filter-label"
                      value={tokenFilter}
                      label="Crypto"
                      onChange={(event) => setTokenFilter(event.target.value)}
                    >
                      <MenuItem value="all">All</MenuItem>
                      {tokenOptions.map((token) => (
                        <MenuItem key={token} value={token}>
                          {token}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  <FormControl fullWidth>
                    <InputLabel id="currency-filter-label">Fiat</InputLabel>
                    <Select
                      labelId="currency-filter-label"
                      value={currencyFilter}
                      label="Fiat"
                      onChange={(event) => setCurrencyFilter(event.target.value)}
                    >
                      <MenuItem value="all">All</MenuItem>
                      {currencyOptions.map((currency) => (
                        <MenuItem key={currency} value={currency}>
                          {currency}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
              <FormControl fullWidth>
                <InputLabel id="status-filter-label">Status</InputLabel>
                <Select
                  labelId="status-filter-label"
                  value={statusFilter}
                      label="Status"
                      onChange={(event) => setStatusFilter(event.target.value)}
                    >
                      {STATUS_FILTERS.map((option) => (
                        <MenuItem key={option.value} value={option.value}>
                          {option.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              {viewMode === 'all' ? (
                <FormControlLabel
                  control={
                    <Switch
                      checked={adBulkSwitchState ?? allAutoEnabled}
                      onChange={(e) => handleBulkAutoToggle(e.target.checked)}
                      disabled={adBulkBusy || filteredAds.length === 0}
                    />
                  }
                  label={adBulkBusy ? 'Applying...' : 'All Auto'}
                />
              ) : null}
            </Stack>

                {groupedAds.length === 0 ? (
                  <Typography color="text.secondary">
                    No ads matching the selected filters.
                  </Typography>
                ) : (
                  groupedAds.map((group, index) => (
                    <Box key={`${group.fiat}-${index}`}>
                      <Typography variant="subtitle2" sx={{ mb: 1 }}>
                        {group.fiat}
                      </Typography>
                      <Grid container spacing={2}>
                        <Grid item xs={12} md={6}>
                          <Stack spacing={2}>
                            {group.sell.length === 0 ? (
                              <Typography color="text.secondary">
                                No SELL ads.
                              </Typography>
                            ) : (
                              group.sell.map((ad) => (
                                <AdCard
                                  key={ad.ad_id}
                                  ad={ad}
                                  automation={getAutomationInfo(ad)}
                                  onToggleAuto={() => handleAdAutoToggle(ad)}
                                  onOffline={() => handleAdOffline(ad)}
                                  onActivate={() => handleAdActivate(ad)}
                                  actionBusy={adActionBusy === ad.ad_id}
                                />
                              ))
                            )}
                          </Stack>
                        </Grid>
                        <Grid item xs={12} md={6}>
                          <Stack spacing={2}>
                            {group.buy.length === 0 ? (
                              <Typography color="text.secondary">
                                No BUY ads.
                              </Typography>
                            ) : (
                              group.buy.map((ad) => (
                                <AdCard
                                  key={ad.ad_id}
                                  ad={ad}
                                  automation={getAutomationInfo(ad)}
                                  onToggleAuto={() => handleAdAutoToggle(ad)}
                                  onOffline={() => handleAdOffline(ad)}
                                  onActivate={() => handleAdActivate(ad)}
                                  actionBusy={adActionBusy === ad.ad_id}
                                />
                              ))
                            )}
                          </Stack>
                        </Grid>
                      </Grid>
                      <Divider sx={{ my: 3 }} />
                    </Box>
                  ))
                )}
              </>
            ) : null}
          </CardContent>
        </Card>
      )}
    </Box>
  )
}

export default AdsPage
