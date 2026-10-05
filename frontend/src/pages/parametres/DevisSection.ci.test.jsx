import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
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
