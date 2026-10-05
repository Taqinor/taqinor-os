import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'

/* CIQ639 — Paramètres › Avancé : seuils 82-21 des TEXTES (servis par
   `seuils_sources`, CIQ614) avec une surcharge VIDE par défaut (fin du 1 000
   prérempli) ; réglages C&I de CIQ622 sans défaut ; garantie autorisée sans
   texte → erreur sous le champ ; enregistrer → rouvrir → enregistrer sans
   toucher = même PATCH. */

import {
  SeuilsEtReglagesCiFields, formReglagesCi, payloadReglagesCi,
  erreurGarantieLocale, MESSAGE_GARANTIE_SANS_VALIDATION,
} from './AvanceSection'

afterEach(() => cleanup())

const SOURCES = {
  declaration: { valeur_kw: 11, source: 'décret 2.25.100 art. 5' },
  autorisation: { valeur_kw: 5000, source: 'décret 2.25.100 art. 5, 18' },
}

const PROFIL_VIERGE = {
  seuil_regime_declaration_kwc: null, seuil_regime_anre_kwc: null,
  recette_ecart_pmax_pct: null, recette_echantillon_iv_pct: null,
  recette_pr_seuil_interne: null, delai_intervention_suivi_heures: null,
  delai_reception_definitive_mois: null,
  securite_obligatoire_avant_demarrage: false,
  garantie_production_autorisee: false, garantie_production_validation: '',
  seuils_sources: SOURCES,
}

describe('CIQ639 — seuils 82-21 sourcés et réglages C&I', () => {
  it('GET null → champs vides, seuils des textes affichés avec leur article', () => {
    const form = formReglagesCi(PROFIL_VIERGE)
    render(<SeuilsEtReglagesCiFields form={form} set={vi.fn()}
                                      seuilsSources={SOURCES} />)
    const anre = screen.getByLabelText('Surcharge du seuil « Autorisation » (kW)')
    expect(anre).toHaveValue(null)
    expect(anre).toHaveAttribute('step', 'any')
    expect(screen.getByLabelText('Surcharge du seuil « Déclaration » (kW)')).toHaveValue(null)
    expect(screen.getByText(/Seuil des textes : 5000 kW — décret 2.25.100 art. 5, 18/))
      .toBeInTheDocument()
    expect(screen.queryByDisplayValue('1000')).toBeNull()
    for (const label of [
      'Écart de recette toléré sur la puissance crête (%)',
      'Échantillon de courbes I-V à la recette (%)',
      "Délai d'intervention du suivi (heures)",
      'Délai de réception définitive (mois)',
    ]) {
      const champ = screen.getByLabelText(label)
      expect(champ).toHaveValue(null)
      expect(champ).toHaveAttribute('step', 'any')
    }
    expect(screen.getAllByText(/sans verdict/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/non engagé/).length).toBeGreaterThan(0)
    expect(screen.getByLabelText('Garantie de production autorisée')).not.toBeChecked()
    expect(payloadReglagesCi(form).seuil_regime_anre_kwc).toBeNull()
  })

  it('une valeur tapée part telle quelle (jamais arrondie)', () => {
    const set = vi.fn()
    render(<SeuilsEtReglagesCiFields form={formReglagesCi(PROFIL_VIERGE)} set={set} />)
    fireEvent.change(screen.getByLabelText('Écart de recette toléré sur la puissance crête (%)'),
      { target: { value: '3.375' } })
    expect(set.mock.calls.at(-1)[0].target.name).toBe('recette_ecart_pmax_pct')
    expect(payloadReglagesCi({ recette_ecart_pmax_pct: '3,375' }).recette_ecart_pmax_pct)
      .toBe('3.375')
  })

  it('garantie autorisée sans texte → erreur sous le champ', () => {
    const form = { ...formReglagesCi(PROFIL_VIERGE), garantie_production_autorisee: true }
    expect(erreurGarantieLocale(form)).toBe(MESSAGE_GARANTIE_SANS_VALIDATION)
    render(<SeuilsEtReglagesCiFields form={form} set={vi.fn()} />)
    const champ = screen.getByLabelText('Validation de la garantie de production (qui, quand)')
    expect(champ).toHaveAttribute('aria-invalid', 'true')
    expect(champ).toHaveAttribute('aria-describedby', 'pe-garantie-validation-erreur')
    expect(screen.getByRole('alert')).toHaveTextContent('assureur ou juriste')
  })

  it('le refus 400 du serveur s’affiche sous le champ fautif', () => {
    const message = "Le délai d'intervention (heures) doit être strictement positif."
    render(<SeuilsEtReglagesCiFields form={formReglagesCi(PROFIL_VIERGE)} set={vi.fn()}
                                      erreur={{ delai_intervention_suivi_heures: [message] }} />)
    const champ = screen.getByLabelText("Délai d'intervention du suivi (heures)")
    expect(champ).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('alert')).toHaveTextContent(message)
  })

  it('enregistrer → rouvrir → enregistrer sans toucher = même PATCH', () => {
    const servi = {
      ...PROFIL_VIERGE,
      seuil_regime_anre_kwc: '2000.00', recette_ecart_pmax_pct: '4.25',
      delai_reception_definitive_mois: 12,
      garantie_production_autorisee: true,
      garantie_production_validation: 'Juriste Y, 03/10/2026',
    }
    const premier = payloadReglagesCi(formReglagesCi(servi))
    // Rouvrir = le PATCH renvoyé par le serveur tel quel, puis ré-enregistrer.
    const second = payloadReglagesCi(formReglagesCi({ ...servi, ...premier }))
    expect(second).toEqual(premier)
    expect(premier.seuil_regime_anre_kwc).toBe('2000.00')
    expect(premier.seuil_regime_declaration_kwc).toBeNull()
    expect(premier.delai_reception_definitive_mois).toBe('12')
    const vierge = payloadReglagesCi(formReglagesCi(PROFIL_VIERGE))
    expect(payloadReglagesCi(formReglagesCi({ ...PROFIL_VIERGE, ...vierge })))
      .toEqual(vierge)
  })
})
