// AGNR33 — un refus 400 « par champ » de l'enregistrement s'affiche sous LE
// champ et le bandeau le nomme (jamais la phrase générique) ; une saisie que
// AGNR8 normalisera est dite sous son champ (« 12,345 → 12,35 »).
//
// Run : npx vitest run src/pages/ventes/DevisGenerator.agnrErreurChamp.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { cycleEcran } from '../../test/cycleEcran'
import { act, fireEvent, screen, waitFor } from '@testing-library/react'

import { DATE_FIGEE, monter, attendreStable, DEVIS_REGISTRE } from './DevisGeneratorGoldenHarnais'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())

cycleEcran({ date: DATE_FIGEE })

const MESSAGE = "Assurez-vous qu'il n'y a pas plus de 2 chiffres après la virgule."
const remise = () => document.querySelector('.gen-discount-input')

describe('AGNR33 — refus par champ et normalisations', () => {
  it('400 { remise_globale } ⇒ message sous « Réduction » et bandeau qui le nomme', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, {
      devis: DEVIS_REGISTRE,
      avant: ({ ventesApi }) => {
        ventesApi.replaceLignesDevis.mockRejectedValue({
          response: { status: 400, data: { remise_globale: [MESSAGE] } },
        })
      },
    })
    await attendreStable(vue.container, act)
    const bouton = [...document.querySelectorAll('button')]
      .find((b) => /Enregistrer les modifications/.test(b.textContent || ''))
    await act(async () => { fireEvent.click(bouton) })
    await waitFor(() => expect(screen.getByTestId('erreur-champ-remise_globale').textContent).toBe(MESSAGE))
    expect(screen.getByTestId('erreur-enregistrement').textContent).toBe(`Réduction : ${MESSAGE}`)
    expect(document.body.textContent).not.toMatch(/L'enregistrement a échoué — vérifiez les champs/)
  }, 60000)

  it('« 12.345 » ⇒ note « 12,345 → 12,35 » sous le champ, et 12.35 part', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, { devis: DEVIS_REGISTRE })
    await attendreStable(vue.container, act)
    await act(async () => { fireEvent.change(remise(), { target: { value: '12.345' } }) })
    expect(screen.getByTestId('note-champ-remise_globale').textContent).toBe('12,345 → 12,35')
    const bouton = [...document.querySelectorAll('button')]
      .find((b) => /Enregistrer les modifications/.test(b.textContent || ''))
    await act(async () => { fireEvent.click(bouton) })
    await waitFor(() => expect(vue.ventesApi.replaceLignesDevis).toHaveBeenCalled(), { timeout: 5000 })
    expect(vue.ventesApi.replaceLignesDevis.mock.calls.at(-1)[2].entete.remise_globale).toBe('12.35')
  }, 60000)
})
