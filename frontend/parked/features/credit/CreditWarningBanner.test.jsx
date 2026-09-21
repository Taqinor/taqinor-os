import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

/* WIR188/NTCRD11 — La bannière d'alerte crédit était CONSTRUITE mais montée
   NULLE PART, et elle embarquait sa PROPRE copie du formulaire de dérogation —
   doublon exact de `DemandeDerogationWizard` (NTCRD28) : deux implémentations
   de la même écriture, deux règles de motif à garder synchrones, et déjà deux
   libellés de bouton différents. Un SEUL composant subsiste désormais. */

vi.mock('../../api/creditApi', () => ({
  default: {
    createDerogation: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
    getFicheClient: vi.fn(() => Promise.resolve({
      data: { encours: '9000', limite: '10000', lettre_score: 'B' },
    })),
  },
}))

import creditApi from '../../api/creditApi'
import CreditWarningBanner from './CreditWarningBanner'

beforeEach(() => { vi.clearAllMocks() })

describe('CreditWarningBanner (WIR188) — les trois modes', () => {
  it('mode « aucun » : RIEN n’est rendu (aucun bruit)', () => {
    const { container } = render(
      <CreditWarningBanner
        warning={{ mode: 'aucun', depassement: '0.00', disponible: null }}
        clientId={3} montant="5000"
      />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('warning absent : RIEN n’est rendu', () => {
    const { container } = render(
      <CreditWarningBanner warning={null} clientId={3} montant="5000" />)
    expect(container).toBeEmptyDOMElement()
  })

  it('mode « avertissement » : orange, non bloquant, sans dérogation', () => {
    render(
      <CreditWarningBanner
        warning={{ mode: 'avertissement', depassement: '4000.00', disponible: '1000.00' }}
        clientId={3} montant="5000"
      />,
    )
    const banniere = screen.getByTestId('credit-warning-banner')
    expect(banniere).toHaveAttribute('data-mode', 'avertissement')
    expect(banniere.className).toContain('credit-banner--warn')
    // `status` et non `alert` : informatif, jamais bloquant.
    expect(banniere).toHaveAttribute('role', 'status')
    expect(banniere).toHaveTextContent(/approche\/dépasse sa limite/)
    // Aucun formulaire de dérogation en mode avertissement.
    expect(screen.queryByTestId('credit-derogation-wizard')).toBeNull()
  })

  it('mode « blocage » : rouge + LE composant unique de dérogation', async () => {
    render(
      <CreditWarningBanner
        warning={{ mode: 'blocage', depassement: '12500.00', disponible: '7500.00' }}
        clientId={3} montant="20000" devisId={42}
      />,
    )
    const banniere = screen.getByTestId('credit-warning-banner')
    expect(banniere).toHaveAttribute('data-mode', 'blocage')
    expect(banniere.className).toContain('credit-banner--block')
    expect(banniere).toHaveAttribute('role', 'alert')
    // C'est le wizard NTCRD28 qui est monté — plus la copie inline.
    expect(await screen.findByTestId('credit-derogation-wizard')).toBeInTheDocument()
  })

  it('le dépassement TEXTE du serveur est bien lu comme un nombre', () => {
    // Le serveur sérialise « 0.00 » en TEXTE : une comparaison brute
    // `depassement > 0` sur une chaîne serait fausse en JS.
    render(
      <CreditWarningBanner
        warning={{ mode: 'avertissement', depassement: '0.00', disponible: '1000.00' }}
        clientId={3} montant="500"
      />,
    )
    expect(screen.getByTestId('credit-warning-banner'))
      .not.toHaveTextContent(/Dépassement estimé/)
  })
})

describe('CreditWarningBanner (WIR188) — soumission de la dérogation', () => {
  it('soumet via l’UNIQUE composant, puis confirme', async () => {
    const onDerogationDemandee = vi.fn()
    render(
      <CreditWarningBanner
        warning={{ mode: 'blocage', depassement: '12500.00', disponible: '7500.00' }}
        clientId={3} montant="20000" devisId={42}
        onDerogationDemandee={onDerogationDemandee}
      />,
    )
    const zone = await screen.findByRole('textbox')
    fireEvent.change(zone, {
      target: { value: 'Client historique, paiement attendu sous 8 jours.' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Soumettre la demande' }))

    await waitFor(() => expect(creditApi.createDerogation).toHaveBeenCalledWith({
      client: 3, montant_demande: '20000', devis: 42,
      motif: 'Client historique, paiement attendu sous 8 jours.',
    }))
    await waitFor(() => expect(onDerogationDemandee).toHaveBeenCalled())
    expect(await screen.findByText(/Demande de dérogation soumise/)).toBeInTheDocument()
    // Le formulaire disparaît : une seule demande par bannière.
    expect(screen.queryByTestId('credit-derogation-wizard')).toBeNull()
  })

  it('un motif trop court ne part jamais (règle unique, celle du wizard)', async () => {
    render(
      <CreditWarningBanner
        warning={{ mode: 'blocage', depassement: '1.00', disponible: '0.00' }}
        clientId={3} montant="20000"
      />,
    )
    const zone = await screen.findByRole('textbox')
    fireEvent.change(zone, { target: { value: 'trop court' } })
    expect(screen.getByRole('button', { name: 'Soumettre la demande' })).toBeDisabled()
    expect(creditApi.createDerogation).not.toHaveBeenCalled()
  })
})
