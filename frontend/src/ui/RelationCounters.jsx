/* VX159 — RelationCounters : le seul bon réflexe d'Odoo, systématisé. En tête
   d'une fiche 360, une rangée de compteurs cliquables (« 3 devis · 1 facture ·
   2 tickets SAV »). @coord ARC46 (construisible avant RecordShell, migrable
   dedans ensuite).

   CONTRAT :
     • Chaque compteur lit une donnée DÉJÀ chargée par la fiche — JAMAIS une
       nouvelle agrégation cross-app (frontière selectors.py respectée côté back).
     • `to` (optionnel) → le compteur est un lien vers la liste cible
       PRÉ-FILTRÉE (query param sur une route EXISTANTE : ?client= / ?fournisseur=
       / ?produit= / ?lead=, même patron que VX112) — zéro nouvelle route.
     • Un compteur sans `count` fini est ignoré (jamais un « 0 » inventé) ; si
       aucun compteur n'est affichable, le composant rend null.

   Props :
     • counters : [{ key, label, count, to? }]
     • className : classes utilitaires additionnelles sur le conteneur */
export default function RelationCounters({ counters = [], className = '' }) {
  const visible = counters.filter((c) => c && c.count != null && Number.isFinite(Number(c.count)))
  if (visible.length === 0) return null

  const chip =
    'inline-flex items-baseline gap-1.5 rounded-full border border-border px-3 py-1 text-sm'

  return (
    <div
      className={`flex flex-wrap items-center gap-2${className ? ` ${className}` : ''}`}
      role="list"
      aria-label="Relations de la fiche"
      data-testid="relation-counters"
    >
      {visible.map((c) => {
        const inner = (
          <>
            <span className="font-semibold tabular-nums text-foreground">{c.count}</span>
            <span className="text-muted-foreground">{c.label}</span>
          </>
        )
        return c.to ? (
          <a
            key={c.key}
            href={c.to}
            role="listitem"
            title={`Voir : ${c.label}`}
            className={`${chip} bg-card transition-colors hover:border-primary/50 hover:bg-accent`}
          >
            {inner}
          </a>
        ) : (
          <span key={c.key} role="listitem" className={`${chip} bg-muted/40`}>
            {inner}
          </span>
        )
      })}
    </div>
  )
}
