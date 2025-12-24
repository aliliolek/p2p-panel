import { useEffect, useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
import CssBaseline from '@mui/material/CssBaseline'
import Grid from '@mui/material/Grid'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import CrudDashboard from './mui-templates/crud-dashboard/CrudDashboard'
import AppTheme from './mui-templates/shared-theme/AppTheme'
import { supabase } from './lib/supabaseClient'

function AuthShell({ children }) {
  return (
    <AppTheme>
      <CssBaseline enableColorScheme />
      {children}
    </AppTheme>
  )
}

function SignInScreen({ onSignIn, error }) {
  return (
    <Grid container sx={{ minHeight: '100vh' }}>
      <Grid
        item
        xs={12}
        md={6}
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          px: { xs: 3, sm: 6 },
          py: { xs: 6, sm: 8 },
          bgcolor: 'background.default',
        }}
      >
        <Paper
          elevation={3}
          sx={{
            width: '100%',
            maxWidth: 420,
            p: { xs: 3, sm: 4 },
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
          }}
        >
          <Typography variant="h4" component="h1">
            Welcome back
          </Typography>
          <Typography color="text.secondary">
            Sign in with Google to access your dashboard.
          </Typography>
          <Button variant="contained" size="large" onClick={onSignIn}>
            Sign in with Google
          </Button>
          {error ? (
            <Typography color="error" variant="body2">
              {error}
            </Typography>
          ) : null}
        </Paper>
      </Grid>
      <Grid
        item
        xs={false}
        md={6}
        sx={{
          display: { xs: 'none', md: 'block' },
          backgroundImage: 'linear-gradient(135deg, #0B6BCB, #4B93F7)',
          color: '#fff',
        }}
      >
        <Box
          sx={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            px: 6,
            textAlign: 'center',
            gap: 2,
          }}
        >
          <Typography variant="h3" sx={{ fontWeight: 600 }}>
            P2P Panel
          </Typography>
          <Typography variant="h6" sx={{ maxWidth: 360 }}>
            Manage your workflows effortlessly with our CRUD dashboard template.
          </Typography>
        </Box>
      </Grid>
    </Grid>
  )
}

function App() {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const loadSession = async () => {
      const { data, error } = await supabase.auth.getSession()
      if (error) {
        setError(error.message)
      } else {
        setSession(data.session)
      }
      setLoading(false)
    }

    loadSession()

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession)
      setLoading(false)
    })

    return () => subscription.unsubscribe()
  }, [])

  const signInWithGoogle = async () => {
    setError('')
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: window.location.origin,
      },
    })

    if (error) {
      setError(error.message)
    }
  }

  const signOut = async () => {
    setError('')
    const { error } = await supabase.auth.signOut()
    if (error) {
      setError(error.message)
    }
  }

  if (loading) {
    return (
      <AuthShell>
        <Box
          sx={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            bgcolor: 'background.default',
          }}
        >
          <CircularProgress />
        </Box>
      </AuthShell>
    )
  }

  if (!session) {
    return (
      <AuthShell>
        <SignInScreen onSignIn={signInWithGoogle} error={error} />
      </AuthShell>
    )
  }

  return <CrudDashboard session={session} onSignOut={signOut} />
}

export default App
