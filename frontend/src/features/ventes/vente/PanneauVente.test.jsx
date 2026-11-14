import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

/* AERR17 (C-AERR-015) — « Confirmer l'avoir » émet un avoir : une confirmation
   qui nomme le devis précède l'appel ; « Annuler » n'envoie rien. Mutant :
   retirer le `confirm` de `confirmerAvoir` ⇒ échec. */

vi.mock('../../../api/ventesApi', () => ({
  default: {
    confirmerAvoirRevision: vi.fn(() => Promise.resolve({ data: {} })),
    emettreFacture: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

import ventesApi from '../../../api/ventesApi'
import PanneauVente from './PanneauVente'
import { ConfirmProvider } from '../../../providers/ConfirmProvider.jsx'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const rendre = () => {
  const vente = exempleContrat('ventes', 'vente_etat', 'exemple_avoir_a_confirmer').vente
  return render(
    <ConfirmProvider>
      <PanneauVente devis={{ id: 318, reference: 'DEV-AERR17', vente }} />
    </ConfirmProvider>,
  )
}

describe('PanneauVente — AERR17 : « Confirmer l\'avoir » confirmé', () => {
  it('Confirmer l\'avoir : confirmation, Annuler ⇒ aucun POST', async () => {
    const user = userEvent.setup()
    rendre()
    await user.click(screen.getByRole('button', { name: /Confirmer l'avoir/ }))
    const boite = await screen.findByRole('alertdialog')
    expect(boite).toHaveTextContent('DEV-AERR17')
    expect(boite).toHaveTextContent('Un avoir sera émis')
    await user.click(within(boite).getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
    expect(ventesApi.confirmerAvoirRevision).not.toHaveBeenCalled()

    // CAD177 — le verrou anti-double-clic du Button tombe après 400 ms sans
    // rendu du bouton (Annuler ne le re-rend pas).
    await new Promise((r) => setTimeout(r, 450))
    await user.click(screen.getByRole('button', { name: /Confirmer l'avoir/ }))
    await user.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(ventesApi.confirmerAvoirRevision).toHaveBeenCalledWith(318))
  })
})

describe('AERR137 — Émettre depuis la ligne de vente', () => {
  it('confirmation nommée, Annuler ⇒ aucune émission', async () => {
    // C-AERR-VER1-101 — mutant : rappeler `actions.emettre(f)` sans confirmation ⇒ rouge.
    const user = userEvent.setup()
    const base = exempleContrat('ventes', 'vente_etat', 'exemple_acompte_brouillon').vente
    const vente = { ...base, factures: [{ ...base.factures[0], id: 12, reference: 'BROUILLON-12', total_ttc: '5000.00' }] }
    render(
      <ConfirmProvider>
        <PanneauVente devis={{ id: 502, reference: 'DEV-AERR137', vente }} />
      </ConfirmProvider>,
    )
    const ligne = screen.getByTestId('facture-vente-12')
    await user.click(within(ligne).getByRole('button', { name: 'Émettre' }))
    const boite = await screen.findByRole('alertdialog')
    expect(boite).toHaveTextContent(/Émettre la facture BROUILLON-12 \(5.000,00 MAD\) \?/)
    expect(boite).toHaveTextContent('Un numéro légal lui sera attribué.')
    await user.click(within(boite).getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
    expect(ventesApi.emettreFacture).not.toHaveBeenCalled()
    expect(within(ligne).getByText('BROUILLON-12')).toBeInTheDocument()

    await new Promise((r) => setTimeout(r, 450))
    await user.click(within(ligne).getByRole('button', { name: 'Émettre' }))
    await user.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(ventesApi.emettreFacture).toHaveBeenCalledTimes(1))
    expect(ventesApi.emettreFacture).toHaveBeenCalledWith(12)
  })
})
