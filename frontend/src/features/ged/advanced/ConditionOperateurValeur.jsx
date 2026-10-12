import { Label, Input, Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../../../ui'

/* Champ + opérateur + valeur d'une condition « champ / opérateur / valeur », partagés
   par les règles d'accès (ReglesAclPage) et les règles de dossier
   (ReglesDossierPage). La valeur disparaît pour l'opérateur `exists`. */
export default function ConditionOperateurValeur({
  champ, setChamp, placeholder, champClassName,
  operateurs, operateur, setOperateur, valeur, setValeur,
}) {
  return (
    <>
      <div>
        <Label>Champ</Label>
        <Input aria-label="Champ de la condition" placeholder={placeholder}
          value={champ} onChange={(e) => setChamp(e.target.value)} className={champClassName} />
      </div>
      <div>
        <Label>Opérateur</Label>
        <Select value={operateur} onValueChange={setOperateur}>
          <SelectTrigger className="w-56"><SelectValue /></SelectTrigger>
          <SelectContent>
            {operateurs.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      {operateur !== 'exists' && (
        <div>
          <Label>Valeur</Label>
          <Input aria-label="Valeur de la condition" value={valeur} onChange={(e) => setValeur(e.target.value)} className="w-40" />
        </div>
      )}
    </>
  )
}
