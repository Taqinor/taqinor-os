import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR37 — `paieApi.journalDePaie`/`journalVentile` (écriture OD équilibrée
   du journal de paie, apps/paie/services.py:journal_de_paie, via
   compta.services) étaient construits sans déclencheur UI. On couvre le
   bouton « Passer l'écriture comptable » de l'onglet Charges & GL : garde
   sans période choisie, puis passage réel avec confirmation de la
   référence renvoyée par le serveur.
   Radix Select ne s'ouvre pas de façon fiable sous jsdom (portail + pointer
   events) — pattern établi (pages/ventes/ListesPrixPage.test.jsx,
   pages/monitoring/ClientPortalPage.test.jsx) : remplacer les primitives
   Select par un <select> natif pour piloter le choix, le reste de
   `../../ui` reste réel. */
vi.mock('../../ui', async (importActual) => {
  const actual = await importActual()
  const Passthrough = ({ children }) => <>{children}</>
  return {
    ...actual,
    Select: ({ value, onValueChange, children }) => (
      <select role="combobox" value={value}
        onChange={(e) => onValueChange(e.target.value)}>
        <option value="" />
        {children}
      </select>
    ),
    SelectTrigger: Passthrough,
    SelectValue: () => null,
    SelectContent: Passthrough,
    SelectItem: ({ value, children }) => <option value={value}>{children}</option>,
  }
})

// `PaieDeclarations` consomme ~36 méthodes `paieApi` (getOrdresVirement/
// getPeriodes au montage, puis etatCharges/coutGlobal/… par onglet). On ne
// pilote que celles du chemin testé (getPeriodes + journalDePaie) et on laisse
// un Proxy renvoyer une promesse vide pour toute autre méthode, afin qu'aucun
// effet de montage ne casse le rendu.
vi.mock('../../api/paieApi', () => {
  const specific = {
    getPeriodes: vi.fn(() => Promise.resolve({
      data: [{ id: 3, libelle: 'Juillet 2026', mois: 7, annee: 2026 }],
    })),
    journalDePaie: vi.fn(() => Promise.resolve({
      data: { ecriture_id: 91, reference: 'PAIE-2026-07' },
    })),
    journalVentile: vi.fn(() => Promise.resolve({
      data: { id: 92, reference: 'PAIE-2026-07-V' },
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
import PaieDeclarations from './PaieDeclarations.jsx'

function wrap(ui) {
  return render(
    <MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>,
  )
}

describe('PaieDeclarations — Charges & GL (WIR37, journal de paie → comptabilité)', () => {
  beforeEach(() => { paieApi.journalDePaie.mockClear() })

  it('refuse de passer l’écriture sans période choisie', async () => {
    wrap(<PaieDeclarations />)
    await userEvent.click(screen.getByRole('tab', { name: 'Charges & GL' }))
    await userEvent.click(
      await screen.findByRole('button', { name: 'Passer l’écriture comptable' }))
    expect(paieApi.journalDePaie).not.toHaveBeenCalled()
  })

  it('passe l’écriture comptable de la période sélectionnée et affiche la référence',
    async () => {
      wrap(<PaieDeclarations />)
      await userEvent.click(screen.getByRole('tab', { name: 'Charges & GL' }))

      const select = await screen.findByRole('combobox')
      await userEvent.selectOptions(select, '3')

      await userEvent.click(
        screen.getByRole('button', { name: 'Passer l’écriture comptable' }))

      await waitFor(() => expect(paieApi.journalDePaie).toHaveBeenCalledWith(3))
      expect(await screen.findByText(/PAIE-2026-07/)).toBeInTheDocument()
    })
})

describe('PaieDeclarations — Cumuls annuels (PACT154, reprise go-live)', () => {
  it('affiche le compte réel de lignes du dry-run (total_lignes, jamais 0 par défaut)', async () => {
    // dry_run_reprise_cumuls (apps/paie/services.py:6322-6356) renvoie
    // {colonnes, mapping, non_mappees, total_lignes, matricules_inconnus,
    // apercu} — jamais un champ `lignes`.
    paieApi.repriseDryRun.mockResolvedValueOnce({
      data: {
        colonnes: ['matricule', 'annee', 'brut'],
        mapping: { matricule: 0, annee: 1, brut: 2 },
        non_mappees: [],
        total_lignes: 137,
        matricules_inconnus: [],
        apercu: [{ matricule: 'M001', annee: 2025, brut: 12000 }],
      },
    })
    wrap(<PaieDeclarations />)
    await userEvent.click(screen.getByRole('tab', { name: 'Cumuls annuels' }))

    const input = document.querySelector('input[type="file"]')
    const file = new File(['matricule,annee,brut\nM001,2025,12000'], 'cumuls.csv', { type: 'text/csv' })
    await userEvent.upload(input, file)
    await userEvent.click(await screen.findByRole('button', { name: /Aperçu \(dry-run\)/ }))

    await waitFor(() => expect(paieApi.repriseDryRun).toHaveBeenCalledWith(file))
    expect(await screen.findByText('137 ligne(s) à importer.')).toBeInTheDocument()
  })
})

describe('PaieDeclarations — Avances/prêts (WIR197, cycle complet en UI)', () => {
  beforeEach(() => {
    paieApi.getAvances.mockClear()
    paieApi.saveAvance.mockClear()
    paieApi.deleteAvance.mockClear()
  })

  it('crée une avance depuis le dialogue « Nouvelle avance » via saveAvance', async () => {
    paieApi.getAvances.mockResolvedValue({ data: [] })
    paieApi.saveAvance.mockResolvedValueOnce({ data: { id: 5 } })
    wrap(<PaieDeclarations />)
    await userEvent.click(screen.getByRole('tab', { name: 'Avances & saisies' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Nouvelle avance' }))

    const dialog = await screen.findByRole('dialog')
    await userEvent.type(
      within(dialog).getByLabelText('ID du profil de paie'), '12')
    await userEvent.type(within(dialog).getByLabelText('Montant total'), '5000')
    await userEvent.type(
      within(dialog).getByLabelText('Date de début de retenue'), '2026-09-01')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(paieApi.saveAvance).toHaveBeenCalledWith(
      undefined,
      expect.objectContaining({
        profil: 12, type: 'avance', montant_total: 5000, date_debut: '2026-09-01',
      }),
    ))
  })

  it('n’affiche Modifier/Supprimer que sur une avance jamais retenue', async () => {
    paieApi.getAvances.mockResolvedValue({
      data: [
        {
          id: 1, profil: 10, type: 'avance', montant_total: 3000,
          montant_rembourse: 0, solde_restant: 3000, soldee: false,
        },
        {
          id: 2, profil: 11, type: 'pret', montant_total: 6000,
          montant_rembourse: 1000, solde_restant: 5000, soldee: false,
        },
      ],
    })
    wrap(<PaieDeclarations />)
    await userEvent.click(screen.getByRole('tab', { name: 'Avances & saisies' }))

    const rowNonRetenue = (await screen.findByText('#10')).closest('tr')
    const rowDejaRetenue = screen.getByText('#11').closest('tr')

    // Déjà retenue (montant_rembourse > 0) : aucune action de ligne exposée.
    expect(
      within(rowDejaRetenue).queryByLabelText("Plus d'actions sur la ligne"),
    ).not.toBeInTheDocument()

    // Jamais retenue : Modifier + Supprimer disponibles.
    await userEvent.click(
      within(rowNonRetenue).getByLabelText("Plus d'actions sur la ligne"))
    expect(await screen.findByText('Modifier')).toBeInTheDocument()
    expect(screen.getByText('Supprimer')).toBeInTheDocument()
  })

  it('supprime une avance non retenue via deleteAvance après confirmation', async () => {
    paieApi.getAvances.mockResolvedValue({
      data: [
        {
          id: 7, profil: 20, type: 'avance', montant_total: 1000,
          montant_rembourse: 0, solde_restant: 1000, soldee: false,
        },
      ],
    })
    paieApi.deleteAvance.mockResolvedValueOnce({ data: null })
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    wrap(<PaieDeclarations />)
    await userEvent.click(screen.getByRole('tab', { name: 'Avances & saisies' }))

    const row = (await screen.findByText('#20')).closest('tr')
    await userEvent.click(within(row).getByLabelText("Plus d'actions sur la ligne"))
    await userEvent.click(await screen.findByText('Supprimer'))

    await waitFor(() => expect(paieApi.deleteAvance).toHaveBeenCalledWith(7))
    confirmSpy.mockRestore()
  })
})
