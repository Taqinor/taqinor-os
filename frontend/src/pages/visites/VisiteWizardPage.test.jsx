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

const { getVisite, terminerVisite, qualifierVisite, patchVisiteMesures } = vi.hoisted(() => ({
  getVisite: vi.fn(),
  terminerVisite: vi.fn(),
  qualifierVisite: vi.fn(),
  patchVisiteMesures: vi.fn(),
}))

vi.mock('../../api/visitesApi', () => ({
  default: {
    getVisite: (...a) => getVisite(...a),
    terminerVisite: (...a) => terminerVisite(...a),
    qualifierVisite: (...a) => qualifierVisite(...a),
    uploadVisitePhoto: vi.fn(),
    deleteVisitePhoto: vi.fn(),
    patchVisiteMesures: (...a) => patchVisiteMesures(...a),
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
import { MESURES_SCHEMA, MESURES_SCHEMA_CI } from './visiteHelpers'
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

/* CIQ609 — gabarit `ci` (site professionnel) : le mock est l'`exemple_ci` du
   contrat partagé `visite_terrain.json` (check_api_shapes), jamais inventé.
   L'exemple ne porte qu'une catégorie de checklist : les onglets sont dérivés
   des catégories du contrat `gabarit_ci`. */
describe('VisiteWizardPage — CIQ609 (gabarit ci)', () => {
  const contrat = documentContrat('visites', 'visite_terrain')
  const CATEGORIES_CI = Object.keys(contrat.gabarit_ci)
  const CI = {
    ...contrat.exemple_ci,
    qualification: null,
    checklist: CATEGORIES_CI.map((categorie) => ({ categorie, libelle: categorie, slots: [] })),
  }
  const catId = (categorie, cle) => `visite-mesure-${categorie}-${cle}`

  beforeEach(() => {
    patchVisiteMesures.mockResolvedValue({ data: {} })
    getVisite.mockResolvedValue({ data: CI })
  })

  it('titre « Visite technique — site professionnel », jamais de champ de toit résidentiel', async () => {
    withProviders()
    expect(await screen.findByRole('heading', { name: 'Visite technique — site professionnel' })).toBeInTheDocument()
    expect(screen.queryByText('Longueur de la zone utile')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /calage du toit/i })).not.toBeInTheDocument()
  })

  it('le schéma reprend les codes, libellés et choix du contrat gabarit_ci, tels quels', () => {
    for (const [categorie, bloc] of Object.entries(contrat.gabarit_ci)) {
      const schema = MESURES_SCHEMA_CI[categorie]
      expect(schema, categorie).toBeTruthy()
      expect(schema.map((c) => c.key), categorie).toEqual(Object.keys(bloc.mesures))
      for (const champ of schema) {
        const def = bloc.mesures[champ.key]
        expect(champ.label, champ.key).toBe(def.libelle)
        if (def.type === 'choix') {
          expect(champ.options.map((o) => o.value), champ.key).toEqual(def.choix)
        }
      }
    }
    // Les champs d'une zone sont ceux de l'exemple servi.
    const zone = contrat.exemple_ci.mesures.toiture_ci.zones_toiture[0]
    const forme = MESURES_SCHEMA_CI.toiture_ci[0].forme
    expect(['id', ...forme.map((c) => c.key)].sort()).toEqual(Object.keys(zone).sort())
    // Gabarits toiture et point_eau : schémas inchangés.
    expect(MESURES_SCHEMA.cheminement.map((c) => c.key)).toEqual(['longueur_estimee_m'])
  })

  it('l’ordre des onglets suit la checklist servie', async () => {
    withProviders()
    await screen.findByRole('heading', { name: 'Visite technique — site professionnel' })
    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual(CATEGORIES_CI)
  })

  it('ajoute une 2e zone de toiture et enregistre les deux, sans arrondir un nombre tapé', async () => {
    const user = userEvent.setup()
    withProviders()
    await user.click(await screen.findByRole('tab', { name: 'toiture_ci' }))
    const form = await screen.findByTestId('visite-mesures-toiture_ci')
    expect(form.querySelectorAll('[data-testid^="visite-ligne-zones_toiture-"]')).toHaveLength(1)
    await user.click(screen.getByRole('button', { name: 'Ajouter une zone' }))
    expect(form.querySelectorAll('[data-testid^="visite-ligne-zones_toiture-"]')).toHaveLength(2)
    const nom = form.querySelector(`#${catId('toiture_ci', 'zones_toiture-z2-libelle')}`)
    await user.type(nom, 'Atelier sud')
    const pente = form.querySelector(`#${catId('toiture_ci', 'zones_toiture-z2-pente_deg')}`)
    expect(pente).toHaveAttribute('step', 'any')
    await user.type(pente, '12.5')
    expect(pente).toHaveValue(12.5)
    await user.click(screen.getByRole('button', { name: /enregistrer les mesures/i }))
    const [visiteId, categorie, valeurs] = patchVisiteMesures.mock.calls[0]
    expect([String(visiteId), categorie]).toEqual(['7', 'toiture_ci'])
    expect(valeurs.zones_toiture.map((z) => z.id)).toEqual(['z1', 'z2'])
    expect(valeurs.zones_toiture[1]).toMatchObject({ libelle: 'Atelier sud', pente_deg: 12.5 })
  })

  it('supprime une zone', async () => {
    const user = userEvent.setup()
    withProviders()
    await user.click(await screen.findByRole('tab', { name: 'toiture_ci' }))
    const form = await screen.findByTestId('visite-mesures-toiture_ci')
    await user.click(screen.getByRole('button', { name: 'Supprimer zone 1' }))
    expect(form.querySelectorAll('[data-testid^="visite-ligne-zones_toiture-"]')).toHaveLength(0)
    await user.click(screen.getByRole('button', { name: /enregistrer les mesures/i }))
    expect(patchVisiteMesures.mock.calls[0][2].zones_toiture).toEqual([])
  })

  it('« non relevé » + motif : l’état du serveur est repris, et un nouveau part avec son motif', async () => {
    const user = userEvent.setup()
    withProviders()
    await user.click(await screen.findByRole('tab', { name: 'comptage' }))
    const form = await screen.findByTestId('visite-mesures-comptage')
    // Venu du serveur (`exemple_ci._non_releves`) : puissance souscrite.
    const deja = form.querySelector(`#${catId('comptage', 'puissance_souscrite_kva_constatee')}-nr`)
    expect(deja).toBeChecked()
    expect(form.querySelector(`#${catId('comptage', 'puissance_souscrite_kva_constatee')}`)).toBeDisabled()
    // Nouveau : type de compteur non relevé, site fermé.
    const caseType = form.querySelector(`#${catId('comptage', 'type_compteur')}-nr`)
    await user.click(caseType)
    await user.click(form.querySelector(`#${catId('comptage', 'type_compteur')}-motif`))
    await user.click(await screen.findByRole('option', { name: 'Site fermé' }))
    await user.click(screen.getByRole('button', { name: /enregistrer les mesures/i }))
    expect(patchVisiteMesures.mock.calls[0][2]._non_releves).toEqual({
      puissance_souscrite_kva_constatee: 'a_faire_par_electricien',
      type_compteur: 'site_ferme',
    })
  })

  it('l’erreur du serveur s’affiche sous le champ fautif (motif manquant)', async () => {
    patchVisiteMesures.mockRejectedValue({
      response: { data: { erreurs: { '_non_releves.type_compteur': 'Motif requis pour Type de compteur.' } } },
    })
    const user = userEvent.setup()
    withProviders()
    await user.click(await screen.findByRole('tab', { name: 'comptage' }))
    const form = await screen.findByTestId('visite-mesures-comptage')
    await user.click(form.querySelector(`#${catId('comptage', 'type_compteur')}-nr`))
    await user.click(screen.getByRole('button', { name: /enregistrer les mesures/i }))
    expect(await screen.findByText('Motif requis pour Type de compteur.')).toBeInTheDocument()
  })

  it('tous les booléens sont des tri-états : jamais un « Non » enregistré sans réponse', async () => {
    getVisite.mockResolvedValue({
      data: { ...CI, mesures: { ...CI.mesures, tableau_general: { ...CI.mesures.tableau_general, parafoudre_existant: null } } },
    })
    const user = userEvent.setup()
    withProviders()
    await user.click(await screen.findByRole('tab', { name: 'tableau_general' }))
    const form = await screen.findByTestId('visite-mesures-tableau_general')
    expect(screen.getByLabelText('Parafoudre existant')).toHaveTextContent('pas encore relevé')
    await user.click(screen.getByRole('button', { name: /enregistrer les mesures/i }))
    expect(patchVisiteMesures.mock.calls[0][2].parafoudre_existant).toBeNull()
    expect(form.querySelector('form')).toHaveAttribute('novalidate')
  })

  it('terminer : activé dès que le serveur dit complet', async () => {
    getVisite.mockResolvedValue({
      data: { ...CI, completude: { complet: true, manquants: [] }, qualification: contrat.exemple.qualification },
    })
    terminerVisite.mockResolvedValue({ data: { ...CI, statut: 'terminee' } })
    const user = userEvent.setup()
    withProviders()
    await user.click(await screen.findByRole('button', { name: /terminer la visite/i }))
    expect(terminerVisite).toHaveBeenCalledWith('7')
    await vi.waitFor(() => expect(toastSuccess).toHaveBeenCalled())
  })

  it('la complétude vient TOUJOURS du serveur : manquants affichés tels quels', async () => {
    withProviders()
    const bloc = await screen.findByTestId('visite-manquants')
    for (const m of CI.completude.manquants) expect(bloc).toHaveTextContent(m.libelle)
    expect(await screen.findByRole('button', { name: /il manque des éléments/i })).toBeDisabled()
  })

  it('le décideur « propriétaire tiers » est proposé', async () => {
    withProviders()
    await screen.findByRole('heading', { name: 'Visite technique — site professionnel' })
    expect(screen.getByRole('button', { name: 'Le propriétaire (un tiers) décide' })).toBeInTheDocument()
  })
})

/* CIQ653 — catégorie « site commerce » : le mock est l'`exemple_ci_commerce` du
   contrat partagé `visite_terrain.json` (check_api_shapes), jamais inventé. */
describe('VisiteWizardPage — CIQ653 (site commerce)', () => {
  const contrat = documentContrat('visites', 'visite_terrain')
  const SITE_CONTRAT = contrat.gabarit_ci_site_commerce.site_commerce
  const COMMERCE = contrat.exemple_ci_commerce
  const tuile = (code, libelle) => ({
    ...COMMERCE.checklist[0].slots[0], code, libelle, requis: false, etat: 'manquant', photos: [],
  })
  const visite = (slots, mesures = COMMERCE.mesures) => ({
    ...COMMERCE,
    qualification: null,
    mesures,
    checklist: [
      { categorie: 'site_commerce', libelle: 'Site commerce', slots },
      ...Object.keys(contrat.gabarit_ci).map((categorie) => ({ categorie, libelle: categorie, slots: [] })),
    ],
  })
  const catId = (cle) => `visite-mesure-site_commerce-${cle}`

  beforeEach(() => {
    patchVisiteMesures.mockResolvedValue({ data: {} })
    getVisite.mockResolvedValue({ data: visite([tuile('secours_existant', 'Secours existant')]) })
  })

  it('le schéma reprend les codes, libellés et choix du contrat, tels quels', () => {
    const schema = MESURES_SCHEMA_CI.site_commerce
    expect(schema.map((c) => c.key)).toEqual(Object.keys(SITE_CONTRAT.mesures))
    for (const champ of schema) {
      const def = SITE_CONTRAT.mesures[champ.key]
      expect(champ.label, champ.key).toBe(def.libelle)
      if (def.type === 'choix') expect(champ.options.map((o) => o.value), champ.key).toEqual(def.choix)
    }
    const circuits = schema.find((c) => c.key === 'circuits_critiques')
    expect(circuits.forme.map((c) => c.key)).toEqual(Object.keys(SITE_CONTRAT.mesures.circuits_critiques.forme))
    expect(circuits.forme[0].options.map((o) => o.value)).toEqual(['froid', 'medical', 'informatique', 'cuisine', 'autre'])
  })

  it('l’exemple servi se rend avec tous ses champs (aucun champ du contrat oublié)', async () => {
    withProviders()
    await screen.findByRole('heading', { name: 'Visite technique — site professionnel' })
    const form = await screen.findByTestId('visite-mesures-site_commerce')
    for (const champ of MESURES_SCHEMA_CI.site_commerce) {
      if (champ.type === 'list') {
        expect(form.querySelector(`[data-testid="visite-liste-${champ.key}"]`), champ.key).toBeTruthy()
      } else {
        expect(form.querySelector(`#${catId(champ.key)}`), champ.key).toBeTruthy()
      }
    }
    expect(screen.getByLabelText("Horaires et jours d'ouverture")).toHaveValue('11 h–23 h, 7/7')
    expect(form.querySelector('form')).toHaveAttribute('novalidate')
  })

  it('saisie : horaires, circuit critique, besoin de continuité — le PATCH porte les clés du contrat', async () => {
    getVisite.mockResolvedValue({
      data: visite([tuile('secours_existant', 'Secours existant')], {
        ...COMMERCE.mesures,
        site_commerce: Object.fromEntries(Object.keys(SITE_CONTRAT.mesures).map((k) => [k, k === 'circuits_critiques' ? [] : null])),
      }),
    })
    const user = userEvent.setup()
    withProviders()
    const form = await screen.findByTestId('visite-mesures-site_commerce')
    await user.type(screen.getByLabelText("Horaires et jours d'ouverture"), '8 h–20 h, lun–sam')
    await user.click(screen.getByRole('button', { name: 'Ajouter un circuit critique' }))
    await user.click(form.querySelector('#visite-mesure-site_commerce-circuits_critiques-0-circuit'))
    await user.click(await screen.findByRole('option', { name: 'Matériel médical' }))
    await user.click(screen.getByLabelText('Besoin de continuité de service'))
    await user.click(await screen.findByRole('option', { name: 'Oui' }))
    await user.click(screen.getByRole('button', { name: /enregistrer les mesures/i }))
    const valeurs = patchVisiteMesures.mock.calls[0][2]
    expect(Object.keys(valeurs).sort()).toEqual([...Object.keys(SITE_CONTRAT.mesures), '_non_releves'].sort())
    expect(valeurs.horaires_constates).toBe('8 h–20 h, lun–sam')
    expect(valeurs.circuits_critiques).toEqual([{ circuit: 'medical', precision: null }])
    expect(valeurs.besoin_continuite_service).toBe(true)
    // Un booléen jamais répondu reste « pas encore relevé » (null), jamais « Non ».
    expect(valeurs.secours_ups).toBeNull()
  })

  it('l’erreur du serveur s’affiche sous le champ fautif', async () => {
    patchVisiteMesures.mockRejectedValue({
      response: { data: { erreurs: { categorie: '« Catégorie du site » : valeur inconnue « casino ».' } } },
    })
    const user = userEvent.setup()
    withProviders()
    await screen.findByTestId('visite-mesures-site_commerce')
    await user.click(screen.getByRole('button', { name: /enregistrer les mesures/i }))
    expect(await screen.findByText('« Catégorie du site » : valeur inconnue « casino ».')).toBeInTheDocument()
  })

  it('la pièce « accord du propriétaire » n’est affichée que si le serveur la sert', async () => {
    withProviders()
    await screen.findByTestId('visite-slot-secours_existant')
    expect(screen.queryByTestId('visite-slot-accord_proprietaire')).not.toBeInTheDocument()
  })

  it('serveur : lead locataire → la tuile « accord du propriétaire » est présente', async () => {
    getVisite.mockResolvedValue({
      data: visite([tuile('secours_existant', 'Secours existant'), tuile('accord_proprietaire', 'Accord du propriétaire')]),
    })
    withProviders()
    expect(await screen.findByTestId('visite-slot-accord_proprietaire')).toHaveTextContent('Accord du propriétaire')
  })

  it('terminer : activé dès que le serveur dit complet', async () => {
    getVisite.mockResolvedValue({
      data: { ...visite([tuile('secours_existant', 'Secours existant')]), completude: { complet: true, manquants: [] }, qualification: contrat.exemple.qualification },
    })
    terminerVisite.mockResolvedValue({ data: { ...COMMERCE, statut: 'terminee' } })
    const user = userEvent.setup()
    withProviders()
    await user.click(await screen.findByRole('button', { name: /terminer la visite/i }))
    expect(terminerVisite).toHaveBeenCalledWith('7')
    await vi.waitFor(() => expect(toastSuccess).toHaveBeenCalled())
  })

  it('enregistrer → rouvrir → enregistrer sans toucher = même PATCH', async () => {
    const user = userEvent.setup()
    const premier = withProviders()
    await screen.findByTestId('visite-mesures-site_commerce')
    await user.click(screen.getByRole('button', { name: /enregistrer les mesures/i }))
    const p1 = patchVisiteMesures.mock.calls[0][2]
    premier.unmount()
    // Le serveur rend la valeur normalisée : on rouvre dessus.
    getVisite.mockResolvedValue({
      data: visite([tuile('secours_existant', 'Secours existant')], { ...COMMERCE.mesures, site_commerce: JSON.parse(JSON.stringify(p1)) }),
    })
    withProviders()
    await screen.findByTestId('visite-mesures-site_commerce')
    await user.click(screen.getByRole('button', { name: /enregistrer les mesures/i }))
    expect(patchVisiteMesures.mock.calls[1][2]).toEqual(p1)
  })
})

/* CIQ661 — supplément MT : le mock est l'`exemple_ci_mt` du contrat partagé
   `visite_terrain.json` (check_api_shapes), jamais inventé. Les catégories du
   supplément sont SERVIES par le serveur quand le niveau constaté vaut `mt`. */
describe('VisiteWizardPage — CIQ661 (supplément MT)', () => {
  const contrat = documentContrat('visites', 'visite_terrain')
  const SUPPLEMENT = contrat.gabarit_ci_supplement_mt
  const CATEGORIES_MT = Object.keys(SUPPLEMENT)
  const MT = contrat.exemple_ci_mt
  const tuile = (code) => ({
    ...MT.checklist[0].slots[0], code, libelle: code, requis: true, etat: 'manquant', photos: [],
  })
  const bloc = (categorie) => ({
    categorie,
    libelle: categorie,
    slots: Object.keys(SUPPLEMENT[categorie]?.photos ?? {}).map(tuile),
  })
  const SOCLE = Object.keys(contrat.gabarit_ci).map((categorie) => ({ categorie, libelle: categorie, slots: [] }))
  const visiteMt = { ...MT, qualification: null, checklist: [...SOCLE, ...CATEGORIES_MT.map(bloc)] }
  const visiteBt = {
    ...visiteMt,
    mesures: { ...MT.mesures, comptage: { ...MT.mesures.comptage, niveau_tension_constate: 'bt' } },
    checklist: SOCLE,
  }
  const catId = (categorie, cle) => `visite-mesure-${categorie}-${cle}`

  beforeEach(() => {
    patchVisiteMesures.mockResolvedValue({ data: {} })
    getVisite.mockResolvedValue({ data: visiteMt })
  })

  it('le schéma reprend les codes, libellés, choix et formes du contrat, tels quels', () => {
    for (const [categorie, def] of Object.entries(SUPPLEMENT)) {
      const schema = MESURES_SCHEMA_CI[categorie]
      expect(schema, categorie).toBeTruthy()
      expect(schema.map((c) => c.key), categorie).toEqual(Object.keys(def.mesures))
      for (const champ of schema) {
        const mesure = def.mesures[champ.key]
        expect(champ.label, champ.key).toBe(mesure.libelle)
        if (mesure.type === 'choix') expect(champ.options.map((o) => o.value), champ.key).toEqual(mesure.choix)
        if (mesure.type === 'liste') {
          expect(champ.forme.map((c) => c.key), champ.key).toEqual(Object.keys(mesure.forme))
        }
      }
    }
  })

  it('MT servi : les catégories du supplément s’affichent, dans l’ordre servi', async () => {
    withProviders()
    await screen.findByRole('heading', { name: 'Visite technique — site professionnel' })
    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual([
      ...Object.keys(contrat.gabarit_ci), ...CATEGORIES_MT,
    ])
  })

  it('passer le niveau à MT fait apparaître le supplément (rechargé depuis le serveur)', async () => {
    getVisite.mockResolvedValueOnce({ data: visiteBt }).mockResolvedValue({ data: visiteMt })
    const user = userEvent.setup()
    withProviders()
    await user.click(await screen.findByRole('tab', { name: 'comptage' }))
    expect(screen.queryByRole('tab', { name: 'poste_mt' })).not.toBeInTheDocument()
    await user.click(await screen.findByLabelText('Niveau de tension constaté'))
    await user.click(await screen.findByRole('option', { name: 'Moyenne tension (MT)' }))
    await user.click(screen.getByRole('button', { name: /enregistrer les mesures/i }))
    expect(patchVisiteMesures.mock.calls[0][2].niveau_tension_constate).toBe('mt')
    expect(await screen.findByRole('tab', { name: 'poste_mt' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'reseau_assurance' })).toBeInTheDocument()
  })

  it('les tuiles photo du poste (cellule, plaque) et des factures sont servies et prises en photo', async () => {
    const user = userEvent.setup()
    withProviders()
    await user.click(await screen.findByRole('tab', { name: 'poste_mt' }))
    expect(await screen.findByTestId('visite-slot-cellule_mt')).toHaveTextContent('Ajouter une photo')
    expect(screen.getByTestId('visite-slot-transformateur_plaque')).toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: 'factures_mt' }))
    expect(await screen.findByTestId('visite-slot-factures_mt')).toHaveTextContent('Ajouter une photo')
  })

  it('la source du cos φ est obligatoire : l’erreur serveur s’affiche sous le champ', async () => {
    patchVisiteMesures.mockRejectedValue({
      response: { data: { erreurs: { source_cos_phi: '« Source du cos φ » est obligatoire dès que « cos φ constaté » est saisi.' } } },
    })
    const user = userEvent.setup()
    withProviders()
    await user.click(await screen.findByRole('tab', { name: 'factures_mt' }))
    const form = await screen.findByTestId('visite-mesures-factures_mt')
    const cos = form.querySelector(`#${catId('factures_mt', 'cos_phi_constate')}`)
    expect(cos).toHaveAttribute('step', 'any')
    await user.type(cos, '0.82')
    expect(cos).toHaveValue(0.82)
    await user.click(screen.getByRole('button', { name: /enregistrer les mesures/i }))
    expect(await screen.findByText('« Source du cos φ » est obligatoire dès que « cos φ constaté » est saisi.')).toBeInTheDocument()
    expect(patchVisiteMesures.mock.calls[0][2].cos_phi_constate).toBe(0.82)
  })

  it('« non relevé » + motif sur une cellule : état du serveur repris, nouveau motif envoyé', async () => {
    const user = userEvent.setup()
    withProviders()
    await user.click(await screen.findByRole('tab', { name: 'reactif_secours' }))
    const form = await screen.findByTestId('visite-mesures-reactif_secours')
    expect(form.querySelector(`#${catId('reactif_secours', 'condensateurs_kvar')}-nr`)).toBeChecked()
    expect(form.querySelector(`#${catId('reactif_secours', 'condensateurs_kvar')}`)).toBeDisabled()
    await user.click(form.querySelector(`#${catId('reactif_secours', 'condensateurs_etat')}-nr`))
    await user.click(form.querySelector(`#${catId('reactif_secours', 'condensateurs_etat')}-motif`))
    await user.click(await screen.findByRole('option', { name: 'Dangereux' }))
    await user.click(screen.getByRole('button', { name: /enregistrer les mesures/i }))
    expect(patchVisiteMesures.mock.calls[0][2]._non_releves).toEqual({
      condensateurs_kvar: 'acces_refuse', condensateurs_etat: 'dangereux',
    })
  })

  it('un transformateur s’ajoute (nombre et kVA, jamais arrondis) ; la date ANRE est une date, les pièces des références', async () => {
    const user = userEvent.setup()
    withProviders()
    await user.click(await screen.findByRole('tab', { name: 'poste_mt' }))
    const form = await screen.findByTestId('visite-mesures-poste_mt')
    await user.click(screen.getByRole('button', { name: 'Ajouter un transformateur' }))
    const kva = form.querySelector(`#${catId('poste_mt', 'transformateurs-1-kva')}`)
    expect(kva).toHaveAttribute('step', 'any')
    await user.type(kva, '630.5')
    expect(kva).toHaveValue(630.5)
    await user.click(screen.getByRole('button', { name: /enregistrer les mesures/i }))
    expect(patchVisiteMesures.mock.calls[0][2].transformateurs[1]).toMatchObject({ kva: 630.5, nb: null })
    await user.click(screen.getByRole('tab', { name: 'reseau_assurance' }))
    const reseau = await screen.findByTestId('visite-mesures-reseau_assurance')
    expect(reseau.querySelector(`#${catId('reseau_assurance', 'capacite_consultee_le')}`)).toHaveAttribute('type', 'date')
    expect(reseau.querySelector(`#${catId('reseau_assurance', 'profil_charge_mesure_fichier')}`)).toHaveAttribute('type', 'text')
    expect(reseau.querySelector('form')).toHaveAttribute('novalidate')
  })

  it('terminer : activé dès que le serveur dit complet', async () => {
    getVisite.mockResolvedValue({
      data: { ...visiteMt, completude: { complet: true, manquants: [] }, qualification: contrat.exemple.qualification },
    })
    terminerVisite.mockResolvedValue({ data: { ...visiteMt, statut: 'terminee' } })
    const user = userEvent.setup()
    withProviders()
    await user.click(await screen.findByRole('button', { name: /terminer la visite/i }))
    expect(terminerVisite).toHaveBeenCalledWith('7')
    await vi.waitFor(() => expect(toastSuccess).toHaveBeenCalled())
  })
})
