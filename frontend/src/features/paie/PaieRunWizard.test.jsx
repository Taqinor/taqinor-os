import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { Toaster } from '../../ui'

/* PACT154 — « Run 13e mois » : run_gratification (backend/django_core/apps/
   paie/views.py:650-672) renvoie {bulletins, nombre} — jamais `crees`.
   `data?.crees ?? 0` affichait donc toujours 0 bulletin généré alors que N
   venaient d'être créés. Comme PaieDeclarations.test.jsx (méthodes paieApi
   non pilotées auto-mockées via Proxy pour ne rien casser au montage). */

const PERIODE = { id: 9, libelle: 'Décembre 2026', mois: 12, annee: 2026, statut: 'brouillon' }

vi.mock('../../api/paieApi', () => {
  const specific = {
    getPeriodes: vi.fn(() => Promise.resolve({ data: [PERIODE] })),
    getProfils: vi.fn(() => Promise.resolve({ data: [] })),
    runGratification: vi.fn(() => Promise.resolve({
      data: { bulletins: [201, 202, 203], nombre: 3 },
    })),
  }
  const handler = {
    get(target, prop) {
      if (prop in target || typeof prop !== 'string') return target[prop]
      target[prop] = vi.fn(() => Promise.resolve({ data: [] }))
      return target[prop]
    },
  }
  return { default: new Proxy(specific, handler) }
})

import paieApi from '../../api/paieApi'
import PaieRunWizard from './PaieRunWizard.jsx'

function wrap(ui) {
  return render(
    <ThemeProvider>
      <Toaster />
      {ui}
    </ThemeProvider>,
  )
}

describe('PaieRunWizard — Run 13e mois (PACT154)', () => {
  it('affiche le compte réel de bulletins générés (`nombre`, jamais `crees`)', async () => {
    wrap(<PaieRunWizard />)

    await userEvent.click(await screen.findByRole('button', { name: /Décembre 2026/ }))
    await userEvent.click(await screen.findByRole('button', { name: /Run 13e mois/ }))

    await waitFor(() => expect(paieApi.runGratification).toHaveBeenCalledWith(9))
    await waitFor(() => {
      expect(document.querySelector('[data-sonner-toast][data-type="success"]'))
        .toHaveTextContent('3 bulletin(s) de 13e mois généré(s).')
    })
  })
})
