import { useState, useEffect } from 'react'
import { useDispatch } from 'react-redux'
import { fetchMe } from '../../features/auth/store/authSlice'
import { fetchProfile } from '../../features/parametres/store/parametresSlice'
import Sidebar from './Sidebar'
import Header from './Header'

export default function Layout({ children }) {
  const dispatch = useDispatch()
  const [collapsed, setCollapsed] = useState(false)

  useEffect(() => {
    dispatch(fetchMe())
    dispatch(fetchProfile())
  }, [dispatch])

  return (
    <div className="layout">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(v => !v)} />
      <div className="layout-main">
        <Header />
        <main className="layout-content">
          {children}
        </main>
      </div>
    </div>
  )
}
