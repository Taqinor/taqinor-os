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
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useParams: () => ({ id: '1' }) }
})

vi.mock('../../api/aoApi', () => ({
  default: {
    affaires: { get: mocks.get, list: mocks.affairesList },
    // Ce que le serveur persiste réellement pour un calepinage (AOF28).
    toitures: { list: mocks.toituresList },
    variantes: { list: mocks.variantesList },
    dossiers: { list: mocks.dossiersList, get: mocks.dossierGet, genererPiece: mocks.genererPiece },
    seriesQR: { list: mocks.seriesList, create: mocks.seriesCreate },
    calepinages: { get: mocks.calepinageGet, calculer: mocks.calepinageCalculer },
  },
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
})

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

    it('« Calepinages » liste les variantes de l’affaire et monte le VRAI CalepinageStudio', async () => {
      renderScreen()
      await screen.findByText('AO-2026-001')
      await userEvent.click(onglet('Calepinages'))

      await waitFor(() => expect(mocks.variantesList).toHaveBeenCalledWith({ appel_offre: '1' }))
      // Le studio prend l'id d'un CALEPINAGE (la variante 42), jamais celui
      // de l'affaire (1) — c'est tout le sens du sélecteur.
      await waitFor(() => expect(mocks.calepinageGet).toHaveBeenCalledWith(42))
      expect(mocks.calepinageGet).not.toHaveBeenCalledWith('1')
      expect(await screen.findByRole('heading', { name: 'Atelier de calepinage' })).toBeInTheDocument()
      expect(screen.getByLabelText('Calepinage')).toBeInTheDocument()
    })

    it('« Calepinages » affiche un état vide qui DIT qu’aucun calepinage n’existe (jamais un écran blanc)', async () => {
      mocks.variantesList.mockResolvedValue({ data: [] })
      renderScreen()
      await screen.findByText('AO-2026-001')
      await userEvent.click(onglet('Calepinages'))

      expect(await screen.findByText('Aucun calepinage pour cette affaire')).toBeInTheDocument()
      expect(screen.getByText(/n’a encore été calculée/)).toBeInTheDocument()
      // Aucun id inventé n'est envoyé à l'atelier quand il n'y a rien à ouvrir.
      expect(mocks.calepinageGet).not.toHaveBeenCalled()
    })

    it('« Dossier » monte le VRAI DossierPage avec l’id du DOSSIER, jamais celui de l’affaire (piège useParams)', async () => {
      renderScreen()
      await screen.findByText('AO-2026-001')
      await userEvent.click(onglet('Dossier'))

      await waitFor(() => expect(mocks.dossiersList).toHaveBeenCalledWith({ appel_offre: '1' }))
      // DossierPage retombe sur `useParams().id` (= l'affaire) sans `dossierId`
      // explicite : il chargerait alors un dossier au hasard sous le titre de
      // cette affaire. On exige l'id du dossier, et JAMAIS celui de l'affaire.
      await waitFor(() => expect(mocks.dossierGet).toHaveBeenCalledWith(77))
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
      expect(await screen.findByText('Bordereau indisponible')).toBeInTheDocument()
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
      await waitFor(() => expect(mocks.toituresList).toHaveBeenCalled())
      const filtre = mocks.toituresList.mock.calls[0][0]
      expect(String(filtre.appel_offre)).toBe('1')
      // …et l'onglet ne liste JAMAIS les autres affaires : c'était la fuite
      // d'origine — l'écran retombait sur la PREMIÈRE affaire de la société.
      expect(mocks.affairesList).not.toHaveBeenCalled()
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

    it('les 4 panneaux réels sont chargés PARESSEUSEMENT (lazy + import dynamique), jamais en import statique', () => {
      for (const chemin of [
        './toiture/ToituresPage',
        './calepinage/CalepinageStudio',
        './bordereau/BordereauPage',
        './dossier/DossierPage',
        './questions/SeriesPage',
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
      expect(lazyDeclares.length).toBe(5)
      expect(montages.length).toBe(lazyDeclares.length)
    })

    it('l’onglet Rentabilité n’apparaît dans AUCUN rendu, onglet par onglet', async () => {
      renderScreen()
      await screen.findByText('AO-2026-001')
      for (const label of [
        'Synthèse', 'Toitures & relevés', 'Calepinages', 'Bordereau',
        'Dossier', 'Questions terrain', 'Historique',
      ]) {
        await userEvent.click(onglet(label))
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
