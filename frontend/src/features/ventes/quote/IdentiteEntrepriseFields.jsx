// CIQ324 — les trois champs FACULTATIFS d'identité d'entreprise des dialogues
// d'acceptation de l'ERP (DevisList, SigneDialog) : un seul composant, jamais
// deux copies. Aucun calcul, aucune validation locale : l'ICE est validé par le
// serveur (`validate_ice_ma`), qui nomme le champ en cas d'erreur.
import { Input, Label } from '../../../ui'

export default function IdentiteEntrepriseFields({ value, onChange, idPrefix = 'accept' }) {
  const v = value || {}
  const champ = (cle) => (e) => onChange({ ...v, [cle]: e.target.value })
  return (
    <fieldset className="grid gap-3 rounded-lg border border-border p-3" data-testid="identite-entreprise">
      <legend className="px-1 text-sm font-semibold">Entreprise (facultatif)</legend>
      <div className="grid gap-1.5">
        <Label htmlFor={`${idPrefix}-raison-sociale`}>Raison sociale</Label>
        <Input id={`${idPrefix}-raison-sociale`} value={v.raison_sociale ?? ''}
               onChange={champ('raison_sociale')} />
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor={`${idPrefix}-qualite`}>Qualité du signataire</Label>
        <Input id={`${idPrefix}-qualite`} value={v.signataire_qualite ?? ''}
               onChange={champ('signataire_qualite')} placeholder="ex. Directeur général" />
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor={`${idPrefix}-ice`}>ICE</Label>
        <Input id={`${idPrefix}-ice`} inputMode="numeric" value={v.ice ?? ''}
               onChange={champ('ice')} placeholder="15 chiffres" />
      </div>
    </fieldset>
  )
}
