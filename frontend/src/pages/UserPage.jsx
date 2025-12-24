import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Grid,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  FormControl,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import RefreshIcon from '@mui/icons-material/Refresh'
import DeleteIcon from '@mui/icons-material/Delete'
import { apiDelete, apiGet, apiPost } from '../lib/apiClient'
import { useUserSession } from '../mui-templates/crud-dashboard/context/UserSessionContext'

const statusColorMap = {
  active: 'success',
  pending: 'default',
  error: 'error',
}

const serializeResponse = (payload) => {
  if (!payload) {
    return ''
  }
  if (typeof payload === 'string') {
    return payload
  }
  try {
    return JSON.stringify(payload)
  } catch (error) {
    return ''
  }
}

const getStatusChipColor = (status) => statusColorMap[status] || 'default'

const defaultForm = {
  exchange: '',
  account_label: '',
  api_key: '',
  api_secret: '',
}

function UserPage() {
  const { accessToken } = useUserSession()
  const [serverInfo, setServerInfo] = useState({
    public_ip: '',
    ip_error: '',
    supported_exchanges: [],
  })
  const [credentials, setCredentials] = useState([])
  const [form, setForm] = useState(defaultForm)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [deletingId, setDeletingId] = useState('')
  const [lastUpdated, setLastUpdated] = useState(null)

  const preferredExchange = useMemo(() => {
    if (form.exchange) return form.exchange
    if (serverInfo.supported_exchanges?.length > 0) {
      return serverInfo.supported_exchanges[0]
    }
    return 'bybit'
  }, [form.exchange, serverInfo.supported_exchanges])

  const handleFormChange = (event) => {
    const { name, value } = event.target
    setForm((prev) => ({
      ...prev,
      [name]: value,
    }))
  }

  const fetchServerInfo = useCallback(async () => {
    const info = await apiGet('/api/info', accessToken)
    setServerInfo(info)
    setForm((prev) => ({
      ...prev,
      exchange: prev.exchange || info.supported_exchanges?.[0] || 'bybit',
    }))
  }, [accessToken])

  const fetchCredentials = useCallback(async () => {
    const result = await apiGet('/api/exchanges/credentials', accessToken)
    setCredentials(result.items || [])
    setLastUpdated(new Date())
  }, [accessToken])

  const loadInitialData = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      await Promise.all([fetchServerInfo(), fetchCredentials()])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [fetchServerInfo, fetchCredentials])

  useEffect(() => {
    if (!accessToken) return
    loadInitialData()
  }, [accessToken, loadInitialData])

  useEffect(() => {
    if (!accessToken) return
    const interval = setInterval(() => {
      fetchCredentials().catch(() => {})
    }, 30000)
    return () => clearInterval(interval)
  }, [accessToken, fetchCredentials])

  const handleCopyIp = async () => {
    if (!serverInfo.public_ip) return
    try {
      await navigator.clipboard.writeText(serverInfo.public_ip)
      setSuccess('IP address copied to clipboard.')
    } catch (err) {
      setError('Unable to copy IP address.')
    }
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    setSuccess('')
    try {
      await apiPost(
        '/api/exchanges/credentials',
        {
          ...form,
          exchange: form.exchange || preferredExchange,
        },
        accessToken,
      )
      setSuccess('Credentials saved. Verification will run shortly.')
      setForm((prev) => ({
        ...prev,
        api_key: '',
        api_secret: '',
      }))
      await fetchCredentials()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleRefresh = async () => {
    setError('')
    setSuccess('')
    try {
      await fetchCredentials()
    } catch (err) {
      setError(err.message)
    }
  }

  const handleDelete = async (credentialId) => {
    const confirmed = window.confirm(
      'Remove this exchange credential? This action cannot be undone.',
    )
    if (!confirmed) {
      return
    }
    setDeletingId(credentialId)
    setError('')
    setSuccess('')
    try {
      await apiDelete(`/api/exchanges/credentials/${credentialId}`, accessToken)
      setSuccess('Credential removed.')
      await fetchCredentials()
    } catch (err) {
      setError(err.message)
    } finally {
      setDeletingId('')
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
    <Box sx={{ p: 3, display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Stack spacing={2}>
        <Typography variant="h4">User</Typography>
        {error ? (
          <Alert severity="error" onClose={() => setError('')}>
            {error}
          </Alert>
        ) : null}
        {success ? (
          <Alert severity="success" onClose={() => setSuccess('')}>
            {success}
          </Alert>
        ) : null}
      </Stack>

      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary">
                Backend IP
              </Typography>
              <Stack
                direction="row"
                alignItems="center"
                justifyContent="space-between"
                spacing={1}
              >
                <Typography variant="h6">
                  {serverInfo.public_ip || 'Unavailable'}
                </Typography>
                <IconButton
                  aria-label="Copy IP"
                  onClick={handleCopyIp}
                  disabled={!serverInfo.public_ip}
                >
                  <ContentCopyIcon fontSize="small" />
                </IconButton>
              </Stack>
              <Typography variant="body2" color="text.secondary">
                Share this IP with Bybit (and other exchanges) to whitelist API
                requests coming from this backend.
              </Typography>
              {serverInfo.ip_error ? (
                <Alert
                  severity="warning"
                  sx={{ mt: 2 }}
                >{`Unable to determine IP automatically: ${serverInfo.ip_error}`}</Alert>
              ) : null}
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Add Exchange Account
            </Typography>
            <Box
              component="form"
              onSubmit={handleSubmit}
              sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}
            >
              <FormControl fullWidth>
                <InputLabel id="exchange-label">Exchange</InputLabel>
                <Select
                  labelId="exchange-label"
                  label="Exchange"
                  name="exchange"
                  value={form.exchange || preferredExchange}
                  onChange={handleFormChange}
                  required
                >
                  {(serverInfo.supported_exchanges || []).map((exchange) => (
                    <MenuItem key={exchange} value={exchange}>
                      {exchange.toUpperCase()}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <TextField
                label="Account label"
                name="account_label"
                value={form.account_label}
                onChange={handleFormChange}
                placeholder="Bybit JDG, Binance personal..."
                fullWidth
              />
              <TextField
                label="API key"
                name="api_key"
                value={form.api_key}
                onChange={handleFormChange}
                required
                fullWidth
              />
              <TextField
                label="API secret"
                name="api_secret"
                value={form.api_secret}
                onChange={handleFormChange}
                required
                fullWidth
                type="password"
              />
              <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
                <Button
                  variant="outlined"
                  startIcon={<RefreshIcon />}
                  onClick={handleRefresh}
                  type="button"
                >
                  Refresh status
                </Button>
                <Button
                  variant="contained"
                  type="submit"
                  disabled={submitting}
                >
                  {submitting ? 'Saving...' : 'Save'}
                </Button>
              </Box>
            </Box>
          </Paper>
        </Grid>
      </Grid>

      <Paper sx={{ p: 3 }}>
        <Stack
          direction={{ xs: 'column', md: 'row' }}
          justifyContent="space-between"
          alignItems={{ xs: 'flex-start', md: 'center' }}
          spacing={1}
          mb={2}
        >
          <Typography variant="h6">Connected Accounts</Typography>
          <Typography variant="body2" color="text.secondary">
            {lastUpdated
              ? `Last updated ${lastUpdated.toLocaleTimeString()}`
              : 'Not updated yet'}
          </Typography>
        </Stack>
        {credentials.length === 0 ? (
          <Typography color="text.secondary">
            You have not added any exchange accounts yet.
          </Typography>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Exchange</TableCell>
                <TableCell>Account</TableCell>
                <TableCell>API key</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Last check</TableCell>
                <TableCell>Response</TableCell>
                <TableCell align="center">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {credentials.map((credential) => (
                <TableRow key={credential.id}>
                  <TableCell sx={{ textTransform: 'capitalize' }}>
                    {credential.exchange}
                  </TableCell>
                  <TableCell>{credential.account_label || '—'}</TableCell>
                  <TableCell>{credential.api_key_preview}</TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={credential.status}
                      color={getStatusChipColor(credential.status)}
                    />
                  </TableCell>
                  <TableCell>
                    {credential.last_check_at
                      ? new Date(credential.last_check_at).toLocaleString()
                      : '—'}
                  </TableCell>
                  <TableCell sx={{ maxWidth: 280 }}>
                    <Typography
                      variant="body2"
                      sx={{
                        fontFamily: 'monospace',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {serializeResponse(credential.last_check_response)}
                    </Typography>
                  </TableCell>
                  <TableCell align="center">
                    <IconButton
                      color="error"
                      size="small"
                      aria-label="Delete credential"
                      onClick={() => handleDelete(credential.id)}
                      disabled={deletingId === credential.id}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Paper>
    </Box>
  )
}

export default UserPage
