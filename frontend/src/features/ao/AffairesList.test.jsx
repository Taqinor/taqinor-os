import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  dupliquer: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
  navigate: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mocks.navigate }
})

vi.mock('../../api/aoApi', () => ({
  default: {
    affaires: {
      list: mocks.list,
      dupliquer: mocks.dupliquer,
      update: mocks.update,
      remove: mocks.remove,
    },
  },
}))

import AffairesList from './AffairesList'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

// `ListShell` rend un `DataTable`, qui lit la densité via `useDensity()` →
// `useTheme()` : sans `<ThemeProvider>` ancêtre, le hook JETTE (« useTheme doit
// être utilisé dans <ThemeProvider> ») et l'écran ne rend rien. C'est le
// patron de test de TOUT écran à DataTable dans ce dépôt (flotte, contrats,
// assurances…) ; l'app le fournit à la racine.
const renderScreen = () => render(
  <MemoryRouter><ThemeProvider><AffairesList /></ThemeProvider></MemoryRouter>,
)

const ROWS = [
  {
    id: 1, reference: 'AO-2026-001', objet: 'Centrale solaire école',
    acheteur: 'Commune X', type_marche: 'public', type_marche_display: 'Public',
    lot: 'Lot 1', date_limite: '2026-09-15', montant_estime: 1500000,
    statut: 'depose', capacite_engagement_label: '3/5 équipes',
    dossier_completude: 80,
  },
  {
    id: 2, reference: 'AO-2026-002', objet: 'Pompage agricole',
    acheteur: 'ORMVA', type_marche: 'public', type_marche_display: 'Public',
    lot: '', date_limite: null, montant_estime: 420000,
    statut: 'gagne', capacite_engagement_label: '',
    dossier_completude: null,
  },
]

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: ROWS })
  mocks.dupliquer.mockResolvedValue({ data: { id: 99 } })
  mocks.update.mockResolvedValue({ data: {} })
})

// `DataTable` rend SIMULTANÉMENT le tableau bureau et les cartes mobiles — le
// repli est purement CSS, et jsdom n'applique aucune media query : chaque
// libellé existe donc EN DOUBLE dans le DOM et tout `getByText` global est
// ambigu. On attend le rendu, puis on porte chaque requête sur la ligne
// `<tr>` du tableau bureau (les cartes mobiles ne sont pas des `<tr>`).
async function findRow(reference) {
  const cells = await screen.findAllByText(reference)
  const row = cells.map((c) => c.closest('tr')).find(Boolean)
  expect(row, `ligne ${reference} absente du tableau bureau`).toBeTruthy()
  return row
}

describe('AffairesList', () => {
  it('charge les affaires via aoApi.affaires.list() (useResource, aucun fetch manuel)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    expect(await findRow('AO-2026-001')).toBeInTheDocument()
    expect(await findRow('AO-2026-002')).toBeInTheDocument()
  })

  it('affiche objet, acheteur, montant estimé et la pastille de statut de chaque affaire', async () => {
    renderScreen()
    // Porté ligne par ligne : on vérifie non seulement que la valeur est là,
    // mais qu'elle est sur la BONNE affaire.
    const row1 = await findRow('AO-2026-001')
    expect(within(row1).getByText('Centrale solaire école')).toBeInTheDocument()
    expect(within(row1).getByText('Commune X')).toBeInTheDocument()
    expect(within(row1).getByText('Déposé')).toBeInTheDocument()
    const row2 = await findRow('AO-2026-002')
    expect(within(row2).getByText('Pompage agricole')).toBeInTheDocument()
    expect(within(row2).getByText('Gagné')).toBeInTheDocument()
  })

  it('capacité vs engagement et complétude du dossier : « — » quand le champ backend est absent (jamais un calcul de substitution)', async () => {
    renderScreen()
    const row2 = await findRow('AO-2026-002')
    expect(row2.textContent).toContain('—')
  })

  it('« Dupliquer » appelle aoApi.affaires.dupliquer() (AOF130, service réel) et navigue vers la copie', async () => {
    renderScreen()
    const row1 = await findRow('AO-2026-001')
    // RowActions (DataTable) rend chaque action à la fois en icône rapide
    // (aria-label = label de l'action) ET dans le menu kebab persistant —
    // l'icône rapide suffit, pas besoin d'ouvrir le menu Radix dans le test.
    fireEvent.click(within(row1).getByLabelText('Dupliquer'))
    await waitFor(() => expect(mocks.dupliquer).toHaveBeenCalledWith(1))
    await waitFor(() => expect(mocks.navigate).toHaveBeenCalledWith('/ao/affaires/99'))
  })

  it('« Archiver » appelle update(id, { archive: true }) — JAMAIS remove() (archivage logique)', async () => {
    renderScreen()
    const row1 = await findRow('AO-2026-001')
    fireEvent.click(within(row1).getByLabelText('Archiver'))
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith(1, { archive: true }))
    expect(mocks.remove).not.toHaveBeenCalled()
  })

  it('cliquer une ligne navigue vers la fiche affaire', async () => {
    renderScreen()
    fireEvent.click(await findRow('AO-2026-001'))
    expect(mocks.navigate).toHaveBeenCalledWith('/ao/affaires/1')
  })
})

// ── Garde de source : « zéro useState/useEffect de fetch » (Done AOF170). ──
describe('AffairesList.jsx — contrat de source', () => {
  const here = dirname(fileURLToPath(import.meta.url))
  const src = readFileSync(join(here, 'AffairesList.jsx'), 'utf8')

  it('n’importe ni useState ni useEffect de React (données 100% via useResource)', () => {
    // La regex ne peut pas balayer la source BRUTE : l'en-tête du fichier
    // DOCUMENTE justement « zéro `useState`/`useEffect` de fetch », donc elle
    // se déclenchait sur le commentaire qui affirme l'invariant qu'elle
    // vérifie. On vise le CODE — ce que le fichier importe réellement de
    // React, et tout appel de l'un des deux hooks.
    const reactImport = src.match(/^import\s+\{([^}]*)\}\s+from\s+'react'/m)?.[1] ?? ''
    expect(reactImport).not.toMatch(/\buseState\b/)
    expect(reactImport).not.toMatch(/\buseEffect\b/)
    expect(src).not.toMatch(/\buseState\s*\(/)
    expect(src).not.toMatch(/\buseEffect\s*\(/)
  })

  it('utilise useResource + aoApi, jamais un axios.get direct', () => {
    expect(src).toMatch(/from '\.\.\/\.\.\/hooks\/useResource'/)
    expect(src).toMatch(/aoApi\.affaires\.list\(\)/)
    expect(src).not.toMatch(/axios\.get/)
  })

  it('persiste tri/filtre en URL (persistToUrl + urlKey) et déclare des vues sauvegardées', () => {
    expect(src).toMatch(/persistToUrl/)
    expect(src).toMatch(/urlKey="ao-affaires"/)
    expect(src).toMatch(/savedViews=\{SAVED_VIEWS\}/)
  })
})
