import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import fs from 'node:fs'
import path from 'node:path'

/* `import.meta.url` est virtuel sous vitest : on part du dossier de travail
   (fixé à `frontend/` par la configuration vitest) et on remonte jusqu'à la
   racine du dépôt — même repli que `src/api/calepinageApi.test.mjs`.
   `globalThis.process` plutôt que `process` nu : le lint de ce dossier ne
   déclare pas les globales Node. */
const RACINE_FRONTEND = globalThis.process.cwd()
function racineDepot() {
  let dossier = RACINE_FRONTEND
  for (let i = 0; i < 8; i += 1) {
    if (fs.existsSync(path.join(dossier, 'backend', 'django_core'))) return dossier
    dossier = path.dirname(dossier)
  }
  throw new Error(`Racine du depot introuvable depuis ${RACINE_FRONTEND}`)
}

/* ============================================================================
   CAL91 — L'OMBRIÈRE EST UNE SURFACE DE POSE, PAS UN OUVRAGE CHIFFRÉ.
   ----------------------------------------------------------------------------
   Ce que ce fichier interdit :
     * qu'une CHARGE ou une STRUCTURE soit calculée (la tâche l'exige : « aucun
       chiffrage de structure ») — la source de l'écran est relue pour le tenir ;
     * qu'une HAUTEUR LIBRE soit supposée (absente ⇒ la couverture n'est pas
       levée, et l'écran le DIT) ;
     * que l'ombrière manque aux TOTAUX PAR BÂTIMENT à côté des pans de toiture ;
     * qu'un pas ou un taux soit recalculé ici (ils viennent de CAL89, qui les
       tient du moteur).
   ========================================================================== */

const layout = vi.fn()
const enregistrerLayoutCalepinage = vi.fn()
const pose = vi.fn()
vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      layout: (...a) => layout(...a),
      enregistrerLayoutCalepinage: (...a) => enregistrerLayoutCalepinage(...a),
    },
    moteur: { pose: (...a) => pose(...a) },
  },
}))

const {
  default: Ombriere, documentOmbriere, totauxParBatiment,
} = await import('../Ombriere')

/** Une réponse de moteur à la forme EXACTE du contrat `pose.json`. */
const REPONSE = {
  schema_version: 1,
  repere: 'OMBRIERE',
  hash_entree: 'def',
  version_moteur: '1.2.3',
  plans: [{
    surface: 'OMBRIERE',
    modules: 24,
    rangees: [{ y0: 0, modules: 12 }, { y0: 2.5, modules: 12 }],
    tables: [
      { x0: 0, x1: 6, y0: 0, y1: 2.3, kit: 'terrain' },
      { x0: 0, x1: 6, y0: 2.5, y1: 4.8, kit: 'terrain' },
    ],
  }],
}

const SAISIE = {
  repere: 'OMB-1',
  label: 'Ombrière parking',
  buildingId: 'BAT-A',
  largeurM: '12',
  profondeurM: '5',
  clearHeightM: '2.5',
  tiltDeg: '7',
  flowAzimuthDeg: '180',
  moduleLongM: '2.278',
  moduleCourtM: '1.134',
  puissanceWc: '720',
  modulesParTable: '2',
  alleeM: '',
}

beforeEach(() => {
  vi.clearAllMocks()
  layout.mockResolvedValue({
    data: {
      roof_layout: {
        zones: [
          { id: 'PAN-A', buildingId: 'BAT-A', geometry: { count: 30 } },
          { id: 'PAN-B', buildingId: 'BAT-B', geometry: { count: 10 } },
        ],
      },
    },
  })
  enregistrerLayoutCalepinage.mockResolvedValue({ data: {} })
  pose.mockResolvedValue({ data: REPONSE })
})
afterEach(() => { cleanup() })

const monter = (props = {}) => render(
  <MemoryRouter><Ombriere calepinageId={9} {...props} /></MemoryRouter>,
)

const remplir = () => {
  for (const [cle, valeur] of Object.entries(SAISIE)) {
    const champ = screen.queryByTestId(`cal-ombriere-${cle}`)
    if (champ) fireEvent.change(champ, { target: { value: valeur } })
  }
}

/* ── 1. AUCUNE CHARGE, AUCUNE STRUCTURE ────────────────────────────────── */

describe('CAL91 — aucun chiffrage de structure', () => {
  it('la source de l’écran ne calcule ni charge, ni poteau, ni masse, ni prix', () => {
    const brut = fs.readFileSync(
      path.join(RACINE_FRONTEND, 'src/features/calepinage/Ombriere.jsx'), 'utf8',
    )
    // On juge le CODE, pas la prose : les commentaires (qui DISENT justement
    // qu'aucune structure n'est chiffrée) sont retirés avant la recherche.
    const source = brut.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
    for (const interdit of [
      /descenteDeCharges/i, /chargeKg/i, /poteau[A-Z]/, /sectionPoteau/i,
      /masseKg/i, /prix/i, /coutStructure/i,
    ]) {
      expect(source, `motif ${interdit}`).not.toMatch(interdit)
    }
  })

  it('le document persisté ne porte AUCUNE clé de structure', () => {
    const s = documentOmbriere(SAISIE, REPONSE)
    const cles = [...Object.keys(s), ...Object.keys(s.engine)].join(' ').toLowerCase()
    for (const interdit of ['charge', 'poteau', 'structure', 'masse', 'prix', 'cout']) {
      expect(cles, `clé ${interdit}`).not.toContain(interdit)
    }
  })
})

/* ── 2. LA HAUTEUR LIBRE N'EST JAMAIS SUPPOSÉE ─────────────────────────── */

describe('CAL91 — la hauteur libre est saisie ou absente, jamais supposée', () => {
  it('saisie ⇒ persistée telle quelle', () => {
    expect(documentOmbriere(SAISIE, REPONSE).clearHeightM).toBe(2.5)
  })

  it('absente ⇒ null (aucune hauteur par défaut) et l’écran le dit', async () => {
    expect(documentOmbriere({ ...SAISIE, clearHeightM: '' }, REPONSE).clearHeightM).toBeNull()
    monter()
    await waitFor(() => expect(layout).toHaveBeenCalled())
    expect(screen.getByTestId('cal-ombriere-hauteur').textContent)
      .toMatch(/non renseignée/i)
  })
})

/* ── 3. LE DOCUMENT ET SON CONTRAT ─────────────────────────────────────── */

describe('CAL91 — la surface persistée est conforme au contrat v2 partagé', () => {
  it('porte le genre `ombriere` et un bloc `engine` entièrement serveur', () => {
    const s = documentOmbriere(SAISIE, REPONSE)
    expect(s.kind).toBe('ombriere')
    expect(s.buildingId).toBe('BAT-A')
    expect(s.flowAzimuthDeg).toBe(180)
    expect(s.engine.modules).toBe(24)
    expect(s.engine.rowPitchM).toBeCloseTo(2.5, 9) // MESURÉ sur les rangées
    expect(s.engine.groundCoverageRatio).toBeCloseTo((2 * 6 * 2.3) / 60, 9)
  })

  it('chaque clé écrite est déclarée par `roof_layout_v2.schema.json`', () => {
    const schema = JSON.parse(fs.readFileSync(path.join(
      racineDepot(),
      'backend/django_core/apps/calepinage/contract_samples/roof_layout_v2.schema.json',
    ), 'utf8'))
    const def = schema.$defs.poseSurface
    expect(def.properties.kind.enum).toContain('ombriere')
    const s = documentOmbriere(SAISIE, REPONSE)
    for (const cle of Object.keys(s)) {
      expect(Object.keys(def.properties), `clé ${cle}`).toContain(cle)
    }
    for (const cle of Object.keys(s.engine)) {
      expect(Object.keys(schema.$defs.posePlanMoteur.properties), `engine.${cle}`).toContain(cle)
    }
  })
})

/* ── 4. LES TOTAUX PAR BÂTIMENT ────────────────────────────────────────── */

describe('CAL91 — l’ombrière se totalise avec le site, par bâtiment', () => {
  const LAYOUT = {
    zones: [
      { id: 'PAN-A', buildingId: 'BAT-A', geometry: { count: 30 } },
      { id: 'PAN-B', buildingId: 'BAT-B', geometry: { count: 10 } },
      { id: 'PAN-C', buildingId: 'BAT-C' }, // rien de posé encore
    ],
    poseSurfaces: [
      { kind: 'ombriere', buildingId: 'BAT-A', engine: { modules: 24 } },
      { kind: 'sol', buildingId: 'BAT-B', engine: { modules: 100 } },
    ],
  }

  it('additionne pans + ombrières + champs au sol du MÊME bâtiment', () => {
    const t = totauxParBatiment(LAYOUT)
    const a = t.find((x) => x.batiment === 'BAT-A')
    expect(a.modules).toBe(54) // 30 (pan) + 24 (ombrière)
    expect(a.pans).toBe(1)
    expect(a.ombrieres).toBe(1)
    const b = t.find((x) => x.batiment === 'BAT-B')
    expect(b.modules).toBe(110)
    expect(b.sols).toBe(1)
  })

  it('un bâtiment dont RIEN n’est posé rend null, jamais 0', () => {
    const c = totauxParBatiment(LAYOUT).find((x) => x.batiment === 'BAT-C')
    expect(c.modules).toBeNull()
    expect(c.pans).toBe(1)
  })

  it('sans `buildingId`, tout tombe dans le bâtiment unique', () => {
    const t = totauxParBatiment({
      zones: [{ id: 'P', geometry: { count: 5 } }],
      poseSurfaces: [{ kind: 'ombriere', engine: { modules: 7 } }],
    })
    expect(t).toHaveLength(1)
    expect(t[0].modules).toBe(12)
  })
})

/* ── 5. L'ÉCRAN : calculer, totaliser, enregistrer, recharger ──────────── */

describe('CAL91 — l’écran pose l’ombrière et la montre dans les totaux', () => {
  it('calcule via la porte moteur, avec le sens d’écoulement comme azimut', async () => {
    monter()
    await waitFor(() => expect(layout).toHaveBeenCalled())
    remplir()
    fireEvent.click(screen.getByTestId('cal-ombriere-calculer'))
    await waitFor(() => expect(pose).toHaveBeenCalled())
    expect(pose.mock.calls[0][0].demande.surfaces[0].azimut_deg).toBe(180)
    await waitFor(() => {
      expect(screen.getByTestId('cal-ombriere-modules').textContent).toContain('24')
    })
    expect(screen.getByTestId('cal-ombriere-pas').textContent).toContain('2.5')
  })

  it('l’ombrière apparaît dans le total de SON bâtiment, à côté du pan', async () => {
    monter()
    await waitFor(() => expect(layout).toHaveBeenCalled())
    remplir()
    fireEvent.click(screen.getByTestId('cal-ombriere-calculer'))
    await waitFor(() => expect(pose).toHaveBeenCalled())
    await waitFor(() => {
      expect(screen.getByTestId('cal-ombriere-total-BAT-A').textContent).toContain('54')
    })
    // Le bâtiment voisin n'a pas bougé.
    expect(screen.getByTestId('cal-ombriere-total-BAT-B').textContent).toContain('10')
  })

  it('l’enregistrement AJOUTE `poseSurfaces` sans toucher `zones`', async () => {
    monter()
    await waitFor(() => expect(layout).toHaveBeenCalled())
    remplir()
    fireEvent.click(screen.getByTestId('cal-ombriere-calculer'))
    await waitFor(() => expect(pose).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('cal-ombriere-enregistrer'))
    await waitFor(() => expect(enregistrerLayoutCalepinage).toHaveBeenCalled())
    const doc = enregistrerLayoutCalepinage.mock.calls[0][1]
    expect(doc.zones).toHaveLength(2)
    expect(doc.poseSurfaces).toHaveLength(1)
    expect(doc.poseSurfaces[0].kind).toBe('ombriere')
  })

  it('RECHARGE une ombrière enregistrée : saisie et plan reviennent', async () => {
    layout.mockResolvedValue({
      data: {
        roof_layout: {
          zones: [{ id: 'PAN-A', buildingId: 'BAT-A', geometry: { count: 30 } }],
          poseSurfaces: [documentOmbriere(SAISIE, REPONSE)],
        },
      },
    })
    monter()
    await waitFor(() => expect(layout).toHaveBeenCalled())
    await waitFor(() => {
      expect(screen.getByTestId('cal-ombriere-clearHeightM').value).toBe('2.5')
    })
    expect(screen.getByTestId('cal-ombriere-largeurM').value).toBe('12')
    expect(screen.getByTestId('cal-ombriere-modules').textContent).toContain('24')
  })

  it('refuse de calculer une emprise incomplète, et le DIT', async () => {
    monter()
    await waitFor(() => expect(layout).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('cal-ombriere-calculer'))
    await waitFor(() => {
      expect(screen.getByTestId('cal-ombriere-message').textContent).toMatch(/incomplets/i)
    })
    expect(pose).not.toHaveBeenCalled()
  })
})

/* ── 6. L'ÉCRAN EST ATTEIGNABLE ────────────────────────────────────────── */

describe('CAL91 — la route est déclarée dans le module', () => {
  it('`/calepinage/:id/ombriere` existe et monte Ombriere', async () => {
    const config = (await import('../module.config')).default
    const route = config.routes.find((r) => r.path === '/calepinage/:id/ombriere')
    expect(route).toBeTruthy()
    expect(route.component).toBeTruthy()
    expect(route.roles).toContain('normal')
  })
})
