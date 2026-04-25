import { Badge, Button, Card, Group, SimpleGrid, Stack, Text, Title } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useEffect, useState } from 'react'

import { attemptsApi, dashboardApi } from '../api/services'
import { buildKioskLaunchUrl } from '../utils/browserLaunch'
import { formatDateIST } from '../utils/time'

export function StudentDashboardPage() {
  const [tests, setTests] = useState([])

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
