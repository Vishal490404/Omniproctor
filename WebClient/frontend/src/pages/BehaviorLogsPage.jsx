import { Button, Card, Group, Select, Stack, Table, Text, Title } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useEffect, useState } from 'react'

import { behaviorApi, testsApi } from '../api/services'
import { formatDateIST } from '../utils/time'

export function BehaviorLogsPage() {
  const [tests, setTests] = useState([])
  const [studentsForTest, setStudentsForTest] = useState([])
  const [selectedTest, setSelectedTest] = useState('')
  const [selectedStudent, setSelectedStudent] = useState('')
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(false)

  const getErrorMessage = (error, fallback = 'Try again') => {
    const detail = error?.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail.map((item) => item?.msg || JSON.stringify(item)).join(', ')
    }
    return fallback
  }

  useEffect(() => {
    async function loadTests() {
      try {
        const { data } = await testsApi.list(true)
        setTests(data)
      } catch (error) {
        notifications.show({ color: 'red', title: 'Failed to load tests', message: getErrorMessage(error) })
      }
    }
    loadTests()
  }, [])

  useEffect(() => {
    async function loadStudentsForTest() {
      if (!selectedTest) {
        setStudentsForTest([])
        setSelectedStudent('')
        return
      }

      try {
        const { data } = await testsApi.studentsForTest(selectedTest)
        setStudentsForTest(data)
      } catch (error) {
        notifications.show({ color: 'red', title: 'Failed to load students', message: getErrorMessage(error) })
      }
    }

    loadStudentsForTest()
  }, [selectedTest])

  const loadEvents = async () => {
    if (!selectedTest || !selectedStudent) {
      notifications.show({ color: 'orange', title: 'Selection required', message: 'Pick both test and student' })
      return
    }

    setLoading(true)
    try {
      const { data } = await behaviorApi.eventsForTestStudent(selectedTest, selectedStudent)
      setEvents(data)
    } catch (error) {
      notifications.show({ color: 'red', title: 'Failed to load logs', message: getErrorMessage(error) })
    } finally {
      setLoading(false)
    }
  }

  return (
    <Stack gap="lg">
      <div>
        <Title order={2}>Behavior Logs</Title>
        <Text size="sm" c="dimmed">View per-student, per-test behavior events from secure browser telemetry.</Text>
      </div>

      <Card className="surface-card" radius="lg" p="lg">
        <Group grow align="flex-end">
          <Select
            label="Test"
            value={selectedTest}
            onChange={(value) => setSelectedTest(value || '')}
            data={tests.map((item) => ({ value: String(item.id), label: item.name }))}
            placeholder="Select test"
          />
          <Select
            label="Student"
            value={selectedStudent}
            onChange={(value) => setSelectedStudent(value || '')}
            data={studentsForTest.map((item) => ({ value: String(item.student_id), label: `${item.full_name} (${item.email})` }))}
            placeholder="Select student"
          />
          <Button loading={loading} onClick={loadEvents}>Load logs</Button>
        </Group>
      </Card>

      <Card className="surface-card" radius="lg" p="lg">
        <Group justify="space-between" mb="sm">
          <Title order={4}>Event Timeline</Title>
          <Text size="sm" c="dimmed">{events.length} events</Text>
        </Group>

        <Table striped withTableBorder>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Time</Table.Th>
              <Table.Th>Type</Table.Th>
              <Table.Th>Severity</Table.Th>
              <Table.Th>Attempt</Table.Th>
              <Table.Th>Payload</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {events.length === 0 ? (
              <Table.Tr>
                <Table.Td colSpan={5}>No logs loaded yet.</Table.Td>
              </Table.Tr>
            ) : (
              events.map((event) => (
                <Table.Tr key={event.id}>
                  <Table.Td>{formatDateIST(event.event_time)}</Table.Td>
                  <Table.Td>{event.event_type}</Table.Td>
                  <Table.Td>{event.severity}</Table.Td>
                  <Table.Td>{event.attempt_id}</Table.Td>
                  <Table.Td>{event.payload ? JSON.stringify(event.payload) : '—'}</Table.Td>
                </Table.Tr>
              ))
            )}
          </Table.Tbody>
        </Table>
      </Card>
    </Stack>
  )
}
