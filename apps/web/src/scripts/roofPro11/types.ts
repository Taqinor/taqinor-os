/**
 * Types partagés par les modules roofPro11.
 * Extraits de roof-tool-pro11.ts (split modulaire 2026-06-20) — INCHANGÉS.
 */
import { type RoofTypeSelect } from '../../lib/roofTypeSelect';
import { type ImagerySettings } from '../../lib/roofConfig';
import { type PackResult, type PanelGrid, type ConfigFamily, OBSTACLE_CLEARANCE_M } from '../../lib/estimatorBrainV2';
import {
  clampDim,
  obstacleRing,
  ringDimsM,
  type Obstacle,
  type ObstacleType,
  type ObstacleProvenance,
} from '../../lib/obstacles';
import { type SerializeMeta, type DevisPayload, type RawContourPoint, type SerializedZoneGeometry } from './prefill';
import { type AreaResult } from '../../lib/roofAreas';
import { geodesicAreaM2, geodesicPerimeterM, isSimplePolygon, type LngLat } from '../../lib/roof';
import { type ProductionSource, type SpecificDateProfile } from '../../lib/productionEngine';
import { type SerializedEdge } from './edges';
import { type CoucheElectrique } from './electrique3d';
import { type BatimentOsmServeur } from './batiment'; // CALX132 câblage

/** Rendu 3D d'une config (scene3d) : mêmes pack/grid/tilt/family, occupation éventuellement
 *  personnalisée. Signature PARTAGÉE de scene3d, layoutEditor et optimizer. */
export type RenderSceneFn = (
  pack: PackResult,
  grid: PanelGrid,
  tiltDeg: number,
  family: ConfigFamily,
  maxCount: number,
  flush?: boolean,
  occupiedSet?: Set<number>,
) => void;

/** ACAL994 — l'économie de l'année 1 du bloc `chiffrage` (contrat calepinage_design_context) : LUE, jamais calculée ici. */
export interface ChiffrageAtelier {
  economie_annee1_mad?: { valeur: number | null; etat: string; option?: string | null } | null;
  /** R2-16/17 — kWc et production annuelle SERVIS (même bloc `chiffrage` : lus, jamais recalculés ici). */
  kwc?: { valeur: number | null; etat: string } | null;
  production_annuelle_kwh?: { valeur: number | null; etat: string } | null;
  /** ACAL2022 — la part production ÷ consommation de la conception SERVIE (%), lue telle quelle. */
  couverture_pct?: { valeur: number | null; etat: string } | null;
}

export interface InitOptions {
  maptilerKey: string;
  mapboxToken?: string;
  reducedMotion: boolean;
  initialQuery?: string;
  onReady?: () => void;
  // Sélecteur « type de toit » créé EAGERLY par le script de page : il détient les
  // puces `[data-rooftype]` (câblées dès le chargement, donc le bouton « Toit en
  // pente » répond avant ce boot). On honore son choix initial puis on s'abonne.
  roofType?: RoofTypeSelect;
  // W112 — mode CAPTURE CLIENT (page /devis/mon-toit) : ne construit QUE la carte +
  // le géocodeur + le pin/tracé. AUCUN optimiseur, AUCUNE scène 3D, AUCUNE carte de
  // production — les panneaux n'apparaissent JAMAIS. Le flux complet (non-capture)
  // reste octet pour octet identique quand le drapeau est absent/false.
  captureOnly?: boolean;
  // W112 — callback déclenché à chaque changement du pin/tracé en mode capture
  // (pin {lat,lng} | null + tracé optionnel [[lat,lng],…]). Permet à la page de
  // refléter l'état (activer le bouton « envoyer », pré-remplir l'adresse, etc.).
  // W2 — `address` (libellé géocodé INVERSE depuis le repère) est joint quand il est
  // disponible : un changement géométrique du pin déclenche d'abord un onCaptureChange
  // SANS adresse (immédiat), puis un second AVEC `address` une fois le reverse-geocode
  // résolu. La page lit `pin.lat`/`pin.lng` comme GPS et `address` comme adresse.
  onCaptureChange?: (state: { pin: { lat: number; lng: number } | null; outline: Array<[number, number]>; address?: string | null }) => void;
  // W113 — HYDRATATION optionnelle depuis un lead (le fetch est fait par la page,
  // pas par l'outil). Sème le pin/tracé de la carte + les champs contact à partir
  // d'un payload lead. Le boot complet reste inchangé quand `hydrate` est absent.
  // PV19 — `devis` (optionnel) hydrate depuis un DEVIS existant : son design (layout
  // sérialisé) et sa CIBLE vendue, qui impose le nombre de panneaux. Le boot lead reste
  // strictement inchangé quand `devis` est absent.
  hydrate?: { lead?: LeadPayload; devis?: DevisPayload };
  // W114/W115 — l'outil expose une petite API à la page (sérialiser le layout
  // finalisé, capturer le PNG 3D) une fois le boot complet terminé. Invoqué
  // seulement en boot complet (jamais en capture). Absent → comportement inchangé.
  onApiReady?: (api: RoofToolApi) => void;
  /** ACAL68 — appelé UNE fois, quand le document a été hydraté (fin du `load` de la carte) :
   *  c'est là que la page hôte pose le fond du document (`fondDuDocument`/`poserFond`). */
  onHydrationTerminee?: () => void;
  /** T4-U4-013 — la page hôte (calepinage de l'ERP) SUIT la localisation du site : `initial` = l'état
   *  lu (provenance, `null` = non localisé, `undefined` = document ancien), `ecouter` reçoit chaque
   *  changement. Absent ⇒ aucune clé `siteLocalise` écrite (site public, autres modes : inchangés). */
  suiviSite?: {
    initial: 'lead' | 'adresse' | 'epingle' | 'trace' | null | undefined;
    ecouter?: (etat: 'lead' | 'adresse' | 'epingle' | 'trace' | null | undefined) => void;
    /** T4-X2-005 — le point de repli SERVI (`calepinage.site_de_repli_point`) : tant que le site n'est pas localisé,
     *  les calculs solaires de l'atelier (pas entre rangées…) y sont calés, comme la simulation. Absent ⇒ le tracé. */
    repli?: { lat: number; lon: number; libelle: string } | null;
  };
  // PV75 — étude BANCABLE (P50/P90 + ratio de performance + cascade des pertes),
  // injectée par la page HÔTE (ToitureDesign.jsx) une fois lue depuis
  // `Devis.etude_params.simulation.pr` (contrat `contract_samples/simulation.json`,
  // moteur PV69/PV74) : l'outil n'appelle JAMAIS Django lui-même — discipline « le
  // navigateur ne parle qu'à la page hôte, la page hôte parle à l'API ». Absent/null
  // → fenêtre de production STRICTEMENT INCHANGÉE (comportement historique, golden).
  bankable?: BankableProduction | null;
  // L-MAP (fondateur 26/08/2026) — contour ORIGINAL du client, `[lat, lng]`
  // OU `{lat, lng}` × n (les DEUX formes réelles de `Lead.roof_outline` — la
  // revue adversariale du 26/08 a prouvé qu'ignorer la forme objet fait
  // échouer l'affichage EN SILENCE pour ces leads), pour un calque
  // GÉO-RÉFÉRENCÉ passif et NON ÉDITABLE sur la carte (voir
  // `referenceContourRing` dans `prefill.ts`, MÊME bornage lat/lng que
  // `normaliserContour` côté ERP) — distinct de `hydrate.lead.roof_outline`/
  // `hydrate.devis.geometrie.roof_outline`, qui SÈMENT la zone active
  // éditable et peuvent diverger du dessin d'origine après une édition.
  // L'appelant (ToitureDesign.jsx) ne transmet cette clé QUE si son propre
  // `contourExploitable` (MÊME predicat) l'accepte déjà — jamais un contour
  // que la bascule/légende hôte refuse. Le tunnel public (`captureBoot.ts`,
  // jamais cette option) et la preview (`preview/toiture-3d-pro-11.astro`)
  // ne la passent jamais : absente → calque vide, boot octet pour octet
  // inchangé.
  referenceContour?: RawContourPoint[] | null;
  // CAL47/CAL48 — section `imagerie` des réglages société (pays, fournisseur actif,
  // fournisseurs autorisés, calques optionnels, attribution saisie), lue par la page
  // HÔTE sur `GET /api/django/calepinage/parametres/` et transmise telle quelle.
  // Absente/vide ⇒ imagerie et géocodage strictement inchangés (Maroc, MapTiler/Mapbox).
  imagery?: ImagerySettings | null;
  // CALX109 — le CATALOGUE DE MODULES de la société, tel que le serveur le sert
  // (`GET /api/django/calepinage/calepinages/<pk>/modules-disponibles/`, contrat
  // `calepinage_modules_disponibles.json`), lu par la page HÔTE et transmis tel quel :
  // l'outil n'appelle JAMAIS Django lui-même (même discipline que `imagery` et
  // `bankable` ci-dessus). La réponse se lit avec `roofPro11/moduleSelect.ts`
  // (`lireModulesDisponibles`), qui en tire les modèles choisissables et ceux qui
  // restent GRISÉS avec leur motif. Absente/vide ⇒ l'atelier pose le module par
  // défaut, NOMMÉ (`MODULE_PAR_DEFAUT_ATELIER`) — comportement d'aujourd'hui, au
  // panneau près. Le type reste volontairement OPAQUE ici : la forme fait foi dans
  // le contrat, et `moduleSelect.ts` est le seul à la lire.
  modulesDisponibles?: unknown;
  /** ACAL777 — facture mensuelle (MAD) du lead servie par le serveur (mode calepinage) : repli d'AFFICHAGE des cartes, jamais écrite au document. */
  factureMensuelleMad?: number | null;
  /** ACAL778 — un devis est lié au calepinage (`contexte.calepinage.devis_lie` non nul) : la carte Recommandation ajoute « Le chiffre du devis est dans l'onglet Économie ». Jamais déduit de `cibleVendue`. */
  devisLie?: boolean;
  /** ACAL994 — bloc `chiffrage` SERVI par design-context (ERP seul ; `null` = rien de servi / hors ligne ⇒ la carte dit « estimation »).
   *  Absent (site public) ⇒ aucune étiquette, rendu inchangé. */
  chiffrage?: ChiffrageAtelier | null;
  /** ACAL80 — point de rendement PVGIS (URL) ; `null` = aucune requête (l'ERP n'a pas la
   *  route `/api/roof-yield` d'apps/web : repli sur la table committée). Absent = le défaut
   *  `/api/roof-yield` des pages publiques. */
  rendementPvgis?: string | null;
  /** ACAL311 — la consommation PROPOSÉE par le serveur (`POST calepinages/<pk>/consommation/
   *  proposer/`, contrat `calepinage_consommation_proposee.json`), fournie par la page HÔTE
   *  (même patron que `rendementPvgis`) : elle rend la réponse 200, ou rejette avec le refus
   *  DÉCODÉ `{message, champs}`. `null` = page hôte sans serveur (kWh affichés « estimation
   *  (barème indicatif) ») ; absente = pages publiques, comportement inchangé. */
  proposerConsommation?: ((corps: import('./consumption').CorpsPropositionConsommation) =>
    Promise<import('./consumption').PropositionConsommation>) | null;
  /** ACAL918 — demande au MOTEUR le plan d'une surface de pose enregistrée (`POST calepinage/moteur/pose/`), fournie
   *  par la page hôte (l'atelier ne parle jamais à Django) : rend la réponse du moteur, ou rejette avec une
   *  `Error` dont le message est le motif français. Absente (pages publiques) = comportement d'avant. */
  demanderPlanSurface?: (surface: import('./poseSurfaces').SurfacePose) => Promise<unknown>;
  /** ACAL840 — la lecture d'une PHOTO de facture (`GET`/`POST calepinages/<pk>/consommation/lire-facture/`,
   *  contrat `calepinage_consommation_photo_facture.json`), fournie par la page hôte (même patron
   *  que `proposerConsommation`). `null`/absente = aucun bouton « Lire une photo de facture ». */
  lireFactureConsommation?: import('./consommationMois').OptionLireFacture | null;
  /** ERR-ACAL311-PANNEAU-ABSENT-ERP — production PAR 1 kWc du plan courant, fournie par une
   *  page hôte SANS fenêtre de production ni `/api/roof-production` (l'ERP) : sans elle,
   *  « Affiner ma consommation » reste masqué faute de plan. Absente = pages publiques,
   *  comportement inchangé (la fenêtre de production interroge sa route). */
  productionAtelier?: ((cfg: ProdConfig) => import('../../lib/productionEngine').PerKwcProduction | null) | null;
  /** LOT 6 (D-ACAL-136) — posé par la seule visionneuse au soleil (`viewerFullBoot.ts`) quand elle teintera le pan
   *  actif : verre et œil de l'atelier (`oeilCamera.ts::verreEtOeilAtelier`). Absent = rendu inchangé. */
  teinteAccesVisible?: boolean;
  /** Lot 8 (D-ACAL-132) — posé par la seule visionneuse pleine des liens de CONFIANCE (`viewerFullBoot.ts`, quand
   *  `visionneuse_soleil` est servie) : l'habit « Montrer au client » de l'ERP (jeu « presentation », ciel qui suit le
   *  soleil, verre sans vernis, sol qui reçoit les ombres). Ignoré par l'ERP (`productionAtelier`). Absent = inchangé. */
  presentationClient?: boolean;

  // CALX104/CALX403 — les deux sections des réglages société que l'ATELIER consomme
  // (`zones_types` pour les gabarits d'obstacle, `degagements` pour la largeur d'allée
  // de circulation par pays, CALX402), lues par la page HÔTE sur
  // `GET /api/django/calepinage/parametres/` et transmises TELLES QUELLES — l'outil
  // n'appelle jamais Django lui-même. Le PAYS, lui, est déjà porté par `imagery.pays`
  // (CAL47) : on ne le redemande pas. Absente/vide ⇒ AUCUN gabarit proposé et AUCUNE
  // largeur d'allée préremplie — jamais une cote ni une largeur de repli.
  reglagesAtelier?: ReglagesAtelier | null;
}

/** CALX104/CALX403 — le sous-ensemble des réglages société que l'atelier lit. Les sections
 *  gardent la forme BRUTE servie par l'API (clés en `snake_case`) : l'atelier les
 *  interprète, il ne les réécrit pas. */
export interface ReglagesAtelier {
  /** Section `zones_types` (CAL74) — les gabarits saisis par la société. */
  zones_types?: unknown;
  /** Section `degagements` (CAL71/CALX402) — dont `allees_circulation` par pays. */
  degagements?: unknown;
  /** ACAL962 — le pays réglé de la société (`imagerie.pays`), `null` si rien n'est réglé. */
  pays?: string | null;
  /** ACAL714 — `{seuil_acces_retrait, ombrage_borne_courant_pct, ombrage_borne_importante_pct}` (`{valeur, source, reference}` chacun), ou `null`. */
  simulation?: unknown;
}

/** PV75 — sous-ensemble bancable de `simulation.pr` (P50/P90/PR/cascade des pertes),
 *  tel que consommé par la fenêtre de production. `loss_breakdown` associe un poste
 *  de perte (température/salissure/ombrage/câblage/onduleur/dispersion/disponibilité…
 *  — la liste n'est pas fermée, un poste inconnu est affiché avec son libellé brut)
 *  à un pourcentage (8.0 = 8 %, pas une fraction). */
export interface BankableProduction {
  p50_kwh: number;
  p90_kwh: number;
  performance_ratio: number;
  loss_breakdown: Record<string, number>;
}

/** W114/W115 — API minimale exposée par l'outil à la page de design. */
export interface RoofToolApi {
  /** Layout finalisé sérialisé en JSON pur (zones + repère). `billKwh` optionnel.
   *  PV13 — `meta` (optionnel) porte scénario / puissance panneau / batterie / origine
   *  devis-lead : la page les CONNAÎT, l'outil ne les devine jamais. */
  serializeLayout: (billKwh?: number | null, meta?: SerializeMeta) => unknown;
  /** ACAL1329 — vrai du premier clic au dernier point d'un pan AJOUTÉ (pan actif ouvert, toit déjà tracé) : l'hôte
   *  suspend l'écriture du brouillon ; `serializeLayout` dit toujours le vrai (le pan en cours y figure). */
  ajoutDePanEnCours?: () => boolean;
  /** ACAL26 — applique UNE section du document (`horizonProfile`, `poseSurfaces`,
   *  `underlay`, `environment`, `alleeTechnique` — ACAL258) par la MÊME fonction d'hydratation que le boot
   *  (`hydratation.ts::appliquerHydratationAuCtx`) — pour les onglets du Rail. */
  appliquerSection: (cle: import('./hydratation').CleSectionAtelier, valeur: unknown) => void;
  /** ACAL286 — la table d'affectation SERVIE (`electrique.affectation[]`, avec `couleur_chaine` /
   *  `couleur_mppt`) teinte les modules du pan actif par chaîne ou par entrée MPPT ; table vide ou
   *  non servie ⇒ teinte éteinte. Aucune écriture : la teinte est dérivée du résultat serveur. */
  setAffectationChaines: (
    rows: readonly import('./scene3d').AffectationRow[] | null | undefined,
    mode?: import('./scene3d').AffectationMode,
  ) => void;
  /** ACAL71 — un contour géoréférencé [[lng, lat], …] devient un NOUVEAU pan de l'atelier
   *  (identifiant `prochainId`), refusé — motif nommé, aucun pan — s'il se croise ou sort
   *  de l'amplitude GPS. */
  ajouterPanDepuisContour: (contourLngLat: unknown) => { ok: true; id: string } | { ok: false; motif: string };
  /** ACAL531 — un obstacle PROPOSÉ par la détection du toit (contour géoréférencé + type) est posé sur le
   *  geste de l'utilisateur : provenance `DEVINE` (non engageable), hauteur vide ; refus nommé sinon. */
  ajouterObstacleDepuisContour: (contourLngLat: unknown, type: unknown) => { ok: true; id: string } | { ok: false; motif: string };
  /** Instantané PNG (data URL) de la 3D rendue, ou null. */
  snapshot: () => string | null;
  /** L-MAP — bascule d'affichage du calque de référence géo-référencé
   *  (`opts.referenceContour`). Sans effet si aucun contour n'a été fourni
   *  au boot (le calque reste vide dans les deux cas). */
  setReferenceContourVisible: (visible: boolean) => void;
  /** ACAL994 — le bloc `chiffrage` relu après « Enregistrer » : la carte Économies et le Total prennent la valeur servie. */
  majChiffrage: (chiffrage: ChiffrageAtelier | null, panneauxDevis?: number | null) => void;
  /* R2-13 — `panneauxDevis` (optionnel) : le compte du devis relu avec le contexte (`cible.panneaux`) ; omis = compte inchangé. */
  /** AP-F2 (fondateur 26/08/2026) — reseme la zone active DEPUIS le contour
   *  ORIGINAL du client (`opts.referenceContour`, MÊME source que le calque
   *  de référence) et relance l'optimiseur, pour que le commercial puisse
   *  annuler ses retouches et repartir du tracé client. Renvoie `false` sans
   *  RIEN changer si aucun contour exploitable n'a été fourni au boot
   *  (`referenceContourRing` renvoie `null`) — jamais un contour deviné. */
  recommencerDepuisTraceClient: () => boolean;
  /** CAL103 — applique la visibilité + l'opacité d'UN calque de l'atelier
   *  (identifiants et ordre : `ORDRE_RENDU_CALQUES` de `mapDraw.ts`). Le panneau
   *  de calques de l'écran hôte est la seule source d'intention. Renvoie false
   *  pour un identifiant inconnu ; un calque sans couche carte est un no-op. */
  setLayerState: (id: string, state: { visible: boolean; opacite?: number }) => boolean;
  /** CAL180 — rend la scène HORS ÉCRAN à `scale` fois la résolution d'écran et
   *  renvoie un blob PNG avec ses dimensions RÉELLES (le facteur est rabaissé si
   *  le plafond de taille l'impose). Côté navigateur : aucune image n'est postée
   *  ici, et l'affiche client existante (`roof-image`) reste inchangée. `null`
   *  quand la scène n'est pas rendable. */
  renderImageHd: (
    scale: number,
  ) => Promise<{ blob: Blob; width: number; height: number; scale: number } | null>;
  /** ACAL726 — comme `renderImageHd`, la carte d'accès solaire allumée pour la capture (année entière) puis
   *  remise dans son état ; `null` sans source d'ombrage (rien à teinter) ou scène non rendable. */
  renderCarteAccesHd: (
    scale: number,
  ) => Promise<{ blob: Blob; width: number; height: number; scale: number } | null>;
  /** ACAL896 — enregistre une orbite de 360° de la carte (10 s) ; un motif français si l'enregistrement est impossible. */
  enregistrerOrbite: (options?: import('./videoOrbite').OptionsOrbite) => Promise<import('./videoOrbite').ResultatOrbite>;
  /** ACAL537 — la scène 3D en glTF binaire (repère local), ou `null` si non rendable. */
  exporterSceneGltf: () => Promise<{ blob: Blob } | null>;
  /** ACAL435 — caméra sur l'une des quatre vues prêtes (600 ms, instantané si reduced-motion). */
  appliquerVue: (nom: 'dessus' | 'sud' | 'trois-quarts' | 'face-panneaux') => void;
  /** F6 — cadre la caméra sur TOUS les pans (sans animation, pente/cap gardés, jamais pendant un tracé) ;
   *  caméra seule, rien de sérialisé. Faux = rien à cadrer. `zoomMax` absent = plafond d'aujourd'hui (19). */
  cadrerToit: (options?: import('../../lib/roof').OptionsCadrage) => boolean;
  /** CAL104 — projection PLAN orthographique (nord en haut, cotée) de la zone
   *  ACTIVE, pour la vue 2D de l'écran hôte. Elle PROJETTE ce que la 3D a posé :
   *  même contour, mêmes modules, donc même compte et mêmes cotes. `null` tant
   *  qu'aucun contour fermé n'existe — jamais un plan inventé. */
  planView: (widthPx: number, heightPx: number) => unknown | null;
  /** CALX3 — le document d'entrée du moteur de calepinage (`{schema_version, repere,
   *  contour, surfaces, kits, parametres, obstacles, zones, engagements}`), composé
   *  depuis la scène VIVANTE à chaque appel. `null` tant qu'aucun pan ne porte un
   *  contour d'au moins 3 sommets — jamais un document creux. */
  entreeMoteur: () => import('./entreeMoteur').DocumentMoteur | null;
  /** CALX3 — repose les modules à partir du plan rendu par le moteur (ses rangées :
   *  position transversale, tronçons, compte). L'atelier est photographié avant, donc
   *  Ctrl+Z revient à la disposition précédente. `false` = rien n'a changé. */
  appliquerPlan: (resultat: unknown) => boolean;
  /** CALX3 — les huit actions de raccourci de l'atelier (`outilTrace`, `outilObstacle`,
   *  `outilZone`, `outilMesure`, `aimantation`, `supprimer`, `dupliquer`, `pleinEcran`),
   *  TOUJOURS présentes et TOUJOURS des fonctions. */
  raccourcis: Record<import('./entreeMoteur').ActionRaccourci, () => void>;
  /** CALX3 — les identifiants de calque réellement installés sur la carte, dans
   *  l'ordre de rendu (`ORDRE_RENDU_CALQUES`). Liste vide hors carte (capture, aperçu). */
  calquesDisponibles: () => string[];
  /** CALX220/221 câblage — la couche électrique de l'atelier (organes/cheminements posés
   *  en 3D, calque « Électrique »). TOUJOURS présente (`creerCoucheElectrique` la construit
   *  inconditionnellement) — `calqueDisponible()` dit si le document porte une couche. */
  electrique: CoucheElectrique;
  /** CALX132 câblage — la page hôte dépose l'empreinte OSM du bâtiment (`batiment` de
   *  `GET crm/leads/<id>/roof-footprint/`, contrat CALX106) : le panneau « Bâtiment »
   *  l'affiche en PROPOSITION, et rien n'est écrit tant que personne n'a cliqué
   *  « Reprendre ». `null`/absent efface la proposition. */
  setBatimentOsmPropose: (batiment: BatimentOsmServeur | null | undefined) => void;
  /** CALX111 câblage — l'identifiant du pan ACTIF, pour que la vue 2D de la page hôte
   *  puisse lire les numéros de module de CE pan (`registreAtelier`) au lieu d'afficher
   *  un plan sans étiquettes. Chaîne vide tant qu'aucun pan n'est actif. */
  panActifId: () => string;
  /** CALX107 câblage — le calque de fond que le document ROUVERT demande (`underlay`,
   *  contrat CALX86), ou `null`. La page hôte s'en sert pour aller chercher le FICHIER
   *  correspondant : l'outil ne parle jamais à Django. */
  fondDuDocument: () => import('./underlay').DocumentUnderlay | null;
  /** CALX107 câblage — le motif quand le document portait un `underlay` ILLISIBLE (il
   *  NOMME le champ fautif), ou `null`. Sans lui, un fond refusé disparaîtrait en
   *  silence. */
  motifFondRefuse: () => string | null;
  /** CALX107/CALX108 câblage — pose (ou retire, `null`) le fond avec la RESSOURCE fournie
   *  par la page hôte (URL pré-signée du fichier, calage à quatre coins d'une `PhotoSite`,
   *  taille du fichier). Rend `{ok:false, motif}` quand rien ne peut être peint — le motif
   *  NOMME ce qui manque, il n'est jamais muet. */
  poserFond: (
    fond: import('./underlay').DocumentUnderlay | null,
    ressource?: import('./underlay').RessourceFond,
  ) => { ok: boolean; motif?: string };
}

/** W113 — payload lead minimal consommé par l'hydratation (forme du GET
 *  /api/django/crm/leads/<id>/). Tous les champs optionnels : un champ absent
 *  ne sème rien. `roof_point` = pin {lat,lng}, `roof_outline` = les points du
 *  contour, dans une des DEUX formes RÉELLES de `Lead.roof_outline` :
 *  `[lat, lng]` (le webhook) ou `{lat, lng}` (import/saisie manuelle) — AP-F1
 *  (fondateur 26/08/2026) : élargi de `Array<[number, number]>` pour que
 *  `hydrateFromLead` accepte exactement ce que `referenceContourRing` accepte
 *  déjà (UN SEUL validateur de contour, voir prefill.ts). */
export interface LeadPayload {
  roof_point?: { lat: number; lng: number } | null;
  roof_outline?: Array<RawContourPoint> | null;
  bill_kwh?: number | null;
  fullName?: string;
  phone?: string;
  city?: string;
  [k: string]: unknown;
}

// ═══════════ PV61 — TYPES D'OBSTACLE & DÉGAGEMENT PAR TYPE ═══════════
export type { ObstacleType, ObstacleProvenance };

/** Choix du sélecteur « type d'obstacle » (libellés FR, ordre du menu). */
export const OBSTACLE_TYPES: { id: ObstacleType; label: string }[] = [
  { id: 'cheminee', label: 'Cheminée' },
  { id: 'ventilation', label: 'Ventilation / VMC' },
  { id: 'chien_assis', label: 'Chien-assis / lucarne' },
  { id: 'edicule', label: 'Édicule / local technique' },
  { id: 'antenne', label: 'Antenne / parabole' },
  { id: 'lanterneau', label: 'Lanterneau' },
  { id: 'exutoire', label: 'Exutoire de fumée' },
  { id: 'climatiseur', label: 'Climatiseur / groupe de clim' },
  { id: 'citerne', label: 'Citerne / réservoir' },
  { id: 'garde_corps', label: 'Garde-corps' },
  { id: 'joint_dilatation', label: 'Joint de dilatation' },
  { id: 'autre', label: 'Autre' },
];

/**
 * Dégagement (m) laissé autour d'un obstacle SELON SON TYPE.
 *
 * SOURCE des valeurs (règles de pose, pas des chiffres inventés) : `OBSTACLE_CLEARANCE_M`
 * (0,30 m) est le recul de base déjà appliqué à tout obstacle — il correspond au passage
 * de maintenance minimal entre un panneau et un accident de toiture. On l'ÉLARGIT pour les
 * obstacles HAUTS ou SALISSANTS, qui portent une ombre portée et demandent un accès :
 *  - cheminée 0,50 m : suie/fumées + ramonage, et une souche dépasse toujours du plan ;
 *  - chien-assis / lucarne 0,50 m : volume haut → ombre portée + accès à la fenêtre ;
 *  - édicule / local technique 0,50 m : même raison (le plus haut des trois) ;
 *  - ventilation / VMC 0,30 m : petit et bas → le recul de base suffit ;
 *  - antenne / parabole 0,30 m : encombrement faible, pas d'entretien récurrent ;
 *  - autre 0,30 m : on retombe exactement sur le comportement historique.
 * Un obstacle SANS type garde donc 0,30 m — le calepinage d'aujourd'hui, inchangé.
 */
export const CLEARANCE_BY_TYPE: Partial<Record<ObstacleType, number>> = {
  cheminee: 0.5,
  ventilation: OBSTACLE_CLEARANCE_M,
  chien_assis: 0.5,
  edicule: 0.5,
  antenne: OBSTACLE_CLEARANCE_M,
  autre: OBSTACLE_CLEARANCE_M,
};

/** ACAL499 — les types SANS valeur d'atelier (miroir de `TYPES_SANS_VALEUR_ATELIER` du serveur) :
 *  leur dégagement ne vient QUE de la société, sinon le recul de base. `CLEARANCE_BY_TYPE`
 *  n'en gagne jamais (aucune valeur publiée). */
const TYPES_SANS_VALEUR_ATELIER: readonly string[] = [
  'lanterneau', 'exutoire', 'climatiseur', 'citerne', 'garde_corps', 'joint_dilatation',
];
let degagementsSociete: Record<string, number> = {};
let sourceDegagementsSociete = '';

/** ACAL499 — retient la section `degagements` de la société (valeurs des seuls types neufs ;
 *  tout le reste est ignoré). Appelée à l'initialisation ; une section absente efface. */
export function poserDegagementsSociete(section: unknown): void {
  degagementsSociete = {};
  sourceDegagementsSociete = '';
  if (!section || typeof section !== 'object') return;
  const s = section as Record<string, unknown>;
  for (const t of TYPES_SANS_VALEUR_ATELIER) {
    const v = s[t];
    if (typeof v === 'number' && Number.isFinite(v) && v >= 0) degagementsSociete[t] = v;
  }
  if (typeof s.source === 'string') sourceDegagementsSociete = s.source.trim();
}

/** ACAL499 — d'où vient le dégagement d'un type neuf : « réglage de votre société — … » ou
 *  « recul de base, aucun dégagement société pour ce type » ; `null` pour les types historiques. */
export function motifDegagementType(type?: ObstacleType | null): string | null {
  if (!type || !TYPES_SANS_VALEUR_ATELIER.includes(type)) return null;
  if (degagementsSociete[type] == null) return 'recul de base, aucun dégagement société pour ce type';
  return `réglage de votre société${sourceDegagementsSociete ? ` — ${sourceDegagementsSociete}` : ''}`;
}

/** Dégagement (m) d'un type d'obstacle. Type absent/inconnu → `OBSTACLE_CLEARANCE_M`. */
export function clearanceForType(type?: ObstacleType | null): number {
  if (!type) return OBSTACLE_CLEARANCE_M;
  return degagementsSociete[type] ?? CLEARANCE_BY_TYPE[type] ?? OBSTACLE_CLEARANCE_M;
}

/** Dégagements (m) PARALLÈLES à une liste d'obstacles (même ordre que leurs anneaux).
 *  CALX104 — un obstacle qui porte SON PROPRE dégagement (posé depuis un gabarit de la
 *  société, avec sa source) prime sur le dégagement de son type ; sans dégagement propre,
 *  le dégagement par type s'applique inchangé. */
export function obstructionClearancesFor(
  obstacles: readonly (ObstacleForme & { type?: ObstacleType })[],
): number[] {
  return obstacles.map((o) => degagementObstacle(o));
}

// ————————————————————————————————————————————————————————————————————————
// CALX103/CALX104 — LA FORME RÉELLE D'UN OBSTACLE (POLYGONE, CERCLE)
//
// Un obstacle était TOUJOURS un rectangle centré (`centerLng`/`centerLat`/`lengthM`/
// `widthM`) : une souche en L ou un édicule biscornu ne se saisissait pas, et une
// cheminée ronde passait pour un carré. Le contrat CALX85 porte désormais la forme
// (`forme` + `contour` | `rayonM`) ; ce bloc en fait de la GÉOMÉTRIE PURE — aucun DOM,
// aucune carte, aucune constante d'ingénierie neuve.
//
// LA BOÎTE RESTE LE REPLI EXPLICITE : `lengthM`/`widthM` continuent d'exister sur chaque
// obstacle (boîte englobante du contour, ou côté du carré circonscrit au disque), pour
// que tout lecteur qui ignore `forme` — un document v2 antérieur, la 3D, un export —
// retrouve EXACTEMENT le rectangle d'aujourd'hui. Ce sont les fonctions ci-dessous qui
// donnent la forme réelle à qui sait la lire.
// ————————————————————————————————————————————————————————————————————————

/** Les trois formes du contrat CALX85. Absente ⇒ `rectangle` (comportement historique). */
export type FormeObstacle = 'rectangle' | 'polygone' | 'cercle';

/** CALX103/CALX104 — les champs de FORME qu'un obstacle peut porter, tous OPTIONNELS et
 *  additifs : un obstacle qui n'en porte aucun est le rectangle d'aujourd'hui. */
export interface ObstacleForme {
  /** Forme réelle. Absente = `rectangle`. */
  forme?: FormeObstacle;
  /** Contour [[lng, lat], …] du polygone (≥ 3 sommets), fermé implicitement. */
  contour?: LngLat[];
  /** Rayon SAISI (m) du disque, centré sur `centerLng`/`centerLat`. Jamais déduit. */
  rayonM?: number;
  /** CALX104 — dégagement PROPRE (m) hérité d'un gabarit société : il PRIME sur le
   *  dégagement du type. Absent ⇒ le dégagement par type s'applique, inchangé. */
  degagementM?: number;
  /** CALX104 — la source TEXTUELLE de ce dégagement propre, telle que la société l'a
   *  saisie. Un chiffre qui retire de la surface sans dire au nom de quoi est indéfendable. */
  sourceDegagement?: string;
}

/** Un obstacle du document, forme comprise. */
export type ObstacleEtendu = Obstacle & ObstacleForme;

/** Nombre de segments qui DESSINENT un disque. CONVENTION DE DESSIN : elle ne change ni le
 *  rayon saisi, ni l'aire annoncée — celles-ci restent calculées sur le disque exact (π r²). */
export const SEGMENTS_CERCLE_OBSTACLE = 36;

const FORME_DEG2RAD = Math.PI / 180;
import { WGS84_RADIUS as FORME_WGS84_RADIUS } from '../../lib/geo';
const FORME_DEG2M = FORME_DEG2RAD * FORME_WGS84_RADIUS;

/** La forme réellement portée par un obstacle (`rectangle` par défaut). */
export function formeObstacle(o: ObstacleForme | null | undefined): FormeObstacle {
  const f = o?.forme;
  return f === 'polygone' || f === 'cercle' ? f : 'rectangle';
}

/** CALX103 — le contour d'un polygone est-il exploitable ? `null` = oui ; sinon le MOTIF
 *  français du refus, qui NOMME la raison (trop peu de sommets, ou tracé qui se croise). */
export function motifContourObstacle(contour: readonly LngLat[] | null | undefined): string | null {
  const pts = Array.isArray(contour) ? contour : [];
  const propres = pts.filter(
    (p): p is LngLat => Array.isArray(p) && p.length === 2 && Number.isFinite(p[0]) && Number.isFinite(p[1]),
  );
  if (propres.length < 3) {
    return 'Obstacle polygonal refusé : il faut au moins trois points — deux points ne délimitent aucune surface.';
  }
  if (!isSimplePolygon(propres as LngLat[])) {
    return 'Obstacle polygonal refusé : le tracé se croise (nœud papillon). Reprenez le contour sans croisement.';
  }
  return null;
}

/** CALX104 — le rayon d'un cercle est-il SAISI ? `null` = oui ; sinon le motif, qui NOMME
 *  le champ manquant. Aucun rayon n'est jamais déduit d'une longueur ni d'une largeur. */
export function motifRayonObstacle(rayonM: number | null | undefined): string | null {
  if (rayonM == null || !Number.isFinite(rayonM) || rayonM <= 0) {
    return 'Obstacle circulaire refusé : saisissez son rayon en mètres — aucun rayon n’est déduit du rectangle.';
  }
  return null;
}

/** Verdict de création d'un obstacle — un refus NOMME toujours sa raison. */
export type VerdictObstacle = { ok: true; obstacle: ObstacleEtendu } | { ok: false; motif: string };

/** Centre (moyenne des sommets) d'un anneau — même convention que `exclusionZoneRing`. */
function centreAnneau(anneau: readonly LngLat[]): LngLat {
  let sLng = 0;
  let sLat = 0;
  for (const [lng, lat] of anneau) {
    sLng += lng;
    sLat += lat;
  }
  return [sLng / anneau.length, sLat / anneau.length];
}

/**
 * CALX103 — obstacle POLYGONAL depuis le contour tracé. Le centre est celui du contour ;
 * `lengthM`/`widthM` reçoivent sa BOÎTE ENGLOBANTE (le repli explicite décrit plus haut,
 * borné comme tout rectangle d'obstacle). `base` recopie le type / la hauteur / la
 * provenance d'un obstacle existant sans rien inventer.
 */
export function obstaclePolygone(
  id: string,
  contour: readonly LngLat[],
  base: Partial<ObstacleEtendu> = {},
): VerdictObstacle {
  const motif = motifContourObstacle(contour);
  if (motif) return { ok: false, motif };
  const anneau = contour.map(([lng, lat]) => [lng, lat] as LngLat);
  const centre = centreAnneau(anneau);
  const dims = ringDimsM(anneau);
  return {
    ok: true,
    obstacle: {
      ...base,
      id,
      centerLng: centre[0],
      centerLat: centre[1],
      lengthM: clampDim(dims.lengthM),
      widthM: clampDim(dims.widthM),
      forme: 'polygone',
      contour: anneau,
    },
  };
}

/**
 * CALX104 — obstacle CIRCULAIRE : centre cliqué + rayon SAISI. `lengthM`/`widthM`
 * reçoivent le côté du carré circonscrit (2 r) — le même repli explicite : un lecteur qui
 * ignore `forme` retrouve un rectangle qui contient le disque, jamais un disque deviné.
 */
export function obstacleCercle(
  id: string,
  centre: LngLat,
  rayonM: number | null | undefined,
  base: Partial<ObstacleEtendu> = {},
): VerdictObstacle {
  const motif = motifRayonObstacle(rayonM);
  if (motif) return { ok: false, motif };
  const r = rayonM as number;
  return {
    ok: true,
    obstacle: {
      ...base,
      id,
      centerLng: centre[0],
      centerLat: centre[1],
      lengthM: clampDim(2 * r),
      widthM: clampDim(2 * r),
      forme: 'cercle',
      rayonM: r,
    },
  };
}

/**
 * L'anneau RÉEL d'un obstacle, celui que le pavage doit éviter : le contour pour un
 * polygone, le disque DESSINÉ (`SEGMENTS_CERCLE_OBSTACLE`) pour un cercle, et le
 * rectangle historique (`obstacleRing`) dans tous les autres cas — y compris un polygone
 * dont le contour manque ou est bancal : on retombe alors sur la boîte, jamais sur rien.
 */
export function anneauObstacle(o: ObstacleEtendu): LngLat[] {
  const forme = formeObstacle(o);
  if (forme === 'polygone' && Array.isArray(o.contour) && !motifContourObstacle(o.contour)) {
    return o.contour.map(([lng, lat]) => [lng, lat] as LngLat);
  }
  if (forme === 'cercle' && !motifRayonObstacle(o.rayonM)) {
    const r = o.rayonM as number;
    const cosLat = Math.max(1e-6, Math.cos(o.centerLat * FORME_DEG2RAD));
    const anneau: LngLat[] = [];
    for (let i = 0; i < SEGMENTS_CERCLE_OBSTACLE; i++) {
      const a = (2 * Math.PI * i) / SEGMENTS_CERCLE_OBSTACLE;
      anneau.push([
        o.centerLng + (r * Math.cos(a)) / (FORME_DEG2M * cosLat),
        o.centerLat + (r * Math.sin(a)) / FORME_DEG2M,
      ]);
    }
    return anneau;
  }
  return obstacleRing(o);
}

/** Les anneaux RÉELS d'une liste d'obstacles — PARALLÈLES à `obstructionClearancesFor`.
 *  Remplace `obstacles.map(obstacleRing)` partout où le pavage reçoit les obstructions. */
export function anneauxObstruction(obstacles: readonly ObstacleEtendu[]): LngLat[][] {
  return obstacles.map((o) => anneauObstacle(o));
}

/** Le dégagement (m) appliqué autour d'un obstacle : le SIEN s'il en porte un (gabarit
 *  société, CALX104), sinon celui de son type (PV61), sinon le dégagement de base. */
export function degagementObstacle(o: (ObstacleForme & { type?: ObstacleType }) | null | undefined): number {
  const propre = o?.degagementM;
  if (typeof propre === 'number' && Number.isFinite(propre) && propre >= 0) return propre;
  return clearanceForType(o?.type);
}

/** L'aire (m²) de la forme RÉELLE d'un obstacle : π r² exact pour un disque (jamais
 *  l'aire du polygone qui le dessine), l'aire géodésique de l'anneau sinon. */
export function aireObstacleM2(o: ObstacleEtendu): number {
  if (formeObstacle(o) === 'cercle' && !motifRayonObstacle(o.rayonM)) {
    const r = o.rayonM as number;
    return Math.PI * r * r;
  }
  return geodesicAreaM2(anneauObstacle(o));
}

/**
 * L'aire (m²) réellement RETIRÉE du posable par un obstacle : sa forme RÉELLE, ÉLARGIE de
 * son dégagement — exactement la bande que le pavage applique (un panneau est refusé s'il
 * entre dans l'obstacle OU s'approche à moins du dégagement de son bord, cf.
 * `estimatorBrainV2` `hitsObstruction`). Jamais la boîte englobante.
 *
 * Pour un disque : π (r + d)². Pour un anneau : A + P·d + π d² — la formule de Steiner,
 * EXACTE pour un contour convexe et MAJORANTE pour un contour rentrant (un coin rentrant
 * voit ses deux bandes se recouvrir). Elle reste, dans les deux cas, STRICTEMENT inférieure
 * à celle de la boîte englobante dès que la forme est plus petite qu'elle — c'est tout
 * l'intérêt de tracer la vraie forme.
 */
export function aireRetireeM2(o: ObstacleEtendu): number {
  const d = degagementObstacle(o);
  if (formeObstacle(o) === 'cercle' && !motifRayonObstacle(o.rayonM)) {
    const r = (o.rayonM as number) + d;
    return Math.PI * r * r;
  }
  const anneau = anneauObstacle(o);
  const aire = geodesicAreaM2(anneau);
  const perimetre = geodesicPerimeterM(anneau); // l'anneau est fermé implicitement
  return aire + perimetre * d + Math.PI * d * d;
}

/**
 * CALX103/CALX104 — les champs de FORME à ÉMETTRE dans le document (et à relire depuis
 * lui) : additifs, jamais émis quand ils sont absents, donc un obstacle rectangulaire
 * sérialise octet pour octet comme aujourd'hui. Prend un `unknown` pour servir les DEUX
 * bouts du round-trip (`serializeLayout` et `deserializeLayout`) avec UNE seule fonction.
 */
export function champsFormeObstacle(o: unknown): ObstacleForme {
  const src = (o ?? {}) as ObstacleForme;
  const forme = src.forme;
  const out: ObstacleForme = {};
  if (forme === 'polygone' && Array.isArray(src.contour) && !motifContourObstacle(src.contour)) {
    out.forme = 'polygone';
    out.contour = src.contour.map(([lng, lat]) => [lng, lat] as LngLat);
  } else if (forme === 'cercle' && !motifRayonObstacle(src.rayonM)) {
    out.forme = 'cercle';
    out.rayonM = src.rayonM as number;
  }
  // CALX104 — le dégagement PROPRE d'un gabarit voyage AVEC sa source : sans elle, le
  // chiffre serait orphelin, et un chiffre qui retire de la surface doit dire d'où il vient.
  if (typeof src.degagementM === 'number' && Number.isFinite(src.degagementM) && src.degagementM >= 0) {
    out.degagementM = src.degagementM;
    const source = typeof src.sourceDegagement === 'string' ? src.sourceDegagement.trim() : '';
    if (source) out.sourceDegagement = source;
  }
  return out;
}

export type TiltMode = 'reco' | number;
// PV62 — 'mixed' = pose MIXTE (portrait/paysage choisi rangée par rangée). Axe de pose
// comme les autres, verrouillable par la puce « Mixte » (toit plat uniquement).
export type OrientMode = 'auto' | 'portrait' | 'landscape' | 'mixed';
// W1 : groupe AZIMUT (plein sud ou aligné sur les arêtes du toit) et groupe MARGE
// de rive (garder la marge de design ou la retirer pour récupérer la rive).
export type AzimuthMode = 'south' | 'aligned';
export type MarginMode = 'keep' | 'remove';

export type RoofType = 'flat' | 'pitched';

/** Données d'une carte « résultat » (recommandation / optimum), partagées entre
 * le rendu de carte et le pré-remplissage du diagnostic. */
export interface CardData {
  title: string;
  isReco: boolean;
  count: number;
  kwc: number;
  annualKwh: number;
  pct: number;
  savingsLow: number;
  savingsHigh: number;
  why: string;
  /** W94 — famille du plan (sélection de la constante bifaciale flat/tilted +
   * libellé de la fourchette). Optionnel (rétro-compatible). */
  family?: ConfigFamily;
  /** W94 — inclinaison du plan (°) : < 12° ou E-O → gain bifacial FLAT, sinon TILTED. */
  tiltDeg?: number;
  /** W94 — besoin annuel (kWh) pour plafonner les économies de la fourchette
   * Année 1 ↔ Année 25 à la facture, à CHAQUE horizon. Optionnel (rétro-compatible). */
  target?: number;
  /** ACAL975 — pose affleurante (toit en pente) : aucun gain bifacial proposé. */
  flush?: boolean;
  /** ACAL1900 — carte d'une pose TENUE (relue ou posée à la main, ERP), jamais celle du gagnant de l'optimiseur. */
  tenue?: boolean;
}

// ═══════════ « PLUSIEURS ZONES » — enregistrements de zone ═══════════
// Plan de RE-RENDU d'une zone : tout ce qu'il faut pour redessiner son bâtiment +
// ses panneaux SANS ré-optimiser. `count` = nombre de panneaux RÉELLEMENT posés.
export interface ZoneRenderPlan {
  pack: PackResult;
  grid: PanelGrid;
  tiltDeg: number;
  family: ConfigFamily;
  flush: boolean;
  count: number;
  obstacles: Obstacle[];
  /** W107 — lift VERTICAL (m) appliqué au pan incliné pour que les pans connectés se
   *  rejoignent sur une faîtière COMMUNE (le plan monte de `ridgeLiftM` sans changer sa
   *  pente). Défaut 0 (pan isolé / toit plat) → rendu inchangé, octet pour octet. */
  ridgeLiftM?: number;
  /** CALX100/CALX101 — le BÂTIMENT du document (`buildings[]`, contrat CALX84) auquel ce
   *  pan appartient, tel que `zones[].buildingId` (CAL59) le désigne. Optionnel : absent
   *  (ou sans hauteur saisie) = la 3D extrude la hauteur de DESSIN annoncée
   *  (`batiment.ts` `HAUTEUR_DESSIN_M`) — le rendu d'aujourd'hui, octet pour octet. */
  batiment?: import('./batiment').Batiment | null;
  /** CALX101 — retrait d'acrotère RÉGLÉ (`setbacksM.parapetM`, CAL76), en mètres : c'est
   *  l'ÉPAISSEUR du bandeau d'acrotère quand une hauteur de relevé est saisie. Optionnel :
   *  absent ou nul = aucun bandeau, la scène d'aujourd'hui. */
  parapetM?: number;
}

/** W69 — pavage gagnant courant (pack + grid + tilt + family + flush) pour
 * re-rendre la 3D avec l'occupation personnalisée (« Personnaliser la disposition »). */
export interface LayoutPlan {
  pack: PackResult;
  grid: PanelGrid;
  tiltDeg: number;
  family: ConfigFamily;
  flush: boolean;
}

export interface AreaRecord {
  id: string;
  label: string;
  vertices: LngLat[];
  obstacles: Obstacle[];
  roofType: RoofType;
  pitchDeg: number;
  /** ACAL252 — PROVENANCE de la pente du pan (`zones[].pitchSource` du document, écrite par l'onglet
   *  Pente) : le mode (degres | pourcentage | cotes) et SES champs. Optionnelle, additive : absente =
   *  jamais renseignée. Réémise telle quelle par `serializeLayout` tant qu'elle décrit encore
   *  `pitchDeg`. */
  pitchSource?: Record<string, unknown>;
  facingAzimuthDeg: number;
  /** W106 — la face de ce pan a-t-elle été fixée À LA MAIN (override par zone) ? Si oui,
   *  l'auto-inférence d'adjacence ne l'écrase jamais. Optionnel (rétro-compatible, défaut false). */
  facingManual?: boolean;
  /** ACAL520 — cadenas du pan (`zones[].verrouille` du document) : verrouillé, ses sommets, son glissé,
   *  sa suppression, ses cotes et sa rotation refusent en le nommant. Absent = modifiable. */
  verrouille?: boolean;
  neededPanels: number;
  neededAuto: boolean;
  result: AreaResult | null;
  renderPlan: ZoneRenderPlan | null;
  /** CAL59 — bâtiment auquel ce pan appartient, pour totaliser un site multi-bâtiments.
   *  Optionnel : absent = bâtiment unique (comportement historique). */
  buildingId?: string;
  /** CAL57 — type d'arête par segment de contour (déduit, corrigible à la main). Optionnel :
   *  absent = aucune arête typée (comportement historique). Recalculé à chaque sérialisation
   *  depuis `vertices`/`roofType`/`facingAzimuthDeg` (voir `edges.ts`) tant qu'aucune n'a été
   *  corrigée à la main. */
  edges?: SerializedEdge[];
  /** CALX109/CALX110 câblage — le MODÈLE de module posé sur CE pan : l'`id` d'une entrée du
   *  catalogue de la société (`InitOptions.modulesDisponibles`, contrat CALX82), tel qu'il
   *  voyage ensuite dans le document sous `zones[].geometry.moduleId`. Optionnel et AJOUTÉ EN
   *  FIN (append-only) : absent = le module par défaut de l'atelier
   *  (`moduleSelect.MODULE_PAR_DEFAUT_ATELIER`), NOMMÉ à l'écran — document et pavage
   *  strictement identiques à ceux d'aujourd'hui, octet pour octet. */
  moduleId?: string;
  /** ACAL28 — la géométrie ENREGISTRÉE de ce pan (`zones[].geometry` du document relu, ou
   *  la pose vivante capturée quand on quitte le pan). Copie profonde. Un pan qui n'est pas
   *  actif est réémis VERBATIM depuis elle (jamais re-pavé ni perdu) ; un pan chargé est
   *  reposé à ses positions par `layoutEditor.hydrateLayout`. Absente = pan jamais posé. */
  geometrieEnregistree?: SerializedZoneGeometry;
  /** ACAL28 — production annuelle (kWh) ENREGISTRÉE attribuée à ce pan tant qu'il n'est pas
   *  recalculé dans la session : part du `result.annualKwh` du document au prorata de son
   *  kWc enregistré (le document ne porte pas de production par pan). Jamais 0 par défaut. */
  annualKwhEnregistre?: number;
  /** ACAL510 — « Pan existant » (modules déjà en place) et son année de mise en service SAISIE (null = non saisie). */
  existant?: boolean;
  anneeMiseEnService?: number | null;
  /** ACAL576 — coupures automatiques du pavage (contrat ACAL586), SAISIES ; absentes = aucune. */
  coupuresPavage?: import('./coupuresPavage').CoupuresPavage;
  /** ACAL579 — portée maximale entre deux pieds de châssis (contrat ACAL587), SAISIE et sourcée. */
  porteeEntrePieds?: import('./piedsChassis').PorteeEntrePieds;
  /** ACAL585 — châssis N × M du pan (contrat ACAL581), SAISI ; absent = pavage d'aujourd'hui. */
  chassis?: import('./chassisPavage').ChassisPan;
}

// ═══════════ W50 — fenêtre « Production estimée » ═══════════
/** Clé d'identité du PLAN de production (GPS/inclinaison/azimut/pose). */
export interface ProdPlaneKey {
  lat: number;
  lon: number;
  tiltDeg: number;
  aspect: number;
  mountingplace: 'building' | 'free';
  /** ACAL982 (revue) — famille de pose du toit plat : `eastwest` = deux jambes (`aspect ∓ 90`). Absente = un plan. */
  family?: ConfigFamily;
}

/** Configuration de production du plan courant (déduite du winner de l'optimiseur). */
export interface ProdConfig {
  lat: number;
  lon: number;
  tiltDeg: number;
  /** Écart au sud de la FACE (Sud, pente) ou du FAÎTE (est-ouest : les jambes sont `aspect − 90` et `aspect + 90`). */
  aspect: number;
  mountingplace: 'building' | 'free';
  /** ACAL982 (revue) — famille de pose du toit plat (`aspect` du gagnant, `estimatorBrainV7.ts::LiveConfigEval`). */
  family?: ConfigFamily;
  panels: number;
  target: number;
}

/** Réponse JSON de /api/roof-production (forme consommée par la fenêtre). */
export interface ProductionApiResponse {
  ok: boolean;
  source: ProductionSource;
  placedKwc?: number;
  annualKwh: number;
  monthlyKwh: number[];
  dailyKwhByMonth: number[];
  typicalDayByMonth: number[][];
  specificDate: SpecificDateProfile | null;
}

/** Options du rendu UNIFIÉ d'une configuration toit plat (carte + 3D + contrôles). */
export interface RenderConfigOpts {
  pack: PackResult;
  grid: PanelGrid;
  family: ConfigFamily;
  tiltDeg: number;
  /** Azimut de face réel du pavage (W1) : production à l'aspect correspondant. */
  azimuthDeg: number;
  isReco: boolean;
  title: string;
  why: string;
  sourceLabel?: string;
  rowId: string | null;
}

// ————————————————————————————————————————————————————————————————————————
// CALX104 — GABARITS D'OBSTACLE DE LA SOCIÉTÉ
//
// La duplication et la trame N×M existaient déjà, mais aucun gabarit NOMMÉ ne se
// réutilisait d'un dossier à l'autre : chaque cheminée se redessinait. Parité PV*SOL
// (bibliothèque d'objets d'ombrage prédéfinis).
//
// D'OÙ VIENNENT LES GABARITS, ET CE QUE LE DÉPÔT N'EN LIVRE PAS : ils sont LUS dans la
// section `zones_types` des réglages société (`GET /api/django/calepinage/parametres/`).
// Le dépôt n'en livre AUCUN : ni cote, ni hauteur, ni dégagement. Tant que la société n'a
// rien saisi, la liste est VIDE et l'écran le dit — jamais une cheminée « standard ».
// ————————————————————————————————————————————————————————————————————————

/** Un gabarit d'obstacle, tel que la société l'a saisi. Tout est OPTIONNEL sauf le nom :
 *  ce sont SES cotes, pas les nôtres. */
export interface GabaritObstacle {
  /** Clé du gabarit dans la section (identifiant stable). */
  cle: string;
  /** Nom affiché dans le sélecteur (`libelle` saisi). */
  libelle: string;
  /** Forme à poser. `rectangle` par défaut quand la société ne la précise pas. */
  forme: FormeObstacle;
  /** Type d'obstacle (porte son dégagement PV61) quand la société l'a saisi. */
  type?: ObstacleType;
  /** Cote NORD-SUD (m) du rectangle, telle que saisie (`longueur_m`). */
  longueurM?: number;
  /** Cote EST-OUEST (m) du rectangle, telle que saisie (`largeur_m`). */
  largeurM?: number;
  /** Rayon (m) du disque (`rayon_m`). */
  rayonM?: number;
  /** Contour RELATIF du polygone, en mètres autour du centre : [[est, nord], …]. */
  sommetsM?: Array<[number, number]>;
  /** Hauteur (m) saisie. Absente = obstacle plan, aucune ombre (CAL66 inchangé). */
  hauteurM?: number;
  /** Dégagement PROPRE (m) du gabarit — il prime sur celui du type. */
  degagementM?: number;
  /** Source textuelle du dégagement propre, saisie par la société. */
  sourceDegagement?: string;
}

/** Un gabarit ÉCARTÉ, avec le champ qui lui manque — l'écran le dit, il ne le devine pas. */
export interface GabaritRefuse {
  cle: string;
  libelle: string;
  motif: string;
}

function nombreReglage(v: unknown): number | undefined {
  return typeof v === 'number' && Number.isFinite(v) && v > 0 ? v : undefined;
}

function texteReglage(v: unknown): string | undefined {
  const s = typeof v === 'string' ? v.trim() : '';
  return s || undefined;
}

/** ACAL1433 — la cote qui manque, en français et sans nom de clé : « la longueur n’est », « la largeur n’est », « la longueur et la largeur ne sont ». */
function cotesManquantes(longueurM?: number, largeurM?: number): string {
  if (longueurM == null && largeurM == null) return 'la longueur et la largeur ne sont';
  return `${longueurM == null ? 'la longueur' : 'la largeur'} n’est`;
}

/** ACAL291/ACAL1433 — la même règle pour les deux lectures : une entrée de genre bande/polygone sans forme, type, cote ni rayon est une ZONE. */
function estGabaritZone(e: Record<string, unknown>): boolean {
  const genre = texteReglage(e.genre);
  return (genre === 'bande' || genre === 'polygone') && !(texteReglage(e.forme) || texteReglage(e.type) || e.longueur_m != null || e.rayon_m != null);
}

/**
 * CALX104 — lit la section `zones_types` et en tire les gabarits POSABLES. Un gabarit sans
 * cote exploitable n'est PAS proposé : il rejoint `refuses` avec le champ qui lui manque,
 * NOMMÉ. Section absente / vide / bancale ⇒ `{gabarits: [], refuses: []}` — l'état vide.
 *
 * Les clés lues sont celles des réglages (`snake_case`) : `libelle`, `type`, `forme`,
 * `longueur_m`, `largeur_m`, `rayon_m`, `sommets`, `hauteur_m`, `retrait_m`, `source`.
 */
export function lireGabaritsObstacle(section: unknown): {
  gabarits: GabaritObstacle[];
  refuses: GabaritRefuse[];
} {
  const gabarits: GabaritObstacle[] = [];
  const refuses: GabaritRefuse[] = [];
  if (!section || typeof section !== 'object' || Array.isArray(section)) return { gabarits, refuses };
  for (const [cle, brut] of Object.entries(section as Record<string, unknown>)) {
    if (!brut || typeof brut !== 'object' || Array.isArray(brut)) continue;
    const e = brut as Record<string, unknown>;
    if (estGabaritZone(e)) continue; // ACAL1433 — une bande ou un polygone de zone n'est pas un obstacle
    const libelle = texteReglage(e.libelle) ?? cle;
    const typeSaisi = texteReglage(e.type);
    const type = OBSTACLE_TYPES.some((t) => t.id === typeSaisi) ? (typeSaisi as ObstacleType) : undefined;
    const longueurM = nombreReglage(e.longueur_m);
    const largeurM = nombreReglage(e.largeur_m);
    const rayonM = nombreReglage(e.rayon_m);
    const hauteurM = nombreReglage(e.hauteur_m);
    const sommetsM = Array.isArray(e.sommets)
      ? (e.sommets as unknown[])
          .filter(
            (p): p is [number, number] =>
              Array.isArray(p) && p.length === 2 && Number.isFinite(p[0]) && Number.isFinite(p[1]),
          )
          .map((p) => [p[0], p[1]] as [number, number])
      : [];
    const formeSaisie = texteReglage(e.forme);
    const forme: FormeObstacle =
      formeSaisie === 'cercle' || formeSaisie === 'polygone' || formeSaisie === 'rectangle'
        ? formeSaisie
        : rayonM != null
          ? 'cercle'
          : sommetsM.length >= 3
            ? 'polygone'
            : 'rectangle';
    const source = texteReglage(e.source);
    const commun = {
      cle,
      libelle,
      forme,
      ...(type ? { type } : {}),
      ...(hauteurM != null ? { hauteurM } : {}),
      ...(typeof e.retrait_m === 'number' && Number.isFinite(e.retrait_m) && e.retrait_m >= 0
        ? { degagementM: e.retrait_m }
        : {}),
      ...(source ? { sourceDegagement: source } : {}),
    };
    if (forme === 'cercle') {
      if (rayonM == null) {
        refuses.push({
          cle,
          libelle,
          motif: `« ${libelle} » n’est pas proposé : son rayon n’est pas saisi.`,
        });
        continue;
      }
      gabarits.push({ ...commun, rayonM });
      continue;
    }
    if (forme === 'polygone') {
      if (sommetsM.length < 3) {
        refuses.push({
          cle,
          libelle,
          motif: `« ${libelle} » n’est pas proposé : son contour compte moins de trois points.`,
        });
        continue;
      }
      gabarits.push({ ...commun, sommetsM });
      continue;
    }
    if (longueurM == null || largeurM == null) {
      refuses.push({
        cle,
        libelle,
        motif: `« ${libelle} » n’est pas proposé : ${cotesManquantes(longueurM, largeurM)} pas saisie${longueurM == null && largeurM == null ? 's' : ''}.`,
      });
      continue;
    }
    gabarits.push({ ...commun, longueurM, largeurM });
  }
  return { gabarits, refuses };
}

/**
 * ACAL291 — un gabarit de ZONE réglementaire de la société (section `zones_types`, genre
 * `bande` | `polygone`) : une zone qui retire de la surface au nom d'une SOURCE écrite. La
 * géométrie reste celle que l'utilisateur trace ; le gabarit apporte libellé, nature, retrait,
 * hauteur et source.
 */
export interface GabaritZone {
  cle: string;
  libelle: string;
  nature: 'INTERDITE' | 'RESERVEE' | 'PREFEREE';
  /** Retrait (m) du gabarit (`retrait_m`), 0 quand la société n'en a pas saisi. */
  retraitM: number;
  hauteurM?: number;
  /** Source textuelle OBLIGATOIRE — elle voyage avec la zone posée. */
  source: string;
  /** ACAL1432 — genre saisi, et pour une bande sa largeur (`largeur_m`) et son côté (`cote`), tels que saisis (jamais complétés). */
  genre: 'bande' | 'polygone';
  largeurM?: number;
  cote?: string;
}

/**
 * ACAL291 — lit les gabarits de ZONE de la section `zones_types`. Un gabarit d'obstacle (forme,
 * type d'obstacle, cotes ou rayon saisis, ou sans `genre`) est IGNORÉ — il relève de
 * `lireGabaritsObstacle`. Un gabarit de zone sans source, ou d'une nature qui ne se trace pas
 * (ENVELOPPE est le contour du toit), n'est pas proposé : il rejoint `refuses` avec son motif.
 */
export function lireGabaritsZone(section: unknown): { gabarits: GabaritZone[]; refuses: GabaritRefuse[] } {
  const gabarits: GabaritZone[] = [];
  const refuses: GabaritRefuse[] = [];
  if (!section || typeof section !== 'object' || Array.isArray(section)) return { gabarits, refuses };
  for (const [cle, brut] of Object.entries(section as Record<string, unknown>)) {
    if (!brut || typeof brut !== 'object' || Array.isArray(brut)) continue;
    const e = brut as Record<string, unknown>;
    if (!estGabaritZone(e)) continue;
    const libelle = texteReglage(e.libelle) ?? cle;
    const source = texteReglage(e.source);
    if (!source) {
      refuses.push({ cle, libelle, motif: `« ${libelle} » n’est pas proposé : sa source (source) n’est pas saisie.` });
      continue;
    }
    const nature = texteReglage(e.nature);
    if (nature !== 'INTERDITE' && nature !== 'RESERVEE' && nature !== 'PREFEREE') {
      refuses.push({ cle, libelle, motif: `« ${libelle} » n’est pas proposé : sa nature (${nature ?? 'non saisie'}) ne se trace pas comme une zone.` });
      continue;
    }
    const hauteurM = nombreReglage(e.hauteur_m);
    const largeurM = nombreReglage(e.largeur_m);
    const cote = texteReglage(e.cote);
    gabarits.push({
      cle,
      libelle,
      nature,
      genre: texteReglage(e.genre) as 'bande' | 'polygone',
      ...(largeurM != null ? { largeurM } : {}),
      ...(cote ? { cote } : {}),
      retraitM: typeof e.retrait_m === 'number' && Number.isFinite(e.retrait_m) && e.retrait_m > 0 ? e.retrait_m : 0,
      ...(hauteurM != null ? { hauteurM } : {}),
      source,
    });
  }
  return { gabarits, refuses };
}

/**
 * CALX104 — pose un gabarit à un centre donné. Toutes les cotes viennent du gabarit :
 * AUCUNE n'est complétée ici. Un gabarit polygonal porte un contour RELATIF (mètres
 * est/nord autour du centre) qu'on replace autour du point posé, sans le déformer.
 */
export function obstacleDepuisGabarit(
  id: string,
  gabarit: GabaritObstacle,
  centre: LngLat,
): VerdictObstacle {
  const base: Partial<ObstacleEtendu> = {
    ...(gabarit.type ? { type: gabarit.type } : {}),
    ...(gabarit.hauteurM != null ? { heightM: gabarit.hauteurM } : {}),
    ...(gabarit.degagementM != null ? { degagementM: gabarit.degagementM } : {}),
    ...(gabarit.sourceDegagement ? { sourceDegagement: gabarit.sourceDegagement } : {}),
  };
  if (gabarit.forme === 'cercle') return obstacleCercle(id, centre, gabarit.rayonM, base);
  if (gabarit.forme === 'polygone') {
    const sommets = gabarit.sommetsM ?? [];
    const cosLat = Math.max(1e-6, Math.cos(centre[1] * FORME_DEG2RAD));
    const contour = sommets.map(
      ([est, nord]) => [centre[0] + est / (FORME_DEG2M * cosLat), centre[1] + nord / FORME_DEG2M] as LngLat,
    );
    return obstaclePolygone(id, contour, base);
  }
  if (gabarit.longueurM == null || gabarit.largeurM == null) {
    return {
      ok: false,
      motif: `« ${gabarit.libelle} » n’est pas posable : ${cotesManquantes(gabarit.longueurM, gabarit.largeurM)} pas saisie${gabarit.longueurM == null && gabarit.largeurM == null ? 's' : ''}.`,
    };
  }
  return {
    ok: true,
    obstacle: {
      ...base,
      id,
      centerLng: centre[0],
      centerLat: centre[1],
      lengthM: clampDim(gabarit.longueurM),
      widthM: clampDim(gabarit.largeurM),
      forme: 'rectangle',
    },
  };
}
