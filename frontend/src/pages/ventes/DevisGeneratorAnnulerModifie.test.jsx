// EDC6 (suite, orchestrateur 09/10/2026) — « Annuler » du générateur (barre
// en tête, pied, rail) sur un écran MODIFIÉ demande confirmation avant
// d'abandonner, comme Échap et le voile du panneau (EDC6) ; sans modification,
// il sort directement comme avant. Écran RÉEL rendu, API mockées ; la
// confirmation passe par le repli `window.confirm` de `useConfirm()` (aucun
// ConfirmProvider monté ici), bouchonné pour choisir « Rester » ou « Abandonner ».
// Run : npx vitest run src/pages/ventes/DevisGeneratorAnnulerModifie.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'

import {
  renderGenerateurEdition, preparerApisGenerateur, ouvrirEditionEtAttendreReference,
} from '../../test/generateurEmbarque'

// EDC (gardes CI) : fabriques partagées — src/test/mocksApiDevis.js.
vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiMock())

import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'

const note = () => screen.getByPlaceholderText(/Conditions particulières/)
// « Annuler » de la barre d'actions en tête (le pied et le rail passent par
// le même `annuler`).
const annulerBarre = () => screen.getByRole('toolbar', { name: /Actions du devis/ })
  .querySelector('.gen-barre-annuler')

beforeEach(() => preparerApisGenerateur({ stockApi, ventesApi }))

describe('EDC6 (suite) — « Annuler » du générateur sur un écran modifié', () => {
  it('sans modification : sortie directe, aucune confirmation', async () => {
    const onCancel = vi.fn()
    const confirmSpy = vi.spyOn(window, 'confirm').mockImplementation(() => true)
    renderGenerateurEdition({ onCancel })
    await ouvrirEditionEtAttendreReference()
    fireEvent.click(annulerBarre())
    await waitFor(() => expect(onCancel).toHaveBeenCalledTimes(1))
    expect(confirmSpy).not.toHaveBeenCalled()
    confirmSpy.mockRestore()
  })

  it('modifié puis « Rester » : on reste dans l\'éditeur, onCancel jamais appelé', async () => {
    const onCancel = vi.fn()
    const confirmSpy = vi.spyOn(window, 'confirm').mockImplementation(() => false)
    renderGenerateurEdition({ onCancel })
    await ouvrirEditionEtAttendreReference()
    fireEvent.change(note(), { target: { value: 'Acompte 30 % à la commande' } })
    await screen.findByTestId('gen-barre-non-enregistre')
    fireEvent.click(annulerBarre())
    await waitFor(() => expect(confirmSpy).toHaveBeenCalledTimes(1))
    expect(confirmSpy.mock.calls[0][0]).toMatch(/pas été enregistrées/)
    await new Promise((r) => setTimeout(r, 50))
    expect(onCancel).not.toHaveBeenCalled()
    expect(note().value).toBe('Acompte 30 % à la commande')
    confirmSpy.mockRestore()
  })

  it('modifié puis « Abandonner » : onCancel appelé une fois', async () => {
    const onCancel = vi.fn()
    const confirmSpy = vi.spyOn(window, 'confirm').mockImplementation(() => true)
    renderGenerateurEdition({ onCancel })
    await ouvrirEditionEtAttendreReference()
    fireEvent.change(note(), { target: { value: 'Acompte 30 % à la commande' } })
    await screen.findByTestId('gen-barre-non-enregistre')
    fireEvent.click(annulerBarre())
    await waitFor(() => expect(onCancel).toHaveBeenCalledTimes(1))
    expect(confirmSpy).toHaveBeenCalledTimes(1)
    confirmSpy.mockRestore()
  })
})
