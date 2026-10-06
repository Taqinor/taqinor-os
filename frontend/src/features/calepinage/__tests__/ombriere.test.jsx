import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import fs from 'node:fs'
import path from 'node:path'
import {
  espions, PAS_REPONSE_POSE, EMPRISE_REPONSE_POSE,
  verifierSectionEcrite, verifierLectureEnEchec, verifierSectionPousseeDansAtelier,
} from '../../../test/fixtures/calepinageApiMock'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

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

// ACAL345 — la doublure partagée de `calepinageApi` (document + `moteur.pose`).
const { layout, enregistrerLayoutCalepinage, enregistrerSectionLayout, pose } = espions
vi.mock('../../../api/calepinageApi', async () => (await import('../../../test/fixtures/calepinageApiMock')).apiDocument({ moteur: true }))

/* CALX51 — `@roofpro/scene3d` porte la couche WebGL (Three + MapLibre) : en CI
 * (job frontend-vitest-shard) seul `frontend/node_modules` est installé, donc
 * l'import dynamique que `Ombriere.jsx` fait de ce module échoue et l'écran ne
 * dessine rien (rouge mesuré sur PR #706, `cal-ombriere-travee` introuvable —
 * en local, la jonction vers `apps/web/node_modules` le fait résoudre, d'où le
 * vert local trompeur). On mocke ici SEULEMENT le placement
 * (`construireOmbriere`) par la MÊME transformation géométrique pure que le
 * builder — x0/x1/y0/y1 moteur → centre + emprise, couverture levée à la
 * hauteur libre SAISIE (ou pas levée du tout), `nonMesure` — appliquée aux
 * VRAIES tables/rangées de l'exemple de contrat `pose.json` (`REPONSE`
 * ci-dessus), donc les assertions existantes n'ont pas besoin de changer. Le
 * VRAI module reste exercé par ses propres tests
 * (`apps/web/src/scripts/roofPro11/*.test.ts`) — ici on ne teste QUE l'écran. */
const construireOmbriere = vi.fn((plan, opts) => {
  const hauteurConnue = Number.isFinite(opts?.hauteurLibreM) && opts.hauteurLibreM > 0
  const hauteurLibreM = hauteurConnue ? opts.hauteurLibreM : 0

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
      // Aucune pente n'est jamais transmise par `Ombriere.jsx` : l'altitude
      // est donc la même hauteur libre pour toutes les tables — comme le
      // fait le VRAI `construireChampPose` quand `tanPente` vaut 0.
      z: hauteurLibreM,
      inclinaisonRad: 0,
      kit: typeof t.kit === 'string' ? t.kit : null,
    })
  }

  const nonMesure = []
  if (!tables.length) nonMesure.push('aucune table rendue par le moteur')
  nonMesure.push('pente du terrain non renseignée : terrain rendu horizontal')

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

  if (!hauteurConnue) {
    nonMesure.push(
      'hauteur libre non renseignée : la couverture n’est pas levée (aucune hauteur supposée)',
    )
  }

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
  construireOmbriere: (...args) => construireOmbriere(...args),
}))

const {
  default: Ombriere, totauxParBatiment, coupeOmbriere,
} = await import('../Ombriere')
const { documentSurfacePose } = await import('../surfacePose')
/** ACAL25 — un seul survivant : l'ombrière est `documentSurfacePose(…, 'ombriere')`. */
const documentOmbriere = (saisie, reponse) => documentSurfacePose(saisie, reponse, 'ombriere')
const { formatCote } = await import('../plan2d')

/** La VRAIE réponse du moteur — l'exemple committé du contrat `pose.json`
 *  (PACT10/13 : un mock écrit à la main est une deuxième source de vérité,
 *  `scripts/check_api_shapes.py` le refuse). */
const REPONSE = exempleContrat('calepinage', 'pose')
const PAS_REPONSE = PAS_REPONSE_POSE
const EMPRISE_REPONSE = EMPRISE_REPONSE_POSE

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
      empreinte_document: 'E0',
    },
  })
  enregistrerLayoutCalepinage.mockResolvedValue({ data: {} })
  enregistrerSectionLayout.mockResolvedValue({ data: { empreinte_document: 'E1' } })
  pose.mockResolvedValue({ data: REPONSE })
})
afterEach(() => { cleanup() })

const monter = (props = {}) => render(
  <MemoryRouter><Ombriere calepinageId={9} {...props} /></MemoryRouter>,
)

const remplir = (valeurs = SAISIE) => {
  for (const [cle, valeur] of Object.entries(valeurs)) {
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
    expect(s.engine.modules).toBe(REPONSE.plans[0].modules)
    expect(s.engine.rowPitchM).toBeCloseTo(PAS_REPONSE, 9) // MESURÉ sur les rangées
    expect(s.engine.groundCoverageRatio).toBeCloseTo(EMPRISE_REPONSE / 60, 9)
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
      expect(screen.getByTestId('cal-ombriere-modules').textContent)
        .toContain(String(REPONSE.plans[0].modules))
    })
    // L'écran arrondit le pas au dixième (`auDixieme`), comme le composant.
    expect(screen.getByTestId('cal-ombriere-pas').textContent)
      .toContain(String(Math.round(PAS_REPONSE * 10) / 10))
  })

  it('l’ombrière apparaît dans le total de SON bâtiment, à côté du pan', async () => {
    monter()
    await waitFor(() => expect(layout).toHaveBeenCalled())
    remplir()
    fireEvent.click(screen.getByTestId('cal-ombriere-calculer'))
    await waitFor(() => expect(pose).toHaveBeenCalled())
    // BAT-A porte déjà 30 modules de pan (mock `layout` du `beforeEach`) ;
    // l'ombrière y ajoute les modules RENDUS PAR LE MOTEUR (exemple de contrat).
    await waitFor(() => {
      expect(screen.getByTestId('cal-ombriere-total-BAT-A').textContent)
        .toContain(String(30 + REPONSE.plans[0].modules))
    })
    // Le bâtiment voisin n'a pas bougé.
    expect(screen.getByTestId('cal-ombriere-total-BAT-B').textContent).toContain('10')
  })

  it('l’enregistrement écrit SEULEMENT `poseSurfaces` par section (la toiture n’est pas envoyée)', async () => {
    monter()
    await waitFor(() => expect(layout).toHaveBeenCalled())
    remplir()
    fireEvent.click(screen.getByTestId('cal-ombriere-calculer'))
    await waitFor(() => expect(pose).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('cal-ombriere-enregistrer'))
    await waitFor(() => expect(enregistrerSectionLayout).toHaveBeenCalled())
    verifierSectionEcrite({ id: 9, kind: 'ombriere' })
  })

  it('lecture en échec → Enregistrer désactivé, message affiché, aucun POST', async () => {
    await verifierLectureEnEchec({ monter, prefixe: 'cal-ombriere' })
  })

  it('pousse la section écrite dans l’atelier vivant', async () => {
    const documentVivant = { empreinte: 'EATELIER', appliquerSection: vi.fn() }
    monter({ documentVivant })
    await waitFor(() => expect(layout).toHaveBeenCalled())
    remplir()
    await verifierSectionPousseeDansAtelier({ documentVivant, prefixe: 'cal-ombriere', kind: 'ombriere' })
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
    expect(screen.getByTestId('cal-ombriere-modules').textContent)
      .toContain(String(REPONSE.plans[0].modules))
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

/* ── 5bis. CALX51 — L'OMBRIÈRE EST DESSINÉE À SA HAUTEUR LIBRE SAISIE ──── */

describe('CALX51 — la coupe lit l’altitude posée, elle n’en décide aucune', () => {
  it('pose le sol, une couverture par travée, et cote la hauteur quand il y en a une', () => {
    const c = coupeOmbriere({
      tables: [
        { cx: 1.5, cy: 1.2, largeurM: 3, profondeurM: 2, z: 2.2, inclinaisonRad: 0, kit: null },
        { cx: 5, cy: 1.2, largeurM: 3, profondeurM: 2, z: 2.2, inclinaisonRad: 0, kit: null },
      ],
    })
    expect(c.tables).toHaveLength(2)
    expect(c.altitudeM).toBe(2.2)
    expect(c.coteHauteur.lengthM).toBe(2.2)
    // La couverture est AU-DESSUS du sol dans le dessin (y écran plus petit).
    expect(c.tables[0].from[1]).toBeLessThan(c.sol.from[1])
  })

  it('altitude nulle ⇒ aucune cote de hauteur, la couverture reste sur le sol', () => {
    const c = coupeOmbriere({
      tables: [{ cx: 1.5, cy: 1.2, largeurM: 3, profondeurM: 2, z: 0, inclinaisonRad: 0, kit: null }],
    })
    expect(c.altitudeM).toBe(0)
    expect(c.coteHauteur).toBeNull()
    expect(c.tables[0].from[1]).toBeCloseTo(c.sol.from[1], 9)
  })

  it('aucune table ⇒ rien n’est dessiné (jamais une ombrière supposée)', () => {
    expect(coupeOmbriere({ tables: [] })).toBeNull()
    expect(coupeOmbriere()).toBeNull()
  })
})

describe('CALX51 — l’écran lève la couverture à la hauteur SAISIE, ou pas du tout', () => {
  it('hauteur libre saisie ⇒ l’altitude des travées est celle-là, et elle est cotée', async () => {
    monter()
    await waitFor(() => expect(layout).toHaveBeenCalled())
    remplir()
    fireEvent.click(screen.getByTestId('cal-ombriere-calculer'))
    await waitFor(() => expect(pose).toHaveBeenCalled())
    await waitFor(() => {
      expect(screen.getAllByTestId('cal-ombriere-travee'))
        .toHaveLength(REPONSE.plans[0].tables.length)
    })
    const altitude = Number(screen.getByTestId('cal-ombriere-altitude').dataset.altitudeM)
    expect(altitude).toBeGreaterThan(0)
    // C'est EXACTEMENT la hauteur libre saisie, pas une hauteur de confort.
    expect(altitude).toBe(Number(SAISIE.clearHeightM))
    expect(screen.getAllByTestId('cal-ombriere-couverture'))
      .toHaveLength(REPONSE.plans[0].tables.length)
    expect(screen.getByTestId('cal-ombriere-cote-hauteur').textContent)
      .toBe(formatCote(Number(SAISIE.clearHeightM)))
  })

  it('hauteur absente ⇒ altitude nulle, aucune cote, et la mention du service est visible', async () => {
    monter()
    await waitFor(() => expect(layout).toHaveBeenCalled())
    remplir({ ...SAISIE, clearHeightM: '' })
    fireEvent.click(screen.getByTestId('cal-ombriere-calculer'))
    await waitFor(() => expect(pose).toHaveBeenCalled())
    await waitFor(() => {
      expect(screen.getByTestId('cal-ombriere-altitude')).toBeTruthy()
    })
    expect(Number(screen.getByTestId('cal-ombriere-altitude').dataset.altitudeM)).toBe(0)
    expect(screen.queryByTestId('cal-ombriere-cote-hauteur')).toBeNull()
    const manques = screen.getByTestId('cal-ombriere-nonmesure').textContent
    expect(manques).toMatch(/hauteur libre non renseignée/i)
    expect(manques).toMatch(/aucune hauteur supposée/i)
  })

  it('le sens d’écoulement saisi est rendu avec le dessin', async () => {
    monter()
    await waitFor(() => expect(layout).toHaveBeenCalled())
    remplir()
    fireEvent.click(screen.getByTestId('cal-ombriere-calculer'))
    await waitFor(() => expect(pose).toHaveBeenCalled())
    await waitFor(() => {
      expect(screen.getByTestId('cal-ombriere-ecoulement').textContent)
        .toContain(`${SAISIE.flowAzimuthDeg}°`)
    })
  })

  it('AUCUNE hauteur de confort n’est écrite dans la source de l’écran', () => {
    const brut = fs.readFileSync(
      path.join(RACINE_FRONTEND, 'src/features/calepinage/Ombriere.jsx'), 'utf8',
    )
    // On juge le CODE, pas la prose : les commentaires (qui DISENT justement
    // qu'aucune hauteur n'est supposée) sont retirés avant la recherche.
    const source = brut.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
    expect(source).not.toMatch(/2[.,]5/)
    expect(source).not.toMatch(/hauteurParDefaut/i)
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

/* ── ACAL25 — module, allée, invalidation, surfaces par id ─────────────────── */

describe('ACAL25 — une seule fonction de surface de pose (module et allée persistés)', () => {
  const SAISIE_620 = {
    ...SAISIE,
    largeurM: '30',
    profondeurM: '10',
    moduleLongM: '2.38',
    moduleCourtM: '1.13',
    puissanceWc: '620',
    modulesParTable: '4',
    alleeM: '0',
  }

  it('l’ombrière 30×10, module 620 Wc, 4 modules/travée, allée 0 persiste module et allée', () => {
    const s = documentOmbriere(SAISIE_620, REPONSE)
    expect(s.moduleWc).toBe(620)
    expect(s.moduleLongM).toBe(2.38)
    expect(s.moduleCourtM).toBe(1.13)
    expect(s.modulesParTable).toBe(4)
    expect(s.alleeM).toBe(0) // 0 est une allée imposée, jamais « absente »
  })

  it('rouvrir une ombrière enregistrée remplit module et allée', async () => {
    layout.mockResolvedValue({
      data: {
        roof_layout: { zones: [], poseSurfaces: [documentOmbriere(SAISIE_620, REPONSE)] },
        empreinte_document: 'E0',
      },
    })
    monter()
    await waitFor(() => {
      expect(screen.getByTestId('cal-ombriere-puissanceWc').value).toBe('620')
    })
    expect(screen.getByTestId('cal-ombriere-moduleLongM').value).toBe('2.38')
    expect(screen.getByTestId('cal-ombriere-moduleCourtM').value).toBe('1.13')
    expect(screen.getByTestId('cal-ombriere-modulesParTable').value).toBe('4')
    expect(screen.getByTestId('cal-ombriere-alleeM').value).toBe('0')
  })

  it('enregistrer → rouvrir → enregistrer sans toucher ⇒ surface octet-identique', async () => {
    monter()
    await waitFor(() => expect(layout).toHaveBeenCalled())
    remplir(SAISIE_620)
    fireEvent.click(screen.getByTestId('cal-ombriere-calculer'))
    await waitFor(() => expect(pose).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('cal-ombriere-enregistrer'))
    await waitFor(() => expect(enregistrerSectionLayout).toHaveBeenCalledTimes(1))
    const premiere = enregistrerSectionLayout.mock.calls[0][1].valeur[0]
    cleanup()

    layout.mockResolvedValue({
      data: { roof_layout: { zones: [], poseSurfaces: [premiere] }, empreinte_document: 'E1' },
    })
    monter()
    await waitFor(() => {
      expect(screen.getByTestId('cal-ombriere-puissanceWc').value).toBe('620')
    })
    fireEvent.click(screen.getByTestId('cal-ombriere-enregistrer'))
    await waitFor(() => expect(enregistrerSectionLayout).toHaveBeenCalledTimes(2))
    const seconde = enregistrerSectionLayout.mock.calls[1][1].valeur[0]
    expect(JSON.stringify(seconde)).toBe(JSON.stringify(premiere))
  })

  it('changer la largeur après Calculer invalide le plan et désactive Enregistrer', async () => {
    monter()
    await waitFor(() => expect(layout).toHaveBeenCalled())
    remplir(SAISIE_620)
    fireEvent.click(screen.getByTestId('cal-ombriere-calculer'))
    await waitFor(() => expect(pose).toHaveBeenCalled())
    await waitFor(() => expect(screen.getByTestId('cal-ombriere-enregistrer')).not.toBeDisabled())
    fireEvent.change(screen.getByTestId('cal-ombriere-largeurM'), { target: { value: '80' } })
    expect(screen.getByTestId('cal-ombriere-enregistrer')).toBeDisabled()
    expect(screen.getByTestId('cal-ombriere-message').textContent).toMatch(/recalculez/i)
    fireEvent.click(screen.getByTestId('cal-ombriere-enregistrer'))
    expect(enregistrerSectionLayout).not.toHaveBeenCalled()
  })

  it('deux ombrières : en enregistrer une conserve l’autre ; la liste choisit celle rééditée', async () => {
    const A = documentOmbriere({ ...SAISIE_620, repere: 'OMB-A', label: 'Parking A' }, REPONSE)
    const B = documentOmbriere({ ...SAISIE_620, repere: 'OMB-B', label: 'Parking B', tiltDeg: '5' }, REPONSE)
    layout.mockResolvedValue({
      data: { roof_layout: { zones: [], poseSurfaces: [A, B] }, empreinte_document: 'E0' },
    })
    monter()
    await waitFor(() => {
      expect(screen.getByTestId('cal-ombriere-puissanceWc').value).toBe('620')
    })
    fireEvent.click(screen.getByRole('button', { name: 'Parking B (OMB-B)' }))
    expect(screen.getByTestId('cal-ombriere-tiltDeg').value).toBe('5')
    fireEvent.change(screen.getByTestId('cal-ombriere-tiltDeg'), { target: { value: '9' } })
    fireEvent.click(screen.getByTestId('cal-ombriere-calculer'))
    await waitFor(() => expect(pose).toHaveBeenCalled())
    await waitFor(() => expect(screen.getByTestId('cal-ombriere-enregistrer')).not.toBeDisabled())
    fireEvent.click(screen.getByTestId('cal-ombriere-enregistrer'))
    await waitFor(() => expect(enregistrerSectionLayout).toHaveBeenCalledTimes(1))
    const { valeur } = enregistrerSectionLayout.mock.calls[0][1]
    expect(valeur).toHaveLength(2)
    expect(valeur[0]).toEqual(A)
    expect(valeur[1].id).toBe('OMB-B')
    expect(valeur[1].tiltDeg).toBe(9)
  })

  it('« Supprimer cette surface » retire la surface par section', async () => {
    const A = documentOmbriere({ ...SAISIE_620, repere: 'OMB-A' }, REPONSE)
    const B = documentOmbriere({ ...SAISIE_620, repere: 'OMB-B' }, REPONSE)
    layout.mockResolvedValue({
      data: { roof_layout: { zones: [], poseSurfaces: [A, B] }, empreinte_document: 'E0' },
    })
    monter()
    await waitFor(() => {
      expect(screen.getByTestId('cal-ombriere-puissanceWc').value).toBe('620')
    })
    fireEvent.click(screen.getByText('Supprimer cette surface'))
    await waitFor(() => expect(enregistrerSectionLayout).toHaveBeenCalledTimes(1))
    const corps = enregistrerSectionLayout.mock.calls[0][1]
    expect(corps.cle).toBe('poseSurfaces')
    expect(corps.valeur).toEqual([B])
  })
})

/* ── ACAL75 — l'ombrière est une couverture continue : allée vide = pose jointive ── */

describe('ACAL75 — allée vide : pose jointive (allee_m 0), politique affichée', () => {
  it('allée vide → demande moteur allee_m 0 et mention pose jointive', async () => {
    monter()
    await waitFor(() => expect(layout).toHaveBeenCalled())
    remplir({ ...SAISIE, alleeM: '' })
    expect(screen.getByText(/Pose jointive \(allée 0\) — saisissez une allée pour en imposer une/))
      .toBeInTheDocument()
    fireEvent.click(screen.getByTestId('cal-ombriere-calculer'))
    await waitFor(() => expect(pose).toHaveBeenCalled())
    // Le moteur reçoit la couverture continue, pas son allée de circulation (0,60 m).
    expect(pose.mock.calls[0][0].demande.parametres.allee_m).toBe(0)
  })

  it('allée saisie → envoyée telle quelle, et la mention pose jointive disparaît', async () => {
    monter()
    await waitFor(() => expect(layout).toHaveBeenCalled())
    remplir({ ...SAISIE, alleeM: '1.2' })
    expect(screen.queryByText(/Pose jointive/)).not.toBeInTheDocument()
    fireEvent.click(screen.getByTestId('cal-ombriere-calculer'))
    await waitFor(() => expect(pose).toHaveBeenCalled())
    expect(pose.mock.calls[0][0].demande.parametres.allee_m).toBe(1.2)
  })

  it('l’allée vide reste persistée null (le défaut jointif n’est pas une saisie)', () => {
    expect(documentOmbriere({ ...SAISIE, alleeM: '' }, REPONSE).alleeM).toBeNull()
  })
})
