// Coque (22/11) — groupe « pose » du DOM du constructeur, DÉPLACÉ VERBATIM depuis
// BuilderDom.jsx (move only) : `#rp9-layout-window` (personnaliser la disposition) et la
// ligne d'état `#rp9-status` (`BuilderStatut`). Mêmes ids, même ordre (layoutEditor.ts).
import Pourquoi from '../commun/Pourquoi'

export default function BuilderPose({
  expert = false, // ACAL869 — le niveau expert (publié par le rail) : ouvre « Réglages avancés » d'office
}) {
  return (
    <>
          {/* W69 — « Personnaliser la disposition » : porté de apps/web/toiture-3d-pro-11.astro
              (bloc rp9-layout-window/rp9-layout-panel, lignes 478-632) — DEUX modes d'édition
              manuelle des panneaux (▦ Emplacements validés / ✥ Placement libre), pilotés par le
              module partagé roofPro11/layoutEditor.ts. Ids/data-* STRICTEMENT identiques à
              l'astro : le moteur les cherche par id, un id renommé = bouton mort silencieux. */}
          <div id="rp9-layout-window" hidden className="border-t border-border bg-card p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-primary-text">Personnaliser la disposition</p>
              <button type="button" id="rp9-layout-toggle" aria-pressed="false"
                className="border border-brass-400 bg-brass-400/10 px-4 py-2 text-sm font-bold text-primary-text transition-colors hover:bg-brass-400/20">
                Déplacer les panneaux
              </button>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
              Activez, puis dans le <strong className="text-foreground">plan tactile</strong> ci-dessous
              touchez un panneau (bleu) puis un emplacement libre (vert) pour l'y déplacer — ou
              utilisez <strong className="text-foreground">+ / −</strong>. Vous pouvez aussi glisser un
              panneau directement sur la 3D. Les panneaux se calent toujours sur des emplacements
              valides (jamais hors toit, hors retrait ou sur un obstacle) ; le nombre, la puissance,
              la production et les économies se recalculent.
            </p>

            <div id="rp9-layout-panel" hidden className="mt-5 space-y-5">
              <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
                <div>
                  <dd id="rp9-layout-count" className="fig text-lg text-foreground sm:text-xl">—</dd>
                  <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mt-0.5">Panneaux posés<Pourquoi cle="toit.pose_panneaux" /></dt>
                </div>
                <div>
                  <dd id="rp9-layout-kwc" className="fig text-lg text-foreground sm:text-xl">—</dd>
                  <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mt-0.5">Puissance<Pourquoi cle="toit.pose_puissance" /></dt>
                </div>
                <div>
                  <dd id="rp9-layout-free" className="fig text-lg text-foreground sm:text-xl">—</dd>
                  <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mt-0.5">Emplacements libres<Pourquoi cle="toit.pose_emplacements_libres" /></dt>
                </div>
                <div>
                  <dd id="rp9-layout-cover" className="fig text-lg text-primary-text sm:text-xl">—</dd>
                  <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mt-0.5">Couverture besoin<Pourquoi cle="toit.pose_couverture" /></dt>
                </div>
              </dl>

              {/* PV25 — sélection MULTIPLE (marquee au glissé + Maj, ou mode sélection au
                  doigt), déplacement du groupe / de la rangée entière, et nudge d'azimut.
                  Chaque déplacement reste « tout ou rien » : si un seul panneau du groupe
                  n'a pas d'emplacement valide, rien ne bouge.
                  PV34 — les gestes SANS modificateur sont désormais les principaux : glisser
                  sur le toit encadre, double-cliquer prend la rangée. Ces boutons restent le
                  repli tactile (et le mode rangée), et le compteur dit en permanence combien
                  de panneaux sont tenus. */}
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Poser &amp; sélectionner</span>
                <button type="button" id="rp9-layout-fill"
                  className="border border-brass-400 bg-brass-400/10 px-4 py-2.5 text-sm font-bold text-primary-text transition-colors hover:bg-brass-400/20 disabled:cursor-not-allowed disabled:opacity-40">
                  ⤢ Remplir automatiquement
                </button>
                <button type="button" id="rp9-layout-select" aria-pressed="false"
                  className="border border-border px-4 py-2.5 text-sm font-bold text-foreground transition-colors hover:border-brass-400 hover:text-primary-text">
                  ▭ Sélection multiple
                </button>
                <button type="button" id="rp9-layout-clear-sel"
                  className="border border-border px-4 py-2.5 text-sm font-bold text-foreground transition-colors hover:border-brass-400 hover:text-primary-text disabled:cursor-not-allowed disabled:opacity-40">
                  ✕ Effacer la sélection
                </button>
                <span id="rp9-layout-selcount" data-rp9-selcount="0" aria-live="polite"
                  className="text-sm font-semibold text-primary-text">
                  Aucun panneau sélectionné
                </span>
              </div>
              {/* PV26 — annuler / rétablir (Ctrl+Z / Ctrl+Y, ou ⌘). Les flèches du
                  clavier déplacent le panneau (ou le groupe) d'un emplacement. */}
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Historique</span>
                <button type="button" id="rp9-layout-undo" disabled
                  className="border border-border px-4 py-2.5 text-sm font-bold text-foreground transition-colors hover:border-brass-400 hover:text-primary-text disabled:cursor-not-allowed disabled:opacity-40">
                  ↶ Annuler <span className="text-muted-foreground">(Ctrl+Z)</span>
                </button>
                <button type="button" id="rp9-layout-redo" disabled
                  className="border border-border px-4 py-2.5 text-sm font-bold text-foreground transition-colors hover:border-brass-400 hover:text-primary-text disabled:cursor-not-allowed disabled:opacity-40">
                  ↷ Rétablir <span className="text-muted-foreground">(Ctrl+Y)</span>
                </button>
                <span className="text-xs text-foreground">Flèches ← ↑ ↓ → : déplacer d’un emplacement</span>
              </div>

              {/* ACAL869 — mode guidé : les gestes de base restent visibles, le reste est rangé ici (ids rp9-* inchangés, seulement repliés). */}
              <details id="rp9-layout-avance" open={!!expert} className="border border-border p-3">
                <summary className="min-h-11 cursor-pointer py-2 text-sm font-semibold text-foreground">Réglages avancés</summary>
                <div className="mt-3 space-y-5">
              {/* PV30 — DEUX MODES d'édition, côte à côte et explicites. « Emplacements
                  validés » (le défaut) ne déplace un panneau que d'une cellule calculée à
                  une autre : sûr, mais impossible d'y gagner de la place. « Placement
                  libre » déplace au centimètre et laisse RÉGLER le retrait de rive et
                  l'écart entre panneaux — les seules limites qui restent sont physiques
                  (contour du toit, chevauchement, obstacle), et les distances réelles
                  s'affichent pendant le geste. */}
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Mode d’édition</span>
                <button type="button" id="rp9-layout-mode-lattice" aria-pressed="true"
                  className="border border-border px-4 py-2.5 text-sm font-bold text-foreground transition-colors hover:border-brass-400 hover:text-primary-text aria-pressed:border-brass-400">
                  ▦ Emplacements validés
                </button>
                <button type="button" id="rp9-layout-mode-free" aria-pressed="false"
                  className="border border-border px-4 py-2.5 text-sm font-bold text-foreground transition-colors hover:border-brass-400 hover:text-primary-text">
                  ✥ Placement libre
                </button>
              </div>

              <div id="rp9-free-controls" hidden className="space-y-3 border border-brass-400/30 bg-brass-400/5 p-3">
                <p className="text-xs leading-relaxed text-foreground">
                  En placement libre, ces deux marges sont les vôtres : les baisser fait tenir
                  plus de panneaux. Les <strong className="text-foreground">distances réellement
                  mesurées</strong> s’affichent pendant le déplacement — rien n’est réduit dans
                  votre dos. Le contour du toit, les chevauchements et les obstacles restent,
                  eux, infranchissables.
                </p>
                <div className="flex flex-wrap items-center gap-3">
                  <label htmlFor="rp9-free-setback" className="text-sm text-foreground">Retrait de rive (cm)</label>
                  <input id="rp9-free-setback" name="freeSetback" type="text" inputMode="decimal" step="any"
                    className="w-24 border border-border bg-background px-3 py-2 text-sm text-foreground" />
                  <label htmlFor="rp9-free-gap" className="text-sm text-foreground">Écart entre panneaux (cm)</label>
                  <input id="rp9-free-gap" name="freeGap" type="text" inputMode="decimal" step="any"
                    className="w-24 border border-border bg-background px-3 py-2 text-sm text-foreground" />
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <button type="button" id="rp9-free-add" aria-pressed="false"
                    className="border border-brass-400 bg-brass-400/10 px-4 py-2.5 text-sm font-bold text-primary-text transition-colors hover:bg-brass-400/20">
                    ＋ Ajouter un panneau
                  </button>
                  <span id="rp9-free-measure" className="fig text-sm text-primary-text" aria-live="polite"></span>
                </div>
              </div>

              {/* Boutons +/− (touch + mouvement réduit, sans glissé fin) */}
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Ajouter / retirer</span>
                <button type="button" id="rp9-layout-minus" aria-label="Retirer un panneau"
                  className="h-11 w-11 border border-border text-2xl font-bold text-foreground transition-colors hover:border-brass-400 hover:text-primary-text disabled:cursor-not-allowed disabled:opacity-40">−</button>
                <button type="button" id="rp9-layout-plus" aria-label="Ajouter un panneau"
                  className="h-11 w-11 border border-border text-2xl font-bold text-foreground transition-colors hover:border-brass-400 hover:text-primary-text disabled:cursor-not-allowed disabled:opacity-40">+</button>
                <button type="button" id="rp9-layout-reset"
                  className="ml-auto border border-brass-400 bg-brass-400/10 px-4 py-2.5 text-sm font-bold text-primary-text transition-colors hover:bg-brass-400/20">
                  ↺ Réinitialiser la disposition optimale
                </button>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Rangée</span>
                <button type="button" id="rp9-layout-row" aria-pressed="false"
                  className="border border-border px-4 py-2.5 text-sm font-bold text-foreground transition-colors hover:border-brass-400 hover:text-primary-text">
                  ⇔ Déplacer la rangée
                </button>
              </div>
              <p className="text-xs leading-relaxed text-foreground">
                Sur la 3D : <strong className="text-foreground">glissez sur le toit, à côté des
                panneaux</strong>, pour encadrer un groupe ou une rangée ·{' '}
                <strong className="text-foreground">double-clic</strong> sur un panneau = toute sa
                rangée · <strong className="text-foreground">Ctrl (⌘) + clic</strong> ajoute ou
                retire un panneau · <strong className="text-foreground">Maj + glissé</strong> ajoute
                un cadre au groupe · <strong className="text-foreground">Échap</strong> lâche la
                sélection. Glissez ensuite n’importe quel panneau sélectionné : tout le groupe
                suit le curseur.
              </p>

              {/* Nudge d'AZIMUT : n'a de sens que sur un toit en PENTE (la face du pan est
                  imposée par la toiture ; sur toit plat l'azimut est un axe de l'optimiseur).
                  Masqué en toit plat. */}
              <div id="rp9-layout-azimuth" hidden className="flex flex-wrap items-center gap-3">
                <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Azimut du pan</span>
                <button type="button" id="rp9-layout-az-minus" aria-label="Diminuer l’azimut d’un degré"
                  className="h-11 w-11 border border-border text-2xl font-bold text-foreground transition-colors hover:border-brass-400 hover:text-primary-text">−</button>
                <span id="rp9-layout-az-value" className="fig text-lg text-foreground">—</span>
                <button type="button" id="rp9-layout-az-plus" aria-label="Augmenter l’azimut d’un degré"
                  className="h-11 w-11 border border-border text-2xl font-bold text-foreground transition-colors hover:border-brass-400 hover:text-primary-text">+</button>
              </div>

              {/* Repli tactile : tap-sélection d'un panneau → tap-cible d'un emplacement vide.
                  Une mini-carte des cellules (occupées / libres) rend l'interaction code-vérifiable
                  et fonctionne sans glissé fin ni mouvement. */}
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Plan des emplacements (tactile) — touchez un panneau, puis un emplacement libre</p>
                <div id="rp9-layout-grid" className="rp9-layout-grid mt-3" role="group" aria-label="Plan des emplacements de panneaux"></div>
                <p id="rp9-layout-note" className="mt-2 min-h-[1.25rem] text-xs leading-relaxed text-foreground" aria-live="polite"></p>
              </div>
                </div>
              </details>
            </div>
          </div>
    </>
  )
}

/** La ligne d'état du constructeur (`#rp9-status`, écrite par le script). */
export function BuilderStatut() {
  return (
    <p id="rp9-status" className="border-t border-border px-4 py-3 text-sm text-muted-foreground" aria-live="polite">Chargement…</p>
  )
}
