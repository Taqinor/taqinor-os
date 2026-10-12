import { useState } from 'react'
import { describe, it, expect, afterEach, vi } from 'vitest'
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
function ctx(extra = {}) {
  return {
    selectedIds: [], toggleSelected: noop, histoCache: {}, lectureClientCache: {},
    variantesEtat: {}, superieurStatus: {}, pdfGenerating: {}, pdfDownloading: {}, pdfSlowPoll: {}, convertingId: null, basculerVersions: noop, toggleHistorique: noop,
    canValiderVente: true, canDelete: true, role: 'admin',
    dispatch: noop, navigate: noop, setFacturerTarget: noop, setRoofOpenId: noop,
    ...extra,
  }
}
function rendre(d, extra = {}) {
  const store = configureStore({
    reducer: { auth: (s = { user: {} }) => s, ventes: (s = {}) => s },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <table><tbody><DevisRow d={d} ctx={ctx(extra)} /></tbody></table>
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

/* VNT79 — la liste lit `d.vente` (VNT68) : UN seul bouton « Facturer… » (ouvert
   par `vente.peut`, jamais sur une version remplacée), une puce de résumé qui
   ouvre la sous-ligne PanneauVente, plus aucune comparaison de chaînes
   (`'9' >= '10'` était vrai), « Réviser » lit `peutReviserDevis`. */
describe('VNT79 — liste des devis : puce, panneau, bouton unique', () => {
  const vente = (variante) => exempleContrat('ventes', 'vente_etat', variante).vente
  const ACCEPTE = {
    ...BASE, id: 502, reference: 'DEV-202610-0021', statut: 'accepte', version: 2,
    vente: vente('exemple'),
  }
  const HERITES = /Générer facture|Facturer par tranches|Facturer \(facture complète\)|Échéancier complet/

  it('accepté avec acompte ouvert : un seul bouton « Facturer… », il cible CE devis', async () => {
    const setFacturerTarget = vi.fn()
    rendre(ACCEPTE, { setFacturerTarget })
    expect(screen.getAllByRole('button', { name: /^Facturer/ })).toHaveLength(1)
    expect(screen.queryByRole('button', { name: HERITES })).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Facturer…' }))
    expect(setFacturerTarget).toHaveBeenCalledWith(ACCEPTE)
  })

  it('plus de comparaison de chaînes : solde "9" sur "10" ne ferme plus la facturation', () => {
    rendre({ ...ACCEPTE, solde: { tranches_facturees: '9', tranches_total: '10' } })
    expect(screen.getByRole('button', { name: 'Facturer…' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: HERITES })).toBeNull()
  })

  it.each(['exemple_tout_facture', 'exemple_acompte_brouillon', 'exemple_revision_en_cours'])(
    '%s : le serveur ferme la facturation, aucun bouton « Facturer… »', (variante) => {
      rendre({ ...ACCEPTE, vente: vente(variante) })
      expect(screen.queryByRole('button', { name: /^Facturer/ })).toBeNull()
      expect(screen.queryByRole('button', { name: HERITES })).toBeNull()
    })

  it('version remplacée : aucun bouton « Facturer… », la puce reste lisible', () => {
    rendre({ ...ACCEPTE, id: 501, is_active: false, vente: vente('exemple_version_remplacee') })
    expect(screen.queryByRole('button', { name: /^Facturer/ })).toBeNull()
    expect(screen.getByTestId('vente-puce-501')).toBeTruthy()
  })

  it('sans `vente` (ancien serveur) : ni puce ni bouton', () => {
    const { vente: _v, ...sans } = ACCEPTE
    rendre(sans)
    expect(screen.queryByTestId('vente-puce-502')).toBeNull()
    expect(screen.queryByRole('button', { name: /^Facturer/ })).toBeNull()
  })

  it('la puce ouvre puis referme la sous-ligne PanneauVente (colSpan 8)', async () => {
    function Hote() {
      const [ouvert, setOuvert] = useState(null)
      return (
        <table><tbody>
          <DevisRow d={ACCEPTE} ctx={ctx({ panneauVenteOpenId: ouvert, setPanneauVenteOpenId: setOuvert })} />
        </tbody></table>
      )
    }
    const store = configureStore({ reducer: { auth: (s = { user: {} }) => s, ventes: (s = {}) => s } })
    render(<Provider store={store}><MemoryRouter><Hote /></MemoryRouter></Provider>)
    expect(screen.queryByTestId('panneau-vente-502')).toBeNull()
    await userEvent.click(screen.getByTestId('vente-puce-502'))
    const panneau = screen.getByTestId('panneau-vente-502')
    expect(panneau.closest('td').getAttribute('colspan')).toBe('8')
    await userEvent.click(screen.getByTestId('vente-puce-502'))
    expect(screen.queryByTestId('panneau-vente-502')).toBeNull()
  })

  it('« Réviser » suit peutReviserDevis (revision_possible servi), plus un prédicat local', async () => {
    rendre({ ...BASE, id: 7, revision_possible: false })
    await userEvent.click(screen.getByRole('button', { name: /plus d'actions/i }))
    expect(screen.queryByText(/Réviser \(nouvelle version\)/)).toBeNull()
    cleanup()
    rendre({ ...BASE, id: 8, revision_possible: true })
    await userEvent.click(screen.getByRole('button', { name: /plus d'actions/i }))
    expect(screen.getByText(/Réviser \(nouvelle version\)/)).toBeTruthy()
  })
})
