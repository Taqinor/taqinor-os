import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { RecordShell } from './RecordShell.jsx'

/* ARC46 — Coquille d'enregistrement (pendant détail/formulaire de ListShell).
   On vérifie le RENDU (en-tête <h1> + retour + statut + actions, onglets, slot
   chatter) — calqué sur DetailShell — ET la barre d'enregistrement optionnelle
   branchée useOptimisticSave (masquée sans onSave, gating « modifié », état
   'Enregistrement…'/'Enregistré'). */

function withRouter(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('RecordShell (ARC46)', () => {
  it('rend le titre en <h1> (heading), le lien retour et les actions', () => {
    withRouter(
      <RecordShell
        title="Dossier #7"
        subtitle="Bennani Youssef"
        backTo="/rh/employes"
        backLabel="Retour aux employés"
        actions={<button type="button">Sortie</button>}
      />,
    )
    expect(screen.getByRole('heading', { name: 'Dossier #7' })).toBeInTheDocument()
    expect(screen.getByText('Bennani Youssef')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Retour aux employés/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sortie' })).toBeInTheDocument()
  })

  it('rend les onglets et le contenu du premier onglet', () => {
    withRouter(
      <RecordShell
        title="X"
        tabs={[
          { value: 'a', label: 'Identité', content: <p>Contenu identité</p> },
          { value: 'b', label: 'Contrat', content: <p>Contenu contrat</p> },
        ]}
      />,
    )
    expect(screen.getByRole('tab', { name: 'Identité' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Contrat' })).toBeInTheDocument()
    expect(screen.getByText('Contenu identité')).toBeInTheDocument()
  })

  it('rend le slot chatter (activité) dans le panneau latéral', () => {
    withRouter(
      <RecordShell title="X" chatter={<div>Historique ici</div>}>
        <p>Corps</p>
      </RecordShell>,
    )
    expect(screen.getByText('Historique ici')).toBeInTheDocument()
    expect(screen.getByText('Corps')).toBeInTheDocument()
  })

  it('NE rend PAS de barre d’enregistrement sans onSave (comportement lecture)', () => {
    withRouter(<RecordShell title="X"><p>Corps</p></RecordShell>)
    expect(document.querySelector('[data-record-savebar]')).toBeNull()
    expect(screen.queryByRole('button', { name: /Enregistrer/ })).toBeNull()
  })

  it('rend la barre d’enregistrement branchée useOptimisticSave quand onSave est fourni', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn(() => Promise.resolve({ ok: true }))
    withRouter(
      <RecordShell title="X" record={{ id: 1, nom: 'A' }} onSave={onSave} />,
    )
    const btn = screen.getByRole('button', { name: /Enregistrer/ })
    expect(btn).toBeEnabled()

    await user.click(btn)
    expect(onSave).toHaveBeenCalledTimes(1)
    // Après succès : libellé d'état « Enregistré ».
    await waitFor(() =>
      expect(screen.getByText('Enregistré')).toBeInTheDocument())
  })

  it('le bouton d’enregistrement est bloqué quand `dirty` est faux', () => {
    withRouter(
      <RecordShell title="X" record={{ id: 1 }} dirty={false} onSave={vi.fn()} />,
    )
    expect(screen.getByRole('button', { name: /Enregistrer/ })).toBeDisabled()
  })

  it('honore un libellé de bouton personnalisé', () => {
    withRouter(
      <RecordShell title="X" record={{ id: 1 }} onSave={vi.fn()} saveLabel="Valider la fiche" />,
    )
    expect(screen.getByRole('button', { name: 'Valider la fiche' })).toBeInTheDocument()
  })
})
