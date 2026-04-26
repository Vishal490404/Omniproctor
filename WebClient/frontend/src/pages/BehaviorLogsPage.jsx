import {
  ActionIcon,
  Badge,
  Button,
  Card,
  Center,
  Code,
  CopyButton,
  Divider,
  Drawer,
  Group,
  Loader,
  MultiSelect,
  Pagination,
  Paper,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  Tooltip,
  rem,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import {
  IconActivity,
  IconAlertTriangle,
  IconCheck,
  IconCopy,
  IconDeviceDesktop,
  IconDownload,
  IconEye,
  IconFilter,
  IconKeyboard,
  IconRefresh,
  IconSearch,
  IconShieldExclamation,
  IconX,
} from '@tabler/icons-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { behaviorApi, testsApi } from '../api/services'
import { formatDateIST } from '../utils/time'

const PAGE_SIZE = 25

const SEVERITY_META = {
  critical: { color: 'red', label: 'Critical' },
  warn: { color: 'orange', label: 'Warning' },
  warning: { color: 'orange', label: 'Warning' },
  info: { color: 'blue', label: 'Info' },
  debug: { color: 'gray', label: 'Debug' },
}

const EVENT_GROUPS = {
  critical: ['VM_DETECTED', 'RENDERER_CRASH', 'SUSPICIOUS_PROCESS'],
  focus: ['FOCUS_LOSS', 'FOCUS_REGAIN', 'FULLSCREEN_EXIT'],
  input: ['KEYSTROKE', 'BLOCKED_HOTKEY', 'CLIPBOARD_COPY'],
  display: ['MONITOR_COUNT_CHANGE'],
  warnings: ['WARNING_DELIVERED', 'WARNING_ACKNOWLEDGED'],
}

const QUICK_RANGES = [
  { value: 'all', label: 'All time' },
  { value: '5m', label: 'Last 5 min' },
  { value: '15m', label: 'Last 15 min' },
  { value: '1h', label: 'Last 1 hour' },
  { value: '24h', label: 'Last 24 hours' },
]

function rangeToCutoffMs(rangeKey) {
  const now = Date.now()
  switch (rangeKey) {
    case '5m':
      return now - 5 * 60 * 1000
    case '15m':
      return now - 15 * 60 * 1000
    case '1h':
      return now - 60 * 60 * 1000
    case '24h':
      return now - 24 * 60 * 60 * 1000
    default:
      return null
  }
}

function severityBadge(severity) {
  const key = (severity || 'info').toLowerCase()
  const meta = SEVERITY_META[key] || SEVERITY_META.info
  return (
    <Badge color={meta.color} variant="light" radius="sm">
      {meta.label}
    </Badge>
  )
}

function eventTypeBadge(eventType) {
  const upper = (eventType || '').toUpperCase()
  let color = 'gray'
  if (EVENT_GROUPS.critical.includes(upper)) color = 'red'
  else if (EVENT_GROUPS.focus.includes(upper)) color = 'yellow'
  else if (EVENT_GROUPS.input.includes(upper)) color = 'grape'
  else if (EVENT_GROUPS.display.includes(upper)) color = 'cyan'
  else if (EVENT_GROUPS.warnings.includes(upper)) color = 'teal'
  return (
    <Badge color={color} variant="filled" radius="sm" style={{ fontFamily: 'monospace' }}>
      {upper || 'UNKNOWN'}
    </Badge>
  )
}

function summarizePayload(eventType, payload) {
  if (!payload || typeof payload !== 'object') return ''
  const upper = (eventType || '').toUpperCase()
  switch (upper) {
    case 'KEYSTROKE': {
      const keys = Array.isArray(payload.keys) ? payload.keys : []
      const burst = payload.burst_size ?? keys.length
      const sample = keys
        .slice(0, 3)
        .map((k) => k?.key)
        .filter(Boolean)
        .join(', ')
      return `${burst} key${burst === 1 ? '' : 's'}${sample ? ` — ${sample}${keys.length > 3 ? '…' : ''}` : ''}`
    }
    case 'BLOCKED_HOTKEY':
      return `${payload.description || payload.combo || 'blocked combo'}`
    case 'FOCUS_LOSS':
      return `Lost to ${payload.proc || 'unknown'} — "${payload.title || ''}"`
    case 'FOCUS_REGAIN':
      return `Returned from ${payload.previous_proc || 'unknown'}`
    case 'FULLSCREEN_EXIT':
      return payload.recovered ? 'Recovered automatically' : 'Manual exit'
    case 'CLIPBOARD_COPY':
      return `${payload.length ?? '?'} chars${payload.has_image ? ' + image' : ''}${payload.has_urls ? ' + url' : ''}`
    case 'MONITOR_COUNT_CHANGE': {
      const prev = payload.previous_count
      const cur = payload.count
      if (prev != null && cur != null) return `${prev} → ${cur} display(s)`
      return `${cur ?? '?'} display(s)`
    }
    case 'VM_DETECTED':
      return payload.indicators?.join(', ') || 'VM/VDI signals matched'
    case 'SUSPICIOUS_PROCESS':
      return `${payload.proc || payload.image_name || 'process'} (${payload.match_reason || 'matched watchlist'})`
    case 'RENDERER_CRASH':
      return `Renderer terminated (${payload.reason || 'unknown'})`
    case 'WARNING_DELIVERED':
      return `"${payload.title || payload.message || 'warning shown'}"`
    default:
      return ''
  }
}

function eventTypeIcon(eventType) {
  const upper = (eventType || '').toUpperCase()
  const props = { size: 16, stroke: 1.5 }
  if (EVENT_GROUPS.critical.includes(upper)) return <IconShieldExclamation {...props} />
  if (EVENT_GROUPS.focus.includes(upper)) return <IconEye {...props} />
  if (EVENT_GROUPS.input.includes(upper)) return <IconKeyboard {...props} />
  if (EVENT_GROUPS.display.includes(upper)) return <IconDeviceDesktop {...props} />
  return <IconActivity {...props} />
}

function MetricCard({ label, value, color = 'gray', icon }) {
  return (
    <Paper className="surface-card" radius="lg" p="md" withBorder>
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <div>
          <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
            {label}
          </Text>
          <Text size="xl" fw={700} mt={4}>
            {value}
          </Text>
        </div>
        {icon ? (
          <Center
            style={{
              width: rem(36),
              height: rem(36),
              borderRadius: rem(10),
              background: `var(--mantine-color-${color}-light)`,
              color: `var(--mantine-color-${color}-filled)`,
            }}
          >
            {icon}
          </Center>
        ) : null}
      </Group>
    </Paper>
  )
}

function downloadJson(filename, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export function BehaviorLogsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialTestId = searchParams.get('testId') || ''
  const initialStudentId = searchParams.get('studentId') || ''

  const [tests, setTests] = useState([])
  const [studentsForTest, setStudentsForTest] = useState([])
  const [selectedTest, setSelectedTest] = useState(initialTestId)
  const [selectedStudent, setSelectedStudent] = useState(initialStudentId)
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(false)

  const [eventTypeFilter, setEventTypeFilter] = useState([])
  const [severityFilter, setSeverityFilter] = useState('all')
  const [rangeFilter, setRangeFilter] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [page, setPage] = useState(1)
  const [drawerEvent, setDrawerEvent] = useState(null)

  const pendingDeepLinkRef = useRef(Boolean(initialTestId && initialStudentId))

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
        if (pendingDeepLinkRef.current) {
          const exists = data.some((s) => String(s.student_id) === String(selectedStudent))
          if (!exists) {
            setSelectedStudent('')
            pendingDeepLinkRef.current = false
            notifications.show({
              color: 'orange',
              title: 'Student not assigned',
              message: 'The linked student is no longer assigned to this test.',
            })
          }
        } else {
          setSelectedStudent('')
        }
      } catch (error) {
        notifications.show({ color: 'red', title: 'Failed to load students', message: getErrorMessage(error) })
      }
    }
    loadStudentsForTest()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTest])

  const loadEvents = async (options = {}) => {
    const { silent = false } = options
    if (!selectedTest || !selectedStudent) {
      if (!silent) {
        notifications.show({ color: 'orange', title: 'Selection required', message: 'Pick both test and student' })
      }
      return
    }
    setLoading(true)
    try {
      const { data } = await behaviorApi.eventsForTestStudent(selectedTest, selectedStudent)
      setEvents(data)
      setPage(1)
    } catch (error) {
      notifications.show({ color: 'red', title: 'Failed to load logs', message: getErrorMessage(error) })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!pendingDeepLinkRef.current) return
    if (!selectedTest || !selectedStudent) return
    if (studentsForTest.length === 0) return
    const exists = studentsForTest.some((s) => String(s.student_id) === String(selectedStudent))
    if (!exists) return
    pendingDeepLinkRef.current = false
    loadEvents({ silent: true })
    setSearchParams({}, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTest, selectedStudent, studentsForTest])

  // ---------------------------------------------------------------- Derived
  const eventTypeOptions = useMemo(() => {
    const types = new Set(events.map((e) => (e.event_type || '').toUpperCase()))
    return Array.from(types)
      .filter(Boolean)
      .sort()
      .map((t) => ({ value: t, label: t }))
  }, [events])

  const filteredEvents = useMemo(() => {
    const cutoff = rangeToCutoffMs(rangeFilter)
    const query = searchQuery.trim().toLowerCase()
    return events.filter((event) => {
      const upperType = (event.event_type || '').toUpperCase()
      if (eventTypeFilter.length > 0 && !eventTypeFilter.includes(upperType)) return false
      if (severityFilter !== 'all' && (event.severity || '').toLowerCase() !== severityFilter) return false
      if (cutoff != null) {
        const ts = event.event_time ? new Date(event.event_time).getTime() : 0
        if (!ts || ts < cutoff) return false
      }
      if (query) {
        const haystack = `${upperType} ${event.severity || ''} ${JSON.stringify(event.payload || {})}`.toLowerCase()
        if (!haystack.includes(query)) return false
      }
      return true
    })
  }, [events, eventTypeFilter, severityFilter, rangeFilter, searchQuery])

  const stats = useMemo(() => {
    const totals = {
      total: filteredEvents.length,
      critical: 0,
      warn: 0,
      info: 0,
      perType: {},
    }
    filteredEvents.forEach((e) => {
      const sev = (e.severity || 'info').toLowerCase()
      if (sev === 'critical') totals.critical += 1
      else if (sev === 'warn' || sev === 'warning') totals.warn += 1
      else totals.info += 1
      const t = (e.event_type || 'UNKNOWN').toUpperCase()
      totals.perType[t] = (totals.perType[t] || 0) + 1
    })
    return totals
  }, [filteredEvents])

  const topTypes = useMemo(() => {
    return Object.entries(stats.perType)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6)
  }, [stats])

  const totalPages = Math.max(1, Math.ceil(filteredEvents.length / PAGE_SIZE))
  const safePage = Math.min(page, totalPages)
  const pageStart = (safePage - 1) * PAGE_SIZE
  const pageEvents = filteredEvents.slice(pageStart, pageStart + PAGE_SIZE)

  const activeFilterCount =
    (eventTypeFilter.length > 0 ? 1 : 0) +
    (severityFilter !== 'all' ? 1 : 0) +
    (rangeFilter !== 'all' ? 1 : 0) +
    (searchQuery.trim() ? 1 : 0)

  const clearFilters = () => {
    setEventTypeFilter([])
    setSeverityFilter('all')
    setRangeFilter('all')
    setSearchQuery('')
    setPage(1)
  }

  const exportFiltered = () => {
    if (filteredEvents.length === 0) {
      notifications.show({ color: 'orange', title: 'Nothing to export', message: 'No events match the current filters.' })
      return
    }
    const ts = new Date().toISOString().replace(/[:.]/g, '-')
    downloadJson(`behavior_test${selectedTest}_student${selectedStudent}_${ts}.json`, filteredEvents)
  }

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end">
        <div>
          <Title order={2}>Behavior Logs</Title>
          <Text size="sm" c="dimmed">
            Per-student, per-test telemetry from the secure browser. Filter by type, severity, and time
            window to drill into suspicious activity.
          </Text>
        </div>
        <Group gap="xs">
          <Tooltip label="Reload events">
            <ActionIcon
              variant="light"
              size="lg"
              onClick={loadEvents}
              loading={loading}
              disabled={!selectedTest || !selectedStudent}
              aria-label="Reload events"
            >
              <IconRefresh size={18} />
            </ActionIcon>
          </Tooltip>
          <Tooltip label="Export filtered events as JSON">
            <ActionIcon
              variant="light"
              size="lg"
              onClick={exportFiltered}
              disabled={filteredEvents.length === 0}
              aria-label="Export"
            >
              <IconDownload size={18} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>

      {/* Selection card */}
      <Card className="surface-card" radius="lg" p="lg" withBorder>
        <Group grow align="flex-end">
          <Select
            label="Test"
            value={selectedTest}
            onChange={(value) => setSelectedTest(value || '')}
            data={tests.map((item) => ({ value: String(item.id), label: item.name }))}
            placeholder="Select test"
            searchable
            nothingFoundMessage="No tests"
          />
          <Select
            label="Student"
            value={selectedStudent}
            onChange={(value) => setSelectedStudent(value || '')}
            data={studentsForTest.map((item) => ({
              value: String(item.student_id),
              label: `${item.full_name} (${item.email})`,
            }))}
            placeholder="Select student"
            searchable
            disabled={!selectedTest}
            nothingFoundMessage="No students assigned"
          />
          <Button loading={loading} onClick={loadEvents} leftSection={<IconRefresh size={16} />}>
            Load logs
          </Button>
        </Group>
      </Card>

      {/* Summary cards */}
      <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="md">
        <MetricCard
          label="Total events"
          value={events.length}
          color="blue"
          icon={<IconActivity size={18} />}
        />
        <MetricCard
          label="Critical"
          value={events.filter((e) => (e.severity || '').toLowerCase() === 'critical').length}
          color="red"
          icon={<IconShieldExclamation size={18} />}
        />
        <MetricCard
          label="Warnings"
          value={events.filter((e) => ['warn', 'warning'].includes((e.severity || '').toLowerCase())).length}
          color="orange"
          icon={<IconAlertTriangle size={18} />}
        />
        <MetricCard
          label="Showing"
          value={`${filteredEvents.length} / ${events.length}`}
          color="gray"
          icon={<IconFilter size={18} />}
        />
      </SimpleGrid>

      {/* Top event types */}
      {topTypes.length > 0 ? (
        <Card className="surface-card" radius="lg" p="md" withBorder>
          <Group justify="space-between" mb="xs">
            <Text size="sm" fw={600} c="dimmed" tt="uppercase">
              Event mix
            </Text>
            <Text size="xs" c="dimmed">
              Tap to filter
            </Text>
          </Group>
          <Group gap="xs">
            {topTypes.map(([type, count]) => {
              const isActive = eventTypeFilter.includes(type)
              return (
                <Badge
                  key={type}
                  size="lg"
                  variant={isActive ? 'filled' : 'light'}
                  color={EVENT_GROUPS.critical.includes(type) ? 'red' : EVENT_GROUPS.focus.includes(type) ? 'yellow' : EVENT_GROUPS.input.includes(type) ? 'grape' : EVENT_GROUPS.display.includes(type) ? 'cyan' : 'gray'}
                  style={{ cursor: 'pointer', fontFamily: 'monospace' }}
                  onClick={() => {
                    setEventTypeFilter((prev) =>
                      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type],
                    )
                    setPage(1)
                  }}
                  rightSection={
                    <Text component="span" size="xs" fw={700}>
                      {count}
                    </Text>
                  }
                >
                  {type}
                </Badge>
              )
            })}
          </Group>
        </Card>
      ) : null}

      {/* Filters */}
      <Card className="surface-card" radius="lg" p="lg" withBorder>
        <Group justify="space-between" mb="md">
          <Group gap="xs">
            <IconFilter size={18} />
            <Text fw={600}>Filters</Text>
            {activeFilterCount > 0 ? (
              <Badge size="sm" color="blue" variant="light">
                {activeFilterCount} active
              </Badge>
            ) : null}
          </Group>
          {activeFilterCount > 0 ? (
            <Button
              variant="subtle"
              size="xs"
              leftSection={<IconX size={14} />}
              onClick={clearFilters}
            >
              Clear all
            </Button>
          ) : null}
        </Group>
        <SimpleGrid cols={{ base: 1, sm: 2, md: 4 }} spacing="md">
          <MultiSelect
            label="Event types"
            placeholder="Any"
            data={eventTypeOptions}
            value={eventTypeFilter}
            onChange={(v) => {
              setEventTypeFilter(v)
              setPage(1)
            }}
            searchable
            clearable
            disabled={events.length === 0}
          />
          <Select
            label="Severity"
            value={severityFilter}
            onChange={(v) => {
              setSeverityFilter(v || 'all')
              setPage(1)
            }}
            data={[
              { value: 'all', label: 'All severities' },
              { value: 'critical', label: 'Critical only' },
              { value: 'warn', label: 'Warnings' },
              { value: 'info', label: 'Info' },
            ]}
          />
          <Select
            label="Time range"
            value={rangeFilter}
            onChange={(v) => {
              setRangeFilter(v || 'all')
              setPage(1)
            }}
            data={QUICK_RANGES}
          />
          <TextInput
            label="Search payload"
            placeholder="e.g. ctrl+shift, OBS, hwnd"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.currentTarget.value)
              setPage(1)
            }}
            leftSection={<IconSearch size={16} />}
          />
        </SimpleGrid>
      </Card>

      {/* Timeline */}
      <Card className="surface-card" radius="lg" p="lg" withBorder>
        <Group justify="space-between" mb="sm">
          <Title order={4}>Event Timeline</Title>
          <Text size="sm" c="dimmed">
            {filteredEvents.length === events.length
              ? `${events.length} events`
              : `${filteredEvents.length} of ${events.length} events`}
          </Text>
        </Group>

        {loading ? (
          <Center p="xl">
            <Loader />
          </Center>
        ) : pageEvents.length === 0 ? (
          <Center p="xl">
            <Stack align="center" gap="xs">
              <IconActivity size={32} stroke={1.2} color="var(--mantine-color-dimmed)" />
              <Text c="dimmed">
                {events.length === 0
                  ? 'Pick a test and student, then load logs.'
                  : 'No events match the current filters.'}
              </Text>
            </Stack>
          </Center>
        ) : (
          <>
            <Table.ScrollContainer minWidth={700}>
              <Table striped highlightOnHover verticalSpacing="sm">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th style={{ width: 170 }}>Time</Table.Th>
                    <Table.Th style={{ width: 200 }}>Type</Table.Th>
                    <Table.Th style={{ width: 110 }}>Severity</Table.Th>
                    <Table.Th style={{ width: 80 }}>Attempt</Table.Th>
                    <Table.Th>Detail</Table.Th>
                    <Table.Th style={{ width: 70 }} />
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {pageEvents.map((event) => (
                    <Table.Tr
                      key={event.id}
                      style={{ cursor: 'pointer' }}
                      onClick={() => setDrawerEvent(event)}
                    >
                      <Table.Td>
                        <Text size="sm">{formatDateIST(event.event_time)}</Text>
                      </Table.Td>
                      <Table.Td>
                        <Group gap={6} wrap="nowrap">
                          {eventTypeIcon(event.event_type)}
                          {eventTypeBadge(event.event_type)}
                        </Group>
                      </Table.Td>
                      <Table.Td>{severityBadge(event.severity)}</Table.Td>
                      <Table.Td>
                        <Tooltip label={`test_attempts.id = ${event.attempt_id}`}>
                          <Text size="sm" c="dimmed">
                            #{event.attempt_number ?? 1}
                          </Text>
                        </Tooltip>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm" lineClamp={1}>
                          {summarizePayload(event.event_type, event.payload) || (
                            <Text component="span" c="dimmed">
                              —
                            </Text>
                          )}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <ActionIcon
                          variant="subtle"
                          aria-label="View payload"
                          onClick={(ev) => {
                            ev.stopPropagation()
                            setDrawerEvent(event)
                          }}
                        >
                          <IconEye size={16} />
                        </ActionIcon>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>

            {totalPages > 1 ? (
              <Group justify="space-between" mt="md">
                <Text size="xs" c="dimmed">
                  Showing {pageStart + 1}–{Math.min(pageStart + PAGE_SIZE, filteredEvents.length)} of{' '}
                  {filteredEvents.length}
                </Text>
                <Pagination
                  value={safePage}
                  onChange={setPage}
                  total={totalPages}
                  size="sm"
                  withEdges
                />
              </Group>
            ) : null}
          </>
        )}
      </Card>

      {/* Detail drawer */}
      <Drawer
        opened={drawerEvent != null}
        onClose={() => setDrawerEvent(null)}
        title={
          drawerEvent ? (
            <Group gap="xs">
              {eventTypeIcon(drawerEvent.event_type)}
              {eventTypeBadge(drawerEvent.event_type)}
              {severityBadge(drawerEvent.severity)}
            </Group>
          ) : (
            'Event detail'
          )
        }
        position="right"
        size="md"
        padding="lg"
      >
        {drawerEvent ? (
          <Stack gap="md">
            <Paper p="sm" radius="md" withBorder>
              <SimpleGrid cols={2} spacing="xs">
                <Text size="xs" c="dimmed">
                  Time
                </Text>
                <Text size="sm">{formatDateIST(drawerEvent.event_time)}</Text>
                <Text size="xs" c="dimmed">
                  Attempt
                </Text>
                <Text size="sm">
                  #{drawerEvent.attempt_number ?? 1}{' '}
                  <Text component="span" c="dimmed" size="xs">
                    (id {drawerEvent.attempt_id})
                  </Text>
                </Text>
                <Text size="xs" c="dimmed">
                  Event ID
                </Text>
                <Text size="sm">#{drawerEvent.id}</Text>
              </SimpleGrid>
            </Paper>

            <div>
              <Text size="xs" fw={600} c="dimmed" tt="uppercase" mb={4}>
                Summary
              </Text>
              <Text size="sm">{summarizePayload(drawerEvent.event_type, drawerEvent.payload) || '—'}</Text>
            </div>

            <Divider />

            <div>
              <Group justify="space-between" mb={4}>
                <Text size="xs" fw={600} c="dimmed" tt="uppercase">
                  Raw payload
                </Text>
                <CopyButton value={JSON.stringify(drawerEvent.payload || {}, null, 2)}>
                  {({ copied, copy }) => (
                    <Tooltip label={copied ? 'Copied' : 'Copy JSON'}>
                      <ActionIcon variant="subtle" onClick={copy} size="sm" aria-label="Copy">
                        {copied ? <IconCheck size={14} /> : <IconCopy size={14} />}
                      </ActionIcon>
                    </Tooltip>
                  )}
                </CopyButton>
              </Group>
              <Code
                block
                style={{
                  maxHeight: 360,
                  overflow: 'auto',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}
              >
                {JSON.stringify(drawerEvent.payload ?? {}, null, 2)}
              </Code>
            </div>
          </Stack>
        ) : null}
      </Drawer>
    </Stack>
  )
}
