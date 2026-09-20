// RLC1 — « Annuler » sur la frise de cadence : une touche traitée par erreur
// se défait pendant 24 h, depuis la fiche, et le motif d'un refus SERVEUR
// s'affiche sous la ligne concernée (jamais un toast générique).
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { exempleContrat } from '../../../../test/fixtures/contractSamples'

const ETAPES = exempleContrat('crm', 'relance_etape_v2').results

vi.mock('../../../../api/crmApi', () => ({
  default: {
    getRelanceEtapesLead: vi.fn(),
    marquerRelanceEtapeFait: vi.fn(),
    marquerRelanceEtapeSautee: vi.fn(),
    reporterRelanceEtape: vi.fn(),
    getRelanceEtapeMessage: vi.fn(),
    whatsappRelanceEtape: vi.fn(),
    annulerRelanceEtape: vi.fn(() => Promise.resolve({ data: { statut: 'a_faire' } })),
  },
}))
vi.mock('../../../../lib/toast', () => ({ toastError: vi.fn() }))

import crmApi from '../../../../api/crmApi'
import { toastError } from '../../../../lib/toast'
import CadenceFrise from './CadenceFrise'

/** Une touche TRAITÉE il y a `heures`, dérivée du contrat committé. */
const traitee = (attrs) => ({
  ...ETAPES[0], id: 701, statut: 'fait', overdue: false,
  traite_par_nom: 'commerciale',
  ...attrs,
})
const ilYA = (heures) => new Date(Date.now() - heures * 3600 * 1000).toISOString()

const servir = (etapes) => {
  crmApi.getRelanceEtapesLead.mockResolvedValue(
    { data: { count: etapes.length, results: etapes } })
}

beforeEach(() => { servir([traitee({ traite_le: ilYA(1) })]) })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('RLC1 — Annuler une touche traitée', () => {
  it('une touche traitée il y a 1 h porte « Annuler », visible sans déplier l\'historique', async () => {
    render(<CadenceFrise leadId={1489} />)
    expect(await screen.findByTestId('frise-annuler')).toBeInTheDocument()
  })

  it('une touche traitée il y a plus de 24 h ne porte plus « Annuler »', async () => {
    servir([traitee({ traite_le: ilYA(25) })])
    render(<CadenceFrise leadId={1489} />)
    // La ligne existe (dépliée depuis l'historique), mais sans bouton.
    await screen.findByRole('button', { name: /touche\(s\) passée\(s\)/ })
    expect(screen.queryByTestId('frise-annuler')).toBeNull()
  })

  it('une annulation MOTEUR ne porte jamais « Annuler » (ce n\'est le geste de personne)', async () => {
    servir([traitee({ statut: 'annulee', note: 'joint', traite_le: ilYA(1) })])
    render(<CadenceFrise leadId={1489} />)
    await screen.findByRole('button', { name: /touche\(s\) passée\(s\)/ })
    expect(screen.queryByTestId('frise-annuler')).toBeNull()
  })

  it('clic « Annuler » → appelle le serveur et prévient le parent (frise + fiche)', async () => {
    const onChanged = vi.fn()
    render(<CadenceFrise leadId={1489} onChanged={onChanged} />)
    fireEvent.click(await screen.findByTestId('frise-annuler'))
    await waitFor(() => expect(crmApi.annulerRelanceEtape).toHaveBeenCalledWith(701))
    await waitFor(() => expect(onChanged).toHaveBeenCalled())
    expect(screen.queryByTestId('frise-annuler-erreur')).toBeNull()
  })

  it('refus serveur (400) : le motif EXACT s\'affiche sous la ligne, pas un toast', async () => {
    const motif = "Cette touche a acté l'envoi du devis : cet effet ne se défait pas ici."
    crmApi.annulerRelanceEtape.mockRejectedValue({
      response: { status: 400, data: { erreurs: { statut: motif } } },
    })
    render(<CadenceFrise leadId={1489} />)
    fireEvent.click(await screen.findByTestId('frise-annuler'))
    expect(await screen.findByTestId('frise-annuler-erreur')).toHaveTextContent(motif)
    expect(toastError).not.toHaveBeenCalled()
  })

  it('panne réseau : un toast, et aucun message de champ inventé', async () => {
    crmApi.annulerRelanceEtape.mockRejectedValue(new Error('boom'))
    render(<CadenceFrise leadId={1489} />)
    fireEvent.click(await screen.findByTestId('frise-annuler'))
    await waitFor(() => expect(toastError).toHaveBeenCalled())
    expect(screen.queryByTestId('frise-annuler-erreur')).toBeNull()
  })
})
