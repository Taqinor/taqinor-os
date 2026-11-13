// AERR12 — « Ajouter le BOQ électrique » demande avant de recharger le devis
// quand une saisie non enregistrée existe (le test existant de ce composant
// vit dans LotsEtBoq.test.jsx, propriétaire devis : nouveau fichier ici).
//
// Run : npx vitest run src/features/ventes/AjouterBoqElectrique.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('../../api/ventesApi', () => ({
  default: { ajouterBoqElectrique: vi.fn() },
}))

import ventesApi from '../../api/ventesApi'
import { ConfirmProvider } from '../../providers/ConfirmProvider'
import useDirtyGuard from '../../ui/useDirtyGuard'
import AjouterBoqElectrique from './AjouterBoqElectrique'

function Ecran({ dirty }) {
  useDirtyGuard(dirty)
  return <AjouterBoqElectrique devisId={7} modifiable />
}

const rendre = (dirty) => render(
  <ConfirmProvider><Ecran dirty={dirty} /></ConfirmProvider>)

beforeEach(() => {
  vi.clearAllMocks()
  ventesApi.ajouterBoqElectrique.mockResolvedValue({ data: { creees: 0 } })
})

describe('AjouterBoqElectrique — saisie non enregistrée', () => {
  it('formulaire modifié monté : confirmation, Annuler ⇒ aucun ajouterBoqElectrique', async () => {
    rendre(true)
    await userEvent.click(screen.getByRole('button', { name: /Ajouter le BOQ électrique/ }))
    expect(await screen.findByText(/vos modifications non enregistrées seront perdues/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(ventesApi.ajouterBoqElectrique).not.toHaveBeenCalled()
  })

  it('formulaire modifié : « Ajouter quand même » envoie le POST', async () => {
    rendre(true)
    await userEvent.click(screen.getByRole('button', { name: /Ajouter le BOQ électrique/ }))
    await userEvent.click(await screen.findByRole('button', { name: 'Ajouter quand même' }))
    await waitFor(() => expect(ventesApi.ajouterBoqElectrique).toHaveBeenCalledWith(7))
  })

  it('sans saisie modifiée : aucune question', async () => {
    rendre(false)
    await userEvent.click(screen.getByRole('button', { name: /Ajouter le BOQ électrique/ }))
    await waitFor(() => expect(ventesApi.ajouterBoqElectrique).toHaveBeenCalledWith(7))
    expect(screen.queryByText(/seront perdues/)).toBeNull()
  })
})
