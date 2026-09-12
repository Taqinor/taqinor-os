/* NTCON36 — capture terrain : 2 taps, brouillon local, file hors-ligne.
 *
 * Ce que le test PROUVE :
 *   - en ligne, une réserve part par l'endpoint normal et sa photo est
 *     téléversée sur l'endpoint multipart EXISTANT (records.Attachment) ;
 *   - hors réseau, l'opération part dans la file GÉNÉRIQUE du dépôt
 *     (`lib/offlineOutbox.queueIfOffline`) — jamais une file maison ;
 *   - la SAISIE est protégée par un brouillon localStorage, restauré au
 *     remontage de l'écran ;
 *   - la photo n'est jamais perdue en silence : hors réseau, l'écran DIT
 *     qu'elle reste à renvoyer et garde le brouillon ;
 *   - une erreur applicative (4xx) est AFFICHÉE et nomme le champ fautif —
 *     jamais un « non enregistré » générique.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

const {
  reservesCreate, journalCreate, uploadAttachment, queueIfOffline,
} = vi.hoisted(() => ({
  reservesCreate: vi.fn(() => Promise.resolve({ data: { id: 77 } })),
  journalCreate: vi.fn(() => Promise.resolve({ data: { id: 12 } })),
  uploadAttachment: vi.fn(() => Promise.resolve({ data: {} })),
  queueIfOffline: vi.fn(),
}))

vi.mock('../../api/btpChantierApi', () => ({
  default: {
    reserves: { create: reservesCreate },
    journal: { create: journalCreate },
  },
}))
vi.mock('../../api/recordsApi', () => ({
  default: { uploadAttachment },
}))
vi.mock('../../lib/offlineOutbox', () => ({ queueIfOffline }))
vi.mock('../../features/btp_chantier/ChantierSelect', () => ({
  default: ({ value, onChange }) => (
    <select
      aria-label="Chantier"
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">Chantier…</option>
      <option value="5">CH-5</option>
    </select>
  ),
}))

import TerrainCapture from './TerrainCapture'

function monter() {
  return render(
    <ThemeProvider>
      <MemoryRouter>
        <TerrainCapture />
      </MemoryRouter>
    </ThemeProvider>,
  )
}

/** Rejoue le comportement réel : appel en ligne d'abord, file si réseau HS. */
function enLigne() {
  queueIfOffline.mockImplementation(async (_module, onlineCall) => ({
    queued: false, data: await onlineCall(),
  }))
}
function horsReseau() {
  queueIfOffline.mockImplementation(async () => ({
    queued: true, clientOpId: 'op-1',
  }))
}

describe('NTCON36 — capture terrain', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    enLigne()
  })

  it('enregistre une réserve en ligne et téléverse sa photo', async () => {
    const user = userEvent.setup()
    monter()
    await user.selectOptions(screen.getByLabelText('Chantier'), '5')
    await user.type(
      screen.getByLabelText('Description de la réserve'),
      'Tableau non conforme')
    const fichier = new File(['x'], 'photo.jpg', { type: 'image/jpeg' })
    await user.upload(screen.getByLabelText('Photo de la réserve'), fichier)
    await user.click(screen.getByTestId('btp-terrain-enregistrer'))

    await waitFor(() => expect(reservesCreate).toHaveBeenCalledTimes(1))
    expect(reservesCreate.mock.calls[0][0]).toMatchObject({
      chantier: 5, description: 'Tableau non conforme', gravite: 'mineure',
    })
    await waitFor(() => expect(uploadAttachment).toHaveBeenCalledTimes(1))
    expect(uploadAttachment.mock.calls[0][0])
      .toBe('btp_chantier.reservechantier')
    expect(uploadAttachment.mock.calls[0][1]).toBe(77)
    expect(uploadAttachment.mock.calls[0][3]).toBe('avant')
  })

  it('passe par la file GÉNÉRIQUE hors réseau (jamais une file maison)', async () => {
    horsReseau()
    const user = userEvent.setup()
    monter()
    await user.selectOptions(screen.getByLabelText('Chantier'), '5')
    await user.type(
      screen.getByLabelText('Description de la réserve'), 'Gaine bloquée')
    await user.click(screen.getByTestId('btp-terrain-enregistrer'))

    await waitFor(() => expect(queueIfOffline).toHaveBeenCalledTimes(1))
    const [module, , opType, charge] = queueIfOffline.mock.calls[0]
    expect(module).toBe('installations')
    expect(opType).toBe('btp.reserve.creer')
    expect(charge).toMatchObject({ chantier: 5, description: 'Gaine bloquée' })
    expect(await screen.findByTestId('btp-terrain-message'))
      .toHaveTextContent(/hors réseau/i)
  })

  it('dit que la photo reste à renvoyer, et garde le brouillon', async () => {
    horsReseau()
    const user = userEvent.setup()
    monter()
    await user.selectOptions(screen.getByLabelText('Chantier'), '5')
    const description = screen.getByLabelText('Description de la réserve')
    await user.type(description, 'Fissure')
    await user.upload(
      screen.getByLabelText('Photo de la réserve'),
      new File(['x'], 'photo.jpg', { type: 'image/jpeg' }))
    await user.click(screen.getByTestId('btp-terrain-enregistrer'))

    const message = await screen.findByTestId('btp-terrain-message')
    expect(message).toHaveTextContent(/photo/i)
    // La saisie n'est PAS effacée tant que la photo n'est pas partie.
    expect(description).toHaveValue('Fissure')
  })

  it('restaure le brouillon local au remontage', async () => {
    const user = userEvent.setup()
    const { unmount } = monter()
    await user.selectOptions(screen.getByLabelText('Chantier'), '5')
    await user.type(
      screen.getByLabelText('Description de la réserve'), 'Reprise VRD')
    unmount()

    monter()
    await waitFor(() => {
      expect(screen.getByLabelText('Description de la réserve'))
        .toHaveValue('Reprise VRD')
    })
    expect(screen.getByLabelText('Chantier')).toHaveValue('5')
  })

  it('enregistre l’entrée du journal du jour', async () => {
    const user = userEvent.setup()
    monter()
    await user.click(screen.getByTestId('btp-terrain-onglet-journal'))
    await user.selectOptions(screen.getByLabelText('Chantier'), '5')
    await user.type(screen.getByLabelText('Météo du jour'), 'Ensoleillé')
    await user.click(screen.getByTestId('btp-terrain-enregistrer'))

    await waitFor(() => expect(journalCreate).toHaveBeenCalledTimes(1))
    expect(journalCreate.mock.calls[0][0]).toMatchObject({
      chantier: 5, meteo: 'Ensoleillé',
    })
    expect(journalCreate.mock.calls[0][0].date).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })

  it('affiche l’erreur du serveur en nommant le champ fautif', async () => {
    queueIfOffline.mockImplementation(async () => {
      const err = new Error('400')
      err.response = { status: 400, data: { description: 'Ce champ est requis.' } }
      throw err
    })
    const user = userEvent.setup()
    monter()
    await user.selectOptions(screen.getByLabelText('Chantier'), '5')
    await user.type(
      screen.getByLabelText('Description de la réserve'), 'x')
    await user.click(screen.getByTestId('btp-terrain-enregistrer'))

    const erreur = await screen.findByTestId('btp-terrain-erreur')
    expect(erreur).toHaveTextContent(/requis/i)
  })

  it('n’enregistre rien sans chantier ni description', async () => {
    monter()
    expect(screen.getByTestId('btp-terrain-enregistrer')).toBeDisabled()
    expect(reservesCreate).not.toHaveBeenCalled()
  })
})
