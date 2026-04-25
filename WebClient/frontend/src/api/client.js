import axios from 'axios'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1',
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
