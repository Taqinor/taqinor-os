import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import EquipementsPage, { GarantiePill } from './EquipementsPage.jsx'
import { resolveScanTarget } from '../../features/sav/equipement'
import { GARANTIE_ETATS, garantieLabel } from '../../features/sav/equipement'

// ADRG66 — doublures réseau de l'écran des équipements (les briques pures
// testées plus bas n'appellent aucune API).
vi.mock('../../features/sav/store/equipementsSlice', () => ({
  fetchEquipements: () => ({ type: 'equipements/fetch/noop' }),
}))
vi.mock('../../api/savApi', () => ({ default: { getTickets: vi.fn(() => Promise.resolve({ data: [] })) } }))
vi.mock('../../api/installationsApi', () => ({ default: { getInstallations: vi.fn(() => Promise.resolve({ data: [] })) } }))
vi.mock('../../api/stockApi', () => ({ default: { getProduits: vi.fn(() => Promise.resolve({ data: [] })) } }))
vi.mock('../../api/importApi', () => ({ default: {} }))
vi.mock('./RegistreGarantiesDialog', () => ({ default: () => null }))
vi.mock('./EquipementFiabilitePanel', () => ({ default: () => null }))
vi.mock('../../components/ExcelImport', () => ({ default: () => null }))

/* J144 — refonte SAV : le parc d'équipements passe à StatusPill + DataTable.
   On verrouille la brique de présentation de l'état de garantie : ton + libellé
   FR explicite (la couleur n'est jamais le seul signal). */

const DOT_CLASS = {
  neutral: 'bg-muted-foreground', success: 'bg-success',
  warning: 'bg-warning', danger: 'bg-destructive',
}

describe('GarantiePill (J144 — état de garantie → ton + libellé FR)', () => {
  it('chaque état de garantie connu rend un libellé FR et un point coloré', () => {
    for (const etat of Object.keys(GARANTIE_ETATS)) {
      const { container, unmount } = render(<GarantiePill eq={{ garantie_etat: etat }} />)
      const hasKnownDot = Object.values(DOT_CLASS)
        .some((cls) => container.querySelector(`.${cls}`))
      expect(hasKnownDot).toBe(true)
      unmount()
    }
  })

  it('affiche le libellé FR « Hors garantie »', () => {
    render(<GarantiePill eq={{ garantie_etat: 'hors_garantie' }} />)
    expect(screen.getByText(garantieLabel({ garantie_etat: 'hors_garantie' }))).toBeInTheDocument()
  })

  it('rend le point coloré correspondant au ton (sous garantie → succès)', () => {
    const { container } = render(
      <GarantiePill eq={{ garantie_etat: 'sous_garantie', date_fin_garantie: '2030-01-01' }} />,
    )
    expect(container.querySelector(`.${DOT_CLASS.success}`)).toBeTruthy()
  })

  it('état manquant → ton neutre + libellé « non renseignée »', () => {
    const { container } = render(<GarantiePill eq={{}} />)
    expect(container.querySelector(`.${DOT_CLASS.neutral}`)).toBeTruthy()
    expect(screen.getByText(/non renseignée/i)).toBeInTheDocument()
  })
})

/* NTMOB15 — scan QR/code-barres natif : décision pure post-résolution
   (stock/produits/resolve/), testable sans monter toute la page. */
describe('resolveScanTarget (NTMOB15 — décision pure post-résolution du scan)', () => {
  const items = [
    { id: 7, produit_nom: 'Onduleur Deye', numero_serie: 'SN-7' },
    { id: 12, produit_nom: 'Panneau 550W', numero_serie: 'SN-12' },
  ]

  it('code non-équipement (ex. produit/système) → erreur explicite', () => {
    expect(resolveScanTarget({ type: 'produit', id: 1 }, items))
      .toEqual({ action: 'error', message: 'Ce code ne correspond pas à un équipement.' })
  })

  it('réponse absente/malformée → erreur, jamais une exception', () => {
    expect(resolveScanTarget(null, items).action).toBe('error')
    expect(resolveScanTarget(undefined, items).action).toBe('error')
  })

  it('équipement déjà chargé localement → sélection directe (pas de 2e requête)', () => {
    const decision = resolveScanTarget({ type: 'equipement', id: 12 }, items)
    expect(decision).toEqual({ action: 'select', equipement: items[1] })
  })

  it('équipement scanné absent du parc local → repli fetch ciblé', () => {
    const decision = resolveScanTarget({ type: 'equipement', id: 99 }, items)
    expect(decision).toEqual({ action: 'fetch', id: 99 })
  })

  it('liste locale vide/absente ne casse jamais la décision', () => {
    expect(resolveScanTarget({ type: 'equipement', id: 5 }, [])).toEqual({ action: 'fetch', id: 5 })
    expect(resolveScanTarget({ type: 'equipement', id: 5 }, undefined)).toEqual({ action: 'fetch', id: 5 })
  })
})

/* ADRG66 (C-ADRG-009) — « Importer » crée des équipements : offert avec
   `equipement_gerer` seulement (repli palier pour un compte hérité). Codes des
   rôles LIVRÉS recopiés du registre (`apps/roles/permissions_registre.py`). */
describe('EquipementsPage — ADRG66 bouton « Importer »', () => {
  const monter = (auth) => render(
    <Provider store={configureStore({ reducer: {
      auth: (s = auth) => s,
      equipements: (s = { items: [], loading: false, error: null }) => s,
    } })}>
      <MemoryRouter><ThemeProvider><EquipementsPage /></ThemeProvider></MemoryRouter>
    </Provider>)

  it('Importer caché sans equipement_gerer (Commercial)', () => {
    monter({ role: 'normal', role_nom: 'Commercial', permissions: ['equipement_voir', 'sav_voir'] })
    expect(screen.getByRole('button', { name: /Étiquettes QR internes/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Importer/ })).toBeNull()
  })

  it('Importer présent avec equipement_gerer (Technicien responsable) et au palier hérité', () => {
    const { unmount } = monter({ role: 'responsable', role_nom: 'Technicien responsable',
      permissions: ['equipement_voir', 'equipement_gerer', 'sav_voir', 'sav_gerer'] })
    expect(screen.getByRole('button', { name: /Importer/ })).toBeInTheDocument()
    unmount()
    monter({ role: 'responsable', permissions: [] })
    expect(screen.getByRole('button', { name: /Importer/ })).toBeInTheDocument()
  })
})
