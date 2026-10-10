import { Route, Routes } from 'react-router-dom'
import HomePage from './pages/HomePage'

// Bảng chỉ đường: đường dẫn "/" thì hiển thị HomePage
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
    </Routes>
  )
}
