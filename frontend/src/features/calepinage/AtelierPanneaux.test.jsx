import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { feuilleAuDoigt } from './__tests__/feuilleAuDoigt'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   CAL37 — l'emplacement des panneaux de l'atelier en mode calepinage.

   Ce que ce fichier prouve :
   1. le panneau affiche la CIBLE servie par le serveur, et « non renseignée »
      quand elle vaut `null` — jamais une puissance inventée ;
   2. une conception en LECTURE SEULE ne propose aucune écriture ;
   3. ACAL42 — le bandeau de lecture seule affiche le motif du SERVEUR
      (`raison_lecture_seule`) ; « Déverrouiller » n'existe plus, le seul geste
      est « Réviser (v2) » de `BoutonDevis`.

   SOLMVP15 — les deux essais du bouton « Reprendre le contour de l'affaire »
   (CAL242, sens CAL240) sont partis avec lui : son endpoint n'existe plus,
   l'app d'appels d'offres sortant du produit.
   ========================================================================== */

/* CALX27 — le droit est PILOTÉ par le test : `AtelierPanneaux` lit désormais
   `calepinage_gerer` (le code EXACT de la garde serveur). Sans ce double, le
   hook irait chercher le store redux, qu'aucun de ces rendus ne monte. */
const mocks = vi.hoisted(() => ({ hasPermission: vi.fn(() => false) }))
vi.mock('../../hooks/useHasPermission', () => ({
  useHasPermission: (code) => mocks.hasPermission(code),
}))

vi.mock('../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      get: vi.fn(),
      genererDevis: vi.fn(),
      syncDevis: vi.fn(),
      modulesDisponibles: vi.fn(() => Promise.resolve({ data: {} })), // ACAL867 — le rail monte l'étape Toit
    },
    // CAL70 — PanneauAllees (monté ici, emplacement CAL37) lit les réglages
    // société et interroge le moteur ; sans double par défaut, la promesse
    // non résolue laisse `.get`/`.calculer` undefined et casse CE fichier.
    parametres: { get: vi.fn().mockResolvedValue({ data: { degagements: {} } }) },
    moteur: { calculer: vi.fn() },
  },
}))
vi.mock('../../api/crmApi', () => ({
  default: { getRoofFootprint: vi.fn(), lancerRechercheEmprise: vi.fn(), getRechercheEmprise: vi.fn() },
}))
vi.mock('../../api/ventesApi', () => ({ default: { reviserDevis: vi.fn() } }))

import calepinageApi from '../../api/calepinageApi'
import crmApi from '../../api/crmApi'
import { fireEvent } from '@testing-library/react'
import AtelierPanneaux from './AtelierPanneaux'
import { conceptionAuto, contourLngLat } from './atelier/conceptionAuto'

const CTX = exempleContrat('calepinage', 'calepinage_design_context')
const CTX_VIDE = exempleContrat('calepinage', 'calepinage_design_context',
  'exemple_vide')
const DETAIL = exempleContrat('calepinage', 'calepinage_detail')

const rendre = (props = {}) => render(
  <MemoryRouter>
    <AtelierPanneaux calepinageId={CTX.calepinage.id} contexte={CTX} {...props} />
  </MemoryRouter>,
)

beforeEach(() => {
  vi.clearAllMocks()
  calepinageApi.calepinages.get.mockResolvedValue({ data: DETAIL })
  // Par défaut : SANS le droit de gérer — l'affordance d'écriture est l'exception.
  mocks.hasPermission.mockReturnValue(false)
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('AtelierPanneaux (CAL37)', () => {
  it('affiche la cible SERVIE et le lien contextuel vers le comparatif', async () => {
    rendre()

    expect(screen.getByTestId('cal-cible-panneaux'))
      .toHaveTextContent(String(CTX.cible.panneaux))
    expect(screen.getByTestId('cal-lien-variantes'))
      .toHaveAttribute('href', `/calepinage/${CTX.calepinage.id}?onglet=variantes`)
  })

  // ACAL1746 — « Factures du lead » et « Brouillon » se chevauchaient dans la colonne de ~340 px (4 colonnes fixes dès sm).
  it('ACAL1746 — les quatre chiffres de la cible suivent la largeur de la colonne, jamais un point de rupture de la fenêtre', () => {
    rendre()
    const grille = screen.getByTestId('cal-cible-panneaux').closest('dl')
    expect(grille.className).toContain('grid-cols-[repeat(auto-fit,minmax(7rem,1fr))]')
    expect(grille.className).not.toMatch(/(?:^|\s)(?:sm|md|lg|xl|2xl):grid-cols-/)
    expect(grille.children).toHaveLength(4)
    expect(grille).toHaveClass('break-words') // un libellé long se replie dans sa case, ne déborde pas
  })

  it('T4-X3-009 — la cible de la feuille Avancé nomme le panneau de la conception, jamais un « 8 » nu', async () => {
    const contexte = { ...CTX, cible: { ...CTX.cible, panneaux: 8, kwc: 4.4, panel_watt: 550 } }
    rendre({ contexte })
    expect(screen.getByTestId('cal-cible-panneaux')).toHaveTextContent(/^8 panneaux de 550 W$/)
  })

  it('cible nulle : « non renseignée », et l’écran le DIT', async () => {
    rendre({ contexte: CTX_VIDE, calepinageId: CTX_VIDE.calepinage.id })

    expect(screen.getByTestId('cal-cible-panneaux'))
      .toHaveTextContent('non renseignée')
    expect(screen.getByRole('status'))
      .toHaveTextContent('Aucune cible de puissance connue')
  })

  it('ACAL942 — empreinte changée : le détail est relu (fiche « Oui » sans F5)', async () => {
    const { rerender } = rendre()
    await waitFor(() => expect(calepinageApi.calepinages.get).toHaveBeenCalledTimes(1))

    const apres = {
      ...CTX, geometrie: { ...CTX.geometrie, empreinte_document: 'f'.repeat(64) },
    }
    rerender(
      <MemoryRouter>
        <AtelierPanneaux calepinageId={CTX.calepinage.id} contexte={apres} />
      </MemoryRouter>,
    )

    await waitFor(() => expect(calepinageApi.calepinages.get).toHaveBeenCalledTimes(2))
  })

  it('R2-09 : la puissance cible porte une virgule, jamais un point brut', async () => {
    rendre({ contexte: { ...CTX, cible: { ...CTX.cible, kwc: 2.13 } } })
    const dd = screen.getByText(/kWc/, { selector: 'dd' })
    expect(dd).toHaveTextContent('2,13 kWc')
  })

  it('R2-13 : conception changée depuis le devis — badge dit tout de suite, « envoyé » ne sera pas modifié', async () => {
    calepinageApi.calepinages.get.mockResolvedValue({ data: { ...DETAIL, layout_stale: true } })
    const lie = { ...CTX.calepinage.devis_lie, statut: 'brouillon' }
    const { rerender } = rendre({ contexte: { ...CTX, calepinage: { ...CTX.calepinage, devis_lie: lie } } })
    expect(await screen.findByTestId('cal-devis-perime')).toHaveTextContent('Devis périmé — à resynchroniser')
    rerender(
      <MemoryRouter>
        <AtelierPanneaux calepinageId={CTX.calepinage.id}
          contexte={{ ...CTX, calepinage: { ...CTX.calepinage, devis_lie: { ...lie, statut: 'envoye' } } }} />
      </MemoryRouter>,
    )
    // ACAL1320 (D-ACAL-73) — la phrase de l'envoyé dit ce que le geste FAIT : aperçu d'abord, puis correction
    // sur place du devis reçu par le client ; jamais « ne sera pas modifié ».
    expect(screen.getByTestId('cal-devis-perime')).toHaveTextContent(
      'Devis envoyé : « Resynchroniser le devis » montre d’abord ce qui change, puis corrige sur place le devis déjà '
      + 'reçu par le client (sa page et son PDF montreront la version corrigée)')
    expect(screen.getByTestId('cal-devis-perime')).not.toHaveTextContent('ne sera pas modifié')
    rerender(
      <MemoryRouter>
        <AtelierPanneaux calepinageId={CTX.calepinage.id}
          contexte={{ ...CTX, calepinage: { ...CTX.calepinage, devis_lie: { ...lie, statut: 'accepte' } } }} />
      </MemoryRouter>,
    )
    expect(screen.getByTestId('cal-devis-perime'))
      .toHaveTextContent('Devis accepté : il ne sera pas modifié — créez une révision')
  })

  it('lecture seule : aucune écriture proposée', async () => {
    rendre({ lectureSeule: true })

    await waitFor(() => expect(screen.getByTestId('cal-atelier-panneaux')).toBeTruthy())
    expect(screen.queryByTestId('cal-bouton-devis')).toBeNull()
    // Le panneau LUI-MÊME reste : consulter une conception figée est le but.
    expect(screen.getByTestId('cal-lien-variantes')).toBeTruthy()
  })
})

/* ============================================================================
   ACAL42 — LE BANDEAU FIGÉ : MOTIF SERVEUR, « RÉVISER (V2) », AUCUN DÉVERROUILLER.
   ========================================================================== */
describe('ACAL42 — bandeau de lecture seule', () => {
  it('bandeau figé : motif serveur et Réviser (v2), aucun Déverrouiller', async () => {
    mocks.hasPermission.mockReturnValue(true)
    const contexte = {
      ...CTX, modifiable: false,
      raison_lecture_seule: 'Devis accepté : révisez-le',
      revision_possible: true,
    }
    rendre({ contexte, lectureSeule: true })

    expect(screen.getByTestId('cal-bandeau-lecture-seule-raison'))
      .toHaveTextContent('Devis accepté : révisez-le')
    expect(screen.queryByTestId('cal-deverrouiller')).toBeNull()
    expect(screen.queryByText(/Déverrouiller/)).toBeNull()
    expect(await screen.findByTestId('cal-devis-reviser-lecture-seule'))
      .toHaveTextContent('Réviser (nouvelle version)')
  })

  it('conception ouverte : aucun bandeau', async () => {
    rendre()
    await waitFor(() => expect(screen.getByTestId('cal-atelier-panneaux')).toBeTruthy())
    expect(screen.queryByTestId('cal-bandeau-lecture-seule')).toBeNull()
  })
})

/* =====================================================================  })
})

   ACAL415 — les outils et onglets de l'atelier dans la palette ⌘K.
   ========================================================================== */
describe('ACAL415 — commandes ⌘K de l’atelier', () => {
  const ecouter = () => {
    const recus = []
    const onEvt = (e) => recus.push(e.detail.actions)
    window.addEventListener('taqinor:lead-workspace-actions', onEvt)
    return { recus, fin: () => window.removeEventListener('taqinor:lead-workspace-actions', onEvt) }
  }

  it('l’atelier poste ses commandes puis les retire au démontage', async () => {
    const { recus, fin } = ecouter()
    const outilObstacle = vi.fn()
    const { unmount } = rendre({ builderApi: { raccourcis: { outilObstacle } } })

    const actions = recus.at(-1)
    expect(actions.some((a) => a.label === 'Ouvrir Horizon lointain')).toBe(true)
    const obstacle = actions.find((a) => a.label === 'Ajouter un obstacle')
    obstacle.run()
    expect(outilObstacle).toHaveBeenCalledTimes(1)

    unmount()
    expect(recus.at(-1)).toEqual([])
    fin()
  })

  it('lecture seule : aucun outil d’édition proposé, les onglets restent', async () => {
    const { recus, fin } = ecouter()
    rendre({ lectureSeule: true, builderApi: { raccourcis: { outilObstacle: vi.fn(), outilMesure: vi.fn() } } })

    const labels = recus.at(-1).map((a) => a.label)
    expect(labels).not.toContain('Ajouter un obstacle')
    expect(labels).toContain('Mesurer une distance')
    expect(labels).toContain('Ouvrir Horizon lointain')
    fin()
  })
})

/* ACAL421 — « Conception automatique » : {lat, lng} servis → [lng, lat] attendus par le builder. */
describe('ACAL421 — conception automatique', () => {
  it('le chemin OSM fermé (dernier nœud = premier) donne un contour sans sommet répété (rejeu runner 44905036243)', () => {
    const p = [{ lat: 33.5, lng: -7.6 }, { lat: 33.5, lng: -7.59 }, { lat: 33.51, lng: -7.59 }, { lat: 33.51, lng: -7.59 }, { lat: 33.5, lng: -7.6 }]
    expect(contourLngLat(p)).toEqual([[-7.6, 33.5], [-7.59, 33.5], [-7.59, 33.51]])
  })
  const POLYGONE = [{ lat: 33.5, lng: -7.6 }, { lat: 33.5, lng: -7.59 }, { lat: 33.51, lng: -7.59 }]
  const builder = (zones = []) => ({
    serializeLayout: vi.fn(() => ({ zones })),
    ajouterPanDepuisContour: vi.fn(() => ({ ok: true, id: 'area-2' })),
  })

  it('emprise convertie en [lng, lat], pan vide remplacé, refus nommé sans emprise', async () => {
    mocks.hasPermission.mockReturnValue(true)
    const builderApi = builder()
    // Décision fondateur 21/11 : tâche de fond — « en cours » affiché pendant la recherche.
    let finir
    crmApi.lancerRechercheEmprise.mockReturnValueOnce(new Promise((r) => { finir = r }))
    rendre({ builderApi })
    fireEvent.click(await screen.findByTestId('cal-conception-auto'))
    expect(await screen.findByTestId('cal-conception-auto-message')).toHaveTextContent('Recherche du bâtiment en cours…')
    expect(screen.getByTestId('cal-conception-auto')).toBeDisabled()
    const pret = exempleContrat('crm', 'lead_emprise_recherche')
    finir({ data: { ...pret, polygon: POLYGONE } })
    await waitFor(() => expect(builderApi.ajouterPanDepuisContour).toHaveBeenCalledTimes(1))
    expect(crmApi.lancerRechercheEmprise).toHaveBeenCalledWith(CTX.calepinage.lead)
    expect(builderApi.ajouterPanDepuisContour.mock.calls[0][0])
      .toEqual([[-7.6, 33.5], [-7.59, 33.5], [-7.59, 33.51]])

    crmApi.lancerRechercheEmprise.mockResolvedValueOnce(reponseContrat('crm', 'lead_emprise_recherche', 'exemple_refus'))
    fireEvent.click(await screen.findByTestId('cal-conception-auto'))
    expect(await screen.findByTestId('cal-conception-auto-message'))
      .toHaveTextContent("OpenStreetMap n'a pas répondu")
    expect(builderApi.ajouterPanDepuisContour).toHaveBeenCalledTimes(1)
  })

  it('suit le statut de la tâche de fond jusqu’au contour, borné à 90 s, sans vraie pause', async () => {
    const enCours = exempleContrat('crm', 'lead_emprise_recherche', 'exemple_vide')
    const pret = exempleContrat('crm', 'lead_emprise_recherche')
    const attendre = vi.fn(() => Promise.resolve())
    crmApi.lancerRechercheEmprise.mockResolvedValueOnce({ data: enCours })
    crmApi.getRechercheEmprise.mockResolvedValueOnce({ data: enCours }).mockResolvedValueOnce({ data: pret })
    const builderApi = builder()
    const r = await conceptionAuto(7, builderApi, { attendre })
    expect(r).toEqual({ ok: true, message: 'Contour posé : le toit est rempli.' })
    expect(crmApi.getRechercheEmprise).toHaveBeenCalledWith(enCours.job_id)
    expect(attendre).toHaveBeenCalledTimes(2)

    crmApi.lancerRechercheEmprise.mockResolvedValueOnce({ data: enCours })
    crmApi.getRechercheEmprise.mockResolvedValue({ data: enCours })
    const borne = await conceptionAuto(7, builder(), { attendre })
    expect(borne.ok).toBe(false)
    expect(borne.message).toMatch(/trop de temps/)
    expect(attendre).toHaveBeenCalledTimes(2 + 45)
  })

  it('bouton absent : pan déjà tracé, lecture seule', async () => {
    rendre({ builderApi: builder([{ vertices: POLYGONE.map((p) => [p.lng, p.lat]) }]) })
    await waitFor(() => expect(screen.getByTestId('cal-atelier-panneaux')).toBeTruthy())
    expect(screen.queryByTestId('cal-conception-auto')).toBeNull()
    cleanup()
    rendre({ builderApi: builder(), lectureSeule: true })
    await waitFor(() => expect(screen.getByTestId('cal-atelier-panneaux')).toBeTruthy())
    expect(screen.queryByTestId('cal-conception-auto')).toBeNull()
  })
})

describe('ACAL867 — l’étape Documents guidée porte « Générer le devis »', () => {
  const rendreA = (recherche) => render(
    <MemoryRouter initialEntries={[`/${recherche}`]}>
      <AtelierPanneaux calepinageId={CTX.calepinage.id} contexte={CTX} />
    </MemoryRouter>,
  )
  const dansActions = () => screen.getByTestId('cal-atelier-actions').querySelector('[data-testid="cal-generer-devis"]')
  // Un calepinage SANS devis lié : le bouton est « Générer le devis » (avec un devis, c'est « Resynchroniser »).
  beforeEach(() => {
    calepinageApi.calepinages.get.mockResolvedValue({ data: exempleContrat('calepinage', 'calepinage_detail', 'exemple_vide') })
  })

  it('étape Documents guidée : un seul bouton, DANS l’écran de l’étape, plus dans cal-atelier-actions', async () => {
    rendreA('?onglet=documents')

    const ecran = await screen.findByTestId('cal-etape-documents-ecran', {}, { timeout: 15_000 })
    await waitFor(() => expect(ecran.querySelector('[data-testid="cal-generer-devis"]')).not.toBeNull())
    expect(screen.getAllByTestId('cal-generer-devis')).toHaveLength(1)
    expect(dansActions()).toBeNull()
    // Refonte 22/11 (maquette Documents) : deux colonnes ; le bouton est au pied de « Prêt à envoyer ? » (gauche).
    const enfants = [...ecran.children]
    expect(enfants).toHaveLength(2)
    expect(enfants[0].querySelector('[data-testid="cal-generer-devis"]')).not.toBeNull()
    // ACAL1985 — en Guidé à Documents, c'est le bouton doré v2 (52 px, rayon 14 par ses jetons), pas le filet de l'Expert.
    const bouton = screen.getByTestId('cal-generer-devis')
    expect(bouton.classList.contains('cal-bouton-or')).toBe(true)
    expect(bouton.classList.contains('cal-bouton-or-grand')).toBe(true)
  }, 30_000)

  it('hors de l’étape Documents, ou en mode expert : le bouton reste dans cal-atelier-actions', async () => {
    rendreA('')
    await waitFor(() => expect(dansActions()).not.toBeNull())
    expect(screen.queryByTestId('cal-etape-documents-ecran')).toBeNull()
    cleanup()
    rendreA('?onglet=documents&mode=expert')
    await waitFor(() => expect(dansActions()).not.toBeNull())
    expect(screen.getAllByTestId('cal-generer-devis')).toHaveLength(1)
    expect(screen.queryByTestId('cal-etape-documents-ecran')).toBeNull()
    // ACAL1802 — en Expert l'or n'est pas l'action de l'étape : bouton à filet.
    expect(screen.getByTestId('cal-generer-devis').classList.contains('cal-bouton-or')).toBe(false)
  }, 30_000)
})

/* T4-X7-010 — feuille « Avancé » au doigt (tablette) : les liens (« Montrer au client », « Relevé de visite »…) mesuraient
   20 px de haut. Toute cible de la feuille fait au moins 44 px de haut sur un écran tactile. */
describe('T4-X7-010 — feuille « Avancé » : cibles de 44 px au doigt', () => {
  it('un lien de la feuille fait 44 px de haut sous (pointer: coarse)', () => {
    const style = feuilleAuDoigt('src/styles/calepinage/50-coque-atelier.css')
    const hote = document.createElement('div')
    hote.innerHTML = '<div class="cal-coque"><div class="cal-coque-avance"><div class="flex"><a href="#x">Montrer au client</a></div></div></div>'
    document.body.appendChild(hote)
    try {
      expect(getComputedStyle(hote.querySelector('a')).minHeight).toBe('44px')
    } finally { style.remove(); hote.remove() }
  })
})
