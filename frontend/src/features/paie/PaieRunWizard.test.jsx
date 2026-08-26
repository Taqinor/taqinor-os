import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
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

describe('PaieRunWizard — Contrôles pré-run : synchroniser-salaire (WIR242)', () => {
  const ECART = {
    profil_id: 55, dossier_id: 8, matricule: 'M008', nom: 'Amrani Yassine',
    salaire_profil: 6000, remuneration_en_vigueur: 6500, date_effet: '2026-01-01',
  }
  const COMPLETUDE_VIDE = {
    actifs_sans_profil: [], profils_sans_cnss: [], profils_sans_rib: [],
    profils_actifs_dossiers_non_actifs: [], contrats_expires: [],
    ecarts_remuneration: [],
  }
  const ECARTS_VIDES = {
    salaries_manquants: [], salaries_nouveaux: [], variations_net: [],
    hs_anormales: [],
  }

  it('synchronise un écart de rémunération et rejoue les contrôles (écart résorbé)', async () => {
    paieApi.controleCompletude
      .mockResolvedValueOnce({
        data: { ...COMPLETUDE_VIDE, ecarts_remuneration: [ECART] },
      })
      .mockResolvedValueOnce({ data: COMPLETUDE_VIDE })
    paieApi.controleEcarts.mockResolvedValue({ data: ECARTS_VIDES })
    paieApi.synchroniserSalaireProfil.mockResolvedValueOnce({
      data: { id: 55, salaire_base: 6500 },
    })

    wrap(<PaieRunWizard />)
    await userEvent.click(await screen.findByRole('button', { name: /Décembre 2026/ }))
    await userEvent.click(await screen.findByRole('button', { name: 'Contrôles pré-run' }))

    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText(/M008 — Amrani Yassine/)).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: /Synchroniser/ }))

    await waitFor(() => expect(paieApi.synchroniserSalaireProfil).toHaveBeenCalledWith(55))
    await waitFor(() => expect(paieApi.controleCompletude).toHaveBeenCalledTimes(2))
    await waitFor(() => {
      expect(document.querySelector('[data-sonner-toast][data-type="success"]'))
        .toHaveTextContent('Salaire synchronisé sur la rémunération RH en vigueur.')
    })
    expect(within(dialog).queryByText(/M008 — Amrani Yassine/)).not.toBeInTheDocument()
  })

  it('affiche le 403 "salaires_voir" du serveur sans le masquer', async () => {
    paieApi.controleCompletude.mockResolvedValue({
      data: { ...COMPLETUDE_VIDE, ecarts_remuneration: [ECART] },
    })
    paieApi.controleEcarts.mockResolvedValue({ data: ECARTS_VIDES })
    paieApi.synchroniserSalaireProfil.mockRejectedValueOnce({
      response: { status: 403, data: { detail: 'Permission "salaires_voir" requise.' } },
    })

    wrap(<PaieRunWizard />)
    await userEvent.click(await screen.findByRole('button', { name: /Décembre 2026/ }))
    await userEvent.click(await screen.findByRole('button', { name: 'Contrôles pré-run' }))

    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: /Synchroniser/ }))

    await waitFor(() => {
      expect(document.querySelector('[data-sonner-toast][data-type="error"]'))
        .toHaveTextContent('Permission "salaires_voir" requise.')
    })
  })
})
