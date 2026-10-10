import axios from 'axios'

// Một instance Axios dùng chung cho toàn dự án.
// Sau này ta sẽ thêm interceptor để tự gắn token và tự refresh.
const api = axios.create({
  baseURL: '/api', // đi qua Vite proxy sang Django
  timeout: 10000,  // quá 10 giây coi như lỗi
})

export default api
