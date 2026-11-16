import { createContext, useContext } from 'react'
import type { SessionInfo } from '../lib/api'

export interface authContextValue {
  status: 'loading' | 'ready'
  online: boolean
  session: SessionInfo | null
  login: (stationCode: string, employeeCode: string, pin: string) => Promise<void>
  logout: () => Promise<void>
  recheckConnection: () => Promise<boolean>
}

export const authContext = createContext<authContextValue>({
  status: 'loading',
  online: false,
  session: null,
  login: async () => {},
  logout: async () => {},
  recheckConnection: async () => false,
})

export function useAuth(): authContextValue {
  return useContext(authContext)
}
