import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   ALEA39 — la recherche de lead du calepinage (« Nouveau » ET la liste) envoie
   le paramètre que `/crm/leads/` lit RÉELLEMENT : `search` (SearchFilter DRF,
   `apps/crm/views.py` LeadViewSet.search_fields). Avant : `q`, ignoré par le
   serveur ⇒ toujours les 20 derniers leads, un lead ancien introuvable.

   Le serveur factice ci-dessous applique la sémantique RÉELLE de DRF :
     * `search` : chaque terme doit apparaître (icontains) dans au moins un des
       champs de recherche ; `q` est IGNORÉ (aucun filtre ne le lit) ;
     * ordre `-date_creation` (le plus récent d'abord), pagination
       PAGE_SIZE 50 / `?page_size=` plafonné à 200 (`core/pagination.py`).
   Le client `crmApi` RÉEL tourne au-dessus : l'assertion porte sur les
   options AFFICHÉES, jamais sur un espion d'appel.
   ========================================================================== */

const serveur = vi.hoisted(() => {
  // 39 leads ; id croissant = création plus récente. Le n° 1 est le plus ancien.
  const leads = Array.from({ length: 39 }, (_, i) => {
    const id = i + 1
    return id === 1
      ? { id, nom: 'Zzz', prenom: 'Ancien', ville: 'Settat', societe: '', email: '', telephone: '' }
      : { id, nom: `Lead${id}`, prenom: 'Récent', ville: 'Casablanca', societe: '', email: '', telephone: '' }
  })
  const CHAMPS = ['nom', 'prenom', 'societe', 'email', 'telephone', 'ville']
  const listeLeads = (params = {}) => {
    let lignes = [...leads].sort((a, b) => b.id - a.id)
    const termes = String(params.search ?? '').trim().toLowerCase().split(/\s+/).filter(Boolean)
    if (termes.length) {
      lignes = lignes.filter((l) => termes.every((t) =>
        CHAMPS.some((c) => String(l[c] ?? '').toLowerCase().includes(t))))
    }
    const taille = Math.min(Number(params.page_size) || 50, 200)
    const page = Number(params.page) || 1
    const debut = (page - 1) * taille
    return {
      count: lignes.length,
      next: debut + taille < lignes.length ? `/crm/leads/?page=${page + 1}` : null,
      previous: null,
      results: lignes.slice(debut, debut + taille),
    }
  }
  const get = (url, config = {}) => {
    if (url === '/crm/leads/') return Promise.resolve({ data: listeLeads(config.params) })
    return Promise.resolve({ data: [] })
  }
  return { get }
})

vi.mock('../../api/axios', () => ({
  default: {
    get: (...a) => serveur.get(...a),
    post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn(),
  },
}))

const mocks = vi.hoisted(() => ({ navigate: vi.fn() }))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mocks.navigate }
})

const REGLAGES = exempleContrat('calepinage', 'parametres_calepinage')

vi.mock('../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      create: vi.fn(),
      list: vi.fn(() => Promise.resolve({ data: { count: 0, next: null, previous: null, results: [] } })),
      update: vi.fn(),
      modeles: vi.fn(() => Promise.resolve({ data: [] })),
      depuisModele: vi.fn(),
    },
    parametres: { get: vi.fn(() => Promise.resolve({ data: REGLAGES })) },
  },
}))

import CalepinageNouveau from './CalepinageNouveau'
import CalepinageList from './CalepinageList'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

beforeEach(() => { vi.clearAllMocks() })

// Les options du SEUL menu de recherche ouvert (d'autres <select> natifs de
// l'écran portent aussi le rôle « option »).
const options = () => {
  const menu = screen.queryByRole('listbox')
  return menu ? within(menu).queryAllByRole('option').map((o) => o.textContent) : []
}

async function taperDansLaRecherche(nomChamp, texte) {
  fireEvent.click(screen.getByRole('combobox', { name: nomChamp }))
  const champ = await screen.findByRole('searchbox')
  // Saisie vide : comportement inchangé (les 20 plus récents).
  await waitFor(() => expect(options()).toHaveLength(20))
  expect(options().some((t) => t.includes('Zzz'))).toBe(false)
  fireEvent.change(champ, { target: { value: texte } })
}

describe('ALEA39 — recherche de lead du calepinage par `search`', () => {
  it('Calepinage → Nouveau : taper « Zzz » propose le lead ancien et rien d’autre', async () => {
    render(<MemoryRouter><CalepinageNouveau /></MemoryRouter>)
    await taperDansLaRecherche('Lead', 'Zzz')
    await waitFor(() => expect(options()).toHaveLength(1))
    expect(options()[0]).toContain('Zzz Ancien')
  })

  it('liste Calepinage : le filtre lead trouve le lead ancien et rien d’autre', async () => {
    render(<MemoryRouter><ThemeProvider><CalepinageList /></ThemeProvider></MemoryRouter>)
    await taperDansLaRecherche('Lead', 'Zzz')
    await waitFor(() => expect(options()).toHaveLength(1))
    expect(options()[0]).toContain('Zzz')
  })
})
