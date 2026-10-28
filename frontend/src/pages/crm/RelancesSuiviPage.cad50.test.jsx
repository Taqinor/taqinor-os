import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '../../test/relancesSuiviHarness'
import { isAdminOrResponsableMock } from '../../test/relancesSuiviMocks'
import { screen, cleanup, waitFor, fireEvent } from '@testing-library/react'

/* CAD50 — « Annuler » (retour arrière 24h) et « Arrêter la cadence » (motif
   obligatoire) directement sur la ligne du Suivi des relances : les deux
   actions n'existaient auparavant que sur la fiche du lead. Contrairement
   au Cockpit (RelancesDuJourWidget.jsx), cet écran sert TOUS les statuts —
   une touche fait/sautée récente est donc directement dans la réponse
   serveur, sans suivi local séparé. */
import { exempleContrat } from '../../test/fixtures/contractSamples'

const ETAPE_MODELE = exempleContrat('crm', 'relance_etapes_suivi').results[0]

vi.mock('../../api/crmApi', async () => (await import('../../test/relancesSuiviMocks')).crmApiSuivi({
  getMesureCadence: vi.fn(() => Promise.reject(new Error('non pertinent ici'))),
  annulerRelanceEtape: vi.fn(),
  arreterCadence: vi.fn(),
}))

import crmApi from '../../api/crmApi'
import { arreterCadenceAvecMotif } from '../../test/arreterCadenceMotif'

function casaISO(d) {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Casablanca' }).format(d)
}

beforeEach(() => {
  isAdminOrResponsableMock.mockReturnValue(false)
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('RelancesSuiviPage — CAD50 (« Annuler »/« Arrêter » hors fiche)', () => {
  it('une touche « a_faire » porte « Arrêter la cadence », motif obligatoire, appelle crmApi.arreterCadence(leadId, {motif})', async () => {
    crmApi.getRelanceEtapesSuivi.mockResolvedValue({
      data: {
        results: [{ ...ETAPE_MODELE, id: 900, statut: 'a_faire', traite_le: null, due_date: casaISO(new Date()) }],
        resume: { a_faire: 1, en_retard: 0, fait: 0, sautee: 0, annulee: 0 },
      },
    })
    crmApi.arreterCadence.mockResolvedValue({ data: { arretees: 1 } })
    mount()
    await screen.findAllByTestId('relance-etape-row')

    await arreterCadenceAvecMotif(crmApi, ETAPE_MODELE.lead)
  })

  it('une touche « fait » traitée il y a moins de 24h porte « Annuler », qui appelle crmApi.annulerRelanceEtape', async () => {
    const ilYA2H = new Date(Date.now() - 2 * 3600 * 1000).toISOString()
    crmApi.getRelanceEtapesSuivi.mockResolvedValue({
      data: {
        results: [{
          ...ETAPE_MODELE, id: 901, statut: 'fait', traite_le: ilYA2H, due_date: casaISO(new Date()),
        }],
        resume: { a_faire: 0, en_retard: 0, fait: 1, sautee: 0, annulee: 0 },
      },
    })
    mount()
    await screen.findAllByTestId('relance-etape-row')

    const bouton = screen.getByRole('button', { name: 'Annuler' })
    fireEvent.click(bouton)
    await waitFor(() => expect(crmApi.annulerRelanceEtape).toHaveBeenCalledWith(901))
  })

  it('une touche « fait » traitée il y a plus de 24h ne porte PAS « Annuler »', async () => {
    const ilYA48H = new Date(Date.now() - 48 * 3600 * 1000).toISOString()
    crmApi.getRelanceEtapesSuivi.mockResolvedValue({
      data: {
        results: [{
          ...ETAPE_MODELE, id: 902, statut: 'fait', traite_le: ilYA48H, due_date: casaISO(new Date()),
        }],
        resume: { a_faire: 0, en_retard: 0, fait: 1, sautee: 0, annulee: 0 },
      },
    })
    mount()
    await screen.findAllByTestId('relance-etape-row')
    expect(screen.queryByRole('button', { name: 'Annuler' })).not.toBeInTheDocument()
  })
})
