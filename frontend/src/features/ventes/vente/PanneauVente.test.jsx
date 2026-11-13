import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

/* AERR17 (C-AERR-015) — « Confirmer l'avoir » émet un avoir : une confirmation
   qui nomme le devis précède l'appel ; « Annuler » n'envoie rien. Mutant :
   retirer le `confirm` de `confirmerAvoir` ⇒ échec. */

vi.mock('../../../api/ventesApi', () => ({
  default: { confirmerAvoirRevision: vi.fn(() => Promise.resolve({ data: {} })) },
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

    await user.click(screen.getByRole('button', { name: /Confirmer l'avoir/ }))
    await user.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(ventesApi.confirmerAvoirRevision).toHaveBeenCalledWith(318))
  })
})
