import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

/* ============================================================================
   AOF105 — Done = revenir à une version antérieure est possible ET tracé dans
   le chatter `records` de l'affaire, la superposition est lisible, test du
   CALCUL DE DIFFÉRENCE DE RANGÉES.
   ----------------------------------------------------------------------------
   Ce fichier est le seul fichier de test déclaré par AOF105 : il couvre donc
   `DiffPlan` (diff + superposition) ET `HistoriqueVersions` (liste + retour à
   une version, non recodé en chatter local).
   ========================================================================== */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  update: vi.fn(),
  confirm: vi.fn(),
}))

vi.mock('../../../api/aoApi', () => ({
  default: { calepinages: { list: mocks.list, update: mocks.update } },
}))

// `useConfirmDialog` s'appuie sur le ConfirmProvider monté à la racine de
// l'app : on le remplace ici pour tester la décision, pas le provider.
vi.mock('../../../ui/confirm', () => ({
  useConfirmDialog: () => ({ confirm: mocks.confirm, confirmDelete: mocks.confirm }),
  toast: { success: vi.fn(), error: vi.fn() },
  toastPromise: (p) => p,
}))

import DiffPlan, { diffRangees, deltaCompte } from './DiffPlan'
import HistoriqueVersions from './HistoriqueVersions'

const R = (cle, y, x0, x1, tables) => ({ cle, y, x0, x1, tables })

// Version A : 4 rangées. Version B : r2 modifiée (allée resserrée), r3
// SUPPRIMÉE, r5 AJOUTÉE — et r4 inchangée mais DÉPLACÉE dans le tableau, ce
// qui piégerait un appariement par index.
const RANGEES_A = [R('r1', 0, 0, 12, 6), R('r2', 2, 0, 12, 6), R('r3', 4, 0, 8, 4), R('r4', 6, 0, 12, 6)]
const RANGEES_B = [R('r1', 0, 0, 12, 6), R('r4', 6, 0, 12, 6), R('r2', 1.8, 0, 12, 7), R('r5', 8, 0, 10, 5)]

const VERSION_A = { id: 1, libelle: 'v1', plan: { rangees: RANGEES_A, compte_modules: 112 } }
const VERSION_B = { id: 2, libelle: 'v2', plan: { rangees: RANGEES_B, compte_modules: 126 } }

describe('diffRangees — le calcul de différence de rangées', () => {
  const d = diffRangees(RANGEES_A, RANGEES_B)

  it('détecte les rangées AJOUTÉES (présentes en B seulement)', () => {
    expect(d.ajoutees.map((r) => r.cle)).toEqual(['r5'])
  })

  it('détecte les rangées RETIRÉES (présentes en A seulement)', () => {
    expect(d.retirees.map((r) => r.cle)).toEqual(['r3'])
  })

  it('détecte les rangées MODIFIÉES et NOMME les champs qui ont bougé', () => {
    expect(d.modifiees).toHaveLength(1)
    expect(d.modifiees[0].cle).toBe('r2')
    expect(d.modifiees[0].champs).toEqual(['y', 'tables'])
    expect(d.modifiees[0].avant.y).toBe(2)
    expect(d.modifiees[0].apres.y).toBe(1.8)
  })

  it('apparie par `cle`, JAMAIS par l’ordre du tableau (r4 déplacée reste inchangée)', () => {
    expect(d.inchangees.map((r) => r.cle).sort()).toEqual(['r1', 'r4'])
  })

  it('deux plans identiques ne produisent AUCUNE différence', () => {
    const same = diffRangees(RANGEES_A, RANGEES_A)
    expect(same.ajoutees).toEqual([])
    expect(same.retirees).toEqual([])
    expect(same.modifiees).toEqual([])
    expect(same.inchangees).toHaveLength(4)
  })

  it('un plan vide côté A rend TOUTES les rangées de B comme ajoutées', () => {
    const d0 = diffRangees([], RANGEES_B)
    expect(d0.ajoutees).toHaveLength(4)
    expect(d0.retirees).toEqual([])
  })
})

describe('deltaCompte — soustraction d’AFFICHAGE entre deux comptes serveur', () => {
  it('rend le delta signé', () => {
    expect(deltaCompte(VERSION_A.plan, VERSION_B.plan)).toBe(14)
    expect(deltaCompte(VERSION_B.plan, VERSION_A.plan)).toBe(-14)
  })

  it('rend null si l’un des deux comptes manque (jamais un delta inventé)', () => {
    expect(deltaCompte({ compte_modules: 112 }, {})).toBeNull()
    expect(deltaCompte(null, VERSION_B.plan)).toBeNull()
  })
})

describe('DiffPlan — superposition lisible', () => {
  it('affiche le delta de compte signé', () => {
    render(<DiffPlan versionA={VERSION_A} versionB={VERSION_B} />)
    expect(screen.getByText('Delta de compte : +14 module(s)')).toBeInTheDocument()
  })

  it('dessine chaque rangée avec sa NATURE de différence', () => {
    const { container } = render(<DiffPlan versionA={VERSION_A} versionB={VERSION_B} />)
    expect(container.querySelectorAll('g[data-nature="ajoutee"]')).toHaveLength(1)
    expect(container.querySelectorAll('g[data-nature="retiree"]')).toHaveLength(1)
    expect(container.querySelectorAll('g[data-nature="modifiee"]')).toHaveLength(1)
    expect(container.querySelectorAll('g[data-nature="inchangee"]')).toHaveLength(2)
  })

  it('la couleur n’est jamais le seul signal : chaque nature est aussi COMPTÉE en toutes lettres', () => {
    render(<DiffPlan versionA={VERSION_A} versionB={VERSION_B} />)
    expect(screen.getByText('Rangée ajoutée : 1')).toBeInTheDocument()
    expect(screen.getByText('Rangée retirée : 1')).toBeInTheDocument()
    expect(screen.getByText('Rangée modifiée : 1')).toBeInTheDocument()
    expect(screen.getByText('Rangée inchangée : 2')).toBeInTheDocument()
  })

  it('détaille en texte ce qui a bougé sur une rangée modifiée', () => {
    render(<DiffPlan versionA={VERSION_A} versionB={VERSION_B} />)
    expect(screen.getByText(/Rangée r2 — y, tables/)).toBeInTheDocument()
  })

  it('deux versions sans rangées : message explicite, jamais un dessin vide', () => {
    render(<DiffPlan versionA={{ plan: { rangees: [] } }} versionB={{ plan: { rangees: [] } }} />)
    expect(screen.getByText(/Aucun plan à superposer/)).toBeInTheDocument()
  })
})

/* ── HistoriqueVersions ──────────────────────────────────────────────────── */

const VERSIONS = [
  { id: 2, libelle: 'v2', auteur: 'Meryem', cree_le: '2026-07-27T10:00:00Z', parametres: { allee: '1,20 m' }, courante: true, plan: { rangees: RANGEES_B, compte_modules: 126 } },
  { id: 1, libelle: 'v1', auteur: 'Reda', cree_le: '2026-07-20T09:00:00Z', parametres: { allee: '1,90 m' }, courante: false, plan: { rangees: RANGEES_A, compte_modules: 112 } },
]

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: VERSIONS })
  mocks.update.mockResolvedValue({ data: {} })
  mocks.confirm.mockResolvedValue(true)
})

describe('HistoriqueVersions — liste et retour à une version', () => {
  it('liste auteur, date, paramètres et compte de chaque version', async () => {
    render(<HistoriqueVersions calepinageId={9} />)
    expect(await screen.findByText('Meryem')).toBeInTheDocument()
    expect(screen.getByText('Reda')).toBeInTheDocument()
    expect(screen.getByText('allee : 1,20 m')).toBeInTheDocument()
    expect(screen.getByText('126')).toBeInTheDocument()
    expect(screen.getByText('112')).toBeInTheDocument()
  })

  it('superpose par défaut la plus ancienne (A) et la plus récente (B)', async () => {
    render(<HistoriqueVersions calepinageId={9} />)
    expect(await screen.findByText(/Superposition v1 → v2/)).toBeInTheDocument()
    expect(screen.getByText('Delta de compte : +14 module(s)')).toBeInTheDocument()
  })

  it('le retour à une version DEMANDE confirmation (jamais un window.confirm) puis PATCHe le serveur', async () => {
    const user = userEvent.setup()
    render(<HistoriqueVersions calepinageId={9} />)
    await screen.findByText('Reda')
    await user.click(screen.getByRole('button', { name: 'Revenir à cette version' }))
    await waitFor(() => expect(mocks.confirm).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith(9, { restaurer_version: 1 }))
  })

  it('confirmation refusée : aucun appel serveur', async () => {
    mocks.confirm.mockResolvedValue(false)
    const user = userEvent.setup()
    render(<HistoriqueVersions calepinageId={9} />)
    await screen.findByText('Reda')
    await user.click(screen.getByRole('button', { name: 'Revenir à cette version' }))
    await waitFor(() => expect(mocks.confirm).toHaveBeenCalled())
    expect(mocks.update).not.toHaveBeenCalled()
  })

  it('la version courante n’offre PAS de bouton de retour', async () => {
    render(<HistoriqueVersions calepinageId={9} />)
    await screen.findByText('Reda')
    expect(screen.getAllByRole('button', { name: 'Revenir à cette version' })).toHaveLength(1)
    expect(screen.getByText('Version courante')).toBeInTheDocument()
  })

  it('historique vide : état nommé, jamais un tableau fantôme', async () => {
    mocks.list.mockResolvedValue({ data: [] })
    render(<HistoriqueVersions calepinageId={9} />)
    expect(await screen.findByText('Aucune version enregistrée')).toBeInTheDocument()
  })
})

/* ── Contrat de source : le chatter est une primitive PLATEFORME ─────────── */
describe('HistoriqueVersions.jsx — contrat de source', () => {
  const here = dirname(fileURLToPath(import.meta.url))
  const src = readFileSync(join(here, 'HistoriqueVersions.jsx'), 'utf8')

  it('n’écrit AUCUNE entrée de chatter côté front (la trace est serveur)', () => {
    expect(src).not.toMatch(/chatter\w*\.(post|create)|LeadActivity|\/historique\/|\/noter\//)
    expect(src).toMatch(/restaurer_version/)
  })

  it('n’utilise aucun window.confirm / alert / prompt (gate a11y AOF188)', () => {
    expect(src).not.toMatch(/window\.(confirm|alert|prompt)\s*\(/)
    expect(src).toMatch(/useConfirmDialog/)
  })
})
