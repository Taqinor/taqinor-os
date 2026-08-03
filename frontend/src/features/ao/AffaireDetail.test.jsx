import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
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
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useParams: () => ({ id: '1' }) }
})

vi.mock('../../api/aoApi', () => ({
  default: {
    affaires: { get: mocks.get, list: mocks.affairesList },
    // Ce que le serveur persiste réellement pour un calepinage (AOF28).
    toitures: { list: mocks.toituresList, create: mocks.toituresCreate },
    // Le panneau Toitures ouvre le wizard de création : une toiture se
    // rattache à un BÂTIMENT (ToitureAO n'a aucune FK vers l'affaire).
    batiments: { list: mocks.batimentsList },
    variantes: { list: mocks.variantesList },
    dossiers: { list: mocks.dossiersList, get: mocks.dossierGet, genererPiece: mocks.genererPiece },
    seriesQR: { list: mocks.seriesList, create: mocks.seriesCreate },
    calepinages: { get: mocks.calepinageGet, calculer: mocks.calepinageCalculer },
    equipements: { list: mocks.equipementsList, bascule: vi.fn() },
    exigencesCps: { list: mocks.exigencesList, create: mocks.exigencesCreate },
  },
}))

// L'aperçu du CPS (AOF175) importe pdfjs : hors sujet ici, on prouve seulement
// que l'onglet monte le VRAI ExigencesPage (même bouchon que son propre test).
vi.mock('./dossier/PiecePreview', () => ({
  default: ({ piece }) => <div data-testid="apercu-cps">{piece ? piece.libelle : 'aucune pièce'}</div>,
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
})

// Les 10 onglets de la fiche, dans leur ordre RÉEL : les 7 d'origine, puis les
// 3 ajoutés le 03/08/2026 — l'ordre des 7 premiers ne bouge jamais.
const ONGLETS = [
  'Synthèse', 'Toitures & relevés', 'Calepinages', 'Bordereau',
  'Dossier', 'Questions terrain', 'Historique',
  'Administratif', 'Équipements', 'CPS & exigences',
]

describe('AffaireDetail', () => {
  it('charge la fiche via aoApi.affaires.get(id) et affiche référence/objet/statut', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith('1'))
    expect(await screen.findByText('AO-2026-001')).toBeInTheDocument()
    expect(screen.getByText('Centrale solaire école')).toBeInTheDocument()
    expect(screen.getByText('Déposé')).toBeInTheDocument()
  })

  it('affiche les 7 onglets attendus (Synthèse, Toitures & relevés, Calepinages, Bordereau, Dossier, Questions terrain, Historique)', async () => {
    renderScreen()
    await screen.findByText('AO-2026-001')
    for (const label of [
      'Synthèse', 'Toitures & relevés', 'Calepinages', 'Bordereau',
      'Dossier', 'Questions terrain', 'Historique',
    ]) {
      expect(screen.getByRole('tab', { name: label })).toBeInTheDocument()
    }
  })

  it('ajoute les 3 onglets du 03/08/2026 APRÈS les 7, sans toucher à leur ordre', async () => {
    renderScreen()
    await screen.findByText('AO-2026-001')
    for (const label of ['Administratif', 'Équipements', 'CPS & exigences']) {
      expect(screen.getByRole('tab', { name: label })).toBeInTheDocument()
    }
    // L'ordre RENDU est l'ordre déclaré : les 7 d'origine d'abord, intacts.
    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual(ONGLETS)
  })

  it('n’a JAMAIS un onglet ou un mot « rentabilité » dans l’arbre (route séparée AOF161)', async () => {
    renderScreen()
    await screen.findByText('AO-2026-001')
    expect(screen.queryByText(/rentabilit/i)).toBeNull()
    expect(screen.queryByRole('tab', { name: /rentabilit/i })).toBeNull()
  })

  it('le bandeau de verdict affiche verdict/échéance/complétude issus tels quels de l’affaire (aucun calcul de KPI)', async () => {
    renderScreen()
    await screen.findByText('AO-2026-001')
    expect(screen.getByText('Confirmé')).toBeInTheDocument()
    expect(screen.getByText('Remise des plis')).toBeInTheDocument()
    expect(screen.getByText('62 %')).toBeInTheDocument()
  })

  it('le bandeau retombe sur « — » quand un champ agrégé est absent (jamais un calcul de substitution)', async () => {
    mocks.get.mockResolvedValue({
      data: { ...AFFAIRE, verdict_global: null, verdict_global_label: null, dossier_completude: null, resultat_issue_display: null },
    })
    renderScreen()
    await screen.findByText('AO-2026-001')
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
  })

  it('le chatter (ChatterTimeline, cible ao.appeloffre) affiche les notes de records', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.getComments).toHaveBeenCalledWith('ao.appeloffre', '1'))
    expect(await screen.findAllByText(/Visite de site effectuée/)).not.toHaveLength(0)
  })

  it('ajouter une note appelle recordsApi.createComment(ao.appeloffre, id, texte) et vide le champ', async () => {
    renderScreen()
    await screen.findByText('AO-2026-001')
    const textarea = screen.getByLabelText('Nouvelle note')
    fireEvent.change(textarea, { target: { value: 'Nouvelle observation terrain.' } })
    fireEvent.click(screen.getByRole('button', { name: /Noter/i }))
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
      await screen.findByText('AO-2026-001')
      await userEvent.click(onglet('Questions terrain'))

      // Le filtre serveur s'appelle `appel_offre` — `affaire` serait ignoré en
      // silence (liste de toute la société avec l'air d'être filtrée).
      await waitFor(() => expect(mocks.seriesList).toHaveBeenCalledWith({ appel_offre: '1' }))
      // Titre propre à SeriesPage (jamais rendu par un placeholder).
      expect(await screen.findByRole('heading', { name: 'Questions terrain' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Nouvelle série/ })).toBeInTheDocument()
    })

    // CONTRAT CORRIGÉ 03/08/2026 : l'atelier pilote une TOITURE, pas une
    // variante. L'onglet et l'atelier avaient été écrits en parallèle et ne se
    // parlaient pas — l'atelier recevait `undefined`. Ces tests épinglent
    // désormais le contrat RÉEL, des deux côtés.
    it('« Calepinages » liste les TOITURES de l’affaire et monte le VRAI atelier', async () => {
      mocks.toituresList.mockResolvedValue({ data: [{ id: 42, nom: 'Toiture bâtiment C' }] })
      renderScreen()
      await screen.findByText('AO-2026-001')
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
      await screen.findByText('AO-2026-001')
      await userEvent.click(onglet('Calepinages'))

      expect(await screen.findByText('Aucune toiture à calepiner')).toBeInTheDocument()
      expect(screen.getByText(/se calcule SUR une toiture/)).toBeInTheDocument()
    })

    it('« Dossier » monte le VRAI DossierPage avec l’id du DOSSIER, jamais celui de l’affaire (piège useParams)', async () => {
      renderScreen()
      await screen.findByText('AO-2026-001')
      await userEvent.click(onglet('Dossier'))

      await waitFor(() => expect(mocks.dossiersList).toHaveBeenCalledWith({ appel_offre: '1' }))
      // DossierPage retombe sur `useParams().id` (= l'affaire) sans `dossierId`
      // explicite : il chargerait alors un dossier au hasard sous le titre de
      // cette affaire. On exige l'id du dossier, et JAMAIS celui de l'affaire.
      await waitFor(() => expect(mocks.dossierGet).toHaveBeenCalledWith(77), { timeout: 15000 })
      expect(mocks.dossierGet).not.toHaveBeenCalledWith('1')
      expect(await screen.findByRole('heading', { name: /Dossier de soumission/ })).toBeInTheDocument()
    })

    it('« Dossier » affiche un état vide motivé quand l’affaire n’a aucun dossier (et ne monte rien)', async () => {
      mocks.dossiersList.mockResolvedValue({ data: [] })
      renderScreen()
      await screen.findByText('AO-2026-001')
      await userEvent.click(onglet('Dossier'))

      expect(await screen.findByText('Aucun dossier de soumission')).toBeInTheDocument()
      expect(screen.getByText(/pas encore de dossier de dépôt/)).toBeInTheDocument()
      expect(mocks.dossierGet).not.toHaveBeenCalled()
    })

    it('« Bordereau » monte le VRAI BordereauPage, qui NOMME son motif d’indisponibilité', async () => {
      renderScreen()
      await screen.findByText('AO-2026-001')
      await userEvent.click(onglet('Bordereau'))

      // Titre d'état vide propre à BordereauPage (aucun placeholder ne le rend).
      expect(await screen.findByText('Bordereau indisponible', {}, { timeout: 15000 })).toBeInTheDocument()
      // Le motif est EXPLICITE (client API sans ressource bordereau), pas un
      // « écran en construction » muet.
      expect(screen.getByText(/ne publie pas encore de ressource bordereau/)).toBeInTheDocument()
    })

    // 03/08/2026 — CE TEST A CHANGÉ DE SENS, volontairement. Il épinglait
    // l'état vide affiché tant que `ToituresPage` n'acceptait aucun filtre.
    // L'empêchement a été levé à la source (propriété `affaireId`), donc le
    // vrai panneau est monté. La propriété à garder n'est PAS « un état vide
    // s'affiche » — c'est « les toitures d'une AUTRE affaire ne fuitent
    // jamais ici », qui est la seule chose qui protégeait l'utilisateur.
    it('« Toitures & relevés » monte le vrai panneau, filtré sur CETTE affaire (aucune fuite)', async () => {
      renderScreen()
      await screen.findByText('AO-2026-001')
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
      await screen.findByText('AO-2026-001')
      await userEvent.click(onglet('Administratif'))

      expect(await screen.findByRole('heading', { name: 'Administratif' }, { timeout: 15000 }))
        .toBeInTheDocument()
      // Titre + états vides propres à AdministratifPage (aucun placeholder).
      expect(screen.getByText('Aucune pièce administrative')).toBeInTheDocument()
      // La propriété est passée explicitement, jamais laissée au repli
      // `useParams()` interne (juste ici par pure coïncidence de nommage).
      expect(codeSeul).toMatch(/<AdministratifPage\s+affaireId=\{id\}/)
    })

    it('« Équipements » monte le VRAI panneau, filtré sur appel_offre (jamais toute la société)', async () => {
      mocks.equipementsList.mockResolvedValue({
        data: [{ id: 3, role: 'onduleur', designation: 'Onduleur 60 kW', marque: 'Deye' }],
      })
      renderScreen()
      await screen.findByText('AO-2026-001')
      await userEvent.click(onglet('Équipements'))

      await waitFor(
        () => expect(mocks.equipementsList).toHaveBeenCalledWith({ appel_offre: '1' }),
        { timeout: 15000 },
      )
      expect(await screen.findByRole('heading', { name: 'Équipements retenus' })).toBeInTheDocument()
      expect(screen.getByText('Onduleur 60 kW')).toBeInTheDocument()
      // Signature déclarée par le panneau : `({ affaireId })`.
      expect(codeSeul).toMatch(/<EquipementsPage\s+affaireId=\{id\}/)
    })

    it('« Équipements » affiche un état vide EXPLICITE quand l’affaire n’en a aucun', async () => {
      renderScreen()
      await screen.findByText('AO-2026-001')
      await userEvent.click(onglet('Équipements'))

      expect(await screen.findByText('Aucun équipement retenu', {}, { timeout: 15000 }))
        .toBeInTheDocument()
    })

    it('« CPS & exigences » filtre sur appel_offre — JAMAIS `affaire`, que le serveur ignore', async () => {
      mocks.exigencesList.mockResolvedValue({
        data: [{ id: 8, code: 'DCAC', libelle: 'Ratio DC/AC admissible', bloquant: true }],
      })
      renderScreen()
      await screen.findByText('AO-2026-001')
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
      expect(screen.getByText('Ratio DC/AC admissible')).toBeInTheDocument()
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
        './bordereau/BordereauPage',
        './dossier/DossierPage',
        './questions/SeriesPage',
        './administratif/AdministratifPage',
        './equipements/EquipementsPage',
        './cps/ExigencesPage',
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
      // CPS & exigences) — l'ÉGALITÉ est la garde : un panneau déclaré `lazy`
      // et monté hors Suspense ferait planter la fiche entière.
      expect(lazyDeclares.length).toBe(8)
      expect(montages.length).toBe(lazyDeclares.length)
    })

    it('l’onglet Rentabilité n’apparaît dans AUCUN rendu, onglet par onglet', async () => {
      renderScreen()
      await screen.findByText('AO-2026-001')
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
