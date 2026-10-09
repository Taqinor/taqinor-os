import { render } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import TicketSuiviPage from '../TicketSuiviPage'

// Rend la page publique de suivi de ticket sur /suivi/tok (l'appelant mocke
// '../../api/axios' dans son propre fichier de test).
export const renderSuiviPage = () => render(
  <MemoryRouter initialEntries={['/suivi/tok']}>
    <Routes><Route path="/suivi/:token" element={<TicketSuiviPage />} /></Routes>
  </MemoryRouter>,
)
