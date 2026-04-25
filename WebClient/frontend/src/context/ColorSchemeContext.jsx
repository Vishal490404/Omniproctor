import { createContext, useContext, useMemo, useState } from 'react'

const ColorSchemeContext = createContext(null)
const COLOR_KEY = 'wc_color_scheme'

function loadColorScheme() {
  const saved = localStorage.getItem(COLOR_KEY)
  if (saved === 'dark' || saved === 'light') {
    return saved
  }
  return 'light'
}

export function ColorSchemeProvider({ children }) {
  const [colorScheme, setColorScheme] = useState(loadColorScheme)

  const toggleColorScheme = () => {
    const next = colorScheme === 'light' ? 'dark' : 'light'
    localStorage.setItem(COLOR_KEY, next)
    setColorScheme(next)
  }

  const value = useMemo(() => ({ colorScheme, toggleColorScheme }), [colorScheme])
  return <ColorSchemeContext.Provider value={value}>{children}</ColorSchemeContext.Provider>
}

export function useColorSchemePreference() {
  const context = useContext(ColorSchemeContext)
  if (!context) {
    throw new Error('useColorSchemePreference must be used within ColorSchemeProvider')
  }
  return context
}
