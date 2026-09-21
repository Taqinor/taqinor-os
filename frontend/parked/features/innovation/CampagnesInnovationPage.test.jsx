import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

// jsdom n'implémente pas ResizeObserver (DataTable/Radix Popover MultiSelect).
beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

/* WIR150 — `CampagneInnovationViewSet` (CRUD + incitation/rapport/cloner/
   tableau-bord/segments/historique/noter) n'avait aucun consommateur réel :
   seul `.incitation()` était appelé. Cet écran câble créer/lister/rapport/
   cloner. */

const {
  list, segmentsDisponibles, create, update, rapport, cloner,
  tableauBord, historique, noter,
} = vi.hoisted(() => ({
  list: vi.fn(() => Promise.resolve({
    data: [{ id: 1, nom: 'Idées pompage', statut: 'active', statut_display: 'Active', segment: ['technicien'], date_debut: '2026-07-01', date_fin: null }],
  })),
  segmentsDisponibles: vi.fn(() => Promise.resolve({ data: { results: ['technicien', 'commercial'] } })),
  create: vi.fn(() => Promise.resolve({ data: { id: 2 } })),
  rapport: vi.fn(() => Promise.resolve({
    data: { nb_utilisateurs_cibles: 5, nb_idees_proposees: 3, top_idees: [{ id: 9, titre: 'Idée A', votes_count: 4 }], taux_conversion: 0.4 },
  })),
  cloner: vi.fn(() => Promise.resolve({ data: { id: 3 } })),
  // WIR213 — lancer/fermer/editer passent tous par le PATCH du statut ou des
  // champs : le serializer n'expose aucune autre voie.
  update: vi.fn(() => Promise.resolve({ data: {} })),
  // WIR213 — tuiles du tableau de bord (NTIDE34), agregat SERVEUR.
  tableauBord: vi.fn(() => Promise.resolve({
    data: {
      actives: 1,
      fermees: 0,
      brouillons: 2,
      taux_realisation: 0.25,
      top_campagnes: [{ id: 1, nom: 'Idees pompage', statut: 'active', nb_idees_proposees: 7 }],
    },
  })),
  // WIR213 — chatter de campagne (NTIDE33) : historique + note.
  historique: vi.fn(() => Promise.resolve({
    data: [{
      id: 1, kind: 'modification', field: 'statut', field_label: 'Statut',
      old_value: 'brouillon', new_value: 'active', body: '',
      user_username: 'reda', created_at: '2026-08-20T09:00:00Z',
    }],
  })),
  noter: vi.fn(() => Promise.resolve({
    data: [
      {
        id: 1, kind: 'modification', field: 'statut', field_label: 'Statut',
        old_value: 'brouillon', new_value: 'active', body: '',
        user_username: 'reda', created_at: '2026-08-20T09:00:00Z',
      },
      {
        id: 2, kind: 'note', field: '', field_label: '', old_value: '',
        new_value: '', body: 'Relancer les techniciens lundi.',
        user_username: 'reda', created_at: '2026-08-20T10:00:00Z',
      },
    ],
  })),
}))

vi.mock('../../api/innovationApi', () => ({
  default: {
    campagnes: {
      list, segmentsDisponibles, create, update, rapport, cloner,
      tableauBord, historique, noter,
    },
  },
}))

import CampagnesInnovationPage from './CampagnesInnovationPage'

beforeEach(() => { vi.clearAllMocks() })

describe('CampagnesInnovationPage (WIR150)', () => {
  it('liste les campagnes existantes', async () => {
    renderPage(<CampagnesInnovationPage />)
    // DataTable rend à la fois la table desktop et le repli carte mobile (CSS
    // seul, les deux existent dans le DOM en jsdom) : on cible le PREMIER
    // match, même patron que ModelesBcf.test.jsx / qhse.render.test.jsx.
    expect((await screen.findAllByText('Idées pompage'))[0]).toBeInTheDocument()
  })

  it('crée une campagne depuis le formulaire', async () => {
    const user = userEvent.setup()
    renderPage(<CampagnesInnovationPage />)
    await screen.findAllByText('Idées pompage')

    await user.click(screen.getByRole('button', { name: /Nouvelle campagne/ }))
    await user.type(screen.getByLabelText('Nom'), 'Relance O&M')
    await user.click(screen.getByRole('button', { name: 'Créer (brouillon)' }))

    await waitFor(() => expect(create).toHaveBeenCalledWith(expect.objectContaining({ nom: 'Relance O&M' })))
  })

  it('affiche le rapport d’une campagne', async () => {
    const user = userEvent.setup()
    renderPage(<CampagnesInnovationPage />)
    await screen.findAllByText('Idées pompage')

    await user.click(screen.getAllByRole('button', { name: 'Rapport' })[0])
    await waitFor(() => expect(rapport).toHaveBeenCalledWith(1))
    expect(await screen.findByText('Idée A')).toBeInTheDocument()
  })

  it('clone une campagne', async () => {
    const user = userEvent.setup()
    renderPage(<CampagnesInnovationPage />)
    await screen.findAllByText('Idées pompage')

    await user.click(screen.getAllByRole('button', { name: 'Cloner' })[0])
    await waitFor(() => expect(cloner).toHaveBeenCalledWith(1))
  })
})

/* ============================================================================
   WIR213 — la campagne était structurellement INERTE : brouillon à vie (aucune
   fermeture), non éditable, sans tableau de bord ni chatter. Ces tests
   verrouillent le cycle complet créer → éditer → lancer → fermer, plus les
   deux lectures qui le rendent intelligible.
   ========================================================================== */
const BROUILLON = {
  id: 5,
  nom: 'Relance O&M',
  statut: 'brouillon',
  statut_display: 'Brouillon',
  segment: ['technicien'],
  description: 'Idées de maintenance',
  message_incitation: 'Une idée pour la maintenance ?',
  tag_auto: 'om',
  date_debut: '2026-09-01',
  date_fin: null,
}

// La campagne ACTIVE du fixture partagé, re-posée à CHAQUE test : un
// `mockResolvedValue` posé dans un test survit à `clearAllMocks` (qui ne vide
// que les appels, pas l'implémentation) et contaminerait le suivant.
const ACTIVE = {
  id: 1, nom: 'Idées pompage', statut: 'active', statut_display: 'Active',
  segment: ['technicien'], date_debut: '2026-07-01', date_fin: null,
}

describe('CampagnesInnovationPage — cycle de vie (WIR213)', () => {
  beforeEach(() => {
    list.mockResolvedValue({ data: [ACTIVE] })
  })

  it('LANCE un brouillon par le PATCH du statut, puis recharge la liste', async () => {
    const user = userEvent.setup()
    list.mockResolvedValue({ data: [BROUILLON] })
    renderPage(<CampagnesInnovationPage />)
    await screen.findAllByText('Relance O&M')

    await user.click(screen.getAllByRole('button', { name: 'Lancer' })[0])
    await waitFor(() => expect(update).toHaveBeenCalledWith(5, { statut: 'active' }))
    // La liste ET le tableau de bord sont relus : le badge et les tuiles
    // viennent du serveur, jamais d'une bascule optimiste à l'écran.
    await waitFor(() => expect(list.mock.calls.length).toBeGreaterThan(1))
    await waitFor(() => expect(tableauBord.mock.calls.length).toBeGreaterThan(1))
  })

  it('FERME une campagne active — et ne propose « Fermer » que sur une active', async () => {
    const user = userEvent.setup()
    renderPage(<CampagnesInnovationPage />)
    await screen.findAllByText('Idées pompage')

    // La campagne du fixture par défaut est ACTIVE : pas de « Lancer », pas de
    // « Modifier » (on ne réécrit pas une campagne déjà partie).
    expect(screen.queryByRole('button', { name: 'Lancer' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Modifier' })).toBeNull()

    await user.click(screen.getAllByRole('button', { name: 'Fermer la campagne' })[0])
    await waitFor(() => expect(update).toHaveBeenCalledWith(1, { statut: 'fermee' }))
  })

  it('ÉDITE un brouillon : le formulaire est pré-rempli et l’enregistrement PATCHe', async () => {
    const user = userEvent.setup()
    list.mockResolvedValue({ data: [BROUILLON] })
    renderPage(<CampagnesInnovationPage />)
    await screen.findAllByText('Relance O&M')

    await user.click(screen.getAllByRole('button', { name: 'Modifier' })[0])
    // Pré-rempli depuis la campagne SERVEUR, jamais un formulaire vide qui
    // effacerait les champs non ressaisis.
    expect(screen.getByLabelText('Nom')).toHaveValue('Relance O&M')
    expect(screen.getByLabelText('Description')).toHaveValue('Idées de maintenance')

    await user.clear(screen.getByLabelText('Nom'))
    await user.type(screen.getByLabelText('Nom'), 'Relance O&M 2026')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(update).toHaveBeenCalledWith(
      5, expect.objectContaining({ nom: 'Relance O&M 2026', message_incitation: 'Une idée pour la maintenance ?' }),
    ))
    expect(create).not.toHaveBeenCalled()
  })

  it('affiche les tuiles du tableau de bord SERVEUR (aucun compte refait sur la liste)', async () => {
    renderPage(<CampagnesInnovationPage />)
    await screen.findAllByText('Idées pompage')

    await waitFor(() => expect(tableauBord).toHaveBeenCalled())
    const tuile = (cle) => document.querySelector(`[data-campagnes-tuile="${cle}"]`)
    await waitFor(() => expect(tuile('actives')).toBeTruthy())
    // La liste ne contient QU'UNE campagne : les 2 brouillons du tableau de
    // bord prouvent que le chiffre vient du serveur.
    expect(tuile('brouillons').textContent).toMatch(/2/)
    expect(tuile('actives').textContent).toMatch(/1/)
    expect(tuile('taux_realisation').textContent).toMatch(/25 %/)
    expect(document.querySelector('[data-campagnes-top]').textContent).toMatch(/7 idée\(s\)/)
  })

  it('ouvre l’ACTIVITÉ : journal de statut affiché, note rechargée DU SERVEUR', async () => {
    const user = userEvent.setup()
    renderPage(<CampagnesInnovationPage />)
    await screen.findAllByText('Idées pompage')

    await user.click(screen.getAllByRole('button', { name: 'Activité' })[0])
    await waitFor(() => expect(historique).toHaveBeenCalledWith(1))
    // Le changement de statut journalisé côté serveur est enfin LISIBLE.
    // Assertion PORTÉE sur le panneau d'activité : « Statut » est aussi
    // l'en-tête d'une colonne du tableau, une recherche globale matcherait
    // deux nœuds.
    const panneau = await waitFor(() => {
      const el = document.querySelector('[data-campagne-activite]')
      expect(el).toBeTruthy()
      return el
    })
    await waitFor(() => expect(panneau.textContent).toMatch(/brouillon → active/))

    await user.type(screen.getByLabelText('Ajouter une note'), 'Relancer les techniciens lundi.')
    await user.click(screen.getByRole('button', { name: 'Noter' }))

    await waitFor(() => expect(noter).toHaveBeenCalledWith(1, 'Relancer les techniciens lundi.'))
    // Le fil rendu est celui que le SERVEUR renvoie, pas un ajout optimiste.
    // Assertion sur le textContent du panneau, comme ci-dessus : ChatterTimeline
    // rend une note en « 📝 Note : <body> » DANS UN SEUL span, donc aucun
    // élément ne porte le body nu comme texte propre — un `getByText(body)`
    // exact ne matcherait jamais, même le fil correctement rendu.
    await waitFor(() => expect(panneau.textContent)
      .toMatch(/Relancer les techniciens lundi\./))
  })
})
