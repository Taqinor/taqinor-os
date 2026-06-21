import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

/* jsdom est recréé entre fichiers mais pas entre tests : on démonte le DOM
   après chaque test pour garder les `getByRole`/`getByLabelText` déterministes. */
afterEach(() => {
  cleanup()
})
