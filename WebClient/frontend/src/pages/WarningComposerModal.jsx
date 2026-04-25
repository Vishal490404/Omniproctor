import {
  Badge,
  Button,
  Group,
  Modal,
  Radio,
  Stack,
  Table,
  Text,
  Textarea,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useEffect, useState } from 'react'

import { warningsApi } from '../api/services'
import { formatDateIST } from '../utils/time'

function severityColor(sev) {
  if (sev === 'critical') return 'red'
  if (sev === 'warn') return 'orange'
  return 'gray'
}

export function WarningComposerModal({ opened, attempt, seedMessage = '', onClose, onSent }) {
  const [message, setMessage] = useState('')
  const [severity, setSeverity] = useState('warn')
  const [sending, setSending] = useState(false)
  const [previous, setPrevious] = useState([])
  const [loadingPrevious, setLoadingPrevious] = useState(false)

  useEffect(() => {
    if (!opened) return
    setMessage(seedMessage || '')
    setSeverity('warn')
    if (!attempt) {
      setPrevious([])
      return
    }
    setLoadingPrevious(true)
    warningsApi
      .listForAttempt(attempt.attempt_id)
      .then(({ data }) => setPrevious(data || []))
      .catch(() => setPrevious([]))
      .finally(() => setLoadingPrevious(false))
  }, [opened, attempt, seedMessage])

  const submit = async () => {
    if (!attempt || !message.trim()) {
      notifications.show({
        color: 'orange',
        title: 'Message required',
        message: 'Type a warning before sending.',
      })
      return
    }
    setSending(true)
    try {
      const { data } = await warningsApi.send(attempt.attempt_id, {
        message: message.trim(),
        severity,
      })
      setPrevious((rows) => [...rows, data])
      setMessage('')
      notifications.show({
        color: 'teal',
        title: 'Warning queued',
        message: `Sent to ${attempt.student_name}. Kiosk will display it within ~3 seconds.`,
      })
      if (onSent) onSent(data)
    } catch (error) {
      const detail = error?.response?.data?.detail
      notifications.show({
        color: 'red',
        title: 'Failed to send warning',
        message: typeof detail === 'string' ? detail : 'Try again',
      })
    } finally {
      setSending(false)
    }
  }

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      size="lg"
      title={attempt ? `Send warning to ${attempt.student_name}` : 'Send warning'}
    >
      <Stack gap="md">
        <Textarea
          label="Message"
          description="Visible inside the kiosk as a banner above the exam."
          placeholder="Please keep your eyes on the screen and avoid switching windows."
          minRows={3}
          maxRows={8}
          value={message}
          onChange={(event) => setMessage(event.currentTarget.value)}
          maxLength={1000}
          autosize
        />
        <Radio.Group
          label="Severity"
          description="Critical warnings stay on screen until the candidate acknowledges."
          value={severity}
          onChange={setSeverity}
        >
          <Group mt="xs">
            <Radio value="info" label="Info" />
            <Radio value="warn" label="Warning" />
            <Radio value="critical" label="Critical" />
          </Group>
        </Radio.Group>

        <Group justify="flex-end">
          <Button variant="default" onClick={onClose} disabled={sending}>
            Cancel
          </Button>
          <Button color="orange" loading={sending} onClick={submit}>
            Send warning
          </Button>
        </Group>

        <Stack gap={4}>
          <Text size="sm" fw={600}>Previously sent</Text>
          {loadingPrevious ? (
            <Text size="xs" c="dimmed">Loading…</Text>
          ) : previous.length === 0 ? (
            <Text size="xs" c="dimmed">No prior warnings for this attempt.</Text>
          ) : (
            <Table striped withTableBorder>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Sent</Table.Th>
                  <Table.Th>Severity</Table.Th>
                  <Table.Th>Message</Table.Th>
                  <Table.Th>Ack'd</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {previous
                  .slice()
                  .reverse()
                  .map((warning) => (
                    <Table.Tr key={warning.id}>
                      <Table.Td>{formatDateIST(warning.created_at)}</Table.Td>
                      <Table.Td>
                        <Badge color={severityColor(warning.severity)} variant="light">
                          {warning.severity}
                        </Badge>
                      </Table.Td>
                      <Table.Td style={{ maxWidth: 320 }}>{warning.message}</Table.Td>
                      <Table.Td>{warning.acknowledged_at ? '✓' : '—'}</Table.Td>
                    </Table.Tr>
                  ))}
              </Table.Tbody>
            </Table>
          )}
        </Stack>
      </Stack>
    </Modal>
  )
}
