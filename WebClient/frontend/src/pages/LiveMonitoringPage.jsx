import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Center,
  Code,
  CopyButton,
  Divider,
  Drawer,
  Group,
  Indicator,
  Loader,
  MultiSelect,
  Paper,
  Progress,
  RingProgress,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Title,
  Tooltip,
  rem,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import {
  IconAlertTriangle,
  IconBellRinging,
  IconCheck,
  IconCopy,
  IconDeviceDesktop,
  IconEye,
  IconEyeOff,
  IconFilter,
  IconRefresh,
  IconSearch,
  IconSend,
  IconShieldCheck,
  IconShieldExclamation,
  IconSortDescending,
  IconUsers,
  IconX,
} from '@tabler/icons-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { behaviorApi, liveApi, testsApi } from '../api/services'
import { formatDateIST, relativeTime } from '../utils/time'
import { WarningComposerModal } from './WarningComposerModal'

const POLL_INTERVAL_MS = 3000
const RISK_ALERT_THRESHOLD = 50
const RISK_ALERT_COOLDOWN_MS = 60_000


function riskBandColor(band) {
  if (band === 'critical') return 'red'
  if (band === 'warn') return 'orange'
  return 'teal'
}

function riskBandLabel(band) {
  if (band === 'critical') return 'Critical'
  if (band === 'warn') return 'Warning'
  return 'OK'
}

function severityColor(sev) {
  const key = (sev || 'info').toLowerCase()
  if (key === 'critical') return 'red'
  if (key === 'warn' || key === 'warning') return 'orange'
  if (key === 'info') return 'blue'
  return 'gray'
}

function focusBadge(state) {
  if (state === 'in_focus') return { color: 'teal', label: 'Focused', icon: <IconEye size={12} stroke={2} /> }
  if (state === 'out_of_focus')
    return { color: 'red', label: 'Lost focus', icon: <IconEyeOff size={12} stroke={2} /> }
  return { color: 'gray', label: 'Unknown', icon: null }
}

function statusBadge(status) {
  const upper = (status || '').toUpperCase()
  if (upper === 'IN_PROGRESS') return { color: 'blue', label: 'In progress' }
  if (upper === 'ENDED') return { color: 'gray', label: 'Ended' }
  return { color: 'gray', label: upper || '—' }
}

function getErrorMessage(error, fallback = 'Try again') {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || JSON.stringify(item)).join(', ')
  }
  return fallback
}

function MetricCard({ label, value, color = 'gray', icon, hint }) {
  return (
    <Paper className="surface-card" radius="lg" p="md" withBorder>
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <div style={{ minWidth: 0 }}>
          <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
            {label}
          </Text>
          <Text size="xl" fw={700} mt={4}>
            {value}
          </Text>
          {hint ? (
            <Text size="xs" c="dimmed" mt={2}>
              {hint}
            </Text>
          ) : null}
        </div>
        {icon ? (
          <Center
            style={{
              width: rem(36),
              height: rem(36),
              borderRadius: rem(10),
              background: `var(--mantine-color-${color}-light)`,
              color: `var(--mantine-color-${color}-filled)`,
              flexShrink: 0,
            }}
          >
            {icon}
          </Center>
        ) : null}
      </Group>
    </Paper>
  )
}

export function LiveMonitoringPage() {
  const [tests, setTests] = useState([])
  const [selectedTest, setSelectedTest] = useState('')
  const [snapshot, setSnapshot] = useState(null)
  const [loading, setLoading] = useState(false)
  const [drawerAttempt, setDrawerAttempt] = useState(null)
  const [drawerEvents, setDrawerEvents] = useState([])
  const [drawerLoading, setDrawerLoading] = useState(false)
  const [composerOpen, setComposerOpen] = useState(false)
  const [composerSeed, setComposerSeed] = useState('')

  const [studentFilter, setStudentFilter] = useState([])
  const [riskBandFilter, setRiskBandFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [view, setView] = useState('table')
  const [sortBy, setSortBy] = useState('risk')

  const lastAlertedRef = useRef({})
  const pollTimerRef = useRef(null)

  useEffect(() => {
    async function loadTests() {
      try {
        const { data } = await testsApi.list(true)
        setTests(data)
      } catch (error) {
        notifications.show({
          color: 'red',
          title: 'Failed to load tests',
          message: getErrorMessage(error),
        })
      }
    }
    loadTests()
  }, [])

  const fetchSnapshot = async () => {
    if (!selectedTest) return
    try {
      const { data } = await liveApi.snapshot(selectedTest)
      setSnapshot(data)

      const now = Date.now()
      data.rows
        .filter((row) => row.risk_score >= RISK_ALERT_THRESHOLD)
        .forEach((row) => {
          const last = lastAlertedRef.current[row.attempt_id] || 0
          if (now - last < RISK_ALERT_COOLDOWN_MS) return
          lastAlertedRef.current[row.attempt_id] = now

          const topReasons =
            (row.top_contributors || [])
              .slice(0, 3)
              .map(([type, weight]) => `${type} (+${weight})`)
              .join(', ') || 'multiple events'

          notifications.show({
            color: 'red',
            icon: <IconBellRinging size={16} />,
            title: `High risk: ${row.student_name}`,
            message: `Score ${row.risk_score} — ${topReasons}`,
            autoClose: 12_000,
          })
        })
    } catch (error) {
      notifications.show({
        color: 'red',
        title: 'Live snapshot failed',
        message: getErrorMessage(error),
      })
    }
  }

  useEffect(() => {
    if (!selectedTest) {
      setSnapshot(null)
      return undefined
    }
    setLoading(true)
    fetchSnapshot().finally(() => setLoading(false))
    if (autoRefresh) {
      pollTimerRef.current = window.setInterval(fetchSnapshot, POLL_INTERVAL_MS)
    }
    return () => {
      if (pollTimerRef.current) {
        window.clearInterval(pollTimerRef.current)
        pollTimerRef.current = null
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTest, autoRefresh])

  const openDrawer = async (row) => {
    setDrawerAttempt(row)
    setDrawerLoading(true)
    setDrawerEvents([])
    try {
      const { data } = await behaviorApi.eventsForAttempt(row.attempt_id)
      setDrawerEvents(data)
    } catch (error) {
      notifications.show({
        color: 'red',
        title: 'Failed to load event stream',
        message: getErrorMessage(error),
      })
    } finally {
      setDrawerLoading(false)
    }
  }

  const closeDrawer = () => {
    setDrawerAttempt(null)
    setDrawerEvents([])
  }

  const openComposer = (seedMessage = '') => {
    setComposerSeed(seedMessage)
    setComposerOpen(true)
  }

  // Used by inline row actions - opens the drawer so the composer
  // modal has an attempt context, then opens the composer with a
  // tailored seed message.
  const quickWarn = (row, seedMessage = '') => {
    setDrawerAttempt(row)
    setDrawerEvents([])
    openComposer(seedMessage)
  }

  const composerAttempt = drawerAttempt
  const allRows = useMemo(() => snapshot?.rows ?? [], [snapshot])

  const studentOptions = useMemo(
    () =>
      allRows
        .map((r) => ({ value: String(r.student_id), label: `${r.student_name} (${r.student_email})` }))
        .sort((a, b) => a.label.localeCompare(b.label)),
    [allRows],
  )

  const filteredRows = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    const out = allRows.filter((row) => {
      if (studentFilter.length > 0 && !studentFilter.includes(String(row.student_id))) return false
      if (riskBandFilter !== 'all' && row.risk_band !== riskBandFilter) return false
      if (statusFilter !== 'all' && (row.status || '').toUpperCase() !== statusFilter) return false
      if (q) {
        const hay = `${row.student_name} ${row.student_email} ${row.latest_event_type || ''}`.toLowerCase()
        if (!hay.includes(q)) return false
      }
      return true
    })

    const cmp = {
      risk: (a, b) => b.risk_score - a.risk_score || a.student_name.localeCompare(b.student_name),
      name: (a, b) => a.student_name.localeCompare(b.student_name),
      lastSeen: (a, b) =>
        new Date(b.last_seen_at || 0).getTime() - new Date(a.last_seen_at || 0).getTime(),
      warnings: (a, b) =>
        (b.warnings_sent || 0) - (a.warnings_sent || 0) || b.risk_score - a.risk_score,
    }
    out.sort(cmp[sortBy] || cmp.risk)
    return out
  }, [allRows, studentFilter, riskBandFilter, statusFilter, searchQuery, sortBy])

  const criticalAttempts = useMemo(
    () => allRows.filter((r) => r.risk_band === 'critical'),
    [allRows],
  )

  const stats = useMemo(() => {
    const t = { total: allRows.length, critical: 0, warn: 0, ok: 0, vm: 0, lostFocus: 0 }
    allRows.forEach((r) => {
      if (r.risk_band === 'critical') t.critical += 1
      else if (r.risk_band === 'warn') t.warn += 1
      else t.ok += 1
      if (r.vm_detected) t.vm += 1
      if (r.focus_state === 'out_of_focus') t.lostFocus += 1
    })
    return t
  }, [allRows])

  const activeFilterCount =
    (studentFilter.length > 0 ? 1 : 0) +
    (riskBandFilter !== 'all' ? 1 : 0) +
    (statusFilter !== 'all' ? 1 : 0) +
    (searchQuery.trim() ? 1 : 0)

  const clearFilters = () => {
    setStudentFilter([])
    setRiskBandFilter('all')
    setStatusFilter('all')
    setSearchQuery('')
  }

  return (
    <Stack gap="lg">
      {/* Header */}
      <Group justify="space-between" align="flex-end">
        <div>
          <Group gap="xs" align="center">
            <Title order={2}>Live Monitoring</Title>
            {selectedTest && autoRefresh ? (
              <Tooltip label="Polling every 3 s">
                <Indicator color="green" size={9} processing>
                  <span style={{ width: 4, height: 4, display: 'inline-block' }} />
                </Indicator>
              </Tooltip>
            ) : null}
          </Group>
          <Text size="sm" c="dimmed">
            Real-time view of in-progress attempts, risk scoring, and proctor alerts.
          </Text>
        </div>
        <Group gap="xs">
          <Switch
            checked={autoRefresh}
            onChange={(e) => setAutoRefresh(e.currentTarget.checked)}
            label="Auto-refresh"
            size="sm"
          />
          <Tooltip label="Refresh now">
            <ActionIcon
              variant="light"
              size="lg"
              onClick={fetchSnapshot}
              loading={loading}
              disabled={!selectedTest}
              aria-label="Refresh"
            >
              <IconRefresh size={18} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>

      {/* Test selector */}
      <Card className="surface-card" radius="lg" p="lg" withBorder>
        <Group align="flex-end" justify="space-between">
          <Select
            label="Test"
            value={selectedTest}
            onChange={(value) => {
              setSelectedTest(value || '')
              clearFilters()
            }}
            data={tests.map((t) => ({ value: String(t.id), label: t.name }))}
            placeholder="Select a test"
            searchable
            nothingFoundMessage="No tests"
            w={400}
          />
          <Stack gap={2} align="flex-end">
            <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
              Snapshot
            </Text>
            <Text size="sm">
              {snapshot
                ? `${snapshot.rows.length} active attempt${snapshot.rows.length === 1 ? '' : 's'} · ${relativeTime(snapshot.generated_at)}`
                : 'No data yet'}
            </Text>
          </Stack>
        </Group>
      </Card>

      {/* Critical attention banner - always visible when there are
          critical attempts so the proctor sees them even if the table
          is scrolled or filtered. */}
      {criticalAttempts.length > 0 ? (
        <Alert
          color="red"
          variant="light"
          radius="lg"
          icon={<IconShieldExclamation size={20} />}
          title={`${criticalAttempts.length} candidate${criticalAttempts.length === 1 ? '' : 's'} need${criticalAttempts.length === 1 ? 's' : ''} attention`}
        >
          <Stack gap="xs">
            <Text size="sm">
              The candidates below are in the critical risk band. Click a chip to open
              the detail panel and send a warning.
            </Text>
            <Group gap="xs">
              {criticalAttempts.slice(0, 6).map((row) => (
                <Badge
                  key={row.attempt_id}
                  size="lg"
                  color="red"
                  variant="filled"
                  radius="sm"
                  style={{ cursor: 'pointer' }}
                  onClick={() => openDrawer(row)}
                  rightSection={<Text size="xs" fw={700}>{row.risk_score}</Text>}
                >
                  {row.student_name}
                </Badge>
              ))}
              {criticalAttempts.length > 6 ? (
                <Text size="xs" c="dimmed">
                  +{criticalAttempts.length - 6} more
                </Text>
              ) : null}
            </Group>
          </Stack>
        </Alert>
      ) : null}

      {/* Metric strip */}
      <SimpleGrid cols={{ base: 2, sm: 3, md: 5 }} spacing="md">
        <MetricCard
          label="Active"
          value={stats.total}
          color="blue"
          icon={<IconUsers size={18} />}
        />
        <MetricCard
          label="Critical"
          value={stats.critical}
          color="red"
          icon={<IconShieldExclamation size={18} />}
          hint={stats.critical ? 'Needs attention' : 'All clear'}
        />
        <MetricCard
          label="Warning"
          value={stats.warn}
          color="orange"
          icon={<IconAlertTriangle size={18} />}
        />
        <MetricCard
          label="OK"
          value={stats.ok}
          color="teal"
          icon={<IconShieldCheck size={18} />}
        />
        <MetricCard
          label="Lost focus / VM"
          value={`${stats.lostFocus} / ${stats.vm}`}
          color="grape"
          icon={<IconDeviceDesktop size={18} />}
          hint="out-of-focus · VM detected"
        />
      </SimpleGrid>

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
          <Group gap="xs">
            <SegmentedControl
              value={view}
              onChange={setView}
              size="xs"
              data={[
                { value: 'table', label: 'Table' },
                { value: 'kanban', label: 'Risk lanes' },
              ]}
            />
            {activeFilterCount > 0 ? (
              <Button
                size="xs"
                variant="subtle"
                leftSection={<IconX size={14} />}
                onClick={clearFilters}
              >
                Clear
              </Button>
            ) : null}
          </Group>
        </Group>

        <SimpleGrid cols={{ base: 1, sm: 2, md: 5 }} spacing="md">
          <MultiSelect
            label="Students"
            placeholder="Any student"
            data={studentOptions}
            value={studentFilter}
            onChange={setStudentFilter}
            searchable
            clearable
            disabled={allRows.length === 0}
          />
          <Select
            label="Risk band"
            value={riskBandFilter}
            onChange={(v) => setRiskBandFilter(v || 'all')}
            data={[
              { value: 'all', label: 'All bands' },
              { value: 'critical', label: 'Critical only' },
              { value: 'warn', label: 'Warnings' },
              { value: 'ok', label: 'OK' },
            ]}
          />
          <Select
            label="Status"
            value={statusFilter}
            onChange={(v) => setStatusFilter(v || 'all')}
            data={[
              { value: 'all', label: 'All' },
              { value: 'IN_PROGRESS', label: 'In progress' },
              { value: 'ENDED', label: 'Ended' },
            ]}
          />
          <Select
            label="Sort by"
            value={sortBy}
            onChange={(v) => setSortBy(v || 'risk')}
            leftSection={<IconSortDescending size={14} />}
            data={[
              { value: 'risk', label: 'Risk score (high → low)' },
              { value: 'warnings', label: 'Warnings sent' },
              { value: 'lastSeen', label: 'Last activity' },
              { value: 'name', label: 'Student name (A → Z)' },
            ]}
          />
          <TextInput
            label="Search"
            placeholder="name, email, latest event"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.currentTarget.value)}
            leftSection={<IconSearch size={16} />}
          />
        </SimpleGrid>
      </Card>

      {/* Active attempts */}
      <Card className="surface-card" radius="lg" p="lg" withBorder>
        <Group justify="space-between" mb="sm">
          <Title order={4}>Active Attempts</Title>
          <Text size="sm" c="dimmed">
            {filteredRows.length === allRows.length
              ? `${allRows.length} attempt${allRows.length === 1 ? '' : 's'}`
              : `${filteredRows.length} of ${allRows.length}`}
          </Text>
        </Group>

        {loading && allRows.length === 0 ? (
          <Center p="xl">
            <Loader />
          </Center>
        ) : filteredRows.length === 0 ? (
          <Center p="xl">
            <Stack align="center" gap="xs">
              <IconUsers size={32} stroke={1.2} color="var(--mantine-color-dimmed)" />
              <Text c="dimmed">
                {!selectedTest
                  ? 'Pick a test to begin monitoring.'
                  : allRows.length === 0
                    ? 'No active attempts yet.'
                    : 'No attempts match the current filters.'}
              </Text>
            </Stack>
          </Center>
        ) : view === 'kanban' ? (
          <KanbanView rows={filteredRows} onSelect={openDrawer} onWarn={quickWarn} />
        ) : (
          <TableView rows={filteredRows} onSelect={openDrawer} onWarn={quickWarn} />
        )}
      </Card>

      {/* Detail drawer */}
      <Drawer
        opened={!!drawerAttempt}
        onClose={closeDrawer}
        position="right"
        size="xl"
        padding="lg"
        title={
          drawerAttempt ? (
            <Group gap="xs">
              <Text fw={600}>{drawerAttempt.student_name}</Text>
              <Text size="sm" c="dimmed">
                · attempt #{drawerAttempt.attempt_id}
              </Text>
            </Group>
          ) : (
            'Attempt'
          )
        }
      >
        {drawerAttempt ? (
          <Stack gap="md">
            <Paper withBorder radius="md" p="md">
              <Group justify="space-between" align="center">
                <Group gap="md" align="center">
                  <RingProgress
                    size={84}
                    thickness={8}
                    roundCaps
                    sections={[
                      {
                        value: Math.min(100, drawerAttempt.risk_score),
                        color: riskBandColor(drawerAttempt.risk_band),
                      },
                    ]}
                    label={
                      <Center>
                        <Text fw={700} size="lg">
                          {drawerAttempt.risk_score}
                        </Text>
                      </Center>
                    }
                  />
                  <Stack gap={2}>
                    <Text size="sm" c="dimmed">
                      {drawerAttempt.student_email}
                    </Text>
                    <Group gap={6}>
                      <Badge color={riskBandColor(drawerAttempt.risk_band)} variant="filled">
                        {riskBandLabel(drawerAttempt.risk_band)}
                      </Badge>
                      <Badge color={statusBadge(drawerAttempt.status).color} variant="light">
                        {statusBadge(drawerAttempt.status).label}
                      </Badge>
                      <Badge
                        color={focusBadge(drawerAttempt.focus_state).color}
                        variant="light"
                        leftSection={focusBadge(drawerAttempt.focus_state).icon}
                      >
                        {focusBadge(drawerAttempt.focus_state).label}
                      </Badge>
                      {drawerAttempt.vm_detected ? (
                        <Badge color="red" variant="filled">
                          VM detected
                        </Badge>
                      ) : null}
                      {drawerAttempt.monitor_count && drawerAttempt.monitor_count > 1 ? (
                        <Badge color="red" variant="light">
                          {drawerAttempt.monitor_count} displays
                        </Badge>
                      ) : null}
                    </Group>
                    <Text size="xs" c="dimmed">
                      Last seen {relativeTime(drawerAttempt.last_seen_at)} · started{' '}
                      {relativeTime(drawerAttempt.started_at)}
                    </Text>
                  </Stack>
                </Group>
                <Stack gap="xs" align="flex-end">
                  <Button
                    color="orange"
                    variant="light"
                    size="xs"
                    onClick={() =>
                      openComposer(
                        `We've noticed unusual activity. Please stay focused on the exam.`,
                      )
                    }
                  >
                    Templated warning
                  </Button>
                  <Button size="xs" onClick={() => openComposer('')}>
                    Custom warning
                  </Button>
                </Stack>
              </Group>
            </Paper>

            {drawerAttempt.top_contributors?.length > 0 ? (
              <div>
                <Text size="xs" fw={600} c="dimmed" tt="uppercase" mb={4}>
                  Top risk contributors (last 60 s)
                </Text>
                <Group gap="xs">
                  {drawerAttempt.top_contributors.map(([type, weight]) => (
                    <Badge
                      key={type}
                      color="red"
                      variant="light"
                      style={{ fontFamily: 'monospace' }}
                    >
                      {type} +{weight}
                    </Badge>
                  ))}
                </Group>
              </div>
            ) : null}

            <Divider label="Event stream (latest first)" labelPosition="left" />
            {drawerLoading ? (
              <Center p="md">
                <Loader size="sm" />
              </Center>
            ) : drawerEvents.length === 0 ? (
              <Text size="sm" c="dimmed" ta="center">
                No events yet.
              </Text>
            ) : (
              <Stack gap="xs">
                {drawerEvents
                  .slice()
                  .reverse()
                  .slice(0, 100)
                  .map((event) => (
                    <Paper key={event.id} withBorder radius="md" p="sm">
                      <Group justify="space-between" wrap="nowrap" align="flex-start">
                        <div style={{ minWidth: 0, flex: 1 }}>
                          <Group gap="xs" wrap="nowrap">
                            <Badge
                              color={severityColor(event.severity)}
                              variant="filled"
                              size="sm"
                              style={{ fontFamily: 'monospace' }}
                            >
                              {event.event_type}
                            </Badge>
                            <Badge
                              color={severityColor(event.severity)}
                              variant="light"
                              size="sm"
                            >
                              {event.severity || 'info'}
                            </Badge>
                          </Group>
                          {event.payload ? (
                            <Code
                              block
                              mt={6}
                              style={{
                                fontSize: 11,
                                maxHeight: 100,
                                overflow: 'auto',
                              }}
                            >
                              {JSON.stringify(event.payload, null, 0)}
                            </Code>
                          ) : null}
                        </div>
                        <Stack gap={2} align="flex-end">
                          <Text size="xs" c="dimmed">
                            {formatDateIST(event.event_time)}
                          </Text>
                          <CopyButton value={JSON.stringify(event.payload || {})}>
                            {({ copied, copy }) => (
                              <Tooltip label={copied ? 'Copied' : 'Copy payload'}>
                                <ActionIcon
                                  variant="subtle"
                                  size="sm"
                                  onClick={copy}
                                  aria-label="Copy"
                                >
                                  {copied ? <IconCheck size={14} /> : <IconCopy size={14} />}
                                </ActionIcon>
                              </Tooltip>
                            )}
                          </CopyButton>
                        </Stack>
                      </Group>
                    </Paper>
                  ))}
              </Stack>
            )}
          </Stack>
        ) : null}
      </Drawer>

      <WarningComposerModal
        opened={composerOpen}
        attempt={composerAttempt}
        seedMessage={composerSeed}
        onClose={() => setComposerOpen(false)}
        onSent={() => {
          setComposerOpen(false)
          fetchSnapshot()
        }}
      />
    </Stack>
  )
}

// ---------------------------------------------------------------- Subviews

function TableView({ rows, onSelect, onWarn }) {
  return (
    <Table.ScrollContainer minWidth={1000}>
      <Table highlightOnHover verticalSpacing="sm" stickyHeader>
        <Table.Thead>
          <Table.Tr>
            <Table.Th style={{ width: 6, padding: 0 }} />
            <Table.Th>Student</Table.Th>
            <Table.Th style={{ width: 220 }}>Risk</Table.Th>
            <Table.Th>Latest event</Table.Th>
            <Table.Th>Top contributor</Table.Th>
            <Table.Th>Focus</Table.Th>
            <Table.Th>Monitors</Table.Th>
            <Table.Th>VM</Table.Th>
            <Table.Th>Warnings</Table.Th>
            <Table.Th>Last seen</Table.Th>
            <Table.Th style={{ width: 60 }} />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((row) => {
            const focus = focusBadge(row.focus_state)
            const bandColor = riskBandColor(row.risk_band)
            const topContributor = row.top_contributors?.[0]
            return (
              <Table.Tr
                key={row.attempt_id}
                style={{ cursor: 'pointer' }}
                onClick={() => onSelect(row)}
              >
                {/* Risk-band edge bar - quick visual scan of severity */}
                <Table.Td
                  style={{
                    padding: 0,
                    background: `var(--mantine-color-${bandColor}-filled)`,
                    width: 6,
                  }}
                />
                <Table.Td>
                  <Stack gap={2}>
                    <Text fw={600}>{row.student_name}</Text>
                    <Text size="xs" c="dimmed">
                      {row.student_email}
                    </Text>
                  </Stack>
                </Table.Td>
                <Table.Td style={{ minWidth: 200 }}>
                  <Stack gap={4}>
                    <Group gap="xs" justify="space-between" wrap="nowrap">
                      <Badge color={bandColor} variant="filled" radius="sm">
                        {row.risk_score}
                      </Badge>
                      <Text size="xs" c="dimmed">
                        {riskBandLabel(row.risk_band)}
                      </Text>
                    </Group>
                    <Progress
                      value={Math.min(100, row.risk_score)}
                      color={bandColor}
                      size="sm"
                    />
                  </Stack>
                </Table.Td>
                <Table.Td>
                  {row.latest_event_type ? (
                    <Tooltip label={row.latest_event_severity || 'info'}>
                      <Badge
                        color={severityColor(row.latest_event_severity)}
                        variant="light"
                        style={{ fontFamily: 'monospace' }}
                      >
                        {row.latest_event_type}
                      </Badge>
                    </Tooltip>
                  ) : (
                    <Text size="xs" c="dimmed">
                      —
                    </Text>
                  )}
                </Table.Td>
                <Table.Td>
                  {topContributor ? (
                    <Badge
                      color="red"
                      variant="light"
                      style={{ fontFamily: 'monospace' }}
                    >
                      {topContributor[0]} +{topContributor[1]}
                    </Badge>
                  ) : (
                    <Text size="xs" c="dimmed">
                      —
                    </Text>
                  )}
                </Table.Td>
                <Table.Td>
                  <Badge color={focus.color} variant="light" leftSection={focus.icon}>
                    {focus.label}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  {row.monitor_count ? (
                    <Badge color={row.monitor_count > 1 ? 'red' : 'teal'} variant="light">
                      {row.monitor_count}
                    </Badge>
                  ) : (
                    <Text size="xs" c="dimmed">
                      —
                    </Text>
                  )}
                </Table.Td>
                <Table.Td>
                  {row.vm_detected ? (
                    <Badge color="red" variant="filled">
                      VM
                    </Badge>
                  ) : (
                    <Text size="xs" c="dimmed">
                      No
                    </Text>
                  )}
                </Table.Td>
                <Table.Td>
                  {row.warnings_sent > 0 ? (
                    <Badge color="grape" variant="light">
                      {row.warnings_sent}
                    </Badge>
                  ) : (
                    <Text size="xs" c="dimmed">0</Text>
                  )}
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{relativeTime(row.last_seen_at)}</Text>
                </Table.Td>
                <Table.Td>
                  <Tooltip label="Send warning">
                    <ActionIcon
                      variant={row.risk_band === 'critical' ? 'filled' : 'light'}
                      color={row.risk_band === 'critical' ? 'red' : 'orange'}
                      onClick={(ev) => {
                        ev.stopPropagation()
                        onWarn(
                          row,
                          row.risk_band === 'critical'
                            ? `We've noticed unusual activity. Please stay focused on the exam.`
                            : '',
                        )
                      }}
                      aria-label="Send warning"
                    >
                      <IconSend size={14} />
                    </ActionIcon>
                  </Tooltip>
                </Table.Td>
              </Table.Tr>
            )
          })}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  )
}

function KanbanView({ rows, onSelect, onWarn: _onWarn }) {
  const lanes = ['critical', 'warn', 'ok']
  const grouped = lanes.reduce((acc, band) => {
    acc[band] = rows.filter((r) => r.risk_band === band)
    return acc
  }, {})

  return (
    <SimpleGrid cols={{ base: 1, md: 3 }} spacing="md">
      {lanes.map((band) => (
        <Stack key={band} gap="xs">
          <Group justify="space-between" px={4}>
            <Group gap={6}>
              <Badge color={riskBandColor(band)} variant="filled" radius="sm">
                {riskBandLabel(band)}
              </Badge>
              <Text size="sm" fw={600}>
                {grouped[band].length}
              </Text>
            </Group>
          </Group>
          {grouped[band].length === 0 ? (
            <Paper withBorder radius="md" p="md">
              <Text size="sm" c="dimmed" ta="center">
                None
              </Text>
            </Paper>
          ) : (
            grouped[band].map((row) => {
              const focus = focusBadge(row.focus_state)
              return (
                <Paper
                  key={row.attempt_id}
                  withBorder
                  radius="md"
                  p="sm"
                  style={{ cursor: 'pointer' }}
                  onClick={() => onSelect(row)}
                >
                  <Group justify="space-between" align="flex-start" wrap="nowrap">
                    <Stack gap={4} style={{ minWidth: 0, flex: 1 }}>
                      <Text fw={600} truncate>
                        {row.student_name}
                      </Text>
                      <Text size="xs" c="dimmed" truncate>
                        {row.student_email}
                      </Text>
                      <Group gap={4} mt={4}>
                        <Badge color={focus.color} variant="dot" size="xs">
                          {focus.label}
                        </Badge>
                        {row.vm_detected ? (
                          <Badge color="red" size="xs">
                            VM
                          </Badge>
                        ) : null}
                        {row.monitor_count && row.monitor_count > 1 ? (
                          <Badge color="red" variant="light" size="xs">
                            {row.monitor_count}×
                          </Badge>
                        ) : null}
                        {row.warnings_sent > 0 ? (
                          <Badge color="grape" variant="light" size="xs">
                            ⚑ {row.warnings_sent}
                          </Badge>
                        ) : null}
                      </Group>
                      {row.latest_event_type ? (
                        <Text
                          size="xs"
                          c="dimmed"
                          style={{ fontFamily: 'monospace' }}
                          truncate
                        >
                          {row.latest_event_type} · {relativeTime(row.last_seen_at)}
                        </Text>
                      ) : null}
                    </Stack>
                    <RingProgress
                      size={48}
                      thickness={5}
                      roundCaps
                      sections={[
                        {
                          value: Math.min(100, row.risk_score),
                          color: riskBandColor(row.risk_band),
                        },
                      ]}
                      label={
                        <Center>
                          <Text fw={700} size="xs">
                            {row.risk_score}
                          </Text>
                        </Center>
                      }
                    />
                  </Group>
                </Paper>
              )
            })
          )}
        </Stack>
      ))}
    </SimpleGrid>
  )
}
