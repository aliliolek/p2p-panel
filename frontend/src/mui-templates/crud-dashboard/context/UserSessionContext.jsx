import { createContext, useContext } from 'react'

export const UserSessionContext = createContext({
  userEmail: '',
  accessToken: '',
  onSignOut: null,
})

export const useUserSession = () => useContext(UserSessionContext)
