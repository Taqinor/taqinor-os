import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import fs from 'node:fs'
import path from 'node:path'

/* `import.meta.url` est virtuel sous vitest : on part du dossier de travail
   (que la configuration vitest fixe à `frontend/`) et on remonte jusqu'à la
   racine du dépôt — le même repli que `src/api/calepinageApi.test.mjs`.
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
   CAL89 — LE MODE TERRAIN SE TRACE, SE CALCULE ET SE RECHARGE.
   ----------------------------------------------------------------------------
   Ce que ce fichier interdit :
     * qu'un PAS inter-rangées soit calculé côté client (il est MESURÉ sur les
       rangées que le moteur renvoie — CAL88 est la seule physique du pas) ;
     * qu'un TAUX D'OCCUPATION soit une saisie (c'est une SORTIE : emprises des
       tables RENDUES par le moteur ÷ surface du terrain saisie) ;
     * qu'un chiffre soit inventé quand une donnée manque (on rend `null`) ;
     * que le mode TOITURE bouge (la clé `poseSurfaces` est additive, `zones`
       n'est jamais touchée).
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
  default: ModeTerrain, pasMesure, tauxOccupation, empriseTablesM2,
  contourTerrain, demandeMoteur, documentTerrain,
} = await import('../ModeTerrain')

/** Une réponse de moteur à la forme EXACTE du contrat `pose.json`. */
const REPONSE = {
  schema_version: 1,
  repere: 'TERRAIN',
  hash_entree: 'abc',
  version_moteur: '1.2.3',
  total_modules: 16,
  plans: [{
    surface: 'TERRAIN',
    modules: 16,
    rangees: [{ y0: 0, modules: 8 }, { y0: 6, modules: 8 }],
    tables: [
      { x0: 0, x1: 4, y0: 0, y1: 2.3, kit: 'terrain' },
      { x0: 4.5, x1: 8.5, y0: 0, y1: 2.3, kit: 'terrain' },
      { x0: 0, x1: 4, y0: 6, y1: 8.3, kit: 'terrain' },
      { x0: 4.5, x1: 8.5, y0: 6, y1: 8.3, kit: 'terrain' },
    ],
  }],
}

const SAISIE = {
  repere: 'TERRAIN',
  label: 'Champ au sol',
  largeurM: '20',
  profondeurM: '10',
  penteTerrainDeg: '3',
  rowAzimuthDeg: '180',
  tiltDeg: '25',
  moduleLongM: '2.278',
  moduleCourtM: '1.134',
  puissanceWc: '720',
  modulesParTable: '2',
  alleeM: '',
}

beforeEach(() => {
  vi.clearAllMocks()
  layout.mockResolvedValue({ data: { roof_layout: { zones: [{ id: 'PAN-A' }] } } })
  enregistrerLayoutCalepinage.mockResolvedValue({ data: {} })
  pose.mockResolvedValue({ data: REPONSE })
})
afterEach(() => { cleanup() })

const monter = (props = {}) => render(
  <MemoryRouter><ModeTerrain calepinageId={7} {...props} /></MemoryRouter>,
)

/* ── 1. LE PAS VIENT DU MOTEUR, JAMAIS D'UNE FORMULE LOCALE ────────────── */

describe('CAL89 — le pas inter-rangées est MESURÉ sur le plan du moteur', () => {
  it('deux rangées à 0 et 6 m ⇒ pas mesuré = 6 m', () => {
    expect(pasMesure(REPONSE.plans[0].rangees)).toBeCloseTo(6, 9)
  })

  it('moins de deux rangées ⇒ null (non mesurable), jamais une valeur de repli', () => {
    expect(pasMesure([{ y0: 0 }])).toBeNull()
    expect(pasMesure([])).toBeNull()
    expect(pasMesure(undefined)).toBeNull()
  })

  it('aucune constante de pas, aucun tan()/latitude dans l’écran — CAL88 est la seule physique', () => {
    const source = fs.readFileSync(
      path.join(RACINE_FRONTEND, 'src/features/calepinage/ModeTerrain.jsx'), 'utf8',
    )
    // Le fichier ne doit contenir AUCUNE trigonométrie de pas ni latitude.
    expect(source).not.toMatch(/Math\.tan\s*\(/)
    expect(source).not.toMatch(/latitude/i)
  })
})

/* ── 2. LE TAUX D'OCCUPATION EST UNE SORTIE ────────────────────────────── */

describe('CAL89 — le taux d’occupation du sol est une SORTIE', () => {
  it('= emprises des tables du moteur ÷ surface du terrain saisie', () => {
    const emprise = 4 * (4 * 2.3)
    expect(empriseTablesM2(REPONSE.plans[0].tables)).toBeCloseTo(emprise, 9)
    expect(tauxOccupation(REPONSE.plans[0].tables, 200)).toBeCloseTo(emprise / 200, 9)
  })

  it('surface de terrain absente ⇒ null, jamais 0 « par défaut »', () => {
    expect(tauxOccupation(REPONSE.plans[0].tables, null)).toBeNull()
    expect(tauxOccupation(REPONSE.plans[0].tables, 0)).toBeNull()
    expect(tauxOccupation([], 200)).toBeNull()
  })
})

/* ── 3. LA DEMANDE ENVOYÉE AU MOTEUR ───────────────────────────────────── */

describe('CAL89 — la demande moteur ne contient que des saisies', () => {
  it('le contour métrique est celui des dimensions saisies', () => {
    expect(contourTerrain('20', '10')).toEqual([[0, 0], [20, 0], [20, 10], [0, 10]])
    expect(contourTerrain('', '10')).toBeNull()
    expect(contourTerrain('0', '10')).toBeNull()
  })

  it('sans allée imposée, `allee_m` n’est PAS envoyé (le moteur applique sa politique)', () => {
    const d = demandeMoteur(SAISIE)
    expect(d.parametres.allee_m).toBeUndefined()
    expect(d.surfaces[0].contour).toEqual([[0, 0], [20, 0], [20, 10], [0, 10]])
    expect(d.surfaces[0].azimut_deg).toBe(180)
    expect(d.kits[0].module_long_m).toBe(2.278)
    expect(d.kits[0].inclinaison_deg).toBe(25)
  })

  it('une allée imposée est transmise telle quelle', () => {
    expect(demandeMoteur({ ...SAISIE, alleeM: '3.5' }).parametres.allee_m).toBe(3.5)
  })

  it('dimensions incomplètes ⇒ aucune demande (rien n’est complété d’office)', () => {
    expect(demandeMoteur({ ...SAISIE, moduleLongM: '' })).toBeNull()
    expect(demandeMoteur({ ...SAISIE, largeurM: '' })).toBeNull()
  })
})

/* ── 4. LE DOCUMENT PERSISTÉ ───────────────────────────────────────────── */

describe('CAL89 — la surface persistée recopie le moteur sans le refaire', () => {
  it('porte le genre `sol`, la saisie, et un bloc `engine` entièrement serveur', () => {
    const s = documentTerrain(SAISIE, REPONSE)
    expect(s.kind).toBe('sol')
    expect(s.areaM2).toBe(200)
    expect(s.terrainSlopeDeg).toBe(3)
    expect(s.tiltDeg).toBe(25)
    expect(s.engine.modules).toBe(16)
    expect(s.engine.rowPitchM).toBeCloseTo(6, 9)
    expect(s.engine.tables).toHaveLength(4)
    expect(s.engine.groundCoverageRatio).toBeCloseTo((4 * 4 * 2.3) / 200, 9)
    expect(s.engine.versionMoteur).toBe('1.2.3')
  })

  it('est VALIDE au regard du contrat v2 partagé (roof_layout_v2.schema.json)', () => {
    const schemaPath = path.join(
      racineDepot(),
      'backend/django_core/apps/calepinage/contract_samples/roof_layout_v2.schema.json',
    )
    const schema = JSON.parse(fs.readFileSync(schemaPath, 'utf8'))
    const def = schema.$defs.poseSurface
    // Le genre est bien déclaré, et chaque clé écrite par l'écran est décrite.
    expect(def.properties.kind.enum).toContain('sol')
    for (const cle of Object.keys(documentTerrain(SAISIE, REPONSE))) {
      expect(Object.keys(def.properties), `clé ${cle}`).toContain(cle)
    }
    const eng = schema.$defs.posePlanMoteur
    for (const cle of Object.keys(documentTerrain(SAISIE, REPONSE).engine)) {
      expect(Object.keys(eng.properties), `engine.${cle}`).toContain(cle)
    }
  })
})

/* ── 5. L'ÉCRAN : tracer, calculer, recharger — sans toucher la toiture ── */

describe('CAL89 — l’écran calcule, enregistre et recharge', () => {
  it('calcule via la porte moteur et affiche modules / pas / taux', async () => {
    monter()
    await waitFor(() => expect(layout).toHaveBeenCalled())
    for (const [cle, valeur] of Object.entries(SAISIE)) {
      const champ = screen.queryByTestId(`cal-terrain-${cle}`)
      if (champ) fireEvent.change(champ, { target: { value: valeur } })
    }
    fireEvent.click(screen.getByTestId('cal-terrain-calculer'))
    await waitFor(() => expect(pose).toHaveBeenCalled())
    expect(pose.mock.calls[0][0].demande.surfaces[0].contour).toHaveLength(4)
    await waitFor(() => {
      expect(screen.getByTestId('cal-terrain-modules').textContent).toContain('16')
    })
    expect(screen.getByTestId('cal-terrain-pas').textContent).toContain('6')
    expect(screen.getByTestId('cal-terrain-taux').textContent).toContain('%')
  })

  it('l’enregistrement AJOUTE `poseSurfaces` sans toucher `zones` (mode toiture intact)', async () => {
    monter()
    await waitFor(() => expect(layout).toHaveBeenCalled())
    for (const [cle, valeur] of Object.entries(SAISIE)) {
      const champ = screen.queryByTestId(`cal-terrain-${cle}`)
      if (champ) fireEvent.change(champ, { target: { value: valeur } })
    }
    fireEvent.click(screen.getByTestId('cal-terrain-calculer'))
    await waitFor(() => expect(pose).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('cal-terrain-enregistrer'))
    await waitFor(() => expect(enregistrerLayoutCalepinage).toHaveBeenCalled())
    const doc = enregistrerLayoutCalepinage.mock.calls[0][1]
    expect(doc.zones).toEqual([{ id: 'PAN-A' }]) // la toiture est intacte
    expect(doc.poseSurfaces).toHaveLength(1)
    expect(doc.poseSurfaces[0].kind).toBe('sol')
  })

  it('RECHARGE un champ déjà enregistré : saisie et plan reviennent', async () => {
    layout.mockResolvedValue({
      data: {
        roof_layout: {
          zones: [{ id: 'PAN-A' }],
          poseSurfaces: [documentTerrain(SAISIE, REPONSE)],
        },
      },
    })
    monter()
    await waitFor(() => expect(layout).toHaveBeenCalled())
    await waitFor(() => {
      expect(screen.getByTestId('cal-terrain-largeurM').value).toBe('20')
    })
    expect(screen.getByTestId('cal-terrain-tiltDeg').value).toBe('25')
    expect(screen.getByTestId('cal-terrain-modules').textContent).toContain('16')
  })

  it('refuse de calculer sur une saisie incomplète, et le DIT', async () => {
    monter()
    await waitFor(() => expect(layout).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('cal-terrain-calculer'))
    await waitFor(() => {
      expect(screen.getByTestId('cal-terrain-message').textContent).toMatch(/incomplètes/i)
    })
    expect(pose).not.toHaveBeenCalled()
  })
})

/* ── 6. L'ÉCRAN EST ATTEIGNABLE ────────────────────────────────────────── */

describe('CAL89 — la route est déclarée dans le module', () => {
  it('`/calepinage/:id/terrain` existe et monte ModeTerrain', async () => {
    const config = (await import('../module.config')).default
    const route = config.routes.find((r) => r.path === '/calepinage/:id/terrain')
    expect(route).toBeTruthy()
    expect(route.component).toBeTruthy()
    expect(route.roles).toContain('normal')
  })
})
