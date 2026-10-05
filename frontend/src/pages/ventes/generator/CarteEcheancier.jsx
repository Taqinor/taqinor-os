// QJR624 (D-QJR5-10) — l'échéancier du devis (acompte / matériel / solde),
// éditable dans l'Édition complète. `saisie === null` : le devis suit
// l'échéancier de la société (rien n'est envoyé tant que le commercial ne
// personnalise pas). Chaque champ nombre porte `step="any"` (règle fondateur :
// aucun champ ne snappe ni ne rejette un nombre tapé).
import { Button, Card, CardContent, Input, Label } from '../../../ui'
import { CalendarClock } from 'lucide-react'
import { GenCardHeader } from './CarteMetrique'
import {
  UNITE_MONTANT, UNITE_PCT, saisieParDefaut, sommePourcentages,
} from '../../../features/ventes/echeancierEdition'

export default function CarteEcheancier({ saisie, setSaisie, mode }) {
  const modifier = (i, champ, valeur) => {
    setSaisie(prev => (prev || []).map((t, j) => (j === i ? { ...t, [champ]: valeur } : t)))
  }
  const somme = sommePourcentages(saisie)
  return (
    <Card data-testid="carte-echeancier">
      <GenCardHeader icon={CalendarClock} title="Échéancier de paiement" />
      <CardContent className="pt-4 grid gap-3">
        {saisie == null ? (
          <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            <span>Ce devis suit l'échéancier de la société (Paramètres → Devis).</span>
            <Button type="button" variant="outline" size="sm"
                    onClick={() => setSaisie(saisieParDefaut(mode))}>
              Personnaliser l'échéancier
            </Button>
          </div>
        ) : (
          <>
            {saisie.map((t, i) => (
              <div key={i} className="grid gap-1.5 sm:grid-cols-[1fr_10rem_6rem_10rem] sm:items-end">
                <Label htmlFor={`gen-echeance-${i}`}>{t.libelle}</Label>
                <Input id={`gen-echeance-${i}`} type="number" min="0" step="any"
                       value={t.valeur}
                       onChange={e => modifier(i, 'valeur', e.target.value)} />
                <select aria-label={`Unité — ${t.libelle}`}
                        className="h-9 rounded-md border border-input bg-background px-2 text-sm"
                        value={t.unite}
                        onChange={e => modifier(i, 'unite', e.target.value)}>
                  <option value={UNITE_PCT}>%</option>
                  <option value={UNITE_MONTANT}>MAD TTC</option>
                </select>
                <Input id={`gen-echeance-date-${i}`} type="date"
                       aria-label={`Date prévue — ${t.libelle}`}
                       value={t.date_prevue || ''}
                       onChange={e => modifier(i, 'date_prevue', e.target.value)} />
              </div>
            ))}
            <p className="text-xs text-muted-foreground">
              La dernière tranche vaut toujours le reste du total : facture d'acompte
              et PDF lisent ces mêmes valeurs. La date prévue est facultative.
              {somme != null && somme !== 100 && (
                <span className="text-warning"> Total des pourcentages : {somme} %.</span>
              )}
            </p>
            <div>
              <Button type="button" variant="ghost" size="sm" onClick={() => setSaisie(null)}>
                Revenir à l'échéancier de la société
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}
