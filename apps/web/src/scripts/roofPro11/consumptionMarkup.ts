/**
 * ERR-ACAL311-PANNEAU-ABSENT-ERP — balisage UNIQUE du panneau « Affiner ma consommation »
 * (W68/W95/W96 + ACAL311). Les deux hôtes du builder le rendent depuis CETTE chaîne :
 * la preview publique (`pages/preview/toiture-3d-pro-11.astro`, `set:html`) et l'atelier
 * ERP (`frontend/src/pages/ventes/ToitureDesign.jsx`, `dangerouslySetInnerHTML`). Avant,
 * il n'existait que dans la page astro : `monterProposition` (consumption.ts) ne trouvait
 * pas `#rp9-cons-panel` dans l'ERP et « Reprendre du lead » restait inatteignable.
 * Les ids sont le contrat lu par `roof-tool-pro11.ts` (`$('rp9-cons-…')`, `$('rp9-appl-…')`).
 * Chaîne constante, sans interpolation : aucune donnée utilisateur n'y entre.
 */
export const CONS_WINDOW_HTML = `
<div id="rp9-cons-window" hidden class="cine-card mt-6 p-5 sm:p-6">
  <div class="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
    <p class="tech-label rule-brass text-brass-300">Affiner ma consommation</p>
    <button type="button" id="rp9-cons-toggle" aria-expanded="false"
      class="border border-brass-400 bg-brass-400/10 px-4 py-2 text-sm font-bold text-brass-300 transition-colors hover:bg-brass-400/20">
      Affiner ma consommation
    </button>
  </div>
  <p class="mt-2 text-xs leading-relaxed text-lune-faint">
    Par défaut votre consommation suit une courbe type calée sur votre facture.
    Affinez-la pour voir l'<strong class="text-lune-soft">autoconsommation</strong>, les
    <strong class="text-lune-soft">économies</strong> (toujours plafonnées à la facture) et la
    <strong class="text-lune-soft">batterie</strong> recommandée bouger en direct.
    Un appareil <strong class="text-lune-soft">déjà compris</strong> ne fait que redessiner la
    répartition (total inchangé) ; un appareil <strong class="text-lune-soft">en plus</strong>
    (clim ou voiture neuve) augmente le total, donc le nombre de panneaux et la batterie.
  </p>

  <div id="rp9-cons-panel" hidden class="mt-5 space-y-6">
    <!-- Bandeau de synthèse : total conso, autoconso, économies, batterie -->
    <dl class="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
      <div>
        <dd id="rp9-cons-total" class="fig text-lg text-white sm:text-xl">—</dd>
        <dt class="tech-label mt-0.5 text-lune-faint">Conso/jour</dt>
      </div>
      <div>
        <dd id="rp9-cons-self" class="fig text-lg text-brass-300 sm:text-xl">—</dd>
        <dt class="tech-label mt-0.5 text-lune-faint">Autoconsommation</dt>
      </div>
      <div>
        <dd id="rp9-cons-savings" class="fig text-lg text-brass-300 sm:text-xl">—</dd>
        <dt class="tech-label mt-0.5 text-lune-faint">Économies/an</dt>
      </div>
      <div>
        <dd id="rp9-cons-batt" class="fig text-lg text-white sm:text-xl">—</dd>
        <dt class="tech-label mt-0.5 text-lune-faint">Batteries</dt>
      </div>
    </dl>

    <!-- W96 — retour sur investissement INDICATIF de la batterie. Hauteur réservée
         (min-height) → zéro CLS ; masqué quand aucune batterie/économie honnête.
         aria-live pour annoncer le retour quand il apparaît. -->
    <p id="rp9-cons-payback" hidden aria-live="polite"
      class="min-h-[1rem] text-xs leading-relaxed text-lune-faint"></p>

    <!-- (A) Édition à la main : barres glissables + saisie numérique -->
    <div>
      <div class="flex flex-wrap items-center justify-between gap-3">
        <p class="tech-label text-lune-faint">Courbe horaire (kWh) — glissez les barres ou tapez les valeurs</p>
        <div class="flex flex-wrap gap-2">
          <button type="button" id="rp9-cons-recal"
            class="border border-white/25 px-3 py-2 text-xs font-semibold text-lune-soft transition-colors hover:border-brass-400 hover:text-brass-300">
            Recaler sur ma facture
          </button>
          <!-- W83 — restaure la forme CALCULÉE (socle facture + appareils) après une
               édition à la main. -->
          <button type="button" id="rp9-cons-reset"
            class="border border-white/25 px-3 py-2 text-xs font-semibold text-lune-soft transition-colors hover:border-brass-400 hover:text-brass-300">
            Réinitialiser la courbe
          </button>
        </div>
      </div>
      <!-- Graphe SVG de conso (barres glissables) — superpose la production (or pâle).
           Hauteur RÉSERVÉE → zéro CLS. -->
      <div class="rp9-cons-graph-wrap mt-3" style="width:100%;height:180px">
        <svg id="rp9-cons-graph" viewBox="0 0 480 160" preserveAspectRatio="none"
          class="rp9-cons-graph" style="width:100%;height:100%;display:block;touch-action:none" role="img" aria-label="Courbe de consommation horaire éditable"></svg>
      </div>
      <!-- Saisie numérique des 24 heures (obligatoire : mobile + mouvement réduit) -->
      <details class="mt-3">
        <summary class="cursor-pointer text-xs font-semibold text-brass-300">Saisie numérique des 24 heures</summary>
        <div id="rp9-cons-inputs" class="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-6"></div>
      </details>
    </div>

    <!-- W95 — PROFIL SAISONNIER (été ≠ hiver) + mini-graphe d'autoconsommation
         MENSUELLE. La production est fortement saisonnière ; un split de conso
         (clim l'été) change HONNÊTEMENT l'autoconsommation annuelle. Hauteurs
         réservées (graphe) → zéro CLS ; mouvement réduit (CSS). -->
    <div class="border-t border-white/10 pt-5">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <p class="tech-label text-lune-faint">Profil saisonnier (été ≠ hiver) + autoconsommation mensuelle</p>
        <button type="button" id="rp9-cons-seasonal-toggle" aria-pressed="false"
          class="border border-white/25 px-3 py-2 text-xs font-semibold text-lune-soft transition-colors hover:border-brass-400 hover:text-brass-300">
          Profil saisonnier : désactivé
        </button>
      </div>
      <!-- Facteurs été/hiver — multiplient le total journalier (la forme est conservée).
           Tout nombre est accepté (step="any", jamais rejeté). -->
      <div id="rp9-cons-seasonal-controls" hidden class="mt-3 grid grid-cols-2 gap-3 border border-white/10 bg-nuit-900/40 p-3 sm:max-w-md">
        <label class="block text-xs text-lune-soft">
          Facteur été (juin–sept.)
          <input id="rp9-cons-summer" type="text" inputmode="decimal" step="any" value="1.3"
            class="mt-1 block w-full border border-white/15 bg-white/5 px-2 py-2 text-sm text-white outline-none focus:border-brass-400" />
        </label>
        <label class="block text-xs text-lune-soft">
          Facteur hiver
          <input id="rp9-cons-winter" type="text" inputmode="decimal" step="any" value="0.9"
            class="mt-1 block w-full border border-white/15 bg-white/5 px-2 py-2 text-sm text-white outline-none focus:border-brass-400" />
        </label>
      </div>
      <!-- Mini-graphe SVG de l'autoconsommation mensuelle (12 barres) — hauteur RÉSERVÉE. -->
      <div class="rp9-cons-month-wrap mt-3" style="width:100%;height:130px">
        <svg id="rp9-cons-month-chart" viewBox="0 0 360 120" preserveAspectRatio="none"
          class="rp9-cons-month-chart" style="width:100%;height:100%;display:block" role="img"
          aria-label="Autoconsommation mensuelle estimée (12 mois)"></svg>
      </div>
    </div>

    <!-- (B) Calculateur d'appareils -->
    <div class="border-t border-white/10 pt-5">
      <p class="tech-label text-lune-faint">Ajouter un appareil</p>
      <div class="mt-3 flex flex-wrap items-end gap-3">
        <label class="block text-sm text-lune-soft">
          Appareil
          <select id="rp9-appl-kind"
            class="mt-1 block w-full border border-white/15 bg-white/5 px-3 py-2.5 text-sm text-white outline-none focus:border-brass-400"></select>
        </label>
        <button type="button" id="rp9-appl-add"
          class="border border-brass-400 bg-brass-400/10 px-4 py-2.5 text-sm font-bold text-brass-300 transition-colors hover:bg-brass-400/20">
          + Ajouter
        </button>
      </div>
      <!-- Saisie spéciale climatisation (BTU ÷ EER) — visible quand « Climatisation » choisie -->
      <div id="rp9-appl-ac" hidden class="mt-3 grid grid-cols-2 gap-3 border border-white/10 bg-nuit-900/40 p-3 sm:grid-cols-4">
        <label class="block text-xs text-lune-soft">
          Puissance (BTU)
          <select id="rp9-ac-btu" class="mt-1 block w-full border border-white/15 bg-white/5 px-2 py-2 text-sm text-white outline-none focus:border-brass-400"></select>
        </label>
        <label class="block text-xs text-lune-soft">
          EER
          <input id="rp9-ac-eer" type="text" inputmode="decimal" value="9"
            class="mt-1 block w-full border border-white/15 bg-white/5 px-2 py-2 text-sm text-white outline-none focus:border-brass-400" />
        </label>
        <label class="block text-xs text-lune-soft">
          Heures/jour
          <input id="rp9-ac-hours" type="text" inputmode="decimal" value="6"
            class="mt-1 block w-full border border-white/15 bg-white/5 px-2 py-2 text-sm text-white outline-none focus:border-brass-400" />
        </label>
        <p id="rp9-ac-watts" class="self-end text-xs text-lune-faint">≈ — W · — kWh/j</p>
      </div>
      <!-- Saisie spéciale voiture électrique (kW × h OU km/jour) -->
      <div id="rp9-appl-ev" hidden class="mt-3 grid grid-cols-2 gap-3 border border-white/10 bg-nuit-900/40 p-3 sm:grid-cols-4">
        <label class="block text-xs text-lune-soft">
          Chargeur (kW)
          <select id="rp9-ev-kw" class="mt-1 block w-full border border-white/15 bg-white/5 px-2 py-2 text-sm text-white outline-none focus:border-brass-400"></select>
        </label>
        <label class="block text-xs text-lune-soft">
          Heures/jour
          <input id="rp9-ev-hours" type="text" inputmode="decimal" value="3"
            class="mt-1 block w-full border border-white/15 bg-white/5 px-2 py-2 text-sm text-white outline-none focus:border-brass-400" />
        </label>
        <label class="block text-xs text-lune-soft">
          ou km/jour
          <input id="rp9-ev-km" type="text" inputmode="decimal" placeholder="ex. 50"
            class="mt-1 block w-full border border-white/15 bg-white/5 px-2 py-2 text-sm text-white outline-none focus:border-brass-400" />
        </label>
        <p id="rp9-ev-note" class="self-end text-xs text-lune-faint">Recharger en plein soleil ↑ l'autoconsommation.</p>
      </div>
      <p id="rp9-appl-note" class="mt-2 min-h-[1rem] text-xs leading-relaxed text-lune-faint" aria-live="polite"></p>

      <!-- Liste des appareils ajoutés (chacun : créneau + « en plus » / « déjà compris » + suppr.) -->
      <ul id="rp9-appl-list" class="mt-4 space-y-2"></ul>
    </div>
  </div>
</div>
`;
