// COUVBAT (ordre fondateur, 26/08/2026) — LE CURSEUR « N BATTERIES » DIT ENFIN
// CE QU'IL COUVRE, ET JUSQU'OÙ ON POURRAIT ALLER.
//
// Deux promesses, et une seule source pour chacune :
//   (1) COUVERTURE — à chaque cran, la part de la consommation du client
//       réellement couverte (solaire direct + batterie), jour ET nuit. Elle
//       vient du MOTEUR HORAIRE (payload `couverture_batterie`), plus du
//       simulateur approché du navigateur : la page LIT, elle ne recalcule pas.
//   (2) AUTONOMIE COMPLÈTE — le nombre de batteries qui couvrirait toute la
//       journée et toute la nuit. Il peut DÉPASSER ce que ce toit remplit
//       chaque jour : dans ce cas on le MONTRE quand même, marqué hors de la
//       plage recommandée — jamais caché, jamais vendu.
//
// Le contrat PARTAGÉ (PACT10) est lu tel quel : si le serveur change de forme,
// ces tests tombent au lieu de laisser les deux moitiés diverger en silence.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { batteryCoverageInfo, type ProposalResponse } from '../src/lib/proposition';

const read = (rel: string): string =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

const PAGE = read('../src/pages/proposition/[...token].astro');
// Les commentaires ne prouvent rien : on ne cherche que dans le CODE.
const CODE = PAGE
  .replace(/<!--[\s\S]*?-->/g, ' ')
  .replace(/\{\/\*[\s\S]*?\*\/\}/g, ' ')
  .replace(/\/\*[\s\S]*?\*\//g, ' ')
  .replace(/^[ \t]*\/\/.*$/gm, ' ');

// L'échantillon partagé porte l'enveloppe PACT10 {endpoint, pourquoi, exemple}.
const CONTRAT = JSON.parse(read(
  '../../../backend/django_core/apps/ventes/contract_samples/couverture_batterie.json',
));
const SERVI = CONTRAT.exemple.couverture_batterie;
const p = (couverture: unknown): Pick<ProposalResponse, 'couverture_batterie'> =>
  ({ couverture_batterie: couverture } as Pick<ProposalResponse, 'couverture_batterie'>);

describe('COUVBAT — batteryCoverageInfo lit le contrat PARTAGÉ, sans rien inventer', () => {
  it('null quand la clé est absente, nulle ou illisible', () => {
    expect(batteryCoverageInfo({})).toBeNull();
    expect(batteryCoverageInfo(p(null))).toBeNull();
    expect(batteryCoverageInfo(p({}))).toBeNull();
    // Une capacité de pack absente ⇒ rien : on n'y substitue JAMAIS un module
    // de catalogue (« 5 kWh ») que ce client n'achète pas.
    expect(batteryCoverageInfo(p({ pas: SERVI.pas }))).toBeNull();
    expect(batteryCoverageInfo(p({ capacite_utile_pack_kwh: 0, pas: SERVI.pas }))).toBeNull();
    expect(batteryCoverageInfo(p({ capacite_utile_pack_kwh: 5, pas: [] }))).toBeNull();
  });

  it('recopie les crans du serveur — jamais un chiffre recalculé', () => {
    const info = batteryCoverageInfo(p(SERVI))!;
    expect(info).not.toBeNull();
    expect(info.capaciteUtilePackKwh).toBe(SERVI.capacite_utile_pack_kwh);
    expect(info.nbPacksMax).toBe(SERVI.nb_packs_max);
    expect(info.pas).toHaveLength(SERVI.pas.length);
    expect(info.pas.map((s) => s.nbPacks)).toEqual(SERVI.pas.map((s: { nb_packs: number }) => s.nb_packs));
    expect(info.pas[1].couverturePct).toBe(SERVI.pas[1].couverture_pct);
    expect(info.pas[1].capaciteKwh).toBe(SERVI.pas[1].capacite_kwh);
    expect(info.pas[1].reseauAnnuelKwh).toBe(SERVI.pas[1].reseau_annuel_kwh);
  });

  it('les trois bandes horaires sont servies telles quelles (24 valeurs)', () => {
    const info = batteryCoverageInfo(p(SERVI))!;
    for (const step of info.pas) {
      expect(Object.keys(step.joursTypes).sort()).toEqual(['1', '11', '4', '7']);
      for (const bandes of Object.values(step.joursTypes)) {
        expect(bandes.direct).toHaveLength(24);
        expect(bandes.battery).toHaveLength(24);
        expect(bandes.grid).toHaveLength(24);
      }
    }
    expect(info.pas[1].joursTypes['7'].battery)
      .toEqual(SERVI.pas[1].jours_types['7'].batterie_kwh);
  });

  it('chaque jour type porte SON taux — servi, jamais recalculé ici', () => {
    const info = batteryCoverageInfo(p(SERVI))!;
    expect(info.pas[1].joursTypes['7'].couverturePct)
      .toBe(SERVI.pas[1].jours_types['7'].couverture_pct);
    // …et il MONTE avec le nombre de batteries, comme le taux annuel.
    const pcts = info.pas.map((s) => s.joursTypes['7'].couverturePct);
    expect(pcts).toEqual([...pcts].sort((a, b) => a - b));
  });

  it('un mois sans taux servi est ÉCARTÉ — la page ne le calcule pas', () => {
    const abime = JSON.parse(JSON.stringify(SERVI));
    delete abime.pas[1].jours_types['7'].couverture_pct;
    const info = batteryCoverageInfo(p(abime))!;
    expect(info.pas[1].joursTypes['7']).toBeUndefined();
    expect(info.pas[1].joursTypes['1']).toBeDefined();
  });

  it('la couverture MONTE avec le nombre de batteries (jour ET nuit)', () => {
    const info = batteryCoverageInfo(p(SERVI))!;
    const pcts = info.pas.map((s) => s.couverturePct);
    expect(pcts).toEqual([...pcts].sort((a, b) => a - b));
    expect(info.pas[0].nbPacks).toBe(0);
    expect(info.pas[0].batterieAnnuelKwh).toBe(0);
  });

  it('un jour type illisible est IGNORÉ, jamais complété localement', () => {
    const abime = JSON.parse(JSON.stringify(SERVI));
    abime.pas[1].jours_types['7'].batterie_kwh = [1, 2, 3]; // pas 24 valeurs
    const info = batteryCoverageInfo(p(abime))!;
    expect(info.pas[1].joursTypes['7']).toBeUndefined();
    expect(info.pas[1].joursTypes['1']).toBeDefined();
  });

  it('un cran sans couverture lisible est ÉCARTÉ, pas rempli d’un zéro', () => {
    const abime = JSON.parse(JSON.stringify(SERVI));
    abime.pas[2].couverture_pct = null;
    const info = batteryCoverageInfo(p(abime))!;
    expect(info.pas.map((s) => s.nbPacks)).not.toContain(SERVI.pas[2].nb_packs);
  });
});

describe('COUVBAT — le repère « autonomie complète » et son honnêteté', () => {
  it('lit le repère du serveur tel quel', () => {
    const auto = batteryCoverageInfo(p(SERVI))!.autonomie!;
    expect(auto).not.toBeNull();
    expect(auto.nbPacks).toBe(SERVI.autonomie_complete.nb_packs);
    expect(auto.capaciteKwh).toBe(SERVI.autonomie_complete.capacite_kwh);
    expect(auto.couverturePct).toBe(SERVI.autonomie_complete.couverture_pct);
    expect(auto.mois).toBe(SERVI.autonomie_complete.mois);
  });

  it('AU-DELÀ DU REMPLISSAGE : le repère reste lu, marqué non remplissable', () => {
    // L'exemple du contrat PORTE ce cas (autonomie 6 packs > 2 remplissables).
    const auto = batteryCoverageInfo(p(SERVI))!.autonomie!;
    expect(auto.seRemplitTousLesJours).toBe(false);
    expect(auto.nbPacksRemplissables).toBeLessThan(auto.nbPacks);
    expect(auto.capaciteRemplissableMaxKwh).toBeGreaterThan(0);
  });

  it('le cas HEUREUX du contrat : atteignable ET remplissable', () => {
    const variante = CONTRAT.exemple_autonomie_atteignable.couverture_batterie;
    const auto = batteryCoverageInfo(p(variante))!.autonomie!;
    expect(auto.seRemplitTousLesJours).toBe(true);
    expect(auto.dansLeCurseur).toBe(true);
  });

  it('un repère illisible ⇒ pas de repère, jamais un nombre fabriqué', () => {
    const abime = JSON.parse(JSON.stringify(SERVI));
    abime.autonomie_complete = { nb_packs: null, capacite_kwh: null };
    expect(batteryCoverageInfo(p(abime))!.autonomie).toBeNull();
    // …et les crans, eux, restent servis : une moitié illisible n'emporte pas
    // l'autre.
    expect(batteryCoverageInfo(p(abime))!.pas.length).toBe(SERVI.pas.length);
  });
});

describe('COUVBAT — la page BRANCHE le bloc servi (et retombe proprement sans lui)', () => {
  it('lit le contrat au lieu de rejouer son moteur approché', () => {
    expect(CODE).toContain('batteryCoverageInfo(data!)');
    expect(CODE).toContain('const batteryCoverage: BatteryCoverageInfo | null');
    // Le dessin vient des bandes SERVIES quand elles existent.
    expect(CODE).toContain('coverageBandsInitial');
    expect(CODE).toContain('renderBatterySplitSvg(coverageBandsInitial');
  });

  it('la capacité par pack vient du DEVIS (CAPUTIL) avant tout repli catalogue', () => {
    // `batteryCoverage.capaciteUtilePackKwh` passe AVANT
    // `DEFAULT_UNIT_CAPACITY_KWH`, qui est une référence de catalogue.
    const i = CODE.indexOf('batteryCoverage?.capaciteUtilePackKwh');
    const j = CODE.indexOf('DEFAULT_UNIT_CAPACITY_KWH;');
    expect(i).toBeGreaterThan(-1);
    expect(j).toBeGreaterThan(i);
  });

  it('le curseur monte jusqu’au dernier cran servi (autonomie comprise)', () => {
    expect(CODE).toContain('batteryCoverage?.nbPacksMax ?? 0');
  });

  it('le repère d’autonomie est affiché, avec sa réserve d’honnêteté', () => {
    expect(CODE).toContain('id="battery-sim-autonomy"');
    expect(CODE).toContain('id="battery-sim-autonomy-n"');
    expect(CODE).toContain('id="battery-sim-autonomy-limite"');
    // La réserve est MASQUÉE quand la banque se remplit — jamais l'inverse.
    expect(CODE).toContain('hidden={batteryCoverage.autonomie.seRemplitTousLesJours}');
    // FR/EN/AR comme tout le reste de la page.
    expect(CODE).toContain('data-fr="Autonomie maximale :"');
    expect(CODE).toContain('data-en="Maximum autonomy:"');
    expect(CODE).toContain('data-ar="أقصى استقلالية:"');
  });

  it('le repère NE PROMET PAS une couverture que le moteur dément', () => {
    // Le N est un PLAFOND DE CAPACITÉ, pas une couverture atteinte : sur le
    // contrat lui-même il ne couvre que 97,5 % (et jusqu'à 73,4 % sur d'autres
    // toits). L'ancienne formulation « de quoi couvrir votre journée ET votre
    // nuit » était donc un chiffre promis que le serveur contredit.
    expect(SERVI.autonomie_complete.couverture_pct).toBeLessThan(100);
    expect(CODE).not.toContain('de quoi couvrir votre journée ET votre nuit');
    expect(CODE).not.toContain('enough to cover your day AND your night');
    // Ce qu'il dit à la place : le taux SERVI, puis ce que le plafond signifie.
    expect(CODE).toContain('id="battery-sim-autonomy-pct"');
    expect(CODE).toContain('batteryCoverage.autonomie.couverturePct');
    expect(CODE).toContain('data-fr="de votre consommation annuelle."');
    expect(CODE).toContain('Au-delà, une batterie de plus n’apporte rien.');
    // Taux non chiffré par le moteur ⇒ fragment masqué, jamais une promesse.
    expect(CODE).toContain('hidden={batteryCoverage.autonomie.couverturePct === null}');
  });

  it('les crans non remplissables sont GRISÉS, pas supprimés', () => {
    expect(CODE).toContain('data-batt-tick={n}');
    expect(CODE).toContain("remplit ? undefined : 'opacity-40'");
    // Bloc servi SANS cran pour ce n ⇒ non remplissable, jamais « supposé bon ».
    expect(CODE).toContain('?.seRemplitTousLesJours ?? false)');
    expect(CODE).not.toContain('?.seRemplitTousLesJours ?? true)');
  });

  it('le curseur ne dépasse JAMAIS le dernier cran servi', () => {
    // Sinon les crans au-delà repartent en silence vers le simulateur
    // approché, sans grisé ni avertissement — ils auraient l'air recommandés.
    expect(CODE).toContain('const BATTERY_SIM_MAX_UNITS = batteryCoverage');
    expect(CODE).toContain('? batteryCoverage.nbPacksMax');
    expect(CODE).toContain(': Math.max(offeredUnits, storageRealMax || 3)');
    // Et l'avertissement couvre aussi le cas « aucun cran pour ce n ».
    expect(CODE).toContain('(cfg.couverture ? (!cran || !cran.remplit) : false)');
  });

  it('les puces d’occupation et les onglets rendent la main au simulateur', () => {
    // RÉGRESSION corrigée : le moteur n'a chiffré QUE le foyer du devis ; sur
    // toute autre hypothèse, TOUTE la ligne (graphe + kWh + taux) repasse au
    // simulateur client — jamais un graphe figé à côté de chiffres qui bougent.
    expect(CODE).toContain('function selectionServieParLeMoteur()');
    expect(CODE).toContain("currentVariant === 'normal'");
    expect(CODE).toContain('currentOccupancy === (cfg.occupancy ?? ');
    expect(CODE).toContain('if (!couv || !selectionServieParLeMoteur()) return null;');
  });

  it('le taux affiché près du graphe est celui du JOUR, pas de l’année', () => {
    // Un taux annuel à côté de trois kWh journaliers ferait voisiner deux
    // grandeurs différentes sans le dire.
    expect(CODE).toContain('const pct = bandes ? bandes.couverturePct : null;');
    expect(CODE).toContain('const batteryCoveragePctInitial = coverageBandsInitial?.couverturePct ?? null;');
    // Le sous-libellé reste celui d'une journée dans les DEUX cas : plus de
    // variante « de l'année » à côté de chiffres journaliers.
    expect(CODE).not.toContain('de votre consommation de l’année couverte');
  });

  it('le premier pixel dit la même chose que l’hydratation (SSR)', () => {
    // (a) la couche batterie de la courbe journalière part des MÊMES bandes
    //     servies que l'aire empilée — le pont inter-îles est optionnel.
    expect(CODE).toContain('batterieHoraireKwh: coverageBandsInitial');
    // (b) l'avertissement de sur-stockage suit côté serveur la MÊME règle
    //     élargie que le script client.
    expect(CODE).toContain('const batteryInitialCranNonRemplissable = batteryCoverage');
    expect(CODE).toContain('batteryInitialOverStorageRefuse !== null || batteryInitialCranNonRemplissable');
  });

  it('le script client RELIT la couverture servie (aucun second moteur)', () => {
    expect(CODE).toContain('function servedBandsAt(');
    expect(CODE).toContain('const bandes = servedBandsAt(n);');
    // Le taux affiché est celui du moteur dès qu'il est servi.
    expect(CODE).toContain("fmtPct(pct ?? res.selfSufficiencyPct)");
    // …et le dessin suit EXACTEMENT la même source que les trois kWh.
    expect(CODE).toContain('lastHourly = bandes ?? res.hourly;');
  });

  it('la saison affichée choisit le jour type dessiné', () => {
    expect(CODE).toContain('const COVERAGE_MONTH_BY_SEASON: Record<SeasonId, string>');
    expect(CODE).toContain("hiver: '1', mi_saison: '4', ete: '7'");
    expect(CODE).toContain('__propSetBatteryVariant?.(layers.variant, layers.occupancy, layers.season)');
  });

  it('SANS le bloc servi, la page garde son comportement d’avant', () => {
    // Le simulateur client reste appelé, et sert de repli à chaque endroit.
    expect(CODE).toContain('res.selfSufficiencyPct');
    expect(CODE).toContain('res.directKwh');
    expect(CODE).toContain('batteryInitial.selfSufficiencyPct');
    expect(CODE).toContain('batteryInitial?.directKwh');
  });

  it('explorer reste une EXPLORATION : aucun prix recalculé au curseur', () => {
    // Les prix affichés restent ceux, RÉELS, du devis et du balayage.
    expect(CODE).toContain('function renderPrice(');
    expect(CODE).toContain('cfg.avecTtc');
    expect(CODE).toContain('palierPriceAt(n)');
    // Le bloc de couverture ne porte aucun prix : rien à en tirer.
    expect(JSON.stringify(SERVI).toLowerCase()).not.toContain('prix');
    expect(JSON.stringify(SERVI).toLowerCase()).not.toContain('ttc');
  });
});
