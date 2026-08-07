import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  navigate: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mocks.navigate }
})

vi.mock('../../api/veilleAoApi', () => ({
  default: {
    avis: { list: mocks.list },
  },
}))

import AvisList, { avisNouveauxDepuisHier, STATUT_AVIS, StatutAvis } from './AvisList'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

// `ListShell` rend un `DataTable`, qui lit la densité via `useDensity()` →
// `useTheme()` : sans `<ThemeProvider>` ancêtre le hook JETTE — même patron de
// test que TOUT écran à DataTable de ce dépôt (voir AffairesList.test.jsx).
const renderScreen = () => render(
  <MemoryRouter><ThemeProvider><AvisList /></ThemeProvider></MemoryRouter>,
)

const ROWS = [
  {
    id: 1, objet: 'Fourniture et pose de panneaux solaires', acheteur: 'Commune X',
    source_libelle: 'Portail officiel', lieu: 'Casablanca-Settat',
    date_limite: '2026-09-15', montant_estime: 850000, score: 42,
    mots_cles_declenches: ['solaire', 'photovoltaïque'], statut: 'nouveau',
    cree_le: new Date().toISOString(),
  },
  {
    id: 2, objet: 'Éclairage public solaire', acheteur: 'ONEE-Eau',
    source_libelle: 'Portail officiel', lieu: 'Figuig',
    date_limite: null, montant_estime: 0, score: 8,
    mots_cles_declenches: [], statut: 'ignore', regle_exclusion_motif: 'hors zone d’intervention',
    cree_le: '2020-01-01T00:00:00Z',
  },
]

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: ROWS })
})

async function findRow(objet) {
  const cells = await screen.findAllByText(objet)
  const row = cells.map((c) => c.closest('tr')).find(Boolean)
  expect(row, `ligne « ${objet} » absente du tableau bureau`).toBeTruthy()
  return row
}

describe('AvisList', () => {
  it('charge les avis via veilleAoApi.avis.list() (useResource, aucun fetch manuel)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    expect(await findRow('Fourniture et pose de panneaux solaires')).toBeInTheDocument()
    expect(await findRow('Éclairage public solaire')).toBeInTheDocument()
  })

  it('affiche acheteur, lieu, montant estimé, score et statut de chaque avis', async () => {
    renderScreen()
    const row1 = await findRow('Fourniture et pose de panneaux solaires')
    expect(within(row1).getByText('Commune X')).toBeInTheDocument()
    expect(within(row1).getByText('Casablanca-Settat')).toBeInTheDocument()
    expect(within(row1).getByText('42')).toBeInTheDocument()
  })

  it('affiche les mots déclencheurs en pastilles', async () => {
    renderScreen()
    const row1 = await findRow('Fourniture et pose de panneaux solaires')
    expect(within(row1).getByText('solaire')).toBeInTheDocument()
    expect(within(row1).getByText('photovoltaïque')).toBeInTheDocument()
  })

  it('VAO10/VAO33 — un avis auto-ignoré affiche la règle qui l’a filtré', async () => {
    renderScreen()
    const row2 = await findRow('Éclairage public solaire')
    expect(within(row2).getByText(/règle : hors zone d’intervention/)).toBeInTheDocument()
  })

  it('cliquer une ligne navigue vers la fiche avis', async () => {
    renderScreen()
    const { fireEvent } = await import('@testing-library/react')
    fireEvent.click(await findRow('Fourniture et pose de panneaux solaires'))
    expect(mocks.navigate).toHaveBeenCalledWith('/veille-ao/avis/1')
  })
})

describe('avisNouveauxDepuisHier (VAO33 Done= « la pastille compte juste »)', () => {
  it('compte les avis "nouveau" créés depuis hier, ignore les autres statuts et les plus anciens', () => {
    const now = new Date('2026-08-07T09:00:00')
    const rows = [
      { statut: 'nouveau', cree_le: '2026-08-06T23:00:00' }, // hier soir : compté
      { statut: 'nouveau', cree_le: '2026-08-07T02:00:00' }, // aujourd’hui : compté
      { statut: 'nouveau', cree_le: '2026-08-05T10:00:00' }, // avant-hier : PAS compté
      { statut: 'retenu', cree_le: '2026-08-07T02:00:00' }, // pas "nouveau" : PAS compté
      { statut: 'nouveau', cree_le: null }, // pas d’horodatage : PAS compté
    ]
    expect(avisNouveauxDepuisHier(rows, now)).toBe(2)
  })

  it('renvoie 0 sur une liste vide ou une date invalide', () => {
    expect(avisNouveauxDepuisHier([], new Date())).toBe(0)
    expect(avisNouveauxDepuisHier([{ statut: 'nouveau', cree_le: '2026-08-07' }], new Date('invalide'))).toBe(0)
  })
})

describe('STATUT_AVIS / StatutAvis — miroir de AvisMarche.statut (VAO8)', () => {
  it('couvre exactement les 5 valeurs du modèle', () => {
    expect(Object.keys(STATUT_AVIS).sort()).toEqual(
      ['converti', 'expire', 'ignore', 'nouveau', 'retenu'].sort(),
    )
  })

  it('StatutAvis est une fabrique statusPill (label + ton par statut)', () => {
    expect(StatutAvis.labelOf('nouveau')).toBe('Nouveau')
    expect(StatutAvis.toneOf('expire')).toBe('danger')
  })
})

// ── Garde de source : « zéro useState/useEffect de fetch » (patron AOF170). ──
describe('AvisList.jsx — contrat de source', () => {
  const here = dirname(fileURLToPath(import.meta.url))
  const src = readFileSync(join(here, 'AvisList.jsx'), 'utf8')

  it('n’importe ni useState ni useEffect de React (données 100% via useResource)', () => {
    const reactImport = src.match(/^import\s+\{([^}]*)\}\s+from\s+'react'/m)?.[1] ?? ''
    expect(reactImport).not.toMatch(/\buseState\b/)
    expect(reactImport).not.toMatch(/\buseEffect\b/)
    expect(src).not.toMatch(/\buseState\s*\(/)
    expect(src).not.toMatch(/\buseEffect\s*\(/)
  })

  it('utilise useResource + veilleAoApi, jamais un axios.get direct', () => {
    expect(src).toMatch(/from '\.\.\/\.\.\/hooks\/useResource'/)
    expect(src).toMatch(/veilleAoApi\.avis\.list\(\)/)
    expect(src).not.toMatch(/axios\.get/)
  })

  it('persiste tri/filtre en URL (persistToUrl + urlKey) et déclare des vues sauvegardées', () => {
    expect(src).toMatch(/persistToUrl/)
    expect(src).toMatch(/urlKey="veille-ao-avis"/)
    expect(src).toMatch(/savedViews=\{SAVED_VIEWS\}/)
  })

  it('utilise urgency.js pour la date limite, jamais un seuil local codé en dur', () => {
    expect(src).toMatch(/daysUntil/)
    expect(src).toMatch(/urgencyLevel/)
    expect(src).toMatch(/urgencyTone/)
    expect(src).toMatch(/urgencyLabel/)
  })
})
