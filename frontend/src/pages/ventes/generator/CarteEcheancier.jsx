// QJR624 (D-QJR5-10) — l'échéancier du devis (acompte / matériel / solde),
// éditable dans l'Édition complète. `saisie === null` : le devis suit
// l'échéancier de la société (rien n'est envoyé tant que le commercial ne
// personnalise pas). Chaque champ nombre porte `step="any"` (règle fondateur :
// aucun champ ne snappe ni ne rejette un nombre tapé).
import { Button, Card, CardContent, Input, Label } from '../../../ui'
import { CalendarClock } from 'lucide-react'
import { GenCardHeader } from './CarteMetrique'
import { useState } from 'react'
import {
  JALONS_PROPOSES, UNITE_MONTANT, UNITE_PCT, saisieParDefaut, sommePourcentages,
  trancheVierge, echeancierFinanceur,
} from '../../../features/ventes/echeancierEdition'

const CHAMP = 'h-9 rounded-md border border-input bg-background px-2 text-sm'

function Erreur({ erreurs, champ }) {
  if (!erreurs?.[champ]) return null
  return <p className="text-xs text-destructive" data-testid={`erreur-condition-${champ}`}>{erreurs[champ]}</p>
}

/**
 * CIQ226 — conditions contractuelles DÉCLARÉES (rien de pré-rempli,
 * D-CIQ-14) : retenue de garantie (libérée à la réception définitive),
 * pénalités de retard (taux par semaine ET plafond), caution, organisme
 * financeur (un client de la société), référence de commande du client.
 * Libellé « organisme financeur », jamais « crédit-bail ».
 */
function ConditionsContractuelles({ conditions, setCondition, erreurs, clients, setSaisie }) {
  const c = conditions || {}
  const [acompteFinanceur, setAcompteFinanceur] = useState('')
  const nombre = (champ, libelle) => (
    <div className="grid gap-1">
      <Label htmlFor={`gen-cond-${champ}`}>{libelle}</Label>
      <Input id={`gen-cond-${champ}`} type="number" min="0" step="any" value={c[champ] ?? ''}
             onChange={e => setCondition(champ, e.target.value)} />
      <Erreur erreurs={erreurs} champ={champ} />
    </div>
  )
  return (
    <fieldset className="grid gap-3 border-t border-border pt-3" data-testid="conditions-contractuelles">
      <legend className="text-sm font-semibold">Conditions demandées par le client</legend>
      <label className="flex items-center gap-2 text-sm cursor-pointer">
        <input type="checkbox" data-testid="gen-cond-retenue" checked={Boolean(c.retenue)}
               onChange={e => setCondition('retenue', e.target.checked)} />
        Le client demande une retenue de garantie (libérée à la réception définitive)
      </label>
      <div className="grid gap-3 sm:grid-cols-3">
        {c.retenue && nombre('retenueTaux', 'Retenue de garantie (%)')}
        {nombre('penaliteTaux', 'Pénalités de retard (% par semaine)')}
        {nombre('penalitePlafond', 'Plafond des pénalités (%)')}
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="grid gap-1">
          <Label htmlFor="gen-cond-cautionNature">Caution (nature)</Label>
          <Input id="gen-cond-cautionNature" placeholder="ex: caution de bonne exécution"
                 value={c.cautionNature ?? ''} onChange={e => setCondition('cautionNature', e.target.value)} />
        </div>
        {nombre('cautionMontant', 'Caution : montant ou %')}
        {nombre('cautionPlafond', 'Caution : plafond')}
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="grid gap-1">
          <Label htmlFor="gen-cond-referenceCommande">Référence de commande du client</Label>
          <Input id="gen-cond-referenceCommande" maxLength={60} value={c.referenceCommande ?? ''}
                 onChange={e => setCondition('referenceCommande', e.target.value)} />
        </div>
        <div className="grid gap-1">
          <Label htmlFor="gen-cond-tiersPayeur">Organisme financeur</Label>
          <select id="gen-cond-tiersPayeur" className={CHAMP} value={c.tiersPayeur ?? ''}
                  onChange={e => setCondition('tiersPayeur', e.target.value)}>
            <option value="">— aucun —</option>
            {(clients || []).map(cl => <option key={cl.id} value={String(cl.id)}>{cl.nom}</option>)}
          </select>
        </div>
        <div className="grid gap-1">
          <Label htmlFor="gen-cond-acompte-financeur">Acompte client (%)</Label>
          <div className="flex gap-2">
            <Input id="gen-cond-acompte-financeur" type="number" min="0" step="any"
                   value={acompteFinanceur} onChange={e => setAcompteFinanceur(e.target.value)} />
            <Button type="button" variant="outline" size="sm" data-testid="btn-echeancier-financeur"
                    disabled={acompteFinanceur === '' || !c.tiersPayeur}
                    onClick={() => setSaisie(echeancierFinanceur(acompteFinanceur))}>
              Échéancier organisme financeur
            </Button>
          </div>
        </div>
      </div>
    </fieldset>
  )
}

// CIQ225 — N jalons : les trois créneaux historiques + les jalons C&I.
const OPTIONS_JALON = [
  ['acompte', 'Acompte'], ['materiel', 'Livraison du matériel'], ['solde', 'Solde'],
  ...JALONS_PROPOSES,
]

export default function CarteEcheancier({
  saisie, setSaisie, mode, effectifs,
  conditions = null, setCondition = null, erreursConditions = null, clients = [],
}) {
  const modifier = (i, champ, valeur) => {
    setSaisie(prev => (prev || []).map((t, j) => (j === i ? { ...t, [champ]: valeur } : t)))
  }
  const changerJalon = (i, type) => {
    const libelle = OPTIONS_JALON.find(([k]) => k === type)?.[1] || type
    setSaisie(prev => (prev || []).map((t, j) => {
      if (j !== i) return t
      const { jalon: _ancien, ...reste } = t
      return { ...reste, type, libelle,
               ...(['acompte', 'materiel', 'solde'].includes(type) ? {} : { jalon: type }) }
    }))
  }
  const retirer = (i) => setSaisie(prev => (prev || []).filter((_, j) => j !== i))
  const deplacer = (i, sens) => setSaisie((prev) => {
    const liste = [...(prev || [])]
    const k = i + sens
    if (k < 0 || k >= liste.length) return liste
    ;[liste[i], liste[k]] = [liste[k], liste[i]]
    return liste
  })
  const ajouter = () => setSaisie(prev => [
    ...(prev || []), trancheVierge('Mise en service', 'mise_en_service')])
  const somme = sommePourcentages(saisie)
  return (
    <Card data-testid="carte-echeancier">
      <GenCardHeader icon={CalendarClock} title="Échéancier de paiement" />
      <CardContent className="pt-4 grid gap-3">
        {saisie == null ? (
          <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            <span>Ce devis suit l'échéancier de la société (Paramètres → Devis).</span>
            <Button type="button" variant="outline" size="sm"
                    onClick={() => setSaisie(saisieParDefaut(mode, effectifs))}>
              Personnaliser l'échéancier
            </Button>
          </div>
        ) : (
          <>
            {saisie.map((t, i) => (
              <div key={i} data-testid={`echeance-ligne-${i}`}
                   className="grid gap-1.5 sm:grid-cols-[1fr_8rem_6rem_6rem_6rem_8rem_auto] sm:items-end">
                <div className="grid gap-1">
                  <Label htmlFor={`gen-echeance-${i}`}>{t.libelle}</Label>
                  <select aria-label={`Jalon — ${t.libelle}`}
                          className="h-9 rounded-md border border-input bg-background px-2 text-sm"
                          value={t.type || ''}
                          onChange={e => changerJalon(i, e.target.value)}>
                    {!OPTIONS_JALON.some(([k]) => k === t.type) && (
                      <option value={t.type || ''}>{t.libelle}</option>
                    )}
                    {OPTIONS_JALON.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                  </select>
                </div>
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
                <Input id={`gen-echeance-delai-${i}`} type="number" min="0" step="any"
                       aria-label={`Délai de règlement (jours) — ${t.libelle}`}
                       placeholder="Délai (j)"
                       value={t.delai_reglement_jours ?? ''}
                       onChange={e => modifier(i, 'delai_reglement_jours', e.target.value)} />
                <Input id={`gen-echeance-semaines-${i}`} type="number" min="0" step="any"
                       aria-label={`Semaines indicatives — ${t.libelle}`}
                       placeholder="Sem. (indicatif)"
                       value={t.semaines_indicatives ?? ''}
                       onChange={e => modifier(i, 'semaines_indicatives', e.target.value)} />
                <Input id={`gen-echeance-date-${i}`} type="date"
                       aria-label={`Date prévue — ${t.libelle}`}
                       value={t.date_prevue || ''}
                       onChange={e => modifier(i, 'date_prevue', e.target.value)} />
                <div className="flex gap-1">
                  <Button type="button" variant="ghost" size="sm" aria-label={`Monter — ${t.libelle}`}
                          disabled={i === 0} onClick={() => deplacer(i, -1)}>↑</Button>
                  <Button type="button" variant="ghost" size="sm" aria-label={`Descendre — ${t.libelle}`}
                          disabled={i === saisie.length - 1} onClick={() => deplacer(i, 1)}>↓</Button>
                  <Button type="button" variant="ghost" size="sm" aria-label={`Retirer — ${t.libelle}`}
                          disabled={saisie.length <= 1} onClick={() => retirer(i)}>×</Button>
                </div>
              </div>
            ))}
            <div>
              <Button type="button" variant="outline" size="sm" onClick={ajouter}>
                Ajouter un jalon
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              La dernière tranche vaut toujours le reste du total : facture d'acompte
              et PDF lisent ces mêmes valeurs. La date prévue est facultative.
              Délai de règlement en jours et semaines (« indicatif ») facultatifs.
            </p>
            {somme != null && somme !== 100 && (
              <p role="alert" data-testid="echeancier-somme" className="text-xs text-warning">
                Total des pourcentages : {somme} % — les jalons doivent totaliser 100 %.
              </p>
            )}
            <div>
              <Button type="button" variant="ghost" size="sm" onClick={() => setSaisie(null)}>
                Revenir à l'échéancier de la société
              </Button>
            </div>
          </>
        )}
        {setCondition && (
          <ConditionsContractuelles conditions={conditions} setCondition={setCondition}
                                    erreurs={erreursConditions} clients={clients}
                                    setSaisie={setSaisie} />
        )}
      </CardContent>
    </Card>
  )
}
