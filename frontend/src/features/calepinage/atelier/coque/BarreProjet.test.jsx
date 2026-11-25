/* Nouveau fichier car : aucun test existant ne porte `BarreProjet` (ACAL2023).
   « Montrer au client » s'ouvre depuis la barre : l'entrée ne porte AUCUN chiffre et ne calcule AUCUNE estimation — elle ouvre la
   vue client (`/calepinage/:id/client`), qui lit la conception courante servie (client/VueClient.test.jsx, ACAL2023). */
import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import BarreProjet from './BarreProjet'

afterEach(cleanup)

const rendre = () => render(
  <MemoryRouter initialEntries={['/calepinage/7']}>
    <Routes>
      <Route path="/calepinage/:id" element={(
        <BarreProjet retour={{ to: '/calepinage', libelle: 'Calepinages' }} titre="Villa Bennani" sousTitre="5 panneaux · 3,55 kWc"
          onExpert={() => {}} />
      )} />
    </Routes>
  </MemoryRouter>,
)

describe('BarreProjet — l’entrée « Montrer au client »', () => {
  it('ouvre la vue client du calepinage, sans chiffre ni estimation propres', () => {
    rendre()
    const entree = screen.getByTestId('cal-barre-montrer-client')
    expect(entree).toHaveAttribute('href', '/calepinage/7/client')
    expect(entree).toHaveTextContent('Montrer au client')
    expect(entree.textContent).not.toMatch(/\d|kWh|%|MAD|estimation/)
  })
})
