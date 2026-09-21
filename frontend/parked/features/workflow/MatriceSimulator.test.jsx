import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* NTWFL32 — simulateur "what-if" de la matrice d'approbation. Vérifie : (1)
   le port JS de `resoudre_matrice` retrouve bien la règle la plus SPÉCIFIQUE
   quand deux règles concurrentes couvrent le même triplet, et (2) l'écran ne
   fait jamais qu'un GET (jamais de POST/PATCH/DELETE). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}

      unobserve() {}

      disconnect() {}
    }
  }
  if (typeof window.matchMedia === 'undefined') {
    window.matchMedia = () => ({
      matches: false,
      addListener() {},
      removeListener() {},
      addEventListener() {},
      removeEventListener() {},
    })
  }
})

const matricesList = vi.fn()

vi.mock('../../api/coreApi', () => ({
  default: {
    matricesApprobation: {
      list: (...a) => matricesList(...a),
    },
  },
}))

import MatriceSimulator from './MatriceSimulator'
import { resoudreMatriceSimulee } from './matriceResolution'

function renderEcran() {
  return render(
    <ThemeProvider>
      <MemoryRouter>
        <MatriceSimulator />
      </MemoryRouter>
    </ThemeProvider>,
  )
}

const REGLE_GENERALE = {
  id: 1, type_objet: 'achat', departement: '', montant_min: null, montant_max: null,
  chaine_paliers: [{ palier: 1, nombre_approbateurs_requis: 1, role_requis: 'Responsable' }],
  actif: true,
}
const REGLE_SPECIFIQUE = {
  id: 2, type_objet: 'achat', departement: '', montant_min: 10000, montant_max: 50000,
  chaine_paliers: [{ palier: 1, nombre_approbateurs_requis: 2, role_requis: 'Direction' }],
  actif: true,
}

describe('resoudreMatriceSimulee (port JS de core.selectors.resoudre_matrice)', () => {
  it('renvoie null sans type d\'objet', () => {
    expect(resoudreMatriceSimulee([REGLE_GENERALE], null, 100, null)).toBeNull()
  })

  it('choisit la règle bornée (plus spécifique) quand le montant tombe dans son intervalle', () => {
    const resolue = resoudreMatriceSimulee(
      [REGLE_GENERALE, REGLE_SPECIFIQUE], 'achat', 25000, null)
    expect(resolue.id).toBe(2)
  })

  it('retombe sur la règle générale hors de l\'intervalle borné', () => {
    const resolue = resoudreMatriceSimulee(
      [REGLE_GENERALE, REGLE_SPECIFIQUE], 'achat', 500, null)
    expect(resolue.id).toBe(1)
  })

  it('ne renvoie rien quand aucune règle active ne couvre le triplet', () => {
    const resolue = resoudreMatriceSimulee(
      [{ ...REGLE_SPECIFIQUE, actif: false }], 'achat', 25000, null)
    expect(resolue).toBeNull()
  })
})

describe('MatriceSimulator (écran)', () => {
  it('bascule la chaîne affichée entre deux règles concurrentes en changeant le montant simulé', async () => {
    const user = userEvent.setup()
    matricesList.mockResolvedValue({ data: [REGLE_GENERALE, REGLE_SPECIFIQUE] })
    renderEcran()

    await user.click(await screen.findByRole('combobox', { name: "Type d'objet" }))
    await user.click(await screen.findByRole('option', { name: 'achat' }))

    // Hors de l'intervalle borné -> règle générale (Responsable, 1 approbateur).
    expect(await screen.findByTestId('matsim-resultat')).toHaveTextContent('Responsable')

    await user.type(screen.getByLabelText('Montant simulé (MAD)'), '25000')
    await waitFor(() => expect(screen.getByTestId('matsim-resultat')).toHaveTextContent('Direction'))

    // Jamais aucune écriture : l'API mockée n'expose que `list`.
    expect(matricesList).toHaveBeenCalled()
  })

  it("affiche « aucune règle » quand rien ne couvre le triplet simulé", async () => {
    const user = userEvent.setup()
    matricesList.mockResolvedValue({ data: [REGLE_SPECIFIQUE] })
    renderEcran()

    await user.click(await screen.findByRole('combobox', { name: "Type d'objet" }))
    await user.click(await screen.findByRole('option', { name: 'achat' }))
    await user.type(screen.getByLabelText('Montant simulé (MAD)'), '500')

    expect(await screen.findByTestId('matsim-aucune-regle')).toBeInTheDocument()
  })
})
