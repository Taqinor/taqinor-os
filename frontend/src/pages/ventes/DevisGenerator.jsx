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
  ArrowLeft, Target, ClipboardList, User, Zap, Sprout, BarChart3,
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
import { createAutoQuote, buildEtudePompage, LEAD_TYPE_TO_MODE } from '../../features/ventes/autoQuote'
import { waterDemandFromFarm } from '../../features/ventes/agronomy'
import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import parametresApi from '../../api/parametresApi'
// NTMFG18 — vérification de faisabilité atelier (simulation SANS écriture).
import mrpApi from '../../api/mrpApi'
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
  Input, Textarea, Label, Segmented,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  HelpTip, ScrollProgress,
} from '../../ui'
import { useCanCreateProduit } from '../../hooks/useHasPermission'
import useKeyboardAwareScroll from '../../hooks/useKeyboardAwareScroll'
import { useDirtyGuard } from '../../ui/useDirtyGuard'
import { useDraftAutosave } from '../../ui/useDraftAutosave'
import { usePasteClean, parsePastedAmount } from '../../hooks/usePasteClean'
import {
  MONTHS_FR, CHART_MONTHS, DEFAULT_MONTHLY_BILLS, DAY_USAGE_DEFAULTS,
  formatMoney, estimerMois, computeROI, ttcFromHt, htFromTtc,
  tauxTvaOf,
  batteryKwhFromLines, batteryCapaciteInconnue, comptePanneauxOption,
  optionTotalsTTC, autoFillLines, defaultProductLines,
  computeEtudeIndustrielle,
  autoFillPompage, pompageSelection, HEURES_POMPAGE_DEFAUT,
  isBattery, isHybridInverter, isReseauInverter, isPanel, isPompe,
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
  COMMERCIAL_CATEGORIES, COMMERCIAL_CATEGORY_QUESTIONS, commercialDayShare,
  TARIF_MT_ONEE, tarifMtDisponible, tarifMtMoyen,
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
} from '../../features/ventes/solar'
import { formatNumber, formatMAD, formatDateTime } from '../../lib/format'
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
import { raisonRepli } from '../../features/ventes/quote/hooks/useComposition'
// QJR102 — `apercu` n'est plus importé ici : la seule valeur d'aperçu que cet
// écran signait était le balayage local du dimensionnement affiché, devenu
// injoignable (la puce « estimation d'exemple » des cartes ROI, elle, passe
// par `CarteMetrique`, qui possède le déballeur).
import { moteur, absent, estFait } from '../../features/ventes/quote/valeur'
// QJR100 — les trois morceaux extraits de cet écran. `CarteMetrique` est LE
// seul déballeur d'une valeur signée ; `LigneTable` possède la table de lignes
// (ajout/suppression/réordonnancement) ; `RailArgent` possède la chaîne
// d'argent (totaux, remise, TVA, prix cible, marge interne).
import CarteMetrique, { GenCardHeader } from './generator/CarteMetrique'
import LigneTable from './generator/LigneTable'
import RailArgent from './generator/RailArgent'

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

// ORDRE FONDATEUR (24/08) — « tous les devis sont générés par défaut avec DEUX
// OPTIONS (sans + avec batterie), sauf si le commercial le précise sur le devis
// modifiable ». Le vocabulaire est le contrat EXACT du moteur PDF (constantes
// SCENARIO_* d'apps/ventes/services.py) : jamais reformulé ici.
// QJR99 — les quatre constantes ET la table QX19 `BATTERIE_LEAD_VERS_SCENARIO`
// ne sont plus RE-DÉCLARÉES ici : elles viennent du reducer (source unique,
// `features/ventes/quote/sizingReducer.js`), qui les possède depuis QJR87.

// Type d'installation (libellé du simulateur) par marché — la seule chose que
// `onModeChange` faisait EN PLUS de poser le mode/scénario, et que le reducer
// (pur, sans notion d'autoconsommation par défaut) ne modélise pas.
const INST_TYPE_PAR_MODE = {
  residentiel: 'Résidentielle',
  industriel: 'Industrielle',
  commercial: 'Commerciale',
  agricole: 'Agricole',
}

const RIEN_A_CHIFFRER = 'aucun dimensionnement chiffré pour cette branche'

/** Recommandation du MOTEUR horaire serveur — publiable telle quelle. */
const valeurMoteurDim = (srv) => (Number(srv?.panneaux) > 0
  ? moteur({ nbPanneaux: srv.panneaux, kwc: srv.kwc })
  : absent(RIEN_A_CHIFFRER))

/**
 * QJR99 — remplace la CHAÎNE DE TERNAIRES `deuxValeursDim`. Chaque branche
 * devient une VALEUR SIGNÉE (QJR86) : `moteur` = moteur horaire serveur,
 * `absent(motif)` = rien de calculable — jamais un chiffre inventé.
 *
 * QJR102 — la branche `apercu` (balayage local `sizingInfo`) EST SUPPRIMÉE :
 * elle était injoignable (voir `deuxValeursDim`). Il ne reste donc QU'UNE
 * source possible, et la règle F3 (« jamais une paire mixte ») devient une
 * propriété du type au lieu d'une comparaison à faire : deux valeurs `moteur`
 * ou rien. Rend la même forme qu'avant (`{ sans, avec }`, chacun
 * `{nbPanneaux, kwc}` ou `null`) : le JSX est inchangé.
 */
const paireDimensionnement = (srvSans, srvAvec) => {
  const mSans = valeurMoteurDim(srvSans)
  const mAvec = valeurMoteurDim(srvAvec)
  if (estFait(mSans) && estFait(mAvec)) return { sans: mSans.valeur, avec: mAvec.valeur }
  // Une seule branche chiffrée : elle sort SEULE — « sans » avant « avec »,
  // comme la cascade historique.
  if (estFait(mSans)) return { sans: mSans.valeur, avec: null }
  if (estFait(mAvec)) return { sans: null, avec: mAvec.valeur }
  return { sans: null, avec: null }
}

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
  // L-2OPT (fondateur 24/08) — '' commun (défaut, comportement historique
  // inchangé) | 'sans' | 'avec' : posée par `fusionnerVariantes` quand les
  // deux optimiseurs résidentiels divergent, préservée au rechargement d'un
  // brouillon/devis (VX62, réouverture ?edit=).
  variante: r.variante ?? '',
}))

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
  const [produits, setProduits] = useState([])
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState({})
  // Avertissements NON bloquants (n'empêchent jamais l'enregistrement) —
  // distincts de `errors` qui, eux, bloquent la sauvegarde.
  const [warnings, setWarnings] = useState({})
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
      total: devisData?.total_ttc ?? null,
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
  const editLoaded = useRef(false)

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

  // NTMFG18 — « Vérifier faisabilité atelier » : simule SANS RIEN ENREGISTRER
  // la charge additionnelle qu'induiraient les lignes du devis en cours de
  // saisie sur les postes de charge (module mrp). No-op silencieux si aucun
  // produit du devis n'a de gamme de fabrication (devis 100% négoce) : le
  // backend renvoie alors `tenable: 'sans_gamme'`.
  const [faisabiliteBusy, setFaisabiliteBusy] = useState(false)
  const [faisabiliteResult, setFaisabiliteResult] = useState(null)
  const verifierFaisabiliteAtelier = async () => {
    setFaisabiliteBusy(true)
    setFaisabiliteResult(null)
    try {
      const lignesPayload = lines
        .filter(l => l.produit && Number(l.quantite) > 0)
        .map(l => ({ produit_id: l.produit, quantite: l.quantite }))
      const resp = await mrpApi.simulerCharge({
        lignes: lignesPayload,
        date_souhaitee: dateValidite || undefined,
      })
      setFaisabiliteResult(resp.data)
    } catch {
      setFaisabiliteResult({ tenable: 'erreur' })
    } finally {
      setFaisabiliteBusy(false)
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
  const [instType, setInstType] = useState('Résidentielle')
  const [recommendedChoice, setRecommendedChoice] = useState('Auto')
  const [note, setNote] = useState('')

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
  // QJR36 — même patron que `sizingServeurMessage` : quand le dry-run serveur
  // (`ventesApi.composerDevis`) échoue et que l'écran retombe sur
  // `composeLocalement()`, le vendeur reçoit une composition JS que le dépôt
  // documente lui-même comme divergente du serveur (câbles, marques épinglées,
  // ordre des lignes, arrondi des panneaux) — SANS aucun signal jusqu'ici.
  // Posé dans le `catch` avec la raison, effacé dès qu'un dry-run réussit.
  // Ne change PAS le comportement du repli, seulement le rend visible.
  const [compositionSourceLocale, setCompositionSourceLocale] = useState(null)
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
  const [categorieCommerciale, setCategorieCommerciale] = useState('hotel')
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
  // Pompage (agricole)
  const [pompeCv, setPompeCv] = useState('5.5')
  const [pompeType, setPompeType] = useState('immergee')
  // (`pompeAlim` vient du reducer, voir plus haut.)
  const [pompeHmt, setPompeHmt] = useState('')
  const [pompeDebit, setPompeDebit] = useState('')
  const [pompeProfondeur, setPompeProfondeur] = useState('')
  const [pompeDistance, setPompeDistance] = useState('20')
  const [pompeHeures, setPompeHeures] = useState(String(HEURES_POMPAGE_DEFAUT))
  // ── Exploitation agricole (données GUIDÉES, toutes optionnelles) — alimentent
  // le calcul FAO-56 (besoin en eau) et le redimensionnement/chiffrage du PDF.
  // Stockées dans etude_params sous ces clés exactes (le backend les relit).
  const [farmRegion, setFarmRegion] = useState('souss-massa')
  const [farmCrop, setFarmCrop] = useState('agrumes')
  const [farmSurfaceHa, setFarmSurfaceHa] = useState('')
  const [farmIrrigation, setFarmIrrigation] = useState('goutte')
  const [farmFuel, setFarmFuel] = useState('butane')
  // Dépense carburant ACTUELLE : saisie au mois OU à l'année (bascule), mais
  // stockée toujours en MAD/AN (fuel_spend_current).
  const [farmFuelSpend, setFarmFuelSpend] = useState('')
  const [farmFuelPeriod, setFarmFuelPeriod] = useState('mois') // 'mois' | 'an'
  const [farmHmtStatic, setFarmHmtStatic] = useState('')
  const [farmHmtDrawdown, setFarmHmtDrawdown] = useState('')

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
    leadId, clientId, dateValidite, instType, scenario, recommendedChoice, note,
    fHiver, fEte, monthly, distributeur, realBillMode, realBillMad, realBillKwh,
    nbPanneaux, panelW, structureType, dayUsage, lines, tauxTva, discountPct,
    multiMode, nombreProprietes, villaGroups, modeInstallation, consoMensuelle,
    categorieCommerciale, commercialAnswers, injectionEnabled,
    tensionRaccordement, repartitionMt,
    prixCible, remiseMax, accessoiresOnly,
    pompeCv, pompeType, pompeAlim, pompeHmt, pompeDebit, pompeProfondeur,
    pompeDistance, pompeHeures, farmRegion, farmCrop, farmSurfaceHa,
    farmIrrigation, farmFuel, farmFuelSpend, farmFuelPeriod, farmHmtStatic,
    farmHmtDrawdown,

  }), [
    leadId, clientId, dateValidite, instType, scenario, recommendedChoice, note,
    fHiver, fEte, monthly, distributeur, realBillMode, realBillMad, realBillKwh,
    nbPanneaux, panelW, structureType, dayUsage, lines, tauxTva, discountPct,
    multiMode, nombreProprietes, villaGroups, modeInstallation, consoMensuelle,
    categorieCommerciale, commercialAnswers, injectionEnabled,
    tensionRaccordement, repartitionMt,
    prixCible, remiseMax, accessoiresOnly,
    pompeCv, pompeType, pompeAlim, pompeHmt, pompeDebit, pompeProfondeur,
    pompeDistance, pompeHeures, farmRegion, farmCrop, farmSurfaceHa,
    farmIrrigation, farmFuel, farmFuelSpend, farmFuelPeriod, farmHmtStatic,
    farmHmtDrawdown,
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
  const dirty = Boolean(
    leadId || clientId || note || fHiver || fEte || nbPanneaux
    || consoMensuelle || prixCible || pompeHmt || pompeDebit || farmSurfaceHa
    || lignesSaisies || remiseSaisie || tvaModifiee || villasSaisies,
  )
  const { restored, restore, discard, clear, savedAt } = useDraftAutosave(draftKey, draftSnapshot, {
    enabled: dirty,
  })
  useDirtyGuard(dirty)

  // Restauration : réinjecte le snapshot sauvegardé dans tous les setters.
  const handleRestoreDraft = () => {
    const d = restore()
    if (!d) return
    if (d.leadId != null) setLeadId(d.leadId)
    if (d.clientId != null) setClientId(d.clientId)
    if (d.dateValidite != null) setDateValidite(d.dateValidite)
    if (d.instType != null) setInstType(d.instType)
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
    // QJR99 — les champs du reducer se restaurent par dispatch. `REOUVERTURE`
    // pose le compte de panneaux SANS le marquer « touché » (comportement
    // historique : un brouillon restauré n'est pas une frappe) ; `SAISI panelW`
    // n'a jamais eu de drapeau propre. `MARCHE_CHANGE` en origine
    // `programme` ne marque pas le marché non plus — le lead peut encore le
    // pré-régler, exactement comme avant.
    if (d.panelW != null) dispatchSizing({ type: 'SAISI', champ: 'panelW', valeur: d.panelW })
    if (d.nbPanneaux != null) dispatchSizing({ type: 'REOUVERTURE', devis: { panneaux: d.nbPanneaux } })
    if (d.structureType != null) dispatchSizing({ type: 'SAISI', champ: 'structure', valeur: d.structureType })
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
    if (d.farmFuel != null) setFarmFuel(d.farmFuel)
    if (d.farmFuelSpend != null) setFarmFuelSpend(d.farmFuelSpend)
    if (d.farmFuelPeriod != null) setFarmFuelPeriod(d.farmFuelPeriod)
    if (d.farmHmtStatic != null) setFarmHmtStatic(d.farmHmtStatic)
    if (d.farmHmtDrawdown != null) setFarmHmtDrawdown(d.farmHmtDrawdown)
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
    setLines(withKeys(defaultProductLines(produits)))
  }, [produits])

  const kwp = (parseInt(nbPanneaux) || 0) * (parseFloat(panelW) || 0) / 1000

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
    if (nSans <= 0 || nAvec === nSans) return kwp
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
    // eslint-disable-next-line react-hooks/set-state-in-effect -- miroir d'un champ posé ailleurs
    dispatchSizing({ type: 'SAISI', champ: 'panelW', valeur: panelW })
  }, [kwp, kwcCible, panelW])

  const showSans = scenario !== 'Avec batterie'
  const showAvec = scenario !== 'Sans batterie'
  const recommended = recommendedChoice !== 'Auto'
    ? recommendedChoice
    : (scenario === 'Sans batterie' ? 'Sans batterie' : 'Avec batterie')
  const sansRec = recommended === 'Sans batterie'
  const avecRec = recommended === 'Avec batterie'

  // ── Totaux + simulation, recalculés en direct ──
  const totals = useMemo(
    () => optionTotalsTTC(lines, discountPct),
    [lines, discountPct],
  )

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
  const selectedLead = leads.find(l => String(l.id) === String(leadId))

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
        selectedLead?.ville || '', quoteLogic.productible),
    })
  }, [dKwp, dMonthly, dDayUsage, dTotals, dLines, quoteLogic,
    consoAnnuelleReelle, distributeur, selectedLead])

  // L-2OPT — miroir local de `roi` recalculé AU kWc DE LA BRANCHE AVEC. `null`
  // dès que rien ne diverge (`kwpAvec === kwp`) : l'écran retombe alors mot
  // pour mot sur `roi`, aucun second calcul, comportement d'hier. Quand les
  // deux optimiseurs ont réellement rendu deux tailles, seuls les champs
  // « avec » de CE résultat sont lus (l'option sans garde `roi`).
  const roiAvec = useMemo(() => {
    if (dKwpAvec === dKwp) return null
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
        selectedLead?.ville || '', quoteLogic.productible),
    })
  }, [dKwpAvec, dKwp, dMonthly, dDayUsage, dTotals, dLines, quoteLogic,
    consoAnnuelleReelle, distributeur, selectedLead])

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
        ville: selectedLead?.ville || '',
        raccordement: selectedLead?.raccordement || '',
        kwp,
        batterieKwh: batteryKwhFromLines(lines),
      })
    : null
  // L-2OPT — l'étude horaire de la branche AVEC porte SON PROPRE kWc. Le corps
  // ci-dessus décrit la branche SANS (`kwp`) ; l'interroger avec les batteries
  // de la composition AVEC produisait une chimère (kWc sans + batteries avec).
  // `null` tant que rien ne diverge ⇒ AUCUN second appel réseau et l'écran lit
  // le corps unique comme hier.
  const etudeHoraireCorpsAvec = (modeInstallation === 'residentiel'
      && kwpAvec !== kwp)
    ? construireCorpsPreview({
        modeInstallation,
        editId,
        leadId,
        fHiver,
        fEte,
        eteDifferente: !!fEte && Number(fEte) > 0,
        ville: selectedLead?.ville || '',
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
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reporte la décision du moteur SERVEUR (déjà asynchrone) dans le reducer, jamais relue dans le même rendu
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
  const apercuPaybackSans = etudeHoraireSourceServeur
    ? (totals.totalSans > 0 && apercuEcoSans > 0
        ? Math.round((totals.totalSans / apercuEcoSans) * 100) / 100 : null)
    : roi?.payback_sans
  const apercuPaybackAvec = etudeHoraireAnnuelAvec
    ? (totals.totalAvec > 0 && apercuEcoAvec > 0
        ? Math.round((totals.totalAvec / apercuEcoAvec) * 100) / 100 : null)
    : roiPourAvec?.payback_avec

  // QJR35 — au montage (roi tourne dès dKwp>0 && dMonthly.some(v=>v>0), vrai
  // avec DEFAULT_MONTHLY_BILLS), les cartes Économies/ROI peuvent afficher un
  // chiffre dérivé du MIROIR LOCAL sans qu'aucune facture réelle ni étude
  // horaire serveur n'existe encore. Ni caché (le vendeur s'en sert comme
  // repère) ni remplacé par un autre chiffre — étiqueté. QJR89/QJR90 rendent
  // cette règle structurelle ; ceci est l'intérim minimal.
  const apercuEstimationExemple = !facturesSaisies && !etudeHoraireSourceServeur

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

  // ── Type d'installation → autoconsommation par défaut (simulateur) ──
  const onInstTypeChange = (type) => {
    setInstType(type)
    setDayUsage(DAY_USAGE_DEFAULTS[type] ?? 50)
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
    onInstTypeChange(INST_TYPE_PAR_MODE[m] ?? 'Résidentielle')
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
  const computeAutoSizing = useCallback((hiverVal, eteVal) => {
    const hiver = parseFloat(hiverVal) || 0
    const besoinKwc = estimerKwcDepuisFacture(hiver)
    if (besoinKwc <= 0) return null
    const eteVale = parseFloat(eteVal) || 0
    const eteEff = eteVale > 0 ? eteVale : hiver
    const dayUsagePct = modeInstallation === 'commercial' ? DAY_USAGE_DEFAULTS['Commerciale']
      : modeInstallation === 'industriel' ? DAY_USAGE_DEFAULTS['Industrielle']
        : DAY_USAGE_DEFAULTS['Résidentielle']
    // Distributeur du devis : c'est SON barème qui convertit les factures en
    // kWh (et qui valorise l'économie par tranche). Il entre donc dans la clé
    // de cache au même titre que la marque épinglée.
    const distributeurBalayage = distributeur
    // PVMRQ — la marque épinglée entre dans la clé de cache : un changement de
    // réglage (ou de gamme du devis) doit rejouer le balayage des paliers.
    const key = [hiver, eteEff, besoinKwc, dayUsagePct, panelW, structureType,
      discountPct, produits.length, JSON.stringify(marquesActives),
      distributeurBalayage, consoAnnuelleReelle ?? ''].join('|')
    if (sizingCacheRef.current.key === key) return sizingCacheRef.current.result
    const factures = estimerMois(hiver, eteEff)
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
    const consoBalayage = (Number(consoAnnuelleReelle) > 0)
      ? Number(consoAnnuelleReelle)
      : consoAnnuelleDepuisFactures(factures, distributeurBalayage)
    const opt = optimalKwcByPayback({
      produits, factures, dayUsagePct,
      panelW, structureType, discountPct,
      kwhPrice: quoteLogic.kwhPrice, efficiency: quoteLogic.efficiency,
      besoinKwc, marques: marquesActives,
      consoAnnuelleKwh: consoBalayage, utility: distributeurBalayage,
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
  }, [modeInstallation, panelW, structureType, discountPct, produits, quoteLogic,
    marquesActives, distributeur, consoAnnuelleReelle])

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
  const deuxValeursDim = (() => {
    if (modeInstallation !== 'residentiel') return { sans: null, avec: null }
    const dim = etudeHoraireDonnees?.dimensionnement
    return paireDimensionnement(dim?.recommandation, dim?.recommandation_avec)
  })()

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
      onInstTypeChange(INST_TYPE_PAR_MODE[modeLead] ?? 'Résidentielle')
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
      ? computeAutoSizing(hiver, ete) : null
    dispatchSizing({ type: 'LEAD_APPLIQUE', lead, sizingLocal })
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
      onInstTypeChange(INST_TYPE_PAR_MODE[modeLead] ?? 'Résidentielle')
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
    if (!editId || editLoaded.current) return
    editLoaded.current = true
    ventesApi.getDevisById(editId).then(({ data: d }) => {
      if (d.statut !== 'brouillon') {
        // APX17 — plus de popup du système : un toast d'erreur français,
        // dans le seul Toaster de l'app.
        toast.error('Ce devis n\'est plus un brouillon — il ne peut plus être modifié.')
        cancel()
        return
      }
      setEditDevis({ id: d.id, reference: d.reference,
                     lineIds: (d.lignes ?? []).map(l => l.id) })
      // QJR99 — la RÉOUVERTURE d'un brouillon est UNE transition
      // (`REOUVERTURE`, dispatchée plus bas quand `panneaux` et `etude_params`
      // sont lus) : mode + compte de panneaux + scénario, dans cet ordre, avec
      // les drapeaux « déjà choisi » que ce round-trip exige. Ne reste ici que
      // le type d'installation, hors modèle du reducer.
      if (d.mode_installation && d.mode_installation !== modeInstallation) {
        onInstTypeChange(INST_TYPE_PAR_MODE[d.mode_installation] ?? 'Résidentielle')
      }
      if (d.lead) setLeadId(String(d.lead))
      else if (d.client) setClientId(String(d.client))
      setDiscountPct(String(parseFloat(d.remise_globale) || 0))
      setTauxTva(String(d.taux_tva ?? '20.00'))
      if (d.date_validite) setDateValidite(d.date_validite)
      if (d.note) setNote(d.note)
      const rows = (d.lignes ?? [])
        .slice()
        // XSAL14 — respecte l'ordre serveur (ordre, id) pour intercaler les
        // sections/notes au bon endroit à la réouverture d'un brouillon.
        .sort((a, b) => (a.ordre ?? 0) - (b.ordre ?? 0) || (a.id ?? 0) - (b.id ?? 0))
        .map(l => ({
          produit: String(l.produit ?? ''),
          designation: l.designation,
          quantite: String(parseFloat(l.quantite) || 0),
          prix_unit_ttc: String(ttcFromHt(l.prix_unitaire || 0, l.taux_tva ?? d.taux_tva)),
          taux_tva: String(parseFloat(l.taux_tva ?? d.taux_tva) || 20),
          // XSAL5 — préserve le drapeau « option » au rechargement d'un brouillon.
          optionnelle: !!l.optionnelle,
          // XSAL14 — préserve le type de ligne (produit / section / note).
          typeLigne: l.type_ligne ?? 'produit',
          // L-2OPT — préserve le tag de variante posé par le serveur (champ
          // pas encore accepté par TOUS les backends — `?? ''` en repli,
          // comportement historique inchangé tant qu'il est absent).
          variante: l.variante ?? '',
          // QJR65 / décision fondateur D12 — LE PRIX TAPÉ À LA MAIN SURVIT À
          // `?edit=`. Ce mappeur ne rendait PAS `prixManuel` : le drapeau
          // revenait `undefined → false`, et l'effet listes-de-prix
          // ([clientId, lines.length]) relançait `refreshTarif` sur CHAQUE
          // ligne au montage — le tarif catalogue écrasait en silence le prix
          // négocié que le vendeur avait tapé ET enregistré. `prix_manuel` est
          // servi par la ligne (QJR59, `LigneDevisSerializer` `__all__`) ; la
          // garde vit, elle, dans `refreshTarif` (`!l.prixManuel`). Champ
          // absent d'un backend plus ancien ⇒ `false`, comportement historique
          // strictement inchangé.
          prixManuel: !!l.prix_manuel,
        }))
      setLines(withKeys(rows))
      linesInitialized.current = true
      // L-2OPT — le nombre de panneaux affiché reste celui de la branche
      // SANS (commun + 'sans' ; une ligne 'avec' divergente ne compte pas
      // ici, sinon les deux optima s'additionneraient).
      const panneaux = rows
        .filter(r => /panneau/i.test(r.designation) && r.variante !== 'avec')
        .reduce((s, r) => s + (parseFloat(r.quantite) || 0), 0)
      const e = d.etude_params || {}
      // ORDRE FONDATEUR (24/08) — round-trip du MARCHÉ, du COMPTE DE PANNEAUX
      // et du SCÉNARIO déjà choisis sur ce devis (etude_params.scenario, posé
      // par `buildEtudeParamsChoice` à l'enregistrement). Sans lui, rouvrir un
      // brouillon reposait le défaut du MODE et l'enregistrement suivant
      // ÉCRASAIT silencieusement le choix du client — un devis « Avec
      // batterie » repartait « Les deux », un devis industriel « Les deux »
      // repartait « Sans batterie ». Le défaut ne vaut que pour un devis
      // VIERGE. Un scénario hors contrat du moteur PDF est IGNORÉ (le Select
      // ne doit jamais l'afficher) — la garde vit dans le reducer.
      dispatchSizing({
        type: 'REOUVERTURE',
        devis: {
          mode_installation: d.mode_installation,
          panneaux,
          scenario: e.scenario,
        },
      })
      // PVMRQ — round-trip de la gamme du devis (`etude_params.gamme.nom`,
      // posée par `services.creer_variante_gamme`/`gamme_nom`) : résout la
      // carte de marques Essentielle/Premium à réappliquer aux
      // auto-remplissages suivants de CE devis (voir `marquesActives`).
      if (e.gamme && typeof e.gamme === 'object' && e.gamme.nom) {
        setGammeNomDevis(String(e.gamme.nom))
      }
      // (le scénario du devis est repris par la transition `REOUVERTURE`
      // ci-dessus, avec son drapeau « déjà choisi ».)
      if (['Auto', 'Aucune recommandation', SCENARIO_SANS, SCENARIO_AVEC]
        .includes(e.recommended_choice)) {
        setRecommendedChoice(e.recommended_choice)
      }
      // QJ31 / QJR66 — round-trip du ×N villas identiques. Le mode multi-villa
      // ne se restaurait QUE depuis le brouillon local (localStorage) : rouvrir
      // un devis ×4 par `?edit=` le ramenait à 1 à l'écran. Devenu bloquant
      // depuis que l'écran est l'écrivain de la clé (il aurait alors envoyé
      // `null` et DÉTRUIT le ×4 en base au premier enregistrement).
      const nProprietes = parseInt(e.nombre_proprietes, 10)
      if (Number.isFinite(nProprietes) && nProprietes > 1) {
        setMultiMode('multiplier')
        setNombreProprietes(String(nProprietes))
      }
      // QX50 — round-trip de l'injection 82-21 (flag activé si l'étude la porte).
      if (e.injection_82_21 || e.injection_dh_an != null) setInjectionEnabled(true)
      // QXMT — round-trip du raccordement MT + de la répartition horaire, pour
      // qu'un devis MT rouvert recalcule au MÊME barème (jamais un retour BT
      // silencieux). Les clés absentes laissent le défaut 'bt' intact.
      if (e.tension_raccordement === 'mt') {
        dispatchSizing({ type: 'SAISI', champ: 'tension', valeur: 'mt' })
      }
      if (e.repartition_mt && typeof e.repartition_mt === 'object') {
        setRepartitionMt({
          pointe: e.repartition_mt.pointe != null ? String(e.repartition_mt.pointe) : '',
          pleines: e.repartition_mt.pleines != null ? String(e.repartition_mt.pleines) : '',
          creuses: e.repartition_mt.creuses != null ? String(e.repartition_mt.creuses) : '',
        })
      }
      // QX44 — round-trip de l'étude commerciale : catégorie + réponses par
      // catégorie (clés snake_case) réinjectées dans le formulaire.
      if (e.categorie_commerciale) {
        setCategorieCommerciale(String(e.categorie_commerciale))
        const qs = COMMERCIAL_CATEGORY_QUESTIONS[String(e.categorie_commerciale)] || []
        const ans = {}
        for (const q of qs) {
          if (e[q.key] !== undefined && e[q.key] !== null) ans[q.key] = e[q.key]
        }
        setCommercialAnswers(ans)
      }
      if (e.pompe_cv) setPompeCv(String(e.pompe_cv))
      if (e.hmt_m) setPompeHmt(String(e.hmt_m))
      if (e.debit_souhaite_m3h) setPompeDebit(String(e.debit_souhaite_m3h))
      if (e.heures_pompage) setPompeHeures(String(e.heures_pompage))
      if (e.conso_annuelle) setConsoMensuelle(String(Math.round(e.conso_annuelle / 12)))
      // QF4 — round-trip du distributeur + de la consommation annuelle réelle
      // (ré-affichée en kWh/mois : le mode « MAD » ne peut pas se reconstruire
      // sans le tarif exact du moment, donc on revient toujours en kWh).
      if (e.distributeur) setDistributeur(String(e.distributeur))
      if (e.conso_annuelle) {
        setRealBillMode('kwh')
        setRealBillKwh(String(Math.round(e.conso_annuelle / 12)))
      }
      // Round-trip des données d'exploitation guidées (toutes optionnelles).
      if (e.region) setFarmRegion(String(e.region))
      if (e.crop) setFarmCrop(String(e.crop))
      if (e.surface_ha != null && e.surface_ha !== '') setFarmSurfaceHa(String(e.surface_ha))
      if (e.irrigation_method) setFarmIrrigation(String(e.irrigation_method))
      if (e.current_fuel) setFarmFuel(String(e.current_fuel))
      // fuel_spend_current est stocké en MAD/AN — on le réaffiche en annuel.
      if (e.fuel_spend_current != null && e.fuel_spend_current !== '') {
        setFarmFuelSpend(String(e.fuel_spend_current))
        setFarmFuelPeriod('an')
      }
      if (e.hmt_static != null && e.hmt_static !== '') setFarmHmtStatic(String(e.hmt_static))
      if (e.hmt_drawdown != null && e.hmt_drawdown !== '') setFarmHmtDrawdown(String(e.hmt_drawdown))
      if (e.profondeur_m != null && e.profondeur_m !== '') setPompeProfondeur(String(e.profondeur_m))
      // QJR66 — les trois dernières entrées pompage du formulaire. Elles
      // partaient déjà dans `etude_params` (`buildEtudePompage`) mais n'étaient
      // JAMAIS relues : rouvrir un brouillon agricole reposait les défauts
      // (immergée / triphasé / 20 m) par-dessus le choix du vendeur, et
      // l'enregistrement suivant les figeait. `alim` porte en plus le
      // drapeau « touché » : une valeur restaurée est un choix humain, pas un
      // défaut, et la déduction depuis le raccordement du lead ne doit plus
      // l'écraser.
      if (e.type_pompe) setPompeType(String(e.type_pompe))
      if (e.alim) dispatchSizing({ type: 'SAISI', champ: 'pompeAlim', valeur: String(e.alim) })
      if (e.distance_m != null && e.distance_m !== '') setPompeDistance(String(e.distance_m))
    }).catch(() => {
      setErrors(prev => ({
        ...prev,
        submit: 'Impossible de charger ce devis — il a peut-être été supprimé.',
      }))
    })
  }, [editId]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Réglages entreprise (Paramètres) → valeurs par défaut du générateur ──
  // FEATURE 10 : en CRÉATION uniquement, la date de validité par défaut suit
  // « validité du devis » (jours) et les heures de pompage suivent « heures de
  // pompage/jour ». Les champs restent librement éditables (rien n'est imposé).
  // En édition (?edit=ID), c'est le devis lui-même qui prime — on ne touche à
  // rien ici.
  const settingsLoaded = useRef(false)
  useEffect(() => {
    if (editId || settingsLoaded.current) return
    settingsLoaded.current = true
    parametresApi.getProfile().then(({ data }) => {
      const jours = parseInt(data?.quote_validity_days, 10)
      if (Number.isFinite(jours) && jours > 0) {
        const d = new Date()
        d.setDate(d.getDate() + jours)
        const iso = `${d.getFullYear()}-${String(d.getMonth() + 1)
          .padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
        setDateValidite(prev => prev || iso)
      }
      const heures = parseFloat(data?.agricole_pump_hours)
      if (Number.isFinite(heures) && heures > 0) {
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
      if (Number.isFinite(cible) && cible > 0) setPrixCible(prev => prev || String(cible))
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
    if (!leadParam || autoRan.current) return
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
  const onRealBillPaste = usePasteClean(parsePastedAmount,
    (clean) => (realBillMode === 'mad' ? setRealBillMad(clean) : setRealBillKwh(clean)))

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

  // VX18 — un modèle appliqué remplace les lignes du formulaire. La réponse
  // apply-preset porte les lignes du devis (modèle HT) ; on les reconvertit en
  // lignes d'écran (TTC) et on remplace via setLines(withKeys(...)). Repli sûr
  // si la forme diffère (aucun crash, on ignore).
  const handlePresetApplied = (data) => {
    const lignes = Array.isArray(data) ? data
      : (data?.lignes || data?.results || [])
    if (!Array.isArray(lignes) || !lignes.length) return
    const rows = lignes.map(l => ({
      produit: l.produit ?? l.produit_id ?? '',
      designation: l.designation ?? '',
      quantite: l.quantite ?? 1,
      // le modèle stocke le HT ; l'écran travaille en TTC (au taux de la ligne).
      prix_unit_ttc: ttcFromHt(l.prix_unitaire ?? l.prix_unit_ht ?? 0, l.taux_tva ?? 20),
      taux_tva: l.taux_tva ?? 20,
      groupeIndex: l.groupe_index ?? null,
      groupeLabel: l.groupe_label ?? '',
    }))
    setLines(withKeys(rows))
  }

  // Dimensionnement pompage : SOURCE UNIQUE écran / devis / PDF.
  // Courbe constructeur (HMT + débit souhaité) si une pompe à courbe convient,
  // sinon sélection historique par CV (débit manuel, pas de m³/jour inventé).
  // Déclaré AVANT handleAutoFill qui le lit (déplacé ici au recalage L-2OPT
  // 25/08 — eslint no-use-before-define, le code autour avait bougé).
  const pompageSel = modeInstallation === 'agricole'
    ? pompageSelection(produits, {
        cv: pompeCv, alim: pompeAlim, typePompe: pompeType,
        hmt: pompeHmt, debit: pompeDebit, heures: pompeHeures,
      })
    : null
  const pompageDims = pompageSel?.dims ?? null

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
      // PVMRQ — marques préférées (Paramètres → Gammes & marques, gamme
      // active de ce devis) : une marque épinglée gagne toujours, jamais de
      // repli silencieux sur une autre marque (voir marquesManquantes ci-dessous).
      marques: marquesActives,
      // PVORD — ordre par défaut de la société (Paramètres → Gammes &
      // marques, ou le bouton « Enregistrer cet ordre » de ce devis) ;
      // absent/vide = ordre canonique du simulateur (comportement historique).
      ordreLignes: gammesConfig?.ordre_lignes,
    })
    // L-2OPT (fondateur 24/08) — deux optimiseurs indépendants : en
    // résidentiel, un scénario qui sert RÉELLEMENT l'option AVEC (« Les
    // deux » ou « Avec batterie » seule) compose CETTE branche à SON PROPRE
    // optimum (kwc_avec, potentiellement différent du kwc_sans ci-dessus).
    // Fusion générique (fusionnerVariantes, solar.js) : deux tailles égales
    // (le cas le plus courant, et le repli quand aucune source n'a d'avis)
    // retombent sur la composition unique ci-dessus, BYTE-IDENTIQUE à
    // l'historique — aucune ligne variantée, repli de sécurité épinglé par
    // test.
    if (modeInstallation === 'residentiel'
        && (scenario === SCENARIO_LES_DEUX || scenario === SCENARIO_AVEC)) {
      const kwpAvec = resolveKwcAvec()
      if (Math.abs(kwpAvec - kwp) > 1e-9) {
        const composeAvec = () => autoFillLines(produits, {
          kwp: kwpAvec,
          panelW: parseFloat(panelW) || 710,
          structureType,
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
    // (autoconsommation réseau, pas de stockage).
    if (modeInstallation === 'industriel' || modeInstallation === 'commercial') {
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
    setLines(withKeys(generated))
    // QJR99 — rend les lignes composées : `resoudreComposition` (moitié pure de
    // `useComposition`) en a besoin pour NOMMER la source du repli.
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
      const taux = produit ? tauxTvaOf(produit) : (parseFloat(li.taux_tva) || 20)
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
    setLines(withKeys(generated))
  }

  const handleAutoFill = async () => {
    // PVOND — le bandeau des onduleurs grisés appartient au DERNIER
    // auto-remplissage : on le vide d'abord, sinon un message du run précédent
    // survivrait à un changement de mode (le pompage n'a pas d'onduleur).
    setOnduleursIncomplets([])
    // Mode agricole : équipement pompage (pompe + variateur + champ PV)
    if (modeInstallation === 'agricole') {
      const generated = autoFillPompage(produits, {
        cv: pompeCv, alim: pompeAlim, typePompe: pompeType,
        distance: pompeDistance, structureType,
        hmt: pompeHmt, debit: pompeDebit, heures: pompeHeures,
      })
      if (!generated.length) {
        setErrors(e => ({ ...e, autofill: 'Renseignez la puissance pompe (CV) ou HMT + débit souhaité.' }))
        return
      }
      setErrors(e => ({ ...e, autofill: null, marquesManquantes: null }))
      setLines(withKeys(generated))
      // QJR99 — le dimensionnement pompage POSE une taille calculée : la même
      // transition que la réouverture d'un devis (`REOUVERTURE`) la pose SANS
      // marquer le champ « touché » (ce n'est pas une frappe) et tient la
      // cible kWc à jour avec elle.
      if (pompageSel) {
        dispatchSizing({ type: 'REOUVERTURE', devis: { panneaux: pompageSel.dims.nbPanneaux } })
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
          structure_type: structureType,
        }
        // Même déclenchement que la fusion locale ci-dessus (composeLocalement) :
        // seuls « Les deux » et « Avec batterie » servent réellement l'axe
        // batterie, et seulement quand il diverge du champ sans stockage.
        if (scenario === SCENARIO_LES_DEUX || scenario === SCENARIO_AVEC) {
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
        setCompositionSourceLocale(null)
        appliquerCompositionServeur(data)
      } catch (err) {
        // REPLI — jamais un écran sans Auto-remplir pour une panne réseau.
        console.error('composerDevis (dry-run) indisponible, repli local :', err)
        // QJR36 — la raison est posée dans l'état (comme `sizingServeurMessage`
        // pour le refus serveur) ; le vendeur reçoit désormais la bannière
        // visible ci-dessous au lieu d'un simple console.error silencieux.
        // QJR99 — cette raison n'est plus rédigée ici : `raisonRepli` (moitié
        // pure de `useComposition`) la produit, ce qui la rend STRUCTURELLE —
        // une composition locale ne peut plus s'afficher sans dire d'où elle
        // vient ni pourquoi. Le repli lui-même est INCHANGÉ.
        setCompositionSourceLocale(raisonRepli(err?.message || 'panne réseau/serveur'))
        composeLocalement()
      } finally {
        setAutoFillLoading(false)
      }
      return
    }
    composeLocalement()
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
    dispatchSizing({ type: 'TAILLE_APPLIQUEE', ligne })
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
  // réseau) : aucune deuxième règle de composition, et donc le même
  // remplacement intégral des lignes que l'Auto-remplir existant produit déjà
  // aujourd'hui (il ne préserve pas plus les lignes ajoutées à la main que
  // lui — comportement historique inchangé, pas régressé par ce bouton).
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
    dispatchSizing({ type: 'RECALCUL_DEMANDE', retenu })
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
    Promise.resolve(handleAutoFill()).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ne réagit qu'au compteur de composition du reducer
  }, [recalcDimTick])

  // ── Sauvegarde ──
  // Une ligne est enregistrée si elle a un produit et une quantité > 0 ;
  // les lignes placeholder (sans produit, prix 0) sont ignorées silencieusement.
  const usableLines = () =>
    lines.filter(l => l.produit && parseFloat(l.quantite) > 0)

  const validate = () => {
    const e = {}
    if (!clientId && !leadId) e.client = 'Sélectionnez un lead ou un client'
    // L'étude industrielle exige la consommation réelle du client
    if (modeInstallation === 'industriel' && !(consoKwhDerivee > 0)) {
      e.conso = 'Mode industriel : renseignez la consommation mensuelle (kWh) '
        + 'ou les factures électriques — l\'étude en dépend.'
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
      // agricole : ≥ 1 pompe. Échappatoire DOCUMENTÉE : cocher « avenant /
      // accessoires seuls » (accessoiresOnly) désactive la garde pour un devis
      // d'accessoires/main-d'œuvre légitime (SAV, extension câblage…).
      const usable = usableLines()
      const has = (pred) => usable.some(l => pred(l.designation))
      if (modeInstallation === 'agricole') {
        if (!has(isPompe)) {
          e.lines = 'Un devis de pompage doit contenir au moins une pompe. '
            + 'Utilisez « Auto-remplir » ou ajoutez une pompe, ou cochez '
            + '« avenant / accessoires seuls ».'
        }
      } else {
        const hasPanel = has(isPanel)
        const hasInverter = has(d => isReseauInverter(d) || isHybridInverter(d))
        if (!hasPanel || !hasInverter) {
          const manque = [
            !hasPanel ? 'un panneau' : null,
            !hasInverter ? 'un onduleur' : null,
          ].filter(Boolean).join(' et ')
          e.lines = `Un devis solaire doit contenir au moins ${manque}. `
            + 'Utilisez « Auto-remplir » ou ajoutez ces lignes, ou cochez '
            + '« avenant / accessoires seuls ».'
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
    let conso = consoDejaConnue ?? null
    if (conso == null && consoAnnuelleReelle > 0) conso = consoAnnuelleReelle
    if (conso == null && entrees.factures_mensuelles_reelles) {
      const derivee = Math.round(entrees.factures_mensuelles_reelles.reduce(
        (somme, bill) => somme + (kwhFromBill(bill, distributeur).kwhMensuel || 0), 0))
      if (derivee > 0) conso = derivee
    }
    if (conso != null) {
      entrees.conso_annuelle = conso
      entrees.distributeur = distributeur
    } else if (distributeur && distributeur !== 'onee') {
      entrees.distributeur = distributeur
    }
    return entrees
  }

  // QXMT — la répartition horaire TELLE QUE SAISIE, ou `null` (règle Z2 : un
  // site repassé en BT n'a plus de répartition MT, on la RETIRE au lieu de
  // laisser traîner celle d'hier). Rien de rempli ⇒ `null` aussi : l'étude MT
  // omet alors économies et payback plutôt que d'inventer un barème.
  const repartitionMtSaisie = () => {
    if (tensionRaccordement !== 'mt') return null
    const parts = {}
    for (const creneau of ['pointe', 'pleines', 'creuses']) {
      const n = parseFloat(repartitionMt[creneau])
      if (Number.isFinite(n)) parts[creneau] = n
    }
    return Object.keys(parts).length ? parts : null
  }

  const blocEtudeMarche = () => {
    const nombre = (v) => {
      const n = parseFloat(v)
      return Number.isFinite(n) ? n : null
    }
    if (modeInstallation === 'industriel' || modeInstallation === 'commercial') {
      const etude = (modeInstallation === 'industriel'
        ? etudeIndustrielle : etudeCommerciale) || {}
      const bloc = {
        ...choixEcran(),
        ...entreesReellesEcran(nombre(etude.conso_annuelle)),
        taux_autoconso: nombre(etude.taux_autoconso),
        taux_couverture: nombre(etude.taux_couverture),
        payback: nombre(etude.payback),
        injection_kwh_an: nombre(etude.injection_kwh_an),
        injection_dh_an: nombre(etude.injection_dh_an),
        // QXMT — raccordement du site + répartition horaire : le mappeur
        // `?edit=` les relit, donc elles doivent être PERSISTÉES, sinon un
        // devis MT rouvert repartait silencieusement au barème BT. On stocke
        // ce que le vendeur a TAPÉ (l'entrée), pas la répartition normalisée
        // par l'étude : c'est la forme que le formulaire réinjecte.
        tension_raccordement: tensionRaccordement || null,
        repartition_mt: repartitionMtSaisie(),
      }
      if (modeInstallation === 'commercial') {
        // QX44 — la catégorie ET ses réponses (clés snake_case à plat, comme
        // le mappeur `?edit=` les relit : `e[q.key]`). Coercition de type
        // IDENTIQUE à celle d'avant, jamais de `prix_achat`.
        bloc.categorie_commerciale = categorieCommerciale || null
        for (const q of (COMMERCIAL_CATEGORY_QUESTIONS[categorieCommerciale] || [])) {
          const brut = commercialAnswers[q.key]
          if (brut === undefined || brut === '' || brut === null) continue
          bloc[q.key] = q.type === 'number'
            ? (parseFloat(brut) || 0)
            : q.type === 'bool' ? !!brut : String(brut)
        }
      }
      return bloc
    }
    if (modeInstallation === 'agricole') {
      // MÊME dérivation que l'aperçu écran et que le devis auto
      // (`buildEtudePompage`) : une seule formule, jamais deux chiffres qui
      // pourraient diverger. Seules les clés du schéma en sortent, typées.
      const p = pompageSel
        ? buildEtudePompage(pompageSel, {
            typePompe: pompeType, alim: pompeAlim,
            hmt: pompeHmt, debit: pompeDebit, heures: pompeHeures,
            profondeur: pompeProfondeur, distance: pompeDistance,
          })
        : {}
      return {
        ...choixEcran(),
        ...entreesReellesEcran(null),
        // DÉRIVÉES du dimensionnement (propriétaire ECRAN au schéma).
        pompe_cv: nombre(p.pompe_cv),
        pompe_kw: nombre(p.pompe_kw),
        debit_hmt_m3h: nombre(p.debit_hmt_m3h),
        m3_jour: nombre(p.m3_jour),
        champ_kwc: nombre(p.champ_kwc),
        // ENTRÉES du vendeur, prises à l'ÉTAT de l'écran (pas au
        // dimensionnement) : ce sont elles que le mappeur `?edit=` réinjecte
        // dans le formulaire, et elles existent même quand aucune pompe à
        // courbe ne peut être retenue.
        hmt_m: nombre(pompeHmt),
        debit_souhaite_m3h: nombre(pompeDebit),
        heures_pompage: nombre(pompeHeures),
        type_pompe: pompeType || null,
        alim: pompeAlim || null,
        profondeur_m: nombre(pompeProfondeur),
        distance_m: nombre(pompeDistance),
        // Exploitation guidée (toutes optionnelles, toutes relues par `?edit=`).
        irrigation_method: farmIrrigation || null,
        region: farmRegion || null,
        crop: farmCrop || null,
        surface_ha: nombre(farmSurfaceHa),
        current_fuel: farmFuel || null,
        fuel_spend_current: nombre(farmFuelSpendAnnual),
        hmt_static: nombre(farmHmtStatic),
        hmt_drawdown: nombre(farmHmtDrawdown),
      }
    }
    // Résidentiel : le serveur est propriétaire de son ÉTUDE — mais pas des
    // CHOIX du vendeur ni des entrées réelles qu'il vient de taper (arbitrage
    // « zéro perte »). Objet vide ⇒ aucun appel du tout (voir
    // `persisterDevis`) ; en pratique `choixEcran()` porte toujours au moins
    // le scénario, sans quoi le moteur PDF totaliserait les deux options.
    const entrees = { ...choixEcran(), ...entreesReellesEcran(null) }
    return Object.keys(entrees).length ? entrees : null
  }

  // Cœur de persistance extrait de `handleSubmit` (aucun changement de
  // comportement) : construit le payload + les lignes, écrit le devis (édition
  // atomique ou création atomique), attache l'étude du marché par l'endpoint de
  // fusion (QJR66 ci-dessus), et RENVOIE {devisId, devisCree} en cas de succès
  // — null sinon (le message HUMAIN est déjà posé dans `errors.submit`).
  // PV23bis (fondateur 20/08) — `ouvrirConception3D` ci-dessous réutilise
  // EXACTEMENT ce même chemin d'écriture pour le bouton « Concevoir en 3D » :
  // un seul endroit qui sait enregistrer un devis, jamais une seconde logique
  // dupliquée.
  const persisterDevis = async () => {
    setSaving(true)
    try {
      const payload = {
        statut: 'brouillon',
        date_validite: dateValidite || null,
        taux_tva: tauxTva,
        remise_globale: discountPct || '0',
        note: note || null,
        mode_installation: modeInstallation,
        prix_cible_kwc: prixCible !== '' ? prixCible : null,
      }
      // QX21 — lignes construites UNE fois (mêmes champs qu'avant : HT dérivé du
      // TTC saisi au taux DE LA LIGNE, groupe villa en mode « villas »).
      // XSAL14 — lignes retenues : produits utilisables + lignes de section/note
      // (intitulé non vide). L'ordre visuel est conservé (ordre = index) pour
      // intercaler les intertitres au bon endroit. Une ligne section/note ne
      // porte ni produit ni prix.
      const isStructure = (l) => l.typeLigne === 'section' || l.typeLigne === 'note'
      const keptLines = lines.filter(l => isStructure(l)
        ? !!(l.designation || '').trim()
        : (l.produit && parseFloat(l.quantite) > 0))
      const lignesPayload = keptLines.map((l, idx) => {
        if (isStructure(l)) {
          return {
            type_ligne: l.typeLigne,
            ordre: idx,
            designation: l.designation,
          }
        }
        return {
          produit: parseInt(l.produit),
          designation: l.designation,
          quantite: l.quantite,
          prix_unitaire: htFromTtc(l.prix_unit_ttc, l.taux_tva ?? 20),
          remise: '0',
          taux_tva: String(l.taux_tva ?? 20),
          groupe_index: multiMode === 'villas' ? l.groupeIndex : null,
          groupe_label: multiMode === 'villas' ? (l.groupeLabel || '') : '',
          // XSAL5 — ligne optionnelle (add-on hors total). Défaut False.
          optionnelle: !!l.optionnelle,
          // XSAL14 — type produit (défaut) + position d'affichage.
          type_ligne: 'produit',
          ordre: idx,
          // L-2OPT (fondateur 24/08) — '' commun | 'sans' | 'avec', posée par
          // `fusionnerVariantes` quand les deux optimiseurs résidentiels
          // divergent. Envoyée systématiquement (le champ absent d'un ancien
          // backend est simplement ignoré par le serializer — jamais bloquant).
          variante: l.variante || '',
          // QJR65 / décision fondateur D12 — le PRIX est une entrée commerciale
          // PERSISTANTE : le marqueur part avec la ligne (`prix_manuel`, accepté
          // par `_replace_lines_atomic`, QJR59/QJR60) pour que la réouverture en
          // `?edit=` le repose et qu'aucun rafraîchissement tarifaire ne
          // réécrive le prix négocié. Sans lui, le marqueur serait remis à
          // `False` à CHAQUE enregistrement — le trou que D12 referme.
          prix_manuel: !!l.prixManuel,
        }
      })

      let devisId
      let devisCree = null
      if (editDevis) {
        // QX21 — ÉDITION ATOMIQUE : le patch du devis PUIS le remplacement des
        // lignes en une transaction serveur. Un échec préserve les lignes
        // existantes (jamais un devis à zéro ligne, plus de delete-puis-recrée).
        await ventesApi.patchDevis(editDevis.id, payload)
        await ventesApi.replaceLignesDevis(editDevis.id, lignesPayload)
        devisId = editDevis.id
        devisCree = { reference: editDevis.reference }
      } else {
        // QX21 — CRÉATION ATOMIQUE : devis + lignes en UN commit serveur → plus
        // de brouillon orphelin/partiel si la connexion est coupée en cours de
        // sauvegarde. Lead prioritaire : le client est résolu côté serveur.
        if (leadId) payload.lead = parseInt(leadId)
        else payload.client = parseInt(clientId)
        const { data } = await ventesApi.createDevisAtomic({
          ...payload, lignes: lignesPayload,
        })
        devisId = data.id
        devisCree = data
      }

      // QJR66 — l'étude du marché courant part par l'endpoint de FUSION, APRÈS
      // les lignes : le serveur vient d'y recalculer ses propres blocs
      // (`rafraichir_etudes_du_devis`), et cette fusion ne touche QUE les clés
      // qu'elle envoie. Résidentiel ⇒ aucun appel.
      const etudeMarche = blocEtudeMarche()
      if (etudeMarche) {
        try {
          await ventesApi.patchEtudeParams(devisId, etudeMarche)
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

      return { devisId, devisCree }
    } catch (err) {
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

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    const res = await persisterDevis()
    if (res) { clear(); finish(res.devisId, res.devisCree) }
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
  // (MAD / prix kWh ONEE). L'étude EXIGE une consommation réelle.
  const avgBill = monthly.reduce((s, v) => s + (parseFloat(v) || 0), 0) / 12
  const consoKwhDerivee = (parseFloat(consoMensuelle) || 0)
    || (facturesSaisies && avgBill > 0 ? Math.round(avgBill / quoteLogic.kwhPrice) : 0)

  const etudeIndustrielle = (modeInstallation === 'industriel' && kwp > 0
      && consoKwhDerivee > 0)
    ? computeEtudeIndustrielle({
        kwp, consoMensuelleKwh: consoKwhDerivee,
        dayUsagePct: dayUsage, totalTtc: kpiTotal,
        kwhPrice: quoteLogic.kwhPrice, efficiency: quoteLogic.efficiency,
        injectionEnabled, ...etudeTension,
      })
    : null

  // QX44 — étude COMMERCIALE : même moteur d'autoconsommation que l'industriel,
  // mais le day-share vient de l'ARCHÉTYPE de la catégorie (hôtel 55 ≠ bureau 80)
  // → à facture égale, une étude hôtel diffère d'une étude bureau.
  const etudeCommerciale = (modeInstallation === 'commercial' && kwp > 0
      && consoKwhDerivee > 0)
    ? computeEtudeIndustrielle({
        kwp, consoMensuelleKwh: consoKwhDerivee,
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

  // ── Données d'exploitation guidées → dépense carburant ANNUELLE + besoin eau ──
  // La dépense saisie au mois est ramenée à l'année (clé fuel_spend_current en
  // MAD/AN). farmFuelSpendAnnual reste '' si rien n'est saisi (champ optionnel).
  const farmFuelSpendAnnual = (() => {
    const v = parseFloat(farmFuelSpend)
    if (!Number.isFinite(v) || v <= 0) return ''
    return farmFuelPeriod === 'mois' ? Math.round(v * 12) : Math.round(v)
  })()

  // Besoin en eau de POINTE (FAO-56) — informatif, le backend le recalcule.
  const farmWaterDemand = useMemo(() => {
    if (modeInstallation !== 'agricole') return null
    if (!(parseFloat(farmSurfaceHa) > 0)) return null
    return waterDemandFromFarm({
      crop: farmCrop, region: farmRegion,
      surfaceHa: farmSurfaceHa, method: farmIrrigation,
    })
  }, [modeInstallation, farmCrop, farmRegion, farmSurfaceHa, farmIrrigation])
  // Volume jour livré par la pompe choisie (m³/jour) — comparé au besoin.
  const pumpM3Day = pompageSel?.m3Jour ?? null

  const pkwc = prixParKwc(kpiTotal, kwp)
  const buyCost = useMemo(() => computeBuyCost(lines, produits), [lines, produits])
  const marge = buyCost != null ? Math.round(kpiTotal - buyCost) : null

  const applyPrixCible = () => {
    const pct = discountForTarget(prixCible, kwp, kpiTotalBrut)
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
        {restored && (
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
              <Label htmlFor="gen-insttype">Type d'Installation</Label>
              <Select value={instType} onValueChange={onInstTypeChange}>
                <SelectTrigger id="gen-insttype"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="Résidentielle">Résidentielle</SelectItem>
                  <SelectItem value="Commerciale">Commerciale</SelectItem>
                  <SelectItem value="Industrielle">Industrielle</SelectItem>
                  <SelectItem value="Agricole">Agricole</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="gen-scenario">Scénario</Label>
              <Select value={scenario} onValueChange={onScenarioChange}>
                <SelectTrigger id="gen-scenario"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="Les deux (Sans + Avec)">Les deux (Sans + Avec batterie)</SelectItem>
                  <SelectItem value="Sans batterie">Sans batterie seulement</SelectItem>
                  <SelectItem value="Avec batterie">Avec batterie seulement</SelectItem>
                </SelectContent>
              </Select>
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
                <Label htmlFor="gen-lead" required>Lead (point de départ)</Label>
                <Select value={leadId ? String(leadId) : undefined} onValueChange={applyLead}>
                  <SelectTrigger id="gen-lead" invalid={!!errors.client}>
                    <SelectValue placeholder="— Sélectionner un lead —" />
                  </SelectTrigger>
                  <SelectContent>
                    {leads.map(l => (
                      <SelectItem key={l.id} value={String(l.id)}>
                        {l.nom}{l.prenom ? ` ${l.prenom}` : ''}
                        {l.societe ? ` (${l.societe})` : ''}
                        {l.facture_hiver ? ` — ${Math.round(parseFloat(l.facture_hiver))} MAD/mois` : ''}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
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

            {!leadId && (
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

        {/* ── Factures électriques (masquées en mode pompage) ── */}
        {modeInstallation !== 'agricole' && (
        <Card>
          <GenCardHeader icon={Zap} title="Factures Électriques" />
          <CardContent className="pt-4">
            <p className="text-sm text-muted-foreground">
              Renseignez vos factures mensuelles (MAD) ou estimez-les via les montants
              hiver/été. Ces valeurs servent au calcul ROI dans le devis.
            </p>
            <div className="mt-3 grid items-end gap-4 sm:grid-cols-3">
              <div className="grid gap-1.5">
                <Label htmlFor="gen-hiver">Facture Hiver moy. (MAD/mois)</Label>
                <Input id="gen-hiver" type="number" min="0" step="any"
                       placeholder="ex: 600" value={fHiver}
                       onChange={e => { setFHiver(e.target.value); syncBillEstimator(e.target.value, fEte) }}
                       onPaste={onHiverPaste} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="gen-ete">Facture Été moy. (MAD/mois)</Label>
                <Input id="gen-ete" type="number" min="0" step="any"
                       placeholder="ex: 400" value={fEte}
                       onChange={e => { setFEte(e.target.value); syncBillEstimator(fHiver, e.target.value) }}
                       onPaste={onEtePaste} />
              </div>
              <Button type="button" variant="outline" onClick={handleEstimerMois}>
                <BarChart3 /> Estimer 12 mois
              </Button>
            </div>
            {errors.bills && <p className="mt-1 text-xs text-destructive">{errors.bills}</p>}
            <div className="gen-monthly-grid">
              {MONTHS_FR.map((m, i) => (
                <div key={m} className="gen-month">
                  <span className="gen-month-label">{m}</span>
                  <input type="number" min="0" step="any" className="form-control form-control-sm"
                         value={monthly[i]}
                         onChange={e => setMonth(i, e.target.value)} />
                </div>
              ))}
            </div>

            {/* QF4 — distributeur réel + facture/consommation réelle : nourrit
                le calcul « deux factures » par tranche (backend QF2) avec les
                vrais chiffres du client au lieu des défauts. */}
            <div className="mt-4 rounded-lg border border-info/30 bg-info/5 p-3 sm:p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Zap className="size-4 text-info" aria-hidden="true" />
                <span className="font-display text-sm font-semibold tracking-tight">
                  Facture réelle du client (recommandé)
                </span>
                {/* VX47 — aide contextuelle : le calcul « par tranche » selon
                    le distributeur n'est pas intuitif pour un nouvel employé. */}
                <HelpTip label="Aide — distributeur et tranches">
                  Chaque distributeur (ONEE, Lydec, Redal) facture l'électricité
                  par <strong>tranches</strong> : plus la consommation est
                  élevée, plus le prix du kWh grimpe. En renseignant la facture
                  ou consommation réelle du client, l'économie solaire est
                  calculée avec le vrai barème du distributeur choisi — sans
                  ces champs, une estimation par défaut est utilisée.
                </HelpTip>
                <span className="text-xs text-muted-foreground">
                  affine les économies avec le barème par tranche du distributeur
                </span>
              </div>
              <div className="mt-3 grid gap-4 sm:grid-cols-3">
                <div className="grid gap-1.5">
                  <Label htmlFor="gen-distributeur">Distributeur</Label>
                  <Select value={distributeur} onValueChange={setDistributeur}>
                    <SelectTrigger id="gen-distributeur"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="onee">ONEE</SelectItem>
                      <SelectItem value="lydec">Lydec (Casablanca)</SelectItem>
                      <SelectItem value="redal">Redal (Rabat-Salé-Kénitra)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="gen-realbill">
                    {realBillMode === 'mad' ? 'Facture réelle (MAD/mois)' : 'Consommation réelle (kWh/mois)'}
                  </Label>
                  <div className="flex gap-2">
                    <Input id="gen-realbill" type="number" min="0" step="any" className="flex-1"
                           placeholder={realBillMode === 'mad' ? 'ex: 850' : 'ex: 650'}
                           value={realBillMode === 'mad' ? realBillMad : realBillKwh}
                           onChange={e => (realBillMode === 'mad'
                             ? setRealBillMad(e.target.value)
                             : setRealBillKwh(e.target.value))}
                           onPaste={onRealBillPaste} />
                    <Select value={realBillMode} onValueChange={setRealBillMode}>
                      <SelectTrigger className="w-24"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="mad">MAD</SelectItem>
                        <SelectItem value="kwh">kWh</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="grid gap-1.5">
                  <Label>Consommation annuelle dérivée</Label>
                  <div className="gen-kwp">
                    {consoAnnuelleReelle != null ? `${fmtNum(consoAnnuelleReelle)} kWh/an` : '—'}
                  </div>
                </div>
              </div>
            </div>

            {(modeInstallation === 'industriel' || modeInstallation === 'commercial') && (
              <div className="mt-3.5 grid gap-4 sm:grid-cols-2">
                <div className="grid gap-1.5">
                  <Label htmlFor="gen-conso">Consommation mensuelle (kWh) — pour l'étude</Label>
                  <Input id="gen-conso" type="number" min="0" step="any"
                         placeholder="ex: 12000" value={consoMensuelle}
                         onChange={e => setConsoMensuelle(e.target.value)} />
                </div>
                {/* QX50 — injection du surplus (loi 82-21), OFF par défaut */}
                <div className="grid gap-1.5">
                  <Label>Injection du surplus (loi 82-21)</Label>
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={injectionEnabled}
                           onChange={e => setInjectionEnabled(e.target.checked)} />
                    Valoriser le surplus injecté (plafond 20 %, tarif ANRE net)
                  </label>
                  <p className="text-xs text-muted-foreground">
                    Tarif ANRE 03/2026-02/2027, plafond en révision.
                  </p>
                </div>
                {/* QXMT — tension de raccordement : un site MT n'est pas
                    facturé au barème BT. 'bt' par défaut → étude inchangée. */}
                <div className="grid gap-1.5">
                  <Label>Raccordement du site</Label>
                  <Segmented
                    data-testid="gen-tension"
                    options={[
                      { value: 'bt', label: 'Basse tension (BT)' },
                      { value: 'mt', label: 'Moyenne tension (MT)' },
                    ]}
                    value={tensionRaccordement}
                    onChange={(v) => dispatchSizing({ type: 'SAISI', champ: 'tension', valeur: v })}
                  />
                  <p className="text-xs text-muted-foreground">
                    Au-delà de ~50 kW le site est en général raccordé en MT :
                    l'étude bascule alors sur le barème horaire ONEE MT.
                  </p>
                </div>
              </div>
            )}

            {/* QXMT — répartition horaire du site MT. Aucune valeur par défaut :
                les plages horaires MT officielles ne sont pas publiées, donc
                aucune répartition n'est inventée. Sans saisie, l'étude OMET
                les économies plutôt que d'afficher un chiffre douteux. */}
            {estMt && (
              <div className="mt-3.5" data-testid="gen-mt-block">
                <div className="grid gap-4 sm:grid-cols-3">
                  {[
                    ['pointe', 'Heures de pointe (%)', TARIF_MT_ONEE.POINTE],
                    ['pleines', 'Heures pleines (%)', TARIF_MT_ONEE.PLEINES],
                    ['creuses', 'Heures creuses (%)', TARIF_MT_ONEE.CREUSES],
                  ].map(([key, label, prix]) => (
                    <div className="grid gap-1.5" key={key}>
                      <Label htmlFor={`gen-mt-${key}`}>{label}</Label>
                      <Input id={`gen-mt-${key}`} type="number" min="0" step="any"
                             data-testid={`gen-mt-${key}`}
                             placeholder="ex: 20"
                             value={repartitionMt[key]}
                             onChange={e => setPartMt(key, e.target.value)} />
                      <p className="text-xs text-muted-foreground">
                        {prix != null
                          ? `${formatNumber(prix, { decimals: 4 })} DH/kWh`
                          : 'tarif à fournir par le fondateur'}
                      </p>
                    </div>
                  ))}
                </div>
                {tarifMtApplique != null ? (
                  <p className="mt-2 text-xs text-muted-foreground" data-testid="gen-mt-tarif">
                    Tarif MT moyen retenu ≈{' '}
                    <strong>{formatNumber(tarifMtApplique, { decimals: 4 })} DH/kWh</strong>
                    {' · '}{TARIF_MT_ONEE.MENTION}
                  </p>
                ) : (
                  <p className="mt-2 text-xs text-warning" data-testid="gen-mt-manquant">
                    {tarifMtDisponible()
                      ? 'Répartition horaire non renseignée : les économies et le '
                        + 'payback sont volontairement omis de l\'étude (les plages '
                        + 'horaires MT officielles ne sont pas publiées — aucun '
                        + 'chiffre n\'est supposé à votre place).'
                      : 'Barème MT ONEE indisponible en source officielle : les '
                        + 'économies et le payback sont omis de l\'étude.'}
                  </p>
                )}
              </div>
            )}

            {/* QX44 — étude commerciale par catégorie */}
            {modeInstallation === 'commercial' && (
              <div className="mt-3.5">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="grid gap-1.5">
                    <Label>Catégorie commerciale</Label>
                    <Select value={categorieCommerciale} onValueChange={setCategorieCommerciale}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {COMMERCIAL_CATEGORIES.map(c => (
                          <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      Profil de charge diurne ≈ {commercialDayShare(categorieCommerciale)} %
                      (ajuste l'autoconsommation de l'étude).
                    </p>
                  </div>
                </div>
                {(COMMERCIAL_CATEGORY_QUESTIONS[categorieCommerciale] || []).length > 0 && (
                  <div className="mt-3 grid gap-4 sm:grid-cols-2">
                    {(COMMERCIAL_CATEGORY_QUESTIONS[categorieCommerciale] || []).map(q => (
                      <div className="grid gap-1.5" key={q.key}>
                        <Label htmlFor={`gen-com-${q.key}`}>{q.label}</Label>
                        {q.type === 'number' && (
                          <Input id={`gen-com-${q.key}`} type="number" min="0" step="any"
                                 value={commercialAnswers[q.key] ?? ''}
                                 onChange={e => setCommercialAnswer(q.key, e.target.value)} />
                        )}
                        {q.type === 'select' && (
                          <Select value={commercialAnswers[q.key] ?? ''}
                                  onValueChange={v => setCommercialAnswer(q.key, v)}>
                            <SelectTrigger id={`gen-com-${q.key}`}><SelectValue placeholder="—" /></SelectTrigger>
                            <SelectContent>
                              {q.options.map(o => (
                                <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        )}
                        {q.type === 'bool' && (
                          <label className="flex items-center gap-2 text-sm cursor-pointer">
                            <input id={`gen-com-${q.key}`} type="checkbox"
                                   checked={!!commercialAnswers[q.key]}
                                   onChange={e => setCommercialAnswer(q.key, e.target.checked)} />
                            Oui
                          </label>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
        )}

        {/* ── Pompage solaire (mode Agricole) ── */}
        {modeInstallation === 'agricole' && (
        <Card>
          <GenCardHeader icon={Sprout} title="Pompage solaire" />
          <CardContent className="pt-4">
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="grid gap-1.5">
                <Label htmlFor="gen-pompecv">
                  Puissance pompe (CV){pompageSel?.mode === 'courbe' && ' — auto (courbe)'}
                </Label>
                <Input id="gen-pompecv" type="number" min="0" step="any"
                       value={pompeCv} onChange={e => setPompeCv(e.target.value)} />
                {pompageDims && (
                  <p className="text-xs text-muted-foreground">
                    ≈ {pompageSel?.kw ?? pompageDims.kw} kW · champ PV conseillé {pompageDims.champKw} kWc
                    ({pompageDims.nbPanneaux} panneaux 710 W)
                  </p>
                )}
              </div>
              <div className="grid gap-1.5">
                <Label>Type de pompe</Label>
                <Segmented
                  options={[
                    { value: 'immergee', label: 'Immergée' },
                    { value: 'surface', label: 'Surface' },
                  ]}
                  value={pompeType}
                  onChange={setPompeType}
                />
              </div>
              <div className="grid gap-1.5">
                <Label>Alimentation</Label>
                <Segmented
                  options={[
                    { value: 'mono', label: 'Mono 220V' },
                    { value: 'tri', label: 'Tri 380V' },
                  ]}
                  value={pompeAlim}
                  onChange={(v) => dispatchSizing({ type: 'SAISI', champ: 'pompeAlim', valeur: v })}
                />
              </div>
            </div>
            <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <div className="grid gap-1.5">
                <Label htmlFor="gen-hmt">HMT (m)</Label>
                <Input id="gen-hmt" type="number" min="0" step="any"
                       placeholder="ex: 120" value={pompeHmt}
                       onChange={e => setPompeHmt(e.target.value)} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="gen-debit">Débit souhaité (m³/h)</Label>
                <Input id="gen-debit" type="number" min="0" step="any"
                       placeholder="ex: 30" value={pompeDebit}
                       onChange={e => setPompeDebit(e.target.value)} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="gen-heures">Heures de pompage effectives / jour</Label>
                <Input id="gen-heures" type="number" min="0" step="any"
                       value={pompeHeures}
                       onChange={e => setPompeHeures(e.target.value)} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="gen-profondeur">Profondeur forage (m) — optionnel</Label>
                <Input id="gen-profondeur" type="number" min="0" step="any"
                       value={pompeProfondeur}
                       onChange={e => setPompeProfondeur(e.target.value)} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="gen-distance">Distance panneaux → coffret (m)</Label>
                <Input id="gen-distance" type="number" min="0" step="any"
                       value={pompeDistance}
                       onChange={e => setPompeDistance(e.target.value)} />
              </div>
            </div>

            {/* ── Votre exploitation (données GUIDÉES, toutes optionnelles) ── */}
            {/* Encouragées : elles permettent au PDF de dimensionner et chiffrer
                sur les données réelles du fermier (besoin en eau FAO-56, économies
                vs carburant). Aucune n'est obligatoire — chacune a un défaut. */}
            <div className="mt-4 rounded-lg border border-success/30 bg-success/5 p-3 sm:p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Sprout className="size-4 text-success" aria-hidden="true" />
                <span className="font-display text-sm font-semibold tracking-tight">
                  Votre exploitation
                </span>
                <span className="text-xs text-muted-foreground">
                  recommandé — affine le devis avec les données réelles du fermier
                </span>
              </div>
              <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <div className="grid gap-1.5">
                  <Label htmlFor="gen-farm-surface">
                    Surface irriguée (ha)
                  </Label>
                  <Input id="gen-farm-surface" type="number" min="0" step="any"
                         placeholder="ex: 5" value={farmSurfaceHa}
                         onChange={e => setFarmSurfaceHa(e.target.value)} />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="gen-farm-crop">Culture</Label>
                  <Select value={farmCrop} onValueChange={setFarmCrop}>
                    <SelectTrigger id="gen-farm-crop"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="agrumes">Agrumes</SelectItem>
                      <SelectItem value="maraichage">Maraîchage</SelectItem>
                      <SelectItem value="olivier">Olivier</SelectItem>
                      <SelectItem value="dattier">Dattier (palmier)</SelectItem>
                      <SelectItem value="cereales">Céréales</SelectItem>
                      <SelectItem value="luzerne">Luzerne / fourrage</SelectItem>
                      <SelectItem value="arganier">Arganier</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="gen-farm-region">Région</Label>
                  <Select value={farmRegion} onValueChange={setFarmRegion}>
                    <SelectTrigger id="gen-farm-region"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="souss-massa">Souss-Massa (Agadir)</SelectItem>
                      <SelectItem value="doukkala">Doukkala (El Jadida)</SelectItem>
                      <SelectItem value="tadla">Tadla (Béni Mellal)</SelectItem>
                      <SelectItem value="saiss">Saïss (Fès-Meknès)</SelectItem>
                      <SelectItem value="oriental">Oriental (Berkane)</SelectItem>
                      <SelectItem value="draa-tafilalet">Drâa-Tafilalet</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="gen-farm-irrigation">Mode d'irrigation</Label>
                  <Select value={farmIrrigation} onValueChange={setFarmIrrigation}>
                    <SelectTrigger id="gen-farm-irrigation"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="goutte">Goutte-à-goutte</SelectItem>
                      <SelectItem value="aspersion">Aspersion</SelectItem>
                      <SelectItem value="gravitaire">Gravitaire</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="gen-farm-fuel">Énergie actuelle</Label>
                  <Select value={farmFuel} onValueChange={setFarmFuel}>
                    <SelectTrigger id="gen-farm-fuel"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="butane">Butane (gaz)</SelectItem>
                      <SelectItem value="diesel">Diesel (gasoil)</SelectItem>
                      <SelectItem value="none">Aucune / nouveau forage</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="gen-farm-fuelspend">
                    Dépense carburant actuelle (MAD) — optionnel
                  </Label>
                  <div className="flex gap-2">
                    <Input id="gen-farm-fuelspend" type="number" min="0" step="any"
                           className="flex-1"
                           placeholder="ex: 2000" value={farmFuelSpend}
                           onChange={e => setFarmFuelSpend(e.target.value)} />
                    <Select value={farmFuelPeriod} onValueChange={setFarmFuelPeriod}>
                      <SelectTrigger id="gen-farm-fuelperiod" className="w-28">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="mois">/ mois</SelectItem>
                        <SelectItem value="an">/ an</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  {farmFuelSpendAnnual !== '' && farmFuelPeriod === 'mois' && (
                    <p className="text-xs text-muted-foreground">
                      ≈ {fmtNum(farmFuelSpendAnnual)} MAD / an
                    </p>
                  )}
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="gen-farm-static">
                    Niveau statique de l'eau (m) — optionnel
                  </Label>
                  <Input id="gen-farm-static" type="number" min="0" step="any"
                         placeholder="ex: 40" value={farmHmtStatic}
                         onChange={e => setFarmHmtStatic(e.target.value)} />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="gen-farm-drawdown">
                    Rabattement en pompage (m) — optionnel
                  </Label>
                  <Input id="gen-farm-drawdown" type="number" min="0" step="any"
                         placeholder="ex: 15" value={farmHmtDrawdown}
                         onChange={e => setFarmHmtDrawdown(e.target.value)} />
                </div>
              </div>

              {/* Readout FAO-56 : besoin estimé vs débit livré par la pompe.
                  Purement informatif (le backend recalcule le besoin lui-même). */}
              {farmWaterDemand && (
                pumpM3Day != null ? (
                  <div className={`mt-3 rounded-lg border p-3 text-sm ${
                    pumpM3Day >= farmWaterDemand.m3DayPeak
                      ? 'border-success/30 bg-success/10 text-success'
                      : 'border-warning/40 bg-warning/10 text-warning'
                  }`}>
                    Besoin estimé ≈ <strong>{fmtNum(farmWaterDemand.m3DayPeak)} m³/jour</strong>
                    {' '}(pointe estivale) — votre pompe livre{' '}
                    <strong>{fmtNum(pumpM3Day)} m³/jour</strong>{' '}
                    {pumpM3Day >= farmWaterDemand.m3DayPeak ? '✓' : '⚠ insuffisant'}
                  </div>
                ) : (
                  <div className="mt-3 rounded-lg border border-info/30 bg-info/10 p-3 text-sm text-info">
                    Besoin estimé ≈ <strong>{fmtNum(farmWaterDemand.m3DayPeak)} m³/jour</strong>
                    {' '}(pointe estivale). Renseignez HMT + débit souhaité pour comparer
                    au débit livré par la pompe.
                  </div>
                )
              )}
            </div>

            {/* ── Résultat du dimensionnement (source des chiffres du PDF) ── */}
            {pompageSel?.mode === 'courbe' && (
              <div className="mt-3 rounded-lg border border-info/30 bg-info/10 p-3 text-sm text-info">
                <strong>Pompe sélectionnée : {pompageSel.pump.nom}</strong>
                <div className="mt-1">
                  {pompageSel.cv} CV ({pompageSel.kw} kW) · débit à {pompeHmt} m
                  de HMT : <strong>{pompageSel.debitHmt} m³/h</strong>
                  {pompageSel.m3Jour != null && (
                    <> · <strong>≈ {pompageSel.m3Jour} m³/jour</strong> sur {pompeHeures} h
                    de pompage effectif</>
                  )}
                </div>
              </div>
            )}
            {pompageSel?.sansPrix?.length > 0 && (
              <div className="mt-3 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
                Seules des pompes <strong>sans prix renseigné</strong> conviennent à cette
                HMT et ce débit ({pompageSel.sansPrix.join(', ')}). Renseignez leur prix
                dans Stock pour les chiffrer — aucune pompe ne sera ajoutée au devis.
              </div>
            )}
          </CardContent>
        </Card>
        )}

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
            <div className="gen-slider-row">
              <span className="gen-slider-label">Consommation diurne (%)</span>
              <input type="range" min="10" max="100" step="5" value={dayUsage}
                     onChange={e => setDayUsage(e.target.value)} />
              <span className="gen-slider-value">{dayUsage}%</span>
            </div>
            <div className="mt-3 flex flex-wrap items-center justify-end gap-3">
              {errors.recalcDim && <span className="text-xs text-destructive">{errors.recalcDim}</span>}
              {errors.autofill && <span className="text-xs text-destructive">{errors.autofill}</span>}
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
                      loading={autoFillLoading} onClick={handleAutoFill}>
                <Zap /> Auto-remplir depuis le stock
              </Button>
            </div>
            {/* QJR36 — même patron que le refus serveur `sizingServeurMessage`
                ci-dessus : le dry-run serveur a échoué et l'écran a composé
                localement (composeLocalement) — comportement de repli
                INCHANGÉ, seule sa visibilité change (avant : console.error
                silencieux uniquement). */}
            {compositionSourceLocale && (
              <div className="mt-3 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning"
                   data-testid="composition-source-locale">
                Composition établie localement (serveur indisponible) — les
                quantités peuvent différer du devis serveur.
                {/* QJR99 — la CAUSE, NOMMÉE (`raisonRepli`, moitié pure de
                    `useComposition`) : une composition de secours ne s'affiche
                    plus sans dire pourquoi elle a remplacé celle du serveur. */}
                <div className="mt-1 text-xs" data-testid="composition-source-locale-raison">
                  {compositionSourceLocale}
                </div>
              </div>
            )}
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
            {modeInstallation === 'agricole' && pompageAutoFilled && pompageSel && (
              <div className="mt-3 rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-success">
                Auto-remplissage effectué —
                {pompageSel.m3Jour != null && (
                  <> <strong>≈ {pompageSel.m3Jour} m³/jour</strong> ·</>
                )}
                {' '}champ PV <strong>{pompageDims?.champKwc ?? pompageDims?.champKw} kWc</strong>
                {' '}({pompageDims?.nbPanneaux} panneaux).
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
                <CarteMetrique label="Taux d'autoconsommation"
                               value={`${etudeCI.taux_autoconso} %`}
                               unit="part de la production consommée" accent />
                {etudeCI.taux_couverture != null && (
                  <CarteMetrique label="Taux de couverture"
                                 value={`${etudeCI.taux_couverture} %`}
                                 unit="part de la conso couverte" accent />
                )}
                {/* QXMT — en MT sans tarif exploitable, `economies_annuelles`
                    vaut null : la carte est OMISE (jamais un « 0 » trompeur),
                    le motif est affiché juste en dessous. */}
                {etudeCI.economies_annuelles != null && (
                  <CarteMetrique label="Économies annuelles (étude)"
                                 value={fmtNum(etudeCI.economies_annuelles)}
                                 unit={etudeCI.tension_raccordement === 'mt'
                                   ? 'MAD / an · barème MT' : 'MAD / an'} />
                )}
                {etudeCI.payback != null && (
                  <CarteMetrique label="Payback (étude)"
                                 value={`${etudeCI.payback} ans`}
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
                      sinon repli sur `roi` (miroir local, inchangé). */}
                  <CarteMetrique label="Production annuelle"
                                 value={fmtNum(Math.round(apercuProductionKwh))}
                                 unit="kWh / an" accent />
                  {etudeHoraireSourceServeur && (
                    <>
                      <CarteMetrique label="Taux d'autoconsommation (sans)"
                                     value={`${formatNumber(etudeHoraireAnnuel.taux_autoconso_sans * 100, { decimals: 0 })} %`}
                                     unit="part de la production consommée" />
                      <CarteMetrique label="Taux de couverture (sans)"
                                     value={`${formatNumber(etudeHoraireAnnuel.couverture_sans * 100, { decimals: 0 })} %`}
                                     unit="part de la conso couverte" />
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
                      <CarteMetrique label="Économies"
                                     value={fmtNum(Math.round(apercuEcoSans))}
                                     unit="MAD / an"
                                     badge={apercuEstimationExemple ? 'estimation d\'exemple' : null} />
                      <CarteMetrique label="ROI"
                                     value={apercuPaybackSans != null ? apercuPaybackSans + ' ans' : 'N/A'}
                                     unit="retour sur invest." accent
                                     badge={apercuEstimationExemple ? 'estimation d\'exemple' : null} />
                      <CarteMetrique label="Coût"
                                     value={fmtNum(Math.round(totals.totalSans))}
                                     unit="MAD TTC" />
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
                                         value={fmtNum(Math.round(apercuEcoAvec))}
                                         unit="MAD / an"
                                         badge={apercuEstimationExemple ? 'estimation d\'exemple' : null} />
                          <CarteMetrique label="ROI"
                                         value={apercuPaybackAvec != null ? apercuPaybackAvec + ' ans' : 'N/A'}
                                         unit="retour sur invest." accent
                                         badge={apercuEstimationExemple ? 'estimation d\'exemple' : null} />
                          <CarteMetrique label="Coût"
                                         value={fmtNum(Math.round(totals.totalAvec))}
                                         unit="MAD TTC" />
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
            pk réel). Ne lit/n'écrit AUCUNE ligne du devis (rule #4, couche
            d'exploration séparée) ; `produits` réutilise le catalogue déjà
            chargé pour « Auto-remplir » (pas de second aller-retour réseau). */}
        <DevisOffresTailles devisId={editId} modeInstallation={modeInstallation} produits={produits} />

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
        <DevisPresetPanel devisId={editDevis?.id} onApplied={handlePresetApplied} />

        {/* ── Notes ── */}
        <Card>
          <GenCardHeader icon={StickyNote} title="Notes" />
          <CardContent className="pt-4">
            <Textarea rows={3} value={note}
                      onChange={e => setNote(e.target.value)}
                      placeholder="Conditions de paiement, remarques internes..." />
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
        {(errors.submit || errors.lines || errors.client || errors.conso) && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {errors.submit || errors.lines || errors.client || errors.conso}
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
            {modeInstallation === 'agricole' && pompageSel?.sansPrix?.length > 0 && (
              <div className="mt-3 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
                Attention : seules des pompes <strong>sans prix renseigné</strong> conviennent
                ({pompageSel.sansPrix.join(', ')}). Aucune pompe ne sera ajoutée au devis tant
                que leur prix n'est pas saisi dans Stock.
              </div>
            )}
            {superieurMsg && (
              <div className={`mt-3 rounded-lg border p-3 text-sm ${superieurMsg.ok
                ? 'border-success/30 bg-success/10 text-success'
                : 'border-destructive/30 bg-destructive/10 text-destructive'}`}>
                {superieurMsg.text}
              </div>
            )}
            {/* NTMFG18 — verdict de faisabilité atelier (non bloquant, ne
                masque jamais le formulaire). Silencieux si le devis n'a
                aucun produit fabriqué en interne (tenable === 'sans_gamme'). */}
            {faisabiliteResult && faisabiliteResult.tenable !== 'sans_gamme' && (
              <div className={`mt-3 rounded-lg border p-3 text-sm ${
                faisabiliteResult.tenable === 'tenable'
                  ? 'border-success/30 bg-success/10 text-success'
                  : faisabiliteResult.tenable === 'non_tenable'
                    ? 'border-destructive/30 bg-destructive/10 text-destructive'
                    : 'border-warning/40 bg-warning/10 text-warning'}`}>
                {faisabiliteResult.tenable === 'tenable' &&
                  'Faisabilité atelier : la charge additionnelle tient dans la capacité disponible.'}
                {faisabiliteResult.tenable === 'tenable_avec_retard' &&
                  `Faisabilité atelier : tenable avec un retard estimé de ${faisabiliteResult.retard_jours} `
                  + `jour(s) — poste goulot : ${faisabiliteResult.poste_goulot || '—'}.`}
                {faisabiliteResult.tenable === 'non_tenable' &&
                  `Faisabilité atelier : NON tenable sur le poste « ${faisabiliteResult.poste_goulot || '—'} ».`}
                {faisabiliteResult.tenable === 'erreur' &&
                  'Vérification de faisabilité atelier indisponible pour le moment.'}
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
              {/* NTMFG18 — faisabilité atelier (aucune écriture). */}
              <Button type="button" variant="outline" loading={faisabiliteBusy}
                      onClick={verifierFaisabiliteAtelier}
                      title="Simule la charge atelier additionnelle qu'induirait ce devis, sans rien enregistrer">
                Vérifier faisabilité atelier
              </Button>
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
              label="Total sans batterie · TTC"
              value={formatMoney(totals.totalSans)}
              hint={avecRec ? undefined : 'Option recommandée'}
            />
            <Stat
              tone={avecRec ? 'impact' : undefined}
              data-testid={avecRec ? 'gen-rail-total' : 'gen-rail-total-avec'}
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
