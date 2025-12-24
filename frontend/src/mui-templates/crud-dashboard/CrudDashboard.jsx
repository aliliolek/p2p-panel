import CssBaseline from '@mui/material/CssBaseline';
import PropTypes from 'prop-types';
import { createHashRouter, RouterProvider, Navigate } from 'react-router';
import DashboardLayout from './components/DashboardLayout';
import NotificationsProvider from './hooks/useNotifications/NotificationsProvider';
import DialogsProvider from './hooks/useDialogs/DialogsProvider';
import AppTheme from '../shared-theme/AppTheme';
import {
  dataGridCustomizations,
  datePickersCustomizations,
  sidebarCustomizations,
  formInputCustomizations,
} from './theme/customizations';
import { UserSessionContext } from './context/UserSessionContext';
import UserPage from '../../pages/UserPage';
import OrdersPage from '../../pages/OrdersPage';
import AdsPage from '../../pages/AdsPage';
import CreateAdPage from '../../pages/CreateAdPage';

const RedirectToUser = () => <Navigate to="/user" replace />;

const router = createHashRouter([
  {
    Component: DashboardLayout,
    children: [
      {
        index: true,
        Component: RedirectToUser,
      },
      {
        path: '/user',
        Component: UserPage,
      },
      {
        path: '/orders',
        Component: OrdersPage,
      },
      {
        path: '/ads',
        Component: AdsPage,
      },
      {
        path: '/create-ad',
        Component: CreateAdPage,
      },
      {
        path: '*',
        Component: RedirectToUser,
      },
    ],
  },
]);

const themeComponents = {
  ...dataGridCustomizations,
  ...datePickersCustomizations,
  ...sidebarCustomizations,
  ...formInputCustomizations,
};

export default function CrudDashboard(props) {
  const { session, onSignOut } = props;
  const userEmail = session?.user?.email ?? '';
  const accessToken = session?.access_token ?? '';
  return (
    <AppTheme {...props} themeComponents={themeComponents}>
      <CssBaseline enableColorScheme />
      <UserSessionContext.Provider
        value={{ userEmail, accessToken, onSignOut }}
      >
        <NotificationsProvider>
          <DialogsProvider>
            <RouterProvider router={router} />
          </DialogsProvider>
        </NotificationsProvider>
      </UserSessionContext.Provider>
    </AppTheme>
  );
}

CrudDashboard.propTypes = {
  onSignOut: PropTypes.func,
  session: PropTypes.shape({
    access_token: PropTypes.string,
    user: PropTypes.shape({
      email: PropTypes.string,
    }),
  }),
};
