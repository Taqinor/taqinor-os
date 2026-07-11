import { describe, it, expect } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { ThemeProvider } from '../design/ThemeProvider'
import { Toaster } from './Toaster'
import { toastError, toastSuccess } from '../lib/toast'

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
