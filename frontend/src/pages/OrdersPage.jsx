import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Grid,
  Stack,
  Tab,
  Tabs,
  Typography,
} from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'
import { apiGet, apiPost } from '../lib/apiClient'
import { useUserSession } from '../mui-templates/crud-dashboard/context/UserSessionContext'
import OrderCard from '../components/OrderCard'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import StopIcon from '@mui/icons-material/Stop'

function OrdersPage() {
  const { accessToken } = useUserSession()
  const [accounts, setAccounts] = useState([])
  const [selectedAccountId, setSelectedAccountId] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [procStatus, setProcStatus] = useState(null)
  const [procError, setProcError] = useState('')
  const [procBusy, setProcBusy] = useState(false)

  const selectedAccount = useMemo(() => {
    if (!selectedAccountId) {
      return accounts[0]
    }
    return accounts.find((account) => account.credential_id === selectedAccountId)
  }, [accounts, selectedAccountId])

  const fetchOrders = useCallback(async () => {
    if (!accessToken) return
    setError('')
    try {
      const data = await apiGet('/api/orders/pending', accessToken)
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

  const fetchProcStatus = useCallback(async () => {
    if (!accessToken) return
    try {
      const data = await apiGet('/api/order-processing/status', accessToken)
      setProcStatus(data)
      setProcError('')
    } catch (err) {
      setProcError(err.message)
    }
  }, [accessToken])

  useEffect(() => {
    if (!accessToken) return
    fetchOrders()
    fetchProcStatus()
  }, [accessToken, fetchOrders, fetchProcStatus])

  useEffect(() => {
    if (procStatus?.running !== true) return undefined
    const id = setInterval(() => {
      fetchProcStatus()
    }, 10000)
    return () => clearInterval(id)
  }, [procStatus?.running, fetchProcStatus])

  const handleRefresh = async () => {
    setRefreshing(true)
    await fetchOrders()
    await fetchProcStatus()
  }

  const handleProcToggle = async () => {
    if (!accessToken) return
    setProcBusy(true)
    setProcError('')
    try {
      const path = procStatus?.running ? '/api/order-processing/stop' : '/api/order-processing/start'
      await apiPost(path, {}, accessToken)
      await fetchProcStatus()
    } catch (err) {
      setProcError(err.message)
    } finally {
      setProcBusy(false)
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
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Typography variant="h4">Orders</Typography>
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="caption" color="text.secondary">
            Auto order processing
          </Typography>
          <Button
            variant="outlined"
            size="small"
            startIcon={procStatus?.running ? <StopIcon /> : <PlayArrowIcon />}
            onClick={handleProcToggle}
            disabled={procBusy}
          >
            {procStatus?.running ? 'Pause' : 'Start'}
          </Button>
          <Button
            startIcon={<RefreshIcon />}
            onClick={handleRefresh}
            disabled={refreshing}
          >
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </Button>
        </Stack>
      </Stack>
      <Typography variant="caption" color="text.secondary">
        {procStatus?.running ? 'Processing pending orders' : 'Processing paused'}
        {procStatus?.last_success_at
          ? ` · Last: ${new Date(procStatus.last_success_at).toLocaleString()}`
          : ''}
        {procStatus?.last_error ? ` · Error: ${procStatus.last_error}` : ''}
      </Typography>
      {error ? (
        <Alert severity="error" onClose={() => setError('')}>
          {error}
        </Alert>
      ) : null}
      {procError ? (
        <Alert severity="error" onClose={() => setProcError('')}>
          {procError}
        </Alert>
      ) : null}

      {accounts.length === 0 ? (
        <Card>
          <CardContent>
            <Typography color="text.secondary">
              No connected exchange accounts support pending orders yet.
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

            {selectedAccount ? (
              <>
                {selectedAccount.error ? (
                  <Alert severity="warning">{selectedAccount.error}</Alert>
                ) : null}
                {selectedAccount.orders.length === 0 ? (
                  <Typography color="text.secondary">
                    No pending orders for this account.
                  </Typography>
                ) : (
                  <Grid container spacing={2}>
                    {selectedAccount.orders.map((order, index) => (
                      <Grid
                        item
                        xs={12}
                        md={6}
                        key={
                          order.order_id ||
                          `${selectedAccount.credential_id}-${index}`
                        }
                      >
                        <OrderCard order={order} />
                      </Grid>
                    ))}
                  </Grid>
                )}
              </>
            ) : null}
          </CardContent>
        </Card>
      )}
    </Box>
  )
}

export default OrdersPage
