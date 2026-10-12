/* Aide partagée des tests admin (ENF19) : confirmer la suppression dans l'AlertDialog maison. */
import { expect } from 'vitest'
import { waitFor } from '@testing-library/react'

export async function confirmerSuppression(user) {
  const confirmBtn = await waitFor(() => {
    const btn = [...document.querySelectorAll('[role="alertdialog"] button')]
      .find((b) => b.textContent.trim() === 'Supprimer')
    expect(btn).toBeTruthy()
    return btn
  })
  await user.click(confirmBtn)
}
