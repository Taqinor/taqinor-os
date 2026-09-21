import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, act, cleanup, waitFor } from '@testing-library/react'

/* CAD113 — dans l'éditeur de cadence, un refus serveur ne part plus en toast
   générique.

   `patch()` — utilisée par TOUS les champs édités en place — remettait la
   valeur précédente et affichait `data.detail ?? 'Modification impossible.'`,
   alors que le sérialiseur renvoie ses erreurs PAR CHAMP
   (`validate_delai_minutes`, `apps/parametres/serializers_referentiels.py`) :
   `detail` était `undefined` et le message EXACT du serveur était jeté. C'est
   le cas d'école de la règle fondateur du 08/09 — « le champ fautif, le
   message exact, jamais un refus muet » — sur le seul écran de configuration
   de cadence du CRM.

   Ce module verrouille les trois faits :
     * le message EXACT du serveur s'affiche SOUS le champ `delai_minutes` ;
     * un bandeau NOMME le champ fautif et y renvoie ;
     * une erreur NON liée à un champ (réseau, 500) garde une phrase claire.
   Plus l'avertissement « cadence muette » du même geste. */

vi.mock('../../api/parametresApi', () => ({
  default: {
    getMessages: vi.fn(async () => ({ data: [] })),
    getCadenceRelance: vi.fn(),
    updateCadenceRelanceEtape: vi.fn(),
    createCadenceRelanceEtape: vi.fn(async () => ({ data: {} })),
    deleteCadenceRelanceEtape: vi.fn(async () => ({ data: {} })),
  },
}))
vi.mock('../../ui/confirm', () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}))

import parametresApi from '../../api/parametresApi'
import { toast } from '../../ui/confirm'
import { ThemeProvider } from '../../design/ThemeProvider'
import CadenceRelanceEditor from './CadenceRelanceEditor'

/** Le message EXACT du sérialiseur (validate_delai_minutes). */
const MESSAGE_SERVEUR = (
  'Le délai en minutes doit rester sous 1440 (24 h) — au-delà, utiliser le '
  + 'délai en jours.'
)

const BARREAU = {
  id: 52, cadence: 'contact', ordre: 2, delai_jours: 0, delai_minutes: 3,
  heure_cible: null, canal: 'appel', libelle: "Appel d'ouverture",
  template_cle: '', dimanche_ok: false, actif: true,
}

let listeCourante = [BARREAU]

beforeEach(() => {
  listeCourante = [BARREAU]
  parametresApi.getCadenceRelance.mockReset()
  parametresApi.getCadenceRelance.mockImplementation(async (cadence) => ({
    data: cadence === 'contact' ? listeCourante : [],
  }))
  parametresApi.updateCadenceRelanceEtape.mockReset()
  toast.error.mockClear()
})
afterEach(() => cleanup())

const renderEditor = async () => {
  await act(async () => {
    render(
      <ThemeProvider>
        <CadenceRelanceEditor />
      </ThemeProvider>,
    )
  })
  await screen.findByDisplayValue("Appel d'ouverture")
}

const user = async () => {
  const { default: userEvent } = await import('@testing-library/user-event')
  return userEvent.setup()
}

/** Reproduit une 400 DRF de VALIDATION : objet {champ: [messages]}. */
const refus400 = (corps) => Object.assign(new Error('400'), {
  response: { status: 400, data: corps },
})

const taperDelaiMinutes = async (valeur) => {
  const u = await user()
  const champ = screen.getByLabelText('Délai (min)', { selector: '#cre-min-52' })
  await u.clear(champ)
  await u.type(champ, String(valeur))
  await u.tab()
}

describe('CAD113 — le champ fautif, le message exact', () => {
  it('affiche le message du serveur SOUS le champ delai_minutes', async () => {
    parametresApi.updateCadenceRelanceEtape.mockRejectedValue(
      refus400({ delai_minutes: [MESSAGE_SERVEUR] }))
    await renderEditor()
    await taperDelaiMinutes(1500)
    const message = await screen.findByText(MESSAGE_SERVEUR, {
      selector: '#cre-min-52-err',
    })
    expect(message).toBeInTheDocument()
    // Le champ se déclare invalide et pointe son message.
    const champ = screen.getByLabelText('Délai (min)', { selector: '#cre-min-52' })
    expect(champ).toHaveAttribute('aria-invalid', 'true')
    expect(champ).toHaveAttribute('aria-describedby', 'cre-min-52-err')
  })

  it('nomme le champ dans un bandeau qui y renvoie', async () => {
    parametresApi.updateCadenceRelanceEtape.mockRejectedValue(
      refus400({ delai_minutes: [MESSAGE_SERVEUR] }))
    await renderEditor()
    await taperDelaiMinutes(1500)
    const lien = await screen.findByRole('link', {
      name: new RegExp(`Délai \\(min\\) : ${MESSAGE_SERVEUR.slice(0, 20)}`),
    })
    expect(lien).toHaveAttribute('href', '#cre-min-52')
  })

  it('ne jette plus le message dans un toast générique', async () => {
    parametresApi.updateCadenceRelanceEtape.mockRejectedValue(
      refus400({ delai_minutes: [MESSAGE_SERVEUR] }))
    await renderEditor()
    await taperDelaiMinutes(1500)
    await screen.findByText(MESSAGE_SERVEUR, { selector: '#cre-min-52-err' })
    expect(toast.error).not.toHaveBeenCalled()
  })

  it('garde une phrase claire pour une erreur non liée à un champ', async () => {
    parametresApi.updateCadenceRelanceEtape.mockRejectedValue(
      Object.assign(new Error('boom'), { response: { status: 500, data: null } }))
    await renderEditor()
    await taperDelaiMinutes(7)
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(
      'La modification n’a pas pu être enregistrée — réessayez.'))
  })

  it('avertit quand TOUS les barreaux de la cadence sont désactivés', async () => {
    listeCourante = [{ ...BARREAU, actif: false }]
    await renderEditor()
    expect(
      await screen.findByText(/ne programmera plus aucune relance/i),
    ).toBeInTheDocument()
  })

  it('n’avertit pas tant qu’un barreau reste actif', async () => {
    await renderEditor()
    expect(screen.queryByText(/ne programmera plus aucune relance/i)).toBeNull()
  })
})
