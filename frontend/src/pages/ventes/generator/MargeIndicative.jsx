// AGNR29 — LA « marge indicative » du générateur, rendue par UN composant
// partagé (Rail d'argent sous la table ET rail latéral ≥ lg). Règle unique
// (AGR134) : une ligne chiffrée sans prix d'achat sort du coût, la marge est
// alors PARTIELLE — jamais de pourcentage calculé sur un coût partiel, et le
// composant le DIT (« marge partielle : N ligne(s) sans prix d'achat »).
// RÈGLE MAISON : donnée INTERNE au générateur, jamais dans une sortie client ;
// rien n'est rendu quand `marge` est absente (compte sans `prix_achat_voir`).
import { formatMoney } from '../../../features/ventes/solar'

const pctMarge = (marge, kpiTotal, lignesSansAchat) => (
  lignesSansAchat === 0 && kpiTotal > 0 ? ` (${Math.round(marge / kpiTotal * 100)} %)` : ''
)

function AvisPartiel({ lignesSansAchat }) {
  if (!(lignesSansAchat > 0)) return null
  return (
    <span className="text-xs text-warning" data-testid="marge-partielle">
      marge partielle : {lignesSansAchat} ligne{lignesSansAchat > 1 ? 's' : ''} sans prix d'achat
    </span>
  )
}

export default function MargeIndicative({ marge, kpiTotal, lignesSansAchat = 0, variante = 'rail' }) {
  if (marge == null) return null
  const ton = marge < 0 ? 'text-destructive' : 'text-success'
  if (variante === 'lateral') {
    return (
      <div>
        <div className="text-xs uppercase tracking-wide text-muted-foreground">
          Marge indicative (interne)
        </div>
        <div className={`text-sm font-semibold ${ton}`}>
          {formatMoney(marge)}
          {pctMarge(marge, kpiTotal, lignesSansAchat)}
        </div>
        <AvisPartiel lignesSansAchat={lignesSansAchat} />
      </div>
    )
  }
  return (
    <div className="gen-total-item">
      {/* VX17 — couleurs via tokens de thème (text-success/destructive)
          plutôt qu'un hex codé en dur. */}
      <span className={`gen-total-label ${ton}`}>
        Marge indicative (interne)
      </span>
      <span className={`gen-total-value ${ton}`}>
        {formatMoney(marge)}
        {pctMarge(marge, kpiTotal, lignesSansAchat)}
      </span>
      <AvisPartiel lignesSansAchat={lignesSansAchat} />
    </div>
  )
}
