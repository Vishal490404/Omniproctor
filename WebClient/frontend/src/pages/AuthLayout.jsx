import { Box, Group, Stack, Text, Title } from '@mantine/core'
import {
  IconActivityHeartbeat,
  IconLockSquareRounded,
  IconShieldCheck,
} from '@tabler/icons-react'

import { BrandLogo } from '../components/BrandLogo'

const FEATURES = [
  {
    icon: IconShieldCheck,
    title: 'Secure exam kiosk',
    body: 'Hardened Chromium browser with full-screen lockdown, hotkey suppression and a host-level firewall.',
  },
  {
    icon: IconActivityHeartbeat,
    title: 'Live behaviour telemetry',
    body: 'Focus changes, monitor count, clipboard, processes - streamed in real-time with risk scoring.',
  },
  {
    icon: IconLockSquareRounded,
    title: 'Role-based access',
    body: 'Teachers manage tests and warnings, students see only what they need.',
  },
]

/**
 * Two-column layout used by Login and Register. The left column is a
 * fixed marketing/brand panel; the right column hosts the form.
 *
 * On screens narrower than 960px (md breakpoint) the brand panel is
 * hidden so the form gets the full width.
 */
export function AuthLayout({ children }) {
  return (
    <Box className="auth-shell">
      <Box className="auth-brand">
        <Stack gap="xl" justify="space-between" h="100%">
          <Group gap="sm">
            <BrandLogo size={42} radius={12} className="auth-brand-mark" />
            <Title order={2} c="white" fw={700}>
              OmniProctor
            </Title>
          </Group>

          <Stack gap="lg" maw={460}>
            <Title order={1} c="white" lh={1.15} fz={42}>
              Run secure online exams without breaking trust.
            </Title>
            <Text c="rgba(255,255,255,0.78)" size="md" lh={1.55}>
              The dashboard, kiosk browser and live monitoring stack -
              one platform, deployed on your own infrastructure.
            </Text>
          </Stack>

          <Stack gap="lg">
            {FEATURES.map(({ icon: Icon, title, body }) => (
              <Group key={title} gap="md" wrap="nowrap" align="flex-start">
                <Box className="auth-feature-icon">
                  <Icon size={22} stroke={1.6} />
                </Box>
                <Stack gap={2}>
                  <Text c="white" fw={600} size="sm">
                    {title}
                  </Text>
                  <Text c="rgba(255,255,255,0.7)" size="sm" lh={1.45}>
                    {body}
                  </Text>
                </Stack>
              </Group>
            ))}
          </Stack>

          <Text c="rgba(255,255,255,0.5)" size="xs">
            © {new Date().getFullYear()} OmniProctor &nbsp;·&nbsp; All rights reserved
          </Text>
        </Stack>
      </Box>

      <Box className="auth-form-pane">
        <Box className="auth-form-inner">{children}</Box>
      </Box>
    </Box>
  )
}
