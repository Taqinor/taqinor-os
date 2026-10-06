import {
  Fragment, useCallback, useDeferredValue, useEffect, useMemo, useReducer,
  useRef, useState,
} from 'react'
import { useDispatch } from 'react-redux'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import {
  // QJR101 — `Sprout` est parti avec le panneau agricole (`PanneauAgricole`),
  // qui l'importe désormais lui-même.
  ArrowLeft, Target, ClipboardList, User, Zap, BarChart3,
  // QJR100 — `ShoppingCart` et `Trash2` sont partis avec la table de lignes
  // (`generator/LigneTable.jsx`), qui les importe désormais elle-même.
  StickyNote, FileText, RotateCcw, Sun, Plus,
  // EZ3 — actions du panneau de succès (envoyer / aperçu).
  Send, Eye,
  // FOUNDER 26/08 — bouton « Recalculer le dimensionnement ».
  RefreshCw,
} from 'lucide-react'
// QX21 — la sauvegarde passe désormais par les endpoints ATOMIQUES de ventesApi
// (createDevisAtomic / replaceLignesDevis) ; createDevis/addLigneDevis (1+N
// round-trips non gardés) ne sont plus utilisés ici.
import {
  createAutoQuote, LEAD_TYPE_TO_MODE,
  // QJR575 — les paramètres du balayage C&I, construits UNE fois (partagés
  // avec le « Devis automatique »).
  parametresBalayageCI,
  // QJR665 — conso de l'étude C&I = celle du balayage (barème national).
  consoMensuelleEtudeCI,
  // QJR308 — même formule que DevisTab.jsx / LeadDevisPanel.jsx : l'avis du
  // palier de 5 kWc, mais affiché ICI au moment RÉEL où `runAutoQuote` déclenche
  // le snap (les deux autres points ne l'affichent qu'avant de naviguer vers
  // ce générateur).
} from '../../features/ventes/autoQuote'
// AGR127/AGR128 — aperçu SERVEUR du pompage (aucun calcul local).
import {
  useEtudePompagePreview, construireCorpsPompage, manquantsPompage,
  useEconomiePompagePreview,
} from '../../features/ventes/etudePompagePreview'
import { saisiesEconomiePompage, lignesDepuisKit } from '../../features/ventes/quote/etudeMarcheBloc'
import {
  POMPAGE_SAISIE_VIDE, etatPompageEcran, poserSaisie,
} from '../../features/ventes/etudePompagePreviewPur'
import {
  ECO_POMPAGE_VIDE, ecoDepuisSaisies, ATTESTATION_VIDE,
} from '../../features/ventes/quote/etudeMarcheBloc'
import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import parametresApi from '../../api/parametresApi'
import { fetchAllPages } from '../../utils/fetchAllPages'
import ClientQuickCreateModal from './ClientQuickCreateModal'
import DevisPresetPanel from './DevisPresetPanel'
// QJR100 — `DevisLineRow` n'est plus importé ici : c'est `LigneTable` qui
// l'enrobe désormais (un seul endroit monte une ligne de devis).
// TAILLES (fondateur 26/08/2026) — écran vendeur Éco/Recommandé/Max, composant
// autonome (se masque lui-même hors résidentiel/devis non enregistré) pour ne
// pas alourdir ce fichier déjà volumineux.
import DevisOffresTailles from './DevisOffresTailles'
import { Combobox } from '../../ui/Combobox'
// APX17 — confirmation maison + toasts (jamais une popup du système).
import { useConfirmDialog, toast } from '../../ui/confirm'
// APX11 — en-tête unique VX28 + accent de module (identité Ventes).
import { PageHeader } from '../../ui/PageHeader'
import { VENTES_ACCENT_STYLE } from '../../features/ventes/accent'
import { searchCompanies } from '../../features/crm/companyLookup'
import {
  // QJR100 — `IconButton` est parti avec la table de lignes (suppression d'une
  // villa), seul endroit de cet écran qui l'utilisait.
  Button, Card, CardContent,
  // APX12 — le langage UNIQUE des KPI d'argent (le total du rail).
  Stat,
  Input, Textarea, Label, Segmented, Switch,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  // QJR101 — `HelpTip` est parti avec la carte des factures : les trois
  // panneaux réseau l'importent chacun pour leur aide « distributeur ».
  ScrollProgress,
  // QJR540 — compteurs factures / BC / chantier du devis rouvert (ex-DevisForm).
  RelationCounters,
} from '../../ui'
// QJR540 — blocs issus de l'ancien modal DevisForm (supprimé) : le calepinage qui
// pilote ce devis (CAL40), son badge « périmé » (CAL188) et les pièces jointes
// du devis (seule UI de pièces jointes devis).
import BlocCalepinageDevis from '../../features/ventes/BlocCalepinageDevis'
import BadgePerime from '../../features/calepinage/BadgePerime'
import AttachmentsPanel from '../../components/AttachmentsPanel'
// QJR553 (D-QJR5-7) — historique des versions + « Revenir à cette version ».
import HistoriqueConfiguration from '../../features/ventes/HistoriqueConfiguration'
import LotsMultiSites from '../../features/ventes/LotsMultiSites'
import AjouterBoqElectrique from '../../features/ventes/AjouterBoqElectrique'
// QJR589 — bannière de dérive lead → devis à deux gestes (partagée cockpit).
import BandeauDeriveLead from '../../features/ventes/quote/BandeauDeriveLead'
// STKCAT10 — le sélecteur de structures PILOTÉ PAR LE CATALOGUE (décision
// fondateur 16/09/2026) qui remplace le bouton acier/aluminium ; il rend
// lui-même ce bouton en REPLI quand la société n'a aucune catégorie typée
// « structure ». Partagé tel quel avec la fiche lead (SectionSite).
import StructureSelector from '../../features/stock/StructureSelector'
import { structuresEligibles } from '../../features/stock/structures'
import { useCanCreateProduit, useIsAdmin } from '../../hooks/useHasPermission'
import useKeyboardAwareScroll from '../../hooks/useKeyboardAwareScroll'
import { useDirtyGuard } from '../../ui/useDirtyGuard'
import { useDraftAutosave } from '../../ui/useDraftAutosave'
import { usePasteClean, parsePastedAmount } from '../../hooks/usePasteClean'
import {
  // QJR101 — `MONTHS_FR` (grille des 12 mois), `TARIF_MT_ONEE` (barème MT) et
  // `COMMERCIAL_CATEGORIES` sont partis avec les panneaux de marché qui les
  // rendent ; `tarifMtDisponible` et `commercialDayShare` restent ici, appelés
  // par l'avertissement de vente et par l'étude commerciale.
  CHART_MONTHS, DEFAULT_MONTHLY_BILLS, DAY_USAGE_DEFAULTS,
  formatMoney, estimerMois, computeROI, ttcFromHt,
  tauxTvaOf, tauxTvaOuDefaut, controlerFacturesSaisies,
  paybackMoteurHoraire, inverterCostFromLines, appartientAuPanierSans,
  appartientAuPanierAvec,
  batteryKwhFromLines, batteryCapaciteInconnue, comptePanneauxOption,
  kwcFactureDesLignes, kwcPourPanneaux,
  // QJR570 (D-QJR5-4) — recomposer FUSIONNE (jamais un remplacement intégral).
  appliquerRecomposition, lignesManuellesEnConflitPossible,
  optionTotalsTTC, autoFillLines, defaultProductLines,
  computeEtudeIndustrielle,
  HEURES_POMPAGE_DEFAUT,
  isBattery, isHybridInverter, isReseauInverter, isOffgridInverter, isPanel, isPompe,
  prixParKwc, discountForTarget,
  computeBuyCost, avecBatterieAvailability, KWH_PRICE, EFFICIENCY,
  panneauxPourKwc,
  TVA_STANDARD_DEFAUT, TVA_PANNEAUX_DEFAUT,
  // QJR66 — `buildEtudeParamsChoice` n'est PLUS importé ici : l'écran n'écrit
  // plus `scenario` / `recommended_option` / `distributeur` / `conso_annuelle`
  // dans `etude_params` (registre de surcharges D12 côté serveur). La fonction
  // reste dans solar.js, avec ses tests — elle n'a simplement plus d'appelant
  // sur ce chemin d'enregistrement.
  kwhFromBill, multiPropertyPreviewTTC,
  productibleForCity,
  COMMERCIAL_CATEGORY_QUESTIONS, commercialDayShare,
  tarifMtDisponible, tarifMtMoyen,
  // Règle fondateur du 18/08 — dimensionnement par PALIERS de 5 kWc, retenus
  // au payback le plus court (jamais un panneau/900 MAD nu).
  estimerKwcDepuisFacture, optimalKwcByPayback,
  // FINDING 25/08 — consommation réelle dérivée des factures par le barème :
  // sans elle le modèle d'économie ne sature pas et l'ascension marginale
  // sur-vend jusqu'au plafond du balayage.
  consoAnnuelleDepuisFactures,
  // PVMRQ — libellé FR d'un rôle ROLES_AUTO_COMPOSITION, pour le bandeau
  // « marque épinglée introuvable ».
  roleLabel,
  // L-2OPT (fondateur 24/08) — deux optimiseurs indépendants (sans/avec
  // batterie) fusionnés en lignes taguées `variante`.
  fusionnerVariantes,
  // PVORD (fondateur 19/08/2026) — ordre par défaut des lignes de devis :
  // dérive la séquence de rôles depuis l'écran (bouton « Enregistrer cet
  // ordre »), appliquée par autoFillLines via ordreLignes.
  deriveRoleOrderFromLines,
  // QJR546 — garde « produit tarifé » des lignes d'un modèle appliqué.
  _hasPrix,
  // ERR-QAC-KWH-SAISI-INCOHERENT-FACTURES — kWh déclaré vs factures du lead.
  controlerKwhDeclare, MESSAGE_KWH_INCOHERENT,
} from '../../features/ventes/solar'
import { formatNumber, formatMAD, formatDateTime, formatDate } from '../../lib/format'
import { peutEditerDevis } from '../../features/ventes/devisStatuts'
// CJ2b — aperçu du moteur horaire résidentiel (PVGIS réel × consommation
// réelle du client, mois par mois) : source UNIQUE des chiffres d'économie à
// l'écran, à la place du miroir local `computeROI` dès que le serveur a
// répondu (voir `roi` ci-dessous, conservé comme repli hors-ligne).
import {
  construireCorpsPreview, etiquetteSource, lignesAffichables,
  useEtudeHorairePreview, verdictBatteriePourTaille,
  falaiseAffichable, glitchAnnuel, balayageStockageAffichable,
  estimationConsoAffichable, LIBELLES_MOIS,
} from '../../features/ventes/etudeHorairePreview'
// QJR99 — LA BASCULE : l'écran adopte la machine à états du dimensionnement
// (QJR87) et les hooks QJR90. Les six `useRef` « touché », l'effet de sizing
// écrit à la main, les écritures gardées d'applyLead/applySiteProfile,
// `onModeChange`, la chaîne de ternaires `deuxValeursDim` et le repli de
// composition silencieux ont été SUPPRIMÉS dans le même commit — aucun double
// chemin.
import {
  sizingReducer, ETAT_INITIAL,
  SCENARIO_LES_DEUX, SCENARIO_SANS, SCENARIO_AVEC,
  toucheNbPanneauxPourComposition,
} from '../../features/ventes/quote/sizingReducer'
import { useSizingMoteur } from '../../features/ventes/quote/hooks/useSizingMoteur'
// QJR215 — la liste blanche du registre d'overrides (contrat QJR1), DÉRIVÉE
// du même module que le client API (QJR214) : jamais une liste recopiée ici.
import {
  CHEMINS_AUTORISES, cheminNonLu, ecartsAuRegistre, valeursImposees,
} from '../../features/ventes/quote/overrides'
import { deuxValeursDim as selecteurDeuxValeursDim }
  from '../../features/ventes/quote/paireDimensionnement'
// QJR426 (DR5) — les 13 cartes de métrique du générateur (bloc Aperçu de la
// Simulation + étude industrielle/commercial) portent désormais la VALEUR
// SIGNÉE (`moteur`/`apercu`) au lieu d'un `value=` littéral : `CarteMetrique`
// reste le seul déballeur (`unwrap`), cet écran ne fait que signer.
import { moteur, apercu } from '../../features/ventes/quote/valeur'
// QJR523 — UN seul couple de mappeurs lignes serveur ⇄ écran.
import {
  lignesServeurVersEcran, erreursBaseLegaleServeur,
} from '../../features/ventes/quote/lignesEcran'
// QJR658 — devis ⇄ état d'écran : un module pur.
import { devisVersEtat, etatVersEcritures } from '../../features/ventes/quote/etatDevis'
// QJR100 — les trois morceaux extraits de cet écran. `CarteMetrique` est LE
// seul déballeur d'une valeur signée ; `LigneTable` possède la table de lignes
// (ajout/suppression/réordonnancement) ; `RailArgent` possède la chaîne
// d'argent (totaux, remise, TVA, prix cible, marge interne).
import CarteMetrique, { GenCardHeader } from './generator/CarteMetrique'
// QJR624 — l'échéancier éditable de l'Édition complète (D-QJR5-10).
import CarteEcheancier from './generator/CarteEcheancier'
import LigneTable from './generator/LigneTable'
import RailArgent from './generator/RailArgent'
// QJR101 — les quatre panneaux de marché. Chacun ne monte que les champs de
// SON marché et lit la clé de son module de stratégie (QJR89) pour se retirer
// ailleurs. Cet écran garde l'en-tête, le sélecteur de marché, le lead/client,
// la table de lignes, le rail d'argent, l'enregistrement — et TOUTE la logique
// transverse (chaîne d'étude horaire, roi, études par marché, validate).
import PanneauResidentiel from './generator/PanneauResidentiel'
import PanneauIndustriel from './generator/PanneauIndustriel'
import PanneauCommercial, { CATEGORIE_NON_PRECISEE } from './generator/PanneauCommercial'
import PanneauAgricole from './generator/PanneauAgricole'
// QJRREM (fondateur 07/09/2026) — miroir EXACT du noyau de répartition de la
// remise globale par ligne (même module que DevisForm.jsx, l'écran d'édition
// HT déjà livré) ; jamais un calcul local ici. `puRemise` (P.U. après remise)
// est utilisé par `DevisLineRow`, pas ici.
import { repartirRemiseParLigne } from '../../features/ventes/remise'

// QX43 — 4 marchés réels : industriel et commercial sont désormais distincts.
const MODE_OPTIONS = [
  { value: 'residentiel', label: '🏠 Résidentiel' },
  { value: 'industriel', label: '🏭 Industriel' },
  { value: 'commercial', label: '🏪 Commercial' },
  { value: 'agricole', label: '🌾 Agricole (pompage)' },
]

// CJ2b — libellés FR des 3 saisons de l'étude horaire (etude.saisons, clés
// serveur inchangeables).
const SAISON_LABELS = { hiver: 'Hiver', mi_saison: 'Mi-saison', ete: 'Été' }

// QJR586 (contrat QJR506) — la « ville de calcul » du lead SERVIE par le
// serveur (`ville_effective` : rattachement VREF prioritaire), la même que le
// moteur, le PDF et le transport. Repli sur `ville` pour un lead servi sans
// la clé (ancienne réponse) ; '' jamais null.
const villeEffectiveLead = (lead) => (lead?.ville_effective ?? lead?.ville) || ''

// ORDRE FONDATEUR (24/08) — « tous les devis sont générés par défaut avec DEUX
// OPTIONS (sans + avec batterie), sauf si le commercial le précise sur le devis
// modifiable ». Le vocabulaire est le contrat EXACT du moteur PDF (constantes
// SCENARIO_* d'apps/ventes/services.py) : jamais reformulé ici.
// QJR99 — les quatre constantes ET la table QX19 `BATTERIE_LEAD_VERS_SCENARIO`
// ne sont plus RE-DÉCLARÉES ici : elles viennent du reducer (source unique,
// `features/ventes/quote/sizingReducer.js`), qui les possède depuis QJR87.

// QJR641 — le Marché est la SEULE source : le sélecteur « Type d'installation »
// (qui doublonnait le marché sans jamais le changer) est supprimé ; le défaut
// de la part diurne se DÉRIVE du marché (libellés du simulateur →
// `DAY_USAGE_DEFAULTS`). La valeur persistée `part_diurne_pct` (QJR528) prime
// à la réouverture.
const INST_TYPE_PAR_MODE = {
  residentiel: 'Résidentielle',
  industriel: 'Industrielle',
  commercial: 'Commerciale',
  agricole: 'Agricole',
}
const partDiurneParDefaut = (mode) =>
  DAY_USAGE_DEFAULTS[INST_TYPE_PAR_MODE[mode] ?? 'Résidentielle'] ?? 50

// DC11 / QJR106 / QJR589 — la bannière « valeurs du lead modifiées » (libellés
// et gestes) vit dans `features/ventes/quote/BandeauDeriveLead.jsx`, partagée
// avec la fenêtre devis du cockpit.

// QJR108 — `RIEN_A_CHIFFRER` / `valeurMoteurDim` / `paireDimensionnement`
// vivaient ICI, non exportés (ce fichier n'exporte que des composants —
// react-refresh), donc vérifiables SEULEMENT par expression régulière sur le
// source. Ils vivent désormais dans le module PUR
// `features/ventes/quote/paireDimensionnement.js`, où ils sont testés par
// EXÉCUTION. Déplacement seul : pas une ligne de logique n'a changé.

let _keyCounter = 0
const newKey = () => ++_keyCounter

// L-2OPT (fondateur 24/08) — déduplique une liste par clé, garde la PREMIÈRE
// occurrence : même patron que `marquesManquantes`/`onduleursIncomplets`
// (solar.js), utilisé quand les DEUX compositions (sans/avec) de
// `handleAutoFill` signalent le même trou catalogue.
const dedupeParCle = (items, keyFn) => {
  const seen = new Set()
  const out = []
  for (const it of items) {
    const k = keyFn(it)
    if (seen.has(k)) continue
    seen.add(k)
    out.push(it)
  }
  return out
}

// VX93 — défaut intelligent : dernier taux TVA saisi sur une ligne ajoutée à la
// main (localStorage). Repli sur le taux standard (20 %) si absent. Toujours
// modifiable ligne par ligne ; jamais bloquant.
const LAST_TVA_KEY = 'taqinor.devisGenerator.lastTva'
const lireLastTva = () => {
  try { return window.localStorage.getItem(LAST_TVA_KEY) || String(TVA_STANDARD_DEFAUT) }
  catch { return String(TVA_STANDARD_DEFAUT) }
}
const ecrireLastTva = (v) => {
  try { if (v !== '' && v != null) window.localStorage.setItem(LAST_TVA_KEY, String(v)) }
  catch { /* no-op silencieux */ }
}

const withKeys = (rows) => rows.map(r => ({
  _key: newKey(),
  produit: String(r.produit ?? ''),
  designation: r.designation,
  quantite: String(r.quantite),
  prix_unit_ttc: String(r.prix_unit_ttc),
  taux_tva: String(r.taux_tva ?? 20),
  // QJ31 — groupe multi-villa (mode B) : null = ligne mono-système (défaut,
  // comportement historique inchangé). 0 = équipement commun, 1..N = villa N.
  groupeIndex: r.groupeIndex ?? null,
  groupeLabel: r.groupeLabel ?? '',
  // XSAL5 — ligne optionnelle (add-on hors total). Défaut False = ligne normale.
  optionnelle: !!r.optionnelle,
  // XSAL14 — type de ligne : 'produit' (défaut) / 'section' / 'note'.
  typeLigne: r.typeLigne ?? 'produit',
  // N2 — verrou « prix tapé à la main » : préservé au rechargement d'un
  // brouillon (VX62 draft restore), sinon False (chargement serveur/auto-fill —
  // rien n'a encore été tapé sur CES lignes-là).
  prixManuel: !!r.prixManuel,
  // QJR218 — même patron que `prixManuel` juste au-dessus : le verrou
  // « quantité tapée à la main » (posé aujourd'hui côté serveur, ex. une
  // resynchronisation, `domain/lignes`) doit lui aussi survivre au
  // rechargement d'un brouillon/devis, jamais retomber à False en silence.
  quantiteManuelle: !!r.quantiteManuelle,
  // L-2OPT (fondateur 24/08) — '' commun (défaut, comportement historique
  // inchangé) | 'sans' | 'avec' : posée par `fusionnerVariantes` quand les
  // deux optimiseurs résidentiels divergent, préservée au rechargement d'un
  // brouillon/devis (VX62, réouverture ?edit=).
  variante: r.variante ?? '',
  // QJR523 — rôle STOCKÉ de la ligne (`role_devis`) : conservé comme
  // `prixManuel`, sinon `remplacer_lignes` re-devine le rôle et écrase celui
  // posé par la composition (ex. 'onduleur_offgrid').
  role_devis: r.role_devis ?? '',
  lot: r.lot ?? null, // QJR667 — lot multi-sites conservé à l'enregistrement
  // QJR529 — remise PAR LIGNE stockée (%), conservée comme `prixManuel` :
  // jamais remise à '0' en silence (le total client monterait).
  remise: String(r.remise ?? '0'),
  // QJR570 — marqueur d'ÉCRAN « ligne issue d'une composition » (jamais
  // envoyé au serveur) : une recomposition retire une ligne composée hier et
  // absente aujourd'hui, mais garde une ligne ajoutée à la main.
  compose: !!r.compose,
}))

// QJR581 — durée pendant laquelle les états posés par le mappeur `?edit=` (et
// ses relectures immédiates : lead, réouverture) forment la RÉFÉRENCE « rien
// n'a changé » de l'Édition complète.
const FENETRE_REFERENCE_MS = 1500

// Nouvelle ligne vide — quantité 0 comme addProductLine() du simulateur
const emptyLine = () => ({
  _key: newKey(),
  produit: '',
  designation: '',
  quantite: '0',
  prix_unit_ttc: '0',
  taux_tva: lireLastTva(),  // VX93 — dernière TVA saisie (défaut 20 %)
  // VX249(b) — 1 des 4 champs VX93 exactement (avec owner/ville sur
  // LeadForm.jsx et payMode sur FactureList.jsx) : reste « suggéré » (style
  // discret dans DevisLineRow.jsx) tant que l'utilisateur n'a pas changé
  // LUI-MÊME le taux de CETTE ligne — retiré via `setLine` ci-dessous.
  _tvaSuggested: true,
  groupeIndex: null,
  groupeLabel: '',
  // XSAL5 — ligne optionnelle (add-on hors total). Défaut False.
  optionnelle: false,
  // XSAL14 — type de ligne : 'produit' (défaut) / 'section' / 'note'.
  typeLigne: 'produit',
  // N2 — aucun prix tapé à la main pour l'instant.
  prixManuel: false,
  // QJR218 — aucune quantité tapée à la main pour l'instant (ligne neuve).
  quantiteManuelle: false,
  // L-2OPT — ligne ajoutée à la main : commune par défaut.
  variante: '',
})

// XSAL14 — ligne de SECTION (intertitre) ou de NOTE (texte sans prix). Ne porte
// ni produit ni prix ni quantité : exclue de tous les totaux, rendue comme
// intertitre/note à l'écran et sur le PDF premium.
const structureLine = (typeLigne) => ({
  _key: newKey(),
  produit: '',
  designation: '',
  quantite: '0',
  prix_unit_ttc: '0',
  taux_tva: '20',
  _tvaSuggested: false,
  groupeIndex: null,
  groupeLabel: '',
  optionnelle: false,
  typeLigne,
  prixManuel: false,
  variante: '',
})

const fmtNum = (v) => (v !== null && v !== undefined) ? formatNumber(v) : 'N/A'

// QJR100 — `GenCardHeader` et `MetricCard` ne sont plus DÉFINIS ici : ils
// vivent dans `generator/CarteMetrique.jsx`, partagés par les morceaux
// extraits (LigneTable, RailArgent). `MetricCard` s'appelle désormais
// `CarteMetrique` et sait, EN PLUS, déballer une valeur signée (QJR86).

// QJR572 — sous un choix que le registre IMPOSE : le dire, et offrir le
// retour à l'automatique (DELETE ?chemin=, `regenererOverride`).
function IndicationRegistre({ chemin, busy, onRegenerer }) {
  return (
    <p className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground"
       data-testid={`registre-impose-${chemin}`}>
      Imposé par le registre —
      <button type="button" className="underline underline-offset-2 hover:text-foreground disabled:opacity-50"
              disabled={busy} onClick={() => onRegenerer(chemin)}>
        revenir à l&apos;automatique
      </button>
    </p>
  )
}

/**
 * Générateur de devis. Utilisable en PLEINE PAGE (route /ventes/devis/nouveau,
 * lit le contexte depuis l'URL) ou EMBARQUÉ dans la fiche lead (props), auquel
 * cas il ne navigue jamais : il rappelle onDone(devisId) / onCancel à la place.
 *
 * @param {boolean}  embedded    Rendu inline (fiche lead) — pas de navigation
 * @param {number}   leadId      Lead de départ (embarqué)
 * @param {boolean}  auto        Lancer le devis auto au montage (embarqué)
 * @param {string}   discount    Remise initiale (embarqué)
 * @param {number}   editId      Éditer un brouillon existant (embarqué)
 * @param {function} onDone      Appelé avec l'id du devis créé/enregistré
 * @param {function} onCancel    Appelé sur Annuler
 */
export default function DevisGenerator({
  embedded = false,
  leadId: leadIdProp = null,
  auto: autoProp = false,
  discount: discountProp = null,
  editId: editIdProp = null,
  onDone = null,
  onCancel = null,
} = {}) {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  // APX17 — confirmations maison (VX19/L152) : plus une seule popup du système.
  const { confirm } = useConfirmDialog()

  // QP2 — renommer la désignation d'une ligne est réservé à Directeur +
  // Commercial responsable (même gate que la création produit, QG4/QG5) ;
  // pour tout autre rôle la désignation est en lecture seule (verrouillée au
  // nom du produit lié). Le backend reste la seule garde qui compte.
  const canRenameLine = useCanCreateProduit()
  // VX51 — un champ bas de page ne doit plus rester caché sous le clavier iOS.
  useKeyboardAwareScroll()
  // Dialogue « renommer ici seulement » vs « créer un nouveau produit ».
  // { key, ancienNom, nouveauNom, produitId } quand ouvert, sinon null.
  const [renameDialog, setRenameDialog] = useState(null)
  const [renameBusy, setRenameBusy] = useState(false)
  const [renameError, setRenameError] = useState(null)

  const [clients, setClients] = useState([])
  const [leads, setLeads] = useState([])
  // ERR-QAH-VENTES-EDITION-PERD-LEAD — le lead du devis rouvert (`?edit=`),
  // relu par son id : la liste `leads` n'est que la PREMIÈRE page paginée, un
  // lead plus ancien n'y figurait pas et le sélecteur repartait vide.
  const [leadDuDevis, setLeadDuDevis] = useState(null)
  const [produits, setProduits] = useState([])
  // STKCAT10 — LES STRUCTURES RÉELLEMENT SÉLECTIONNABLES de la société (non
  // archivées, chiffrées, de catégorie typée « structure »). Une seule et même
  // liste sert le sélecteur à l'écran ET la validation de l'id épinglé sur le
  // lead (`LEAD_APPLIQUE`) : le reducer ne peut donc pas poser une structure
  // que l'écran ne propose pas.
  const structuresCatalogue = useMemo(() => structuresEligibles(produits), [produits])
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState({})
  // Avertissements NON bloquants (n'empêchent jamais l'enregistrement) —
  // distincts de `errors` qui, eux, bloquent la sauvegarde.
  const [warnings, setWarnings] = useState({})
  // ERR-QAC-FACTURES-ECRAN-INVRAISEMBLABLES — signature de la série de
  // factures dont l'écart avec la facture d'hiver du lead a déjà été
  // CONFIRMÉ par le vendeur (second clic sur Enregistrer).
  const facturesEcartConfirme = useRef(null)
  // Chargement des référentiels (leads/clients/produits) : on distingue
  // « en cours » (selects affichent « Chargement… ») de « échec réseau »
  // (bannière rouge explicite plutôt qu'un select vide silencieux).
  const [refsLoading, setRefsLoading] = useState(true)
  const [loadFailed, setLoadFailed] = useState([])
  const [searchParams] = useSearchParams()
  const autoRan = useRef(false)
  // QJR99 — LA MACHINE À ÉTATS DU DIMENSIONNEMENT (QJR87) remplace les SIX
  // `useRef` « touché » (`modeTouched`, `structureTouched`, `tensionTouched`,
  // `pompeAlimTouched`, `nbPanneauxTouched`, `scenarioTouched`), le ref
  // `attenteSizingServeur` et les douze `useState` de champs qu'ils gardaient.
  // Un drapeau est désormais de l'ÉTAT : énumérable, testable, sérialisable —
  // c'est ce qui rend « ce que le vendeur a touché » lisible au lieu d'être
  // enfoui dans des refs invisibles.
  //
  // Mode choisi PAR L'UTILISATEUR (`touche.mode`) : un lead sélectionné ensuite
  // ne l'écrase jamais. Mêmes garde-fous « intact » pour structure / tension /
  // alimentation pompe / nombre de panneaux. ORDRE FONDATEUR (24/08) — le
  // scénario par défaut est « Les deux (Sans + Avec) » et ne cède qu'à un choix
  // EXPLICITE (`touche.scenario`).
  const [sizing, dispatchSizing] = useReducer(sizingReducer, ETAT_INITIAL)

  // EZ3 — L'ABANDON POST-CRÉATION. En pleine page, `finish()` renvoyait sur la
  // liste NUE en JETANT l'id du devis qu'on venait de passer 20 minutes à
  // construire : il fallait le retrouver à la main pour l'envoyer. Le mode
  // embarqué, lui, recevait déjà `onDone(devisId)`.
  // Désormais, la création en pleine page ouvre un PANNEAU DE SUCCÈS qui offre
  // l'action suivante évidente (envoyer, aperçu) sans re-chercher quoi que ce
  // soit. Le mode embarqué est INCHANGÉ.
  const [succes, setSucces] = useState(null) // { id, reference, total }
  const finish = (devisId, devisData) => {
    if (embedded) { onDone?.(devisId); return }
    setSucces({
      id: devisId,
      reference: devisData?.reference ?? editDevis?.reference ?? '',
      // ERR-QAH-VENTES-TOTAL-DIVERGENCE-CREATION — le total d'AFFICHAGE
      // canonique (celui de la liste et du PDF), pas une somme de lignes.
      total: devisData?.total_affiche ?? devisData?.total_ttc ?? null,
    })
  }
  const cancel = () => {
    if (embedded) { onCancel?.(); return }
    navigate('/ventes/devis')
  }

  // Édition d'un brouillon existant (?edit=ID) : chargé une fois, sauvegarde
  // EN PLACE (mêmes référence et statut) au lieu d'une création.
  const editId = embedded ? editIdProp : searchParams.get('edit')
  const [editDevis, setEditDevis] = useState(null)
  // QJR548 — le chargeur `?edit=` se relance quand le devis a été recomposé
  // côté serveur (taille d'offre appliquée) : `editLoaded` retient le numéro
  // de chargement déjà servi, `rechargeEdit` en demande un nouveau.
  const editLoaded = useRef(null)
  // QJR549 (contrat QJR503) — VERROU OPTIMISTE. `jetonRef` = `updated_at` du
  // devis tel que l'écran le connaît : capturé au chargement `?edit=` (et à
  // chaque rechargement), ré-armé depuis la réponse de CHAQUE écriture de cet
  // écran (replace-lines, etude-params, tailles d'offre) — sans quoi l'écran
  // se signalerait ses propres écritures. Envoyé en `expected_updated_at` ;
  // un 409 `devis_modifie` affiche la bannière « Modifié par X ».
  const jetonRef = useRef(null)
  const forcerSansJeton = useRef(false)
  const [conflitVerrou, setConflitVerrou] = useState(null)
  const armerJeton = (updatedAt) => { if (updatedAt) jetonRef.current = updatedAt }
  // QJR581 — fenêtre de capture de la référence « rien n'a changé ».
  const captureReferenceJusqua = useRef(0)
  const [rechargeEdit, setRechargeEdit] = useState(0)

  // QJ28 — « Contacter mon supérieur » pendant la génération : notifie le
  // supérieur du vendeur avec un lien vers le devis. Manuel (un bouton), et
  // seulement sur un devis déjà enregistré (édition).
  const [superieurBusy, setSuperieurBusy] = useState(false)
  const [superieurMsg, setSuperieurMsg] = useState(null)
  const contacterSuperieur = async () => {
    if (!editDevis?.id) return
    setSuperieurBusy(true)
    setSuperieurMsg(null)
    try {
      await ventesApi.contacterSuperieur(editDevis.id)
      setSuperieurMsg({ ok: true, text: 'Votre supérieur a été notifié.' })
    } catch (err) {
      const detail = err?.response?.data?.detail
      setSuperieurMsg({
        ok: false,
        text: typeof detail === 'string'
          ? detail : 'Notification du supérieur impossible.',
      })
    } finally {
      setSuperieurBusy(false)
    }
  }

  // QJR215 — le registre de surcharges (QJR214/QJR216) : lecture à l'ouverture,
  // pose EXPLICITE d'un chemin (le vendeur DÉCLARE, il ne devine pas), retour à
  // l'automatique par DELETE ?chemin=. `overridesReg` porte la forme EXACTE du
  // contrat (`overrides`/`effectif`/`lignes`, apps/ventes/contract_samples/
  // devis_overrides.json) — jamais recalculée ici, seulement affichée.
  // QJR572 — déclarée ici : `alignerSurRegistre` (ci-dessous) la pose.
  const [recommendedChoice, setRecommendedChoice] = useState('Auto')
  const [overridesReg, setOverridesReg] = useState(null)
  // QJR574 (D-QJR5-8) — le panneau BRUT « Surcharges (registre) » (chemin +
  // valeur JSON libre) est réservé aux administrateurs : Scénario, Option
  // recommandée et nombre de panneaux portent déjà la surcharge (QJR572).
  // L'endpoint reste IsResponsableOrAdmin ; le registre est lu pour tous.
  const estAdmin = useIsAdmin()
  const [overridesBusy, setOverridesBusy] = useState(false)
  // Un refus 400 est affiché TEL QUEL (le message FR du serveur, jamais avalé
  // ni remplacé par une phrase générique) — les formes varient selon le refus
  // (`{detail}`, `{chemin: "..."}`, `{chemin: ["..."]}`) : on en extrait la
  // PREMIÈRE valeur textuelle, sans reformuler son contenu.
  const [overridesErreur, setOverridesErreur] = useState(null)
  const [ovChemin, setOvChemin] = useState(CHEMINS_AUTORISES[0])
  const [ovValeur, setOvValeur] = useState('')

  const messageErreurOverrides = (err) => {
    const data = err?.response?.data
    if (data && typeof data === 'object') {
      const brut = Object.values(data)[0]
      const texte = Array.isArray(brut) ? brut[0] : brut
      if (typeof texte === 'string') return texte
    }
    // QJR309 — un refus CLIENT-SIDE de la liste blanche (`ventesApi.
    // poserOverrides`, AVANT tout réseau) est un TypeError NU, sans
    // `.response` : il ne doit JAMAIS être maquillé en refus du serveur — son
    // propre message nomme déjà le chemin fautif (voir `ventesApi.js`),
    // rendu tel quel plutôt que remplacé par la phrase générique ci-dessous.
    if (!err?.response && err instanceof TypeError && typeof err.message === 'string') {
      return err.message
    }
    return 'La surcharge a été refusée par le serveur.'
  }

  // QJR572 — LE REGISTRE GAGNE AU PDF (scenario.py, utils/options.py,
  // builder.py) : à l'arrivée du registre, Scénario, Option recommandée et
  // nombre de panneaux affichent la valeur qu'il IMPOSE, jamais une valeur
  // d'`etude_params` que le document ignore. Transition `REOUVERTURE` (le
  // choix est déjà fait), sans toucher aux autres champs.
  const alignerSurRegistre = (data) => {
    const imp = valeursImposees(data)
    const devis = {}
    if (typeof imp.scenario === 'string') devis.scenario = imp.scenario
    const n = Number.parseInt(imp['taille.nb_panneaux'], 10)
    if (n > 0) devis.panneaux = n
    if (Object.keys(devis).length) dispatchSizing({ type: 'REOUVERTURE', devis })
    if (imp.recommended_option === 'Sans batterie' || imp.recommended_option === 'Avec batterie') {
      setRecommendedChoice(imp.recommended_option)
    }
  }

  const chargerOverrides = (id) => {
    if (!id) return
    ventesApi.lireOverrides(id)
      .then(({ data }) => {
        // QJR581 — hydratation serveur tardive : la référence « rien n'a
        // changé » est re-capturée sur l'état qu'elle pose.
        captureReferenceJusqua.current = Date.now() + FENETRE_REFERENCE_MS
        setOverridesReg(data); alignerSurRegistre(data)
      })
      .catch(() => {})
  }

  // Lecture du registre À L'OUVERTURE d'un devis existant.
  // QJR572 — relu à CHAQUE ouverture d'un devis, jamais à chaque rendu.
  useEffect(() => {
    if (editDevis?.id) chargerOverrides(editDevis.id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editDevis?.id])

  const poserOverride = async () => {
    if (!editDevis?.id || !ovChemin) return
    setOverridesBusy(true)
    setOverridesErreur(null)
    let valeur
    try { valeur = JSON.parse(ovValeur) } catch { valeur = ovValeur }
    try {
      const { data } = await ventesApi.poserOverrides(editDevis.id, {
        [ovChemin]: { valeur },
      })
      setOverridesReg(data)
      setOvValeur('')
    } catch (err) {
      setOverridesErreur(messageErreurOverrides(err))
    } finally {
      setOverridesBusy(false)
    }
  }

  const regenererOverride = async (chemin) => {
    if (!editDevis?.id) return
    setOverridesBusy(true)
    setOverridesErreur(null)
    try {
      const { data } = await ventesApi.regenererOverride(editDevis.id, chemin)
      setOverridesReg(data)
    } catch (err) {
      setOverridesErreur(messageErreurOverrides(err))
    } finally {
      setOverridesBusy(false)
    }
  }

  // ── Document ──
  const [leadId, setLeadId] = useState('')
  // Pré-sélection d'un client passé en query (?client=<id>) depuis « Nouveau
  // devis » de la liste clients — plein écran et sans lead (un lead résout le
  // client côté serveur). Calculé à l'init : aucun setState dans un effet.
  const [clientId, setClientId] = useState(
    () => (!embedded && searchParams.get('client') && !searchParams.get('lead'))
      ? String(searchParams.get('client'))
      : '',
  )
  // QG3 — création rapide de client sans quitter le devis (chemin sans lead).
  const [clientQuickCreateOpen, setClientQuickCreateOpen] = useState(false)
  const [dateValidite, setDateValidite] = useState('')
  const [note, setNote] = useState('')
  // QJR624 — échéancier du devis rouvert (`null` = celui de la société). Il
  // n'est renvoyé que s'il était déjà propre au devis ou si le commercial l'a
  // touché : un devis qui suit la société n'en reçoit pas un figé en silence.
  const [echeancierSaisie, setEcheancierSaisieBrut] = useState(null)
  const echeancierAEnvoyer = useRef(false)
  // CIQ225 — jalons EFFECTIFS de la société (`payment_terms_effectifs`) : le défaut
  // de « Personnaliser l'échéancier » vient d'eux, plus d'une constante JS.
  const [termesEffectifs, setTermesEffectifs] = useState(null)
  const setEcheancierSaisie = useCallback((valeur) => {
    echeancierAEnvoyer.current = true
    setEcheancierSaisieBrut(valeur)
  }, [])

  // ── Factures électriques (valeurs initiales du simulateur) ──
  const [fHiver, setFHiver] = useState('')
  const [fEte, setFEte] = useState('')
  const [monthly, setMonthly] = useState(DEFAULT_MONTHLY_BILLS)
  // QF4 — distributeur réel + facture/consommation réelle du client, pour que
  // le calcul « deux factures » par tranche (backend QF2) utilise ses vrais
  // chiffres au lieu des défauts. Stockés dans etude_params à l'enregistrement
  // (distributeur, conso_annuelle) — jamais utilisés pour écraser les factures
  // mensuelles affichées ci-dessus (qui restent l'estimation hiver/été).
  const [distributeur, setDistributeur] = useState('onee')
  const [realBillMode, setRealBillMode] = useState('mad') // 'mad' | 'kwh'
  const [realBillMad, setRealBillMad] = useState('')
  const [realBillKwh, setRealBillKwh] = useState('')
  // COUV-HOR (29/09/2026) — ce que le VENDEUR a lui-même saisi, distingué de
  // ce que `?edit=` a réaffiché. Une facture/kWh tapée reste souveraine ; un
  // distributeur jamais choisi (le défaut 'onee' ci-dessus) n'est jamais
  // estampillé sur une conso que l'écran n'a pas calculée à son barème.
  const [realBillSaisi, setRealBillSaisi] = useState(false)
  const [distributeurChoisi, setDistributeurChoisi] = useState(false)
  // La conso STOCKÉE du devis rouvert : { valeur, descendDesFactures, factures }.
  const consoStockee = useRef(null)

  // VX237 — les handlers de collage nettoyé (onHiverPaste/onEtePaste/
  // onRealBillPaste) sont déclarés plus bas, APRÈS `syncBillEstimator` qu'ils
  // appellent (règle react-hooks/immutability : pas d'accès avant déclaration).

  // ── Paramètres techniques ──
  // QJR99 — les onze champs ci-dessous SONT l'état du reducer : l'écran les lit
  // sous leurs noms historiques (aucune ligne de rendu changée), mais plus
  // aucun `setState` ne les écrit — seuls des dispatches.
  //   · `kwcCible` (EZ5) est le miroir bidirectionnel de `nbPanneaux` ; la
  //     conversion vit dans le reducer (`SAISI`), plus dans deux gestionnaires.
  //   · `sizingInfo` (règle fondateur 18/08) justifie le palier retenu du
  //     balayage LOCAL (kWc, besoin lu sur la facture, payback). `null` = rien à
  //     montrer — et c'est TOUJOURS `null` en résidentiel depuis U3-MOTEUR.
  //   · `sizingServeurMessage` (= `motifMoteur`, U3-900) porte le message
  //     FRANÇAIS EXACT du serveur quand il décline : un vide honnête, jamais
  //     une supposition sur 900 DH.
  //   · `recalcDimTick` (= `compositionSeq`) fait relancer la composition même
  //     quand le recalcul retombe sur le MÊME nombre de panneaux.
  const {
    nbPanneaux, kwcCible, panelW, scenario, modeInstallation, sizingInfo,
    structure: structureType,
    // STKCAT10 — l'id du PRODUIT de structure choisi au catalogue ('' = aucun).
    structureProduitId,
    tension: tensionRaccordement,
    pompeAlim,
    motifMoteur: sizingServeurMessage,
    compositionSeq: recalcDimTick,
  } = sizing
  const [dayUsage, setDayUsage] = useState(DAY_USAGE_DEFAULTS['Résidentielle'])
  // Cache du dernier calcul (optimalKwcByPayback chiffre CHAQUE palier avec
  // le catalogue réel — pas gratuit) : évite de le rejouer à chaque frappe
  // de `syncBillEstimator` quand rien de pertinent n'a changé depuis.
  const sizingCacheRef = useRef({ key: '', result: null })

  // ── Lignes (prix TTC, comme le simulateur) & remise ──
  const [lines, setLines] = useState([])
  // Confirmation d'auto-remplissage agricole (m³/jour + champ PV) — affichée
  // une fois l'auto-remplissage pompage réussi.
  const [pompageAutoFilled, setPompageAutoFilled] = useState(false)
  // PVOND — onduleurs GRISÉS par le verrou de complétude : écartés de
  // l'auto-composition parce qu'il leur manque une variable du contrat
  // (puissance AC, MPPT, tensions, courant, rendement, plage batterie,
  // garantie). Chaque entrée porte {id, nom, manquantes[]} et s'affiche avec
  // son motif, comme « prix à renseigner » pour un produit non tarifé.
  const [onduleursIncomplets, setOnduleursIncomplets] = useState([])
  // U3COMPOSE (26/08/2026) — l'Auto-remplir résidentiel appelle désormais le
  // dry-run serveur (POST /ventes/devis/composition/, source de vérité
  // unique U3) au lieu de recomposer le kit en JavaScript : état de
  // chargement dédié pendant l'aller-retour réseau (le bouton porte
  // `loading={autoFillLoading}`).
  const [autoFillLoading, setAutoFillLoading] = useState(false)
  // QJR577 (D-QJR5-9) — UN SEUL COMPOSEUR en résidentiel : quand le dry-run
  // serveur (`ventesApi.composerDevis`) échoue, l'écran ne recompose PLUS en
  // JavaScript (`composeLocalement`, moteur que le dépôt documente divergent
  // du serveur : câbles, marques épinglées, ordre, arrondi) — les lignes ne
  // bougent pas, l'erreur est DITE et « Réessayer » rejoue le dry-run.
  // Effacé à chaque succès de `handleAutoFill`, quel que soit le marché.
  // (Remplace `compositionSourceLocale` + sa bannière QJR36/QJR211, dont il
  // ne restait plus aucun écrivain.)
  const [compositionErreur, setCompositionErreur] = useState(null)
  // DC11 / QJR106 — même patron que `sizingServeurMessage` et
  // `compositionErreur` ci-dessus : un VERDICT DU SERVEUR, rendu tel
  // quel, jamais recalculé ici. Le devis porte l'estampille des valeurs
  // énergie/toiture qu'il a REPRISES du lead ; le serveur (`apps.crm`) compare
  // avec le lead COURANT et rend la liste des champs qui ont bougé DEPUIS
  // (`lead_valeurs_modifiees` du GET devis). Liste vide ⇒ rien à dire.
  const [leadValeursModifiees, setLeadValeursModifiees] = useState([])
  // PVMRQ — réglages « Gammes & marques » de la société (chargés UNE fois,
  // best-effort : une société sans réglage ou un rôle non responsable/admin
  // — l'endpoint est `IsResponsableOrAdmin` — retombe sur `{}` silencieusement,
  // donc sur le comportement historique SANS préférence de marque).
  const [gammesConfig, setGammesConfig] = useState(null)
  // PVORD (fondateur 19/08/2026) — bouton « Enregistrer cet ordre comme
  // ordre par défaut » (voir handleSaveOrdreLignes) : état de chargement
  // dédié, séparé de `saving` (l'enregistrement du DEVIS) — les deux actions
  // sont indépendantes et ne doivent pas se griser l'une l'autre.
  const [savingOrdreLignes, setSavingOrdreLignes] = useState(false)
  // Gamme du devis rouvert (`etude_params.gamme.nom`, QJ29/services.gamme_nom) —
  // round-trip minimal : le générateur ne construit PAS de choix de gamme,
  // il lit seulement celle déjà posée par un devis existant pour résoudre la
  // bonne carte de marques (slot Essentielle par défaut, voir marquesActives).
  const [gammeNomDevis, setGammeNomDevis] = useState('')
  const [previewCollapsed, setPreviewCollapsed] = useState(false)
  const [tauxTva, setTauxTva] = useState('20.00')
  const [discountPct, setDiscountPct] = useState('0')
  const linesInitialized = useRef(false)
  // VX90 — après « Ajouter ligne », déplacer le focus sur le sélecteur produit
  // de la NOUVELLE ligne (ref-walk DOM via data-line-key ; pas de useFieldArray).
  const linesTableRef = useRef(null)
  const [pendingFocusKey, setPendingFocusKey] = useState(null)

  // ── QJ31 — Multi-propriétés (un seul devis, jamais scindé) ──
  // 'none' = mono-système (défaut, comportement historique inchangé) ;
  // 'multiplier' = ×N villas identiques (etude_params.nombre_proprietes) ;
  // 'villas' = groupes de lignes par villa (groupe_index/groupe_label, QJ29).
  const [multiMode, setMultiMode] = useState('none')
  const [nombreProprietes, setNombreProprietes] = useState('2')
  // Groupes villas (mode B) : [{ index, label }]. index 0 = équipement commun.
  const [villaGroups, setVillaGroups] = useState([
    { index: 0, label: 'Équipement commun' },
    { index: 1, label: 'Villa 1' },
  ])

  // ── Multi-marchés ── (`modeInstallation` vient du reducer, voir plus haut)
  // VX138(e) — le bloc « Plusieurs propriétés ? » est un accordéon replié PAR
  // DÉFAUT en agricole (carte non pertinente pour ce mode, jamais masquée) ;
  // état local pour que l'utilisateur puisse toujours le rouvrir librement —
  // seul un CHANGEMENT de mode réinitialise le défaut, pas les re-rendus.
  const [multiAccordionOpen, setMultiAccordionOpen] = useState(() => modeInstallation !== 'agricole')
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- réinitialise le défaut d'accordéon à chaque changement de mode
    setMultiAccordionOpen(modeInstallation !== 'agricole')
  }, [modeInstallation])
  const [consoMensuelle, setConsoMensuelle] = useState('')
  // QX44 — étude commerciale par catégorie (mode commercial). categorie +
  // réponses par catégorie (clés snake_case), stockées dans etude_params.
  const [categorieCommerciale, setCategorieCommerciale] = useState(CATEGORIE_NON_PRECISEE)
  const [commercialAnswers, setCommercialAnswers] = useState({})
  const setCommercialAnswer = (key, val) =>
    setCommercialAnswers(prev => ({ ...prev, [key]: val }))
  // QX50 — injection du surplus (loi 82-21). OFF par défaut, activable par devis
  // (industriel/commercial) ; la ligne ne s'affiche jamais sans sa mention.
  const [injectionEnabled, setInjectionEnabled] = useState(false)
  // QXMT — tension de raccordement du site (industriel/commercial). 'bt' par
  // défaut : tant qu'on n'a pas déclaré 'mt', l'étude est EXACTEMENT celle
  // d'avant. Le questionnaire du tunnel web pose déjà la question
  // (lead.web_questionnaire.tension_raccordement) — on la reprend s'il l'a.
  // (`tensionRaccordement` vient du reducer, voir plus haut.)
  // Répartition horaire de la consommation MT (%, saisie libre). VIDE par
  // défaut : les plages horaires MT officielles ne sont pas publiées, donc
  // aucune répartition n'est inventée — sans elle, l'étude MT omet les
  // économies plutôt que d'afficher un chiffre douteux.
  const [repartitionMt, setRepartitionMt] = useState({
    pointe: '', pleines: '', creuses: '',
  })
  const setPartMt = (key, val) => setRepartitionMt(p => ({ ...p, [key]: val }))
  // QXMT — un dossier raccordé en MOYENNE TENSION n'est pas facturé au barème
  // BT : l'étude passe alors au barème ONEE « Tarif Général (MT) », pondéré par
  // la répartition horaire du site. `estMt` ne vaut true QUE si l'utilisateur
  // (ou le questionnaire web) l'a déclaré — sinon tout le calcul reste celui
  // d'avant, à l'identique. Dérivé ICI, avant `validate()` et l'étude, pour
  // qu'aucun consommateur ne le lise avant sa déclaration.
  const estMt = tensionRaccordement === 'mt'
    && (modeInstallation === 'industriel' || modeInstallation === 'commercial')
  const tarifMtApplique = estMt ? tarifMtMoyen(repartitionMt) : null
  const etudeTension = { tensionRaccordement, repartitionMt }
  const [prixCible, setPrixCible] = useState('')
  // ── Logique de devis éditable (D5 ; Paramètres → Avancé). Défauts = constantes
  // historiques du simulateur, donc le devis est identique tant que rien n'est
  // édité. kwhPrice/efficiency alimentent les calculs ; prixCibleDefaut
  // pré-remplit le prix cible ; remiseMax = limite indicative.
  const [quoteLogic, setQuoteLogic] = useState({
    kwhPrice: KWH_PRICE, efficiency: EFFICIENCY,
    // DC4/DC6 — repères TVA société (défauts réforme 20/10) : pilotent les
    // repli de taux et l'avertissement de divergence, jamais un recalage forcé.
    tvaStandard: TVA_STANDARD_DEFAUT, tvaPanneaux: TVA_PANNEAUX_DEFAUT,
    // QX38 — override productible société (CompanyProfile.productible_kwh_kwc).
    // Défaut historique 1600 → productibleForCity lit alors le PVGIS par ville
    // (source unique alignée écran/PDF/web) ; une valeur société ≠ 1600 prime.
    productible: null,
  })
  const [remiseMax, setRemiseMax] = useState('')
  // QX20 — échappatoire documentée à la garde d'équipement : un avenant ou un
  // devis d'accessoires/main-d'œuvre seuls (SAV, extension câblage…) n'a pas à
  // contenir panneau+onduleur/pompe. OFF par défaut (garde active).
  const [accessoiresOnly, setAccessoiresOnly] = useState(false)
  // OFFGRID (ajout produit onduleur hors réseau) — « Raccordement » du devis,
  // même patron d'état qu'`accessoiresOnly` juste au-dessus (booléen simple,
  // PAS le reducer sizingReducer : orthogonal au dimensionnement kWc/panneaux
  // qu'il modélise). Défaut = raccordé au réseau (comportement byte-identique
  // à l'historique) ; `horsReseauTouched` protège un choix manuel du vendeur
  // contre un lead appliqué ensuite (même garde que les drapeaux « touché »
  // du reducer pour scenario/structure/tension).
  const [horsReseau, setHorsReseau] = useState(false)
  const [horsReseauTouched, setHorsReseauTouched] = useState(false)
  // Pompage (agricole)
  // AGR128 — TOUS les états initiaux agricoles sont VIDES hors lead : un
  // défaut (« 5.5 » CV, « 20 » m, « immergée », « souss-massa », « agrumes »,
  // « butane ») produisait un devis plausible sans aucune donnée du forage.
  const [pompeCv, setPompeCv] = useState('')
  const [pompeType, setPompeType] = useState('')
  // (`pompeAlim` vient du reducer, voir plus haut.)
  const [pompeHmt, setPompeHmt] = useState('')
  const [pompeDebit, setPompeDebit] = useState('')
  const [pompeProfondeur, setPompeProfondeur] = useState('')
  const [pompeDistance, setPompeDistance] = useState('')
  const [pompeHeures, setPompeHeures] = useState(String(HEURES_POMPAGE_DEFAUT))
  // ── Exploitation agricole (données GUIDÉES, toutes optionnelles) — alimentent
  // le calcul FAO-56 (besoin en eau) et le redimensionnement/chiffrage du PDF.
  // Stockées dans etude_params sous ces clés exactes (le backend les relit).
  const [farmRegion, setFarmRegion] = useState('')
  const [farmCrop, setFarmCrop] = useState('')
  const [farmSurfaceHa, setFarmSurfaceHa] = useState('')
  const [farmIrrigation, setFarmIrrigation] = useState('')
  // Dépense carburant ACTUELLE : saisie au mois OU à l'année (bascule), mais
  // stockée toujours en MAD/AN (fuel_spend_current).
  // AGR212 — l'économie DÉCLARÉE (énergie, consommation, prix payé daté,
  // mois d'irrigation, facture réseau, entretien) : tout vide au départ,
  // écrit dans `saisies_economie_pompage` — plus jamais « butane » par
  // défaut, plus jamais × 12.
  const [ecoPompage, setEcoPompage] = useState(ECO_POMPAGE_VIDE)
  const majEco = useCallback(
    (cle, valeur) => setEcoPompage((e) => ({ ...e, [cle]: valeur })), [])
  // AGR218 — attestation d'usage agricole (case + date + signataire).
  const [attestationAgricole, setAttestationAgricole] = useState(ATTESTATION_VIDE)
  const majAttestation = useCallback(
    (cle, valeur) => setAttestationAgricole((a) => ({ ...a, [cle]: valeur })), [])
  const [reperesEnergie, setReperesEnergie] = useState({})
  const [farmHmtStatic, setFarmHmtStatic] = useState('')
  const [farmHmtDrawdown, setFarmHmtDrawdown] = useState('')
  // AGR128 — les blocs NOUVEAUX du générateur agricole (cas de pompe,
  // besoin, point d'eau, HMT détaillée), vides au départ. `majPompage`
  // pose UNE valeur à son chemin (copie, jamais en place).
  const [pompageSaisie, setPompageSaisie] = useState(POMPAGE_SAISIE_VIDE)
  const majPompage = useCallback(
    (chemin, valeur) => setPompageSaisie((s) => poserSaisie(s, chemin, valeur)),
    [],
  )

  // ── VX62 — Brouillon auto + garde de sortie ──
  // Le formulaire (2 300+ lignes, ~20 min de saisie) n'avait NI brouillon NI
  // garde : un onglet fermé/un swipe retour = tout perdu. On sauvegarde un
  // snapshot débouncé dans localStorage (clé scopée lead/client/édition), on
  // propose « Reprendre le brouillon » au montage, on purge au succès, et on
  // pose useDirtyGuard pour la fermeture d'onglet.
  const draftKey = editId
    ? `devis:edit:${editId}`
    : (leadId ? `devis:lead:${leadId}` : (clientId ? `devis:client:${clientId}` : 'devis:new'))
  // Snapshot des champs éditables saillants (les référentiels leads/clients/
  // produits ne sont jamais persistés — seulement la saisie de l'utilisateur).
  const draftSnapshot = useMemo(() => ({
    leadId, clientId, dateValidite, scenario, recommendedChoice, note,
    fHiver, fEte, monthly, distributeur, realBillMode, realBillMad, realBillKwh,
    realBillSaisi, distributeurChoisi,
    nbPanneaux, panelW, structureType, structureProduitId, dayUsage, lines, tauxTva, discountPct,
    multiMode, nombreProprietes, villaGroups, modeInstallation, consoMensuelle,
    categorieCommerciale, commercialAnswers, injectionEnabled,
    tensionRaccordement, repartitionMt,
    prixCible, remiseMax, accessoiresOnly, horsReseau, horsReseauTouched,
    pompeCv, pompeType, pompeAlim, pompeHmt, pompeDebit, pompeProfondeur,
    pompeDistance, pompeHeures, farmRegion, farmCrop, farmSurfaceHa,
    farmIrrigation, ecoPompage, attestationAgricole, farmHmtStatic,
    farmHmtDrawdown, pompageSaisie,

  }), [
    leadId, clientId, dateValidite, scenario, recommendedChoice, note,
    fHiver, fEte, monthly, distributeur, realBillMode, realBillMad, realBillKwh,
    realBillSaisi, distributeurChoisi,
    nbPanneaux, panelW, structureType, structureProduitId, dayUsage, lines, tauxTva, discountPct,
    multiMode, nombreProprietes, villaGroups, modeInstallation, consoMensuelle,
    categorieCommerciale, commercialAnswers, injectionEnabled,
    tensionRaccordement, repartitionMt,
    prixCible, remiseMax, accessoiresOnly, horsReseau, horsReseauTouched,
    pompeCv, pompeType, pompeAlim, pompeHmt, pompeDebit, pompeProfondeur,
    pompeDistance, pompeHeures, farmRegion, farmCrop, farmSurfaceHa,
    farmIrrigation, ecoPompage, attestationAgricole, farmHmtStatic,
    farmHmtDrawdown, pompageSaisie,
  ])
  // « Dirty » = l'utilisateur a réellement saisi quelque chose de significatif
  // (au moins un identifiant de cible OU une note OU des factures OU des
  // paramètres techniques). Tant que le formulaire est vierge, ni brouillon ni
  // garde ne s'activent (évite un bandeau/blocage sur un simple montage).
  // EZ4 — L'ANGLE MORT DU BROUILLON : `dirty` ignorait `lines`, `discountPct`,
  // `tauxTva` et `villaGroups` — or ces quatre champs sont DÉJÀ dans
  // `draftSnapshot` ci-dessus. Un utilisateur qui n'avait fait qu'ajouter des
  // LIGNES (le cœur du devis) n'était donc ni sauvegardé ni protégé par la
  // garde de fermeture d'onglet. Seul ce prédicat était à corriger.
  const lignesSaisies = lines.some(
    (l) => l.produit || (l.designation || '').trim() || parseFloat(l.prix_unit_ttc) > 0,
  )
  const remiseSaisie = parseFloat(discountPct) > 0
  const tvaModifiee = String(tauxTva ?? '') !== '' && parseFloat(tauxTva) !== TVA_STANDARD_DEFAUT
  // `villaGroups` a des libellés PAR DÉFAUT : le signal utile est le mode
  // multi-propriétés lui-même (défaut 'none'), pas la présence de libellés.
  const villasSaisies = multiMode !== 'none'
  const formulaireNonVierge = Boolean(
    leadId || clientId || note || fHiver || fEte || nbPanneaux
    || consoMensuelle || prixCible || pompeHmt || pompeDebit || farmSurfaceHa
    || lignesSaisies || remiseSaisie || tvaModifiee || villasSaisies,
  )
  // QJR581 — « dirty » veut dire « DIFFÉRENT de la référence » : l'état que le
  // mappeur `?edit=` vient de poser (édition) ou le dernier enregistrement
  // réussi. Sans référence : non-vacuité en création, jamais en édition (le
  // devis n'est pas encore chargé). Avant, ouvrir un devis sans rien toucher
  // écrivait un « brouillon non enregistré » et armait la garde de sortie,
  // même après un enregistrement réussi.
  const snapshotJson = useMemo(() => JSON.stringify(draftSnapshot), [draftSnapshot])
  const [referenceEcran, setReferenceEcran] = useState(null)
  useEffect(() => {
    if (Date.now() < captureReferenceJusqua.current) {
      setReferenceEcran(snapshotJson)
    }
  }, [snapshotJson])
  const dirty = referenceEcran != null
    ? snapshotJson !== referenceEcran
    : (editId ? false : formulaireNonVierge)
  const { restored, restore, discard, clear, savedAt } = useDraftAutosave(draftKey, draftSnapshot, {
    enabled: dirty,
    version: editId ? (editDevis?.updated_at ?? null) : undefined,
  })
  useDirtyGuard(dirty)
  // QJR581 — un brouillon local d'édition n'est repris que s'il porte la
  // version COURANTE du devis ; sinon (devis modifié depuis, ou brouillon
  // d'avant QJR581 sans version) il est purgé, avec une notice.
  const brouillonPerime = Boolean(editId && restored && editDevis
    && restored.version !== editDevis.updated_at)
  const brouillonProposable = Boolean(restored
    && (!editId || (editDevis && restored.version === editDevis.updated_at)))
  useEffect(() => {
    if (!brouillonPerime) return
    discard()
    toast.info('Brouillon local ignoré : ce devis a été modifié depuis.')
  }, [brouillonPerime, discard])
  // Après un enregistrement réussi, l'état courant DEVIENT la référence.
  const marquerEnregistre = () => setReferenceEcran(snapshotJson)

  // Restauration : réinjecte le snapshot sauvegardé dans tous les setters.
  const handleRestoreDraft = () => {
    const d = restore()
    if (!d) return
    if (d.leadId != null) setLeadId(d.leadId)
    if (d.clientId != null) setClientId(d.clientId)
    if (d.dateValidite != null) setDateValidite(d.dateValidite)
    // QJR641 — un vieux brouillon qui porte encore `instType` : clé ignorée.
    // Le scénario du brouillon local est lui aussi un choix déjà posé : un lead
    // sélectionné après restauration ne le réécrit pas. QJR99 — même effet
    // qu'avant (`scenarioTouched.current = true` + `setScenario`), en UNE
    // transition. Il DOIT précéder le marché ci-dessous : c'est ce qui empêche
    // `MARCHE_CHANGE` de reposer le défaut du marché par-dessus.
    if (d.scenario != null) dispatchSizing({ type: 'SAISI', champ: 'scenario', valeur: d.scenario })
    if (d.recommendedChoice != null) setRecommendedChoice(d.recommendedChoice)
    if (d.note != null) setNote(d.note)
    if (d.fHiver != null) setFHiver(d.fHiver)
    if (d.fEte != null) setFEte(d.fEte)
    if (d.monthly != null) setMonthly(d.monthly)
    if (d.distributeur != null) setDistributeur(d.distributeur)
    if (d.realBillMode != null) setRealBillMode(d.realBillMode)
    if (d.realBillMad != null) setRealBillMad(d.realBillMad)
    if (d.realBillKwh != null) setRealBillKwh(d.realBillKwh)
    if (d.realBillSaisi != null) setRealBillSaisi(!!d.realBillSaisi)
    if (d.distributeurChoisi != null) setDistributeurChoisi(!!d.distributeurChoisi)
    // QJR99 — les champs du reducer se restaurent par dispatch. `REOUVERTURE`
    // pose le compte de panneaux SANS le marquer « touché » (comportement
    // historique : un brouillon restauré n'est pas une frappe) ; `SAISI panelW`
    // n'a jamais eu de drapeau propre. `MARCHE_CHANGE` en origine
    // `programme` ne marque pas le marché non plus — le lead peut encore le
    // pré-régler, exactement comme avant.
    if (d.panelW != null) dispatchSizing({ type: 'SAISI', champ: 'panelW', valeur: d.panelW })
    if (d.nbPanneaux != null) dispatchSizing({ type: 'REOUVERTURE', devis: { panneaux: d.nbPanneaux } })
    if (d.structureType != null) dispatchSizing({ type: 'SAISI', champ: 'structure', valeur: d.structureType })
    // STKCAT10 — le PRODUIT de structure se restaure comme le reste du
    // brouillon : sans ça, reprendre un brouillon reperdait la pergola
    // choisie et recomposait en acier, en silence.
    if (d.structureProduitId != null) {
      dispatchSizing({ type: 'SAISI', champ: 'structureProduit', valeur: d.structureProduitId })
    }
    if (d.dayUsage != null) setDayUsage(d.dayUsage)
    if (Array.isArray(d.lines)) { setLines(withKeys(d.lines)); linesInitialized.current = true }
    if (d.tauxTva != null) setTauxTva(d.tauxTva)
    if (d.discountPct != null) setDiscountPct(d.discountPct)
    if (d.multiMode != null) setMultiMode(d.multiMode)
    if (d.nombreProprietes != null) setNombreProprietes(d.nombreProprietes)
    if (Array.isArray(d.villaGroups)) setVillaGroups(d.villaGroups)
    if (d.modeInstallation != null) {
      dispatchSizing({ type: 'MARCHE_CHANGE', mode: d.modeInstallation, origine: 'programme' })
    }
    if (d.consoMensuelle != null) setConsoMensuelle(d.consoMensuelle)
    if (d.categorieCommerciale != null) setCategorieCommerciale(d.categorieCommerciale)
    if (d.commercialAnswers && typeof d.commercialAnswers === 'object') setCommercialAnswers(d.commercialAnswers)
    if (d.injectionEnabled != null) setInjectionEnabled(d.injectionEnabled)
    if (d.tensionRaccordement != null) {
      dispatchSizing({ type: 'SAISI', champ: 'tension', valeur: d.tensionRaccordement })
    }
    if (d.repartitionMt && typeof d.repartitionMt === 'object') setRepartitionMt(d.repartitionMt)
    if (d.prixCible != null) setPrixCible(d.prixCible)
    if (d.remiseMax != null) setRemiseMax(d.remiseMax)
    if (d.accessoiresOnly != null) setAccessoiresOnly(d.accessoiresOnly)
    // OFFGRID — un choix déjà posé (brouillon local) est un choix EXPLICITE :
    // il ferme `horsReseauTouched`, sinon un lead appliqué après restauration
    // écraserait le raccordement que le vendeur avait retenu.
    if (d.horsReseau != null) { setHorsReseau(d.horsReseau); setHorsReseauTouched(true) }
    if (d.pompeCv != null) setPompeCv(d.pompeCv)
    if (d.pompeType != null) setPompeType(d.pompeType)
    if (d.pompeAlim != null) dispatchSizing({ type: 'SAISI', champ: 'pompeAlim', valeur: d.pompeAlim })
    if (d.pompeHmt != null) setPompeHmt(d.pompeHmt)
    if (d.pompeDebit != null) setPompeDebit(d.pompeDebit)
    if (d.pompeProfondeur != null) setPompeProfondeur(d.pompeProfondeur)
    if (d.pompeDistance != null) setPompeDistance(d.pompeDistance)
    if (d.pompeHeures != null) setPompeHeures(d.pompeHeures)
    if (d.farmRegion != null) setFarmRegion(d.farmRegion)
    if (d.farmCrop != null) setFarmCrop(d.farmCrop)
    if (d.farmSurfaceHa != null) setFarmSurfaceHa(d.farmSurfaceHa)
    if (d.farmIrrigation != null) setFarmIrrigation(d.farmIrrigation)
    if (d.ecoPompage && typeof d.ecoPompage === 'object') setEcoPompage(d.ecoPompage)
    if (d.attestationAgricole && typeof d.attestationAgricole === 'object') {
      setAttestationAgricole(d.attestationAgricole)
    }
    if (d.farmHmtStatic != null) setFarmHmtStatic(d.farmHmtStatic)
    if (d.farmHmtDrawdown != null) setFarmHmtDrawdown(d.farmHmtDrawdown)
    if (d.pompageSaisie && typeof d.pompageSaisie === 'object') setPompageSaisie(d.pompageSaisie)
  }

  useEffect(() => {
    // Les trois échecs réseau sont SURFACÉS (bannière) au lieu d'avaler l'erreur :
    // un select vide sans explication n'aide personne. (refsLoading/loadFailed
    // partent déjà de true/[] ; on ne re-set rien de synchrone dans l'effet.)
    const fail = (label) => setLoadFailed(prev =>
      prev.includes(label) ? prev : [...prev, label])
    // RÉGRESSION CONFIRMÉE (CI run 32200473257, e2e devis.spec.js E4, même
    // appel que LeadDevisPanel.jsx) — `stockApi.getProduits()` sans
    // paramètre ne renvoie que la PAGE 1 (50 produits, triés par nom). Un
    // catalogue de plus de 50 références perd silencieusement une famille
    // triée après la coupure (« Panneau… » est passée en page 2 sur le
    // catalogue de démo, count=101) : l'auto-remplissage la voit comme
    // absente du stock. `fetchAllPages` (VX54, déjà le chemin de
    // stockSlice.js) lit le catalogue ENTIER.
    Promise.allSettled([
      crmApi.getClients().then(r => setClients(r.data.results ?? r.data)).catch(() => { fail('clients'); throw 0 }),
      crmApi.getLeads().then(r => setLeads(r.data.results ?? r.data)).catch(() => { fail('leads'); throw 0 }),
      fetchAllPages((page) => stockApi.getProduits({ page }).then((r) => r.data))
        .then(setProduits).catch(() => { fail('produits'); throw 0 }),
    ]).finally(() => setRefsLoading(false))
  }, [])

  // Table par défaut du simulateur une fois le stock chargé
  useEffect(() => {
    if (linesInitialized.current || !produits.length) return
    linesInitialized.current = true
    // QJR570 — les lignes par défaut sont une composition (pas une saisie).
    setLines(withKeys(defaultProductLines(produits).map(r => ({ ...r, compose: true }))))
  }, [produits])

  // QJR576 — LA conversion partagée ; compte ENTIER (plancher explicite).
  const kwp = kwcPourPanneaux(Math.floor(parseFloat(nbPanneaux) || 0), panelW)
  // QJR568 — `kwp` reste la CIBLE (envoyée au dry-run de composition) ; le kWc
  // réellement FACTURÉ par les lignes (celui que le PDF dérive) alimente
  // prix/kWc, prix cible, études C&I et l'aperçu horaire. Repli sur la cible
  // sans ligne panneau.
  const kwpLignes = kwcFactureDesLignes(lines, panelW, kwp)
  const panneauxLignes = comptePanneauxOption(lines, 'sans')

  // L-2OPT — kWc PROPRE à l'option « Avec batterie ». `kwp` ci-dessus est le
  // compte de la branche SANS (le rechargement d'un brouillon exclut
  // explicitement les lignes taguées 'avec'), alors que `totals.totalAvec` et
  // `batteryKwhFromLines` chiffrent la composition AVEC ENTIÈRE. Sans ce
  // second kWc, l'écran divisait un coût « avec » par une économie « sans » :
  // payback affiché plusieurs fois trop long, et l'étude horaire serveur
  // interrogée sur une chimère (kWc sans + batteries avec).
  // Dérivé des LIGNES avec la règle du backend (variante '' + 'avec').
  // NON DIVERGENT (aucune ligne variantée, ou les deux branches au même
  // nombre de panneaux) ⇒ `kwp` est renvoyé TEL QUEL : aucune re-dérivation
  // flottante, comportement byte-identique à l'historique.
  const kwpAvec = (() => {
    const nSans = comptePanneauxOption(lines, 'sans')
    const nAvec = comptePanneauxOption(lines, 'avec')
    // QJR568 — non divergent : le kWc FACTURÉ des lignes (repli : la cible).
    if (nSans <= 0 || nAvec === nSans) return kwpLignes
    return nAvec * (parseFloat(panelW) || 0) / 1000
  })()

  // EZ5 — dimensionner en kWc. Les deux champs sont BIDIRECTIONNELS : taper une
  // puissance cible remplit les panneaux (via `panneauxPourKwc`, la conversion
  // DÉJÀ utilisée par le pré-remplissage depuis le lead — rien de réécrit), et
  // changer les panneaux remet la cible à jour. Aucune valeur n'est jamais
  // rejetée ni « snappée » : le champ garde EXACTEMENT ce qui est tapé, la
  // conversion ne s'applique qu'une fois le nombre lisible (garde `step="any"`
  // + `noValidate` intactes).
  // QJR99 — les deux gestionnaires ne sont plus que des dispatches : la
  // conversion bidirectionnelle, le drapeau « touché » et l'effacement du
  // justificatif « palier retenu » vivent DANS le reducer (`SAISI`), en une
  // seule transition — plus deux gestionnaires qui devaient rester d'accord.
  const onKwcCibleChange = (v) =>
    dispatchSizing({ type: 'SAISI', champ: 'kwcCible', valeur: v })
  const onNbPanneauxChange = (v) =>
    dispatchSizing({ type: 'SAISI', champ: 'nbPanneaux', valeur: v })
  // Le nombre de panneaux peut aussi être posé SANS passer par le champ
  // (pré-remplissage depuis un lead, dimensionnement pompage, reprise de
  // brouillon) : on renseigne alors la cible si elle est encore vide — jamais
  // par-dessus une valeur tapée par l'utilisateur. Re-dispatcher la puissance
  // panneau COURANTE recale la cible sur le compte courant sans poser aucun
  // drapeau (`SAISI panelW` n'en a jamais eu) : c'est le seul chemin du reducer
  // qui écrit `kwcCible` sans rien marquer.
  useEffect(() => {
    if (kwcCible !== '' || kwp <= 0) return
     
    dispatchSizing({ type: 'SAISI', champ: 'panelW', valeur: panelW })
  }, [kwp, kwcCible, panelW])

  // QJR572 — ce que le registre IMPOSE (indications sous les Select).
  const imposees = useMemo(() => valeursImposees(overridesReg), [overridesReg])

  const showSans = scenario !== 'Avec batterie'
  const showAvec = scenario !== 'Sans batterie'
  const recommended = recommendedChoice !== 'Auto'
    ? recommendedChoice
    : (scenario === 'Sans batterie' ? 'Sans batterie' : 'Avec batterie')
  const sansRec = recommended === 'Sans batterie'
  const avecRec = recommended === 'Avec batterie'

  // ── Totaux + simulation, recalculés en direct ──
  // ERR-QAH-VENTES-TOTAL-DIVERGENCE-CREATION — le SCÉNARIO déclaré entre dans
  // le calcul : c'est lui qui, au noyau, fait d'un devis à deux onduleurs un
  // devis à deux options (panier filtré + règle QF9). Sans lui, le formulaire
  // chiffrait l'option AVEC avec les accessoires Huawei que le serveur retire.
  const totals = useMemo(
    () => optionTotalsTTC(lines, discountPct, { scenario }),
    [lines, discountPct, scenario],
  )

  // ── QJRREM (fondateur 07/09/2026) — remise par ligne, écran de création ──
  // « La remise de 5 % est gardée partout et s'applique aussi à chaque poste
  // de la liste des composants, de l'installation, de tout. » Jusqu'ici la
  // remise globale n'apparaissait QUE dans le rail (`totals` ci-dessus) :
  // impossible de dire au client ce que CE poste coûte après remise.
  // Répartition partagée avec le miroir du noyau (`features/ventes/remise.js`,
  // mêmes cas de test que `apps/ventes/tests/test_remise_par_ligne.py`),
  // jamais un calcul local — même patron que `DevisForm.jsx` (écran
  // d'édition HT, déjà livré). Le champ s'appelle `totalHt` dans le miroir
  // mais reçoit ici le TTC de ligne (même formule que `DevisLineRow.lineTtc`,
  // cet écran restant 100 % TTC — aucune conversion HT).
  //
  // POPULATION — `repartirRemiseParLigne` retient les lignes non optionnelles
  // de type produit (`ligneCompteDansTotaux`, via les champs
  // `optionnelle`/`typeLigne` mappés ci-dessous). QJR567 — le total du rail
  // (`optionTotalsTTC` ci-dessus) filtre désormais par LA MÊME fonction avant
  // de répartir les lignes en DEUX paniers Sans/Avec batterie au fil des
  // mots-clés/`variante` (`appartientAuPanierSans`/`appartientAuPanierAvec`) :
  // avant, il comptait une ligne optionnelle que le document exclut. Sur un
  // devis mono-composition (aucune ligne `variante`), les deux paniers
  // réunissent donc les mêmes lignes que la répartition ci-dessous (aux
  // arrondis de chaîne près : le rail suit la chaîne canonique HT → TVA du
  // noyau, la répartition ventile un TTC de ligne). Sur un devis « Les deux » (deux options DÉCLARÉES, lignes
  // `variante: 'sans'|'avec'`), la répartition ci-dessous porte sur TOUTES
  // les lignes non optionnelles des deux paniers réunis — elle recolle au
  // total des deux paniers ADDITIONNÉS, pas au total d'une option affichée
  // séparément. Une vraie répartition PAR PANIER exigerait deux appels
  // distincts au miroir sur deux univers de lignes disjoints : hors périmètre
  // de QJRREM, laissé pour une tâche dédiée si le fondateur le demande.
  const lignesRemiseesTtc = useMemo(
    () => repartirRemiseParLigne(
      lines.map(l => ({
        totalHt: (parseFloat(l.quantite) || 0) * (parseFloat(l.prix_unit_ttc) || 0),
        optionnelle: l.optionnelle,
        typeLigne: l.typeLigne,
      })),
      discountPct,
    ),
    [lines, discountPct],
  )
  // Condition d'affichage = remise > 0 (jamais « montant ≠ catalogue ») :
  // remise nulle ⇒ écran inchangé à l'octet (le miroir rend le catalogue).
  const montrerRemise = (parseFloat(discountPct) || 0) > 0

  // QJ31 — aperçu multi-propriétés (miroir écran du backend QJ29). Null quand
  // aucun mode multi n'est actif (aperçu mono-système inchangé).
  const multiPreview = useMemo(
    () => multiPropertyPreviewTTC(lines, {
      nombreProprietes: multiMode === 'multiplier' ? nombreProprietes : null,
      discountPct,
    }),
    [lines, multiMode, nombreProprietes, discountPct],
  )

  // Simulation/graphique en VALEURS DIFFÉRÉES : la frappe et les bascules
  // restent instantanées (les champs gardent leurs valeurs exactes — rien
  // n'est perdu ni arrondi), le recalcul lourd + recharts suit d'un souffle.
  const dMonthly = useDeferredValue(monthly)
  const dLines = useDeferredValue(lines)
  const dTotals = useDeferredValue(totals)
  const dKwp = useDeferredValue(kwp)
  const dKwpLignes = useDeferredValue(kwpLignes)
  const dKwpAvec = useDeferredValue(kwpAvec)
  const dDayUsage = useDeferredValue(dayUsage)

  // BAT5DEF (26/08/2026) — au moins une ligne batterie n'a pas de kWh lisible
  // dans sa désignation : `batteryKwhFromLines` ne lui compte plus un défaut
  // fabriqué de 5 kWh (RÈGLE FONDATEUR « zéro chiffre inventé »), donc la
  // capacité utilisée en aval (ROI, étude horaire) peut être SOUS-estimée.
  // Signalé à l'écran plutôt que tu — jamais un chiffre qu'on tairait.
  const capaciteBatterieInconnue = useMemo(
    () => batteryCapaciteInconnue(dLines), [dLines])

  // QF4/QF5 — consommation annuelle RÉELLE dérivée de la facture/kWh du
  // client (barème par tranche du distributeur choisi). Alimente à la fois
  // etude_params (à l'enregistrement) et l'aperçu écran (roi ci-dessous) —
  // UNE seule dérivation, jamais deux chiffres qui pourraient diverger.
  const consoAnnuelleReelle = (() => {
    if (realBillMode === 'kwh') {
      const kwh = parseFloat(realBillKwh) || 0
      return kwh > 0 ? Math.round(kwh * 12) : null
    }
    const mad = parseFloat(realBillMad) || 0
    if (mad <= 0) return null
    const { kwhMensuel } = kwhFromBill(mad, distributeur)
    return kwhMensuel > 0 ? Math.round(kwhMensuel * 12) : null
  })()

  // N1/N4 — `monthly` démarre avec les valeurs D'EXEMPLE du simulateur
  // (DEFAULT_MONTHLY_BILLS) : tant qu'aucune n'a été touchée (hiver/été,
  // « Estimer 12 mois », ou une case du détail mensuel éditée à la main),
  // AUCUNE vraie facture client n'existe encore. Sert à la fois à décider si
  // le graphique écran peut se présenter comme un fait (N4) et si
  // `etude_params.factures_mensuelles_reelles` doit être semé à
  // l'enregistrement (N1) — jamais les valeurs d'exemple.
  const facturesSaisies = monthly.some(
    (v, i) => Number(v) !== DEFAULT_MONTHLY_BILLS[i])

  // Lead prioritaire résolu tôt : le calcul ROI ci-dessous lit sa ville
  // (productible par ville) — doit être déclaré avant le useMemo (pas de TDZ).
  const leadsListe = (leadDuDevis
    && !leads.some(l => String(l.id) === String(leadDuDevis.id)))
    ? [leadDuDevis, ...leads] : leads
  const selectedLead = leadsListe.find(l => String(l.id) === String(leadId))

  const roi = useMemo(() => {
    if (dKwp <= 0 || !dMonthly.some(v => v > 0)) return null
    return computeROI({
      kwp: dKwp,
      factures: dMonthly.map(v => parseFloat(v) || 0),
      dayUsagePct: parseInt(dDayUsage) || 50,
      totalSans: dTotals.totalSans,
      totalAvec: dTotals.totalAvec,
      batteryKwh: batteryKwhFromLines(dLines),
      // Q1 (fondateur 20/08/2026) — lignes RÉELLES pour la provision de
      // remplacement onduleur (prix TTC de la ligne, jamais 8 % forfaitaires).
      lines: dLines,
      kwhPrice: quoteLogic.kwhPrice,
      efficiency: quoteLogic.efficiency,
      // QF5 — bascule sur le modèle « deux factures » par tranche (parité
      // PDF) dès qu'une consommation réelle + un distributeur sont connus.
      consoAnnuelleKwh: consoAnnuelleReelle,
      utility: distributeur,
      // QX38 — productible CANONIQUE PVGIS par ville (source unique alignée
      // avec le PDF/web) ; override société si renseigné ≠ 1600.
      productible: productibleForCity(
        (selectedLead?.ville_effective ?? selectedLead?.ville) || '', quoteLogic.productible),
    })
  }, [dKwp, dMonthly, dDayUsage, dTotals, dLines, quoteLogic,
    consoAnnuelleReelle, distributeur, selectedLead])

  // L-2OPT — miroir local de `roi` recalculé AU kWc DE LA BRANCHE AVEC. `null`
  // dès que rien ne diverge (`kwpAvec === kwp`) : l'écran retombe alors mot
  // pour mot sur `roi`, aucun second calcul, comportement d'hier. Quand les
  // deux optimiseurs ont réellement rendu deux tailles, seuls les champs
  // « avec » de CE résultat sont lus (l'option sans garde `roi`).
  const roiAvec = useMemo(() => {
    // QJR568 — « non divergent » se juge contre le kWc FACTURÉ des lignes
    // (`kwpAvec` y retombe quand les options ne divergent pas).
    if (dKwpAvec === dKwp || dKwpAvec === dKwpLignes) return null
    if (dKwpAvec <= 0 || !dMonthly.some(v => v > 0)) return null
    return computeROI({
      kwp: dKwpAvec,
      factures: dMonthly.map(v => parseFloat(v) || 0),
      dayUsagePct: parseInt(dDayUsage) || 50,
      totalSans: dTotals.totalSans,
      totalAvec: dTotals.totalAvec,
      batteryKwh: batteryKwhFromLines(dLines),
      lines: dLines,
      kwhPrice: quoteLogic.kwhPrice,
      efficiency: quoteLogic.efficiency,
      consoAnnuelleKwh: consoAnnuelleReelle,
      utility: distributeur,
      productible: productibleForCity(
        (selectedLead?.ville_effective ?? selectedLead?.ville) || '', quoteLogic.productible),
    })
  }, [dKwpAvec, dKwp, dKwpLignes, dMonthly, dDayUsage, dTotals, dLines, quoteLogic,
    consoAnnuelleReelle, distributeur, selectedLead])

  // QJR586 — la ville de CALCUL du lead sélectionné (servie par le serveur).
  const villeCalculLead = villeEffectiveLead(selectedLead)

  // Source des chiffres « avec batterie » du miroir local : `roiAvec` quand
  // les deux optimiseurs divergent, sinon `roi` (identique par construction).
  const roiPourAvec = roiAvec || roi

  // CJ2b — ORDRE FONDATEUR : « on ne voit ni l'économie réelle calculée, ni
  // les données PVGIS — cette donnée devrait être comparée à la courbe de
  // consommation ». Résidentiel UNIQUEMENT : appelle le moteur horaire
  // serveur (intégration PVGIS réelle × consommation réelle, mois par mois)
  // au lieu de ne montrer QUE le miroir local `roi` ci-dessus (conservé
  // intact comme repli hors-ligne). `null` = rien à ancrer (aucune facture,
  // aucun devis) : aucun appel réseau (règle d'honnêteté — on omet, on
  // n'invente pas).
  const etudeHoraireCorps = modeInstallation === 'residentiel'
    ? construireCorpsPreview({
        modeInstallation,
        editId,
        leadId,
        fHiver,
        fEte,
        eteDifferente: !!fEte && Number(fEte) > 0,
        ville: villeCalculLead,
        raccordement: selectedLead?.raccordement || '',
        // QJR568 — le kWc FACTURÉ par les lignes, pas la seule cible.
        kwp: kwpLignes,
        batterieKwh: batteryKwhFromLines(lines),
      })
    : null
  // L-2OPT — l'étude horaire de la branche AVEC porte SON PROPRE kWc. Le corps
  // ci-dessus décrit la branche SANS (`kwp`) ; l'interroger avec les batteries
  // de la composition AVEC produisait une chimère (kWc sans + batteries avec).
  // `null` tant que rien ne diverge ⇒ AUCUN second appel réseau et l'écran lit
  // le corps unique comme hier.
  const etudeHoraireCorpsAvec = (modeInstallation === 'residentiel'
      && kwpAvec !== kwpLignes)
    ? construireCorpsPreview({
        modeInstallation,
        editId,
        leadId,
        fHiver,
        fEte,
        eteDifferente: !!fEte && Number(fEte) > 0,
        ville: villeCalculLead,
        raccordement: selectedLead?.raccordement || '',
        kwp: kwpAvec,
        batterieKwh: batteryKwhFromLines(lines),
      })
    : null
  // QJR99 — `useSizingMoteur` (QJR90) enrobe `useEtudeHorairePreview` : il rend
  // les mêmes données réseau (aucun appel supplémentaire) PLUS une `decision`
  // déjà prise par sa moitié pure. La garde de réponse PÉRIMÉE y couvre les
  // DEUX branches : l'ancienne comparaison de clé en ligne ne valait que pour
  // `donnees`, si bien que la branche d'ÉCHEC refermait l'attente et épinglait
  // le refus d'une facture qu'on venait de remplacer (correctif intentionnel).
  const {
    decision: decisionMoteur,
    donnees: etudeHoraireDonnees,
    chargement: etudeHoraireChargement,
    erreur: etudeHoraireErreur,
  } = useSizingMoteur(etudeHoraireCorps, {
    attente: sizing.attenteMoteur,
    toucheNbPanneaux: toucheNbPanneauxPourComposition(sizing),
  })
  const { donnees: etudeHoraireDonneesAvec } =
    useEtudeHorairePreview(etudeHoraireCorpsAvec)
  // U3-900 (fondateur 29/08/2026, « ALL sizing goes through the new sizing
  // tool ») — LE SEUL remplaçant du repli `estimerPanneaux` (panneaux/900 MAD,
  // supprimé du backend le même jour, cf. apps/ventes/dimensionnement.py).
  // L'attente (`sizing.attenteMoteur`) est posée par applyLead /
  // applySiteProfile / syncBillEstimator quand le résidentiel ne se dimensionne
  // plus à l'écran : la recommandation du moteur horaire SERVEUR
  // (`etudeHoraireDonnees`, déjà interrogé dès que fHiver/lead est posé — AUCUN
  // appel réseau supplémentaire) la satisfait dès qu'elle répond. Un dry-run qui
  // décline (ville manquante, catalogue incomplet…) affiche son message
  // FRANÇAIS EXACT et ne préremplit RIEN — un vide honnête plutôt qu'une
  // supposition sur 900 DH (règle #4 CLAUDE.md). Une frappe manuelle gagne
  // toujours, comme partout ailleurs sur ce champ.
  //
  // QJR99 — la DÉCISION (appliquer / refuser / abandonner / attendre) est prise
  // par `useSizingMoteur` ; il ne reste ici que sa traduction en transition. La
  // garde de réponse périmée, les deux formes de motif (F4 :
  // `avertissements[0]` PUIS `dimensionnement.motivation`, rendues VERBATIM) et
  // la priorité de la frappe manuelle sont toutes dans la moitié pure, testée.
  const actionMoteur = decisionMoteur.action
  const recoMoteur = decisionMoteur.recommandation ?? null
  const motifMoteurServeur = decisionMoteur.motif ?? null
  useEffect(() => {
    // dispatch SYNCHRONE dans l'effet, idiome MAISON (ProductTour.jsx,
    // Avatar.jsx, FollowToggle.jsx…) : la valeur arrive d'un aller-retour
    // réseau DÉJÀ asynchrone (`useEtudeHorairePreview`), et la différer encore
    // d'une microtâche n'ajouterait qu'un tour de boucle entre la réponse et
    // l'affichage. Aucune de ces valeurs n'est relue dans le MÊME rendu.
     
    if (actionMoteur === 'appliquer') {
      dispatchSizing({ type: 'MOTEUR_A_REPONDU', recommandation: recoMoteur })
    } else if (actionMoteur === 'refuser') {
      dispatchSizing({ type: 'MOTEUR_A_REFUSE', motif: motifMoteurServeur })
    } else if (actionMoteur === 'abandonner') {
      // Une frappe manuelle a gagné : l'attente se referme sans rien appliquer.
      dispatchSizing({ type: 'MOTEUR_A_REPONDU' })
    }
  }, [actionMoteur, recoMoteur, motifMoteurServeur])
  // Le serveur GAGNE dès qu'il a répondu (etude non nul) : `roi` reste le
  // seul chiffre affiché tant que la réponse n'est pas là (ou a échoué).
  const etudeHoraireAnnuel = etudeHoraireDonnees?.etude?.annuel || null
  const etudeHoraireSourceServeur = !!etudeHoraireAnnuel
  // Réponse serveur à lire pour l'option AVEC. DIVERGENT : uniquement la
  // sienne — tant qu'elle n'est pas revenue, l'écran retombe sur le miroir
  // local `roiAvec` (au bon kWc) plutôt que de ré-afficher l'étude du kWc
  // SANS, ce qui recréerait exactement le croisement corrigé ici. NON
  // divergent : le corps unique, comme hier.
  const etudeHoraireDonneesPourAvec = etudeHoraireCorpsAvec
    ? etudeHoraireDonneesAvec
    : etudeHoraireDonnees
  const etudeHoraireAnnuelAvec =
    etudeHoraireDonneesPourAvec?.etude?.annuel || null
  const etudeHoraireLignes = useMemo(
    () => lignesAffichables(etudeHoraireDonnees?.dimensionnement),
    [etudeHoraireDonnees])
  // Lignes de dimensionnement à interroger pour le VERDICT batterie : celles
  // de l'étude de la branche AVEC (son kWc), jamais celles du kWc SANS.
  const etudeHoraireLignesAvec = useMemo(
    () => lignesAffichables(etudeHoraireDonneesPourAvec?.dimensionnement),
    [etudeHoraireDonneesPourAvec])
  const etudeHoraireSourceLabel = etudeHoraireDonnees?.consommation
    ? etiquetteSource(etudeHoraireDonnees.consommation.source)
    : null
  // L-FRONT lot 4 — falaise tarifaire (palier visé + meilleure combinaison du
  // balayage qui y passe), résumé annuel des impulsions équipements (glitch)
  // et décomposition mensuelle de la consommation estimée : les trois `null`
  // quand le moteur n'a rien calculé (mode non résidentiel, Z2, aucun
  // équipement concentrable) — jamais un bloc affiché sur un chiffre absent.
  const etudeHoraireFalaise = useMemo(
    () => falaiseAffichable(etudeHoraireDonnees?.dimensionnement),
    [etudeHoraireDonnees])
  const etudeHoraireGlitch = useMemo(
    () => glitchAnnuel(etudeHoraireDonnees?.etude),
    [etudeHoraireDonnees])
  const etudeHoraireEstimationConso = useMemo(
    () => estimationConsoAffichable(etudeHoraireDonnees?.estimation_conso),
    [etudeHoraireDonnees])
  const [ligneStockageOuverte, setLigneStockageOuverte] = useState(null)

  // CJ2b — chiffres AFFICHÉS dans le bloc « Aperçu de la Simulation »
  // (Production / Économies / ROI) : le serveur horaire gagne dès qu'il a
  // répondu, sinon repli SUR `roi` tel quel (miroir local inchangé — c'est
  // uniquement la SOURCE de ce qui est montré à l'écran qui bascule). Le
  // payback affiché en mode serveur est une simple division coût réel des
  // lignes / économie réelle serveur — jamais un chiffre inventé.
  const apercuProductionKwh = etudeHoraireSourceServeur
    ? etudeHoraireAnnuel.production_kwh : roi?.production_annuelle_kwh
  const apercuEcoSans = etudeHoraireSourceServeur
    ? etudeHoraireAnnuel.economie_sans_mad : roi?.eco_annuelle_sans
  // CJ2b — ORDRE FONDATEUR (« l'omission honnête, jamais un zéro inventé ») :
  // le moteur dit, POUR LA TAILLE CHIFFRÉE, si l'option batterie est
  // électriquement livrable. Quand elle ne l'est pas, les cartes « Avec
  // batterie » n'affichent AUCUN montant — elles affichent la raison. C'est le
  // trou catalogue RÉEL exhumé par CJ2a (panneau 710 Wc + hybride 5 kW
  // monophasé : Isc 18,6 A > 17,0 A) : sans cette garde, l'écran promettait au
  // vendeur l'économie d'une installation qu'on ne peut pas livrer.
  // `null` (le moteur ne dit rien sur cette taille) ⇒ comportement d'avant.
  // L-2OPT — verdict + économie « avec » lus sur l'étude de la branche AVEC,
  // à SON kWc (`kwpAvec`). Non divergent : mêmes lignes, même taille, même
  // résultat qu'hier.
  const verdictBatterieServeur = etudeHoraireAnnuelAvec
    ? verdictBatteriePourTaille(etudeHoraireLignesAvec, kwpAvec)
    : null
  const batterieInvendableServeur = verdictBatterieServeur
    ? !verdictBatterieServeur.vendable : false
  const apercuEcoAvec = etudeHoraireAnnuelAvec
    ? (batterieInvendableServeur ? null : etudeHoraireAnnuelAvec.economie_avec_mad)
    : roiPourAvec?.eco_annuelle_avec
  // ERR-QAH-FIG-PAYBACK-FORMULE-ECRAN — branche serveur : le payback du
  // MOTEUR (cashflow 25 ans QX39, `paybackMoteurHoraire`) sur l'économie
  // servie, jamais une division coût ÷ économie. Un cumul qui ne croise jamais
  // zéro s'affiche « Non rentabilisé sur 25 ans », jamais « 25 ans ».
  const paybackServeurSans = etudeHoraireSourceServeur
    ? paybackMoteurHoraire(totals.totalSans, apercuEcoSans, {
        annuel: etudeHoraireAnnuel,
        inverterReplaceCost: inverterCostFromLines(lines.filter(appartientAuPanierSans)),
      })
    : null
  const paybackServeurAvec = etudeHoraireAnnuelAvec
    ? paybackMoteurHoraire(totals.totalAvec, apercuEcoAvec, {
        annuel: etudeHoraireAnnuelAvec,
        rendementBatterie: etudeHoraireDonneesPourAvec?.etude?.rendement_batterie ?? null,
        stockage: batteryKwhFromLines(lines) > 0,
        inverterReplaceCost: inverterCostFromLines(lines.filter(appartientAuPanierAvec)),
      })
    : null
  const apercuPaybackSans = etudeHoraireSourceServeur
    ? (paybackServeurSans?.paybackYears ?? null)
    : roi?.payback_sans
  const apercuPaybackAvec = etudeHoraireAnnuelAvec
    ? (paybackServeurAvec?.paybackYears ?? null)
    : roiPourAvec?.payback_avec
  const apercuPaybackSansJamais = etudeHoraireSourceServeur
    ? !!paybackServeurSans?.jamaisRembourse : !!roi?.payback_sans_jamais
  const apercuPaybackAvecJamais = etudeHoraireAnnuelAvec
    ? !!paybackServeurAvec?.jamaisRembourse : !!roiPourAvec?.payback_avec_jamais

  // QJR35 — au montage (roi tourne dès dKwp>0 && dMonthly.some(v=>v>0), vrai
  // avec DEFAULT_MONTHLY_BILLS), les cartes Économies/ROI peuvent afficher un
  // chiffre dérivé du MIROIR LOCAL sans qu'aucune facture réelle ni étude
  // horaire serveur n'existe encore. Ni caché (le vendeur s'en sert comme
  // repère) ni remplacé par un autre chiffre — étiqueté. QJR89/QJR90 rendent
  // cette règle structurelle ; ceci est l'intérim minimal.
  const apercuEstimationExemple = !facturesSaisies && !etudeHoraireSourceServeur
  // QJR426 (DR5) — même discriminant que la puce ci-dessus, porté sur la
  // VALEUR SIGNÉE des quatre cartes Économies/ROI : `apercu()` (puce
  // `PUCE_APERCU`, strictement le même texte que le `badge` littéral
  // remplacé) quand aucune donnée réelle n'appuie le chiffre, `moteur()`
  // (aucune puce, comme aujourd'hui) dès qu'une facture réelle ou l'étude
  // horaire serveur est là — rendu byte-identique à l'ancien `badge=`.
  const signerEcoOuRoi = (v) => (apercuEstimationExemple ? apercu(v) : moteur(v))

  const chartData = useMemo(() => {
    if (!roi) return []
    // L-2OPT — la courbe « avec batterie » suit le kWc de SA branche quand les
    // deux optimiseurs divergent (`roiAvec`), sinon `roi` (identique).
    const detailAvec = (roiAvec || roi).monthly_detail
    return roi.monthly_detail.map((d, i) => ({
      month: CHART_MONTHS[i],
      facture: d.facture,
      ecoSans: Math.round(d.eco_sans),
      ecoAvec: Math.round((detailAvec[i] ?? d).eco_avec),
    }))
  }, [roi, roiAvec])

  // ── QJR641 — Marché → autoconsommation diurne par défaut (simulateur) ──
  const appliquerPartDiurneDuMarche = (mode) => {
    setDayUsage(partDiurneParDefaut(mode))
  }

  // ── Mode d'installation (Résidentiel / Industriel-Commercial / Agricole) ──
  // APX17 — la confirmation QX23 vit maintenant dans `onModeChangeUi` (le SEUL
  // chemin où l'utilisateur choisit lui-même un marché). `appliquerMarcheEcran`
  // reste SYNCHRONE : les trois appels programmatiques (préremplissage
  // lead/payload, rechargement d'un brouillon) doivent poser leur état dans le
  // même tour — le rendre asynchrone ferait écraser `scenario` chargé par le
  // défaut du mode.
  // QJR99 — la CASCADE de quatre branches (`if industriel … else résidentiel`)
  // qui reposait `setScenario` SANS CONDITION est SUPPRIMÉE : le défaut de
  // marché vit dans `DEFAUT_SCENARIO_PAR_MODE` (reducer) et ne s'applique plus
  // qu'à un scénario INTACT — correctif intentionnel, l'ancienne cascade jetait
  // en silence un choix explicite du commercial. Ne reste ici que le seul effet
  // que le reducer ne modélise pas : le type d'installation (autoconsommation
  // par défaut du simulateur).
  const appliquerMarcheEcran = (m, origine) => {
    if (m === modeInstallation) return
    dispatchSizing({ type: 'MARCHE_CHANGE', mode: m, origine })
    appliquerPartDiurneDuMarche(m)
  }
  // Chemins PROGRAMMATIQUES (pré-remplissage lead/payload, rechargement d'un
  // brouillon) : ils appellent `appliquerMarcheEcran(m, 'programme')`
  // directement — ils ne marquent JAMAIS le marché comme choisi par le
  // vendeur. (Passe Fable M5c : l'ancien alias `onModeChange` n'avait plus
  // aucun appelant — supprimé, eslint no-unused-vars est ERROR en CI.)
  // Pose le drapeau « le commercial a choisi son marché » sans rien changer
  // d'autre (ex-`modeTouched.current = true` du gestionnaire JSX) : le marché
  // visé EST le marché courant, donc seule la marque du drapeau subsiste — y
  // compris si la confirmation ci-dessous est refusée, comme avant.
  const marquerMarcheTouche = () =>
    dispatchSizing({ type: 'MARCHE_CHANGE', mode: modeInstallation, origine: 'utilisateur' })

  // QX23 — changer de marché après saisie écrase l'étude/ROI et les lignes
  // auto-remplies : on confirme AVANT (jamais de rejet silencieux de l'étude).
  // La confirmation n'apparaît que s'il y a réellement quelque chose à perdre.
  const onModeChangeUi = async (m) => {
    if (m === modeInstallation) return
    const hasWork = lines.some(l => l.produit && parseFloat(l.quantite) > 0)
      || !!etudeIndustrielle || pompageAutoFilled
    if (hasWork) {
      const ok = await confirm({
        title: 'Changer de marché ?',
        description: "L'étude et les lignes déjà remplies pour ce devis seront réinitialisées.",
        confirmLabel: 'Changer de marché',
      })
      if (!ok) return
    }
    appliquerMarcheEcran(m, 'utilisateur')
  }

  // ── Scénario / recommandation : réinitialisation si incompatible ──
  const onScenarioChange = (v) => {
    // « sauf si le commercial le précise » : dès qu'il choisit lui-même, aucun
    // pré-remplissage (lead, profil site) ne réécrit son scénario.
    dispatchSizing({ type: 'SAISI', champ: 'scenario', valeur: v })
    if ((v === 'Sans batterie' && recommendedChoice === 'Avec batterie') ||
        (v === 'Avec batterie' && recommendedChoice === 'Sans batterie')) {
      setRecommendedChoice('Auto')
    }
  }

  // ── Lead prioritaire : factures remplies + client résolu depuis le lead ──
  // (selectedLead est déclaré plus haut, avant le calcul ROI.)
  const resolvedClientLabel = useMemo(() => {
    if (!selectedLead) return null
    // B2B : si le client résolu porte un ICE, on l'affiche (devis professionnel).
    const linked = selectedLead.client_id
      ? clients.find(c => String(c.id) === String(selectedLead.client_id))
      : null
    const iceSuffix = (c) =>
      (c && c.ice) ? ` · ICE ${c.ice}` : ''
    if (selectedLead.client_nom) {
      return `${selectedLead.client_nom} (client existant lié)${iceSuffix(linked)}`
    }
    if (selectedLead.email) {
      const match = clients.find(c =>
        (c.email || '').toLowerCase() === selectedLead.email.toLowerCase())
      if (match) return `${match.nom} ${match.prenom || ''} (client existant — même email)`.trim() + iceSuffix(match)
    }
    return `${selectedLead.nom} ${selectedLead.prenom || ''} (sera créé automatiquement depuis le lead)`.trim()
  }, [selectedLead, clients])

  // ── PVMRQ — réglages « Gammes & marques » (Paramètres → Gammes & marques) ──
  // Chargés UNE fois, en CRÉATION comme en ÉDITION (une marque épinglée
  // s'applique à chaque auto-remplissage, pas seulement au premier chargement
  // d'un devis neuf). Best-effort : la LECTURE est ouverte à tout utilisateur
  // authentifié de la société (`IsAuthenticated` — l'épinglage doit s'appliquer
  // aux devis de TOUS les commerciaux ; seule l'ÉCRITURE reste
  // Admin/Responsable, cf. `views/parametres_gammes.py`). Un échec réseau
  // retombe silencieusement sur `{}` (aucune préférence, comportement
  // historique), jamais un blocage de l'écran. Déclaré AVANT
  // `computeAutoSizing` ci-dessous : `marquesActives` entre dans sa clé de
  // cache/dépendances, donc doit déjà être initialisé à ce point du rendu.
  const gammesLoaded = useRef(false)
  useEffect(() => {
    if (gammesLoaded.current) return
    gammesLoaded.current = true
    ventesApi.getParametresGammes()
      .then(({ data }) => setGammesConfig(data || {}))
      .catch(() => setGammesConfig({}))
  }, [])

  // Carte de marques ACTIVE pour ce devis : la gamme du devis rouvert
  // (`gammeNomDevis`, résolue contre les libellés `nom_essentielle`/
  // `nom_premium` du réglage — MIROIR du backend `services.marque_preferee`)
  // si elle correspond au libellé Premium, sinon le slot Essentielle par
  // défaut (comportement pour un devis neuf/sans gamme, ou tant que le
  // réglage n'est pas encore chargé). Les clés internes de `marques` sont
  // TOUJOURS les slots fixes 'Essentielle'/'Premium', jamais le libellé
  // renommé (voir ParametresGammes, apps/ventes/models.py).
  const marquesActives = useMemo(() => {
    const marques = gammesConfig?.marques
    if (!marques || typeof marques !== 'object') return {}
    const nomActuel = (gammeNomDevis || '').trim().toLowerCase()
    const nomPremium = (gammesConfig?.nom_premium || '').trim().toLowerCase()
    const slot = (nomActuel && nomActuel === nomPremium) ? 'Premium' : 'Essentielle'
    return marques[slot] || {}
  }, [gammesConfig, gammeNomDevis])

  // Règle fondateur du 18/08 — dimensionnement par PALIERS de 5 kWc au
  // payback le plus court, partagé par les trois pré-remplissages (lead,
  // profil site, saisie manuelle des factures). Retourne null quand la
  // facture d'hiver est sous le seuil de 900 MAD (aucun palier chiffrable —
  // les appelants attendent alors le moteur horaire SERVEUR, U3-900 :
  // attenteSizingServeur).
  // Mémoïsé via `sizingCacheRef` : `syncBillEstimator` tourne à chaque frappe
  // sur le champ facture, or chaque palier est chiffré avec le catalogue
  // réel (autoFillLines + ROI) — pas gratuit à rejouer si rien n'a changé.
  // `villeLead` : la ville du lead EN COURS d'application (`applyLead`) — à cet
  // instant `selectedLead` décrit encore le rendu précédent (leadId pas encore
  // posé) et le balayage partait au productible par défaut (CI #752).
  const computeAutoSizing = useCallback((hiverVal, eteVal, villeLead) => {
    const hiver = parseFloat(hiverVal) || 0
    const besoinKwc = estimerKwcDepuisFacture(hiver)
    if (besoinKwc <= 0) return null
    const eteVale = parseFloat(eteVal) || 0
    const eteEff = eteVale > 0 ? eteVale : hiver
    // QJR575 — distributeur DÉCLARÉ : celui que le vendeur a choisi, sinon
    // celui du lead, jamais le défaut d'écran 'onee' (sinon l'écran passait
    // au modèle « factures » quand le devis automatique restait en
    // « estimation » : deux kWc selon le bouton). Il entre dans la clé.
    const distributeurDeclare = distributeurChoisi ? distributeur : selectedLead?.distributeur
    const categorieBalayage = categorieCommerciale === CATEGORIE_NON_PRECISEE
      ? null : categorieCommerciale
    // ERR-QAH-DIFF-ROI-PRODUCTIBLE-DEFAUT — même productible que l'aperçu
    // (`roi`) et que le PDF : sans lui, `computeROI` retombait sur GHI × 0,8
    // (≈ 1 256 kWh/kWc contre ≈ 1 536 au document). Il entre dans la clé.
    const productibleBalayage = productibleForCity(
      (villeLead ?? villeCalculLead) || '', quoteLogic.productible)
    // PVMRQ — la marque épinglée entre dans la clé de cache : un changement de
    // réglage (ou de gamme du devis) doit rejouer le balayage des paliers.
    // STKCAT10 — le PRODUIT de structure entre dans la clé au même titre que
    // le bouton acier/alu : changer de structure change le prix de chaque
    // palier, donc le palier retenu.
    const key = [hiver, eteEff, besoinKwc, modeInstallation, categorieBalayage ?? '', panelW,
      structureType, structureProduitId ?? '',
      discountPct, produits.length, JSON.stringify(marquesActives),
      distributeurDeclare ?? '', consoAnnuelleReelle ?? '', productibleBalayage].join('|')
    if (sizingCacheRef.current.key === key) return sizingCacheRef.current.result
    // FINDING 25/08 — la CONSOMMATION RÉELLE du client entre dans le balayage.
    // Sans elle, `computeROI` ne plafonne rien : l'économie reste linéaire en
    // kWc, chaque pas marginal se « rembourse » et l'ascension ne s'arrête
    // qu'au plafond (mesuré : besoin 100 kWc → 100 kWc, 522 341 MAD). Dérivée
    // des factures du client par le barème du distributeur — jamais un chiffre
    // posé (`consoAnnuelleDepuisFactures`, la dérivation déjà utilisée par
    // autoQuote.js pour `etude_params.conso_annuelle`).
    // Une consommation RÉELLE saisie par le vendeur (champ facture/kWh réel,
    // QF4) prime sur la dérivation : c'est celle que l'aperçu `roi` utilise
    // déjà, et le dimensionnement doit dimensionner le MÊME client que
    // l'aperçu. Sinon, dérivation depuis les factures du balayage.
    // QJR575 — MÊME construction que le « Devis automatique ».
    const balayage = parametresBalayageCI({
      factures: estimerMois(hiver, eteEff), mode: modeInstallation,
      categorie: categorieBalayage, distributeurDeclare, consoAnnuelleReelle,
    })
    const opt = optimalKwcByPayback({
      produits, factures: balayage.factures, dayUsagePct: balayage.dayUsagePct,
      panelW, structureType, structureProduitId, discountPct,
      kwhPrice: quoteLogic.kwhPrice, efficiency: quoteLogic.efficiency,
      besoinKwc, marques: marquesActives,
      consoAnnuelleKwh: balayage.consoAnnuelleKwh, utility: balayage.utility,
      productible: productibleBalayage,
    })
    // QJR102 — LE SECOND BALAYAGE (celui de l'axe stockage, exposé jadis sous
    // la clé imbriquée du même nom) EST SUPPRIMÉ : il était RÉSIDENTIEL-ONLY
    // et le résidentiel ne passe plus jamais par ce balayage depuis U3-MOTEUR.
    // Preuve d'injoignabilité (greps joints au commit) : cette clé n'avait
    // qu'UN lecteur, la branche locale de `deuxValeursDim`, dans une fonction
    // qui rend `{sans:null, avec:null}` hors résidentiel — et EN résidentiel le
    // reducer met TOUJOURS `sizingInfo` à `null` (sizingReducer.js:253/278 pour
    // les pré-remplissages, :358 pour le recalcul). Les trois appelants
    // restants (`applyLead`, `applySiteProfile`, `syncBillEstimator`) sont tous
    // gardés par `!== 'residentiel'`. Le balayage ci-dessus, lui, reste le seul
    // dimensionneur des marchés sans moteur serveur.
    // `optimalKwcByPayback` GARDE son paramètre d'axe stockage (décision
    // fondateur D11 : il reste le moteur de 3 marchés sur 4, et
    // solar.deuxOptimiseurs.test.mjs le couvre en propre).
    let result = null
    if (opt.nbPanneaux > 0) result = { besoinKwc, ...opt }
    sizingCacheRef.current = { key, result }
    return result
  }, [modeInstallation, panelW, structureType, structureProduitId, discountPct,
    produits, quoteLogic, marquesActives, distributeur, distributeurChoisi,
    categorieCommerciale, consoAnnuelleReelle, villeCalculLead, selectedLead?.distributeur])

  // L-2OPT — kWc de la branche AVEC batterie POUR LA COMPOSITION EN COURS :
  // le moteur horaire serveur (recommandation_avec, source de vérité) prime
  // dès qu'il a répondu pour ce contexte ; repli local (même balayage
  // payback que ci-dessus, objectif avecBatterie) ; repli ultime kwc_sans —
  // jamais un chiffre inventé (règle #4). Un nombre de panneaux TAPÉ À LA
  // MAIN (nbPanneauxTouched, même garde-fou que partout ailleurs sur ce
  // champ) vaut pour les DEUX branches : aucune divergence n'est recomposée
  // par-dessus un choix déjà fait par l'utilisateur.
  const resolveKwcAvec = () => {
    if (toucheNbPanneauxPourComposition(sizing)) return kwp
    const backendAvec = etudeHoraireDonnees?.dimensionnement?.recommandation_avec
    if (Number(backendAvec?.kwc) > 0) return Number(backendAvec.kwc)
    // U3-MOTEUR (fondateur 29/08/2026) — le repli local (balayage par paliers
    // `computeAutoSizing`, objectif avecBatterie) est RETIRÉ : ce kWc part au
    // serveur en `body.kwc` pour composer la seconde option, c'est donc un
    // DIMENSIONNEMENT, et le seul dimensionneur est désormais le moteur
    // horaire. Tant qu'il n'a pas chiffré de `recommandation_avec`, l'option
    // AVEC se compose à la taille SANS (`kwp`) — aucune divergence fabriquée
    // par une seconde méthode de calcul (règle chiffres-vérifiés).
    return kwp
  }

  // FOUNDER 26/08 — les DEUX valeurs de dimensionnement pour l'AFFICHAGE
  // (« Recommandé sans batterie : N panneaux · X kWc » / « … avec … »),
  // INDÉPENDANTES du scénario choisi. Résidentiel UNIQUEMENT : l'agricole n'a
  // aucune notion de facture → kWc (dimensionnement pompage, HMT/débit) et
  // l'industriel/commercial ne vendent jamais l'option batterie
  // (`composeLocalement` force ces quantités à 0 quel que soit le scénario) —
  // y afficher une valeur « avec » serait un chiffre fabriqué. `null` = rien de
  // calculable pour l'instant (jamais un défaut inventé, règle #4).
  //
  // F3 (revue adversariale 26/08) — sans/avec ne se repliaient PAS ensemble :
  // un côté pouvait venir du serveur (moteur horaire PVGIS) pendant que
  // l'autre retombait sur le balayage local — deux méthodes de calcul
  // DIFFÉRENTES dont l'ÉCART affiché n'était alors plus comparable. La règle
  // (la paire n'existe qu'à SOURCE UNIQUE) vit maintenant dans
  // `paireDimensionnement` (QJR99, haut de ce fichier), où elle est EXPRIMÉE
  // par les valeurs signées (QJR86) au lieu d'être une cascade de `if`.
  //
  // QJR102 — LA BRANCHE LOCALE EST SUPPRIMÉE. Elle était structurellement
  // injoignable : cette fonction rend `{sans:null, avec:null}` hors
  // résidentiel, et EN résidentiel `sizingInfo` vaut TOUJOURS `null` depuis
  // U3-MOTEUR (le reducer l'y met à `null` sur les trois pré-remplissages —
  // sizingReducer.js:253/278 — et sur le recalcul — :358). Elle masquait le
  // bug de SOURCE MIXTE que F3 interdit (l'ancien `asSans()` préférait le
  // serveur jusque dans la branche « paire locale »). Le dimensionnement
  // affiché ici ne peut donc plus venir que du MOTEUR — une seule source, un
  // écart toujours comparable.
  // QJR108 — le sélecteur ENTIER (garde de marché comprise) vit dans le module
  // pur `features/ventes/quote/paireDimensionnement.js` : il est désormais
  // exécuté par les tests, plus seulement décrit par une regex.
  const deuxValeursDim = selecteurDeuxValeursDim(
    modeInstallation, etudeHoraireDonnees)

  const applyLead = (id) => {
    setLeadId(id)
    if (!id) return
    setClientId('') // le client est résolu côté serveur depuis le lead
    const lead = leads.find(l => String(l.id) === String(id))
    if (!lead) return
    // QJR99 — les SEPT écritures gardées (mode, scénario, structure, tension,
    // alimentation pompe, taille souhaitée, dimensionnement par facture) sont
    // devenues UNE transition `LEAD_APPLIQUE`. Chaque garde-fou « intact » y
    // est écrit une fois, testé, et le bug QJR38 (« brancher sur le mode du
    // rendu PRÉCÉDENT ») ne peut plus revenir : le mode visé EST dans l'état
    // que la transition produit.
    //
    // Ce qui reste ICI est tout ce que le reducer ne modélise PAS : le type
    // d'installation (autoconsommation par défaut), les champs pompe, la
    // consommation, les factures affichées, et la RÉSOLUTION du balayage local
    // — un reducer pur ne va jamais chercher un chiffre au catalogue.
    const modeLead = !sizing.touche.mode && lead.type_installation
      ? LEAD_TYPE_TO_MODE[lead.type_installation] : null
    // Mode RÉELLEMENT visé par ce pré-remplissage (miroir EXACT du calcul que
    // fait le reducer) : il décide du type d'installation et du dimensionneur.
    const modeCible = modeLead || modeInstallation
    if (modeLead && modeLead !== modeInstallation) {
      appliquerPartDiurneDuMarche(modeLead)
    }
    // Lead agricole : recopie pompe CV / HMT / débit (l'alimentation, elle,
    // suit le raccordement DANS la transition ci-dessous).
    if (LEAD_TYPE_TO_MODE[lead.type_installation] === 'agricole') {
      if (lead.pompe_cv != null && lead.pompe_cv !== '') setPompeCv(String(lead.pompe_cv))
      if (lead.pompe_hmt_m != null && lead.pompe_hmt_m !== '') setPompeHmt(String(lead.pompe_hmt_m))
      if (lead.pompe_debit_m3h != null && lead.pompe_debit_m3h !== '') setPompeDebit(String(lead.pompe_debit_m3h))
    }
    if (lead.conso_mensuelle_kwh) setConsoMensuelle(String(lead.conso_mensuelle_kwh))
    const hiver = parseFloat(lead.facture_hiver) || 0
    // bascule OFF → la valeur unique vaut hiver ET été
    const ete = (lead.ete_differente && lead.facture_ete)
      ? parseFloat(lead.facture_ete) : hiver
    // La taille souhaitée du lead est PRIORITAIRE sur la facture : on ne
    // chiffre le balayage local que si elle ne fournit rien (même garde que le
    // reducer, pour ne pas payer `optimalKwcByPayback` pour rien). Résidentiel :
    // AUCUN balayage local — U3-MOTEUR, le moteur horaire serveur dimensionne.
    const tailleKwc = parseFloat(lead.taille_souhaitee_kwc) || 0
    const fromTaille = (!sizing.touche.nbPanneaux && tailleKwc > 0)
      ? panneauxPourKwc(tailleKwc, panelW)
      : 0
    const sizingLocal = (hiver > 0 && fromTaille <= 0 && modeCible !== 'residentiel')
      ? computeAutoSizing(hiver, ete, villeEffectiveLead(lead)) : null
    // STKCAT10 — la liste des structures RÉELLEMENT sélectionnables voyage
    // avec l'action : le reducer valide contre ELLE l'id épinglé sur le lead
    // (`lead.structure_produit`, STKCAT9) et n'applique jamais un produit
    // archivé, dépricé, détypé ou d'une autre société. Un module pur ne va
    // chercher aucun catalogue lui-même — c'est l'appelant qui l'apporte.
    dispatchSizing({
      type: 'LEAD_APPLIQUE',
      lead,
      sizingLocal,
      structuresEligibles: structuresCatalogue.map((p) => p.id),
    })
    // OFFGRID — défaut dérivé du raccordement du lead : « aucun » (site
    // isolé) bascule le devis en hors réseau tant que le vendeur n'a pas
    // choisi lui-même (même garde « touché » que pompeAlim/structure/tension
    // ci-dessus dans le reducer — ici en état simple, voir sa déclaration).
    if (!horsReseauTouched) setHorsReseau(lead.raccordement === 'aucun')
    if (hiver > 0) {
      setFHiver(String(lead.facture_hiver))
      setFEte(lead.ete_differente && lead.facture_ete ? String(lead.facture_ete) : '')
      setMonthly(estimerMois(hiver, ete))
    }
  }

  // ── WIR99/DC12 — Pré-remplissage d'un devis SANS LEAD depuis le profil
  // site/énergie réutilisable du client (`crm.SiteProfile`, résolu côté
  // serveur par `/ventes/devis/prefill-site/`). Miroir EXACT d'`applyLead` :
  // mêmes champs, mêmes garde-fous « touched » — un champ que l'utilisateur a
  // déjà réglé n'est JAMAIS écrasé. Aucun profil (ou aucun client) → no-op
  // strict : le comportement historique est inchangé.
  const applySiteProfile = (p) => {
    if (!p) return
    // QJR99 — miroir d'`applyLead` : une SEULE transition
    // (`PROFIL_SITE_APPLIQUE`) porte le mode, l'alimentation pompe et le
    // dimensionnement par facture. QJR38 — le mode RÉELLEMENT visé est calculé
    // ici comme dans le reducer (et non lu sur le rendu précédent) : c'est ce
    // bug-là qui faisait armer au résidentiel une attente que le moteur
    // résidentiel-only ne satisferait jamais pour un profil industriel.
    const modeLead = !sizing.touche.mode
        && p.type_installation && LEAD_TYPE_TO_MODE[p.type_installation]
      ? LEAD_TYPE_TO_MODE[p.type_installation] : null
    const modeCible = modeLead || modeInstallation
    if (modeLead && modeLead !== modeInstallation) {
      appliquerPartDiurneDuMarche(modeLead)
    }
    if (LEAD_TYPE_TO_MODE[p.type_installation] === 'agricole') {
      if (p.pompe_cv != null && p.pompe_cv !== '') setPompeCv(String(p.pompe_cv))
      if (p.pompe_hmt_m != null && p.pompe_hmt_m !== '') setPompeHmt(String(p.pompe_hmt_m))
      if (p.pompe_debit_m3h != null && p.pompe_debit_m3h !== '') setPompeDebit(String(p.pompe_debit_m3h))
    }
    if (p.conso_mensuelle_kwh) setConsoMensuelle(String(p.conso_mensuelle_kwh))
    const hiver = parseFloat(p.facture_hiver) || 0
    const ete = (p.ete_differente && p.facture_ete) ? parseFloat(p.facture_ete) : hiver
    // Règle fondateur du 18/08 — même chaîne palier/payback que applyLead (voir
    // computeAutoSizing) ; le résidentiel, lui, attend le moteur horaire
    // SERVEUR (U3-900 — plus de repli `estimerPanneaux`).
    const sizingLocal = (hiver > 0 && !sizing.touche.nbPanneaux && modeCible !== 'residentiel')
      ? computeAutoSizing(hiver, ete) : null
    dispatchSizing({ type: 'PROFIL_SITE_APPLIQUE', profil: p, sizingLocal })
    if (hiver > 0) {
      setFHiver(String(p.facture_hiver))
      setFEte(p.ete_differente && p.facture_ete ? String(p.facture_ete) : '')
      setMonthly(estimerMois(hiver, ete))
    }
  }

  // Sélection d'un client (chemin SANS lead) : pose l'id puis va chercher son
  // profil site. Best-effort — une absence de profil ou une erreur réseau ne
  // doit jamais empêcher de sélectionner le client.
  const applyClient = (v) => {
    const id = v ? String(v) : ''
    setClientId(id)
    if (!id || leadId) return
    ventesApi.getPrefillSite(id)
      .then((res) => applySiteProfile(res?.data?.profil))
      .catch(() => {})
  }

  // Client pré-sélectionné par ?client=<id> : même pré-remplissage, une seule
  // fois au montage (jamais rejoué ensuite).
  const sitePrefillDone = useRef(false)
  useEffect(() => {
    if (sitePrefillDone.current || !clientId || leadId) return
    sitePrefillDone.current = true
    ventesApi.getPrefillSite(clientId)
      .then((res) => applySiteProfile(res?.data?.profil))
      .catch(() => {})
    // Pré-remplissage au montage uniquement (garde `sitePrefillDone`) ;
    // rejouer à chaque changement d'état écraserait la saisie en cours.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- montage seul
  }, [clientId, leadId])

  // ── Devis automatique (bouton « ⚡ Devis auto » du lead) ──
  // Sensible au marché du lead : résidentiel (comportement historique),
  // agricole (pompage, mêmes appels que le flux manuel) ou industriel
  // (dimensionnement factures + étude d'autoconsommation comme en manuel).
  // On lit le lead DIRECTEMENT (l'état posé par applyLead est asynchrone).
  const runAutoQuote = async (lead, discountStr) => {
    setSaving(true)
    // QJR602 suivi (D-QJR5-13) — une taille explicite est respectée telle
    // quelle : plus d'arrondi au palier de 5 kWc, donc plus d'avis de palier.
    try {
      // Calcul partagé avec le panneau devis inline (autoQuote.js) — jamais
      // dupliqué : un seul endroit dimensionne le devis auto. On transmet les
      // heures de pompage du réglage entreprise (pompeHeures) et un rappel qui
      // affiche les chiffres d'étude industrielle avant la fin.
      const devisId = await createAutoQuote({
        lead, produits, discountStr, dispatch, quoteLogic,
        pumpHours: parseFloat(pompeHeures) || HEURES_POMPAGE_DEFAUT,
        onEtude: (et) => setWarnings(prev => ({
          ...prev,
          autoEtude: `Étude auto : autoconsommation ${et.taux_autoconso} %`
            + ` · économies ${fmtNum(et.economies_annuelles)} MAD/an`
            + (et.payback != null ? ` · retour ${et.payback} ans` : ''),
        })),
        // PVMRQ — marques préférées (gamme active) : même contrainte que
        // l'auto-remplissage manuel (handleAutoFill).
        marques: marquesActives,
        // PVORD — ordre par défaut de la société, même contrainte que
        // l'auto-remplissage manuel (handleAutoFill) ci-dessous.
        ordreLignes: gammesConfig?.ordre_lignes,
      })
      finish(devisId)
    } catch (err) {
      const msg = typeof err?.detail === 'string'
        ? err.detail
        : 'Le devis automatique a échoué — vérifiez le lead et réessayez.'
      setErrors(prev => ({ ...prev, submit: msg }))
      setSaving(false)
    }
  }

  // ── Édition d'un brouillon (?edit=ID) : préremplissage complet ──
  useEffect(() => {
    if (!editId || editLoaded.current === rechargeEdit) return
    editLoaded.current = rechargeEdit
    ventesApi.getDevisById(editId).then(({ data: d }) => {
      // QJR532 (D-QJR5-1) — le refus vient du SERVEUR (`modifiable`, QJR516),
      // plus d'une garde « statut !== brouillon » : un envoyé se corrige sur
      // place ; un accepté / remplacé dit pourquoi (raison_non_modifiable).
      if (!peutEditerDevis(d)) {
        // APX17 — plus de popup du système : un toast d'erreur français,
        // dans le seul Toaster de l'app.
        toast.error(d.raison_non_modifiable
          || 'Ce devis ne peut plus être modifié — révisez-le pour créer une nouvelle version.')
        cancel()
        return
      }
      // QJR581 — la RÉFÉRENCE « rien n'a changé » se capture sur l'état que
      // ce mappeur (et ses relectures immédiates : lead, réouverture) pose.
      captureReferenceJusqua.current = Date.now() + FENETRE_REFERENCE_MS
      // QJR549 — le jeton de fraîcheur du devis CHARGÉ (et rechargé).
      jetonRef.current = d.updated_at ?? null
      setEditDevis({ id: d.id, reference: d.reference,
                     statut: d.statut, date_envoi: d.date_envoi ?? null,
                     // QJR548 — verdict SERVI (QJR516), relu par les gestes
                     // de l'écran qui disent AVANT le clic s'ils sont permis.
                     modifiable: d.modifiable,
                     raison_non_modifiable: d.raison_non_modifiable || '',
                     // QJR580 — le lead / client DU DEVIS, lus par leurs noms
                     // servis (jamais `leads.find` : lead hors page 1).
                     lead_nom: d.lead_nom || '', client_nom: d.client_nom || '',
                     // QJR581 — version du devis : un brouillon local d'une
                     // AUTRE version n'est jamais proposé.
                     updated_at: d.updated_at ?? null,
                     // QJR540 — relations et état du calepinage, déjà servis
                     // par DevisSerializer : lus tels quels (zéro appel réseau).
                     factures_liees: d.factures_liees ?? [],
                     bon_commande_etat: d.bon_commande_etat ?? null,
                     chantier: d.chantier ?? null,
                     layout_stale: d.layout_stale ?? null,
                     layout_nb_panneaux: d.layout_nb_panneaux ?? null,
                     lineIds: (d.lignes ?? []).map(l => l.id) })
      // QJR658 — LE MAPPEUR EST UN MODULE PUR (`quote/etatDevis.js`,
      // aller-retour exécuté par `etatDevis.test.mjs`) : il lit le devis
      // servi et rend l'état d'écran ; ici on ne fait que le POSER.
      const etat = devisVersEtat(d)
      const pose = (valeur, setter) => { if (valeur !== undefined) setter(valeur) }
      // Défaut de part diurne du marché (QJR641), avant la valeur persistée.
      if (etat.mode && etat.mode !== modeInstallation) appliquerPartDiurneDuMarche(etat.mode)
      if (d.lead) {
        setLeadId(etat.leadId)
        // ERR-QAH-VENTES-EDITION-PERD-LEAD — relit le lead par son id et repose
        // ses factures hiver/été SANS redimensionner ; une valeur déjà présente
        // n'est jamais écrasée ; une panne reste ISOLÉE.
        Promise.resolve().then(() => crmApi.getLead(d.lead)).then(({ data: lead }) => {
          if (!lead || lead.id == null) return
          // QJR581 — hydratation serveur tardive : re-capture de la référence.
          captureReferenceJusqua.current = Date.now() + FENETRE_REFERENCE_MS
          setLeadDuDevis(lead)
          if (parseFloat(lead.facture_hiver) > 0) {
            setFHiver(prev => prev || String(lead.facture_hiver))
            setFEte(prev => prev || (lead.ete_differente && lead.facture_ete
              ? String(lead.facture_ete) : ''))
          }
        }).catch(() => {})
      } else pose(etat.clientId, setClientId)
      // DC11 / QJR106 — verdict de dérive du serveur (liste vide = aucune bannière).
      setLeadValeursModifiees(etat.leadValeursModifiees)
      setDiscountPct(etat.discountPct)
      setTauxTva(etat.tauxTva)
      pose(etat.dateValidite, setDateValidite)
      pose(etat.note, setNote)
      // QJR624 — l'échéancier DU DEVIS.
      echeancierAEnvoyer.current = etat.echeancierAEnvoyer
      setEcheancierSaisieBrut(etat.echeancier)
      setPrixCible(etat.prixCible)
      setLines(withKeys(etat.lignes))
      linesInitialized.current = true
      // QJR99 / QJR526 — la RÉOUVERTURE est UNE transition du reducer : mode,
      // compte de panneaux (branche SANS), scénario, wattage et structure.
      dispatchSizing({
        type: 'REOUVERTURE',
        devis: {
          mode_installation: etat.mode,
          panneaux: etat.panneaux,
          scenario: etat.scenario,
          panel_watt: etat.reouverture.panelW,
          structure: etat.reouverture.structure,
          structureProduitId: etat.reouverture.structureProduitId,
        },
      })
      setHorsReseau(etat.reouverture.horsReseau)
      setHorsReseauTouched(true)
      setAccessoiresOnly(etat.reouverture.accessoiresOnly)
      pose(etat.gammeNom, setGammeNomDevis)
      pose(etat.recommendedChoice, setRecommendedChoice)
      pose(etat.multiMode, setMultiMode)
      pose(etat.nombreProprietes, setNombreProprietes)
      pose(etat.villaGroups, setVillaGroups)
      pose(etat.injectionEnabled, setInjectionEnabled)
      if (etat.tension === 'mt') dispatchSizing({ type: 'SAISI', champ: 'tension', valeur: 'mt' })
      pose(etat.partDiurne, setDayUsage)
      pose(etat.repartitionMt, setRepartitionMt)
      pose(etat.categorieCommerciale, setCategorieCommerciale)
      pose(etat.commercialAnswers, setCommercialAnswers)
      pose(etat.pompe.cv, setPompeCv)
      pose(etat.pompe.hmt, setPompeHmt)
      pose(etat.pompe.debit, setPompeDebit)
      if (etat.pompageSaisie) setPompageSaisie(etat.pompageSaisie)
      pose(etat.consoMensuelle, setConsoMensuelle)
      pose(etat.distributeur, setDistributeur)
      pose(etat.distributeurChoisi, setDistributeurChoisi)
      pose(etat.monthly, setMonthly)
      consoStockee.current = etat.consoStockee
      pose(etat.realBillMode, setRealBillMode)
      pose(etat.realBillKwh, setRealBillKwh)
      pose(etat.farm.region, setFarmRegion)
      pose(etat.farm.crop, setFarmCrop)
      pose(etat.farm.surfaceHa, setFarmSurfaceHa)
      pose(etat.farm.irrigation, setFarmIrrigation)
      // AGR212 — l'économie déclarée se relit telle qu'enregistrée.
      setEcoPompage(etat.saisiesEco || ecoDepuisSaisies(null))
      // AGR218 — l'attestation d'usage agricole se relit telle que saisie.
      setAttestationAgricole(etat.farm.attestation || ATTESTATION_VIDE)
      pose(etat.farm.hmtStatic, setFarmHmtStatic)
      pose(etat.farm.hmtDrawdown, setFarmHmtDrawdown)
      pose(etat.pompe.profondeur, setPompeProfondeur)
      // QJR66 — `alim` restaurée est un choix humain (drapeau « touché »).
      pose(etat.pompe.type, setPompeType)
      if (etat.pompe.alim) dispatchSizing({ type: 'SAISI', champ: 'pompeAlim', valeur: etat.pompe.alim })
      pose(etat.pompe.distance, setPompeDistance)
    }).catch(() => {
      setErrors(prev => ({
        ...prev,
        submit: 'Impossible de charger ce devis — il a peut-être été supprimé.',
      }))
    })
  }, [editId, rechargeEdit]) // eslint-disable-line react-hooks/exhaustive-deps

  // QJR548 — une taille d'offre appliquée RECOMPOSE le devis côté serveur
  // (lignes, totaux, études) : l'écran relit ce devis par LE chargeur
  // `?edit=` ci-dessus et efface son brouillon local — sinon le prochain
  // « Enregistrer » renverrait les anciennes lignes et annulerait la taille
  // appliquée en silence. La confirmation est posée par DevisOffresTailles.
  const rechargerDevisRecompose = () => {
    clear()
    setRechargeEdit(n => n + 1)
  }

  // ── Réglages entreprise (Paramètres) → valeurs par défaut du générateur ──
  // FEATURE 10 : en CRÉATION uniquement, la date de validité par défaut suit
  // « validité du devis » (jours) et les heures de pompage suivent « heures de
  // pompage/jour ». Les champs restent librement éditables (rien n'est imposé).
  // QJR527 — en édition (?edit=ID), le devis prime sur la date de validité,
  // les heures de pompage et le prix cible (relu par le mappeur) ; mais la
  // LOGIQUE société (tarif kWh, rendement, TVA, productible, remise max) est
  // chargée dans les DEUX modes — sinon l'étude I/C était re-persistée au
  // tarif par défaut du code et imprimée.
  const settingsLoaded = useRef(false)
  useEffect(() => {
    if (settingsLoaded.current) return
    settingsLoaded.current = true
    parametresApi.getProfile().then(({ data }) => {
      const jours = parseInt(data?.quote_validity_days, 10)
      if (!editId && Number.isFinite(jours) && jours > 0) {
        const d = new Date()
        d.setDate(d.getDate() + jours)
        const iso = `${d.getFullYear()}-${String(d.getMonth() + 1)
          .padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
        setDateValidite(prev => prev || iso)
      }
      // AGR208/AGR212 — repères énergie datés et sourcés (simple indication à
      // côté du champ prix, jamais recopiés dedans).
      setReperesEnergie(data?.reperes_energie_agricole || {})
      setTermesEffectifs(data?.payment_terms_effectifs || null)
      const heures = parseFloat(data?.agricole_pump_hours)
      if (!editId && Number.isFinite(heures) && heures > 0) {
        setPompeHeures(String(heures))
      }
      // Logique de devis éditable (D5) — repli sur les constantes du simulateur.
      const kwh = parseFloat(data?.onee_tarif_kwh)
      const rend = parseFloat(data?.rendement_global)
      const tvaStd = parseFloat(data?.tva_standard)
      const tvaPan = parseFloat(data?.tva_panneaux)
      // QJR39 — CompanyProfile.productible_kwh_kwc (QX38, exposé tel quel par
      // CompanyProfileSerializer, fields='__all__') : ce setQuoteLogic
      // RECONSTRUIT l'objet entier (repli des 4 champs ci-dessus, historique),
      // ce qui EFFAÇAIT silencieusement le `productible: null` de l'état
      // initial et rendait le réglage société mort à l'écran — le générateur
      // et le PDF citaient alors deux productibles différents pour le même
      // devis. Repli EXPLICITE sur `null` (jamais une constante d'écran) :
      // `productibleForCity` (solar.js) sait déjà retomber sur le PVGIS par
      // ville quand aucune surcharge société réelle n'existe.
      const prod = parseFloat(data?.productible_kwh_kwc)
      setQuoteLogic({
        kwhPrice: (Number.isFinite(kwh) && kwh > 0) ? kwh : KWH_PRICE,
        efficiency: (Number.isFinite(rend) && rend > 0) ? rend : EFFICIENCY,
        tvaStandard: (Number.isFinite(tvaStd) && tvaStd > 0) ? tvaStd : TVA_STANDARD_DEFAUT,
        tvaPanneaux: (Number.isFinite(tvaPan) && tvaPan > 0) ? tvaPan : TVA_PANNEAUX_DEFAUT,
        productible: (Number.isFinite(prod) && prod > 0) ? prod : null,
      })
      const cible = parseFloat(data?.prix_cible_kwc_defaut)
      if (!editId && Number.isFinite(cible) && cible > 0) setPrixCible(prev => prev || String(cible))
      const rmax = parseFloat(data?.remise_max_pct)
      if (Number.isFinite(rmax) && rmax > 0) setRemiseMax(String(rmax))
    }).catch(() => { /* réglages indisponibles → on garde les défauts code */ })
  }, [editId])

  // Arrivée depuis le lead. Pleine page : via l'URL (?lead=…&auto=1&discount=…).
  // Embarqué : via les props (leadId/auto/discount), jamais l'URL.
  useEffect(() => {
    const leadParam = embedded
      ? (leadIdProp != null ? String(leadIdProp) : '')
      : searchParams.get('lead')
    // QJR525 — en ÉDITION (Édition complète embarquée depuis la fiche lead),
    // le devis rouvert prime : le mappeur `?edit=` pose déjà le lead, et
    // `applyLead` réécrirait les 12 factures réelles stockées par une
    // estimation hiver/été sans aucun geste du vendeur.
    if (!leadParam || autoRan.current || editId) return
    if (!leads.length || !produits.length) return
    autoRan.current = true
    const lead = leads.find(l => String(l.id) === leadParam)
    if (!lead) return
    // Initialisation unique (garde autoRan) — pas de cascade.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    applyLead(leadParam)
    const wantAuto = embedded ? autoProp : (searchParams.get('auto') === '1')
    const discount = embedded ? (discountProp || '0') : (searchParams.get('discount') || '0')
    if (wantAuto) {
      runAutoQuote(lead, discount)
      if (discount) setDiscountPct(discount)
    }
  }, [leads, produits]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Factures : estimation hiver/été + suggestion panneaux ──
  // Règle fondateur du 18/08 — même chaîne palier/payback que applyLead/
  // applySiteProfile (computeAutoSizing, mémoïsée — cette fonction tourne à
  // chaque frappe sur le champ facture) ; sous le seuil, attend le moteur
  // horaire SERVEUR (U3-900 — plus de repli `estimerPanneaux`).
  const syncBillEstimator = (hiverVal, eteVal) => {
    const hiver = parseFloat(hiverVal) || 0
    const ete = parseFloat(eteVal) || 0
    if (hiver <= 0) return
    // N3 — un nombre de panneaux TAPÉ À LA MAIN (`touche.nbPanneaux`, le MÊME
    // garde-fou « intact » qu'applyLead/applySiteProfile ci-dessus) n'est plus
    // jamais re-forcé par le redimensionnement automatique déclenché par la
    // frappe sur les factures : il ne se resynchronise qu'via une recomposition
    // EXPLICITE (« Auto-remplir », ou en retouchant nbPanneaux/kwcCible
    // eux-mêmes). Les factures (monthly), elles, restent toujours à jour.
    //
    // QJR99 — un montant de facture tapé à l'écran est un PRÉ-REMPLISSAGE de
    // profil énergétique comme un autre : il emprunte la MÊME transition que
    // le profil site (`PROFIL_SITE_APPLIQUE`), qui porte déjà le garde-fou N3,
    // le choix résidentiel-attend-le-moteur / autres-marchés-balayage-local, et
    // l'effacement du justificatif. Une seule règle, trois appelants — plus
    // trois copies à garder d'accord. U3-MOTEUR : en résidentiel, chaque frappe
    // relance le dry-run serveur (le corps d'aperçu porte `fHiver`/`fEte`) et
    // c'est SA recommandation qui remplit le nombre de panneaux ; aucun palier
    // chiffré à l'écran ne s'y substitue, donc aucun balayage local à résoudre.
    if (!sizing.touche.nbPanneaux) {
      const sizingLocal = modeInstallation === 'residentiel'
        ? null : computeAutoSizing(hiver, ete)
      dispatchSizing({
        type: 'PROFIL_SITE_APPLIQUE',
        profil: { type_installation: modeInstallation, facture_hiver: hiver },
        sizingLocal,
      })
    }
    setMonthly(estimerMois(hiver, ete > 0 ? ete : hiver))
  }

  // VX237 — montant collé d'Excel/facture ("12 500,00", "3 200 DH"...) nettoyé
  // vers une chaîne numérique simple au lieu de tomber brut dans le champ
  // number (qui rejetterait silencieusement le format non reconnu). Déclarés
  // ici (après syncBillEstimator) pour respecter react-hooks/immutability.
  const onHiverPaste = usePasteClean(parsePastedAmount,
    (clean) => { setFHiver(clean); syncBillEstimator(clean, fEte) })
  const onEtePaste = usePasteClean(parsePastedAmount,
    (clean) => { setFEte(clean); syncBillEstimator(fHiver, clean) })
  // COUV-HOR — les gestes du VENDEUR sur la carte factures (frappe, collage,
  // choix du distributeur) ; `?edit=` et le brouillon passent par les setters
  // bruts et ne comptent donc jamais comme une saisie.
  const saisirRealBillMad = (v) => { setRealBillMad(v); setRealBillSaisi(true) }
  const saisirRealBillKwh = (v) => { setRealBillKwh(v); setRealBillSaisi(true) }
  const choisirDistributeur = (v) => { setDistributeur(v); setDistributeurChoisi(true) }
  const onRealBillPaste = usePasteClean(parsePastedAmount,
    (clean) => (realBillMode === 'mad' ? saisirRealBillMad(clean) : saisirRealBillKwh(clean)))

  const handleEstimerMois = () => {
    const hiver = parseFloat(fHiver) || 0
    const ete = parseFloat(fEte) || 0
    if (hiver <= 0 && ete <= 0) {
      setErrors(e => ({ ...e, bills: 'Entrez au moins une facture (hiver ou été)' }))
      return
    }
    setErrors(e => ({ ...e, bills: null }))
    setMonthly(estimerMois(hiver, ete))
  }

  const setMonth = (i, v) =>
    setMonthly(m => m.map((old, idx) => (idx === i ? v : old)))

  // ── Lignes ──
  // VX188 — callback stabilisé (identité stable via useCallback, clé de ligne
  // en ARGUMENT) pour que `React.memo(DevisLineRow)` saute le re-rendu d'une
  // ligne inchangée. VX93 — mémorise le dernier taux TVA saisi à la main pour
  // pré-remplir la prochaine ligne ajoutée (ecrireLastTva est un writer stable).
  const setLine = useCallback((key, k, v) => {
    if (k === 'taux_tva') ecrireLastTva(v)
    setLines(ls => ls.map(l => (l._key === key
      ? {
          ...l, [k]: v,
          // VX249(b) — une modification MANUELLE du taux retire le style
          // « suggéré » de CETTE ligne (jamais les autres) ; tout autre champ
          // laisse `_tvaSuggested` inchangé.
          ...(k === 'taux_tva' ? { _tvaSuggested: false } : {}),
          // N2 — la frappe manuelle du prix pose le verrou `prixManuel` : la
          // résolution de liste de prix (refreshTarif, déclenchée par l'effet
          // [clientId, lines.length]) ne réécrit plus ce prix tant que le
          // produit de CETTE ligne n'est pas resélectionné (onProduitChange
          // lève le verrou).
          ...(k === 'prix_unit_ttc' ? { prixManuel: true } : {}),
          // QJR569 — même règle pour la QUANTITÉ tapée d'une ligne produit :
          // le verrou `quantiteManuelle` (gardes D12 du serveur) est posé ICI
          // seulement — une composition ne le pose jamais.
          ...(k === 'quantite' && l.produit ? { quantiteManuelle: true } : {}),
        }
      : l)))
  }, [setLines])

  // XSAL3 — badge « Tarif : <liste> » par ligne, quand le prix résolu vient
  // d'une liste de prix client (source !== 'standard'). Purement informatif +
  // pré-remplissage au changement de produit/quantité/client — ne touche
  // JAMAIS une valeur déjà tapée manuellement par l'utilisateur après coup
  // (aucun re-snap sur un prix modifié à la main).
  const [tarifBadges, setTarifBadges] = useState({})

  // Identité stable (useCallback, dépend seulement de `clientId`) : référencée
  // par onProduitChange/onQuantiteChange ci-dessous (exhaustive-deps /
  // preserve-manual-memoization) sans faire recréer ces callbacks à chaque
  // rendu.
  const refreshTarif = useCallback(async (key, produitId, quantite) => {
    if (!produitId) {
      setTarifBadges(b => { const { [key]: _drop, ...rest } = b; return rest })
      return
    }
    try {
      const { data } = await ventesApi.getPrixApplicable({
        produit: produitId,
        client: clientId || undefined,
        quantite: quantite || 1,
      })
      if (data.source && data.source !== 'standard') {
        setTarifBadges(b => ({ ...b, [key]: data.liste_nom }))
        // N2 — jamais réécrire un prix TAPÉ À LA MAIN (drapeau `prixManuel`,
        // relu ICI au moment de l'écriture via la mise à jour fonctionnelle —
        // jamais un `lines` capturé au lancement de l'appel réseau, qui serait
        // périmé) : le vendeur reprend la main tant qu'il n'a pas resélectionné
        // le produit de cette ligne (onProduitChange lève le verrou).
        setLines(ls => ls.map(l =>
          (l._key === key && !l.prixManuel) ? { ...l, prix_unit_ttc: String(data.prix) } : l))
      } else {
        setTarifBadges(b => { const { [key]: _drop, ...rest } = b; return rest })
      }
    } catch {
      // Résolution de prix indisponible : on garde le prix standard déjà posé,
      // jamais de blocage de la saisie.
      setTarifBadges(b => { const { [key]: _drop, ...rest } = b; return rest })
    }
  }, [clientId, setLines])

  const onProduitChange = useCallback((key, produitId) => {
    const p = produits.find(p => String(p.id) === String(produitId))
    setLines(ls => ls.map(l =>
      l._key === key
        ? {
            ...l,
            produit: produitId,
            designation: p?.nom ?? l.designation,
            prix_unit_ttc: p ? String(ttcFromHt(p.prix_vente, tauxTvaOf(p))) : l.prix_unit_ttc,
            taux_tva: p ? String(tauxTvaOf(p)) : (l.taux_tva ?? '20'),
            // N2 — resélectionner un produit reprend la main sur son prix
            // catalogue : lève le verrou manuel posé par une frappe précédente.
            prixManuel: false,
            // QJR569 — …et le verrou de quantité (nouveau produit, nouvelle main).
            quantiteManuelle: false,
            // QJR570 — un produit choisi à la main n'est plus une ligne composée.
            compose: false,
            // QJR523 — le rôle stocké était celui de l'ANCIEN produit : le
            // serveur le re-déduit du nouveau.
            role_devis: '',
          }
        : l
    ))
    if (p) {
      const l = lines.find(x => x._key === key)
      refreshTarif(key, produitId, l?.quantite)
    }
  }, [produits, lines, refreshTarif, setLines])

  // Ré-interroge le tarif applicable quand la quantité change sur une ligne
  // déjà liée à un produit (paliers XSAL2), ou quand le client change (liste
  // XSAL1 assignée) — pour toutes les lignes liées à un produit.
  const onQuantiteChange = useCallback((key, quantite) => {
    setLine(key, 'quantite', quantite)
    const l = lines.find(x => x._key === key)
    if (l?.produit) refreshTarif(key, l.produit, quantite)
  }, [lines, setLine, refreshTarif])

  useEffect(() => {
    lines.forEach(l => { if (l.produit) refreshTarif(l._key, l.produit, l.quantite) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId, lines.length])

  // QP2 — au blur d'une désignation modifiée (par un rôle autorisé) qui diffère
  // du nom du produit lié, propose les deux options : « renommer ici seulement »
  // (on garde le texte divergent, rien d'autre) ou « créer un nouveau produit
  // dans le stock » (clone serveur via /dupliquer/, puis on relie la ligne au
  // clone). Non bloquant : ne s'ouvre que sur une vraie divergence.
  const onDesignationBlur = useCallback((key) => {
    if (!canRenameLine) return
    const l = lines.find(x => x._key === key)
    if (!l || !l.produit) return
    const prod = produits.find(p => String(p.id) === String(l.produit))
    if (!prod) return
    const nouveauNom = (l.designation || '').trim()
    if (!nouveauNom || nouveauNom === (prod.nom || '').trim()) return
    setRenameError(null)
    setRenameDialog({ key, ancienNom: prod.nom, nouveauNom, produitId: l.produit })
  }, [canRenameLine, lines, produits])

  // Option (a) — « Renommer sur ce devis seulement » : on garde la désignation
  // divergente telle quelle, aucun produit créé. Juste fermer le dialogue.
  const renameHereOnly = () => setRenameDialog(null)

  // Option (b) — « Créer un nouveau produit dans le stock » : clone SERVEUR du
  // produit de base sous le nouveau nom (prix d'achat copié côté serveur,
  // jamais transmis par le client — QP2/QG4), puis relie la ligne au clone.
  const renameAsNewProduct = async () => {
    if (!renameDialog) return
    setRenameBusy(true)
    setRenameError(null)
    try {
      const res = await stockApi.dupliquerProduit(renameDialog.produitId, renameDialog.nouveauNom)
      const clone = res.data
      setProduits(ps => [...ps, clone])
      setLines(ls => ls.map(l =>
        l._key === renameDialog.key
          ? {
              ...l,
              produit: String(clone.id),
              designation: clone.nom,
              prix_unit_ttc: String(ttcFromHt(clone.prix_vente, tauxTvaOf(clone))),
              taux_tva: String(tauxTvaOf(clone)),
            }
          : l))
      setRenameDialog(null)
    } catch (err) {
      const detail = err?.response?.data?.detail
      setRenameError(typeof detail === 'string'
        ? detail : 'La création du nouveau produit a échoué.')
    } finally {
      setRenameBusy(false)
    }
  }

  const addLine = () => setLines(ls => {
    const line = emptyLine()
    setPendingFocusKey(line._key) // VX90 — focus la nouvelle ligne après rendu.
    return [...ls, line]
  })
  // XSAL14 — ajoute une ligne de SECTION (intertitre) ou de NOTE (texte sans
  // prix). Exclue de tous les totaux ; rendue comme intertitre/note.
  const addStructureLine = (typeLigne) => setLines(ls => {
    const line = structureLine(typeLigne)
    setPendingFocusKey(line._key)
    return [...ls, line]
  })
  const removeLine = useCallback((key) =>
    setLines(ls => ls.filter(l => l._key !== key)), [setLines])
  // PVORD (fondateur 19/08/2026) — réordonnancement manuel des lignes dans
  // l'éditeur (monter/descendre). Mutation PURE de l'ORDRE du tableau
  // `lines` : le chemin de sauvegarde existant (`lignesPayload`, plus bas)
  // dérive déjà `ordre: idx` de cet ordre — aucun autre câblage requis pour
  // que le nouvel ordre soit persisté au « Enregistrer ». `delta` = -1
  // (monter) ou +1 (descendre) ; hors bornes = no-op silencieux.
  const moveLine = useCallback((key, delta) => setLines(ls => {
    const idx = ls.findIndex(l => l._key === key)
    if (idx < 0) return ls
    const target = idx + delta
    if (target < 0 || target >= ls.length) return ls
    const copy = ls.slice()
    const [item] = copy.splice(idx, 1)
    copy.splice(target, 0, item)
    return copy
  }), [setLines])
  const moveLineUp = useCallback((key) => moveLine(key, -1), [moveLine])
  const moveLineDown = useCallback((key) => moveLine(key, 1), [moveLine])
  // PVORD — « Enregistrer cet ordre comme ordre par défaut » : dérive la
  // séquence de rôles depuis les lignes COURANTES de l'écran (classification
  // réutilisée, jamais un nouveau mot-clé — voir deriveRoleOrderFromLines) et
  // la PATCH sur ParametresGammes.ordre_lignes. Best-effort, même patron que
  // GammesMarquesPage.jsx : un rôle non Admin/Responsable reçoit un 403 (géré
  // via un toast d'erreur), jamais un plantage de l'écran.
  const handleSaveOrdreLignes = async () => {
    const derived = deriveRoleOrderFromLines(lines)
    setSavingOrdreLignes(true)
    try {
      const { data } = await ventesApi.updateParametresGammes({ ordre_lignes: derived })
      setGammesConfig(prev => ({ ...(prev || {}), ordre_lignes: data?.ordre_lignes ?? derived }))
      toast.success('Ordre des lignes enregistré comme ordre par défaut pour les prochains devis.')
    } catch (err) {
      const detail = err?.response?.data?.detail
      toast.error(typeof detail === 'string'
        ? detail : 'Impossible d\'enregistrer cet ordre par défaut.')
    } finally {
      setSavingOrdreLignes(false)
    }
  }
  // VX188 — identité stable pour ProduitPicker.onProduitCreated (passé à
  // chaque DevisLineRow) : setProduits est déjà un setState fonctionnel,
  // aucune dépendance réelle.
  const onProduitCreated = useCallback((p) => setProduits(ps => [...ps, p]), [])

  // VX90 — quand une ligne vient d'être ajoutée, focaliser son ProduitPicker et
  // la faire défiler dans la vue. On cible la ligne par son data-line-key, puis
  // le premier bouton (le déclencheur du ProduitPicker) de cette ligne.
  useEffect(() => {
    if (pendingFocusKey == null) return
    const row = linesTableRef.current
      ?.querySelector(`[data-line-key="${pendingFocusKey}"]`)
    if (row) {
      const picker = row.querySelector('button[type="button"]')
      picker?.focus()
      row.scrollIntoView({ block: 'nearest' })
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset one-shot du focus (VX90)
    setPendingFocusKey(null)
  }, [pendingFocusKey, lines])

  // ── QJ31 — Multi-propriétés ──────────────────────────────────────────────
  // Bascule de mode. En passant en « villas », chaque ligne sans groupe est
  // rattachée à l'équipement commun (index 0) par défaut ; en repassant en
  // « none »/« multiplier », on efface les groupes (mono-système / ×N).
  const onMultiModeChange = (m) => {
    setMultiMode(m)
    if (m === 'villas') {
      setLines(ls => ls.map(l =>
        l.groupeIndex == null ? { ...l, groupeIndex: 0, groupeLabel: 'Équipement commun' } : l))
    } else {
      setLines(ls => ls.map(l => ({ ...l, groupeIndex: null, groupeLabel: '' })))
    }
  }

  // Assigne une ligne à un groupe villa (met à jour l'index + le libellé).
  const setLineGroupe = useCallback((key, idx) => {
    const grp = villaGroups.find(g => g.index === idx)
    setLines(ls => ls.map(l =>
      l._key === key ? { ...l, groupeIndex: idx, groupeLabel: grp?.label ?? '' } : l))
  }, [villaGroups, setLines])

  const addVillaGroup = () => {
    setVillaGroups(gs => {
      const nextIndex = gs.reduce((m, g) => Math.max(m, g.index), 0) + 1
      return [...gs, { index: nextIndex, label: `Villa ${nextIndex}` }]
    })
  }

  const renameVillaGroup = (idx, label) => {
    setVillaGroups(gs => gs.map(g => (g.index === idx ? { ...g, label } : g)))
    // Répercute le nouveau libellé sur les lignes déjà rattachées à ce groupe.
    setLines(ls => ls.map(l => (l.groupeIndex === idx ? { ...l, groupeLabel: label } : l)))
  }

  const removeVillaGroup = (idx) => {
    if (idx === 0) return // l'équipement commun n'est pas supprimable
    setVillaGroups(gs => gs.filter(g => g.index !== idx))
    // Les lignes du groupe supprimé retombent sur l'équipement commun.
    setLines(ls => ls.map(l =>
      l.groupeIndex === idx ? { ...l, groupeIndex: 0, groupeLabel: 'Équipement commun' } : l))
  }

  // QJR570 (D-QJR5-4) — LE point d'écriture des trois recompositions
  // (composition locale, dry-run serveur, pompage) : FUSION par id produit
  // (`fusionnerRecomposition`) — prix tapés, sections, notes, options et
  // produits ajoutés à la main conservés d'office. Une quantité figée en
  // conflit est GARDÉE (le vendeur l'a confirmé avant le geste) et NOMMÉE.
  const modeRecomposition = useRef('garder')
  const recomposerLignes = (generated) => {
    const mode = modeRecomposition.current
    modeRecomposition.current = 'garder'
    const { conflits } = appliquerRecomposition(lines, generated, mode)
    setLines(ls => withKeys(appliquerRecomposition(ls, generated, mode).lignes))
    if (conflits.length) {
      toast.warning('Quantités figées gardées : ' + conflits.slice(0, 5)
        .map(c => `${c.designation} ${c.figee} (recalculé : ${c.recalculee})`).join(', ')
        + (conflits.length > 5 ? '…' : '') + '.')
    }
  }

  // QJR570 — la seule question posée avant une recomposition : des quantités
  // figées à la main existent (5 désignations au plus). Sans elles, AUCUNE
  // confirmation et le geste part de façon synchrone (invariant F2 QJR99 :
  // jamais de `confirm` DANS handleAutoFill). Annuler ne dispatche rien.
  const avecQuantitesFigees = (geste) => {
    // Conflit POSSIBLE seulement s'il existe une quantité figée à la main ;
    // prix tapés et options sont gardés d'office (aucun dialogue).
    const manuelles = lignesManuellesEnConflitPossible(lines)
    if (!manuelles.length) { modeRecomposition.current = 'garder'; geste(); return }
    const noms = manuelles.slice(0, 5)
      .map(l => `${l.designation || 'ligne'} : ${l.quantite}`).join(', ')
      + (manuelles.length > 5 ? '…' : '')
    confirm({
      title: 'Garder vos saisies ?',
      description: `Lignes saisies à la main (${noms}) : la recomposition peut les GARDER `
        + 'ou prendre uniquement les valeurs recalculées.',
      confirmLabel: 'Recomposer en les gardant',
      alternativeLabel: 'Prendre N (recalculé)',
      destructive: false,
    }).then((choix) => {
      if (choix === 'alternative') { modeRecomposition.current = 'recalcule'; geste() }
      else if (choix) { modeRecomposition.current = 'garder'; geste() }
    })
  }

  // QJR546 — appliquer un modèle REMPLACE les lignes À L'ÉCRAN, en création
  // comme en édition (plus d'apply-preset serveur qui ajoutait des lignes en
  // base sans que l'écran les voie) : remise, TVA et marché du modèle posés,
  // lignes au produit sans prix SAUTÉES et NOMMÉES. L'étude du client source
  // (etude_params_snapshot) n'est JAMAIS réappliquée. L'Enregistrer suivant
  // persiste le tout par replace-lines.
  const handlePresetApplied = (preset) => {
    const snapshot = Array.isArray(preset?.lignes_snapshot) ? preset.lignes_snapshot : []
    if (!snapshot.length) return
    const parId = new Map(produits.map(p => [String(p.id), p]))
    const sansPrix = []
    const retenues = snapshot.filter((l) => {
      const id = l.produit ?? l.produit_id
      if (id == null || id === '') return true
      const produit = parId.get(String(id))
      if (produit && !_hasPrix(produit)) {
        sansPrix.push(l.designation || produit.nom || `#${id}`)
        return false
      }
      return true
    })
    if (preset.mode_installation) appliquerMarcheEcran(preset.mode_installation, 'programme')
    if (preset.taux_tva != null) setTauxTva(String(preset.taux_tva))
    if (preset.remise_globale != null) setDiscountPct(String(parseFloat(preset.remise_globale) || 0))
    // QJR523 — même mappeur que la réouverture `?edit=` (HT → TTC au taux de
    // la ligne, tous les champs portés).
    setLines(withKeys(lignesServeurVersEcran(retenues, preset.taux_tva)))
    if (sansPrix.length) {
      toast.warning('Produit(s) sans prix non repris du modèle : ' + sansPrix.join(', '))
    }
  }

  // AGR130 — le dimensionnement pompage vit CÔTÉ SERVEUR (aperçu AGR127,
  // `apercuPompage` ci-dessous) : plus aucune sélection JavaScript.
  // AGR128 — l'état de l'écran recomposé dans la forme du corps du contrat
  // (AGR127) ; l'aperçu SERVEUR n'est demandé que pour le marché agricole et
  // seulement quand l'essentiel est saisi (sinon `null`, aucun appel).
  const etatPompage = useMemo(() => etatPompageEcran(pompageSaisie, {
    pompeCv, pompeType, pompeAlim, pompeHmt, pompeDebit, pompeProfondeur,
    pompeDistance, farmRegion, farmCrop, farmSurfaceHa, farmIrrigation,
    farmHmtStatic, farmHmtDrawdown, leadId: leadId || null,
    editId: editId || null,
  }), [pompageSaisie, pompeCv, pompeType, pompeAlim, pompeHmt, pompeDebit,
    pompeProfondeur, pompeDistance, farmRegion, farmCrop, farmSurfaceHa,
    farmIrrigation, farmHmtStatic, farmHmtDrawdown, leadId, editId])
  const pompageManquants = modeInstallation === 'agricole'
    ? manquantsPompage(etatPompage) : []
  const corpsPompage = modeInstallation === 'agricole'
    ? construireCorpsPompage(etatPompage) : null
  const apercuPompage = useEtudePompagePreview(corpsPompage)
  // AGR212 — mois d'irrigation PRÉ-COCHÉS par le calendrier de la culture :
  // ceux où le besoin servi par l'aperçu serveur (besoin agronomique) est > 0.
  const moisCalendrier = useMemo(() => {
    const b = apercuPompage?.donnees?.besoin
    if (!b || b.nature !== 'agronomique_plein' || !Array.isArray(b.m3_jour_mois)) return []
    return b.m3_jour_mois.map((v, i) => (v > 0 ? i + 1 : null)).filter(Boolean)
  }, [apercuPompage?.donnees])
  const aujourdhuiIso = new Date().toISOString().slice(0, 10)
  const ecoAvecCalendrier = (ecoPompage.mois == null && moisCalendrier.length)
    ? {
        ...ecoPompage,
        dateDeclaration: ecoPompage.dateDeclaration || aujourdhuiIso,
        mois: moisCalendrier,
        moisProvenance: ecoPompage.confirme
          ? { origine: 'saisie', detail: null, date: ecoPompage.dateDeclaration || aujourdhuiIso }
          : { origine: 'calculee', detail: 'calendrier_culture', date: ecoPompage.dateDeclaration || aujourdhuiIso },
      }
    : { ...ecoPompage, dateDeclaration: ecoPompage.dateDeclaration || aujourdhuiIso }
  // AGR212 — la garde de cohérence (AGR204) vient de l'aperçu SERVEUR de
  // l'économie : la case « je confirme ce chiffre » n'apparaît que si elle
  // avertit.
  const saisiesEcoApercu = modeInstallation === 'agricole'
    ? saisiesEconomiePompage(ecoAvecCalendrier) : null
  const economiePompage = useEconomiePompagePreview(
    saisiesEcoApercu && apercuPompage?.donnees
      ? { saisies: saisiesEcoApercu, sortie_etude_pompage: apercuPompage.donnees, lignes: [] }
      : null)
  const coherenceAvertit = (economiePompage?.coherence || []).length > 0

  // U3COMPOSE (26/08/2026) — composition LOCALE (JavaScript), CONSERVÉE : le
  // chemin agricole (déjà séparé, ci-dessous) reste local car aucun dry-run
  // serveur n'existe pour l'agricole/l'industriel/le commercial (à faire dans
  // un chantier séparé, voir rapport) ; ET le REPLI résidentiel si l'appel
  // réseau échoue — l'écran ne doit JAMAIS se retrouver sans Auto-remplir.
  // Extrait tel quel de l'ancien corps de `handleAutoFill` : comportement
  // byte-identique à avant U3COMPOSE, pour ces trois marchés comme pour le repli.
  const composeLocalement = () => {
    if (kwp <= 0) {
      setErrors(e => ({ ...e, autofill: 'Entrez le nombre de panneaux' }))
      return
    }
    let generated = autoFillLines(produits, {
      kwp,
      panelW: parseFloat(panelW) || 710,
      structureType,
      // STKCAT10 — le produit choisi au catalogue prime sur le bouton
      // acier/alu et fait émettre UNE ligne structure à son nom.
      structureProduitId,
      // PVMRQ — marques préférées (Paramètres → Gammes & marques, gamme
      // active de ce devis) : une marque épinglée gagne toujours, jamais de
      // repli silencieux sur une autre marque (voir marquesManquantes ci-dessous).
      marques: marquesActives,
      // PVORD — ordre par défaut de la société (Paramètres → Gammes &
      // marques, ou le bouton « Enregistrer cet ordre » de ce devis) ;
      // absent/vide = ordre canonique du simulateur (comportement historique).
      ordreLignes: gammesConfig?.ordre_lignes,
      // OFFGRID — site isolé : UNE seule option (panneaux + onduleur hors
      // réseau + batterie), jamais le double panier sans/avec ci-dessous.
      // `undefined` quand `horsReseau` est faux : appel BYTE-IDENTIQUE à
      // l'historique (aucun paramètre `offgrid` n'existait avant ce chantier).
      offgrid: horsReseau || undefined,
    })
    // OFFGRID — l'auto-remplissage hors réseau a échoué (aucun onduleur/
    // batterie priced au catalogue) : `autoFillLines` renvoie un tableau VIDE
    // avec son motif FRANÇAIS exact, jamais un repli silencieux sur l'hybride.
    if (horsReseau && generated.offgridErreur) {
      setErrors(e => ({ ...e, autofill: generated.offgridErreur }))
      return
    }
    // L-2OPT (fondateur 24/08) — deux optimiseurs indépendants : en
    // résidentiel, un scénario qui sert RÉELLEMENT l'option AVEC (« Les
    // deux » ou « Avec batterie » seule) compose CETTE branche à SON PROPRE
    // optimum (kwc_avec, potentiellement différent du kwc_sans ci-dessus).
    // Fusion générique (fusionnerVariantes, solar.js) : deux tailles égales
    // (le cas le plus courant, et le repli quand aucune source n'a d'avis)
    // retombent sur la composition unique ci-dessus, BYTE-IDENTIQUE à
    // l'historique — aucune ligne variantée, repli de sécurité épinglé par
    // test. OFFGRID — jamais cette branche : une composition hors réseau ne
    // connaît qu'UNE option, déjà posée ci-dessus.
    if (!horsReseau && modeInstallation === 'residentiel'
        && (scenario === SCENARIO_LES_DEUX || scenario === SCENARIO_AVEC)) {
      const kwpAvec = resolveKwcAvec()
      if (Math.abs(kwpAvec - kwp) > 1e-9) {
        const composeAvec = () => autoFillLines(produits, {
          kwp: kwpAvec,
          panelW: parseFloat(panelW) || 710,
          structureType,
          structureProduitId,
          marques: marquesActives,
          ordreLignes: gammesConfig?.ordre_lignes,
        })
        if (scenario === SCENARIO_AVEC) {
          // mono avec : compose l'optimum AVEC seul, aucune fusion.
          generated = composeAvec()
        } else {
          const lignesSans = generated
          const lignesAvec = composeAvec()
          generated = fusionnerVariantes(lignesSans, lignesAvec)
          generated.actualPanelW = lignesSans.actualPanelW
          generated.kwcReel = lignesSans.kwcReel
          generated.onduleursIncomplets = dedupeParCle(
            [...(lignesSans.onduleursIncomplets ?? []), ...(lignesAvec.onduleursIncomplets ?? [])],
            (o) => o.id)
          generated.marquesManquantes = dedupeParCle(
            [...(lignesSans.marquesManquantes ?? []), ...(lignesAvec.marquesManquantes ?? [])],
            (m) => `${m.role}|${m.marque}`)
        }
      }
    }
    // Les MÉTADONNÉES du tableau (wattage réel, kWc réel, onduleurs grisés)
    // sont relevées ICI, avant tout `.map()` : un `.map()` rend un tableau NEUF
    // et les perdrait en route (les modes industriel/commercial ci-dessous en
    // font un).
    const metaPanelW = generated.actualPanelW
    const metaKwcReel = generated.kwcReel
    const metaOnduleursIncomplets = generated.onduleursIncomplets ?? []
    const metaMarquesManquantes = generated.marquesManquantes ?? []
    // Modes industriel ET commercial (QX44) : sans batterie par défaut
    // (autoconsommation réseau, pas de stockage). OFFGRID — jamais cette
    // garde : un système hors réseau porte TOUJOURS sa batterie, quel que
    // soit le marché du devis.
    if (!horsReseau && (modeInstallation === 'industriel' || modeInstallation === 'commercial')) {
      generated = generated.map(r =>
        (isBattery(r.designation) || isHybridInverter(r.designation))
          ? { ...r, quantite: 0 } : r)
    }
    if (!generated.length) {
      setErrors(e => ({ ...e, autofill: 'Aucun produit solaire reconnu dans le stock.' }))
      return
    }
    // Dire EXACTEMENT ce qui manque — jamais de ligne « — Produit — » à
    // 0 MAD laissée sans explication.
    const manquants = generated
      .filter(r => !r.produit && parseFloat(r.quantite) > 0)
      .map(r => r.designation || 'ligne sans produit')
    // QX19 — divergence de wattage : le catalogue a substitué un panneau d'une
    // AUTRE puissance que celle saisie (ex. 550 W pour 710 W). Le kWc affiché
    // (issu du wattage saisi) ne correspond alors plus aux lignes réelles. On
    // le signale visiblement plutôt que d'expédier un système mal étiqueté.
    const askedW = parseFloat(panelW) || 710
    const realW = metaPanelW
    let mismatch = null
    if (realW && Math.abs(realW - askedW) > 1) {
      const kwcReel = metaKwcReel
      mismatch = `Attention : le stock ne propose pas de panneau ${askedW} W ; `
        + `un panneau ${realW} W a été retenu. La puissance réelle du système est `
        + `${kwcReel} kWc (et non ${kwp} kWc). Ajustez le nombre de panneaux ou le `
        + 'wattage pour la cible voulue.'
    }
    // PVMRQ — une marque épinglée sans AUCUN candidat en stock : même patron
    // visuel que le message « Aucun produit du stock ne correspond à… »
    // ci-dessus, mais un message DISTINCT (la cause n'est pas « rôle non
    // reconnu », c'est « cette marque précise n'est pas au catalogue ») —
    // jamais un repli silencieux sur une autre marque.
    const marquesMsg = metaMarquesManquantes.length
      ? `Marque épinglée introuvable au stock : ${metaMarquesManquantes
          .map(m => `${m.marque} (${roleLabel(m.role)})`).join(', ')}. `
        + 'Ajoutez le produit ou changez la marque dans Paramètres → Gammes.'
      : null
    setErrors(e => ({
      ...e,
      autofill: manquants.length
        ? `Aucun produit du stock ne correspond à : ${[...new Set(manquants)].join(', ')}. `
          + 'Complétez le catalogue ou choisissez ces produits à la main dans les lignes.'
        : null,
      autofillKwc: mismatch,
      marquesManquantes: marquesMsg,
    }))
    // PVOND — onduleurs ÉCARTÉS de l'auto-composition faute de contrat complet
    // (même patron que « prix à renseigner ») : on les nomme avec leur motif
    // plutôt que de les laisser disparaître sans explication.
    setOnduleursIncomplets(metaOnduleursIncomplets)
    recomposerLignes(generated)
    // Rend les lignes composées à l'appelant (`composeLocalement`, qui dit
    // seulement si une composition a été posée).
    return generated
  }

  // U3COMPOSE — l'optimum AXE BATTERIE envoyé au dry-run serveur : même
  // précédence que `resolveKwcAvec` ci-dessus (le moteur horaire serveur
  // prime), sans jamais inventer un nombre de panneaux hors d'une dérivation
  // réelle (repli sur la conversion kWc→panneaux du wattage saisi).
  const buildDimensionnementAvec = (kwpAvec) => {
    const backendAvec = etudeHoraireDonnees?.dimensionnement?.recommandation_avec
    const panelWNum = parseFloat(panelW) || 710
    // QJR37 — le moteur horaire (recommandation/recommandation_avec) émet la
    // clé `panneaux` (vérifié contre apps/ventes/contract_samples/
    // etude_horaire.json : "recommandation_avec": {"panneaux": 17, …}), jamais
    // `nb_panneaux` — cette dernière n'existe QUE côté REQUÊTE de
    // POST /ventes/devis/composition/ (contract_samples/devis_composition.json,
    // champ d'entrée `dimensionnement_avec: {nb_panneaux?, kwc?, …}`), une
    // forme différente qu'on continue de PRODUIRE ci-dessous inchangée.
    const nbPanneauxAvec = Number(backendAvec?.panneaux) > 0
      ? Math.round(Number(backendAvec.panneaux))
      : Math.round((kwpAvec * 1000) / panelWNum)
    const dims = { nb_panneaux: nbPanneauxAvec, kwc: kwpAvec }
    const battKwh = Number(backendAvec?.batterie_kwh)
    if (battKwh > 0) dims.batterie_kwh = battKwh
    return dims
  }

  // U3COMPOSE — mappe la réponse du dry-run serveur (contract_samples/
  // devis_composition.json) vers les lignes éditables de l'écran. Le HT
  // (`prix_unitaire_ht`) fait foi — c'est le prix RÉEL en base — mais le TTC
  // affiché est RE-DÉRIVÉ ici avec `tauxTvaOf`/`ttcFromHt` (le taux RÉEL par
  // produit — 10 % panneaux, 20 % le reste, DC7) plutôt que le
  // `prix_unitaire_ttc`/`taux_tva` renvoyés par le dry-run, qui appliquent un
  // taux UNIQUE à toute la composition (simplification de prévisualisation
  // côté serveur, `taux_tva` de la requête, 20 % par défaut) : sans ce
  // ré-alignement une ligne panneau afficherait un TTC calculé à 20 % au lieu
  // de 10 % — un écart de PRIX réel, pas un simple arrondi.
  const appliquerCompositionServeur = (data) => {
    const generated = (data.lignes || []).map(li => {
      const produit = produits.find(p => String(p.id) === String(li.produit))
      const taux = produit ? tauxTvaOf(produit) : tauxTvaOuDefaut(li.taux_tva, 20)
      const prixTtc = produit
        ? ttcFromHt(li.prix_unitaire_ht, taux)
        : (li.prix_unitaire_ttc ?? 0)
      return {
        produit: li.produit ?? '',
        designation: li.designation,
        quantite: li.quantite,
        prix_unit_ttc: prixTtc,
        taux_tva: taux,
        variante: li.variante || '',
      }
    })
    if (!generated.length) {
      setErrors(e => ({ ...e, autofill: 'Aucun produit solaire reconnu dans le stock.' }))
      return
    }
    // Même message que la composition locale (mêmes clés d'erreur, même bandeau).
    const manquants = generated
      .filter(r => !r.produit && parseFloat(r.quantite) > 0)
      .map(r => r.designation || 'ligne sans produit')
    const askedW = parseFloat(panelW) || 710
    const realW = data.panel_watt
    let mismatch = null
    if (realW && Math.abs(realW - askedW) > 1) {
      mismatch = `Attention : le stock ne propose pas de panneau ${askedW} W ; `
        + `un panneau ${realW} W a été retenu. La puissance réelle du système est `
        + `${data.kwc_reel} kWc (et non ${kwp} kWc). Ajustez le nombre de panneaux ou le `
        + 'wattage pour la cible voulue.'
    }
    const marquesManquantes = data.marques_manquantes || []
    const marquesMsg = marquesManquantes.length
      ? `Marque épinglée introuvable au stock : ${marquesManquantes
          .map(m => `${m.marque} (${roleLabel(m.role)})`).join(', ')}. `
        + 'Ajoutez le produit ou changez la marque dans Paramètres → Gammes.'
      : null
    const manquantsMsg = manquants.length
      ? `Aucun produit du stock ne correspond à : ${[...new Set(manquants)].join(', ')}. `
        + 'Complétez le catalogue ou choisissez ces produits à la main dans les lignes.'
      : null
    // `avertissements` (dry-run serveur) : mêmes messages que ceux que PVOND
    // affichait localement pour un onduleur incomplet, un rôle absent, etc. —
    // rendus tels quels dans le même bandeau, jamais tus.
    const avertissementsMsg = (data.avertissements || []).join(' ') || null
    setErrors(e => ({
      ...e,
      autofill: [manquantsMsg, avertissementsMsg].filter(Boolean).join(' ') || null,
      autofillKwc: mismatch,
      marquesManquantes: marquesMsg,
    }))
    recomposerLignes(generated)
  }

  const handleAutoFill = async () => {
    // PVOND — le bandeau des onduleurs grisés appartient au DERNIER
    // auto-remplissage : on le vide d'abord, sinon un message du run précédent
    // survivrait à un changement de mode (le pompage n'a pas d'onduleur).
    setOnduleursIncomplets([])
    // Mode agricole : équipement pompage (pompe + variateur + champ PV)
    if (modeInstallation === 'agricole') {
      // AGR130 — Auto-remplir pose les lignes du KIT de la taille choisie,
      // telles que le serveur les a composées (aperçu AGR127) : aucune
      // composition JavaScript. Sans aperçu, rien n'est inventé.
      const kit = apercuPompage?.donnees?.kit
      const generated = lignesDepuisKit(kit, produits)
      if (!generated.length) {
        setErrors(e => ({ ...e, autofill: 'Le dimensionnement du serveur n\'est pas encore disponible : '
          + 'renseignez le besoin, la hauteur et le cas de pompe, puis patientez un instant.' }))
        return
      }
      setErrors(e => ({ ...e, autofill: null, marquesManquantes: null }))
      recomposerLignes(generated)
      // Succès sur le marché agricole : une erreur de composition
      // résidentielle antérieure ne décrit plus rien (QJR577).
      setCompositionErreur(null)
      // QJR99 — le dimensionnement POSE une taille calculée : la même
      // transition que la réouverture d'un devis (`REOUVERTURE`) la pose SANS
      // marquer le champ « touché » (ce n'est pas une frappe).
      const nb = apercuPompage?.donnees?.champ?.nb_panneaux
      if (Number.isFinite(Number(nb)) && Number(nb) > 0) {
        dispatchSizing({ type: 'REOUVERTURE', devis: { panneaux: Number(nb) } })
      }
      setPompageAutoFilled(true)
      return
    }
    // U3COMPOSE (26/08/2026) — RÉSIDENTIEL SEULEMENT : le dry-run serveur
    // (POST /ventes/devis/composition/, U3) devient la source de vérité de
    // l'aperçu écran au lieu de la recomposition locale (deux implémentations
    // divergeaient déjà avant U3, incident du 20/08 — câbles, marques,
    // ordre, arrondi panneaux). Un échec réseau/serveur retombe SANS
    // EXCEPTION sur `composeLocalement` (ex-corps de cette fonction) :
    // l'écran ne doit jamais se retrouver sans Auto-remplir. Agricole
    // (ci-dessus) / industriel / commercial : AUCUN dry-run serveur n'existe
    // pour ces marchés — comportement local strictement inchangé.
    if (modeInstallation === 'residentiel') {
      if (kwp <= 0) {
        setErrors(e => ({ ...e, autofill: 'Entrez le nombre de panneaux' }))
        return
      }
      setAutoFillLoading(true)
      try {
        const body = {
          kwc: kwp,
          panel_watt: parseFloat(panelW) || 710,
          // STKCAT1/STKCAT7 — `structure_type` reste envoyé comme ALIAS
          // DÉPRÉCIÉ (compatibilité descendante ET repli quand aucun produit
          // n'est choisi) ; `structure_produit_id`, quand il est là, est
          // PRIORITAIRE côté serveur et les deux ne se combinent jamais.
          structure_type: structureType,
          ...(structureProduitId
            ? { structure_produit_id: Number(structureProduitId) }
            : {}),
        }
        // BARÈME TRANSPORT — QJR604 : l'écran envoie l'ID du lead ; le serveur
        // en résout la ville (lead de la société) et reprice la ligne
        // Transport dans l'étape composer. Sans lead : prix catalogue.
        if (selectedLead?.id) body.lead = selectedLead.id
        // OFFGRID — champ additif optionnel (contrat backend) : absent quand
        // `horsReseau` est faux, le serveur dérive alors de
        // `lead.raccordement == 'aucun'` lui-même. Envoyé explicitement ici
        // pour couvrir le cas où le vendeur bascule le contrôle à la main sans
        // que le lead porte ce raccordement.
        if (horsReseau) body.hors_reseau = true
        // Même déclenchement que la fusion locale ci-dessus (composeLocalement) :
        // seuls « Les deux » et « Avec batterie » servent réellement l'axe
        // batterie, et seulement quand il diverge du champ sans stockage.
        // OFFGRID — jamais cette branche : une composition hors réseau ne
        // connaît qu'une option, le serveur ne reçoit pas `dimensionnement_avec`.
        if (!horsReseau && (scenario === SCENARIO_LES_DEUX || scenario === SCENARIO_AVEC)) {
          const kwpAvec = resolveKwcAvec()
          if (Math.abs(kwpAvec - kwp) > 1e-9) {
            if (scenario === SCENARIO_AVEC) {
              // mono avec : compose l'optimum AVEC seul, aucune fusion —
              // MIROIR EXACT de `composeAvec()` du repli local, qui compose
              // UNE fois à `kwpAvec`. Envoyer `dimensionnement_avec` ici
              // ferait composer au serveur DEUX champs fusionnés (variantes
              // 'sans'/'avec') alors que l'écran n'affiche même pas l'option
              // sans batterie dans ce scénario : le kWc AVEC devient donc la
              // puissance UNIQUE de la requête.
              body.kwc = kwpAvec
            } else {
              body.dimensionnement_avec = buildDimensionnementAvec(kwpAvec)
            }
          }
        }
        const { data } = await ventesApi.composerDevis(body)
        setCompositionErreur(null)
        appliquerCompositionServeur(data)
      } catch (err) {
        // QJR577 (D-QJR5-9) — PLUS de repli JavaScript : les lignes restent
        // celles de l'écran, l'erreur du serveur est rendue telle quelle (ou
        // une cause française générique) avec « Réessayer ».
        const detail = err?.response?.data?.detail
        setCompositionErreur(typeof detail === 'string' && detail
          ? detail
          : "Le serveur n'a pas pu composer ce devis (réseau ou serveur "
            + 'indisponible) — les lignes n\'ont pas changé.')
      } finally {
        setAutoFillLoading(false)
      }
      return
    }
    // Marchés indus/commercial (aucun dry-run serveur pour eux, QJR113 GATED
    // D10) : `composeLocalement()` reste LEUR composeur. Un succès efface une
    // erreur de composition résidentielle antérieure (QJR577).
    if (composeLocalement()) setCompositionErreur(null)
  }

  // CJ2b — bouton « Appliquer cette taille » d'une ligne du tableau de
  // dimensionnement (moteur horaire serveur) : pose `nbPanneaux`/`panelW`
  // depuis la ligne choisie puis relance EXACTEMENT le même chemin de
  // composition que le bouton « Auto-remplir » (`handleAutoFill`) — jamais
  // une seconde règle de composition.
  //
  // QJR99 — le couple `appliquerTaillePending` (ref) + effet calé sur
  // `[nbPanneaux, panelW]` est SUPPRIMÉ : la transition `TAILLE_APPLIQUEE`
  // incrémente elle-même `compositionSeq`, et l'UNIQUE effet de composition
  // ci-dessous relance l'auto-remplissage. Au passage l'ancien montage ne
  // repartait PAS quand la ligne choisie retombait sur le compte courant (aucun
  // changement de dépendance → drapeau laissé armé pour la frappe suivante) ;
  // un compteur, lui, avance toujours.
  const appliquerTailleDimensionnement = (ligne) => {
    if (!ligne || !(ligne.panneaux > 0)) return
    // QJR570 — confirmation (quantités figées seulement) AVANT la transition.
    avecQuantitesFigees(() => dispatchSizing({ type: 'TAILLE_APPLIQUEE', ligne }))
  }

  // FOUNDER 26/08 — bouton « Recalculer le dimensionnement ». Causes RÉELLES
  // (revue adversariale 26/08 — corrige la prose initiale, qui affirmait à
  // tort que `nbPanneauxTouched` restait FERMÉ après un chargement d'édition ;
  // en réalité rien dans l'effet d'édition ?edit= ne touche ce ref, il reste
  // à sa valeur `useRef(false)` par défaut — c'est la preuve gardée par les
  // tests ROOT CAUSE 1-3 ci-dessous) :
  //   1. En ÉDITION (?edit=ID), `fHiver`/`fEte` ne sont JAMAIS reposées
  //      depuis le devis serveur (aucune source ne les porte encore côté
  //      serveur) — retaper la facture repart donc d'un champ VIDE, pas de
  //      la facture d'origine.
  //   2. Le bouton « Auto-remplir » existant (`handleAutoFill`) ne fait que
  //      recomposer le catalogue au `nbPanneaux` COURANT — il ne redérive
  //      jamais ce compte depuis la facture (`computeAutoSizing` n'y est
  //      jamais appelé).
  //   3. Dès qu'un nombre de panneaux a été touché À LA MAIN (n'importe où,
  //      n'importe quand dans la session — pas spécifiquement à cause de
  //      l'édition), `touche.nbPanneaux` se ferme et plus AUCUNE frappe sur
  //      la facture ne recalcule quoi que ce soit (N3, comportement voulu).
  // Ce bouton est le déverrouillage EXPLICITE demandé par le fondateur : un
  // clic vaut consentement à remplacer les quantités auto-dérivées (jamais
  // une frappe seule, cf. règle N3/`syncBillEstimator`).
  //
  // Rejoue le MÊME balayage palier/payback que `computeAutoSizing` sur la
  // facture ACTUELLE (fHiver/fEte), pose les DEUX résultats (sans/avec,
  // L-2OPT), puis relance la composition par le chemin EXACT du bouton
  // « Auto-remplir » (`handleAutoFill` — dry-run serveur résidentiel, repli
  // local `composeLocalement` inchangé pour les autres marchés/pannes
  // réseau) : aucune deuxième règle de composition, et donc la même FUSION
  // que l'Auto-remplir (QJR570, D-QJR5-4 : prix tapés, sections, notes,
  // options et produits ajoutés à la main conservés ; quantités figées
  // confirmées AVANT la transition, jamais dans handleAutoFill).
  //
  // QJR99 — F1/F2 (revue adversariale 26/08) exigeaient de DÉVERROUILLER le
  // garde-fou « touché » le temps du calcul synchrone, puis de restaurer
  // EXACTEMENT sa valeur d'avant le clic — une danse à trois instructions
  // (`recalcDimPriorTouched` / `= false` / restauration dans l'effet) entre
  // lesquelles une frappe pouvait s'engouffrer. Les deux refs SONT SUPPRIMÉES :
  // `RECALCUL_DEMANDE` rouvre le drapeau POUR LA COMPOSITION QUI SUIT et le
  // restaure DANS LA MÊME TRANSITION (invariant 3 du reducer) — la fenêtre
  // n'existe plus, et `toucheNbPanneauxPourComposition` est le seul lecteur qui
  // la voit ouverte, sur une seule transition.
  const recalculerDimensionnement = () => {
    // U3-MOTEUR (fondateur 29/08/2026) — en RÉSIDENTIEL, ce bouton relit la
    // recommandation du MOTEUR HORAIRE serveur (déjà interrogée par le dry-run
    // d'aperçu — aucun appel réseau supplémentaire), jamais un palier chiffré
    // à l'écran : c'était le dernier endroit où un nombre de panneaux
    // auto-calculé localement pouvait encore écraser celui du moteur.
    // `sizingInfo` reste NUL sur ce chemin : son encart parle de « palier
    // retenu / besoin lu sur la facture », deux notions du balayage local qui
    // ne décrivent pas ce que le moteur a fait (règle chiffres-vérifiés).
    let retenu = null
    if (modeInstallation === 'residentiel') {
      const dim = etudeHoraireDonnees?.dimensionnement
      const source = (scenario === SCENARIO_AVEC
        && Number(dim?.recommandation_avec?.panneaux) > 0)
        ? dim.recommandation_avec : dim?.recommandation
      if (!(Number(source?.panneaux) > 0)) {
        setErrors(e => ({
          ...e,
          // Message FRANÇAIS du serveur quand il en a un (il nomme la donnée
          // manquante), sinon la cause générique — jamais un chiffre supposé.
          recalcDim: dim?.motivation
            || etudeHoraireDonnees?.avertissements?.[0]
            || (etudeHoraireChargement
              ? 'Dimensionnement en cours de calcul — réessayez dans un instant.'
              : "Le moteur n'a pas pu chiffrer de recommandation : complétez la "
                + 'facture, la ville et le raccordement du client, puis réessayez.'),
        }))
        return
      }
      retenu = {
        nbPanneaux: Number(source.panneaux),
        kwcOptimal: source.kwc != null ? Number(source.kwc) : null,
      }
    } else {
      const sizing = computeAutoSizing(fHiver, fEte)
      if (!sizing) {
        setErrors(e => ({
          ...e,
          recalcDim: 'Renseignez une facture hiver exploitable (au moins '
            + '~900 MAD/mois) pour recalculer le dimensionnement.',
        }))
        return
      }
      retenu = sizing
    }
    setErrors(e => ({ ...e, recalcDim: null }))
    // Une seule transition : la taille retenue est posée, `sizingInfo` reste
    // NUL en résidentiel (son encart parle de « palier retenu », une notion du
    // balayage local), le garde-fou « touché » est rouvert POUR LA COMPOSITION
    // QUI SUIT et restauré dans le même mouvement, et `compositionSeq` avance —
    // un recalcul qui retombe sur le MÊME compte de panneaux doit quand même
    // relancer la composition (catalogue/marques/scénario ont pu changer).
    // QJR570 — confirmation (quantités figées seulement) AVANT la transition.
    avecQuantitesFigees(() => dispatchSizing({ type: 'RECALCUL_DEMANDE', retenu }))
  }
  // QJR99 — L'UNIQUE effet de composition : « Appliquer cette taille » et
  // « Recalculer le dimensionnement » avancent tous deux `compositionSeq`, et
  // relancent donc EXACTEMENT le chemin du bouton « Auto-remplir » (dry-run
  // serveur résidentiel, repli local ailleurs) — jamais une seconde règle de
  // composition. F2 (26/08) reste satisfait sans aucune manœuvre de
  // verrouillage : `handleAutoFill` lit `resolveKwcAvec()` — donc la fenêtre
  // `recalcul` ouverte par CETTE transition — dans son préfixe SYNCHRONE, et
  // toute action ultérieure referme la fenêtre côté reducer.
  useEffect(() => {
    if (!recalcDimTick) return
    // Différé en MICROTÂCHE (règle react-hooks/set-state-in-effect — les
    // setState du préfixe synchrone de `handleAutoFill` cascaderaient dans
    // l'effet). Aucun événement utilisateur ni re-rendu ne peut s'intercaler
    // avant une microtâche, et `handleAutoFill` lit la fenêtre `recalcul` par
    // CLÔTURE du rendu qui l'a ouverte — F2 reste satisfait à l'identique.
    queueMicrotask(() => { Promise.resolve(handleAutoFill()).catch(() => {}) })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ne réagit qu'au compteur de composition du reducer
  }, [recalcDimTick])

  // ── Sauvegarde ──
  // Une ligne est enregistrée si elle a un produit et une quantité > 0 ;
  // les lignes placeholder (sans produit, prix 0) sont ignorées silencieusement.
  const usableLines = () =>
    lines.filter(l => l.produit && parseFloat(l.quantite) > 0)

  const validate = () => {
    const e = {}
    // QJR580 — en édition, le devis a déjà son client (lecture seule).
    if (!editId && !clientId && !leadId) e.client = 'Sélectionnez un lead ou un client'
    // L'étude industrielle exige la consommation réelle du client
    if (modeInstallation === 'industriel' && !(consoKwhDerivee > 0)) {
      e.conso = 'Mode industriel : renseignez la consommation mensuelle (kWh) '
        + 'ou les factures électriques — l\'étude en dépend.'
    }
    // ERR-QAC-KWH-SAISI-INCOHERENT-FACTURES (décision fondateur 30/09/2026) —
    // le kWh mensuel DÉCLARÉ sur la fiche du lead (celui que le serveur chiffre
    // en priorité, Q14) contredit ses factures (barème ÷ facture hors
    // [0,5 ; 2]) ⇒ enregistrement REFUSÉ, jamais un chiffrage silencieux. Le
    // serveur (`/atomic`, `replace-lines`) applique la même garde.
    if (!e.conso && selectedLead) {
      const ctlKwh = controlerKwhDeclare(selectedLead.conso_mensuelle_kwh, {
        factureHiver: selectedLead.facture_hiver,
        factureEte: selectedLead.facture_ete,
        eteDifferente: selectedLead.ete_differente,
      })
      if (ctlKwh && !ctlKwh.coherent) e.conso = MESSAGE_KWH_INCOHERENT
    }
    const orphan = lines.find(l =>
      !l.produit && parseFloat(l.quantite) > 0 && parseFloat(l.prix_unit_ttc) > 0)
    if (orphan) {
      e.lines = `Sélectionnez un produit du stock pour la ligne « ${orphan.designation || '—'} »`
    } else if (!usableLines().length) {
      e.lines = 'Au moins une ligne avec un produit et une quantité > 0'
    } else if (!accessoiresOnly) {
      // QX20 — un devis solaire DOIT contenir de l'équipement solaire cohérent
      // avec le marché. Résidentiel/industriel : ≥ 1 panneau ET ≥ 1 onduleur ;
      // agricole : ≥ 1 pompe. Échappatoire DOCUMENTÉE : cocher « Composition
      // libre » (accessoiresOnly, relabellée — incident fondateur 01/09 round
      // 2) désactive la garde pour un devis composé à la main (accessoires/
      // main-d'œuvre seuls, ou toute composition hors calculateur), MÊME sur
      // un devis « Hors réseau » — cette garde ne dépend jamais de `horsReseau`.
      const usable = usableLines()
      const has = (pred) => usable.some(l => pred(l.designation))
      if (modeInstallation === 'agricole') {
        // AGR130 — une pompe EXISTANTE n'a pas de ligne pompe (le kit n'en
        // pose pas) ; une pompe NEUVE exige une pompe ou son placeholder
        // « prix à renseigner » (ligne sans produit, jamais chiffrée à 0).
        const existante = pompageSaisie.mode_pompe === 'existante'
        const placeholderPompe = lines.some(l => !l.produit && isPompe(l.designation))
        if (!existante && !has(isPompe) && !placeholderPompe) {
          e.lines = 'Un devis de pompage doit contenir au moins une pompe. '
            + 'Utilisez « Auto-remplir » ou ajoutez une pompe, ou cochez '
            + '« Composition libre ».'
        }
      } else {
        const hasPanel = has(isPanel)
        // OFFGRID — un onduleur hors réseau compte comme onduleur : un devis
        // hors réseau qui ne porte QUE cette ligne (jamais réseau/hybride)
        // doit pouvoir s'enregistrer, sans obliger le vendeur à garder une
        // ligne hybride « pour passer la garde ».
        const hasInverter = has(d => isReseauInverter(d) || isHybridInverter(d) || isOffgridInverter(d))
        if (!hasPanel || !hasInverter) {
          const manque = [
            !hasPanel ? 'un panneau' : null,
            !hasInverter ? 'un onduleur' : null,
          ].filter(Boolean).join(' et ')
          e.lines = `Un devis solaire doit contenir au moins ${manque}. `
            + 'Utilisez « Auto-remplir » ou ajoutez ces lignes, ou cochez '
            + '« Composition libre ».'
        }
      }
    }
    // ERR-QAC-FACTURES-ECRAN-INVRAISEMBLABLES — les 12 factures partent comme
    // « réelles » (`entreesReellesEcran`) : une facture sous les lignes fixes
    // du compteur est REFUSÉE (le serveur la refuserait aussi, après
    // l'enregistrement des lignes) ; un écart avec la facture d'hiver du lead
    // se fait CONFIRMER une fois (second clic), jamais corrigé en silence.
    if (facturesSaisies) {
      const ctl = controlerFacturesSaisies(monthly, {
        factureHiverLead: selectedLead?.facture_hiver,
      })
      if (ctl.sousPlancher.length) {
        e.factures = `Facture(s) mensuelle(s) inférieure(s) aux lignes fixes du `
          + `compteur (${ctl.plancher.toFixed(2)} MAD TTC/mois) — mois `
          + `${ctl.sousPlancher.join(', ')}. Une facture réelle ne peut pas être `
          + 'aussi basse : corrigez la saisie (hiver/été ou détail mensuel).'
      } else if (ctl.ecartLead) {
        const signature = monthly.map(v => Number(v) || 0).join('|')
          + `#${ctl.ecartLead.lead}`
        if (facturesEcartConfirme.current !== signature) {
          facturesEcartConfirme.current = signature
          e.factures = `La facture d'hiver enregistrée (${Math.round(ctl.ecartLead.serie)} MAD) `
            + `s'écarte de celle du lead (${Math.round(ctl.ecartLead.lead)} MAD). `
            + 'Vérifiez la saisie, puis cliquez à nouveau pour confirmer.'
        }
      }
    }
    // Avertissement NON bloquant : le lead choisi est perdu et/ou archivé.
    // On le signale avant l'enregistrement sans jamais l'empêcher.
    const w = {}
    // QXMT — raccordement MT sans tarif exploitable : l'étude part SANS
    // économies ni payback (volontairement omis). C'est un AVERTISSEMENT, pas
    // une erreur : rien n'est rejeté, rien n'est corrigé à la place du vendeur.
    if (estMt && tarifMtApplique == null) {
      w.tensionMt = tarifMtDisponible()
        ? 'Raccordement MT sans répartition horaire : le devis sera enregistré '
          + 'avec une étude SANS économies ni payback (aucun chiffre n\'est '
          + 'supposé). Renseignez pointe / pleines / creuses pour les obtenir.'
        : 'Raccordement MT : le barème MT ONEE n\'est pas disponible en source '
          + 'officielle — l\'étude sera enregistrée sans économies ni payback.'
    }
    if (selectedLead && (selectedLead.perdu || selectedLead.is_archived)) {
      const flags = [
        selectedLead.perdu ? 'perdu' : null,
        selectedLead.is_archived ? 'archivé' : null,
      ].filter(Boolean).join(' et ')
      const nom = `${selectedLead.nom}${selectedLead.prenom ? ` ${selectedLead.prenom}` : ''}`.trim()
      w.lead = `Attention : le lead « ${nom} » est ${flags}. `
        + 'Vous pouvez tout de même créer ce devis.'
    }
    setWarnings(w)
    setErrors(e)
    return Object.keys(e).length === 0
  }

  // QJR66 (audit L3 du 29/08/2026) — LA SOUS-CLÉ D'ÉTUDE DU MARCHÉ COURANT,
  // et RIEN D'AUTRE.
  //
  // CE QUI SE PASSAIT. `persisterDevis` reconstruisait `etude_params` DE ZÉRO
  // et le posait en bloc dans le corps du devis : toute clé que l'écran ne
  // recompose pas lui-même — `factures_mensuelles_reelles`, `gamme`, et les
  // quatre blocs écrits par les rafraîchisseurs serveur (`etude_horaire`,
  // `dimensionnement`, `profils_comparatifs`, `simulation`) — DISPARAISSAIT à
  // la sauvegarde suivante du vendeur.
  //
  // CE QUI SE PASSE MAINTENANT. Le corps du devis ne porte plus d'étude du
  // tout ; l'écran écrit UNIQUEMENT la sous-clé de SON marché, par l'endpoint
  // de FUSION `PATCH /ventes/devis/<id>/etude-params/` (QJR62) — seules les
  // clés envoyées bougent, les autres restent intouchées bit à bit.
  //   • TOUS LES MARCHÉS — les ENTRÉES RÉELLES tapées par le vendeur sur CET
  //     écran, et elles seules : les 12 factures du client, la consommation
  //     annuelle et le distributeur (voir `entreesReellesEcran` ci-dessous).
  //     ARBITRAGE ORCHESTRATEUR (QJR66, 29/08/2026) : « zéro perte ». Une
  //     première version de cette tâche n'écrivait RIEN en résidentiel, ce qui
  //     re-rouvrait le trou N1 — un devis créé À LA MAIN (hors devis auto d'un
  //     lead) n'avait plus AUCUN moyen d'alimenter
  //     `factures_mensuelles_reelles`, la donnée la plus précieuse du dossier,
  //     et le moteur PDF retombait sur une facture « avant » reconstruite
  //     depuis l'économie SUPPOSÉE (proxy circulaire). Ces trois clés sont des
  //     ENTRÉES déclarées `ECRAN` dans le schéma : c'est leur chemin.
  //     Le RESTE des entrées résidentielles (scénario, option recommandée)
  //     passe, lui, par le REGISTRE DE SURCHARGES D12 — pas par ici.
  //   • industriel / commercial — les cinq dérivées de leur étude
  //     d'autoconsommation (+ la catégorie commerciale, qui EST l'entrée de
  //     cette étude : elle choisit l'archétype de part diurne).
  //   • agricole — le bloc pompage (pompe, HMT, débit à la HMT, m³/jour,
  //     champ kWc, méthode d'irrigation).
  //   • résidentiel — RIEN DE PLUS que les entrées réelles ci-dessus : le
  //     serveur est propriétaire de son étude (dimensionnement, bloc horaire,
  //     profils, calepinage).
  // Le schéma serveur (`apps/ventes/domain/etude_schema.py`) est la SEULE
  // porte : une clé hors schéma ou une clé DÉRIVÉE dont l'écran n'est pas
  // propriétaire (`puissance_kwc`, `production_annuelle`,
  // `economies_annuelles`, `etude_horaire`…) est refusée en 400 français.
  // C'est voulu : ces chiffres-là appartiennent à l'étape qui les CALCULE.
  //
  // `null` RETIRE la clé (règle Z2) : une étude qui n'est plus calculable est
  // retirée, jamais laissée périmée — on envoie donc le bloc du marché même
  // quand l'étude est indisponible, pour effacer un chiffre devenu faux.
  //
  // LES ENTRÉES RÉELLES DE L'ÉCRAN — tous marchés (arbitrage « zéro perte »).
  // Reprend MOT POUR MOT les deux règles d'avant, sans en inventer une
  // troisième : le seed N1 (`facturesSaisies` — jamais les valeurs D'EXEMPLE
  // de `DEFAULT_MONTHLY_BILLS`) et la règle QF4 de `buildEtudeParamsChoice`
  // (une conso annuelle déjà connue ⇒ on n'envoie que le distributeur ; une
  // facture réelle saisie ⇒ les deux ; sinon le distributeur seulement s'il
  // n'est pas le défaut ONEE).
  //
  // AUCUNE CLÉ N'EST ENVOYÉE À `null` ICI : `null` SUPPRIME (règle Z2), et
  // supprimer les factures semées par le devis auto parce que CE vendeur n'a
  // rien retapé serait exactement la perte que cette tâche referme. Une clé
  // que l'écran ne connaît pas est simplement ABSENTE du corps — la fusion la
  // laisse alors intacte, bit à bit.
  // QF7 / QJR66 — LES CHOIX DU COMMERCIAL, tous marchés. L'ancien
  // `buildEtudeParamsChoice`, à la sémantique près : le scénario et l'option
  // recommandée AFFICHÉS À L'ÉCRAN sont persistés pour TOUS les modes
  // (résidentiel / industriel / commercial / agricole), pas seulement quand
  // une étude existe.
  //
  // POURQUOI C'EST BLOQUANT. `etude_params['scenario']` est LU par
  // `quote_engine/builder.py` (`_stored_choice`) et par `utils/options.py`
  // pour décider quelles lignes composent l'option vendue. Absent, le moteur
  // prend la branche « artefact » et TOTALISE TOUTES les lignes — les deux
  // onduleurs ET la batterie d'un devis « Les deux » — pendant que le total
  // d'affichage montre, lui, l'option choisie : DEUX chiffres contradictoires
  // sous les yeux du client. Le retirer du corps du devis (QJR66) sans le
  // remettre sur le canal de fusion ouvrait exactement ce trou.
  //
  // JAMAIS `null` : ces deux clés ne valent que quand l'écran les possède
  // réellement — et il les possède toujours (un défaut de mode, ou le choix
  // explicite du vendeur). Le câblage vers le REGISTRE D12 (`scenario`,
  // `recommended_option` sont des chemins surchargeables) est un chantier M5 :
  // en attendant, l'écran reste leur écrivain, par le canal validé.
  //
  // QJ31 (mode A) — ×N VILLAS IDENTIQUES. `selectors.py` multiplie le total du
  // devis par `etude_params['nombre_proprietes']` (défaut 1) : sans écrivain,
  // un devis ×4 rendait le total d'UNE villa. C'est le SEUL choix de ce bloc
  // qui s'envoie à `null` — et c'est VOULU : le sélecteur multi-villa est
  // toujours dans un état défini, donc « pas de ×N à l'écran » signifie
  // vraiment « ce devis est mono-système », et `null` RETIRE la clé (règle Z2)
  // au lieu de laisser traîner le ×4 d'hier. Contraste avec les factures
  // réelles, où « rien de retapé » ne veut PAS dire « pas de factures » — d'où
  // l'absence de clé là-bas. Le mappeur `?edit=` repose le mode depuis cette
  // même clé (plus bas), sans quoi rouvrir un devis ×4 l'aurait remis à 1.
  const choixEcran = () => {
    const choix = {}
    if (scenario) choix.scenario = scenario
    if (recommended) choix.recommended_option = recommended
    const n = multiMode === 'multiplier' ? parseInt(nombreProprietes, 10) : 1
    choix.nombre_proprietes = (Number.isFinite(n) && n > 1) ? n : null
    return choix
  }

  const entreesReellesEcran = (consoDejaConnue) => {
    const entrees = {}
    if (facturesSaisies) {
      entrees.factures_mensuelles_reelles = monthly.map(v => parseFloat(v) || 0)
    }
    // Conso annuelle : la source la plus DIRECTE d'abord (l'étude du marché,
    // qui descend de la saisie « consommation »), puis la facture réelle QF4,
    // puis la dérivation depuis les 12 factures (kwhFromBill au barème réel du
    // distributeur choisi — même patron que `autoQuote.js`, jamais un chiffre
    // supposé).
    //
    // COUV-HOR (29/09/2026) — une facture/kWh TAPÉE dans cette session reste
    // souveraine ; une conso STOCKÉE qui était une saisie repart telle quelle
    // (exacte, sans la dérive ×12 de l'aller-retour kWh/mois) ; sinon les
    // factures (celles de l'écran, à défaut celles du devis) sont RE-DÉRIVÉES
    // au barème — jamais la valeur réaffichée par `?edit=` réécrite à
    // l'identique (DEV-202609-0113 : 198 000 MAD ÷ 1,20 = 165 000 kWh revenait
    // à chaque enregistrement, étiqueté 'onee').
    const stockee = consoStockee.current
    let conso = consoDejaConnue ?? null
    let auBareme = false   // conso calculée ICI au barème de `distributeur`
    if (conso == null && realBillSaisi && consoAnnuelleReelle > 0) {
      conso = consoAnnuelleReelle
      auBareme = realBillMode === 'mad'
    }
    if (conso == null && stockee && !stockee.descendDesFactures) conso = stockee.valeur
    const factures = entrees.factures_mensuelles_reelles || stockee?.factures || null
    if (conso == null && factures) {
      const derivee = consoAnnuelleDepuisFactures(factures, distributeur)
      if (derivee > 0) { conso = derivee; auBareme = true }
    }
    if (conso == null && consoAnnuelleReelle > 0) {
      conso = consoAnnuelleReelle
      auBareme = realBillMode === 'mad'
    }
    if (conso != null) {
      entrees.conso_annuelle = conso
      // Jamais un distributeur que personne n'a choisi sur une conso que
      // l'écran n'a pas calculée à son barème.
      if (auBareme || distributeurChoisi) entrees.distributeur = distributeur
    } else if (distributeur && distributeur !== 'onee') {
      entrees.distributeur = distributeur
    }
    return entrees
  }

  // QJR542 — la projection « étude du marché → clés etude_params légales »
  // vit dans UNE fonction pure partagée avec le devis automatique
  // (`features/ventes/quote/etudeMarcheBloc.js`) ; ici on ne fait que lui
  // passer l'état de l'écran. Résidentiel ⇒ `null` si rien à écrire (aucun
  // appel, voir `persisterDevis`).
  // QJR658 — l'état d'écran à enregistrer, dans la forme de `etatDevis.js`.
  const etatEcran = () => ({
    mode: modeInstallation, dateValidite, tauxTva, discountPct, note, prixCible,
    echeancier: echeancierSaisie, echeancierAEnvoyer: echeancierAEnvoyer.current,
    lignes: lines, multiMode, nombreProprietes, scenario, recommendedChoice,
    partDiurne: dayUsage, tension: tensionRaccordement, repartitionMt,
    // QJR575 — la sentinelle « Non précisée » se persiste null.
    categorieCommerciale: categorieCommerciale === CATEGORIE_NON_PRECISEE ? null : categorieCommerciale,
    commercialAnswers,
    pompe: {
      cv: pompeCv, hmt: pompeHmt, debit: pompeDebit, type: pompeType,
      alim: pompeAlim, profondeur: pompeProfondeur, distance: pompeDistance,
    },
    pompageSaisie,
    farm: {
      irrigation: farmIrrigation, region: farmRegion, crop: farmCrop,
      surfaceHa: farmSurfaceHa,
      hmtStatic: farmHmtStatic, hmtDrawdown: farmHmtDrawdown,
      attestation: attestationAgricole,
    },
    saisiesEco: ecoAvecCalendrier,
  })
  const blocEtudeMarche = () => etatVersEcritures(etatEcran(), {
    etude: modeInstallation === 'industriel' ? etudeIndustrielle : etudeCommerciale,
    recommended,
    entrees: entreesReellesEcran,
  }).etude

  // Cœur de persistance extrait de `handleSubmit` (aucun changement de
  // comportement) : construit le payload + les lignes, écrit le devis (édition
  // atomique ou création atomique), attache l'étude du marché par l'endpoint de
  // fusion (QJR66 ci-dessus), et RENVOIE {devisId, devisCree} en cas de succès
  // — null sinon (le message HUMAIN est déjà posé dans `errors.submit`).
  // PV23bis (fondateur 20/08) — `ouvrirConception3D` ci-dessous réutilise
  // EXACTEMENT ce même chemin d'écriture pour le bouton « Concevoir en 3D » :
  // un seul endroit qui sait enregistrer un devis, jamais une seconde logique
  // dupliquée.
  // QJR553 — `surcharge` (optionnelle, « Revenir à cette version ») :
  // `{ lignes, entete, etude_params }` d'un instantané rejoués par CE MÊME
  // chemin d'écriture (replace-lines + jeton) — jamais un second chemin.
  const persisterDevis = async (surcharge = null) => {
    setSaving(true)
    try {
      // QJR515 — `statut` n'est JAMAIS dans l'en-tête d'édition (un envoyé ne
      // repasse jamais en brouillon) : posé seulement à la création ci-dessous.
      // QJR658 — en-tête et lignes construits par le module pur
      // (`etatVersEcritures`), le même que l'aller-retour testé.
      const ecritures = etatVersEcritures(etatEcran())
      const payload = { ...ecritures.entete }
      // QX21 — lignes construites UNE fois (mêmes champs qu'avant : HT dérivé du
      // TTC saisi au taux DE LA LIGNE, groupe villa en mode « villas »).
      // XSAL14 — lignes retenues : produits utilisables + lignes de section/note
      // (intitulé non vide). L'ordre visuel est conservé (ordre = index) pour
      // intercaler les intertitres au bon endroit. Une ligne section/note ne
      // porte ni produit ni prix.
      // QJR523 — payload construit par le mappeur UNIQUE (lignesEcran.js) :
      // prix HT dérivé du TTC au taux DE LA LIGNE, groupe villa en mode
      // « villas », option / type / ordre / variante / verrous manuels
      // (QJR65 / D12, QJR218) et rôle stocké.
      const lignesPayload = ecritures.lignes

      let devisId
      let devisCree = null
      if (editDevis) {
        // QJR544 — ÉDITION ATOMIQUE : en-tête + lignes + choix d'écran en UN
        // appel, UNE transaction serveur (replace-lines). Un échec ne change
        // RIEN (ni en-tête, ni lignes) ; plus de PATCH d'en-tête séparé.
        // QJR624 — l'échéancier part dans `entete` (contrat QJR504) : posé
        // par `etatVersEcritures` quand il est propre au devis ou touché.
        const extra = {
          entete: surcharge?.entete ? { ...payload, ...surcharge.entete } : payload,
          etude_params: surcharge?.etude_params ?? choixEcran(),
        }
        // QJR549 — le jeton part avec l'édition ; « Enregistrer quand même »
        // (après un 409) renvoie UNE fois sans jeton.
        if (jetonRef.current && !forcerSansJeton.current) {
          extra.expected_updated_at = jetonRef.current
        }
        forcerSansJeton.current = false
        const reponse = await ventesApi.replaceLignesDevis(
          editDevis.id, surcharge?.lignes ?? lignesPayload, extra)
        armerJeton(reponse?.data?.updated_at)
        setConflitVerrou(null)
        devisId = editDevis.id
        devisCree = { reference: editDevis.reference }
      } else {
        // QX21 — CRÉATION ATOMIQUE : devis + lignes en UN commit serveur → plus
        // de brouillon orphelin/partiel si la connexion est coupée en cours de
        // sauvegarde. Lead prioritaire : le client est résolu côté serveur.
        payload.statut = 'brouillon'
        if (leadId) payload.lead = parseInt(leadId)
        else payload.client = parseInt(clientId)
        // ERR-QAH-VENTES-TOTAL-DIVERGENCE-CREATION — les CHOIX de l'écran
        // (scénario, option recommandée, ×N) partent AVEC la création : ils
        // décident de l'option que suit l'argent, donc du total que renvoie le
        // serveur. Envoyés seulement après (PATCH `etude-params` ci-dessous),
        // la réponse de création totalisait TOUTES les lignes — les deux
        // onduleurs compris — et l'écran « Devis enregistré » affichait un prix
        // qu'aucun document ne porte. Le PATCH qui suit reste inchangé (il
        // repose les mêmes choix + les entrées réelles, sans bouger le total).
        const { data } = await ventesApi.createDevisAtomic({
          ...payload, etude_params: choixEcran(), lignes: lignesPayload,
        })
        devisId = data.id
        devisCree = data
      }

      // QJR66 — l'étude du marché courant part par l'endpoint de FUSION, APRÈS
      // les lignes : le serveur vient d'y recalculer ses propres blocs
      // (`rafraichir_etudes_du_devis`), et cette fusion ne touche QUE les clés
      // qu'elle envoie. Résidentiel ⇒ aucun appel.
      // QJR553 — une version restaurée porte SA propre étude (déjà rejouée
      // ci-dessus) : l'étude de l'écran courant ne la recouvre pas.
      const etudeMarche = surcharge ? null : blocEtudeMarche()
      if (etudeMarche) {
        try {
          const reponseEtude = await ventesApi.patchEtudeParams(devisId, etudeMarche)
          // QJR549 — cette écriture avance aussi le jeton : ré-armé.
          armerJeton(reponseEtude?.data?.updated_at)
        } catch (errEtude) {
          // Le devis EST enregistré : une étude refusée ne doit jamais faire
          // croire à un échec d'enregistrement (ni pousser à un second POST
          // qui créerait un doublon). On le DIT, en français, et on continue.
          const detail = errEtude?.response?.data?.detail
          toast.error(typeof detail === 'string'
            ? `Devis enregistré, étude non attachée : ${detail}`
            : "Devis enregistré, mais l'étude n'a pas pu être attachée.")
        }
      }

      // QJR572 — le registre suit l'écran : APRÈS l'enregistrement réussi
      // (lignes + choix d'écran), un chemin DÉJÀ surchargé dont la valeur
      // affichée a changé est reposé (ou rendu à l'automatique sur « Auto »).
      // Rien à la création, rien sans surcharge. `etude_params` reste écrit
      // (repli du moteur). Une erreur est DITE, l'enregistrement reste fait.
      if (editDevis && !surcharge) {
        const { patch, regenerer } = ecartsAuRegistre({
          scenario,
          recommended_option: recommendedChoice,
          'taille.nb_panneaux': nbPanneaux,
        }, overridesReg)
        try {
          if (Object.keys(patch).length) {
            const { data } = await ventesApi.poserOverrides(devisId, patch)
            setOverridesReg(data)
            armerJeton(data?.updated_at)
          }
          for (const chemin of regenerer) {
            const { data } = await ventesApi.regenererOverride(devisId, chemin)
            setOverridesReg(data)
            armerJeton(data?.updated_at)
          }
        } catch (errOv) {
          const msg = messageErreurOverrides(errOv)
          setOverridesErreur(msg)
          toast.error(`Devis enregistré, registre non mis à jour : ${msg}`)
        }
      }

      return { devisId, devisCree }
    } catch (err) {
      // QJR549 — 409 `devis_modifie` : quelqu'un (ou le catalogue) a écrit ce
      // devis depuis l'ouverture. Bannière NON bloquante, rien d'autre écrit.
      if (err?.response?.status === 409 && err?.response?.data?.code === 'devis_modifie') {
        setConflitVerrou({ par: err.response.data.updated_by_nom || '' })
        return null
      }
      // Message HUMAIN, jamais de JSON brut — et le formulaire reste vivant.
      const raw = err?.response?.data ?? err
      let msg
      if (raw?.lead) {
        msg = 'Ce lead n\'existe plus (supprimé entre-temps ?). '
          + 'La liste des leads a été rechargée — choisissez-en un autre.'
        setLeadId('')
        crmApi.getLeads()
          .then(r => setLeads(r.data.results ?? r.data)).catch(() => {})
      } else if (raw?.client) {
        msg = 'Ce client n\'existe plus. Choisissez un autre client ou un lead.'
        setClientId('')
        crmApi.getClients().then(r => setClients(r.data.results ?? r.data)).catch(() => {})
      } else if (raw?.code === 'kwh_incoherent_factures') {
        // ERR-QAC-KWH-SAISI-INCOHERENT-FACTURES — refus serveur : sous le champ.
        msg = typeof raw.detail === 'string' ? raw.detail : MESSAGE_KWH_INCOHERENT
        setErrors(prev => ({ ...prev, conso: msg }))
      } else if (Object.keys(erreursBaseLegaleServeur(raw, lines)).length) {
        // AGR218 — refus « base légale obligatoire à 0 % » : le message du
        // serveur s'affiche SOUS le champ de la ligne visée.
        const parLigne = erreursBaseLegaleServeur(raw, lines)
        setLines(ls => ls.map(l => (parLigne[l._key]
          ? { ...l, _erreurBaseLegale: parLigne[l._key] } : l)))
        msg = raw.detail
      } else if (typeof raw?.detail === 'string') {
        msg = raw.detail
      } else {
        msg = 'L\'enregistrement a échoué — vérifiez les champs et réessayez.'
      }
      setErrors(prev => ({ ...prev, submit: msg }))
      return null
    } finally {
      setSaving(false)
    }
  }

  // QJR547 — « Enregistrer comme modèle » photographie l'ÉCRAN : le devis
  // est d'abord enregistré par le chemin unique (`persisterDevis`), sans
  // quitter l'écran ; un échec (validation ou serveur) → aucun modèle.
  const enregistrerAvantModele = async () => {
    if (!validate()) return false
    const res = await persisterDevis()
    if (!res) return false
    clear(); marquerEnregistre()
    return true
  }

  // QJR553 (D-QJR5-7) — « Revenir à cette version » : l'écran est rechargé
  // depuis le contenu de l'instantané (lignes, remise) puis enregistré par le
  // chemin NORMAL (replace-lines avec entete + etude_params + jeton) ; sur un
  // envoyé, c'est une correction sur place tracée (QJR518). Puis l'écran
  // relit le devis enregistré.
  const [versionHistorique, setVersionHistorique] = useState(0)
  const revenirAVersion = async (snap) => {
    const contenu = snap?.contenu || {}
    // Le lot (propre à UN devis) ne voyage pas : l'écran ne gère pas les lots.
    const lignesSnap = (contenu.lignes || []).map((l) => {
      const copie = { ...l }
      delete copie.lot
      return copie
    })
    if (!lignesSnap.length) return
    const ok = await confirm({
      title: 'Revenir à cette version ?',
      description: 'Le devis reprend les lignes, la remise et l\'échéancier de cette '
        + 'version, puis il est enregistré. La version actuelle reste dans l\'historique.',
      confirmLabel: 'Revenir à cette version',
    })
    if (!ok) return
    setLines(withKeys(lignesServeurVersEcran(lignesSnap, tauxTva)))
    if (contenu.remise_globale != null) {
      setDiscountPct(String(parseFloat(contenu.remise_globale) || 0))
    }
    const entete = {}
    if (contenu.remise_globale != null) entete.remise_globale = contenu.remise_globale
    if (Array.isArray(contenu.echeancier)) entete.echeancier = contenu.echeancier
    const etude = contenu.etude && Object.keys(contenu.etude).length ? contenu.etude : undefined
    const res = await persisterDevis({ lignes: lignesSnap, entete, etude_params: etude })
    if (res) {
      toast.success('Version restaurée et enregistrée.')
      clear()
      setVersionHistorique(n => n + 1)
      setRechargeEdit(n => n + 1)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    const res = await persisterDevis()
    if (res) { clear(); marquerEnregistre(); finish(res.devisId, res.devisCree) }
  }

  // PV23bis (fondateur 20/08) — « Concevoir en 3D » depuis l'écran de devis :
  // l'outil 3D travaille désormais TOUJOURS SUR LE DEVIS (jamais un aller-
  // retour lead déconnecté qui en créerait un second, cf. le bouton
  // ci-dessous). Le formulaire est d'abord enregistré (création ou édition,
  // via `persisterDevis` ci-dessus) pour que l'outil s'ouvre attaché à un
  // devis réel et resynchronise ses lignes (PV21) ; le chemin lead ne
  // survit que comme repli « conception avant devis valide », quand le
  // formulaire n'est pas encore un devis enregistrable.
  const ouvrirConception3D = async () => {
    if (!validate()) {
      if (leadId && selectedLead) navigate(`/devis-design/${selectedLead.id}`)
      return
    }
    const res = await persisterDevis()
    if (!res) return
    clear()
    marquerEnregistre()
    navigate(`/ventes/devis/${res.devisId}/design`)
  }

  const selectedClient = clients.find(c => String(c.id) === String(clientId))

  // ZSAL9 — avertissements de vente (« sale warnings ») : message du client
  // sélectionné + des produits présents dans les lignes. Purement informatif à
  // l'écran (une bannière non intrusive) ; le blocage éventuel est appliqué
  // côté serveur à l'acceptation/facturation (garde XFAC28-like).
  const saleWarnings = useMemo(() => {
    const out = []
    if (selectedClient?.avertissement_vente) {
      out.push({
        key: `client-${selectedClient.id}`,
        cible: selectedClient.nom || 'Client',
        message: selectedClient.avertissement_vente,
        bloquant: !!selectedClient.avertissement_bloquant,
      })
    }
    const seen = new Set()
    for (const l of lines) {
      if (!l.produit || seen.has(l.produit)) continue
      seen.add(l.produit)
      const p = produits.find(x => String(x.id) === String(l.produit))
      if (p?.avertissement_vente) {
        out.push({
          key: `produit-${p.id}`,
          cible: p.nom || 'Produit',
          message: p.avertissement_vente,
          bloquant: !!p.avertissement_bloquant,
        })
      }
    }
    return out
  }, [selectedClient, lines, produits])

  // QC1 — recherche client sur les données propres (endpoint /search/). On ne
  // retient QUE les correspondances de source « client » : le devis a besoin
  // d'un id client réel (un fournisseur/lead n'est pas sélectionnable ici). Le
  // client choisi est ajouté à la liste locale s'il n'y figure pas déjà.
  const onSearchClient = async (query) => {
    const hits = await searchCompanies(query, { searcher: crmApi.searchClients })
    const clientHits = hits.filter(h => h.source === 'client')
    setClients((cs) => {
      const known = new Set(cs.map(c => String(c.id)))
      const news = clientHits
        .filter(h => !known.has(String(h.id)))
        .map(h => ({ id: h.id, nom: h.nom, adresse: h.adresse, telephone: h.telephone }))
      return news.length ? [...cs, ...news] : cs
    })
    return clientHits.map(h => ({ value: String(h.id), label: h.nom }))
  }

  // ── KPI multi-marchés : étude industrielle, pompage, prix/kWc, marge ──
  const kpiTotal = avecRec && showAvec ? totals.totalAvec : totals.totalSans
  const kpiTotalBrut = avecRec && showAvec ? totals.totalAvecBrut : totals.totalSansBrut

  // APX16 — écart entre les DEUX options, visible PENDANT la construction du
  // devis (le rail n'affichait qu'un total, même en scénario double).
  // Dérivé des totaux déjà calculés : aucun calcul nouveau.
  const ecartOptions = (showSans && showAvec)
    ? Math.round(totals.totalAvec - totals.totalSans)
    : null
  const ecartOptionsPct = (ecartOptions != null && totals.totalSans > 0)
    ? Math.round((ecartOptions / totals.totalSans) * 100)
    : null

  // Consommation industrielle : saisie directe, sinon dérivée des factures
  // au barème national, la MÊME que le balayage (QJR665, décision fondateur
  // 01/10 — jamais moyenne ÷ prix kWh). L'étude EXIGE une consommation réelle.
  // QJR582 — la facture réelle « recommandée » (QF4) passe AVANT la
  // dérivation des factures quand le champ d'étude est vide : sinon validate()
  // bloquait un devis industriel où seule elle était remplie. La souveraineté
  // COUV-HOR (realBillSaisi, entreesReellesEcran) reste intacte.
  const consoKwhDerivee = (parseFloat(consoMensuelle) || 0)
    || (realBillSaisi && consoAnnuelleReelle > 0 ? Math.round(consoAnnuelleReelle / 12) : 0)
    || (facturesSaisies ? consoMensuelleEtudeCI({
      factures: monthly, mode: modeInstallation,
      distributeurDeclare: distributeurChoisi ? distributeur : selectedLead?.distributeur,
    }) : 0)

  // QJR568 — les deux études C&I (persistées) au kWc FACTURÉ des lignes.
  const etudeIndustrielle = (modeInstallation === 'industriel' && kwpLignes > 0
      && consoKwhDerivee > 0)
    ? computeEtudeIndustrielle({
        kwp: kwpLignes, consoMensuelleKwh: consoKwhDerivee,
        dayUsagePct: dayUsage, totalTtc: kpiTotal,
        kwhPrice: quoteLogic.kwhPrice, efficiency: quoteLogic.efficiency,
        injectionEnabled, ...etudeTension,
      })
    : null

  // QX44 — étude COMMERCIALE : même moteur d'autoconsommation que l'industriel,
  // mais le day-share vient de l'ARCHÉTYPE de la catégorie (hôtel 55 ≠ bureau 80)
  // → à facture égale, une étude hôtel diffère d'une étude bureau.
  const etudeCommerciale = (modeInstallation === 'commercial' && kwpLignes > 0
      && consoKwhDerivee > 0)
    ? computeEtudeIndustrielle({
        kwp: kwpLignes, consoMensuelleKwh: consoKwhDerivee,
        dayUsagePct: commercialDayShare(categorieCommerciale), totalTtc: kpiTotal,
        kwhPrice: quoteLogic.kwhPrice, efficiency: quoteLogic.efficiency,
        injectionEnabled, ...etudeTension,
      })
    : null
  // Étude « industriel/commercial » unifiée pour l'aperçu écran + la persistance.
  const etudeCI = etudeIndustrielle || etudeCommerciale

  // Disponibilité de l'option « avec batterie » (règle : jamais sans onduleur)
  const avecDispo = avecBatterieAvailability(lines, produits, kwp)
  const showAvecWarning = showAvec && lines.length > 0 && !avecDispo.available

  // (Dimensionnement pompage : déclaré plus haut, avant handleAutoFill —
  // eslint no-use-before-define, recalage L-2OPT 25/08.)


  // AGR129 — le besoin en eau et l'eau livrée viennent de l'aperçu SERVEUR
  // (`apercuPompage`, AGR127) : plus de besoin FAO-56 calculé dans le
  // navigateur (le jumeau `agronomy.js` disparaît avec AGR131).

  // QJR568 — prix/kWc et prix cible au kWc FACTURÉ des lignes.
  const pkwc = prixParKwc(kpiTotal, kwpLignes)
  const buyCost = useMemo(() => computeBuyCost(lines, produits), [lines, produits])
  const marge = buyCost != null ? Math.round(kpiTotal - buyCost) : null

  const applyPrixCible = () => {
    const pct = discountForTarget(prixCible, kwpLignes, kpiTotalBrut)
    if (pct == null) return
    setDiscountPct(String(Math.max(0, pct)))
  }

  // Réinitialiser : recharge la page, comme le bouton du simulateur
  const handleReset = async () => {
    const ok = await confirm({
      title: 'Réinitialiser le formulaire ?',
      description: 'Toutes les saisies en cours seront perdues.',
      confirmLabel: 'Réinitialiser',
    })
    if (ok) window.location.reload()
  }

  // EZ3 — PANNEAU DE SUCCÈS : la création ne se termine plus par un renvoi sur
  // la liste nue. Le devis fraîchement créé s'annonce (numéro + total) et
  // propose l'action SUIVANTE évidente. « Envoyer par WhatsApp » ouvre la liste
  // sur ce devis précis AVEC l'aperçu WhatsApp déjà ouvert (le flux existant de
  // DevisList, jamais un second) — un clic ici, un clic « Ouvrir WhatsApp ».
  if (succes && !embedded) {
    return (
      <div className="page gen-page">
        <Card className="mx-auto max-w-xl" data-testid="devis-succes">
          <CardContent className="flex flex-col gap-4 pt-6 text-center">
            <div>
              <p className="text-sm text-muted-foreground">Devis enregistré</p>
              <p className="font-display text-xl font-bold">{succes.reference || '—'}</p>
              {succes.total != null && (
                <p className="num mt-1 text-2xl font-semibold">{formatMoney(succes.total)}</p>
              )}
            </div>
            <div className="flex flex-col gap-2 sm:flex-row sm:justify-center">
              <Button
                onClick={() => navigate(`/ventes/devis?devis=${succes.id}&envoyer=1`)}
                data-testid="succes-whatsapp"
              >
                <Send /> Envoyer par WhatsApp
              </Button>
              <Button
                variant="outline"
                onClick={() => navigate(`/ventes/devis?devis=${succes.id}&apercu=1`)}
                data-testid="succes-apercu"
              >
                <Eye /> Aperçu du PDF
              </Button>
              <Button
                variant="ghost"
                onClick={() => navigate(`/ventes/devis?devis=${succes.id}`)}
                data-testid="succes-liste"
              >
                Retour à la liste
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // QJR101 — le branchement des trois panneaux raccordés au réseau
  // (résidentiel / industriel / commercial). QUE des props : aucun calcul ne
  // descend ici, l'état et les gestes restent définis ci-dessus.
  const socleFactures = {
    marche: modeInstallation,
    fHiver, setFHiver, fEte, setFEte, syncBillEstimator,
    onHiverPaste, onEtePaste, handleEstimerMois, errors, monthly, setMonth,
    distributeur, setDistributeur: choisirDistributeur, realBillMode, setRealBillMode,
    realBillMad, setRealBillMad: saisirRealBillMad,
    realBillKwh, setRealBillKwh: saisirRealBillKwh,
    onRealBillPaste, consoAnnuelleReelle,
  }
  // QJR101 — les entrées d'étude que l'industriel et le commercial partagent.
  const socleEtudeReseau = {
    consoMensuelle, setConsoMensuelle, injectionEnabled, setInjectionEnabled,
    tensionRaccordement, dispatchSizing, estMt, repartitionMt, setPartMt,
    tarifMtApplique,
  }

  return (
    <div className={embedded ? 'gen-embedded' : 'page gen-page'}>
      {/* VX136 — formulaire-fleuve (2319+ l.) : barre de progression de
          scroll native, `scroll(nearest)` suit le conteneur qui défile
          réellement (`.layout-content` en page pleine, le Sheet englobant
          quand `embedded` dans LeadDevisPanel). */}
      <ScrollProgress />
      {/* APX11 — en-tête unique VX28 + accent Ventes (le `<h2>` est conservé :
          les ancres e2e `getByRole('heading')` ne bougent pas). */}
      {!embedded && (
        <PageHeader
          style={VENTES_ACCENT_STYLE}
          className="app-accent-rail"
          icon={FileText}
          title="Générateur de Devis Solaire"
          subtitle={editDevis ? `Édition — ${editDevis.reference ?? 'devis existant'}` : 'Nouveau devis · tout est en TTC'}
          actions={(
            <Button variant="outline" onClick={() => navigate('/ventes/devis')}>
              <ArrowLeft /> Retour aux devis
            </Button>
          )}
        />
      )}

      {/* VX16 — mise en page à deux colonnes sur lg+ : le formulaire à gauche,
          un rail récapitulatif STICKY à droite. Sur mobile/tablette, layout
          inchangé (le rail est masqué, les actions restent dans le formulaire). */}
      <div className="lg:flex lg:items-start lg:gap-6">
      {/* noValidate : aucune contrainte navigateur — toute valeur saisie est
          acceptée telle quelle (les steps ne servent qu'aux flèches). */}
      <form id="gen-form" onSubmit={handleSubmit} noValidate className="flex flex-col gap-4 lg:flex-1 lg:min-w-0">
        {editDevis?.statut === 'envoye' && (
          <div
            data-testid="devis-envoye-banner"
            role="status"
            className="rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning"
          >
            Devis envoyé{editDevis.date_envoi ? ` le ${formatDate(editDevis.date_envoi)}` : ''} :
            vos corrections seront visibles sur le lien de la proposition ; un PDF déjà envoyé
            par email ou WhatsApp n'est pas mis à jour — renvoyez-le si besoin. Le statut reste Envoyé.
          </div>
        )}
        {/* QJR549 (ex-DevisForm VX243c) — bannière NON bloquante : le devis a
            été enregistré ailleurs pendant cette édition (409 devis_modifie). */}
        {conflitVerrou && (
          <div
            data-testid="devis-verrou-banner"
            role="alert"
            className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning"
          >
            <span>
              Modifié par {conflitVerrou.par || 'un autre utilisateur'}
              {' '}pendant votre édition — vérifiez avant d'enregistrer.
            </span>
            <span className="flex gap-2">
              <Button
                type="button" size="sm" variant="outline"
                onClick={() => { setConflitVerrou(null); clear(); setRechargeEdit(n => n + 1) }}
              >
                Revoir
              </Button>
              <Button
                type="button" size="sm" variant="outline"
                onClick={() => {
                  forcerSansJeton.current = true
                  setConflitVerrou(null)
                  handleSubmit({ preventDefault: () => {} })
                }}
              >
                Enregistrer quand même
              </Button>
            </span>
          </div>
        )}
        {/* QJR540 (ex-DevisForm VX250) — lecture PURE du statut chargé : ne
            change jamais un statut (règle #4). */}
        {editDevis?.statut === 'envoye' && (
          <p
            data-testid="devis-attente-signature"
            role="status"
            className="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-warning"
          >
            En attente de signature client
          </p>
        )}
        {/* QJR540 (ex-DevisForm VX159/VX250) — compteurs dérivés du devis
            déjà chargé : zéro appel réseau nouveau. */}
        {editDevis?.id && (
          <RelationCounters
            counters={[
              {
                label: 'factures liées',
                count: editDevis.factures_liees?.length ?? 0,
                to: `/ventes/factures?q=${encodeURIComponent(editDevis.client_nom ?? '')}`,
              },
              { label: 'bon de commande', count: editDevis.bon_commande_etat ? 1 : 0 },
              {
                label: 'chantier',
                count: editDevis.chantier ? 1 : 0,
                to: editDevis.chantier ? `/chantiers?id=${editDevis.chantier.id}` : undefined,
              },
            ]}
          />
        )}
        {brouillonProposable && (
          <div
            data-testid="draft-restore-banner"
            className="flex flex-col gap-2 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning sm:flex-row sm:items-center sm:justify-between"
          >
            <span>
              Un brouillon non enregistré du{' '}
              {(() => {
                try { return formatDateTime(restored.savedAt) }
                catch { return 'précédent' }
              })()}{' '}
              a été retrouvé.
            </span>
            <div className="flex gap-2">
              <Button type="button" size="sm" variant="outline" onClick={handleRestoreDraft}>
                Reprendre le brouillon
              </Button>
              <Button type="button" size="sm" variant="ghost" onClick={discard}>
                Ignorer
              </Button>
            </div>
          </div>
        )}
        {/* EZ4 — la confiance vient de la CONTINUITÉ VISIBLE (patron
            Docs/Notion) : tant qu'on ne voit rien, on ne sait pas si le travail
            est à l'abri. Discret, jamais bloquant. */}
        {savedAt && (
          <p
            data-testid="draft-saved-indicator"
            className="text-xs text-muted-foreground"
            role="status"
          >
            Brouillon enregistré à{' '}
            {(() => {
              try {
                return new Date(savedAt).toLocaleTimeString('fr-FR', {
                  hour: '2-digit', minute: '2-digit',
                })
              } catch { return 'l’instant' }
            })()}
          </p>
        )}
        {refsLoading && (
          <div className="rounded-lg border border-info/30 bg-info/10 p-3 text-sm text-info">
            Chargement des données (leads, clients, produits)…
          </div>
        )}
        {loadFailed.length > 0 && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            Échec du chargement : {loadFailed.join(', ')}. Vérifiez votre connexion puis rechargez la page.
          </div>
        )}
        {/* ZSAL9 — avertissements de vente (client/produits) : bannière non
            intrusive ; un avertissement bloquant est signalé mais n'empêche pas
            la saisie (le blocage réel est côté serveur à l'acceptation). */}
        {saleWarnings.length > 0 && (
          <div
            data-testid="sale-warnings"
            className="flex flex-col gap-1 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning"
          >
            {saleWarnings.map(w => (
              <div key={w.key}>
                <span className="font-medium">{w.cible} :</span> {w.message}
                {w.bloquant && (
                  <span className="ml-1 font-medium">
                    (bloquant — un responsable devra passer outre)
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
        {/* ── Mode d'installation (marché) ── */}
        <Card>
          <GenCardHeader icon={Target} title="Marché / Mode d'installation" />
          <CardContent className="pt-4">
            <Segmented
              className="flex-wrap"
              options={MODE_OPTIONS}
              value={modeInstallation}
              onChange={(v) => { marquerMarcheTouche(); onModeChangeUi(v) }}
            />
            {modeInstallation === 'residentiel' && kwp > 36 && (
              <div className="mt-3 rounded-lg border border-info/30 bg-info/10 p-3 text-sm text-info">
                Ce système fait {formatNumber(kwp, { decimals: 2 })} kWc — au-delà de l'échelle résidentielle.
                Le mode Industriel ou Commercial produira un document plus adapté
                (étude d'autoconsommation, option unique). Vous pouvez ignorer cette suggestion.
              </div>
            )}
            {showAvecWarning && (
              <div className="mt-3 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
                Option « avec batterie » indisponible pour ce système : {avecDispo.reason}.
                Le PDF sera un document à option unique (sans batterie) — jamais une
                option partielle silencieuse.
              </div>
            )}
            {showAvec && lines.length > 0 && avecDispo.batterieDifferee && (
              <div className="mt-3 rounded-lg border border-info/30 bg-info/10 p-3 text-sm text-info">
                Option « avec » sans batterie chiffrée : le document la présente comme
                « Hybride, batterie plus tard » (onduleur hybride seul, économies
                calculées sans stockage). Le client pourra ajouter la batterie ensuite.
              </div>
            )}
            {errors.conso && (
              <div className="mt-3 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                {errors.conso}
              </div>
            )}
          </CardContent>
        </Card>

        {/* ── Informations du document ── */}
        <Card>
          <GenCardHeader icon={ClipboardList} title="Informations du document" />
          <CardContent className="grid gap-4 pt-4 sm:grid-cols-2 lg:grid-cols-3">
            <div className="grid gap-1.5">
              <Label htmlFor="gen-num">N° de Devis</Label>
              <Input id="gen-num" value="Généré automatiquement" disabled />
            </div>
            <div className="grid gap-1.5">
              {/* OFFGRID — « Raccordement » du devis : défaut « Raccordé au
                  réseau » (comportement historique byte-identique), dérivé du
                  lead (raccordement === 'aucun') tant que le vendeur ne
                  choisit pas lui-même. */}
              <Label htmlFor="gen-raccordement">Raccordement</Label>
              <Select
                value={horsReseau ? 'hors_reseau' : 'reseau'}
                onValueChange={(v) => {
                  setHorsReseauTouched(true)
                  setHorsReseau(v === 'hors_reseau')
                }}
              >
                <SelectTrigger id="gen-raccordement"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="reseau">Raccordé au réseau</SelectItem>
                  <SelectItem value="hors_reseau">Hors réseau (site isolé)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="gen-scenario">Scénario</Label>
              {/* OFFGRID — un système hors réseau porte TOUJOURS sa batterie :
                  option unique, le sélecteur Sans/Avec/Les deux est désactivé
                  (jamais retiré du DOM — l'id `gen-scenario` reste stable pour
                  les tests/lecteurs d'écran) et sans effet sur la composition
                  tant qu'il l'est (voir composeLocalement/handleAutoFill). */}
              <Select value={scenario} onValueChange={onScenarioChange} disabled={horsReseau}>
                <SelectTrigger id="gen-scenario"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="Les deux (Sans + Avec)">Les deux (Sans + Avec batterie)</SelectItem>
                  <SelectItem value="Sans batterie">Sans batterie seulement</SelectItem>
                  <SelectItem value="Avec batterie">Avec batterie seulement</SelectItem>
                </SelectContent>
              </Select>
              {horsReseau && (
                <p className="text-xs text-muted-foreground">
                  Système hors réseau : option unique avec batterie.
                </p>
              )}
              {'scenario' in imposees && (
                <IndicationRegistre chemin="scenario" busy={overridesBusy}
                                    onRegenerer={regenererOverride} />
              )}
            </div>
            {/* Incident fondateur 01/09 (round 2) — même échappatoire que la
                case de LigneTable (même state `accessoiresOnly`, même clé de
                persistance), reprise ICI en évidence à côté de Raccordement/
                Scénario pour que le fondateur la trouve sans descendre
                jusqu'à la table des lignes. Composer un devis à la main
                fonctionne même sur « Hors réseau » (validate() n'exige plus
                panneau/onduleur quand elle est active). */}
            <div className="grid gap-1.5">
              <Label htmlFor="gen-composition-libre">Composition</Label>
              <label htmlFor="gen-composition-libre"
                     className="flex h-10 items-center gap-2.5 text-sm text-foreground cursor-pointer">
                <Switch id="gen-composition-libre" checked={accessoiresOnly}
                        onCheckedChange={setAccessoiresOnly} />
                Composition libre (aucun panneau/onduleur imposé)
              </label>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="gen-reco">Option Recommandée</Label>
              <Select value={recommendedChoice} onValueChange={setRecommendedChoice}>
                <SelectTrigger id="gen-reco"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="Auto">Auto (défaut)</SelectItem>
                  <SelectItem value="Aucune recommandation">Aucune recommandation</SelectItem>
                  <SelectItem value="Sans batterie">Sans batterie</SelectItem>
                  <SelectItem value="Avec batterie">Avec batterie</SelectItem>
                </SelectContent>
              </Select>
              {'recommended_option' in imposees && (
                <IndicationRegistre chemin="recommended_option" busy={overridesBusy}
                                    onRegenerer={regenererOverride} />
              )}
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="gen-validite">Date de validité</Label>
              <Input id="gen-validite" type="date" value={dateValidite}
                     onChange={e => setDateValidite(e.target.value)} />
            </div>
          </CardContent>
        </Card>

        {/* ── Lead / Client (lead prioritaire) ── */}
        <Card>
          <GenCardHeader icon={User} title="Lead & Client" />
          <CardContent className="pt-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-1.5">
                {editId ? (
                  /* QJR580 — Édition complète : lead / client en LECTURE
                     SEULE. L'enregistrement d'édition ne porte ni lead ni
                     client : un sélecteur actif laissait croire à une
                     réaffectation jetée, tout en ré-semant les factures du
                     nouveau lead (applyLead) sur ce devis. Réaffecter n'est
                     pas une correction (D-QJR5-1). */
                  <>
                    <Label>Lead / client du devis</Label>
                    <div className="rounded-md border border-border bg-muted/40 px-3 py-2 text-sm"
                         data-testid="gen-lead-lecture-seule">
                      <strong>{editDevis?.lead_nom || editDevis?.client_nom || '…'}</strong>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        Changer de client = créer un nouveau devis.
                      </p>
                    </div>
                  </>
                ) : (<>
                <Label htmlFor="gen-lead" required>Lead (point de départ)</Label>
                {/* CI #752 — aucune option n'a la valeur '' : un '' ne vient que
                    du <select> natif caché du Select quand la valeur posée
                    n'est pas ENCORE dans ses options (lead d'un devis rouvert
                    relu après coup, hors première page de `leads`). Il vidait
                    le lead ; il est ignoré. */}
                <Select value={leadId ? String(leadId) : undefined}
                        onValueChange={(v) => { if (v) applyLead(v) }}>
                  <SelectTrigger id="gen-lead" invalid={!!errors.client}>
                    <SelectValue placeholder="— Sélectionner un lead —" />
                  </SelectTrigger>
                  <SelectContent>
                    {leadsListe.map(l => (
                      <SelectItem key={l.id} value={String(l.id)}>
                        {l.nom}{l.prenom ? ` ${l.prenom}` : ''}
                        {l.societe ? ` (${l.societe})` : ''}
                        {l.facture_hiver ? ` — ${Math.round(parseFloat(l.facture_hiver))} MAD/mois` : ''}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                </>)}
                {errors.client && <p className="text-xs text-destructive">{errors.client}</p>}
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="gen-tel">Téléphone</Label>
                <Input id="gen-tel" disabled placeholder="—"
                       value={selectedLead?.telephone ?? selectedClient?.telephone ?? ''} />
              </div>
            </div>

            {selectedLead && (
              <div className="mt-3 rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-success">
                ✓ Client du devis : <strong>{resolvedClientLabel}</strong>
                {selectedLead.facture_hiver
                  ? ` · factures remplies depuis le lead (${selectedLead.facture_hiver}${selectedLead.ete_differente && selectedLead.facture_ete ? ` hiver / ${selectedLead.facture_ete} été` : ' MAD/mois'})`
                  : ' · aucune facture enregistrée sur ce lead'}
              </div>
            )}

            {/* QX28 — raccourci vers la conception 3D. PV23bis (fondateur
                20/08, remplace PV23 ci-dessous) : visible dès qu'un lead OU
                un client est choisi — plus seulement quand le lead porte un
                repère toit (GPS) — parce que le bouton n'ouvre plus jamais un
                lead déconnecté du devis : il enregistre D'ABORD le formulaire
                (création ou édition, `ouvrirConception3D`) puis ouvre
                l'outil SUR ce devis. Le repère GPS du lead, quand il existe,
                reste simplement annoncé dans le libellé. */}
            {(selectedLead || clientId) && (
              <div className="mt-3 flex flex-wrap items-center gap-3 rounded-lg border border-brass-400/40 bg-brass-400/10 p-3 text-sm">
                {/* L-DESSIN (fondateur 25/08) — le libellé ne testait QUE
                    `roof_point` : un lead dont le client a DESSINÉ son toit
                    (`roof_outline`, la donnée la plus riche, chargée telle
                    quelle dans l'outil) s'annonçait « pas de repère ». Les
                    deux états sont désormais nommés, le tracé d'abord. */}
                <span>
                  {Array.isArray(selectedLead?.roof_outline) && selectedLead.roof_outline.length >= 3
                    ? '🛰️ Contour de toit tracé par le client sur ce lead — il est chargé dans l\'outil 3D.'
                    : selectedLead?.roof_point
                      ? '🛰️ Repère toit disponible sur ce lead (GPS).'
                      : '🛰️ Concevez la toiture en 3D — le devis est d\'abord enregistré en brouillon.'}
                </span>
                {/* PV23bis — remplace PV23 : édition COMME création passent
                    désormais par `ouvrirConception3D` (enregistrement
                    d'abord, puis ouverture SUR le devis) — une édition non
                    enregistrée n'est plus perdue en repartant du lead. */}
                <Button type="button" variant="outline" size="sm"
                        disabled={saving} onClick={ouvrirConception3D}>
                  Concevoir en 3D
                </Button>
              </div>
            )}

            {!leadId && !editId && (
              <div className="mt-3 grid gap-4 sm:grid-cols-2">
                <div className="grid gap-1.5">
                  <Label htmlFor="gen-client">…ou choisir un client directement (sans lead)</Label>
                  <div className="flex gap-2">
                    <div className="flex-1">
                      {/* QC1 — sélecteur client en Combobox recherché sur les
                          données propres (endpoint /search/, filtré aux clients
                          — un devis a besoin d'un id client réel). Les options
                          déjà chargées servent de repli/affichage immédiat. */}
                      <Combobox
                        id="gen-client"
                        options={clients.map(c => ({
                          value: String(c.id),
                          label: `${c.nom}${c.prenom ? ` ${c.prenom}` : ''}`,
                        }))}
                        value={clientId ? String(clientId) : null}
                        onSearch={onSearchClient}
                        onChange={(v) => applyClient(v)}
                        placeholder="— Sélectionner un client —"
                        searchPlaceholder="Nom ou ICE…"
                        emptyText="Aucun client dans vos données"
                      />
                    </div>
                    {/* QG3 — création rapide, sans quitter le devis */}
                    <Button type="button" variant="outline" onClick={() => setClientQuickCreateOpen(true)}>
                      <Plus /> Nouveau client
                    </Button>
                  </div>
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="gen-adresse">Adresse</Label>
                  <Input id="gen-adresse" value={selectedClient?.adresse ?? ''} disabled placeholder="—" />
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* ── Le panneau du marché choisi (QJR101) ──────────────────────
            Quatre panneaux, un par marché : chacun porte SES champs et se
            retire lui-même hors de sa clé de marché, donc exactement un rend,
            à la place qu'occupaient les deux cartes conditionnelles. */}
        <PanneauResidentiel {...socleFactures} />
        <PanneauIndustriel {...socleFactures} {...socleEtudeReseau} />
        <PanneauCommercial
          {...socleFactures}
          {...socleEtudeReseau}
          categorieCommerciale={categorieCommerciale}
          setCategorieCommerciale={setCategorieCommerciale}
          commercialAnswers={commercialAnswers}
          setCommercialAnswer={setCommercialAnswer}
        />
        <PanneauAgricole
          marche={modeInstallation}
          pompeCv={pompeCv} setPompeCv={setPompeCv}
          pompeType={pompeType} setPompeType={setPompeType}
          pompeAlim={pompeAlim} dispatchSizing={dispatchSizing}
          pompeHmt={pompeHmt} setPompeHmt={setPompeHmt}
          pompeDebit={pompeDebit} setPompeDebit={setPompeDebit}
          pompeHeures={pompeHeures} setPompeHeures={setPompeHeures}
          pompeProfondeur={pompeProfondeur} setPompeProfondeur={setPompeProfondeur}
          pompeDistance={pompeDistance} setPompeDistance={setPompeDistance}
          farmSurfaceHa={farmSurfaceHa} setFarmSurfaceHa={setFarmSurfaceHa}
          farmCrop={farmCrop} setFarmCrop={setFarmCrop}
          farmRegion={farmRegion} setFarmRegion={setFarmRegion}
          farmIrrigation={farmIrrigation} setFarmIrrigation={setFarmIrrigation}
          ecoPompage={ecoPompage} majEco={majEco}
          attestation={attestationAgricole} majAttestation={majAttestation}
          reperesEnergie={reperesEnergie} moisCalendrier={moisCalendrier}
          coherenceAvertit={coherenceAvertit}
          farmHmtStatic={farmHmtStatic} setFarmHmtStatic={setFarmHmtStatic}
          farmHmtDrawdown={farmHmtDrawdown} setFarmHmtDrawdown={setFarmHmtDrawdown}
          pompageSaisie={pompageSaisie} majPompage={majPompage}
          apercuPompage={apercuPompage}
        />

        {/* ── Paramètres techniques ── */}
        <Card>
          <GenCardHeader icon={Zap} title="Paramètres Techniques" />
          <CardContent className="pt-4">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {/* EZ5 — on DIMENSIONNE en kWc, pas en nombre de panneaux : le
                  client et le commercial disent « 3 kWc », jamais « 5 panneaux
                  de 550 W ». Le champ est BIDIRECTIONNEL — taper une puissance
                  cible remplit les panneaux, changer les panneaux remet la
                  cible à jour. La conversion réutilise `panneauxPourKwc`
                  (features/ventes/solar.js), déjà employée par le
                  pré-remplissage depuis le lead : rien n'est réécrit. */}
              <div className="grid gap-1.5">
                <Label htmlFor="gen-kwc-cible">Puissance cible (kWc)</Label>
                <Input id="gen-kwc-cible" type="number" min="0" step="any"
                       placeholder="ex: 3" value={kwcCible}
                       data-testid="gen-kwc-cible"
                       onChange={e => onKwcCibleChange(e.target.value)} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="gen-nbpanneaux" required>Nombre de panneaux</Label>
                <Input id="gen-nbpanneaux" type="number" min="1" max="500" step="any"
                       placeholder="ex: 14" value={nbPanneaux}
                       onChange={e => onNbPanneauxChange(e.target.value)} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="gen-panelw">Puissance Panneau (W)</Label>
                <Input id="gen-panelw" type="number" min="100" max="1000" step="any"
                       value={panelW}
                       onChange={e => dispatchSizing({ type: 'SAISI', champ: 'panelW', valeur: e.target.value })} />
              </div>
              <div className="grid gap-1.5">
                <Label>Puissance PV (kWp) — calculée</Label>
                <div className="gen-kwp">{kwp > 0 ? formatNumber(kwp, { decimals: 2 }) + ' kWp' : '—'}</div>
              </div>
              {/* QJR568 — les lignes et la cible divergent (quantité panneau
                  corrigée à la main) : on le DIT, sans recomposer d'office. */}
              {panneauxLignes > 0 && (parseInt(nbPanneaux) || 0) > 0
                && panneauxLignes !== (parseInt(nbPanneaux) || 0) && (
                <p className="text-xs text-warning sm:col-span-2" data-testid="gen-divergence-panneaux">
                  Les lignes portent {formatNumber(panneauxLignes)} panneaux, la cible en
                  vise {formatNumber(parseInt(nbPanneaux) || 0)} — recomposer ? (Auto-remplir)
                </p>
              )}
              {/* STKCAT10 (décision fondateur 16/09/2026) — le bouton
                  acier/aluminium est remplacé par un sélecteur ouvert sur
                  TOUTES les structures typées du catalogue (pergola, carport,
                  bac lesté…). Le bouton d'hier reste le REPLI quand la société
                  n'en a aucune : le sélecteur ne peut jamais naître vide. */}
              <StructureSelector
                id="gen-structure-produit"
                label="Type de Structure"
                produits={produits}
                value={structureProduitId}
                onChange={(v) => dispatchSizing({ type: 'SAISI', champ: 'structureProduit', valeur: v })}
                fallback={(
                  <div className="grid gap-1.5">
                    <Label>Type de Structure</Label>
                    <Segmented
                      options={[
                        { value: 'acier', label: 'Acier galvanisé' },
                        { value: 'aluminium', label: 'Aluminium' },
                      ]}
                      value={structureType}
                      onChange={(v) => dispatchSizing({ type: 'SAISI', champ: 'structure', valeur: v })}
                    />
                  </div>
                )}
              />
            </div>
            {/* Règle fondateur du 18/08 — justifie la taille retenue par le
                dimensionnement facture → paliers : palier de 5 kWc, besoin lu
                sur la facture d'hiver, payback le plus court parmi les
                paliers testés (`optimalKwcByPayback`, voir `sizingInfo.paliers`). */}
            {sizingInfo?.kwcOptimal > 0 && (() => {
              // PVMRQ — REPLI : une marque épinglée introuvable au stock ampute
              // CHAQUE palier (lignes placeholder à 0 MAD) ; leur payback serait
              // FABRIQUÉ, donc aucun n'est comparable et la taille retombe sur
              // le besoin lu sur la facture. On le DIT, jamais en silence — et
              // surtout on ne prétend pas avoir classé par retour sur
              // investissement.
              if (sizingInfo.repliMarqueManquante) {
                const mm = sizingInfo.marquesManquantes ?? []
                return (
                  <div className="mt-3 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
                    Taille retenue : palier de <strong>{sizingInfo.kwcOptimal} kWc</strong>
                    {' '}— besoin lu sur la facture d'hiver ≈ {sizingInfo.besoinKwc} kWc.
                    {' '}Le classement par retour sur investissement est <strong>suspendu</strong> :
                    {' '}marque épinglée introuvable au stock
                    {mm.length > 0 && (
                      <> ({mm.map(m => `${m.marque} (${roleLabel(m.role)})`).join(', ')})</>
                    )}, les paliers chiffrés seraient incomplets.
                    {' '}Ajoutez le produit ou changez la marque dans Paramètres → Gammes.
                  </div>
                )
              }
              const retenu = sizingInfo.paliers?.find(p => p.kwc === sizingInfo.kwcOptimal)
              return (
                <div className="mt-3 rounded-lg border border-info/30 bg-info/10 p-3 text-sm text-info">
                  Taille retenue : palier de <strong>{sizingInfo.kwcOptimal} kWc</strong>
                  {' '}— besoin lu sur la facture d'hiver ≈ {sizingInfo.besoinKwc} kWc,
                  {' '}retour sur investissement le plus court parmi les paliers testés
                  {Number.isFinite(retenu?.payback) && (
                    <> (<strong>{retenu.payback} ans</strong>)</>
                  )}.
                </div>
              )
            })()}
            {/* FOUNDER 26/08 — les DEUX valeurs de dimensionnement (L-2OPT),
                toujours dérivées d'un calcul réel (serveur horaire si
                disponible, sinon le même balayage local que ci-dessus —
                jamais un chiffre inventé, et jamais la paire mixée depuis
                deux sources différentes — voir deuxValeursDim/F3). Résidentiel
                uniquement : l'option batterie n'existe nulle part ailleurs
                (agricole = pompage, industriel/commercial ne la vendent
                jamais). Mono-option (`showSans`/`showAvec`, scénario déjà
                choisi) : seule la valeur réellement vendue sur CE devis
                s'affiche.
                F4 (revue adversariale 26/08) — le garde EXTÉRIEUR doit
                refléter EXACTEMENT ce que le contenu va rendre : l'ancien
                `(deuxValeursDim.sans || deuxValeursDim.avec)` pouvait être
                vrai (ex. `sans` calculable) alors que `showSans` est FAUX
                (scénario mono « Avec batterie ») ET `avec` encore `null` —
                un wrapper vide (marge + data-testid orphelins) s'affichait
                pour rien. Le garde reprend donc les DEUX conditions
                (source ET scénario) que le contenu vérifie déjà.
                F5 (revue adversariale 26/08) — « Recommandé » en tête : ce
                sont des RECOMMANDATIONS de l'optimiseur, pas une description
                des lignes composées — un nombre de panneaux TAPÉ À LA MAIN
                peut diverger du dimensionnement optimal affiché ici. */}
            {modeInstallation === 'residentiel'
              && ((showSans && deuxValeursDim.sans) || (showAvec && deuxValeursDim.avec)) && (
              <div className="mt-2 grid gap-0.5 text-sm text-foreground"
                   data-testid="dimensionnement-deux-valeurs">
                {showSans && deuxValeursDim.sans && (
                  <div>
                    Recommandé sans batterie : <strong>{deuxValeursDim.sans.nbPanneaux} panneaux</strong>
                    {' '}· {formatNumber(deuxValeursDim.sans.kwc, { decimals: 2 })} kWc
                  </div>
                )}
                {showAvec && deuxValeursDim.avec && (
                  <div>
                    Recommandé avec batterie : <strong>{deuxValeursDim.avec.nbPanneaux} panneaux</strong>
                    {' '}· {formatNumber(deuxValeursDim.avec.kwc, { decimals: 2 })} kWc
                  </div>
                )}
              </div>
            )}
            {/* U3-900 — le moteur horaire serveur a décliné le dimensionnement
                (donnée nommée : ville, facture…) au lieu de deviner une
                taille : message FRANÇAIS EXACT, aucun panneau prérempli. */}
            {modeInstallation === 'residentiel' && sizingServeurMessage && (
              <div className="mt-2 text-xs text-warning" data-testid="sizing-serveur-refus">
                {sizingServeurMessage}
              </div>
            )}
            {/* QJR641 — curseur masqué en commercial (sans effet : la part
                diurne vient de la catégorie, `commercialDayShare`) et en
                agricole. */}
            {(modeInstallation === 'residentiel' || modeInstallation === 'industriel') && (
              <div className="gen-slider-row" data-testid="curseur-part-diurne">
                <span className="gen-slider-label">Consommation diurne (%)</span>
                <input type="range" min="10" max="100" step="5" value={dayUsage}
                       onChange={e => setDayUsage(e.target.value)} />
                <span className="gen-slider-value">{dayUsage}%</span>
              </div>
            )}
            <div className="mt-3 flex flex-wrap items-center justify-end gap-3">
              {errors.recalcDim && <span className="text-xs text-destructive">{errors.recalcDim}</span>}
              {errors.autofill && <span className="text-xs text-destructive">{errors.autofill}</span>}
              {/* AGR128 — agricole : aucun devis plausible sans le besoin, la
                  hauteur et le cas de pompe ; le message NOMME ce qui manque. */}
              {pompageManquants.length > 0 && (
                <span className="text-xs text-warning" data-testid="pompage-manquants">
                  Auto-remplir indisponible — à renseigner : {pompageManquants.join(', ')}.
                </span>
              )}
              {errors.autofillKwc && <span className="text-xs text-warning">{errors.autofillKwc}</span>}
              {/* PVMRQ — même patron visuel que `errors.autofill` ci-dessus. */}
              {errors.marquesManquantes && <span className="text-xs text-destructive">{errors.marquesManquantes}</span>}
              {/* FOUNDER 26/08 — recalcule le dimensionnement (nombre de
                  panneaux, sans ET avec batterie) depuis la facture ACTUELLE,
                  puis recompose (même chemin qu'« Auto-remplir » ci-contre) :
                  contrairement à ce dernier, qui recompose au nombre de
                  panneaux COURANT sans jamais le redériver. Désactivé sans
                  facture hiver exploitable, ou en agricole (dimensionnement
                  pompage, aucune notion de facture → kWc). */}
              <Button type="button" variant="outline"
                      data-testid="btn-recalculer-dimensionnement"
                      loading={autoFillLoading}
                      disabled={!(parseFloat(fHiver) > 0) || modeInstallation === 'agricole'}
                      onClick={recalculerDimensionnement}>
                <RefreshCw /> Recalculer le dimensionnement
              </Button>
              <Button type="button" className="bg-brass-400 text-nuit hover:bg-brass-500"
                      data-testid="btn-auto-remplir"
                      disabled={pompageManquants.length > 0}
                      loading={autoFillLoading} onClick={() => avecQuantitesFigees(handleAutoFill)}>
                <Zap /> Auto-remplir depuis le stock
              </Button>
            </div>
            {/* QJR577 (D-QJR5-9) — le dry-run serveur a échoué : AUCUNE
                composition de secours, l'erreur est dite et « Réessayer »
                rejoue le même dry-run. */}
            {compositionErreur && (
              <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
                   data-testid="composition-erreur" role="alert">
                <span>{compositionErreur}</span>
                <Button type="button" size="sm" variant="outline"
                        data-testid="composition-reessayer"
                        loading={autoFillLoading}
                        onClick={() => avecQuantitesFigees(handleAutoFill)}>
                  Réessayer
                </Button>
              </div>
            )}
            {/* QJR589 (contrat QJR505) — la dérive lead → devis, NOMMÉE et
                RÉSOLUBLE : « Reprendre les valeurs du lead » / « Garder les
                valeurs du devis ». Verdict serveur (`lead_valeurs_modifiees`)
                — l'écran ne compare rien. Après succès, l'écran relit le devis. */}
            <BandeauDeriveLead
              devisId={editDevis?.id}
              statut={editDevis?.statut}
              champs={leadValeursModifiees}
              onResolu={() => {
                setLeadValeursModifiees([])
                clear()
                setRechargeEdit(n => n + 1)
              }}
            />
            {onduleursIncomplets.length > 0 && (
              <div className="mt-3 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
                <strong>Onduleur(s) non chiffrable(s)</strong> — fiche technique
                incomplète, écartés de l'auto-remplissage (toujours
                sélectionnables à la main) :
                <ul className="mt-1 list-disc pl-5">
                  {onduleursIncomplets.map(o => (
                    <li key={o.id}>
                      {o.nom} — à renseigner : {o.manquantes.join(', ')}
                    </li>
                  ))}
                </ul>
                Complétez leur fiche technique dans Stock pour les rendre
                chiffrables.
              </div>
            )}
            {modeInstallation === 'agricole' && pompageAutoFilled && apercuPompage?.donnees && (
              <div className="mt-3 rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-success"
                   data-testid="pompage-auto-rempli">
                Auto-remplissage effectué (kit calculé par le serveur) —
                {' '}champ PV <strong>{apercuPompage.donnees.champ?.kwc ?? '—'} kWc</strong>
                {' '}({apercuPompage.donnees.champ?.nb_panneaux ?? '—'} panneaux).
              </div>
            )}
          </CardContent>
        </Card>

        {/* ── Aperçu de la simulation (masqué en mode pompage) ── */}
        {modeInstallation !== 'agricole' && (
        <Card>
          <GenCardHeader icon={BarChart3} title="Aperçu de la Simulation">
            {/* Repliable sur téléphone uniquement (bouton caché sur bureau) */}
            <Button type="button" size="sm" variant="outline" className="gen-preview-toggle"
                    onClick={() => setPreviewCollapsed(v => !v)}>
              {previewCollapsed ? 'Afficher' : 'Replier'}
            </Button>
          </GenCardHeader>
          <CardContent className={`gen-preview-body pt-4${previewCollapsed ? ' m-collapsed' : ''}`}>
            {/* CJ2b — ORDRE FONDATEUR (20/08) : « on ne voit ni l'économie
                réelle calculée, ni les données PVGIS — cette donnée devrait
                être comparée à la courbe de consommation ». Résidentiel
                uniquement, sous le bandeau de source (serveur vs estimation
                locale, règle d'honnêteté #2/#4), le tableau de
                dimensionnement (paliers candidats du moteur horaire, chacun
                avec sa réalité batterie — règle #1) et le détail saisonnier
                production × consommation. */}
            {modeInstallation === 'residentiel' && etudeHoraireCorps && (
              <div className="mb-4" data-testid="etude-horaire-block">
                {etudeHoraireSourceServeur ? (
                  <p className="mb-2 text-xs font-medium text-success" data-testid="etude-horaire-source">
                    Chiffres du moteur horaire (serveur) — PVGIS réel × consommation réelle du client.
                    {etudeHoraireSourceLabel?.estimation && (
                      <> {' '}Détail mensuel : {etudeHoraireSourceLabel.libelle}.</>
                    )}
                  </p>
                ) : (
                  <p className="mb-2 text-xs text-muted-foreground" data-testid="etude-horaire-source">
                    {etudeHoraireChargement
                      ? 'Calcul du moteur horaire en cours…'
                      : (etudeHoraireErreur
                          || 'Estimation locale (hors ligne) — en attente du moteur horaire serveur.')}
                  </p>
                )}
                {etudeHoraireDonnees?.avertissements?.length > 0 && (
                  <ul className="mb-3 list-disc pl-5 text-xs text-warning" data-testid="etude-horaire-avertissements">
                    {etudeHoraireDonnees.avertissements.map((a) => <li key={a}>{a}</li>)}
                  </ul>
                )}
                {etudeHoraireLignes.length > 0 && (
                  <div style={{ overflowX: 'auto' }}>
                    <table className="w-full border-collapse text-xs" data-testid="etude-horaire-dimensionnement">
                      <thead>
                        <tr className="border-b border-border text-left text-muted-foreground">
                          <th className="py-1 pr-3 font-medium">kWc</th>
                          <th className="py-1 pr-3 font-medium">Onduleur (règle 80 %)</th>
                          <th className="py-1 pr-3 font-medium">Autoconso.</th>
                          <th className="py-1 pr-3 font-medium">Couverture</th>
                          <th className="py-1 pr-3 font-medium">Éco. sans (MAD/an)</th>
                          <th className="py-1 pr-3 font-medium">Éco. avec (MAD/an)</th>
                          <th className="py-1 pr-3 font-medium">Payback</th>
                          <th className="py-1 pr-3 font-medium">Résiduel après (kWh/mois)</th>
                          <th className="py-1 pr-3 font-medium">Remplissage batterie</th>
                          <th className="py-1" />
                        </tr>
                      </thead>
                      <tbody>
                        {etudeHoraireLignes.map((ligne) => {
                          const estRecommandee = etudeHoraireDonnees?.dimensionnement
                            ?.recommandation?.panneaux === ligne.panneaux
                          // L-2OPT (fondateur 24/08) — second optimiseur, même
                          // patron : surligne DISTINCTEMENT le palier optimal
                          // AVEC batterie (recommandation_avec, moteur horaire
                          // serveur) — peut différer de `estRecommandee`
                          // ci-dessus (les deux optima peuvent diverger).
                          const estRecommandeeAvec = etudeHoraireDonnees?.dimensionnement
                            ?.recommandation_avec?.panneaux === ligne.panneaux
                          // L-FRONT lot 4 — résiduel/tranche après la meilleure option
                          // chiffrée (avec batterie si vendable, sinon sans), et
                          // remplissage moyen du stockage retenu pour cette taille.
                          // `null`/absent -> cellule vide, jamais un calcul de repli.
                          const residuelApres = ligne.batterieVendable
                            ? (ligne.residuel_avec_kwh_mois ?? ligne.residuel_kwh_mois)
                            : ligne.residuel_sans_kwh_mois
                          const trancheApres = ligne.batterieVendable
                            ? (ligne.tranche_apres_avec?.libelle ?? ligne.tranche_apres?.libelle)
                            : ligne.tranche_apres_sans?.libelle
                          const remplissageMoyen = ligne.remplissage?.moyen
                          const paliersStockage = balayageStockageAffichable(ligne)
                          const stockageOuvert = ligneStockageOuverte === ligne.panneaux
                          return (
                            <Fragment key={ligne.panneaux}>
                              <tr
                                  className={`border-b border-border${estRecommandee ? ' bg-success/10' : ''}${estRecommandeeAvec ? ' bg-info/10' : ''}`}>
                                <td className="py-1.5 pr-3">
                                  {formatNumber(ligne.kwc, { decimals: 2 })} kWc
                                  {estRecommandee && <span className="gen-rec-badge"> ★ Recommandé (sans)</span>}
                                  {estRecommandeeAvec && <span className="gen-rec-badge" data-testid="etude-horaire-reco-avec"> ★ Recommandé (avec)</span>}
                                </td>
                                <td className="py-1.5 pr-3">
                                  {ligne.onduleur} — {formatNumber(ligne.ratio_onduleur_kwc * 100, { decimals: 0 })} % du kWc
                                  {!ligne.regle_80_pct_respectee && (
                                    <span className="text-warning"> (sous 80 %)</span>
                                  )}
                                </td>
                                <td className="py-1.5 pr-3">{formatNumber(ligne.taux_autoconso_sans * 100, { decimals: 0 })} %</td>
                                <td className="py-1.5 pr-3">{formatNumber(ligne.couverture_sans * 100, { decimals: 0 })} %</td>
                                <td className="py-1.5 pr-3">{fmtNum(Math.round(ligne.economie_sans_mad))}</td>
                                <td className="py-1.5 pr-3">
                                  {ligne.batterieVendable
                                    ? fmtNum(Math.round(ligne.economie_avec_mad))
                                    : <span className="text-muted-foreground">{ligne.raisonBatterie}</span>}
                                </td>
                                <td className="py-1.5 pr-3">{ligne.payback_sans_annees != null ? `${ligne.payback_sans_annees} ans` : 'N/A'}</td>
                                <td className="py-1.5 pr-3" data-testid="etude-horaire-residuel">
                                  {residuelApres != null
                                    ? <>{fmtNum(Math.round(residuelApres))} kWh{trancheApres && <> — {trancheApres}</>}</>
                                    : '—'}
                                </td>
                                <td className="py-1.5 pr-3" data-testid="etude-horaire-remplissage">
                                  {remplissageMoyen != null
                                    ? `${formatNumber(remplissageMoyen * 100, { decimals: 0 })} %`
                                    : '—'}
                                </td>
                                <td className="py-1.5">
                                  <div style={{ display: 'flex', gap: '0.375rem' }}>
                                    <Button type="button" size="sm" variant="outline"
                                            onClick={() => appliquerTailleDimensionnement(ligne)}>
                                      Appliquer cette taille
                                    </Button>
                                    {paliersStockage.length > 0 && (
                                      <Button type="button" size="sm" variant="ghost"
                                              data-testid="etude-horaire-stockage-toggle"
                                              onClick={() => setLigneStockageOuverte(
                                                stockageOuvert ? null : ligne.panneaux)}>
                                        {stockageOuvert ? 'Masquer stockage' : 'Détail stockage'}
                                      </Button>
                                    )}
                                  </div>
                                </td>
                              </tr>
                              {stockageOuvert && paliersStockage.length > 0 && (
                                <tr className="border-b border-border">
                                  <td colSpan={9} className="bg-muted/30 py-2 pr-3">
                                    <div style={{ overflowX: 'auto' }}>
                                      <table className="w-full border-collapse text-xs"
                                             data-testid="etude-horaire-balayage-stockage">
                                        <thead>
                                          <tr className="text-left text-muted-foreground">
                                            <th className="py-1 pr-3 font-medium">Batterie (kWh)</th>
                                            <th className="py-1 pr-3 font-medium">Coût TTC</th>
                                            <th className="py-1 pr-3 font-medium">Éco. (MAD/an)</th>
                                            <th className="py-1 pr-3 font-medium">Éco. marginale</th>
                                            <th className="py-1 pr-3 font-medium">Payback</th>
                                            <th className="py-1 pr-3 font-medium">Résiduel (kWh/mois)</th>
                                            <th className="py-1 pr-3 font-medium">Remplissage moyen</th>
                                          </tr>
                                        </thead>
                                        <tbody>
                                          {paliersStockage.map((p) => (
                                            <tr key={p.capaciteKwh}>
                                              <td className="py-1 pr-3">{fmtNum(p.capaciteKwh)} kWh</td>
                                              <td className="py-1 pr-3">{p.coutTtc != null ? `${fmtNum(Math.round(p.coutTtc))} MAD` : '—'}</td>
                                              <td className="py-1 pr-3">{p.economieMad != null ? fmtNum(Math.round(p.economieMad)) : '—'}</td>
                                              <td className="py-1 pr-3">{p.economieMarginaleMad != null ? fmtNum(Math.round(p.economieMarginaleMad)) : '—'}</td>
                                              <td className="py-1 pr-3">{p.paybackAnnees != null ? `${p.paybackAnnees} ans` : '—'}</td>
                                              <td className="py-1 pr-3">
                                                {p.residuelKwhMois != null
                                                  ? <>{fmtNum(Math.round(p.residuelKwhMois))}{p.trancheApres && <> — {p.trancheApres}</>}</>
                                                  : '—'}
                                              </td>
                                              <td className="py-1 pr-3">{p.remplissageMoyen != null ? `${formatNumber(p.remplissageMoyen * 100, { decimals: 0 })} %` : '—'}</td>
                                            </tr>
                                          ))}
                                        </tbody>
                                      </table>
                                    </div>
                                  </td>
                                </tr>
                              )}
                            </Fragment>
                          )
                        })}
                      </tbody>
                    </table>
                    {etudeHoraireDonnees?.dimensionnement?.motivation && (
                      <p className="mt-2 text-xs text-muted-foreground" data-testid="etude-horaire-motivation">
                        {etudeHoraireDonnees.dimensionnement.motivation}
                      </p>
                    )}
                  </div>
                )}
                {etudeHoraireDonnees?.etude?.saisons && (
                  <div className="mt-3 grid gap-2 sm:grid-cols-3" data-testid="etude-horaire-saisons">
                    {Object.entries(SAISON_LABELS).map(([cle, libelle]) => {
                      const s = etudeHoraireDonnees.etude.saisons[cle]
                      if (!s) return null
                      return (
                        <div key={cle} className="rounded-lg border border-border p-2">
                          <div className="text-xs font-medium">{libelle}</div>
                          <div className="text-xs text-muted-foreground">
                            Production {fmtNum(Math.round(s.production_kwh))} kWh
                            {' · '}Consommation {fmtNum(Math.round(s.consommation_kwh))} kWh
                            {' · '}Autoconsommé {fmtNum(Math.round(s.autoconsomme_sans_kwh))} kWh
                            {' '}({formatNumber(s.taux_autoconso_sans * 100, { decimals: 0 })} %)
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
                {/* L-FRONT lot 4 — falaise tarifaire : la marche du barème juste
                    sous la consommation actuelle (« land frankly under the
                    cliff »), + la meilleure combinaison du balayage qui y passe.
                    Omis en bloc quand le moteur n'a rien calculé. */}
                {etudeHoraireFalaise && (
                  <div className="mt-3 rounded-lg border border-border p-3" data-testid="etude-horaire-falaise">
                    <div className="text-xs font-medium">Falaise tarifaire</div>
                    <div className="text-xs text-muted-foreground">
                      Palier visé : {fmtNum(etudeHoraireFalaise.cibleKwhMois)} kWh/mois
                      {etudeHoraireFalaise.trancheActuelle && (
                        <> — actuellement en {etudeHoraireFalaise.trancheActuelle}</>
                      )}
                      {etudeHoraireFalaise.trancheVisee && (
                        <>, marche visée : {etudeHoraireFalaise.trancheVisee}</>
                      )}
                      .
                    </div>
                    {etudeHoraireFalaise.meilleure && (
                      <div className="mt-1 text-xs text-muted-foreground" data-testid="etude-horaire-meilleure-falaise">
                        Meilleure combinaison sous la marche : {etudeHoraireFalaise.meilleure.panneaux} panneaux
                        {etudeHoraireFalaise.meilleure.kwc != null && <> ({formatNumber(etudeHoraireFalaise.meilleure.kwc, { decimals: 2 })} kWc)</>}
                        {etudeHoraireFalaise.meilleure.batterieKwh
                          ? <> + {fmtNum(etudeHoraireFalaise.meilleure.batterieKwh)} kWh de batterie</>
                          : ''}
                        {etudeHoraireFalaise.meilleure.residuelKwhMois != null && (
                          <> — résiduel {fmtNum(Math.round(etudeHoraireFalaise.meilleure.residuelKwhMois))} kWh/mois
                            {etudeHoraireFalaise.meilleure.trancheApres && <> ({etudeHoraireFalaise.meilleure.trancheApres})</>}</>
                        )}
                        {etudeHoraireFalaise.meilleure.paybackAnnees != null && (
                          <> — payback {etudeHoraireFalaise.meilleure.paybackAnnees} ans</>
                        )}.
                      </div>
                    )}
                  </div>
                )}
                {/* L-FRONT lot 4 — résumé annuel des impulsions équipements
                    (glitch) : n'apparaît que si le moteur a vraiment déclaré au
                    moins un équipement concentrable (part_glitch additif). */}
                {etudeHoraireGlitch && (
                  <div className="mt-3 rounded-lg border border-border p-3" data-testid="etude-horaire-glitch">
                    <div className="text-xs font-medium">Pointes équipements ({etudeHoraireGlitch.couches.join(', ')})</div>
                    <div className="text-xs text-muted-foreground">
                      {fmtNum(Math.round(etudeHoraireGlitch.sansKwh))} kWh/an partent au réseau sans batterie
                      {etudeHoraireGlitch.batterieKwh != null && (
                        <>, dont {fmtNum(Math.round(etudeHoraireGlitch.batterieKwh))} kWh/an rattrapés par le stockage</>
                      )}.
                    </div>
                  </div>
                )}
                {/* L-FRONT lot 4 — décomposition mensuelle de la consommation
                    estimée (base + chaque équipement déclaré), pour que le
                    commercial voie chaque ajout compté. Omise en bloc si la clé
                    `estimation_conso` est absente du payload. */}
                {etudeHoraireEstimationConso && (
                  <div className="mt-3" style={{ overflowX: 'auto' }}>
                    <div className="mb-1 text-xs font-medium">Décomposition mensuelle de la consommation (kWh)</div>
                    <table className="w-full border-collapse text-xs" data-testid="etude-horaire-estimation-conso">
                      <thead>
                        <tr className="border-b border-border text-left text-muted-foreground">
                          <th className="py-1 pr-3 font-medium">Poste</th>
                          {LIBELLES_MOIS.map((m) => <th key={m} className="py-1 pr-2 font-medium">{m}</th>)}
                        </tr>
                      </thead>
                      <tbody>
                        <tr className="border-b border-border">
                          <td className="py-1 pr-3">Base</td>
                          {etudeHoraireEstimationConso.base.map((v, i) => (
                            <td key={LIBELLES_MOIS[i]} className="py-1 pr-2">{fmtNum(Math.round(v))}</td>
                          ))}
                        </tr>
                        {etudeHoraireEstimationConso.ajouts.map((a) => (
                          <tr key={a.cle} className="border-b border-border">
                            <td className="py-1 pr-3">+ {a.libelle}</td>
                            {a.valeurs.map((v, i) => (
                              <td key={LIBELLES_MOIS[i]} className="py-1 pr-2">{fmtNum(Math.round(v))}</td>
                            ))}
                          </tr>
                        ))}
                        <tr className="font-medium">
                          <td className="py-1 pr-3">Total</td>
                          {etudeHoraireEstimationConso.total.map((v, i) => (
                            <td key={LIBELLES_MOIS[i]} className="py-1 pr-2">{fmtNum(Math.round(v))}</td>
                          ))}
                        </tr>
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
            {etudeCI && (
              <div className="gen-metrics-grid" style={{ marginBottom: '0.75rem' }}>
                {/* QJR213/DV3 (30/08/2026) — ces QUATRE cartes SEULEMENT sont
                    nourries par `computeEtudeIndustrielle` (le miroir local
                    `features/ventes/solar.js`), pas par le moteur serveur :
                    étiquetage SEULEMENT (mot du fondateur D10) — ne JAMAIS
                    serveriser l'étude indus/commercial dans cette tâche. Les
                    9 autres cartes de cet écran sont hors périmètre DV3.
                    QJR426 — la prop `valeur`, signée via `apercu` : valeur.js
                    docstring NOMME `computeEtudeIndustrielle` comme exemple canonique
                    d'aperçu local, la puce `PUCE_APERCU` (« estimation
                    d'exemple ») consolide donc le libellé ad hoc
                    « estimation locale » posé ici avant QJR86/CarteMetrique
                    — même MOTIF (chiffre local, pas une mesure), la valeur
                    et le libellé restent inchangés à l'octet. */}
                <CarteMetrique label="Taux d'autoconsommation"
                               valeur={apercu(`${etudeCI.taux_autoconso} %`)}
                               unit="part de la production consommée" accent />
                {etudeCI.taux_couverture != null && (
                  <CarteMetrique label="Taux de couverture"
                                 valeur={apercu(`${etudeCI.taux_couverture} %`)}
                                 unit="part de la conso couverte" accent />
                )}
                {/* QXMT — en MT sans tarif exploitable, `economies_annuelles`
                    vaut null : la carte est OMISE (jamais un « 0 » trompeur),
                    le motif est affiché juste en dessous. */}
                {etudeCI.economies_annuelles != null && (
                  <CarteMetrique label="Économies annuelles (étude)"
                                 valeur={apercu(fmtNum(etudeCI.economies_annuelles))}
                                 unit={etudeCI.tension_raccordement === 'mt'
                                   ? 'MAD / an · barème MT' : 'MAD / an'} />
                )}
                {etudeCI.payback != null && (
                  <CarteMetrique label="Payback (étude)"
                                 valeur={apercu(`${etudeCI.payback} ans`)}
                                 unit="retour sur invest." />
                )}
              </div>
            )}
            {/* QJR34 — l'étude industriel/commercial EXIGE une consommation
                réelle (saisie directe ou factures réelles) : sans elle,
                consoKwhDerivee reste à 0 et etudeCI/etudeIndustrielle/
                etudeCommerciale court-circuitent déjà vers null (jamais un
                repli forfaitaire) — cet avis rend la raison visible au
                vendeur au lieu de laisser le panneau simplement vide. */}
            {(modeInstallation === 'industriel' || modeInstallation === 'commercial')
              && !etudeCI && (
              <p className="mb-3 rounded-lg border border-warning/40 bg-warning/10 p-3 text-xs text-warning"
                 data-testid="etude-ci-indisponible">
                Étude indisponible : saisissez la consommation ou les factures réelles.
              </p>
            )}
            {etudeCI?.etude_mt_motif && (
              <p className="mb-3 rounded-lg border border-warning/40 bg-warning/10 p-3 text-xs text-warning"
                 data-testid="etude-mt-motif">
                {etudeCI.etude_mt_motif}
              </p>
            )}
            {etudeCI?.tarif_mt_dh_kwh != null && (
              <p className="mb-3 text-xs text-muted-foreground" data-testid="etude-mt-source">
                Énergie valorisée à {formatNumber(etudeCI.tarif_mt_dh_kwh, { decimals: 4 })} DH/kWh
                {' — '}{etudeCI.tarif_mt_mention}
              </p>
            )}
            {!roi ? (
              <p className="text-center text-sm text-muted-foreground">
                Renseignez le nombre de panneaux et les factures, puis la simulation
                s'actualise automatiquement.
              </p>
            ) : (
              <>
                {/* QF5 — quand une facture/consommation réelle est capturée
                    (QF4), l'écran affiche le MÊME calcul « deux factures » par
                    tranche que le PDF (facture sans vs avec solaire) au lieu
                    d'une estimation moyenne. */}
                {roi.savings_model === 'factures' ? (
                  <div className="mb-3 rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-success">
                    Facture réelle {distributeur.toUpperCase()} ≈ <strong>{fmtNum(roi.facture_sans)} MAD/an</strong>
                    {' '}sans solaire → avec solaire ≈{' '}
                    <strong>
                      {fmtNum(sansRec || !showAvec ? roi.facture_avec_sans : roi.facture_avec_avec)} MAD/an
                    </strong>
                    {' '}— économie calculée par tranche (barème {distributeur.toUpperCase()}), pas une estimation.
                  </div>
                ) : (
                  <div className="mb-3 rounded-lg border border-info/30 bg-info/10 p-3 text-sm text-info">
                    Estimation (production × autoconsommation × tarif moyen) — renseignez la
                    facture réelle du client ci-dessus pour un calcul par tranche exact.
                  </div>
                )}
                <div className="gen-metrics-grid">
                  {/* CJ2b — Production/Autoconso/Couverture : le serveur
                      horaire (PVGIS réel) gagne dès qu'il a répondu (résidentiel),
                      sinon repli sur `roi` (miroir local, inchangé).
                      QJR426 — aucune puce ici avant comme après : cette carte
                      ne distingue déjà pas ses deux sources à l'écran (le
                      repli `roi` reste, comme aujourd'hui, non étiqueté) —
                      `moteur()` reproduit ce silence à l'octet, jamais un
                      nouveau badge introduit au passage. */}
                  {/* QA-FIGURES — `figure` pose `data-figure` (clés :
                      apps/ventes/quote_engine/figures.py) : la parité écran /
                      PDF / page publique / API est vérifiée par
                      e2e/figures-parite.spec.js. */}
                  <CarteMetrique label="Production annuelle"
                                 valeur={moteur(fmtNum(Math.round(apercuProductionKwh)))}
                                 unit="kWh / an" accent
                                 figure="production_annuelle_kwh" />
                  {etudeHoraireSourceServeur && (
                    <>
                      {/* QJR426 — ces deux cartes ne rendent QUE dans la
                          branche serveur (`etudeHoraireSourceServeur`) :
                          `moteur()` y est toujours exact, jamais un motif
                          inventé. */}
                      <CarteMetrique label="Taux d'autoconsommation (sans)"
                                     valeur={moteur(`${formatNumber(etudeHoraireAnnuel.taux_autoconso_sans * 100, { decimals: 0 })} %`)}
                                     unit="part de la production consommée" />
                      <CarteMetrique label="Taux de couverture (sans)"
                                     valeur={moteur(`${formatNumber(etudeHoraireAnnuel.couverture_sans * 100, { decimals: 0 })} %`)}
                                     unit="part de la conso couverte"
                                     figure="couverture_pct" figureOption="sans" />
                    </>
                  )}
                </div>
                {/* VX138 — comparateur Sans/Avec : 2 colonnes NOMMÉES au lieu
                    d'une grille homogène de jusqu'à 6 cartes reliées par la
                    seule étoile — la recommandation devient un liseré porté
                    par TOUTE la colonne. */}
                <div className="gen-compare-grid">
                  {showSans && (
                    <div className={`gen-compare-col${sansRec ? ' gen-compare-col-rec' : ''}`}>
                      <div className="gen-compare-col-title">
                        Sans batterie
                        {sansRec && <span className="gen-rec-badge">★ Recommandé</span>}
                      </div>
                      {/* QJR426 — `signerEcoOuRoi` reproduit EXACTEMENT
                          l'ancien `badge={apercuEstimationExemple ? ... :
                          null}` : `apercu()` porte la même puce
                          `PUCE_APERCU` (« estimation d'exemple », le même
                          texte), `moteur()` n'en porte aucune. */}
                      <CarteMetrique label="Économies"
                                     valeur={signerEcoOuRoi(fmtNum(Math.round(apercuEcoSans)))}
                                     unit="MAD / an"
                                     figure="economie_annuelle" figureOption="sans" />
                      <CarteMetrique label="ROI"
                                     valeur={signerEcoOuRoi(
                                       apercuPaybackSansJamais ? 'Non rentabilisé sur 25 ans'
                                         : apercuPaybackSans != null ? apercuPaybackSans + ' ans' : 'N/A')}
                                     unit="retour sur invest." accent
                                     figure="payback_ans" figureOption="sans" />
                      {/* QJR426 — le coût est celui, certain, des lignes du
                          devis (`optionTotalsTTC`) : jamais de disclaimer
                          avant, `moteur()` en garde l'absence à l'octet. */}
                      <CarteMetrique label="Coût"
                                     valeur={moteur(fmtNum(Math.round(totals.totalSans)))}
                                     unit="MAD TTC"
                                     figure="total_ttc" figureOption="sans" />
                    </div>
                  )}
                  {showAvec && (
                    <div className={`gen-compare-col${avecRec ? ' gen-compare-col-rec' : ''}`}>
                      <div className="gen-compare-col-title">
                        Avec batterie
                        {avecRec && <span className="gen-rec-badge">★ Recommandé</span>}
                      </div>
                      {/* CJ2b — OMISSION HONNÊTE. Le moteur horaire dit que
                          l'option batterie n'est pas livrable à cette taille :
                          on affiche SA raison, jamais un montant — et surtout
                          jamais le « 0 MAD » que produirait un arrondi sur une
                          valeur absente. */}
                      {batterieInvendableServeur ? (
                        <p className="text-xs text-muted-foreground"
                           data-testid="etude-horaire-batterie-invendable">
                          Option batterie non livrable pour cette taille :{' '}
                          {verdictBatterieServeur.raison}
                        </p>
                      ) : (
                        <>
                          <CarteMetrique label="Économies"
                                         valeur={signerEcoOuRoi(fmtNum(Math.round(apercuEcoAvec)))}
                                         unit="MAD / an"
                                         figure="economie_annuelle" figureOption="avec" />
                          <CarteMetrique label="ROI"
                                         valeur={signerEcoOuRoi(
                                           apercuPaybackAvecJamais ? 'Non rentabilisé sur 25 ans'
                                             : apercuPaybackAvec != null ? apercuPaybackAvec + ' ans' : 'N/A')}
                                         unit="retour sur invest." accent
                                         figure="payback_ans" figureOption="avec" />
                          <CarteMetrique label="Coût"
                                         valeur={moteur(fmtNum(Math.round(totals.totalAvec)))}
                                         unit="MAD TTC"
                                         figure="total_ttc" figureOption="avec" />
                          {/* BAT5DEF — au moins une ligne batterie n'a pas de
                              kWh lisible : la capacité utilisée par le ROI et
                              l'étude horaire est SOUS-estimée (0 kWh pour
                              cette ligne, jamais un défaut inventé). Signalé
                              à l'écran, jamais caché — même patron que
                              gen-mt-manquant. */}
                          {capaciteBatterieInconnue && (
                            <p className="text-xs text-warning"
                               data-testid="gen-battery-capacite-inconnue">
                              Capacité batterie non lisible sur au moins une
                              ligne (désignation sans kWh) : les économies et
                              le payback « avec batterie » sont sous-estimés,
                              renseignez le kWh dans la désignation.
                            </p>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>
                <div className="gen-chart-title">Économies mensuelles estimées (MAD / mois)</div>
                {/* N4 — tant qu'aucune facture RÉELLE n'a été saisie
                    (facturesSaisies), `monthly` ne porte que les valeurs
                    D'EXEMPLE du simulateur (DEFAULT_MONTHLY_BILLS) : le
                    graphique « Facture ONEE » ne doit alors jamais se
                    présenter comme une donnée du client — il est masqué au
                    profit d'un message explicite. */}
                {facturesSaisies ? (
                  <ResponsiveContainer width="100%" height={260}>
                    <ComposedChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(0,0,0,0.07)" />
                      <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }}
                             label={{ value: 'MAD / mois', angle: -90, position: 'insideLeft', fontSize: 11 }}
                             tickFormatter={(v) => formatNumber(v)} />
                      <Tooltip formatter={(v, name) => [`${formatMAD(v, { decimals: 0 })}`, name]} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Bar dataKey="facture" name="Facture ONEE (MAD)"
                           fill="rgba(181,192,206,0.55)" stroke="rgba(181,192,206,0.8)" radius={[3, 3, 0, 0]} />
                      {showSans && (
                        <Line type="monotone" dataKey="ecoSans"
                              name={'Option 1 – Sans batterie' + (sansRec ? ' ⭐' : '')}
                              stroke="var(--gen-chart-sans)" strokeWidth={sansRec ? 3.5 : 2.2}
                              dot={{ r: sansRec ? 5 : 4 }} />
                      )}
                      {showAvec && (
                        <Line type="monotone" dataKey="ecoAvec"
                              name={'Option 2 – Avec batterie' + (avecRec ? ' ⭐' : '')}
                              stroke="var(--gen-chart-avec)" strokeWidth={avecRec ? 3.5 : 2.2}
                              dot={{ r: avecRec ? 5 : 4 }} />
                      )}
                    </ComposedChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="py-6 text-center text-sm text-muted-foreground" data-testid="chart-no-bills">
                    Graphique masqué — exemple sans saisie réelle. Renseignez vos
                    factures (hiver/été ou détail mensuel ci-dessus) pour voir vos
                    économies mensuelles réelles.
                  </p>
                )}
              </>
            )}
          </CardContent>
        </Card>
        )}

        {/* ── Tailles Éco / Recommandé / Max (fondateur 26/08/2026) ──
            Composant autonome : se masque lui-même hors résidentiel ou sur un
            devis pas encore enregistré (editId absent — l'API a besoin d'un
            pk réel). Éco / Max ne configurent que la carte d'exploration ;
            « Recommandé » RECOMPOSE le devis côté serveur (lignes, totaux,
            études — pipeline RECONCILIER) : `onDevisRecompose` relance alors
            le chargeur `?edit=` (QJR548). « Appliquer » lit le verdict de
            modifiabilité servi (QJR516). `produits` réutilise le catalogue
            déjà chargé pour « Auto-remplir » (pas de second aller-retour). */}
        <DevisOffresTailles devisId={editId} modeInstallation={modeInstallation} produits={produits}
                            modifiable={editDevis?.modifiable}
                            raisonNonModifiable={editDevis?.raison_non_modifiable}
                            onDevisRecompose={rechargerDevisRecompose}
                            onDevisEcrit={armerJeton} />

        {/* ── Lignes de produits (QJR100 : <LigneTable/> possède la table,
            l'ajout, la suppression et le réordonnancement ; <RailArgent/>
            possède la chaîne d'argent, DANS la même carte comme avant) ── */}
        <LigneTable
          lines={lines}
          produits={produits}
          linesTableRef={linesTableRef}
          canRenameLine={canRenameLine}
          tarifBadges={tarifBadges}
          quoteLogic={quoteLogic}
          onSetField={setLine}
          onDesignationBlur={onDesignationBlur}
          onProduitChange={onProduitChange}
          onProduitCreated={onProduitCreated}
          onQuantiteChange={onQuantiteChange}
          onSetGroupe={setLineGroupe}
          onRemove={removeLine}
          onMoveUp={moveLineUp}
          onMoveDown={moveLineDown}
          addLine={addLine}
          addStructureLine={addStructureLine}
          handleSaveOrdreLignes={handleSaveOrdreLignes}
          savingOrdreLignes={savingOrdreLignes}
          multiMode={multiMode}
          onMultiModeChange={onMultiModeChange}
          multiAccordionOpen={multiAccordionOpen}
          setMultiAccordionOpen={setMultiAccordionOpen}
          nombreProprietes={nombreProprietes}
          setNombreProprietes={setNombreProprietes}
          multiPreview={multiPreview}
          villaGroups={villaGroups}
          renameVillaGroup={renameVillaGroup}
          removeVillaGroup={removeVillaGroup}
          addVillaGroup={addVillaGroup}
          errorLines={errors.lines}
          accessoiresOnly={accessoiresOnly}
          setAccessoiresOnly={setAccessoiresOnly}
          lignesRemiseesTtc={lignesRemiseesTtc}
          montrerRemise={montrerRemise}
        >
          <RailArgent
            showSans={showSans}
            showAvec={showAvec}
            sansRec={sansRec}
            avecRec={avecRec}
            totals={totals}
            discountPct={discountPct}
            setDiscountPct={setDiscountPct}
            remiseMax={remiseMax}
            tauxTva={tauxTva}
            setTauxTva={setTauxTva}
            pkwc={pkwc}
            prixCible={prixCible}
            setPrixCible={setPrixCible}
            applyPrixCible={applyPrixCible}
            kwp={kwp}
            marge={marge}
            kpiTotal={kpiTotal}
          />
        </LigneTable>

        {/* VX18 — modèles de devis : appliquer un modèle remplace les lignes.
            APX16 — le panneau n'apparaissait QU'EN ÉDITION : on ne pouvait pas
            partir d'un modèle pour créer un devis, ce qui est pourtant le
            besoin le plus fréquent. Il est désormais là DÈS LA CRÉATION
            (replié) ; sans devisId, l'application se fait localement depuis
            l'instantané de lignes du modèle (aucun endpoint nouveau) et la
            section « Enregistrer comme modèle » dit honnêtement qu'elle
            attend que le devis existe. */}
        <DevisPresetPanel devisId={editDevis?.id} onApplied={handlePresetApplied}
                          avantEnregistrement={enregistrerAvantModele} />

        {/* QJR553 (D-QJR5-7) — historique des versions, avec « Revenir à
            cette version » seulement si le devis est modifiable (QJR516). */}
        {editDevis?.id && (
          <HistoriqueConfiguration devisId={editDevis.id}
                                   peutRevenir={peutEditerDevis(editDevis)}
                                   onRevenir={revenirAVersion}
                                   rafraichir={versionHistorique} />
        )}

        {/* QJR540 — blocs repris du modal DevisForm (supprimé) : badge
            « calepinage périmé » (CAL188, lu de `layout_stale`), le calepinage
            qui pilote ce devis (CAL40, silencieux sans calepinage) et les
            pièces jointes du devis. N'existent que sur un devis enregistré. */}
        {editDevis?.id && (
          <Card data-testid="devis-edition-blocs">
            <CardContent className="pt-4 space-y-3">
              <BadgePerime layoutStale={editDevis.layout_stale}
                layoutNbPanneaux={editDevis.layout_nb_panneaux} />
              <BlocCalepinageDevis devisId={editDevis.id} />
              <AjouterBoqElectrique devisId={editDevis.id} modifiable={peutEditerDevis(editDevis)} onAjoute={rechargerDevisRecompose} />
              <LotsMultiSites devisId={editDevis.id} modifiable={peutEditerDevis(editDevis)} onChange={rechargerDevisRecompose} />
              <div>
                <p className="mb-2 text-sm font-semibold text-foreground">Pièces jointes</p>
                <AttachmentsPanel model="ventes.devis" id={editDevis.id} />
              </div>
            </CardContent>
          </Card>
        )}

        {/* QJR215 — registre de surcharges (QJR214/QJR216) : lecture à
            l'ouverture (au montage de ce panneau), pose EXPLICITE d'un
            chemin, retour à l'automatique par chemin. N'existe que sur un
            devis DÉJÀ enregistré (le registre vit sur `Devis.overrides`).
            QJR574 — administrateurs seulement. */}
        {editDevis?.id && estAdmin && (
          <Card data-testid="overrides-panel">
            <GenCardHeader icon={FileText} title="Surcharges (registre)" />
            <CardContent className="pt-4 space-y-3">
              <div className="flex flex-wrap items-end gap-2">
                <select
                  data-testid="overrides-chemin"
                  className="rounded-md border border-input bg-background px-2 py-1.5 text-sm"
                  value={ovChemin}
                  onChange={(e) => setOvChemin(e.target.value)}
                >
                  {/* QJR571 (D-QJR5-8) — un chemin que le moteur ne lit pas
                      est DIT tel quel : sa pose ne change pas le document. */}
                  {CHEMINS_AUTORISES.map((c) => (
                    <option key={c} value={c}>
                      {cheminNonLu(c) ? `${c} — sans effet sur le document` : c}
                    </option>
                  ))}
                </select>
                <Input
                  data-testid="overrides-valeur"
                  placeholder="Valeur (ex. 14, &quot;ONEE&quot;, [1,2,3])"
                  value={ovValeur}
                  onChange={(e) => setOvValeur(e.target.value)}
                  className="max-w-xs"
                />
                <Button type="button" size="sm" data-testid="overrides-poser"
                        disabled={overridesBusy || !ovValeur}
                        onClick={poserOverride}>
                  Poser
                </Button>
              </div>
              {/* Un refus 400 est affiché VERBATIM — jamais avalé. */}
              {overridesErreur && (
                <p className="rounded-md border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive"
                   data-testid="overrides-erreur">
                  {overridesErreur}
                </p>
              )}
              {/* Bloc `effectif` : valeur AUTO vs valeur MANUELLE, côte à
                  côte — la déclaration devient visible, jamais tacite. */}
              {overridesReg?.effectif && Object.keys(overridesReg.effectif).length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs" data-testid="overrides-effectif-table">
                    <thead>
                      <tr className="text-left text-muted-foreground">
                        <th className="pr-3 py-1">Chemin</th>
                        <th className="pr-3 py-1">Auto</th>
                        <th className="pr-3 py-1">Manuel</th>
                        <th className="pr-3 py-1">Effectif</th>
                        <th className="pr-3 py-1">Source</th>
                        <th className="py-1" />
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(overridesReg.effectif).map(([chemin, v]) => (
                        <tr key={chemin} className="border-t border-border"
                            data-testid={`overrides-effectif-row-${chemin}`}>
                          <td className="pr-3 py-1 font-mono">
                            {chemin}
                            {v.non_lu && (
                              <span className="ml-1 font-sans text-muted-foreground"
                                    data-testid={`overrides-non-lu-${chemin}`}>
                                — sans effet sur le document
                              </span>
                            )}
                          </td>
                          <td className="pr-3 py-1">{v.auto == null ? '—' : JSON.stringify(v.auto)}</td>
                          <td className="pr-3 py-1">{v.manuel == null ? '—' : JSON.stringify(v.manuel)}</td>
                          <td className="pr-3 py-1 font-medium">{v.effectif == null ? '—' : JSON.stringify(v.effectif)}</td>
                          <td className="pr-3 py-1">{v.source}</td>
                          <td className="py-1">
                            {v.source === 'manuel' && (
                              <Button type="button" size="sm" variant="ghost"
                                      data-testid={`overrides-regenerer-${chemin}`}
                                      disabled={overridesBusy}
                                      onClick={() => regenererOverride(chemin)}>
                                Régénérer
                              </Button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* ── QJR624 — Échéancier (Édition complète seulement) ── */}
        {editDevis && (
          <CarteEcheancier saisie={echeancierSaisie} setSaisie={setEcheancierSaisie}
                           mode={modeInstallation} effectifs={termesEffectifs} />
        )}

        {/* ── QJR627 (D-QJR5-6) — Notes = texte CLIENT, imprimé (PDF + proposition) ── */}
        <Card>
          <GenCardHeader icon={StickyNote} title="Texte pour le client (imprimé sur le devis)" />
          <CardContent className="pt-4">
            <Textarea rows={3} value={note}
                      onChange={e => setNote(e.target.value)}
                      placeholder="Conditions particulières, précisions pour le client…" />
          </CardContent>
        </Card>

        {/* Avertissements NON bloquants (lead perdu/archivé, chiffres d'étude
            auto) — informatifs, n'empêchent jamais l'enregistrement. */}
        {Object.values(warnings).filter(Boolean).length > 0 && (
          <div className="rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
            {Object.values(warnings).filter(Boolean).map((w, i) => (
              <p key={i}>{w}</p>
            ))}
          </div>
        )}
        {/* Toute raison de blocage est VISIBLE à côté du bouton — jamais de
            clic silencieux sans effet. */}
        {(errors.submit || errors.lines || errors.client || errors.conso || errors.factures) && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive" data-testid="erreur-enregistrement">
            {errors.submit || errors.lines || errors.client || errors.conso || errors.factures}
          </div>
        )}

        {/* ── Création ── */}
        <Card>
          <GenCardHeader icon={FileText}
                         title={editDevis ? `Modification du devis ${editDevis.reference}` : 'Création du Devis'} />
          <CardContent className="pt-4">
            <p className="text-sm text-muted-foreground">
              {embedded
                ? "Vérifiez puis enregistrez. Le devis s'affiche ensuite ici même "
                  + 'avec son PDF, sans quitter la fiche du lead.'
                : 'Vérifiez les informations ci-dessus puis créez le devis. Le PDF '
                  + 'premium 3 pages se génère ensuite depuis la liste des devis (bouton « PDF »).'}
            </p>
            {modeInstallation === 'agricole' && (apercuPompage?.donnees?.prix_a_renseigner || []).length > 0 && (
              <div className="mt-3 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning"
                   data-testid="pompage-prix-a-renseigner">
                Attention : seules des pompes <strong>sans prix renseigné</strong> conviennent
                ({apercuPompage.donnees.prix_a_renseigner.join(', ')}). Aucune pompe ne sera chiffrée
                au devis tant que leur prix n'est pas saisi dans Stock.
              </div>
            )}
            {superieurMsg && (
              <div className={`mt-3 rounded-lg border p-3 text-sm ${superieurMsg.ok
                ? 'border-success/30 bg-success/10 text-success'
                : 'border-destructive/30 bg-destructive/10 text-destructive'}`}>
                {superieurMsg.text}
              </div>
            )}
            <div className="gen-actions-sticky mt-3 flex flex-wrap items-center justify-end gap-3">
              {/* VX138(d) — bandeau sticky au scroll (plus seulement mobile) :
                  TTC courant condensé, dérivé de `totals`/`kpiTotal` déjà en
                  mémoire (même valeur que le rail latéral VX16) ; masqué en
                  lg+ où le rail latéral l'affiche déjà. */}
              <div className="mr-auto flex items-baseline gap-1.5 text-sm lg:hidden">
                <span className="text-muted-foreground">Total TTC</span>
                <strong className="tabular-nums text-base font-semibold text-foreground">
                  {formatMoney(kpiTotal)}
                </strong>
              </div>
              {/* QJ28 — notification manuelle au supérieur (devis déjà enregistré) */}
              {editDevis && (
                <Button type="button" variant="outline" loading={superieurBusy}
                        onClick={contacterSuperieur}
                        title="Envoyer une notification à mon supérieur avec le lien de ce devis">
                  Contacter mon supérieur
                </Button>
              )}
              {!embedded && (
                <Button type="button" variant="outline" onClick={handleReset}>
                  <RotateCcw /> Réinitialiser
                </Button>
              )}
              <Button type="button" variant="ghost" onClick={cancel}>
                Annuler
              </Button>
              <Button type="submit" loading={saving}>
                {saving
                  ? 'Enregistrement...'
                  : (editDevis ? <><Sun /> Enregistrer les modifications</> : <><Sun /> Créer le devis</>)}
              </Button>
            </div>
          </CardContent>
        </Card>
      </form>

      {/* VX16 — rail récapitulatif STICKY (lg+ uniquement, jamais sur mobile).
          Total TTC de l'option retenue + marge indicative (INTERNE, jamais dans
          le PDF/client) + résumé système (kWc/panneaux) + Annuler/Créer câblés
          sur le même formulaire (form="gen-form"). */}
      <aside className="gen-summary-rail hidden lg:flex lg:w-72 lg:shrink-0 lg:sticky lg:flex-col lg:gap-3"
             style={{ top: 'var(--header-h, 64px)' }}>
        {/* APX12 — le total du rail devient LE chiffre le plus soigné de
            l'app : il passe par `<Stat>` comme les KPI d'argent des deux
            autres surfaces (bandeau statuts DevisList, cockpit trésorerie
            FactureList). Il n'avait jusqu'ici NI `.num` NI chiffres
            tabulaires — le seul montant héros du dossier à ne pas les
            porter. `tone="impact"` lui pose l'accent brass du module. */}
        {/* APX16 — le scénario « Les deux (Sans + Avec) » construisait DEUX
            options mais le rail n'en montrait qu'UNE : impossible de voir
            l'écart pendant la construction. Les deux totaux sont désormais
            côte à côte, avec l'écart en MAD ET en %. L'option recommandée
            garde l'accent (`tone="impact"`). */}
        {showSans && showAvec ? (
          <>
            <Stat
              tone={!avecRec ? 'impact' : undefined}
              data-testid={avecRec ? 'gen-rail-total-sans' : 'gen-rail-total'}
              data-figure="total_ttc" data-figure-option="sans"
              label="Total sans batterie · TTC"
              value={formatMoney(totals.totalSans)}
              hint={avecRec ? undefined : 'Option recommandée'}
            />
            <Stat
              tone={avecRec ? 'impact' : undefined}
              data-testid={avecRec ? 'gen-rail-total' : 'gen-rail-total-avec'}
              data-figure="total_ttc" data-figure-option="avec"
              label="Total avec batterie · TTC"
              value={formatMoney(totals.totalAvec)}
              hint={avecRec ? 'Option recommandée' : undefined}
            />
            {ecartOptions != null && (
              <p className="num text-xs text-muted-foreground" data-testid="gen-rail-ecart">
                Écart batterie : {formatMoney(ecartOptions)}
                {ecartOptionsPct != null ? ` (${ecartOptionsPct > 0 ? '+' : ''}${ecartOptionsPct} %)` : ''}
              </p>
            )}
          </>
        ) : (
          <Stat
            tone="impact"
            data-testid="gen-rail-total"
            label={`Total ${scenario === 'Avec batterie' ? 'avec batterie' : 'sans batterie'} · TTC`}
            value={formatMoney(kpiTotal)}
          />
        )}
        <Card>
          <CardContent className="pt-4 flex flex-col gap-3">
            {marge != null && (
              <div>
                <div className="text-xs uppercase tracking-wide text-muted-foreground">
                  Marge indicative (interne)
                </div>
                <div className={`text-sm font-semibold ${marge < 0 ? 'text-destructive' : 'text-success'}`}>
                  {formatMoney(marge)}
                  {kpiTotal > 0 ? ` (${Math.round(marge / kpiTotal * 100)} %)` : ''}
                </div>
              </div>
            )}
            <div className="border-t border-border pt-3">
              <div className="text-xs uppercase tracking-wide text-muted-foreground mb-1">Système</div>
              <div className="text-sm text-foreground">
                {kwp > 0 ? `${formatNumber(kwp, { decimals: 2 })} kWc` : '— kWc'}
                {parseInt(nbPanneaux) > 0 ? ` · ${parseInt(nbPanneaux)} panneaux` : ''}
              </div>
            </div>
            <div className="flex flex-col gap-2 pt-1">
              <Button type="submit" form="gen-form" loading={saving}>
                {saving ? 'Enregistrement...'
                  : (editDevis ? <><Sun /> Enregistrer</> : <><Sun /> Créer le devis</>)}
              </Button>
              <Button type="button" variant="ghost" onClick={cancel}>Annuler</Button>
            </div>
          </CardContent>
        </Card>
      </aside>
      </div>
      <ClientQuickCreateModal
        open={clientQuickCreateOpen}
        onClose={() => setClientQuickCreateOpen(false)}
        onCreated={(c) => {
          setClients(cs => [...cs, c])
          setClientId(String(c.id))
          setClientQuickCreateOpen(false)
        }}
      />

      {/* QP2 — dialogue de renommage : deux choix explicites lorsqu'une ligne
          est renommée à l'écart du nom du produit lié (rôle autorisé). */}
      <Dialog open={!!renameDialog} onOpenChange={(o) => { if (!o) setRenameDialog(null) }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Désignation modifiée</DialogTitle>
            <DialogDescription>
              Vous avez renommé cette ligne
              {renameDialog ? ` « ${renameDialog.nouveauNom} »` : ''} — elle diffère du
              produit du stock{renameDialog ? ` « ${renameDialog.ancienNom} »` : ''}.
              Que souhaitez-vous faire ?
            </DialogDescription>
          </DialogHeader>
          {renameError && (
            <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {renameError}
            </div>
          )}
          <DialogFooter className="flex-col gap-2 sm:flex-col sm:items-stretch">
            <Button type="button" variant="outline" onClick={renameHereOnly} disabled={renameBusy}>
              Renommer sur ce devis seulement
            </Button>
            <Button type="button" onClick={renameAsNewProduct} loading={renameBusy}>
              {renameBusy
                ? 'Création…'
                : `Créer un nouveau produit « ${renameDialog?.nouveauNom ?? ''} » dans le stock`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
