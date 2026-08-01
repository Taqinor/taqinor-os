import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ImportDxf from './ImportDxf'

/* AOF81 — l'écran est livrable AVANT l'endpoint de parsing : les deux chemins
   dégradés (analyseur absent / analyseur en erreur) DOIVENT rendre un message
   FR et un repli, jamais une page blanche. Le chemin nominal est vérifié sur un
   payload de calques simulé. */

const PAYLOAD = {
  unite: 'cm',
  calques: [
    {
      nom: 'TOITURE',
      entites: 1,
      sommets: [
        [0, 0],
        [2562, 0],
        [2562, 5110],
        [0, 5110],
      ],
    },
    { nom: 'EDICULES', entites: 28 },
    { nom: 'COTES', entites: 64 },
  ],
}

function fichierDxf() {
  return new File(['0\nSECTION\n'], 'plan-toiture.dxf', { type: 'image/vnd.dxf' })
}

describe('ImportDxf (AOF81)', () => {
  it('sans analyseur, dégrade avec un message FR et un repli — aucune page blanche', async () => {
    const user = userEvent.setup()
    const onTracerAlaMain = vi.fn()
    render(<ImportDxf onTracerAlaMain={onTracerAlaMain} />)
    await user.upload(screen.getByLabelText('Fichier DXF'), fichierDxf())

    const bloc = await screen.findByRole('alert')
    expect(bloc.textContent).toMatch(/pas encore disponible/i)
    expect(bloc.textContent).toMatch(/tracer la toiture à la main/i)
    await user.click(screen.getByRole('button', { name: /Tracer la toiture à la main/i }))
    expect(onTracerAlaMain).toHaveBeenCalled()
  })

  it('un endpoint absent (404) donne le même message explicite', async () => {
    const user = userEvent.setup()
    const analyserDxf = vi.fn().mockRejectedValue({ response: { status: 404 } })
    render(<ImportDxf analyserDxf={analyserDxf} />)
    await user.upload(screen.getByLabelText('Fichier DXF'), fichierDxf())
    const bloc = await screen.findByRole('alert')
    expect(bloc.textContent).toMatch(/pas encore disponible/i)
  })

  it('une erreur serveur (500) est expliquée en français, sans écran vide', async () => {
    const user = userEvent.setup()
    const analyserDxf = vi.fn().mockRejectedValue({ response: { status: 500 } })
    render(<ImportDxf analyserDxf={analyserDxf} />)
    await user.upload(screen.getByLabelText('Fichier DXF'), fichierDxf())
    const bloc = await screen.findByRole('alert')
    expect(bloc.textContent).toMatch(/erreur 500/i)
    expect(screen.getByRole('button', { name: /Tracer la toiture à la main/i })).toBeTruthy()
  })

  it('un DXF sans calque exploitable dégrade proprement', async () => {
    const user = userEvent.setup()
    const analyserDxf = vi.fn().mockResolvedValue({ calques: [] })
    render(<ImportDxf analyserDxf={analyserDxf} />)
    await user.upload(screen.getByLabelText('Fichier DXF'), fichierDxf())
    const bloc = await screen.findByRole('alert')
    expect(bloc.textContent).toMatch(/aucun calque exploitable/i)
  })

  it('liste les calques avec leur nombre d’entités et présélectionne l’enveloppe', async () => {
    const user = userEvent.setup()
    const analyserDxf = vi.fn().mockResolvedValue(PAYLOAD)
    render(<ImportDxf analyserDxf={analyserDxf} />)
    await user.upload(screen.getByLabelText('Fichier DXF'), fichierDxf())

    await screen.findByText('EDICULES')
    expect(screen.getByText('28')).toBeTruthy()
    expect(screen.getByText('64')).toBeTruthy()
    // Le calque porteur des sommets est présélectionné comme enveloppe.
    expect(screen.getByLabelText("Calque d'enveloppe : TOITURE")).toBeChecked()
    // L'unité annoncée par le payload est reprise.
    expect(screen.getByLabelText('Unité du fichier')).toHaveValue('cm')
  })

  it('l’aperçu se recentre automatiquement sur le calque d’enveloppe', async () => {
    const user = userEvent.setup()
    render(<ImportDxf analyserDxf={vi.fn().mockResolvedValue(PAYLOAD)} />)
    await user.upload(screen.getByLabelText('Fichier DXF'), fichierDxf())
    const svg = await waitFor(() => document.querySelector('[data-ao-dxf-apercu]'))
    const [x, y, l, h] = svg.getAttribute('data-viewbox').split(' ').map(Number)
    // Marge de 8 % du plus grand côté (5110) autour de la boîte englobante.
    expect(x).toBeCloseTo(-408.8, 1)
    expect(y).toBeCloseTo(-408.8, 1)
    expect(l).toBeCloseTo(2562 + 817.6, 1)
    expect(h).toBeCloseTo(5110 + 817.6, 1)
  })

  it('le mapping importé convertit les sommets vers les mètres', async () => {
    const user = userEvent.setup()
    const onImporter = vi.fn()
    render(<ImportDxf analyserDxf={vi.fn().mockResolvedValue(PAYLOAD)} onImporter={onImporter} />)
    await user.upload(screen.getByLabelText('Fichier DXF'), fichierDxf())
    await screen.findByText('EDICULES')
    await user.click(screen.getByLabelText("Calque d'obstacles : EDICULES"))
    await user.click(screen.getByRole('button', { name: /Importer ce mapping/i }))

    const arg = onImporter.mock.calls[0][0]
    expect(arg.calqueEnveloppe).toBe('TOITURE')
    expect(arg.calquesObstacles).toEqual(['EDICULES'])
    expect(arg.unite).toBe('cm')
    expect(arg.facteurVersMetres).toBe(0.01)
    expect(arg.sommets[1][0]).toBeCloseTo(25.62, 5)
    expect(arg.sommets[2][1]).toBeCloseTo(51.1, 5)
  })
})
