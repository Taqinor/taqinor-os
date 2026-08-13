// NTMOB17 — mode « Économie de données ».
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import {
  getDataSaverPref, setDataSaverPref, dataSaverInterval,
  compressPhotoForUpload, setPhotoQualityPref,
  DATA_SAVER_POLL_FACTOR,
} from './prefs'
import DataSaverThumb from '../../features/pwa/DataSaverThumb'

vi.mock('../../ui/file-utils', () => ({
  compressImage: vi.fn(async () => 'compressee'),
}))

describe('NTMOB17 — préférence économie de données', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('est désactivée par défaut et persiste une fois activée', () => {
    expect(getDataSaverPref()).toBe(false)
    setDataSaverPref(true)
    expect(getDataSaverPref()).toBe(true)
    setDataSaverPref(false)
    expect(getDataSaverPref()).toBe(false)
  })

  it('ralentit les cadences de sondage quand elle est active', () => {
    expect(dataSaverInterval(3000, false)).toBe(3000)
    expect(dataSaverInterval(3000, true)).toBe(3000 * DATA_SAVER_POLL_FACTOR)
  })

  it('force la compression photo même si « Original » est choisi', async () => {
    setPhotoQualityPref('original')
    expect(await compressPhotoForUpload('brute')).toBe('brute')
    setDataSaverPref(true)
    expect(await compressPhotoForUpload('brute')).toBe('compressee')
  })
})

describe('NTMOB17 — vignette DataSaverThumb', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('charge l\'image immédiatement quand le mode est inactif', () => {
    render(<DataSaverThumb src="/photo.jpg" alt="toit" onActivate={() => {}} />)
    expect(screen.getByRole('img', { name: 'toit' })).toHaveAttribute('src', '/photo.jpg')
  })

  it('n\'émet aucune requête image tant que la vignette n\'est pas touchée', () => {
    setDataSaverPref(true)
    const onActivate = vi.fn()
    render(<DataSaverThumb src="/photo.jpg" alt="toit" onActivate={onActivate} />)
    expect(screen.queryByRole('img')).toBeNull()
    const bouton = screen.getByRole('button', { name: /Charger l'aperçu de toit/ })
    // Premier tap : la vignette se charge, la visionneuse ne s'ouvre pas.
    fireEvent.click(bouton)
    expect(onActivate).not.toHaveBeenCalled()
    expect(screen.getByRole('img', { name: 'toit' })).toHaveAttribute('src', '/photo.jpg')
    // Tap suivant : comportement normal.
    fireEvent.click(screen.getByRole('button'))
    expect(onActivate).toHaveBeenCalledTimes(1)
  })
})
