import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import kbApi from '../../api/kbApi'
import BlocInsertPicker from './BlocInsertPicker'

/* WIR250 — jusqu'ici invisible PAR CONSTRUCTION (`if (!blocs.length) return
   null`) : sans aucun bloc existant, il n'y avait ni moyen d'en créer un ni
   la moindre affordance visible. « Enregistrer la sélection comme bloc »
   reste TOUJOURS visible, et la suppression du bloc choisi est câblée. */

vi.mock('../../api/kbApi', () => ({
  default: {
    listBlocs: vi.fn(() => Promise.resolve({ data: [] })),
    createBloc: vi.fn(() => Promise.resolve({ data: { id: 1, nom: 'Signature', corps: 'bonjour' } })),
    removeBloc: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

vi.mock('../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

function withProviders(ui) {
  return render(<ThemeProvider>{ui}</ThemeProvider>)
}

function makeTextareaRef(value, selectionStart, selectionEnd) {
  return { current: { selectionStart, selectionEnd, value } }
}

describe('BlocInsertPicker — WIR250', () => {
  it('reste visible et propose « Enregistrer la sélection comme bloc » même sans aucun bloc existant', async () => {
    withProviders(
      <BlocInsertPicker textareaRef={{ current: null }} corps="bonjour le monde" onApply={vi.fn()} />,
    )
    expect(await screen.findByText('Aucun bloc réutilisable pour l’instant.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Enregistrer la sélection comme bloc/ })).toBeInTheDocument()
    // Pas de sélecteur « Insérer » tant qu'aucun bloc n'existe.
    expect(screen.queryByLabelText('Choisir un bloc réutilisable')).not.toBeInTheDocument()
  })

  it('« Enregistrer la sélection comme bloc » crée le bloc via createBloc depuis le texte sélectionné', async () => {
    const corps = 'Bonjour, ceci est une signature standard.'
    const ref = makeTextareaRef(corps, 10, 41) // sélectionne "ceci est une signature standard."
    const promptSpy = vi.spyOn(window, 'prompt').mockReturnValue('Signature standard')
    const user = userEvent.setup()
    withProviders(<BlocInsertPicker textareaRef={ref} corps={corps} onApply={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: /Enregistrer la sélection comme bloc/ }))

    await waitFor(() => expect(kbApi.createBloc).toHaveBeenCalledWith({
      nom: 'Signature standard', corps: corps.slice(10, 41),
    }))
    promptSpy.mockRestore()
  })

  it('refuse d’enregistrer un bloc sans sélection de texte', async () => {
    const ref = makeTextareaRef('sans rien de sélectionné', 5, 5)
    const promptSpy = vi.spyOn(window, 'prompt')
    const user = userEvent.setup()
    withProviders(<BlocInsertPicker textareaRef={ref} corps="sans rien de sélectionné" onApply={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: /Enregistrer la sélection comme bloc/ }))
    expect(kbApi.createBloc).not.toHaveBeenCalled()
    expect(promptSpy).not.toHaveBeenCalled()
    promptSpy.mockRestore()
  })

  it('insère le bloc choisi à la position du curseur puis peut le supprimer via removeBloc', async () => {
    kbApi.listBlocs.mockResolvedValueOnce({
      data: [{ id: 7, nom: 'Réponse type SAV', corps: '[réponse SAV]' }],
    })
    const onApply = vi.fn()
    const ref = makeTextareaRef('avant|après', 6, 6) // curseur après "avant|"
    const user = userEvent.setup()
    withProviders(<BlocInsertPicker textareaRef={ref} corps="avant|après" onApply={onApply} />)

    await user.selectOptions(await screen.findByLabelText('Choisir un bloc réutilisable'), '7')
    await user.click(screen.getByRole('button', { name: 'Insérer' }))
    expect(onApply).toHaveBeenCalledWith('avant|[réponse SAV]après')

    // WIR250 (fix Fable) — `insererBloc()` réinitialise `choix` (setChoix(''))
    // après insertion, désactivant « Supprimer » : il faut re-sélectionner le
    // bloc avant de le supprimer, exactement comme le ferait un utilisateur.
    await user.selectOptions(screen.getByLabelText('Choisir un bloc réutilisable'), '7')
    await user.click(screen.getByRole('button', { name: /Supprimer/ }))
    await waitFor(() => expect(kbApi.removeBloc).toHaveBeenCalledWith(7))
  })
})
