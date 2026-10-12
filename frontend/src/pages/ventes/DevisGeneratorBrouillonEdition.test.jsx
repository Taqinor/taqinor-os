// QJR581 — ouvrir un devis sans rien changer ne crée plus de « brouillon non
// enregistré » ; un brouillon local périmé (devis modifié depuis) n'est jamais
// proposé ; la garde de sortie se désarme après un enregistrement réussi.
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorBrouillonEdition.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'

import { estimerMois } from '../../features/ventes/solar'
import { exempleContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiAvecLead())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiEdition())

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'
import { declarerBeforeEachDevis, lignesResidentielles, makeDevisStore, renderEditionPage } from './devisGenerator.testHelpers.jsx'

const CLE = 'taqinor:draft:devis:edit:42'
const UPDATED_AT = '2026-09-30T10:00:00Z'
const PANNEAU = { id: 101, nom: 'Panneau Canadien Solar 715W', prix_vente: 1200, tva: 10, is_archived: false }
const ONDULEUR = { id: 102, nom: 'Onduleur réseau 5kW Monophasé', prix_vente: 9000, tva: 20, is_archived: false }
const LEAD = { id: 7, nom: 'Karim', prenom: 'Brouillon', facture_hiver: '2000', ete_differente: false }

function devis42() {
  const contrat = exempleContrat('ventes', 'devis_modifiabilite', 'exemple_brouillon')
  return {
    data: {
      ...contrat, id: 42, lead: 7, client: 9, lead_nom: 'Karim Brouillon',
      updated_at: UPDATED_AT,
      mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
      etude_params: { scenario: 'Sans batterie', factures_mensuelles_reelles: estimerMois(2000, 2000) },
      lignes: lignesResidentielles(PANNEAU, ONDULEUR),
    },
  }
}

const makeStore = () => makeDevisStore('normal', 'Commercial')

function renderEdition() {
  return renderEditionPage(DevisGenerator, makeStore(), 42)
}

const quitterBloque = () => {
  const ev = new Event('beforeunload', { cancelable: true })
  window.dispatchEvent(ev)
  return ev.defaultPrevented
}

declarerBeforeEachDevis({ stockApi, crmApi, ventesApi, produits: [PANNEAU, ONDULEUR], lead: LEAD, devis: () => devis42(), ecritures: true, localStorage: true })

describe('QJR581 — brouillon local en Édition complète', () => {
  it('rouvrir le devis 42 sans rien changer : aucun brouillon écrit, aucune garde de sortie', async () => {
    renderEdition()
    await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(7))
    await new Promise(r => setTimeout(r, 2200))
    expect(window.localStorage.getItem(CLE)).toBeNull()
    expect(quitterBloque()).toBe(false)
  }, 15000)

  it('getLead résolu après la fenêtre de 1,5 s : toujours aucun brouillon, aucune garde', async () => {
    crmApi.getLead.mockImplementation(() => new Promise(r => setTimeout(() => r({ data: LEAD }), 2000)))
    renderEdition()
    await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(7))
    await new Promise(r => setTimeout(r, 4200))
    expect(window.localStorage.getItem(CLE)).toBeNull()
    expect(quitterBloque()).toBe(false)
  }, 15000)

  it('brouillon local à updated_at ancien : aucun bandeau « Reprendre », brouillon purgé', async () => {
    window.localStorage.setItem(CLE, JSON.stringify({
      savedAt: '2026-09-29T08:00:00Z', version: '2026-09-29T07:00:00Z', data: { note: 'vieux' },
    }))
    renderEdition()
    await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    await waitFor(() => expect(window.localStorage.getItem(CLE)).toBeNull())
    expect(screen.queryByTestId('draft-restore-banner')).toBeNull()
  })

  it('brouillon local à updated_at courant : « Reprendre » proposé', async () => {
    window.localStorage.setItem(CLE, JSON.stringify({
      savedAt: '2026-09-30T11:00:00Z', version: UPDATED_AT, data: { note: 'récent' },
    }))
    renderEdition()
    expect(await screen.findByTestId('draft-restore-banner')).toBeTruthy()
  })

  it('après un enregistrement réussi : la garde de sortie est désarmée', async () => {
    renderEdition()
    await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(7))
    await new Promise(r => setTimeout(r, 1700))
    fireEvent.change(screen.getByPlaceholderText(/Conditions particulières/), { target: { value: 'Acompte 30 %' } })
    await waitFor(() => expect(quitterBloque()).toBe(true))
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer les modifications/ }))
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalled())
    await waitFor(() => expect(quitterBloque()).toBe(false))
  }, 15000)

  // ATOT20 — DEV-DEMO-0001 : lignes SANS taux (`taux_tva` null), panneau
  // produit 10 %, devis 20 %. Le serveur les chiffre au taux du DEVIS ; l'écran
  // aussi (jamais `produit_tva`) : ouvrir puis enregistrer sans toucher écrit
  // '20' et ne déclenche aucune garde de sortie, ni à l'ouverture ni après.
  it('ouvrir puis enregistrer sans toucher : aucun beforeunload, ni à l’ouverture ni après l’enregistrement', async () => {
    const d = devis42()
    d.data.lignes = d.data.lignes.map(l => ({ ...l, taux_tva: null, produit_tva: l.produit === PANNEAU.id ? '10.00' : '20.00' }))
    ventesApi.getDevisById.mockResolvedValue(d)
    ventesApi.replaceLignesDevis.mockResolvedValue({ data: { updated_at: '2026-09-30T10:05:00Z' } })
    renderEdition()
    await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(7))
    await new Promise(r => setTimeout(r, 2200))
    expect(quitterBloque()).toBe(false)
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer les modifications/ }))
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalled())
    const [, lignes] = ventesApi.replaceLignesDevis.mock.calls.at(-1)
    expect(lignes.map(l => l.taux_tva)).toEqual(['20', '20'])
    await new Promise(r => setTimeout(r, 1200))
    expect(quitterBloque()).toBe(false)
    expect(window.localStorage.getItem(CLE)).toBeNull()
  }, 20000)
})
