import { BadgeCheck, Loader2, ShieldCheck, TriangleAlert } from 'lucide-react'
import { Badge } from '../../../ui'
import { cn } from '../../../lib/cn'

/* ============================================================================
   AOF93 — Barre de verdict PERMANENTE de l'atelier de calepinage.
   ----------------------------------------------------------------------------
   Toujours visible, elle répond en un coup d'œil à la seule question qui
   compte avant un dépôt : « ce qu'on dessine tient-il l'engagement du
   marché ? ».

   **Aucune valeur n'est calculée ni rédigée ici.** Le serveur renvoie, pour
   chaque grandeur, le couple `{ valeur, texte }` — `texte` étant déjà formaté
   par `core.formats_fr` (le MÊME formateur que les pièces imprimées, donc
   aucune divergence écran/PDF possible). Le verdict lui-même est un CODE
   serveur (`confirme` / `tendu`) accompagné de son libellé et de son motif :
   le front n'en choisit que la couleur.

   Deux garde-fous portés par cette barre :
   • le badge « optimum prouvé — programmation dynamique au pas de 1 cm » ne
     s'affiche QUE si le régime de preuve du moteur l'autorise (AOF44) ; une
     recherche heuristique n'a pas le droit de se présenter comme prouvée ;
   • quand la capacité passe sous l'engagement, la mention de LIGNE
     D'AJUSTEMENT est affichée automatiquement — c'est le serveur qui décide
     (`ligne_ajustement.requise`), jamais une comparaison écrite ici.

   `perime` (piloté par `useCalepinage`, AOF94) estompe TOUTES les grandeurs
   dérivées et affiche « recalcul… » : on n'affiche jamais l'ancien chiffre
   comme s'il était courant.

   ── Contrat de charge utile ───────────────────────────────────────────────
   resultat = {
     modules:    { valeur, texte },              // ex. « 314 modules »
     puissance:  { valeur, texte },              // ex. « 196,3 kWc »
     engagement: { valeur, texte },              // engagement au marché
     marge:      { valeur, texte, signe: 'positif'|'nul'|'negatif' },
     verdict:    { code: 'confirme'|'tendu', libelle, motif? },
     preuve?:    { prouve: bool, badge },        // AOF44 — régime de preuve
     sceau?:     { dessine_compte: bool, libelle },
     ligne_ajustement?: { requise: bool, mention },
   }
   ========================================================================== */

const TONS_VERDICT = {
  confirme: { tone: 'success', icone: ShieldCheck },
  tendu: { tone: 'warning', icone: TriangleAlert },
}

const TONS_MARGE = {
  positif: 'text-success',
  nul: 'text-muted-foreground',
  negatif: 'text-destructive',
}

function Grandeur({ libelle, valeur, perime, className, ...rest }) {
  if (!valeur?.texte) return null
  return (
    <div className="flex flex-col" {...rest}>
      <span className="text-[11px] uppercase tracking-wide text-muted-foreground">{libelle}</span>
      <span
        className={cn('font-display text-base font-semibold tabular-nums', className, perime && 'opacity-40')}
        data-perime={perime ? 'true' : undefined}
        title={perime ? 'Valeur en cours de recalcul — non courante' : undefined}
      >
        {valeur.texte}
      </span>
    </div>
  )
}

/**
 * @param {object}  resultat  Résultat serveur (contrat ci-dessus).
 * @param {boolean} [perime]  Un recalcul est en vol : les grandeurs affichées
 *                            ne sont plus courantes (AOF94).
 */
export default function VerdictBar({ resultat, perime = false }) {
  if (!resultat?.verdict?.code) return null

  const { verdict, preuve, sceau, ligne_ajustement: ligneAjustement } = resultat
  const style = TONS_VERDICT[verdict.code] || { tone: 'neutral', icone: ShieldCheck }
  const Icone = style.icone

  return (
    <div
      data-ao-verdict={verdict.code}
      role="status"
      aria-live="polite"
      aria-busy={perime ? 'true' : 'false'}
      className="flex flex-wrap items-center gap-x-6 gap-y-3 rounded-md border border-border bg-card px-4 py-3"
    >
      <div data-ao-compte="modules">
        <Grandeur libelle="Modules" valeur={resultat.modules} perime={perime} />
      </div>
      <Grandeur libelle="Puissance" valeur={resultat.puissance} perime={perime} />
      <Grandeur libelle="Engagement au marché" valeur={resultat.engagement} perime={perime} />
      <Grandeur
        libelle="Marge"
        valeur={resultat.marge}
        perime={perime}
        data-marge-signe={resultat.marge?.signe}
        className={TONS_MARGE[resultat.marge?.signe] || 'text-foreground'}
      />

      <div className="ml-auto flex flex-wrap items-center gap-2">
        {perime && (
          <Badge tone="neutral" data-recalcul="true">
            <Loader2 className="size-3 animate-spin" aria-hidden="true" />
            recalcul…
          </Badge>
        )}
        {/* AOF44 — badge de preuve : jamais affiché sur une méthode heuristique. */}
        {preuve?.prouve && preuve.badge && (
          <Badge tone="info" data-preuve="prouve">
            <BadgeCheck className="size-3" aria-hidden="true" />
            {preuve.badge}
          </Badge>
        )}
        {sceau?.dessine_compte && sceau.libelle && (
          <Badge tone="outline" data-sceau="dessine-compte">{sceau.libelle} ✓</Badge>
        )}
        <Badge tone={style.tone} data-verdict={verdict.code}>
          <Icone className="size-3.5" aria-hidden="true" />
          {verdict.libelle}
        </Badge>
      </div>

      {verdict.motif && (
        <p className="w-full text-xs text-muted-foreground">{verdict.motif}</p>
      )}

      {/* Mention automatique de la ligne d'ajustement — décidée par le serveur. */}
      {ligneAjustement?.requise && ligneAjustement.mention && (
        <p className="w-full text-xs font-medium text-destructive" data-ligne-ajustement="requise">
          {ligneAjustement.mention}
        </p>
      )}
    </div>
  )
}
