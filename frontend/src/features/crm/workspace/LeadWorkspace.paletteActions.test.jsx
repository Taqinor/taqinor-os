import { describe, it, expect, vi } from 'vitest'
import { renderLeadWorkspace } from '../../../test/leadWorkspaceHarness'
import { LEAD_A, installerHooksLeadWorkspace } from '../../../test/leadWorkspaceMocks'
import { render, screen, act } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import crmReducer from '../store/crmSlice'
import { readRecentEntities } from '../../../providers/commandActions'
import LeadWorkspace from './LeadWorkspace'

/* LW26 — actions contextuelles ⌘K (taqinor:lead-workspace-actions) + Récents.
   Mêmes neutralisations que LeadWorkspaceCreate.test.jsx, sauf LeadDevisPanel
   (exposé pour vérifier le mode passé par « Devis automatique »). */
vi.mock('../../../pages/crm/leads/LeadDevisPanel', () => ({
  default: (props) => <div data-testid="devis-panel" data-mode={props.mode} />,
}))
vi.mock('../../../pages/crm/leads/SigneDialog', () => ({ default: () => null }))

vi.mock('../../../api/crmApi', async () => (await import('../../../test/leadWorkspaceMocks')).crmApiLeadWorkspace())


installerHooksLeadWorkspace()

function renderEdit(lead = LEAD_A) {
  return renderLeadWorkspace({ lead })
}

describe('LW26 — actions contextuelles ⌘K + Récents', () => {
  it('poste taqinor:lead-workspace-actions au montage avec les actions attendues, le retire au démontage', () => {
    const onEvt = vi.fn()
    window.addEventListener('taqinor:lead-workspace-actions', onEvt)
    const { unmount } = renderEdit()
    expect(onEvt).toHaveBeenCalled()
    const actions = onEvt.mock.calls[onEvt.mock.calls.length - 1][0].detail.actions
    const ids = actions.map((a) => a.id)
    expect(ids).toEqual(expect.arrayContaining([
      'lw-wa-devis', 'lw-devis-auto', 'lw-archive', 'lw-convert', 'lw-note', 'lw-goto-toiture',
    ]))
    unmount()
    const lastCall = onEvt.mock.calls[onEvt.mock.calls.length - 1][0]
    expect(lastCall.detail.actions).toEqual([])
    window.removeEventListener('taqinor:lead-workspace-actions', onEvt)
  })

  it('pousse le lead dans les Récents à l’ouverture, AVEC le vrai nom (jamais vide)', () => {
    renderEdit()
    const recent = readRecentEntities()
    // LW44 — avant le fix, le libellé était TOUJOURS vide à la 1re ouverture
    // (`nomTitreRef` pas encore resynchronisé quand ce push lisait sa valeur).
    expect(recent[0]).toMatchObject({ type: 'lead', id: 1, label: 'Lead — Ali Ben' })
  })

  it('navigation vers un autre lead → les Récents portent le nom du NOUVEAU lead, jamais le précédent', () => {
    const store = configureStore({ reducer: { crm: crmReducer, auth: (s = { user: { id: 42 } }) => s } })
    const wrap = (lead) => (
      <Provider store={store}>
        <MemoryRouter>
          <LeadWorkspace lead={lead} onClose={vi.fn()} onSaved={vi.fn()} />
        </MemoryRouter>
      </Provider>
    )
    const { rerender } = render(wrap(LEAD_A))
    expect(readRecentEntities()[0]).toMatchObject({ id: 1, label: 'Lead — Ali Ben' })
    const LEAD_B = { id: 2, nom: 'Zohra', prenom: 'Idrissi', stage: 'NEW', is_archived: false }
    rerender(wrap(LEAD_B))
    // LW44 — avant le fix, ce push lisait encore le nom du lead PRÉCÉDENT
    // (A), le réducteur n'ayant pas encore rejoué LOAD_LEAD au moment où
    // l'ancien effet lisait sa ref.
    expect(readRecentEntities()[0]).toMatchObject({ type: 'lead', id: 2, label: 'Lead — Zohra Idrissi' })
  })

  it('l’action « Devis automatique » ouvre le panneau devis en mode auto', () => {
    let captured = null
    const onEvt = (e) => { captured = e.detail.actions }
    window.addEventListener('taqinor:lead-workspace-actions', onEvt)
    renderEdit()
    window.removeEventListener('taqinor:lead-workspace-actions', onEvt)
    const devisAuto = captured.find((a) => a.id === 'lw-devis-auto')
    expect(devisAuto).toBeDefined()
    act(() => { devisAuto.run() })
    expect(screen.getByTestId('devis-panel')).toHaveAttribute('data-mode', 'auto')
  })

  it('QJR599 — l’action « Nouveau devis (édition complète) » ouvre le panneau devis en mode edit', () => {
    let captured = null
    const onEvt = (e) => { captured = e.detail.actions }
    window.addEventListener('taqinor:lead-workspace-actions', onEvt)
    renderEdit()
    window.removeEventListener('taqinor:lead-workspace-actions', onEvt)
    const edition = captured.find((a) => a.id === 'lw-devis-edition')
    expect(edition).toBeDefined()
    act(() => { edition.run() })
    expect(screen.getByTestId('devis-panel')).toHaveAttribute('data-mode', 'edit')
  })

  it('l’action « Aller à : Toiture & site » fait défiler jusqu’à la section', () => {
    let captured = null
    const onEvt = (e) => { captured = e.detail.actions }
    window.addEventListener('taqinor:lead-workspace-actions', onEvt)
    renderEdit()
    window.removeEventListener('taqinor:lead-workspace-actions', onEvt)
    const goToToiture = captured.find((a) => a.id === 'lw-goto-toiture')
    expect(goToToiture).toBeDefined()
    const section = document.querySelector('[data-nav-id="toiture"]')
    expect(section).not.toBeNull()
    const scrollSpy = vi.fn()
    section.scrollIntoView = scrollSpy
    act(() => { goToToiture.run() })
    expect(scrollSpy).toHaveBeenCalled()
  })
})
