import {
  Alert,
  Badge,
  Button,
  Card,
  Code,
  Group,
  Progress,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import {
  IconBrandWindows,
  IconCheck,
  IconDownload,
  IconExternalLink,
  IconInfoCircle,
} from '@tabler/icons-react'
import { useCallback, useEffect, useState } from 'react'

import { downloadsApi, saveBlobResponse } from '../api/services'

function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return ''
  const units = ['B', 'KB', 'MB', 'GB']
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  return `${value.toFixed(value < 10 && unit > 0 ? 2 : 1)} ${units[unit]}`
}

function shortHash(value) {
  if (!value) return ''
  return `${value.slice(0, 12)}…${value.slice(-12)}`
}

export function DownloadsPage() {
  const [manifest, setManifest] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [downloading, setDownloading] = useState(false)
  const [progress, setProgress] = useState(0)

  const loadManifest = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await downloadsApi.getManifest()
      setManifest(data)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to load downloads manifest.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadManifest()
  }, [loadManifest])

  const handleDownload = async () => {
    if (downloading) return
    setDownloading(true)
    setProgress(0)
    const toastId = `installer-download-${Date.now()}`
    notifications.show({
      id: toastId,
      title: 'Downloading kiosk installer',
      message: 'Starting download…',
      color: 'blue',
      loading: true,
      autoClose: false,
      withCloseButton: false,
    })
    try {
      const response = await downloadsApi.downloadInstaller('windows', (event) => {
        if (event.total) {
          const pct = Math.round((event.loaded / event.total) * 100)
          setProgress(pct)
          notifications.update({
            id: toastId,
            message: `${pct}% downloaded (${formatBytes(event.loaded)})`,
            color: 'blue',
            loading: true,
            autoClose: false,
            withCloseButton: false,
          })
        }
      })
      saveBlobResponse(response, manifest?.windows?.filename || 'OmniProctorKioskSetup.exe')
      notifications.update({
        id: toastId,
        title: 'Installer downloaded',
        message: 'Run the installer to install the kiosk browser.',
        color: 'teal',
        icon: <IconCheck size={16} />,
        loading: false,
        autoClose: 5000,
        withCloseButton: true,
      })
    } catch (err) {
      notifications.update({
        id: toastId,
        title: 'Download failed',
        message: err?.response?.data?.detail || err?.message || 'Try again later.',
        color: 'red',
        loading: false,
        autoClose: 6000,
        withCloseButton: true,
      })
    } finally {
      setDownloading(false)
      setProgress(0)
    }
  }

  const tryOpenKiosk = () => {
    window.location.href = 'omniproctor-browser://ping'
  }

  const windows = manifest?.windows
  const available = !!windows?.available

  return (
    <Stack gap="lg">
      <Stack gap={2}>
        <Title order={2}>Downloads</Title>
        <Text size="sm" c="dimmed">
          Install the OmniProctor secure kiosk browser to take exams. The
          installer also registers the <Code>omniproctor-browser://</Code>{' '}
          URL handler so kiosk launch links work from this dashboard.
        </Text>
      </Stack>

      {error && (
        <Alert color="red" icon={<IconInfoCircle size={16} />} title="Manifest unavailable">
          {error}
        </Alert>
      )}

      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="lg">
        <Card className="surface-card" radius="lg" p="lg">
          <Stack gap="md">
            <Group justify="space-between" align="flex-start" wrap="nowrap">
              <Group gap="sm" wrap="nowrap">
                <IconBrandWindows size={32} />
                <Stack gap={2}>
                  <Title order={3}>Windows 10 / 11</Title>
                  <Text size="sm" c="dimmed">
                    64-bit · Inno Setup installer · admin rights required
                  </Text>
                </Stack>
              </Group>
              {available ? (
                <Badge color="teal" variant="light">
                  v{windows.version}
                </Badge>
              ) : (
                <Badge color="gray" variant="light">
                  Not published
                </Badge>
              )}
            </Group>

            {available ? (
              <Stack gap={6}>
                <Text size="sm">
                  <Text component="span" c="dimmed">Filename:</Text>{' '}
                  <Code>{windows.filename}</Code>
                </Text>
                <Text size="sm">
                  <Text component="span" c="dimmed">Size:</Text>{' '}
                  {formatBytes(windows.size_bytes)}
                </Text>
                <Text size="sm">
                  <Text component="span" c="dimmed">SHA-256:</Text>{' '}
                  <Code title={windows.sha256}>{shortHash(windows.sha256)}</Code>
                </Text>
              </Stack>
            ) : (
              <Alert color="orange" icon={<IconInfoCircle size={16} />} title="Not yet uploaded">
                Ask an administrator to publish the kiosk installer. Once
                <Code> OmniProctorKioskSetup.exe </Code>
                is dropped into the server's installers directory, it will
                appear here automatically.
              </Alert>
            )}

            {downloading && <Progress value={progress} striped animated radius="md" />}

            <Group gap="sm">
              <Button
                leftSection={<IconDownload size={16} />}
                onClick={handleDownload}
                loading={downloading}
                disabled={!available}
              >
                {downloading ? `${progress}%` : 'Download for Windows'}
              </Button>
            </Group>
          </Stack>
        </Card>

        <Card className="surface-card" radius="lg" p="lg">
          <Stack gap="md">
            <Title order={3}>Installation steps</Title>
            <Stack gap={6}>
              <Text size="sm">
                <b>1.</b> Click <i>Download for Windows</i> and save the installer.
              </Text>
              <Text size="sm">
                <b>2.</b> Run <Code>OmniProctorKioskSetup.exe</Code>. Approve the
                Windows UAC prompt — the kiosk needs admin rights for the
                network firewall.
              </Text>
              <Text size="sm">
                <b>3.</b> Leave the “Register the omniproctor-browser:// URL
                protocol” option checked, then click <i>Install</i>.
              </Text>
              <Text size="sm">
                <b>4.</b> Return to your dashboard and click{' '}
                <i>Open in kiosk browser</i> on any assigned test.
              </Text>
            </Stack>
          </Stack>
        </Card>
      </SimpleGrid>

      {loading && <Text size="sm" c="dimmed">Loading manifest…</Text>}
    </Stack>
  )
}
