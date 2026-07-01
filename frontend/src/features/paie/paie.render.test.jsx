import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import MesBulletins from './MesBulletins.jsx'
import PaieRunWizard from './PaieRunWizard.jsx'

/* Smoke : les écrans Paie montent sans planter (imports résolus, kit UX1 OK).
   L'API est mockée pour renvoyer des listes vides — on vérifie que le titre et
   les repères clés s'affichent, sans dépendre du réseau. */
vi.mock('../../api/paieApi', () => ({
  default: {
    getPeriodes: vi.fn(() => Promise.resolve({ data: [] })),
    getProfils: vi.fn(() => Promise.resolve({ data: [] })),
    getBulletins: vi.fn(() => Promise.resolve({ data: [] })),
    getMesBulletins: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))

function wrap(ui) {
  return render(
    <MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>,
  )
}

describe('Paie — smoke de rendu', () => {
  it('MesBulletins (UX14) monte et affiche son titre + garde d’isolation', () => {
    wrap(<MesBulletins />)
    expect(screen.getByText('Mes bulletins')).toBeInTheDocument()
    expect(
      screen.getByText(/Seuls vos propres bulletins validés/i),
    ).toBeInTheDocument()
  })

  it('PaieRunWizard (UX10) monte et affiche l’assistant après chargement', async () => {
    wrap(<PaieRunWizard />)
    // D'abord l'état de chargement (rendu synchrone), puis le titre.
    expect(screen.getByText(/Chargement de la paie/i)).toBeInTheDocument()
    expect(await screen.findByText('Run de paie')).toBeInTheDocument()
  })
})
