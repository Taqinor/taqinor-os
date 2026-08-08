import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

/* ============================================================================
   AOF103 + PACT172 — Done = aucune phrase de verdict en dur dans le code (le
   verdict vient TOUJOURS du serveur), un cas « tenu sauf » testé, tableau
   lisible sur tablette, appel réseau vers l'endpoint RÉEL
   (`aoApi.calepinage.variantes.sensibilites`), forme de réponse RÉELLE
   (`calepinage_service.calculer_sensibilites` : reference_modules /
   plancher_modules / engagement_modules / verdict / non_applicables /
   sensibilites — jamais lignes/plancher, qui n'ont jamais existé côté
   serveur).
   ========================================================================== */

const mocks = vi.hoisted(() => ({ sensibilites: vi.fn() }))

vi.mock('../../../api/aoApi', () => ({
  default: { calepinage: { variantes: { sensibilites: mocks.sensibilites } } },
}))

import SensibilitesPanel, { lignesSensibilites, lignesPlancher } from './SensibilitesPanel'

// Sensibilités : forme RÉELLE de `calculer_sensibilites` (code/libelle/modules/
// delta/tenu) — les libellés viennent du SERVEUR (jamais du front).
const S = (code, libelle, modules, delta, tenu) => ({ code, libelle, modules, delta, tenu })

const TOUT_TENU = {
  reference_modules: 314,
  plancher_modules: 288,
  engagement_modules: 280,
  verdict: 'engagement tenu partout : plancher 288 modules pour un engagement de 280 (3 variantes défavorables rejouées)',
  non_applicables: [],
  sensibilites: [
    S('PORTRAIT', '100 % portrait — impact chiffré de -12 modules', 302, -12, true),
    S('PAYSAGE', '100 % paysage — impact chiffré de -18 modules', 296, -18, true),
    S('ALLEE_190', 'allée de maintenance de 1,90 m — impact chiffré de -26 modules', 288, -26, true),
  ],
}

const TENU_SAUF = {
  ...TOUT_TENU,
  engagement_modules: 300,
  verdict: 'engagement tenu sauf PAYSAGE (296), ALLEE_190 (288) : plancher 288 modules pour un engagement de 300',
  sensibilites: [
    S('PORTRAIT', '100 % portrait — impact chiffré de -12 modules', 302, -12, true),
    S('PAYSAGE', '100 % paysage — impact chiffré de -18 modules', 296, -18, false),
    S('ALLEE_190', 'allée de maintenance de 1,90 m — impact chiffré de -26 modules', 288, -26, false),
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.sensibilites.mockResolvedValue({ data: TOUT_TENU })
})

describe('lignesSensibilites — la RÉFÉRENCE suivie des sensibilités SERVEUR', () => {
  it('place la référence en tête, delta 0, jamais recalculé', () => {
    const lignes = lignesSensibilites({
      referenceModules: 314, engagementModules: 280, sensibilites: TOUT_TENU.sensibilites,
    })
    expect(lignes).toHaveLength(4)
    expect(lignes[0]).toMatchObject({ cle: 'reference', modules: 314, delta: 0, tenu: true })
  })

  it('sans référence : aucune ligne (jamais un tableau fondé sur du vide)', () => {
    expect(lignesSensibilites({ referenceModules: null, sensibilites: TOUT_TENU.sensibilites })).toEqual([])
  })

  it('la référence est INCOMPLÈTE (non évaluée) sans engagement déclaré', () => {
    const lignes = lignesSensibilites({ referenceModules: 314, engagementModules: null, sensibilites: [] })
    expect(lignes[0].tenu).toBeNull()
  })
})

describe('lignesPlancher — sélection parmi des nombres SERVEUR, jamais un recalcul', () => {
  it('retient la ou les lignes dont `modules` égale le plancher publié', () => {
    const lignes = lignesSensibilites({
      referenceModules: TENU_SAUF.reference_modules,
      engagementModules: TENU_SAUF.engagement_modules,
      sensibilites: TENU_SAUF.sensibilites,
    })
    const p = lignesPlancher(lignes, TENU_SAUF.plancher_modules)
    expect(p).toHaveLength(1)
    expect(p[0].cle).toBe('ALLEE_190')
  })

  it('sans plancher publié : aucune ligne marquée', () => {
    expect(lignesPlancher([{ cle: 'x', modules: 10 }], null)).toEqual([])
  })
})

describe('SensibilitesPanel — rendu', () => {
  it('appelle le VRAI endpoint porté par la variante, jamais l’ancien endpoint « calepinage »', async () => {
    render(<SensibilitesPanel varianteId={42} />)
    await screen.findByText(/engagement tenu partout/)
    expect(mocks.sensibilites).toHaveBeenCalledWith(42)
  })

  it('affiche le verdict SERVEUR tel quel, dans une région annoncée (aria-live)', async () => {
    render(<SensibilitesPanel varianteId={42} />)
    const phrase = await screen.findByText(/engagement tenu partout/)
    expect(phrase).toHaveAttribute('aria-live', 'polite')
    expect(phrase.textContent).toBe(TOUT_TENU.verdict)
  })

  it('cas « tenu sauf » : le verdict SERVEUR et les verdicts de ligne viennent du payload', async () => {
    mocks.sensibilites.mockResolvedValue({ data: TENU_SAUF })
    render(<SensibilitesPanel varianteId={42} />)
    expect(await screen.findByText(TENU_SAUF.verdict)).toBeInTheDocument()
    // Référence + PORTRAIT tenus (OK), PAYSAGE + ALLEE_190 fautifs (Bloquant).
    expect(screen.getAllByText('Bloquant')).toHaveLength(2)
    expect(screen.getAllByText('OK')).toHaveLength(2)
  })

  it('met le PLANCHER en évidence sur sa ligne (comparaison de nombres serveur)', async () => {
    mocks.sensibilites.mockResolvedValue({ data: TENU_SAUF })
    render(<SensibilitesPanel varianteId={42} />)
    await screen.findByText(TENU_SAUF.verdict)
    const marqueur = screen.getByText('Plancher')
    expect(marqueur.closest('tr').textContent).toContain('1,90')
  })

  it('scénarios non applicables : phrases SERVEUR affichées telles quelles', async () => {
    mocks.sensibilites.mockResolvedValue({
      data: { ...TOUT_TENU, non_applicables: ['non-cotés : aucun obstacle non coté dans ce relevé'] },
    })
    render(<SensibilitesPanel varianteId={42} />)
    await screen.findByText(TOUT_TENU.verdict)
    expect(screen.getByText('non-cotés : aucun obstacle non coté dans ce relevé')).toBeInTheDocument()
  })

  it('tableau lisible sur tablette : défilement horizontal DANS son conteneur, en-têtes portées', async () => {
    const { container } = render(<SensibilitesPanel varianteId={42} />)
    await screen.findByText(/engagement tenu partout/)
    const table = container.querySelector('table')
    expect(table.parentElement.className).toContain('overflow-x-auto')
    expect(container.querySelector('table caption')).not.toBeNull()
    expect(container.querySelectorAll('thead th[scope="col"]')).toHaveLength(4)
    // Référence + 3 sensibilités.
    expect(container.querySelectorAll('tbody th[scope="row"]')).toHaveLength(4)
  })

  it('erreur réseau : message nommé, jamais un tableau fantôme', async () => {
    mocks.sensibilites.mockRejectedValue({ response: { data: { detail: 'panne' } } })
    render(<SensibilitesPanel varianteId={42} />)
    expect(await screen.findByText('Impossible de charger les sensibilités')).toBeInTheDocument()
  })

  it('aucune sensibilité calculée (pas de référence) : état vide nommé, jamais un tableau fantôme', async () => {
    mocks.sensibilites.mockResolvedValue({ data: { reference_modules: null, sensibilites: [] } })
    render(<SensibilitesPanel varianteId={42} />)
    expect(await screen.findByText('Aucune sensibilité calculée')).toBeInTheDocument()
  })
})

/* ── Contrat de SOURCE : aucun libellé de scénario, aucune phrase de verdict
      pré-écrite ne peut se glisser dans le composant. ───────────────────── */
describe('SensibilitesPanel.jsx — contrat de source', () => {
  const here = dirname(fileURLToPath(import.meta.url))
  const src = readFileSync(join(here, 'SensibilitesPanel.jsx'), 'utf8')
  // Le bandeau de commentaire cite les scénarios pour documenter le contrat :
  // le contrat de source porte sur le CODE, pas sur la documentation.
  const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')

  it('ne contient AUCUN libellé de scénario (ils viennent tous du serveur)', () => {
    expect(code).not.toMatch(/100 % portrait|100 % paysage|dégagement maximal|segments raccourcis/i)
  })

  it('n’appelle plus jamais l’ancien endpoint « calepinage » (calepinages.sensibilites)', () => {
    expect(code).not.toMatch(/calepinages\.sensibilites/)
    expect(code).toMatch(/calepinage\.variantes\.sensibilites/)
  })

  it('n’assemble AUCUNE phrase de verdict : le composant AFFICHE `data.verdict`, il ne le compose pas', () => {
    expect(code).toMatch(/\{data\.verdict\}/)
    expect(code).not.toMatch(/tenu partout|tenu sauf/i)
  })

  it('lit le verdict SERVEUR par ligne (`tenu`), jamais une comparaison locale au compte', () => {
    expect(code).toMatch(/typeof ligne\.tenu !== 'boolean'/)
    expect(code).not.toMatch(/compte_modules\s*[<>]=?\s*engagement/)
  })
})
