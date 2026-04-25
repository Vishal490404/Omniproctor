import {
  IconChevronLeft,
  IconChevronRight,
  IconDashboard,
  IconDeviceDesktopAnalytics,
  IconDownload,
  IconFileDescription,
  IconLogout,
  IconMoon,
  IconSun,
  IconUsers,
} from '@tabler/icons-react'
import { ActionIcon, AppShell, Avatar, Burger, Button, Group, NavLink, Stack, Text, Tooltip } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../context/AuthContext'
import { useColorSchemePreference } from '../context/ColorSchemeContext'

export function AppShellLayout({ children }) {
  const [opened, { toggle }] = useDisclosure()
  const [desktopCollapsed, setDesktopCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuth()
  const { colorScheme, toggleColorScheme } = useColorSchemePreference()

  const links = user?.role === 'student'
    ? [
        { to: '/student', label: 'My Dashboard', icon: IconDashboard, exact: true },
        { to: '/student/downloads', label: 'Downloads', icon: IconDownload },
      ]
    : [
        { to: '/portal/tests', label: 'Tests', icon: IconFileDescription },
        { to: '/portal/students', label: 'Students', icon: IconUsers },
        { to: '/portal/logs', label: 'Behavior Logs', icon: IconDeviceDesktopAnalytics },
        { to: '/portal/downloads', label: 'Downloads', icon: IconDownload },
      ]

  return (
    <AppShell
      className="app-shell"
      padding="lg"
      header={{ height: 68 }}
      navbar={{ width: 250, breakpoint: 'sm', collapsed: { mobile: !opened, desktop: desktopCollapsed } }}
    >
      <AppShell.Header className="app-header">
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group wrap="nowrap" gap="sm">
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
            <ActionIcon
              variant="light"
              className="shell-action"
              visibleFrom="sm"
              onClick={() => setDesktopCollapsed((prev) => !prev)}
              aria-label="Toggle sidebar"
            >
              {desktopCollapsed ? <IconChevronRight size={18} /> : <IconChevronLeft size={18} />}
            </ActionIcon>
            <Group gap="xs" wrap="nowrap">
              <div className="brand-dot" />
              <Text fw={700} size="lg">Omniproctor</Text>
            </Group>
          </Group>
          <Group wrap="nowrap" gap="sm">
            <Tooltip label={colorScheme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}>
              <ActionIcon className="shell-action" variant="light" onClick={toggleColorScheme} aria-label="Toggle color scheme">
                {colorScheme === 'dark' ? <IconSun size={18} /> : <IconMoon size={18} />}
              </ActionIcon>
            </Tooltip>
            <Group gap={8}>
              <Avatar radius="xl" color="teal">{user?.full_name?.[0] || 'U'}</Avatar>
              <Text size="sm" c="dimmed">{user?.full_name}</Text>
            </Group>
            <ActionIcon variant="light" color="red" onClick={() => { logout(); navigate('/login') }}>
              <IconLogout size={18} />
            </ActionIcon>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md" className="app-navbar">
        <Stack>
          {links.map((link) => {
            const path = location.pathname.replace(/\/+$/, '') || '/'
            const isActive = link.exact
              ? path === link.to.replace(/\/+$/, '')
              : path.startsWith(link.to)
            return (
              <NavLink
                key={link.to}
                className="shell-nav-link"
                label={link.label}
                leftSection={<link.icon size={16} />}
                active={isActive}
                onClick={() => navigate(link.to)}
                variant="filled"
                radius="md"
              />
            )
          })}
          <Button variant="subtle" color="red" leftSection={<IconLogout size={16} />} onClick={() => { logout(); navigate('/login') }}>
            Sign out
          </Button>
        </Stack>
      </AppShell.Navbar>

      <AppShell.Main className="app-main">
        <div className="page-shell">{children}</div>
      </AppShell.Main>
    </AppShell>
  )
}
