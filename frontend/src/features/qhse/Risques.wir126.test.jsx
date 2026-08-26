import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { reponseContrat } from '../../test/fixtures/contractSamples'

/* WIR126 — les onglets de Risques.jsx (Permis & LOTO, Incidents en priorité)
   étaient lecture seule alors que le backend supporte création + cycle de vie
   testés (PermisTravail créer/valider/clôturer, ConsignationLoto créer/
   déconsigner, Incident créer — débloque la chaîne d'escalade déjà testée
   côté serveur, AnalyseIncident.genererCapa). On vérifie que chaque onglet
   prioritaire expose désormais ses actions d'écriture de bout en bout.
   Réseau mocké.
   WIR278 — onglet « Contexte SMQ (ISO 4) » (contexte singleton + parties
   intéressées). Le mock de `contexteOrganisation.courant` IMPORTE le
   contrat committé (apps/qhse/contract_samples/contexte_organisation_courant.json,
   PACT10/13). */

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
  empty, permisCreate, permisValider, permisCloturer, lotoCreate,
  lotoDeconsigner, incidentCreate, genererCapa,
  exerciceCreate, exerciceRealiser, exerciceCreerCapa, exerciceDus, exerciceRelancer,
  permisPdf, inductionPdf, contexteCourant, contexteUpdateCourant, partieCreate,
} = vi.hoisted(() => ({
  empty: () => Promise.resolve({ data: [] }),
  permisCreate: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  permisValider: vi.fn(() => Promise.resolve({ data: {} })),
  permisCloturer: vi.fn(() => Promise.resolve({ data: {} })),
  lotoCreate: vi.fn(() => Promise.resolve({ data: { id: 2 } })),
  lotoDeconsigner: vi.fn(() => Promise.resolve({ data: {} })),
  incidentCreate: vi.fn(() => Promise.resolve({ data: { id: 3 } })),
  genererCapa: vi.fn(() => Promise.resolve({ data: {} })),
  // WIR234 — exercices d'urgence : planifier/réaliser/créer CAPA/dus+relancer.
  exerciceCreate: vi.fn(() => Promise.resolve({ data: { id: 70 } })),
  exerciceRealiser: vi.fn(() => Promise.resolve({ data: {} })),
  exerciceCreerCapa: vi.fn(() => Promise.resolve({ data: {} })),
  exerciceDus: vi.fn(() => Promise.resolve({ data: [] })),
  exerciceRelancer: vi.fn(() => Promise.resolve({ data: { relances: 1 } })),
  // WIR235 (XQHS27) — PDF terrain bilingue FR/AR (permis + induction).
  permisPdf: vi.fn(() => Promise.resolve({ data: new Blob(['%PDF-1.4']) })),
  inductionPdf: vi.fn(() => Promise.resolve({ data: new Blob(['%PDF-1.4']) })),
  // WIR278 (XQHS15) — contexte SMQ singleton + parties intéressées.
  contexteCourant: vi.fn(),
  contexteUpdateCourant: vi.fn(() => Promise.resolve({ data: {} })),
  partieCreate: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
}))

const PERMIS_ROW = {
  id: 10, reference: 'PT-000010', titre: 'Soudure toiture', type_permis: 'point_chaud',
  type_permis_display: 'Point chaud', statut: 'brouillon', date_fin: null,
}
const LOTO_ROW = {
  id: 20, reference: 'LOTO-000020', equipement: 'TGBT chantier',
  point_consignation: 'Disjoncteur principal', statut: 'consignee',
}
const PLAN_ROW = {
  id: 60, titre: 'Plan évacuation Bouskoura', chantier_id: 5,
  point_rassemblement: 'Portail principal', nb_secouristes: 2,
}
const PARTIE_ROW = {
  id: 100, partie: 'Client', attentes: 'Qualité et délais',
  pertinence: 'forte', pertinence_display: 'Forte',
}
const EXERCICE_PLANIFIE_ROW = {
  id: 70, plan: 60, plan_titre: 'Plan évacuation Bouskoura',
  type_exercice: 'evacuation', type_exercice_display: 'Évacuation',
  date_prevue: '2026-09-01', date_realisee: null, statut: 'planifie',
  statut_display: 'Planifié', observations: '', capa_liee: null,
}
const INDUCTION_ROW = {
  id: 80, personne_nom: 'Karim S.', chantier_id: 9, acquittement: false,
  date_induction: '2026-08-01',
}
const EXERCICE_ECART_ROW = {
  id: 71, plan: 60, plan_titre: 'Plan évacuation Bouskoura',
  type_exercice: 'evacuation', type_exercice_display: 'Évacuation',
  date_prevue: '2026-06-01', date_realisee: '2026-06-01', statut: 'realise',
  statut_display: 'Réalisé', observations: 'Sortie de secours bloquée',
  capa_liee: null,
}

vi.mock('../../api/qhseApi', () => ({
  default: {
    evaluationsRisque: { list: empty },
    risquesOpportunites: { list: empty, revuesDues: empty },
    permisTravail: {
      list: vi.fn(() => Promise.resolve({ data: [PERMIS_ROW] })),
      create: (...a) => permisCreate(...a),
      valider: (...a) => permisValider(...a),
      cloturer: (...a) => permisCloturer(...a),
      pdf: (...a) => permisPdf(...a),
    },
    consignationsLoto: {
      list: vi.fn(() => Promise.resolve({ data: [LOTO_ROW] })),
      create: (...a) => lotoCreate(...a),
      deconsigner: (...a) => lotoDeconsigner(...a),
    },
    inductionsSecurite: {
      list: vi.fn(() => Promise.resolve({ data: [INDUCTION_ROW] })),
      pdf: (...a) => inductionPdf(...a),
    },
    plansUrgence: { list: vi.fn(() => Promise.resolve({ data: [PLAN_ROW] })) },
    secouristes: { list: empty },
    exercicesUrgence: {
      list: vi.fn(() => Promise.resolve({
        data: [EXERCICE_PLANIFIE_ROW, EXERCICE_ECART_ROW],
      })),
      create: (...a) => exerciceCreate(...a),
      realiser: (...a) => exerciceRealiser(...a),
      creerCapa: (...a) => exerciceCreerCapa(...a),
      dus: (...a) => exerciceDus(...a),
      relancerExercices: (...a) => exerciceRelancer(...a),
    },
    incidents: {
      list: empty,
      create: (...a) => incidentCreate(...a),
      cloturer: vi.fn(() => Promise.resolve({ data: {} })),
      notificationsEnRetard: empty,
      relancerNotifications: vi.fn(() => Promise.resolve({ data: { relances: 0 } })),
    },
    declarationsCnss: { list: empty },
    analysesIncident: {
      list: vi.fn(() => Promise.resolve({
        data: [{ id: 30, incident_reference: 'INC-000030', methode_display: '5 pourquoi', nb_causes: 1, nb_capa: 0, statut_display: 'Ouverte' }],
      })),
      genererCapa: (...a) => genererCapa(...a),
    },
    observationsSecurite: { list: empty },
    liensSignalement: { list: empty },
    signalementsPublics: { list: empty },
    contexteOrganisation: {
      courant: (...a) => contexteCourant(...a),
      updateCourant: (...a) => contexteUpdateCourant(...a),
    },
    partiesInteressees: {
      list: vi.fn(() => Promise.resolve({ data: [PARTIE_ROW] })),
      create: (...a) => partieCreate(...a),
    },
  },
}))

vi.mock('../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

import Risques from './Risques'

function withProviders(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

beforeEach(() => {
  vi.clearAllMocks()
  contexteCourant.mockResolvedValue(
    reponseContrat('qhse', 'contexte_organisation_courant'))
})

describe('Risques — Permis & LOTO (WIR126)', () => {
  it('propose de créer un permis de travail et l\'envoie au serveur', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Permis & LOTO' }))

    // DataTable rend à la fois la table desktop et le repli carte mobile
    // (CSS seul, `dt-desktop:hidden` — les deux existent dans le DOM en
    // jsdom) : getAllByText, même patron que qhse.render.test.jsx.
    await waitFor(() => expect(screen.getAllByText('Soudure toiture').length).toBeGreaterThan(0))
    await user.click(screen.getByRole('button', { name: /Nouveau permis/ }))

    await user.type(screen.getByLabelText('Titre'), 'Travail en hauteur toiture')
    await user.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(permisCreate).toHaveBeenCalledWith(
      expect.objectContaining({ titre: 'Travail en hauteur toiture', type_permis: 'hauteur' }),
    ))
  })

  it('un permis brouillon peut être validé puis clôturé', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Permis & LOTO' }))
    await waitFor(() => expect(screen.getAllByText('Soudure toiture').length).toBeGreaterThan(0))

    // RowActions rend le bouton à la fois côté table desktop et carte
    // mobile (même patron que le texte de ligne ci-dessus) : premier match.
    await user.click(screen.getAllByRole('button', { name: 'Valider' })[0])
    await waitFor(() => expect(permisValider).toHaveBeenCalledWith(10))

    await user.click(screen.getAllByRole('button', { name: 'Clôturer' })[0])
    await waitFor(() => expect(permisCloturer).toHaveBeenCalledWith(10))
  })

  it('propose de créer une consignation LOTO rattachée à un permis', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Permis & LOTO' }))
    await waitFor(() => expect(screen.getAllByText('TGBT chantier').length).toBeGreaterThan(0))

    await user.click(screen.getByRole('button', { name: /Nouvelle consignation/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Équipement'), 'Armoire électrique')
    await user.click(within(dialog).getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(lotoCreate).toHaveBeenCalledWith(
      expect.objectContaining({ permis: 10, equipement: 'Armoire électrique' }),
    ))
  })

  it('une consignation consignée peut être déconsignée', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Permis & LOTO' }))
    await waitFor(() => expect(screen.getAllByText('TGBT chantier').length).toBeGreaterThan(0))

    await user.click(screen.getAllByRole('button', { name: 'Déconsigner' })[0])
    await waitFor(() => expect(lotoDeconsigner).toHaveBeenCalledWith(20))
  })
})

describe('Risques — Incidents (WIR126)', () => {
  it('propose de déclarer un incident et l\'envoie au serveur (débloque l\'escalade)', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Incidents' }))

    await user.click(await screen.findByRole('button', { name: /Déclarer un incident/ }))
    await user.type(screen.getByLabelText('Titre'), 'Chute d\'objet')
    await user.click(screen.getByRole('button', { name: 'Déclarer' }))

    await waitFor(() => expect(incidentCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        titre: 'Chute d\'objet', type_incident: 'incident', gravite: 'mineure',
      }),
    ))
  })

  it('une analyse d\'incident peut générer une CAPA', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Incidents' }))
    await waitFor(() => expect(screen.getAllByText('INC-000030').length).toBeGreaterThan(0))

    await user.click(screen.getAllByRole('button', { name: 'Générer CAPA' })[0])
    await waitFor(() => expect(genererCapa).toHaveBeenCalledWith(30))
  })
})

describe('Risques — Exercices d\'urgence / drills (WIR234)', () => {
  it('propose de planifier un exercice rattaché à un plan, envoyé au serveur', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Préparation site' }))
    await waitFor(() => expect(screen.getAllByText('Plan évacuation Bouskoura').length).toBeGreaterThan(0))

    await user.click(screen.getByRole('button', { name: /Planifier un exercice/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Date prévue'), '2026-10-01')
    await user.click(within(dialog).getByRole('button', { name: 'Planifier' }))

    await waitFor(() => expect(exerciceCreate).toHaveBeenCalledWith(
      expect.objectContaining({ plan: 60, type_exercice: 'evacuation', date_prevue: '2026-10-01' }),
    ))
  })

  it('un exercice planifié se réalise (chrono + participants + observations)', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Préparation site' }))
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'Réaliser' }).length).toBeGreaterThan(0))

    await user.click(screen.getAllByRole('button', { name: 'Réaliser' })[0])
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Durée d’évacuation (secondes)'), '180')
    await user.type(within(dialog).getByLabelText('Nombre de participants'), '15')
    await user.click(within(dialog).getByRole('button', { name: 'Enregistrer la réalisation' }))

    await waitFor(() => expect(exerciceRealiser).toHaveBeenCalledWith(70,
      expect.objectContaining({ duree_evacuation_secondes: 180, nb_participants: 15 })))
  })

  it('un exercice réalisé avec un écart propose Créer CAPA (le planifié, non)', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Préparation site' }))
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'Réaliser' }).length).toBeGreaterThan(0))
    // Un seul exercice (l'écart, id 71) porte le bouton — l'autre est encore
    // `planifie` et ne l'affiche pas.
    expect(screen.getAllByRole('button', { name: 'Créer CAPA' }).length).toBeGreaterThan(0)

    await user.click(screen.getAllByRole('button', { name: 'Créer CAPA' })[0])
    await waitFor(() => expect(exerciceCreerCapa).toHaveBeenCalledWith(71))
  })

  it('liste les plans en retard d\'exercice et relance en masse', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Préparation site' }))
    await waitFor(() => expect(exerciceDus).toHaveBeenCalled())

    await user.click(screen.getByRole('button', { name: /Relancer/ }))
    await waitFor(() => expect(exerciceRelancer).toHaveBeenCalled())
  })
})

describe('Risques — PDF terrain bilingues FR/AR (WIR235)', () => {
  beforeEach(() => {
    URL.createObjectURL = vi.fn(() => 'blob:mock')
    URL.revokeObjectURL = vi.fn()
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  })

  it('un permis de travail se télécharge en PDF (FR) puis (AR)', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Permis & LOTO' }))
    await waitFor(() => expect(screen.getAllByText('Soudure toiture').length).toBeGreaterThan(0))

    // Un permis « brouillon » porte 4 actions (Valider, Clôturer, PDF FR, PDF
    // AR) : `RowActions` n'en révèle que 2 en raccourci, les PDF vivent dans
    // le menu kebab de la ligne.
    const ligne = screen.getAllByText('Soudure toiture')
      .map((el) => el.closest('tr')).find(Boolean)
    await user.click(within(ligne).getByLabelText("Plus d'actions sur la ligne"))
    await user.click(await screen.findByRole('menuitem', { name: 'PDF (FR)' }))
    await waitFor(() => expect(permisPdf).toHaveBeenCalledWith(10, { lang: 'fr' }))

    await user.click(within(ligne).getByLabelText("Plus d'actions sur la ligne"))
    await user.click(await screen.findByRole('menuitem', { name: 'PDF (AR)' }))
    await waitFor(() => expect(permisPdf).toHaveBeenCalledWith(10, { lang: 'ar' }))
  })

  it('une induction sécurité se télécharge en PDF (FR) puis (AR)', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Préparation site' }))
    await waitFor(() => expect(screen.getAllByText('Karim S.').length).toBeGreaterThan(0))

    await user.click(screen.getAllByRole('button', { name: 'PDF (FR)' })[0])
    await waitFor(() => expect(inductionPdf).toHaveBeenCalledWith(80, { lang: 'fr' }))

    await user.click(screen.getAllByRole('button', { name: 'PDF (AR)' })[0])
    await waitFor(() => expect(inductionPdf).toHaveBeenCalledWith(80, { lang: 'ar' }))
  })
})

describe('Risques — Contexte SMQ ISO 4 (WIR278)', () => {
  it('charge le contexte singleton (contrat committé importé) et l’enregistre', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Contexte SMQ (ISO 4)' }))

    const swot = await screen.findByLabelText('SWOT')
    // `toHaveValue` compare en `===` (jest-dom `compareAsSet`) : il n'accepte
    // AUCUN matcher asymétrique. On compare donc la valeur elle-même.
    await waitFor(() => expect(swot.value).toEqual(
      expect.stringContaining('équipe technique solaire expérimentée')))

    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(contexteUpdateCourant).toHaveBeenCalledWith(
      expect.objectContaining({
        swot: expect.stringContaining('équipe technique solaire expérimentée'),
      }),
    ))
  })

  it('crée une partie intéressée', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Contexte SMQ (ISO 4)' }))
    await waitFor(() => expect(screen.getAllByText('Client').length).toBeGreaterThan(0))

    await user.click(screen.getByRole('button', { name: /Nouvelle partie intéressée/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Partie'), 'Autorité locale')
    await user.click(within(dialog).getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(partieCreate).toHaveBeenCalledWith(
      expect.objectContaining({ partie: 'Autorité locale', pertinence: 'moyenne' }),
    ))
  })
})
