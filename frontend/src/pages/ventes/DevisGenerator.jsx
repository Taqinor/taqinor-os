import { Fragment, useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'
import { useDispatch } from 'react-redux'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import {
  ArrowLeft, Target, ClipboardList, User, Zap, Sprout, BarChart3,
  ShoppingCart, StickyNote, FileText, RotateCcw, Sun, Plus, Trash2,
  // EZ3 — actions du panneau de succès (envoyer / aperçu).
  Send, Eye,
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
import DevisLineRow from './DevisLineRow'
import { Combobox } from '../../ui/Combobox'
// APX17 — confirmation maison + toasts (jamais une popup du système).
import { useConfirmDialog, toast } from '../../ui/confirm'
// APX11 — en-tête unique VX28 + accent de module (identité Ventes).
import { PageHeader } from '../../ui/PageHeader'
import { VENTES_ACCENT_STYLE } from '../../features/ventes/accent'
import { searchCompanies } from '../../features/crm/companyLookup'
import {
  Button, IconButton, Card, CardContent,
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
  formatMoney, estimerMois, estimerPanneaux, computeROI, ttcFromHt, htFromTtc,
  tauxTvaOf,
  batteryKwhFromLines, comptePanneauxOption,
  optionTotalsTTC, autoFillLines, defaultProductLines,
  computeEtudeIndustrielle,
  autoFillPompage, pompageSelection, HEURES_POMPAGE_DEFAUT,
  isBattery, isHybridInverter, isReseauInverter, isPanel, isPompe,
  prixParKwc, discountForTarget,
  computeBuyCost, avecBatterieAvailability, KWH_PRICE, EFFICIENCY,
  panneauxPourKwc,
  TVA_STANDARD_DEFAUT, TVA_PANNEAUX_DEFAUT,
  kwhFromBill, buildEtudeParamsChoice, multiPropertyPreviewTTC,
  productibleForCity,
  COMMERCIAL_CATEGORIES, COMMERCIAL_CATEGORY_QUESTIONS, commercialDayShare,
  TARIF_MT_ONEE, tarifMtDisponible, tarifMtMoyen,
  // Règle fondateur du 18/08 — dimensionnement par PALIERS de 5 kWc, retenus
  // au payback le plus court (jamais un panneau/900 MAD nu).
  estimerKwcDepuisFacture, optimalKwcByPayback,
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
const SCENARIO_LES_DEUX = 'Les deux (Sans + Avec)'
const SCENARIO_SANS = 'Sans batterie'
const SCENARIO_AVEC = 'Avec batterie'
const SCENARIOS_VALIDES = [SCENARIO_LES_DEUX, SCENARIO_SANS, SCENARIO_AVEC]
// QX19 — scénario déjà CHOISI par le client dans le tunnel (crm.Lead.
// batterie_souhaitee) : même table de correspondance que le devis auto
// (features/ventes/autoQuote.js), jamais une seconde traduction divergente.
const BATTERIE_LEAD_VERS_SCENARIO = {
  sans: SCENARIO_SANS,
  avec: SCENARIO_AVEC,
  les_deux: SCENARIO_LES_DEUX,
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

// En-tête de carte du générateur (style design system, repose sur Card).
function GenCardHeader({ icon: Icon, title, children }) {
  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-3 sm:px-5">
      {Icon && <Icon className="size-4 text-primary" aria-hidden="true" />}
      <span className="font-display text-base font-semibold tracking-tight">{title}</span>
      {children && <div className="ml-auto flex items-center gap-2">{children}</div>}
    </div>
  )
}

function MetricCard({ label, value, unit, recommended, accent }) {
  return (
    <div className={`gen-metric${accent ? ' gen-metric-accent' : ''}${recommended ? ' gen-metric-rec' : ''}`}>
      <div className="gen-metric-label">
        {label}
        {recommended && <span className="gen-rec-badge">★ Recommandé</span>}
      </div>
      <div className="gen-metric-value">{value}</div>
      <div className="gen-metric-unit">{unit}</div>
    </div>
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
  // Mode choisi PAR L'UTILISATEUR : un lead sélectionné ensuite ne l'écrase
  // jamais (le pré-réglage depuis le lead ne joue que sur le défaut intact).
  const modeTouched = useRef(false)
  // Mêmes garde-fous « intact » pour les champs que applyLead peut pré-remplir :
  // dès que l'utilisateur y a touché, le lead ne les écrase plus.
  const structureTouched = useRef(false)
  const tensionTouched = useRef(false)
  const pompeAlimTouched = useRef(false)
  const nbPanneauxTouched = useRef(false)
  // ORDRE FONDATEUR (24/08) — le scénario par défaut est « Les deux (Sans +
  // Avec) » ; il ne cède qu'à un choix EXPLICITE (celui du commercial à
  // l'écran, ou celui déjà porté par le lead / le devis rouvert).
  const scenarioTouched = useRef(false)

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
  // Défaut fondateur : DEUX options (sans + avec batterie) sur tout devis vierge.
  const [scenario, setScenario] = useState(SCENARIO_LES_DEUX)
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
  const [nbPanneaux, setNbPanneaux] = useState('')
  // EZ5 — puissance cible saisie par l'utilisateur (kWc). Miroir bidirectionnel
  // de `nbPanneaux` ; jamais envoyée au serveur (le devis porte les lignes, pas
  // une puissance cible) — c'est un champ de SAISIE, pas un champ de données.
  const [kwcCible, setKwcCible] = useState('')
  const [panelW, setPanelW] = useState('710')
  const [structureType, setStructureType] = useState('acier')
  const [dayUsage, setDayUsage] = useState(DAY_USAGE_DEFAULTS['Résidentielle'])
  // Règle fondateur du 18/08 — justificatif du palier retenu (kWc, besoin lu
  // sur la facture, payback) quand le nombre de panneaux vient du nouveau
  // dimensionnement facture → paliers. Null = pas de justificatif à montrer
  // (taille posée à la main, ou sous le seuil de 900 MAD → repli historique).
  const [sizingInfo, setSizingInfo] = useState(null)
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

  // ── Multi-marchés ──
  const [modeInstallation, setModeInstallation] = useState('residentiel')
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
  const [tensionRaccordement, setTensionRaccordement] = useState('bt')
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
  // édité. kwhPrice/efficiency/panneauxParTranche alimentent les calculs ;
  // prixCibleDefaut pré-remplit le prix cible ; remiseMax = limite indicative.
  const [quoteLogic, setQuoteLogic] = useState({
    kwhPrice: KWH_PRICE, efficiency: EFFICIENCY, panneauxParTranche: 8,
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
  const [pompeAlim, setPompeAlim] = useState('tri')
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
    // sélectionné après restauration ne le réécrit pas.
    if (d.scenario != null) { scenarioTouched.current = true; setScenario(d.scenario) }
    if (d.recommendedChoice != null) setRecommendedChoice(d.recommendedChoice)
    if (d.note != null) setNote(d.note)
    if (d.fHiver != null) setFHiver(d.fHiver)
    if (d.fEte != null) setFEte(d.fEte)
    if (d.monthly != null) setMonthly(d.monthly)
    if (d.distributeur != null) setDistributeur(d.distributeur)
    if (d.realBillMode != null) setRealBillMode(d.realBillMode)
    if (d.realBillMad != null) setRealBillMad(d.realBillMad)
    if (d.realBillKwh != null) setRealBillKwh(d.realBillKwh)
    if (d.nbPanneaux != null) setNbPanneaux(d.nbPanneaux)
    if (d.panelW != null) setPanelW(d.panelW)
    if (d.structureType != null) setStructureType(d.structureType)
    if (d.dayUsage != null) setDayUsage(d.dayUsage)
    if (Array.isArray(d.lines)) { setLines(withKeys(d.lines)); linesInitialized.current = true }
    if (d.tauxTva != null) setTauxTva(d.tauxTva)
    if (d.discountPct != null) setDiscountPct(d.discountPct)
    if (d.multiMode != null) setMultiMode(d.multiMode)
    if (d.nombreProprietes != null) setNombreProprietes(d.nombreProprietes)
    if (Array.isArray(d.villaGroups)) setVillaGroups(d.villaGroups)
    if (d.modeInstallation != null) setModeInstallation(d.modeInstallation)
    if (d.consoMensuelle != null) setConsoMensuelle(d.consoMensuelle)
    if (d.categorieCommerciale != null) setCategorieCommerciale(d.categorieCommerciale)
    if (d.commercialAnswers && typeof d.commercialAnswers === 'object') setCommercialAnswers(d.commercialAnswers)
    if (d.injectionEnabled != null) setInjectionEnabled(d.injectionEnabled)
    if (d.tensionRaccordement != null) setTensionRaccordement(d.tensionRaccordement)
    if (d.repartitionMt && typeof d.repartitionMt === 'object') setRepartitionMt(d.repartitionMt)
    if (d.prixCible != null) setPrixCible(d.prixCible)
    if (d.remiseMax != null) setRemiseMax(d.remiseMax)
    if (d.accessoiresOnly != null) setAccessoiresOnly(d.accessoiresOnly)
    if (d.pompeCv != null) setPompeCv(d.pompeCv)
    if (d.pompeType != null) setPompeType(d.pompeType)
    if (d.pompeAlim != null) setPompeAlim(d.pompeAlim)
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
  const onKwcCibleChange = (v) => {
    setKwcCible(v)
    const n = panneauxPourKwc(v, panelW)
    if (n > 0) {
      nbPanneauxTouched.current = true
      setNbPanneaux(String(n))
      // Taille posée à la main : le justificatif « palier retenu » de
      // l'auto-dimensionnement ne s'applique plus à cette valeur.
      setSizingInfo(null)
    }
  }
  const onNbPanneauxChange = (v) => {
    nbPanneauxTouched.current = true
    setNbPanneaux(v)
    const puissance = (parseFloat(v) || 0) * (parseFloat(panelW) || 0) / 1000
    setKwcCible(puissance > 0 ? String(Math.round(puissance * 100) / 100) : '')
    setSizingInfo(null)
  }
  // Le nombre de panneaux peut aussi être posé SANS passer par le champ
  // (pré-remplissage depuis un lead, dimensionnement pompage, reprise de
  // brouillon) : on renseigne alors la cible si elle est encore vide — jamais
  // par-dessus une valeur tapée par l'utilisateur.
  useEffect(() => {
    if (kwcCible !== '' || kwp <= 0) return
    // eslint-disable-next-line react-hooks/set-state-in-effect -- miroir d'un champ posé ailleurs
    setKwcCible(String(Math.round(kwp * 100) / 100))
  }, [kwp, kwcCible])

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
  const {
    donnees: etudeHoraireDonnees,
    chargement: etudeHoraireChargement,
    erreur: etudeHoraireErreur,
  } = useEtudeHorairePreview(etudeHoraireCorps)
  const { donnees: etudeHoraireDonneesAvec } =
    useEtudeHorairePreview(etudeHoraireCorpsAvec)
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
  // chemin où l'utilisateur choisit lui-même un marché). `onModeChange` reste
  // SYNCHRONE : les trois appels programmatiques (préremplissage lead/payload,
  // rechargement d'un brouillon) doivent poser leur état dans le même tour —
  // le rendre asynchrone ferait écraser `scenario` chargé par le défaut du
  // mode.
  const onModeChange = (m) => {
    if (m === modeInstallation) return
    setModeInstallation(m)
    if (m === 'industriel') {
      onInstTypeChange('Industrielle')
      // Défaut industriel : sans batterie, réseau. L'auto-remplissage de ces
      // deux marchés MET À ZÉRO batterie + onduleur hybride (voir
      // `handleAutoFill`) et l'écran annonce un « document à option unique » :
      // le double scénario n'y est donc PAS servable, l'ordre fondateur des
      // deux options par défaut ne s'y applique pas.
      setScenario(SCENARIO_SANS)
    } else if (m === 'commercial') {
      // QX43 — commercial : comme l'industriel, autoconsommation réseau sans
      // batterie par défaut (l'étude par catégorie arrive avec QX44).
      onInstTypeChange('Commerciale')
      setScenario(SCENARIO_SANS)
    } else if (m === 'agricole') {
      // Pompage : ni batterie ni onduleur (règle du repo) — le scénario n'est
      // pas touché, aucune option batterie n'est composée de toute façon.
      onInstTypeChange('Agricole')
    } else {
      onInstTypeChange('Résidentielle')
      setScenario(SCENARIO_LES_DEUX)
    }
  }

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
    onModeChange(m)
  }

  // ── Scénario / recommandation : réinitialisation si incompatible ──
  const onScenarioChange = (v) => {
    // « sauf si le commercial le précise » : dès qu'il choisit lui-même, aucun
    // pré-remplissage (lead, profil site) ne réécrit son scénario.
    scenarioTouched.current = true
    setScenario(v)
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
  // les appelants gardent alors le repli historique `estimerPanneaux`).
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
    // PVMRQ — la marque épinglée entre dans la clé de cache : un changement de
    // réglage (ou de gamme du devis) doit rejouer le balayage des paliers.
    const key = [hiver, eteEff, besoinKwc, dayUsagePct, panelW, structureType,
      discountPct, produits.length, JSON.stringify(marquesActives)].join('|')
    if (sizingCacheRef.current.key === key) return sizingCacheRef.current.result
    const factures = estimerMois(hiver, eteEff)
    const opt = optimalKwcByPayback({
      produits, factures, dayUsagePct,
      panelW, structureType, discountPct,
      kwhPrice: quoteLogic.kwhPrice, efficiency: quoteLogic.efficiency,
      besoinKwc, marques: marquesActives,
    })
    // L-2OPT (fondateur 24/08) — second optimiseur, MÊME balayage, objectif
    // AVEC batterie (`avecBatterie: true` — optimalKwcByPayback l'accepte
    // déjà, jamais utilisé jusqu'ici) : la taille optimale « avec » peut
    // différer de la taille optimale « sans » (le coût batterie déplace le
    // point de payback minimal). Exposé en `.avec`, JAMAIS à la place du
    // résultat plat ci-dessous (`sizing.nbPanneaux` reste le SANS — contrat
    // gardé par DevisGeneratorNbPanneauxTouched.test.mjs).
    const optAvec = optimalKwcByPayback({
      produits, factures, dayUsagePct,
      panelW, structureType, discountPct,
      kwhPrice: quoteLogic.kwhPrice, efficiency: quoteLogic.efficiency,
      besoinKwc, marques: marquesActives, avecBatterie: true,
    })
    let result = null
    if (opt.nbPanneaux > 0) {
      const sansPart = { besoinKwc, ...opt }
      // Jamais de chiffre inventé (règle #4) : sans optimum AVEC exploitable,
      // il retombe sur le SANS — aucune divergence fabriquée entre les deux
      // branches.
      const avecPart = (optAvec.nbPanneaux > 0) ? { besoinKwc, ...optAvec } : sansPart
      result = { ...sansPart, avec: avecPart }
    }
    sizingCacheRef.current = { key, result }
    return result
  }, [modeInstallation, panelW, structureType, discountPct, produits, quoteLogic, marquesActives])

  // L-2OPT — kWc de la branche AVEC batterie POUR LA COMPOSITION EN COURS :
  // le moteur horaire serveur (recommandation_avec, source de vérité) prime
  // dès qu'il a répondu pour ce contexte ; repli local (même balayage
  // payback que ci-dessus, objectif avecBatterie) ; repli ultime kwc_sans —
  // jamais un chiffre inventé (règle #4). Un nombre de panneaux TAPÉ À LA
  // MAIN (nbPanneauxTouched, même garde-fou que partout ailleurs sur ce
  // champ) vaut pour les DEUX branches : aucune divergence n'est recomposée
  // par-dessus un choix déjà fait par l'utilisateur.
  const resolveKwcAvec = () => {
    if (nbPanneauxTouched.current) return kwp
    const backendAvec = etudeHoraireDonnees?.dimensionnement?.recommandation_avec
    if (Number(backendAvec?.kwc) > 0) return Number(backendAvec.kwc)
    const sizing = computeAutoSizing(fHiver, fEte)
    if (sizing?.avec?.kwcOptimal > 0) return sizing.avec.kwcOptimal
    return kwp
  }

  const applyLead = (id) => {
    setLeadId(id)
    if (!id) return
    setClientId('') // le client est résolu côté serveur depuis le lead
    const lead = leads.find(l => String(l.id) === String(id))
    if (!lead) return
    // Pré-réglage du mode depuis le lead UNIQUEMENT si l'utilisateur n'a pas
    // déjà choisi un mode lui-même — son choix ne se réinitialise JAMAIS.
    const modeLead = !modeTouched.current && lead.type_installation
      ? LEAD_TYPE_TO_MODE[lead.type_installation] : null
    if (modeLead) onModeChange(modeLead)
    // Mode RÉELLEMENT visé par ce pré-remplissage : `modeInstallation` est
    // encore la valeur du rendu courant après `onModeChange` (setState ne
    // rafraîchit pas la constante fermée).
    const modeCible = modeLead || modeInstallation
    // ORDRE FONDATEUR (24/08) — le scénario du lead est un choix DÉJÀ FAIT
    // (tunnel : batterie_souhaitee) : il l'emporte sur le défaut du mode, dans
    // les deux sens (« sans » restreint, « les deux » rouvre un mode qui
    // partait mono). Rien de renseigné → le défaut du mode reste, exactement
    // comme le devis auto (autoQuote.js, QX19). Posé APRÈS `onModeChange`
    // ci-dessus, qui repose justement ce défaut. JAMAIS en pompage : un devis
    // agricole ne porte ni batterie ni onduleur, quoi qu'ait coché le lead.
    // L-2OPT — scénario RÉELLEMENT visé après cette ligne (setScenario est
    // asynchrone) : sert au choix sans/avec de computeAutoSizing ci-dessous,
    // même patron que `modeCible` juste au-dessus.
    let scenarioCible = scenario
    if (!scenarioTouched.current && modeCible !== 'agricole') {
      const scenarioLead = BATTERIE_LEAD_VERS_SCENARIO[String(lead.batterie_souhaitee ?? '')]
      if (scenarioLead) { setScenario(scenarioLead); scenarioCible = scenarioLead }
    }
    // Structure préférée du lead (acier/aluminium) si non touchée par l'utilisateur.
    if (!structureTouched.current
        && (lead.structure_pref === 'acier' || lead.structure_pref === 'aluminium')) {
      setStructureType(lead.structure_pref)
    }
    // QXMT — le tunnel web pose déjà la tension de raccordement (BT/MT) au
    // client pro : on la reprend telle quelle plutôt que de la redemander,
    // tant que le vendeur n'a pas fixé lui-même le sélecteur.
    if (!tensionTouched.current) {
      const tensionLead = String(
        lead.web_questionnaire?.tension_raccordement ?? '').toLowerCase()
      if (tensionLead === 'bt' || tensionLead === 'mt') setTensionRaccordement(tensionLead)
    }
    // Lead agricole : recopie pompe CV / HMT / débit ; l'alimentation suit le
    // raccordement (monophase→mono / triphase→tri) tant qu'elle est intacte.
    if (LEAD_TYPE_TO_MODE[lead.type_installation] === 'agricole') {
      if (lead.pompe_cv != null && lead.pompe_cv !== '') setPompeCv(String(lead.pompe_cv))
      if (lead.pompe_hmt_m != null && lead.pompe_hmt_m !== '') setPompeHmt(String(lead.pompe_hmt_m))
      if (lead.pompe_debit_m3h != null && lead.pompe_debit_m3h !== '') setPompeDebit(String(lead.pompe_debit_m3h))
      if (!pompeAlimTouched.current) {
        if (lead.raccordement === 'monophase') setPompeAlim('mono')
        else if (lead.raccordement === 'triphase') setPompeAlim('tri')
      }
    }
    if (lead.conso_mensuelle_kwh) setConsoMensuelle(String(lead.conso_mensuelle_kwh))
    // Taille souhaitée (kWc) du lead → nb de panneaux, prioritaire sur
    // l'estimation par facture, tant que le champ n'a pas été touché.
    const tailleKwc = parseFloat(lead.taille_souhaitee_kwc) || 0
    const fromTaille = (!nbPanneauxTouched.current && tailleKwc > 0)
      ? panneauxPourKwc(tailleKwc, panelW)
      : 0
    if (fromTaille > 0) setNbPanneaux(String(fromTaille))
    const hiver = parseFloat(lead.facture_hiver) || 0
    if (hiver > 0) {
      // bascule OFF → la valeur unique vaut hiver ET été
      const ete = (lead.ete_differente && lead.facture_ete)
        ? parseFloat(lead.facture_ete) : hiver
      setFHiver(String(lead.facture_hiver))
      setFEte(lead.ete_differente && lead.facture_ete ? String(lead.facture_ete) : '')
      // L'estimation par facture ne s'applique que si la taille souhaitée n'a
      // pas déjà fourni un nombre de panneaux (taille prioritaire). Règle
      // fondateur du 18/08 — dimensionnement par paliers de 5 kWc au payback
      // le plus court ; sous le seuil de 900 MAD, repli sur `estimerPanneaux`.
      if (fromTaille <= 0) {
        const sizing = computeAutoSizing(hiver, ete)
        if (sizing) {
          // L-2OPT — un scénario mono « Avec batterie » compose l'optimum
          // AVEC seul (payback minimal AVEC batterie), pas l'optimum SANS.
          const retenu = (modeCible === 'residentiel' && scenarioCible === SCENARIO_AVEC)
            ? sizing.avec : sizing
          setNbPanneaux(String(retenu.nbPanneaux))
          setSizingInfo(retenu)
        } else {
          const suggested = estimerPanneaux(hiver, quoteLogic.panneauxParTranche)
          if (suggested > 0) setNbPanneaux(String(suggested))
          setSizingInfo(null)
        }
      }
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
    if (!modeTouched.current
        && p.type_installation && LEAD_TYPE_TO_MODE[p.type_installation]) {
      onModeChange(LEAD_TYPE_TO_MODE[p.type_installation])
    }
    if (LEAD_TYPE_TO_MODE[p.type_installation] === 'agricole') {
      if (p.pompe_cv != null && p.pompe_cv !== '') setPompeCv(String(p.pompe_cv))
      if (p.pompe_hmt_m != null && p.pompe_hmt_m !== '') setPompeHmt(String(p.pompe_hmt_m))
      if (p.pompe_debit_m3h != null && p.pompe_debit_m3h !== '') setPompeDebit(String(p.pompe_debit_m3h))
      if (!pompeAlimTouched.current) {
        if (p.raccordement === 'monophase') setPompeAlim('mono')
        else if (p.raccordement === 'triphase') setPompeAlim('tri')
      }
    }
    if (p.conso_mensuelle_kwh) setConsoMensuelle(String(p.conso_mensuelle_kwh))
    const hiver = parseFloat(p.facture_hiver) || 0
    if (hiver > 0) {
      const ete = (p.ete_differente && p.facture_ete) ? parseFloat(p.facture_ete) : hiver
      setFHiver(String(p.facture_hiver))
      setFEte(p.ete_differente && p.facture_ete ? String(p.facture_ete) : '')
      // Règle fondateur du 18/08 — même chaîne palier/payback que applyLead
      // (voir computeAutoSizing) ; repli sur estimerPanneaux sous le seuil.
      if (!nbPanneauxTouched.current) {
        const sizing = computeAutoSizing(hiver, ete)
        if (sizing) {
          // L-2OPT — même choix sans/avec qu'applyLead (le mode a déjà pu
          // être posé par onModeChange juste au-dessus).
          const retenu = (modeInstallation === 'residentiel' && scenario === SCENARIO_AVEC)
            ? sizing.avec : sizing
          setNbPanneaux(String(retenu.nbPanneaux))
          setSizingInfo(retenu)
        } else {
          const suggested = estimerPanneaux(hiver, quoteLogic.panneauxParTranche)
          if (suggested > 0) setNbPanneaux(String(suggested))
          setSizingInfo(null)
        }
      }
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
      if (d.mode_installation) {
        modeTouched.current = true
        onModeChange(d.mode_installation)
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
        }))
      setLines(withKeys(rows))
      linesInitialized.current = true
      // L-2OPT — le nombre de panneaux affiché reste celui de la branche
      // SANS (commun + 'sans' ; une ligne 'avec' divergente ne compte pas
      // ici, sinon les deux optima s'additionneraient).
      const panneaux = rows
        .filter(r => /panneau/i.test(r.designation) && r.variante !== 'avec')
        .reduce((s, r) => s + (parseFloat(r.quantite) || 0), 0)
      if (panneaux > 0) setNbPanneaux(String(panneaux))
      const e = d.etude_params || {}
      // PVMRQ — round-trip de la gamme du devis (`etude_params.gamme.nom`,
      // posée par `services.creer_variante_gamme`/`gamme_nom`) : résout la
      // carte de marques Essentielle/Premium à réappliquer aux
      // auto-remplissages suivants de CE devis (voir `marquesActives`).
      if (e.gamme && typeof e.gamme === 'object' && e.gamme.nom) {
        setGammeNomDevis(String(e.gamme.nom))
      }
      // ORDRE FONDATEUR (24/08) — round-trip du SCÉNARIO déjà choisi sur ce
      // devis (etude_params.scenario/recommended_choice, posés par
      // `buildEtudeParamsChoice` à l'enregistrement). Sans lui, rouvrir un
      // brouillon reposait le défaut du MODE (`onModeChange` ci-dessus) et
      // l'enregistrement suivant ÉCRASAIT silencieusement le choix du client —
      // un devis « Avec batterie » repartait « Les deux », un devis
      // industriel « Les deux » repartait « Sans batterie ». Le défaut ne vaut
      // que pour un devis VIERGE. Valeurs inconnues ignorées : le Select ne
      // doit jamais afficher un scénario hors contrat du moteur PDF.
      if (SCENARIOS_VALIDES.includes(e.scenario)) {
        scenarioTouched.current = true
        setScenario(e.scenario)
      }
      if (['Auto', 'Aucune recommandation', SCENARIO_SANS, SCENARIO_AVEC]
        .includes(e.recommended_choice)) {
        setRecommendedChoice(e.recommended_choice)
      }
      // QX50 — round-trip de l'injection 82-21 (flag activé si l'étude la porte).
      if (e.injection_82_21 || e.injection_dh_an != null) setInjectionEnabled(true)
      // QXMT — round-trip du raccordement MT + de la répartition horaire, pour
      // qu'un devis MT rouvert recalcule au MÊME barème (jamais un retour BT
      // silencieux). Les clés absentes laissent le défaut 'bt' intact.
      if (e.tension_raccordement === 'mt') setTensionRaccordement('mt')
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
      const perTr = parseInt(data?.panneaux_par_900mad, 10)
      const tvaStd = parseFloat(data?.tva_standard)
      const tvaPan = parseFloat(data?.tva_panneaux)
      setQuoteLogic({
        kwhPrice: (Number.isFinite(kwh) && kwh > 0) ? kwh : KWH_PRICE,
        efficiency: (Number.isFinite(rend) && rend > 0) ? rend : EFFICIENCY,
        panneauxParTranche: (Number.isFinite(perTr) && perTr > 0) ? perTr : 8,
        tvaStandard: (Number.isFinite(tvaStd) && tvaStd > 0) ? tvaStd : TVA_STANDARD_DEFAUT,
        tvaPanneaux: (Number.isFinite(tvaPan) && tvaPan > 0) ? tvaPan : TVA_PANNEAUX_DEFAUT,
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
  // chaque frappe sur le champ facture) ; repli sur estimerPanneaux sous le
  // seuil de 900 MAD.
  const syncBillEstimator = (hiverVal, eteVal) => {
    const hiver = parseFloat(hiverVal) || 0
    const ete = parseFloat(eteVal) || 0
    if (hiver <= 0) return
    // N3 — un nombre de panneaux TAPÉ À LA MAIN (nbPanneauxTouched, le MÊME
    // garde-fou « intact » qu'applyLead/applySiteProfile ci-dessus) n'est plus
    // jamais re-forcé par le redimensionnement automatique déclenché par la
    // frappe sur les factures : il ne se resynchronise qu'via une recomposition
    // EXPLICITE (« Auto-remplir », ou en retouchant nbPanneaux/kwcCible
    // eux-mêmes). Les factures (monthly), elles, restent toujours à jour.
    if (!nbPanneauxTouched.current) {
      const sizing = computeAutoSizing(hiver, ete)
      if (sizing) {
        // L-2OPT — un scénario mono « Avec batterie » compose l'optimum
        // AVEC seul (même choix qu'applyLead/applySiteProfile ci-dessus).
        if (modeInstallation === 'residentiel' && scenario === SCENARIO_AVEC) {
          setNbPanneaux(String(sizing.avec.nbPanneaux))
          setSizingInfo(sizing.avec)
        } else {
          setNbPanneaux(String(sizing.nbPanneaux))
          setSizingInfo(sizing)
        }
      } else {
        const suggested = estimerPanneaux(hiver)
        if (suggested > 0) setNbPanneaux(String(suggested))
        setSizingInfo(null)
      }
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

  const handleAutoFill = () => {
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
      if (pompageSel) setNbPanneaux(String(pompageSel.dims.nbPanneaux))
      setPompageAutoFilled(true)
      return
    }
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
  }

  // CJ2b — bouton « Appliquer cette taille » d'une ligne du tableau de
  // dimensionnement (moteur horaire serveur) : pose `nbPanneaux`/`panelW`
  // depuis la ligne choisie puis relance EXACTEMENT le même chemin de
  // composition que le bouton « Auto-remplir » (`handleAutoFill`) — jamais
  // une seconde règle de composition. `setState` est asynchrone : on ne peut
  // pas appeler `handleAutoFill()` dans la même passe (il lirait encore
  // l'ancien `nbPanneaux`/`panelW` par fermeture) — un drapeau + un effet
  // déclenchent l'auto-remplissage une fois les deux champs à jour.
  const appliquerTaillePending = useRef(false)
  const appliquerTailleDimensionnement = (ligne) => {
    if (!ligne || !(ligne.panneaux > 0)) return
    nbPanneauxTouched.current = true
    setSizingInfo(null)
    setKwcCible(ligne.kwc != null ? String(ligne.kwc) : '')
    if (ligne.panel_watt) setPanelW(String(ligne.panel_watt))
    setNbPanneaux(String(ligne.panneaux))
    appliquerTaillePending.current = true
  }
  useEffect(() => {
    if (!appliquerTaillePending.current) return
    appliquerTaillePending.current = false
    handleAutoFill()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ne réagit qu'au drapeau « Appliquer cette taille », pas à chaque frappe de nbPanneaux/panelW
  }, [nbPanneaux, panelW])

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

  // Cœur de persistance extrait de `handleSubmit` (aucun changement de
  // comportement) : construit etudeParams/payload/lignes, écrit le devis
  // (édition atomique ou création atomique), et RENVOIE {devisId, devisCree}
  // en cas de succès — null sinon (le message HUMAIN est déjà posé dans
  // `errors.submit`). PV23bis (fondateur 20/08) — `ouvrirConception3D`
  // ci-dessous réutilise EXACTEMENT ce même chemin d'écriture pour le bouton
  // « Concevoir en 3D » : un seul endroit qui sait enregistrer un devis,
  // jamais une seconde logique dupliquée.
  const persisterDevis = async () => {
    setSaving(true)
    try {
      // Paramètres d'étude stockés avec le devis (alimentent la page Étude
      // du PDF et le bloc résumé pompage)
      let etudeParams = null
      if (modeInstallation === 'industriel' && etudeIndustrielle) {
        etudeParams = etudeIndustrielle
      } else if (modeInstallation === 'commercial') {
        // QX44 — étude commerciale (si conso saisie) + catégorie + réponses par
        // catégorie (clés snake_case, coercition de type ; jamais de prix_achat).
        const answers = {}
        for (const q of (COMMERCIAL_CATEGORY_QUESTIONS[categorieCommerciale] || [])) {
          const raw = commercialAnswers[q.key]
          if (raw === undefined || raw === '' || raw === null) continue
          answers[q.key] = q.type === 'number'
            ? (parseFloat(raw) || 0)
            : q.type === 'bool' ? !!raw : String(raw)
        }
        etudeParams = {
          ...(etudeCommerciale || {}),
          categorie_commerciale: categorieCommerciale,
          ...answers,
        }
      } else if (modeInstallation === 'agricole' && pompageSel) {
        etudeParams = buildEtudePompage(pompageSel, {
          typePompe: pompeType, alim: pompeAlim,
          hmt: pompeHmt, debit: pompeDebit, heures: pompeHeures,
          profondeur: pompeProfondeur, distance: pompeDistance,
        })
        // Données d'exploitation guidées (clés exactes lues par le backend pour
        // redimensionner/chiffrer le PDF). Optionnelles : numériques null si vides.
        etudeParams = {
          ...etudeParams,
          region: farmRegion,
          crop: farmCrop,
          surface_ha: parseFloat(farmSurfaceHa) || null,
          irrigation_method: farmIrrigation,
          current_fuel: farmFuel,
          fuel_spend_current: farmFuelSpendAnnual !== '' ? farmFuelSpendAnnual : null,
          hmt_static: parseFloat(farmHmtStatic) || null,
          hmt_drawdown: parseFloat(farmHmtDrawdown) || null,
        }
      }
      // N1 — sème les 12 factures RÉELLES du client (etude_params.
      // factures_mensuelles_reelles) depuis la saisie hiver/été OU le détail
      // mensuel de CE devis, quand elle a RÉELLEMENT été faite
      // (facturesSaisies — jamais les valeurs D'EXEMPLE de
      // DEFAULT_MONTHLY_BILLS). Un devis créé à la main (sans passer par le
      // devis auto d'un lead) n'avait AUCUN moyen d'alimenter ce champ : sans
      // lui, le moteur PDF ne peut plus reconstruire la facture « avant »
      // (page 1 économies). Même patron que le devis auto (autoQuote.js,
      // bloc PACT10/QF-REAL) : kwhFromBill au barème réel du distributeur
      // choisi, jamais un chiffre supposé. Rien saisi → aucun changement de
      // payload (etudeParams reste exactement ce qu'il était).
      if (facturesSaisies) {
        const facturesReelles = monthly.map(v => parseFloat(v) || 0)
        etudeParams = {
          ...(etudeParams || {}),
          factures_mensuelles_reelles: facturesReelles,
        }
        // conso_annuelle dérivée UNIQUEMENT si aucune source plus directe ne
        // l'a déjà posée (« Facture réelle du client » QF4/QF5 ci-dessous via
        // buildEtudeParamsChoice, ou l'étude industrielle/agricole
        // ci-dessus) — buildEtudeParamsChoice garde alors ce chiffre intact.
        if (etudeParams.conso_annuelle == null) {
          const consoDeriveeFactures = Math.round(facturesReelles.reduce(
            (somme, bill) => somme + (kwhFromBill(bill, distributeur).kwhMensuel || 0), 0))
          if (consoDeriveeFactures > 0) etudeParams.conso_annuelle = consoDeriveeFactures
        }
      }
      // QF7 — persiste le scénario + l'option recommandée affichés à l'écran
      // pour TOUS les modes (résidentiel/industriel/agricole), pas seulement
      // quand une étude existe déjà : sans cette garantie un devis industriel
      // sans étude dégénérée (kwp=0, ex. lignes ajoutées à la main) perdait
      // silencieusement le choix sans/avec fait à l'écran. Le PDF (QF6) doit
      // pouvoir mettre en avant EXACTEMENT la même option (« Auto » résolu →
      // l'option du scénario) quel que soit le mode. QF4 — le distributeur +
      // la consommation annuelle RÉELLE (facture/kWh du client) sont fusionnés
      // dans le même appel (jamais deux logiques de fusion divergentes).
      etudeParams = buildEtudeParamsChoice(etudeParams, {
        scenario, recommendedChoice, recommendedOption: recommended,
        distributeur, consoAnnuelleReelle,
      })
      // QJ31 (mode A) — ×N villas identiques : multiplicateur stocké dans
      // etude_params (lu par le backend QJ29). N=1/absent = mono-système.
      if (multiMode === 'multiplier') {
        const n = parseInt(nombreProprietes, 10)
        if (Number.isFinite(n) && n > 1) etudeParams = { ...etudeParams, nombre_proprietes: n }
      }
      const payload = {
        statut: 'brouillon',
        date_validite: dateValidite || null,
        taux_tva: tauxTva,
        remise_globale: discountPct || '0',
        note: note || null,
        mode_installation: modeInstallation,
        etude_params: etudeParams,
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
    || (avgBill > 0 ? Math.round(avgBill / quoteLogic.kwhPrice) : 0)

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
              onChange={(v) => { modeTouched.current = true; onModeChangeUi(v) }}
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
                <span>
                  {selectedLead?.roof_point
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
                    onChange={(v) => { tensionTouched.current = true; setTensionRaccordement(v) }}
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
                  onChange={(v) => { pompeAlimTouched.current = true; setPompeAlim(v) }}
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
                       value={panelW} onChange={e => setPanelW(e.target.value)} />
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
                  onChange={(v) => { structureTouched.current = true; setStructureType(v) }}
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
            <div className="gen-slider-row">
              <span className="gen-slider-label">Consommation diurne (%)</span>
              <input type="range" min="10" max="100" step="5" value={dayUsage}
                     onChange={e => setDayUsage(e.target.value)} />
              <span className="gen-slider-value">{dayUsage}%</span>
            </div>
            <div className="mt-3 flex flex-wrap items-center justify-end gap-3">
              {errors.autofill && <span className="text-xs text-destructive">{errors.autofill}</span>}
              {errors.autofillKwc && <span className="text-xs text-warning">{errors.autofillKwc}</span>}
              {/* PVMRQ — même patron visuel que `errors.autofill` ci-dessus. */}
              {errors.marquesManquantes && <span className="text-xs text-destructive">{errors.marquesManquantes}</span>}
              <Button type="button" className="bg-brass-400 text-nuit hover:bg-brass-500" onClick={handleAutoFill}>
                <Zap /> Auto-remplir depuis le stock
              </Button>
            </div>
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
                <MetricCard label="Taux d'autoconsommation"
                            value={`${etudeCI.taux_autoconso} %`}
                            unit="part de la production consommée" accent />
                {etudeCI.taux_couverture != null && (
                  <MetricCard label="Taux de couverture"
                              value={`${etudeCI.taux_couverture} %`}
                              unit="part de la conso couverte" accent />
                )}
                {/* QXMT — en MT sans tarif exploitable, `economies_annuelles`
                    vaut null : la carte est OMISE (jamais un « 0 » trompeur),
                    le motif est affiché juste en dessous. */}
                {etudeCI.economies_annuelles != null && (
                  <MetricCard label="Économies annuelles (étude)"
                              value={fmtNum(etudeCI.economies_annuelles)}
                              unit={etudeCI.tension_raccordement === 'mt'
                                ? 'MAD / an · barème MT' : 'MAD / an'} />
                )}
                {etudeCI.payback != null && (
                  <MetricCard label="Payback (étude)"
                              value={`${etudeCI.payback} ans`}
                              unit="retour sur invest." />
                )}
              </div>
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
                  <MetricCard label="Production annuelle"
                              value={fmtNum(Math.round(apercuProductionKwh))}
                              unit="kWh / an" accent />
                  {etudeHoraireSourceServeur && (
                    <>
                      <MetricCard label="Taux d'autoconsommation (sans)"
                                  value={`${formatNumber(etudeHoraireAnnuel.taux_autoconso_sans * 100, { decimals: 0 })} %`}
                                  unit="part de la production consommée" />
                      <MetricCard label="Taux de couverture (sans)"
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
                      <MetricCard label="Économies"
                                  value={fmtNum(Math.round(apercuEcoSans))}
                                  unit="MAD / an" />
                      <MetricCard label="ROI"
                                  value={apercuPaybackSans != null ? apercuPaybackSans + ' ans' : 'N/A'}
                                  unit="retour sur invest." accent />
                      <MetricCard label="Coût"
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
                          <MetricCard label="Économies"
                                      value={fmtNum(Math.round(apercuEcoAvec))}
                                      unit="MAD / an" />
                          <MetricCard label="ROI"
                                      value={apercuPaybackAvec != null ? apercuPaybackAvec + ' ans' : 'N/A'}
                                      unit="retour sur invest." accent />
                          <MetricCard label="Coût"
                                      value={fmtNum(Math.round(totals.totalAvec))}
                                      unit="MAD TTC" />
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

        {/* ── Lignes de produits ── */}
        <Card>
          <GenCardHeader icon={ShoppingCart} title="Lignes de Produits">
            {/* XSAL14 — section (intertitre) / note (texte) : structurent le
                devis sans prix, exclues de tous les totaux. */}
            <Button type="button" size="sm" variant="ghost"
                    onClick={() => addStructureLine('section')}
                    title="Ajouter un intertitre de section (sans prix)">
              + Section
            </Button>
            <Button type="button" size="sm" variant="ghost"
                    onClick={() => addStructureLine('note')}
                    title="Ajouter une note (texte sans prix)">
              + Note
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={addLine}>
              <Plus /> Ajouter ligne
            </Button>
            {/* PVORD (fondateur 19/08/2026) — persiste l'ordre ÉCRAN courant
                comme nouvel ordre par défaut des PROCHAINS devis
                (ParametresGammes.ordre_lignes). Réservé Admin/Responsable
                côté serveur (même garde que Paramètres → Gammes & marques) ;
                un rôle non autorisé reçoit un toast d'erreur, pas un crash. */}
            <Button type="button" size="sm" variant="ghost"
                    loading={savingOrdreLignes}
                    onClick={handleSaveOrdreLignes}
                    title="Enregistre l'ordre actuel des lignes comme ordre par défaut pour les prochains devis">
              Enregistrer cet ordre comme ordre par défaut
            </Button>
          </GenCardHeader>
          <CardContent className="px-0 pt-0">
            {/* ── QJ31 — Multi-propriétés (un seul devis) ──
                VX138(e) — accordéon : repliée PAR DÉFAUT en agricole (non
                pertinent pour ce mode) mais jamais masquée ; l'utilisateur
                peut toujours la rouvrir librement. */}
            <details className="mx-4 mt-4 rounded-lg border border-border bg-muted/30 sm:mx-5"
                      open={multiAccordionOpen}
                      onToggle={e => setMultiAccordionOpen(e.currentTarget.open)}>
              <summary className="cursor-pointer select-none px-3 py-3 font-display text-sm font-semibold tracking-tight sm:px-4">
                Plusieurs propriétés ?
                {multiMode !== 'none' && (
                  <span className="ml-2 text-xs font-normal text-muted-foreground">
                    ({multiMode === 'multiplier' ? '× N identiques' : '+ Villas différentes'})
                  </span>
                )}
              </summary>
              <div className="border-t border-border p-3 sm:p-4">
              <div className="flex flex-wrap items-center gap-3">
                <Segmented
                  className="flex-wrap"
                  options={[
                    { value: 'none', label: 'Une seule' },
                    { value: 'multiplier', label: '× N identiques' },
                    { value: 'villas', label: '+ Villas différentes' },
                  ]}
                  value={multiMode}
                  onChange={onMultiModeChange}
                />
              </div>

              {multiMode === 'multiplier' && (
                <div className="mt-3 flex flex-wrap items-end gap-3">
                  <div className="grid gap-1.5">
                    <Label htmlFor="gen-nbprop">Nombre de propriétés identiques</Label>
                    <Input id="gen-nbprop" type="number" min="1" step="any" className="w-40"
                           value={nombreProprietes}
                           onChange={e => setNombreProprietes(e.target.value)} />
                  </div>
                  {multiPreview?.mode === 'multiplicateur' && (
                    <div className="text-sm text-muted-foreground">
                      {multiPreview.nombreProprietes} × {formatMoney(multiPreview.totalUnitaireSans)}
                      {' = '}
                      <strong className="text-foreground">{formatMoney(multiPreview.totalMultiSans)}</strong>
                      {' '}(total pour {multiPreview.nombreProprietes} propriétés)
                    </div>
                  )}
                </div>
              )}

              {multiMode === 'villas' && (
                <div className="mt-3 flex flex-col gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    {villaGroups.map(g => (
                      <div key={g.index} className="flex items-center gap-1 rounded-md border border-border bg-card px-2 py-1">
                        <Input
                          className="h-7 w-32 border-0 bg-transparent px-1 text-sm shadow-none focus-visible:ring-0"
                          value={g.label}
                          onChange={e => renameVillaGroup(g.index, e.target.value)}
                          aria-label={`Nom du groupe ${g.index}`} />
                        {g.index !== 0 && (
                          <IconButton type="button" label="Supprimer la villa" size="sm"
                                      className="size-6 text-destructive hover:bg-destructive/10"
                                      onClick={() => removeVillaGroup(g.index)}>
                            <Trash2 />
                          </IconButton>
                        )}
                      </div>
                    ))}
                    <Button type="button" size="sm" variant="outline" onClick={addVillaGroup}>
                      <Plus /> Ajouter une villa
                    </Button>
                  </div>
                  {multiPreview?.mode === 'villas' && (
                    <div className="rounded-md border border-info/30 bg-info/5 p-2 text-sm">
                      {multiPreview.groupes.map(g => (
                        <div key={g.index} className="flex justify-between gap-4">
                          <span>{g.label}</span>
                          <span className="tabular-nums">{formatMoney(g.totalTtc)}</span>
                        </div>
                      ))}
                      <div className="mt-1 flex justify-between gap-4 border-t border-info/30 pt-1 font-semibold">
                        <span>Total général</span>
                        <span className="tabular-nums">{formatMoney(multiPreview.grandTotalTtc)}</span>
                      </div>
                    </div>
                  )}
                </div>
              )}
              </div>
            </details>

            {errors.lines && <div className="px-4 py-2 text-xs text-destructive">{errors.lines}</div>}
            {/* QX20 — échappatoire documentée à la garde d'équipement solaire */}
            <label className="px-4 pb-1 flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
              <input type="checkbox" checked={accessoiresOnly}
                     onChange={e => setAccessoiresOnly(e.target.checked)} />
              Avenant / accessoires ou main-d'œuvre seuls (désactive la vérification équipement)
            </label>
            <div className="lines-table-wrap">
              <table className="lines-table" ref={linesTableRef}>
                <thead>
                  <tr>
                    <th style={{ minWidth: 160 }}>Désignation</th>
                    <th style={{ minWidth: 170 }}>Produit (stock)</th>
                    {multiMode === 'villas' && <th style={{ minWidth: 130 }}>Villa</th>}
                    <th className="col-num">Qté</th>
                    <th className="col-num">Prix Unit. TTC</th>
                    <th className="col-num" style={{ width: 64 }} title="Taux TVA de la ligne (réforme : 10 % panneaux PV, 20 % le reste)">TVA %</th>
                    <th className="col-num">Total TTC</th>
                    {/* XSAL5 — case « option » : la ligne est un add-on proposé
                        hors total (activable par le client sur la proposition). */}
                    <th style={{ width: 56 }} title="Ligne optionnelle (add-on) : proposée au client hors total">Option</th>
                    {/* PVORD — monter/descendre : ordre par défaut = ordre du
                        simulateur (autoFillLines), réordonnable ici. */}
                    <th className="col-ordre" title="Réordonner la ligne">Ordre</th>
                    <th className="col-del"></th>
                  </tr>
                </thead>
                <tbody>
                  {/* VX188 — ligne extraite en <DevisLineRow> mémoïsé : taper
                      dans Note/farmSurfaceHa/n'importe lequel des autres
                      useState ne re-rend plus les lignes inchangées (callbacks
                      stabilisés ci-dessus, clé en argument). */}
                  {lines.map((l, i) => (
                    <DevisLineRow
                      key={l._key}
                      line={l}
                      produits={produits}
                      multiMode={multiMode}
                      villaGroups={villaGroups}
                      canRenameLine={canRenameLine}
                      tarifBadge={tarifBadges[l._key]}
                      tvaPanneaux={quoteLogic.tvaPanneaux}
                      tvaStandard={quoteLogic.tvaStandard}
                      onSetField={setLine}
                      onDesignationBlur={onDesignationBlur}
                      onProduitChange={onProduitChange}
                      onProduitCreated={onProduitCreated}
                      onQuantiteChange={onQuantiteChange}
                      onSetGroupe={setLineGroupe}
                      onRemove={removeLine}
                      canMoveUp={i > 0}
                      canMoveDown={i < lines.length - 1}
                      onMoveUp={moveLineUp}
                      onMoveDown={moveLineDown}
                    />
                  ))}
                </tbody>
              </table>
            </div>

            {/* VX138 — chaîne de totaux hiérarchisée (paliers F121 existants) :
                brut (tier-1) → remise/TVA (tier-2) → total final (tier-3, le
                TTC retenu devient le point focal). */}
            <div className="gen-totals-row gen-tier-1">
              {showSans && (
                <div className="gen-total-item">
                  <span className="gen-total-label">Total SANS batterie{sansRec ? ' ⭐' : ''}</span>
                  <span className="gen-total-value">{formatMoney(totals.totalSansBrut)}</span>
                </div>
              )}
              {showAvec && (
                <div className="gen-total-item">
                  <span className="gen-total-label">Total AVEC batterie{avecRec ? ' ⭐' : ''}</span>
                  <span className="gen-total-value orange">{formatMoney(totals.totalAvecBrut)}</span>
                </div>
              )}
            </div>
            <div className="gen-totals-row gen-discount-row">
              <div className="gen-total-item gen-total-inline gen-tier-2">
                <span className="gen-total-label">Réduction</span>
                <input type="number" min="0" max="100" step="any" className="gen-discount-input"
                       value={discountPct} onChange={e => setDiscountPct(e.target.value)} />
                <span style={{ fontWeight: 700 }}>%</span>
                {remiseMax !== '' && parseFloat(discountPct) > parseFloat(remiseMax) && (
                  /* VX17 — couleur d'avertissement via token de thème. */
                  <span className="text-warning ml-1.5" style={{ fontSize: 11 }}>
                    ⚠ au-delà de la limite conseillée ({remiseMax} %)
                  </span>
                )}
              </div>
              <div className="gen-total-item gen-total-inline gen-tier-2">
                <span className="gen-total-label">TVA</span>
                <input type="number" min="0" max="100" step="any" className="gen-discount-input"
                       value={tauxTva} onChange={e => setTauxTva(e.target.value)} />
                <span style={{ fontWeight: 700 }}>%</span>
              </div>
              {parseFloat(discountPct) > 0 && showSans && (
                <div className="gen-total-item gen-tier-3">
                  <span className="gen-total-label green">Total final SANS batterie</span>
                  <span className="gen-total-value green">{formatMoney(totals.totalSans)}</span>
                </div>
              )}
              {parseFloat(discountPct) > 0 && showAvec && (
                <div className="gen-total-item gen-tier-3">
                  <span className="gen-total-label green">Total final AVEC batterie</span>
                  <span className="gen-total-value green">{formatMoney(totals.totalAvec)}</span>
                </div>
              )}
            </div>

            {/* ── Prix par kWc, prix cible et marge (écran uniquement) ── */}
            <div className="gen-totals-row gen-discount-row">
              {pkwc != null && (() => {
                // Repère vs cible société : vert si ≤ cible (bon), rouge si au-dessus.
                const cibleNum = parseFloat(prixCible)
                const hasCible = Number.isFinite(cibleNum) && cibleNum > 0
                const sousCible = hasCible ? pkwc <= cibleNum : null
                // VX17 — couleur via tokens de thème (success/destructive).
                const couleurCls = sousCible == null ? ''
                  : (sousCible ? 'text-success' : 'text-destructive')
                return (
                  <div className="gen-total-item">
                    <span className="gen-total-label">Prix / kWc</span>
                    <span className={`gen-total-value ${couleurCls}`}>
                      {formatMoney(pkwc)}/kWc
                    </span>
                    {hasCible && (
                      <span className={`gen-total-hint ${couleurCls}`} style={{ fontSize: 12 }}>
                        {sousCible
                          ? `≤ cible (${formatMoney(cibleNum)}/kWc)`
                          : `au-dessus de la cible (${formatMoney(cibleNum)}/kWc)`}
                      </span>
                    )}
                  </div>
                )
              })()}
              <div className="gen-total-item gen-total-inline">
                <span className="gen-total-label">Prix cible / kWc</span>
                <input type="number" min="0" step="any" className="gen-discount-input"
                       style={{ width: 100 }} placeholder="ex: 9000"
                       value={prixCible} onChange={e => setPrixCible(e.target.value)} />
                <Button type="button" size="sm" variant="outline"
                        onClick={applyPrixCible}
                        disabled={!(kwp > 0) || prixCible === ''}>
                  Appliquer via remise
                </Button>
              </div>
              {marge != null && (
                <div className="gen-total-item">
                  {/* VX17 — couleurs via tokens de thème (text-success/destructive)
                      plutôt qu'un hex codé en dur. */}
                  <span className={`gen-total-label ${marge < 0 ? 'text-destructive' : 'text-success'}`}>
                    Marge indicative (interne)
                  </span>
                  <span className={`gen-total-value ${marge < 0 ? 'text-destructive' : 'text-success'}`}>
                    {formatMoney(marge)}
                    {kpiTotal > 0 ? ` (${Math.round(marge / kpiTotal * 100)} %)` : ''}
                  </span>
                </div>
              )}
            </div>
            {marge != null && marge < 0 && (
              <div className="mx-5 mb-4 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                Le total après remise est INFÉRIEUR au coût d'achat estimé — vous
                vendez à perte. Réduisez la remise ou le prix cible.
              </div>
            )}
          </CardContent>
        </Card>

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
