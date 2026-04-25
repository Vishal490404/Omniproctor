import { Button, Card, Group, PasswordInput, Select, Stack, Text, TextInput, Title } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useForm } from '@mantine/form'
import { Link, useNavigate } from 'react-router-dom'

import { authApi } from '../api/services'

const roleOptions = [
  { value: 'teacher', label: 'Teacher' },
  { value: 'student', label: 'Student' },
]

export function RegisterPage() {
  const navigate = useNavigate()
  const form = useForm({
    initialValues: { full_name: '', email: '', password: '', role: 'student' },
    validate: {
      full_name: (value) => (value.length >= 2 ? null : 'Name is too short'),
      email: (value) => (/^\S+@\S+\.\S+$/.test(value) ? null : 'Invalid email'),
      password: (value) => (value.length >= 8 ? null : 'Min 8 characters'),
    },
  })

  const onSubmit = form.onSubmit(async (values) => {
    try {
      await authApi.register(values)
      notifications.show({ color: 'teal', title: 'Account created', message: 'Please login now.' })
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
    <Group justify="center" mt={50}>
      <Card className="surface-card" shadow="sm" radius="lg" p="xl" w={430}>
        <Title order={2}>Create account</Title>
        <Text c="dimmed" size="sm" mt={4}>Register as teacher or student</Text>
        <form onSubmit={onSubmit}>
          <Stack mt="lg">
            <TextInput label="Full name" withAsterisk {...form.getInputProps('full_name')} />
            <TextInput label="Email" withAsterisk {...form.getInputProps('email')} />
            <PasswordInput label="Password" withAsterisk {...form.getInputProps('password')} />
            <Select label="Role" data={roleOptions} {...form.getInputProps('role')} />
            <Button type="submit">Create account</Button>
            <Text size="sm">Already registered? <Link to="/login">Sign in</Link></Text>
          </Stack>
        </form>
      </Card>
    </Group>
  )
}
