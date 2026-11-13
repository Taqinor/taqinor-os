// AERR120 — jumeau d'ACVI68 sur la fiche lead PLEINE PAGE (`/crm/leads/<id>`) :
// un refus d'acceptation rouvre « Signé » pré-rempli, l'erreur sous son champ,
// sans quitter la page. Nouveau fichier car : aucun module de test pour
// LeadDetailPage.
//
// Run : npx vitest run src/pages/crm/leads/LeadDetailPage.test.jsx
import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import { mockMatchMedia } from '../../../test/matchMedia'

const etat = vi.hoisted(() => ({
  props: null,
  devis: {
    id: 77, reference: 'DEV-SIGNE-77', statut: 'envoye', total_ttc: 90000, nb_options: 2,
    date_creation: '2026-09-01', mode_installation: 'industriel',
  },
}))

vi.mock('../../../api/crmApi', async (importOriginal) =>
  (await import('../../../test/etendreApi')).etendreApi(importOriginal, {
    getLead: vi.fn(() => Promise.resolve({ data: { id: 12, nom: 'Alami', prenom: 'Karim' } })),
  }))
vi.mock('../../../api/ventesApi', async (importOriginal) =>
  (await import('../../../test/etendreApi')).etendreApi(importOriginal, {
    getDevis: vi.fn(() => Promise.resolve({ data: { results: [etat.devis] } })),
  }))
// La fiche elle-même est hors sujet : seul compte ce que la PAGE fait du
// refus que la fiche lui remonte (`onSigneRefuse`).
vi.mock('../../../features/crm/workspace/LeadWorkspace', () => ({
  default: (props) => { etat.props = props; return <div data-testid="lead-workspace" /> },
}))
vi.mock('../../../features/uxviews/FavoriButton', () => ({ default: () => null }))

import LeadDetailPage from './LeadDetailPage'

beforeAll(() => { if (typeof window.matchMedia !== 'function') mockMatchMedia(false) })

function Chemin() {
  return <span data-testid="chemin">{useLocation().pathname}</span>
}

describe('LeadDetailPage — AERR120 refus de « Signé »', () => {
  it('refus de Signé : dialogue rouvert pré-rempli, page gardée', async () => {
    render(
      <MemoryRouter initialEntries={['/crm/leads/12']}>
        <Routes>
          <Route path="/crm/leads/:id" element={<><LeadDetailPage /><Chemin /></>} />
          <Route path="/crm/leads" element={<Chemin />} />
        </Routes>
      </MemoryRouter>,
    )
    await screen.findByTestId('lead-workspace')
    // La fiche a fermé son dialogue au clic (fête), puis le serveur refuse.
    act(() => {
      etat.props.onSigneRefuse({ id: 12, nom: 'Alami', prenom: 'Karim' }, {
        saisie: {
          devisId: '77', optionChoice: 'avec_batterie', nom: 'K. Alami', date: '2026-11-02',
          entrepriseSaisie: { raison_sociale: 'Alami SARL', signataire_qualite: 'Gérant', ice: '001122334455667' },
          message: null,
        },
        erreurs: { date: 'Date invalide.' },
      })
    })
    await screen.findByLabelText('Devis accepté')
    expect(screen.getByLabelText(/Nom de la personne/)).toHaveValue('K. Alami')
    expect(screen.getByLabelText("Date d'acceptation")).toHaveValue('2026-11-02')
    expect(screen.getByRole('radio', { name: /Avec batterie/ })).toBeChecked()
    expect(screen.getByLabelText('ICE')).toHaveValue('001122334455667')
    expect(screen.getByText('Date invalide.')).toBeInTheDocument()
    expect(screen.getByTestId('chemin')).toHaveTextContent('/crm/leads/12')
  })
})
