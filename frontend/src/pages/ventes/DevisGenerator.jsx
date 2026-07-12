import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'
import { useDispatch } from 'react-redux'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import {
  ArrowLeft, Target, ClipboardList, User, Zap, Sprout, BarChart3,
  ShoppingCart, StickyNote, FileText, RotateCcw, Sun, Plus, Trash2,
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
import ClientQuickCreateModal from './ClientQuickCreateModal'
import DevisPresetPanel from './DevisPresetPanel'
import DevisLineRow from './DevisLineRow'
import { Combobox } from '../../ui/Combobox'
import { searchCompanies } from '../../features/crm/companyLookup'
import {
  Button, IconButton, Card, CardContent,
  Input, Textarea, Label, Segmented,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  HelpTip, ScrollProgress,
} from '../../ui'
import { useCanCreateProduit } from '../../hooks/useHasPermission'
import useKeyboardAwareScroll from '../../hooks/useKeyboardAwareScroll'
import { useDirtyGuard } from '../../ui/useDirtyGuard'
import { useDraftAutosave } from '../../ui/useDraftAutosave'
import {
  MONTHS_FR, CHART_MONTHS, DEFAULT_MONTHLY_BILLS, DAY_USAGE_DEFAULTS,
  formatMoney, estimerMois, estimerPanneaux, computeROI, ttcFromHt, htFromTtc,
  tauxTvaOf,
  batteryKwhFromLines, optionTotalsTTC, autoFillLines, defaultProductLines,
  computeEtudeIndustrielle,
  autoFillPompage, pompageSelection, HEURES_POMPAGE_DEFAUT,
  isBattery, isHybridInverter, isReseauInverter, isPanel, isPompe,
  prixParKwc, discountForTarget,
  computeBuyCost, avecBatterieAvailability, KWH_PRICE, EFFICIENCY,
  panneauxPourKwc,
  TVA_STANDARD_DEFAUT, TVA_PANNEAUX_DEFAUT,
  kwhFromBill, buildEtudeParamsChoice, multiPropertyPreviewTTC,
  productibleForCity,
} from '../../features/ventes/solar'
import { formatNumber, formatMAD, formatDateTime } from '../../lib/format'

const MODE_OPTIONS = [
  { value: 'residentiel', label: '🏠 Résidentiel' },
  { value: 'industriel', label: '🏭 Industriel / Commercial' },
  { value: 'agricole', label: '🌾 Agricole (pompage)' },
]

let _keyCounter = 0
const newKey = () => ++_keyCounter

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
  const pompeAlimTouched = useRef(false)
  const nbPanneauxTouched = useRef(false)

  // Fin de parcours : embarqué → callbacks (jamais de navigation) ; pleine
  // page → retour à la liste des devis (comportement historique).
  const finish = (devisId) => {
    if (embedded) { onDone?.(devisId); return }
    navigate('/ventes/devis')
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
  const [scenario, setScenario] = useState('Les deux (Sans + Avec)')
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

  // ── Paramètres techniques ──
  const [nbPanneaux, setNbPanneaux] = useState('')
  const [panelW, setPanelW] = useState('710')
  const [structureType, setStructureType] = useState('acier')
  const [dayUsage, setDayUsage] = useState(DAY_USAGE_DEFAULTS['Résidentielle'])

  // ── Lignes (prix TTC, comme le simulateur) & remise ──
  const [lines, setLines] = useState([])
  // Confirmation d'auto-remplissage agricole (m³/jour + champ PV) — affichée
  // une fois l'auto-remplissage pompage réussi.
  const [pompageAutoFilled, setPompageAutoFilled] = useState(false)
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
    setMultiAccordionOpen(modeInstallation !== 'agricole')
  }, [modeInstallation])
  const [consoMensuelle, setConsoMensuelle] = useState('')
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
  const dirty = Boolean(
    leadId || clientId || note || fHiver || fEte || nbPanneaux
    || consoMensuelle || prixCible || pompeHmt || pompeDebit || farmSurfaceHa,
  )
  const { restored, restore, discard, clear } = useDraftAutosave(draftKey, draftSnapshot, {
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
    if (d.scenario != null) setScenario(d.scenario)
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
    Promise.allSettled([
      crmApi.getClients().then(r => setClients(r.data.results ?? r.data)).catch(() => { fail('clients'); throw 0 }),
      crmApi.getLeads().then(r => setLeads(r.data.results ?? r.data)).catch(() => { fail('leads'); throw 0 }),
      stockApi.getProduits().then(r => setProduits(r.data.results ?? r.data)).catch(() => { fail('produits'); throw 0 }),
    ]).finally(() => setRefsLoading(false))
  }, [])

  // Table par défaut du simulateur une fois le stock chargé
  useEffect(() => {
    if (linesInitialized.current || !produits.length) return
    linesInitialized.current = true
    setLines(withKeys(defaultProductLines(produits)))
  }, [produits])

  const kwp = (parseInt(nbPanneaux) || 0) * (parseFloat(panelW) || 0) / 1000

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

  const chartData = useMemo(() => {
    if (!roi) return []
    return roi.monthly_detail.map((d, i) => ({
      month: CHART_MONTHS[i],
      facture: d.facture,
      ecoSans: Math.round(d.eco_sans),
      ecoAvec: Math.round(d.eco_avec),
    }))
  }, [roi])

  // ── Type d'installation → autoconsommation par défaut (simulateur) ──
  const onInstTypeChange = (type) => {
    setInstType(type)
    setDayUsage(DAY_USAGE_DEFAULTS[type] ?? 50)
  }

  // ── Mode d'installation (Résidentiel / Industriel-Commercial / Agricole) ──
  const onModeChange = (m) => {
    if (m === modeInstallation) return
    // QX23 — changer de mode marché après saisie écrase l'étude/ROI et les
    // lignes auto-remplies : on confirme AVANT (jamais de rejet silencieux de
    // l'étude). Ne demande la confirmation que s'il y a réellement quelque
    // chose à perdre (au moins une ligne avec produit, ou une étude calculée).
    const hasWork = lines.some(l => l.produit && parseFloat(l.quantite) > 0)
      || !!etudeIndustrielle || pompageAutoFilled
    if (hasWork) {
      const ok = window.confirm(
        'Changer de marché va réinitialiser l\'étude et les lignes déjà '
        + 'remplies pour ce devis. Continuer ?')
      if (!ok) return
    }
    setModeInstallation(m)
    if (m === 'industriel') {
      onInstTypeChange('Industrielle')
      setScenario('Sans batterie') // défaut industriel : sans batterie, réseau
    } else if (m === 'agricole') {
      onInstTypeChange('Agricole')
    } else {
      onInstTypeChange('Résidentielle')
      setScenario('Les deux (Sans + Avec)')
    }
  }

  // ── Scénario / recommandation : réinitialisation si incompatible ──
  const onScenarioChange = (v) => {
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

  const applyLead = (id) => {
    setLeadId(id)
    if (!id) return
    setClientId('') // le client est résolu côté serveur depuis le lead
    const lead = leads.find(l => String(l.id) === String(id))
    if (!lead) return
    // Pré-réglage du mode depuis le lead UNIQUEMENT si l'utilisateur n'a pas
    // déjà choisi un mode lui-même — son choix ne se réinitialise JAMAIS.
    if (!modeTouched.current
        && lead.type_installation && LEAD_TYPE_TO_MODE[lead.type_installation]) {
      onModeChange(LEAD_TYPE_TO_MODE[lead.type_installation])
    }
    // Structure préférée du lead (acier/aluminium) si non touchée par l'utilisateur.
    if (!structureTouched.current
        && (lead.structure_pref === 'acier' || lead.structure_pref === 'aluminium')) {
      setStructureType(lead.structure_pref)
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
      // pas déjà fourni un nombre de panneaux (taille prioritaire).
      if (fromTaille <= 0) {
        const suggested = estimerPanneaux(hiver, quoteLogic.panneauxParTranche)
        if (suggested > 0) setNbPanneaux(String(suggested))
      }
      setMonthly(estimerMois(hiver, ete))
    }
  }

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
        window.alert('Ce devis n\'est plus un brouillon — il ne peut plus être modifié.')
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
      const rows = (d.lignes ?? []).map(l => ({
        produit: String(l.produit ?? ''),
        designation: l.designation,
        quantite: String(parseFloat(l.quantite)),
        prix_unit_ttc: String(ttcFromHt(l.prix_unitaire, l.taux_tva ?? d.taux_tva)),
        taux_tva: String(parseFloat(l.taux_tva ?? d.taux_tva) || 20),
      }))
      setLines(withKeys(rows))
      linesInitialized.current = true
      const panneaux = rows
        .filter(r => /panneau/i.test(r.designation))
        .reduce((s, r) => s + (parseFloat(r.quantite) || 0), 0)
      if (panneaux > 0) setNbPanneaux(String(panneaux))
      const e = d.etude_params || {}
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
  const syncBillEstimator = (hiverVal, eteVal) => {
    const hiver = parseFloat(hiverVal) || 0
    const ete = parseFloat(eteVal) || 0
    if (hiver <= 0) return
    const suggested = estimerPanneaux(hiver)
    if (suggested > 0) setNbPanneaux(String(suggested))
    setMonthly(estimerMois(hiver, ete > 0 ? ete : hiver))
  }

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
      // VX249(b) — une modification MANUELLE du taux retire le style
      // « suggéré » de CETTE ligne (jamais les autres) ; tout autre champ
      // laisse `_tvaSuggested` inchangé.
      ? { ...l, [k]: v, ...(k === 'taux_tva' ? { _tvaSuggested: false } : {}) }
      : l)))
  }, [])

  // XSAL3 — badge « Tarif : <liste> » par ligne, quand le prix résolu vient
  // d'une liste de prix client (source !== 'standard'). Purement informatif +
  // pré-remplissage au changement de produit/quantité/client — ne touche
  // JAMAIS une valeur déjà tapée manuellement par l'utilisateur après coup
  // (aucun re-snap sur un prix modifié à la main).
  const [tarifBadges, setTarifBadges] = useState({})

  const refreshTarif = async (key, produitId, quantite) => {
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
        setLines(ls => ls.map(l =>
          l._key === key ? { ...l, prix_unit_ttc: String(data.prix) } : l))
      } else {
        setTarifBadges(b => { const { [key]: _drop, ...rest } = b; return rest })
      }
    } catch {
      // Résolution de prix indisponible : on garde le prix standard déjà posé,
      // jamais de blocage de la saisie.
      setTarifBadges(b => { const { [key]: _drop, ...rest } = b; return rest })
    }
  }

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
          }
        : l
    ))
    if (p) {
      const l = lines.find(x => x._key === key)
      refreshTarif(key, produitId, l?.quantite)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [produits, lines])

  // Ré-interroge le tarif applicable quand la quantité change sur une ligne
  // déjà liée à un produit (paliers XSAL2), ou quand le client change (liste
  // XSAL1 assignée) — pour toutes les lignes liées à un produit.
  const onQuantiteChange = useCallback((key, quantite) => {
    setLine(key, 'quantite', quantite)
    const l = lines.find(x => x._key === key)
    if (l?.produit) refreshTarif(key, l.produit, quantite)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lines, setLine])

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
  const removeLine = useCallback((key) =>
    setLines(ls => ls.filter(l => l._key !== key)), [])
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
  }, [villaGroups])

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

  const handleAutoFill = () => {
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
      setErrors(e => ({ ...e, autofill: null }))
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
    })
    // Mode industriel : sans batterie par défaut (réseau seul, triphasé)
    if (modeInstallation === 'industriel') {
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
    const realW = generated.actualPanelW
    let mismatch = null
    if (realW && Math.abs(realW - askedW) > 1) {
      const kwcReel = generated.kwcReel
      mismatch = `Attention : le stock ne propose pas de panneau ${askedW} W ; `
        + `un panneau ${realW} W a été retenu. La puissance réelle du système est `
        + `${kwcReel} kWc (et non ${kwp} kWc). Ajustez le nombre de panneaux ou le `
        + 'wattage pour la cible voulue.'
    }
    setErrors(e => ({
      ...e,
      autofill: manquants.length
        ? `Aucun produit du stock ne correspond à : ${[...new Set(manquants)].join(', ')}. `
          + 'Complétez le catalogue ou choisissez ces produits à la main dans les lignes.'
        : null,
      autofillKwc: mismatch,
    }))
    setLines(withKeys(generated))
  }

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

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    setSaving(true)
    try {
      // Paramètres d'étude stockés avec le devis (alimentent la page Étude
      // du PDF et le bloc résumé pompage)
      let etudeParams = null
      if (modeInstallation === 'industriel' && etudeIndustrielle) {
        etudeParams = etudeIndustrielle
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
      const lignesPayload = usableLines().map(l => ({
        produit: parseInt(l.produit),
        designation: l.designation,
        quantite: l.quantite,
        prix_unitaire: htFromTtc(l.prix_unit_ttc, l.taux_tva ?? 20),
        remise: '0',
        taux_tva: String(l.taux_tva ?? 20),
        groupe_index: multiMode === 'villas' ? l.groupeIndex : null,
        groupe_label: multiMode === 'villas' ? (l.groupeLabel || '') : '',
      }))

      let devisId
      if (editDevis) {
        // QX21 — ÉDITION ATOMIQUE : le patch du devis PUIS le remplacement des
        // lignes en une transaction serveur. Un échec préserve les lignes
        // existantes (jamais un devis à zéro ligne, plus de delete-puis-recrée).
        await ventesApi.patchDevis(editDevis.id, payload)
        await ventesApi.replaceLignesDevis(editDevis.id, lignesPayload)
        devisId = editDevis.id
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
      }

      clear() // VX62 — succès : purge le brouillon local.
      finish(devisId)
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
    } finally {
      setSaving(false)
    }
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
      })
    : null

  // Disponibilité de l'option « avec batterie » (règle : jamais sans onduleur)
  const avecDispo = avecBatterieAvailability(lines, produits, kwp)
  const showAvecWarning = showAvec && lines.length > 0 && !avecDispo.available

  // Dimensionnement pompage : SOURCE UNIQUE écran / devis / PDF.
  // Courbe constructeur (HMT + débit souhaité) si une pompe à courbe convient,
  // sinon sélection historique par CV (débit manuel, pas de m³/jour inventé).
  const pompageSel = modeInstallation === 'agricole'
    ? pompageSelection(produits, {
        cv: pompeCv, alim: pompeAlim, typePompe: pompeType,
        hmt: pompeHmt, debit: pompeDebit, heures: pompeHeures,
      })
    : null
  const pompageDims = pompageSel?.dims ?? null

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
  const handleReset = () => {
    if (window.confirm('Réinitialiser le formulaire ?')) window.location.reload()
  }

  return (
    <div className={embedded ? 'gen-embedded' : 'page gen-page'}>
      {/* VX136 — formulaire-fleuve (2319+ l.) : barre de progression de
          scroll native, `scroll(nearest)` suit le conteneur qui défile
          réellement (`.layout-content` en page pleine, le Sheet englobant
          quand `embedded` dans LeadDevisPanel). */}
      <ScrollProgress />
      {!embedded && (
        <div className="page-header">
          <h2>Générateur de Devis Solaire</h2>
          <Button variant="outline" onClick={() => navigate('/ventes/devis')}>
            <ArrowLeft /> Retour aux devis
          </Button>
        </div>
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
              onChange={(v) => { modeTouched.current = true; onModeChange(v) }}
            />
            {modeInstallation === 'residentiel' && kwp > 36 && (
              <div className="mt-3 rounded-lg border border-info/30 bg-info/10 p-3 text-sm text-info">
                Ce système fait {formatNumber(kwp, { decimals: 2 })} kWc — au-delà de l'échelle résidentielle.
                Le mode Industriel / Commercial produira un document plus adapté
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

            {/* QX28 — le lead porte un repère toit (GPS) : raccourci vers la
                conception 3D qui EXPLOITE ces données, plutôt qu'un devis à plat
                qui les ignore. Visible seulement quand roof_point est présent. */}
            {selectedLead?.roof_point && (
              <div className="mt-3 flex flex-wrap items-center gap-3 rounded-lg border border-brass-400/40 bg-brass-400/10 p-3 text-sm">
                <span>🛰️ Repère toit disponible sur ce lead (GPS).</span>
                <Button type="button" variant="outline" size="sm"
                        onClick={() => navigate(`/devis-design/${selectedLead.id}`)}>
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
                        onChange={(v) => setClientId(v ? String(v) : '')}
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
                       onChange={e => { setFHiver(e.target.value); syncBillEstimator(e.target.value, fEte) }} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="gen-ete">Facture Été moy. (MAD/mois)</Label>
                <Input id="gen-ete" type="number" min="0" step="any"
                       placeholder="ex: 400" value={fEte}
                       onChange={e => { setFEte(e.target.value); syncBillEstimator(fHiver, e.target.value) }} />
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
                             : setRealBillKwh(e.target.value))} />
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

            {modeInstallation === 'industriel' && (
              <div className="mt-3.5 grid gap-4 sm:grid-cols-2">
                <div className="grid gap-1.5">
                  <Label htmlFor="gen-conso">Consommation mensuelle (kWh) — pour l'étude</Label>
                  <Input id="gen-conso" type="number" min="0" step="any"
                         placeholder="ex: 12000" value={consoMensuelle}
                         onChange={e => setConsoMensuelle(e.target.value)} />
                </div>
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
              <div className="grid gap-1.5">
                <Label htmlFor="gen-nbpanneaux" required>Nombre de panneaux</Label>
                <Input id="gen-nbpanneaux" type="number" min="1" max="500" step="any"
                       placeholder="ex: 14" value={nbPanneaux}
                       onChange={e => { nbPanneauxTouched.current = true; setNbPanneaux(e.target.value) }} />
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
            <div className="gen-slider-row">
              <span className="gen-slider-label">Consommation diurne (%)</span>
              <input type="range" min="10" max="100" step="5" value={dayUsage}
                     onChange={e => setDayUsage(e.target.value)} />
              <span className="gen-slider-value">{dayUsage}%</span>
            </div>
            <div className="mt-3 flex flex-wrap items-center justify-end gap-3">
              {errors.autofill && <span className="text-xs text-destructive">{errors.autofill}</span>}
              {errors.autofillKwc && <span className="text-xs text-warning">{errors.autofillKwc}</span>}
              <Button type="button" className="bg-brass-400 text-nuit hover:bg-brass-500" onClick={handleAutoFill}>
                <Zap /> Auto-remplir depuis le stock
              </Button>
            </div>
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
            {etudeIndustrielle && (
              <div className="gen-metrics-grid" style={{ marginBottom: '0.75rem' }}>
                <MetricCard label="Taux d'autoconsommation"
                            value={`${etudeIndustrielle.taux_autoconso} %`}
                            unit="part de la production consommée" accent />
                {etudeIndustrielle.taux_couverture != null && (
                  <MetricCard label="Taux de couverture"
                              value={`${etudeIndustrielle.taux_couverture} %`}
                              unit="part de la conso couverte" accent />
                )}
                <MetricCard label="Économies annuelles (étude)"
                            value={fmtNum(etudeIndustrielle.economies_annuelles)}
                            unit="MAD / an" />
                {etudeIndustrielle.payback != null && (
                  <MetricCard label="Payback (étude)"
                              value={`${etudeIndustrielle.payback} ans`}
                              unit="retour sur invest." />
                )}
              </div>
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
                  <MetricCard label="Production annuelle"
                              value={fmtNum(Math.round(roi.production_annuelle_kwh))}
                              unit="kWh / an" accent />
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
                                  value={fmtNum(Math.round(roi.eco_annuelle_sans))}
                                  unit="MAD / an" />
                      <MetricCard label="ROI"
                                  value={roi.payback_sans !== null ? roi.payback_sans + ' ans' : 'N/A'}
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
                      <MetricCard label="Économies"
                                  value={fmtNum(Math.round(roi.eco_annuelle_avec))}
                                  unit="MAD / an" />
                      <MetricCard label="ROI"
                                  value={roi.payback_avec !== null ? roi.payback_avec + ' ans' : 'N/A'}
                                  unit="retour sur invest." accent />
                      <MetricCard label="Coût"
                                  value={fmtNum(Math.round(totals.totalAvec))}
                                  unit="MAD TTC" />
                    </div>
                  )}
                </div>
                <div className="gen-chart-title">Économies mensuelles estimées (MAD / mois)</div>
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
              </>
            )}
          </CardContent>
        </Card>
        )}

        {/* ── Lignes de produits ── */}
        <Card>
          <GenCardHeader icon={ShoppingCart} title="Lignes de Produits">
            <Button type="button" size="sm" variant="outline" onClick={addLine}>
              <Plus /> Ajouter ligne
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
                    <th className="col-del"></th>
                  </tr>
                </thead>
                <tbody>
                  {/* VX188 — ligne extraite en <DevisLineRow> mémoïsé : taper
                      dans Note/farmSurfaceHa/n'importe lequel des autres
                      useState ne re-rend plus les lignes inchangées (callbacks
                      stabilisés ci-dessus, clé en argument). */}
                  {lines.map(l => (
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
            Disponible en édition (le panneau exige un devisId serveur). */}
        {editDevis && (
          <DevisPresetPanel devisId={editDevis.id} onApplied={handlePresetApplied} />
        )}

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
      <aside className="gen-summary-rail hidden lg:block lg:w-72 lg:shrink-0 lg:sticky"
             style={{ top: 'var(--header-h, 64px)' }}>
        <Card>
          <CardContent className="pt-4 flex flex-col gap-3">
            <div>
              <div className="text-xs uppercase tracking-wide text-muted-foreground">
                Total {scenario === 'Avec batterie' ? 'avec batterie'
                  : scenario === 'Sans batterie' ? 'sans batterie'
                    : (avecRec ? 'avec batterie' : 'sans batterie')} · TTC
              </div>
              <div className="text-2xl font-bold text-foreground">{formatMoney(kpiTotal)}</div>
            </div>
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
