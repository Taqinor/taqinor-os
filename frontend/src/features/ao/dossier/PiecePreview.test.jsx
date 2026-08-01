import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

/* AOF175 — prévisualisation de pièce et comparaison de versions.
   Le WORKER pdfjs est déjà posé par un autre consommateur (l'underlay de
   calepinage / `PdfCanvas`) : c'est le cas nominal, et il PROUVE le partage —
   `ensureWorkerPartage()` doit alors rendre la main sans jamais évaluer
   l'import dynamique du worker. */

const pdf = vi.hoisted(() => {
  const GlobalWorkerOptions = { workerPort: { __pose_par: 'underlay' }, workerSrc: null }
  return {
    GlobalWorkerOptions,
    destroy: vi.fn(),
    getDocumentCalls: [],
    viewportScales: [],
  }
})

vi.mock('pdfjs-dist', () => ({
  GlobalWorkerOptions: pdf.GlobalWorkerOptions,
  getDocument: (opts) => {
    pdf.getDocumentCalls.push(opts)
    return {
      promise: Promise.resolve({
        numPages: 1,
        getPage: () => Promise.resolve({
          getViewport: ({ scale }) => {
            pdf.viewportScales.push(scale)
            // Planche A3 paysage : 1190 × 842 pt.
            return { width: 1190 * scale, height: 842 * scale }
          },
          render: () => ({ promise: Promise.resolve() }),
        }),
        destroy: pdf.destroy,
      }),
    }
  },
}))

import PiecePreview, { ensureWorkerPartage } from './PiecePreview'

const PIECE = {
  id: 5, code: 'planche_05H', libelle: 'Planche 05H — bâtiment C',
  indice_revision: 'B', indice_revision_precedent: 'A',
}

// Octets bruts (pas un Blob) : jsdom n'a pas besoin de `Blob.arrayBuffer`.
const octets = (n) => new Uint8Array([37, 80, 68, 70, n])

beforeEach(() => {
  vi.clearAllMocks()
  pdf.getDocumentCalls.length = 0
  pdf.viewportScales.length = 0
  pdf.GlobalWorkerOptions.workerPort = { __pose_par: 'underlay' }
  pdf.GlobalWorkerOptions.workerSrc = null
})

afterEach(() => { document.body.innerHTML = '' })

describe('PiecePreview (AOF175)', () => {
  it('n’introduit AUCUN <iframe> ni <embed> — le PDF est dessiné sur des <canvas>', async () => {
    const { container } = render(<PiecePreview piece={PIECE} blob={octets(1)} />)
    await waitFor(() => expect(container.querySelectorAll('canvas').length).toBe(1))
    expect(container.querySelector('iframe')).toBeNull()
    expect(container.querySelector('embed')).toBeNull()
    expect(container.querySelector('object')).toBeNull()
  })

  it('réutilise le worker pdfjs DÉJÀ posé (un seul worker partagé avec l’underlay)', async () => {
    const portAvant = pdf.GlobalWorkerOptions.workerPort
    await expect(ensureWorkerPartage()).resolves.toBe(false)
    expect(pdf.GlobalWorkerOptions.workerPort).toBe(portAvant)

    render(<PiecePreview piece={PIECE} blob={octets(1)} />)
    await waitFor(() => expect(pdf.getDocumentCalls.length).toBe(1))
    expect(pdf.GlobalWorkerOptions.workerPort).toBe(portAvant)
  })

  it('une planche A3 est lisible AU TRAIT : le zoom agrandit réellement le canvas, sans plafond de largeur', async () => {
    const { container } = render(<PiecePreview piece={PIECE} blob={octets(1)} />)
    await waitFor(() => expect(container.querySelector('canvas')).not.toBeNull())
    const largeur1 = parseFloat(container.querySelector('canvas').style.width)
    // Aucun plafond de largeur (contrairement à l'aperçu A4 des devis).
    expect(container.querySelector('canvas').className).toContain('max-w-none')

    fireEvent.click(screen.getByRole('button', { name: 'Zoomer' }))
    await waitFor(() => {
      const c = container.querySelector('canvas')
      expect(parseFloat(c.style.width)).toBeGreaterThan(largeur1)
    })
    expect(screen.getByText('125 %')).toBeInTheDocument()
  })

  it('« comparer à la version précédente » affiche les DEUX versions côte à côte avec leurs indices', async () => {
    const { container } = render(
      <PiecePreview piece={PIECE} blob={octets(2)} blobPrecedent={octets(1)} />,
    )
    await waitFor(() => expect(container.querySelectorAll('canvas').length).toBe(1))

    fireEvent.click(screen.getByRole('button', { name: /Comparer à la version précédente/ }))
    await waitFor(() => expect(container.querySelectorAll('canvas').length).toBe(2))
    expect(screen.getByText('Version précédente — indice A')).toBeInTheDocument()
    expect(screen.getByText('Version courante — indice B')).toBeInTheDocument()
  })

  it('la comparaison est indisponible (et non trompeuse) sans version précédente', async () => {
    render(<PiecePreview piece={PIECE} blob={octets(1)} />)
    expect(
      screen.getByRole('button', { name: /Comparer à la version précédente/ }),
    ).toBeDisabled()
  })

  it('montage/démontage sans fuite : le document pdfjs est détruit et l’hôte vidé', async () => {
    const { container, unmount } = render(<PiecePreview piece={PIECE} blob={octets(1)} />)
    await waitFor(() => expect(container.querySelectorAll('canvas').length).toBe(1))
    unmount()
    await waitFor(() => expect(pdf.destroy).toHaveBeenCalled())
    expect(document.querySelectorAll('canvas').length).toBe(0)
  })

  it('le plein écran s’ouvre et se quitte (jamais une souricière)', async () => {
    render(<PiecePreview piece={PIECE} blob={octets(1)} />)
    fireEvent.click(screen.getByRole('button', { name: 'Plein écran' }))
    expect(await screen.findByRole('dialog', { name: /Aperçu plein écran/ })).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('sans aperçu disponible, aucun rendu n’est tenté (état vide nommé)', () => {
    render(<PiecePreview piece={PIECE} />)
    expect(screen.getByText('Planche 05H — bâtiment C')).toBeInTheDocument()
    expect(pdf.getDocumentCalls.length).toBe(0)
  })
})
