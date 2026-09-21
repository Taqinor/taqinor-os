import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import fs from 'node:fs'
import path from 'node:path'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

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

/* CALX50 — `@roofpro/scene3d` porte la couche WebGL (Three + MapLibre) : en CI
 * (job frontend-vitest-shard) seul `frontend/node_modules` est installé, donc
 * l'import dynamique que `ModeTerrain.jsx` fait de ce module échoue et l'écran
 * ne dessine rien (rouge mesuré sur PR #706, `cal-terrain-table` introuvable —
 * en local, la jonction vers `apps/web/node_modules` le fait résoudre, d'où le
 * vert local trompeur). On mocke ici SEULEMENT le placement
 * (`construireChampPose`) par la MÊME transformation géométrique pure que le
 * builder — x0/x1/y0/y1 moteur → centre + emprise, pas inter-rangées MESURÉ,
 * `nonMesure` — appliquée aux VRAIES tables/rangées de l'exemple de contrat
 * `pose.json` (`REPONSE` ci-dessus), donc les assertions existantes n'ont pas
 * besoin de changer. Le VRAI module reste exercé par ses propres tests
 * (`apps/web/src/scripts/roofPro11/*.test.ts`) — ici on ne teste QUE l'écran. */
const construireChampPose = vi.fn((plan, opts) => {
  const tablesMoteur = plan?.tables ?? []
  const tables = []
  let empriseTablesM2Calc = 0
  for (const t of tablesMoteur) {
    const largeurM = Math.abs(t.x1 - t.x0)
    const profondeurM = Math.abs(t.y1 - t.y0)
    empriseTablesM2Calc += largeurM * profondeurM
    tables.push({
      cx: (t.x0 + t.x1) / 2,
      cy: (t.y0 + t.y1) / 2,
      largeurM,
      profondeurM,
      z: Number.isFinite(opts?.hauteurLibreM) ? opts.hauteurLibreM : 0,
      inclinaisonRad: 0,
      kit: typeof t.kit === 'string' ? t.kit : null,
    })
  }
  const nonMesure = []
  if (!tables.length) nonMesure.push('aucune table rendue par le moteur')
  if (!Number.isFinite(opts?.penteTerrainDeg)) {
    nonMesure.push('pente du terrain non renseignée : terrain rendu horizontal')
  }

  const y = Array.from(new Set((plan?.rangees ?? [])
    .map((r) => Number(r?.y0)).filter((v) => Number.isFinite(v)))).sort((a, b) => a - b)
  let pasInterRangeeM = null
  if (y.length >= 2) {
    let min = Infinity
    for (let i = 1; i < y.length; i += 1) min = Math.min(min, y[i] - y[i - 1])
    pasInterRangeeM = Number.isFinite(min) && min > 0 ? min : null
  }
  if (pasInterRangeeM === null) {
    nonMesure.push('pas inter-rangées non mesurable (moins de deux rangées posées)')
  }

  const aire = Number.isFinite(opts?.aireTerrainM2) ? opts.aireTerrainM2 : null
  let tauxOccupationCalc = null
  if (aire !== null && aire > 0 && tables.length) tauxOccupationCalc = empriseTablesM2Calc / aire
  else nonMesure.push('taux d’occupation non calculable (surface du terrain manquante)')

  return {
    tables,
    modules: Number.isFinite(plan?.modules) ? plan.modules : null,
    pasInterRangeeM,
    empriseTablesM2: empriseTablesM2Calc,
    tauxOccupation: tauxOccupationCalc,
    nonMesure,
  }
})
vi.mock('@roofpro/scene3d', () => ({
  construireChampPose: (...args) => construireChampPose(...args),
}))

const {
  default: ModeTerrain, pasMesure, tauxOccupation, empriseTablesM2,
  contourTerrain, demandeMoteur, documentTerrain, planVue2D,
} = await import('../ModeTerrain')
const { formatCote } = await import('../plan2d')

/** La VRAIE réponse du moteur — l'exemple committé du contrat `pose.json`
 *  (PACT10/13 : un mock écrit à la main est une deuxième source de vérité,
 *  `scripts/check_api_shapes.py` le refuse). */
const REPONSE = exempleContrat('calepinage', 'pose')
/** Le pas inter-rangées, MESURÉ sur les rangées de l'exemple — jamais retapé. */
const PAS_REPONSE = REPONSE.plans[0].rangees[1].y0 - REPONSE.plans[0].rangees[0].y0
/** L'emprise totale des tables de l'exemple, par la même formule que `empriseTablesM2`. */
const EMPRISE_REPONSE = REPONSE.plans[0].tables.reduce(
  (acc, t) => acc + Math.abs(t.x1 - t.x0) * Math.abs(t.y1 - t.y0), 0,
)

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
  it('le pas mesuré = l’écart entre les deux `y0` de l’exemple de contrat', () => {
    expect(pasMesure(REPONSE.plans[0].rangees)).toBeCloseTo(PAS_REPONSE, 9)
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
    expect(empriseTablesM2(REPONSE.plans[0].tables)).toBeCloseTo(EMPRISE_REPONSE, 9)
    expect(tauxOccupation(REPONSE.plans[0].tables, 200)).toBeCloseTo(EMPRISE_REPONSE / 200, 9)
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
    expect(s.engine.modules).toBe(REPONSE.plans[0].modules)
    expect(s.engine.rowPitchM).toBeCloseTo(PAS_REPONSE, 9)
    expect(s.engine.tables).toHaveLength(REPONSE.plans[0].tables.length)
    expect(s.engine.groundCoverageRatio).toBeCloseTo(EMPRISE_REPONSE / 200, 9)
    expect(s.engine.versionMoteur).toBe(REPONSE.version_moteur)
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
      expect(screen.getByTestId('cal-terrain-modules').textContent)
        .toContain(String(REPONSE.plans[0].modules))
    })
    // L'écran arrondit le pas au dixième (`auDixieme`), comme le composant.
    expect(screen.getByTestId('cal-terrain-pas').textContent)
      .toContain(String(Math.round(PAS_REPONSE * 10) / 10))
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
    expect(screen.getByTestId('cal-terrain-modules').textContent)
      .toContain(String(REPONSE.plans[0].modules))
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

/* ── 6bis. CALX50 — LE CHAMP EST DESSINÉ, PAS SEULEMENT COMPTÉ ─────────── */

const remplir = (valeurs = SAISIE) => {
  for (const [cle, valeur] of Object.entries(valeurs)) {
    const champ = screen.queryByTestId(`cal-terrain-${cle}`)
    if (champ) fireEvent.change(champ, { target: { value: valeur } })
  }
}

describe('CALX50 — la mise en page du champ ne décide d’aucune géométrie', () => {
  const VUE = planVue2D({
    contourM: [[0, 0], [20, 0], [20, 10], [0, 10]],
    tables: [
      { cx: 2, cy: 1.5, largeurM: 2, profondeurM: 1 },
      { cx: 6, cy: 5.5, largeurM: 2, profondeurM: 1 },
    ],
    rangees: [{ y0: 1 }, { y0: 5 }],
    pasM: 4,
    compteModules: 12,
  })
  const longueur = (c) => Math.hypot(c.to[0] - c.from[0], c.to[1] - c.from[1])

  it('place le contour, une forme par table et une ligne par rangée', () => {
    expect(VUE.contour).toHaveLength(4)
    expect(VUE.tables).toHaveLength(2)
    expect(VUE.tables[0]).toHaveLength(4)
    expect(VUE.rangees).toHaveLength(2)
  })

  it('garde la MÊME échelle sur les deux axes (une cote reste lisible à la règle)', () => {
    expect(VUE.cotes[0].lengthM).toBeCloseTo(20, 9)
    expect(VUE.cotes[1].lengthM).toBeCloseTo(10, 9)
    expect(longueur(VUE.cotes[0]) / longueur(VUE.cotes[1])).toBeCloseTo(2, 9)
  })

  it('le trait de cote du pas mesure EXACTEMENT le pas reçu, pas un écart voisin', () => {
    expect(VUE.cotePas.lengthM).toBe(4)
    expect(longueur(VUE.cotePas)).toBeCloseTo(4 * VUE.pxParM, 9)
  })

  it('le compte est celui du moteur, RECOPIÉ — jamais le nombre de formes', () => {
    expect(VUE.compteModules).toBe(12)
    expect(VUE.tables).toHaveLength(2)
  })

  it('moins de trois sommets ⇒ rien n’est dessiné (jamais un champ supposé)', () => {
    expect(planVue2D({ contourM: [[0, 0], [1, 0]] })).toBeNull()
    expect(planVue2D({ contourM: null })).toBeNull()
    expect(planVue2D()).toBeNull()
  })

  it('sans rangée mesurable, aucun trait de pas n’est tracé', () => {
    const v = planVue2D({
      contourM: [[0, 0], [20, 0], [20, 10], [0, 10]],
      tables: [{ cx: 2, cy: 1.5, largeurM: 2, profondeurM: 1 }],
      rangees: [{ y0: 1 }],
      pasM: null,
    })
    expect(v.cotePas).toBeNull()
  })
})

describe('CALX50 — l’écran dessine le champ rendu par le moteur', () => {
  it('une forme par table du moteur, une ligne par rangée, et le pas MESURÉ coté', async () => {
    monter()
    await waitFor(() => expect(layout).toHaveBeenCalled())
    remplir()
    fireEvent.click(screen.getByTestId('cal-terrain-calculer'))
    await waitFor(() => expect(pose).toHaveBeenCalled())
    await waitFor(() => {
      expect(screen.getAllByTestId('cal-terrain-table'))
        .toHaveLength(REPONSE.plans[0].tables.length)
    })
    expect(screen.getAllByTestId('cal-terrain-rangee'))
      .toHaveLength(REPONSE.plans[0].rangees.length)
    // Le pas dessiné est celui qui est MESURÉ sur les rangées du moteur : la
    // même valeur que la tuile chiffrée, pas une seconde formule.
    expect(screen.getByTestId('cal-terrain-cote-pas').textContent)
      .toBe(formatCote(PAS_REPONSE))
  })

  it('le compte affiché reste celui du moteur, jamais le nombre de tables dessinées', async () => {
    // L'exemple de contrat pose 12 modules sur 2 tables : les deux nombres
    // diffèrent, donc un recomptage se verrait.
    expect(REPONSE.plans[0].modules).not.toBe(REPONSE.plans[0].tables.length)
    monter()
    await waitFor(() => expect(layout).toHaveBeenCalled())
    remplir()
    fireEvent.click(screen.getByTestId('cal-terrain-calculer'))
    await waitFor(() => expect(pose).toHaveBeenCalled())
    await waitFor(() => {
      expect(screen.getByTestId('cal-terrain-emprise').textContent)
        .toMatch(new RegExp(`${REPONSE.plans[0].modules} module`))
    })
    expect(screen.getByTestId('cal-terrain-emprise').textContent)
      .toMatch(new RegExp(`${REPONSE.plans[0].tables.length} table`))
  })

  it('pente non renseignée ⇒ « terrain rendu horizontal » est affiché tel quel', async () => {
    monter()
    await waitFor(() => expect(layout).toHaveBeenCalled())
    remplir({ ...SAISIE, penteTerrainDeg: '' })
    fireEvent.click(screen.getByTestId('cal-terrain-calculer'))
    await waitFor(() => expect(pose).toHaveBeenCalled())
    await waitFor(() => {
      expect(screen.getByTestId('cal-terrain-nonmesure').textContent)
        .toMatch(/terrain rendu horizontal/i)
    })
  })

  it('pente renseignée ⇒ la mention disparaît (rien n’est dit qui ne soit vrai)', async () => {
    monter()
    await waitFor(() => expect(layout).toHaveBeenCalled())
    remplir()
    fireEvent.click(screen.getByTestId('cal-terrain-calculer'))
    await waitFor(() => expect(pose).toHaveBeenCalled())
    await waitFor(() => {
      expect(screen.getAllByTestId('cal-terrain-table').length).toBeGreaterThan(0)
    })
    expect(screen.queryByTestId('cal-terrain-nonmesure')).toBeNull()
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
