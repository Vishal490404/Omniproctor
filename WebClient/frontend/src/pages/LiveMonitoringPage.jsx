import {
  Badge,
  Button,
  Card,
  Divider,
  Drawer,
  Group,
  Progress,
  Select,
  Stack,
  Table,
  Text,
  Title,
  Tooltip,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useEffect, useMemo, useRef, useState } from 'react'

import { behaviorApi, liveApi, testsApi } from '../api/services'
import { formatDateIST } from '../utils/time'
import { WarningComposerModal } from './WarningComposerModal'

const POLL_INTERVAL_MS = 3000
const RISK_ALERT_THRESHOLD = 50
const RISK_ALERT_COOLDOWN_MS = 60_000

function relativeTime(iso) {
  if (!iso) return '—'
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return '—'
  const delta = Math.max(0, Date.now() - then)
  if (delta < 5_000) return 'just now'
  if (delta < 60_000) return `${Math.floor(delta / 1000)}s ago`
  if (delta < 3_600_000) return `${Math.floor(delta / 60_000)}m ago`
  return `${Math.floor(delta / 3_600_000)}h ago`
}

function riskBandColor(band) {
  if (band === 'critical') return 'red'
  if (band === 'warn') return 'orange'
  return 'teal'
}

function severityColor(sev) {
  if (sev === 'critical') return 'red'
  if (sev === 'warn') return 'orange'
  return 'gray'
}

function focusBadge(state) {
  if (state === 'in_focus') return { color: 'teal', label: 'Focused' }
  if (state === 'out_of_focus') return { color: 'red', label: 'Lost focus' }
  return { color: 'gray', label: 'Unknown' }
}

function getErrorMessage(error, fallback = 'Try again') {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || JSON.stringify(item)).join(', ')
  }
  return fallback
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

  const lastAlertedRef = useRef({}) // attempt_id -> timestamp ms
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

          const topReasons = (row.top_contributors || [])
            .slice(0, 3)
            .map(([type, weight]) => `${type} (+${weight})`)
            .join(', ') || 'multiple events'

          notifications.show({
            color: 'red',
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
    pollTimerRef.current = window.setInterval(fetchSnapshot, POLL_INTERVAL_MS)
    return () => {
      if (pollTimerRef.current) {
        window.clearInterval(pollTimerRef.current)
        pollTimerRef.current = null
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTest])

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

  const composerAttempt = drawerAttempt

  const tableRows = useMemo(() => snapshot?.rows ?? [], [snapshot])

  return (
    <Stack gap="lg">
      <div>
        <Title order={2}>Live Monitoring</Title>
        <Text size="sm" c="dimmed">
          Real-time view of in-progress attempts, risk scoring and proctor alerts. Polled every 3 seconds.
        </Text>
      </div>

      <Card className="surface-card" radius="lg" p="lg">
        <Group align="flex-end" justify="space-between">
          <Select
            label="Test"
            value={selectedTest}
            onChange={(value) => setSelectedTest(value || '')}
            data={tests.map((t) => ({ value: String(t.id), label: t.name }))}
            placeholder="Select a test"
            w={360}
          />
          <Group gap="xs">
            <Text size="sm" c="dimmed">
              {snapshot ? `${snapshot.rows.length} active attempt(s)` : '—'}
            </Text>
            {snapshot && (
              <Text size="xs" c="dimmed">
                snapshot {relativeTime(snapshot.generated_at)}
              </Text>
            )}
          </Group>
        </Group>
      </Card>

      <Card className="surface-card" radius="lg" p="lg">
        <Title order={4} mb="sm">Active Attempts</Title>
        <Table striped highlightOnHover withTableBorder>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Student</Table.Th>
              <Table.Th>Risk</Table.Th>
              <Table.Th>Latest event</Table.Th>
              <Table.Th>Focus</Table.Th>
              <Table.Th>Monitors</Table.Th>
              <Table.Th>VM</Table.Th>
              <Table.Th>Warnings</Table.Th>
              <Table.Th>Last seen</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {tableRows.length === 0 ? (
              <Table.Tr>
                <Table.Td colSpan={8}>
                  {loading ? 'Loading…' : selectedTest ? 'No active attempts.' : 'Pick a test to begin monitoring.'}
                </Table.Td>
              </Table.Tr>
            ) : (
              tableRows.map((row) => {
                const focus = focusBadge(row.focus_state)
                return (
                  <Table.Tr key={row.attempt_id} style={{ cursor: 'pointer' }} onClick={() => openDrawer(row)}>
                    <Table.Td>
                      <Stack gap={2}>
                        <Text fw={600}>{row.student_name}</Text>
                        <Text size="xs" c="dimmed">{row.student_email}</Text>
                      </Stack>
                    </Table.Td>
                    <Table.Td style={{ minWidth: 160 }}>
                      <Stack gap={4}>
                        <Group gap="xs" justify="space-between">
                          <Badge color={riskBandColor(row.risk_band)} variant="light">
                            {row.risk_score}
                          </Badge>
                          <Text size="xs" c="dimmed">{row.risk_band}</Text>
                        </Group>
                        <Progress
                          value={Math.min(100, row.risk_score)}
                          color={riskBandColor(row.risk_band)}
                          size="sm"
                        />
                      </Stack>
                    </Table.Td>
                    <Table.Td>
                      {row.latest_event_type ? (
                        <Tooltip label={row.latest_event_severity || 'info'}>
                          <Badge color={severityColor(row.latest_event_severity)} variant="outline">
                            {row.latest_event_type}
                          </Badge>
                        </Tooltip>
                      ) : (
                        <Text size="xs" c="dimmed">—</Text>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <Badge color={focus.color} variant="dot">{focus.label}</Badge>
                    </Table.Td>
                    <Table.Td>
                      {row.monitor_count ? (
                        <Badge color={row.monitor_count > 1 ? 'red' : 'teal'}>{row.monitor_count}</Badge>
                      ) : (
                        <Text size="xs" c="dimmed">—</Text>
                      )}
                    </Table.Td>
                    <Table.Td>
                      {row.vm_detected ? <Badge color="red">VM</Badge> : <Text size="xs" c="dimmed">No</Text>}
                    </Table.Td>
                    <Table.Td>{row.warnings_sent}</Table.Td>
                    <Table.Td>{relativeTime(row.last_seen_at)}</Table.Td>
                  </Table.Tr>
                )
              })
            )}
          </Table.Tbody>
        </Table>
      </Card>

      <Drawer
        opened={!!drawerAttempt}
        onClose={closeDrawer}
        position="right"
        size="xl"
        title={drawerAttempt ? `${drawerAttempt.student_name} · attempt #${drawerAttempt.attempt_id}` : ''}
      >
        {drawerAttempt && (
          <Stack gap="md">
            <Group justify="space-between">
              <Stack gap={2}>
                <Text size="sm" c="dimmed">{drawerAttempt.student_email}</Text>
                <Text size="sm">
                  Risk <Badge color={riskBandColor(drawerAttempt.risk_band)}>{drawerAttempt.risk_score}</Badge> ·
                  Focus <Badge color={focusBadge(drawerAttempt.focus_state).color}>{focusBadge(drawerAttempt.focus_state).label}</Badge> ·
                  Monitors {drawerAttempt.monitor_count ?? '—'}
                </Text>
              </Stack>
              <Group>
                <Button
                  color="orange"
                  variant="light"
                  onClick={() =>
                    openComposer(`We've noticed unusual activity (risk ${drawerAttempt.risk_score}). Please stay focused on the exam.`)
                  }
                >
                  Send templated warning
                </Button>
                <Button onClick={() => openComposer('')}>Send custom warning</Button>
              </Group>
            </Group>

            {drawerAttempt.top_contributors?.length > 0 && (
              <Card withBorder radius="md" p="sm">
                <Text size="xs" c="dimmed" mb={4}>Top risk contributors (last 60s)</Text>
                <Group gap="xs">
                  {drawerAttempt.top_contributors.map(([type, weight]) => (
                    <Badge key={type} color="red" variant="light">
                      {type} +{weight}
                    </Badge>
                  ))}
                </Group>
              </Card>
            )}

            <Divider label="Event stream" labelPosition="left" />
            {drawerLoading ? (
              <Text size="sm" c="dimmed">Loading…</Text>
            ) : (
              <Table striped withTableBorder>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Time</Table.Th>
                    <Table.Th>Type</Table.Th>
                    <Table.Th>Severity</Table.Th>
                    <Table.Th>Payload</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {drawerEvents.length === 0 ? (
                    <Table.Tr>
                      <Table.Td colSpan={4}>No events yet.</Table.Td>
                    </Table.Tr>
                  ) : (
                    drawerEvents
                      .slice()
                      .reverse()
                      .slice(0, 200)
                      .map((event) => (
                        <Table.Tr key={event.id}>
                          <Table.Td>{formatDateIST(event.event_time)}</Table.Td>
                          <Table.Td>{event.event_type}</Table.Td>
                          <Table.Td>
                            <Badge color={severityColor(event.severity)} variant="dot">
                              {event.severity}
                            </Badge>
                          </Table.Td>
                          <Table.Td style={{ maxWidth: 360, fontFamily: 'monospace', fontSize: 12 }}>
                            {event.payload ? JSON.stringify(event.payload) : '—'}
                          </Table.Td>
                        </Table.Tr>
                      ))
                  )}
                </Table.Tbody>
              </Table>
            )}
          </Stack>
        )}
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
