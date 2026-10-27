import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent, within } from '@testing-library/react'
import { useState } from 'react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* CIQ106 — Paramètres › Devis : forfaits des prestations C&I et bande
   interne prix/kWc (CIQ105), chacun avec sa source. Aucune valeur
   pré-remplie ; un montant sans source → erreur sous le champ Source ;
   enregistrer → rouvrir → enregistrer sans toucher = rien de modifié. */

vi.mock('../../api/ventesApi', () => ({
  default: {
    getVarianteConfig: vi.fn(() => Promise.resolve({ data: { variante_pct: '20.00' } })),
    setVarianteConfig: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

import DevisSection from './DevisSection'
import { formDevisBase } from '../../test/fixtures/devisSectionForm'

afterEach(() => cleanup())

const store = configureStore({
  reducer: { auth: (s = { role: 'admin', role_nom: null }) => s },
})

const baseForm = formDevisBase({ forfaits_ci: {}, bande_prix_kwc_ci: null })

// Harnais à état : `setForm` réel, et chaque nouvel état est journalisé.
function rendre(formInitial = baseForm) {
  const journal = []
  function Harnais() {
    const [form, setFormEtat] = useState(formInitial)
    const setForm = (fn) => setFormEtat((p) => {
      const suivant = typeof fn === 'function' ? fn(p) : fn
      journal.push(suivant)
      return suivant
    })
    return (
      <DevisSection form={form} set={vi.fn()} setForm={setForm} setPT={vi.fn()}
                    setPrefix={vi.fn()} setNumbering={vi.fn()}
                    numberingPreview={() => 'DEV-1'} canManageSensitive />
    )
  }
  render(<Provider store={store}><Harnais /></Provider>)
  return journal
}

describe('CIQ106 — prestations C&I et bande prix/kWc', () => {
  it("CCAT101 — le titre « Prestations C&I » porte l'ancre #prestations-ci", () => {
    rendre()
    const ancre = document.getElementById('prestations-ci')
    expect(ancre).not.toBeNull()
    expect(ancre).toHaveTextContent('Prestations C&I')
  })

  // CCAT103 — tableau compact : en-têtes une fois, intro de calcul, effet de la bande.
  it('CCAT103 — tableau : en-têtes une seule fois, une ligne par prestation', () => {
    rendre()
    const bloc = screen.getByTestId('prestations-ci')
    const entetes = within(bloc).getAllByRole('columnheader').map((th) => th.textContent)
    expect(entetes).toEqual(['Prestation', 'Fixe HT', 'Par kWc HT', 'Par panneau HT', 'Source', 'Date'])
    expect(within(bloc).getAllByTestId(/^prestation-ci-/)).toHaveLength(8)
    // Les ids historiques sont conservés.
    expect(document.getElementById('pe-ci-transport_ci-par_panneau_ht')).not.toBeNull()
    expect(document.getElementById('pe-ci-etudes_ingenierie-date')).not.toBeNull()
  })

  it('CCAT103 — intro du calcul du prix et effet de la bande prix/kWc', () => {
    rendre()
    expect(screen.getByText(/Prix d'une prestation = fixe \+ par kWc × puissance \+ par panneau × nombre de panneaux/))
      .toHaveTextContent(/une seule ligne « Installation clé en main » ; le détail reste sur le devis interne\./)
    expect(screen.getByText(/Hors de cette bande, le vendeur voit une alerte interne sur le devis ; jamais montré au client\./))
      .toBeInTheDocument()
  })

  it('CCAT103 — la saisie envoie la même forme forfaits_ci qu’avant (montant, source, date)', () => {
    const journal = rendre()
    fireEvent.change(screen.getByLabelText('Transport C&I — Par panneau HT'), { target: { value: '12.5' } })
    fireEvent.change(screen.getByLabelText('Transport C&I — source'), { target: { value: 'Offre transporteur' } })
    fireEvent.change(screen.getByLabelText('Transport C&I — date'), { target: { value: '2026-10-01' } })
    expect(journal.at(-1).forfaits_ci).toEqual({
      transport_ci: { par_panneau_ht: '12.5', source: 'Offre transporteur', date: '2026-10-01' },
    })
    expect(screen.getByLabelText('Transport C&I — Par panneau HT')).toHaveAttribute('step', 'any')
  })

  it('aucune valeur pré-remplie : chaque prestation est « prix à renseigner »', () => {
    rendre()
    const montant = screen.getByLabelText('Pose des modules — Fixe HT')
    expect(montant).toHaveValue(null)
    expect(montant).toHaveAttribute('step', 'any')
    expect(screen.getByLabelText('Pose des modules — source')).toHaveValue('')
    expect(screen.getAllByText('prix à renseigner')).toHaveLength(8)
    expect(screen.getByLabelText('Minimum HT / kWc')).toHaveValue(null)
    expect(screen.getByText(/Jamais imprimé au client/)).toBeInTheDocument()
  })

  it('saisir une prestation sans source → erreur sous le champ Source', () => {
    const journal = rendre()
    fireEvent.change(screen.getByLabelText('Pose des modules — Fixe HT'),
      { target: { value: '5000' } })
    expect(journal.at(-1).forfaits_ci.pose_modules.fixe_ht).toBe('5000')
    const source = screen.getByLabelText('Pose des modules — source')
    expect(source).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('alert')).toHaveTextContent(/Source obligatoire/)
    fireEvent.change(source, { target: { value: 'Devis sous-traitant' } })
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('la bande prix/kWc sans source affiche aussi l’erreur', () => {
    rendre()
    fireEvent.change(screen.getByLabelText('Maximum HT / kWc'), { target: { value: '6000' } })
    expect(screen.getByLabelText('Bande prix/kWc — source'))
      .toHaveAttribute('aria-invalid', 'true')
  })

  it('enregistrer → rouvrir → enregistrer sans toucher = aucune modification', () => {
    // Profil tel que le serveur (CIQ105) le sert après enregistrement.
    const serveur = {
      ...baseForm,
      forfaits_ci: {
        pose_modules: {
          fixe_ht: '5000', par_kwc_ht: '120.5', par_panneau_ht: null,
          source: 'Devis sous-traitant', date: '2026-09-15',
        },
      },
      bande_prix_kwc_ci: {
        min_ht: '4000', max_ht: '6000', source: 'Trois offres', date: null,
      },
    }
    const journal = rendre(serveur)
    expect(screen.getByLabelText('Pose des modules — Fixe HT')).toHaveValue(5000)
    expect(screen.getByLabelText('Pose des modules — Par kWc HT')).toHaveValue(120.5)
    expect(screen.getByLabelText('Minimum HT / kWc')).toHaveValue(4000)
    expect(screen.queryByRole('alert')).toBeNull()
    // Rien n'a été touché : aucun nouvel état, donc rien de neuf à envoyer.
    expect(journal).toHaveLength(0)
  })
})
