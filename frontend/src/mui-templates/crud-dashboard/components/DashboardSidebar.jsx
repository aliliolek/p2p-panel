import * as React from 'react'
import PropTypes from 'prop-types'
import { useTheme } from '@mui/material/styles'
import useMediaQuery from '@mui/material/useMediaQuery'
import Drawer from '@mui/material/Drawer'
import Toolbar from '@mui/material/Toolbar'
import List from '@mui/material/List'
import ListItemButton from '@mui/material/ListItemButton'
import ListItemIcon from '@mui/material/ListItemIcon'
import ListItemText from '@mui/material/ListItemText'
import PersonIcon from '@mui/icons-material/Person'
import ListAltIcon from '@mui/icons-material/ListAlt'
import StorefrontIcon from '@mui/icons-material/Storefront'
import { useLocation, useNavigate } from 'react-router'

const DRAWER_WIDTH = 260
const COLLAPSED_WIDTH = 80

const NAV_ITEMS = [
  {
    id: 'user',
    label: 'User',
    icon: <PersonIcon />,
    href: '/user',
  },
  {
    id: 'orders',
    label: 'Orders',
    icon: <ListAltIcon />,
    href: '/orders',
  },
  {
    id: 'ads',
    label: 'My Ads',
    icon: <StorefrontIcon />,
    href: '/ads',
  },
  {
    id: 'create-ad',
    label: 'Create Ad',
    icon: <StorefrontIcon />,
    href: '/create-ad',
  },
]

function DrawerContent({ collapsed, onNavigate, currentPath }) {
  return (
    <>
      <Toolbar />
      <List sx={{ flex: 1, px: collapsed ? 1 : 2 }}>
        {NAV_ITEMS.map((item) => (
          <ListItemButton
            key={item.id}
            selected={currentPath.startsWith(item.href)}
            onClick={() => onNavigate(item.href)}
            sx={{
              borderRadius: 2,
              mb: 0.5,
            }}
          >
            <ListItemIcon sx={{ minWidth: collapsed ? 0 : 40 }}>
              {item.icon}
            </ListItemIcon>
            <ListItemText
              primary={item.label}
              sx={{
                opacity: collapsed ? 0 : 1,
                transition: 'opacity 0.2s ease',
              }}
            />
          </ListItemButton>
        ))}
      </List>
    </>
  )
}

DrawerContent.propTypes = {
  collapsed: PropTypes.bool.isRequired,
  currentPath: PropTypes.string.isRequired,
  onNavigate: PropTypes.func.isRequired,
}

export default function DashboardSidebar({
  expanded = true,
  setExpanded,
  container,
}) {
  const theme = useTheme()
  const isMdUp = useMediaQuery(theme.breakpoints.up('md'))
  const location = useLocation()
  const navigate = useNavigate()

  const collapsed = isMdUp ? !expanded : false
  const drawerWidth = collapsed ? COLLAPSED_WIDTH : DRAWER_WIDTH

  const handleNavigate = React.useCallback(
    (href) => {
      navigate(href)
      if (!isMdUp) {
        setExpanded(false)
      }
    },
    [navigate, isMdUp, setExpanded],
  )

  const sharedSx = {
    width: drawerWidth,
    flexShrink: 0,
    [`& .MuiDrawer-paper`]: {
      width: drawerWidth,
      boxSizing: 'border-box',
      borderRight: '1px solid',
      borderColor: 'divider',
    },
  }

  return (
    <>
      <Drawer
        container={container}
        variant="temporary"
        open={!isMdUp && expanded}
        onClose={() => setExpanded(false)}
        ModalProps={{
          keepMounted: true,
        }}
        sx={{
          display: { xs: 'block', md: 'none' },
          ...sharedSx,
        }}
      >
        <DrawerContent
          collapsed={false}
          onNavigate={handleNavigate}
          currentPath={location.pathname}
        />
      </Drawer>
      <Drawer
        variant="permanent"
        open
        sx={{
          display: { xs: 'none', md: 'block' },
          ...sharedSx,
        }}
      >
        <DrawerContent
          collapsed={collapsed}
          onNavigate={handleNavigate}
          currentPath={location.pathname}
        />
      </Drawer>
    </>
  )
}

DashboardSidebar.propTypes = {
  container: (props, propName) => {
    if (props[propName] == null) {
      return null
    }
    if (typeof props[propName] !== 'object' || props[propName].nodeType !== 1) {
      return new Error(`Expected prop '${propName}' to be of type Element`)
    }
    return null
  },
  expanded: PropTypes.bool,
  setExpanded: PropTypes.func.isRequired,
}
