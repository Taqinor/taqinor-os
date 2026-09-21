import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import MesBulletins from './MesBulletins.jsx'
import PaieRunWizard from './PaieRunWizard.jsx'

/* Smoke : les écrans Paie montent sans planter (imports résolus, kit UX1 OK).
   L'API est mockée pour renvoyer des listes vides — on vérifie que le titre et
   les repères clés s'affichent, sans dépendre du réseau. */
const periodeTest = { id: 7, statut: 'brouillon', libelle: 'Juillet 2026' }

vi.mock('../../api/paieApi', () => ({
  default: {
    getPeriodes: vi.fn(() => Promise.resolve({ data: [] })),
    getProfils: vi.fn(() => Promise.resolve({ data: [] })),
    getBulletins: vi.fn(() => Promise.resolve({ data: [] })),
    getMesBulletins: vi.fn(() => Promise.resolve({ data: [] })),
    avertissements: vi.fn(() => Promise.resolve({
      data: [
        { type: 'cnss_manquant', employe_id: 1, matricule: 'M1', nom: 'A B',
          gravite: 'bloquant', message: 'A B — numéro CNSS manquant.' },
      ],
    })),
    createPeriode: vi.fn(() => Promise.resolve({ data: periodeTest })),
    // WIR39 — contrôles pré-run détaillés (YHIRE3 complétude + XPAI15 écarts).
    controleCompletude: vi.fn(() => Promise.resolve({
      data: {
        actifs_sans_profil: [
          { dossier_id: 9, matricule: 'M9', nom: 'Test Employé' },
        ],
        profils_sans_cnss: [], profils_sans_rib: [],
        profils_actifs_dossiers_non_actifs: [], contrats_expires: [],
        ecarts_remuneration: [],
      },
    })),
    controleEcarts: vi.fn(() => Promise.resolve({
      data: {
        salaries_manquants: [], salaries_nouveaux: [], variations_net: [],
        hs_anormales: [], seuil_pct: 20,
      },
    })),
  },
}))

import paieApi from '../../api/paieApi'

function wrap(ui) {
  return render(
    <MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>,
  )
}

describe('Paie — smoke de rendu', () => {
  it('MesBulletins (UX14) monte et affiche son titre + garde d’isolation', () => {
    wrap(<MesBulletins />)
    expect(screen.getByText('Mes bulletins')).toBeInTheDocument()
    expect(
      screen.getByText(/Seuls vos propres bulletins validés/i),
    ).toBeInTheDocument()
  })

  it('PaieRunWizard (UX10) monte et affiche l’assistant après chargement', async () => {
    wrap(<PaieRunWizard />)
    // D'abord l'état de chargement (rendu synchrone), puis le titre.
    expect(screen.getByText(/Chargement de la paie/i)).toBeInTheDocument()
    expect(await screen.findByText('Run de paie')).toBeInTheDocument()
  })

  it('PaieRunWizard (YHIRE3/XPAI15/ZPAI2) affiche le panneau d’avertissements '
    + 'pré-run après création d’une période', async () => {
    wrap(<PaieRunWizard />)
    await screen.findByText('Run de paie')
    fireEvent.click(screen.getByRole('button', { name: /Créer la période/i }))
    await waitFor(() => {
      expect(screen.getByText(/1 avertissement\(s\) avant de lancer la paie/i))
        .toBeInTheDocument()
    })
    expect(screen.getByText(/numéro CNSS manquant/i)).toBeInTheDocument()
  })

  it('PaieRunWizard (WIR39) affiche les contrôles pré-run détaillés à la demande',
    async () => {
      wrap(<PaieRunWizard />)
      await screen.findByText('Run de paie')
      fireEvent.click(screen.getByRole('button', { name: /Créer la période/i }))
      const bouton = await screen.findByRole(
        'button', { name: /Contrôles pré-run/i })

      fireEvent.click(bouton)

      await waitFor(() => expect(paieApi.controleCompletude).toHaveBeenCalledWith(7))
      expect(paieApi.controleEcarts).toHaveBeenCalledWith(7)

      const dialog = await screen.findByRole('dialog')
      expect(within(dialog).getByText(/Actifs sans profil de paie/))
        .toBeInTheDocument()
      expect(within(dialog).getByText(/Test Employé/)).toBeInTheDocument()
      expect(within(dialog).getByText('Aucun écart signalé')).toBeInTheDocument()
    })
})
