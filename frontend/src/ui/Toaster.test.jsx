import { describe, it, expect } from 'vitest'
import { render, screen, act, waitFor } from '@testing-library/react'
import { ThemeProvider } from '../design/ThemeProvider'
import { Toaster } from './Toaster'
import { toastError, toastSuccess, toastInfo, toastWarning } from '../lib/toast'

describe('Toaster (VX196 — announceur assertif des erreurs)', () => {
  it('relaie toastError vers une région role="alert"/aria-live="assertive"', async () => {
    render(
      <ThemeProvider>
        <Toaster />
      </ThemeProvider>,
    )
    const region = screen.getByRole('alert')
    expect(region).toHaveAttribute('aria-live', 'assertive')
    await act(async () => {
      toastError('Le changement d’étape n’a pas pu être enregistré')
    })
    expect(region).toHaveTextContent('Le changement d’étape n’a pas pu être enregistré')
  })

  it('toastSuccess ne touche pas la région assertive', async () => {
    render(
      <ThemeProvider>
        <Toaster />
      </ThemeProvider>,
    )
    const region = screen.getByRole('alert')
    await act(async () => {
      toastSuccess('Enregistré.')
    })
    expect(region).toHaveTextContent('')
  })
})

// VX130 — le toast devient un objet de marque : 4 variantes distinctes,
// chacune dérivée des MÊMES tokens sémantiques que Badge (parité clair/
// sombre automatique), plus richColors (couleurs génériques hors thème).
describe('VX130 — Toaster : 4 variantes de type dérivées des tokens (parité Badge)', () => {
  function renderToaster() {
    return render(
      <ThemeProvider>
        <Toaster />
      </ThemeProvider>,
    )
  }

  it('toastSuccess : classe success dérivée de --success (bg-success/12 border-success/40)', async () => {
    renderToaster()
    await act(async () => { toastSuccess('Enregistré.') })
    await waitFor(() => {
      const el = document.querySelector('[data-sonner-toast][data-type="success"]')
      expect(el).toBeTruthy()
      expect(el.className).toMatch(/bg-success\/12/)
      expect(el.className).toMatch(/border-success\/40/)
      expect(el.className).toMatch(/text-success/)
    })
  })

  it('toastError : classe error dérivée de --destructive', async () => {
    renderToaster()
    await act(async () => { toastError('Échec.') })
    await waitFor(() => {
      const el = document.querySelector('[data-sonner-toast][data-type="error"]')
      expect(el).toBeTruthy()
      expect(el.className).toMatch(/bg-destructive\/12/)
      expect(el.className).toMatch(/text-destructive/)
    })
  })

  it('toastWarning : classe warning dérivée de --warning', async () => {
    renderToaster()
    await act(async () => { toastWarning('Stock bas.') })
    await waitFor(() => {
      const el = document.querySelector('[data-sonner-toast][data-type="warning"]')
      expect(el).toBeTruthy()
      expect(el.className).toMatch(/bg-warning\/12/)
      expect(el.className).toMatch(/text-warning/)
    })
  })

  it('toastInfo : classe info dérivée de --info', async () => {
    renderToaster()
    await act(async () => { toastInfo('Nouvelle version.') })
    await waitFor(() => {
      const el = document.querySelector('[data-sonner-toast][data-type="info"]')
      expect(el).toBeTruthy()
      expect(el.className).toMatch(/bg-info\/12/)
      expect(el.className).toMatch(/text-info/)
    })
  })

})
