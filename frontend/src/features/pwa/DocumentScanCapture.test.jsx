// NTMOB13 — DocumentScanCapture : câblage capture → détection → recadrage →
// onScan. La détection de contour elle-même (documentScan.js) est déjà
// couverte en profondeur par documentScan.test.jsx (logique pure) ; ce test
// mocke `detectDocumentBounds` pour rester focalisé sur le CÂBLAGE du
// composant (transitions d'écran, badge auto/manuel, appel final onScan).
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('./documentScan', () => ({
  toGrayscale: vi.fn(() => new Float64Array(4)),
  detectDocumentBounds: vi.fn(),
  boundsToInsets: vi.fn(() => ({ top: 5, right: 5, bottom: 5, left: 5 })),
  insetsToBounds: vi.fn((insets, w, h) => ({ x: 0, y: 0, width: w, height: h })),
  MIN_CONFIDENCE: 0.5,
}))

// Simule la caméra : un clic remet immédiatement un faux fichier + une
// géoloc au parent via onCapture — même patron que NumeriserPage.test.jsx.
vi.mock('./CameraCapture', () => ({
  default: ({ onCapture, onClose }) => (
    <div>
      <button type="button" onClick={() => onCapture(
        new File(['raw'], 'raw.jpg', { type: 'image/jpeg' }),
        { latitude: 33.5, longitude: -7.6, precision_m: 10 })}>
        Simuler capture
      </button>
      <button type="button" onClick={onClose}>Fermer caméra</button>
    </div>
  ),
}))

import DocumentScanCapture from './DocumentScanCapture'
import { detectDocumentBounds } from './documentScan'

function installDomMocks() {
  globalThis.Image = class {
    constructor() { this.naturalWidth = 800; this.naturalHeight = 600 }
    set src(_v) { queueMicrotask(() => this.onload?.()) }
  }
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:fake')
  globalThis.URL.revokeObjectURL = vi.fn()
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
    drawImage: vi.fn(),
    getImageData: vi.fn(() => ({ data: new Uint8ClampedArray(4) })),
  }))
  HTMLCanvasElement.prototype.toBlob = vi.fn((cb) => {
    cb(new Blob(['cropped'], { type: 'image/jpeg' }))
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  installDomMocks()
})
afterEach(() => cleanup())

async function simulateCapture(user) {
  await user.click(screen.getByRole('button', { name: 'Simuler capture' }))
}

describe('DocumentScanCapture (NTMOB13)', () => {
  it('détection confiante → écran de revue avec le badge « détecté »', async () => {
    detectDocumentBounds.mockReturnValue(
      { x: 10, y: 10, width: 700, height: 500, confidence: 1 })
    const user = userEvent.setup()
    render(<DocumentScanCapture onScan={vi.fn()} onClose={vi.fn()} />)

    await simulateCapture(user)
    expect(await screen.findByText(/Document détecté/)).toBeInTheDocument()
  })

  it('confiance insuffisante → repli manuel explicite (jamais un blocage)', async () => {
    detectDocumentBounds.mockReturnValue(
      { x: 0, y: 0, width: 800, height: 600, confidence: 0 })
    const user = userEvent.setup()
    render(<DocumentScanCapture onScan={vi.fn()} onClose={vi.fn()} />)

    await simulateCapture(user)
    expect(await screen.findByText(/Recadrage manuel/)).toBeInTheDocument()
  })

  it('Valider envoie le fichier recadré + la géoloc au parent, puis ferme', async () => {
    detectDocumentBounds.mockReturnValue(
      { x: 10, y: 10, width: 700, height: 500, confidence: 1 })
    const user = userEvent.setup()
    const onScan = vi.fn()
    const onClose = vi.fn()
    render(<DocumentScanCapture onScan={onScan} onClose={onClose} />)

    await simulateCapture(user)
    await screen.findByText(/Document détecté/)
    await user.click(screen.getByRole('button', { name: /valider et envoyer/i }))

    await waitFor(() => expect(onScan).toHaveBeenCalledTimes(1))
    const [file, geo] = onScan.mock.calls[0]
    expect(file).toBeInstanceOf(File)
    expect(geo).toEqual({ latitude: 33.5, longitude: -7.6, precision_m: 10 })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('Reprendre revient à la caméra sans jamais appeler onScan', async () => {
    detectDocumentBounds.mockReturnValue(
      { x: 10, y: 10, width: 700, height: 500, confidence: 1 })
    const user = userEvent.setup()
    const onScan = vi.fn()
    render(<DocumentScanCapture onScan={onScan} onClose={vi.fn()} />)

    await simulateCapture(user)
    await screen.findByText(/Document détecté/)
    await user.click(screen.getByRole('button', { name: /reprendre la photo/i }))

    expect(await screen.findByRole('button', { name: 'Simuler capture' })).toBeInTheDocument()
    expect(onScan).not.toHaveBeenCalled()
  })

  it('les 4 curseurs de marge (haut/gauche/droite/bas) sont exposés pour ajustement manuel', async () => {
    detectDocumentBounds.mockReturnValue(
      { x: 0, y: 0, width: 800, height: 600, confidence: 0 })
    const user = userEvent.setup()
    render(<DocumentScanCapture onScan={vi.fn()} onClose={vi.fn()} />)

    await simulateCapture(user)
    await screen.findByText(/Recadrage manuel/)
    expect(screen.getByRole('slider', { name: 'Marge haute' })).toBeInTheDocument()
    expect(screen.getByRole('slider', { name: 'Marge gauche' })).toBeInTheDocument()
    expect(screen.getByRole('slider', { name: 'Marge droite' })).toBeInTheDocument()
    expect(screen.getByRole('slider', { name: 'Marge basse' })).toBeInTheDocument()
  })
})
