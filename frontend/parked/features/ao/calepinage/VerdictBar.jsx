import { BadgeCheck, Loader2, Save, ShieldCheck, TriangleAlert } from 'lucide-react'
import { Badge, Button } from '../../../ui'
import { cn } from '../../../lib/cn'

/* ============================================================================
   AOF93 — Barre de verdict PERMANENTE de l'atelier de calepinage.
   ----------------------------------------------------------------------------
   RECÂBLAGE DU 03/08/2026 — CE QUI A CHANGÉ, ET POURQUOI.
   Cette barre consommait un contrat inventé : `{modules: {valeur, texte},
   puissance, engagement, marge: {signe}, verdict: {code}, sceau,
   ligne_ajustement}`, avec des textes déjà formatés par le serveur. AUCUNE
   route ne publie cela. Le seul producteur de résultat de calepinage,
   `POST /ao/calepinage/calculer/` (sérialiseur `ResultatCalepinageSerializer`,
   corps bâti par `apps/ao/calepinage_io.resultat_vers_json` +
   `preuve_vers_json`), publie exactement ceci :

     { repere, hash_entree, version_moteur, schema_version,
       total_modules, kwc, engageable, motifs_non_engageable,
       engagement_modules, plans[], rangees[], depuis_cache,
       preuve: { total_retenu, total_optimal, methode, methode_exacte,
                 optimal, libelle, pas_cm, nb_optima, borne_superieure,
                 marge_troncon_min, marge_bande_min, rangee_critique,
                 obstacle_critique, controles[], version_moteur } }

   La barre affiche donc CES champs, tels quels. Elle ne calcule rien.

   DEUX GRANDEURS DE L'ANCIENNE BARRE N'EXISTENT PAS CÔTÉ SERVEUR, et elles ne
   sont PAS reconstituées ici :
   • la MARGE (engagement − capacité) — le serveur ne la publie pas ; la
     soustraire ici serait très exactement le chiffre métier calculé côté
     client que la garde d'AOF94 interdit. La barre affiche les deux comptes
     côte à côte et laisse la comparaison au lecteur ;
   • le VERDICT capacité-vs-engagement (`confirme`/`tendu`) et la mention de
     LIGNE D'AJUSTEMENT qui en découle — même raison : c'est une décision, et
     aucune route ne la rend. (Le moteur sait la produire —
     `core/calepinage/types.py::verdict`, `sensibilites.py` — mais elle ne
     sort que par les sensibilités d'une VARIANTE, pas par le calcul.)

   CE QUI EST BIEN UN VERDICT SERVEUR, et que la barre affiche : `engageable`
   + `motifs_non_engageable` (`core/calepinage/obstacles.engageable` : un
   compte n'est engageable que s'il repose sur du RELEVÉ). Le front n'en
   choisit que la couleur.

   AOF44 — le badge de preuve n'apparaît QUE si le régime de preuve du moteur
   l'autorise (`preuve.methode_exacte`) : une recherche heuristique n'a pas le
   droit de se présenter comme prouvée. Le texte affiché est `preuve.libelle`,
   généré par le moteur.

   `perime` (piloté par `useCalepinage`) estompe TOUTES les grandeurs et
   affiche « recalcul… » : on n'affiche jamais l'ancien chiffre comme s'il
   était courant.

   ── PV32 — état du mode « rangées imposées par l'utilisateur » ────────────
   `preuve.methode` vaut exactement `impose_utilisateur` (vocabulaire
   VERROUILLÉ d'AOF44, `core.calepinage.types.MethodePreuve`) quand le plan
   affiché est celui posé à la main (PV29/PV30) : la barre le dit sans
   détour (« Plan imposé — non optimal ») pour qu'un plan choisi ne puisse
   JAMAIS se faire passer pour un optimum prouvé.

   L'ÉCART À L'OPTIMUM affiché (« -N modules vs optimum ») est LU tel quel
   sur `resultat.plans[0].ecart_a_l_optimum` — un entier que le moteur calcule
   lui-même (`apps/ao/calepinage_io.plan_vers_json`) — jamais reconstitué par
   soustraction de `preuve.total_optimal`/`preuve.total_retenu` ici : c'est
   très exactement le chiffre métier calculé côté client que la garde
   d'AOF94 interdit (voir le paragraphe sur la MARGE ci-dessus). Toitures à
   PLUSIEURS pans : seul le premier plan est lu, faute d'agrégation publiée
   par le serveur — une limite assumée, pas une estimation.

   `onEnregistrerVariante`/`enregistrementEnCours` sont INJECTÉS par
   `CalepinageStudio` (même patron que `onDefinirRetenue` dans
   `VariantesCompare.jsx`) : cette barre reste un composant d'AFFICHAGE, elle
   ne parle jamais au réseau elle-même.
   ========================================================================== */

const estNombre = (valeur) => typeof valeur === 'number' && Number.isFinite(valeur)

function Grandeur({ libelle, valeur, unite, perime, ...rest }) {
  if (!estNombre(valeur)) return null
  return (
    <div className="flex flex-col" {...rest}>
      <span className="text-[11px] uppercase tracking-wide text-muted-foreground">{libelle}</span>
      <span
        className={cn('font-display text-base font-semibold tabular-nums', perime && 'opacity-40')}
        data-perime={perime ? 'true' : undefined}
        title={perime ? 'Valeur en cours de recalcul — non courante' : undefined}
      >
        {valeur}{unite ? ` ${unite}` : ''}
      </span>
    </div>
  )
}

/**
 * @param {object}  resultat  Corps de `/ao/calepinage/calculer/` (contrat ci-dessus).
 * @param {boolean} [perime]  Un calcul est en vol : les grandeurs affichées ne
 *                            sont plus courantes (AOF94).
 * @param {Function} [onEnregistrerVariante]  PV32 — présent SEULEMENT quand un
 *   brouillon de rangées imposées est actif ; enregistre le plan affiché comme
 *   variante ALTERNATIVE (non publiable, sous l'optimum).
 * @param {boolean} [enregistrementEnCours]  PV32 — désactive le bouton pendant l'appel.
 */
export default function VerdictBar({
  resultat, perime = false, onEnregistrerVariante, enregistrementEnCours = false,
}) {
  if (!resultat || !estNombre(resultat.total_modules)) return null

  const preuve = resultat.preuve || null
  // `engageable` est le SEUL verdict que cette route publie. Une réponse qui
  // ne le porte pas n'est pas « engageable » : on n'affiche alors AUCUN
  // verdict, plutôt qu'un vert rassurant sans fondement.
  const engageable = typeof resultat.engageable === 'boolean' ? resultat.engageable : null
  const motifs = Array.isArray(resultat.motifs_non_engageable) ? resultat.motifs_non_engageable : []
  const style = engageable
    ? { tone: 'success', Icone: ShieldCheck, libelle: 'Compte engageable' }
    : { tone: 'warning', Icone: TriangleAlert, libelle: 'Compte non engageable' }
  const { Icone } = style

  // PV32 — vocabulaire VERROUILLÉ d'AOF44 : un plan imposé à la main ne se
  // présente JAMAIS comme un optimum prouvé.
  const modeImpose = preuve?.methode === 'impose_utilisateur'
  // Entier LU tel quel sur le premier plan — aucune soustraction locale
  // (voir l'en-tête du fichier).
  const ecartPremierPlan = resultat.plans?.[0]?.ecart_a_l_optimum
  const ecartTexte = estNombre(ecartPremierPlan)
    ? `${ecartPremierPlan > 0 ? '-' : ''}${ecartPremierPlan} modules vs optimum`
    : null

  return (
    <div
      data-ao-verdict={engageable === null ? undefined : String(engageable)}
      role="status"
      aria-live="polite"
      aria-busy={perime ? 'true' : 'false'}
      className="flex flex-wrap items-center gap-x-6 gap-y-3 rounded-md border border-border bg-card px-4 py-3"
    >
      <div data-ao-compte="modules">
        <Grandeur libelle="Modules" valeur={resultat.total_modules} perime={perime} />
      </div>
      <Grandeur libelle="Puissance" valeur={resultat.kwc} unite="kWc" perime={perime} />
      <div data-ao-compte="engagement">
        <Grandeur
          libelle="Engagement au marché"
          valeur={resultat.engagement_modules}
          unite="modules"
          perime={perime}
        />
      </div>

      <div className="ml-auto flex flex-wrap items-center gap-2">
        {perime && (
          <Badge tone="neutral" data-recalcul="true">
            <Loader2 className="size-3 animate-spin" aria-hidden="true" />
            recalcul…
          </Badge>
        )}
        {resultat.depuis_cache && (
          <Badge tone="outline" data-depuis-cache="true">résultat en cache</Badge>
        )}
        {/* AOF44 — jamais affiché sur une méthode heuristique. */}
        {preuve?.methode_exacte && preuve.libelle && (
          <Badge tone="info" data-preuve="prouve">
            <BadgeCheck className="size-3" aria-hidden="true" />
            {preuve.libelle}
          </Badge>
        )}
        {/* PV32 — un plan imposé le DIT : jamais un optimum prouvé. */}
        {modeImpose && (
          <Badge tone="warning" data-ao-impose-verdict="true">
            <TriangleAlert className="size-3" aria-hidden="true" />
            Plan imposé — non optimal
          </Badge>
        )}
        {modeImpose && ecartTexte && (
          <Badge tone="neutral" data-ao-ecart-optimum="true">{ecartTexte}</Badge>
        )}
        {engageable !== null && (
          <Badge tone={style.tone} data-verdict={String(engageable)}>
            <Icone className="size-3.5" aria-hidden="true" />
            {style.libelle}
          </Badge>
        )}
        {/* PV32 — visible seulement quand `CalepinageStudio` injecte l'action
            (un brouillon de rangées imposées est actif). */}
        {onEnregistrerVariante && (
          <Button
            size="sm"
            variant="outline"
            loading={enregistrementEnCours}
            onClick={onEnregistrerVariante}
          >
            <Save className="size-3.5" aria-hidden="true" />
            Enregistrer comme variante
          </Button>
        )}
      </div>

      {/* Motifs de non-engageabilité : phrases du MOTEUR, affichées verbatim. */}
      {motifs.length > 0 && (
        <ul className="w-full list-disc pl-5 text-xs text-muted-foreground" data-motifs="non-engageable">
          {motifs.map((motif) => <li key={motif}>{motif}</li>)}
        </ul>
      )}
    </div>
  )
}
