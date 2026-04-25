import { Button, Card, Group, PasswordInput, Stack, Text, TextInput, Title } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useForm } from '@mantine/form'
import { Link, useNavigate } from 'react-router-dom'

import { authApi } from '../api/services'
import { useAuth } from '../context/AuthContext'

export function LoginPage() {
  const navigate = useNavigate()
  const { login } = useAuth()

  const form = useForm({
    initialValues: { email: '', password: '' },
    validate: {
      email: (value) => (/^\S+@\S+\.\S+$/.test(value) ? null : 'Invalid email'),
      password: (value) => (value.length >= 8 ? null : 'Min 8 characters'),
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
    <Group justify="center" mt={70}>
      <Card className="surface-card" shadow="sm" radius="lg" p="xl" w={430}>
        <Title order={2}>Welcome back</Title>
        <Text c="dimmed" size="sm" mt={4}>Login to manage tests and assignments</Text>
        <form onSubmit={onSubmit}>
          <Stack mt="lg">
            <TextInput label="Email" placeholder="you@example.com" withAsterisk {...form.getInputProps('email')} />
            <PasswordInput label="Password" placeholder="Your password" withAsterisk {...form.getInputProps('password')} />
            <Button type="submit">Sign in</Button>
            <Text size="sm">Need an account? <Link to="/register">Create one</Link></Text>
          </Stack>
        </form>
      </Card>
    </Group>
  )
}
