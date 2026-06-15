import { useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'
import { useDispatch } from 'react-redux'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { createDevis, addLigneDevis } from '../../features/ventes/store/ventesSlice'
import { createAutoQuote, buildEtudePompage, LEAD_TYPE_TO_MODE } from '../../features/ventes/autoQuote'
import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import parametresApi from '../../api/parametresApi'
import ProduitPicker from '../../components/ProduitPicker'
import {
  MONTHS_FR, CHART_MONTHS, DEFAULT_MONTHLY_BILLS, DAY_USAGE_DEFAULTS,
  formatMoney, estimerMois, estimerPanneaux, computeROI, ttcFromHt, htFromTtc,
  tauxTvaOf,
  batteryKwhFromLines, optionTotalsTTC, autoFillLines, defaultProductLines,
  computeEtudeIndustrielle,
  autoFillPompage, pompageSelection, HEURES_POMPAGE_DEFAUT,
  isBattery, isHybridInverter, prixParKwc, discountForTarget,
  computeBuyCost, avecBatterieAvailability, KWH_PRICE,
} from '../../features/ventes/solar'

const MODES = [
  ['residentiel', '🏠 Résidentiel'],
  ['industriel', '🏭 Industriel / Commercial'],
  ['agricole', '🌾 Agricole (pompage)'],
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
  const [searchParams] = useSearchParams()
  const autoRan = useRef(false)
  // Mode choisi PAR L'UTILISATEUR : un lead sélectionné ensuite ne l'écrase
  // jamais (le pré-réglage depuis le lead ne joue que sur le défaut intact).
  const modeTouched = useRef(false)

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

  // ── Document ──
  const [leadId, setLeadId] = useState('')
  const [clientId, setClientId] = useState('')
  const [dateValidite, setDateValidite] = useState('')
  const [instType, setInstType] = useState('Résidentielle')
  const [scenario, setScenario] = useState('Les deux (Sans + Avec)')
  const [recommendedChoice, setRecommendedChoice] = useState('Auto')
  const [note, setNote] = useState('')

  // ── Factures électriques (valeurs initiales du simulateur) ──
  const [fHiver, setFHiver] = useState('')
  const [fEte, setFEte] = useState('')
  const [monthly, setMonthly] = useState(DEFAULT_MONTHLY_BILLS)

  // ── Paramètres techniques ──
  const [nbPanneaux, setNbPanneaux] = useState('')
  const [panelW, setPanelW] = useState('710')
  const [structureType, setStructureType] = useState('acier')
  const [dayUsage, setDayUsage] = useState(DAY_USAGE_DEFAULTS['Résidentielle'])

  // ── Lignes (prix TTC, comme le simulateur) & remise ──
  const [lines, setLines] = useState([])
  const [previewCollapsed, setPreviewCollapsed] = useState(false)
  const [tauxTva, setTauxTva] = useState('20.00')
  const [discountPct, setDiscountPct] = useState('0')
  const linesInitialized = useRef(false)

  // ── Multi-marchés ──
  const [modeInstallation, setModeInstallation] = useState('residentiel')
  const [consoMensuelle, setConsoMensuelle] = useState('')
  const [prixCible, setPrixCible] = useState('')
  // Pompage (agricole)
  const [pompeCv, setPompeCv] = useState('5.5')
  const [pompeType, setPompeType] = useState('immergee')
  const [pompeAlim, setPompeAlim] = useState('tri')
  const [pompeHmt, setPompeHmt] = useState('')
  const [pompeDebit, setPompeDebit] = useState('')
  const [pompeProfondeur, setPompeProfondeur] = useState('')
  const [pompeDistance, setPompeDistance] = useState('20')
  const [pompeHeures, setPompeHeures] = useState(String(HEURES_POMPAGE_DEFAUT))

  useEffect(() => {
    crmApi.getClients().then(r => setClients(r.data.results ?? r.data)).catch(() => {})
    crmApi.getLeads().then(r => setLeads(r.data.results ?? r.data)).catch(() => {})
    stockApi.getProduits().then(r => setProduits(r.data.results ?? r.data)).catch(() => {})
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

  const roi = useMemo(() => {
    if (dKwp <= 0 || !dMonthly.some(v => v > 0)) return null
    return computeROI({
      kwp: dKwp,
      factures: dMonthly.map(v => parseFloat(v) || 0),
      dayUsagePct: parseInt(dDayUsage) || 50,
      totalSans: dTotals.totalSans,
      totalAvec: dTotals.totalAvec,
      batteryKwh: batteryKwhFromLines(dLines),
    })
  }, [dKwp, dMonthly, dDayUsage, dTotals, dLines])

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
    if (selectedLead.client_nom) return `${selectedLead.client_nom} (client existant lié)`
    if (selectedLead.email) {
      const match = clients.find(c =>
        (c.email || '').toLowerCase() === selectedLead.email.toLowerCase())
      if (match) return `${match.nom} ${match.prenom || ''} (client existant — même email)`.trim()
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
    if (lead.conso_mensuelle_kwh) setConsoMensuelle(String(lead.conso_mensuelle_kwh))
    const hiver = parseFloat(lead.facture_hiver) || 0
    if (hiver > 0) {
      // bascule OFF → la valeur unique vaut hiver ET été
      const ete = (lead.ete_differente && lead.facture_ete)
        ? parseFloat(lead.facture_ete) : hiver
      setFHiver(String(lead.facture_hiver))
      setFEte(lead.ete_differente && lead.facture_ete ? String(lead.facture_ete) : '')
      const suggested = estimerPanneaux(hiver)
      if (suggested > 0) setNbPanneaux(String(suggested))
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
      // dupliqué : un seul endroit dimensionne le devis auto.
      const devisId = await createAutoQuote({
        lead, produits, discountStr, dispatch,
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
    || (avgBill > 0 ? Math.round(avgBill / KWH_PRICE) : 0)

  const etudeIndustrielle = (modeInstallation === 'industriel' && kwp > 0
      && consoKwhDerivee > 0)
    ? computeEtudeIndustrielle({
        kwp, consoMensuelleKwh: consoKwhDerivee,
        dayUsagePct: dayUsage, totalTtc: kpiTotal,
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
          <h2>☀️ Générateur de Devis Solaire</h2>
          <button className="btn btn-outline" onClick={() => navigate('/ventes/devis')}>
            ← Retour aux devis
          </button>
        </div>
      )}

      {/* noValidate : aucune contrainte navigateur — toute valeur saisie est
          acceptée telle quelle (les steps ne servent qu'aux flèches). */}
      <form onSubmit={handleSubmit} noValidate>
        {/* ── Mode d'installation (marché) ── */}
        <div className="gen-card">
          <div className="gen-card-header">🎯 Marché / Mode d'installation</div>
          <div className="gen-card-body">
            <div className="gen-radio-group">
              {MODES.map(([value, label]) => (
                <label key={value}
                       className={`gen-radio${modeInstallation === value ? ' selected' : ''}`}>
                  <input type="radio" name="mode-installation" value={value}
                         checked={modeInstallation === value}
                         onChange={() => { modeTouched.current = true; onModeChange(value) }} />
                  {label}
                </label>
              ))}
            </div>
            {modeInstallation === 'residentiel' && kwp > 36 && (
              <div className="gen-resolved-client" style={{ background: '#eff6ff', borderColor: '#bfdbfe', color: '#1e40af' }}>
                💡 Ce système fait {kwp.toFixed(2)} kWc — au-delà de l'échelle résidentielle.
                Le mode Industriel / Commercial produira un document plus adapté
                (étude d'autoconsommation, option unique). Vous pouvez ignorer cette suggestion.
              </div>
            )}
            {showAvecWarning && (
              <div className="form-error-box" style={{ marginTop: '0.75rem' }}>
                ⚠ Option « avec batterie » indisponible pour ce système : {avecDispo.reason}.
                Le PDF sera un document à option unique (sans batterie) — jamais une
                option partielle silencieuse.
              </div>
            )}
            {errors.conso && (
              <div className="form-error-box" style={{ marginTop: '0.75rem' }}>{errors.conso}</div>
            )}
          </div>
        </div>

        {/* ── Informations du document ── */}
        <div className="gen-card">
          <div className="gen-card-header">📋 Informations du Document</div>
          <div className="gen-card-body">
            <div className="gen-grid">
              <div className="form-group">
                <label className="form-label">N° de Devis</label>
                <input className="form-control" value="Généré automatiquement" disabled />
              </div>
              <div className="form-group">
                <label className="form-label">Type d'Installation</label>
                <select className="form-select" value={instType} onChange={e => onInstTypeChange(e.target.value)}>
                  <option>Résidentielle</option>
                  <option>Commerciale</option>
                  <option>Industrielle</option>
                  <option>Agricole</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Scénario</label>
                <select className="form-select" value={scenario} onChange={e => onScenarioChange(e.target.value)}>
                  <option value="Les deux (Sans + Avec)">Les deux (Sans + Avec batterie)</option>
                  <option value="Sans batterie">Sans batterie seulement</option>
                  <option value="Avec batterie">Avec batterie seulement</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Option Recommandée</label>
                <select className="form-select" value={recommendedChoice} onChange={e => setRecommendedChoice(e.target.value)}>
                  <option value="Auto">Auto (défaut)</option>
                  <option value="Aucune recommandation">Aucune recommandation</option>
                  <option value="Sans batterie">Sans batterie</option>
                  <option value="Avec batterie">Avec batterie</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Date de validité</label>
                <input type="date" className="form-control" value={dateValidite}
                       onChange={e => setDateValidite(e.target.value)} />
              </div>
            </div>
          </div>
        </div>

        {/* ── Lead / Client (lead prioritaire) ── */}
        <div className="gen-card">
          <div className="gen-card-header">👤 Lead & Client</div>
          <div className="gen-card-body">
            <div className="gen-grid">
              <div className="form-group fg-grow">
                <label className="form-label">
                  Lead (point de départ) <span className="req">*</span>
                </label>
                <select
                  className={`form-select${errors.client ? ' is-invalid' : ''}`}
                  value={leadId}
                  onChange={e => applyLead(e.target.value)}
                >
                  <option value="">— Sélectionner un lead —</option>
                  {leads.map(l => (
                    <option key={l.id} value={l.id}>
                      {l.nom}{l.prenom ? ` ${l.prenom}` : ''}
                      {l.societe ? ` (${l.societe})` : ''}
                      {l.facture_hiver ? ` — ${Math.round(parseFloat(l.facture_hiver))} MAD/mois` : ''}
                    </option>
                  ))}
                </select>
                {errors.client && <div className="form-feedback">{errors.client}</div>}
              </div>
              <div className="form-group fg-grow">
                <label className="form-label">Téléphone</label>
                <input className="form-control" disabled placeholder="—"
                       value={selectedLead?.telephone ?? selectedClient?.telephone ?? ''} />
              </div>
            </div>

            {selectedLead && (
              <div className="gen-resolved-client">
                ✓ Client du devis : <strong>{resolvedClientLabel}</strong>
                {selectedLead.facture_hiver
                  ? ` · factures remplies depuis le lead (${selectedLead.facture_hiver}${selectedLead.ete_differente && selectedLead.facture_ete ? ` hiver / ${selectedLead.facture_ete} été` : ' MAD/mois'})`
                  : ' · aucune facture enregistrée sur ce lead'}
              </div>
            )}

            {!leadId && (
              <div className="gen-grid" style={{ marginTop: '0.75rem' }}>
                <div className="form-group fg-grow">
                  <label className="form-label">…ou choisir un client directement (sans lead)</label>
                  <select className="form-select" value={clientId}
                          onChange={e => setClientId(e.target.value)}>
                    <option value="">— Sélectionner un client —</option>
                    {clients.map(c => (
                      <option key={c.id} value={c.id}>
                        {c.nom}{c.prenom ? ` ${c.prenom}` : ''}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-group fg-grow">
                  <label className="form-label">Adresse</label>
                  <input className="form-control" value={selectedClient?.adresse ?? ''} disabled
                         placeholder="—" />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── Factures électriques (masquées en mode pompage) ── */}
        {modeInstallation !== 'agricole' && (
        <div className="gen-card">
          <div className="gen-card-header">💡 Factures Électriques</div>
          <div className="gen-card-body">
            <p className="gen-hint">
              Renseignez vos factures mensuelles (MAD) ou estimez-les via les montants
              hiver/été. Ces valeurs servent au calcul ROI dans le devis.
            </p>
            <div className="gen-grid">
              <div className="form-group">
                <label className="form-label">Facture Hiver moy. (MAD/mois)</label>
                <input type="number" min="0" step="any" className="form-control"
                       placeholder="ex: 600" value={fHiver}
                       onChange={e => { setFHiver(e.target.value); syncBillEstimator(e.target.value, fEte) }} />
              </div>
              <div className="form-group">
                <label className="form-label">Facture Été moy. (MAD/mois)</label>
                <input type="number" min="0" step="any" className="form-control"
                       placeholder="ex: 400" value={fEte}
                       onChange={e => { setFEte(e.target.value); syncBillEstimator(fHiver, e.target.value) }} />
              </div>
              <div className="form-group" style={{ alignSelf: 'flex-end' }}>
                <button type="button" className="btn btn-outline" onClick={handleEstimerMois}>
                  📊 Estimer 12 mois
                </button>
              </div>
            </div>
            {errors.bills && <div className="form-feedback">{errors.bills}</div>}
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
            {modeInstallation === 'industriel' && (
              <div className="gen-grid" style={{ marginTop: '0.85rem' }}>
                <div className="form-group">
                  <label className="form-label">Consommation mensuelle (kWh) — pour l'étude</label>
                  <input type="number" min="0" step="any" className="form-control"
                         placeholder="ex: 12000" value={consoMensuelle}
                         onChange={e => setConsoMensuelle(e.target.value)} />
                </div>
              </div>
            )}
          </div>
        </div>
        )}

        {/* ── Pompage solaire (mode Agricole) ── */}
        {modeInstallation === 'agricole' && (
        <div className="gen-card">
          <div className="gen-card-header">🌾 Pompage solaire</div>
          <div className="gen-card-body">
            <div className="gen-grid">
              <div className="form-group">
                <label className="form-label">
                  Puissance pompe (CV)
                  {pompageSel?.mode === 'courbe' && ' — auto (courbe)'}
                </label>
                <input type="number" min="0" step="any" className="form-control"
                       value={pompeCv} onChange={e => setPompeCv(e.target.value)} />
                {pompageDims && (
                  <div className="gen-hint" style={{ marginTop: 4 }}>
                    ≈ {pompageSel?.kw ?? pompageDims.kw} kW · champ PV conseillé {pompageDims.champKw} kWc
                    ({pompageDims.nbPanneaux} panneaux 710 W)
                  </div>
                )}
              </div>
              <div className="form-group">
                <label className="form-label">Type de pompe</label>
                <div className="gen-radio-group">
                  <label className={`gen-radio${pompeType === 'immergee' ? ' selected' : ''}`}>
                    <input type="radio" name="pompe-type" value="immergee"
                           checked={pompeType === 'immergee'}
                           onChange={() => setPompeType('immergee')} />
                    Immergée
                  </label>
                  <label className={`gen-radio${pompeType === 'surface' ? ' selected' : ''}`}>
                    <input type="radio" name="pompe-type" value="surface"
                           checked={pompeType === 'surface'}
                           onChange={() => setPompeType('surface')} />
                    Surface
                  </label>
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Alimentation</label>
                <div className="gen-radio-group">
                  <label className={`gen-radio${pompeAlim === 'mono' ? ' selected' : ''}`}>
                    <input type="radio" name="pompe-alim" value="mono"
                           checked={pompeAlim === 'mono'}
                           onChange={() => setPompeAlim('mono')} />
                    Mono 220V
                  </label>
                  <label className={`gen-radio${pompeAlim === 'tri' ? ' selected' : ''}`}>
                    <input type="radio" name="pompe-alim" value="tri"
                           checked={pompeAlim === 'tri'}
                           onChange={() => setPompeAlim('tri')} />
                    Tri 380V
                  </label>
                </div>
              </div>
            </div>
            <div className="gen-grid" style={{ marginTop: '0.75rem' }}>
              <div className="form-group">
                <label className="form-label">HMT (m)</label>
                <input type="number" min="0" step="any" className="form-control"
                       placeholder="ex: 120" value={pompeHmt}
                       onChange={e => setPompeHmt(e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Débit souhaité (m³/h)</label>
                <input type="number" min="0" step="any" className="form-control"
                       placeholder="ex: 30" value={pompeDebit}
                       onChange={e => setPompeDebit(e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Heures de pompage effectives / jour</label>
                <input type="number" min="0" step="any" className="form-control"
                       value={pompeHeures}
                       onChange={e => setPompeHeures(e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Profondeur forage (m) — optionnel</label>
                <input type="number" min="0" step="any" className="form-control"
                       value={pompeProfondeur}
                       onChange={e => setPompeProfondeur(e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Distance panneaux → coffret (m)</label>
                <input type="number" min="0" step="any" className="form-control"
                       value={pompeDistance}
                       onChange={e => setPompeDistance(e.target.value)} />
              </div>
            </div>

            {/* ── Résultat du dimensionnement (source des chiffres du PDF) ── */}
            {pompageSel?.mode === 'courbe' && (
              <div className="gen-resolved-client"
                   style={{ marginTop: '0.75rem', background: '#eff6ff', borderColor: '#bfdbfe', color: '#1e40af' }}>
                <strong>Pompe sélectionnée : {pompageSel.pump.nom}</strong>
                <div style={{ marginTop: 4 }}>
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
              <div className="form-error-box" style={{ marginTop: '0.75rem' }}>
                ⚠ Seules des pompes <strong>sans prix renseigné</strong> conviennent à cette
                HMT et ce débit ({pompageSel.sansPrix.join(', ')}). Renseignez leur prix
                dans Stock pour les chiffrer — aucune pompe ne sera ajoutée au devis.
              </div>
            )}
          </div>
        </div>
        )}

        {/* ── Paramètres techniques ── */}
        <div className="gen-card">
          <div className="gen-card-header">⚡ Paramètres Techniques</div>
          <div className="gen-card-body">
            <div className="gen-grid">
              <div className="form-group">
                <label className="form-label">Nombre de panneaux <span className="req">*</span></label>
                <input type="number" min="1" max="500" step="any" className="form-control"
                       placeholder="ex: 14" value={nbPanneaux}
                       onChange={e => setNbPanneaux(e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Puissance Panneau (W)</label>
                <input type="number" min="100" max="1000" step="any" className="form-control"
                       value={panelW} onChange={e => setPanelW(e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Puissance PV (kWp) — calculée</label>
                <div className="gen-kwp">{kwp > 0 ? kwp.toFixed(2) + ' kWp' : '—'}</div>
              </div>
              <div className="form-group">
                <label className="form-label">Type de Structure</label>
                <div className="gen-radio-group">
                  <label className={`gen-radio${structureType === 'acier' ? ' selected' : ''}`}>
                    <input type="radio" name="structure-type" value="acier"
                           checked={structureType === 'acier'}
                           onChange={() => setStructureType('acier')} />
                    Acier galvanisé
                  </label>
                  <label className={`gen-radio${structureType === 'aluminium' ? ' selected' : ''}`}>
                    <input type="radio" name="structure-type" value="aluminium"
                           checked={structureType === 'aluminium'}
                           onChange={() => setStructureType('aluminium')} />
                    Aluminium
                  </label>
                </div>
              </div>
            </div>
            <div className="gen-slider-row">
              <span className="gen-slider-label">Consommation diurne (%)</span>
              <input type="range" min="10" max="100" step="5" value={dayUsage}
                     onChange={e => setDayUsage(e.target.value)} />
              <span className="gen-slider-value">{dayUsage}%</span>
            </div>
            <div className="gen-actions-right">
              {errors.autofill && <span className="form-feedback">{errors.autofill}</span>}
              <button type="button" className="btn gen-btn-orange" onClick={handleAutoFill}>
                ⚡ Auto-remplir depuis le stock
              </button>
            </div>
          </div>
        </div>

        {/* ── Aperçu de la simulation (masqué en mode pompage) ── */}
        {modeInstallation !== 'agricole' && (
        <div className="gen-card">
          <div className="gen-card-header">
            📊 Aperçu de la Simulation
            {/* Repliable sur téléphone uniquement (bouton caché sur bureau) */}
            <button type="button" className="btn btn-sm btn-outline gen-preview-toggle"
                    onClick={() => setPreviewCollapsed(v => !v)}>
              {previewCollapsed ? 'Afficher' : 'Replier'}
            </button>
          </div>
          <div className={`gen-card-body gen-preview-body${previewCollapsed ? ' m-collapsed' : ''}`}>
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
              <p className="gen-hint" style={{ textAlign: 'center' }}>
                Renseignez le nombre de panneaux et les factures, puis la simulation
                s'actualise automatiquement.
              </p>
            ) : (
              <>
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
          </div>
        </div>
        )}

        {/* ── Lignes de produits ── */}
        <div className="gen-card">
          <div className="gen-card-header">
            🛒 Lignes de Produits
            <button type="button" className="btn btn-sm btn-outline" onClick={addLine}>
              + Ajouter ligne
            </button>
          </div>
          <div className="gen-card-body" style={{ padding: 0 }}>
            {errors.lines && <div className="form-feedback" style={{ padding: '8px 16px' }}>{errors.lines}</div>}
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
                    return (
                      <tr key={l._key}>
                        <td>
                          <input className="form-control form-control-sm" value={l.designation}
                                 onChange={e => setLine(l._key, 'designation', e.target.value)}
                                 placeholder="Désignation" />
                        </td>
                        <td>
                          <ProduitPicker
                            produits={produits}
                            value={l.produit}
                            onChange={id => onProduitChange(l._key, id)}
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
                        </td>
                        <td className="line-total" data-label="Total TTC">{formatMoney(lineTtc)}</td>
                        <td>
                          <button type="button" className="btn-icon-danger"
                                  onClick={() => removeLine(l._key)} title="Supprimer">✕</button>
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
              {pkwc != null && (
                <div className="gen-total-item">
                  <span className="gen-total-label">Prix / kWc</span>
                  <span className="gen-total-value">{formatMoney(pkwc)}/kWc</span>
                </div>
              )}
              <div className="gen-total-item gen-total-inline">
                <span className="gen-total-label">Prix cible / kWc</span>
                <input type="number" min="0" step="any" className="gen-discount-input"
                       style={{ width: 100 }} placeholder="ex: 9000"
                       value={prixCible} onChange={e => setPrixCible(e.target.value)} />
                <button type="button" className="btn btn-sm btn-outline"
                        onClick={applyPrixCible}
                        disabled={!(kwp > 0) || prixCible === ''}>
                  Appliquer via remise
                </button>
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
              <div className="form-error-box" style={{ margin: '0 1.25rem 1rem' }}>
                ⚠ Le total après remise est INFÉRIEUR au coût d'achat estimé — vous
                vendez à perte. Réduisez la remise ou le prix cible.
              </div>
            )}
          </div>
        </div>

        {/* ── Notes ── */}
        <div className="gen-card">
          <div className="gen-card-header">📝 Notes</div>
          <div className="gen-card-body">
            <textarea className="form-control" rows={3} value={note}
                      onChange={e => setNote(e.target.value)}
                      placeholder="Conditions de paiement, remarques internes..." />
          </div>
        </div>

        {/* Toute raison de blocage est VISIBLE à côté du bouton — jamais de
            clic silencieux sans effet. */}
        {(errors.submit || errors.lines || errors.client || errors.conso) && (
          <div className="form-error-box">
            {errors.submit || errors.lines || errors.client || errors.conso}
          </div>
        )}

        {/* ── Création ── */}
        <div className="gen-card">
          <div className="gen-card-header">
            {editDevis ? `📄 Modification du devis ${editDevis.reference}` : '📄 Création du Devis'}
          </div>
          <div className="gen-card-body">
            <p className="gen-hint">
              {embedded
                ? "Vérifiez puis enregistrez. Le devis s'affiche ensuite ici même "
                  + 'avec son PDF, sans quitter la fiche du lead.'
                : 'Vérifiez les informations ci-dessus puis créez le devis. Le PDF '
                  + 'premium 3 pages se génère ensuite depuis la liste des devis (bouton « PDF »).'}
            </p>
            <div className="gen-actions-right gen-actions-sticky">
              {!embedded && (
                <button type="button" className="btn btn-outline" onClick={handleReset}>
                  🔄 Réinitialiser
                </button>
              )}
              <button type="button" className="btn btn-outline" onClick={cancel}>
                Annuler
              </button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving
                  ? 'Enregistrement...'
                  : (editDevis ? '💾 Enregistrer les modifications' : '☀️ Créer le devis')}
              </button>
            </div>
          </div>
        </div>
      </form>
    </div>
  )
}
