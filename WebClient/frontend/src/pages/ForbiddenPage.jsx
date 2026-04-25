import { Button, Card, Group, Stack, Text, Title } from '@mantine/core'
import { useNavigate } from 'react-router-dom'

export function ForbiddenPage() {
  const navigate = useNavigate()

  return (
    <Group justify="center" mt={80}>
      <Card className="surface-card" p="xl" radius="lg" w={520}>
        <Stack>
          <Title order={2}>Access Denied</Title>
          <Text c="dimmed">You do not have permission to view this route.</Text>
          <Button onClick={() => navigate('/login')}>Go to login</Button>
        </Stack>
      </Card>
    </Group>
  )
}
