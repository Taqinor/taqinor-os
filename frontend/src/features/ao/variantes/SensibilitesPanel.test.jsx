import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

/* ============================================================================
   AOF103 — Done = aucune phrase de verdict en dur dans le code, un cas
   « tenu sauf » testé, tableau lisible sur tablette.
   ========================================================================== */

const mocks = vi.hoisted(() => ({ sensibilites: vi.fn() }))

vi.mock('../../../api/aoApi', () => ({
  default: { calepinages: { sensibilites: mocks.sensibilites } },
}))

import SensibilitesPanel, { construirePhrase, lignePlancher } from './SensibilitesPanel'

// Libellés de scénarios : ils viennent du SERVEUR (jamais du front).
const L = (cle, libelle, compte, tenu, ecart) => ({
  cle, libelle, compte_modules: compte, puissance_kwc: compte * 0.55, tenu, ecart_engagement_modules: ecart,
})

const TOUT_TENU = {
  engagement_modules: 280,
  plancher: { cle: 'allee_190', compte_modules: 288 },
  lignes: [
    L('portrait', '100 % portrait', 302, true, 22),
    L('paysage', '100 % paysage', 296, true, 16),
    L('allee_190', 'Allées 1,90 m', 288, true, 8),
  ],
}

const TENU_SAUF = {
  engagement_modules: 300,
  plancher: { cle: 'allee_190', compte_modules: 288 },
  lignes: [
    L('portrait', '100 % portrait', 302, true, 2),
    L('paysage', '100 % paysage', 296, false, -4),
    L('allee_190', 'Allées 1,90 m', 288, false, -12),
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.sensibilites.mockResolvedValue({ data: TOUT_TENU })
})

describe('construirePhrase — la phrase est COMPOSÉE, jamais rédigée', () => {
  it('tous les scénarios tenus : « tenu partout » avec le compte et l’engagement du payload', () => {
    expect(construirePhrase({ lignes: TOUT_TENU.lignes, engagementModules: 280 }))
      .toBe('Engagement tenu partout (engagement : 280 modules) — 3 scénario(s) défavorable(s) testé(s).')
  })

  it('cas « tenu sauf » : énumère EXACTEMENT les libellés SERVEUR des scénarios fautifs', () => {
    expect(construirePhrase({ lignes: TENU_SAUF.lignes, engagementModules: 300 }))
      .toBe('Engagement tenu sauf : 100 % paysage, Allées 1,90 m (engagement : 300 modules).')
  })

  it('un scénario non évalué rend le verdict INCOMPLET (jamais un « tenu partout » optimiste)', () => {
    const lignes = [L('portrait', '100 % portrait', 302, true, 2), { cle: 'x', libelle: 'Cotes douteuses au pire', compte_modules: null }]
    expect(construirePhrase({ lignes, engagementModules: 300 }))
      .toBe('Verdict incomplet : 1 scénario(s) non évalué(s) — Cotes douteuses au pire.')
  })

  it('aucune ligne : aucune phrase (jamais un verdict sur du vide)', () => {
    expect(construirePhrase({ lignes: [], engagementModules: 300 })).toBe('')
  })
})

describe('lignePlancher', () => {
  it('respecte le plancher DÉSIGNÉ par le serveur', () => {
    const p = lignePlancher(TENU_SAUF.lignes, TENU_SAUF.plancher)
    expect(p.ligne.cle).toBe('allee_190')
    expect(p.deduit).toBe(false)
  })

  it('à défaut, SÉLECTIONNE le plus petit compte et le signale comme déduit', () => {
    const p = lignePlancher(TENU_SAUF.lignes, null)
    expect(p.ligne.cle).toBe('allee_190')
    expect(p.deduit).toBe(true)
  })
})

describe('SensibilitesPanel — rendu', () => {
  it('affiche la phrase générée dans une région annoncée (aria-live)', async () => {
    render(<SensibilitesPanel calepinageId={3} />)
    const phrase = await screen.findByText(/Engagement tenu partout/)
    expect(phrase).toHaveAttribute('aria-live', 'polite')
  })

  it('cas « tenu sauf » : la phrase et les verdicts de ligne viennent du payload', async () => {
    mocks.sensibilites.mockResolvedValue({ data: TENU_SAUF })
    render(<SensibilitesPanel calepinageId={3} />)
    expect(await screen.findByText(/Engagement tenu sauf : 100 % paysage, Allées 1,90 m/)).toBeInTheDocument()
    expect(screen.getAllByText('Bloquant')).toHaveLength(2)
    expect(screen.getAllByText('OK')).toHaveLength(1)
  })

  it('met le PLANCHER en évidence sur sa ligne', async () => {
    mocks.sensibilites.mockResolvedValue({ data: TENU_SAUF })
    render(<SensibilitesPanel calepinageId={3} />)
    await screen.findByText(/Engagement tenu sauf/)
    const marqueur = screen.getByText('Plancher')
    expect(marqueur.closest('tr').textContent).toContain('Allées 1,90 m')
  })

  it('tableau lisible sur tablette : défilement horizontal DANS son conteneur, en-têtes portées', async () => {
    const { container } = render(<SensibilitesPanel calepinageId={3} />)
    await screen.findByText(/Engagement tenu partout/)
    const table = container.querySelector('table')
    expect(table.parentElement.className).toContain('overflow-x-auto')
    expect(container.querySelector('table caption')).not.toBeNull()
    expect(container.querySelectorAll('thead th[scope="col"]')).toHaveLength(5)
    expect(container.querySelectorAll('tbody th[scope="row"]')).toHaveLength(3)
  })

  it('aucune sensibilité calculée : état vide nommé, jamais un tableau fantôme', async () => {
    mocks.sensibilites.mockResolvedValue({ data: { lignes: [] } })
    render(<SensibilitesPanel calepinageId={3} />)
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
    expect(code).not.toMatch(/portrait|paysage|dégagement maximal|segments raccourcis|1,90|1,20/i)
  })

  it('ne contient AUCUNE phrase de verdict pré-écrite pour un cas particulier', () => {
    // Les seules occurrences autorisées sont la CHARPENTE (préfixes) — jamais
    // une phrase complète qui nommerait un scénario ou un chiffre.
    expect(code).not.toMatch(/tenu sauf[^`'"]*(portrait|paysage|allée)/i)
    expect(code).toMatch(/fautives\.map\(\(l\) => l\.libelle\)\.join/)
  })

  it('lit le verdict SERVEUR par ligne (`tenu`), jamais une comparaison locale au compte', () => {
    expect(code).toMatch(/typeof ligne\.tenu !== 'boolean'/)
    expect(code).not.toMatch(/compte_modules\s*[<>]=?\s*engagement/)
  })
})
