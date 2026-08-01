// ODY7 — Les liens CROISÉS changent d'app PROPREMENT.
// ----------------------------------------------------------------------------
// AUDIT (fait pour cette tâche, sur `pages/` + `features/`) : TOUTES les
// navigations inter-apps réelles — client → devis (`ClientList.jsx`),
// devis → lead / bon de commande / facture / chantier (`DevisList.jsx`),
// chantier → client / lead / devis / contrat SAV (`InstallationDetail.jsx`),
// OCR → factures fournisseur (`OcrUpload.jsx`), client → archive
// (`ClientDetailPanel.jsx`) — passent par `navigate()` de react-router. Les
// SEULES navigations « dures » (`window.location.href`) du frontend visent
// `/login` depuis `SessionProvider.jsx` (expiration de session, volontaire).
// Aucun point d'appel ne rend donc l'écran d'une app « dans » la coquille d'une
// autre : la coquille étant DÉRIVÉE de la route (ODY4), elle se reconstruit
// entièrement sur l'app cible dès que l'URL change. Ce fichier VERROUILLE cette
// propriété sur 6 parcours croisés réels + 1 contrôle intra-app.
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import Sidebar from '../../components/layout/Sidebar'
import { useCrossAppNavigate, crossAppTransition } from './ActiveAppContext'

function makeStore({ role = 'admin', permissions = [], modulesDesactives = [] } = {}) {
  return configureStore({
    reducer: {
      auth: (s = { role, permissions, modulesDesactives, user: null }) => s,
      parametres: (s = { profile: { nom: 'TAQINOR' } }) => s,
    },
  })
}

// Bouton de test qui suit un lien croisé EXACTEMENT comme un écran réel :
// via le point d'entrée nommé `useCrossAppNavigate` (ODY7).
function CrossLink({ to }) {
  const crossAppNavigate = useCrossAppNavigate()
  return <button type="button" onClick={() => crossAppNavigate(to)}>suivre</button>
}

function renderJourney(from, to) {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={[from]}>
        <CrossLink to={to} />
        <Sidebar collapsed={false} onToggle={() => {}} onNavigate={() => {}} />
      </MemoryRouter>
    </Provider>,
  )
}

const appName = (c) => c.querySelector('.sidebar-app-name')?.textContent ?? null
const navHrefs = (c) =>
  Array.from(c.querySelectorAll('.sidebar-nav a')).map((a) => a.getAttribute('href'))

// Les 6 parcours croisés RÉELS recensés par l'audit ci-dessus.
const JOURNEYS = [
  { name: 'client → devis', from: '/crm', to: '/ventes/devis/nouveau?client=1', source: 'CRM', target: 'VENTES' },
  { name: 'devis → lead', from: '/ventes/devis', to: '/crm/leads?lead=7', source: 'VENTES', target: 'CRM' },
  { name: 'devis → chantier', from: '/ventes/devis', to: '/chantiers', source: 'VENTES', target: 'CHANTIERS' },
  { name: 'chantier → contrat SAV', from: '/chantiers', to: '/sav/contrats', source: 'CHANTIERS', target: 'APRÈS-VENTE' },
  { name: 'OCR → factures fournisseur', from: '/ia/ocr', to: '/stock/factures-fournisseur', source: 'INTELLIGENCE', target: 'STOCK' },
  { name: 'ticket SAV → client', from: '/sav', to: '/crm', source: 'APRÈS-VENTE', target: 'CRM' },
]

describe('ODY7 — un lien croisé bascule la coquille sur l’app CIBLE', () => {
  JOURNEYS.forEach(({ name, from, to, source, target }) => {
    it(`${name} : ${source} → ${target}`, async () => {
      const { container } = renderJourney(from, to)
      expect(appName(container)).toBe(source)
      const before = navHrefs(container)

      await userEvent.click(screen.getByRole('button', { name: 'suivre' }))

      // 1. l'identité de la coquille est celle de l'app CIBLE…
      expect(appName(container)).toBe(target)
      // 2. …et plus AUCUNE destination de l'app source n'y subsiste (jamais un
      //    écran cible rendu « dans » la coquille source).
      const after = navHrefs(container)
      expect(after.length).toBeGreaterThan(0)
      expect(after.filter((h) => before.includes(h))).toEqual([])
    })
  })

  it('contrôle : une navigation INTRA-app ne rebâtit pas la coquille', async () => {
    const { container } = renderJourney('/ventes/devis', '/ventes/factures')
    const before = navHrefs(container)
    await userEvent.click(screen.getByRole('button', { name: 'suivre' }))
    expect(appName(container)).toBe('VENTES')
    expect(navHrefs(container)).toEqual(before)
  })

  it('crossAppTransition décrit chaque parcours (from / to / switched)', () => {
    JOURNEYS.forEach(({ from, to }) => {
      const transition = crossAppTransition(from, to)
      expect(transition.switched).toBe(true)
      expect(transition.from).toBeTruthy()
      expect(transition.to).toBeTruthy()
      expect(transition.from).not.toBe(transition.to)
    })
    expect(crossAppTransition('/ventes/devis', '/ventes/factures').switched).toBe(false)
  })
})
