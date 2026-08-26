/**
 * W116 / W117 — Logique PURE de la proposition client en ligne.
 *
 * La page /proposition/[token] et le proxy /api/proposition-accept appellent
 * UNIQUEMENT des fonctions de ce module pour tout ce qui n'est pas du DOM :
 * formatage monétaire, choix d'option, mise en forme de la requête d'acceptation,
 * décision « quel état afficher ». Tout est testé sous vitest (aucun DOM, aucun
 * réseau) — les fonctions sont volontairement déterministes et sans effet de bord.
 *
 * Le navigateur du client n'appelle JAMAIS le backend en direct : la page lit la
 * proposition côté serveur (frontmatter Astro), et la signature passe par le
 * proxy same-origin. Le backend ne renvoie jamais de prix d'achat / marge — on ne
 * lit donc que les champs publics du contrat vérifié.
 */

// L-PCMP — import de TYPE uniquement (effacé à la compilation) : ce module
// reste sans aucune dépendance à l'exécution, mais les silhouettes
// d'occupation gardent UNE seule définition (`lib/dayProfiles.ts`).
import type { OccupancyId, SeasonId, ServedProduction } from './dayProfiles';
// L-DEUXOPT (25/08/2026) — lecture de `production_par_option` : réutilise
// STRICTEMENT le même validateur que `courbes_journalieres.production`
// (aucune seconde définition de « forme 24 h valide »).
import { parseServedProductionEntry, parseServedProductionMap } from './dayProfiles';

/** Une ligne d'équipement telle que renvoyée par le backend (champs publics). */
export interface ProposalItem {
  designation: string;
  quantite: number;
  prix_unit_ht: number;
  prix_unit_ttc: number;
  remise: number;
  marque: string;
  /**
   * WJ32 — texte de description du produit (fiche commerciale). Backend
   * `_line_to_item` l'expose déjà (`description`) ; optionnel — un produit
   * historique sans fiche renvoie une chaîne vide, jamais inventée.
   */
  description?: string;
  /**
   * WJ32 — texte de garantie constructeur/performance du produit. Backend
   * `_line_to_item` l'expose déjà (`garantie`) ; vide quand non renseigné.
   */
  garantie?: string;
  taux_tva: number;
}

/** Un palier de TVA agrégé (taux → montant). */
export interface TvaParTaux {
  taux: number;
  base?: number;
  montant: number;
}

/** Le bloc de totaux d'une option (sans ou avec batterie). */
export interface ProposalTotaux {
  ht_brut: number;
  remise: number;
  ht_net: number;
  tva: number;
  tva_par_taux?: TvaParTaux[];
  ttc: number;
}

/** Le devis complet (sous-objet `quote` du contrat). */
export interface ProposalQuote {
  ref: string;
  date: string;
  client_name: string;
  client_addr?: string;
  client_phone?: string;
  inst_type?: string;
  /**
   * WJ126/QX49 — clé machine MINUSCULE du mode d'installation
   * (`residentiel|industriel|commercial|agricole`, cf. `Devis.ModeInstallation`
   * backend). Le builder la pose AUSSI ici (dans `data`, donc dans `quote`) en
   * plus du niveau racine du payload. C'est le champ sur lequel la page branche
   * ses 4 variantes — jamais l'ancien `inst_type` (libellé capitalisé qui ne
   * matchait aucun littéral minuscule, bug historique). Absent → résidentiel.
   */
  mode_installation?: string | null;
  puissance_kwc?: number;
  nb_panneaux?: number;
  watt_par_panneau?: number;
  prod_kwh?: number;
  total_sans?: number;
  total_avec?: number;
  eco_s_ann?: number;
  eco_a_ann?: number;
  /** Économie cumulée sur la durée (champ backend `eco_a_cumul`, MAD). */
  eco_a_cumul?: number;
  roi_s?: number | string;
  roi_a?: number | string;
  /** Date limite de validité (peut aussi voyager au niveau racine du contrat). */
  date_validite?: string | null;
  scenario?: string;
  recommended?: OptionKey | string;
  sans_items?: ProposalItem[];
  avec_items?: ProposalItem[];
  totaux_sans?: ProposalTotaux;
  totaux_avec?: ProposalTotaux;
  display_total?: number;
  nb_options?: number;
  roof_image_key?: string;
  /** Factures mensuelles (MAD) du client si le backend les expose — sert
   *  uniquement à l'accroche « < votre facture actuelle » (WJ10). Optionnel :
   *  absent → l'accroche comparative est masquée, jamais inventée. */
  factures_mensuelles?: number[] | null;
  etude?: Record<string, unknown>;
}

/** Totaux d'options agrégés au niveau racine du contrat. */
export interface OptionTotals {
  sans_batterie: number;
  avec_batterie: number;
  display_total: number;
  nb_options: number;
}

/** Réponse complète de GET /api/django/ventes/proposal/<token>/. */
export interface ProposalResponse {
  reference: string;
  date: string;
  client_name: string;
  statut: string;
  quote: ProposalQuote;
  /**
   * L-INTPREV / LANE T-WEB (25/08/2026) — `true` UNIQUEMENT quand CE GET a
   * résolu le jeton d'APERÇU INTERNE (le commercial relit sa proposition
   * depuis l'ERP), cf. `public_views._resolve_share_link_by_token` +
   * `_resolve_proposal_link`. Payload par ailleurs IDENTIQUE au jeton
   * public : la page s'en sert seulement pour un bandeau discret, désactiver
   * la signature et les demandes de contact, et couper toute
   * balise/beacon (elle ne doit jamais engager le client ni compter une
   * visite CLIENT depuis un aperçu commercial). Absent/faux → rendu
   * strictement inchangé.
   */
  apercu_interne?: boolean | null;
  /**
   * WJ126/QX49 — mode d'installation (clé machine MINUSCULE, cf.
   * `Devis.ModeInstallation`) exposé au NIVEAU RACINE du payload par
   * `proposal_data`. C'est la source de vérité de la variante à rendre —
   * `resolveInstallMode` la lit ici en priorité (repli `quote.mode_installation`,
   * puis résidentiel). Jamais l'ancien `inst_type`. Absent/vide → résidentiel.
   */
  mode_installation?: string | null;
  /**
   * WJ126/QX49 — catégorie commerciale (`hotel|restaurant|commerce|bureau|
   * sante|ecole|hammam|boulangerie|froid|autre`, cf. quote_engine/commercial/
   * categories.py). Présente uniquement en mode commercial ; `null` sinon. Sert
   * à choisir l'archétype de bloc commercial (`commercialArchetype`).
   */
  categorie_commerciale?: string | null;
  /**
   * WJ126/QX49 — bloc KPI par mode, whitelist STRICTE côté serveur (jamais
   * prix_achat/marge — RULE #4). Forme selon le mode : `AgricoleKpis` (pompage)
   * ou `AutoconsoKpis` (industriel/commercial) ; `null` en résidentiel (ou hors
   * mode géré). La page ne re-calcule rien : `agricoleKpis`/`autoconsoKpis`
   * l'extraient typé, chaque champ absent devenant `null` (jamais fabriqué).
   */
  mode_kpis?: ProposalModeKpis | null;
  roof_image_url: string | null;
  /**
   * PVUNI (fondateur 2026-08-18) — LE CALEPINAGE 3D NE COLLE PLUS AUX LIGNES.
   *
   * La vue 3D montre le calepinage tel qu'il a été JOUÉ ; les lignes du devis,
   * elles, peuvent avoir bougé depuis (une quantité corrigée à la main, une
   * seconde marque ajoutée) sans que personne ne rejoue la 3D. Le serveur
   * compare les deux comptes et pose ce drapeau : la page ne recalcule RIEN,
   * elle se contente de le dire honnêtement sous la vue.
   *
   * `false`/absent = les deux concordent, ou le devis n'a pas de calepinage :
   * rendu strictement inchangé. `layout_nb_panneaux` porte le compte pour
   * lequel la 3D a été étudiée (celui des lignes reste `quote.nb_panneaux`).
   */
  layout_stale?: boolean | null;
  layout_nb_panneaux?: number | null;
  /**
   * Production solaire estimée, kWh/mois (12 valeurs, index 0 = janvier). Peut
   * être absent ou `[]` — le graphe se masque alors gracieusement (P2).
   */
  monthly_production?: number[];
  /**
   * Consommation électrique du client, kWh/mois (12 valeurs). Peut être absent
   * ou `[]` — la comparaison se réduit alors à la production seule (P2).
   */
  monthly_consumption?: number[];
  /**
   * PVCOV (fondateur 2026-08-18) — LA SYNTHÈSE DE LA PAGE 1 DU PDF, SERVIE.
   *
   * Ces cinq champs sortent de `quote_engine/residential/renderer.
   * synthese_economies` — LA MÊME fonction qui alimente la page 1 du devis PDF.
   * Le lien client et le PDF lisent donc littéralement les mêmes nombres : ils
   * ne PEUVENT plus diverger, et une correction du moteur se propage ici sans
   * qu'une ligne de cette page bouge.
   *
   *  · `pct_cut` — réduction de facture en % (le « −N % »).
   *  · `annual_before` / `annual_after` — facture ANNUELLE (MAD/an) avant et
   *    après solaire.
   *  · `coverage_pct` — couverture solaire en % (la donut « ÉNERGIE SOLAIRE »),
   *    déjà bornée 1..100 côté moteur : 100 % signifie production ≥ consommation.
   *  · `coverage_estimated` — vrai quand la consommation n'est pas mesurée mais
   *    dérivée de la facture : la page l'écrit « (estimation) », jamais en creux.
   *
   * TOUS `null` quand le devis n'a pas la forme résidentielle attendue — la page
   * masque alors le bloc entier plutôt que d'inventer un chiffre.
   */
  pct_cut?: number | null;
  annual_before?: number | null;
  annual_after?: number | null;
  coverage_pct?: number | null;
  coverage_estimated?: boolean | null;
  option_totals: OptionTotals;
  /**
   * L-VAR (ordre fondateur, 24/08/2026) — LES CÔTÉS QUE L'ÉQUIPEMENT SERT.
   *
   * Liste ordonnée, sous-ensemble de `['sans','avec']` : ce que le matériel du
   * devis peut PHYSIQUEMENT livrer, indépendamment du nombre d'options que le
   * document PRÉSENTE (`option_totals.nb_options`, qui ne commande plus que la
   * signature). Absente ⇒ backend antérieur au contrat : `variantesServables`
   * retombe sur le signal historique et la page ne bouge pas d'un pixel.
   */
  variantes_servables?: string[] | null;
  accepted: boolean;
  accepte_par_nom?: string | null;
  date_acceptation?: string | null;
  /**
   * Date limite de validité du devis (échéance d'offre). Le backend PEUT
   * l'exposer (champ `Devis.date_validite`, format ISO `YYYY-MM-DD` ou FR
   * `JJ/MM/AAAA`). Absent → la page affiche une fenêtre de validité « par
   * défaut » clairement libellée (jamais un compte-à-rebours qui se réinitialise).
   * Le champ peut aussi voyager dans `quote.date_validite`.
   */
  date_validite?: string | null;
  /**
   * WJ25 — layout de toiture OPTIONNEL (backend PLAN2 QJ26, pas encore exposé
   * aujourd'hui : le champ est absent → la page garde le héros statique). Quand
   * il arrive, sa forme est celle de `serializeLayout` du builder
   * (roofPro11/prefill.ts) : { version, pin, outline, billKwh, zones[],
   * activeAreaId }. On le lit défensivement via `parseRoofLayout` — jamais
   * directement.
   */
  roof_layout?: unknown;
  /**
   * WJ128 — schéma unifilaire (SLD) OPTIONNEL, déjà rendu en SVG CLIENT-SAFE
   * côté serveur (aucun prix d'achat/marge, aucune donnée interne — le
   * backend ne l'expose que quand l'étude électrique du devis existe).
   * `null`/absent → la section « Schéma électrique » ne rend RIEN (le PDF
   * téléchargeable, quand l'étude existe, embarque déjà le schéma — flux
   * INCHANGÉ, voir CLAUDE.md règle #4). Lu défensivement via `hasSldSvg`.
   */
  sld_svg?: string | null;
  /**
   * 2026-08-18 — DÉTAIL ÉLECTRIQUE public (chaînes, protections nominatives,
   * câbles), whitelist STRICTE côté serveur
   * (`public_views._conception_electrique_publique`) : jamais la nomenclature
   * d'achat, jamais les paramètres de calcul, jamais un montant. `null`/absent
   * tant que l'étude électrique n'existe pas — aucun dépliant ne s'affiche
   * alors. Typé `unknown` À DESSEIN : il n'entre dans la page qu'à travers
   * `parseConceptionElectrique`, qui valide et OMET toute valeur absente.
   */
  conception_electrique?: unknown;
  /**
   * L-NIV-VU (24/08/2026) — CE QUE LE NIVEAU « standard » MASQUE RÉELLEMENT
   * SUR CETTE PAGE-CI, constaté serveur sur la charge utile déjà dégradée
   * (`public_views._niveau_masque`) : `'nomenclature_kit'` (les lignes
   * fixation/câblage/protection ont fusionné en une ligne « kit ») et/ou
   * `'dimensionnement_electrique'` (calibres, sections et longueurs de câble
   * retirés du schéma et du détail électrique).
   *
   * Liste VIDE ou absente ⇒ la page n'annonce RIEN : au niveau « confiance »,
   * bien sûr, mais AUSSI au niveau « standard » sur un devis où il n'y avait
   * rien à masquer (moins de deux lignes kit, pas de conception électrique).
   * Annoncer « version simplifiée » là serait un fait inventé — règle
   * fondateur « zéro chiffre/fait inventé ».
   *
   * Les marques et modèles, eux, restent TOUJOURS affichés aux deux niveaux
   * (décision fondateur 24/08/2026) : ils ne figurent jamais dans cette liste.
   */
  niveau_masque?: string[] | null;
  /**
   * WJ32 — bloc de financement backend (QJ12, `compute_financing_block`),
   * DIFFÉRENT du calcul générique `financingComparison` ci-dessus : porte un
   * programme réel (Tatwir Croissance Verte / ISTIDAMA…) et une comparaison
   * ONEE déjà rédigée côté serveur. Absent quand `display_total` est
   * indisponible — le bloc financement se masque alors (jamais un calcul de
   * repli qui divergerait du backend).
   */
  financing?: ProposalFinancingBlock | null;
  /**
   * WJ32 — résumés « autres tailles » des variantes actives du même devis
   * (QJ15, `_variant_summaries`). Tableau vide quand le devis est isolé
   * (aucun frère/sœur actif) — la strip « autres tailles » se masque alors.
   */
  variants?: ProposalVariantSummary[];
  /**
   * GAMMES — choix de gamme (deux devis frères). Clé ABSENTE quand le vendeur
   * a envoyé une gamme seule, ou quand le devis n'appartient à aucune paire :
   * la page rend alors strictement ce qu'elle rend aujourd'hui.
   */
  gammes?: ProposalGammes | null;
  /**
   * COUTURE BACKEND (clé convenue, 2026-08-18) — RESYNCHRONISATION APRÈS ENVOI.
   * Le backend ajoute cette clé quand un devis DÉJÀ ENVOYÉ a été resynchronisé
   * après coup (prix catalogue corrigé côté Stock) : la page est re-rendue en
   * direct depuis les lignes, elle peut donc afficher un total qui ne
   * correspond plus au PDF que le client a reçu en pièce jointe. On le DIT en
   * une ligne discrète près du total, au lieu de laisser l'écart se découvrir à
   * la signature. Clé ABSENTE — le cas normal — ⇒ rien n'est rendu, la page ne
   * bouge pas d'un pixel. Lue défensivement par `resyncApresEnvoi` : une date
   * illisible n'affiche rien plutôt qu'une date inventée.
   */
  resync_apres_envoi?: { date?: string | null } | null;
  /**
   * WJ114 — bloc vendeur OPTIONNEL (note personnelle + identité), pas encore
   * exposé par le backend aujourd'hui : lu défensivement (`sellerNote` ci-
   * dessous) pour qu'il s'allume dès que l'ERP le fournira, sans crash ni
   * placeholder en attendant. Aucun de ces trois champs n'est requis
   * ensemble — `sellerNote` ne renvoie que ceux réellement fournis.
   */
  seller?: {
    /** Courte note personnalisée rédigée par le vendeur pour ce client. */
    note?: string | null;
    /** Nom du vendeur/conseiller. */
    name?: string | null;
    /** URL de la photo du vendeur. */
    photo_url?: string | null;
  } | null;
  /**
   * L-PROP CJ2b-bis (lot 4, 24/08) — sous-ensemble PUBLIC, client-safe, du
   * bloc « falaise » du moteur horaire interne (`dimensionnement.falaise` /
   * `meilleure_falaise` — voir `frontend/src/features/ventes/
   * etudeHorairePreviewPur.js falaiseAffichable`, même lot). Le pitch : le
   * dimensionnement retenu atterrit franchement SOUS le palier tarifaire
   * suivant. [HANDOFF public payload] — clé pas encore servie par
   * `apps/ventes/public_views.py` au moment de cette lane ; forme CONVENUE
   * avec la lane backend du même lot. `null`/absent ⇒ bloc entier masqué,
   * jamais un chiffre recalculé côté web (zéro chiffre inventé, CLAUDE.md).
   */
  tranche_tarifaire?: {
    tranche_actuelle?: { libelle?: string | null } | null;
    tranche_visee?: { libelle?: string | null } | null;
    cible_kwh_mois?: number | null;
    residuel_kwh_mois?: number | null;
  } | null;
  /**
   * L-PROP CJ2b-bis — remplissage batterie moyen + couverture des « glitchs »
   * (part des pointes d'équipements que la batterie rattrape), sous-ensemble
   * public des blocs internes `remplissage`/`etude.glitch.annuel` (même lot).
   * [HANDOFF public payload] — même statut que `tranche_tarifaire` ci-dessus.
   */
  batterie_regime?: {
    remplissage_moyen_pct?: number | null;
    couverture_glitch_pct?: number | null;
  } | null;
  /**
   * ORDRE FONDATEUR (24/08/2026, soir) — le mini-balayage de stockage
   * (`apps.ventes.dimensionnement` DIM2), sous-ensemble public : les paliers
   * de capacité RETENUS pour la taille recommandée (batterie « toujours
   * pleine ») + le premier palier REFUSÉ (celui qui ne se rechargerait plus
   * chaque jour). Alimente le sélecteur « N packs » de la page publique —
   * jamais un prix/pourcentage inventé, uniquement ceux déjà calculés par le
   * moteur (`apps/ventes/public_views.py _balayage_stockage_publique`).
   */
  balayage_stockage?: {
    paliers?: Array<{
      nb_packs?: number | null;
      capacite_kwh?: number | null;
      cout_ttc?: number | null;
      remplissage_moyen_pct?: number | null;
      // ORDRE FONDATEUR (24/08/2026) — période de retour et économie annuelle
      // DU PALIER, calculées par le moteur (`dimensionnement._palier_rendu` :
      // `payback_annees` = coût TTC ÷ économie annuelle du palier) et servies
      // telles quelles. Absentes ⇒ la page n'affiche AUCUN payback pour ce
      // palier (jamais une valeur approchée, jamais un calcul en JS).
      payback_annees?: number | null;
      economie_mad?: number | null;
    }> | null;
    refuse?: {
      nb_packs?: number | null;
      capacite_kwh?: number | null;
      remplissage_pire_mois_pct?: number | null;
    } | null;
  } | null;
  /**
   * P2-C (ordre fondateur 25/08/2026, soir — « add more than just 2
   * batteries in the web page battery option ; extra batteries might add
   * extra panels with extra cost, that is still fine ») — PALIERS DE
   * CAPACITÉ BATTERIE du sélecteur public sur la carte « Avec batterie »
   * (section #options), CONTRAT PROPRE distinct de `balayage_stockage`
   * ci-dessus (qui alimente le simulateur à curseur plus bas sur la page —
   * deux fonctionnalités différentes, jamais fusionnées). Chaque palier peut
   * porter un nombre de PANNEAUX DIFFÉRENT — une capacité plus grosse peut
   * avoir besoin de plus de solaire pour se remplir chaque jour, voulu par
   * le fondateur. `retenu=true` marque le palier du devis RÉEL (ses chiffres
   * restent ceux du document officiel, jamais recalculés côté web) ;
   * `remplissage_ok=false` marque un palier où la batterie ne se remplirait
   * pas tous les jours (pilule affichée désactivée). Chaque champ est
   * sanitisé INDIVIDUELLEMENT (`paliersBatterie` plus bas) — `null`/absent ⇒
   * omis à l'écran, jamais un défaut fabriqué. Clé absente ou liste vide ⇒
   * le sélecteur ne rend RIEN, pixel identique à l'existant.
   */
  paliers_batterie?: Array<{
    capacite_kwh?: number | null;
    nb_batteries_5?: number | null;
    nb_batteries_10?: number | null;
    nb_panneaux?: number | null;
    puissance_kwc?: number | null;
    prix_ttc?: number | null;
    economies_annuelles?: number | null;
    payback_annees?: number | null;
    remplissage_ok?: boolean | null;
    retenu?: boolean | null;
  }> | null;
  /**
   * L-PROP CJ2b-bis — décomposition mensuelle de l'estimation de
   * consommation, MÊME CONTRAT que le moteur horaire interne
   * (`estimation_conso: { base_mensuelle:[12], ajouts:{...},
   * totale_mensuelle:[12] }` — voir `estimationConsoAffichable` côté CRM,
   * même lot 4). [HANDOFF public payload] — même statut ci-dessus.
   */
  estimation_conso?: {
    base_mensuelle?: number[];
    ajouts?: Record<string, number[]>;
    totale_mensuelle?: number[];
  } | null;
  /**
   * L-PROP TASK2 — « Une journée type » (production PV vs consommation, jour
   * moyen des 4 mois janvier/avril/juillet/novembre), MÊME FORME que
   * `apps/web/src/lib/jourTypeData.ts` (tunnel `/devis/mon-toit`) mais servie
   * PAR DEVIS ici plutôt qu'un jeu de données générique. Clé objet indexée par
   * mois (« 1 »/« 4 »/« 7 »/« 11 » en chaîne) → { prod_kw[24], conso_kw[24],
   * conso_jour_kwh, prod_jour_kwh, autoconsomme_kwh, surplus_kwh }.
   * [HANDOFF public payload] — clé pas encore servie par `public_views.py` au
   * moment de cette lane ; voir `apps.ventes.etude_horaire.jours_types_annee`
   * côté backend pour la calculer. `null`/absent ⇒ section masquée entière.
   */
  jours_types?: Record<string, {
    prod_kw?: unknown;
    conso_kw?: unknown;
    conso_jour_kwh?: unknown;
    prod_jour_kwh?: unknown;
    autoconsomme_kwh?: unknown;
    surplus_kwh?: unknown;
  }> | null;
  /**
   * COUVBAT (ordre fondateur, 26/08/2026) — CE QUE LE CURSEUR « N BATTERIES »
   * DOIT MONTRER : pour chaque cran, la part de la consommation du client
   * réellement COUVERTE (solaire direct + batterie), heure par heure sur les
   * quatre jours types publics ET sur l'année ; plus le nombre de batteries
   * d'une AUTONOMIE COMPLÈTE (jour + nuit).
   *
   * CONTRAT PARTAGÉ (PACT10) :
   * `backend/django_core/apps/ventes/contract_samples/couverture_batterie.json`
   * — c'est CE fichier que les deux moitiés lisent, pas cette interface.
   *
   * La page N'EN CALCULE AUCUN CHIFFRE : elle LIT. Ces courbes viennent du
   * moteur horaire (mêmes douze jours types et même simulateur de batterie que
   * l'étude complète), là où la page rejouait avant un moteur approché sur une
   * silhouette générique. Clé absente ⇒ la page retombe EXACTEMENT sur son
   * comportement d'avant (simulateur client `lib/batterySim`).
   */
  couverture_batterie?: {
    capacite_utile_pack_kwh?: unknown;
    rendement?: unknown;
    conso_annuelle_kwh?: unknown;
    mois_jours_types?: unknown;
    nb_packs_max?: unknown;
    pas?: unknown;
    autonomie_complete?: unknown;
  } | null;
  /**
   * L-PCMP (fondateur, 24/08/2026) — les TROIS silhouettes d'occupation
   * calculées par le moteur sur les MÊMES factures réelles du client, plus
   * l'installation OPTIMALE que le balayage retient pour chacune.
   *
   * CONTRAT PARTAGÉ (PACT10) :
   * `backend/django_core/apps/ventes/contract_samples/profils_comparatifs.json`
   * — c'est CE fichier que les deux moitiés lisent, pas cette interface.
   *
   * La page N'EN CALCULE AUCUN CHIFFRE : elle bascule d'affichage entre les
   * trois blocs SERVIS. Les taux arrivent déjà en POURCENTAGE, les économies
   * en MAD/an entiers. Clé absente / `null` ⇒ section masquée entière.
   */
  profils_comparatifs?: {
    profil_reel?: string | null;
    kwc_devis?: number | null;
    batterie_kwh_devis?: number | null;
    avec_batterie?: boolean | null;
    devise?: string | null;
    note?: string | null;
    profils?: Array<{
      occupation?: string | null;
      est_profil_reel?: boolean | null;
      economie_sans_mad?: number | null;
      economie_avec_mad?: number | null;
      taux_autoconso_sans_pct?: number | null;
      taux_autoconso_avec_pct?: number | null;
      couverture_sans_pct?: number | null;
      couverture_avec_pct?: number | null;
      optimal?: {
        kwc?: number | null;
        panneaux?: number | null;
        batterie_kwh?: number | null;
        avec_batterie?: boolean | null;
        economie_mad?: number | null;
        identique_au_devis?: boolean | null;
      } | null;
    }> | null;
  } | null;
  /**
   * L-DEUXOPT (lane « deux optimiseurs », 25/08/2026) — DEUX DIMENSIONNEMENTS
   * PHYSIQUEMENT DIFFÉRENTS quand ajouter une batterie change le calcul
   * optimal du nombre de panneaux (ex. 22 panneaux sans batterie / 26 avec).
   * [HANDOFF public payload] — forme CONVENUE avec la lane backend du même
   * lot. `divergent` EXPLICITE (jamais déduit d'une différence de nombres qui
   * pourrait n'être qu'un arrondi) : `true` ⇒ les deux côtés ci-dessous
   * décrivent CHACUN son propre système ; `false`/absent ⇒ la page ne bouge
   * pas d'un pixel (cas historique, un seul dimensionnement pour les deux
   * options). Chaque champ de `sans`/`avec` peut être `null` individuellement
   * — omis à l'écran, jamais un défaut fabriqué (règle fondateur « zéro
   * chiffre inventé »).
   */
  dimensionnement_options?: {
    sans?: {
      nb_panneaux?: number | null;
      puissance_kwc?: number | null;
      nb_batteries?: number | null;
      capacite_batterie_kwh?: number | null;
      production_annuelle_kwh?: number | null;
    } | null;
    avec?: {
      nb_panneaux?: number | null;
      puissance_kwc?: number | null;
      nb_batteries?: number | null;
      capacite_batterie_kwh?: number | null;
      production_annuelle_kwh?: number | null;
    } | null;
    divergent?: boolean | null;
  } | null;
  /**
   * L-DEUXOPT — série de production PROPRE À CHAQUE option, MÊME FORME que le
   * bloc `courbes_journalieres.production` (voir `dayProfiles.ts`
   * `ServedProduction`, par saison) — soit une carte par saison, soit une
   * entrée UNIQUE (repli, un seul « jour type » pour ce côté). Sert à rejouer
   * le simulateur batterie sur la production RÉELLE de l'option « avec »
   * (plus de panneaux ⇒ courbe différente) au lieu du repli générique.
   * Typé `unknown` À DESSEIN : n'entre dans la page qu'à travers
   * `productionSeriesForOption`, qui valide et renvoie `null` sur tout ce qui
   * n'est pas exploitable — jamais un chiffre inventé. `null`/absent par côté
   * ⇒ le simulateur garde son repli historique pour ce côté.
   */
  production_par_option?: {
    sans?: unknown;
    avec?: unknown;
  } | null;
}

/** L-DEUXOPT — dimensionnement RÉEL d'une option, sanitisé champ par champ. */
export interface DimensionnementOption {
  nbPanneaux: number | null;
  puissanceKwc: number | null;
  nbBatteries: number | null;
  capaciteBatterieKwh: number | null;
  productionAnnuelleKwh: number | null;
}

// `finiteOrNull` est déjà défini plus bas dans ce module (bloc falaise
// tarifaire/CJ2b-bis) : function declaration → hoisté, réutilisable ici sans
// seconde définition (TypeScript refuserait la redéclaration).

/**
 * L-DEUXOPT — dimensionnement RÉEL d'UNE option (`'sans'`/`'avec'`, l'écriture
 * du contrat backend — voir `VarianteServable`), sanitisé champ par champ :
 * toute valeur non numérique finie devient `null` — jamais un défaut fabriqué.
 * `null` global quand le bloc entier ou cette option est absent.
 */
export function dimensionnementOption(
  p: Pick<ProposalResponse, 'dimensionnement_options'>,
  opt: VarianteServable,
): DimensionnementOption | null {
  const raw = p?.dimensionnement_options?.[opt];
  if (!raw || typeof raw !== 'object') return null;
  return {
    nbPanneaux: finiteOrNull(raw.nb_panneaux),
    puissanceKwc: finiteOrNull(raw.puissance_kwc),
    nbBatteries: finiteOrNull(raw.nb_batteries),
    capaciteBatterieKwh: finiteOrNull(raw.capacite_batterie_kwh),
    productionAnnuelleKwh: finiteOrNull(raw.production_annuelle_kwh),
  };
}

/**
 * Vrai UNIQUEMENT quand le backend affirme EXPLICITEMENT une divergence de
 * dimensionnement entre les deux options. Absent/`false` ⇒ la page rend
 * exactement ce qu'elle rendait avant ce lot (aucun des blocs
 * `dimensionnementOption`/`productionSeriesForOption` n'est censé être
 * consulté par la page dans ce cas — c'est cette fonction qui le garde).
 */
export function dimensionnementDivergent(
  p: Pick<ProposalResponse, 'dimensionnement_options'>,
): boolean {
  return p?.dimensionnement_options?.divergent === true;
}

/**
 * L-DEUXOPT — série de production propre à UNE option (`'sans'`/`'avec'`),
 * MÊME FORME que `courbes_journalieres.production` (voir dayProfiles.ts,
 * `ServedProduction`) : soit une entrée UNIQUE servie à la racine (repli le
 * plus simple, un seul « jour type » pour ce côté), soit une carte par
 * saison — dans ce cas `season` sélectionne l'entrée à utiliser (même saison
 * que celle affichée par la courbe journalière). `null` quand rien
 * d'exploitable n'est servi pour ce côté ou cette saison — le simulateur
 * batterie garde alors son repli historique.
 */
export function productionSeriesForOption(
  p: Pick<ProposalResponse, 'production_par_option'>,
  opt: VarianteServable,
  season: SeasonId | null,
): ServedProduction | null {
  const raw = p?.production_par_option?.[opt];
  if (raw === null || raw === undefined) return null;
  const flat = parseServedProductionEntry(raw);
  if (flat) return flat;
  if (season) {
    const bySeason = parseServedProductionMap(raw);
    if (bySeason[season]) return bySeason[season] as ServedProduction;
  }
  return null;
}

/** WJ32 — bloc `financing` backend (QJ12), structure de `compute_financing_block`. */
export interface ProposalFinancingBlock {
  indicatif: true;
  cash: { montant_ttc: number; label: string };
  credit: {
    mensualite: number;
    duree_mois: number;
    taux_annuel_pct: number;
    programme_nom: string;
    programme_label: string | null;
  };
  onee_comparison: {
    show: boolean;
    message: string;
    eco_mensuelle_sans: number;
    eco_mensuelle_avec: number;
  };
  guidance_text: string | null;
}

/** WJ32 — un résumé de variante (QJ15 `_variant_summaries`), pour la strip « autres tailles ». */
export interface ProposalVariantSummary {
  id: number;
  reference: string;
  version: number;
  note: string;
  total_ttc: number;
}

export type OptionKey = 'sans_batterie' | 'avec_batterie';

/**
 * GAMMES (fondateur 2026-08-18) — offre à DEUX GAMMES paramétrable.
 *
 * Une gamme est un devis frère COMPLET (composition et prix propres) : le lien
 * client rend TOUJOURS le devis de son jeton, et n'expose la gamme sœur que
 * lorsque le vendeur a choisi d'envoyer LES DEUX. Le libellé est une DONNÉE
 * (aucune marque codée en dur). Ce bloc est indépendant de l'axe
 * « avec / sans batterie » (`OptionKey`), qui reste INTERNE à chaque gamme.
 */
export interface ProposalGammeCard {
  nom: string;
  recommandee: boolean;
  reference: string;
  total_ttc: number | null;
}

export interface ProposalGammeSoeur extends ProposalGammeCard {
  /** Lien PUBLIC de la gamme sœur : son document complet ET son PDF. */
  proposition_path: string;
  /** Écart TTC de la sœur PAR RAPPORT à la gamme affichée, en MAD signés. */
  ecart_ttc: number | null;
}

export interface ProposalGammeComparatifRow {
  designation: string;
  quantite?: number | null;
  quantite_soeur?: number | null;
}

export interface ProposalGammes {
  envoi: 'les_deux';
  courante: ProposalGammeCard;
  soeur: ProposalGammeSoeur;
  comparatif: ProposalGammeComparatifRow[];
}

/**
 * Bloc de choix de gamme, ou `null` — le backend n'envoie la clé qu'en mode
 * d'envoi « les_deux » ; en mode « seule » rien de la sœur ne franchit la
 * frontière publique, donc la page rend le devis comme aujourd'hui.
 */
export function proposalGammes(
  p: { gammes?: ProposalGammes | null },
): ProposalGammes | null {
  const g = p.gammes;
  if (!g || typeof g !== 'object') return null;
  if (g.envoi !== 'les_deux') return null;
  if (!g.courante?.nom || !g.soeur?.nom || !g.soeur?.proposition_path) return null;
  return g;
}

/**
 * Écart de prix en MAD ABSOLUS, signé : « + 8 500 MAD » / « − 8 500 MAD »
 * (jamais un pourcentage, jamais un mot qui dénigre la gamme économique).
 * `null` quand l'écart est inconnu ou nul — la carte n'affiche alors rien.
 */
export function gammeEcartLabel(ecart: number | null | undefined): string | null {
  if (typeof ecart !== 'number' || !Number.isFinite(ecart)) return null;
  const rounded = Math.round(ecart);
  if (rounded === 0) return null;
  return `${rounded > 0 ? '+' : '−'} ${formatMAD(Math.abs(rounded))}`;
}

/** Lignes qui DIFFÈRENT entre les deux compositions (tableau comparatif). */
export function gammeComparatif(
  g: ProposalGammes | null,
): ProposalGammeComparatifRow[] {
  return Array.isArray(g?.comparatif) ? g!.comparatif : [];
}

/**
 * Format monétaire marocain : `12 500 MAD` (espace fine de milliers, devise
 * après le nombre). Identique à lib/format.formatMAD ; dupliqué ici pour garder
 * ce module autonome et sûr à importer côté navigateur sans dépendances.
 */
export function formatMAD(amount: number | null | undefined): string {
  const n = typeof amount === 'number' && Number.isFinite(amount) ? amount : 0;
  const rounded = Math.round(n);
  const sign = rounded < 0 ? '-' : '';
  const digits = Math.abs(rounded).toString();
  const grouped = digits.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  return `${sign}${grouped} MAD`;
}

/**
 * Format nombre marocain SANS devise (ex. production en kWh, panneaux) :
 * `8 640` — séparateur de milliers espace. `decimals` arrondit (défaut 0).
 */
export function formatNumber(value: number | null | undefined, decimals = 0): string {
  const n = typeof value === 'number' && Number.isFinite(value) ? value : 0;
  const factor = 10 ** decimals;
  const rounded = Math.round(n * factor) / factor;
  const sign = rounded < 0 ? '-' : '';
  const abs = Math.abs(rounded);
  const intPart = Math.trunc(abs).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  if (decimals <= 0) return `${sign}${intPart}`;
  const frac = (abs - Math.trunc(abs)).toFixed(decimals).slice(2).replace(/0+$/, '');
  return frac ? `${sign}${intPart},${frac}` : `${sign}${intPart}`;
}

/** Pourcentage lisible : `30 %` (espace avant le signe, virgule décimale). */
export function formatPercent(value: number | null | undefined, decimals = 0): string {
  return `${formatNumber(value, decimals)} %`;
}

/**
 * WJ72 — UN SEUL style de nombre de bout en bout : l'estimation instantanée
 * (/devis/mon-toit) affichait jusqu'ici le kWc BRUT (`String(est.kwc)` →
 * point décimal, ex. « 7.5 kWc ») pendant que la proposition utilisait déjà
 * `formatNumber(kwc, 2)` (virgule décimale, zéros de fin retirés, ex.
 * « 7,5 kWc » ou « 11 kWc »). Un client qui compare son estimation à sa
 * proposition voyait deux langages de nombres différents. `formatKwc` est
 * l'UNIQUE point de formatage kWc du site — mon-toit.astro (FR/EN/AR) et la
 * proposition l'utilisent tous les deux désormais, jamais un `String(...)`
 * ou un `.toFixed(...)` local.
 */
export function formatKwc(value: number | null | undefined): string {
  return formatNumber(value, 2);
}

/**
 * Affiche une durée de retour sur investissement. Le backend peut renvoyer un
 * nombre (années) ou une chaîne déjà formatée — on respecte les deux.
 */
export function formatPayback(roi: number | string | null | undefined): string | null {
  if (roi === null || roi === undefined || roi === '') return null;
  if (typeof roi === 'number') {
    if (!Number.isFinite(roi) || roi <= 0) return null;
    return `${formatNumber(roi, 1)} ans`;
  }
  const trimmed = String(roi).trim();
  return trimmed.length ? trimmed : null;
}

/**
 * Nombre d'options réel : on fait confiance à `option_totals.nb_options` quand il
 * est présent (1 ou 2), sinon on retombe sur la présence des deux blocs de totaux.
 */
export function optionCount(p: ProposalResponse): number {
  const n = p.option_totals?.nb_options;
  if (n === 1 || n === 2) return n;
  const hasSans = !!p.quote?.totaux_sans;
  const hasAvec = !!p.quote?.totaux_avec;
  if (hasSans && hasAvec) return 2;
  return 1;
}

/** Vrai si la proposition propose deux options (sans batterie vs avec batterie). */
export function hasTwoOptions(p: ProposalResponse): boolean {
  return optionCount(p) === 2;
}

/** L'option recommandée, normalisée. Défaut : `avec_batterie` si présente, sinon `sans_batterie`. */
export function recommendedOption(p: ProposalResponse): OptionKey {
  const r = p.quote?.recommended;
  if (r === 'sans_batterie' || r === 'avec_batterie') return r;
  return p.quote?.totaux_avec ? 'avec_batterie' : 'sans_batterie';
}

/** TTC d'une option donnée (lecture défensive). */
export function optionTtc(p: ProposalResponse, opt: OptionKey): number {
  const t = opt === 'avec_batterie' ? p.quote?.totaux_avec : p.quote?.totaux_sans;
  if (t && Number.isFinite(t.ttc)) return t.ttc;
  return opt === 'avec_batterie' ? p.option_totals?.avec_batterie ?? 0 : p.option_totals?.sans_batterie ?? 0;
}

/**
 * WJ83 — Garde-fou « zéro chiffre inventé » appliqué au PRIX : `optionTtc`
 * retombe sur `0` (via `?? 0`) quand aucun totaux n'est exploitable — un
 * payload dégénéré (devis mal formé, option absente) affichait alors
 * « 0 MAD TTC, clé en main » comme un VRAI prix. `hasRealPrice` distingue un
 * prix réel (TTC backend strictement positif) d'un repli à 0 : la page doit
 * alors masquer le prix + le CTA de signature et afficher un message
 * honnête (« prix communiqué par votre conseiller ») plutôt qu'un chiffre.
 */
export function hasRealPrice(p: ProposalResponse, opt: OptionKey): boolean {
  const ttc = optionTtc(p, opt);
  return Number.isFinite(ttc) && ttc > 0;
}

/** Étiquette FR courte d'une option. */
export function optionLabel(opt: OptionKey): string {
  return opt === 'avec_batterie' ? 'Avec batterie' : 'Sans batterie';
}

/** WJ43 — Étiquette arabe d'une option (paire de `optionLabel` pour le data-i18n). */
export function optionLabelAr(opt: OptionKey): string {
  return opt === 'avec_batterie' ? 'مع بطارية' : 'بدون بطارية';
}

/** WJ43 — Étiquette anglaise d'une option (paire de `optionLabel` pour le data-i18n). */
export function optionLabelEn(opt: OptionKey): string {
  return opt === 'avec_batterie' ? 'With battery' : 'Without battery';
}

/** Lignes d'équipement d'une option (toujours un tableau). */
export function optionItems(p: ProposalResponse, opt: OptionKey): ProposalItem[] {
  const items = opt === 'avec_batterie' ? p.quote?.avec_items : p.quote?.sans_items;
  return Array.isArray(items) ? items : [];
}

/** Totaux d'une option (peut être absent pour une option non proposée). */
export function optionTotaux(p: ProposalResponse, opt: OptionKey): ProposalTotaux | null {
  const t = opt === 'avec_batterie' ? p.quote?.totaux_avec : p.quote?.totaux_sans;
  return t ?? null;
}

/**
 * L'option « par défaut » à pré-sélectionner dans le formulaire de signature :
 * la recommandée si deux options, sinon la seule disponible.
 */
export function defaultSelectedOption(p: ProposalResponse): OptionKey {
  if (hasTwoOptions(p)) return recommendedOption(p);
  return p.quote?.totaux_avec && !p.quote?.totaux_sans ? 'avec_batterie' : 'sans_batterie';
}

// ── L-VAR (ordre fondateur, 24/08/2026) — CE QUE L'ÉQUIPEMENT PEUT SERVIR ────

/** Un côté servable du devis, dans l'écriture du contrat backend. */
export type VarianteServable = 'sans' | 'avec';

/** L'ordre d'affichage canonique — jamais celui, arbitraire, du payload. */
const VARIANTES_CANONIQUES: readonly VarianteServable[] = ['sans', 'avec'];

/**
 * Les variantes que l'équipement du devis peut PHYSIQUEMENT servir.
 *
 * ORDRE FONDATEUR (24/08/2026) — LE TÉLÉCHARGEMENT NE DÉPEND PLUS DU NOMBRE
 * D'OPTIONS PRÉSENTÉES. Un devis à deux options rétréci côté backend
 * (`nb_options` retombé à 1 : incident DEV-202608-0023) faisait disparaître
 * D'UN COUP la case de signature, le sélecteur de variante PDF et le
 * `?variante=` — alors que l'équipement, lui, servait toujours les deux côtés.
 * Les deux sujets sont désormais SÉPARÉS : `hasTwoOptions` ne commande plus que
 * la SIGNATURE (le devis ne PRÉSENTE qu'une option ⇒ rien à choisir en
 * signant), tandis que le téléchargement lit cette liste-ci.
 *
 * Source : clé RACINE `variantes_servables` du payload public (liste ordonnée,
 * sous-ensemble de ['sans','avec']). Lecture DÉFENSIVE : tout ce qui n'est pas
 * l'une des deux valeurs canoniques est ignoré. Clé absente / vide / illisible
 * (backend antérieur au contrat) ⇒ REPLI sur le signal historique, donc rendu
 * strictement inchangé sur les payloads d'avant : deux options présentées ⇒ les
 * deux côtés, sinon le seul côté que le devis porte.
 */
export function variantesServables(p: ProposalResponse | null | undefined): VarianteServable[] {
  if (!p) return [];
  const raw = p.variantes_servables;
  if (Array.isArray(raw)) {
    const servables = VARIANTES_CANONIQUES.filter((v) => raw.includes(v));
    if (servables.length > 0) return servables;
  }
  if (hasTwoOptions(p)) return ['sans', 'avec'];
  return defaultSelectedOption(p) === 'avec_batterie' ? ['avec'] : ['sans'];
}

/**
 * Le sélecteur « quelle version télécharger ? » n'a de sens que si les DEUX
 * côtés sont servables — sinon il n'y aurait rien à choisir.
 */
export function showVariantSelector(p: ProposalResponse | null | undefined): boolean {
  const servables = variantesServables(p);
  return servables.includes('sans') && servables.includes('avec');
}

/** Vrai si la proposition est déjà acceptée (signée) — affiche l'état confirmé. */
export function isAccepted(p: Pick<ProposalResponse, 'accepted' | 'statut'>): boolean {
  return p.accepted === true || p.statut === 'accepte';
}

// ── WJ82 · États explicites d'une offre morte (refusée / expirée / retirée) ──

/**
 * L'état de l'offre du point de vue de la signature. `statut` backend est l'un
 * des 5 statuts canoniques du devis (brouillon/envoye/accepte/refuse/expire —
 * voir `apps/ventes/models.py Devis.Statut`) ; « withdrawn » n'existe pas côté
 * backend aujourd'hui mais est accepté défensivement comme alias de `refuse`
 * si jamais rencontré (jamais une nouvelle valeur inventée, juste une synonymie
 * de lecture). `expired` retombe sur `resolveValidity` (date_validite dépassée)
 * quand le statut lui-même ne le dit pas déjà.
 */
export type OfferState = 'live' | 'accepted' | 'refused' | 'expired' | 'withdrawn';

/**
 * WJ82 — Résout l'état de signature d'une offre : une offre acceptée, refusée,
 * expirée (statut backend `expire` OU date de validité dépassée) ou retirée ne
 * doit plus pouvoir être signée. `live` = tout le reste (brouillon/envoyé,
 * dans les temps) — seul état où le formulaire + le CTA collant restent actifs.
 */
export function resolveOfferState(
  p: Pick<ProposalResponse, 'statut' | 'accepted' | 'date_validite' | 'quote'>,
  now: Date = new Date(),
): OfferState {
  if (isAccepted(p)) return 'accepted';
  const statut = (p.statut ?? '').trim().toLowerCase();
  if (statut === 'refuse' || statut === 'refusee' || statut === 'refusé') return 'refused';
  if (statut === 'withdrawn' || statut === 'retire' || statut === 'retiré') return 'withdrawn';
  if (statut === 'expire' || statut === 'expiré' || statut === 'expired') return 'expired';
  if (resolveValidity(p, now).expired) return 'expired';
  return 'live';
}

/** Vrai quand l'offre ne peut plus être signée (tout sauf `live`). */
export function isOfferDead(state: OfferState): boolean {
  return state !== 'live';
}

// ── Formulaire de signature : validation + mise en forme de la requête ───────

export interface SignFormState {
  nom: string;
  option: OptionKey | null;
}

export interface SignValidation {
  valid: boolean;
  /** Message FR à afficher quand invalide (null si valide). */
  error: string | null;
}

/**
 * Validation du formulaire de signature côté client (le backend revalide).
 * - nom non vide,
 * - option choisie OBLIGATOIRE quand il y a deux options.
 */
export function validateSign(form: SignFormState, twoOptions: boolean): SignValidation {
  const nom = (form.nom ?? '').trim();
  if (!nom) return { valid: false, error: 'Veuillez saisir votre nom complet.' };
  if (twoOptions && form.option !== 'sans_batterie' && form.option !== 'avec_batterie') {
    return { valid: false, error: 'Veuillez choisir une option avant de signer.' };
  }
  return { valid: true, error: null };
}

export interface AcceptRequestBody {
  nom: string;
  option?: OptionKey;
}

/**
 * Met en forme le corps envoyé au proxy /api/proposition-accept (qui le relaie
 * tel quel au backend). `option` n'est inclus que lorsqu'il y a deux options —
 * conforme au contrat (option REQUISE si nb_options===2, ignorée sinon).
 */
export function buildAcceptBody(form: SignFormState, twoOptions: boolean): AcceptRequestBody {
  const body: AcceptRequestBody = { nom: (form.nom ?? '').trim() };
  if (twoOptions && (form.option === 'sans_batterie' || form.option === 'avec_batterie')) {
    body.option = form.option;
  }
  return body;
}

/**
 * Construit l'URL backend de l'endpoint d'acceptation à partir d'une base API et
 * d'un token. Utilisé côté serveur par le proxy. Encode le token (path segment).
 */
export function acceptEndpoint(apiBase: string, token: string): string {
  const base = (apiBase || 'https://api.taqinor.ma').replace(/\/+$/, '');
  return `${base}/api/django/ventes/proposal/${encodeURIComponent(token)}/accept/`;
}

/** Construit l'URL backend de lecture de la proposition (frontmatter Astro). */
export function proposalEndpoint(apiBase: string, token: string): string {
  const base = (apiBase || 'https://api.taqinor.ma').replace(/\/+$/, '');
  return `${base}/api/django/ventes/proposal/${encodeURIComponent(token)}/`;
}

/**
 * URL publique du DEVIS PDF premium (même token) : le bouton « Télécharger le
 * devis » pointe directement vers le backend (nouvel onglet). Le lien est public
 * et tokenisé — pas d'auth, pas de prix d'achat (le backend ne les rend jamais).
 */
export function proposalPdfEndpoint(apiBase: string, token: string): string {
  const base = (apiBase || 'https://api.taqinor.ma').replace(/\/+$/, '');
  return `${base}/api/django/ventes/proposal/${encodeURIComponent(token)}/pdf/`;
}

// ── WJ29 · « Être contacté » / « Demander un rappel » — notification équipe ──
//
// QW5 (2026-07-05) — la route backend EXISTE et est aliasée sous ce mount
// (apps/ventes/urls.py, réutilisant les vues QJ27 déjà exposées sous
// public/) : channel/message/revision_kind sont bien reçus et traités
// (chatter + notification owner+supérieur, idempotence par lien+canal). Le
// proxy /api/proposition-contact dégrade quand même proprement (message FR
// clair) sur un éventuel 404/5xx/panne réseau, en gardant le lien wa.me
// instantané disponible en parallèle.

/** Construit l'URL backend de la demande de contact (même convention que /accept/). */
export function contactEndpoint(apiBase: string, token: string): string {
  const base = (apiBase || 'https://api.taqinor.ma').replace(/\/+$/, '');
  return `${base}/api/django/ventes/proposal/${encodeURIComponent(token)}/contact/`;
}

/** Canal choisi par le client pour la demande de contact. WJ85 — `voice`
 *  couvre l'invitation à la note vocale WhatsApp (canal distinct de `whatsapp`
 *  générique, pour que l'équipe voie que le client a été orienté vers un
 *  message vocal plutôt qu'un texte). WJ54 — `revision` couvre la demande de
 *  modification structurée (voir `RevisionKind` ci-dessous) : un canal
 *  DISTINCT des précédents pour que le CRM/lead webhook puisse la trier
 *  séparément d'un simple rappel/question. */
export type ContactChannel = 'rappel' | 'whatsapp' | 'question' | 'voice' | 'revision';

export interface ContactRequestState {
  channel: ContactChannel;
  /** Message libre optionnel (ex. depuis « Poser une question »). */
  message?: string;
  /** WJ54 — précise le TYPE de modification demandée (uniquement quand `channel === 'revision'`). */
  revisionKind?: RevisionKind;
}

export interface ContactRequestBody {
  channel: ContactChannel;
  message: string;
  /** WJ54 — omis quand `channel !== 'revision'` (jamais un champ vide envoyé sans raison). */
  revision_kind?: RevisionKind;
}

/**
 * WJ29/WJ85 — Met en forme le corps envoyé au proxy /api/proposition-contact.
 * Le canal est normalisé (repli 'rappel' si invalide) ; le message est
 * tronqué à une longueur raisonnable pour ne jamais inonder l'upstream.
 */
export function buildContactBody(state: ContactRequestState): ContactRequestBody {
  const channel: ContactChannel =
    state.channel === 'whatsapp' || state.channel === 'question' || state.channel === 'voice' || state.channel === 'revision'
      ? state.channel
      : 'rappel';
  const message = (state.message ?? '').trim().slice(0, 2000);
  const body: ContactRequestBody = { channel, message };
  if (channel === 'revision') {
    const kind = state.revisionKind;
    body.revision_kind = kind === 'kwc' || kind === 'batterie' || kind === 'autre' ? kind : 'autre';
  }
  return body;
}

// ── WJ54 · « Demander une modification » — formulaire de révision structurée ─

/**
 * WJ54 — Type d'ajustement demandé par le client sur SA proposition : ajuster
 * la puissance (kWc), changer l'option batterie, ou « autre » (texte libre
 * obligatoire dans ce cas). Volontairement les 3 catégories les plus
 * fréquentes observées en négociation avant signature — pas une nomenclature
 * exhaustive.
 */
export type RevisionKind = 'kwc' | 'batterie' | 'autre';

export interface RevisionRequestState {
  kind: RevisionKind;
  /** Texte libre — TOUJOURS envoyé (contexte utile même pour kwc/batterie), tronqué comme un message normal. */
  detail: string;
}

export interface RevisionValidation {
  valid: boolean;
  /** Message FR à afficher quand invalide (null si valide). */
  error: string | null;
}

/**
 * WJ54 — Validation du formulaire de révision : le type doit être l'une des 3
 * valeurs reconnues ; le texte libre est OBLIGATOIRE pour « autre » (sinon la
 * demande n'a aucun contenu exploitable), optionnel pour kwc/batterie (le type
 * suffit à orienter le conseiller, le texte est un complément).
 */
export function validateRevisionRequest(state: RevisionRequestState): RevisionValidation {
  const kind = state.kind;
  if (kind !== 'kwc' && kind !== 'batterie' && kind !== 'autre') {
    return { valid: false, error: 'Veuillez choisir le type de modification souhaitée.' };
  }
  const detail = (state.detail ?? '').trim();
  if (kind === 'autre' && !detail) {
    return { valid: false, error: 'Merci de préciser votre demande en quelques mots.' };
  }
  return { valid: true, error: null };
}

/**
 * WJ54 — Construit le corps de la demande de révision, prêt à poster vers le
 * proxy /api/proposition-contact (même endpoint que WJ29 — canal `revision`
 * distinct, AUCUN nouveau endpoint). Le message combine un préfixe FR lisible
 * par le conseiller (« Ajuster la puissance (kWc) » etc.) et le texte libre du
 * client, tronqué comme tout message de contact.
 */
export function buildRevisionContactState(state: RevisionRequestState): ContactRequestState {
  const kind: RevisionKind = state.kind === 'kwc' || state.kind === 'batterie' ? state.kind : 'autre';
  const labels: Record<RevisionKind, string> = {
    kwc: 'Ajuster la puissance (kWc)',
    batterie: 'Changer l’option batterie',
    autre: 'Autre modification',
  };
  const detail = (state.detail ?? '').trim();
  const message = detail ? `${labels[kind]} — ${detail}` : labels[kind];
  return { channel: 'revision', message, revisionKind: kind };
}

export interface ContactResult {
  /** Vrai quand la notification a probablement atteint l'équipe (best-effort). */
  ok: boolean;
  /** Message FR à confirmer au client, TOUJOURS rassurant même en dégradé. */
  detail: string;
  /**
   * Vrai quand le backend n'a pas (encore) de route de contact ou est
   * injoignable : le client garde alors le lien wa.me instantané en avant,
   * jamais un message d'échec brut.
   */
  degraded: boolean;
}

/**
 * WJ29 — Normalise le résultat du proxy de contact EN DÉGRADANT TOUJOURS
 * PROPREMENT : le backend ne porte pas encore cette route (404) ou peut être
 * injoignable (5xx / erreur réseau) — dans les deux cas, le client voit un
 * message honnête qui le renvoie vers WhatsApp, jamais une erreur technique.
 * Un succès (2xx) confirme l'envoi au client.
 */
export function normalizeContactResponse(status: number, networkError: boolean = false): ContactResult {
  if (!networkError && status >= 200 && status < 300) {
    return { ok: true, detail: 'Merci — nous vous rappelons très vite.', degraded: false };
  }
  return {
    ok: false,
    degraded: true,
    detail: 'Service momentanément indisponible — contactez-nous sur WhatsApp, nous répondons vite.',
  };
}

/**
 * Lecture défensive d'un tableau mensuel (production/consommation) : renvoie
 * exactement 12 valeurs finies ≥ 0 si l'entrée est un tableau de 12 éléments avec
 * au moins une valeur > 0, sinon `null` (tableau vide, taille ≠ 12, ou tout zéro).
 * Le graphe (proposalChart) refait ce nettoyage, mais l'exposer ici permet à la
 * page de décider d'AFFICHER ou non le bloc graphe sans dupliquer la règle.
 */
export function monthlySeries(arr: number[] | undefined | null): number[] | null {
  if (!Array.isArray(arr) || arr.length !== 12) return null;
  let any = false;
  const out = arr.map((v) => {
    const n = typeof v === 'number' && Number.isFinite(v) && v > 0 ? v : 0;
    if (n > 0) any = true;
    return n;
  });
  return any ? out : null;
}

/**
 * Vrai si la proposition porte AU MOINS une série de production exploitable —
 * condition d'affichage du bloc graphe (P2). Sans production, on n'affiche rien
 * (une conso « solo » ne raconte aucune histoire sur cette page).
 */
export function hasProductionSeries(p: ProposalResponse): boolean {
  return monthlySeries(p.monthly_production) !== null;
}

// ── L-NIV-VU · « Version simplifiée » — SEULEMENT quand c'est vrai ─────────
//
// Constat fondateur du 24/08/2026 : basculer « Client standard » ↔ « Client de
// confiance » ne se VOYAIT pas sur la page client. La chaîne fonctionnait — ce
// qui manquait, c'est que la page DISE ce qui a été simplifié, et seulement
// quand quelque chose l'a réellement été (`niveau_masque`, constaté serveur).
//
// Aucune dégradation nouvelle n'est introduite ici : ce bloc n'AJOUTE qu'une
// phrase, et les marques/modèles comme tous les montants restent identiques
// aux deux niveaux (décision fondateur, armée par des tests Django).

/** Libellés client des dégradations réellement appliquées. */
const LIBELLES_NIVEAU_MASQUE: Record<string, string> = {
  nomenclature_kit:
    'le détail des fournitures de pose (fixations, câblage, protections) est'
    + ' regroupé en une seule ligne',
  dimensionnement_electrique:
    'les calibres, sections de câble et longueurs du dimensionnement'
    + ' électrique ne sont pas détaillés',
};

/**
 * Phrase à afficher au client, ou `null` quand il n'y a RIEN à annoncer.
 *
 * `null` dans les trois cas honnêtes : niveau « confiance », clé absente
 * (backend antérieur à L-NIV-VU), ou niveau « standard » sur un devis où
 * aucune dégradation ne s'est déclenchée. Une clé inconnue est IGNORÉE plutôt
 * que rendue telle quelle — jamais de jargon serveur sur une page client.
 */
export function noteVersionSimplifiee(
  p: Pick<ProposalResponse, 'niveau_masque'>,
): string | null {
  const cles = Array.isArray(p.niveau_masque) ? p.niveau_masque : [];
  const raisons = cles
    .map((c) => LIBELLES_NIVEAU_MASQUE[c])
    .filter((libelle): libelle is string => typeof libelle === 'string');
  if (raisons.length === 0) return null;
  return `Version simplifiée : ${raisons.join(' ; ')}.`
    + ' Demandez la version détaillée à votre conseiller.';
}

// ── WJ128 · Schéma électrique (SLD) — affichage + téléchargement SVG ────────
//
// Le backend rend le schéma unifilaire en SVG CLIENT-SAFE (aucun prix
// d'achat/marge) et l'expose dans `sld_svg` UNIQUEMENT quand l'étude
// électrique du devis existe (sinon `null`) — jamais un placeholder inventé.
// Le PDF téléchargeable embarque déjà le schéma quand l'étude existe (flux
// PDF INCHANGÉ, CLAUDE.md règle #4) : cette section est un affichage web
// SUPPLÉMENTAIRE, pas un nouveau chemin de génération.

/**
 * Vrai quand la proposition porte un schéma électrique exploitable. Simple
 * garde de présence (chaîne non vide) — le SVG lui-même n'est jamais reparsé
 * côté client, il est injecté tel quel (déjà nettoyé côté serveur).
 */
export function hasSldSvg(p: Pick<ProposalResponse, 'sld_svg'>): boolean {
  return typeof p.sld_svg === 'string' && p.sld_svg.trim().length > 0;
}

/**
 * Nom de fichier du schéma téléchargé : `schema-electrique-<référence>.svg`.
 * La référence devis peut porter des caractères peu sûrs pour un nom de
 * fichier (espaces, slashes…) — on ne garde que [A-Za-z0-9_-], le reste
 * devient `-` ; une référence qui ne laisse rien d'exploitable retombe sur
 * `devis` (jamais un nom de fichier vide).
 */
export function sldSvgFilename(reference: string | null | undefined): string {
  const raw = (reference ?? '').trim();
  const safe = raw.replace(/[^A-Za-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '');
  return `schema-electrique-${safe || 'devis'}.svg`;
}

// ── 2026-08-18 · « Dans votre installation » — le DÉTAIL ÉLECTRIQUE, SANS PRIX ─
//
// Décision fondateur : le client voit enfin ce que contiennent les lignes qu'il
// paie. Le backend (`public_views._conception_electrique_publique`) expose un
// bloc `conception_electrique` sur liste blanche STRICTE — chaînes, protections
// nominatives, câbles — et RIEN d'autre : pas de nomenclature d'achat, pas de
// paramètres de calcul, aucun montant (règle #4 ; le moteur électrique n'en
// connaît aucun). Le bloc n'existe que lorsque l'étude électrique a réellement
// été faite ; `null`/absent ⇒ aucun dépliant ne s'affiche.
//
// TOUT EST LU DÉFENSIVEMENT et TOUTE VALEUR ABSENTE EST OMISE (règle dure) :
// une chaîne sans nombre de modules ne devient jamais « 0 module ».

/** Une chaîne de modules : combien de modules, sur quel MPPT, sur quel pan. */
export interface ConceptionChaine {
  pan?: number;
  mppt?: number;
  nb_modules?: number;
}

/** Un organe de protection réellement posé (ce qui est écrit dans le coffret). */
export interface ConceptionProtection {
  repere?: string;
  designation?: string;
  calibre?: string;
  quantite?: number;
}

/**
 * Les organes, PRÉ-ROUTÉS PAR LE SERVEUR (L-1V, 24/08/2026).
 *
 * La page rangeait auparavant chaque organe d'un côté ou de l'autre en
 * cherchant « dc », « gpv » ou « chaîne » dans SA DÉSIGNATION. Le jour où
 * l'anticopie a fusionné les lignes du kit en un seul « Kit de fixation,
 * câblage et protection complet », l'heuristique a classé le poste entier du
 * côté alternatif : le client a perdu TOUS ses organes continus (fusibles gPV,
 * parafoudre DC, sectionneur DC) sur sa fiche technique, pendant que le schéma
 * unifilaire de la même page continuait de les dessiner. Le côté est désormais
 * une décision du MOTEUR (`core.electrique.protections`), servie telle quelle.
 */
export interface GroupesOrganes {
  dc: ConceptionProtection[];
  ac: ConceptionProtection[];
  communs: ConceptionProtection[];
}

/** Une liaison câblée : ce qu'elle relie, sa section, sa longueur. */
export interface ConceptionCable {
  liaison?: string;
  section_mm2?: number;
  longueur_m?: number;
}

export interface ConceptionElectrique {
  chaines: ConceptionChaine[];
  /** TOUS les organes, dans l'ordre du moteur (c'est l'ordre du schéma). */
  protections: ConceptionProtection[];
  /** Les mêmes, répartis PAR LE SERVEUR — la page ne décide plus d'un côté. */
  groupes: GroupesOrganes;
  cables: ConceptionCable[];
}

/** Nombre fini et strictement positif, sinon `undefined` (jamais un 0 inventé). */
function nombrePositif(v: unknown): number | undefined {
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) && n > 0 ? n : undefined;
}

/** Chaîne non vide, taillée, sinon `undefined`. */
function texteNonVide(v: unknown): string | undefined {
  if (typeof v !== 'string') return undefined;
  const t = v.trim();
  return t.length ? t : undefined;
}

/**
 * Pose la clé UNIQUEMENT si la valeur existe. C'est le cœur de la règle dure :
 * un objet public ne porte jamais `{ mppt: undefined }` ni `{ mppt: 0 }` — la
 * clé est simplement absente, et le rendu n'a donc rien à afficher.
 */
function poser(cible: Record<string, unknown>, cle: string, valeur: unknown): void {
  if (valeur !== undefined) cible[cle] = valeur;
}

/**
 * Lecture défensive du bloc `conception_electrique`. Renvoie `null` quand le
 * backend ne l'a pas envoyé, l'a envoyé à `null`, ou quand il ne reste RIEN
 * d'affichable après nettoyage — jamais un bloc à moitié vide.
 */
export function parseConceptionElectrique(
  p: Pick<ProposalResponse, 'conception_electrique'>,
): ConceptionElectrique | null {
  const brut = p?.conception_electrique;
  if (!brut || typeof brut !== 'object') return null;
  const src = brut as Record<string, unknown>;
  const liste = (v: unknown): Record<string, unknown>[] =>
    Array.isArray(v) ? v.filter((e): e is Record<string, unknown> => !!e && typeof e === 'object') : [];

  // Une CHAÎNE sans nombre de modules ne dit rien : elle est écartée.
  const chaines: ConceptionChaine[] = [];
  for (const c of liste(src.chaines)) {
    const item: Record<string, unknown> = {};
    poser(item, 'pan', nombrePositif(c.pan));
    poser(item, 'mppt', nombrePositif(c.mppt));
    poser(item, 'nb_modules', nombrePositif(c.nb_modules));
    if (item.nb_modules !== undefined) chaines.push(item as ConceptionChaine);
  }

  // Un ORGANE sans désignation ne serait qu'un repère orphelin : écarté.
  const organes = (v: unknown): ConceptionProtection[] => {
    const sortie: ConceptionProtection[] = [];
    for (const o of liste(v)) {
      const item: Record<string, unknown> = {};
      poser(item, 'repere', texteNonVide(o.repere));
      poser(item, 'designation', texteNonVide(o.designation));
      poser(item, 'calibre', texteNonVide(o.calibre));
      poser(item, 'quantite', nombrePositif(o.quantite));
      if (item.designation !== undefined) sortie.push(item as ConceptionProtection);
    }
    return sortie;
  };
  const protections = organes(src.protections);
  const groupes: GroupesOrganes = {
    dc: organes(src.protections_dc),
    ac: organes(src.protections_ac),
    communs: organes(src.protections_communes),
  };

  // Une LIAISON sans section NI longueur n'apprend rien : écartée.
  const cables: ConceptionCable[] = [];
  for (const c of liste(src.cables)) {
    const item: Record<string, unknown> = {};
    poser(item, 'liaison', texteNonVide(c.liaison));
    poser(item, 'section_mm2', nombrePositif(c.section_mm2));
    poser(item, 'longueur_m', nombrePositif(c.longueur_m));
    if (item.section_mm2 !== undefined || item.longueur_m !== undefined) {
      cables.push(item as ConceptionCable);
    }
  }

  if (!chaines.length && !protections.length && !cables.length) return null;
  return { chaines, protections, groupes, cables };
}

/** Les deux familles de fiche qui accueillent des organes de protection. */
const SLUGS_PROTECTION: readonly string[] = ['protection-dc', 'protection-ac'];

/**
 * RÉPARTIT les organes de l'étude sur les lignes rendues — une PARTITION, pas
 * un filtre : chaque organe apparaît EXACTEMENT UNE FOIS, et aucun ne peut
 * rester orphelin. Rend un tableau aligné sur `slugs` (organes par ligne).
 *
 * La règle, dans l'ordre :
 *  1. chaque ligne `protection-dc` reçoit le groupe DC du serveur, chaque ligne
 *     `protection-ac` le groupe AC — les côtés viennent du MOTEUR, la page ne
 *     lit plus aucune désignation pour en décider ;
 *  2. les organes COMMUNS (coffret AC/DC, mise à la terre) vont sur la PREMIÈRE
 *     ligne de protection : ils n'appartiennent exclusivement à aucun côté ;
 *  3. **un groupe sans ligne d'accueil rejoint cette même première ligne.**
 *     C'est le cas du catalogue réel depuis l'anticopie : le devis ne porte
 *     plus qu'UNE ligne « Kit de fixation, câblage et protection complet ».
 *     Sans cette règle, tout un côté du dossier disparaîtrait de la page alors
 *     que le schéma unifilaire, lui, le dessine — la contradiction que ce
 *     chantier ferme.
 *
 * Aucune ligne de protection dans le devis ⇒ que des tableaux vides (il n'y a
 * rien à quoi accrocher un organe ; la page n'invente pas une ligne).
 */
export function repartirOrganes(
  conception: ConceptionElectrique | null,
  slugs: ReadonlyArray<string | null | undefined>,
): ConceptionProtection[][] {
  const parLigne: ConceptionProtection[][] = slugs.map(() => []);
  if (!conception) return parLigne;
  const indices = slugs
    .map((s, i) => (SLUGS_PROTECTION.includes(String(s)) ? i : -1))
    .filter((i) => i >= 0);
  if (!indices.length) return parLigne;
  const premier = indices[0];
  const { dc, ac, communs } = conception.groupes;
  let dcPlace = false;
  let acPlace = false;
  // La PREMIÈRE ligne de chaque famille sert d'accueil : deux lignes
  // « protection-dc » ne montrent pas deux fois les mêmes organes.
  for (const i of indices) {
    if (slugs[i] === 'protection-dc' && !dcPlace) {
      parLigne[i].push(...dc);
      dcPlace = true;
    } else if (slugs[i] === 'protection-ac' && !acPlace) {
      parLigne[i].push(...ac);
      acPlace = true;
    }
  }
  if (!dcPlace) parLigne[premier].push(...dc);
  if (!acPlace) parLigne[premier].push(...ac);
  parLigne[premier].push(...communs);
  return parLigne;
}

/** Ce qu'un dépliant « Dans votre installation » montre pour une famille donnée. */
export interface ConceptionPourLigne {
  chaines: ConceptionChaine[];
  protections: ConceptionProtection[];
  cables: ConceptionCable[];
  /** Les câbles montrés ici sont RATTACHÉS (le devis n'a pas de ligne câblage) :
   *  la page les annonce alors par un intertitre « Câblage », pour qu'on ne les
   *  lise pas comme des organes de protection. Faux sous une ligne câblage. */
  cablesRattaches: boolean;
}

/** Options de rattachement d'une ligne d'équipement (toutes facultatives). */
export interface ConceptionPourLigneOpts {
  /** Les organes QUE LE SERVEUR A ROUTÉS vers cette ligne (`repartirOrganes`).
   *  La page ne filtre plus rien elle-même : elle affiche ce qu'on lui donne. */
  organes?: ConceptionProtection[];
  /** Cette ligne accueille-t-elle les câbles faute de ligne « câblage » dédiée ?
   *  Le choix de la ligne hôte appartient à l'appelant (`indexHoteDesCables`),
   *  pour qu'une seule ligne les porte — jamais les deux protections. */
  rattacherCables?: boolean;
}

/**
 * Index de la ligne de protection qui ACCUEILLE les câbles, dans l'ordre des
 * lignes rendues. Le catalogue résidentiel réel ne porte AUCUN poste « câble »
 * (ses postes génériques sont « Tableau De Protection AC/DC », « Accessoires »,
 * « Socles », « Structures acier/aluminium ») : sans ce rattachement, les
 * sections et longueurs calculées par l'étude n'apparaissaient NULLE PART.
 * Rend -1 — donc aucun rattachement — dès qu'une vraie ligne « câblage »
 * existe (les câbles ont alors leur propre dépliant) ou qu'aucune ligne de
 * protection n'existe.
 */
export function indexHoteDesCables(slugs: ReadonlyArray<string | null | undefined>): number {
  if (slugs.some((s) => s === 'cablage')) return -1;
  return slugs.findIndex((s) => s === 'protection-dc' || s === 'protection-ac');
}

/**
 * Le détail à déplier SOUS une ligne d'équipement, choisi par la FAMILLE de sa
 * fiche technique (le slug rendu par `ficheSlugPourLigne`) :
 *
 *  · `protection-dc` / `protection-ac` → les organes que `repartirOrganes` a
 *    routés vers CETTE ligne, tels quels (côtés décidés par le moteur) ;
 *  · `cablage`        → les sections et longueurs de liaison ;
 *  · panneaux/onduleur → le chaînage (modules par MPPT).
 *
 * Faute de ligne « câblage » au devis, `rattacherCables` accroche les liaisons
 * sous la ligne de protection (intertitre « Câblage » côté page).
 *
 * Toute autre famille (batterie, structure, accessoires de pose, supervision,
 * grands projets) n'a rien à dire ici : `null`, et aucun dépliant n'est rendu.
 * `null` aussi quand la famille est concernée mais que l'étude ne porte AUCUNE
 * valeur pour elle — jamais un dépliant vide. Une valeur absente reste OMISE :
 * ce rattachement ne fabrique rien, il montre ce que l'étude a déjà calculé.
 */
export function conceptionPourLigne(
  conception: ConceptionElectrique | null,
  ficheSlug: string | null | undefined,
  opts?: ConceptionPourLigneOpts,
): ConceptionPourLigne | null {
  if (!conception || !ficheSlug) return null;
  // Une FABRIQUE, pas une constante partagée : chaque appel repart de trois
  // tableaux neufs (aucun aliasing possible entre deux lignes du devis).
  const vide = (): ConceptionPourLigne => ({ chaines: [], protections: [], cables: [], cablesRattaches: false });
  const estProtection = SLUGS_PROTECTION.includes(ficheSlug);
  let bloc: ConceptionPourLigne;
  if (estProtection) {
    // Les organes viennent PRÉ-ROUTÉS (`repartirOrganes`) : aucune lecture de
    // libellé ici, donc aucun côté ne peut plus disparaître parce qu'une
    // désignation a changé. Ordre du moteur conservé — c'est celui du schéma.
    bloc = { ...vide(), protections: [...(opts?.organes ?? [])] };
  } else if (ficheSlug === 'cablage') {
    bloc = { ...vide(), cables: conception.cables };
  } else if (
    ficheSlug === 'canadian-solar-710'
    || ficheSlug === 'jinko-710'
    || ficheSlug === 'onduleur-deye-hybride'
    || ficheSlug === 'onduleur-huawei-reseau'
  ) {
    bloc = { ...vide(), chaines: conception.chaines };
  } else {
    return null;
  }
  // Rattachement des câbles orphelins : sous la protection choisie par
  // l'appelant, et seulement s'il y a vraiment des liaisons à montrer.
  if (estProtection && opts?.rattacherCables && conception.cables.length) {
    bloc = { ...bloc, cables: conception.cables, cablesRattaches: true };
  }
  const rien = !bloc.chaines.length && !bloc.protections.length && !bloc.cables.length;
  return rien ? null : bloc;
}

/**
 * Libellé d'une chaîne, dans la langue active. C'est le SEUL des trois qui a
 * besoin de mots (« modules ») — un repère, un calibre, une section et une
 * longueur s'écrivent pareil dans les trois langues. Chaque morceau est OMIS
 * quand la valeur manque : « MPPT 1 » ne devient jamais « MPPT — ».
 */
const CHAINE_MOTS: Record<PropLang, { modules: string; pan: string }> = {
  fr: { modules: 'modules', pan: 'pan' },
  en: { modules: 'modules', pan: 'roof section' },
  ar: { modules: 'لوحاً', pan: 'جهة' },
};

export function chaineLabel(c: ConceptionChaine, lang: PropLang = 'fr'): string {
  const mots = CHAINE_MOTS[lang] || CHAINE_MOTS.fr;
  const parts: string[] = [];
  if (c.nb_modules !== undefined) parts.push(`${formatNumber(c.nb_modules)} ${mots.modules}`);
  if (c.mppt !== undefined) parts.push(`MPPT ${formatNumber(c.mppt)}`);
  if (c.pan !== undefined) parts.push(`${mots.pan} ${formatNumber(c.pan)}`);
  return parts.join(' · ');
}

/**
 * Libellé d'un organe de protection : repère, désignation et calibre tels que
 * le moteur électrique les a posés — donc tels qu'ils sont écrits dans le
 * coffret et sur le schéma, ce que le client peut aller vérifier. Neutre en
 * langue (un repère et un calibre ne se traduisent pas). La QUANTITÉ n'est PAS
 * dans ce libellé : la page l'affiche à part, comme sur les lignes de devis.
 */
export function protectionLabel(o: ConceptionProtection): string {
  return [o.repere, o.designation, o.calibre].filter((v) => !!v).join(' · ');
}

/**
 * Libellé d'une liaison câblée : ce qu'elle relie, sa section, sa longueur.
 * Neutre en langue. Section et longueur sont formatées comme tous les nombres
 * de la page (virgule décimale) ; une valeur absente est OMISE.
 */
export function cableLabel(c: ConceptionCable): string {
  const parts: string[] = [];
  if (c.liaison) parts.push(c.liaison);
  if (c.section_mm2 !== undefined) parts.push(`${formatNumber(c.section_mm2, 2)} mm²`);
  if (c.longueur_m !== undefined) parts.push(`${formatNumber(c.longueur_m, 1)} m`);
  return parts.join(' · ');
}

/**
 * Normalise une réponse d'acceptation backend (succès OU erreur) en un objet
 * stable que le client peut afficher. On reflète le `detail` backend tel quel
 * pour les 400/409/404 ; un succès porte la référence + le nom du signataire.
 */
export interface AcceptResult {
  ok: boolean;
  status: number;
  detail: string;
  reference?: string;
  accepte_par_nom?: string;
}

export function normalizeAcceptResponse(status: number, payload: unknown): AcceptResult {
  const body = (payload ?? {}) as Record<string, unknown>;
  const detail = typeof body.detail === 'string' && body.detail.trim() ? body.detail.trim() : '';
  if (status >= 200 && status < 300) {
    return {
      ok: true,
      status,
      detail: detail || 'Devis accepté.',
      reference: typeof body.reference === 'string' ? body.reference : undefined,
      accepte_par_nom: typeof body.accepte_par_nom === 'string' ? body.accepte_par_nom : undefined,
    };
  }
  // Messages FR de repli par code, si le backend n'a pas fourni de `detail`.
  const fallback =
    status === 404
      ? 'Ce lien de proposition est introuvable ou a expiré.'
      : status === 409
        ? 'Ce devis a déjà été traité.'
        : status === 400
          ? 'La demande est invalide. Vérifiez votre saisie.'
          : 'Une erreur est survenue. Veuillez réessayer.';
  return { ok: false, status, detail: detail || fallback };
}

// ════════════════════════════════════════════════════════════════════════════
// WJ9–WJ16 — élévation « best-in-world » de la proposition client.
//
// DISCIPLINE « ZÉRO CHIFFRE INVENTÉ » : chaque fonction ci-dessous ne produit un
// nombre que (a) lu directement du payload backend, ou (b) calculé par une règle
// documentée à partir de valeurs PRÉSENTES dans le payload, ou (c) une fourchette
// CLAIREMENT libellée « indicative / à confirmer ». Quand aucune source honnête
// n'existe, on renvoie `null` et la page affiche un repli libellé — jamais une
// valeur fabriquée. Économies en autoconsommation (loi 82-21) : aucune promesse
// de revente/injection du surplus.
// ════════════════════════════════════════════════════════════════════════════

// ── Constantes physiques / financières documentées ──────────────────────────

/**
 * WJ9 — Horizon d'analyse des économies cumulées : 25 ans. Durée de vie
 * économique conventionnelle de l'installation retenue pour le calcul (choix
 * prudent), et non un chiffre marketing. La garantie de performance des panneaux
 * posés va en réalité au-delà : linéaire sur 30 ans, ≥ 87,4 % de la puissance
 * initiale à 30 ans (donc ≥ 89,4 % à 25 ans), cf. `src/lib/warranty.ts`.
 */
export const SAVINGS_HORIZON_YEARS = 25;

/**
 * WJ9 — Dérive annuelle de la facture d'électricité (« coût de ne rien faire »).
 * Hypothèse PRUDENTE et libellée : 0 % par défaut (économies à tarif constant).
 * Le calcul de cumul reste honnête même sans inflation tarifaire. Toute hausse
 * réelle ne ferait qu'augmenter l'économie — on ne la promet donc pas.
 *
 * WJ75 — CONFIRMÉ ALIGNÉ avec le backend (lu dans le moteur de devis vendorisé,
 * `apps/ventes/quote_engine/`) : `pricing.py calculate_savings_roi` fixe
 * `eco_a_cumul = economie_opt2` (l'économie ANNUELLE, malgré son nom) SANS
 * aucune dérive tarifaire, et `generate_devis_premium.py` l'utilise comme un
 * TAUX PAR AN pour bâtir sa courbe cumulative sur 26 points (0 à 25 ans) :
 * `CUMUL_A = [-TOTAL_AVEC + eco_a_cumul * y for y in YEARS]` — une simple
 * multiplication linéaire, aucun terme `(1+i)^y`. Le PDF premium et cette page
 * web utilisent donc EXACTEMENT la même hypothèse (0 % d'escalade tarifaire) ;
 * aucun décalage à corriger entre les deux documents. Le nom du champ backend
 * (« cumul ») est trompeur — c'est un TAUX ANNUEL, pas un total déjà cumulé
 * (voir savingsHeadline ci-dessous, qui le multiplie désormais par `years`
 * au lieu de l'afficher tel quel comme un cumul déjà calculé).
 */
export const BILL_INFLATION_RATE = 0;

/**
 * WJ14 — Facteur d'émission du réseau électrique marocain (ONEE), en kg de CO₂
 * évité par kWh solaire autoconsommé. Le mix marocain reste fortement carboné
 * (charbon majoritaire) ; 0,81 kg CO₂/kWh est l'ordre de grandeur publié pour le
 * facteur d'émission moyen du réseau. Constante AFFICHÉE à l'écran.
 */
export const CO2_KG_PER_KWH = 0.81;

/**
 * WJ14 — Équivalent « arbres » : un arbre mûr absorbe ≈ 22 kg de CO₂ par an
 * (ordre de grandeur communément retenu). Constante AFFICHÉE à l'écran.
 */
export const CO2_KG_PER_TREE_YEAR = 22;

/**
 * WJ10 — Taux annuel INDICATIF d'un éco-prêt vert au Maroc (TAEG approximatif).
 * Aucune offre n'est contractuelle ici : la mensualité affichée est une simple
 * illustration « à confirmer » auprès de la banque. Fourchette ~7–9 %.
 */
export const GREEN_LOAN_RATE_LOW = 0.07;
export const GREEN_LOAN_RATE_HIGH = 0.09;

/** WJ10 — Durée INDICATIVE d'un éco-prêt vert (mois). 7 ans. */
export const GREEN_LOAN_MONTHS = 84;

// ── WJ15 · Fenêtre de validité honnête ───────────────────────────────────────

export interface ValidityWindow {
  /** Date d'échéance affichable (libellé FR « JJ mois AAAA »), ou null. */
  label: string | null;
  /** Vrai quand la date vient RÉELLEMENT du backend (sinon repli libellé). */
  fromBackend: boolean;
  /** Vrai si l'échéance est déjà passée (offre expirée). */
  expired: boolean;
}

const MONTHS_FR = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
];

/**
 * Parse une date backend en `Date` UTC midi (robuste aux fuseaux). Accepte ISO
 * `YYYY-MM-DD` et FR `JJ/MM/AAAA`. Renvoie `null` si non parsable.
 */
export function parseBackendDate(raw: string | null | undefined): Date | null {
  if (!raw || typeof raw !== 'string') return null;
  const s = raw.trim();
  let y = 0, m = 0, d = 0;
  const iso = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
  const fr = /^(\d{1,2})\/(\d{1,2})\/(\d{4})/.exec(s);
  if (iso) {
    y = +iso[1]; m = +iso[2]; d = +iso[3];
  } else if (fr) {
    d = +fr[1]; m = +fr[2]; y = +fr[3];
  } else {
    return null;
  }
  if (m < 1 || m > 12 || d < 1 || d > 31) return null;
  const dt = new Date(Date.UTC(y, m - 1, d, 12, 0, 0));
  if (Number.isNaN(dt.getTime())) return null;
  return dt;
}

/** Formate une `Date` en « 15 juillet 2026 » (FR). */
export function formatFrenchDate(dt: Date): string {
  return `${dt.getUTCDate()} ${MONTHS_FR[dt.getUTCMonth()]} ${dt.getUTCFullYear()}`;
}

/**
 * WJ15 — Résout la fenêtre de validité du devis SANS jamais inventer une date.
 *  - Si le backend fournit `date_validite` (racine ou `quote`), on l'affiche
 *    telle quelle (`fromBackend: true`), en signalant si elle est déjà passée.
 *  - Sinon, repli HONNÊTE : `label = null` + `fromBackend: false` → la page
 *    affiche une mention libellée (« sous réserve de validité ») et NON un
 *    compte-à-rebours. `now` est injectable pour les tests (déterminisme).
 */
export function resolveValidity(
  p: Pick<ProposalResponse, 'date_validite' | 'quote'>,
  now: Date = new Date(),
): ValidityWindow {
  const raw = p.date_validite ?? p.quote?.date_validite ?? null;
  const dt = parseBackendDate(raw);
  if (!dt) return { label: null, fromBackend: false, expired: false };
  const expired = dt.getTime() < now.getTime();
  return { label: formatFrenchDate(dt), fromBackend: true, expired };
}

/**
 * Date de RESYNCHRONISATION APRÈS ENVOI, formatée FR (« 18 août 2026 »), ou
 * `null`. Le devis a été envoyé au client avec un PDF, puis resynchronisé
 * (correction d'un prix catalogue) : la page rend les lignes en direct, elle
 * peut donc montrer un total différent de la pièce jointe reçue. La page
 * l'annonce alors près du total.
 *
 * Défensif de bout en bout : clé absente, `null`, type inattendu ou date non
 * parsable ⇒ `null` ⇒ AUCUNE ligne rendue. Jamais une date fabriquée, jamais
 * une mention sur un devis qui n'a pas bougé.
 */
export function resyncApresEnvoi(
  p: Pick<ProposalResponse, 'resync_apres_envoi'>,
): string | null {
  const brut = p?.resync_apres_envoi;
  if (!brut || typeof brut !== 'object') return null;
  const raw = (brut as { date?: unknown }).date;
  const dt = parseBackendDate(typeof raw === 'string' ? raw : null);
  return dt ? formatFrenchDate(dt) : null;
}

// ── WJ42 · Horodatage de signature localisé (FR/AR/EN) ───────────────────────

/** Langue active de la page proposition (bascule FR/EN/AR — WJ17/WJ43). */
export type PropLang = 'fr' | 'en' | 'ar';

const STAMP_LOCALE: Record<PropLang, string> = {
  fr: 'fr-MA',
  en: 'en-GB',
  ar: 'ar-MA',
};

/**
 * WJ42 — Formate un horodatage de signature dans la langue active. Auparavant
 * la page injectait toujours `frenchStamp()` en texte brut dans `#sign-stamp`,
 * ce qui (a) écrasait le markup dual-node d'i18n et (b) affichait une date
 * française même en mode arabe/anglais. Cette fonction est PURE (testable sans
 * DOM) : le composant appelant doit la ré-invoquer à chaque bascule de langue
 * ET la ré-enregistrer via le registre `propI18nBusyLabels` (même discipline
 * que `renderSubmitLabel`), jamais un remplacement ponctuel non ré-inscrit.
 */
export function localizedStamp(d: Date, lang: PropLang): string {
  const locale = STAMP_LOCALE[lang] ?? STAMP_LOCALE.fr;
  try {
    return d.toLocaleString(locale, { dateStyle: 'long', timeStyle: 'short' });
  } catch {
    return d.toLocaleString('fr-FR');
  }
}

/** WJ42 — Libellé « Réf. … · signature horodatée le … » dans les 3 langues. */
export function signStampLabel(reference: string, d: Date, lang: PropLang): string {
  const stamp = localizedStamp(d, lang);
  if (lang === 'ar') {
    return `المرجع ${reference} · تم توقيعه بتاريخ ${stamp} (بتوقيت جهازكم).`;
  }
  if (lang === 'en') {
    return `Ref. ${reference} · signature timestamped on ${stamp} (your device's local time).`;
  }
  return `Réf. ${reference} · signature horodatée le ${stamp} (heure de votre appareil).`;
}

// ── WJ9 · Argent dans le temps (cumul 25 ans + cadrage mensuel) ──────────────

export interface SavingsHeadline {
  /** Économie annuelle (MAD/an) — backend `eco_*_ann`. */
  annual: number | null;
  /** Économie cumulée sur l'horizon (MAD) — dérivée du TAUX annuel `eco_a_cumul` (× years) ou du calcul local. */
  cumulative: number | null;
  /** Horizon retenu (ans). */
  years: number;
  /** Économie mensuelle équivalente (MAD/mois) ≈ annuel / 12. */
  monthly: number | null;
  /** Retour sur investissement (déjà formaté). */
  payback: string | null;
  /** Vrai si le TAUX vient directement du backend (`eco_a_cumul`) plutôt que du fallback `annual`. */
  cumulativeFromBackend: boolean;
}

/**
 * WJ9/WJ75 — Construit le bandeau « money over time » de l'option recommandée.
 *
 *  - `annual` : économie annuelle backend (`eco_*_ann`).
 *  - `cumulative` : sur l'horizon (`years`, 25 ans par défaut).
 *
 * WJ75 — CORRECTIF : malgré son nom, le champ backend `eco_a_cumul`
 * (`apps/ventes/quote_engine/pricing.py calculate_savings_roi`) n'est PAS déjà
 * un total cumulé — c'est le même chiffre que l'économie ANNUELLE
 * (`eco_a_cumul == eco_a_ann` côté backend), utilisé par le moteur PDF comme un
 * TAUX PAR AN : `generate_devis_premium.py` construit sa courbe cumulative par
 * `CUMUL_A = [-total + eco_a_cumul * y for y in YEARS]` (multiplication
 * linéaire, AUCUNE dérive tarifaire — 0 % d'escalade, comme `BILL_INFLATION_RATE`
 * ci-dessus). Avant ce correctif, cette fonction affichait `eco_a_cumul`
 * DIRECTEMENT comme si le backend avait déjà fait `× 25` — ce qui montrait la
 * valeur d'UNE SEULE ANNÉE sous le libellé « cumul sur 25 ans » (sous-estimation
 * ≈25× du chiffre le plus visible de la page). Le calcul respecte maintenant la
 * MÊME hypothèse que le PDF (taux annuel backend × horizon, 0 % d'escalade) —
 * les deux documents sont désormais alignés, jamais un cumul sur 25 ans qui
 * n'est en réalité qu'un an. Le repli local (sans backend) applique la même
 * discipline (`BILL_INFLATION_RATE`, 0 % par défaut) à `annual`. On NE calcule
 * jamais sans un taux/annuel positif présent.
 *  - `monthly` : annuel / 12 (simple cadrage de lecture, pas un nouveau chiffre).
 */
export function savingsHeadline(
  p: ProposalResponse,
  opt: OptionKey,
  years: number = SAVINGS_HORIZON_YEARS,
): SavingsHeadline {
  const annualRaw = opt === 'avec_batterie' ? p.quote?.eco_a_ann : p.quote?.eco_s_ann;
  const annual = typeof annualRaw === 'number' && Number.isFinite(annualRaw) && annualRaw > 0
    ? annualRaw : null;
  const paybackRaw = opt === 'avec_batterie' ? p.quote?.roi_a : p.quote?.roi_s;

  // WJ75 — `eco_a_cumul` est un TAUX ANNUEL (voir la note ci-dessus), jamais un
  // total déjà cumulé : on le multiplie par `years`, exactement comme le fait
  // le moteur PDF (`eco_a_cumul * y`), au lieu de l'afficher tel quel.
  const backendRate = p.quote?.eco_a_cumul;
  const hasBackendRate = typeof backendRate === 'number' && Number.isFinite(backendRate) && backendRate > 0;
  const rate = hasBackendRate ? backendRate : annual;
  let cumulative: number | null = null;
  const cumulativeFromBackend = hasBackendRate;
  if (rate !== null && years > 0) {
    // Série honnête : taux constant (0 % d'escalade, comme le PDF) sauf si
    // BILL_INFLATION_RATE est un jour changé — alors Σ taux·(1+i)^k, k=0..years-1.
    const i = BILL_INFLATION_RATE;
    cumulative = i === 0
      ? rate * years
      : Math.round((rate * (Math.pow(1 + i, years) - 1)) / i);
  }

  return {
    annual,
    cumulative,
    years,
    monthly: annual !== null ? Math.round(annual / 12) : null,
    payback: formatPayback(paybackRaw),
    cumulativeFromBackend,
  };
}

// ── PVCOV (fondateur 2026-08-18) · La synthèse page 1 du PDF, SERVIE ────────

/** Nombre fini servi par le backend, sinon `null` (jamais un 0 fabriqué). */
function servedNumber(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

/** Le « −N % » + la facture avant/après, tels que servis (aucun modèle local). */
export interface SyntheseEconomies {
  /** Réduction de facture en % — backend `pct_cut`, affiché « −N % ». */
  pctCut: number;
  /** Facture annuelle AVANT solaire (MAD/an) — backend `annual_before`. */
  annuelAvant: number;
  /** Facture annuelle APRÈS solaire (MAD/an) — backend `annual_after`. */
  annuelApres: number;
  /** Les mêmes montants ramenés au mois (÷ 12 : changement d'unité, pas un calcul). */
  mensuelAvant: number;
  mensuelApres: number;
}

/**
 * PVCOV — Lit la synthèse d'économies que le moteur a calculée pour la PAGE 1
 * DU PDF (`residential/renderer.synthese_economies`, servie telle quelle par
 * `proposal_data`).
 *
 * DISCIPLINE (ordre fondateur du 18/08) : la page CONSOMME ces nombres, elle ne
 * les reconstruit pas. Aucun barème, aucun tarif, aucune hypothèse
 * d'autoconsommation ici — la SEULE arithmétique autorisée est la division par
 * 12 pour la lecture mensuelle. Conséquence voulue : PDF et lien client
 * affichent le même chiffre, et une correction du moteur se propage seule.
 *
 * Renvoie `null` — donc « le bloc ne rend rien » — dès qu'un des trois champs
 * manque (devis hors forme résidentielle : le backend sert `null`), que la
 * facture d'avant n'est pas strictement positive, ou que le payload est
 * incohérent (facture d'après négative ou supérieure à celle d'avant) : on se
 * tait plutôt que d'annoncer une facture qui augmente.
 */
export function syntheseEconomies(p: ProposalResponse): SyntheseEconomies | null {
  const pctCut = servedNumber(p?.pct_cut);
  const avant = servedNumber(p?.annual_before);
  const apres = servedNumber(p?.annual_after);
  if (pctCut === null || avant === null || apres === null) return null;
  if (avant <= 0 || apres < 0 || apres > avant) return null;
  return {
    pctCut,
    annuelAvant: avant,
    annuelApres: apres,
    mensuelAvant: Math.round(avant / 12),
    mensuelApres: Math.round(apres / 12),
  };
}

/** La couverture solaire servie (la donut « ÉNERGIE SOLAIRE »). */
export interface CouvertureSolaire {
  /** Pourcentage de couverture — backend `coverage_pct`, déjà borné 1..100. */
  pct: number;
  /** Consommation dérivée de la facture plutôt que mesurée → « (estimation) ». */
  estimated: boolean;
}

/**
 * PVCOV — Lit la couverture solaire du MÊME calcul que la donut de la page 1 du
 * PDF. Le moteur borne déjà la valeur à 1..100 : la page affiche donc 100 %
 * UNIQUEMENT quand le moteur dit production ≥ consommation, jamais par un
 * arrondi local. Rien n'est recalculé ici — pas de production, pas de
 * consommation, pas de ratio.
 *
 * `null` (donut masquée) quand le backend ne sert pas la valeur, ou qu'elle
 * sort de la plage servie 1..100 (payload incohérent : se taire plutôt que
 * dessiner un anneau faux).
 */
export function couvertureSolaire(p: ProposalResponse): CouvertureSolaire | null {
  const pct = servedNumber(p?.coverage_pct);
  if (pct === null || pct <= 0 || pct > 100) return null;
  return { pct, estimated: p?.coverage_estimated === true };
}

// ── CJ2b (21/08/2026) · Économies MENSUELLES réelles, contre la courbe ──────
// Le fondateur : « on ne voit ni l'économie calculée réelle ni la donnée PVGIS
// — elles doivent servir à COMPARER la courbe de consommation ». `courbes_
// journalieres` (dayProfiles.ts) donne déjà la FORME ; cette clé additive
// sœur donne l'ARGENT, mois par mois, pour que le client voie production,
// consommation ET économie dans le même chapitre.

/** Douze lectures MAD/mois (index 0 = janvier), comparées au graphe production/consommation. */
export interface EconomiesMensuelles {
  /** 12 valeurs MAD économisées par mois, SANS batterie. */
  sans: number[];
  /**
   * 12 valeurs MAD économisées par mois AVEC batterie — `null` quand l'option
   * n'est pas VENDABLE à ce devis (jamais un zéro déguisé en absence d'offre).
   */
  avec: number[] | null;
  /** Somme annuelle SANS batterie (MAD/an). */
  totalSans: number;
  /** Somme annuelle AVEC batterie (MAD/an) — `null` quand `avec` l'est. */
  totalAvec: number | null;
  devise: string;
  /** Provenance du calcul — `'estimation'` ⇒ la page DOIT l'étiqueter. */
  modele: 'horaire' | 'factures' | 'estimation';
  estimation: boolean;
  /** Phrase source, prête à afficher TELLE QUELLE (jamais réécrite). */
  note: string;
}

/** Exactement 12 nombres finis, sinon `null` (jamais un tableau à moitié lu). */
function finiteMonthlyArray(v: unknown): number[] | null {
  if (!Array.isArray(v) || v.length !== 12) return null;
  const out = v.map((x) => Number(x));
  return out.every((n) => Number.isFinite(n)) ? out : null;
}

/**
 * CJ2b — Lit `economies_mensuelles`, clé ADDITIVE au NIVEAU RACINE du payload
 * (sœur de `courbes_journalieres`, jamais dans `quote`) : le moteur horaire
 * compare production PVGIS et consommation réelle heure par heure et sert le
 * résultat déjà en MAD, mois par mois. ABSENTE tant que le calcul n'est pas
 * servable (décision fondateur Q6 : on omet, on n'approxime jamais) ⇒ `null`
 * ⇒ la page ne rend RIEN, jamais un bloc à zéro. `avec`/`totalAvec` restent
 * `null` quand l'option batterie n'est pas VENDABLE à ce devis — jamais une
 * figure batterie posée sur un devis qui n'en porte pas.
 *
 * Non typée dans `ProposalResponse` (comme `courbes_journalieres`) : lue
 * défensivement via cast, exactement la même discipline que `dayProfiles.
 * parseDailyCurves`.
 */
export function economiesMensuelles(p: ProposalResponse | null | undefined): EconomiesMensuelles | null {
  const raw = (p as unknown as Record<string, unknown> | null | undefined)?.economies_mensuelles;
  if (!raw || typeof raw !== 'object') return null;
  const r = raw as Record<string, unknown>;
  const sans = finiteMonthlyArray(r.sans);
  const totalSans = servedNumber(r.total_sans);
  if (!sans || totalSans === null) return null;
  const avecRaw = finiteMonthlyArray(r.avec);
  const totalAvecRaw = servedNumber(r.total_avec);
  const hasAvec = avecRaw !== null && totalAvecRaw !== null;
  const modeleRaw = typeof r.modele === 'string' ? r.modele : '';
  const modele: EconomiesMensuelles['modele'] =
    modeleRaw === 'horaire' || modeleRaw === 'factures' ? modeleRaw : 'estimation';
  return {
    sans,
    avec: hasAvec ? avecRaw : null,
    totalSans,
    totalAvec: hasAvec ? totalAvecRaw : null,
    devise: typeof r.devise === 'string' && r.devise ? r.devise : 'MAD',
    modele,
    // FAIL-SAFE, PAS FAIL-OPEN. `r.estimation === true` seul retombait sur
    // `false` — « c'est mesuré » — dès que le drapeau manquait ou arrivait
    // malformé : le pire défaut possible sous la règle « zéro chiffre
    // inventé », puisqu'il présente un modèle comme une mesure. Un chiffre
    // n'échappe à l'étiquette « estimation » que lorsque le serveur affirme
    // DEUX choses : le modèle horaire, et l'absence d'estimation. Même règle
    // que celle appliquée côté serveur (`_economies_mensuelles_publiques`) —
    // au moindre doute, on étiquette.
    estimation: r.estimation === true || modele !== 'horaire',
    note: typeof r.note === 'string' ? r.note : '',
  };
}

/**
 * CJ2b — LE SEUL SIGNAL QUI PEUT RETIRER LA CASE BATTERIE DU GRAPHE.
 *
 * Quand le bloc `economies_mensuelles` EST servi mais dit explicitement qu'il
 * n'existe pas de figure « avec batterie » (`avec === null`), l'option n'est pas
 * VENDABLE à ce devis : aucun bouton, aucune figure, jamais un zéro déguisé.
 *
 * MAIS un bloc ABSENT (`null` — le cas de très loin le plus courant, et celui de
 * tous les devis d'avant CJ2b) n'affirme RIEN : il ne doit donc rien interdire.
 * C'est exactement l'inversion qui a fait disparaître la case sur un devis
 * batterie-seule (le backend ne servait pas `avec`), pour la troisième fois.
 * Cette fonction existe pour que l'invariant « absent ⇒ n'interdit rien » soit
 * ÉPINGLÉ par un test, plutôt que confié à un `&&` au fil de la page.
 */
export function economiesInterdisentBatterie(
  eco: Pick<EconomiesMensuelles, 'avec'> | null | undefined,
): boolean {
  return !!eco && eco.avec === null;
}

// ── WJ14 · Impact environnemental humain (CO₂ ≈ arbres) ──────────────────────

export interface EnvironmentalImpact {
  /** kg de CO₂ évités par an (production × facteur réseau). */
  co2KgPerYear: number;
  /** Tonnes de CO₂ évitées par an (arrondi 1 décimale). */
  co2TonnesPerYear: number;
  /** Équivalent en arbres « plantés » (absorption annuelle). */
  trees: number;
  /** Constantes affichées pour la transparence. */
  kgPerKwh: number;
  kgPerTreeYear: number;
}

/**
 * WJ14 — Calcule l'impact environnemental À PARTIR de la production annuelle
 * backend (`prod_kwh`). Renvoie `null` si la production est absente/nulle (aucun
 * chiffre inventé). Les constantes sont retournées pour être affichées à côté.
 */
export function environmentalImpact(
  prodKwh: number | null | undefined,
  kgPerKwh: number = CO2_KG_PER_KWH,
  kgPerTreeYear: number = CO2_KG_PER_TREE_YEAR,
): EnvironmentalImpact | null {
  const prod = typeof prodKwh === 'number' && Number.isFinite(prodKwh) && prodKwh > 0 ? prodKwh : null;
  if (prod === null) return null;
  const co2KgPerYear = prod * kgPerKwh;
  return {
    co2KgPerYear: Math.round(co2KgPerYear),
    co2TonnesPerYear: Math.round((co2KgPerYear / 1000) * 10) / 10,
    trees: Math.round(co2KgPerYear / kgPerTreeYear),
    kgPerKwh,
    kgPerTreeYear,
  };
}

// ── WJ10 · Comparatif de financement (cash vs éco-prêt indicatif) ────────────

export interface FinancingComparison {
  /** Prix comptant TTC (backend). */
  cash: number;
  /** Mensualité indicative basse (taux bas), MAD/mois. */
  monthlyLow: number;
  /** Mensualité indicative haute (taux haut), MAD/mois. */
  monthlyHigh: number;
  /** Durée indicative (mois). */
  months: number;
  /**
   * Facture mensuelle actuelle estimée (backend `factures_mensuelles` moyenne),
   * pour l'accroche « mensualité < votre facture ». null si indisponible.
   */
  currentBillMonthly: number | null;
  /** Vrai si la mensualité basse est strictement < facture actuelle. */
  beatsBill: boolean;
}

/**
 * Mensualité d'un prêt amortissable (formule standard). `rate` est ANNUEL.
 * Renvoie un entier MAD. Taux 0 → simple division.
 */
export function loanMonthlyPayment(principal: number, annualRate: number, months: number): number {
  if (principal <= 0 || months <= 0) return 0;
  const r = annualRate / 12;
  if (r === 0) return Math.round(principal / months);
  const factor = (r * Math.pow(1 + r, months)) / (Math.pow(1 + r, months) - 1);
  return Math.round(principal * factor);
}

/**
 * WJ10 — Comparatif cash vs éco-prêt INDICATIF. Le prix comptant vient du
 * backend (TTC de l'option). Les mensualités sont une fourchette CLAIREMENT
 * indicative (taux/durée non contractuels) — la page les libelle « à confirmer ».
 * `currentBillMonthly` se déduit de `factures_mensuelles` backend (moyenne) si
 * présent, sinon null (la page masque alors l'accroche comparative).
 */
export function financingComparison(
  p: ProposalResponse,
  opt: OptionKey,
): FinancingComparison | null {
  const cash = optionTtc(p, opt);
  if (!Number.isFinite(cash) || cash <= 0) return null;
  const monthlyHigh = loanMonthlyPayment(cash, GREEN_LOAN_RATE_HIGH, GREEN_LOAN_MONTHS);
  const monthlyLow = loanMonthlyPayment(cash, GREEN_LOAN_RATE_LOW, GREEN_LOAN_MONTHS);

  const bills = p.quote?.factures_mensuelles;
  let currentBillMonthly: number | null = null;
  if (Array.isArray(bills) && bills.length > 0) {
    const valid = bills.filter((v) => typeof v === 'number' && Number.isFinite(v) && v > 0);
    if (valid.length > 0) {
      currentBillMonthly = Math.round(valid.reduce((a, b) => a + b, 0) / valid.length);
    }
  }

  return {
    cash,
    monthlyLow,
    monthlyHigh,
    months: GREEN_LOAN_MONTHS,
    currentBillMonthly,
    beatsBill: currentBillMonthly !== null && monthlyLow < currentBillMonthly,
  };
}

// ── WJ53 · « Payer comptant / paiement échelonné » — toggle interactif ───────

/**
 * WJ53 — Choix de durées (mois) proposés par le toggle « paiement échelonné ».
 * Volontairement COURT (pas de simulation de crédit bancaire, voir WJ10/WJ32
 * pour l'éco-prêt) : c'est une simple division indicative du TTC, pour un
 * client qui négocie un paiement en plusieurs fois DIRECTEMENT avec Taqinor —
 * jamais présentée comme une offre bancaire.
 */
export const INSTALLMENT_MONTH_OPTIONS = [3, 6, 12, 24] as const;
export type InstallmentMonths = (typeof INSTALLMENT_MONTH_OPTIONS)[number];

export interface InstallmentSplit {
  /** Prix comptant TTC (backend, inchangé). */
  cashTtc: number;
  /** Nombre de mois choisi. */
  months: InstallmentMonths;
  /** TTC ÷ mois, arrondi au MAD — AUCUN taux/intérêt ajouté (simple division). */
  monthly: number;
}

/**
 * WJ53 — Calcule la mensualité INDICATIVE d'un paiement échelonné sur `months`
 * mois, par simple division du TTC (aucun taux inventé, aucun frais). Renvoie
 * `null` quand le TTC n'est pas un prix réel positif (même garde-fou zéro-total
 * que `hasRealPrice`) — jamais un chiffre calculé sur un montant fabriqué.
 */
export function installmentSplit(
  cashTtc: number,
  months: InstallmentMonths = 12,
): InstallmentSplit | null {
  if (!Number.isFinite(cashTtc) || cashTtc <= 0) return null;
  const safeMonths = INSTALLMENT_MONTH_OPTIONS.includes(months) ? months : 12;
  return {
    cashTtc,
    months: safeMonths,
    monthly: Math.round(cashTtc / safeMonths),
  };
}

// ── WJ12 · Contact intégré (WhatsApp prérempli avec la réf devis) ────────────

/**
 * Numéro WhatsApp TAQINOR (format international sans « + », tel que requis par
 * wa.me). Valeur RÉELLE confirmée (= `WHATSAPP_LEADS` de lib/nap.ts) ; dupliquée
 * ici pour garder ce module autonome (importable côté navigateur sans dépendance).
 */
export const TAQINOR_WHATSAPP = '212661850410';

/**
 * WJ12 — Construit un deep-link wa.me prérempli citant la RÉFÉRENCE du devis.
 * `phone` peut surcharger le numéro par défaut. Le message est encodé URL.
 */
export function whatsappLink(reference: string, phone: string = TAQINOR_WHATSAPP): string {
  const digits = (phone || TAQINOR_WHATSAPP).replace(/[^\d]/g, '') || TAQINOR_WHATSAPP;
  const ref = (reference || '').trim();
  const msg = ref
    ? `Bonjour, j'ai une question sur ma proposition Taqinor (réf. ${ref}).`
    : 'Bonjour, j\'ai une question sur ma proposition Taqinor.';
  return `https://wa.me/${digits}?text=${encodeURIComponent(msg)}`;
}

/**
 * WJ56 — Partage du lien TOKENISÉ de LA PROPOSITION ELLE-MÊME (pas une question
 * pour Taqinor) : le client transmet sa proposition à un conjoint/co-décideur
 * SANS rien ressaisir. Différent de `whatsappLink` (qui adresse un message AU
 * numéro Taqinor) — ici `wa.me/` sans numéro ouvre le compositeur WhatsApp
 * générique (le client choisit lui-même le destinataire). `pageUrl` est
 * l'URL COMPLÈTE de la page courante (avec le token), jamais reconstruite.
 */
export function whatsappShareLink(pageUrl: string, reference: string): string {
  const url = (pageUrl || '').trim();
  const ref = (reference || '').trim();
  const msg = ref
    ? `Voici ma proposition solaire Taqinor (réf. ${ref}) : ${url}`
    : `Voici ma proposition solaire Taqinor : ${url}`;
  return `https://wa.me/?text=${encodeURIComponent(msg)}`;
}

// ── W343 · « Partager avec un proche » — composeur de parrainage post-signature ─
//
// DISTINCT de whatsappShareLink (WJ56) : WJ56 partage LA MÊME PROPOSITION avec
// un co-décideur du MÊME foyer (avant signature, pour décider ensemble). W343
// partage le programme de PARRAINAGE (/parrainage, W338) avec un PROCHE
// DIFFÉRENT, une fois le devis SIGNÉ (le moment de satisfaction maximale) —
// un lien vers un NOUVEAU projet solaire pour ce proche, pas vers ce devis-ci.
//
// ZÉRO CHANGEMENT BACKEND (même discipline que /parrainage, W338) : le
// `<code>` du lien tagué est simplement la RÉFÉRENCE du devis déjà signé —
// aucun code de parrainage n'existe côté backend aujourd'hui, donc on réutilise
// un identifiant déjà réel plutôt que d'en inventer un nouveau. L'ERP peut
// filtrer ses leads entrants sur `utm_source=parrainage` et retrouver le
// parrain via `utm_campaign` (= la référence de SON devis), exactement comme
// documenté sur /parrainage.astro.

/**
 * W343 — Construit l'URL de /parrainage TAGUÉE avec la référence du client qui
 * vient de signer, dans le MÊME format que documenté sur /parrainage.astro
 * (`utm_source=parrainage&utm_campaign=<code>`). `siteOrigin` est l'origine
 * RÉELLE servie (ex. `Astro.url.origin`), jamais reconstruite en dur.
 */
export function referralTaggedLink(siteOrigin: string, reference: string): string {
  const origin = (siteOrigin || 'https://taqinor.ma').replace(/\/+$/, '');
  const code = (reference || '').trim();
  const qs = code ? `?utm_source=parrainage&utm_campaign=${encodeURIComponent(code)}` : '?utm_source=parrainage';
  return `${origin}/parrainage${qs}`;
}

/**
 * W343 — Compositeur WhatsApp « Partager avec un proche » : `wa.me/` SANS
 * numéro (même mécanique que whatsappShareLink) ouvre le compositeur générique
 * — le client choisit lui-même à qui l'envoyer. Le message pointe vers le lien
 * de parrainage TAGUÉ (referralTaggedLink), jamais vers la proposition elle-même.
 */
export function whatsappReferralLink(siteOrigin: string, reference: string): string {
  const url = referralTaggedLink(siteOrigin, reference);
  const msg = `J'ai fait installer mes panneaux solaires avec Taqinor — si ça vous intéresse, voici le lien : ${url}`;
  return `https://wa.me/?text=${encodeURIComponent(msg)}`;
}

/**
 * WJ85 — Intention du point de contact « au moindre doute » (avant signature).
 * `discuss` (« Discuter sur WhatsApp ») et `question` (« Poser une question »)
 * pointaient auparavant vers le MÊME `whatsappLink(reference)`, un seul message
 * générique — deux boutons qui font la même chose lisent comme du remplissage.
 * `voice` couvre l'invitation à une note vocale (canal WhatsApp natif, plus
 * rapide à envoyer qu'un texte pour beaucoup de clients).
 */
export type WhatsappIntent = 'discuss' | 'question' | 'voice';

/**
 * WJ85 — Construit un deep-link wa.me avec un PRÉREMPLISSAGE distinct par
 * intention (toujours citant la référence quand présente, même discipline que
 * `whatsappLink`). `phone` peut surcharger le numéro par défaut.
 */
export function whatsappLinkForIntent(
  reference: string,
  intent: WhatsappIntent,
  phone: string = TAQINOR_WHATSAPP,
): string {
  const digits = (phone || TAQINOR_WHATSAPP).replace(/[^\d]/g, '') || TAQINOR_WHATSAPP;
  const ref = (reference || '').trim();
  const refSuffix = ref ? ` (réf. ${ref})` : '';
  const messages: Record<WhatsappIntent, string> = {
    discuss: `Bonjour, je voudrais discuter de ma proposition Taqinor${refSuffix} avant de signer.`,
    question: `Bonjour, j'ai une question précise sur ma proposition Taqinor${refSuffix}.`,
    voice: `Bonjour, je vous envoie une note vocale au sujet de ma proposition Taqinor${refSuffix}.`,
  };
  const msg = messages[intent] ?? messages.question;
  return `https://wa.me/${digits}?text=${encodeURIComponent(msg)}`;
}

// ── WJ11 · Payload d'acceptation enrichi (rétro-compatible) ──────────────────

export interface SignSignatureMeta {
  /** Image PNG de la signature manuscrite (data URL), ou chaîne vide. */
  signature_data_url?: string;
  /** Consentement explicite à la signature électronique. */
  consent_esign?: boolean;
  /** Horodatage côté client (ISO 8601) du moment de la signature. */
  signed_at_client?: string;
  /**
   * WJ87 — Nom facultatif de la personne/du foyer au nom de qui le signataire
   * agit (ex. « mes parents », « mon foyer »). Le signataire enregistré reste
   * TOUJOURS `nom` (champ de base) ; ce champ est une précision ADDITIVE,
   * jamais un remplacement — un backend qui l'ignore continue de fonctionner
   * exactement comme avant.
   */
  on_behalf_of?: string;
  /**
   * WJ108 — code OTP à 6 chiffres (backend `apps/ventes/services.py
   * validate_esign_otp`, toggle `ESIGN_OTP_ENABLED`). Omis quand vide : un
   * backend/toggle OFF ignore silencieusement ce champ (comportement
   * inchangé), un backend/toggle ON qui n'a rien reçu répond avec le message
   * « code requis » que `isOtpRequiredMessage` reconnaît plus bas.
   */
  otp_code?: string;
}

/**
 * WJ11 — Étend `buildAcceptBody` avec des champs OPTIONNELS que le backend peut
 * ignorer sans casser le contrat existant (`nom` + `option?` restent la base).
 * Aucun champ obligatoire n'est ajouté — un backend non mis à jour fonctionne
 * exactement comme avant.
 */
export function buildAcceptBodyRich(
  form: SignFormState,
  twoOptions: boolean,
  meta: SignSignatureMeta = {},
): AcceptRequestBody & SignSignatureMeta {
  const body: AcceptRequestBody & SignSignatureMeta = buildAcceptBody(form, twoOptions);
  if (typeof meta.signature_data_url === 'string' && meta.signature_data_url) {
    body.signature_data_url = meta.signature_data_url;
  }
  if (meta.consent_esign === true) body.consent_esign = true;
  if (typeof meta.signed_at_client === 'string' && meta.signed_at_client) {
    body.signed_at_client = meta.signed_at_client;
  }
  // WJ87 — omis quand vide/absent (jamais une chaîne vide envoyée au backend).
  if (typeof meta.on_behalf_of === 'string' && meta.on_behalf_of.trim()) {
    body.on_behalf_of = meta.on_behalf_of.trim();
  }
  // WJ108 — idem : omis quand vide (jamais un champ vide envoyé sans raison).
  if (typeof meta.otp_code === 'string' && meta.otp_code.trim()) {
    body.otp_code = meta.otp_code.trim();
  }
  return body;
}

// ── WJ108 · OTP e-signature (backend toggle ESIGN_OTP_ENABLED, latent) ───────
//
// Le backend (`apps/ventes/services.py validate_esign_otp`) répond aux 3
// messages FR EXACTS ci-dessous selon l'état de l'OTP — AUCUN flag structuré
// (type `otp_required: true`) n'accompagne ces messages aujourd'hui (voir
// `apps/ventes/public_views.py proposal_accept` : un simple `{'detail': ...}`
// en 400, indiscernable structurellement d'une autre erreur de validation).
// Reconnaître le besoin d'OTP passe donc PAR CONTENU DE MESSAGE — fragile
// (un futur changement de libellé backend le casserait silencieusement) mais
// c'est le seul signal disponible sans modification côté serveur. Tant que
// ESIGN_OTP_ENABLED reste OFF (comportement par défaut), ces messages ne sont
// jamais renvoyés : cette détection reste un pur no-op aujourd'hui.

const OTP_REQUIRED_MESSAGES = [
  'Un code de confirmation est requis. Demandez-le via le bouton « Envoyer le code ».',
  'Le code de confirmation a expiré ou n\'a pas été demandé. Redemandez un nouveau code.',
  'Code de confirmation incorrect. Vérifiez le code reçu et réessayez.',
] as const;

/**
 * WJ108 — Vrai si le `detail` d'une réponse 400 de `/accept/` signale un
 * besoin d'OTP (absent/expiré/incorrect) plutôt qu'une autre erreur de
 * validation (nom manquant, devis déjà traité, etc.). `null`/vide → false.
 */
export function isOtpRequiredDetail(detail: string | null | undefined): boolean {
  const d = (detail ?? '').trim();
  if (!d) return false;
  return (OTP_REQUIRED_MESSAGES as readonly string[]).includes(d);
}

/**
 * WJ108 — Vrai UNIQUEMENT pour le message « code incorrect » (distinct de
 * « requis »/« expiré ») — permet d'afficher un message d'erreur ciblé
 * (« code incorrect, réessayez ») plutôt que de redemander un nouveau code à
 * chaque échec.
 */
export function isOtpIncorrectDetail(detail: string | null | undefined): boolean {
  return (detail ?? '').trim() === OTP_REQUIRED_MESSAGES[2];
}

/** Construit l'URL backend de demande d'envoi d'un code OTP (même convention que `/accept/`). */
export function otpRequestEndpoint(apiBase: string, token: string): string {
  const base = (apiBase || 'https://api.taqinor.ma').replace(/\/+$/, '');
  return `${base}/api/django/ventes/proposal/${encodeURIComponent(token)}/otp/`;
}

// ════════════════════════════════════════════════════════════════════════════
// WJ25 — VISIONNEUSE 3D EN LECTURE SEULE du toit du client sur la proposition.
//
// Toute la logique PURE vit ici (parse défensif du `roof_layout` backend,
// conversion lng/lat → ENU mètres, calepinage ILLUSTRATIF des panneaux) — la
// visionneuse Three.js (roofPro11/viewerOnly.ts) ne fait QUE dessiner ce
// modèle. Aucun chiffre affiché au client ne dérive de ce module : c'est de la
// géométrie de rendu (le nombre de panneaux vient du layout serveur, les kWc /
// production / économies viennent du payload quote).
// ════════════════════════════════════════════════════════════════════════════

/** Un obstacle du layout (zone d'exclusion, rectangle axe-aligné N/E). */
export interface RoofLayoutObstacle {
  centerLng: number;
  centerLat: number;
  lengthM: number;
  widthM: number;
}

/** Face d'un panneau dans un pack chevron Est-Ouest (toit plat). */
export type RoofLayoutPanelFace = 'E' | 'W';

/** Un panneau RÉELLEMENT posé (centre ENU mètres, repère `RoofLayoutZoneGeometry.origin`). */
export interface RoofLayoutGeometryPanel {
  cx: number;
  cy: number;
  face?: RoofLayoutPanelFace;
}

/**
 * WJ127 — Géométrie RÉELLE (posée) d'une zone, telle que sérialisée par le
 * builder (`roofPro11/prefill.ts` `serializeLayout`, champ additif `geometry`
 * d'une `SerializedZone` — présent seulement quand un plan de rendu existe
 * pour la zone). C'est le calepinage EXACT conçu dans l'ERP (édition manuelle
 * comprise, cellules réellement occupées — voir PV27), jamais un re-pavage
 * illustratif. `origin` est le repère [lng,lat] des centres `panels[].{cx,cy}`
 * (mètres ENU, x=Est, y=Nord — même convention que `roofPro2.ts`/
 * `estimatorBrainV2.ts`).
 */
export interface RoofLayoutZoneGeometry {
  /** Azimut de FACE du pan (°, 0=N, 90=E, 180=S, 270=O). */
  azimuthDeg: number;
  /** Inclinaison RÉELLE des panneaux posés (°). */
  tiltDeg: number;
  family: 'south' | 'eastwest';
  /** Pose affleurante (toit en pente) ? */
  flush: boolean;
  /**
   * Nombre de panneaux RÉELLEMENT posés (== `panels.length` côté builder,
   * PV27) — le chiffre à afficher partout où « combien de panneaux » compte
   * réellement (légende de zone), DISTINCT de `neededPanels` (la CIBLE
   * dimensionnée par l'étude, qui peut différer du posé).
   */
  count: number;
  /** Origine [lng,lat] du repère ENU des centres de panneaux. */
  origin: [number, number];
  /** Centres ENU (m, repère `origin`) des panneaux RÉELLEMENT posés. */
  panels: RoofLayoutGeometryPanel[];
}

/** Une zone (pan de toit) du layout backend, déjà validée. */
export interface RoofLayoutZone {
  id: string;
  label: string;
  /** Contour [[lng,lat],…] (≥ 3 sommets valides — garanti par le parse). */
  vertices: Array<[number, number]>;
  obstacles: RoofLayoutObstacle[];
  roofType: 'flat' | 'pitched';
  /** Pente (°) — 0 pour un toit plat ; bornée [0, 60]. */
  pitchDeg: number;
  /** Azimut de FACE des panneaux (0–360, 180 = plein sud). */
  facingAzimuthDeg: number;
  /** Nombre de panneaux dimensionné par l'étude (0 = « tout ce qui tient »). */
  neededPanels: number;
  /**
   * WJ127 — Calepinage RÉEL de la zone (présent seulement si le backend l'a
   * fourni ET qu'il est exploitable — voir `parseRoofLayout`). Absent → la
   * visionneuse retombe sur le re-pavage ILLUSTRATIF historique (zéro
   * régression sur un `roof_layout` déjà en base, sans ce champ).
   */
  geometry?: RoofLayoutZoneGeometry;
}

/** Layout de toiture validé (miroir défensif de `serializeLayout` du builder). */
export interface RoofLayout {
  version: number;
  zones: RoofLayoutZone[];
}

function isFiniteNum(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v);
}

/**
 * WJ127 — Parse DÉFENSIF de `zone.geometry` (voir `RoofLayoutZoneGeometry`) :
 * ne jette JAMAIS — toute forme douteuse (champ manquant/invalide, aucun
 * panneau exploitable) renvoie `null`, et la zone reste alors géométriquement
 * valide SANS `geometry` (repli illustratif dans `buildViewerModel`).
 */
function parseZoneGeometry(raw: unknown): RoofLayoutZoneGeometry | null {
  if (!raw || typeof raw !== 'object') return null;
  const g = raw as Record<string, unknown>;
  if (!isFiniteNum(g.azimuthDeg) || !isFiniteNum(g.tiltDeg)) return null;
  const family: 'south' | 'eastwest' | null =
    g.family === 'south' || g.family === 'eastwest' ? g.family : null;
  if (!family) return null;
  const originRaw = g.origin;
  if (!Array.isArray(originRaw) || originRaw.length < 2) return null;
  const olng = originRaw[0];
  const olat = originRaw[1];
  if (!isFiniteNum(olng) || !isFiniteNum(olat)) return null;
  if (olng < -180 || olng > 180 || olat < -90 || olat > 90) return null;
  const panelsRaw = Array.isArray(g.panels) ? g.panels : [];
  const panels: RoofLayoutGeometryPanel[] = [];
  for (const p of panelsRaw) {
    if (!p || typeof p !== 'object') continue;
    const po = p as Record<string, unknown>;
    if (!isFiniteNum(po.cx) || !isFiniteNum(po.cy)) continue;
    const face: RoofLayoutPanelFace | undefined = po.face === 'E' || po.face === 'W' ? po.face : undefined;
    panels.push(face ? { cx: po.cx, cy: po.cy, face } : { cx: po.cx, cy: po.cy });
  }
  if (panels.length === 0) return null;
  // `count` (déclaré par le builder) DOIT normalement valoir panels.length —
  // repli sur panels.length si absent/incohérent (jamais un chiffre inventé,
  // jamais un throw sur une divergence mineure).
  const count = isFiniteNum(g.count) && g.count >= 0 ? Math.floor(g.count) : panels.length;
  return {
    azimuthDeg: ((g.azimuthDeg % 360) + 360) % 360,
    tiltDeg: Math.min(60, Math.max(0, g.tiltDeg)),
    family,
    flush: g.flush === true,
    count,
    origin: [olng, olat],
    panels,
  };
}

/**
 * WJ25 — Parse DÉFENSIF du champ backend `roof_layout` (PLAN2 QJ26, optionnel).
 * Renvoie `null` pour tout ce qui n'est pas un layout exploitable (absent,
 * malformé, aucune zone d'au moins 3 sommets valides) — la page garde alors le
 * héros statique, comportement d'aujourd'hui. Ne jette jamais.
 */
export function parseRoofLayout(raw: unknown): RoofLayout | null {
  if (!raw || typeof raw !== 'object') return null;
  const obj = raw as Record<string, unknown>;
  const zonesRaw = obj.zones;
  if (!Array.isArray(zonesRaw)) return null;
  const zones: RoofLayoutZone[] = [];
  for (const z of zonesRaw) {
    if (!z || typeof z !== 'object') continue;
    const zo = z as Record<string, unknown>;
    const vertsRaw = Array.isArray(zo.vertices) ? zo.vertices : [];
    const vertices: Array<[number, number]> = [];
    for (const v of vertsRaw) {
      if (!Array.isArray(v) || v.length < 2) continue;
      const lng = v[0];
      const lat = v[1];
      if (!isFiniteNum(lng) || !isFiniteNum(lat)) continue;
      if (lng < -180 || lng > 180 || lat < -90 || lat > 90) continue;
      vertices.push([lng, lat]);
    }
    if (vertices.length < 3) continue;
    const obstacles: RoofLayoutObstacle[] = [];
    const obsRaw = Array.isArray(zo.obstacles) ? zo.obstacles : [];
    for (const o of obsRaw) {
      if (!o || typeof o !== 'object') continue;
      const oo = o as Record<string, unknown>;
      if (
        isFiniteNum(oo.centerLng) && isFiniteNum(oo.centerLat) &&
        isFiniteNum(oo.lengthM) && oo.lengthM > 0 &&
        isFiniteNum(oo.widthM) && oo.widthM > 0
      ) {
        obstacles.push({
          centerLng: oo.centerLng,
          centerLat: oo.centerLat,
          lengthM: oo.lengthM,
          widthM: oo.widthM,
        });
      }
    }
    const roofType: 'flat' | 'pitched' = zo.roofType === 'pitched' ? 'pitched' : 'flat';
    const pitchRaw = isFiniteNum(zo.pitchDeg) ? zo.pitchDeg : 0;
    const pitchDeg = roofType === 'pitched' ? Math.min(60, Math.max(0, pitchRaw)) : 0;
    const azRaw = isFiniteNum(zo.facingAzimuthDeg) ? zo.facingAzimuthDeg : 180;
    const facingAzimuthDeg = ((azRaw % 360) + 360) % 360;
    const needed = isFiniteNum(zo.neededPanels) && zo.neededPanels > 0
      ? Math.floor(zo.neededPanels)
      : 0;
    // WJ127 — géométrie RÉELLE optionnelle (jamais requise : un layout ancien,
    // sans ce champ, reste un layout valide — repli illustratif inchangé).
    const geometry = parseZoneGeometry(zo.geometry);
    zones.push({
      id: typeof zo.id === 'string' ? zo.id : `zone-${zones.length + 1}`,
      label: typeof zo.label === 'string' && zo.label.trim() ? zo.label.trim() : `Pan ${zones.length + 1}`,
      vertices,
      obstacles,
      roofType,
      pitchDeg,
      facingAzimuthDeg,
      neededPanels: needed,
      ...(geometry ? { geometry } : {}),
    });
  }
  if (zones.length === 0) return null;
  return { version: isFiniteNum(obj.version) ? obj.version : 1, zones };
}

// ── Constantes de géométrie (dupliquées de roofPro2/roofPro11 — la visionneuse
//    reste autonome ; PURE représentation, aucun chiffre client n'en dérive) ──
/** Grand côté du panneau (m) — même valeur que lib/roofPro2 PANEL2_LONG_M. */
export const VIEWER_PANEL_LONG_M = 2.384;
/** Petit côté du panneau (m) — même valeur que lib/roofPro2 PANEL2_SHORT_M. */
export const VIEWER_PANEL_SHORT_M = 1.303;
/** Retrait de rive (m) — même valeur que lib/roofPro2 PERIMETER_SETBACK_M. */
export const VIEWER_SETBACK_M = 0.5;
/** Épaisseur du panneau (m) — même valeur que lib/roofPro2 PANEL2_THICK_M. */
export const VIEWER_PANEL_THICK_M = 0.033;
/** Jeu entre panneaux d'une MÊME rangée (m) — même valeur que le
 *  `PANEL_SIDE_GAP_M` de lib/estimatorBrainV2 : le pas de colonne du calepinage
 *  du builder vaut EXACTEMENT `rowWidthM + VIEWER_PANEL_SIDE_GAP_M`. */
export const VIEWER_PANEL_SIDE_GAP_M = 0.02;
/** Hauteur du châssis avant sur toit plat (m) — `frontStrut` de
 *  roofPro11/scene3d.ts (le panneau y est posé à frontStrut + montée/2 + 0,07). */
export const VIEWER_FLAT_STAND_M = 0.1;
/** Déport du panneau au-dessus du pan en pose affleurante (m) — même valeur que
 *  lib/estimatorBrainV6 PITCHED_FLUSH_STANDOFF_M. */
export const VIEWER_FLUSH_STANDOFF_M = 0.06;
/** Inclinaison VISUELLE des châssis sur toit plat (°) — représentation 3D
 *  uniquement (aucune valeur affichée n'en dérive). */
export const VIEWER_FLAT_TILT_DEG = 15;
/** Plafond dur d'instances panneau (garde-fou perf bas de gamme). */
export const VIEWER_MAX_PANELS = 600;

const VIEWER_DEG2RAD = Math.PI / 180;
const VIEWER_DEG2M = 111_320; // mètres par degré de latitude (WGS84 approx.)

/** Point-dans-polygone (ray casting) en coordonnées planes. */
export function viewerPointInRing(pt: [number, number], ring: Array<[number, number]>): boolean {
  let inside = false;
  const [px, py] = pt;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    const intersects = yi > py !== yj > py && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi;
    if (intersects) inside = !inside;
  }
  return inside;
}

/** Un panneau posé (centre ENU mètres, dans la frame du modèle). */
export interface ViewerPanel {
  x: number;
  y: number;
  /**
   * WJ130 — Face du panneau dans un chevron Est-Ouest dos à dos (`family:
   * 'eastwest'`), telle que posée par le builder. Le rendu incline le panneau
   * dans le sens OPPOSÉ pour la face 'E' (roofPro11/scene3d.ts : `signedTilt =
   * face === 'E' ? -tilt : tilt`). Absente en famille sud (tilt simple).
   */
  face?: RoofLayoutPanelFace;
}

/** Pose d'un panneau dans le calepinage : grand côté dans la pente (portrait)
 *  ou le long de la rangée (paysage) — mêmes deux poses que le builder
 *  (`PanelGrid.panelOrientation` de lib/estimatorBrainV2). */
export type ViewerPanelPose = 'portrait' | 'landscape';

/** Une zone prête à dessiner (tout en mètres ENU, origine = centroïde global). */
export interface ViewerZone {
  ringENU: Array<[number, number]>;
  obstaclesENU: Array<{ x: number; y: number; widthM: number; lengthM: number }>;
  roofType: 'flat' | 'pitched';
  /** Inclinaison des PANNEAUX (° — pente du pan si pitched, châssis visuel sinon). */
  tiltDeg: number;
  azimuthDeg: number;
  panels: ViewerPanel[];
  /** Empreinte du panneau : le long de la rangée / dans la pente (m). */
  panelAlongM: number;
  panelDepthM: number;
  /**
   * WJ130 — Longueur du panneau DANS LE SENS DE LA PENTE (m), NON projetée :
   * c'est le `slopeLenM` du builder, la vraie dimension de la boîte 3D avant
   * l'inclinaison (`panelDepthM = panelSlopeM · cos(tilt)` en est l'empreinte
   * au sol). Le rendu la lit telle quelle au lieu de diviser l'empreinte par
   * `cos(tilt)` — même géométrie que roofPro11/scene3d.ts
   * (`BoxGeometry(rowWidthM, slopeLenM, PANEL2_THICK_M)`).
   */
  panelSlopeM: number;
  /** WJ130 — Pose du panneau, celle du pack gagnant côté builder. */
  panelPose: ViewerPanelPose;
  /** WJ130 — Famille de config posée : 'eastwest' = chevrons dos à dos. */
  family: 'south' | 'eastwest';
  /** WJ130 — Pose affleurante (panneaux coplanaires au pan) ? */
  flush: boolean;
}

/** Modèle complet consommé par roofPro11/viewerOnly.ts. JSON pur. */
export interface ViewerModel {
  zones: ViewerZone[];
  /** Rayon englobant (m) — cadre la caméra sans calcul côté client. */
  radiusM: number;
  totalPanels: number;
}

/** Empreinte de panneau d'une zone : les panneaux + les dimensions du RECTANGLE
 *  à dessiner (le long de la rangée / au sol dans la pente / longueur réelle de
 *  pente) et la pose qui les a produites. */
export interface ZonePanelFootprint {
  panels: ViewerPanel[];
  /** Côté du panneau le long de la rangée (m) = `rowWidthM` du builder. */
  alongM: number;
  /** Empreinte AU SOL dans le sens de la pente (m) = `slopeM · cos(tilt)`. */
  depthM: number;
  /** Côté du panneau dans le sens de la pente (m) = `slopeLenM` du builder. */
  slopeM: number;
  pose: ViewerPanelPose;
}

/** Pose de REPLI (aucune géométrie réelle exploitable) : portrait sur pan
 *  incliné (pose affleurante courante), paysage sur toit plat. Règle
 *  HISTORIQUE du calepinage illustratif — inchangée. */
function defaultViewerPose(roofType: 'flat' | 'pitched'): ViewerPanelPose {
  return roofType === 'pitched' ? 'portrait' : 'landscape';
}

/**
 * WJ130 — Écart maximal toléré (m) entre le pas de colonne MESURÉ sur les
 * centres réels et l'un des deux pas théoriques du builder
 * (`VIEWER_PANEL_SHORT_M + jeu` = 1,323 m en portrait, `VIEWER_PANEL_LONG_M +
 * jeu` = 2,404 m en paysage). Assez large pour absorber le bruit flottant du
 * repère ENU, assez serré pour REFUSER un pas double (une colonne sautée en
 * portrait donne 2,646 m, à 0,242 m du pas paysage : sans cette borne on
 * conclurait « paysage » sur un calepinage portrait troué).
 */
const VIEWER_POSE_PITCH_TOL_M = 0.15;

/**
 * WJ130 — Retrouve la POSE (portrait / paysage) du calepinage RÉEL à partir des
 * seuls centres de panneaux sérialisés par le builder.
 *
 * Pourquoi c'est nécessaire : `serializeLayout` (roofPro11/prefill.ts) n'exporte
 * que `{cx, cy, face}` par panneau — jamais `rowWidthM`/`slopeLenM` ni la pose
 * du pack gagnant. Or l'ERP dessine chaque panneau
 * `BoxGeometry(rowWidthM, slopeLenM, …)`, avec {rowWidth, slopeLen} = (petit,
 * grand) en portrait et (grand, petit) en paysage : sans la pose, le site
 * dessinerait des rectangles tournés de 90° aux BONNES positions.
 *
 * Comment : le pavage du builder (`packCells` de lib/estimatorBrainV2) pose les
 * centres sur un lattice de PHASE FIXE le long de l'axe de rangée
 * `u = [-cos(az), sin(az)]`, au pas `rowWidthM + PANEL_SIDE_GAP_M` — le même
 * pour TOUTES les rangées. Le plus petit écart NON NUL entre deux projections
 * `u` distinctes vaut donc exactement ce pas (deux colonnes voisines occupées
 * suffisent), et il n'est jamais plus PETIT que lui. On le compare aux deux pas
 * théoriques et on tranche.
 *
 * Renvoie `null` (l'appelant garde alors la pose de repli) dès que la mesure
 * n'est pas concluante : une seule colonne occupée, ou un pas qui ne tombe sur
 * aucun des deux (pavage MIXTE PV62, où la pose change de rangée en rangée et
 * n'est de toute façon pas exportée). Pur, ne jette jamais.
 */
export function inferPanelPose(g: RoofLayoutZoneGeometry): ViewerPanelPose | null {
  if (g.panels.length < 2) return null;
  const az = g.azimuthDeg * VIEWER_DEG2RAD;
  // Axe des rangées, MÊME convention que packCells : f = [sin az, cos az]
  // (direction de visée), u = [-f[1], f[0]].
  const ux = -Math.cos(az);
  const uy = Math.sin(az);
  const us: number[] = [];
  for (const p of g.panels) {
    const u = p.cx * ux + p.cy * uy;
    if (Number.isFinite(u)) us.push(u);
  }
  if (us.length < 2) return null;
  us.sort((a, b) => a - b);
  let minGap = Infinity;
  for (let i = 1; i < us.length; i++) {
    const gap = us[i] - us[i - 1];
    // Écarts ~0 = panneaux d'une MÊME colonne (rangées empilées, ou les deux
    // versants d'un chevron Est-Ouest) : ils ne mesurent pas le pas de colonne.
    if (gap > 1e-3 && gap < minGap) minGap = gap;
  }
  if (!Number.isFinite(minGap)) return null;
  const portraitPitch = VIEWER_PANEL_SHORT_M + VIEWER_PANEL_SIDE_GAP_M;
  const landscapePitch = VIEWER_PANEL_LONG_M + VIEWER_PANEL_SIDE_GAP_M;
  const dP = Math.abs(minGap - portraitPitch);
  const dL = Math.abs(minGap - landscapePitch);
  if (dP <= VIEWER_POSE_PITCH_TOL_M && dP <= dL) return 'portrait';
  if (dL <= VIEWER_POSE_PITCH_TOL_M) return 'landscape';
  return null;
}

/**
 * WJ25 — Calepinage ILLUSTRATIF d'une zone : grille orientée par l'azimut de
 * face, cellules entièrement DANS le contour (retrait de rive) et HORS des
 * obstacles, plafonnée à `neededPanels` (quand > 0). Même esprit que le builder
 * (les N premières cellules), sans en dupliquer l'optimiseur. Pur.
 */
export function packZonePanels(
  ringENU: Array<[number, number]>,
  azimuthDeg: number,
  tiltDeg: number,
  roofType: 'flat' | 'pitched',
  neededPanels: number,
  obstaclesENU: Array<{ x: number; y: number; widthM: number; lengthM: number }> = [],
): ZonePanelFootprint {
  // Portrait sur pan incliné (pose affleurante courante), paysage sur toit plat.
  const pose = defaultViewerPose(roofType);
  const alongM = roofType === 'pitched' ? VIEWER_PANEL_SHORT_M : VIEWER_PANEL_LONG_M;
  const slopeM = roofType === 'pitched' ? VIEWER_PANEL_LONG_M : VIEWER_PANEL_SHORT_M;
  const tilt = tiltDeg * VIEWER_DEG2RAD;
  const depthM = slopeM * Math.cos(tilt); // empreinte au sol dans le sens de la pente
  // Pas de rangée : affleurant → quasi bord à bord ; châssis plat → espace anti-ombrage.
  const rowPitch = roofType === 'pitched' ? depthM + 0.05 : depthM + 1.2;
  const colPitch = alongM + 0.05;

  const az = azimuthDeg * VIEWER_DEG2RAD;
  const f: [number, number] = [Math.sin(az), Math.cos(az)]; // direction de face (aval)
  const u: [number, number] = [-f[1], f[0]]; // direction de rangée

  let aMin = Infinity, aMax = -Infinity, bMin = Infinity, bMax = -Infinity;
  for (const [x, y] of ringENU) {
    const a = x * u[0] + y * u[1];
    const b = x * f[0] + y * f[1];
    if (a < aMin) aMin = a;
    if (a > aMax) aMax = a;
    if (b < bMin) bMin = b;
    if (b > bMax) bMax = b;
  }
  if (!Number.isFinite(aMin) || aMax - aMin < alongM || bMax - bMin < depthM) {
    return { panels: [], alongM, depthM, slopeM, pose };
  }

  const inObstacle = (x: number, y: number): boolean => {
    for (const o of obstaclesENU) {
      if (Math.abs(x - o.x) <= o.widthM / 2 + 0.1 && Math.abs(y - o.y) <= o.lengthM / 2 + 0.1) return true;
    }
    return false;
  };

  const cap = neededPanels > 0 ? Math.min(neededPanels, VIEWER_MAX_PANELS) : VIEWER_MAX_PANELS;
  const panels: ViewerPanel[] = [];
  const halfA = alongM / 2;
  const halfD = depthM / 2;
  // Parcours des rangées de l'AVAL vers l'AMONT (le sud d'abord pour une face sud),
  // même esprit que « les N premières cellules » du builder.
  for (let b = bMax - VIEWER_SETBACK_M - halfD; b >= bMin + VIEWER_SETBACK_M + halfD; b -= rowPitch) {
    for (let a = aMin + VIEWER_SETBACK_M + halfA; a <= aMax - VIEWER_SETBACK_M - halfA; a += colPitch) {
      const cx = a * u[0] + b * f[0];
      const cy = a * u[1] + b * f[1];
      // Centre + 4 coins dans le polygone, et centre/coins hors obstacles.
      const corners: Array<[number, number]> = [
        [cx + halfA * u[0] + halfD * f[0], cy + halfA * u[1] + halfD * f[1]],
        [cx - halfA * u[0] + halfD * f[0], cy - halfA * u[1] + halfD * f[1]],
        [cx + halfA * u[0] - halfD * f[0], cy + halfA * u[1] - halfD * f[1]],
        [cx - halfA * u[0] - halfD * f[0], cy - halfA * u[1] - halfD * f[1]],
      ];
      if (!viewerPointInRing([cx, cy], ringENU)) continue;
      if (!corners.every((c) => viewerPointInRing(c, ringENU))) continue;
      if (inObstacle(cx, cy) || corners.some(([x, y]) => inObstacle(x, y))) continue;
      panels.push({ x: cx, y: cy });
      if (panels.length >= cap) return { panels, alongM, depthM, slopeM, pose };
    }
  }
  return { panels, alongM, depthM, slopeM, pose };
}

/**
 * WJ127 — Calepinage RÉEL d'une zone : reprend les panneaux EXACTEMENT posés
 * dans le builder (`zone.geometry`, cellules réellement occupées — PV27),
 * jamais un re-pavage. `zone.geometry.panels[].{cx,cy}` sont en ENU mètres
 * dans le repère `zone.geometry.origin` (voir `roofPro2.ts`/`estimatorBrainV2.ts` :
 * x=Est, y=Nord, origine = centroïde du tracé au moment du pack) — on repasse
 * donc par lat/lng (inverse exact de cette conversion) puis on reprojette avec
 * `toGlobalENU`, la MÊME fonction que celle utilisée pour le contour de la
 * zone (`buildViewerModel`), pour que panneaux et contour partagent un seul
 * repère cohérent. Renvoie `null` quand la zone n'a pas de géométrie réelle
 * exploitable (layout ancien, ou `geometry` invalide) — l'appelant retombe
 * alors sur `packZonePanels` (comportement illustratif inchangé). Pur.
 */
export function realZonePanels(
  zone: RoofLayoutZone,
  toGlobalENU: (pt: [number, number]) => [number, number],
): ZonePanelFootprint | null {
  const g = zone.geometry;
  if (!g || g.panels.length === 0) return null;
  const [olng, olat] = g.origin;
  const cosOriginLat = Math.cos(olat * VIEWER_DEG2RAD);
  if (!(cosOriginLat > 0.01)) return null; // garde-fou latitude aberrante (jamais en pratique)
  const panels: ViewerPanel[] = [];
  for (const p of g.panels) {
    const lng = olng + p.cx / (VIEWER_DEG2M * cosOriginLat);
    const lat = olat + p.cy / VIEWER_DEG2M;
    const [x, y] = toGlobalENU([lng, lat]);
    // WJ130 — la FACE du chevron Est-Ouest suit le panneau jusqu'au rendu :
    // c'est elle qui donne le SENS d'inclinaison (dos à dos), exactement comme
    // dans roofPro11/scene3d.ts. Jamais inventée : seulement recopiée.
    panels.push(p.face ? { x, y, face: p.face } : { x, y });
    if (panels.length >= VIEWER_MAX_PANELS) break;
  }
  if (panels.length === 0) return null;
  // WJ130 — Empreinte du panneau : la POSE du pack gagnant, RETROUVÉE sur les
  // centres réels (`inferPanelPose`), et non plus la règle générique du repli —
  // c'est ce qui faisait dessiner au site des rectangles tournés de 90° par
  // rapport à l'ERP. Mesure non concluante (colonne unique, pavage mixte) →
  // pose de repli historique, positions toujours exactes.
  const pose = inferPanelPose(g) ?? defaultViewerPose(zone.roofType);
  const tilt = g.tiltDeg * VIEWER_DEG2RAD;
  const alongM = pose === 'portrait' ? VIEWER_PANEL_SHORT_M : VIEWER_PANEL_LONG_M;
  const slopeM = pose === 'portrait' ? VIEWER_PANEL_LONG_M : VIEWER_PANEL_SHORT_M;
  const depthM = slopeM * Math.cos(tilt);
  return { panels, alongM, depthM, slopeM, pose };
}

/**
 * WJ25 — Construit le modèle 3D complet à partir d'un layout validé : centroïde
 * global comme origine ENU, une ViewerZone par zone (contour + obstacles +
 * calepinage), rayon englobant pour cadrer la caméra. Renvoie `null` quand rien
 * n'est dessinable. Pur, JSON-sûr (calculé côté serveur, sérialisé au client).
 */
export function buildViewerModel(layout: RoofLayout | null): ViewerModel | null {
  if (!layout || layout.zones.length === 0) return null;
  // Centroïde global (tous sommets confondus) = origine de la scène.
  let lng0 = 0, lat0 = 0, n = 0;
  for (const z of layout.zones) {
    for (const [lng, lat] of z.vertices) {
      lng0 += lng;
      lat0 += lat;
      n++;
    }
  }
  if (n === 0) return null;
  lng0 /= n;
  lat0 /= n;
  const cosLat = Math.cos(lat0 * VIEWER_DEG2RAD);
  const toENU = ([lng, lat]: [number, number]): [number, number] => [
    (lng - lng0) * VIEWER_DEG2M * cosLat,
    (lat - lat0) * VIEWER_DEG2M,
  ];

  const zones: ViewerZone[] = [];
  let radiusM = 0;
  let totalPanels = 0;
  let budget = VIEWER_MAX_PANELS;
  for (const z of layout.zones) {
    const ringENU = z.vertices.map(toENU);
    for (const [x, y] of ringENU) radiusM = Math.max(radiusM, Math.hypot(x, y));
    const obstaclesENU = z.obstacles.map((o) => {
      const [x, y] = toENU([o.centerLng, o.centerLat]);
      return { x, y, widthM: o.widthM, lengthM: o.lengthM };
    });
    // WJ127 — calepinage RÉEL (zone.geometry) en priorité ; repli illustratif
    // (packZonePanels, comportement historique STRICTEMENT inchangé) quand la
    // zone n'a pas de géométrie réelle exploitable — zéro régression sur un
    // roof_layout déjà en base (sans `geometry`).
    const real = realZonePanels(z, toENU);
    const tiltDeg = real && z.geometry ? z.geometry.tiltDeg : z.roofType === 'pitched' ? z.pitchDeg : VIEWER_FLAT_TILT_DEG;
    const azimuthDeg = real && z.geometry ? z.geometry.azimuthDeg : z.facingAzimuthDeg;
    const packed = real ?? packZonePanels(ringENU, azimuthDeg, tiltDeg, z.roofType, z.neededPanels, obstaclesENU);
    const panels = packed.panels.slice(0, Math.max(0, budget));
    budget -= panels.length;
    totalPanels += panels.length;
    zones.push({
      ringENU,
      obstaclesENU,
      roofType: z.roofType,
      tiltDeg,
      azimuthDeg,
      panels,
      panelAlongM: packed.alongM,
      panelDepthM: packed.depthM,
      panelSlopeM: packed.slopeM,
      panelPose: packed.pose,
      // WJ130 — famille / pose affleurante RÉELLES quand le builder les a
      // sérialisées ; sinon les valeurs implicites du repli illustratif (sud,
      // affleurant sur pan incliné) — rendu du repli strictement inchangé.
      family: real && z.geometry ? z.geometry.family : 'south',
      flush: real && z.geometry ? z.geometry.flush : z.roofType === 'pitched',
    });
  }
  if (zones.length === 0) return null;
  return { zones, radiusM: Math.max(radiusM, 6), totalPanels };
}

/**
 * WJ118 — Aplati les sommets de TOUTES les zones d'un RoofLayout (roof_layout
 * exposé par le backend depuis QJ26, `_safe_roof_layout`) en un contour
 * [lat,lng] — la convention attendue par `buildPublicRoofImageSpec`
 * (roofPro11/viewerOnly.ts, IDENTIQUE à `captureOutline`), alors que
 * `RoofLayoutZone.vertices` est en [lng,lat]. Même ENSEMBLE de sommets que le
 * centroïde calculé par `buildViewerModel` ci-dessus (une moyenne ne dépend pas
 * de l'ordre) : l'origine ENU de la photo drapée tombe donc EXACTEMENT sur
 * celle du modèle 3D. Filtre défensivement les entrées invalides — jamais un
 * throw ; layout absent ou sans zone exploitable → tableau vide (le client
 * saute alors l'appel réseau de la photo satellite). Pure, exportée pour test.
 */
export function roofLayoutOutlineLatLng(layout: RoofLayout | null): Array<[number, number]> {
  if (!layout || !Array.isArray(layout.zones)) return [];
  const out: Array<[number, number]> = [];
  for (const zone of layout.zones) {
    if (!zone || !Array.isArray(zone.vertices)) continue;
    for (const v of zone.vertices) {
      if (!Array.isArray(v) || v.length < 2) continue;
      const [lng, lat] = v;
      if (!isFiniteNum(lng) || !isFiniteNum(lat)) continue;
      out.push([lat, lng]);
    }
  }
  return out;
}

// ════════════════════════════════════════════════════════════════════════════
// WJ2 — « Voir les panneaux sur votre toit » à la CAPTURE (mon-toit.astro).
// Construit un RoofLayout ILLUSTRATIF à un seul pan à partir du contour posé
// par le visiteur (captureBoot.ts onCaptureChange) + le kWc de l'estimation
// instantanée WJ1 (billEstimate). AUCUNE donnée backend ici (page publique,
// avant tout devis) : le nombre de panneaux dérive du MÊME calcul
// PANEL2_WATT que le reste du site (estimatorBrain), jamais un chiffre
// inventé. Toit supposé plat orienté plein sud (176°) — représentation
// illustrative « votre toit, vos panneaux », pas une étude technique.
// ════════════════════════════════════════════════════════════════════════════

/** Watt-crête d'un panneau — même constante que le reste du site (roofPro2). */
export const CAPTURE_PANEL_WATT = 720;

/**
 * WJ2 — Construit un RoofLayout à un seul pan (plat, plein sud illustratif)
 * depuis un contour de toit `[[lat,lng],…]` (≥ 3 sommets, tel que renvoyé par
 * `onCaptureChange`) et un kWc cible (estimation WJ1). Renvoie `null` si le
 * contour n'a pas assez de sommets ou si le kWc n'est pas un nombre positif —
 * la page dégrade alors proprement (pas de bouton « voir les panneaux »).
 */
export function capturePreviewLayout(
  outlineLatLng: Array<[number, number]>,
  kwc: number | null,
): RoofLayout | null {
  if (!Array.isArray(outlineLatLng) || outlineLatLng.length < 3) return null;
  if (!Number.isFinite(kwc) || (kwc as number) <= 0) return null;
  const vertices: Array<[number, number]> = [];
  for (const pt of outlineLatLng) {
    if (!Array.isArray(pt) || pt.length < 2) continue;
    const [lat, lng] = pt;
    if (!isFiniteNum(lat) || !isFiniteNum(lng)) continue;
    vertices.push([lng, lat]); // RoofLayoutZone attend [lng,lat]
  }
  if (vertices.length < 3) return null;
  const neededPanels = Math.max(1, Math.ceil(((kwc as number) * 1000) / CAPTURE_PANEL_WATT));
  return {
    version: 1,
    zones: [
      {
        id: 'capture-preview',
        label: 'Votre toit',
        vertices,
        obstacles: [],
        roofType: 'flat',
        pitchDeg: 0,
        facingAzimuthDeg: 176, // plein sud illustratif — aucune boussole réelle à cette étape
        neededPanels,
      },
    ],
  };
}

// ════════════════════════════════════════════════════════════════════════════
// WJ26 — « Tout est expliqué » : légende + annotations + visite guidée autour
// de la 3D. Discipline inchangée : CHAQUE chiffre vient du layout serveur ou du
// payload quote ; quand une valeur manque, on renvoie null et la page affiche
// « estimation indisponible » — jamais une valeur fabriquée.
// ════════════════════════════════════════════════════════════════════════════

/** Libellé FR d'orientation (8 directions) depuis un azimut de face 0–360. */
export function orientationLabelFr(azimuthDeg: number): string {
  const az = ((azimuthDeg % 360) + 360) % 360;
  const labels = ['Nord', 'Nord-Est', 'Est', 'Sud-Est', 'Sud', 'Sud-Ouest', 'Ouest', 'Nord-Ouest'];
  return labels[Math.round(az / 45) % 8];
}

/** Annotation client-lisible d'une zone (pan) du layout. */
export interface ZoneAnnotation {
  label: string;
  /** Nombre de panneaux dimensionné pour ce pan (null si non dimensionné). */
  panels: number | null;
  /** Orientation lisible (« Sud », « Sud-Est »…). */
  orientation: string;
  /** Pente (°) du pan — null pour un toit plat (châssis standard). */
  tiltDeg: number | null;
  roofTypeLabel: string;
  /** kWc du pan = panneaux × Wc/panneau (payload) ; null si l'un manque. */
  kwc: number | null;
}

/**
 * WJ26/WJ127 — Annotations par pan, à afficher en légende autour de la 3D. Le
 * nombre de panneaux préfère le POSÉ RÉEL (`zone.geometry.count`, le calepinage
 * effectivement dessiné) quand la zone porte une géométrie exploitable — sinon
 * repli sur la CIBLE dimensionnée par l'étude (`neededPanels`), comportement
 * historique. Sans ce repli, la légende affichait la cible d'étude (ex. 20)
 * pendant que le bloc devis affiche le posé (`q.nb_panneaux`, ex. 18) : deux
 * chiffres différents sur la même page pour « le nombre de panneaux ». La
 * puissance par panneau vient du payload quote (`watt_par_panneau`) — le kWc
 * n'est calculé que si les deux sont présents (produit de deux valeurs
 * serveur, pas une invention).
 */
export function zoneAnnotations(
  layout: RoofLayout,
  wattParPanneau?: number | null,
): ZoneAnnotation[] {
  const watt = isFiniteNum(wattParPanneau) && wattParPanneau > 0 ? wattParPanneau : null;
  return layout.zones.map((z) => {
    const panels = z.geometry && z.geometry.count > 0
      ? z.geometry.count
      : z.neededPanels > 0 ? z.neededPanels : null;
    return {
      label: z.label,
      panels,
      orientation: orientationLabelFr(z.facingAzimuthDeg),
      tiltDeg: z.roofType === 'pitched' && z.pitchDeg > 0 ? Math.round(z.pitchDeg) : null,
      roofTypeLabel: z.roofType === 'pitched' ? 'Toit en pente' : 'Toit plat',
      kwc: panels !== null && watt !== null ? Math.round(((panels * watt) / 1000) * 100) / 100 : null,
    };
  });
}

/** Texte de repli honnête quand un chiffre ne peut pas être calculé. */
export const FIGURE_UNAVAILABLE = 'estimation indisponible';

/** Une étape de la visite guidée (FR + gloss arabe court). */
export interface WalkStep {
  id: string;
  title: string;
  titleAr: string;
  /** Phrase FR en langage simple — chiffres serveur ou repli libellé. */
  body: string;
}

/**
 * WJ26 — Visite guidée en 4 étapes : « voici votre toit → voici vos panneaux →
 * voici ce qu'ils produisent → voici votre économie ». Chaque chiffre est lu du
 * payload backend (nb_panneaux / puissance_kwc / prod_kwh / eco_*_ann) ; toute
 * valeur absente devient « estimation indisponible » — jamais un nombre
 * fabriqué. Pure (testable sans DOM).
 */
export function walkthroughSteps(p: ProposalResponse): WalkStep[] {
  const q = p.quote;
  const nb = isFiniteNum(q?.nb_panneaux) && q!.nb_panneaux! > 0 ? q!.nb_panneaux! : null;
  const kwc = isFiniteNum(q?.puissance_kwc) && q!.puissance_kwc! > 0 ? q!.puissance_kwc! : null;
  const prod = isFiniteNum(q?.prod_kwh) && q!.prod_kwh! > 0 ? q!.prod_kwh! : null;
  const head = savingsHeadline(p, recommendedOption(p));

  const panneauxBody =
    nb !== null
      ? `${formatNumber(nb)} panneaux${kwc !== null ? `, soit ${formatNumber(kwc, 2)} kWc` : ''}, positionnés selon l’étude de votre toiture.`
      : `Vos panneaux sont positionnés selon l’étude de votre toiture (nombre : ${FIGURE_UNAVAILABLE}).`;
  const prodBody =
    prod !== null
      ? `Environ ${formatNumber(prod)} kWh produits par an — de l’électricité que vous n’achetez plus au réseau.`
      : `Production annuelle : ${FIGURE_UNAVAILABLE}.`;
  const ecoBody =
    head.annual !== null
      ? `Environ ${formatMAD(head.annual)} d’économies par an${head.monthly !== null ? ` (≈ ${formatMAD(head.monthly)}/mois)` : ''}, en autoconsommation (loi 82-21).`
      : `Économie annuelle : ${FIGURE_UNAVAILABLE}.`;

  return [
    {
      id: 'toit',
      title: 'Voici votre toit',
      titleAr: 'هذا سطح منزلكم',
      body: 'Le contour et les pans que vous voyez sont ceux de VOTRE toiture, telle que tracée lors de l’étude. Faites glisser pour tourner autour.',
    },
    {
      id: 'panneaux',
      title: 'Voici vos panneaux',
      titleAr: 'هذه ألواحكم الشمسية',
      body: panneauxBody,
    },
    {
      id: 'production',
      title: 'Voici ce qu’ils produisent',
      titleAr: 'هذا ما تنتجه',
      body: prodBody,
    },
    {
      id: 'economie',
      title: 'Voici votre économie',
      titleAr: 'هذا ما توفرونه',
      body: ecoBody,
    },
  ];
}

// ════════════════════════════════════════════════════════════════════════════
// WJ32 — Complétude du contenu de la proposition : financement backend réel,
// fiche produit enrichie (marque/garantie/fiche technique), « Et après ? »,
// « Nos hypothèses », accompagnement post-installation, FAQ objections,
// variantes côte-à-côte. Même discipline « zéro chiffre inventé » : chaque
// fonction ne lit QUE des champs backend présents, et dégrade proprement
// (tableau vide / null) quand une donnée manque — jamais un repli fabriqué.
// ════════════════════════════════════════════════════════════════════════════

/**
 * WJ32 — Lecture défensive du bloc `financing` BACKEND (QJ12). Différent de
 * `financingComparison` (calcul générique ci-dessus, gardé pour compat) : ce
 * bloc porte le VRAI programme (Tatwir/ISTIDAMA) choisi par le backend selon
 * `inst_type`. Renvoie `null` quand absent/malformé — la page masque alors
 * le bloc financement (jamais de mélange entre les deux sources).
 */
export function backendFinancing(p: Pick<ProposalResponse, 'financing'>): ProposalFinancingBlock | null {
  const f = p.financing;
  if (!f || typeof f !== 'object') return null;
  if (!f.cash || !f.credit || typeof f.cash.montant_ttc !== 'number') return null;
  return f;
}

/** WJ32 — Variantes actives « autres tailles » (tableau vide si le devis est isolé). */
export function proposalVariants(p: Pick<ProposalResponse, 'variants'>): ProposalVariantSummary[] {
  return Array.isArray(p.variants) ? p.variants : [];
}

/** WJ114 — note personnelle du vendeur, lue défensivement. */
export interface SellerNote {
  note: string | null;
  name: string | null;
  photoUrl: string | null;
}

/**
 * WJ114 — « décider en 10 secondes » (Storydoc) : la personnalisation
 * (note + identité du vendeur) augmente l'engagement, mais le backend
 * n'expose PAS ENCORE ce bloc aujourd'hui (aucune intégration ERP livrée) —
 * lecture défensive (optional chaining) pour s'allumer sans changement de
 * code le jour où l'ERP le fournira. Renvoie `null` si les TROIS champs sont
 * absents/vides (rien à rendre) ; sinon un objet avec les seuls champs
 * réellement fournis (jamais de valeur fabriquée pour compléter).
 */
export function sellerNote(p: Pick<ProposalResponse, 'seller'>): SellerNote | null {
  const s = p?.seller;
  if (!s || typeof s !== 'object') return null;
  const note = typeof s.note === 'string' && s.note.trim() ? s.note.trim() : null;
  const name = typeof s.name === 'string' && s.name.trim() ? s.name.trim() : null;
  const photoUrl = typeof s.photo_url === 'string' && s.photo_url.trim() ? s.photo_url.trim() : null;
  if (!note && !name && !photoUrl) return null;
  return { note, name, photoUrl };
}

// ── WJ32 · « Et après ? » — timeline des prochaines étapes ───────────────────

export interface NextStep {
  id: string;
  title: string;
  titleAr: string;
  /** WJ43 — variante anglaise (segment marocains-du-monde). */
  titleEn: string;
  body: string;
  bodyAr: string;
  bodyEn: string;
}

/**
 * WJ32 — Les 4 étapes après signature. Les DÉLAIS (48–72 h visite, 7–14 j
 * installation) sont des repères opérationnels standard TAQINOR — libellés
 * comme des fourchettes indicatives, jamais un engagement contractuel daté.
 * Toujours affichée (pas de dépendance à un champ backend) : c'est un
 * processus, pas un chiffre client — rien à masquer.
 */
export function nextSteps(): NextStep[] {
  return [
    {
      id: 'signature',
      title: 'Signature',
      titleAr: 'التوقيع',
      titleEn: 'Signature',
      body: 'Vous signez en ligne ci-dessous. Votre conseiller Taqinor confirme la réception dans la journée.',
      bodyAr: 'توقعون إلكترونياً أدناه، ويؤكد مستشاركم الاستلام خلال اليوم نفسه.',
      bodyEn: 'You sign online below. Your Taqinor advisor confirms receipt the same day.',
    },
    {
      id: 'visite',
      title: 'Visite technique',
      titleAr: 'الزيارة التقنية',
      titleEn: 'Technical visit',
      body: 'Un technicien confirme les mesures sur site sous 48–72 h (délai indicatif).',
      bodyAr: 'يتحقق فني من القياسات في الموقع خلال 48 إلى 72 ساعة (أجل تقريبي).',
      bodyEn: 'A technician confirms the on-site measurements within 48–72 h (indicative timeframe).',
    },
    {
      id: 'installation',
      title: 'Installation',
      titleAr: 'التركيب',
      titleEn: 'Installation',
      body: 'Pose de votre installation par notre équipe, généralement sous 7–14 jours (délai indicatif) selon la disponibilité matériel.',
      bodyAr: 'تركيب منظومتكم بواسطة فريقنا، عادة خلال 7 إلى 14 يوماً (أجل تقريبي) حسب توفر المعدات.',
      bodyEn: 'Our team installs your system, typically within 7–14 days (indicative timeframe) depending on equipment availability.',
    },
    {
      id: 'mise-en-service',
      title: 'Mise en service',
      titleAr: 'التشغيل',
      titleEn: 'Commissioning',
      body: 'Vérification finale, mise en service et remise des documents (garanties, attestations).',
      bodyAr: 'فحص نهائي، تشغيل المنظومة وتسليم الوثائق (الضمانات والشهادات).',
      bodyEn: 'Final check, commissioning, and handover of documents (warranties, certificates).',
    },
  ];
}

// ── WJ32 · « Nos hypothèses » — disclosure sourcée, jamais de valeur inventée ─

export interface AssumptionItem {
  label: string;
  labelAr: string;
  /** WJ43 — variante anglaise. */
  labelEn: string;
  value: string;
  /**
   * WJ43 — la valeur n'avait jusqu'ici AUCUNE traduction (ni AR ni EN) : elle
   * s'affichait en français quelle que soit la langue active. `valueAr`/
   * `valueEn` corrigent cette fuite au passage (même chiffres, texte traduit).
   */
  valueAr: string;
  valueEn: string;
}

/**
 * WJ32 — Hypothèses RÉELLES qui sous-tendent les chiffres de la page, sourcées
 * UNIQUEMENT depuis des champs backend/constantes déjà affichées ailleurs sur
 * la page (jamais une nouvelle valeur inventée ici) :
 *  - tarif : loi 82-21 autoconsommation, dérive 0 % (BILL_INFLATION_RATE) ;
 *  - horizon : SAVINGS_HORIZON_YEARS (25 ans, durée de vie économique retenue —
 *    la garantie de performance panneau va au-delà : 30 ans, cf. warranty.ts) ;
 *  - type d'installation : `quote.inst_type` (résidentiel/industriel/agricole) ;
 *  - financement : programme backend s'il est présent (Tatwir/ISTIDAMA…).
 * Toujours au moins 2 lignes (tarif + horizon sont des constantes du module,
 * jamais absentes) — le bloc n'est donc jamais vide.
 */
export function proposalAssumptions(p: ProposalResponse): AssumptionItem[] {
  const items: AssumptionItem[] = [
    {
      label: 'Cadre tarifaire',
      labelAr: 'الإطار التعريفي',
      labelEn: 'Tariff framework',
      value: 'Autoconsommation basse tension (loi 82-21), tarif ONEE supposé constant (0 % de dérive) — toute hausse réelle ne ferait qu\'augmenter l\'économie.',
      valueAr: 'الاستهلاك الذاتي في التوتر المنخفض (القانون 82-21)، بافتراض تعريفة ONEE ثابتة (0 % تغير) — أي ارتفاع فعلي لن يزيد إلا من التوفير.',
      valueEn: 'Low-voltage self-consumption (law 82-21), assuming a constant ONEE tariff (0 % drift) — any real increase would only raise your savings.',
    },
    {
      label: 'Horizon d\'analyse',
      labelAr: 'أفق التحليل',
      labelEn: 'Analysis horizon',
      value: `${SAVINGS_HORIZON_YEARS} ans — durée de garantie de performance standard d'un panneau photovoltaïque.`,
      valueAr: `${SAVINGS_HORIZON_YEARS} سنة — مدة ضمان الأداء المعيارية للوح الشمسي.`,
      valueEn: `${SAVINGS_HORIZON_YEARS} years — standard performance warranty duration of a solar panel.`,
    },
  ];
  const instType = p.quote?.inst_type;
  if (instType) {
    const label =
      instType === 'agricole'
        ? 'Pompage solaire (dimensionné HMT + débit souhaité)'
        : instType === 'industriel' || instType === 'commercial'
          ? 'Autoconsommation industrielle/commerciale (étude taux de couverture)'
          : 'Résidentiel (simulateur)';
    const labelAr =
      instType === 'agricole'
        ? 'ضخ شمسي (محسوب حسب HMT ومعدل الضخ المرغوب)'
        : instType === 'industriel' || instType === 'commercial'
          ? 'استهلاك ذاتي صناعي/تجاري (دراسة معدل التغطية)'
          : 'سكني (المحاكي)';
    const labelEn =
      instType === 'agricole'
        ? 'Solar pumping (sized on head + desired flow rate)'
        : instType === 'industriel' || instType === 'commercial'
          ? 'Industrial/commercial self-consumption (coverage-rate study)'
          : 'Residential (simulator)';
    items.push({ label: 'Type d\'installation', labelAr: 'نوع التركيب', labelEn: 'Installation type', value: label, valueAr: labelAr, valueEn: labelEn });
  }
  const fin = backendFinancing(p);
  if (fin?.credit?.programme_label) {
    const rate = formatNumber(fin.credit.taux_annuel_pct, 2);
    const years = Math.round(fin.credit.duree_mois / 12);
    items.push({
      label: 'Programme de financement indicatif',
      labelAr: 'برنامج التمويل الإرشادي',
      labelEn: 'Indicative financing programme',
      value: `${fin.credit.programme_label} — taux ${rate} %/an, ${years} ans (à confirmer avec votre banque).`,
      valueAr: `${fin.credit.programme_label} — معدل ${rate} %/سنة، ${years} سنة (يُؤكَّد مع بنككم).`,
      valueEn: `${fin.credit.programme_label} — rate ${rate} %/year, ${years} years (to confirm with your bank).`,
    });
  }
  return items;
}

// ── WJ32 · Accompagnement post-installation ───────────────────────────────────

export interface MonitoringPoint {
  label: string;
  labelAr: string;
  /** WJ43 — variante anglaise. */
  labelEn: string;
}

/**
 * WJ32 — Points d'accompagnement post-installation : FAITS opérationnels
 * (garanties déjà affichées ailleurs sur la page, SAV Taqinor) — pas de
 * chiffre nouveau.
 *
 * (fondateur 2026-08-18) LE SUIVI PAR L'APPLICATION DE L'ONDULEUR N'EST PLUS
 * INCONDITIONNEL. Il était rendu « toujours », y compris sur un devis de
 * POMPAGE qui ne contient aucun onduleur (pompe + variateur) : la page
 * promettait alors une application pour un matériel non vendu. L'appelant
 * passe la présence RÉELLE d'une ligne onduleur (`equipmentPresence` de
 * `propositionPage.ts`, lue sur les lignes du devis) ; sans elle, seuls les
 * points génériques de maintenance restent — jamais un point inventé.
 */
export function monitoringPoints(
  presence?: { onduleur?: boolean } | null,
): MonitoringPoint[] {
  const onduleur = presence?.onduleur === true;
  return [
    ...(onduleur ? [{
      label: 'Suivi de production disponible via l\'application de votre onduleur',
      labelAr: 'تتبع الإنتاج متاح عبر تطبيق العاكس',
      labelEn: 'Production monitoring available via your inverter\'s app',
    }] : []),
    {
      label: 'SAV Taqinor joignable sur WhatsApp pour toute question après installation',
      labelAr: 'خدمة ما بعد البيع لتاقينور متاحة عبر واتساب لأي سؤال بعد التركيب',
      labelEn: 'Taqinor after-sales support reachable on WhatsApp for any question after installation',
    },
    {
      label: 'Garanties constructeur actives dès la mise en service (voir « Pourquoi nous faire confiance »)',
      labelAr: 'ضمانات الصانع سارية فور التشغيل',
      labelEn: 'Manufacturer warranties active from commissioning (see "Why trust us")',
    },
  ];
}

// ── WJ32 · FAQ objections (contenu éditorial fixe, pas de dépendance backend) ─

export interface FaqItem {
  id: string;
  question: string;
  questionAr: string;
  /** WJ43 — variante anglaise. */
  questionEn: string;
  answer: string;
  answerAr: string;
  answerEn: string;
}

/** WJ32 — 5 objections fréquentes avant signature, réponses factuelles courtes. */
export function objectionFaq(): FaqItem[] {
  return [
    {
      id: 'panne-reseau',
      question: 'Que se passe-t-il en cas de coupure du réseau électrique ?',
      questionAr: 'ماذا يحدث في حال انقطاع التيار الكهربائي؟',
      questionEn: 'What happens during a power grid outage?',
      answer: 'Une installation sans batterie s\'arrête par sécurité (norme anti-îlotage) ; une installation avec batterie peut continuer à alimenter les circuits prioritaires.',
      answerAr: 'التركيب بدون بطارية يتوقف لأسباب أمنية؛ أما مع البطارية فيمكن أن يستمر تزويد الدارات ذات الأولوية.',
      answerEn: 'A battery-less installation shuts down for safety (anti-islanding standard); a battery-equipped installation can keep powering priority circuits.',
    },
    {
      id: 'entretien',
      question: 'Quel entretien est nécessaire ?',
      questionAr: 'ما هي الصيانة المطلوبة؟',
      questionEn: 'What maintenance is required?',
      answer: 'Un nettoyage occasionnel des panneaux (poussière) et une vérification visuelle annuelle suffisent dans la majorité des cas.',
      answerAr: 'تنظيف الألواح بين الحين والآخر وفحص بصري سنوي يكفيان في أغلب الحالات.',
      answerEn: 'Occasional panel cleaning (dust) and an annual visual check are enough in most cases.',
    },
    {
      id: 'demenagement',
      question: 'Puis-je emporter mon installation si je déménage ?',
      questionAr: 'هل يمكنني نقل التركيب إذا انتقلت للسكن في مكان آخر؟',
      questionEn: 'Can I take my installation with me if I move?',
      // La réponse doit tenir DEVANT la fiche technique « structure-fixation »
      // atteignable depuis la même page : celle-ci dit que sur toiture inclinée
      // les fixations traversent la couverture et sont étanchées point par
      // point. Promettre à tout le monde une pose lestée démontable contredisait
      // donc la fiche du même devis — on distingue les deux cas.
      answer: 'Sur toiture-terrasse — la grande majorité de nos poses — l\'installation repose sur des socles lestés, sans fixation au bâtiment : elle peut être démontée et remontée. Sur toiture inclinée, les fixations sont étanchées point par point : le démontage se fait alors sur étude.',
      answerAr: 'على السطح المستوي — وهو حال الغالبية العظمى من تركيباتنا — يرتكز النظام على قواعد مثقّلة دون تثبيت بالمبنى: يمكن تفكيكه وإعادة تركيبه. أما على السطح المائل، فالتثبيتات معزولة نقطة بنقطة: عندئذ يتم التفكيك بعد دراسة.',
      answerEn: 'On a flat roof — the vast majority of our installations — the system rests on ballasted mounts, with no fixing to the building: it can be dismantled and reinstalled. On a pitched roof, the fixings are sealed point by point: dismantling is then subject to a survey.',
    },
    {
      id: 'toit-abime',
      question: 'Est-ce que l\'installation abîme la toiture ?',
      questionAr: 'هل يضر التركيب بالسطح؟',
      questionEn: 'Does the installation damage the roof?',
      answer: 'La fixation est étudiée pour respecter l\'étanchéité de votre toiture ; l\'étude technique en amont vérifie la structure porteuse.',
      answerAr: 'يُدرس التثبيت لاحترام عزل السطح؛ وتتحقق الدراسة التقنية المسبقة من متانة البنية الحاملة.',
      answerEn: 'The mounting is engineered to preserve your roof\'s waterproofing; the upfront technical study verifies the load-bearing structure.',
    },
    {
      id: 'garanties',
      question: 'Que couvrent exactement les garanties ?',
      questionAr: 'ماذا تغطي الضمانات بالضبط؟',
      questionEn: 'What exactly do the warranties cover?',
      answer: 'Les garanties constructeur (panneaux/onduleur) couvrent le matériel selon les durées indiquées dans « Pourquoi nous faire confiance » ci-dessous ; la main d\'œuvre Taqinor est couverte séparément selon votre contrat.',
      answerAr: 'تغطي ضمانات الصانع (الألواح والعاكس) المعدات حسب المدد المذكورة أدناه؛ أما اليد العاملة لتاقينور فمشمولة بضمان منفصل حسب عقدكم.',
      answerEn: 'Manufacturer warranties (panels/inverter) cover the equipment for the durations shown in "Why trust us" below; Taqinor\'s labour is covered separately under your contract.',
    },
  ];
}

// ── WJ55/WJ109 · Télémétrie de vue/engagement de la proposition ──────────────
//
// « Le CRM sait QUE le client a lu, mais pas QUAND » : un follow-up envoyé au
// moment où le client rouvre sa proposition (ou vient de faire défiler jusqu'au
// bloc financement) convertit bien mieux qu'une relance calendaire aveugle.
//
// WJ109 — [CORRECTIF DE CORRUPTION DE DONNÉES EN PRODUCTION] Cette télémétrie
// postait auparavant vers le fil lead CRM (`LEAD_WEBHOOK_URL`,
// `apps/crm/webhooks.py`) avec l'idée que le backend « ferait correspondre »
// l'événement à un lead existant via son téléphone. En réalité ce webhook
// traite CHAQUE payload comme une mise à jour de lead : sans nom exploitable
// dans l'événement, il écrase le NOM RÉEL du lead existant par « Lead site
// web » et le retague — donc un client qui se contente d'OUVRIR sa proposition
// corrompait sa propre fiche CRM. Cette télémétrie doit désormais transiter
// EXCLUSIVEMENT par le canal télémétrie/funnel dédié (`FUNNEL_WEBHOOK_URL`,
// le même que `lib/funnelBeacon.ts`), jamais par le webhook de capture de
// lead — voir `pages/api/proposition-track.ts`.

/** Les deux moments suivis (WJ55) : première vue, et défilement jusqu'au bloc financement. */
export type ProposalEngagementEvent = 'proposal_first_view' | 'proposal_scrolled_financing';

export interface ProposalTrackContext {
  reference: string;
  token: string;
  clientPhone?: string | null;
}

/**
 * WJ109 — Payload de TÉLÉMÉTRIE pure (jamais un objet « lead ») : aucun champ
 * qui ressemble à un contact (nom/téléphone) n'y voyage plus — seul un
 * identifiant de corrélation non qualifiant (référence ou token) est inclus,
 * pour permettre un futur rapprochement CÔTÉ LECTURE (jamais une écriture) au
 * moment de l'analyse, sans jamais risquer une écriture de lead par ping.
 */
export interface ProposalTrackPayload {
  event_type: ProposalEngagementEvent;
  reference: string;
  token: string;
  page: string;
  /** LANE T-WEB (25/08/2026) — empreinte d'appareil anonyme, ADDITIVE (voir
   *  lib/visite.ts `appareilId`) : présente uniquement quand fournie par
   *  l'appelant, jamais fabriquée ici, jamais requise. */
  appareil_id?: string;
}

/**
 * WJ55/WJ109 — Construit le payload envoyé au proxy `/api/proposition-track`,
 * ou `null` quand ni référence ni token ne sont disponibles (rien de
 * corrélable à journaliser). Ce payload est PUREMENT télémétrique : il ne
 * porte plus de téléphone/contact et ne doit JAMAIS être posté vers le webhook
 * de capture de lead (voir la note ci-dessus). `appareilId` (LANE T-WEB) est
 * ADDITIF : omis du payload quand absent/vide.
 */
export function buildProposalTrackPayload(
  ctx: ProposalTrackContext,
  event: ProposalEngagementEvent,
  appareilId?: string,
): ProposalTrackPayload | null {
  const reference = (ctx.reference ?? '').trim();
  const token = (ctx.token ?? '').trim();
  if (!reference && !token) return null;
  return {
    event_type: event,
    reference,
    token,
    page: `/proposition/${token}`,
    ...(appareilId ? { appareil_id: appareilId } : {}),
  };
}

// ════════════════════════════════════════════════════════════════════════════
// WJ126 · Proposition MODE-AWARE — 4 variantes (résidentiel / agricole /
// industriel / commercial) à partir du bloc QX49 exposé par le backend
// (`mode_installation` clé machine minuscule, `mode_kpis` whitelisté,
// `categorie_commerciale`). TOUTE la logique de choix de variante + d'extraction
// de KPI vit ici (pure, testée sans DOM) ; la page ne fait que brancher sur
// `resolveInstallMode` et rendre ce que ces fonctions renvoient.
//
// DISCIPLINE « ZÉRO CHIFFRE INVENTÉ » : un KPI absent du payload devient `null`
// (jamais 0, jamais une valeur fabriquée) — la page l'omet honnêtement. AUCUN
// champ d'un mode ne fuit dans un autre : `agricoleKpis` ne renvoie rien hors
// pompage, `autoconsoKpis` rien hors industriel/commercial. La page ne branche
// JAMAIS sur `inst_type` (libellé capitalisé qui ne matchait aucun littéral
// minuscule) — uniquement sur `mode_installation` (clé machine QX49).
// ════════════════════════════════════════════════════════════════════════════

/** Les 4 marchés du générateur de devis (clé machine minuscule, cf.
 *  `Devis.ModeInstallation` backend). Repli résidentiel quand absent/inconnu. */
export type InstallMode = 'residentiel' | 'industriel' | 'commercial' | 'agricole';

/**
 * WJ126/QX49 — KPI POMPAGE (agricole). Chaque nombre est soit une valeur backend
 * réelle, soit `null` (jamais fabriqué). `fda_eligible` : irrigation localisée
 * (goutte) → subvention FDA envisageable « sous réserve », jamais promise.
 */
export interface AgricoleKpis {
  pompe_cv: number | null;
  pompe_kw: number | null;
  hmt_m: number | null;
  debit_hmt_m3h: number | null;
  m3_jour: number | null;
  champ_kwc: number | null;
  bassin_m3: number | null;
  fda_eligible: boolean;
}

/**
 * WJ126/QX49 — KPI AUTOCONSOMMATION (industriel/commercial). L'injection 82-21
 * n'est présente (`injection_kwh_an`/`injection_dh_an` non nuls) que si le
 * backend l'a réellement calculée sur ce devis — sinon `null`, jamais promise.
 */
export interface AutoconsoKpis {
  taux_autoconso: number | null;
  taux_couverture: number | null;
  economies_annuelles: number | null;
  payback: number | null;
  injection_kwh_an: number | null;
  injection_dh_an: number | null;
}

/** Union lâche du bloc `mode_kpis` backend (forme réelle choisie par le mode). */
export type ProposalModeKpis = Partial<AgricoleKpis> & Partial<AutoconsoKpis>;

/** Coercition défensive d'un KPI en nombre fini (accepte number ou chaîne
 *  numérique — le backend `_kpi_num` renvoie des floats, mais on ne casse pas
 *  sur une string) ; toute autre entrée → `null` (jamais 0 fabriqué). */
function kpiNumber(v: unknown): number | null {
  if (typeof v === 'number') return Number.isFinite(v) ? v : null;
  if (typeof v === 'string' && v.trim() !== '') {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

/**
 * WJ126 — Résout la variante à rendre à partir de `mode_installation` (clé
 * machine QX49, MINUSCULE). Lit le niveau racine du payload en priorité, puis
 * `quote.mode_installation` (le builder l'y place aussi), et JAMAIS `inst_type`.
 * La comparaison est tolérante (`includes` + minuscule) pour absorber un futur
 * alias (`professionnel` = nom interne d'industriel) sans jamais matcher un
 * mode par erreur. Absent/vide/inconnu → `residentiel` (repli honnête).
 */
export function resolveInstallMode(
  p: Pick<ProposalResponse, 'mode_installation' | 'quote'>,
): InstallMode {
  const raw =
    p.mode_installation ??
    (p.quote as { mode_installation?: string | null } | undefined)?.mode_installation ??
    '';
  const s = String(raw).trim().toLowerCase();
  if (s.includes('agricole') || s.includes('pompage')) return 'agricole';
  if (s.includes('commercial') && !s.includes('industriel')) return 'commercial';
  if (s.includes('industriel') || s.includes('professionnel')) return 'industriel';
  return 'residentiel';
}

/**
 * WJ126 — Extrait les KPI pompage TYPÉS. Renvoie `null` hors mode agricole
 * (zéro fuite inter-mode). En mode agricole mais `mode_kpis` absent/partiel :
 * renvoie l'objet avec chaque champ à `null` (+ `fda_eligible: false`) — la page
 * rend alors le héros pompage et OMET honnêtement chaque valeur manquante.
 */
export function agricoleKpis(
  p: Pick<ProposalResponse, 'mode_installation' | 'mode_kpis' | 'quote'>,
): AgricoleKpis | null {
  if (resolveInstallMode(p) !== 'agricole') return null;
  const k = (p.mode_kpis ?? {}) as ProposalModeKpis;
  return {
    pompe_cv: kpiNumber(k.pompe_cv),
    pompe_kw: kpiNumber(k.pompe_kw),
    hmt_m: kpiNumber(k.hmt_m),
    debit_hmt_m3h: kpiNumber(k.debit_hmt_m3h),
    m3_jour: kpiNumber(k.m3_jour),
    champ_kwc: kpiNumber(k.champ_kwc),
    bassin_m3: kpiNumber(k.bassin_m3),
    fda_eligible: k.fda_eligible === true,
  };
}

/**
 * WJ126 — Extrait les KPI autoconsommation TYPÉS. Renvoie `null` hors
 * industriel/commercial (zéro fuite inter-mode). En mode industriel/commercial
 * mais `mode_kpis` absent/partiel : objet à champs `null` — omission honnête.
 */
export function autoconsoKpis(
  p: Pick<ProposalResponse, 'mode_installation' | 'mode_kpis' | 'quote'>,
): AutoconsoKpis | null {
  const mode = resolveInstallMode(p);
  if (mode !== 'industriel' && mode !== 'commercial') return null;
  const k = (p.mode_kpis ?? {}) as ProposalModeKpis;
  return {
    taux_autoconso: kpiNumber(k.taux_autoconso),
    taux_couverture: kpiNumber(k.taux_couverture),
    economies_annuelles: kpiNumber(k.economies_annuelles),
    payback: kpiNumber(k.payback),
    injection_kwh_an: kpiNumber(k.injection_kwh_an),
    injection_dh_an: kpiNumber(k.injection_dh_an),
  };
}

/** WJ126 — Vrai quand l'injection 82-21 est RÉELLEMENT calculée (kWh/an positif) :
 *  seule condition d'affichage de la ligne injection + mention ANRE. */
export function hasInjection(k: AutoconsoKpis | null): boolean {
  return !!k && k.injection_kwh_an !== null && k.injection_kwh_an > 0;
}

/** WJ126 — Un point du mini-cashflow autoconsommation (net cumulé, MAD). */
export interface CashflowPoint {
  /** Année (0 = mise en service). */
  year: number;
  /** Trésorerie nette cumulée à cette année (négative avant le point mort). */
  cumulative: number;
}

/**
 * WJ126 — Mini-cashflow 10 ans (industriel/commercial) : `-investissement TTC`
 * + `économies_annuelles × année`. MÊME modèle linéaire que le PDF et
 * `savingsHeadline` (0 % d'escalade tarifaire, `BILL_INFLATION_RATE`) — aucune
 * dérive inventée. Renvoie `null` si l'économie annuelle ou le TTC réel manque
 * (jamais un cashflow construit sur un chiffre fabriqué).
 */
export function autoconsoCashflow(
  p: ProposalResponse,
  opt: OptionKey,
  k: AutoconsoKpis | null,
  years: number = 10,
): CashflowPoint[] | null {
  if (!k) return null;
  const annual = k.economies_annuelles;
  const outlay = optionTtc(p, opt);
  if (
    annual === null || annual <= 0 ||
    !Number.isFinite(outlay) || outlay <= 0 ||
    years <= 0
  ) {
    return null;
  }
  const pts: CashflowPoint[] = [];
  for (let y = 0; y <= years; y++) {
    pts.push({ year: y, cumulative: Math.round(-outlay + annual * y) });
  }
  return pts;
}

/** WJ126 — Livraison d'eau estimée d'un mois (m³). */
export interface WaterDeliveryMonth {
  /** Index du mois (0 = janvier). */
  monthIndex: number;
  /** Volume estimé livré ce mois (m³) — dérivé, jamais mesuré. */
  m3: number;
}

/**
 * WJ126 — Répartition MENSUELLE INDICATIVE de la livraison d'eau (agricole) :
 * capacité annuelle ≈ `m3_jour × 365` répartie selon la PART d'ensoleillement de
 * chaque mois (`monthly_production`), le pompage solaire suivant le soleil. C'est
 * une DÉRIVATION documentée à partir de deux valeurs PRÉSENTES (m3_jour +
 * production mensuelle), pas un chiffre inventé ; la page l'étiquette clairement
 * « estimation — capacité, suit l'ensoleillement ». Renvoie `null` (bloc omis)
 * si `m3_jour` ou la série de production manque. AUCUNE série de BESOIN culture
 * n'existe dans ce payload (elle vient de QX48/WJ124) — la page n'affiche donc
 * QUE la livraison, jamais une courbe « besoin » fabriquée.
 */
export function agricoleMonthlyDelivery(
  p: Pick<ProposalResponse, 'monthly_production'>,
  k: AgricoleKpis | null,
): WaterDeliveryMonth[] | null {
  if (!k || k.m3_jour === null || k.m3_jour <= 0) return null;
  const prod = monthlySeries(p.monthly_production);
  if (!prod) return null;
  const sum = prod.reduce((a, b) => a + b, 0);
  if (sum <= 0) return null;
  const annual = k.m3_jour * 365;
  return prod.map((v, i) => ({
    monthIndex: i,
    m3: Math.round((v / sum) * annual),
  }));
}

/** WJ126 — Archétype de bloc commercial (contenu QUALITATIF, aucun chiffre). */
export interface CommercialArchetype {
  key: string;
  icon: string;
  labelFr: string;
  labelEn: string;
  labelAr: string;
  accrocheFr: string;
  accrocheEn: string;
  accrocheAr: string;
}

/**
 * WJ126 — Table d'archétypes commerciaux, MIROIR de
 * `quote_engine/commercial/categories.py METADATA` (les accroches FR sont
 * reprises telles quelles ; EN/AR sont des traductions). Contenu 100 %
 * QUALITATIF — aucun nombre (les chiffres réels viennent des KPI backend, pas
 * d'ici). Catégorie absente/inconnue → `autre` (bloc générique honnête).
 */
const COMMERCIAL_ARCHETYPES: Record<string, CommercialArchetype> = {
  hotel: {
    key: 'hotel', icon: '🏨',
    labelFr: 'Hôtel / Riad', labelEn: 'Hotel / Riad', labelAr: 'فندق / رياض',
    accrocheFr: 'Chaque nuitée mieux margée : le solaire allège la climatisation, la piscine et la blanchisserie.',
    accrocheEn: 'Better margin per night: solar eases air-conditioning, the pool and the laundry.',
    accrocheAr: 'هامش أفضل لكل ليلة: تخفّف الطاقة الشمسية التكييف والمسبح والمغسلة.',
  },
  restaurant: {
    key: 'restaurant', icon: '🍽️',
    labelFr: 'Restaurant / Café', labelEn: 'Restaurant / Café', labelAr: 'مطعم / مقهى',
    accrocheFr: 'Sécurisez la chaîne du froid et maîtrisez le poste énergie de votre cuisine.',
    accrocheEn: 'Secure the cold chain and control your kitchen’s energy costs.',
    accrocheAr: 'أمّنوا سلسلة التبريد وتحكّموا في تكلفة طاقة مطبخكم.',
  },
  commerce: {
    key: 'commerce', icon: '🛒',
    labelFr: 'Commerce / Supermarché', labelEn: 'Retail / Supermarket', labelAr: 'متجر / سوبر ماركت',
    accrocheFr: 'Froid alimentaire, éclairage et climatisation : votre base diurne couverte par le solaire.',
    accrocheEn: 'Food refrigeration, lighting and cooling: your daytime base covered by solar.',
    accrocheAr: 'تبريد الأغذية والإنارة والتكييف: قاعدتكم النهارية تغطّيها الطاقة الشمسية.',
  },
  bureau: {
    key: 'bureau', icon: '🏢',
    labelFr: 'Bureau / Siège', labelEn: 'Office / HQ', labelAr: 'مكتب / مقر',
    accrocheFr: 'Vos heures de bureau coïncident avec le soleil : autoconsommation élevée, peu d’export.',
    accrocheEn: 'Your office hours match the sun: high self-consumption, little export.',
    accrocheAr: 'ساعات عملكم تتزامن مع الشمس: استهلاك ذاتي مرتفع وتصدير قليل.',
  },
  sante: {
    key: 'sante', icon: '🏥',
    labelFr: 'Santé (clinique / cabinet)', labelEn: 'Healthcare (clinic / practice)', labelAr: 'صحة (عيادة)',
    accrocheFr: 'Continuité de service et maîtrise du coût énergie, en journée comme en garde.',
    accrocheEn: 'Service continuity and energy-cost control, by day and on call.',
    accrocheAr: 'استمرارية الخدمة وضبط تكلفة الطاقة، نهاراً وأثناء المداومة.',
  },
  ecole: {
    key: 'ecole', icon: '🎓',
    labelFr: 'École privée', labelEn: 'Private school', labelAr: 'مدرسة خاصة',
    accrocheFr: 'Consommation en période scolaire, production toute l’année : un budget énergie prévisible.',
    accrocheEn: 'Consumption during term, production all year: a predictable energy budget.',
    accrocheAr: 'استهلاك خلال الموسم الدراسي وإنتاج طوال السنة: ميزانية طاقة متوقّعة.',
  },
  hammam: {
    key: 'hammam', icon: '🧖',
    labelFr: 'Hammam / Spa / Gym', labelEn: 'Hammam / Spa / Gym', labelAr: 'حمام / سبا / نادٍ رياضي',
    accrocheFr: 'Chauffe de l’eau et confort thermique : le solaire allège votre poste énergie.',
    accrocheEn: 'Water heating and thermal comfort: solar eases your energy costs.',
    accrocheAr: 'تسخين الماء والراحة الحرارية: تخفّف الطاقة الشمسية تكلفة طاقتكم.',
  },
  boulangerie: {
    key: 'boulangerie', icon: '🥖',
    labelFr: 'Boulangerie', labelEn: 'Bakery', labelAr: 'مخبزة',
    accrocheFr: 'Le solaire couvre le froid, l’éclairage et la clim de jour — en toute transparence sur la cuisson.',
    accrocheEn: 'Solar covers refrigeration, lighting and daytime cooling — transparent about baking.',
    accrocheAr: 'تغطّي الطاقة الشمسية التبريد والإنارة والتكييف نهاراً — بشفافية بشأن الخَبز.',
  },
  froid: {
    key: 'froid', icon: '❄️',
    labelFr: 'Entrepôt froid', labelEn: 'Cold storage', labelAr: 'مستودع تبريد',
    accrocheFr: 'Sécurisez votre chaîne du froid et abaissez le coût de la base 24 h.',
    accrocheEn: 'Secure your cold chain and cut the cost of the 24 h base load.',
    accrocheAr: 'أمّنوا سلسلة التبريد واخفضوا تكلفة الحمل الأساسي على مدار 24 ساعة.',
  },
  autre: {
    key: 'autre', icon: '🏪',
    labelFr: 'Commerce', labelEn: 'Business', labelAr: 'نشاط تجاري',
    accrocheFr: 'Le solaire couvre la consommation diurne de votre établissement en autoconsommation.',
    accrocheEn: 'Solar covers your premises’ daytime consumption in self-consumption.',
    accrocheAr: 'تغطّي الطاقة الشمسية الاستهلاك النهاري لمنشأتكم عبر الاستهلاك الذاتي.',
  },
};

/**
 * WJ126 — Résout l'archétype commercial d'une `categorie_commerciale` (miroir
 * du backend). Catégorie absente/inconnue → `autre` (jamais un crash, jamais un
 * bloc fabriqué) — renvoie TOUJOURS un archétype exploitable.
 */
export function commercialArchetype(category: string | null | undefined): CommercialArchetype {
  const key = String(category ?? '').trim().toLowerCase();
  return COMMERCIAL_ARCHETYPES[key] ?? COMMERCIAL_ARCHETYPES.autre;
}

/** WJ126 — Mois FR/EN/AR courts (0 = janvier) pour l'axe du mini-graphe eau. */
export const MONTHS_SHORT: Record<PropLang, string[]> = {
  fr: ['jan', 'fév', 'mar', 'avr', 'mai', 'jun', 'jul', 'aoû', 'sep', 'oct', 'nov', 'déc'],
  en: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
  ar: ['ينا', 'فبر', 'مار', 'أبر', 'ماي', 'يون', 'يول', 'غشت', 'شت', 'أكت', 'نون', 'دجن'],
};

// ════════════════════════════════════════════════════════════════════════════
// L-PROP CJ2b-bis — falaise tarifaire / régime batterie / estimation conso,
// sous-ensemble PUBLIC des blocs du moteur horaire interne (lot 4, 24/08).
// DISCIPLINE : chaque parseur renvoie `null` dès que la clé est absente ou
// que sa forme ne peut pas être validée — jamais un chiffre recalculé ni un
// défaut fabriqué côté web (CLAUDE.md, zéro chiffre inventé). Les payloads
// « anciens » (devis générés avant le lot 4) n'ont simplement pas ces clés :
// la page ne doit ni planter ni afficher un bloc vide.
// ════════════════════════════════════════════════════════════════════════════

/** Bloc « falaise » client-safe — palier tarifaire actuel/visé + résiduel. */
export interface TarifBracketStory {
  trancheActuelleLibelle: string | null;
  trancheViseeLibelle: string | null;
  cibleKwhMois: number | null;
  residuelKwhMois: number | null;
}

function finiteOrNull(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

function nonEmptyStringOrNull(v: unknown): string | null {
  return typeof v === 'string' && v.trim() !== '' ? v : null;
}

/**
 * Le pitch tarifaire prêt à afficher, ou `null` quand le backend n'a rien
 * servi (clé `tranche_tarifaire` absente — devis pré-lot-4 — ou aucun des
 * quatre sous-champs n'est lisible). Chaque sous-champ manque INDÉPENDAMMENT
 * (un résiduel sans tranche nommée reste affichable) — jamais de valeur de
 * repli fabriquée à sa place.
 */
export function tarifBracketStory(
  p: Pick<ProposalResponse, 'tranche_tarifaire'>,
): TarifBracketStory | null {
  const t = p.tranche_tarifaire;
  if (!t || typeof t !== 'object') return null;
  const trancheActuelleLibelle = nonEmptyStringOrNull(t.tranche_actuelle?.libelle);
  const trancheViseeLibelle = nonEmptyStringOrNull(t.tranche_visee?.libelle);
  const cibleKwhMois = finiteOrNull(t.cible_kwh_mois);
  const residuelKwhMois = finiteOrNull(t.residuel_kwh_mois);
  if (!trancheActuelleLibelle && !trancheViseeLibelle && cibleKwhMois === null && residuelKwhMois === null) {
    return null;
  }
  return { trancheActuelleLibelle, trancheViseeLibelle, cibleKwhMois, residuelKwhMois };
}

/** Remplissage batterie moyen + couverture des glitchs (pointes rattrapées). */
export interface BatteryRegimeInfo {
  remplissageMoyenPct: number | null;
  couvertureGlitchPct: number | null;
}

/**
 * `null` quand `batterie_regime` est absent ou que ses deux champs sont
 * illisibles ensemble (rien à montrer). Un seul des deux présent reste
 * affichable — la page affiche alors seulement celui-là.
 */
export function batteryRegimeInfo(
  p: Pick<ProposalResponse, 'batterie_regime'>,
): BatteryRegimeInfo | null {
  const b = p.batterie_regime;
  if (!b || typeof b !== 'object') return null;
  const remplissageMoyenPct = finiteOrNull(b.remplissage_moyen_pct);
  const couvertureGlitchPct = finiteOrNull(b.couverture_glitch_pct);
  if (remplissageMoyenPct === null && couvertureGlitchPct === null) return null;
  return { remplissageMoyenPct, couvertureGlitchPct };
}

/** Un palier de capacité du mini-balayage de stockage — batterie « toujours pleine ». */
export interface StoragePalier {
  nbPacks: number;
  capaciteKwh: number;
  coutTtc: number | null;
  remplissageMoyenPct: number | null;
  /** Période de retour DU PALIER, en années — moteur (`payback_annees`), jamais
   *  recalculée ici. `null` quand le moteur ne la donne pas : on l'OMET. */
  paybackAnnees: number | null;
  /** Économie annuelle DU PALIER (MAD) — moteur (`economie_mad`). `null` ⇒ omise. */
  economieMad: number | null;
}

/** Le premier palier REFUSÉ — au-delà, la batterie ne se rechargerait plus chaque jour. */
export interface StoragePalierRefuse {
  nbPacks: number;
  capaciteKwh: number;
  remplissagePireMoisPct: number | null;
}

/** Mini-balayage de stockage public : paliers retenus + premier refusé. */
export interface StorageSweepInfo {
  paliers: StoragePalier[];
  refuse: StoragePalierRefuse | null;
}

/**
 * `null` quand `balayage_stockage` est absent ou qu'aucun palier retenu ni
 * refusé n'est lisible — rien à montrer, le sélecteur retombe sur son
 * comportement historique (curseur 0..3 sans paliers réels).
 */
export function storageSweepInfo(
  p: Pick<ProposalResponse, 'balayage_stockage'>,
): StorageSweepInfo | null {
  const b = p.balayage_stockage;
  if (!b || typeof b !== 'object') return null;
  const paliers: StoragePalier[] = [];
  for (const raw of b.paliers ?? []) {
    const nbPacks = finiteOrNull(raw?.nb_packs);
    const capaciteKwh = finiteOrNull(raw?.capacite_kwh);
    if (nbPacks === null || capaciteKwh === null) continue;
    paliers.push({
      nbPacks,
      capaciteKwh,
      coutTtc: finiteOrNull(raw?.cout_ttc),
      remplissageMoyenPct: finiteOrNull(raw?.remplissage_moyen_pct),
      paybackAnnees: finiteOrNull(raw?.payback_annees),
      economieMad: finiteOrNull(raw?.economie_mad),
    });
  }
  let refuse: StoragePalierRefuse | null = null;
  const nbPacksRefuse = finiteOrNull(b.refuse?.nb_packs);
  const capaciteKwhRefuse = finiteOrNull(b.refuse?.capacite_kwh);
  if (nbPacksRefuse !== null && capaciteKwhRefuse !== null) {
    refuse = {
      nbPacks: nbPacksRefuse,
      capaciteKwh: capaciteKwhRefuse,
      remplissagePireMoisPct: finiteOrNull(b.refuse?.remplissage_pire_mois_pct),
    };
  }
  if (paliers.length === 0 && refuse === null) return null;
  return { paliers, refuse };
}

// ── P2-C (ordre fondateur 25/08/2026, soir) — SÉLECTEUR DE PALIERS BATTERIE ──
// « add more than just 2 batteries in the web page battery option ; extra
// batteries might add extra panels with extra cost, that is still fine ».
// CONTRAT PROPRE `paliers_batterie` (racine du payload), servi par une lane
// backend parallèle — distinct de `balayage_stockage` ci-dessus qui alimente
// le simulateur à curseur ailleurs sur la page.

/**
 * Un palier de capacité batterie du sélecteur public, sanitisé champ par
 * champ : toute valeur non numérique finie devient `null` — jamais un défaut
 * fabriqué. `capaciteKwh` est le seul champ requis (c'est ce qui nomme la
 * pilule) ; un palier sans capacité lisible est ignoré par `paliersBatterie`.
 */
export interface PalierBatterie {
  capaciteKwh: number;
  nbBatteries5: number | null;
  nbBatteries10: number | null;
  nbPanneaux: number | null;
  puissanceKwc: number | null;
  prixTtc: number | null;
  economiesAnnuelles: number | null;
  paybackAnnees: number | null;
  /** `false` UNIQUEMENT quand le moteur l'affirme explicitement — absent/`true` ⇒ palier servable. */
  remplissageOk: boolean;
  /** `true` UNIQUEMENT quand le moteur l'affirme explicitement — c'est le palier du devis réel. */
  retenu: boolean;
}

/**
 * Les paliers de capacité batterie du sélecteur public (carte « Avec
 * batterie », section #options). Liste VIDE quand la clé `paliers_batterie`
 * est absente, n'est pas un tableau, ou qu'aucune entrée n'a de
 * `capacite_kwh` lisible — le sélecteur ne rend alors RIEN, la carte reste
 * strictement celle d'aujourd'hui.
 */
export function paliersBatterie(
  p: Pick<ProposalResponse, 'paliers_batterie'>,
): PalierBatterie[] {
  const raw = p?.paliers_batterie;
  if (!Array.isArray(raw)) return [];
  const out: PalierBatterie[] = [];
  for (const entry of raw) {
    if (!entry || typeof entry !== 'object') continue;
    const capaciteKwh = finiteOrNull(entry.capacite_kwh);
    if (capaciteKwh === null) continue;
    out.push({
      capaciteKwh,
      nbBatteries5: finiteOrNull(entry.nb_batteries_5),
      nbBatteries10: finiteOrNull(entry.nb_batteries_10),
      nbPanneaux: finiteOrNull(entry.nb_panneaux),
      puissanceKwc: finiteOrNull(entry.puissance_kwc),
      prixTtc: finiteOrNull(entry.prix_ttc),
      economiesAnnuelles: finiteOrNull(entry.economies_annuelles),
      paybackAnnees: finiteOrNull(entry.payback_annees),
      remplissageOk: entry.remplissage_ok !== false,
      retenu: entry.retenu === true,
    });
  }
  return out;
}

/** Le palier RETENU pour ce devis — ses chiffres restent ceux du document
 *  officiel, jamais recalculés. `null` quand aucun palier n'est marqué `retenu`
 *  (repli honnête : le sélecteur n'affiche alors aucune pré-sélection « retenue »). */
export function palierBatterieRetenu(paliers: PalierBatterie[]): PalierBatterie | null {
  return paliers.find((palier) => palier.retenu) ?? null;
}

/** Libellés FR des ajouts d'estimation de consommation — mêmes clés que le
 *  moteur horaire interne (chauffe-eau/VE/clim/piscine). */
const ESTIMATION_CONSO_AJOUT_LABELS: Record<string, string> = {
  chauffe_eau: 'Chauffe-eau électrique',
  ve: 'Véhicule électrique',
  clim: 'Climatisation',
  piscine: 'Piscine',
};

export interface EstimationConsoAjout {
  cle: string;
  libelle: string;
  valeurs: number[];
}

export interface EstimationConsoAffichable {
  base: number[];
  total: number[];
  ajouts: EstimationConsoAjout[];
}

function isValidMonthly12(a: unknown): a is number[] {
  return Array.isArray(a) && a.length === 12 && a.every((v) => typeof v === 'number' && Number.isFinite(v));
}

/**
 * Décomposition mensuelle prête à l'affichage, ou `null` quand `base_mensuelle`
 * / `totale_mensuelle` ne sont pas EXACTEMENT 12 nombres finis chacun. Chaque
 * ligne d'ajout n'apparaît que si sa propre série de 12 est valide — une clé
 * d'ajout illisible est simplement omise, jamais remplacée par des zéros.
 */
export function estimationConsoAffichable(
  p: Pick<ProposalResponse, 'estimation_conso'>,
): EstimationConsoAffichable | null {
  const e = p.estimation_conso;
  if (!e || typeof e !== 'object') return null;
  const base = e.base_mensuelle;
  const total = e.totale_mensuelle;
  if (!isValidMonthly12(base) || !isValidMonthly12(total)) return null;
  const ajoutsSrc = e.ajouts && typeof e.ajouts === 'object' ? (e.ajouts as Record<string, unknown>) : {};
  const ajouts: EstimationConsoAjout[] = Object.keys(ajoutsSrc)
    .filter((cle) => isValidMonthly12(ajoutsSrc[cle]))
    .map((cle) => ({
      cle,
      libelle: ESTIMATION_CONSO_AJOUT_LABELS[cle] ?? cle,
      valeurs: ajoutsSrc[cle] as number[],
    }));
  return { base, total, ajouts };
}

// ════════════════════════════════════════════════════════════════════════════
// L-PROP TASK2 — « Une journée type » PAR DEVIS (production vs consommation,
// 4 petits multiples janvier/avril/juillet/novembre). MÊME discipline « tout
// ou rien » que `apps/web/src/lib/jourTypeData.ts hasJourTypeData()` : un jeu
// PARTIEL serait plus trompeur qu'utile, les quatre mois sont conçus pour se
// comparer entre eux.
// ════════════════════════════════════════════════════════════════════════════

export type ProposalJourTypeMonthId = 1 | 4 | 7 | 11;

export interface ProposalJourTypeMonth {
  /** 24 valeurs — puissance PRODUITE moyenne de chaque heure du jour moyen (kW). */
  prodKw: number[];
  /** 24 valeurs — puissance CONSOMMÉE moyenne de chaque heure du jour moyen (kW). */
  consoKw: number[];
  consoJourKwh: number;
  prodJourKwh: number;
  autoconsommeKwh: number;
  surplusKwh: number;
}

export const PROPOSAL_JOUR_TYPE_MONTH_IDS: readonly ProposalJourTypeMonthId[] = [1, 4, 7, 11];

export const PROPOSAL_JOUR_TYPE_MONTH_LABELS: Record<ProposalJourTypeMonthId, { fr: string; en: string; ar: string }> = {
  1: { fr: 'Janvier', en: 'January', ar: 'يناير' },
  4: { fr: 'Avril', en: 'April', ar: 'أبريل' },
  7: { fr: 'Juillet', en: 'July', ar: 'يوليوز' },
  11: { fr: 'Novembre', en: 'November', ar: 'نونبر' },
};

function isValidHourly24(a: unknown): a is number[] {
  return Array.isArray(a) && a.length === 24 && a.every((v) => typeof v === 'number' && Number.isFinite(v) && v >= 0);
}

/**
 * Les 4 mois « jour type » prêts à l'affichage, ou `null` tant que le backend
 * ne sert pas encore `jours_types` (clé absente aujourd'hui — voir le
 * [HANDOFF] sur `ProposalResponse.jours_types`), qu'aucun devis ne l'a, ou que
 * l'un des quatre mois est illisible : PAS de jeu partiel affiché.
 */
export function proposalJoursTypes(
  p: Pick<ProposalResponse, 'jours_types'>,
): Record<ProposalJourTypeMonthId, ProposalJourTypeMonth> | null {
  const src = p.jours_types;
  if (!src || typeof src !== 'object') return null;
  const out: Partial<Record<ProposalJourTypeMonthId, ProposalJourTypeMonth>> = {};
  for (const m of PROPOSAL_JOUR_TYPE_MONTH_IDS) {
    const entry = (src as Record<string, unknown>)[String(m)];
    if (!entry || typeof entry !== 'object') continue;
    const e = entry as Record<string, unknown>;
    if (!isValidHourly24(e.prod_kw) || !isValidHourly24(e.conso_kw)) continue;
    const consoJourKwh = finiteOrNull(e.conso_jour_kwh);
    const prodJourKwh = finiteOrNull(e.prod_jour_kwh);
    const autoconsommeKwh = finiteOrNull(e.autoconsomme_kwh);
    const surplusKwh = finiteOrNull(e.surplus_kwh);
    if (consoJourKwh === null || prodJourKwh === null || autoconsommeKwh === null || surplusKwh === null) continue;
    out[m] = { prodKw: e.prod_kw, consoKw: e.conso_kw, consoJourKwh, prodJourKwh, autoconsommeKwh, surplusKwh };
  }
  return PROPOSAL_JOUR_TYPE_MONTH_IDS.every((m) => !!out[m])
    ? (out as Record<ProposalJourTypeMonthId, ProposalJourTypeMonth>)
    : null;
}


// ── COUVBAT — LA COUVERTURE DE LA CONSOMMATION, CRAN PAR CRAN ──────────────
// Ordre fondateur du 26/08/2026 : « en déplaçant le curseur, montrer ce que la
// batterie choisie COUVRE de ma consommation, jour ET nuit ». Rien n'est
// calculé ici : ces fonctions LISENT et VALIDENT le bloc `couverture_batterie`
// servi par le moteur horaire. Une entrée illisible est IGNORÉE, jamais
// complétée par une estimation locale (règle « zéro chiffre inventé »).

/** Les trois bandes horaires d'un jour type, telles que le moteur les sert. */
export interface BatteryCoverageHours {
  /** 24 kWh couverts par le solaire DIRECT (min(conso, prod) de l'heure). */
  direct: number[];
  /** 24 kWh couverts par la BATTERIE (ce qu'elle restitue à cette heure). */
  battery: number[];
  /** 24 kWh importés du RÉSEAU (le reste). */
  grid: number[];
  /**
   * % de la consommation DE CE JOUR-LÀ couverte (direct + batterie), servi par
   * le moteur. Distinct du taux ANNUEL du cran : la ligne de chiffres qui
   * entoure le graphe parle du jour AFFICHÉ, jamais de l'année — sinon deux
   * grandeurs différentes voisineraient sans le dire.
   */
  couverturePct: number;
}

/** Un cran du curseur : son année et ses quatre jours types. */
export interface BatteryCoverageStep {
  nbPacks: number;
  capaciteKwh: number;
  /** % de la consommation ANNUELLE couverte (direct + batterie). */
  couverturePct: number;
  directAnnuelKwh: number;
  batterieAnnuelKwh: number;
  reseauAnnuelKwh: number;
  /** `false` ⇒ ce toit ne remplirait pas cette banque tous les jours. */
  seRemplitTousLesJours: boolean;
  /** Indexé par mois (« 1 »/« 4 »/« 7 »/« 11 »). */
  joursTypes: Record<string, BatteryCoverageHours>;
}

/** Le repère « autonomie complète » : jour + nuit, et son honnêteté. */
export interface BatteryFullAutonomy {
  nbPacks: number;
  capaciteKwh: number;
  /** `false` ⇒ à afficher HORS de la plage recommandée, jamais comme offre. */
  seRemplitTousLesJours: boolean;
  /** Le plus grand nombre de packs que ce toit remplit CHAQUE jour. */
  nbPacksRemplissables: number;
  capaciteRemplissableMaxKwh: number;
  /** % de consommation couverte à ce nombre de packs (`null` si non servi). */
  couverturePct: number | null;
  /** Le curseur atteint-il ce cran ? */
  dansLeCurseur: boolean;
  /** Mois du jour type le plus gourmand (celui qui dicte le repère). */
  mois: number | null;
}

export interface BatteryCoverageInfo {
  /** Capacité UTILE d'un pack DU DEVIS (règle CAPUTIL) — jamais un catalogue. */
  capaciteUtilePackKwh: number;
  consoAnnuelleKwh: number | null;
  nbPacksMax: number;
  pas: BatteryCoverageStep[];
  autonomie: BatteryFullAutonomy | null;
}

function coverageHours(raw: unknown): BatteryCoverageHours | null {
  if (!raw || typeof raw !== 'object') return null;
  const r = raw as Record<string, unknown>;
  if (!isValidHourly24(r.direct_kwh) || !isValidHourly24(r.batterie_kwh)
      || !isValidHourly24(r.reseau_kwh)) return null;
  // Le taux du jour est SERVI : sans lui, la page n'aurait plus de source
  // unique pour la ligne de chiffres qui entoure le graphe — on écarte le mois
  // plutôt que de le calculer soi-même.
  const couverturePct = finiteOrNull(r.couverture_pct);
  if (couverturePct === null) return null;
  return {
    direct: r.direct_kwh, battery: r.batterie_kwh, grid: r.reseau_kwh,
    couverturePct,
  };
}

/**
 * `null` quand `couverture_batterie` est absent, illisible, ou qu'aucun cran
 * exploitable n'en sort — la page garde alors EXACTEMENT son affichage d'avant
 * (simulateur client), jamais un bloc à moitié rempli.
 */
export function batteryCoverageInfo(
  p: Pick<ProposalResponse, 'couverture_batterie'>,
): BatteryCoverageInfo | null {
  const b = p.couverture_batterie;
  if (!b || typeof b !== 'object') return null;
  const packKwh = finiteOrNull(b.capacite_utile_pack_kwh);
  if (packKwh === null || packKwh <= 0) return null;
  const pas: BatteryCoverageStep[] = [];
  for (const raw of (Array.isArray(b.pas) ? b.pas : []) as unknown[]) {
    if (!raw || typeof raw !== 'object') continue;
    const r = raw as Record<string, unknown>;
    const nbPacks = finiteOrNull(r.nb_packs);
    const capaciteKwh = finiteOrNull(r.capacite_kwh);
    const couverturePct = finiteOrNull(r.couverture_pct);
    if (nbPacks === null || capaciteKwh === null || couverturePct === null) continue;
    const joursTypes: Record<string, BatteryCoverageHours> = {};
    const src = (r.jours_types ?? {}) as Record<string, unknown>;
    for (const mois of Object.keys(src)) {
      const heures = coverageHours(src[mois]);
      if (heures) joursTypes[mois] = heures;
    }
    pas.push({
      nbPacks: Math.trunc(nbPacks),
      capaciteKwh,
      couverturePct,
      directAnnuelKwh: finiteOrNull(r.direct_annuel_kwh) ?? 0,
      batterieAnnuelKwh: finiteOrNull(r.batterie_annuel_kwh) ?? 0,
      reseauAnnuelKwh: finiteOrNull(r.reseau_annuel_kwh) ?? 0,
      seRemplitTousLesJours: r.se_remplit_tous_les_jours !== false,
      joursTypes,
    });
  }
  if (pas.length === 0) return null;
  pas.sort((a, c) => a.nbPacks - c.nbPacks);

  let autonomie: BatteryFullAutonomy | null = null;
  const a = (b.autonomie_complete ?? null) as Record<string, unknown> | null;
  if (a && typeof a === 'object') {
    const nbPacks = finiteOrNull(a.nb_packs);
    const capaciteKwh = finiteOrNull(a.capacite_kwh);
    if (nbPacks !== null && nbPacks > 0 && capaciteKwh !== null) {
      autonomie = {
        nbPacks: Math.trunc(nbPacks),
        capaciteKwh,
        seRemplitTousLesJours: a.se_remplit_tous_les_jours === true,
        nbPacksRemplissables: Math.max(
          0, Math.trunc(finiteOrNull(a.nb_packs_remplissables) ?? 0)),
        capaciteRemplissableMaxKwh: finiteOrNull(a.capacite_remplissable_max_kwh) ?? 0,
        couverturePct: finiteOrNull(a.couverture_pct),
        dansLeCurseur: a.dans_le_curseur === true,
        mois: finiteOrNull(a.mois),
      };
    }
  }
  return {
    capaciteUtilePackKwh: packKwh,
    consoAnnuelleKwh: finiteOrNull(b.conso_annuelle_kwh),
    nbPacksMax: Math.trunc(
      finiteOrNull(b.nb_packs_max) ?? pas[pas.length - 1].nbPacks),
    pas,
    autonomie,
  };
}


// ── L-PCMP — les trois silhouettes d'occupation, PRÊTES À AFFICHER ──────────
// Aucune économie n'est calculée ici : cette fonction ne fait que LIRE et
// VALIDER les blocs déjà calculés par le moteur (règle « zéro chiffre
// inventé »). Un bloc dont l'économie de base est illisible est OMIS — jamais
// complété par une estimation locale.

/** L'installation que le moteur retient comme optimale POUR CETTE silhouette. */
export interface OccupancyOptimal {
  kwc: number;
  panneaux: number | null;
  batterieKwh: number;
  avecBatterie: boolean;
  economieMad: number | null;
  /**
   * `null` quand la comparaison n'a pas pu être faite côté serveur — la page
   * se tait alors plutôt que d'affirmer « déjà optimal ».
   */
  identiqueAuDevis: boolean | null;
}

/** Un comportement d'occupation, avec ses chiffres SERVEUR. */
export interface OccupancyScenario {
  occupancy: OccupancyId;
  estProfilReel: boolean;
  economieSansMad: number;
  economieAvecMad: number | null;
  tauxAutoconsoSansPct: number | null;
  tauxAutoconsoAvecPct: number | null;
  couvertureSansPct: number | null;
  couvertureAvecPct: number | null;
  optimal: OccupancyOptimal | null;
}

/** Le comparatif complet des silhouettes d'occupation. */
export interface OccupancyScenarios {
  /** Le profil RÉELLEMENT déclaré par le client — sélectionné par défaut. */
  profilReel: OccupancyId | null;
  kwcDevis: number | null;
  batterieKwhDevis: number;
  avecBatterie: boolean;
  note: string | null;
  scenarios: OccupancyScenario[];
}

function isOccupancyId(v: unknown): v is OccupancyId {
  return v === 'presence_jour' || v === 'absence_jour' || v === 'presence_partielle';
}

/**
 * `null` quand `profils_comparatifs` est absent, illisible, ou qu'aucune
 * silhouette n'est exploitable — la page masque alors la section entière et
 * garde son affichage d'avant, exactement comme pour `balayage_stockage`.
 */
export function occupancyScenarios(
  p: Pick<ProposalResponse, 'profils_comparatifs'>,
): OccupancyScenarios | null {
  const b = p.profils_comparatifs;
  if (!b || typeof b !== 'object') return null;
  const scenarios: OccupancyScenario[] = [];
  for (const raw of b.profils ?? []) {
    const occupancy = raw?.occupation;
    const economieSansMad = finiteOrNull(raw?.economie_sans_mad);
    if (!isOccupancyId(occupancy) || economieSansMad === null) continue;
    const opt = raw?.optimal;
    const optKwc = finiteOrNull(opt?.kwc);
    scenarios.push({
      occupancy,
      estProfilReel: raw?.est_profil_reel === true,
      economieSansMad,
      economieAvecMad: finiteOrNull(raw?.economie_avec_mad),
      tauxAutoconsoSansPct: finiteOrNull(raw?.taux_autoconso_sans_pct),
      tauxAutoconsoAvecPct: finiteOrNull(raw?.taux_autoconso_avec_pct),
      couvertureSansPct: finiteOrNull(raw?.couverture_sans_pct),
      couvertureAvecPct: finiteOrNull(raw?.couverture_avec_pct),
      optimal: optKwc === null || optKwc <= 0 ? null : {
        kwc: optKwc,
        panneaux: finiteOrNull(opt?.panneaux),
        batterieKwh: finiteOrNull(opt?.batterie_kwh) ?? 0,
        avecBatterie: opt?.avec_batterie === true,
        economieMad: finiteOrNull(opt?.economie_mad),
        identiqueAuDevis: typeof opt?.identique_au_devis === 'boolean'
          ? opt.identique_au_devis
          : null,
      },
    });
  }
  if (scenarios.length === 0) return null;
  return {
    profilReel: isOccupancyId(b.profil_reel) ? b.profil_reel : null,
    kwcDevis: finiteOrNull(b.kwc_devis),
    batterieKwhDevis: finiteOrNull(b.batterie_kwh_devis) ?? 0,
    avecBatterie: b.avec_batterie === true,
    note: nonEmptyStringOrNull(b.note),
    scenarios,
  };
}
