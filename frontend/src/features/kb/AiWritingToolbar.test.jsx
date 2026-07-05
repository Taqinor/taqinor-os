import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import AiWritingToolbar from './AiWritingToolbar'

vi.mock('../../api/iaApi', () => ({
  default: { kbRedaction: vi.fn() },
}))

import iaApi from '../../api/iaApi'

function wrap(ui) {
  return <ThemeProvider>{ui}</ThemeProvider>
}

function renderToolbar(props = {}) {
  const textareaRef = { current: { selectionStart: 0, selectionEnd: 0 } }
  const onApply = vi.fn()
  const utils = render(wrap(
    <AiWritingToolbar textareaRef={textareaRef} corps="Bonjour" onApply={onApply} {...props} />,
  ))
  return { ...utils, onApply, textareaRef }
}

describe('AiWritingToolbar (XKB23)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('avec clé : reformuler remplace la sélection par le résultat', async () => {
    iaApi.kbRedaction.mockResolvedValue({ data: { texte: 'Salut' } })
    const { onApply, textareaRef } = renderToolbar()
    textareaRef.current = { selectionStart: 0, selectionEnd: 7 } // toute la sélection "Bonjour"
    await userEvent.click(screen.getByRole('button', { name: 'Reformuler' }))
    await waitFor(() => expect(iaApi.kbRedaction).toHaveBeenCalledWith(
      expect.objectContaining({ action: 'reformuler', texte: 'Bonjour' }),
    ))
    await waitFor(() => expect(onApply).toHaveBeenCalledWith('Salut'))
  })

  it('avec clé : résumer produit un chapeau ajouté devant le corps', async () => {
    iaApi.kbRedaction.mockResolvedValue({ data: { texte: 'Un résumé net.' } })
    const { onApply } = renderToolbar({ corps: 'Long contenu existant.' })
    await userEvent.click(screen.getByRole('button', { name: 'Résumer' }))
    await waitFor(() => expect(onApply).toHaveBeenCalledWith('Un résumé net.\n\nLong contenu existant.'))
  })

  it('sans clé (erreur config manquante) : message clair, aucun crash', async () => {
    iaApi.kbRedaction.mockRejectedValue({
      response: { data: { detail: 'GROQ_API_KEY manquante dans .env' } },
    })
    const { onApply } = renderToolbar()
    await userEvent.click(screen.getByRole('button', { name: 'Générer' }))
    await waitFor(() => expect(iaApi.kbRedaction).toHaveBeenCalled())
    expect(onApply).not.toHaveBeenCalled()
    // Le composant reste monté et utilisable (pas de throw) : les boutons sont
    // toujours présents après l'échec.
    expect(screen.getByRole('button', { name: 'Reformuler' })).toBeInTheDocument()
  })

  it('available=false masque/désactive proprement la barre entière', () => {
    render(wrap(
      <AiWritingToolbar available={false} textareaRef={{ current: null }} corps="" onApply={vi.fn()} />,
    ))
    expect(screen.queryByTestId('kb-ai-toolbar')).not.toBeInTheDocument()
  })

  it('ne plante pas si aucune donnée (corps/ref undefined)', async () => {
    render(wrap(<AiWritingToolbar onApply={vi.fn()} />))
    expect(screen.getByTestId('kb-ai-toolbar')).toBeInTheDocument()
  })
})
