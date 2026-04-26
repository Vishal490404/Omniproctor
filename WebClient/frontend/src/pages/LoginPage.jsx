import {
  Anchor,
  Box,
  Button,
  Group,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useForm } from '@mantine/form'
import { IconArrowRight, IconLock, IconMail } from '@tabler/icons-react'
import { Link, useNavigate } from 'react-router-dom'

import { authApi } from '../api/services'
import { useAuth } from '../context/AuthContext'
import { AuthLayout } from './AuthLayout'

export function LoginPage() {
  const navigate = useNavigate()
  const { login } = useAuth()

  const form = useForm({
    initialValues: { email: '', password: '' },
    validate: {
      email: (value) =>
        /^\S+@\S+\.\S+$/.test(value) ? null : 'Enter a valid email address',
      password: (value) =>
        value.length >= 8 ? null : 'Password must be at least 8 characters',
    },
  })

  const onSubmit = form.onSubmit(async (values) => {
    try {
      const { data } = await authApi.login(values)
      login(data.token.access_token, data.user)
      if (data.user.role === 'student') {
        navigate('/student')
      } else {
        navigate('/portal/tests')
      }
    } catch (error) {
      notifications.show({
        color: 'red',
        title: 'Login failed',
        message: error?.response?.data?.detail || 'Unable to login',
      })
    }
  })

  return (
    <AuthLayout>
      <Stack gap="xl">
        <Stack gap={6}>
          <Text size="sm" c="dimmed" fw={500}>
            Welcome back
          </Text>
          <Title order={1} fz={34} lh={1.15}>
            Sign in to your dashboard
          </Title>
          <Text c="dimmed" size="sm">
            Enter your credentials to manage tests, monitor live sessions and
            review behaviour logs.
          </Text>
        </Stack>

        <Box className="auth-card">
          <form onSubmit={onSubmit}>
            <Stack gap="md">
              <TextInput
                label="Email address"
                placeholder="you@school.edu"
                size="md"
                radius="md"
                leftSection={<IconMail size={18} stroke={1.6} />}
                withAsterisk
                {...form.getInputProps('email')}
              />
              <PasswordInput
                label="Password"
                placeholder="At least 8 characters"
                size="md"
                radius="md"
                leftSection={<IconLock size={18} stroke={1.6} />}
                withAsterisk
                {...form.getInputProps('password')}
              />

              <Button
                type="submit"
                size="md"
                radius="md"
                className="auth-submit-btn"
                rightSection={<IconArrowRight size={18} stroke={1.8} />}
                loading={form.submitting}
                fullWidth
              >
                Sign in
              </Button>

              <Box className="auth-divider">or</Box>

              <Group justify="center" gap={6}>
                <Text size="sm" c="dimmed">
                  New here?
                </Text>
                <Anchor component={Link} to="/register" size="sm" fw={600}>
                  Create an account
                </Anchor>
              </Group>
            </Stack>
          </form>
        </Box>

        <Text size="xs" c="dimmed" ta="center">
          By signing in you agree to OmniProctor's terms and acknowledge that
          test sessions are recorded and analysed for academic integrity.
        </Text>
      </Stack>
    </AuthLayout>
  )
}
