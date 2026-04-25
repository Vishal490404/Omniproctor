import axios from 'axios'

// Resolve the API base URL with the following precedence:
//   1. window.__APP_CONFIG__.API_BASE_URL  - written at *container start* by
//      frontend/docker-entrypoint.sh from the API_BASE_URL env var. Lets one
//      built image be promoted across dev/staging/prod without rebuilding.
//   2. import.meta.env.VITE_API_BASE_URL    - baked at *build time* (handy
//      for `npm run dev` and standalone Vite builds).
//   3. http://localhost:8001/api/v1         - last-resort dev fallback.
const runtimeConfig =
  (typeof window !== 'undefined' && window.__APP_CONFIG__) || {}

export const API_BASE_URL =
  runtimeConfig.API_BASE_URL ||
  import.meta.env.VITE_API_BASE_URL ||
  'http://localhost:8001/api/v1'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
})

const AUTH_ROUTES = ['/auth/login', '/auth/register']
let authRedirectInProgress = false

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('wc_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status
    const requestUrl = String(error?.config?.url || '')
    const isAuthRequest = AUTH_ROUTES.some((route) => requestUrl.includes(route))

    if (status === 401 && !isAuthRequest && !authRedirectInProgress) {
      authRedirectInProgress = true
      localStorage.removeItem('wc_token')
      localStorage.removeItem('wc_user')

      if (window.location.pathname !== '/login') {
        window.location.replace('/login')
      }
    }

    return Promise.reject(error)
  },
)

export default apiClient
