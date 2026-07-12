import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* VX228 — RapprochementDetailDialog : contrat d'interaction complet.
   Une ligne non suggérée doit rester pointable manuellement (candidates GL
   pré-filtrées) et le bandeau d'écart doit décroître EN DIRECT à chaque
   pointage, jusqu'à « Rapproché ✓ » (clôturable). Aucun appel réseau réel —
   comptaApi.rapprochements est mocké avec une petite machine à états
   (avant/après pointer()) pour observer la transition resume() en direct. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const ligneAvant = {
  id: 10,
  rapprochement: 1,
  date_operation: '2026-07-01',
  libelle: 'Virement client X',
  reference: 'VIR-1',
  montant: 500,
  montant_pointe: 0,
  ecart: 500,
  est_concordante: false,
  statut: 'attente',
  statut_display: 'En attente',
  lignes_gl: [],
}

const ligneApres = { ...ligneAvant, montant_pointe: 500, ecart: 0, est_concordante: true, lignes_gl: [55] }

const rowInitial = {
  id: 1,
  compte_tresorerie: 2,
  compte_libelle: 'BMCE — Compte courant',
  libelle: 'Rapprochement juillet',
  date_debut: '2026-07-01',
  date_fin: '2026-07-31',
  date_releve: '2026-07-31',
  solde_releve: 500,
  statut: 'en_cours',
  statut_display: 'En cours',
  lignes_releve: [ligneAvant],
  est_rapproche: false,
}

const resumeAvant = {
  solde_releve: 500, solde_gl: 0, ecart: 500,
  lignes_total: 1, lignes_pointees: 0, lignes_non_pointees: 1,
  montant_pointe: 0, montant_non_pointe: 500,
  statut: 'en_cours', rapproche: false,
}

const resumeApres = {
  solde_releve: 500, solde_gl: 500, ecart: 0,
  lignes_total: 1, lignes_pointees: 1, lignes_non_pointees: 0,
  montant_pointe: 500, montant_non_pointe: 0,
  statut: 'en_cours', rapproche: true,
}

const ligneGl = {
  id: 55, date: '2026-07-02', journal: 'BQ1', reference: 'REF-55',
  libelle: 'Virement reçu — client X', debit: 500, credit: 0, montant: 500, pointee: false,
}

const empty = () => Promise.resolve({ data: [] })
const res = () => ({ list: empty, get: empty, create: empty, update: empty, remove: empty })

const getMock = vi.fn()
  .mockResolvedValueOnce({ data: rowInitial })
  .mockResolvedValue({ data: { ...rowInitial, lignes_releve: [ligneApres], est_rapproche: true, statut: 'rapproche' } })
const resumeMock = vi.fn()
  .mockResolvedValueOnce({ data: resumeAvant })
  .mockResolvedValue({ data: resumeApres })
const pointerMock = vi.fn().mockResolvedValue({ data: {} })

vi.mock('../../api/comptaApi', () => ({
  default: {
    downloadBlob: vi.fn(),
    cockpit: empty,
    comptes: res(), journaux: res(), plans: res(),
    ecritures: { ...res(), valider: empty, extourner: empty },
    exercices: { ...res(), cloturer: empty, rouvrir: empty },
    rapprochements: {
      ...res(),
      list: () => Promise.resolve({ data: [rowInitial] }),
      get: (id) => getMock(id),
      lignesGl: () => Promise.resolve({ data: [ligneGl] }),
      resume: (id) => resumeMock(id),
      ajouterLigneReleve: empty,
      pointer: (id, data) => pointerMock(id, data),
      suggestions: empty,
      accepterSuggestions: empty,
      cloturer: vi.fn().mockResolvedValue({ data: {} }),
    },
    modelesRapprochement: { ...res(), appliquer: empty },
    rapprochements3voies: { ...res(), evaluer: empty, valider: empty },
    budgets: res(), centresCout: res(), periodes: { ...res(), cloturer: empty, rouvrir: empty },
  },
}))

function mount(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('RapprochementDetailDialog — flux pointer→resume (VX228)', () => {
  it('ouvre le détail, montre l’écart, pointe une ligne et le réduit à zéro en direct', async () => {
    const { default: RapprochementsPage } = await import('./pages/RapprochementsPage.jsx')
    mount(<RapprochementsPage />)

    // Ouvrir le rapprochement — un clic de ligne ouvre le détail. Le repli
    // carte mobile (M154) duplique le libellé en DOM sous `sm:hidden` (CSS non
    // appliquée sous jsdom) : viser explicitement l'occurrence dans une <tr>.
    await screen.findAllByText('Rapprochement juillet')
    const rowLabel = screen.getAllByText('Rapprochement juillet').find((el) => el.closest('tr'))
    fireEvent.click(rowLabel.closest('tr'))

    // Le dialog s'ouvre et montre l'écart courant.
    await screen.findByText('Rapprochement — Rapprochement juillet')
    await waitFor(() => {
      expect(screen.getByText(/Écart : 500,00 MAD/)).toBeInTheDocument()
    })

    // Sélectionner la ligne relevé révèle les candidates du grand-livre.
    fireEvent.click(screen.getByText('Virement client X'))
    const glLabel = await screen.findByText('Virement reçu — client X')
    const glCheckbox = glLabel.closest('label').querySelector('button[role="checkbox"]')
    fireEvent.click(glCheckbox)

    // Pointer → resume() rechargé, l'écart tombe à 0 et « Rapproché ✓ » apparaît.
    fireEvent.click(screen.getByRole('button', { name: /^Pointer$/ }))

    await waitFor(() => {
      expect(pointerMock).toHaveBeenCalledWith(1, { ligne_releve: 10, lignes_gl: [55] })
    })
    await waitFor(() => {
      expect(screen.getByText('Rapproché ✓')).toBeInTheDocument()
    })
    // Écart 0 → clôturable : le bouton « Clôturer » apparaît dans le dialog.
    expect(screen.getByRole('button', { name: /Clôturer/ })).toBeInTheDocument()
  }, 30000)
})
