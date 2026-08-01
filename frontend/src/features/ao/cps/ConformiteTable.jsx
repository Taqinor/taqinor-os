import { AlertTriangle, RefreshCcw } from 'lucide-react'
import { Badge, Card, EmptyState } from '../../../ui'
import { StatutControle } from '../statusAo'
import { NON_EVALUE, severiteAffichee, valeurExigee } from './ConformiteTable.utils'

/* ============================================================================
   AOF181 — Tableau de conformité VIVANT du cahier des charges (CPS).
   ----------------------------------------------------------------------------
   Chaque ligne est une clause du CPS (AOF14) confrontée à l'état RÉEL du
   dossier. Le verdict n'est PAS produit ici : il vient de la chaîne électrique
   (AOF99 — ratio DC/AC, plafond par onduleur) et du contrôleur de cohérence
   croisée (AOF146). **Aucun chiffre de conformité n'est calculé côté front**
   (garde AOF94) : ni écart, ni ratio, ni « ça passe » déduit d'une comparaison
   de deux nombres affichés. Une clause dont le serveur n'a rien dit s'affiche
   « Non évalué » — jamais « conforme » par défaut, qui est exactement la
   manière dont un dossier part avec un bloquant invisible.

   La sévérité affichée réutilise la pastille PARTAGÉE `StatutControle`
   (`../statusAo`, AOF10) : une clause BLOQUANTE non satisfaite est un
   `bloquant`, une clause non bloquante non satisfaite un `avertissement`, une
   clause satisfaite un `ok`. Aucune taxonomie de plus, aucun hex local.

   Hook e2e : `data-ao-controle` (contrat AOF8) — une ligne de ce tableau EST un
   contrôle individuel de la porte avant dépôt ; aucun nouveau `data-ao-*`.
   ========================================================================== */

function SourceDce({ exigence }) {
  const piece = exigence.source_piece || exigence.source
  if (!piece) return <span className="text-muted-foreground">—</span>
  return (
    <span>
      {piece}
      {exigence.source_page ? `, p. ${exigence.source_page}` : ''}
    </span>
  )
}

function LigneExigence({ exigence }) {
  const severite = severiteAffichee(exigence)
  const bloque = severite === 'bloquant'
  const conformite = exigence.conformite || {}
  return (
    <tr
      data-ao-controle={exigence.code || String(exigence.id)}
      className={`border-b border-border align-top last:border-b-0 ${
        bloque ? 'bg-destructive/5' : ''
      }`}
    >
      <td className="px-2 py-2">
        <span className={`text-sm font-medium ${bloque ? 'text-destructive' : ''}`}>
          {exigence.libelle || exigence.code}
        </span>
        <div className="mt-0.5 flex flex-wrap items-center gap-1">
          {exigence.bloquant && <Badge tone="danger">Bloquante</Badge>}
          {exigence.a_reverifier && (
            <Badge tone="warning">
              <RefreshCcw className="size-3" aria-hidden="true" />
              À revérifier
              {exigence.erratum_ref ? ` — erratum ${exigence.erratum_ref}` : ''}
            </Badge>
          )}
        </div>
      </td>
      <td className="px-2 py-2 text-sm tabular-nums">{valeurExigee(exigence)}</td>
      <td className="px-2 py-2 text-sm tabular-nums">
        {conformite.valeur_constatee != null && conformite.valeur_constatee !== ''
          ? String(conformite.valeur_constatee)
          : <span className="text-muted-foreground">—</span>}
      </td>
      <td className="px-2 py-2 text-xs text-muted-foreground">
        <SourceDce exigence={exigence} />
      </td>
      <td className="px-2 py-2 text-xs text-muted-foreground">
        {conformite.origine_label || conformite.origine || '—'}
      </td>
      <td className="px-2 py-2">
        {severite
          ? <StatutControle status={severite} data-ao-etat={severite} />
          : <Badge tone="neutral" data-ao-etat={NON_EVALUE}>Non évalué</Badge>}
        {conformite.message && (
          <p className={`mt-1 text-xs ${bloque ? 'text-destructive' : 'text-muted-foreground'}`}>
            {conformite.message}
          </p>
        )}
      </td>
    </tr>
  )
}

export default function ConformiteTable({ exigences = [] }) {
  if (exigences.length === 0) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title="Aucune exigence saisie"
        description="Saisissez les clauses du CPS pour que la conformité du dossier devienne vérifiable."
      />
    )
  }

  return (
    <Card className="overflow-x-auto p-0">
      <table className="w-full min-w-[52rem] text-left">
        <caption className="px-3 py-2 text-left text-xs text-muted-foreground">
          Conformité évaluée par le serveur (chaîne électrique et contrôleur avant dépôt) —
          aucune valeur n’est recalculée à l’écran.
        </caption>
        <thead className="text-xs text-muted-foreground">
          <tr className="border-b border-border">
            <th scope="col" className="px-2 py-2 font-medium">Clause</th>
            <th scope="col" className="px-2 py-2 font-medium">Exigé</th>
            <th scope="col" className="px-2 py-2 font-medium">Constaté</th>
            <th scope="col" className="px-2 py-2 font-medium">Source (DCE)</th>
            <th scope="col" className="px-2 py-2 font-medium">Origine du constat</th>
            <th scope="col" className="px-2 py-2 font-medium">Conformité</th>
          </tr>
        </thead>
        <tbody>
          {exigences.map((e) => <LigneExigence key={e.id ?? e.code} exigence={e} />)}
        </tbody>
      </table>
    </Card>
  )
}
