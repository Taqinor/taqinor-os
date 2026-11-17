import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'

/* AGR607 — Paramètres › Avancé : « Écart de recette pompage toléré (%) »,
   réglage société SANS défaut (AGR606). Vide = envoyé null avec l'aide « non
   saisi : l'écart sera affiché sans verdict » ; une valeur tapée part telle
   quelle (jamais arrondie) ; le 400 du serveur s'affiche SOUS le champ ;
   enregistrer → rouvrir → enregistrer sans toucher = même PATCH. */

import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import AvanceSection, { EcartRecettePompageField } from './AvanceSection'
import { CHAMP_ECART_RECETTE, nombreOuNull } from './peConstants'

afterEach(() => cleanup())

/* ALEC49 — sections chantiers montées seulement avec la lecture du module
   chantiers (les routes serveur sont gardées `LectureDuModule`). */
vi.mock('./EquipeTerrainSection', () => ({ default: () => <div>SECTION-EQUIPES</div> }))
vi.mock('./FicheInterventionModelesSection', () => ({ default: () => <div>SECTION-MODELES</div> }))
vi.mock('./SettingsAuditFeed', () => ({ default: () => null }))

describe('ALEC49 — sections chantiers selon le droit', () => {
  const rendreAvance = (auth) => {
    const store = configureStore({ reducer: { auth: (s = auth) => s } })
    return render(
      <Provider store={store}>
        <AvanceSection form={{}} set={vi.fn()} typesItv={[]} checklistEtapes={[]} cfDefs={[]}
          newCf={{ libelle: '', type: 'text' }} setNewCf={vi.fn()} newType="" newEtape="" />
      </Provider>,
    )
  }
  it('Commercial responsable (aucun code installation_*) : ni équipes ni modèles', () => {
    rendreAvance({
      role: 'responsable', role_nom: 'Commercial responsable', user: { portee: 'interne' },
      permissions: ['devis_voir', 'devis_gerer'],
    })
    expect(screen.queryByText('SECTION-EQUIPES')).toBeNull()
    expect(screen.queryByText('SECTION-MODELES')).toBeNull()
  })
  it('Directeur (admin interne) : les deux sections', () => {
    rendreAvance({ role: 'admin', role_nom: 'Directeur', user: { portee: 'interne' }, permissions: [] })
    expect(screen.getByText('SECTION-EQUIPES')).toBeInTheDocument()
    expect(screen.getByText('SECTION-MODELES')).toBeInTheDocument()
  })
})

const champ = () => screen.getByLabelText('Écart de recette pompage toléré (%)')

describe('AGR607 — écart de recette pompage toléré', () => {
  it('vide : step="any", aide « sans verdict », envoyé null', () => {
    render(<EcartRecettePompageField form={{ [CHAMP_ECART_RECETTE]: '' }}
                                     set={vi.fn()} />)
    expect(champ()).toHaveAttribute('step', 'any')
    expect(champ()).toHaveAttribute('name', CHAMP_ECART_RECETTE)
    expect(champ()).toHaveValue(null)
    expect(screen.getByText(/l'écart sera affiché sans verdict/)).toBeInTheDocument()
    expect(nombreOuNull('')).toBeNull()
  })

  it('une valeur tapée est envoyée telle quelle (jamais arrondie)', () => {
    const set = vi.fn()
    render(<EcartRecettePompageField form={{ [CHAMP_ECART_RECETTE]: '' }} set={set} />)
    fireEvent.change(champ(), { target: { value: '12.375' } })
    expect(set).toHaveBeenCalled()
    expect(set.mock.calls.at(-1)[0].target.name).toBe(CHAMP_ECART_RECETTE)
    expect(nombreOuNull('12.375')).toBe('12.375')
    expect(nombreOuNull('12,5')).toBe('12.5')
  })

  it('le refus 400 du serveur s’affiche sous le champ', () => {
    const message = "L'écart de recette pompage toléré doit être compris entre 0 (exclu) et 100 %."
    render(<EcartRecettePompageField form={{ [CHAMP_ECART_RECETTE]: '150' }}
                                     set={vi.fn()}
                                     erreur={{ [CHAMP_ECART_RECETTE]: [message] }} />)
    expect(screen.getByRole('alert')).toHaveTextContent(message)
    expect(champ()).toHaveAttribute('aria-invalid', 'true')
    expect(champ()).toHaveAttribute('aria-describedby', 'pe-ecart-recette-erreur')
    expect(screen.queryByText(/sans verdict/)).toBeNull()
  })

  it('enregistrer → rouvrir → enregistrer sans toucher = même PATCH', () => {
    // Rouvrir = la valeur servie, affichée telle quelle dans le champ ; le
    // PATCH suivant (sans toucher) renvoie exactement la même valeur.
    for (const servi of ['7.25', null]) {
      const form = { [CHAMP_ECART_RECETTE]: servi ?? '' }
      render(<EcartRecettePompageField form={form} set={vi.fn()} />)
      const premier = nombreOuNull(form[CHAMP_ECART_RECETTE])
      const second = nombreOuNull(champ().value)
      expect(second).toBe(premier)
      expect(premier).toBe(servi)
      cleanup()
    }
  })
})
