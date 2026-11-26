import Pourquoi from '../commun/Pourquoi'
import TableauComparatif from './TableauComparatif.jsx'
import { CONS_WINDOW_HTML } from '@roofpro/consumptionMarkup' // ERR-ACAL311-PANNEAU-ABSENT-ERP

// Coque (22/11) — l'INSPECTEUR du constructeur, DÉPLACÉ VERBATIM depuis pages/ventes/ToitureDesign.jsx
// (move only) : la carte « Recommandation » (`rp9-results`, `rp9-reco-*`, `rp9-need-*`), le total des
// zones (`rp9-areas-window`, ancrage de edgesUi.ts / zones.ts), « Comparer les poses » (calepinage) et
// « Affiner ma consommation » (`#rp9-cons-window`). Mêmes ids, même ordre ; toujours monté.

// ERR-ACAL311-PANNEAU-ABSENT-ERP (vague 10, rejeu P5.5) — objet `__html` UNIQUE au module :
// React 19 compare la prop `dangerouslySetInnerHTML` par IDENTITÉ et réécrivait `innerHTML` à
// chaque rendu d'un objet littéral neuf. Le constructeur saisit `#rp9-cons-window` à son boot :
// le nœud qu'il démasquait était remplacé (détaché), la fenêtre affichée restait `hidden`.
const CONS_WINDOW_INNER = { __html: CONS_WINDOW_HTML }

// ACAL1268 — `sansReseau` (lead de pompage) : ni production visée, ni production, ni couverture, ni économies, ni consommation.
export default function InspecteurBuilder({ estCalepinage = false, sansReseau = false }) {
  return (
    <>
        {/* RECOMMANDATION (panneaux/optimiseur visibles ici) */}
        <div id="rp9-results" className="rp9-results rounded-xl border border-border bg-card mt-6 p-6">
          <p className="text-xs font-semibold uppercase tracking-wide text-primary-text">Recommandation</p>
          <p id="rp9-reco-title" className="fig mt-4 text-2xl text-primary-text">—</p>
          <div className="mt-5 border border-border bg-card/60 p-4">
            <label htmlFor="rp9-need-input" className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Panneaux à poser</label>
            <div className="mt-2 flex items-center gap-3">
              <button type="button" id="rp9-need-minus" aria-label="Un de moins" className="h-11 w-11 border border-border text-2xl text-foreground">−</button>
              <input id="rp9-need-input" type="text" inputMode="numeric" defaultValue="—" disabled
                className="fig h-11 w-20 border border-border bg-background text-center text-2xl text-foreground" />
              <button type="button" id="rp9-need-plus" aria-label="Un de plus" className="h-11 w-11 border border-border text-2xl text-foreground">+</button>
            </div>
            <label htmlFor="rp9-cible-kwh" hidden={sansReseau} className="mt-2 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">Production visée (kWh/an)</label>
            <input id="rp9-cible-kwh" hidden={sansReseau} type="text" inputMode="numeric" autoComplete="off" aria-label="Production annuelle visée en kWh par an"
              className="fig mt-1 h-11 w-32 border border-border bg-background text-center text-foreground" />
            <p id="rp9-need-note" className="mt-2 min-h-[1.5rem] text-xs text-muted-foreground" aria-live="polite"></p>
          </div>
          <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-6" aria-live="polite">
            <div><dd id="rp9-reco-kwc" className="fig text-2xl text-foreground">—</dd><dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mt-1">Puissance<Pourquoi cle="toit.reco_puissance" /></dt></div>
            <div><dd id="rp9-reco-panels" className="fig text-2xl text-foreground">—</dd><dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mt-1">Panneaux<Pourquoi cle="toit.reco_panneaux" /></dt></div>
            <div hidden={sansReseau}><dd id="rp9-reco-prod" className="fig text-xl text-foreground">—</dd><dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mt-1">Production<Pourquoi cle="toit.reco_production" /></dt></div>
            <div hidden={sansReseau}><dd id="rp9-reco-cover" className="fig text-xl text-foreground">—</dd><dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mt-1">Couverture<Pourquoi cle="toit.reco_couverture" /></dt></div>
          </dl>
          <dl className="mt-5 border-t border-border pt-5" hidden={sansReseau}>
            <div>
              <dd id="rp9-reco-savings" className="fig text-xl text-primary-text">—</dd>
              <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mt-1">Économies (estimation de l’atelier, plafonnée à la facture)<Pourquoi cle="toit.reco_economies" /></dt>
              <p id="rp9-reco-savings-note" hidden className="mt-1 text-xs text-muted-foreground">Le chiffre du devis est dans l’onglet Économie</p>
            </div>
          </dl>
          <p id="rp9-reco-why" className="mt-5 min-h-[3.5rem] text-xs text-foreground"></p>
          <p id="rp9-reco-bifacial" className="mt-2 text-xs text-muted-foreground"></p>
          <p id="rp9-reco-band" className="mt-2 min-h-[2.5rem] text-xs text-muted-foreground" aria-live="polite"></p>
          <p id="rp9-maxline" className="mt-3 text-xs text-muted-foreground"></p>
        </div>

        {/* CALX94/CALX109 — L'ANCRAGE ATTENDU par `roofPro11/edgesUi.ts` (« Corriger le
            type d'une arête », CALX94) et `roofPro11/zones.ts` (sélecteur de module du pan
            actif, CALX109) : les deux s'accrochent à `ctx.dom.areasWindowEl`, lu depuis
            `#rp9-areas-window` (`roof-tool-pro11.ts`). Cet id n'existait QUE sur la page de
            démonstration publique (`pages/preview/toiture-3d-pro-11.astro`) — absent d'ici,
            il rendait les deux gestes injoignables sur l'écran RÉELLEMENT servi par
            `/calepinage/:id` comme par `/devis-design/:id` (voir l'en-tête de
            `frontend/e2e/calepinage-parcours.spec.js`, CALX130). `edgesUi.ts` retombe sur
            ce même conteneur dès que `#rp9-edges-host` est absent (son repli documenté) :
            un seul ancrage suffit aux deux modules, aucun besoin d'un second conteneur.
            Même contenu/emplacement que la page publique, juste après `#rp9-results` :
            masqué par défaut, affiché par le script dès qu'une zone a un résultat
            (`zones.ts renderAreasPanel`). Non conditionnel au mode — comme `#rp9-results`
            ci-dessus, c'est un module du CONSTRUCTEUR partagé par les trois modes ; un
            conteneur `hidden` par défaut ne change rien au mode devis. */}
        <div id="rp9-areas-window" hidden className="rounded-xl border border-border bg-card mt-6 p-5 sm:p-6">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-primary-text">Total — toutes les zones</p>
            <p className="text-xs text-muted-foreground">Chaque zone est dimensionnée puis ajustable ; les totaux additionnent toutes les zones.</p>
          </div>
          <dl className="mt-4 grid grid-cols-[repeat(auto-fit,minmax(7rem,1fr))] gap-x-6 gap-y-4" aria-live="polite">
            <div>
              <dd id="rp9-areas-total-panels" className="fig text-lg text-foreground sm:text-xl">—</dd>
              <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mt-0.5">Panneaux</dt>
            </div>
            <div>
              <dd id="rp9-areas-total-kwc" className="fig text-lg text-foreground sm:text-xl">—</dd>
              <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mt-0.5">Puissance</dt>
            </div>
            <div hidden={sansReseau}>
              <dd id="rp9-areas-total-prod" className="fig text-lg text-foreground sm:text-xl">—</dd>
              <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mt-0.5">Production estimée</dt>
            </div>
            <div hidden={sansReseau}>
              <dd id="rp9-areas-total-savings" className="fig text-lg text-primary-text sm:text-xl">—</dd>
              <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mt-0.5">Économies estimées</dt>
            </div>
          </dl>
          {/* Liste des zones (script-rendu) : libellé, panneaux, kWc, « Voir » + suppr. La
              zone active est mise en évidence. `edgesUi.ts`/`zones.ts` (module picker,
              CALX109) ajoutent aussi leurs propres panneaux ICI (`appendChild`, patron
              `obstaclesUi.ts ensureTypePicker`) — rien d'autre à câbler côté écran. */}
          <ul id="rp9-areas-list" className="mt-5 space-y-2"></ul>
          <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
            « + Ajouter une zone » fige la zone tracée et démarre un nouveau tracé sur la même
            facture. La 3D et les graphes détaillés affichent la zone sélectionnée (« Voir ») ;
            les totaux ci-dessus restent la somme de toutes les zones. Chiffres indicatifs, pas un devis.
          </p>
        </div>

        {/* ACAL546 — « Comparer les poses » (toit plat), sans colonne en MAD ; mode calepinage seulement. */}
        {estCalepinage && <TableauComparatif />}

        {/* ERR-ACAL311-PANNEAU-ABSENT-ERP — « Affiner ma consommation » (`#rp9-cons-window`) :
            balisage UNIQUE partagé avec la preview publique (`@roofpro/consumptionMarkup`),
            sans lequel `consumption.ts monterProposition` ne montait rien ici (« Reprendre du
            lead », CSV, Ramadan, classe tarifaire). Objet constant (CONS_WINDOW_INNER) : React ne la réécrit pas. */}
        <div hidden={sansReseau}
          // check-no-danger-allow: CONS_WINDOW_HTML est une chaîne CONSTANTE du dépôt (@roofpro/consumptionMarkup), aucune donnée utilisateur
          dangerouslySetInnerHTML={CONS_WINDOW_INNER}
        />

        {/* ACAL780 — charges à venir (voiture électrique, pompe à chaleur) : niveau expert, monté par
            `consumption.ts` ; `hidden` tant que le Mode expert n'est pas actif. */}
        <div data-cons-charges hidden className="mt-2" />
    </>
  )
}
