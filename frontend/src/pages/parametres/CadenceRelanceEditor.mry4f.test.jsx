import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, act, cleanup, waitFor } from '@testing-library/react'

/* MRY28 — éditeur des trois cadences de relance (contact / après devis /
   réveil), Paramètres → Référentiels → « Cadences de relance ». Ce module
   couvre l'édition EN PLACE (PATCH) des lignes posées par `seed_cadence`
   (MRY4) ; l'ajout et la suppression d'un barreau, ouverts par CAD53, sont
   couverts par `CadenceRelanceEditor.cad53.test.jsx`.

   PARAM-CADENCE (décision fondateur 25/09/2026) — les deux nouvelles
   cadences À CLÉ (« Après l'appel (avant devis) » / « Visite technique »)
   sont couvertes plus bas avec la charge utile COMMITTÉE du contrat
   `cadence_relance_v2` (`exemple_apres_contact`, PACT10) — jamais un objet
   retapé à la main. */
import { exempleContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/parametresApi', () => ({
  default: {
    getMessages: vi.fn(async () => ({
      data: [
        { cle: 'identite', label: "Message d'identité" },
        { cle: 'appel_ouverture', label: "Appel d'ouverture" },
      ],
    })),
    getCadenceRelance: vi.fn(async (cadence) => ({
      data: cadence === 'contact'
        ? [
          {
            id: 51, cadence: 'contact', ordre: 1, delai_jours: 0,
            delai_minutes: 0, heure_cible: null, canal: 'whatsapp',
            libelle: "Message d'identité", template_cle: 'identite', actif: true,
          },
          {
            id: 52, cadence: 'contact', ordre: 2, delai_jours: 0,
            delai_minutes: 3, heure_cible: null, canal: 'appel',
            libelle: "Appel d'ouverture", template_cle: 'appel_ouverture', actif: true,
          },
        ]
        : [],
    })),
    updateCadenceRelanceEtape: vi.fn(async () => ({ data: {} })),
  },
}))

import parametresApi from '../../api/parametresApi'
import { ThemeProvider } from '../../design/ThemeProvider'
import CadenceRelanceEditor from './CadenceRelanceEditor'

beforeEach(() => {
  parametresApi.getCadenceRelance.mockClear()
  parametresApi.updateCadenceRelanceEtape.mockClear()
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
}

describe('MRY28 CadenceRelanceEditor', () => {
  it('charge la cadence « contact » par défaut et affiche ses étapes', async () => {
    await renderEditor()
    await waitFor(() =>
      expect(parametresApi.getCadenceRelance).toHaveBeenCalledWith('contact'))
    expect(await screen.findByDisplayValue("Message d'identité")).toBeInTheDocument()
    expect(screen.getByDisplayValue("Appel d'ouverture")).toBeInTheDocument()
    expect(screen.getByText('#1')).toBeInTheDocument()
    expect(screen.getByText('#2')).toBeInTheDocument()
  })

  it('bascule vers l\'onglet « Après devis » sans étape (liste vide)', async () => {
    await renderEditor()
    await screen.findByDisplayValue("Message d'identité")
    const { default: userEvent } = await import('@testing-library/user-event')
    const user = userEvent.setup()
    await user.click(screen.getByRole('tab', { name: 'Après devis' }))
    await waitFor(() =>
      expect(parametresApi.getCadenceRelance).toHaveBeenCalledWith('apres_devis'))
    expect(await screen.findByText('Aucune étape pour cette cadence.')).toBeInTheDocument()
  })

  it('modifie le délai en minutes et envoie le PATCH attendu', async () => {
    await renderEditor()
    const input = await screen.findByLabelText('Délai (min)', {
      selector: '#cre-min-52',
    })
    const { default: userEvent } = await import('@testing-library/user-event')
    const user = userEvent.setup()
    await user.clear(input)
    await user.type(input, '5')
    await user.tab()
    await waitFor(() =>
      expect(parametresApi.updateCadenceRelanceEtape).toHaveBeenCalledWith(
        52, { delai_minutes: 5 }))
  })

  it('bascule l\'interrupteur Actif et envoie le PATCH', async () => {
    await renderEditor()
    await screen.findByDisplayValue("Message d'identité")
    const { default: userEvent } = await import('@testing-library/user-event')
    const user = userEvent.setup()
    await user.click(screen.getByLabelText('Active — étape 1'))
    await waitFor(() =>
      expect(parametresApi.updateCadenceRelanceEtape).toHaveBeenCalledWith(
        51, { actif: false }))
  })
})

// PARAM-CADENCE (décision fondateur 25/09/2026) — l'onglet « Après l'appel
// (avant devis) » (cadence `apres_contact`) : charge utile COMMITTÉE du
// contrat `cadence_relance_v2` (`exemple_apres_contact`, PACT10).
describe('PARAM-CADENCE — onglet « Après l\'appel (avant devis) »', () => {
  // Lu dans `beforeEach` (phase d'exécution), jamais au niveau du `describe`
  // (phase de COLLECTE) : une variante de contrat pas encore publiée ne doit
  // faire échouer QUE ces tests-ci, jamais planter tout le fichier (et donc
  // les tests MRY28 existants ci-dessus).
  let BARREAUX
  let DEVIS

  beforeEach(() => {
    BARREAUX = exempleContrat('parametres', 'cadence_relance_v2', 'exemple_apres_contact')
    DEVIS = BARREAUX[0] // { id: 901, cle: 'devis', libelle: 'Préparer et envoyer le devis…' }
    parametresApi.getCadenceRelance.mockImplementation(async (cadence) => ({
      data: cadence === 'apres_contact' ? BARREAUX : [],
    }))
  })

  const ouvrirOnglet = async () => {
    await renderEditor()
    const { default: userEvent } = await import('@testing-library/user-event')
    const user = userEvent.setup()
    await user.click(screen.getByRole('tab', { name: "Après l'appel (avant devis)" }))
    await waitFor(() =>
      expect(parametresApi.getCadenceRelance).toHaveBeenCalledWith('apres_contact'))
  }

  it('affiche la liste de `exemple_apres_contact` avec la clé de chaque barreau', async () => {
    await ouvrirOnglet()
    expect(await screen.findByDisplayValue(DEVIS.libelle)).toBeInTheDocument()
    // La clé — LECTURE SEULE — s'affiche en badge discret, une par barreau.
    for (const b of BARREAUX) {
      expect(screen.getByTestId(`cre-cle-${b.id}`)).toHaveTextContent(`clé : ${b.cle}`)
    }
    // L'aide au-dessus de la table dit la règle du contrat (`notes.cle`),
    // jamais un chiffre inventé.
    expect(screen.getByTestId('cadence-aide-cle-apres_contact')).toHaveTextContent(
      /défaut de la plateforme/)
  })

  it('D3 — n’affiche pas le bouton « Ajouter un barreau » (l’ajout à la main est refusé)', async () => {
    await ouvrirOnglet()
    await screen.findByDisplayValue(DEVIS.libelle)
    expect(screen.queryByRole('button', { name: /Ajouter un barreau/i }))
      .not.toBeInTheDocument()
  })

  it('un PATCH de libellé sur cette cadence ne porte jamais `cle`', async () => {
    await ouvrirOnglet()
    const input = await screen.findByLabelText('Libellé', {
      selector: `#cre-lib-${DEVIS.id}`,
    })
    const { default: userEvent } = await import('@testing-library/user-event')
    const user = userEvent.setup()
    await user.clear(input)
    await user.type(input, 'Préparer le devis — renommé')
    await user.tab()
    await waitFor(() =>
      expect(parametresApi.updateCadenceRelanceEtape).toHaveBeenCalledWith(
        DEVIS.id, { libelle: 'Préparer le devis — renommé' }))
    const [, payload] = parametresApi.updateCadenceRelanceEtape.mock.calls.at(-1)
    expect(payload).not.toHaveProperty('cle')
  })
})

// D3 — même garde-fou sur le second onglet à clé.
describe('PARAM-CADENCE — onglet « Visite technique » (D3)', () => {
  it('n’affiche pas non plus le bouton « Ajouter un barreau »', async () => {
    await renderEditor()
    const { default: userEvent } = await import('@testing-library/user-event')
    const user = userEvent.setup()
    await user.click(screen.getByRole('tab', { name: 'Visite technique' }))
    await waitFor(() =>
      expect(parametresApi.getCadenceRelance).toHaveBeenCalledWith('visite'))
    await screen.findByText('Aucune étape pour cette cadence.')
    expect(screen.queryByRole('button', { name: /Ajouter un barreau/i }))
      .not.toBeInTheDocument()
  })
})
