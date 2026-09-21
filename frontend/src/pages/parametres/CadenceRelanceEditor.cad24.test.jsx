import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, act, cleanup } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

/* CAD24 — l'écran montre ENFIN quelle touche part le dimanche.

   `dimanche_ok` est la vraie commande du rendez-vous dominical du Protocole
   v3 : l'API la sert, mais l'éditeur ne l'affichait pas — le fondateur
   réglait une « Heure cible » sans voir QUELLE ligne tombe le dimanche, et
   cette heure était de toute façon écartée par le calcul (corrigé côté
   serveur par la même tâche).

   CONTRAT PARTAGÉ (PACT10) : la réponse simulée ici est LUE dans
   `apps/parametres/contract_samples/cadence_relance_v2.json`, le fichier que
   le test backend `tests_cad24_heure_dominicale.py` affirme de son côté —
   jamais une forme recopiée à la main, qui divergerait en silence. */

const ici = dirname(fileURLToPath(import.meta.url))
const CONTRAT = JSON.parse(readFileSync(join(
  ici, '..', '..', '..', '..', 'backend', 'django_core', 'apps', 'parametres',
  'contract_samples', 'cadence_relance_v2.json'), 'utf8'))

const LIGNES = CONTRAT.exemple_liste

vi.mock('../../api/parametresApi', () => ({
  default: {
    getMessages: vi.fn(async () => ({ data: [] })),
    getCadenceRelance: vi.fn(async () => ({ data: [] })),
    updateCadenceRelanceEtape: vi.fn(async () => ({ data: {} })),
  },
}))

import parametresApi from '../../api/parametresApi'
import { ThemeProvider } from '../../design/ThemeProvider'
import CadenceRelanceEditor from './CadenceRelanceEditor'

beforeEach(() => {
  parametresApi.getCadenceRelance.mockReset()
  parametresApi.getCadenceRelance.mockImplementation(async (cadence) => ({
    data: cadence === 'contact' ? LIGNES : [],
  }))
  parametresApi.updateCadenceRelanceEtape.mockClear()
})
afterEach(() => cleanup())

const renderEditor = async () => {
  await act(async () => {
    render(
      <ThemeProvider>
        <CadenceRelanceEditor />
      </ThemeProvider>,
    )
  })
}

describe('CAD24 — la case « dimanche » et la mention de la règle', () => {
  it('le contrat partagé porte bien `dimanche_ok`', () => {
    expect(Object.keys(CONTRAT.exemple)).toContain('dimanche_ok')
    expect(LIGNES.filter(l => l.dimanche_ok)).toHaveLength(1)
  })

  it('affiche une case « Autorisée le dimanche » par étape', async () => {
    await renderEditor()
    const cases = await screen.findAllByRole('checkbox', {
      name: /Autorisée le dimanche \(16 h-19 h\)/,
    })
    expect(cases).toHaveLength(LIGNES.length)
  })

  it('la case n\'est cochée que sur la touche dominicale du contrat',
    async () => {
      await renderEditor()
      const dominicale = LIGNES.find(l => l.dimanche_ok)
      const cochee = await screen.findByRole('checkbox', {
        name: `Autorisée le dimanche (16 h-19 h) — étape ${dominicale.ordre}`,
      })
      expect(cochee).toBeChecked()
      const autre = LIGNES.find(l => !l.dimanche_ok)
      expect(screen.getByRole('checkbox', {
        name: `Autorisée le dimanche (16 h-19 h) — étape ${autre.ordre}`,
      })).not.toBeChecked()
    })

  it('la case est en LECTURE seule — aucun PATCH n\'en sort', async () => {
    await renderEditor()
    const dominicale = LIGNES.find(l => l.dimanche_ok)
    const cochee = await screen.findByRole('checkbox', {
      name: `Autorisée le dimanche (16 h-19 h) — étape ${dominicale.ordre}`,
    })
    expect(cochee).toHaveAttribute('readonly')
    const { default: userEvent } = await import('@testing-library/user-event')
    await userEvent.setup().click(cochee)
    expect(parametresApi.updateCadenceRelanceEtape).not.toHaveBeenCalled()
  })

  it('affiche la mention de la règle sous la cadence', async () => {
    await renderEditor()
    const mention = await screen.findByTestId('cadence-regle-dimanche-contact')
    expect(mention).toHaveTextContent(
      /Une seule touche par cadence peut être autorisée le dimanche/)
    expect(mention).toHaveTextContent(/entre 16 h et 19 h/)
    expect(mention).toHaveTextContent(/16 h 30/)
  })
})
