import api from './api'

// Gọi GET /api/health/ và trả về phần dữ liệu JSON
export const getHealth = async () => (await api.get('/health/')).data
