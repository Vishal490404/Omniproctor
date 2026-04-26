import {
  Badge,
  Button,
  Card,
  Group,
  Select,
  Stack,
  Table,
  Tabs,
  Text,
  TextInput,
  Textarea,
  Title,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconActivity } from '@tabler/icons-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { testsApi, usersApi } from '../api/services'

export function StudentsPage() {
  const [students, setStudents] = useState([])
  const [tests, setTests] = useState([])
  const [activeTab, setActiveTab] = useState('single')
  const [selectedStudent, setSelectedStudent] = useState('')
  const [selectedTest, setSelectedTest] = useState('')
  const [bulkEmails, setBulkEmails] = useState('')
  const [bulkResult, setBulkResult] = useState(null)
  const [assignedStudents, setAssignedStudents] = useState([])
  const [assignedSearch, setAssignedSearch] = useState('')
  const [loadingAssigned, setLoadingAssigned] = useState(false)
  const [copySourceTest, setCopySourceTest] = useState('')
  const [copyTargetTest, setCopyTargetTest] = useState('')
  const [copyLoading, setCopyLoading] = useState(false)
  const [copySummary, setCopySummary] = useState(null)

  const navigate = useNavigate()

  const getErrorMessage = (error, fallback = 'Try again') => {
    const detail = error?.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail
        .map((item) => item?.msg || JSON.stringify(item))
        .join(', ')
    }
    return fallback
  }

  async function loadData() {
    try {
      const [studentsResp, testsResp] = await Promise.all([
        usersApi.students(),
        testsApi.list(true),
      ])
      setStudents(studentsResp.data)
      setTests(testsResp.data)
    } catch (error) {
      notifications.show({ color: 'red', title: 'Load failed', message: getErrorMessage(error) })
    }
  }

  async function loadAssignedStudents() {
    if (!selectedTest) {
      setAssignedStudents([])
      return
    }

    setLoadingAssigned(true)
    try {
      const { data } = await testsApi.studentsForTest(selectedTest)
      setAssignedStudents(data)
    } catch (error) {
      notifications.show({ color: 'red', title: 'Failed to load assignments', message: getErrorMessage(error) })
    } finally {
      setLoadingAssigned(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  useEffect(() => {
    loadAssignedStudents()
  }, [selectedTest])

  useEffect(() => {
    setBulkResult(null)
    setCopySummary(null)
  }, [activeTab, selectedTest])

  const assign = async () => {
    if (!selectedStudent || !selectedTest) {
      notifications.show({ color: 'orange', title: 'Selection required', message: 'Pick test and student' })
      return
    }

    try {
      await testsApi.assignStudent(selectedTest, selectedStudent)
      notifications.show({ color: 'teal', title: 'Assigned', message: 'Student added to test' })
      loadAssignedStudents()
    } catch (error) {
      notifications.show({ color: 'red', title: 'Assignment failed', message: getErrorMessage(error) })
    }
  }

  const bulkAssign = async () => {
    if (!selectedTest) {
      notifications.show({ color: 'orange', title: 'Select test', message: 'Pick a test first' })
      return
    }

    const emails = bulkEmails
      .split(/[\n,;]+/)
      .map((item) => item.trim())
      .filter(Boolean)

    if (emails.length === 0) {
      notifications.show({ color: 'orange', title: 'No emails found', message: 'Add at least one email' })
      return
    }

    try {
      const { data } = await testsApi.bulkAssignByEmail(selectedTest, { emails })
      setBulkResult(data)
      notifications.show({
        color: data.summary.failed > 0 ? 'yellow' : 'teal',
        title: 'Bulk assignment finished',
        message: `${data.summary.assigned} assigned, ${data.summary.failed} failed`,
      })
      loadAssignedStudents()
    } catch (error) {
      notifications.show({ color: 'red', title: 'Bulk assignment failed', message: getErrorMessage(error) })
    }
  }

  const removeStudent = async (studentId) => {
    if (!selectedTest) return

    const proceed = window.confirm('Remove this student from the selected test?')
    if (!proceed) return

    try {
      await testsApi.removeStudent(selectedTest, studentId)
      notifications.show({ color: 'teal', title: 'Removed', message: 'Student removed from test' })
      loadAssignedStudents()
    } catch (error) {
      notifications.show({ color: 'red', title: 'Removal failed', message: getErrorMessage(error) })
    }
  }

  const copyParticipants = async () => {
    if (!copySourceTest || !copyTargetTest) {
      notifications.show({ color: 'orange', title: 'Selection required', message: 'Choose both source and target tests' })
      return
    }

    if (copySourceTest === copyTargetTest) {
      notifications.show({ color: 'orange', title: 'Invalid selection', message: 'Source and target tests must be different' })
      return
    }

    setCopyLoading(true)
    try {
      const { data: sourceParticipants } = await testsApi.studentsForTest(copySourceTest)
      const results = []
      let copied = 0
      let skipped = 0

      for (const participant of sourceParticipants) {
        try {
          await testsApi.assignStudent(copyTargetTest, participant.student_id)
          copied += 1
          results.push({ email: participant.email, status: 'copied', message: 'Added to target test' })
        } catch (error) {
          skipped += 1
          results.push({
            email: participant.email,
            status: 'skipped',
            message: error?.response?.data?.detail || 'Could not copy participant',
          })
        }
      }

      const summary = { copied, skipped, total: sourceParticipants.length }
      setCopySummary({ summary, results })
      notifications.show({
        color: skipped > 0 ? 'yellow' : 'teal',
        title: 'Copy finished',
        message: `${copied} copied, ${skipped} skipped`,
      })
      if (String(copyTargetTest) === String(selectedTest)) {
        loadAssignedStudents()
      }
    } catch (error) {
      notifications.show({ color: 'red', title: 'Copy failed', message: getErrorMessage(error) })
    } finally {
      setCopyLoading(false)
    }
  }

  const openStudentLogs = (student) => {
    if (!selectedTest || !student?.student_id) return
    const params = new URLSearchParams({
      testId: String(selectedTest),
      studentId: String(student.student_id),
    })
    navigate(`/portal/logs?${params.toString()}`)
  }

  const filteredAssignedStudents = useMemo(() => {
    return assignedStudents.filter((item) => {
      const haystack = `${item.full_name} ${item.email}`.toLowerCase()
      return haystack.includes(assignedSearch.trim().toLowerCase())
    })
  }, [assignedStudents, assignedSearch])

  const selectedTestName = tests.find((item) => String(item.id) === String(selectedTest))?.name || 'Selected test'

  return (
    <Stack gap="lg" className="teacher-page">
      <div className="page-intro">
        <Title order={2}>Students</Title>
        <Text size="sm" c="dimmed">Assign and manage students with clear workflows, attempt limits, and behavior logs.</Text>
      </div>

      <Card className="surface-card teacher-panel" radius="lg" p="lg">
        <Group mt="xs" grow align="flex-end">
          <Select
            label="Working test"
            value={selectedTest}
            onChange={(value) => setSelectedTest(value || '')}
            data={tests.map((item) => ({ value: String(item.id), label: item.name }))}
            placeholder="Select test"
          />
        </Group>

        <Group mt="sm" gap="sm">
          <Badge variant="light" color="teal">{students.length} registered</Badge>
          <Badge variant="light" color="blue">{assignedStudents.length} assigned</Badge>
          {selectedTest && <Badge variant="light" color="gray">Working on: {selectedTestName}</Badge>}
        </Group>

        <Tabs value={activeTab} onChange={(value) => setActiveTab(value || 'single')} mt="lg" className="teacher-tabs">
          <Tabs.List>
            <Tabs.Tab value="single">Single assign</Tabs.Tab>
            <Tabs.Tab value="bulk">Bulk assign</Tabs.Tab>
            <Tabs.Tab value="copy">Copy participants</Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="single" pt="md">
            <Group grow align="flex-end">
              <Select
                label="Student"
                value={selectedStudent}
                onChange={(value) => setSelectedStudent(value || '')}
                data={students.map((item) => ({ value: String(item.id), label: `${item.full_name} (${item.email})` }))}
              />
              <Button onClick={assign}>Assign student</Button>
            </Group>
          </Tabs.Panel>

          <Tabs.Panel value="bulk" pt="md">
            <Stack>
              <Text size="sm" c="dimmed">
                Paste emails separated by comma or new lines. Unknown emails will be listed as failed.
              </Text>
              <Textarea
                label="Student emails"
                minRows={5}
                autosize
                placeholder="student1@school.edu, student2@school.edu"
                value={bulkEmails}
                onChange={(e) => setBulkEmails(e.currentTarget.value)}
              />
              <Group justify="flex-end">
                <Button variant="light" onClick={() => { setBulkEmails(''); setBulkResult(null) }}>Clear</Button>
                <Button onClick={bulkAssign}>Assign by email list</Button>
              </Group>
            </Stack>
          </Tabs.Panel>

          <Tabs.Panel value="copy" pt="md">
            <Stack>
              <Text size="sm" c="dimmed">
                Copy all participants from one test to another. Existing assignments in the target test are skipped.
              </Text>
              <Group grow align="flex-end">
                <Select
                  label="Source test"
                  value={copySourceTest}
                  onChange={(value) => setCopySourceTest(value || '')}
                  data={tests.map((item) => ({ value: String(item.id), label: item.name }))}
                />
                <Select
                  label="Target test"
                  value={copyTargetTest}
                  onChange={(value) => setCopyTargetTest(value || '')}
                  data={tests.map((item) => ({ value: String(item.id), label: item.name }))}
                />
                <Button loading={copyLoading} onClick={copyParticipants}>Copy participants</Button>
              </Group>
            </Stack>
          </Tabs.Panel>
        </Tabs>

        {bulkResult && (
          <Card withBorder radius="md" mt="md" p="sm" className="inline-summary-card">
            <Group mb="xs" gap="sm">
              <Badge color="teal">Assigned: {bulkResult.summary.assigned}</Badge>
              <Badge color="red">Failed: {bulkResult.summary.failed}</Badge>
              <Badge color="gray">Total: {bulkResult.summary.total}</Badge>
            </Group>
          </Card>
        )}

        {copySummary && (
          <Card withBorder radius="md" mt="md" p="sm" className="inline-summary-card">
            <Group gap="sm" mb="xs">
              <Badge color="teal">Copied: {copySummary.summary.copied}</Badge>
              <Badge color="yellow">Skipped: {copySummary.summary.skipped}</Badge>
              <Badge color="gray">Total: {copySummary.summary.total}</Badge>
            </Group>
          </Card>
        )}
      </Card>

      <Card className="surface-card teacher-panel" radius="lg" p="lg">
        <Group justify="space-between" align="center" mb="sm" className="panel-header">
          <div>
            <Title order={4}>Assigned Students</Title>
            <Text size="sm" c="dimmed">{selectedTest ? `Showing assignments for ${selectedTestName}` : 'Select a test to inspect assignments'}</Text>
          </div>
          <TextInput
            label="Search"
            placeholder="Search name or email"
            value={assignedSearch}
            onChange={(e) => setAssignedSearch(e.currentTarget.value)}
            w={320}
          />
        </Group>

        {!selectedTest ? (
          <Text size="sm" c="dimmed">Choose a test above to inspect assigned students, attempts, and logs.</Text>
        ) : (
          <div className="table-shell">
            <Table striped withTableBorder>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Name</Table.Th>
                  <Table.Th>Email</Table.Th>
                  <Table.Th>Attempt Usage</Table.Th>
                  <Table.Th>Assigned At</Table.Th>
                  <Table.Th>Action</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {loadingAssigned ? (
                  <Table.Tr>
                    <Table.Td colSpan={5}>Loading assignments...</Table.Td>
                  </Table.Tr>
                ) : filteredAssignedStudents.length === 0 ? (
                  <Table.Tr>
                    <Table.Td colSpan={5}>No assigned students found.</Table.Td>
                  </Table.Tr>
                ) : (
                  filteredAssignedStudents.map((item) => (
                    <Table.Tr key={item.assignment_id}>
                      <Table.Td>{item.full_name}</Table.Td>
                      <Table.Td>{item.email}</Table.Td>
                      <Table.Td>
                        <Group gap="xs">
                          <Badge color={item.can_attempt ? 'blue' : 'red'}>{item.attempts_used}/{item.max_attempts}</Badge>
                          <Text size="xs" c="dimmed">{item.attempts_remaining} left</Text>
                        </Group>
                      </Table.Td>
                      <Table.Td>{new Date(item.assigned_at).toLocaleString()}</Table.Td>
                      <Table.Td>
                        <Group gap="xs">
                          <Button
                            size="xs"
                            variant="light"
                            leftSection={<IconActivity size={14} />}
                            onClick={() => openStudentLogs(item)}
                          >
                            Attempt logs
                          </Button>
                          <Button size="xs" color="red" variant="light" onClick={() => removeStudent(item.student_id)}>Remove</Button>
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                  ))
                )}
              </Table.Tbody>
            </Table>
          </div>
        )}
      </Card>

      <Card className="surface-card teacher-panel" radius="lg" p="lg">
        <Title order={4} mb="sm">Registered Students</Title>
        <Text size="sm" c="dimmed" mb="sm">{students.length} students available for assignment</Text>
        <div className="table-shell">
          <Table striped withTableBorder>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Email</Table.Th>
                <Table.Th>Role</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {students.map((student) => (
                <Table.Tr key={student.id}>
                  <Table.Td>{student.full_name}</Table.Td>
                  <Table.Td>{student.email}</Table.Td>
                  <Table.Td>{student.role}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </div>
      </Card>

    </Stack>
  )
}
