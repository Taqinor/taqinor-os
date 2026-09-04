import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { reponseContrat } from '../../test/fixtures/contractSamples'

/* WIR276 — les 5 registres ISO QHSE exposés côté serveur par WIR275
   (campagnes de rappel, certifications, programme d'audit, réunions +
   décisions, objectifs QHSE) n'avaient AUCUN écran. On vérifie que chaque
   onglet expose au minimum la création + la consultation. Le mock de
   `creerCapaDepuisDecision` IMPORTE le contrat committé
   (apps/qhse/contract_samples/decision_reunion_creer_capa.json, PACT10/13)
   au lieu d'inventer sa charge utile. Réseau mocké. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
  if (typeof Element.prototype.hasPointerCapture === 'undefined') {
    Element.prototype.hasPointerCapture = () => false
  }
  if (typeof Element.prototype.scrollIntoView === 'undefined') {
    Element.prototype.scrollIntoView = () => {}
  }
})

const {
  empty, campagneCreate, certificationCreate, programmeCreate, reunionCreate,
  decisionCreate, decisionCreerCapa, objectifCreate, revueObjectifCreate,
  campagnePeupler, campagneNotifier, campagneCloturer, elementPlanifier,
} = vi.hoisted(() => ({
  empty: () => Promise.resolve({ data: [] }),
  campagneCreate: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  certificationCreate: vi.fn(() => Promise.resolve({ data: { id: 2 } })),
  programmeCreate: vi.fn(() => Promise.resolve({ data: { id: 3 } })),
  reunionCreate: vi.fn(() => Promise.resolve({ data: { id: 4 } })),
  decisionCreate: vi.fn(() => Promise.resolve({ data: { id: 5 } })),
  decisionCreerCapa: vi.fn(),
  objectifCreate: vi.fn(() => Promise.resolve({ data: { id: 6 } })),
  revueObjectifCreate: vi.fn(() => Promise.resolve({ data: { id: 7 } })),
  campagnePeupler: vi.fn(() => Promise.resolve({ data: { crees: 3 } })),
  campagneNotifier: vi.fn(() => Promise.resolve({ data: { notifies: 2 } })),
  campagneCloturer: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  elementPlanifier: vi.fn(() => Promise.resolve({ data: { ticket_id: 7 } })),
}))

const DECISION_ROW = {
  id: 90, reunion: 40, texte: 'Renforcer la formation LOTO', capa_id: null,
}
const REUNION_ROW = {
  id: 40, type_reunion: 'reunion_hse', type_reunion_display: 'Réunion HSE',
  date_reunion: '2026-08-01', statut: 'planifiee', statut_display: 'Planifiée',
}
const OBJECTIF_ROW = {
  id: 60, intitule: 'Taux de fréquence accidents', domaine: 'securite',
  domaine_display: 'Sécurité', valeur_cible: 2, echeance: '2027-01-01',
}
// AUDV10 — campagne de rappel peuplable/notifiable/clôturable + son élément.
const CAMPAGNE_ROW = {
  id: 1, titre: 'Rappel onduleurs X', produit: 12, gravite: 'majeure',
  nb_elements: 1, statut: 'en_cours', statut_display: 'En cours',
}
const ELEMENT_ROW = {
  id: 200, campagne: 1, numero_serie: 'SN-0042', statut: 'a_notifier',
  statut_display: 'À notifier', ticket_sav_id: null,
}

vi.mock('../../api/qhseApi', () => ({
  default: {
    campagnesRappel: {
      list: () => Promise.resolve({ data: [CAMPAGNE_ROW] }),
      create: (...a) => campagneCreate(...a),
      peupler: (...a) => campagnePeupler(...a),
      notifier: (...a) => campagneNotifier(...a),
      cloturer: (...a) => campagneCloturer(...a),
    },
    elementsRappel: {
      list: () => Promise.resolve({ data: [ELEMENT_ROW] }),
      planifierRemplacement: (...a) => elementPlanifier(...a),
    },
    certifications: { list: empty, create: (...a) => certificationCreate(...a) },
    programmesAudit: { list: empty, create: (...a) => programmeCreate(...a) },
    reunionsQhse: {
      list: () => Promise.resolve({ data: [REUNION_ROW] }),
      create: (...a) => reunionCreate(...a),
    },
    decisionsReunion: {
      list: () => Promise.resolve({ data: [DECISION_ROW] }),
      create: (...a) => decisionCreate(...a),
      creerCapaDepuisDecision: (...a) => decisionCreerCapa(...a),
    },
    objectifsQhse: {
      list: () => Promise.resolve({ data: [OBJECTIF_ROW] }),
      create: (...a) => objectifCreate(...a),
    },
    revuesObjectif: { list: empty, create: (...a) => revueObjectifCreate(...a) },
  },
}))

import IsoQhse from './IsoQhse'

function withProviders(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

beforeEach(() => {
  vi.clearAllMocks()
  decisionCreerCapa.mockResolvedValue(reponseContrat('qhse', 'decision_reunion_creer_capa'))
})

describe('IsoQhse — Rappels produit (WIR276)', () => {
  it('crée une campagne de rappel', async () => {
    const user = userEvent.setup()
    withProviders(<IsoQhse />)
    await user.click(await screen.findByRole('button', { name: /Nouvelle campagne/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Titre'), 'Rappel onduleurs X')
    await user.type(within(dialog).getByLabelText('Produit (id)'), '12')
    await user.click(within(dialog).getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(campagneCreate).toHaveBeenCalledWith(
      expect.objectContaining({ titre: 'Rappel onduleurs X', produit: 12, gravite: 'majeure' }),
    ))
  })
})

describe('IsoQhse — Cycle de rappel produit (AUDV10)', () => {
  it('peuple une campagne depuis le parc réel', async () => {
    const user = userEvent.setup()
    withProviders(<IsoQhse />)
    await user.click(await screen.findByRole('button', { name: 'Peupler depuis le parc' }))
    await waitFor(() => expect(campagnePeupler).toHaveBeenCalledWith(1))
  })

  it('notifie les responsables des éléments à notifier', async () => {
    const user = userEvent.setup()
    withProviders(<IsoQhse />)
    await user.click(await screen.findByRole('button', { name: 'Notifier les responsables' }))
    await waitFor(() => expect(campagneNotifier).toHaveBeenCalledWith(1))
  })

  it('clôture une campagne après vérification d’efficacité (action au menu)', async () => {
    const user = userEvent.setup()
    withProviders(<IsoQhse />)
    // Deux listes (campagnes + éléments) partagent l'onglet — le kebab de la
    // campagne est le premier rendu dans le DOM.
    const kebabs = await screen.findAllByRole('button', { name: "Plus d'actions sur la ligne" })
    await user.click(kebabs[0])
    await user.click(await screen.findByRole('menuitem', { name: 'Clôturer' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Date de vérification d’efficacité'), '2026-09-04')
    await user.click(within(dialog).getByRole('button', { name: 'Clôturer' }))

    await waitFor(() => expect(campagneCloturer).toHaveBeenCalledWith(
      1, expect.objectContaining({ date_verification_efficacite: '2026-09-04' }),
    ))
  })

  it('planifie le remplacement SAV d’un élément concerné', async () => {
    const user = userEvent.setup()
    withProviders(<IsoQhse />)
    await user.click(await screen.findByRole('button', { name: 'Planifier remplacement' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Client (id)'), '55')
    await user.click(within(dialog).getByRole('button', { name: 'Planifier' }))

    await waitFor(() => expect(elementPlanifier).toHaveBeenCalledWith(
      200, { client_id: 55 },
    ))
  })
})

describe('IsoQhse — Certifications (WIR276)', () => {
  it('crée une certification', async () => {
    const user = userEvent.setup()
    withProviders(<IsoQhse />)
    await user.click(screen.getByRole('tab', { name: 'Certifications' }))
    await user.click(await screen.findByRole('button', { name: /Nouvelle certification/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Organisme'), 'IMANOR')
    await user.click(within(dialog).getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(certificationCreate).toHaveBeenCalledWith(
      expect.objectContaining({ referentiel: 'iso_9001', organisme: 'IMANOR' }),
    ))
  })
})

describe('IsoQhse — Programme d\'audit (WIR276)', () => {
  it('crée un programme d\'audit', async () => {
    const user = userEvent.setup()
    withProviders(<IsoQhse />)
    await user.click(screen.getByRole('tab', { name: 'Programme d’audit' }))
    await user.click(await screen.findByRole('button', { name: /Nouveau programme/ }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(programmeCreate).toHaveBeenCalledWith(
      expect.objectContaining({ annee: new Date().getFullYear() }),
    ))
  })
})

describe('IsoQhse — Revues de direction (WIR276)', () => {
  it('crée une réunion QHSE', async () => {
    const user = userEvent.setup()
    withProviders(<IsoQhse />)
    await user.click(screen.getByRole('tab', { name: 'Revues de direction' }))
    await user.click(await screen.findByRole('button', { name: /Nouvelle réunion/ }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(reunionCreate).toHaveBeenCalledWith(
      expect.objectContaining({ type_reunion: 'reunion_hse' }),
    ))
  })

  it('crée une décision rattachée à une réunion existante', async () => {
    const user = userEvent.setup()
    withProviders(<IsoQhse />)
    await user.click(screen.getByRole('tab', { name: 'Revues de direction' }))
    await waitFor(() => expect(screen.getAllByText('Renforcer la formation LOTO').length).toBeGreaterThan(0))

    await user.click(screen.getByRole('button', { name: /Nouvelle décision/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Décision'), 'Revoir la procédure LOTO')
    await user.click(within(dialog).getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(decisionCreate).toHaveBeenCalledWith(
      expect.objectContaining({ reunion: 40, texte: 'Revoir la procédure LOTO' }),
    ))
  })

  it('une décision sans CAPA propose « Créer CAPA » (contrat committé importé)', async () => {
    const user = userEvent.setup()
    withProviders(<IsoQhse />)
    await user.click(screen.getByRole('tab', { name: 'Revues de direction' }))
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'Créer CAPA' }).length).toBeGreaterThan(0))

    await user.click(screen.getAllByRole('button', { name: 'Créer CAPA' })[0])
    await waitFor(() => expect(decisionCreerCapa).toHaveBeenCalledWith(90))
  })
})

describe('IsoQhse — Objectifs QHSE (WIR276)', () => {
  it('crée un objectif', async () => {
    const user = userEvent.setup()
    withProviders(<IsoQhse />)
    await user.click(screen.getByRole('tab', { name: 'Objectifs QHSE' }))
    await user.click(await screen.findByRole('button', { name: /Nouvel objectif/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Intitulé'), 'Taux de satisfaction client')
    await user.click(within(dialog).getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(objectifCreate).toHaveBeenCalledWith(
      expect.objectContaining({ intitule: 'Taux de satisfaction client', domaine: 'qualite' }),
    ))
  })

  it('crée une revue rattachée à un objectif existant', async () => {
    const user = userEvent.setup()
    withProviders(<IsoQhse />)
    await user.click(screen.getByRole('tab', { name: 'Objectifs QHSE' }))
    await waitFor(() => expect(screen.getAllByText('Taux de fréquence accidents').length).toBeGreaterThan(0))

    await user.click(screen.getByRole('button', { name: /Nouvelle revue/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Valeur constatée'), '1.5')
    await user.click(within(dialog).getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(revueObjectifCreate).toHaveBeenCalledWith(
      expect.objectContaining({ objectif: 60, valeur_constatee: '1.5' }),
    ))
  })
})
