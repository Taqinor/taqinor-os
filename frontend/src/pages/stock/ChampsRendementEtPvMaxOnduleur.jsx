// Champs « rendement publié » et « puissance PV maximale raccordable » de la
// fiche onduleur — sortis de `ProduitForm.jsx` (fichier de plus de 2 000 lignes
// qui ne doit pas grossir). Mêmes champs, mêmes identifiants, même ordre.
// Tous optionnels : vides = non publiés, jamais envoyés à 0.
import { FormField, Input } from '../../ui'

export default function ChampsRendementEtPvMaxOnduleur({ ficheFields, setFicheField }) {
  return (
    <>
      <FormField label="Rendement maximal (%)" htmlFor="pf-ft-rendmax"
                 hint="Optionnel — « peak efficiency » publié.">
        <Input id="pf-ft-rendmax" type="number" step="any" inputMode="decimal"
               value={ficheFields.ond_rendement_max_pct}
               onChange={e => setFicheField('ond_rendement_max_pct', e.target.value)} />
      </FormField>
      <FormField label="Rendement CEC (%)" htmlFor="pf-ft-rendcec"
                 hint="Optionnel — rendement pondéré CEC publié.">
        <Input id="pf-ft-rendcec" type="number" step="any" inputMode="decimal"
               value={ficheFields.ond_rendement_cec_pct}
               onChange={e => setFicheField('ond_rendement_cec_pct', e.target.value)} />
      </FormField>
      {/* Fondateur 17/11/2026 — la borne panneaux d'un onduleur se lit sur sa
          fiche constructeur : c'est elle que le moteur de devis applique à un
          hybride (au lieu de 1,35 × la puissance AC). */}
      <FormField label="Puissance PV maximale raccordable (kWc)" htmlFor="pf-ft-dcmax"
                 hint={'Fiche constructeur : "Max. PV access power" (hybride) ou "Recommended max. PV power"'}>
        <Input id="pf-ft-dcmax" type="number" min="0" step="any" inputMode="decimal"
               value={ficheFields.ond_dc_max_kwc}
               onChange={e => setFicheField('ond_dc_max_kwc', e.target.value)} />
      </FormField>
    </>
  )
}
