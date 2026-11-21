import { formatNumber } from '../../../lib/format'
import { Badge } from '../../../ui'

/* ACAL784 — deux lignes de l'onglet Raccordement : le régime loi 82-21 du site et la part
   injectée simulée face au plafond légal. Tout est LU du serveur (`regime`, `injection`,
   `injection_motif` du contrat calepinage_raccordement.json, ACAL782/783) : aucun seuil, aucun
   calcul ici. Un bloc absent ne rend aucune ligne. */

function textePuissance(regime) {
  if (regime.puissance_retenue_kw == null) return ''
  return ` — puissance retenue ${formatNumber(regime.puissance_retenue_kw, { decimals: 0 })} kW`
}

function LigneRegime({ regime }) {
  if (regime.a_qualifier) {
    return (
      <p className="text-sm" data-testid="acal784-regime">
        Régime à qualifier : puissance du site inconnue
      </p>
    )
  }
  const base = regime.base_puissance === 'a_confirmer_avec_le_distributeur'
    ? ', base à confirmer avec le distributeur' : ''
  return (
    <p className="text-sm" data-testid="acal784-regime">
      {`Régime 82-21 : ${regime.libelle}${textePuissance(regime)}${base}`}
    </p>
  )
}

function LigneInjection({ injection, motif }) {
  if (!injection) {
    return motif
      ? <p className="text-sm text-muted-foreground" data-testid="acal784-injection">{motif}</p>
      : null
  }
  return (
    <div className="flex flex-col gap-1" data-testid="acal784-injection">
      <p className="flex flex-wrap items-center gap-2 text-sm">
        <span>
          {`Injection simulée : ${formatNumber(injection.part_injectee_pct, { decimals: 0 })} % `
            + `de la production annuelle ; plafond légal ${formatNumber(injection.plafond_pct, { decimals: 0 })} %`}
        </span>
        {injection.depasse
          ? <Badge tone="warning" data-testid="acal784-voyant">Au-dessus du plafond</Badge>
          : null}
      </p>
      {injection.depasse && injection.avertissement
        ? <p className="text-sm text-muted-foreground" data-testid="acal784-avertissement">{injection.avertissement}</p>
        : null}
      {injection.mention
        ? <p className="text-xs text-muted-foreground" data-testid="acal784-mention">{injection.mention}</p>
        : null}
    </div>
  )
}

export default function RegimeEtInjection({ regime = null, injection = null, injectionMotif = null } = {}) {
  if (!regime && !injection && !injectionMotif) return null
  return (
    <section className="flex flex-col gap-2 border border-border/60 px-3 py-2" data-testid="acal784-regime-injection">
      {regime ? <LigneRegime regime={regime} /> : null}
      <LigneInjection injection={injection} motif={injectionMotif} />
    </section>
  )
}
