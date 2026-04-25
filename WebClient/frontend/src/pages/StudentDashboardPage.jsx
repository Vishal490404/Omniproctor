import { Alert, Badge, Button, Card, Group, SimpleGrid, Stack, Text, Title } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconDownload } from '@tabler/icons-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { attemptsApi, dashboardApi } from '../api/services'
import { buildKioskLaunchUrl } from '../utils/browserLaunch'
import { formatDateIST } from '../utils/time'

export function StudentDashboardPage() {
  const [tests, setTests] = useState([])
  const [showInstallBanner, setShowInstallBanner] = useState(false)
  const probeAttemptedRef = useRef(false)

  async function loadMyTests() {
    try {
      const { data } = await dashboardApi.myTests()
      setTests(data)
    } catch (error) {
      notifications.show({ color: 'red', title: 'Failed to load', message: error?.response?.data?.detail || 'Try again' })
    }
  }

  useEffect(() => {
    loadMyTests()
  }, [])

  // Best-effort detection: launch a hidden iframe with the kiosk protocol; if
  // the page never loses focus within 1.5 s, the protocol handler is almost
  // certainly not registered -> show the install banner.
  useEffect(() => {
    if (probeAttemptedRef.current) return
    probeAttemptedRef.current = true
    let timer = null
    let focusLostAt = null
    const handleBlur = () => {
      focusLostAt = Date.now()
    }
    const handleFocus = () => {
      // If the OS handed focus to the kiosk handler, we're done.
      if (focusLostAt) {
        clearTimeout(timer)
        setShowInstallBanner(false)
      }
    }
    window.addEventListener('blur', handleBlur)
    window.addEventListener('focus', handleFocus)
    let iframe = null
    try {
      iframe = document.createElement('iframe')
      iframe.style.display = 'none'
      iframe.src = 'omniproctor-browser://ping'
      document.body.appendChild(iframe)
    } catch {
      setShowInstallBanner(true)
    }
    timer = setTimeout(() => {
      if (!focusLostAt && document.hasFocus()) {
        setShowInstallBanner(true)
      }
      try {
        if (iframe?.parentNode) iframe.parentNode.removeChild(iframe)
      } catch {
        // ignore
      }
    }, 1500)
    return () => {
      clearTimeout(timer)
      window.removeEventListener('blur', handleBlur)
      window.removeEventListener('focus', handleFocus)
    }
  }, [])

  const launchKiosk = async (item) => {
    if (!item.can_attempt) {
      notifications.show({ color: 'orange', title: 'Attempt limit reached', message: 'No attempts remaining for this test.' })
      return
    }

    try {
      await attemptsApi.start(item.id)
      const launchUrl = buildKioskLaunchUrl(item.external_link)
      if (!launchUrl) {
        notifications.show({ color: 'red', title: 'Invalid test link', message: 'This test link is not valid.' })
        return
      }
      window.location.href = launchUrl
    } catch (error) {
      notifications.show({ color: 'red', title: 'Unable to start attempt', message: error?.response?.data?.detail || 'Try again' })
    }
  }

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <Stack gap={2}>
          <Title order={2}>My Assigned Tests</Title>
          <Text size="sm" c="dimmed">Launch your exam securely in the kiosk browser.</Text>
        </Stack>
        <Badge color="teal" size="lg" variant="light">{tests.length} assigned</Badge>
      </Group>

      {showInstallBanner && (
        <Alert
          color="orange"
          icon={<IconDownload size={16} />}
          title="Kiosk browser not detected"
          withCloseButton
          onClose={() => setShowInstallBanner(false)}
        >
          <Text size="sm" mb="xs">
            We couldn&apos;t find the OmniProctor secure kiosk browser on this
            device. Install it once to take exams.
          </Text>
          <Button
            component={Link}
            to="/student/downloads"
            size="xs"
            leftSection={<IconDownload size={14} />}
          >
            Download kiosk browser
          </Button>
        </Alert>
      )}

      {tests.length === 0 && (
        <Card className="surface-card" radius="lg" p="xl">
          <Stack gap={6}>
            <Title order={4}>No tests assigned yet</Title>
            <Text c="dimmed">Your teacher has not assigned any tests. Check back later.</Text>
          </Stack>
        </Card>
      )}

      <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="lg">
        {tests.map((item) => (
          <Card key={item.id} className="surface-card student-test-card" radius="lg" p="lg">
            <Stack gap={4}>
              <Title order={3}>{item.name}</Title>
              <Text c="dimmed">{item.description || 'No description available'}</Text>
            </Stack>

            <Stack gap={8} mt="md">
              <Text size="sm" c="dimmed">
                Window: {formatDateIST(item.start_time)} - {formatDateIST(item.end_time)}
              </Text>
              <Text size="sm" c="dimmed">
                Attempts: {item.attempts_used}/{item.max_attempts} used
              </Text>
              <Group justify="space-between" align="center" mt={2}>
                <Badge color={item.is_active ? 'teal' : 'gray'}>{item.is_active ? 'Active' : 'Inactive'}</Badge>
                <Badge color={item.can_attempt ? 'blue' : 'red'}>{item.can_attempt ? `${item.attempts_remaining} remaining` : 'Limit reached'}</Badge>
              </Group>

              <Group justify="flex-start" align="center" mt="xs">
                {buildKioskLaunchUrl(item.external_link) ? (
                  <Button className="kiosk-btn" size="sm" variant="light" onClick={() => launchKiosk(item)} disabled={!item.can_attempt}>
                    Open in kiosk browser
                  </Button>
                ) : (
                  <Text size="sm" c="dimmed">Invalid link</Text>
                )}
              </Group>
            </Stack>
          </Card>
        ))}
      </SimpleGrid>
    </Stack>
  )
}
