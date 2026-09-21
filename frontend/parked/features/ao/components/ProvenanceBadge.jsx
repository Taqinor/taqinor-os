import { SimpleTooltip } from '../../../ui/Tooltip'
import { cn } from '../../../lib/cn'
import { provenanceLabel, provenanceDescription, provenanceToken } from '../provenance'

/* ============================================================================
   AOF9 — ProvenanceBadge : pastille + infobulle de provenance d'une valeur.
   ----------------------------------------------------------------------------
   Petit point coloré (jamais de texte coloré — le contraste AA est vérifié
   sur le point lui-même via les tokens `--ao-provenance-*`, pas sur du texte)
   + libellé FR + infobulle expliquant la provenance (dégagement dérivé,
   fermeture de cotes…). Couleur posée en `style` (le token n'est pas encore
   mappé en utilitaire Tailwind) — jamais un hex en dur (`npm run check-hex`
   ne scanne pas les composants, mais la règle produit reste : `var()` only).

   `level`       : 'mesure' | 'confirmer' | 'deduit' | 'devine' (provenance.js)
   `description` : infobulle custom (sinon la description normative du niveau)
   ========================================================================== */
export function ProvenanceBadge({ level, description, className }) {
  const token = provenanceToken(level)
  const label = provenanceLabel(level)
  const tip = description ?? provenanceDescription(level)

  return (
    <SimpleTooltip label={tip}>
      <span
        className={cn('inline-flex items-center gap-1.5 text-xs font-medium text-foreground', className)}
        data-ao-provenance={level}
      >
        <span
          className="size-2 shrink-0 rounded-full"
          style={token ? { background: `var(${token})` } : undefined}
          aria-hidden="true"
        />
        {label}
      </span>
    </SimpleTooltip>
  )
}

export default ProvenanceBadge
