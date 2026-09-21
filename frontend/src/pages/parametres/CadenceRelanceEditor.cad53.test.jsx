import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, act, cleanup, waitFor } from '@testing-library/react'

/* CAD53 (décision fondateur du 21/09/2026) — l'éditeur de cadence OUVRE
   l'ajout et la suppression d'un barreau, et expose la case « Autorisée le
   dimanche (16 h-19 h) ».

   Le garde-fou décisif est la NON-RÉTROACTIVITÉ : le gabarit est copié
   barreau par barreau à l'initialisation d'un plan
   (`crm.services.initialiser_plan_relance`), donc un plan DÉJÀ lancé garde
   ses touches. Côté écran, cela se vérifie en deux points, et ce module les
   verrouille :

     * ajouter puis supprimer un barreau n'appelle QUE les routes du GABARIT
       (`/parametres/cadence-relance/`) — jamais une route de touches de lead ;
     * l'écran DIT la non-rétroactivité, dans le panneau et dans la
       confirmation de suppression, plutôt que de la laisser deviner. */

vi.mock('../../api/parametresApi', () => ({
  default: {
    getMessages: vi.fn(async () => ({
      data: [{ cle: 'identite', label: "Message d'identité" }],
    })),
    getCadenceRelance: vi.fn(),
    updateCadenceRelanceEtape: vi.fn(async () => ({ data: {} })),
    createCadenceRelanceEtape: vi.fn(async () => ({ data: {} })),
    deleteCadenceRelanceEtape: vi.fn(async () => ({ data: {} })),
  },
}))

import parametresApi from '../../api/parametresApi'
import { ThemeProvider } from '../../design/ThemeProvider'
import CadenceRelanceEditor from './CadenceRelanceEditor'

const BARREAU_1 = {
  id: 51, cadence: 'contact', ordre: 1, delai_jours: 0, delai_minutes: 0,
  heure_cible: null, canal: 'whatsapp', libelle: "Message d'identité",
  template_cle: 'identite', dimanche_ok: false, actif: true,
}
const BARREAU_AJOUTE = {
  id: 99, cadence: 'contact', ordre: 2, delai_jours: 1, delai_minutes: 0,
  heure_cible: null, canal: 'appel', libelle: 'Nouveau barreau',
  template_cle: '', dimanche_ok: false, actif: true,
}

/** La liste renvoyée par le serveur, pilotée test par test. */
let listeCourante = [BARREAU_1]

beforeEach(() => {
  listeCourante = [BARREAU_1]
  parametresApi.getCadenceRelance.mockReset()
  parametresApi.getCadenceRelance.mockImplementation(async (cadence) => ({
    data: cadence === 'contact' ? listeCourante : [],
  }))
  parametresApi.updateCadenceRelanceEtape.mockClear()
  parametresApi.createCadenceRelanceEtape.mockClear()
  parametresApi.deleteCadenceRelanceEtape.mockClear()
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
  await screen.findByDisplayValue("Message d'identité")
}

const user = async () => {
  const { default: userEvent } = await import('@testing-library/user-event')
  return userEvent.setup()
}

describe('CAD53 — ajout, suppression et case dimanche', () => {
  it('affiche l’avertissement de non-rétroactivité', async () => {
    await renderEditor()
    expect(
      screen.getByText(/ne s’appliquent qu’aux relances à venir/i),
    ).toBeInTheDocument()
  })

  it('ajoute un barreau et recharge la liste du gabarit', async () => {
    await renderEditor()
    const u = await user()
    parametresApi.createCadenceRelanceEtape.mockImplementation(async () => {
      listeCourante = [BARREAU_1, BARREAU_AJOUTE]
      return { data: BARREAU_AJOUTE }
    })
    await u.click(screen.getByRole('button', { name: /Ajouter un barreau/i }))
    await waitFor(() =>
      expect(parametresApi.createCadenceRelanceEtape).toHaveBeenCalledTimes(1))
    // Le rang n'est PAS inventé par l'écran : le serveur le calcule.
    const envoye = parametresApi.createCadenceRelanceEtape.mock.calls[0][0]
    expect(envoye.cadence).toBe('contact')
    expect(envoye).not.toHaveProperty('ordre')
    expect(await screen.findByDisplayValue('Nouveau barreau')).toBeInTheDocument()
  })

  it('supprime un barreau après confirmation, et rappelle la non-rétroactivité', async () => {
    listeCourante = [BARREAU_1, BARREAU_AJOUTE]
    await renderEditor()
    const u = await user()
    await u.click(screen.getByRole('button', { name: 'Supprimer le barreau 2' }))
    // La confirmation redit ce qui ne bougera PAS : la phrase apparaît donc
    // DEUX fois — dans le panneau et dans la modale.
    await waitFor(() => expect(
      screen.getAllByText(/ne s’appliquent qu’aux relances à venir/i).length,
    ).toBeGreaterThanOrEqual(2))
    parametresApi.deleteCadenceRelanceEtape.mockImplementation(async () => {
      listeCourante = [BARREAU_1]
      return { data: {} }
    })
    await u.click(screen.getByRole('button', { name: 'Supprimer' }))
    await waitFor(() =>
      expect(parametresApi.deleteCadenceRelanceEtape)
        .toHaveBeenCalledWith(BARREAU_AJOUTE.id))
    await waitFor(() =>
      expect(screen.queryByDisplayValue('Nouveau barreau')).toBeNull())
  })

  it('n’écrit QUE sur le gabarit — aucune touche de plan n’est modifiée', async () => {
    listeCourante = [BARREAU_1, BARREAU_AJOUTE]
    await renderEditor()
    const u = await user()
    await u.click(screen.getByRole('button', { name: /Ajouter un barreau/i }))
    await waitFor(() =>
      expect(parametresApi.createCadenceRelanceEtape).toHaveBeenCalled())
    await u.click(screen.getByRole('button', { name: 'Supprimer le barreau 2' }))
    await u.click(screen.getByRole('button', { name: 'Supprimer' }))
    await waitFor(() =>
      expect(parametresApi.deleteCadenceRelanceEtape).toHaveBeenCalled())
    // Les seules écritures sont celles du GABARIT : aucun PATCH sur un autre
    // barreau, et l'écran n'a aucun moyen d'atteindre une touche de lead.
    expect(parametresApi.updateCadenceRelanceEtape).not.toHaveBeenCalled()
    expect(Object.keys(parametresApi).filter(
      k => /relance/i.test(k) && /create|update|delete/i.test(k),
    )).toEqual([
      'updateCadenceRelanceEtape',
      'createCadenceRelanceEtape',
      'deleteCadenceRelanceEtape',
    ])
  })

  it('rend la case dimanche éditable et envoie le PATCH', async () => {
    await renderEditor()
    const u = await user()
    await u.click(
      screen.getByLabelText('Autorisée le dimanche (16 h-19 h) — étape 1'))
    await waitFor(() =>
      expect(parametresApi.updateCadenceRelanceEtape).toHaveBeenCalledWith(
        51, { dimanche_ok: true }))
  })
})
