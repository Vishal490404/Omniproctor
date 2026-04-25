import {
  Button,
  Card,
  Group,
  NumberInput,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Textarea,
  Title,
} from '@mantine/core'
import { IconWorldWww } from '@tabler/icons-react'
import { notifications } from '@mantine/notifications'
import { useEffect, useState } from 'react'

import { testsApi } from '../api/services'
import { buildKioskLaunchUrl, normalizeTestUrl } from '../utils/browserLaunch'
import { formatDateIST, getTestStatus, toLocalDateTimeInputValue, toUtcIsoFromLocalDateTime } from '../utils/time'

export function TestsPage() {
  const [tests, setTests] = useState([])
  const [loading, setLoading] = useState(false)
  const [includeInactive, setIncludeInactive] = useState(true)
  const [editingTestId, setEditingTestId] = useState(null)
  const [form, setForm] = useState({
    name: '',
    description: '',
    external_link: '',
    is_active: true,
    max_attempts: 1,
    start_time: '',
    end_time: '',
  })

  const getErrorMessage = (error, fallback = 'Try again') => {
    const detail = error?.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail.map((item) => item?.msg || JSON.stringify(item)).join(', ')
    }
    return fallback
  }

  const getCalculatedDuration = () => {
    if (!form.start_time || !form.end_time) return 'Select start and end time'

    const start = new Date(form.start_time)
    const end = new Date(form.end_time)
    const diffMs = end.getTime() - start.getTime()

    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || diffMs <= 0) {
      return 'Invalid time range'
    }

    const totalMinutes = Math.floor(diffMs / 60000)
    const hours = Math.floor(totalMinutes / 60)
    const minutes = totalMinutes % 60

    if (hours === 0) return `${minutes} min`
    if (minutes === 0) return `${hours} hr`
    return `${hours} hr ${minutes} min`
  }

  async function loadTests() {
    setLoading(true)
    try {
      const { data } = await testsApi.list(includeInactive)
      setTests(data)
    } catch (error) {
      notifications.show({ color: 'red', title: 'Failed to load tests', message: getErrorMessage(error) })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadTests()
  }, [includeInactive])

  const createTest = async () => {
    if (!form.name || !form.external_link || !form.start_time || !form.end_time) {
      notifications.show({ color: 'orange', title: 'Missing fields', message: 'Name, link, start time, and end time are required' })
      return
    }

    if (new Date(form.end_time) <= new Date(form.start_time)) {
      notifications.show({ color: 'orange', title: 'Invalid time range', message: 'End time must be after start time' })
      return
    }

    try {
      const payload = {
        ...form,
        external_link: normalizeTestUrl(form.external_link),
        start_time: toUtcIsoFromLocalDateTime(form.start_time),
        end_time: toUtcIsoFromLocalDateTime(form.end_time),
      }
      await testsApi.create(payload)
      notifications.show({ color: 'teal', title: 'Test created', message: 'New test added successfully' })
      setForm({ name: '', description: '', external_link: '', is_active: true, max_attempts: 1, start_time: '', end_time: '' })
      loadTests()
    } catch (error) {
      notifications.show({ color: 'red', title: 'Create failed', message: getErrorMessage(error) })
    }
  }

  const beginEdit = (item) => {
    setEditingTestId(item.id)
    setForm({
      name: item.name || '',
      description: item.description || '',
      external_link: item.external_link || '',
      is_active: Boolean(item.is_active),
      max_attempts: item.max_attempts || 1,
      start_time: toLocalDateTimeInputValue(item.start_time),
      end_time: toLocalDateTimeInputValue(item.end_time),
    })
  }

  const resetForm = () => {
    setEditingTestId(null)
    setForm({ name: '', description: '', external_link: '', is_active: true, max_attempts: 1, start_time: '', end_time: '' })
  }

  const saveTest = async () => {
    if (editingTestId) {
      if (!form.name || !form.external_link || !form.start_time || !form.end_time) {
        notifications.show({ color: 'orange', title: 'Missing fields', message: 'Name, link, start time, and end time are required' })
        return
      }

      if (new Date(form.end_time) <= new Date(form.start_time)) {
        notifications.show({ color: 'orange', title: 'Invalid time range', message: 'End time must be after start time' })
        return
      }

      try {
        const payload = {
          ...form,
          external_link: normalizeTestUrl(form.external_link),
          start_time: toUtcIsoFromLocalDateTime(form.start_time),
          end_time: toUtcIsoFromLocalDateTime(form.end_time),
        }
        await testsApi.update(editingTestId, payload)
        notifications.show({ color: 'teal', title: 'Test updated', message: 'Test changes saved successfully' })
        resetForm()
        loadTests()
      } catch (error) {
        notifications.show({ color: 'red', title: 'Update failed', message: getErrorMessage(error) })
      }
      return
    }

    return createTest()
  }

  return (
    <Stack gap="lg" className="teacher-page">
      <Group justify="space-between" align="flex-end" className="panel-header">
        <div className="page-intro">
          <Title order={2}>Tests</Title>
          <Text size="sm" c="dimmed">Create assessments and control when students can see them.</Text>
        </div>
        <Switch
          className="teacher-toggle"
          checked={includeInactive}
          onChange={(event) => setIncludeInactive(event.currentTarget.checked)}
          label="Include inactive"
        />
      </Group>

      <Card className="surface-card teacher-panel" radius="lg" p="lg">
        <Group justify="space-between" mb="sm">
          <Title order={4}>{editingTestId ? 'Edit Test' : 'Create Test'}</Title>
          {editingTestId && (
            <Button variant="subtle" color="gray" onClick={resetForm}>
              Cancel edit
            </Button>
          )}
        </Group>
        <SimpleGrid cols={{ base: 1, md: 2 }} mt="md" className="teacher-form-grid">
          <TextInput
            label="Test name"
            placeholder="Data Structures Midterm"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.currentTarget.value })}
          />
          <TextInput
            label="External link"
            leftSection={<IconWorldWww size={14} />}
            placeholder="https://..."
            value={form.external_link}
            onChange={(e) => setForm({ ...form, external_link: e.currentTarget.value })}
          />
          <TextInput
            label="Start time"
            type="datetime-local"
            value={form.start_time}
            onChange={(e) => setForm({ ...form, start_time: e.currentTarget.value })}
          />
          <TextInput
            label="End time"
            type="datetime-local"
            value={form.end_time}
            onChange={(e) => setForm({ ...form, end_time: e.currentTarget.value })}
          />
          <TextInput
            label="Calculated duration"
            value={getCalculatedDuration()}
            readOnly
            className="readonly-field"
          />
          <Switch
            label="Enable test"
            description="Students can access this test only when enabled and within the selected time range."
            checked={form.is_active}
            onChange={(event) => setForm({ ...form, is_active: event.currentTarget.checked })}
            mt={30}
          />
          <NumberInput
            label="Attempt limit"
            description="1 = single attempt. Set >1 to allow multiple attempts."
            min={1}
            value={form.max_attempts}
            onChange={(value) => setForm({ ...form, max_attempts: Number(value) || 1 })}
          />
          <Textarea
            label="Description"
            placeholder="Include exam rules, duration, and attempt policy"
            autosize
            minRows={3}
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.currentTarget.value })}
          />
        </SimpleGrid>
        <Group justify="flex-end" mt="md">
          <Button variant="light" onClick={resetForm}>
            Reset
          </Button>
          <Button onClick={saveTest}>{editingTestId ? 'Save changes' : 'Create test'}</Button>
        </Group>
      </Card>

      <Card className="surface-card teacher-panel" radius="lg" p="lg">
        <Group justify="space-between" mb="sm" className="panel-header">
          <Title order={4}>Existing Tests</Title>
          <Text size="sm" c="dimmed">{loading ? 'Loading...' : `${tests.length} tests`}</Text>
        </Group>
        <div className="table-shell">
          <Table striped highlightOnHover withTableBorder>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Attempts</Table.Th>
                <Table.Th>Window</Table.Th>
                <Table.Th>Link</Table.Th>
                <Table.Th>Action</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {tests.length === 0 ? (
                <Table.Tr>
                  <Table.Td colSpan={6}>No tests yet. Create your first test above.</Table.Td>
                </Table.Tr>
              ) : (
                tests.map((item) => (
                  <Table.Tr key={item.id}>
                    <Table.Td>{item.name}</Table.Td>
                    <Table.Td>{getTestStatus(item)}</Table.Td>
                    <Table.Td>{item.max_attempts === 1 ? 'Single' : `${item.max_attempts} max`}</Table.Td>
                    <Table.Td>
                      {formatDateIST(item.start_time)} - {formatDateIST(item.end_time)}
                    </Table.Td>
                    <Table.Td>
                      {buildKioskLaunchUrl(item.external_link) ? (
                        <Button
                          component="a"
                          href={buildKioskLaunchUrl(item.external_link)}
                          size="xs"
                          variant="light"
                        >
                          Open in kiosk browser
                        </Button>
                      ) : (
                        <Text size="sm" c="dimmed">Invalid link</Text>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <Button size="xs" variant="light" onClick={() => beginEdit(item)}>
                        Edit
                      </Button>
                    </Table.Td>
                  </Table.Tr>
                ))
              )}
            </Table.Tbody>
          </Table>
        </div>
      </Card>
    </Stack>
  )
}
