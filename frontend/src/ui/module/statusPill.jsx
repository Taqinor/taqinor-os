import { StatusPill } from '../StatusPill'

/* ============================================================================
   UX1 — Fabrique de pastille de statut par module.
   ----------------------------------------------------------------------------
   Chaque module ERP a sa propre taxonomie de statuts (ex. contrats :
   { actif, expire, resilie }). `statusPill(map)` crée UN composant `Pill` qui
   mappe une valeur de statut connue vers son libellé + son ton, en réutilisant
   le primitif StatusPill (point coloré + jetons de thème). On expose aussi des
   helpers (toneOf / labelOf / options) pour les colonnes de tableau et les
   filtres de vues sauvegardées.

   Usage :
     const StatutContrat = statusPill({
       actif:   { label: 'Actif',   tone: 'success' },
       expire:  { label: 'Expiré',  tone: 'warning' },
       resilie: { label: 'Résilié', tone: 'danger'  },
     })
     <StatutContrat status="actif" />
   ========================================================================== */

export function statusPill(map = {}) {
  function Pill({ status, label, ...props }) {
    const entry = map[status]
    return (
      <StatusPill
        status={status}
        tone={entry?.tone}
        label={label ?? entry?.label ?? status}
        {...props}
      />
    )
  }

  Pill.toneOf = (status) => map[status]?.tone
  Pill.labelOf = (status) => map[status]?.label ?? status
  Pill.options = Object.entries(map).map(([value, v]) => ({
    value,
    label: v.label ?? value,
  }))

  return Pill
}

export default statusPill
