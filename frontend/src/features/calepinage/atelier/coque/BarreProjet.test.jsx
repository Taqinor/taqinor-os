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

describe('BarreProjet — « Générer le devis » selon le droit (D-ACAL-106)', () => {
  it('sans `ventes_creer` (Technicien) le bouton n\'est pas proposé ; avec, il l\'est', async () => {
    const { Provider } = await import('react-redux')
    const { configureStore } = await import('@reduxjs/toolkit')
    const boutique = (permissions) => configureStore({ reducer: { auth: (s = { role: 'technicien', permissions }) => s } })
    const monter = (permissions) => render(
      <Provider store={boutique(permissions)}>
        <MemoryRouter initialEntries={['/calepinage/7']}>
          <Routes>
            <Route path="/calepinage/:id" element={(
              <BarreProjet retour={{ to: '/calepinage', libelle: 'Calepinages' }} titre="Villa" onExpert={() => {}} onDevis={() => {}} />
            )} />
          </Routes>
        </MemoryRouter>
      </Provider>,
    )
    const { unmount } = monter(['calepinage_voir', 'calepinage_releve'])
    expect(screen.queryByTestId('cal-generer-devis-haut')).toBeNull()
    unmount()
    monter(['calepinage_voir', 'ventes_creer'])
    expect(screen.getByTestId('cal-generer-devis-haut')).toBeInTheDocument()
  })
})
