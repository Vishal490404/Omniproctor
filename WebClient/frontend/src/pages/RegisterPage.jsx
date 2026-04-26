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
  UnstyledButton,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useForm } from '@mantine/form'
import {
  IconArrowRight,
  IconLock,
  IconMail,
  IconSchool,
  IconUser,
  IconUserCheck,
} from '@tabler/icons-react'
import { Link, useNavigate } from 'react-router-dom'

import { authApi } from '../api/services'
import { AuthLayout } from './AuthLayout'

const roleOptions = [
  {
    value: 'teacher',
    label: 'Teacher',
    description: 'Create tests, assign students, monitor live sessions.',
    icon: IconUserCheck,
  },
  {
    value: 'student',
    label: 'Student',
    description: 'Take tests in the secure kiosk browser.',
    icon: IconSchool,
  },
]

export function RegisterPage() {
  const navigate = useNavigate()
  const form = useForm({
    initialValues: {
      full_name: '',
      email: '',
      password: '',
      role: 'student',
    },
    validate: {
      full_name: (value) =>
        value.trim().length >= 2 ? null : 'Please enter your full name',
      email: (value) =>
        /^\S+@\S+\.\S+$/.test(value) ? null : 'Enter a valid email address',
      password: (value) =>
        value.length >= 8 ? null : 'Password must be at least 8 characters',
    },
  })

  const onSubmit = form.onSubmit(async (values) => {
    try {
      await authApi.register(values)
      notifications.show({
        color: 'teal',
        title: 'Account created',
        message: 'Your account is ready - sign in to continue.',
      })
      navigate('/login')
    } catch (error) {
      notifications.show({
        color: 'red',
        title: 'Registration failed',
        message: error?.response?.data?.detail || 'Unable to register',
      })
    }
  })

  return (
    <AuthLayout>
      <Stack gap="xl">
        <Stack gap={6}>
          <Text size="sm" c="dimmed" fw={500}>
            Get started
          </Text>
          <Title order={1} fz={34} lh={1.15}>
            Create your OmniProctor account
          </Title>
          <Text c="dimmed" size="sm">
            Pick the role that fits you - you can join an organisation or run
            a test session in minutes.
          </Text>
        </Stack>

        <Box className="auth-card">
          <form onSubmit={onSubmit}>
            <Stack gap="md">
              <Stack gap={6}>
                <Text size="sm" fw={600}>
                  I am a
                </Text>
                <Box className="auth-role-grid">
                  {roleOptions.map(({ value, label, description, icon: Icon }) => {
                    const active = form.values.role === value
                    return (
                      <UnstyledButton
                        key={value}
                        className="auth-role-card"
                        data-active={active}
                        onClick={() => form.setFieldValue('role', value)}
                      >
                        <Stack gap={4}>
                          <Group gap={8}>
                            <Icon
                              size={18}
                              stroke={1.6}
                              color={active ? '#228be6' : undefined}
                            />
                            <Text
                              size="sm"
                              fw={600}
                              c={active ? 'blue.6' : undefined}
                            >
                              {label}
                            </Text>
                          </Group>
                          <Text size="xs" c="dimmed" lh={1.4}>
                            {description}
                          </Text>
                        </Stack>
                      </UnstyledButton>
                    )
                  })}
                </Box>
              </Stack>

              <TextInput
                label="Full name"
                placeholder="Jane Doe"
                size="md"
                radius="md"
                leftSection={<IconUser size={18} stroke={1.6} />}
                withAsterisk
                {...form.getInputProps('full_name')}
              />
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
                description="Use a unique password - we'll never email it back to you."
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
                Create account
              </Button>

              <Group justify="center" gap={6}>
                <Text size="sm" c="dimmed">
                  Already have an account?
                </Text>
                <Anchor component={Link} to="/login" size="sm" fw={600}>
                  Sign in
                </Anchor>
              </Group>
            </Stack>
          </form>
        </Box>
      </Stack>
    </AuthLayout>
  )
}
