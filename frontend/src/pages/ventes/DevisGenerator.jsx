import {
  useCallback, useEffect, useMemo, useReducer,
  useRef, useState,
} from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  // QJR101 — `Sprout` est parti avec le panneau agricole (`PanneauAgricole`),
  // qui l'importe désormais lui-même.
  ArrowLeft, Target, ClipboardList, Zap,
  // QJR100 — `ShoppingCart` et `Trash2` sont partis avec la table de lignes
  // (`generator/LigneTable.jsx`), qui les importe désormais elle-même.
  FileText, Sun,
  // EZ3 — actions du panneau de succès (envoyer / aperçu).
  Send, Eye,
  // FOUNDER 26/08 — bouton « Recalculer le dimensionnement ».
  RefreshCw,
} from 'lucide-react'
// QX21 — la sauvegarde passe désormais par les endpoints ATOMIQUES de ventesApi
// (createDevisAtomic / replaceLignesDevis) ; createDevis/addLigneDevis (1+N
// round-trips non gardés) ne sont plus utilisés ici.
import {
  LEAD_TYPE_TO_MODE,
  // QJR665 — conso de l'étude C&I = celle du balayage (barème national).
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
import {
  saisiesEconomiePompage,
  TARIF_SAISIE_VIDE, tarifDeclareDepuisSaisie,
  ECO_CI_VIDE, saisiesEconomieCi,
} from '../../features/ventes/quote/etudeMarcheBloc'
import { useApercuEconomieCi } from '../../features/ventes/quote/hooks/useApercuEconomieCi'
import {
  POMPAGE_SAISIE_VIDE, etatPompageEcran, poserSaisie, libelleProvenance,
} from '../../features/ventes/etudePompagePreviewPur'
import { entreesPompageDuLead } from '../../features/ventes/quote/entreesPompageLead'
import {
  ECO_POMPAGE_VIDE, ATTESTATION_VIDE,
} from '../../features/ventes/quote/etudeMarcheBloc'
import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import parametresApi from '../../api/parametresApi'
import { fetchAllPages } from '../../utils/fetchAllPages'
import ClientQuickCreateModal from './ClientQuickCreateModal'
// QJR100 — `DevisLineRow` n'est plus importé ici : c'est `LigneTable` qui
// l'enrobe désormais (un seul endroit monte une ligne de devis).
// TAILLES (fondateur 26/08/2026) — écran vendeur Éco/Recommandé/Max, composant
// autonome (se masque lui-même hors résidentiel/devis non enregistré) pour ne
// pas alourdir ce fichier déjà volumineux.
import DevisOffresTailles from './DevisOffresTailles'
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
  Input, Label, Segmented, Switch,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  // QJR101 — `HelpTip` est parti avec la carte des factures : les trois
  // panneaux réseau l'importent chacun pour leur aide « distributeur ».
  ScrollProgress,
  // QJR540 — `RelationCounters` est parti avec les bandeaux d'édition (SPL53).
} from '../../ui'
// QJR540 — blocs issus de l'ancien modal DevisForm (supprimé) : le calepinage qui
// pilote ce devis (CAL40), son badge « périmé » (CAL188) et les pièces jointes
// du devis (seule UI de pièces jointes devis).
// QJR553 (D-QJR5-7) — historique des versions + « Revenir à cette version ».
// QJR589 — bannière de dérive lead → devis à deux gestes (partagée cockpit).
import BandeauDeriveLead from '../../features/ventes/quote/BandeauDeriveLead'
// STKCAT10 — le sélecteur de structures PILOTÉ PAR LE CATALOGUE (décision
// fondateur 16/09/2026) qui remplace le bouton acier/aluminium ; il rend
// lui-même ce bouton en REPLI quand la société n'a aucune catégorie typée
// « structure ». Partagé tel quel avec la fiche lead (SectionSite).
import StructureSelector from '../../features/stock/StructureSelector'
import { structuresEligibles } from '../../features/stock/structures'
import { useCanCreateProduit } from '../../hooks/useHasPermission'
import useKeyboardAwareScroll from '../../hooks/useKeyboardAwareScroll'
import { useDirtyGuard } from '../../ui/useDirtyGuard'
import { useDraftAutosave } from '../../ui/useDraftAutosave'
import { usePasteClean, parsePastedAmount } from '../../hooks/usePasteClean'
import {
  // QJR101 — `MONTHS_FR` (grille des 12 mois), le barème MT et
  // `COMMERCIAL_CATEGORIES` sont partis avec les panneaux de marché qui les
  // rendent. CIQ126 — l'étude C&I locale (et son avertissement MT) est
  // supprimée : le moteur serveur C&I est la seule source.
  CHART_MONTHS, DEFAULT_MONTHLY_BILLS, DAY_USAGE_DEFAULTS,
  formatMoney, estimerMois, htFromTtc,
  comptePanneauxOption,
  kwcFactureDesLignes, kwcPourPanneaux,
  optionTotalsTTC, defaultProductLines,
  prixParKwc, discountForTarget,
  computeBuyCostDetail, avecBatterieAvailability, KWH_PRICE, EFFICIENCY,
  TVA_STANDARD_DEFAUT, TVA_PANNEAUX_DEFAUT,
  // QJR66 — `buildEtudeParamsChoice` n'est PLUS importé ici : l'écran n'écrit
  // plus `scenario` / `recommended_option` / `distributeur` / `conso_annuelle`
  // dans `etude_params` (registre de surcharges D12 côté serveur). La fonction
  // reste dans solar.js, avec ses tests — elle n'a simplement plus d'appelant
  // sur ce chemin d'enregistrement.
  baremeDepuisProfil, multiPropertyPreviewTTC, lignesRemiseesParPanier,
  COMMERCIAL_CATEGORY_QUESTIONS,
  // FINDING 25/08 — consommation réelle dérivée des factures par le barème :
  // sans elle le modèle d'économie ne sature pas et l'ascension marginale
  // sur-vend jusqu'au plafond du balayage.
  // PVMRQ — libellé FR d'un rôle ROLES_AUTO_COMPOSITION, pour le bandeau
  // « marque épinglée introuvable ».
  roleLabel,
  // PVORD (fondateur 19/08/2026) — ordre par défaut des lignes de devis :
  // dérive la séquence de rôles depuis l'écran (bouton « Enregistrer cet
  // ordre »), appliquée par autoFillLines via ordreLignes.
  // QJR546 — garde « produit tarifé » des lignes d'un modèle appliqué.
  _hasPrix,
  // ERR-QAC-KWH-SAISI-INCOHERENT-FACTURES — kWh déclaré vs factures du lead.
  MESSAGE_KWH_INCOHERENT,
} from '../../features/ventes/solar'
import { formatNumber } from '../../lib/format'
// CJ2b — l'aperçu du moteur horaire résidentiel vit dans `useApercuEtude`
// (SPL51, dérivations) et `ApercuSimulation` (SPL52, carte).
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
// QJR215 — la liste blanche du registre d'overrides (contrat QJR1), DÉRIVÉE
// du même module que le client API (QJR214) : jamais une liste recopiée ici.
import {
  CHEMINS_AUTORISES, valeursImposees,
} from '../../features/ventes/quote/overrides'
import { deuxValeursDim as selecteurDeuxValeursDim }
  from '../../features/ventes/quote/paireDimensionnement'
// QJR426 (DR5) — les 13 cartes de métrique du générateur (bloc Aperçu de la
// Simulation + étude industrielle/commercial) portent désormais la VALEUR
// SIGNÉE (`moteur`/`apercu`) au lieu d'un `value=` littéral : `CarteMetrique`
// reste le seul déballeur (`unwrap`), cet écran ne fait que signer.
// QJR523 — UN seul couple de mappeurs lignes serveur ⇄ écran.
// QJR658 — devis ⇄ état d'écran : un module pur.
// CIQ125 — profil déclaré C&I (corps de l'aperçu serveur + entrées v2).
import { useEtudeCiPreview } from '../../features/ventes/etudeCiPreview'
import {
  profilCiVide, poserProfilCi, corpsCiDepuisProfil, profilCiAncre,
} from '../../features/ventes/quote/profilCi'
// QJR100 — les trois morceaux extraits de cet écran. `CarteMetrique` est LE
// seul déballeur d'une valeur signée ; `LigneTable` possède la table de lignes
// (ajout/suppression/réordonnancement) ; `RailArgent` possède la chaîne
// d'argent (totaux, remise, TVA, prix cible, marge interne).
import { GenCardHeader } from './generator/CarteMetrique'
// QJR624 — l'échéancier éditable de l'Édition complète (D-QJR5-10).
import { CONDITIONS_VIDES } from '../../features/ventes/echeancierEdition'
import LigneTable from './generator/LigneTable'
import RailArgent from './generator/RailArgent'
import IndicationRegistre from './generator/IndicationRegistre'
import PanneauSurcharges from './generator/PanneauSurcharges'
import CarteCreation from './generator/CarteCreation'
import BlocsEditionComplete from './generator/BlocsEditionComplete'
import CarteLeadClient from './generator/CarteLeadClient'
import ApercuSimulation from './generator/ApercuSimulation'
import BandeauxEdition from './generator/BandeauxEdition'
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
// ATOT25 — désormais via `solar.lignesRemiseesParPanier` (répartition par panier).
import { usePersistanceDevis } from '../../features/ventes/quote/hooks/usePersistanceDevis'
import { normaliserNombreEntete } from '../../features/ventes/quote/etatDevis'
import { useChargeurEdition } from '../../features/ventes/quote/hooks/useChargeurEdition'
import { useRegistreOverrides } from '../../features/ventes/quote/hooks/useRegistreOverrides'
import { useLignesEcran } from './generator/hooks/useLignesEcran'
import { useCompositionEcran } from './generator/hooks/useCompositionEcran'
import { useLeadClientEcran } from './generator/hooks/useLeadClientEcran'
import { useApercuEtude } from './generator/hooks/useApercuEtude'
// SPL43 — aides de module déplacées (fabrique de lignes, défauts d'écran).
import { withKeys } from '../../features/ventes/quote/ligneFabrique.js'
import {
  partDiurneParDefaut,
  FENETRE_REFERENCE_MS,
} from '../../features/ventes/quote/ecranDefauts.js'

// QX43 — 4 marchés réels : industriel et commercial sont désormais distincts.
const MODE_OPTIONS = [
  { value: 'residentiel', label: '🏠 Résidentiel' },
  { value: 'industriel', label: '🏭 Industriel' },
  { value: 'commercial', label: '🏪 Commercial' },
  { value: 'agricole', label: '🌾 Agricole (pompage)' },
]



// ORDRE FONDATEUR (24/08) — « tous les devis sont générés par défaut avec DEUX
// OPTIONS (sans + avec batterie), sauf si le commercial le précise sur le devis
// modifiable ». Le vocabulaire est le contrat EXACT du moteur PDF (constantes
// SCENARIO_* d'apps/ventes/services.py) : jamais reformulé ici.
// QJR99 — les quatre constantes ET la table QX19 `BATTERIE_LEAD_VERS_SCENARIO`
// ne sont plus RE-DÉCLARÉES ici : elles viennent du reducer (source unique,
// `features/ventes/quote/sizingReducer.js`), qui les possède depuis QJR87.


// DC11 / QJR106 / QJR589 — la bannière « valeurs du lead modifiées » (libellés
// et gestes) vit dans `features/ventes/quote/BandeauDeriveLead.jsx`, partagée
// avec la fenêtre devis du cockpit.

// QJR108 — `RIEN_A_CHIFFRER` / `valeurMoteurDim` / `paireDimensionnement`
// vivaient ICI, non exportés (ce fichier n'exporte que des composants —
// react-refresh), donc vérifiables SEULEMENT par expression régulière sur le
// source. Ils vivent désormais dans le module PUR
// `features/ventes/quote/paireDimensionnement.js`, où ils sont testés par
// EXÉCUTION. Déplacement seul : pas une ligne de logique n'a changé.








// QJR100 — `GenCardHeader` et `MetricCard` ne sont plus DÉFINIS ici : ils
// vivent dans `generator/CarteMetrique.jsx`, partagés par les morceaux
// extraits (LigneTable, RailArgent). `MetricCard` s'appelle désormais
// `CarteMetrique` et sait, EN PLUS, déballer une valeur signée (QJR86).

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
  // AGNR19 — le client d'ARRIVÉE (`?client=<id>`) relu par son id : jamais
  // cherché dans une page de la liste.
  const [clientArrivee, setClientArrivee] = useState(null)
  const clientsConnus = (clientArrivee
    && !clients.some(c => String(c.id) === String(clientArrivee.id)))
    ? [...clients, clientArrivee] : clients
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
  const facturesEcartConfirmeRef = useRef(null)
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
  // AGNR21 — l'enregistrement PARTIEL (lignes écrites, étude ou registre
  // refusés) : bandeau persistant, l'écran reste sur le formulaire.
  const [reserveEnregistrement, setReserveEnregistrement] = useState(null)
  // AGNR35 — le barème EFFECTIF de la société (profil `bareme_effectif`) :
  // `null` = barème national (constantes de l'écran, chiffres inchangés).
  const [baremeSociete, setBaremeSociete] = useState(null)
  // AGNR33 — refus 400 « par champ » de l'en-tête et notes de normalisation
  // (AGNR8), affichés sous LE champ concerné.
  const [erreursChamps, setErreursChamps] = useState({})
  // QJR549 (contrat QJR503) — VERROU OPTIMISTE. `jetonRef` = `updated_at` du
  // devis tel que l'écran le connaît : capturé au chargement `?edit=` (et à
  // chaque rechargement), ré-armé depuis la réponse de CHAQUE écriture de cet
  // écran (replace-lines, etude-params, tailles d'offre) — sans quoi l'écran
  // se signalerait ses propres écritures. Envoyé en `expected_updated_at` ;
  // un 409 `devis_modifie` affiche la bannière « Modifié par X ».
  const jetonRef = useRef(null)
  const forcerSansJetonRef = useRef(false)
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
  // SPL46 — registre de surcharges (état + gestes déplacés tels quels dans le hook).
  const {
    overridesReg, setOverridesReg, estAdmin, overridesBusy, overridesErreur, setOverridesErreur,
    ovChemin, setOvChemin, ovValeur, setOvValeur, messageErreurOverrides, poserOverride,
    regenererOverride,
  } = useRegistreOverrides({
    dispatchSizing, editDevis, captureReferenceJusqua, setRecommendedChoice,
  })

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
  // CIQ226 — conditions contractuelles DÉCLARÉES (retenue, pénalités,
  // caution, organisme financeur, référence de commande) : rien de pré-rempli.
  const [conditions, setConditions] = useState(CONDITIONS_VIDES)
  const conditionsServies = useRef([])
  const setCondition = (champ, valeur) => setConditions((c) => ({ ...c, [champ]: valeur }))
  const setEcheancierSaisie = useCallback((valeur) => {
    echeancierAEnvoyer.current = true
    setEcheancierSaisieBrut(valeur)
  }, [])

  // ── Factures électriques (valeurs initiales du simulateur) ──
  const [fHiver, setFHiver] = useState('')
  const [fEte, setFEte] = useState('')
  const [monthly, setMonthly] = useState(DEFAULT_MONTHLY_BILLS)
  // AGNR13 — la PROVENANCE de chaque case du détail mensuel : 'exemple'
  // (valeur du simulateur, jamais une facture du client), 'derivee' (hiver /
  // été, lead) ou 'tapee'. Tant qu'une case est 'exemple', la série ne part
  // jamais comme `factures_mensuelles_reelles`.
  const [provenanceMois, setProvenanceMois] = useState(() => Array(12).fill('exemple'))
  const poserMoisDerives = (valeurs) => {
    setMonthly(valeurs)
    setProvenanceMois(Array(12).fill('derivee'))
  }
  // Une série RELUE du devis (`?edit=`) est celle que le vendeur avait saisie.
  const poserMoisRelus = (valeurs) => {
    setMonthly(valeurs)
    setProvenanceMois(Array(12).fill('tapee'))
  }
  // AGNR17 — hiver / été TAPÉS par le vendeur (frappe ou collage) : avec un
  // mois tapé ou relu, les factures sont PROTÉGÉES — aucun pré-remplissage
  // (lead, profil de site, frappe hiver/été) ne les écrase sans geste.
  const [facturesTapees, setFacturesTapees] = useState(false)
  const facturesProtegees = facturesTapees || provenanceMois.includes('tapee')
  // Lu par les réponses ASYNCHRONES (profil de site) : la valeur COURANTE,
  // jamais celle du rendu qui a lancé la requête.
  const facturesProtegeesRef = useRef(facturesProtegees)
  useEffect(() => { facturesProtegeesRef.current = facturesProtegees }, [facturesProtegees])
  // Un changement de lead repart d'un état VIDE (jamais les factures de A).
  const reinitialiserFactures = () => {
    setFHiver('')
    setFEte('')
    setMonthly(DEFAULT_MONTHLY_BILLS)
    setProvenanceMois(Array(12).fill('exemple'))
  }
  const [avisFactures, setAvisFactures] = useState(null)
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
  // PVORD (fondateur 19/08/2026) — bouton « Enregistrer cet ordre comme
  // ordre par défaut » (voir handleSaveOrdreLignes) : état de chargement
  // dédié, séparé de `saving` (l'enregistrement du DEVIS) — les deux actions
  // sont indépendantes et ne doivent pas se griser l'une l'autre.
  const [savingOrdreLignes, setSavingOrdreLignes] = useState(false)
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
  // CIQ125 — LE profil déclaré C&I (commercial ET industriel) : la SEULE
  // saisie de consommation de ces marchés, tapée telle quelle (texte), mise à
  // la forme du contrat `etude_ci_preview.json` par `quote/profilCi.js`.
  const [profilCi, setProfilCi] = useState(profilCiVide)
  // CIQ222 — le tarif de SA facture (contrat `tarifs_ci.json`), tel que tapé.
  const [tarifSaisie, setTarifSaisie] = useState(TARIF_SAISIE_VIDE)
  const setTarifChamp = (champ, valeur) => setTarifSaisie((t) => ({ ...t, [champ]: valeur }))
  // CIQ223 — les saisies de l'économie C&I (contrat `economie_ci.json`).
  const [ecoCi, setEcoCi] = useState(ECO_CI_VIDE)
  const setEcoChamp = (champ, valeur) => setEcoCi((e) => ({ ...e, [champ]: valeur }))
  // QX44 — étude commerciale par catégorie (mode commercial). categorie +
  // réponses par catégorie (clés snake_case), stockées dans etude_params.
  const [categorieCommerciale, setCategorieCommerciale] = useState(CATEGORIE_NON_PRECISEE)
  const [commercialAnswers, setCommercialAnswers] = useState({})
  const setCommercialAnswer = (key, val) =>
    setCommercialAnswers(prev => ({ ...prev, [key]: val }))
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
  // AGR420 — une énergie retouchée à la main perd sa provenance « lead ».
  const majEco = useCallback(
    (cle, valeur) => setEcoPompage((e) => ({
      ...e, [cle]: valeur, ...(cle === 'energie' ? { energieProvenance: null } : {}),
    })), [])
  // AGR420 — valeurs posées par un lead (garde « touché » : une saisie du
  // vendeur n'est jamais écrasée) et leur provenance affichée.
  const posesLead = useRef({})
  const [provenancesLead, setProvenancesLead] = useState([])
  // Valeurs COURANTES (la relecture du lead est asynchrone : une fermeture
  // périmée ne verrait pas ce que le vendeur vient de taper).
  const courantPompage = useRef({})
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
  useEffect(() => {
    courantPompage.current = {
      pompeHmt, pompeDebit, farmHmtStatic, pompeProfondeur, pompeDistance,
      pompeCv, pompeType, farmRegion, farmCrop, farmSurfaceHa, farmIrrigation,
      eco: ecoPompage,
    }
  })

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
    fHiver, fEte, monthly, provenanceMois, distributeur, realBillMode, realBillMad, realBillKwh,
    realBillSaisi, distributeurChoisi,
    nbPanneaux, panelW, structureType, structureProduitId, dayUsage, lines, tauxTva, discountPct,
    multiMode, nombreProprietes, villaGroups, modeInstallation, consoMensuelle,
    categorieCommerciale, commercialAnswers,
    tensionRaccordement, profilCi,
    prixCible, remiseMax, accessoiresOnly, horsReseau, horsReseauTouched,
    pompeCv, pompeType, pompeAlim, pompeHmt, pompeDebit, pompeProfondeur,
    pompeDistance, farmRegion, farmCrop, farmSurfaceHa,
    farmIrrigation, ecoPompage, attestationAgricole, farmHmtStatic,
    farmHmtDrawdown, pompageSaisie,
    // AGNR30 — conditions, échéancier, tarif déclaré et éco C&I : les
    // modifier arme la garde de sortie et crée un brouillon local.
    conditions, echeancierSaisie, tarifSaisie, ecoCi,
  }), [
    leadId, clientId, dateValidite, scenario, recommendedChoice, note,
    fHiver, fEte, monthly, provenanceMois, distributeur, realBillMode, realBillMad, realBillKwh,
    realBillSaisi, distributeurChoisi,
    nbPanneaux, panelW, structureType, structureProduitId, dayUsage, lines, tauxTva, discountPct,
    multiMode, nombreProprietes, villaGroups, modeInstallation, consoMensuelle,
    categorieCommerciale, commercialAnswers,
    tensionRaccordement, profilCi,
    prixCible, remiseMax, accessoiresOnly, horsReseau, horsReseauTouched,
    pompeCv, pompeType, pompeAlim, pompeHmt, pompeDebit, pompeProfondeur,
    pompeDistance, farmRegion, farmCrop, farmSurfaceHa,
    farmIrrigation, ecoPompage, attestationAgricole, farmHmtStatic,
    farmHmtDrawdown, pompageSaisie,
    conditions, echeancierSaisie, tarifSaisie, ecoCi,
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
    // AGNR30 — conditions, échéancier, tarif déclaré, éco C&I.
    if (d.conditions != null) setConditions(d.conditions)
    if (d.echeancierSaisie != null) setEcheancierSaisie(d.echeancierSaisie)
    if (d.tarifSaisie != null) setTarifSaisie(d.tarifSaisie)
    if (d.ecoCi != null) setEcoCi(d.ecoCi)
    // AGNR13 — la provenance revient avec le brouillon ; un brouillon ancien
    // (sans elle) garde la règle d'avant : une série modifiée = saisie.
    if (Array.isArray(d.provenanceMois) && d.provenanceMois.length === 12) {
      setProvenanceMois(d.provenanceMois)
    } else if (Array.isArray(d.monthly)
      && d.monthly.some((v, i) => Number(v) !== DEFAULT_MONTHLY_BILLS[i])) {
      setProvenanceMois(Array(12).fill('tapee'))
    }
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
    if (d.tensionRaccordement != null) {
      dispatchSizing({ type: 'SAISI', champ: 'tension', valeur: d.tensionRaccordement })
    }
    if (d.profilCi && typeof d.profilCi === 'object') setProfilCi({ ...profilCiVide(), ...d.profilCi })
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
    // AGNR26 — `pompeHeures` d'un brouillon ancien est ignoré (champ retiré).
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
      // ALEA40 — clients et leads lus EN ENTIER (pagination DRF 50) : un
      // client ou un lead hors des 50 plus récents reste sélectionnable.
      fetchAllPages((page) => crmApi.getClients({ page }).then((r) => r.data))
        .then((d) => setClients(d?.results ?? d)).catch(() => { fail('clients'); throw 0 }),
      fetchAllPages((page) => crmApi.getLeads({ page }).then((r) => r.data))
        .then((d) => setLeads(d?.results ?? d)).catch(() => { fail('leads'); throw 0 }),
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
  // ATOT25 — la répartition se fait désormais PAR PANIER sur les HT
  // persistés (miroir de `builder._annoter_remise`) : chaque ligne vaut la
  // ligne du PDF au centime, et l'« Arrondi commercial » du rail explique
  // l'écart entre Σ lignes et le total affiché.
  const remiseParPanier = useMemo(
    () => lignesRemiseesParPanier(lines, discountPct, {
      scenario, option: avecRec && showAvec ? 'avec' : 'sans',
    }),
    [lines, discountPct, scenario, avecRec, showAvec],
  )
  const lignesRemiseesTtc = remiseParPanier.parLigne
  // Condition d'affichage = remise > 0 (jamais « montant ≠ catalogue ») :
  // remise nulle ⇒ écran inchangé à l'octet (le miroir rend le catalogue).
  const montrerRemise = (parseFloat(discountPct) || 0) > 0

  // QJ31 — aperçu multi-propriétés (miroir écran du backend QJ29). Null quand
  // aucun mode multi n'est actif (aperçu mono-système inchangé).
  const multiPreview = useMemo(
    () => multiPropertyPreviewTTC(lines, {
      nombreProprietes: multiMode === 'multiplier' ? nombreProprietes : null,
      discountPct,
      // ATOT24 — la chaîne du rail : scénario + option effective (celle de
      // `kpiTotal`), jamais l'option « sans » inconditionnelle.
      scenario,
      option: avecRec && showAvec ? 'avec' : 'sans',
    }),
    [lines, multiMode, nombreProprietes, discountPct, scenario, avecRec, showAvec],
  )

  // SPL51 — dérivations d'aperçu et d'étude horaire (déplacées telles quelles dans le hook, même position : l'ordre des hooks est inchangé).
  const {
    capaciteBatterieInconnue, consoAnnuelleReelle, facturesSaisies, moisNonSaisis, leadsListe,
    selectedLead, typeLeadEffectif, marcheSegment, bandeauSegment, rappelIce, changerTypeLead, roi,
    villeCalculLead, etudeHoraireCorps, etudeHoraireDonnees, etudeHoraireChargement,
    etudeHoraireErreur, etudeHoraireAnnuel, etudeHoraireSourceServeur, etudeHoraireAnnuelAvec,
    etudeHoraireLignes, etudeHoraireSourceLabel, etudeHoraireFalaise, etudeHoraireGlitch,
    etudeHoraireEstimationConso, ligneStockageOuverte, setLigneStockageOuverte,
    apercuProductionKwh, apercuEcoSans, verdictBatterieServeur, batterieInvendableServeur,
    apercuEcoAvec, apercuPaybackSans, apercuPaybackAvec, apercuPaybackSansJamais,
    apercuPaybackAvecJamais, signerEcoOuRoi, chartData,
  } = useApercuEtude({
    monthly, lines, totals, kwp, kwpLignes, kwpAvec, dayUsage, realBillMode, realBillKwh,
    realBillMad, distributeur, baremeSociete, provenanceMois, realBillSaisi, leadDuDevis, leads,
    leadId, modeInstallation, clientsConnus, clientId, confirm, quoteLogic, editId, fHiver, fEte,
    sizing, dispatchSizing,
  })

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
      || !!apercuCi.donnees || pompageAutoFilled
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

  // ── CIQ125 — profil déclaré C&I → aperçu du moteur serveur, en direct ──
  // Le corps part tel que tapé (aucun calcul, aucun défaut) ; le lead et le
  // devis voyagent pour que le serveur résolve ce qui n'est pas saisi
  // (`entrees_resolues`, priorité corps > devis > lead). AUCUN appel hors C&I.
  const marcheCi = modeInstallation === 'commercial' || modeInstallation === 'industriel'
  const ctxProfilCi = {
    mode: modeInstallation,
    lead: leadId ? Number(leadId) : null,
    devis: editId ? Number(editId) : null,
    ville: villeCalculLead || null,
    categorie: modeInstallation === 'commercial' && categorieCommerciale !== CATEGORIE_NON_PRECISEE
      ? categorieCommerciale : null,
    reponses: modeInstallation === 'commercial' ? commercialAnswers : null,
    // CIQ222 — le tarif déclaré part au moteur (`corps.tarif`), jamais une grille.
    tarif: tarifDeclareDepuisSaisie(tarifSaisie, { aujourdhui: new Date().toISOString().slice(0, 10) }),
  }
  const corpsCi = marcheCi ? corpsCiDepuisProfil(profilCi, ctxProfilCi) : null
  const apercuCi = useEtudeCiPreview(corpsCi)
  const resoluesCi = apercuCi.donnees?.entrees_resolues || {}
  // Consommation connue : saisie dans le profil (ou taille explicite), ou
  // reprise de la fiche lead par le serveur (valeur résolue non vide).
  const consoCiConnue = profilCiAncre(profilCi)
    || [resoluesCi.kwh_mensuels?.valeur, resoluesCi.kwh_annuel?.valeur]
      .some((v) => (Array.isArray(v) ? v.some((x) => Number(x) > 0) : Number(v) > 0))
  const setChampCi = (chemin, valeur) => setProfilCi((p) => poserProfilCi(p, chemin, valeur))

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

  // AGR420 — recopie `lead.entrees_pompage` dans les états agricoles. Une
  // entrée absente laisse l'état VIDE ; un état déjà saisi par le vendeur
  // (autre que la valeur posée par un lead) n'est jamais écrasé.
  const appliquerEntreesPompage = (lead) => {
    const res = entreesPompageDuLead(lead)
    if (!res) return
    const poseurs = {
      pompeHmt: setPompeHmt, pompeDebit: setPompeDebit,
      farmHmtStatic: setFarmHmtStatic, pompeProfondeur: setPompeProfondeur,
      pompeDistance: setPompeDistance, pompeCv: setPompeCv, pompeType: setPompeType,
      farmRegion: setFarmRegion, farmCrop: setFarmCrop,
      farmSurfaceHa: setFarmSurfaceHa, farmIrrigation: setFarmIrrigation,
    }
    const actuel = courantPompage.current
    const libre = (cle, courant) => courant === '' || courant == null
      || courant === posesLead.current[cle]
    for (const [cle, valeur] of Object.entries(res.ecran)) {
      const poser = poseurs[cle]
      if (poser && libre(cle, actuel[cle])) { poser(valeur); posesLead.current[cle] = valeur }
    }
    const eco = {}
    for (const [cle, valeur] of Object.entries(res.eco)) {
      if (cle === 'moisProvenance' || cle === 'energieProvenance') continue
      if (libre(`eco.${cle}`, actuel.eco?.[cle])) {
        eco[cle] = valeur
        posesLead.current[`eco.${cle}`] = valeur
      }
    }
    if ('energie' in eco) eco.energieProvenance = res.eco.energieProvenance
    if ('mois' in eco) eco.moisProvenance = res.eco.moisProvenance
    if (Object.keys(eco).length) setEcoPompage((e) => ({ ...e, ...eco }))
    setProvenancesLead(res.provenances)
  }

  // SPL50 — lien lead/client du devis (déplacé tel quel dans le hook ; l'effet d'arrivée du lead reste plus bas).
  const {
    applyLead, applyClient, runAutoQuote,
  } = useLeadClientEcran({
    leads, structuresCatalogue, setSaving, setErrors, sizing, dispatchSizing, finish, leadId,
    setLeadId, clientId, setClientId, setFHiver, setFEte, setMonthly: poserMoisDerives, modeInstallation,
    setConsoMensuelle, setHorsReseau, horsReseauTouched, setPompeCv, setPompeHmt, setPompeDebit,
    appliquerPartDiurneDuMarche, appliquerEntreesPompage,
    facturesProtegeesRef, reinitialiserFactures, setAvisFactures, consoMensuelle,
    pompeCv, pompeHmt, pompeDebit, baremeSociete,
  })

  // SPL45 — chargeur `?edit=` (déplacé tel quel dans le hook, même position : l'ordre des effets est inchangé).
  const {
    rechargerDevisRecompose,
  } = useChargeurEdition({
    setLeadDuDevis, setErrors, dispatchSizing, cancel, editId, setEditDevis, jetonRef,
    captureReferenceJusqua, rechargeEdit, setRechargeEdit, setRecommendedChoice, setLeadId,
    setClientId, setDateValidite, setNote, setEcheancierSaisieBrut, echeancierAEnvoyer,
    setConditions, conditionsServies, setFHiver, setFEte, setMonthly: poserMoisRelus, setDistributeur,
    setRealBillMode, setRealBillKwh, setDistributeurChoisi, consoStockee, modeInstallation,
    setDayUsage, setLines, setLeadValeursModifiees, setTauxTva, setDiscountPct, linesInitialized,
    setMultiMode, setNombreProprietes, setVillaGroups, setConsoMensuelle, setProfilCi,
    setTarifSaisie, setEcoCi, setCategorieCommerciale, setCommercialAnswers, setPrixCible,
    setAccessoiresOnly, setHorsReseau, setHorsReseauTouched, setPompeCv, setPompeType, setPompeHmt,
    setPompeDebit, setPompeProfondeur, setPompeDistance, setFarmRegion, setFarmCrop,
    setFarmSurfaceHa, setFarmIrrigation, setEcoPompage, setAttestationAgricole, setFarmHmtStatic,
    setFarmHmtDrawdown, setPompageSaisie, clear, appliquerPartDiurneDuMarche, baremeSociete,
  })

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
      setBaremeSociete(baremeDepuisProfil(data?.bareme_effectif))
      // AGNR26 — `agricole_pump_hours` reste un réglage SERVEUR (repli PVGIS
      // du moteur pompage) : l'écran n'a plus de champ « heures » à pré-remplir.
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
    // AGNR19 — le lead d'ARRIVÉE est relu PAR SON ID (jamais cherché dans la
    // page 1 d'une liste paginée) ; la liste chargée ne sert que de repli, et
    // un id introuvable des deux côtés est DIT.
    const appliquerArrivee = (lead) => {
      if (!lead) {
        setErrors(prev => ({ ...prev, client: `Lead introuvable (n° ${leadParam}).` }))
        return
      }
      // Initialisation unique (garde autoRan) — pas de cascade.
      applyLead(leadParam, lead)
      const wantAuto = embedded ? autoProp : (searchParams.get('auto') === '1')
      const discount = embedded ? (discountProp || '0') : (searchParams.get('discount') || '0')
      if (wantAuto) {
        runAutoQuote(lead, discount)
        if (discount) setDiscountPct(discount)
      }
    }
    // Présent dans la liste chargée : appliqué tout de suite (comportement
    // d'avant) ; sinon relu PAR SON ID, puis appliqué.
    const dejaCharge = leads.find(l => String(l.id) === String(leadParam))
    if (dejaCharge) {
      appliquerArrivee(dejaCharge)
      return
    }
    Promise.resolve()
      .then(() => crmApi.getLead(leadParam))
      .then((rep) => (rep?.data && String(rep.data.id) === String(leadParam) ? rep.data : null))
      .catch(() => null)
      .then((lead) => {
        if (lead) setLeadDuDevis(lead)
        appliquerArrivee(lead)
      })
  }, [leads, produits]) // eslint-disable-line react-hooks/exhaustive-deps

  // AGNR19 — le client d'arrivée (`?client=<id>`, plein écran sans lead) est
  // relu par son id, une fois.
  const clientArriveeLu = useRef(false)
  useEffect(() => {
    if (clientArriveeLu.current || embedded) return
    const id = searchParams.get('client')
    if (!id || searchParams.get('lead')) return
    clientArriveeLu.current = true
    crmApi.getClient(id).then(({ data }) => { if (data) setClientArrivee(data) }).catch(() => {})
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Factures : estimation hiver/été + suggestion panneaux ──
  // Règle fondateur du 18/08 — même chaîne palier/payback que applyLead/
  // applySiteProfile (computeAutoSizing, mémoïsée — cette fonction tourne à
  // chaque frappe sur le champ facture) ; sous le seuil, attend le moteur
  // horaire SERVEUR (U3-900 — plus de repli `estimerPanneaux`).
  // AGNR17 — frappe / collage du VENDEUR sur hiver / été : saisie protégée.
  const saisirFHiver = (v) => { setFHiver(v); setFacturesTapees(true); setAvisFactures(null) }
  const saisirFEte = (v) => { setFEte(v); setFacturesTapees(true); setAvisFactures(null) }
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
      // CIQ126 — plus aucun balayage local (voir applyLead).
      const sizingLocal = null
      dispatchSizing({
        type: 'PROFIL_SITE_APPLIQUE',
        profil: { type_installation: modeInstallation, facture_hiver: hiver },
        sizingLocal,
      })
    }
    // AGNR17 — la frappe hiver/été ne remplace JAMAIS des mois tapés ou
    // relus du devis : seul le geste « Estimer 12 mois » le fait.
    if (!provenanceMois.includes('tapee')) poserMoisDerives(estimerMois(hiver, ete > 0 ? ete : hiver))
  }

  // VX237 — montant collé d'Excel/facture ("12 500,00", "3 200 DH"...) nettoyé
  // vers une chaîne numérique simple au lieu de tomber brut dans le champ
  // number (qui rejetterait silencieusement le format non reconnu). Déclarés
  // ici (après syncBillEstimator) pour respecter react-hooks/immutability.
  const onHiverPaste = usePasteClean(parsePastedAmount,
    (clean) => { saisirFHiver(clean); syncBillEstimator(clean, fEte) })
  const onEtePaste = usePasteClean(parsePastedAmount,
    (clean) => { saisirFEte(clean); syncBillEstimator(fHiver, clean) })
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
    poserMoisDerives(estimerMois(hiver, ete))
  }

  const setMonth = (i, v) => {
    setMonthly(m => m.map((old, idx) => (idx === i ? v : old)))
    // AGNR13 — une case vidée n'est pas « tapée ».
    const tapee = String(v ?? '').trim() !== ''
    setProvenanceMois(p => p.map((old, idx) => (idx === i ? (tapee ? 'tapee' : 'exemple') : old)))
  }

  // SPL47 — gestes de lignes, villas, recomposition et modèles (déplacés tels quels dans le hook).
  const {
    setLine, tarifBadges, onProduitChange, onQuantiteChange, onDesignationBlur, renameHereOnly,
    renameAsNewProduct, addLine, addStructureLine, removeLine, moveLineUp, moveLineDown,
    handleSaveOrdreLignes, onProduitCreated, onMultiModeChange, setLineGroupe, addVillaGroup,
    renameVillaGroup, removeVillaGroup, recomposerLignes, avecQuantitesFigees, handlePresetApplied,
  } = useLignesEcran({
    confirm, canRenameLine, renameDialog, setRenameDialog, setRenameBusy, setRenameError, produits,
    setProduits, clientId, lines, setLines, setSavingOrdreLignes, setTauxTva, setDiscountPct,
    linesTableRef, pendingFocusKey, setPendingFocusKey, setMultiMode, villaGroups, setVillaGroups,
    appliquerMarcheEcran,
  })

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

  // SPL48 — composition, Auto-remplir et recalcul du dimensionnement (déplacés tels quels dans le hook).
  const {
    handleAutoFill, appliquerTailleDimensionnement, recalculerDimensionnement,
  } = useCompositionEcran({
    produits, setErrors, dispatchSizing, panelW, scenario, modeInstallation, structureType,
    structureProduitId, recalcDimTick, setPompageAutoFilled, setOnduleursIncomplets,
    setAutoFillLoading, setCompositionErreur, profilCi, horsReseau, kwp, selectedLead,
    etudeHoraireDonnees, etudeHoraireChargement, marcheCi, ctxProfilCi, apercuCi, resolveKwcAvec,
    recomposerLignes, avecQuantitesFigees, apercuPompage,
  })

  const selectedClient = clientsConnus.find(c => String(c.id) === String(clientId))

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
  // CIQ125 (transition, retirée avec l'étude locale par CIQ126) : en C&I la
  // seule saisie est le profil déclaré — sa moyenne mensuelle nourrit encore
  // l'étude locale jusqu'à sa suppression.
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
  const buyDetail = useMemo(() => computeBuyCostDetail(lines, produits), [lines, produits])
  const buyCost = buyDetail.cost
  const marge = buyCost != null ? Math.round(kpiTotal - buyCost) : null

  const applyPrixCible = () => {
    const pct = discountForTarget(prixCible, kwpLignes, kpiTotalBrut)
    if (pct == null) return
    setDiscountPct(String(Math.max(0, pct)))
  }

  // SPL44 — persistance et validation (déplacées telles quelles dans le hook).
  const {
    usableLines, enregistrerAvantModele, versionHistorique, revenirAVersion, handleSubmit,
    ouvrirConception3D,
  } = usePersistanceDevis({
    navigate, confirm, setClients, setLeads, setSaving, setErrors, setWarnings,
    facturesEcartConfirmeRef, finish, editId, editDevis, jetonRef, forcerSansJetonRef,
    setConflitVerrou, armerJeton, setRechargeEdit, recommendedChoice, overridesReg,
    setOverridesReg, setOverridesErreur, messageErreurOverrides, leadId, setLeadId, clientId,
    setClientId, dateValidite, note, echeancierSaisie, echeancierAEnvoyer, conditions,
    conditionsServies, monthly, distributeur, realBillMode, realBillSaisi, distributeurChoisi,
    consoStockee, nbPanneaux, scenario, modeInstallation, pompeAlim, lines, setLines, tauxTva,
    discountPct, setDiscountPct, multiMode, nombreProprietes, profilCi, tarifSaisie, ecoCi,
    categorieCommerciale, commercialAnswers, prixCible, accessoiresOnly, pompeCv, pompeType,
    pompeHmt, pompeDebit, pompeProfondeur, pompeDistance, farmRegion, farmCrop, farmSurfaceHa,
    farmIrrigation, attestationAgricole, farmHmtStatic, farmHmtDrawdown, pompageSaisie, clear,
    marquerEnregistre, recommended, consoAnnuelleReelle, facturesSaisies, selectedLead, marcheCi,
    ctxProfilCi, consoCiConnue, aujourdhuiIso, ecoAvecCalendrier,
    setEditDevis, setReserveEnregistrement, setErreursChamps, baremeSociete,
  })

  // Réinitialiser : recharge la page, comme le bouton du simulateur
  const handleReset = async () => {
    const ok = await confirm({
      title: 'Réinitialiser le formulaire ?',
      description: 'Toutes les saisies en cours seront perdues.',
      confirmLabel: 'Réinitialiser',
    })
    if (ok) window.location.reload()
  }

  // CIQ223 — l'économie C&I SERVIE (`POST /ventes/economie-ci/preview/`) :
  // la sortie de l'aperçu C&I, les saisies, et les lignes du devis (le serveur
  // recalcule l'investissement). Aucun chiffre d'économie calculé ici.
  const ecoCiEffectif = { ...ecoCi, revente_demandee: profilCi.tension === 'mt' && Boolean(profilCi.revente) }
  const corpsEcoCi = marcheCi && apercuCi.donnees ? {
    sortie_etude_ci: apercuCi.donnees,
    saisies: saisiesEconomieCi(ecoCiEffectif, { aujourdhui: aujourdhuiIso }) || {},
    lignes: usableLines().map((l) => {
      const q = parseFloat(l.quantite) || 0
      const tva = parseFloat(l.taux_tva ?? 20)
      const ttc = (parseFloat(l.prix_unit_ttc) || 0) * q
      return {
        produit: Number(l.produit), quantite: q, taux_tva: tva,
        totaux: { ht: htFromTtc(parseFloat(l.prix_unit_ttc) || 0, tva) * q, ttc },
      }
    }),
  } : null
  const apercuEcoCi = useApercuEconomieCi(corpsEcoCi)

  // EZ3 — PANNEAU DE SUCCÈS : la création ne se termine plus par un renvoi sur
  // la liste nue. Le devis fraîchement créé s'annonce (numéro + total) et
  // propose l'action SUIVANTE évidente. « Envoyer par WhatsApp » ouvre la liste
  // sur ce devis précis AVEC l'aperçu WhatsApp déjà ouvert (le flux existant de
  // DevisList, jamais un second) — un clic ici, un clic « Ouvrir WhatsApp ».
  // AGNR33 — une saisie que l'enregistrement NORMALISERA (AGNR8 : 2
  // décimales) est dite sous son champ dès la frappe (« 12,345 → 12,35 »).
  const notesNormalisation = {}
  for (const [champ, valeur] of [['remise_globale', discountPct], ['taux_tva', tauxTva], ['prix_cible_kwc', prixCible]]) {
    const n = normaliserNombreEntete(valeur)
    if (n.change) {
      notesNormalisation[champ] = `${String(n.tape).replace('.', ',')} → `
        + (n.envoye == null ? 'non envoyé (nombre illisible)' : String(n.envoye).replace('.', ','))
    }
  }
  const lignesQuantiteNulle = lines.filter(l => l.typeLigne !== 'section' && l.typeLigne !== 'note'
    && l.produit && !(parseFloat(l.quantite) > 0) && (l.prixManuel || !l.compose))
  const avisQuantiteNulle = !lignesQuantiteNulle.length ? null
    : lignesQuantiteNulle.length === 1
      ? `1 ligne à quantité 0 ne sera pas enregistrée : ${lignesQuantiteNulle[0].designation || '—'}`
      : `${lignesQuantiteNulle.length} lignes à quantité 0 ne seront pas enregistrées : `
        + lignesQuantiteNulle.map(l => l.designation || '—').join(', ')

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
    fHiver, setFHiver: saisirFHiver, fEte, setFEte: saisirFEte, syncBillEstimator,
    onHiverPaste, onEtePaste, handleEstimerMois, errors, monthly, setMonth, moisNonSaisis,
    avisFactures,
    distributeur, setDistributeur: choisirDistributeur, realBillMode, setRealBillMode,
    realBillMad, setRealBillMad: saisirRealBillMad,
    realBillKwh, setRealBillKwh: saisirRealBillKwh,
    onRealBillPaste, consoAnnuelleReelle,
  }
  // QJR101 — les entrées d'étude que l'industriel et le commercial partagent.
  // CIQ125 — le profil déclaré C&I + la réponse du moteur serveur.
  const socleEtudeReseau = {
    profilCi, setChampCi, apercuCi, tarifSaisie, setTarifChamp,
    apercuEcoCi, ecoCi, setEcoChamp,
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
        <BandeauxEdition
          editDevis={editDevis} conflitVerrou={conflitVerrou} setConflitVerrou={setConflitVerrou}
          clear={clear} setRechargeEdit={setRechargeEdit} forcerSansJetonRef={forcerSansJetonRef}
          handleSubmit={handleSubmit} brouillonProposable={brouillonProposable} restored={restored}
          handleRestoreDraft={handleRestoreDraft} discard={discard} savedAt={savedAt}
          refsLoading={refsLoading} loadFailed={loadFailed} saleWarnings={saleWarnings}
        />
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
                  tant qu'il l'est (voir handleAutoFill). */}
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
              {erreursChamps.date_validite && (
                <p className="text-xs text-destructive" data-testid="erreur-champ-date_validite">
                  {erreursChamps.date_validite}
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* SPL50 — carte Lead & Client (déplacée telle quelle). */}
        <CarteLeadClient
          clients={clients} saving={saving} errors={errors} editId={editId} editDevis={editDevis}
          leadId={leadId} clientId={clientId} setClientQuickCreateOpen={setClientQuickCreateOpen}
          leadsListe={leadsListe} selectedLead={selectedLead}
          resolvedClientLabel={resolvedClientLabel} applyLead={applyLead} applyClient={applyClient}
          selectedClient={selectedClient} onSearchClient={onSearchClient}
          ouvrirConception3D={ouvrirConception3D}
        />

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
        {bandeauSegment && (
          <div role="status" data-testid="bandeau-segment-lead"
               className="flex flex-wrap items-center gap-3 rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-sm">
            <span>
              Ce lead est typé « {typeLeadEffectif || 'non renseigné'} » : le script
              d’appel, le score et le suivi le traitent comme{' '}
              {typeLeadEffectif || 'un lead sans type'}. Changer le type
              {marcheSegment === 'agricole' ? ' en Agricole' : ''} ?
            </span>
            <Button type="button" variant="outline" size="sm"
                    onClick={changerTypeLead}>
              Passer en {marcheSegment}
            </Button>
          </div>
        )}
        {rappelIce && (
          <p role="status" data-testid="rappel-ice-manquant"
             className="rounded-md border border-border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
            ICE à demander au client — il sera obligatoire à l’acceptation en ligne
            et à la facture.
          </p>
        )}
        {modeInstallation === 'agricole' && provenancesLead.length > 0 && (
          <ul className="grid gap-0.5 rounded-md border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground"
              data-testid="provenance-lead-pompage" aria-label="Valeurs reprises de la fiche lead">
            {provenancesLead.map((p) => (
              <li key={p.colonne}>
                {p.libelle} : {p.valeur} — {libelleProvenance(p.provenance)}
              </li>
            ))}
          </ul>
        )}
        <PanneauAgricole
          marche={modeInstallation}
          pompeCv={pompeCv} setPompeCv={setPompeCv}
          pompeType={pompeType} setPompeType={setPompeType}
          pompeAlim={pompeAlim} dispatchSizing={dispatchSizing}
          pompeHmt={pompeHmt} setPompeHmt={setPompeHmt}
          pompeDebit={pompeDebit} setPompeDebit={setPompeDebit}
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
                paliers testés (`sizingInfo.paliers`). */}
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
            {/* QJR641 / CIQ126 — curseur du RÉSIDENTIEL seulement : en C&I le
                profil de charge est celui déclaré au moteur serveur. */}
            {modeInstallation === 'residentiel' && (
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
                      disabled={modeInstallation === 'agricole' || (marcheCi
                        ? !(Number(apercuCi.donnees?.taille?.nb_panneaux) > 0)
                        : !(parseFloat(fHiver) > 0))}
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
        <ApercuSimulation
          setPreviewCollapsed={setPreviewCollapsed} previewCollapsed={previewCollapsed}
          modeInstallation={modeInstallation} etudeHoraireCorps={etudeHoraireCorps}
          etudeHoraireSourceServeur={etudeHoraireSourceServeur}
          etudeHoraireSourceLabel={etudeHoraireSourceLabel}
          etudeHoraireChargement={etudeHoraireChargement} etudeHoraireErreur={etudeHoraireErreur}
          etudeHoraireDonnees={etudeHoraireDonnees} etudeHoraireLignes={etudeHoraireLignes}
          ligneStockageOuverte={ligneStockageOuverte}
          appliquerTailleDimensionnement={appliquerTailleDimensionnement}
          setLigneStockageOuverte={setLigneStockageOuverte}
          etudeHoraireFalaise={etudeHoraireFalaise} etudeHoraireGlitch={etudeHoraireGlitch}
          etudeHoraireEstimationConso={etudeHoraireEstimationConso} marcheCi={marcheCi} roi={roi}
          etudeHoraireAnnuel={etudeHoraireAnnuel} sansRec={sansRec} showAvec={showAvec}
          etudeHoraireAnnuelAvec={etudeHoraireAnnuelAvec} distributeur={distributeur}
          apercuProductionKwh={apercuProductionKwh} showSans={showSans}
          signerEcoOuRoi={signerEcoOuRoi} apercuEcoSans={apercuEcoSans}
          apercuPaybackSansJamais={apercuPaybackSansJamais} apercuPaybackSans={apercuPaybackSans}
          totals={totals} avecRec={avecRec} batterieInvendableServeur={batterieInvendableServeur}
          verdictBatterieServeur={verdictBatterieServeur} apercuEcoAvec={apercuEcoAvec}
          apercuPaybackAvecJamais={apercuPaybackAvecJamais} apercuPaybackAvec={apercuPaybackAvec}
          capaciteBatterieInconnue={capaciteBatterieInconnue} facturesSaisies={facturesSaisies}
          chartData={chartData}
        />
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
            remiseParPanier={remiseParPanier}
            erreursChamps={erreursChamps}
            notesNormalisation={notesNormalisation}
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
            margeLignesSansAchat={buyDetail.sansAchat}
            kpiTotal={kpiTotal}
          />
        </LigneTable>

        {/* SPL49 — modèles, historique et blocs de l'Édition complète (déplacés tels quels). */}
        <BlocsEditionComplete
          editDevis={editDevis} rechargerDevisRecompose={rechargerDevisRecompose}
          handlePresetApplied={handlePresetApplied} enregistrerAvantModele={enregistrerAvantModele}
          versionHistorique={versionHistorique} revenirAVersion={revenirAVersion}
        />

        {/* SPL46 — le panneau brut du registre (admin, devis enregistré) : sa
            condition d'affichage vit avec lui dans PanneauSurcharges. */}
        <PanneauSurcharges editDevis={editDevis} estAdmin={estAdmin}
                           ovChemin={ovChemin} setOvChemin={setOvChemin}
                           ovValeur={ovValeur} setOvValeur={setOvValeur}
                           overridesBusy={overridesBusy} poserOverride={poserOverride}
                           overridesErreur={overridesErreur} overridesReg={overridesReg}
                           regenererOverride={regenererOverride} />

        {/* AGNR31 — une ligne produit saisie (prix tapé, ou ajoutée à la
            main) à quantité 0 ou vide ne partira pas : annoncé AVANT l'envoi,
            jamais bloquant (même filtre que `lignesEnvoyees`). */}
        {avisQuantiteNulle && (
          <div className="rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning"
               data-testid="avis-quantite-nulle">
            {avisQuantiteNulle}
          </div>
        )}
        {reserveEnregistrement && (
          <div role="alert" data-testid="reserve-enregistrement"
               className="rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
            {reserveEnregistrement}
          </div>
        )}
        {/* SPL49 — échéancier, notes client, avertissements et carte Création (déplacés tels quels). */}
        <CarteCreation
          embedded={embedded} clients={clients} saving={saving} errors={errors} warnings={warnings}
          cancel={cancel} editDevis={editDevis} superieurBusy={superieurBusy}
          superieurMsg={superieurMsg} contacterSuperieur={contacterSuperieur} note={note}
          setNote={setNote} echeancierSaisie={echeancierSaisie} termesEffectifs={termesEffectifs}
          conditions={conditions} setCondition={setCondition}
          setEcheancierSaisie={setEcheancierSaisie} modeInstallation={modeInstallation}
          apercuPompage={apercuPompage} kpiTotal={kpiTotal} handleReset={handleReset}
        />
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
