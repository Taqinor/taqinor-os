import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

const mocks = vi.hoisted(() => ({ tableauMarches: vi.fn() }))

vi.mock('../../api/aoApi', () => ({
  default: { tableauMarches: mocks.tableauMarches },
}))

import DashboardPage from './DashboardPage'

const renderScreen = () => render(<MemoryRouter><DashboardPage /></MemoryRouter>)

const here = dirname(fileURLToPath(import.meta.url))
//: La VÉRITÉ du contrat : le selector qui sert GET /ao/tableau-marches/.
const SELECTORS_PY = join(
  here, '..', '..', '..', '..',
  'backend', 'django_core', 'apps', 'ao', 'selectors.py',
)

/* ============================================================================
   PACT13 — la charge utile est IMPORTÉE, plus jamais inventée.
   ----------------------------------------------------------------------------
   La toute première version de ce fichier déclarait à la main
   `PAYLOAD = { ao_en_cours: 7, …, echeances_dues: [ … ] }` — l'INVERSE EXACT de
   ce que le backend renvoie — et restait VERT : il vérifiait l'écran contre
   l'hypothèse de l'écran. Un mock écrit à la main est une DEUXIÈME source de
   vérité ; c'est elle qu'il fallait supprimer.

   La forme vient désormais de l'exemple COMMITTÉ dans l'app
   (`backend/django_core/apps/ao/contract_samples/tableau_marches.json`), le
   même fichier que le backend affirme et que `scripts/check_api_shapes.py`
   compare au dictionnaire RÉELLEMENT renvoyé par la vue. Si le serveur change
   de forme, l'exemple change, et ce test casse tout seul.
   ========================================================================== */
const PAYLOAD = exempleContrat('ao', 'tableau_marches')

beforeEach(() => {
  vi.clearAllMocks()
  mocks.tableauMarches.mockResolvedValue({ data: PAYLOAD })
})

describe('DashboardPage', () => {
  it('charge le tableau de bord via UN SEUL appel agrégé (aoApi.tableauMarches)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.tableauMarches).toHaveBeenCalledTimes(1))
    expect(await screen.findByText('AO en cours')).toBeInTheDocument()
  })

  it('affiche les 5 KPI lus dans les BONS blocs du payload réel (aucun calcul côté front)', async () => {
    renderScreen()
    await screen.findByText('AO en cours')
    expect(screen.getByText('7')).toBeInTheDocument()               // en_cours.total
    expect(screen.getByText('43 %')).toBeInTheDocument()            // reussite.taux_reussite_pct (42.5 arrondi à l'affichage)
    expect(screen.getByText('250 000 MAD')).toBeInTheDocument()     // cautions.montant_immobilise
    expect(screen.getByText('3')).toBeInTheDocument()               // marches_en_execution.total
    expect(screen.getByText('1 240 / 1 500')).toBeInTheDocument()   // capacite.demontree_modules vs engagee_modules
  })

  it('rend les blocs du payload comme des VALEURS, jamais comme enfant React', async () => {
    // Régression du crash de production : `marches_en_execution` (un OBJET)
    // partait tel quel dans le JSX — React lève « Objects are not valid as a
    // React child » et l'écran affichait « Une erreur est survenue ». Si la
    // régression revient, `render` lève et ce test tombe AVANT l'assertion.
    renderScreen()
    await screen.findByText('AO en cours')
    expect(screen.queryByText('[object Object]')).toBeNull()
  })

  it('le centre d’échéances consomme la VRAIE liste (en_cours.par_echeance), même payload, aucune seconde requête', async () => {
    renderScreen()
    await screen.findByText('AO en cours')
    expect(screen.getByText('Centrale PV 500 kWc — lycée Ibn Sina')).toBeInTheDocument()
    expect(screen.getByText('Pompage solaire — 12 forages')).toBeInTheDocument()
    // Jours restants CALCULÉS SERVEUR (`jours_restants`), relayés tels quels.
    expect(screen.getByText('J-7')).toBeInTheDocument()
    expect(screen.getByText('En retard (J+6)')).toBeInTheDocument()
    // Un AO sans date limite n'est pas une échéance : il n'entre pas au centre.
    expect(screen.queryByText('Ombrières parking')).toBeNull()
    expect(mocks.tableauMarches).toHaveBeenCalledTimes(1)
  })

  it('affiche `echeances_dues` comme un COMPTEUR (un entier ne se .map() pas)', async () => {
    // C'était l'exception qui plantait l'écran : (data.echeances_dues ?? []).map(…)
    // sur un ENTIER → TypeError.
    renderScreen()
    expect(await screen.findByText('Échéances de remise — 3 rappels dus')).toBeInTheDocument()
  })

  it('un payload vide (utilisateur sans société) affiche des zéros, sans planter', async () => {
    // Un autre ÉTAT du serveur (`tableau_marches_vide`), jamais une autre
    // FORME : la variante vit dans le même document de contrat.
    mocks.tableauMarches.mockResolvedValue(
      reponseContrat('ao', 'tableau_marches', 'exemple_vide'))
    renderScreen()
    await screen.findByText('AO en cours')
    expect(screen.getByText('0 %')).toBeInTheDocument()
    expect(screen.getByText('0 / 0')).toBeInTheDocument()
    expect(screen.getByText('Échéances de remise')).toBeInTheDocument()
    expect(screen.getByText('Rien à échéance')).toBeInTheDocument()
  })
})

/* ── Garde de contrat : le mock DOIT reproduire les clés du serveur ─────────
   Le mock est confronté au fichier qui sert réellement l'endpoint. Toute
   divergence (clé ajoutée, renommée, retirée côté backend) fait tomber ce test
   au lieu de laisser un écran vert en test et rouge en production. */
function clesDuBloc(source, nomFonction) {
  const debut = source.indexOf(`def ${nomFonction}(`)
  if (debut === -1) return []
  const suite = source.slice(debut + 1)
  const fin = suite.indexOf('\ndef ')
  const corps = fin === -1 ? suite : suite.slice(0, fin)
  // Clés de PREMIER niveau du dict retourné : indentation de 8 espaces.
  return [...corps.matchAll(/^ {8}'([a-z_]+)':/gm)].map((m) => m[1]).sort()
}

describe('GET /ao/tableau-marches/ — contrat serveur', () => {
  it('le fichier selector existe (sinon le contrat n’est pas vérifiable)', () => {
    expect(existsSync(SELECTORS_PY)).toBe(true)
  })

  it('le mock a EXACTEMENT les clés de premier niveau du selector', () => {
    const py = readFileSync(SELECTORS_PY, 'utf8')
    const clesVide = clesDuBloc(py, 'tableau_marches_vide')
    const clesReelles = clesDuBloc(py, 'tableau_marches')
    expect(clesVide).toHaveLength(6)
    expect(clesReelles).toEqual(clesVide) // le tableau « vide » publie le même contrat
    expect(Object.keys(PAYLOAD).sort()).toEqual(clesVide)
  })

  it('`echeances_dues` est un COMPTEUR côté serveur (un len()), pas une liste', () => {
    const py = readFileSync(SELECTORS_PY, 'utf8')
    expect(py).toMatch(/'echeances_dues':\s*len\(/)
    expect(typeof PAYLOAD.echeances_dues).toBe('number')
  })

  it('chaque sous-clé lue par l’écran existe dans le selector', () => {
    const py = readFileSync(SELECTORS_PY, 'utf8')
    const sousCles = [
      'total', 'sous_7_jours', 'en_retard', 'par_echeance',
      'taux_reussite_pct', 'gagnes', 'perdus',
      'montant_immobilise', 'nombre', 'expirant_avant_ouverture',
      'montant_offre_ht',
      'demontree_modules', 'engagee_modules', 'ecart_modules',
      'reference', 'objet', 'acheteur', 'statut_display',
      'date_limite', 'jours_restants',
    ]
    sousCles.forEach((cle) => expect(py).toContain(`'${cle}'`))
  })
})

// ── Garde de source : seuils d'urgence via ui/module/urgency.js, jamais une
//    constante locale (Done AOF172). ────────────────────────────────────────
/* Une garde « la source ne contient PAS X » ne peut pas balayer le fichier
   brut : l'en-tête de `DashboardPage.jsx` DOCUMENTE justement que
   `EcheanceCenter` porte les seuils (« daysUntil/urgencyLevel/urgencyTone/
   urgencyLabel… »), donc la garde se déclenchait sur le commentaire qui
   affirme l'invariant qu'elle vérifie. On retire commentaires de bloc et de
   ligne avant d'assertionner — les littéraux de chaîne sont alternés EN
   PREMIER pour qu'une URL contenant `//` ne soit jamais prise pour un
   commentaire. */
function stripComments(source) {
  return source.replace(
    /(['"`])(?:\\.|(?!\1)[^\\])*\1|\/\*[\s\S]*?\*\/|\/\/[^\n]*/g,
    (match) => (/^['"`]/.test(match) ? match : ' '),
  )
}

describe('DashboardPage.jsx — contrat de source', () => {
  const src = readFileSync(join(here, 'DashboardPage.jsx'), 'utf8')
  const code = stripComments(src)

  it('utilise EcheanceCenter (qui porte lui-même urgency.js) — aucun seuil de jours codé en dur ici', () => {
    expect(code).toMatch(/EcheanceCenter/)
    expect(code).not.toMatch(/urgencyLevel|urgencyTone|urgencyLabel|daysUntil/)
    expect(code).not.toMatch(/\bJ-\d/)
  })

  it('un seul appel réseau agrégé (aoApi.tableauMarches), jamais un axios.get direct', () => {
    expect(code).toMatch(/aoApi\.tableauMarches\(\)/)
    expect(code).not.toMatch(/axios\.get/)
  })

  it('ne lit plus AUCUNE clé plate fantôme (celles qui n’ont jamais existé côté serveur)', () => {
    expect(code).not.toMatch(
      /data\.ao_en_cours|data\.taux_reussite\b|data\.cautions_immobilisees|data\.capacite_vs_engagement/,
    )
    // `echeances_dues` est un entier : plus aucun `.map()` dessus.
    expect(code).not.toMatch(/echeances_dues[^\n]*\.map\(/)
  })
})
