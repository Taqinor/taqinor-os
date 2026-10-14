import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import DevisRow from './DevisRow'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

// ADEV8 — le VRAI DevisRow est rendu ; une version envoyée REMPLACÉE
// (is_active=false) n'offre ni Relancer / Accepter / Refuser / Copier le lien
// et affiche « Remplacée par <réf> ». La version active garde tous ses gestes.
afterEach(() => cleanup())

const noop = () => {}
function ctx() {
  return {
    selectedIds: [], toggleSelected: noop, histoCache: {}, lectureClientCache: {},
    variantesEtat: {}, superieurStatus: {}, pdfGenerating: {}, pdfDownloading: {}, pdfSlowPoll: {}, convertingId: null, basculerVersions: noop, toggleHistorique: noop,
    canValiderVente: true, canDelete: true, role: 'admin',
    dispatch: noop, navigate: noop, setFacturerTarget: noop, setRoofOpenId: noop,
  }
}
function rendre(d) {
  const store = configureStore({
    reducer: { auth: (s = { user: {} }) => s, ventes: (s = {}) => s },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <table><tbody><DevisRow d={d} ctx={ctx()} /></tbody></table>
      </MemoryRouter>
    </Provider>,
  )
}
const BASE = {
  id: 1, reference: 'DEV-1', statut: 'envoye', version: 1, client_nom: 'X',
  total_ttc: 1000, is_active: true,
}

describe('ADEV8 — version remplacée en lecture seule', () => {
  it('V1 remplacée : aucun geste, libellé « Remplacée par »', async () => {
    rendre({ ...BASE, is_active: false, superseded_by_ref: 'DEV-2' })
    expect(screen.queryByRole('button', { name: /relancer/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /accepter/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /refuser/i })).toBeNull()
    expect(screen.getByTestId('devis-remplacee-par').textContent).toMatch(/Remplacée par DEV-2/)
    await userEvent.click(screen.getByRole('button', { name: /plus d'actions/i }))
    expect(screen.queryByText(/Copier le lien de la proposition/i)).toBeNull()
    expect(screen.queryByText(/Copier l.aperçu interne/i)).toBeNull()
  })

  it('V2 active : garde tous ses gestes', async () => {
    rendre({ ...BASE, reference: 'DEV-2', version: 2 })
    expect(screen.getByRole('button', { name: /relancer/i })).toBeTruthy()
    expect(screen.getByRole('button', { name: /accepter/i })).toBeTruthy()
    expect(screen.getByRole('button', { name: /refuser/i })).toBeTruthy()
    expect(screen.queryByTestId('devis-remplacee-par')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: /plus d'actions/i }))
    expect(screen.getByText(/Copier le lien de la proposition/i)).toBeTruthy()
  })
})

// VNT79 — sur un accepté, le bouton unique « Facturer… » suit `vente.peut` et
// n'existe jamais sur une version remplacée (exemples committés vente_etat.json).
describe('VNT79 — « Facturer… » jamais sur une version remplacée', () => {
  const accepte = (variante) => {
    const ex = exempleContrat('ventes', 'vente_etat', variante)
    return {
      ...BASE, id: ex.id, reference: ex.reference, statut: 'accepte',
      is_active: ex.vente.est_tete, vente: ex.vente,
    }
  }

  it('V1 remplacée acceptée : aucun « Facturer… »', () => {
    rendre(accepte('exemple_version_remplacee'))
    expect(screen.queryByRole('button', { name: 'Facturer…' })).toBeNull()
  })

  it('tête acceptée : un seul « Facturer… »', () => {
    rendre(accepte('exemple'))
    expect(screen.getAllByRole('button', { name: /^Facturer/ })).toHaveLength(1)
  })
})
