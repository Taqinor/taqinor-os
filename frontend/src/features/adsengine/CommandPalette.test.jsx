import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* PUB51 — Palette de commandes (Ctrl-K) : saute à un écran (catalogue
   statique) ou une campagne/ad (données tirées puis mises en cache
   module-level — `vi.resetModules()` réinitialise ce cache entre chaque
   test pour l'isolation). */

const mocks = vi.hoisted(() => ({
  campaignsList: vi.fn(),
  adsCockpit: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    campaigns: { list: mocks.campaignsList },
    metrics: { adsCockpit: mocks.adsCockpit },
  },
}))

let CommandPalette

beforeEach(async () => {
  vi.resetModules()
  vi.clearAllMocks()
  mocks.campaignsList.mockResolvedValue({ data: [
    { id: 1, name: 'Campagne Résidentiel Casa' },
    { id: 2, name: 'Campagne Pompage Agadir' },
  ] })
  mocks.adsCockpit.mockResolvedValue({ data: [
    { id: 9, ad_name: 'Reel toiture v1' },
  ] })
  CommandPalette = (await import('./CommandPalette')).default
})

const renderPalette = () => render(<MemoryRouter><CommandPalette /></MemoryRouter>)

const openWithCtrlK = () => fireEvent.keyDown(window, { key: 'k', ctrlKey: true })

describe('CommandPalette (PUB51)', () => {
  it('est invisible tant que Ctrl-K n\'a pas été pressé', () => {
    renderPalette()
    expect(screen.queryByTestId('ae-command-palette')).toBeNull()
  })

  it('Ctrl-K ouvre la palette et Escape la ferme', async () => {
    renderPalette()
    openWithCtrlK()
    expect(await screen.findByTestId('ae-command-palette')).toBeInTheDocument()
    fireEvent.keyDown(screen.getByTestId('ae-command-palette-input'), { key: 'Escape' })
    await waitFor(() => expect(screen.queryByTestId('ae-command-palette')).toBeNull())
  })

  it('affiche le catalogue des écrans par défaut (sans saisie)', async () => {
    renderPalette()
    openWithCtrlK()
    const items = await screen.findAllByTestId('ae-command-palette-item')
    expect(items.length).toBeGreaterThan(10) // les 17 écrans
    expect(items.some(i => i.textContent.includes("L'Arbre"))).toBe(true)
  })

  it('filtre les écrans par la saisie', async () => {
    renderPalette()
    openWithCtrlK()
    const input = await screen.findByTestId('ae-command-palette-input')
    fireEvent.change(input, { target: { value: 'arbre' } })
    const items = screen.getAllByTestId('ae-command-palette-item')
    expect(items.length).toBe(1)
    expect(items[0]).toHaveTextContent("L'Arbre")
  })

  it('tire les campagnes une fois ouverte et les propose dans la recherche', async () => {
    renderPalette()
    openWithCtrlK()
    await waitFor(() => expect(mocks.campaignsList).toHaveBeenCalled())
    const input = await screen.findByTestId('ae-command-palette-input')
    fireEvent.change(input, { target: { value: 'résidentiel' } })
    const items = screen.getAllByTestId('ae-command-palette-item')
    expect(items.some(i => i.textContent.includes('Campagne Résidentiel Casa'))).toBe(true)
  })

  it('tire les ads et les propose dans la recherche', async () => {
    renderPalette()
    openWithCtrlK()
    await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
    const input = await screen.findByTestId('ae-command-palette-input')
    fireEvent.change(input, { target: { value: 'toiture' } })
    const items = screen.getAllByTestId('ae-command-palette-item')
    expect(items.some(i => i.textContent.includes('Reel toiture v1'))).toBe(true)
  })

  it('sélectionner un résultat ferme la palette', async () => {
    renderPalette()
    openWithCtrlK()
    const items = await screen.findAllByTestId('ae-command-palette-item')
    fireEvent.click(items[0])
    await waitFor(() => expect(screen.queryByTestId('ae-command-palette')).toBeNull())
  })

  it('Entrée sélectionne le résultat actif et ferme la palette', async () => {
    renderPalette()
    openWithCtrlK()
    const input = await screen.findByTestId('ae-command-palette-input')
    fireEvent.keyDown(input, { key: 'Enter' })
    await waitFor(() => expect(screen.queryByTestId('ae-command-palette')).toBeNull())
  })

  it('aucune correspondance affiche un état vide', async () => {
    renderPalette()
    openWithCtrlK()
    const input = await screen.findByTestId('ae-command-palette-input')
    fireEvent.change(input, { target: { value: 'zzz-introuvable' } })
    expect(await screen.findByTestId('ae-command-palette-empty')).toBeInTheDocument()
  })

  it('cliquer sur l\'overlay ferme la palette', async () => {
    renderPalette()
    openWithCtrlK()
    await screen.findByTestId('ae-command-palette')
    fireEvent.click(screen.getByTestId('ae-command-palette-overlay'))
    await waitFor(() => expect(screen.queryByTestId('ae-command-palette')).toBeNull())
  })
})
