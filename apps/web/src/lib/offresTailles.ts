/**
 * TAILLES (ordre fondateur, 26/08/2026) — lecture du bloc public
 * `offres_tailles` : les TROIS tailles d'installation explorables côté client
 * (Éco → Recommandé → Max), chacune servie dans ses deux variantes
 * `sans` / `avec` batterie.
 *
 * CE MODULE NE CALCULE RIEN — exactement comme `economiesPeriodes.ts`. Il LIT
 * et valide ce que `apps/ventes/offres_tailles.py` a déjà calculé : pas une
 * addition, pas une division, pas un produit en croix. Règle « zéro chiffre
 * inventé » : un chiffre qui apparaît côté client sort du moteur, ou
 * n'apparaît pas.
 *
 * DISCIPLINE D'OMISSION (les `_card_if` du PDF) : toute valeur absente ou
 * illisible fait DISPARAÎTRE la ligne concernée — jamais un zéro, jamais un
 * tiret présenté comme une donnée, jamais un forfait. Une carte peut donc être
 * plus pauvre qu'une autre : c'est la vérité de CE devis-là.
 *
 * Contrat de référence : `apps/ventes/contract_samples/offres_tailles.json`.
 */

/** Un montant servi par le moteur : un nombre fini, rien d'autre. */
function nombre(valeur: unknown): number | null {
  return typeof valeur === 'number' && Number.isFinite(valeur) ? valeur : null;
}

function texte(valeur: unknown): string | null {
  return typeof valeur === 'string' && valeur.trim() ? valeur : null;
}

/**
 * ANTICOPIE — le vocabulaire des familles est BORNÉ à ces trois mots (contrat,
 * note `anticopie`) : jamais un calibre, jamais une quantité de nomenclature.
 * Une famille hors de cette liste est ignorée plutôt que rendue : c'est la
 * garantie que « ce qui change » reste lisible au niveau STANDARD sans livrer
 * la nomenclature.
 */
export const FAMILLES_COMPARABLES = ['panneau', 'onduleur', 'batterie'] as const;
export type FamilleComparable = (typeof FAMILLES_COMPARABLES)[number];

/**
 * Les libellés AFFICHABLES des trois familles, dans les trois langues.
 *
 * Ils vivent ICI, collés au vocabulaire borné, et non dans le gabarit : une clé
 * de contrat (`panneau`) n'est pas un mot d'interface. Rendue brute, elle
 * donnait « − batterie » à un client anglophone et un mot français en
 * caractères latins au milieu d'un tableau arabe RTL.
 *
 * Le type `Record<FamilleComparable, …>` est la garde : ajouter une famille au
 * vocabulaire sans lui donner ses trois langues ne compile pas.
 */
export const FAMILLE_LABELS: Record<FamilleComparable, { fr: string; en: string; ar: string }> = {
  panneau: { fr: 'panneau', en: 'panel', ar: 'لوح' },
  onduleur: { fr: 'onduleur', en: 'inverter', ar: 'عاكس' },
  batterie: { fr: 'batterie', en: 'battery', ar: 'بطارية' },
};

function familles(brut: unknown): FamilleComparable[] {
  if (!Array.isArray(brut)) return [];
  const sortie: FamilleComparable[] = [];
  for (const item of brut) {
    const f = texte(item);
    if (!f) continue;
    if ((FAMILLES_COMPARABLES as readonly string[]).includes(f)
        && !sortie.includes(f as FamilleComparable)) {
      sortie.push(f as FamilleComparable);
    }
  }
  return sortie;
}

/** Une ligne de matériel PUBLIÉE : marque + modèle toujours, garantie
 *  UNIQUEMENT quand la fiche produit la porte (règle `_gar_de_la_fiche`). */
export interface OffreMateriel {
  role: string;
  famille: FamilleComparable | null;
  marque: string | null;
  modele: string | null;
  /** Absente quand la fiche ne la porte pas — jamais une durée supposée. */
  garantieAns: number | null;
}

function materiel(brut: unknown): OffreMateriel[] {
  if (!Array.isArray(brut)) return [];
  const sortie: OffreMateriel[] = [];
  for (const item of brut) {
    if (!item || typeof item !== 'object') continue;
    const o = item as Record<string, unknown>;
    const role = texte(o.role);
    if (!role) continue;
    const marque = texte(o.marque);
    const modele = texte(o.modele);
    // Une ligne sans marque NI modèle ne dirait rien au client : on l'écarte
    // plutôt que d'afficher un rôle nu.
    if (!marque && !modele) continue;
    const fam = texte(o.famille);
    const garantie = nombre(o.garantie_ans);
    sortie.push({
      role,
      famille: fam && (FAMILLES_COMPARABLES as readonly string[]).includes(fam)
        ? (fam as FamilleComparable)
        : null,
      marque,
      modele,
      garantieAns: garantie !== null && garantie > 0 ? garantie : null,
    });
  }
  return sortie;
}

/** La banque batterie de CETTE taille — toujours dénommée dans le module DES
 *  LIGNES DU DEVIS (principe fondateur 26/08), homogène par construction. */
export interface OffreBatterie {
  nbModules: number;
  /** Nominal de l'étiquette — la grandeur avec laquelle le client compte. */
  moduleKwh: number | null;
  /** Capacité UTILE (règle CAPUTIL) — servie, jamais dérivée ici. */
  capaciteUtileKwh: number | null;
  /** `false` UNIQUEMENT quand le moteur l'affirme — absent/`true` ⇒ servable. */
  remplissageOk: boolean;
}

function batterie(brut: unknown): OffreBatterie | null {
  if (!brut || typeof brut !== 'object') return null;
  const o = brut as Record<string, unknown>;
  const nbModules = nombre(o.nb_modules);
  if (nbModules === null || nbModules <= 0) return null;
  return {
    nbModules,
    moduleKwh: nombre(o.module_kwh),
    capaciteUtileKwh: nombre(o.capacite_utile_kwh),
    remplissageOk: o.remplissage_ok !== false,
  };
}

/** Les familles qui APPARAISSENT / DISPARAISSENT par rapport au devis. Omis
 *  quand rien ne diffère, et JAMAIS servi sur la carte `recommande` (qui EST
 *  la référence). */
export interface OffreFamillesDiff {
  ajoutees: FamilleComparable[];
  retirees: FamilleComparable[];
}

function famillesDiff(brut: unknown): OffreFamillesDiff | null {
  if (!brut || typeof brut !== 'object') return null;
  const o = brut as Record<string, unknown>;
  const ajoutees = familles(o.ajoutees);
  const retirees = familles(o.retirees);
  if (ajoutees.length === 0 && retirees.length === 0) return null;
  return { ajoutees, retirees };
}

/** Une variante servie d'une taille : « sans batterie » ou « avec batterie ».
 *  CHAQUE champ est facultatif et sanitisé INDIVIDUELLEMENT. */
export interface OffreVariante {
  nbPanneaux: number | null;
  puissanceKwc: number | null;
  prixTtc: number | null;
  /** Le MÊME arrondi que le PDF — jamais un second arrondi côté page. */
  prixParKwcTtc: number | null;
  economieAnnuelleMad: number | null;
  paybackAnnees: number | null;
  couverturePct: number | null;
  tauxAutoconsommationPct: number | null;
  productionAnnuelleKwh: number | null;
  /** Dernier point de la courbe cumulée déjà tracée par la page. */
  economiesCumulees25AnsMad: number | null;
  batterie: OffreBatterie | null;
  materiel: OffreMateriel[];
  familles: FamilleComparable[];
  famillesDiff: OffreFamillesDiff | null;
  /** `false` UNIQUEMENT quand le moteur l'affirme (taille bornée par le toit). */
  toitOk: boolean | null;
  /**
   * #8 — ARTEFACTS PROPRES À CETTE OPTION (calepinage / schéma unifilaire),
   * servis par une lane backend PARALLÈLE qui n'a pas encore atterri.
   *
   * LECTURE STRICTEMENT DÉFENSIVE : tant que le backend ne les sert pas, ces
   * deux champs valent `null` et la page garde ses artefacts UNIQUES
   * d'aujourd'hui (le calepinage et le schéma du devis officiel) — jamais un
   * cadre vide, jamais un « bientôt disponible », jamais un dessin fabriqué
   * pour une taille qui n'a pas été étudiée.
   */
  calepinageSvg: string | null;
  schemaSvg: string | null;
}

/**
 * `null` quand la variante n'est pas servie, ou qu'elle ne porte NI nombre de
 * panneaux NI prix : une carte qui n'annonce ni taille ni prix n'explore rien,
 * on préfère l'absence à une carte vide.
 */
function variante(brut: unknown): OffreVariante | null {
  if (!brut || typeof brut !== 'object') return null;
  const o = brut as Record<string, unknown>;
  const nbPanneaux = nombre(o.nb_panneaux);
  const prixTtc = nombre(o.prix_ttc);
  if (nbPanneaux === null && prixTtc === null) return null;
  return {
    nbPanneaux,
    puissanceKwc: nombre(o.puissance_kwc),
    prixTtc,
    prixParKwcTtc: nombre(o.prix_par_kwc_ttc),
    economieAnnuelleMad: nombre(o.economie_annuelle_mad),
    paybackAnnees: nombre(o.payback_annees),
    couverturePct: nombre(o.couverture_pct),
    tauxAutoconsommationPct: nombre(o.taux_autoconsommation_pct),
    productionAnnuelleKwh: nombre(o.production_annuelle_kwh),
    economiesCumulees25AnsMad: nombre(o.economies_cumulees_25_ans_mad),
    batterie: batterie(o.batterie),
    materiel: materiel(o.materiel),
    familles: familles(o.familles),
    famillesDiff: famillesDiff(o.familles_diff),
    toitOk: typeof o.toit_ok === 'boolean' ? o.toit_ok : null,
    // Un SVG servi doit VRAIMENT en être un : une chaîne quelconque recopiée
    // dans le DOM par `set:html` serait une injection. Même garde que
    // `hasSldSvg` pour le schéma unique de la page.
    calepinageSvg: svgServi(o.calepinage_svg),
    schemaSvg: svgServi(o.schema_svg),
  };
}

/** Un SVG SERVI, et rien d'autre : la chaîne doit commencer par `<svg`. Toute
 *  autre valeur est écartée — la page garde alors son artefact d'aujourd'hui. */
function svgServi(valeur: unknown): string | null {
  const s = texte(valeur);
  return s && s.trimStart().startsWith('<svg') ? s : null;
}

/** La configuration DEMANDÉE quand le client clique « Demander cette
 *  configuration » — ce que le commercial verra dans la demande. */
export interface OffreConfig {
  nbPanneaux: number | null;
  batterieNbModules: number | null;
  batterieModuleKwh: number | null;
}

function config(brut: unknown): OffreConfig {
  if (!brut || typeof brut !== 'object') {
    return { nbPanneaux: null, batterieNbModules: null, batterieModuleKwh: null };
  }
  const o = brut as Record<string, unknown>;
  return {
    nbPanneaux: nombre(o.nb_panneaux),
    batterieNbModules: nombre(o.batterie_nb_modules),
    batterieModuleKwh: nombre(o.batterie_module_kwh),
  };
}

export interface OffreTaille {
  /** `eco` | `recommande` | `max` — la clé stable du contrat. */
  cle: string;
  /** Titre SERVI par le backend (« Éco », « Recommandé », « Max »). */
  titre: string;
  recommande: boolean;
  /** `true` ⇒ l'état affiché ÉGALE exactement le devis officiel. */
  estLeDevis: boolean;
  /** `true` ⇒ le commercial a quitté le défaut moteur sur CETTE taille. */
  ajuste: boolean;
  config: OffreConfig;
  sans: OffreVariante | null;
  avec: OffreVariante | null;
}

function taille(brut: unknown): OffreTaille | null {
  if (!brut || typeof brut !== 'object') return null;
  const o = brut as Record<string, unknown>;
  const cle = texte(o.cle);
  const titre = texte(o.titre);
  // Le titre est SERVI (noms approuvés par le fondateur) : la page n'en
  // fabrique aucun à partir de la clé technique.
  if (!cle || !titre) return null;
  const sans = variante(o.sans);
  const avec = variante(o.avec);
  if (!sans && !avec) return null;
  return {
    cle,
    titre,
    recommande: o.recommande === true,
    estLeDevis: o.est_le_devis === true,
    ajuste: o.ajuste === true,
    config: config(o.config),
    sans,
    avec,
  };
}

export interface OffresTailles {
  /** `false` ⇒ le devis ne sert pas l'option batterie : AUCUNE bascule. */
  avecServable: boolean;
  moduleBatterieKwh: number | null;
  plafondToitPanneaux: number | null;
  /** `0` ⇒ « aucune hausse tarifaire supposée » (note au-dessus du cumul). */
  escaladeTarifairePct: number | null;
  horizonAnnees: number | null;
  offres: OffreTaille[];
}

/**
 * `null` quand le backend ne sert pas la clé (devis non résidentiel, pompage,
 * sans profil de consommation, section « Économies » décochée, ou toute erreur
 * de dérivation), ou quand MOINS DE DEUX tailles en sortent : une section
 * « Explorer d'autres tailles » qui n'en montre qu'une n'explore rien. La page
 * ne rend alors AUCUNE section — jamais une section vide, jamais un chiffre de
 * remplissage.
 */
export function offresTailles(payload: unknown): OffresTailles | null {
  if (!payload || typeof payload !== 'object') return null;
  const brut = (payload as Record<string, unknown>).offres_tailles;
  if (!brut || typeof brut !== 'object') return null;
  const o = brut as Record<string, unknown>;
  const offres: OffreTaille[] = [];
  for (const item of (Array.isArray(o.offres) ? o.offres : []) as unknown[]) {
    const t = taille(item);
    if (t) offres.push(t);
  }
  if (offres.length < 2) return null;
  // HONNÊTETÉ — la bascule « Avec batterie » n'existe que si le devis SERT
  // réellement l'option ET qu'au moins une taille porte sa variante `avec`.
  const avecServable = o.avec_servable === true && offres.some((t) => t.avec !== null);
  return {
    avecServable,
    moduleBatterieKwh: nombre(o.module_batterie_kwh),
    plafondToitPanneaux: nombre(o.plafond_toit_panneaux),
    escaladeTarifairePct: nombre(o.escalade_tarifaire_pct),
    horizonAnnees: nombre(o.horizon_annees),
    offres,
  };
}

// ── Sélection & rendu ───────────────────────────────────────────────────────

/**
 * La variante à AFFICHER pour une taille, selon l'état de la bascule. Repli
 * honnête sur `sans` quand la taille ne porte pas de variante « avec » (le
 * contrat autorise une taille sans banque servable) — jamais un mélange.
 */
export function varianteAffichee(t: OffreTaille, avecBatterie: boolean): OffreVariante | null {
  return avecBatterie ? (t.avec ?? t.sans) : (t.sans ?? t.avec);
}

/** La taille sélectionnée PAR DÉFAUT : celle du devis officiel, sinon celle
 *  marquée « recommandé », sinon la première servie. Un client qui ne touche
 *  à rien lit donc exactement son devis. */
export function tailleParDefaut(bloc: OffresTailles): OffreTaille {
  return bloc.offres.find((t) => t.estLeDevis)
    ?? bloc.offres.find((t) => t.recommande)
    ?? bloc.offres[0];
}

/**
 * RÈGLE CTA (critique Fable, contrat note `cta`) — la page n'a le droit
 * d'ouvrir le lien de signature (`#signer`) QUE depuis une carte dont l'état
 * AFFICHÉ égale exactement le devis officiel :
 *   1. la taille est celle du devis (`est_le_devis`),
 *   2. elle n'a PAS été ajustée à la main (un ajustement n'est plus le devis),
 *   3. la variante affichée est celle réellement RETENUE au devis
 *      (basculer « Sans/Avec » quitte l'état officiel),
 *   4. un prix réel est bien servi (sans prix, il n'y a rien à signer).
 * Partout ailleurs — toute autre carte, toute autre variante — le SEUL CTA est
 * la demande de modification.
 */
export function peutSigner(
  t: OffreTaille,
  avecBatterie: boolean,
  varianteDuDevis: 'sans' | 'avec',
): boolean {
  if (!t.estLeDevis || t.ajuste) return false;
  if ((avecBatterie ? 'avec' : 'sans') !== varianteDuDevis) return false;
  // GARDE DE REPLI (trou défensif, corrigé le 26/08) — `varianteAffichee` se
  // rabat volontairement sur l'autre variante quand celle demandée manque, ce
  // qui est le bon comportement pour AFFICHER une carte. Ici ce serait un
  // mensonge : sur une carte « avec » incomplète, le repli aurait montré le
  // prix SANS batterie sous un bouton « aller à la signature ». On exige donc
  // que la variante demandée existe RÉELLEMENT, sans repli.
  if ((avecBatterie ? t.avec : t.sans) === null) return false;
  const v = varianteAffichee(t, avecBatterie);
  return v !== null && v.prixTtc !== null;
}

/**
 * Le message PRÉREMPLI de la demande de modification pour une taille : il dit
 * la configuration DEMANDÉE (panneaux + banque dans le module du devis), pour
 * que le commercial voie exactement ce qui a été demandé. Aucun prix n'y
 * figure : le client demande une CONFIGURATION, pas un tarif.
 */
export function messageDemandeTaille(t: OffreTaille, avecBatterie: boolean): string {
  const v = varianteAffichee(t, avecBatterie);
  const bits: string[] = [];
  const panneaux = v?.nbPanneaux ?? t.config.nbPanneaux;
  if (panneaux !== null) bits.push(`${panneaux} panneaux`);
  if (v?.puissanceKwc != null) bits.push(`${v.puissanceKwc} kWc`);
  if (avecBatterie && v?.batterie) {
    const module = v.batterie.moduleKwh;
    bits.push(module != null
      ? `${v.batterie.nbModules} × ${module} kWh de batterie`
      : `${v.batterie.nbModules} batteries`);
  } else if (!avecBatterie) {
    bits.push('sans batterie');
  }
  const detail = bits.length > 0 ? ` (${bits.join(' · ')})` : '';
  return `Je souhaite la taille « ${t.titre} »${detail}`;
}

/** Une ligne du tableau « ce qui change » : un libellé, puis une cellule par
 *  taille (chaîne VIDE quand cette taille ne porte pas la valeur — jamais un
 *  tiret présenté comme une donnée). */
export interface LigneComparaison {
  cle: string;
  cellules: string[];
}

/**
 * Le tableau « ce qui change » sous les cartes. Construit UNIQUEMENT à partir
 * des familles servies (`familles` / `familles_diff`), donc anticopie-safe :
 * jamais un calibre, jamais une quantité de nomenclature.
 *
 * Une ligne dont AUCUNE taille ne porte de valeur est OMISE (une ligne vide
 * n'apprend rien). La colonne de la taille du devis porte la chaîne vide sur
 * la ligne « matériel » : elle EST la référence, le libellé est rendu par la
 * page en i18n, jamais par ce module.
 */
export function famillesDiffParTaille(
  bloc: OffresTailles,
  avecBatterie: boolean,
): Array<{ cle: string; ajoutees: FamilleComparable[]; retirees: FamilleComparable[] }> {
  return bloc.offres.map((t) => {
    const diff = varianteAffichee(t, avecBatterie)?.famillesDiff ?? null;
    return {
      cle: t.cle,
      ajoutees: diff?.ajoutees ?? [],
      retirees: diff?.retirees ?? [],
    };
  });
}

/** `true` dès qu'AU MOINS une taille porte une différence de familles à
 *  montrer — sinon la ligne « matériel » du tableau est omise. */
export function aUneDiffMateriel(bloc: OffresTailles, avecBatterie: boolean): boolean {
  return famillesDiffParTaille(bloc, avecBatterie)
    .some((d) => d.ajoutees.length > 0 || d.retirees.length > 0);
}

// ── Cumul 25 ans — année par année, depuis la série DÉJÀ servie ─────────────

/**
 * La courbe cumulée 25 ans que la page trace déjà (`quote.cashflow_sans` /
 * `quote.cashflow_avec`, publiées par `quote_engine.pricing`). Chaque entrée
 * est la trésorerie nette CUMULÉE de l'année, servie telle quelle.
 *
 * `[]` quand la série n'est pas servie ou n'est pas une liste de nombres finis
 * — le tableau année-par-année n'est alors pas rendu du tout. AUCUN calcul
 * ici : la page se contente de FORMATER l'année et sa valeur servie.
 */
export interface AnneeCumulee {
  /** 1..N — la série servie commence à l'année 1 (l'année 0 vaut −prix). */
  annee: number;
  cumuleMad: number;
}

export function cumulAnnuelServi(
  payload: unknown,
  avecBatterie: boolean,
): AnneeCumulee[] {
  if (!payload || typeof payload !== 'object') return [];
  const quote = (payload as Record<string, unknown>).quote;
  if (!quote || typeof quote !== 'object') return [];
  const brut = (quote as Record<string, unknown>)[avecBatterie ? 'cashflow_avec' : 'cashflow_sans'];
  if (!Array.isArray(brut) || brut.length === 0) return [];
  const sortie: AnneeCumulee[] = [];
  for (let i = 0; i < brut.length; i += 1) {
    const v = nombre(brut[i]);
    // Une série trouée n'est pas une série : on s'arrête au premier point
    // illisible plutôt que d'inventer la continuité.
    if (v === null) break;
    sortie.push({ annee: i + 1, cumuleMad: v });
  }
  return sortie;
}
