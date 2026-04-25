import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import '@mantine/core/styles.css'
import '@mantine/notifications/styles.css'

import { AuthProvider } from './context/AuthContext'
import { ColorSchemeProvider, useColorSchemePreference } from './context/ColorSchemeContext'
import { theme } from './theme'
import { AppRouter } from './router'
import './styles.css'

function RootApp() {
  const { colorScheme } = useColorSchemePreference()

  return (
    <MantineProvider theme={theme} defaultColorScheme="light" forceColorScheme={colorScheme}>
      <Notifications />
      <BrowserRouter>
        <AuthProvider>
          <AppRouter />
        </AuthProvider>
      </BrowserRouter>
    </MantineProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ColorSchemeProvider>
      <RootApp />
    </ColorSchemeProvider>
  </React.StrictMode>,
)
