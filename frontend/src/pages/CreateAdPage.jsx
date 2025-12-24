import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  CircularProgress,
  FormControl,
  FormControlLabel,
  FormGroup,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Slider,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from '@mui/material'
import { apiGet, apiPost } from '../lib/apiClient'
import { useUserSession } from '../mui-templates/crud-dashboard/context/UserSessionContext'

const BUY_QTY_LIMITS = {
  USDT: { min: 10, max: 50000 },
  USDC: { min: 10, max: 50000 },
  BTC: { min: 0.00011788, max: 2 },
  ETH: { min: 0.00360639, max: 30 },
}

const SELL_QTY_FIXED = {
  USDT: 10,
  USDC: 10,
  BTC: 0.00011788,
  ETH: 0.00360639,
}

function formatNumber(value) {
  if (value == null || Number.isNaN(value)) return ''
  return Number(value)
    .toLocaleString(undefined, { maximumFractionDigits: 8 })
    .replace(/\u00a0/g, ' ')
}

function uniqueOrFirst(items) {
  if (!items || items.length === 0) return []
  return Array.from(new Set(items))
}

function CreateAdPage() {
  const { accessToken } = useUserSession()
  const [config, setConfig] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [submitError, setSubmitError] = useState('')
  const [submitSuccess, setSubmitSuccess] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const [accountId, setAccountId] = useState('')
  const [selectedTokens, setSelectedTokens] = useState([])
  const [selectedFiats, setSelectedFiats] = useState([])
  const [buyQuantityMap, setBuyQuantityMap] = useState({})
  const [remarkMarker, setRemarkMarker] = useState('')
  const [minAmountMap, setMinAmountMap] = useState({})
  const [maxAmountMap, setMaxAmountMap] = useState({})

  const tabs = [{ value: 'fiat-balance', label: 'Create Fiat Balance Ads' }]
  const [activeTab, setActiveTab] = useState('fiat-balance')

  useEffect(() => {
    const fetchConfig = async () => {
      if (!accessToken) return
      setLoading(true)
      setError('')
      try {
        const data = await apiGet('/api/fiat-balance/config', accessToken)
        setConfig(data)
        const firstAccount = data.accounts && data.accounts[0]
        setAccountId(firstAccount ? firstAccount.credential_id : '')
        setSelectedTokens(uniqueOrFirst(data.tokens))
        setSelectedFiats(uniqueOrFirst(data.fiats))
        setRemarkMarker(data.remark_marker || '')
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }
    fetchConfig()
  }, [accessToken])

  const account = useMemo(() => {
    if (!config) return null
    return config.accounts.find((item) => item.credential_id === accountId) || null
  }, [config, accountId])

  const fiatLimits = useMemo(() => {
    if (!config || !config.limits) return {}
    const out = {}
    selectedFiats.forEach((fiat) => {
      const entries = config.limits[fiat] || []
      const mins = []
      const maxs = []
      entries.forEach((item) => {
        const min = parseFloat(item.minAmount)
        const max = parseFloat(item.maxAmount)
        if (!Number.isNaN(min)) mins.push(min)
        if (!Number.isNaN(max)) maxs.push(max)
      })
      if (mins.length || maxs.length) {
        out[fiat] = {
          min: mins.length ? Math.min(...mins) : null,
          max: maxs.length ? Math.max(...maxs) : null,
        }
      }
    })
    return out
  }, [config, selectedFiats])

  const buyRange = useMemo(() => {
    const range = {}
    selectedTokens.forEach((t) => {
      range[t] = BUY_QTY_LIMITS[t] || { min: 0, max: 0 }
    })
    return range
  }, [selectedTokens])

  const sellRange = useMemo(() => {
    const range = {}
    selectedTokens.forEach((t) => {
      const balance = account?.balances?.[t] ?? 0
      const fallbackMax = BUY_QTY_LIMITS[t]?.max || SELL_QTY_FIXED[t] || 0
      range[t] = {
        min: SELL_QTY_FIXED[t] || 0,
        max: balance > 0 ? balance : fallbackMax,
      }
    })
    return range
  }, [selectedTokens, account])

  useEffect(() => {
    if (!selectedTokens.length) return
    setBuyQuantityMap((prev) => {
      const next = { ...prev }
      selectedTokens.forEach((t) => {
        const { min } = buyRange[t] || { min: 0 }
        if (next[t] == null) next[t] = min
      })
      return next
    })
  }, [selectedTokens, buyRange])

  const handleToggle = (value, list, setter) => {
    if (list.includes(value)) {
      setter(list.filter((item) => item !== value))
    } else {
      setter([...list, value])
    }
  }

  const handleSubmit = async () => {
    if (!accessToken || !config) return
    setSubmitting(true)
    setSubmitError('')
    setSubmitSuccess('')
    setDeleting(false)
    try {
      await apiPost(
        '/api/fiat-balance/create-batch',
        {
          credential_id: accountId,
          tokens: selectedTokens,
          fiats: selectedFiats,
          buyQuantityMap,
          sellQuantityMap: SELL_QTY_FIXED,
          paymentPeriod: '15',
          remark: remarkMarker,
          minAmountMap: Object.fromEntries(
            Object.entries(minAmountMap).filter(([, v]) => v !== ''),
          ),
          maxAmountMap: Object.fromEntries(
            Object.entries(maxAmountMap).filter(([, v]) => v !== ''),
          ),
        },
        accessToken,
      )
      setSubmitSuccess('Batch creation started')
    } catch (err) {
      setSubmitError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async () => {
    if (!accessToken || !config) return
    setDeleting(true)
    setSubmitError('')
    setSubmitSuccess('')
    setSubmitting(false)
    try {
      await apiPost(
        '/api/fiat-balance/delete-by-remark',
        {
          credential_id: accountId,
          remark: remarkMarker,
        },
        accessToken,
      )
      setSubmitSuccess('Deletion completed')
    } catch (err) {
      setSubmitError(err.message)
    } finally {
      setDeleting(false)
    }
  }

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
    <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      <Typography variant="h6">Create Ad</Typography>
      {error ? (
        <Alert severity="error" onClose={() => setError('')}>
          {error}
        </Alert>
      ) : null}
      {submitError ? (
        <Alert severity="error" onClose={() => setSubmitError('')}>
          {submitError}
        </Alert>
      ) : null}
      {submitSuccess ? (
        <Alert severity="success" onClose={() => setSubmitSuccess('')}>
          {submitSuccess}
        </Alert>
      ) : null}

      <Tabs value={activeTab} onChange={(_e, v) => setActiveTab(v)} size="small">
        {tabs.map((tab) => (
          <Tab key={tab.value} value={tab.value} label={tab.label} />
        ))}
      </Tabs>

      {activeTab === 'fiat-balance' ? (
        <Card>
          <CardContent sx={{ p: 2 }}>
            <Stack spacing={1.5}>
              <FormControl fullWidth size="small">
                <InputLabel id="account-label">Account</InputLabel>
                <Select
                  labelId="account-label"
                  label="Account"
                  value={accountId}
                  onChange={(e) => setAccountId(e.target.value)}
                >
                  {config?.accounts?.map((acc) => (
                    <MenuItem key={acc.credential_id} value={acc.credential_id}>
                      {acc.account_label || acc.exchange}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <Grid container spacing={1.5}>
                <Grid item xs={12} md={6}>
                  <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                    Crypto
                  </Typography>
                  <FormGroup row>
                    {config?.tokens?.map((tkn) => (
                      <FormControlLabel
                        key={tkn}
                        control={
                          <Checkbox
                            size="small"
                            checked={selectedTokens.includes(tkn)}
                            onChange={() => handleToggle(tkn, selectedTokens, setSelectedTokens)}
                          />
                        }
                        label={tkn}
                      />
                    ))}
                  </FormGroup>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                    Fiat
                  </Typography>
                  <FormGroup row>
                    {config?.fiats?.map((cur) => (
                      <FormControlLabel
                        key={cur}
                        control={
                          <Checkbox
                            size="small"
                            checked={selectedFiats.includes(cur)}
                            onChange={() => handleToggle(cur, selectedFiats, setSelectedFiats)}
                          />
                        }
                        label={cur}
                      />
                    ))}
                  </FormGroup>
                </Grid>
              </Grid>

              <Grid container spacing={0.5}>
                {selectedFiats.map((cur) => (
                  <Grid item xs={12} sm={6} md={2} key={cur} sx={{ maxWidth: 200 }}>
                    <Stack
                      spacing={0.5}
                      sx={{
                        border: '1px solid',
                        borderColor: 'divider',
                        borderRadius: 1,
                        p: 1,
                        bgcolor: 'background.paper',
                      }}
                    >
                      <Typography variant="caption" sx={{ fontWeight: 600 }}>
                        {cur}
                      </Typography>
                      <Stack direction="row" spacing={0.75}>
                        <TextField
                          label="Min"
                          value={minAmountMap[cur] ?? ''}
                          onChange={(e) =>
                            setMinAmountMap((prev) => ({ ...prev, [cur]: e.target.value }))
                          }
                          sx={{ width: '48%' }}
                          size="small"
                          type="number"
                          helperText={
                            fiatLimits[cur]
                              ? `Default: ${formatNumber(fiatLimits[cur].min)}`
                              : 'Optional'
                          }
                        />
                        <TextField
                          label="Max"
                          value={maxAmountMap[cur] ?? ''}
                          onChange={(e) =>
                            setMaxAmountMap((prev) => ({ ...prev, [cur]: e.target.value }))
                          }
                          sx={{ width: '48%' }}
                          size="small"
                          type="number"
                          helperText={
                            fiatLimits[cur]
                              ? `Default: ${formatNumber(fiatLimits[cur].max)}`
                              : 'Optional'
                          }
                        />
                      </Stack>
                    </Stack>
                  </Grid>
                ))}
              </Grid>

              <Grid container spacing={1}>
                <Grid item xs={12} md={6}>
                  <TextField label="Payment Method" value="Balance (416)" disabled fullWidth size="small" />
                </Grid>
                <Grid item xs={12} md={6}>
                  <TextField
                    label="Remark"
                    value={remarkMarker}
                    onChange={(e) => setRemarkMarker(e.target.value)}
                    fullWidth
                    size="small"
                  />
                </Grid>
              </Grid>

              <Stack
                direction="row"
                spacing={1}
                flexWrap="wrap"
                useFlexGap
                sx={{ rowGap: 1 }}
              >
                {selectedTokens.map((tkn) => (
                  <Box
                    key={tkn}
                    sx={{
                      border: '1px solid',
                      borderColor: 'divider',
                      borderRadius: 1.5,
                      p: 1.25,
                      bgcolor: 'background.default',
                      width: 220,
                      flexShrink: 0,
                    }}
                  >
                    <Stack spacing={1}>
                      <Typography variant="subtitle2">{tkn}</Typography>
                      <TextField
                        label="BUY qty"
                        type="number"
                        value={Number(buyQuantityMap[tkn]) || ''}
                        onChange={(e) =>
                          setBuyQuantityMap((prev) => ({
                            ...prev,
                            [tkn]: Number(e.target.value),
                          }))
                        }
                        size="small"
                        fullWidth
                        helperText={`Range: ${formatNumber(buyRange[tkn]?.min)} - ${formatNumber(
                          buyRange[tkn]?.max,
                        )}`}
                        inputProps={{
                          min: buyRange[tkn]?.min || 0,
                          max: buyRange[tkn]?.max || 0,
                          step: '0.000001',
                        }}
                      />
                      <TextField
                        label="SELL qty"
                        value={SELL_QTY_FIXED[tkn]}
                        fullWidth
                        size="small"
                        disabled
                        helperText={`Uses balance, min ${SELL_QTY_FIXED[tkn]}`}
                      />
                    </Stack>
                  </Box>
                ))}
              </Stack>

              <Stack direction="row" justifyContent="flex-end" spacing={1.5}>
                <Button
                  variant="contained"
                  size="small"
                  onClick={handleSubmit}
                  disabled={
                    submitting ||
                    !accountId ||
                    selectedTokens.length === 0 ||
                    selectedFiats.length === 0
                  }
                >
                  {submitting ? 'Creating...' : 'Create All Ads'}
                </Button>
                <Button
                  variant="outlined"
                  size="small"
                  color="error"
                  onClick={handleDelete}
                  disabled={deleting || !accountId || !remarkMarker}
                >
                  {deleting ? 'Deleting...' : 'Delete by Remark'}
                </Button>
              </Stack>
            </Stack>
          </CardContent>
        </Card>
      ) : null}
    </Box>
  )
}

export default CreateAdPage
