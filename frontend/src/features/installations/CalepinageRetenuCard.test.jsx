// CAL213 — encart « Calepinage retenu » de la fiche chantier : apparaît
// quand le chantier a un calepinage retenu (CAL245), disparaît sinon.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})

import CalepinageRetenuCard from './CalepinageRetenuCard'

// Échantillon du contrat CAL245 (voir
// apps/installations/contract_samples/calepinage_retenu.json) — mêmes clés,
// jamais un mock inventé.
const CALEPINAGE = {
  calepinage_id: 7,
  kwc: 8.64,
  nb_modules: 12,
  planche_url: '/calepinage/7',
  plan_pose_url: '/ventes/devis/103/3d',
}

function wrap(ui) {
  return <MemoryRouter>{ui}</MemoryRouter>
}

beforeEach(() => vi.clearAllMocks())

describe('CalepinageRetenuCard (CAL213)', () => {
  it('ne rend rien quand le chantier n\'a pas de calepinage retenu', () => {
    const { container } = render(wrap(<CalepinageRetenuCard calepinage={null} />))
    expect(container).toBeEmptyDOMElement()
  })

  it('affiche le kWc, le nombre de modules et les deux liens', () => {
    render(wrap(<CalepinageRetenuCard calepinage={CALEPINAGE} />))
    expect(screen.getByText('Calepinage retenu')).toBeInTheDocument()
    expect(screen.getByText('8.64 kWc')).toBeInTheDocument()
    expect(screen.getByText('12 modules')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Voir le calepinage' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Plan de pose 3D' })).toBeInTheDocument()
  })

  it('navigue vers la planche puis vers le plan de pose au clic', async () => {
    const user = userEvent.setup()
    render(wrap(<CalepinageRetenuCard calepinage={CALEPINAGE} />))

    await user.click(screen.getByRole('button', { name: 'Voir le calepinage' }))
    expect(navigateMock).toHaveBeenCalledWith('/calepinage/7')

    await user.click(screen.getByRole('button', { name: 'Plan de pose 3D' }))
    expect(navigateMock).toHaveBeenCalledWith('/ventes/devis/103/3d')
  })

  it('affiche un tiret quand kWc/nb_modules sont null (calepinage posé mais non simulé)', () => {
    render(wrap(<CalepinageRetenuCard calepinage={{
      ...CALEPINAGE, kwc: null, nb_modules: null,
    }}
    />))
    const tirets = screen.getAllByText('—')
    expect(tirets).toHaveLength(2)
  })

  it('omet un lien absent sans planter (planche_url ou plan_pose_url manquant)', () => {
    render(wrap(<CalepinageRetenuCard calepinage={{
      ...CALEPINAGE, plan_pose_url: null,
    }}
    />))
    expect(screen.getByRole('button', { name: 'Voir le calepinage' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Plan de pose 3D' })).not.toBeInTheDocument()
  })
})
