import apiClient from './client'

export const authApi = {
  register: (payload) => apiClient.post('/auth/register', payload),
  login: (payload) => apiClient.post('/auth/login', payload),
}

export const testsApi = {
  list: (includeInactive = true) => apiClient.get(`/tests?include_inactive=${includeInactive}`),
  create: (payload) => apiClient.post('/tests', payload),
  update: (id, payload) => apiClient.patch(`/tests/${id}`, payload),
  studentsForTest: (id) => apiClient.get(`/tests/${id}/students`),
  assignStudent: (testId, studentId, payload = {}) =>
    apiClient.post(`/tests/${testId}/students/${studentId}`, payload),
  removeStudent: (testId, studentId) => apiClient.delete(`/tests/${testId}/students/${studentId}`),
  bulkAssignByEmail: (testId, payload) =>
    apiClient.post(`/tests/${testId}/students/bulk-email`, payload),
}

export const attemptsApi = {
  start: (testId) => apiClient.post(`/tests/${testId}/attempts/start`),
  end: (testId, payload = {}) => apiClient.post(`/tests/${testId}/attempts/end`, payload),
  mine: (testId) => apiClient.get(`/tests/${testId}/attempts/me`),
  listForStudent: (testId, studentId) => apiClient.get(`/tests/${testId}/students/${studentId}/attempts`),
  summaryForStudent: (testId, studentId) => apiClient.get(`/tests/${testId}/students/${studentId}/attempt-summary`),
}

export const behaviorApi = {
  logEvent: (attemptId, payload) => apiClient.post(`/behavior/attempts/${attemptId}/events`, payload),
  eventsForAttempt: (attemptId) => apiClient.get(`/behavior/attempts/${attemptId}/events`),
  eventsForTestStudent: (testId, studentId) => apiClient.get(`/behavior/tests/${testId}/students/${studentId}/events`),
}

export const usersApi = {
  students: () => apiClient.get('/users/students'),
}

export const dashboardApi = {
  myTests: () => apiClient.get('/dashboard/me/tests'),
}

export const downloadsApi = {
  getManifest: () => apiClient.get('/downloads/manifest'),
  // Streams the installer as a Blob. The Bearer token is attached by the
  // axios request interceptor in client.js so we don't have to set it here.
  downloadInstaller: (platform = 'windows', onProgress) =>
    apiClient.get(`/downloads/installer/${platform}`, {
      responseType: 'blob',
      onDownloadProgress: onProgress,
    }),
}

/** Trigger a browser save-as dialog for an axios blob response. */
export function saveBlobResponse(response, fallbackFilename = 'download.bin') {
  const disposition = response?.headers?.['content-disposition'] || ''
  let filename = fallbackFilename
  const match = /filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i.exec(disposition)
  if (match) {
    filename = decodeURIComponent(match[1] || match[2] || fallbackFilename).trim()
  }
  const blob = new Blob([response.data], { type: 'application/octet-stream' })
  const url = window.URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  // Defer revoke so Safari/Edge actually finish the download.
  setTimeout(() => window.URL.revokeObjectURL(url), 1500)
}
