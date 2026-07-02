import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, act, cleanup, waitFor } from '@testing-library/react'

/* N94 — smoke de l'éditeur de traductions : il se monte, charge les surcharges,
   liste des clés du catalogue groupées par espace de noms, et affiche la valeur
   surchargée par-dessus la valeur statique. */

vi.mock('../../api/parametresApi', () => ({
  default: {
    getTranslationOverrides: vi.fn(async () => ({
      data: { overrides: { fr: { 'common.save': 'Sauvegarder !' } } },
    })),
    saveTranslationOverrides: vi.fn(async () => ({ data: { overrides: {} } })),
  },
}))

import parametresApi from '../../api/parametresApi'
import { I18nProvider } from '../../i18n'
import { ThemeProvider } from '../../design/ThemeProvider'
import TraductionsSection from './TraductionsSection'

beforeEach(() => {
  window.localStorage.clear()
  parametresApi.getTranslationOverrides.mockClear()
})
afterEach(() => cleanup())

const renderSection = async () => {
  await act(async () => {
    render(
      <I18nProvider>
        <ThemeProvider>
          <TraductionsSection />
        </ThemeProvider>
      </I18nProvider>,
    )
  })
}

describe('N94 TraductionsSection', () => {
  it('se monte et charge les surcharges de la société', async () => {
    await renderSection()
    await waitFor(() =>
      expect(parametresApi.getTranslationOverrides).toHaveBeenCalled())
    // Le champ recherche et un groupe d'espace de noms sont rendus.
    expect(screen.getByLabelText('Rechercher une traduction')).toBeInTheDocument()
    // Le groupe `common.*` doit exister (le catalogue contient common.save).
    expect(screen.getByText('common.*')).toBeInTheDocument()
  })

  it('affiche la valeur surchargée par-dessus le catalogue statique', async () => {
    await renderSection()
    // La cellule FR de common.save montre la surcharge, pas « Enregistrer ».
    const cell = await screen.findByLabelText('Traduction Français de common.save')
    expect(cell).toHaveValue('Sauvegarder !')
  })

  it('rend les trois colonnes de langue pour une clé', async () => {
    await renderSection()
    await screen.findByLabelText('Traduction Français de common.save')
    expect(screen.getByLabelText('Traduction English de common.save')).toHaveValue('Save')
    // AR : valeur statique du catalogue (pas de surcharge).
    expect(screen.getByLabelText('Traduction العربية de common.save')).toBeInTheDocument()
  })
})
