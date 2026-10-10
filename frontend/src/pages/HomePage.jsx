import { useCallback, useEffect, useState } from 'react'
import { Alert, Button, Card, Descriptions, Spin, Tag, Typography } from 'antd'
import { getHealth } from '../services/health'

// Thẻ màu xanh nếu ok, đỏ nếu lỗi
const StatusTag = ({ s }) => (
  <Tag color={s === 'ok' ? 'success' : 'error'}>{s === 'ok' ? 'OK' : 'LỖI'}</Tag>
)

export default function HomePage() {
  const [data, setData] = useState(null)       // kết quả JSON từ backend
  const [error, setError] = useState(null)     // lỗi khi không gọi được backend
  const [loading, setLoading] = useState(true) // đang chờ phản hồi

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await getHealth())
    } catch (err) {
      // Khi backend trả 503, vẫn có JSON mô tả service nào lỗi
      if (err.response?.data?.services) setData(err.response.data)
      else setError(err.message) // backend chưa chạy hoặc proxy lỗi
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  return (
    <div style={{ maxWidth: 560, margin: '48px auto', padding: '0 16px' }}>
      <Typography.Title level={3}>Enterprise Project &amp; Workflow Management</Typography.Title>
      <Card title="Trạng thái hệ thống" extra={<Button onClick={load}>Kiểm tra lại</Button>}>
        {loading && <Spin />}
        {error && <Alert type="error" showIcon message="Không gọi được backend" description={error} />}
        {data && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="Tổng thể"><StatusTag s={data.status} /></Descriptions.Item>
            <Descriptions.Item label="PostgreSQL">
              <StatusTag s={data.services.database.status} /> {data.services.database.detail}
            </Descriptions.Item>
            <Descriptions.Item label="Redis">
              <StatusTag s={data.services.redis.status} /> {data.services.redis.detail}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Card>
    </div>
  )
}
