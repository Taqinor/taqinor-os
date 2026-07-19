import { useState, useRef, useEffect } from 'react'
import { HelpCircle } from 'lucide-react'

/* ============================================================================
   PUB54 — Aide contextuelle FR (« ? » pédagogiques), contenu STATIQUE, zéro
   dépendance.
   ----------------------------------------------------------------------------
   Un « ? » à côté de chaque métrique technique, cliquable ET focusable au
   clavier, qui affiche une explication en français simple. Le contenu vit
   ICI (``METRIC_HELP``, clé stable) — n'importe quel écran adsengine peut
   l'adopter (``<MetricHelp metric="frequency" />``), y compris le Cockpit
   quand sa lane le branche (cette lane ne modifie pas son corps).
   ========================================================================== */

export const METRIC_HELP = {
  cost_per_signature: "Combien coûte, en moyenne, UNE vente signée : dépense publicitaire totale divisée par le nombre de signatures. C'est le seul chiffre qui compte pour une vente consultative — pas le coût par clic ni par lead.",
  spend: "La dépense publicitaire réelle sur la période affichée, telle que rapportée par Meta (devise du compte publicitaire).",
  cpl: "Coût par lead : dépense divisée par le nombre de leads RÉELS générés (pas les « résultats » bruts de Meta, qui peuvent compter des doublons).",
  frequency: "Nombre moyen de fois qu'une même personne a vu votre publicité. Au-delà de 3-4, l'audience se lasse — c'est un signal de fatigue créative, pas juste un chiffre.",
  mer: "Marketing Efficiency Ratio : chiffre d'affaires signé (Odoo, en MAD) divisé par la dépense publicitaire Meta. Un MER de 5 = 5 MAD de vente pour 1 MAD dépensé. N'est calculé que si les deux montants partagent la même devise — jamais converti ni inventé.",
  learning: "L'algorithme Meta a besoin d'environ 50 événements d'optimisation par semaine pour « apprendre » et stabiliser les coûts. Une campagne encore en apprentissage peut avoir des coûts instables — c'est normal et temporaire.",
  junk_rate: "Part des leads reçus clairement invalides (numéro faux, spam/bot, hors zone) — jamais un simple « non qualifié ». Un taux élevé pointe vers un ciblage ou une accroche à revoir.",
  pacing_enveloppe: "Le budget total fixé pour le mois en cours — la limite que le moteur surveille pour ne jamais la dépasser.",
  pacing_burn: "Ce qui a déjà été dépensé ce mois-ci sur l'enveloppe budgétaire.",
  pacing_projection: "Estimation de la dépense totale en fin de mois si le rythme actuel se maintient — permet d'anticiper un dépassement avant qu'il n'arrive.",
  pacing_etat: "Le rythme de dépense comparé à l'enveloppe : « sur le rythme » veut dire que la trajectoire mène pile à l'enveloppe fixée en fin de mois.",
  reconciliation: "Comparaison entre la dépense rapportée par Meta et celle enregistrée dans l'ERP — un écart signale une désynchronisation (sync manquée, arrondi, campagne créée hors moteur) à vérifier.",
  quality_ranking: "Classement Meta de la qualité perçue de votre publicité par les utilisateurs, comparé aux annonces concurrentes visant la même audience (repli en dessous de la moyenne = pénalité de diffusion).",
  hook_rate: "Part des spectateurs d'une vidéo qui regardent au-delà des 3 premières secondes — mesure si l'accroche capte l'attention avant le message.",
  cost_per_result: "Dépense divisée par le nombre de résultats obtenus pour ce créatif/cette dimension (tag hook/angle/format) — permet de comparer des créatifs entre eux.",
  sante_creative: "Score composite (poids fixes) qui résume la santé créative — fatigue, diversité de hooks, fréquence. Affichage et alerte SEULEMENT : jamais utilisé pour décider un budget.",
  sante_operations: "Score composite (poids fixes) qui résume la santé opérationnelle — pacing, câblage, données à jour. Affichage et alerte SEULEMENT : jamais utilisé pour décider un budget.",
  guardrail_quadrant: "Les garde-fous DURS (fréquence, classement qualité, CPL, qualité de compte) : ils ne font QUE freiner (jamais accélérer) une action automatique — un garde-fou qui « freine » bloque la proposition tant que la valeur reste hors seuil.",
}

export default function MetricHelp({ metric, label }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const text = METRIC_HELP[metric]

  useEffect(() => {
    if (!open) return
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  // Clé inconnue : ne rend rien plutôt qu'un « ? » vide (jamais de contenu
  // inventé côté écran).
  if (!text) return null

  return (
    <span className="ae-metric-help" data-testid={`ae-metric-help-${metric}`} ref={ref}
      style={{ position: 'relative', display: 'inline-flex', verticalAlign: 'middle', marginLeft: '0.25rem' }}>
      <button type="button" className="ae-metric-help-btn"
        data-testid={`ae-metric-help-toggle-${metric}`}
        aria-label={`Aide : ${label || metric}`}
        aria-expanded={open}
        onClick={(e) => { e.stopPropagation(); setOpen(o => !o) }}
        style={{ border: 'none', background: 'transparent', color: '#94a3b8', cursor: 'pointer',
          display: 'inline-flex', alignItems: 'center', padding: 0, lineHeight: 0 }}>
        <HelpCircle size={13} aria-hidden="true" />
      </button>
      {open && (
        <span role="tooltip" className="ae-metric-help-popover"
          data-testid={`ae-metric-help-popover-${metric}`}
          style={{ position: 'absolute', top: '130%', left: 0, zIndex: 30, width: 240,
            background: '#0f172a', color: '#f1f5f9', padding: '0.5rem 0.65rem', borderRadius: 6,
            fontSize: '0.78rem', lineHeight: 1.4, fontWeight: 400, boxShadow: '0 8px 20px rgba(0,0,0,0.25)' }}>
          {text}
        </span>
      )}
    </span>
  )
}
