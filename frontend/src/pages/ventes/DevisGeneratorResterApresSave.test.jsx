// EDC7 — moitié générateur du contrat EDC : après « Enregistrer les
// modifications » en Édition complète embarquée, l'écran RESTE dans l'éditeur
// (`onEnregistre(devisId)`, plus de `onDone` qui faisait basculer le panneau
// sur l'aperçu) ; `onDirtyChange` suit `dirty` (vrai après une frappe, faux
// après l'enregistrement) ; sans `onEnregistre`, repli sur `onDone`.
//
// Écran RÉEL rendu, API mockées.
// Run : npx vitest run src/pages/ventes/DevisGeneratorResterApresSave.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'

import { toast } from '../../ui/confirm'
import {
  PANNEAU, renderGenerateurEdition, preparerApisGenerateur, ouvrirEditionEtAttendreReference,
} from '../../test/generateurEmbarque'

// EDC (gardes CI) : fabriques partagées — src/test/mocksApiDevis.js.
vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiMock())

import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'

const boutonPied = () => screen.getByRole('button', { name: /Enregistrer les modifications/ })
const note = () => screen.getByPlaceholderText(/Conditions particulières/)

beforeEach(() => preparerApisGenerateur({ stockApi, ventesApi }))

/** Ouvre, attend la fenêtre de référence QJR581 (1,5 s), tape une note. */
async function ouvrirEtModifier() {
  await ouvrirEditionEtAttendreReference()
  fireEvent.change(note(), { target: { value: 'Acompte 30 % à la commande' } })
}

/** Clique « Enregistrer » ; un éventuel écart de factures se confirme d'un second clic. */
async function enregistrer() {
  fireEvent.click(boutonPied())
  await waitFor(() => {
    if (!ventesApi.replaceLignesDevis.mock.calls.length
        && screen.queryByTestId('erreur-enregistrement')) {
      fireEvent.click(boutonPied())
    }
    expect(ventesApi.replaceLignesDevis).toHaveBeenCalledTimes(1)
  })
}

describe('EDC7 — rester dans l\'éditeur après « Enregistrer les modifications »', () => {
  it('embarqué + onEnregistre : onEnregistre(42), pas onDone, toast, état conservé, dirty true → false', async () => {
    const onEnregistre = vi.fn()
    const onDone = vi.fn()
    const onDirtyChange = vi.fn()
    const succes = vi.spyOn(toast, 'success')
    renderGenerateurEdition({ onEnregistre, onDone, onDirtyChange })
    // Valeur initiale : rien n'a changé.
    await waitFor(() => expect(onDirtyChange).toHaveBeenCalled())
    expect(onDirtyChange.mock.calls[0][0]).toBe(false)

    await ouvrirEtModifier()
    await waitFor(() => expect(onDirtyChange).toHaveBeenLastCalledWith(true))

    await enregistrer()
    await waitFor(() => expect(onEnregistre).toHaveBeenCalledWith(42))
    expect(onEnregistre).toHaveBeenCalledTimes(1)
    expect(onDone).not.toHaveBeenCalled()
    expect(succes).toHaveBeenCalledWith('Modifications enregistrées.')
    // `marquerEnregistre()` : dirty repasse à faux, le panneau le sait.
    await waitFor(() => expect(onDirtyChange).toHaveBeenLastCalledWith(false))
    // L'écran est TOUJOURS monté, avec la saisie de l'utilisateur.
    expect(boutonPied()).toBeInTheDocument()
    expect(note()).toHaveValue('Acompte 30 % à la commande')
    expect(screen.getByDisplayValue(PANNEAU.nom)).toBeInTheDocument()
    expect(screen.queryByText('Modifications non enregistrées')).toBeNull()
    succes.mockRestore()
  }, 20000)

  it('le jeton ré-armé part avec l\'enregistrement suivant (pas de faux conflit 409)', async () => {
    const onEnregistre = vi.fn()
    renderGenerateurEdition({ onEnregistre, onDone: vi.fn() })
    await ouvrirEtModifier()
    await enregistrer()
    await waitFor(() => expect(onEnregistre).toHaveBeenCalledTimes(1))
    fireEvent.change(note(), { target: { value: 'Acompte 40 %' } })
    fireEvent.click(boutonPied())
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalledTimes(2))
    const extra = ventesApi.replaceLignesDevis.mock.calls[1][2]
    expect(extra.expected_updated_at).toBe('2026-10-09T09:30:00Z')
    await waitFor(() => expect(onEnregistre).toHaveBeenCalledTimes(2))
  }, 20000)

  it('sans onEnregistre : repli sur onDone(42), comme avant', async () => {
    const onDone = vi.fn()
    renderGenerateurEdition({ onDone })
    await ouvrirEtModifier()
    await enregistrer()
    await waitFor(() => expect(onDone).toHaveBeenCalledWith(42))
  }, 20000)
})
