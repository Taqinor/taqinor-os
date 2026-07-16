import { Link } from 'react-router-dom'
import { cn } from '../lib/cn'

/* VX159/VX250 — RelationCounters : le seul bon réflexe d'Odoo, systématisé.
   Chaque fiche 360 (Lead, Client, Fournisseur, Produit, et — VX250 — le
   détail Devis/Facture) affichait ses relations À SA FAÇON, aucune
   convention « compteurs cliquables en tête de fiche » (« 3 devis · 1
   facture impayée · 2 tickets SAV »). UN SEUL composant, jamais un second
   (@coord VX159/ARC46 — construit indépendant, migrable dans RecordShell
   plus tard).

   Composant 100 % PRÉSENTATION : `counters` est déjà résolu par l'APPELANT
   via le selector/les données du domaine CIBLE (jamais une agrégation
   cross-app posée ICI — la frontière `selectors.py` reste celle de chaque
   domaine). `prix_achat`/toute donnée interne ne transite JAMAIS par ce
   composant — il ne reçoit que { label, count, to? }.

   `counters`: [{ label, count, to? }] — un compteur à `count === 0` est
   simplement OMIS (jamais un badge vide) ; `to` absent → texte statique
   (jamais un lien mort). Le nombre et le libellé forment UN SEUL nœud texte
   (« 3 devis », jamais un <strong>3</strong> isolé) : une fiche affiche
   parfois le même total ailleurs (ex. un Stat déjà existant) — un nombre nu
   isolé collisionnerait avec les assertions de texte exact des tests déjà en
   place sur ces écrans. */
export function RelationCounters({ counters = [], className }) {
  const visible = (counters ?? []).filter((c) => c && c.count > 0)
  if (visible.length === 0) return null

  return (
    <div
      className={cn('flex flex-wrap items-center gap-x-1.5 gap-y-1 text-sm', className)}
      aria-label="Relations de cette fiche"
    >
      {visible.map((c, i) => {
        const text = `${c.count} ${c.label}`
        return (
          <span key={c.key ?? c.label} className="flex items-center">
            {i > 0 && <span className="mx-1.5 text-muted-foreground" aria-hidden="true">·</span>}
            {c.to ? (
              <Link
                to={c.to}
                className="font-medium tabular-nums text-foreground underline-offset-2 hover:text-primary hover:underline"
              >
                {text}
              </Link>
            ) : (
              <span className="font-medium tabular-nums text-foreground">{text}</span>
            )}
          </span>
        )
      })}
    </div>
  )
}

export default RelationCounters
