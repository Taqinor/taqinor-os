import { useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'
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
import { createDevis, addLigneDevis } from '../../features/ventes/store/ventesSlice'
import { createAutoQuote, buildEtudePompage, LEAD_TYPE_TO_MODE } from '../../features/ventes/autoQuote'
import { waterDemandFromFarm } from '../../features/ventes/agronomy'
import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import parametresApi from '../../api/parametresApi'
import ProduitPicker from '../../components/ProduitPicker'
import ClientQuickCreateModal from './ClientQuickCreateModal'
import {
  Button, IconButton, Card, CardContent,
  Input, Textarea, Label, Segmented,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import {
  MONTHS_FR, CHART_MONTHS, DEFAULT_MONTHLY_BILLS, DAY_USAGE_DEFAULTS,
  formatMoney, estimerMois, estimerPanneaux, computeROI, ttcFromHt, htFromTtc,
  tauxTvaOf,
  batteryKwhFromLines, optionTotalsTTC, autoFillLines, defaultProductLines,
  computeEtudeIndustrielle,
  autoFillPompage, pompageSelection, HEURES_POMPAGE_DEFAUT,
  isBattery, isHybridInverter, prixParKwc, discountForTarget,
  computeBuyCost, avecBatterieAvailability, KWH_PRICE, EFFICIENCY,
  panneauxPourKwc, expectedTvaForDesignation,
  TVA_STANDARD_DEFAUT, TVA_PANNEAUX_DEFAUT,
  classifyProduct,
  kwhFromBill, buildEtudeParamsChoice,
} from '../../features/ventes/solar'

const MODE_OPTIONS = [
  { value: 'residentiel', label: '🏠 Résidentiel' },
  { value: 'industriel', label: '🏭 Industriel / Commercial' },
  { value: 'agricole', label: '🌾 Agricole (pompage)' },
]

let _keyCounter = 0
const newKey = () => ++_keyCounter

const withKeys = (rows) => rows.map(r => ({
  _key: newKey(),
  produit: String(r.produit ?? ''),
  designation: r.designation,
  quantite: String(r.quantite),
  prix_unit_ttc: String(r.prix_unit_ttc),
  taux_tva: String(r.taux_tva ?? 20),
}))

// Nouvelle ligne vide — quantité 0 comme addProductLine() du simulateur
const emptyLine = () => ({
  _key: newKey(),
  produit: '',
  designation: '',
  quantite: '0',
  prix_unit_ttc: '0',
  taux_tva: '20',
})

const fmtNum = (v) => (v !== null && v !== undefined) ? v.toLocaleString('fr-MA') : 'N/A'

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

  // ── Multi-marchés ──
  const [modeInstallation, setModeInstallation] = useState('residentiel')
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
  })
  const [remiseMax, setRemiseMax] = useState('')
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
    })
  }, [dKwp, dMonthly, dDayUsage, dTotals, dLines, quoteLogic, consoAnnuelleReelle, distributeur])

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
  const selectedLead = leads.find(l => String(l.id) === String(leadId))

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
  const setLine = (key, k, v) =>
    setLines(ls => ls.map(l => (l._key === key ? { ...l, [k]: v } : l)))

  const onProduitChange = (key, produitId) => {
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
  }

  const addLine = () => setLines(ls => [...ls, emptyLine()])
  const removeLine = (key) => setLines(ls => ls.filter(l => l._key !== key))

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
    setErrors(e => ({
      ...e,
      autofill: manquants.length
        ? `Aucun produit du stock ne correspond à : ${[...new Set(manquants)].join(', ')}. `
          + 'Complétez le catalogue ou choisissez ces produits à la main dans les lignes.'
        : null,
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
      let devisId
      if (editDevis) {
        // ÉDITION EN PLACE : mêmes référence et statut ; les anciennes lignes
        // sont remplacées par celles du formulaire.
        await ventesApi.patchDevis(editDevis.id, payload)
        await Promise.all(editDevis.lineIds.map(id =>
          ventesApi.deleteLigneDevis(id).catch(() => {})))
        devisId = editDevis.id
      } else {
        // Lead prioritaire : le client est résolu côté serveur depuis le lead.
        if (leadId) payload.lead = parseInt(leadId)
        else payload.client = parseInt(clientId)
        const devis = await dispatch(createDevis(payload)).unwrap()
        devisId = devis.id
      }

      await Promise.all(usableLines().map(l =>
        dispatch(addLigneDevis({
          devis: devisId,
          produit: parseInt(l.produit),
          designation: l.designation,
          quantite: l.quantite,
          // le modèle stocke des prix HT ; l'écran travaille en TTC comme le
          // simulateur. Réforme TVA : le HT est dérivé au taux DE LA LIGNE
          // (10 % panneaux / 20 % le reste) pour que le TTC tapé soit exact.
          prix_unitaire: htFromTtc(l.prix_unit_ttc, l.taux_tva ?? 20),
          remise: '0',
          taux_tva: String(l.taux_tva ?? 20),
        })).unwrap()
      ))

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
      {!embedded && (
        <div className="page-header">
          <h2>Générateur de Devis Solaire</h2>
          <Button variant="outline" onClick={() => navigate('/ventes/devis')}>
            <ArrowLeft /> Retour aux devis
          </Button>
        </div>
      )}

      {/* noValidate : aucune contrainte navigateur — toute valeur saisie est
          acceptée telle quelle (les steps ne servent qu'aux flèches). */}
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
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
                Ce système fait {kwp.toFixed(2)} kWc — au-delà de l'échelle résidentielle.
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

            {!leadId && (
              <div className="mt-3 grid gap-4 sm:grid-cols-2">
                <div className="grid gap-1.5">
                  <Label htmlFor="gen-client">…ou choisir un client directement (sans lead)</Label>
                  <div className="flex gap-2">
                    <div className="flex-1">
                      <Select value={clientId ? String(clientId) : undefined} onValueChange={setClientId}>
                        <SelectTrigger id="gen-client">
                          <SelectValue placeholder="— Sélectionner un client —" />
                        </SelectTrigger>
                        <SelectContent>
                          {clients.map(c => (
                            <SelectItem key={c.id} value={String(c.id)}>
                              {c.nom}{c.prenom ? ` ${c.prenom}` : ''}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
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
                <div className="gen-kwp">{kwp > 0 ? kwp.toFixed(2) + ' kWp' : '—'}</div>
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
                  {showSans && (
                    <MetricCard label="Éco. Option 1 – Sans batterie"
                                value={fmtNum(Math.round(roi.eco_annuelle_sans))}
                                unit="MAD / an" recommended={sansRec} />
                  )}
                  {showAvec && (
                    <MetricCard label="Éco. Option 2 – Avec batterie"
                                value={fmtNum(Math.round(roi.eco_annuelle_avec))}
                                unit="MAD / an" recommended={avecRec} />
                  )}
                  {showSans && (
                    <MetricCard label="ROI Sans batterie"
                                value={roi.payback_sans !== null ? roi.payback_sans + ' ans' : 'N/A'}
                                unit="retour sur invest." recommended={sansRec} accent />
                  )}
                  {showAvec && (
                    <MetricCard label="ROI Avec batterie"
                                value={roi.payback_avec !== null ? roi.payback_avec + ' ans' : 'N/A'}
                                unit="retour sur invest." recommended={avecRec} accent />
                  )}
                  {showSans && (
                    <MetricCard label="Coût Option 1 – Sans"
                                value={fmtNum(Math.round(totals.totalSans))}
                                unit="MAD TTC" recommended={sansRec} />
                  )}
                  {showAvec && (
                    <MetricCard label="Coût Option 2 – Avec"
                                value={fmtNum(Math.round(totals.totalAvec))}
                                unit="MAD TTC" recommended={avecRec} />
                  )}
                </div>
                <div className="gen-chart-title">Économies mensuelles estimées (MAD / mois)</div>
                <ResponsiveContainer width="100%" height={260}>
                  <ComposedChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(0,0,0,0.07)" />
                    <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }}
                           label={{ value: 'MAD / mois', angle: -90, position: 'insideLeft', fontSize: 11 }}
                           tickFormatter={(v) => v.toLocaleString('fr-MA')} />
                    <Tooltip formatter={(v, name) => [`${Math.round(v).toLocaleString('fr-MA')} MAD`, name]} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="facture" name="Facture ONEE (MAD)"
                         fill="rgba(181,192,206,0.55)" stroke="rgba(181,192,206,0.8)" radius={[3, 3, 0, 0]} />
                    {showSans && (
                      <Line type="monotone" dataKey="ecoSans"
                            name={'Option 1 – Sans batterie' + (sansRec ? ' ⭐' : '')}
                            stroke="#1A2B4A" strokeWidth={sansRec ? 3.5 : 2.2}
                            dot={{ r: sansRec ? 5 : 4 }} />
                    )}
                    {showAvec && (
                      <Line type="monotone" dataKey="ecoAvec"
                            name={'Option 2 – Avec batterie' + (avecRec ? ' ⭐' : '')}
                            stroke="#F5A623" strokeWidth={avecRec ? 3.5 : 2.2}
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
            {errors.lines && <div className="px-4 py-2 text-xs text-destructive">{errors.lines}</div>}
            <div className="lines-table-wrap">
              <table className="lines-table">
                <thead>
                  <tr>
                    <th style={{ minWidth: 160 }}>Désignation</th>
                    <th style={{ minWidth: 170 }}>Produit (stock)</th>
                    <th className="col-num">Qté</th>
                    <th className="col-num">Prix Unit. TTC</th>
                    <th className="col-num" style={{ width: 64 }} title="Taux TVA de la ligne (réforme : 10 % panneaux PV, 20 % le reste)">TVA %</th>
                    <th className="col-num">Total TTC</th>
                    <th className="col-del"></th>
                  </tr>
                </thead>
                <tbody>
                  {lines.map(l => {
                    const lineTtc =
                      (parseFloat(l.quantite) || 0) * (parseFloat(l.prix_unit_ttc) || 0)
                    // Indice non bloquant : la désignation a été éditée et ne
                    // correspond plus au nom du produit choisi — la classification
                    // (réseau/hybride/batterie/panneau) pourrait changer la
                    // répartition d'options du PDF. On n'altère jamais la saisie.
                    const prodLie = l.produit
                      ? produits.find(p => String(p.id) === String(l.produit))
                      : null
                    const designationDivergente = !!prodLie
                      && (l.designation || '').trim() !== (prodLie.nom || '').trim()
                    return (
                      <tr key={l._key}>
                        <td data-label="Désignation">
                          <input className="form-control form-control-sm" value={l.designation}
                                 onChange={e => setLine(l._key, 'designation', e.target.value)}
                                 placeholder="Désignation" />
                          {designationDivergente && (
                            <div className="mt-0.5 text-xs text-warning"
                                 title="La désignation diffère du nom du produit — vérifiez la classification PDF">
                              Désignation modifiée (produit : {prodLie.nom})
                            </div>
                          )}
                        </td>
                        <td data-label="Produit (stock)">
                          <ProduitPicker
                            produits={produits}
                            value={l.produit}
                            onChange={id => onProduitChange(l._key, id)}
                            typeFilter={classifyProduct(l.designation) || undefined}
                            onProduitCreated={(p) => setProduits(ps => [...ps, p])}
                          />
                        </td>
                        <td data-label="Qté">
                          <input type="number" min="0" step="any"
                                 className="form-control form-control-sm ta-right" value={l.quantite}
                                 onChange={e => setLine(l._key, 'quantite', e.target.value)} />
                        </td>
                        <td data-label="Prix unit. TTC">
                          <input type="number" min="0" step="any"
                                 className="form-control form-control-sm ta-right" value={l.prix_unit_ttc}
                                 onChange={e => setLine(l._key, 'prix_unit_ttc', e.target.value)} />
                        </td>
                        <td data-label="TVA %">
                          <input type="number" min="0" step="any"
                                 className="form-control form-control-sm ta-right"
                                 style={{ width: 56, fontSize: '0.75rem', color: '#64748b' }}
                                 value={l.taux_tva ?? '20'}
                                 onChange={e => setLine(l._key, 'taux_tva', e.target.value)} />
                          {(() => {
                            // DC7 — AVERTISSEMENT de divergence uniquement : le
                            // taux attendu suit la désignation + les repères TVA
                            // société (expectedTvaForDesignation), et `Produit.tva`
                            // reste la source autoritaire par ligne. On n'altère
                            // JAMAIS la valeur saisie (frappe souveraine).
                            const t = parseFloat(l.taux_tva)
                            if (!Number.isFinite(t) || !(l.designation || '').trim()) return null
                            const expected = expectedTvaForDesignation(l.designation, {
                              tvaPanneaux: quoteLogic.tvaPanneaux,
                              tvaStandard: quoteLogic.tvaStandard,
                            })
                            if (t !== expected) {
                              return <div className="mt-0.5 text-xs text-warning">{`${expected} % attendu`}</div>
                            }
                            return null
                          })()}
                        </td>
                        <td className="line-total" data-label="Total TTC">{formatMoney(lineTtc)}</td>
                        <td>
                          <IconButton type="button" label="Supprimer la ligne" size="sm"
                                      className="text-destructive hover:bg-destructive/10"
                                      onClick={() => removeLine(l._key)}>
                            <Trash2 />
                          </IconButton>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            <div className="gen-totals-row">
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
              <div className="gen-total-item gen-total-inline">
                <span className="gen-total-label">Réduction</span>
                <input type="number" min="0" max="100" step="any" className="gen-discount-input"
                       value={discountPct} onChange={e => setDiscountPct(e.target.value)} />
                <span style={{ fontWeight: 700 }}>%</span>
                {remiseMax !== '' && parseFloat(discountPct) > parseFloat(remiseMax) && (
                  <span style={{ fontSize: 11, color: '#b45309', marginLeft: 6 }}>
                    ⚠ au-delà de la limite conseillée ({remiseMax} %)
                  </span>
                )}
              </div>
              <div className="gen-total-item gen-total-inline">
                <span className="gen-total-label">TVA</span>
                <input type="number" min="0" max="100" step="any" className="gen-discount-input"
                       value={tauxTva} onChange={e => setTauxTva(e.target.value)} />
                <span style={{ fontWeight: 700 }}>%</span>
              </div>
              {parseFloat(discountPct) > 0 && showSans && (
                <div className="gen-total-item">
                  <span className="gen-total-label green">Total final SANS batterie</span>
                  <span className="gen-total-value green">{formatMoney(totals.totalSans)}</span>
                </div>
              )}
              {parseFloat(discountPct) > 0 && showAvec && (
                <div className="gen-total-item">
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
                const couleur = sousCible == null ? undefined
                  : (sousCible ? '#16a34a' : '#b91c1c')
                return (
                  <div className="gen-total-item">
                    <span className="gen-total-label">Prix / kWc</span>
                    <span className="gen-total-value" style={{ color: couleur }}>
                      {formatMoney(pkwc)}/kWc
                    </span>
                    {hasCible && (
                      <span className="gen-total-hint" style={{ color: couleur, fontSize: 12 }}>
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
                  <span className={`gen-total-label${marge < 0 ? '' : ' green'}`}
                        style={marge < 0 ? { color: '#b91c1c' } : undefined}>
                    Marge indicative (interne)
                  </span>
                  <span className="gen-total-value"
                        style={{ color: marge < 0 ? '#b91c1c' : '#16a34a' }}>
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
      <ClientQuickCreateModal
        open={clientQuickCreateOpen}
        onClose={() => setClientQuickCreateOpen(false)}
        onCreated={(c) => {
          setClients(cs => [...cs, c])
          setClientId(String(c.id))
          setClientQuickCreateOpen(false)
        }}
      />
    </div>
  )
}
