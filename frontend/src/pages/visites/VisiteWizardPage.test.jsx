// VT10 — l'écran wizard affiche les manquants EXACTEMENT comme le serveur
// les liste (jamais une re-dérivation locale), la tuile « à refaire » montre
// le motif serveur, « Terminer » reste désactivé tant que la visite est
// incomplète, et le panneau devis n'affiche jamais `prix_achat`. Le fixture
// ci-dessous copie la forme du contrat committé
// `apps/crm/contract_samples/visite_terrain.json` (PACT10).
import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

const VISITE_INCOMPLETE = {
  id: 7, lead: 118, statut: 'en_cours', date_prevue: '2026-09-15', date_realisee: null,
  notes: '', modifiable: true, raison_lecture_seule: '',
  photo_toit: { assemblage_etat: 'aucun', assemblage_erreur: '', url: null, texture_calage: null },
  checklist: [
    {
      categorie: 'toiture', libelle: 'Toiture',
      slots: [
        {
          code: 'toiture_vue_generale', libelle: 'Vue générale du toit',
          guide: 'Cadrer tout le pan de toit utile.', requis: true, min_photos: 2, etat: 'ok',
          photos: [{ id: 31, url: '/media/toit-1.jpg', filename: 'toit-1.jpg', gps_lat: 33.5, gps_lng: -7.5, commentaire: '', a_refaire: false, motif_refaire: '' }],
        },
        {
          code: 'toiture_obstacles', libelle: 'Obstacles et ombrages',
          guide: 'Cheminées, antennes, arbres.', requis: true, min_photos: 1, etat: 'a_refaire',
          photos: [{ id: 32, url: '/media/obstacle-1.jpg', filename: 'obstacle-1.jpg', gps_lat: null, gps_lng: null, commentaire: '', a_refaire: true, motif_refaire: 'Photo floue — reprendre l’antenne côté est.' }],
        },
      ],
    },
    {
      categorie: 'tableau', libelle: 'Tableau électrique',
      slots: [{ code: 'tableau_ouvert', libelle: 'Tableau ouvert (disjoncteurs visibles)', guide: 'Capot ouvert.', requis: true, min_photos: 1, etat: 'manquant', photos: [] }],
    },
    {
      categorie: 'local_onduleur', libelle: 'Emplacement onduleur',
      slots: [{ code: 'onduleur_mur', libelle: 'Mur d’installation prévu', guide: '', requis: true, min_photos: 1, etat: 'manquant', photos: [] }],
    },
    {
      categorie: 'cheminement', libelle: 'Cheminement des câbles',
      slots: [{ code: 'cheminement_parcours', libelle: 'Parcours toit → onduleur', guide: '', requis: false, min_photos: 1, etat: 'manquant', photos: [] }],
    },
    {
      categorie: 'general', libelle: 'Général',
      slots: [{ code: 'general_facade', libelle: 'Façade du bâtiment', guide: '', requis: true, min_photos: 1, etat: 'manquant', photos: [] }],
    },
  ],
  mesures: {
    toiture: { longueur_m: 12.5, largeur_m: 8.0, pente_deg: 15.0, toit_plat: false, orientation: 'sud', type_couverture: 'tuile', etat_couverture: 'bon', obstacles_notes: '' },
    tableau: { calibre_disjoncteur_a: 63, type_alimentation: 'mono', emplacements_libres: 4 },
    local_onduleur: { largeur_mur_cm: null, hauteur_mur_cm: null, profondeur_degagement_cm: null, distance_tableau_m: null, local_abrite: null, local_ventile: null },
    cheminement: { longueur_estimee_m: null },
  },
  completude: {
    complet: false,
    manquants: [
      { type: 'photo', categorie: 'tableau', code: 'tableau_ouvert', libelle: 'Tableau ouvert (disjoncteurs visibles)' },
      { type: 'photo_a_refaire', categorie: 'toiture', code: 'toiture_obstacles', libelle: 'Obstacles et ombrages' },
      { type: 'mesure', categorie: 'local_onduleur', code: 'largeur_mur_cm', libelle: 'Largeur du mur libre (cm)' },
    ],
  },
  client_panel: {
    lead_nom: 'Client Démo', telephone: '+212600000000', whatsapp: '+212600000000',
    adresse: 'Quartier Démo, Bouskoura', ville: 'Bouskoura', gps_lat: 33.4589, gps_lng: -7.6528,
  },
  devis: [
    {
      id: 214, numero: 'DEV-202609-0012', statut: 'envoye', date: '2026-09-02', total_ttc: '84500.00',
      lignes: [{ designation: 'Panneau 550 Wc', quantite: '12.000', prix_unitaire_ttc: '1850.00', total_ttc: '22200.00' }],
    },
  ],
}

const { getVisite, terminerVisite, qualifierVisite } = vi.hoisted(() => ({
  getVisite: vi.fn(),
  terminerVisite: vi.fn(),
  qualifierVisite: vi.fn(),
}))

vi.mock('../../api/visitesApi', () => ({
  default: {
    getVisite: (...a) => getVisite(...a),
    terminerVisite: (...a) => terminerVisite(...a),
    qualifierVisite: (...a) => qualifierVisite(...a),
    uploadVisitePhoto: vi.fn(),
    deleteVisitePhoto: vi.fn(),
    patchVisiteMesures: vi.fn(),
    // VTA11 — l'historique des visites du même lead (panneau en lecture seule
    // monté par le wizard). Liste vide ici : ces cas testent le wizard.
    getVisites: vi.fn(async () => ({ data: [] })),
  },
}))

// VISITE-QUALIF — `toast.message` (le rappel non bloquant de fin de visite)
// est espionné ; `success`/`error` sont neutralisés aussi (aucun <Toaster/>
// monté ici — pas besoin des vrais appels sonner pour ces cas).
const { toastMessage, toastSuccess, toastError } = vi.hoisted(() => ({
  toastMessage: vi.fn(), toastSuccess: vi.fn(), toastError: vi.fn(),
}))
vi.mock('../../ui/confirm', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    toast: { ...actual.toast, message: toastMessage, success: toastSuccess, error: toastError },
  }
})

import VisiteWizardPage from './VisiteWizardPage'
import { MESURES_SCHEMA } from './visiteHelpers'
import { documentContrat } from '../../test/fixtures/contractSamples'

function withProviders() {
  return render(
    <MemoryRouter initialEntries={['/visites/7']}>
      <Routes>
        <Route path="/visites/:id" element={<VisiteWizardPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  getVisite.mockResolvedValue({ data: VISITE_INCOMPLETE })
})

describe('VisiteWizardPage — VT10', () => {
  it('affiche les manquants EXACTEMENT comme le serveur les liste (mêmes libellés, jamais reformulés)', async () => {
    withProviders()
    const bloc = await screen.findByTestId('visite-manquants')
    expect(bloc).toHaveTextContent('Tableau ouvert (disjoncteurs visibles)')
    expect(bloc).toHaveTextContent('Obstacles et ombrages')
    expect(bloc).toHaveTextContent('Largeur du mur libre (cm)')
  })

  it('la tuile « à refaire » montre le motif serveur', async () => {
    withProviders()
    expect(await screen.findByText('Photo floue — reprendre l’antenne côté est.')).toBeInTheDocument()
  })

  it('« Terminer » reste désactivé tant que la visite est incomplète (completude.complet=false)', async () => {
    withProviders()
    const bouton = await screen.findByRole('button', { name: /il manque des éléments/i })
    expect(bouton).toBeDisabled()
    expect(terminerVisite).not.toHaveBeenCalled()
  })

  it('« Terminer » est activé quand completude.complet=true', async () => {
    getVisite.mockResolvedValue({
      data: { ...VISITE_INCOMPLETE, completude: { complet: true, manquants: [] } },
    })
    withProviders()
    const bouton = await screen.findByRole('button', { name: /terminer la visite/i })
    expect(bouton).not.toBeDisabled()
  })

  it('le panneau devis n’affiche jamais prix_achat (le serveur ne l’envoie pas, l’écran n’en ajoute pas)', async () => {
    withProviders()
    const panneau = await screen.findByTestId('visite-client-devis-panel')
    expect(panneau.textContent).not.toMatch(/prix.?achat/i)
    expect(panneau).toHaveTextContent('DEV-202609-0012')
  })

  it('le formulaire mesures : inputs numériques step="any" + form noValidate (aucun nombre tapé avalé/rejeté)', async () => {
    withProviders()
    await screen.findByTestId('visite-mesures-toiture')
    const input = screen.getByLabelText(/Longueur de la zone utile/i)
    expect(input).toHaveAttribute('step', 'any')
    expect(input.closest('form')).toHaveAttribute('novalidate')
  })

  it('affiche le panneau client (VT7) avec le lien WhatsApp et sans invention', async () => {
    withProviders()
    const panneau = await screen.findByTestId('visite-client-devis-panel')
    expect(panneau).toHaveTextContent('Client Démo')
    const wa = screen.getByRole('link', { name: /whatsapp/i })
    expect(wa).toHaveAttribute('href', 'https://wa.me/212600000000')
  })
})

// VISITE-QUALIF — bloc « Qualification client », placé juste avant l'action
// Terminer : défauts pré-sélectionnés, rappel non bloquant si jamais
// enregistrée, aucun rappel une fois enregistrée, résumé lecture seule.
describe('VisiteWizardPage — VISITE-QUALIF', () => {
  it('affiche le bloc Qualification client avec ses défauts pré-sélectionnés', async () => {
    withProviders()
    const bloc = await screen.findByTestId('visite-qualification')
    expect(bloc).toHaveTextContent('Qualification client')
    expect(screen.getByRole('button', { name: 'Tiède' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('« Terminer » sans qualification : le 1er clic NE termine PAS, le 2e (assumé) termine', async () => {
    // Le retour vers l'historique du lead part au moment de terminer/ — une
    // qualification enregistrée après coup n'y serait plus. Le 1er clic
    // s'arrête donc et propose de l'enregistrer ; le bouton devient
    // « Terminer sans qualification » et seul CE clic assumé termine.
    getVisite.mockResolvedValue({
      data: { ...VISITE_INCOMPLETE, completude: { complet: true, manquants: [] } },
    })
    terminerVisite.mockResolvedValue({
      data: { ...VISITE_INCOMPLETE, statut: 'terminee', completude: { complet: true, manquants: [] } },
    })
    const user = userEvent.setup()
    withProviders()
    const bouton = await screen.findByRole('button', { name: /terminer la visite/i })
    await user.click(bouton)
    expect(toastMessage).toHaveBeenCalled()
    expect(terminerVisite).not.toHaveBeenCalled()
    const assume = await screen.findByRole(
      'button', { name: /terminer sans qualification/i })
    await user.click(assume)
    expect(terminerVisite).toHaveBeenCalledWith('7')
    // Laisse le POST terminer/ (mocké résolu) se résoudre avant la fin du test
    // — sinon la mise à jour d'état arrive après le démontage (act warning).
    await vi.waitFor(() => expect(toastSuccess).toHaveBeenCalled())
  })

  it('« Terminer » avec une qualification déjà enregistrée ne déclenche AUCUN rappel', async () => {
    getVisite.mockResolvedValue({
      data: {
        ...VISITE_INCOMPLETE,
        completude: { complet: true, manquants: [] },
        qualification: {
          temperature: 'chaud', devis: 'convient', devis_details: '', decideur: 'seul',
          frein: 'aucun', declencheur: 'economies', rappel: 'demain_matin', conseil_closing: '',
        },
      },
    })
    terminerVisite.mockResolvedValue({ data: { ...VISITE_INCOMPLETE, statut: 'terminee' } })
    const user = userEvent.setup()
    withProviders()
    const bouton = await screen.findByRole('button', { name: /terminer la visite/i })
    await user.click(bouton)
    expect(toastMessage).not.toHaveBeenCalled()
    expect(terminerVisite).toHaveBeenCalledWith('7')
    await vi.waitFor(() => expect(toastSuccess).toHaveBeenCalled())
  })

  it('visite non modifiable (validée) : résumé lecture seule, jamais les chips interactives', async () => {
    getVisite.mockResolvedValue({
      data: {
        ...VISITE_INCOMPLETE,
        modifiable: false,
        raison_lecture_seule: 'Visite déjà validée.',
        completude: { complet: true, manquants: [] },
        qualification: {
          temperature: 'froid', devis: 'nouveau', devis_details: 'Toit trop petit', decideur: 'seul',
          frein: 'timing', declencheur: 'ecologie', rappel: 'cette_semaine', conseil_closing: '',
        },
      },
    })
    withProviders()
    const bloc = await screen.findByTestId('visite-qualification')
    expect(bloc).toHaveTextContent('Froid')
    expect(screen.queryByRole('button', { name: /enregistrer la qualification/i })).not.toBeInTheDocument()
  })
})

/* AGR422 — gabarit « relevé du point d'eau » : le mock est l'`exemple_point_eau`
   du contrat partagé `visite_terrain.json` (check_api_shapes), jamais inventé. */
describe('VisiteWizardPage — AGR422 (gabarit point_eau)', () => {
  const contrat = documentContrat('visites', 'visite_terrain')
  const POINT_EAU = { ...contrat.exemple_point_eau, qualification: null }

  const catId = (categorie, cle) => `visite-mesure-${categorie}-${cle}`

  it('titre « Visite de relevé du point d’eau », jamais de champ de toit', async () => {
    getVisite.mockResolvedValue({ data: POINT_EAU })
    withProviders()
    expect(await screen.findByRole('heading', { name: 'Visite de relevé du point d’eau' })).toBeInTheDocument()
    expect(screen.queryByText('Longueur de la zone utile')).not.toBeInTheDocument()
    expect(screen.queryByText('Orientation')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /calage du toit/i })).not.toBeInTheDocument()
  })

  it('l’ordre des onglets suit le gabarit servi', async () => {
    getVisite.mockResolvedValue({ data: POINT_EAU })
    withProviders()
    await screen.findByRole('heading', { name: 'Visite de relevé du point d’eau' })
    const onglets = screen.getAllByRole('tab').map((t) => t.textContent)
    expect(onglets).toEqual(POINT_EAU.checklist.map((c) => c.libelle))
  })

  it('le schéma de mesures reprend les codes ET les choix du contrat, tels quels', () => {
    const gabarit = contrat.gabarit_point_eau
    for (const [categorie, bloc] of Object.entries(gabarit)) {
      const schema = MESURES_SCHEMA[categorie]
      expect(schema, categorie).toBeTruthy()
      expect(schema.map((c) => c.key), categorie).toEqual(Object.keys(bloc.mesures))
      for (const champ of schema) {
        const def = bloc.mesures[champ.key]
        expect(champ.label, champ.key).toBe(def.libelle)
        if (def.type === 'choix') {
          expect(champ.options.map((o) => o.value), champ.key).toEqual(def.choix)
          for (const o of champ.options) expect(o.label.trim().length).toBeGreaterThan(0)
        }
      }
    }
    // Le gabarit toiture est inchangé.
    expect(MESURES_SCHEMA.toiture.map((c) => c.key)).toEqual([
      'longueur_m', 'largeur_m', 'toit_plat', 'pente_deg', 'orientation',
      'type_couverture', 'etat_couverture', 'obstacles_notes',
    ])
  })

  it('on saisit une mesure (12,5 jamais arrondi) et on coche « non mesurable »', async () => {
    getVisite.mockResolvedValue({ data: POINT_EAU })
    const user = userEvent.setup()
    withProviders()
    const niveau = await screen.findByLabelText(/Niveau statique \(pompe arrêtée\)/)
    expect(niveau.id).toBe(catId('point_eau', 'niveau_statique_m'))
    expect(niveau).toHaveAttribute('step', 'any')
    await user.clear(niveau)
    await user.type(niveau, '12.5')
    expect(niveau).toHaveValue(12.5)
    const caseDebit = await screen.findByRole('checkbox', { name: 'Débit non mesurable sur place' })
    expect(caseDebit).not.toBeChecked()
    await user.click(caseDebit)
    expect(caseDebit).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Niveau non mesurable sur place' })).toBeInTheDocument()
  })

  it('chaque catégorie du gabarit affiche ses mesures et le tri-état n’enregistre pas « Non » sans réponse', async () => {
    getVisite.mockResolvedValue({ data: POINT_EAU })
    const user = userEvent.setup()
    withProviders()
    await screen.findByRole('heading', { name: 'Visite de relevé du point d’eau' })
    for (const categorie of ['pompe_existante', 'electricite', 'site_pv', 'administratif']) {
      const libelle = POINT_EAU.checklist.find((c) => c.categorie === categorie).libelle
      await user.click(screen.getByRole('tab', { name: libelle }))
      const form = await screen.findByTestId(`visite-mesures-${categorie}`)
      for (const champ of MESURES_SCHEMA[categorie]) {
        expect(form.querySelector(`#${catId(categorie, champ.key)}`), `${categorie}.${champ.key}`).toBeTruthy()
      }
    }
    // « compteur_eau » (requis) vaut null dans l'exemple : le sélecteur reste
    // sur « pas encore relevé ».
    expect(screen.getByLabelText("Compteur d'eau sur le forage")).toHaveTextContent('pas encore relevé')
  })

  it('terminer sans aucun champ de toit : activé dès que le serveur dit complet', async () => {
    getVisite.mockResolvedValue({
      data: { ...POINT_EAU, completude: { complet: true, manquants: [] } },
    })
    withProviders()
    const bouton = await screen.findByRole('button', { name: /terminer la visite/i })
    expect(bouton).not.toBeDisabled()
    expect(screen.queryByText('Longueur de la zone utile')).not.toBeInTheDocument()
  })

  it('la complétude vient TOUJOURS du serveur : manquants affichés tels quels', async () => {
    getVisite.mockResolvedValue({ data: POINT_EAU })
    withProviders()
    const bloc = await screen.findByTestId('visite-manquants')
    for (const m of POINT_EAU.completude.manquants) expect(bloc).toHaveTextContent(m.libelle)
    expect(await screen.findByRole('button', { name: /il manque des éléments/i })).toBeDisabled()
  })

  it('une visite toiture garde son titre (nom du client) et ses champs', async () => {
    getVisite.mockResolvedValue({ data: { ...VISITE_INCOMPLETE, gabarit: 'toiture' } })
    withProviders()
    expect(await screen.findByRole('heading', { name: 'Client Démo' })).toBeInTheDocument()
    expect(screen.getByText('Longueur de la zone utile (m)')).toBeInTheDocument()
  })
})
