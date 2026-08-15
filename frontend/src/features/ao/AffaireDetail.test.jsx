import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  getComments: vi.fn(),
  getAttachments: vi.fn(),
  createComment: vi.fn(),
  uploadAttachment: vi.fn(),
  affairesList: vi.fn(),
  toituresList: vi.fn(),
  variantesList: vi.fn(),
  dossiersList: vi.fn(),
  dossierGet: vi.fn(),
  genererPiece: vi.fn(),
  // AOF176 — appelé par le contenu PAR DÉFAUT de l'emplacement « actions » de
  // `DossierPage` (contrôles avant dépôt + ZIP), désormais monté sans que le
  // monteur ait à le passer.
  controlesAvantDepot: vi.fn(),
  seriesList: vi.fn(),
  seriesCreate: vi.fn(),
  calepinageGet: vi.fn(),
  calepinageCalculer: vi.fn(),
  // Seconde vague 03/08/2026 — les 3 derniers écrans inatteignables.
  batimentsList: vi.fn(),
  toituresCreate: vi.fn(),
  equipementsList: vi.fn(),
  exigencesList: vi.fn(),
  exigencesCreate: vi.fn(),
  // PACT69 — le panneau « Bordereau » interroge désormais la VRAIE ressource
  // (`aoApi.bordereaux`), publiée par cette même tâche.
  bordereauxList: vi.fn(),
  bordereauxGet: vi.fn(),
  bordereauxControles: vi.fn(),
  lignesBordereauUpdate: vi.fn(),
  // PACT70 — l'onglet « Suivi administratif » (SuiviAdministratifAO).
  cautionsList: vi.fn(),
  echeancesAoList: vi.fn(),
  resultatsAoList: vi.fn(),
  // PACT71/PACT72 — `DossierPage` monte désormais aussi `ChecklistPartenaire`
  // et `PiecesFournies` PAR DÉFAUT (pleine largeur, sous sa grille).
  completude: vi.fn(),
  checklistList: vi.fn(),
  piecesFourniesList: vi.fn(),
  // PACT74 — l'onglet « Pièces du DCE » (PiecesConsultation).
  piecesConsultationList: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useParams: () => ({ id: '1' }) }
})

vi.mock('../../api/aoApi', () => ({
  default: {
    // WIR206 — `transitions`/`lead` sont interrogés au montage par
    // StatutChanger/LeadPanel : sans bouchon, un appel sur `undefined` fait
    // planter TOUTE la fiche (pas seulement le nouveau contrôle).
    affaires: {
      get: mocks.get, list: mocks.affairesList,
      transitions: () => Promise.resolve({ data: { statut: 'brouillon', statut_display: 'Brouillon', transitions: [] } }),
      lead: () => Promise.resolve({ data: { lead_id: null, fiche: null } }),
      changerStatut: vi.fn(), rattacherLead: vi.fn(),
    },
    // Ce que le serveur persiste réellement pour un calepinage (AOF28).
    // WIR207 — `appliquerPreset` : bouchon défensif, au cas où un flux de
    // test ouvre l'atelier d'une toiture (PresetToitureSelector).
    toitures: { list: mocks.toituresList, create: mocks.toituresCreate, appliquerPreset: vi.fn() },
    bibliotheque: { list: () => Promise.resolve({ data: [] }) },
    // Le panneau Toitures ouvre le wizard de création : une toiture se
    // rattache à un BÂTIMENT (ToitureAO n'a aucune FK vers l'affaire).
    batiments: { list: mocks.batimentsList },
    variantes: { list: mocks.variantesList },
    dossiers: {
      list: mocks.dossiersList, get: mocks.dossierGet, genererPiece: mocks.genererPiece,
      controlesAvantDepot: mocks.controlesAvantDepot, completude: mocks.completude,
    },
    checklistPartenaire: { list: mocks.checklistList, pointer: vi.fn() },
    piecesDossierAo: { list: mocks.piecesFourniesList, update: vi.fn() },
    piecesConsultation: { list: mocks.piecesConsultationList, create: vi.fn(), update: vi.fn(), additif: vi.fn() },
    seriesQR: { list: mocks.seriesList, create: mocks.seriesCreate },
    calepinages: { get: mocks.calepinageGet, calculer: mocks.calepinageCalculer },
    equipements: { list: mocks.equipementsList, bascule: vi.fn() },
    exigencesCps: { list: mocks.exigencesList, create: mocks.exigencesCreate },
    bordereaux: {
      list: mocks.bordereauxList, get: mocks.bordereauxGet, controles: mocks.bordereauxControles,
    },
    lignesBordereau: { update: mocks.lignesBordereauUpdate },
    cautionsSoumission: { list: mocks.cautionsList, create: vi.fn(), deriverDefinitive: vi.fn() },
    echeancesAo: { list: mocks.echeancesAoList, create: vi.fn(), update: vi.fn() },
    resultatsAo: { list: mocks.resultatsAoList, enregistrer: vi.fn() },
  },
}))

// L'aperçu du CPS (AOF175) importe pdfjs : hors sujet ici, on prouve seulement
// que l'onglet monte le VRAI ExigencesPage (même bouchon que son propre test).
vi.mock('./dossier/PiecePreview', () => ({
  default: ({ piece }) => <div data-testid="apercu-cps">{piece ? piece.libelle : 'aucune pièce'}</div>,
}))

/* `VariantesCompare` (onglet « Variantes ») lit la permission élevée
   `ao_rentabilite_voir` via `useHasPermission`, qui passe par le store Redux —
   absent de ce rendu. On la refuse : c'est le cas par défaut de la fiche, et
   celui qui garantit qu'aucune donnée d'économie n'entre dans l'arbre. */
vi.mock('../../hooks/useHasPermission', () => ({
  useHasPermission: () => false,
  useHasRole: () => false,
  useIsAdmin: () => false,
  useIsAdminOrResponsable: () => false,
}))

vi.mock('../../api/recordsApi', () => ({
  default: {
    getComments: mocks.getComments,
    getAttachments: mocks.getAttachments,
    createComment: mocks.createComment,
    uploadAttachment: mocks.uploadAttachment,
  },
}))

import AffaireDetail from './AffaireDetail'

const here = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(join(here, 'AffaireDetail.jsx'), 'utf8')

/* Les gardes de structure portent sur le CODE, pas sur la prose : la fiche
   DOIT pouvoir raconter dans ses commentaires ce qu'elle a réparé (« cinq
   onglets rendaient un TabPlaceholder », « aucun panneau n'importe
   aoRentabiliteApi ») sans qu'une garde anti-régression prenne cette mémoire
   pour une rechute. On retire donc commentaires de bloc et de ligne avant
   d'assertionner. */
const codeSeul = source
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/^\s*\/\/.*$/gm, '')

const renderScreen = () => render(<MemoryRouter><AffaireDetail /></MemoryRouter>)

const AFFAIRE = {
  id: 1, reference: 'AO-2026-001', objet: 'Centrale solaire école',
  acheteur: 'Commune X', type_marche: 'public', type_marche_display: 'Public',
  lot: 'Lot 1', date_limite: '2026-09-15', montant_estime: 1500000,
  caution_provisoire: 30000, statut: 'depose',
  verdict_global: 'confirme', verdict_global_label: 'Confirmé',
  prochaine_echeance_libelle: 'Remise des plis', prochaine_echeance_date: '2026-09-15',
  dossier_completude: 62, resultat_issue_display: null,
}

const COMMENTS = [
  { id: 10, body: 'Visite de site effectuée.', author_display: 'Reda Kasri', created_at: '2026-08-01T10:00:00Z' },
]

// Une variante de calepinage telle que `variantes-calepinage` la renvoie.
const VARIANTE = { id: 42, nom: 'Variante portrait 4 rangées', role: 'candidate', statut: 'brouillon' }

// Un dossier de dépôt : son id (77) est DIFFÉRENT de l'id d'affaire (1) —
// c'est ce qui rend visible le piège `useParams` de `DossierPage`.
const DOSSIER = { id: 77, reference: 'AODOS-202608-0001', statut: 'brouillon', pieces: [], echeances: [] }

// Charge utile de l'atelier de calepinage (contrat `PlanLayer`/`VerdictBar`) :
// des grandeurs GÉOMÉTRIQUES (modules/kWc), aucune donnée économique.
const PLAN = {
  plan: {
    cadre: { x_min: 0, y_min: 0, largeur_m: 40, hauteur_m: 20 },
    rangees: [], allees: [], rives: [], degagements: [], obstacles: [], zones: [],
  },
  resultat: {
    modules: { valeur: 314, texte: '314 modules' },
    verdict: { code: 'confirme', libelle: 'Confirmé' },
  },
  parametres: { taille_chaine: 18 },
}

const onglet = (nom) => screen.getByRole('tab', { name: nom })

beforeEach(() => {
  vi.clearAllMocks()
  mocks.get.mockResolvedValue({ data: AFFAIRE })
  mocks.getComments.mockResolvedValue({ data: COMMENTS })
  mocks.getAttachments.mockResolvedValue({ data: [] })
  mocks.createComment.mockResolvedValue({ data: {} })
  mocks.variantesList.mockResolvedValue({ data: [VARIANTE] })
  mocks.dossiersList.mockResolvedValue({ data: [DOSSIER] })
  mocks.dossierGet.mockResolvedValue({ data: DOSSIER })
  mocks.seriesList.mockResolvedValue({ data: [] })
  mocks.calepinageGet.mockResolvedValue({ data: PLAN })
  mocks.toituresList.mockResolvedValue({ data: [] })
  mocks.affairesList.mockResolvedValue({ data: [] })
  mocks.batimentsList.mockResolvedValue({ data: [] })
  mocks.toituresCreate.mockResolvedValue({ data: { id: 900 } })
  mocks.equipementsList.mockResolvedValue({ data: [] })
  mocks.exigencesList.mockResolvedValue({ data: [] })
  mocks.controlesAvantDepot.mockResolvedValue({ data: { controles: [] } })
  mocks.bordereauxList.mockResolvedValue({ data: [] })
  mocks.cautionsList.mockResolvedValue({ data: [] })
  mocks.echeancesAoList.mockResolvedValue({ data: [] })
  mocks.resultatsAoList.mockResolvedValue({ data: [] })
  mocks.completude.mockResolvedValue({ data: { complet: false, raisons_de_non_depot: [] } })
  mocks.checklistList.mockResolvedValue({ data: [] })
  mocks.piecesFourniesList.mockResolvedValue({ data: [] })
  mocks.piecesConsultationList.mockResolvedValue({ data: [] })
})

// Les 13 onglets de la fiche, dans leur ordre RÉEL : les 7 d'origine, les 3
// ajoutés le 03/08/2026, « Variantes » (PACT171), « Suivi administratif »
// (PACT70), puis « Pièces du DCE » (PACT74) — l'ordre des 12 premiers ne
// bouge jamais (un onglet nouveau s'ajoute EN QUEUE, il ne s'intercale pas).
const ONGLETS = [
  'Synthèse', 'Toitures & relevés', 'Calepinages', 'Bordereau',
  'Dossier', 'Questions terrain', 'Historique',
  'Administratif', 'Équipements', 'CPS & exigences',
  'Variantes', 'Suivi administratif', 'Pièces du DCE',
]

describe('AffaireDetail', () => {
  it('charge la fiche via aoApi.affaires.get(id) et affiche référence/objet/statut', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith('1'))
    expect((await screen.findAllByText('AO-2026-001')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Centrale solaire école').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Déposé').length).toBeGreaterThan(0)
  })

  it('affiche les 7 onglets attendus (Synthèse, Toitures & relevés, Calepinages, Bordereau, Dossier, Questions terrain, Historique)', async () => {
    renderScreen()
    await screen.findAllByText('AO-2026-001')
    for (const label of [
      'Synthèse', 'Toitures & relevés', 'Calepinages', 'Bordereau',
      'Dossier', 'Questions terrain', 'Historique',
    ]) {
      expect(screen.getByRole('tab', { name: label })).toBeInTheDocument()
    }
  })

  it('ajoute les 3 onglets du 03/08/2026 APRÈS les 7, sans toucher à leur ordre', async () => {
    renderScreen()
    await screen.findAllByText('AO-2026-001')
    for (const label of ['Administratif', 'Équipements', 'CPS & exigences']) {
      expect(screen.getByRole('tab', { name: label })).toBeInTheDocument()
    }
    // L'ordre RENDU est l'ordre déclaré : les 7 d'origine d'abord, intacts.
    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual(ONGLETS)
  })

  it('ajoute « Variantes » (PACT171) en 11e onglet, APRÈS les 10 précédents', async () => {
    renderScreen()
    await screen.findAllByText('AO-2026-001')
    expect(screen.getByRole('tab', { name: 'Variantes' })).toBeInTheDocument()
    const onglets = screen.getAllByRole('tab').map((t) => t.textContent)
    expect(onglets).toEqual(ONGLETS)
    expect(onglets[10]).toBe('Variantes')
  })

  it('ajoute « Suivi administratif » (PACT70) en 12e onglet', async () => {
    renderScreen()
    await screen.findAllByText('AO-2026-001')
    const onglets = screen.getAllByRole('tab').map((t) => t.textContent)
    expect(onglets).toEqual(ONGLETS)
    expect(onglets[onglets.length - 2]).toBe('Suivi administratif')
  })

  it('ajoute « Pièces du DCE » (PACT74) en 13e et dernier onglet', async () => {
    renderScreen()
    await screen.findAllByText('AO-2026-001')
    const onglets = screen.getAllByRole('tab').map((t) => t.textContent)
    expect(onglets).toEqual(ONGLETS)
    expect(onglets[onglets.length - 1]).toBe('Pièces du DCE')
  })

  it('n’a JAMAIS un onglet ou un mot « rentabilité » dans l’arbre (route séparée AOF161)', async () => {
    renderScreen()
    await screen.findAllByText('AO-2026-001')
    expect(screen.queryByText(/rentabilit/i)).toBeNull()
    expect(screen.queryByRole('tab', { name: /rentabilit/i })).toBeNull()
  })

  it('le bandeau de verdict affiche verdict/échéance/complétude issus tels quels de l’affaire (aucun calcul de KPI)', async () => {
    renderScreen()
    await screen.findAllByText('AO-2026-001')
    expect(screen.getAllByText('Confirmé').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Remise des plis').length).toBeGreaterThan(0)
    expect(screen.getAllByText('62 %').length).toBeGreaterThan(0)
  })

  it('le bandeau retombe sur « — » quand un champ agrégé est absent (jamais un calcul de substitution)', async () => {
    mocks.get.mockResolvedValue({
      data: { ...AFFAIRE, verdict_global: null, verdict_global_label: null, dossier_completude: null, resultat_issue_display: null },
    })
    renderScreen()
    await screen.findAllByText('AO-2026-001')
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
  })

  it('le chatter (ChatterTimeline, cible ao.appeloffre) affiche les notes de records', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.getComments).toHaveBeenCalledWith('ao.appeloffre', '1'))
    expect((await screen.findAllByText(/Visite de site effectuée/)).length).toBeGreaterThan(0)
  })

  it('ajouter une note appelle recordsApi.createComment(ao.appeloffre, id, texte) et vide le champ', async () => {
    renderScreen()
    await screen.findAllByText('AO-2026-001')
    const textarea = screen.getByLabelText('Nouvelle note')
    fireEvent.change(textarea, { target: { value: 'Nouvelle observation terrain.' } })
    fireEvent.click(screen.getAllByRole('button', { name: /Noter/i })[0])
    await waitFor(() => expect(mocks.createComment).toHaveBeenCalledWith(
      'ao.appeloffre', '1', 'Nouvelle observation terrain.',
    ))
    await waitFor(() => expect(textarea.value).toBe(''))
  })

  /* ══ RÉPARATION 03/08/2026 — les 5 onglets morts rendent leur VRAI panneau ══
     La fiche déclarait 7 onglets et en rendait CINQ en `TabPlaceholder` muet
     alors que les panneaux existaient, non importés. Chaque test ci-dessous
     épingle le panneau RÉEL (ou son état vide MOTIVÉ), pas un libellé. */

  describe('les 5 onglets branchés sur leur panneau réel', () => {
    it('« Questions terrain » monte le VRAI SeriesPage, filtré sur l’affaire (appel_offre)', async () => {
      renderScreen()
      await screen.findAllByText('AO-2026-001')
      await userEvent.click(onglet('Questions terrain'))

      // Le filtre serveur s'appelle `appel_offre` — `affaire` serait ignoré en
      // silence (liste de toute la société avec l'air d'être filtrée).
      await waitFor(() => expect(mocks.seriesList).toHaveBeenCalledWith({ appel_offre: '1' }))
      // Titre propre à SeriesPage (jamais rendu par un placeholder).
      expect(await screen.findByRole('heading', { name: 'Questions terrain' })).toBeInTheDocument()
      expect(screen.getAllByRole('button', { name: /Nouvelle série/ })[0]).toBeInTheDocument()
    })

    // CONTRAT CORRIGÉ 03/08/2026 : l'atelier pilote une TOITURE, pas une
    // variante. L'onglet et l'atelier avaient été écrits en parallèle et ne se
    // parlaient pas — l'atelier recevait `undefined`. Ces tests épinglent
    // désormais le contrat RÉEL, des deux côtés.
    it('« Calepinages » liste les TOITURES de l’affaire et monte le VRAI atelier', async () => {
      mocks.toituresList.mockResolvedValue({ data: [{ id: 42, nom: 'Toiture bâtiment C' }] })
      renderScreen()
      await screen.findAllByText('AO-2026-001')
      await userEvent.click(onglet('Calepinages'))

      await waitFor(() => expect(mocks.toituresList).toHaveBeenCalledWith({ appel_offre: '1' }))
      // Le sélecteur porte sur la TOITURE, pas sur un « calepinage » — il
      // n'existe aucun modèle `Calepinage` côté serveur.
      expect(await screen.findByLabelText('Toiture')).toBeInTheDocument()
      // Et l'onglet n'interroge JAMAIS la ressource fictive `calepinages`.
      expect(mocks.calepinageGet).not.toHaveBeenCalled()
    })

    // Garde de CONTRAT ENTRE LES DEUX MOITIÉS : le nom de la propriété passée
    // à l'atelier doit être celui que l'atelier déclare. C'est exactement ce
    // qui a failli partir en silence (l'onglet passait `calepinageId`, l'atelier
    // attendait `toitureId` → `undefined`, aucun test ne le voyait).
    it('l’onglet passe à l’atelier la propriété que l’atelier DÉCLARE (toitureId)', () => {
      const studio = readFileSync(join(here, 'calepinage/CalepinageStudio.jsx'), 'utf8')
      const declaree = studio.match(/export default function CalepinageStudio\(\{\s*([A-Za-z]+)/)
      expect(declaree, 'signature de CalepinageStudio illisible').not.toBeNull()
      expect(codeSeul).toMatch(new RegExp(`<CalepinageStudio\\s+${declaree[1]}=`))
    })

    it('« Calepinages » affiche un état vide qui DIT pourquoi (jamais un écran blanc)', async () => {
      mocks.toituresList.mockResolvedValue({ data: [] })
      renderScreen()
      await screen.findAllByText('AO-2026-001')
      await userEvent.click(onglet('Calepinages'))

      expect((await screen.findAllByText('Aucune toiture à calepiner')).length).toBeGreaterThan(0)
      expect(screen.getAllByText(/se calcule SUR une toiture/).length).toBeGreaterThan(0)
    })

    // PV59 — la synthèse multi-toitures (PV68 `synthese_calepinage`, dans la
    // MÊME requête `aoApi.affaires.get(id)` que le reste de la fiche).
    describe('« Calepinages » — synthèse multi-toitures (PV59/PV68)', () => {
      const SYNTHESE = {
        total_modules: 350, total_kwc: 218, toitures_total: 3, toitures_calepinees: 2,
        toitures: [
          {
            toiture: 42, code_document: '05H', designation: '', batiment: 5, batiment_code: 'C',
            calepinee: true, variante: 100, variante_nom: 'Retenue', statut: 'publiable',
            modules: 200, kwc: 125, optimal: true, methode: 'dp_exact_1cm',
          },
          {
            toiture: 43, code_document: '06H', designation: '', batiment: 5, batiment_code: 'C',
            calepinee: true, variante: 101, variante_nom: 'Retenue', statut: 'publiable',
            modules: 150, kwc: 93, optimal: true, methode: 'dp_exact_1cm',
          },
          {
            toiture: 44, code_document: '07H', designation: '', batiment: 6, batiment_code: 'D',
            calepinee: false, variante: null, variante_nom: '', statut: '',
            modules: 0, kwc: 0, optimal: null, methode: '',
          },
        ],
      }

      it('affiche les totaux, le compte de toitures manquantes et une ligne PAR TOITURE (y compris la NON calepinée)', async () => {
        mocks.get.mockResolvedValue({ data: { ...AFFAIRE, synthese_calepinage: SYNTHESE } })
        mocks.toituresList.mockResolvedValue({ data: [{ id: 42, nom: 'Toiture 05H' }] })
        renderScreen()
        await screen.findAllByText('AO-2026-001')
        await userEvent.click(onglet('Calepinages'))

        const bloc = await screen.findByLabelText('Toiture').then(
          () => document.querySelector('[data-ao-synthese-calepinage]'),
        )
        expect(bloc, 'bloc de synthèse absent').not.toBeNull()
        const zone = within(bloc)
        expect(zone.getByText('350')).toBeInTheDocument() // total_modules
        expect(zone.getByText('218 kWc')).toBeInTheDocument() // total_kwc
        expect(zone.getByText('2 / 3')).toBeInTheDocument() // toitures_calepinees / total
        expect(zone.getByText('C — 05H')).toBeInTheDocument()
        expect(zone.getByText('C — 06H')).toBeInTheDocument()
        expect(zone.getByText('D — 07H')).toBeInTheDocument()
        expect(zone.getByText('200 modules · 125 kWc')).toBeInTheDocument()
        // La toiture NON calepinée le DIT — jamais une ligne muette.
        expect(zone.getByText('Pas encore calepinée')).toBeInTheDocument()
      })

      it('null-safe : sans `synthese_calepinage`, le bloc de synthèse n’apparaît PAS (jamais un bloc à zéros)', async () => {
        mocks.toituresList.mockResolvedValue({ data: [{ id: 42, nom: 'Toiture 05H' }] })
        renderScreen()
        await screen.findAllByText('AO-2026-001')
        await userEvent.click(onglet('Calepinages'))

        await screen.findByLabelText('Toiture')
        expect(document.querySelector('[data-ao-synthese-calepinage]')).toBeNull()
      })
    })

    it('« Dossier » monte le VRAI DossierPage avec l’id du DOSSIER, jamais celui de l’affaire (piège useParams)', async () => {
      renderScreen()
      await screen.findAllByText('AO-2026-001')
      await userEvent.click(onglet('Dossier'))

      await waitFor(() => expect(mocks.dossiersList).toHaveBeenCalledWith({ appel_offre: '1' }))
      // DossierPage retombe sur `useParams().id` (= l'affaire) sans `dossierId`
      // explicite : il chargerait alors un dossier au hasard sous le titre de
      // cette affaire. On exige l'id du dossier, et JAMAIS celui de l'affaire.
      await waitFor(() => expect(mocks.dossierGet).toHaveBeenCalledWith(77), { timeout: 15000 })
      expect(mocks.dossierGet).not.toHaveBeenCalledWith('1')
      expect(await screen.findByRole('heading', { name: /Dossier de soumission/ })).toBeInTheDocument()
    })

    /* Les 3 emplacements de `DossierPage` (contrôles avant dépôt, ZIP,
       échéances) restaient VIDES aux deux points de montage : les panneaux
       AOF176/177/178 existaient sur le disque, importés par personne. */
    it('« Dossier » affiche les contrôles avant dépôt, le ZIP et les échéances — avec la date limite de l’AFFAIRE', async () => {
      renderScreen()
      await screen.findAllByText('AO-2026-001')
      await userEvent.click(onglet('Dossier'))

      // Les contrôles portent sur le DOSSIER (77), jamais sur l'affaire (1).
      await waitFor(
        () => expect(mocks.controlesAvantDepot).toHaveBeenCalledWith(77),
        { timeout: 15000 },
      )
      expect(await screen.findByRole('heading', { name: 'Contrôles avant dépôt' })).toBeInTheDocument()
      expect(screen.getAllByRole('button', { name: /Constituer le ZIP de dépôt/ })[0]).toBeInTheDocument()
      // `DossierAOSerializer` ne publie aucune date limite : elle vient de
      // l'affaire, passée explicitement par l'onglet.
      expect(screen.getAllByText('Date limite de remise des plis').length).toBeGreaterThan(0)
      expect(screen.getAllByText('15/09/2026').length).toBeGreaterThan(0)
      expect(codeSeul).toMatch(/<DossierPage\s+dossierId=\{courant\}\s+dateLimite=\{dateLimite\}/)
    })

    it('« Dossier » affiche un état vide motivé quand l’affaire n’a aucun dossier (et ne monte rien)', async () => {
      mocks.dossiersList.mockResolvedValue({ data: [] })
      renderScreen()
      await screen.findAllByText('AO-2026-001')
      await userEvent.click(onglet('Dossier'))

      expect((await screen.findAllByText('Aucun dossier de soumission')).length).toBeGreaterThan(0)
      expect(screen.getAllByText(/pas encore de dossier de dépôt/).length).toBeGreaterThan(0)
      expect(mocks.dossierGet).not.toHaveBeenCalled()
    })

    // PACT69 — `aoApi.bordereaux` est désormais PUBLIÉ : l'onglet monte le
    // VRAI `BordereauAffairePanel`, qui interroge le serveur au lieu d'un
    // motif d'indisponibilité figé.
    it('« Bordereau » monte le VRAI BordereauAffairePanel, filtré sur CETTE affaire', async () => {
      renderScreen()
      await screen.findAllByText('AO-2026-001')
      await userEvent.click(onglet('Bordereau'))

      await waitFor(
        () => expect(mocks.bordereauxList).toHaveBeenCalledWith({ appel_offre: '1' }),
        { timeout: 15000 },
      )
      // Aucun bordereau pour cette affaire (mock par défaut) : état vide
      // HONNÊTE, propre à `BordereauAffairePanel` — jamais un motif figé.
      expect((await screen.findAllByText('Aucun bordereau des prix')).length).toBeGreaterThan(0)
    })

    // 03/08/2026 — CE TEST A CHANGÉ DE SENS, volontairement. Il épinglait
    // l'état vide affiché tant que `ToituresPage` n'acceptait aucun filtre.
    // L'empêchement a été levé à la source (propriété `affaireId`), donc le
    // vrai panneau est monté. La propriété à garder n'est PAS « un état vide
    // s'affiche » — c'est « les toitures d'une AUTRE affaire ne fuitent
    // jamais ici », qui est la seule chose qui protégeait l'utilisateur.
    it('« Toitures & relevés » monte le vrai panneau, filtré sur CETTE affaire (aucune fuite)', async () => {
      renderScreen()
      await screen.findAllByText('AO-2026-001')
      await userEvent.click(onglet('Toitures & relevés'))

      // Le panneau interroge les toitures AVEC le filtre de CETTE affaire
      // (l'id vient de l'URL, donc '1' — jamais celui d'un sous-document).
      await waitFor(() => expect(mocks.toituresList).toHaveBeenCalled(), { timeout: 15000 })
      const filtre = mocks.toituresList.mock.calls[0][0]
      expect(String(filtre.appel_offre)).toBe('1')
      // …et l'onglet ne liste JAMAIS les autres affaires : c'était la fuite
      // d'origine — l'écran retombait sur la PREMIÈRE affaire de la société.
      expect(mocks.affairesList).not.toHaveBeenCalled()
    })
  })

  /* ══ SECONDE VAGUE 03/08/2026 — les 3 derniers écrans que rien n'atteignait ══
     `AdministratifPage`, `EquipementsPage` et `ExigencesPage` étaient importés
     NULLE PART : ni route, ni onglet. Chaque test ci-dessous épingle le panneau
     RÉEL et, surtout, le NOM DU FILTRE SERVEUR — c'est là que se cache le
     défaut silencieux (un filtre inconnu est ignoré, jamais refusé). */
  describe('les 3 onglets ajoutés', () => {
    it('« Administratif » monte le VRAI panneau avec un affaireId EXPLICITE', async () => {
      renderScreen()
      await screen.findAllByText('AO-2026-001')
      await userEvent.click(onglet('Administratif'))

      expect(await screen.findByRole('heading', { name: 'Administratif' }, { timeout: 15000 }))
        .toBeInTheDocument()
      // Titre + états vides propres à AdministratifPage (aucun placeholder).
      expect(screen.getAllByText('Aucune pièce administrative').length).toBeGreaterThan(0)
      // La propriété est passée explicitement, jamais laissée au repli
      // `useParams()` interne (juste ici par pure coïncidence de nommage).
      expect(codeSeul).toMatch(/<AdministratifPage\s+affaireId=\{id\}/)
    })

    it('« Équipements » monte le VRAI panneau, filtré sur appel_offre (jamais toute la société)', async () => {
      mocks.equipementsList.mockResolvedValue({
        data: [{ id: 3, role: 'onduleur', designation: 'Onduleur 60 kW', marque: 'Deye' }],
      })
      renderScreen()
      await screen.findAllByText('AO-2026-001')
      await userEvent.click(onglet('Équipements'))

      await waitFor(
        () => expect(mocks.equipementsList).toHaveBeenCalledWith({ appel_offre: '1' }),
        { timeout: 15000 },
      )
      expect(await screen.findByRole('heading', { name: 'Équipements retenus' })).toBeInTheDocument()
      expect(screen.getAllByText('Onduleur 60 kW').length).toBeGreaterThan(0)
      // Signature déclarée par le panneau : `({ affaireId })`.
      expect(codeSeul).toMatch(/<EquipementsPage\s+affaireId=\{id\}/)
    })

    it('« Équipements » affiche un état vide EXPLICITE quand l’affaire n’en a aucun', async () => {
      renderScreen()
      await screen.findAllByText('AO-2026-001')
      await userEvent.click(onglet('Équipements'))

      expect((await screen.findAllByText('Aucun équipement retenu', {}, { timeout: 15000 })).length)
        .toBeGreaterThan(0)
    })

    it('« CPS & exigences » filtre sur appel_offre — JAMAIS `affaire`, que le serveur ignore', async () => {
      mocks.exigencesList.mockResolvedValue({
        data: [{ id: 8, code: 'DCAC', libelle: 'Ratio DC/AC admissible', bloquant: true }],
      })
      renderScreen()
      await screen.findAllByText('AO-2026-001')
      await userEvent.click(onglet('CPS & exigences'))

      // LE point de la réparation : `ExigenceCPSViewSet.get_queryset` n'honore
      // que ('appel_offre', 'type_exigence', 'bloquant', 'a_reverifier',
      // 'piece_consultation'). `affaire` était ignoré EN SILENCE → les clauses
      // de toutes les affaires de la société sous le titre d'une seule.
      await waitFor(
        () => expect(mocks.exigencesList).toHaveBeenCalledWith({ appel_offre: '1' }),
        { timeout: 15000 },
      )
      for (const appel of mocks.exigencesList.mock.calls) {
        expect(appel[0]).not.toHaveProperty('affaire')
      }
      expect(await screen.findByRole('heading', { name: 'CPS & exigences' })).toBeInTheDocument()
      expect(screen.getAllByText('Ratio DC/AC admissible').length).toBeGreaterThan(0)
    })
  })

  /* ══ 11ᵉ onglet — le comparateur de variantes était monté NULLE PART ══════
     `VariantesCompare` et `VarianteColonne` existaient, testés, sans aucune
     route ni aucun onglet pour les atteindre. */
  describe('l’onglet « Variantes »', () => {
    const variante = (id, nom, compte) => ({
      id, nom, statut: 'calculee', est_retenue: false,
      technique: { compte_modules: compte, puissance_kwc: compte * 0.55, kits: [], allee_m: 1.2 },
      conformite: {},
    })

    it('monte le VRAI comparateur, filtré sur appel_offre (jamais toute la société)', async () => {
      mocks.variantesList.mockResolvedValue({
        data: [variante(11, 'Portrait 4 rangées', 314), variante(12, 'Paysage 5 rangées', 296)],
      })
      renderScreen()
      await screen.findAllByText('AO-2026-001')
      await userEvent.click(onglet('Variantes'))

      // `affaire` serait IGNORÉ en silence par `VarianteCalepinageViewSet`.
      await waitFor(
        () => expect(mocks.variantesList).toHaveBeenCalledWith({ appel_offre: '1' }),
        { timeout: 15000 },
      )
      for (const appel of mocks.variantesList.mock.calls) {
        expect(appel[0]).not.toHaveProperty('affaire')
      }
      expect(await screen.findByRole('heading', { name: 'Comparer les variantes' })).toBeInTheDocument()
      // Les colonnes réelles (`VarianteColonne`) et leur bande CONFORMITÉ AO.
      expect(screen.getAllByText('Conformité AO').length).toBeGreaterThan(0)
      expect(screen.getByRole('region', { name: 'Variante Portrait 4 rangées' })).toBeInTheDocument()
      expect(codeSeul).toMatch(/<VariantesCompare\s+affaireId=\{id\}/)
    })

    it('affiche un état vide MOTIVÉ quand l’affaire n’a pas assez de variantes', async () => {
      renderScreen()
      await screen.findAllByText('AO-2026-001')
      await userEvent.click(onglet('Variantes'))

      expect((await screen.findAllByText('Pas assez de variantes à comparer', {}, { timeout: 15000 })).length)
        .toBeGreaterThan(0)
      expect(screen.getAllByText(/au moins 2 variantes calculées/).length).toBeGreaterThan(0)
    })
  })

  /* ══ 12ᵉ onglet — PACT70 : cautions, échéances, résultat étaient sans écran ══
     Le tableau de bord AGRÈGE ces trois ressources sans qu'aucun écran ne
     permette d'en créer une seule. */
  describe('l’onglet « Suivi administratif »', () => {
    it('monte le VRAI SuiviAdministratifAO, filtré sur CETTE affaire pour les trois ressources', async () => {
      renderScreen()
      await screen.findAllByText('AO-2026-001')
      await userEvent.click(onglet('Suivi administratif'))

      await waitFor(
        () => expect(mocks.cautionsList).toHaveBeenCalledWith({ appel_offre: '1' }),
        { timeout: 15000 },
      )
      expect(mocks.echeancesAoList).toHaveBeenCalledWith({ appel_offre: '1' })
      expect(mocks.resultatsAoList).toHaveBeenCalledWith({ appel_offre: '1' })
      expect(await screen.findByRole('heading', { name: 'Suivi administratif' })).toBeInTheDocument()
      expect(screen.getByRole('heading', { name: 'Cautions' })).toBeInTheDocument()
      expect(screen.getByRole('heading', { name: 'Échéances' })).toBeInTheDocument()
      expect(screen.getByRole('heading', { name: 'Résultat (ouverture des plis)' })).toBeInTheDocument()
    })
  })

  /* ══ 13ᵉ onglet — PACT74 : le DCE reçu de l'acheteur n'était stocké nulle part ══ */
  describe('l’onglet « Pièces du DCE »', () => {
    it('monte le VRAI PiecesConsultation, filtré sur CETTE affaire', async () => {
      renderScreen()
      await screen.findAllByText('AO-2026-001')
      await userEvent.click(onglet('Pièces du DCE'))

      await waitFor(
        () => expect(mocks.piecesConsultationList).toHaveBeenCalledWith({ appel_offre: '1' }),
        { timeout: 15000 },
      )
      expect(await screen.findByRole('heading', { name: 'Pièces du dossier de consultation' })).toBeInTheDocument()
    })
  })

  describe('gardes de structure', () => {
    it('plus AUCUN TabPlaceholder ne subsiste dans la fiche', () => {
      expect(codeSeul).not.toMatch(/TabPlaceholder/)
      expect(codeSeul).not.toMatch(/Écran dédié en construction/)
      // Les 5 onglets réparés ne rendent plus un composant local muet : ils
      // montent un panneau lazy ou un état vide MOTIVÉ (testés plus haut).
      expect(codeSeul).not.toMatch(/lane distincte du Groupe AOF/)
    })

    it('les panneaux réels sont chargés PARESSEUSEMENT (lazy + import dynamique), jamais en import statique', () => {
      for (const chemin of [
        './toiture/ToituresPage',
        './calepinage/CalepinageStudio',
        './bordereau/BordereauAffairePanel',
        './dossier/DossierPage',
        './questions/SeriesPage',
        './administratif/AdministratifPage',
        './equipements/EquipementsPage',
        './cps/ExigencesPage',
        './variantes/VariantesCompare',
        './SuiviAdministratifAO',
        './PiecesConsultation',
      ]) {
        // lazy(() => import('<chemin>')…
        expect(codeSeul).toMatch(
          new RegExp(`lazy\\(\\s*\\(\\)\\s*=>\\s*import\\('${chemin.replace(/[./]/g, '\\$&')}'\\)`),
        )
        // …et surtout AUCUN import statique du même panneau (il repasserait
        // dans le bundle de la fiche, soit ~60 écrans au premier rendu).
        expect(codeSeul).not.toMatch(
          new RegExp(`^import\\s+[^\\n]*from\\s+'${chemin.replace(/[./]/g, '\\$&')}'`, 'm'),
        )
      }
    })

    it('chaque panneau différé est rendu derrière une frontière Suspense à repli squelette', () => {
      expect(codeSeul).toMatch(/<Suspense fallback=\{<Skeleton/)
      // Autant de montages de panneau différé que de panneaux lazy déclarés.
      const lazyDeclares = codeSeul.match(/=\s*lazy\(/g) || []
      const montages = codeSeul.match(/<PanneauDiffere>/g) || []
      // 5 panneaux de la 1re vague + 3 de la 2de (Administratif, Équipements,
      // CPS & exigences) + le comparateur de variantes + les 2 de la vague §E
      // (Suivi administratif PACT70, Pièces du DCE PACT74) — l'ÉGALITÉ est la
      // garde : un panneau déclaré `lazy` et monté hors Suspense ferait
      // planter la fiche entière.
      expect(lazyDeclares.length).toBe(11)
      expect(montages.length).toBe(lazyDeclares.length)
    })

    it('l’onglet Rentabilité n’apparaît dans AUCUN rendu, onglet par onglet', async () => {
      renderScreen()
      await screen.findAllByText('AO-2026-001')
      // Les 10 onglets, y compris les 3 ajoutés le 03/08/2026 : un panneau
      // nouvellement branché ne doit pas ramener l'économie du dossier par la
      // fenêtre. Chaque panneau est DIFFÉRÉ, d'où l'attente explicite.
      for (const label of ONGLETS) {
        await userEvent.click(onglet(label))
        await waitFor(
          () => expect(document.querySelector('[data-ao-panneau-differe]')).toBeNull(),
          { timeout: 15000 },
        )
        expect(screen.queryByRole('tab', { name: /rentabilit/i })).toBeNull()
        expect(screen.queryByText(/rentabilit/i)).toBeNull()
      }
      // Et AUCUN chemin réseau vers l'économie n'existe dans le code de la
      // fiche (en-tête du groupe : réservée au Directeur, route séparée) —
      // `aoRentabiliteApi` est un export SÉPARÉ d'`aoApi`, jamais importé ici.
      expect(codeSeul).not.toMatch(/aoRentabiliteApi/)
      expect(codeSeul).not.toMatch(/rentabilite/i)
    })
  })
})
