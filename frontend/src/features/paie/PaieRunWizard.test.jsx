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

// WIR242 — un écart salaire profil ↔ rémunération RH, résorbé par le bouton
// « Synchroniser » du dialogue de contrôles pré-run.
const COMPLETUDE_AVEC_ECART = {
  actifs_sans_profil: [], profils_sans_cnss: [], profils_sans_rib: [],
  profils_actifs_dossiers_non_actifs: [], contrats_expires: [],
  ecarts_remuneration: [{ profil_id: 77, dossier_id: 12, matricule: 'M012', nom: 'A. Test' }],
}
const ECARTS_VIDES = {
  salaries_manquants: [], salaries_nouveaux: [], variations_net: [], hs_anormales: [],
}

vi.mock('../../api/paieApi', () => {
  const specific = {
    getPeriodes: vi.fn(() => Promise.resolve({ data: [PERIODE] })),
    getProfils: vi.fn(() => Promise.resolve({ data: [] })),
    runGratification: vi.fn(() => Promise.resolve({
      data: { bulletins: [201, 202, 203], nombre: 3 },
    })),
    controleCompletude: vi.fn(() => Promise.resolve({ data: COMPLETUDE_AVEC_ECART })),
    controleEcarts: vi.fn(() => Promise.resolve({ data: ECARTS_VIDES })),
    synchroniserSalaireProfil: vi.fn(() => Promise.resolve({ data: { id: 77 } })),
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

describe('PaieRunWizard — Synchroniser un écart salaire (WIR242)', () => {
  it('synchronise le profil en écart et rejoue les contrôles', async () => {
    wrap(<PaieRunWizard />)

    await userEvent.click(await screen.findByRole('button', { name: /Décembre 2026/ }))
    await userEvent.click(await screen.findByRole('button', { name: /Contrôles pré-run/ }))

    await userEvent.click(await screen.findByRole('button', { name: 'Synchroniser' }))

    await waitFor(() => expect(paieApi.synchroniserSalaireProfil).toHaveBeenCalledWith(77))
    await waitFor(() => expect(paieApi.controleCompletude).toHaveBeenCalledTimes(2))
  })
})
