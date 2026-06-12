import { useEffect, useMemo, useRef, useState } from 'react'
import { useDispatch } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { createDevis, addLigneDevis } from '../../features/ventes/store/ventesSlice'
import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import {
  MONTHS_FR, CHART_MONTHS, DEFAULT_MONTHLY_BILLS, DAY_USAGE_DEFAULTS,
  formatMoney, estimerMois, estimerPanneaux, computeROI, ttcFromHt,
  batteryKwhFromLines, optionTotalsTTC, autoFillLines, defaultProductLines,
} from '../../features/ventes/solar'

let _keyCounter = 0
const newKey = () => ++_keyCounter

const withKeys = (rows) => rows.map(r => ({
  _key: newKey(),
  produit: String(r.produit ?? ''),
  designation: r.designation,
  quantite: String(r.quantite),
  prix_unit_ttc: String(r.prix_unit_ttc),
}))

// Nouvelle ligne vide — quantité 0 comme addProductLine() du simulateur
const emptyLine = () => ({
  _key: newKey(),
  produit: '',
  designation: '',
  quantite: '0',
  prix_unit_ttc: '0',
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

export default function DevisGenerator() {
  const dispatch = useDispatch()
  const navigate = useNavigate()

  const [clients, setClients] = useState([])
  const [produits, setProduits] = useState([])
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState({})

  // ── Document ──
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
  const [tauxTva, setTauxTva] = useState('20.00')
  const [discountPct, setDiscountPct] = useState('0')
  const linesInitialized = useRef(false)

  useEffect(() => {
    crmApi.getClients().then(r => setClients(r.data.results ?? r.data)).catch(() => {})
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

  const roi = useMemo(() => {
    if (kwp <= 0 || !monthly.some(v => v > 0)) return null
    return computeROI({
      kwp,
      factures: monthly.map(v => parseFloat(v) || 0),
      dayUsagePct: parseInt(dayUsage) || 50,
      totalSans: totals.totalSans,
      totalAvec: totals.totalAvec,
      batteryKwh: batteryKwhFromLines(lines),
    })
  }, [kwp, monthly, dayUsage, totals, lines])

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

  // ── Scénario / recommandation : réinitialisation si incompatible ──
  const onScenarioChange = (v) => {
    setScenario(v)
    if ((v === 'Sans batterie' && recommendedChoice === 'Avec batterie') ||
        (v === 'Avec batterie' && recommendedChoice === 'Sans batterie')) {
      setRecommendedChoice('Auto')
    }
  }

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
            prix_unit_ttc: p ? String(ttcFromHt(p.prix_vente)) : l.prix_unit_ttc,
          }
        : l
    ))
  }

  const addLine = () => setLines(ls => [...ls, emptyLine()])
  const removeLine = (key) => setLines(ls => ls.filter(l => l._key !== key))

  const handleAutoFill = () => {
    if (kwp <= 0) {
      setErrors(e => ({ ...e, autofill: 'Entrez le nombre de panneaux' }))
      return
    }
    const generated = autoFillLines(produits, {
      kwp,
      panelW: parseFloat(panelW) || 710,
      structureType,
    })
    if (!generated.length) {
      setErrors(e => ({ ...e, autofill: 'Aucun produit solaire reconnu dans le stock.' }))
      return
    }
    setErrors(e => ({ ...e, autofill: null }))
    setLines(withKeys(generated))
  }

  // ── Sauvegarde ──
  // Une ligne est enregistrée si elle a un produit et une quantité > 0 ;
  // les lignes placeholder (sans produit, prix 0) sont ignorées silencieusement.
  const usableLines = () =>
    lines.filter(l => l.produit && parseFloat(l.quantite) > 0)

  const validate = () => {
    const e = {}
    if (!clientId) e.client = 'Client requis'
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
      const devis = await dispatch(createDevis({
        client: parseInt(clientId),
        statut: 'brouillon',
        date_validite: dateValidite || null,
        taux_tva: tauxTva,
        remise_globale: discountPct || '0',
        note: note || null,
      })).unwrap()

      const tvaFactor = 1 + (parseFloat(tauxTva) || 20) / 100
      await Promise.all(usableLines().map(l =>
        dispatch(addLigneDevis({
          devis: devis.id,
          produit: parseInt(l.produit),
          designation: l.designation,
          quantite: l.quantite,
          // le modèle stocke des prix HT ; l'écran travaille en TTC comme le simulateur
          prix_unitaire: ((parseFloat(l.prix_unit_ttc) || 0) / tvaFactor).toFixed(2),
          remise: '0',
        })).unwrap()
      ))

      navigate('/ventes/devis')
    } catch (err) {
      const msg = err?.detail ?? err?.non_field_errors?.[0] ?? JSON.stringify(err)
      setErrors(prev => ({ ...prev, submit: msg }))
    } finally {
      setSaving(false)
    }
  }

  const selectedClient = clients.find(c => String(c.id) === String(clientId))

  return (
    <div className="page gen-page">
      <div className="page-header">
        <h2>☀️ Générateur de Devis Solaire</h2>
        <button className="btn btn-outline" onClick={() => navigate('/ventes/devis')}>
          ← Retour aux devis
        </button>
      </div>

      <form onSubmit={handleSubmit}>
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

        {/* ── Client ── */}
        <div className="gen-card">
          <div className="gen-card-header">👤 Informations Client</div>
          <div className="gen-card-body">
            <div className="gen-grid">
              <div className="form-group">
                <label className="form-label">Client <span className="req">*</span></label>
                <select
                  className={`form-select${errors.client ? ' is-invalid' : ''}`}
                  value={clientId}
                  onChange={e => setClientId(e.target.value)}
                >
                  <option value="">— Sélectionner un client —</option>
                  {clients.map(c => (
                    <option key={c.id} value={c.id}>
                      {c.nom}{c.prenom ? ` ${c.prenom}` : ''}
                    </option>
                  ))}
                </select>
                {errors.client && <div className="form-feedback">{errors.client}</div>}
              </div>
              <div className="form-group">
                <label className="form-label">Téléphone</label>
                <input className="form-control" value={selectedClient?.telephone ?? ''} disabled
                       placeholder="—" />
              </div>
              <div className="form-group fg-grow">
                <label className="form-label">Adresse</label>
                <input className="form-control" value={selectedClient?.adresse ?? ''} disabled
                       placeholder="—" />
              </div>
            </div>
          </div>
        </div>

        {/* ── Factures électriques ── */}
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
                <input type="number" min="0" step="10" className="form-control"
                       placeholder="ex: 600" value={fHiver}
                       onChange={e => { setFHiver(e.target.value); syncBillEstimator(e.target.value, fEte) }} />
              </div>
              <div className="form-group">
                <label className="form-label">Facture Été moy. (MAD/mois)</label>
                <input type="number" min="0" step="10" className="form-control"
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
                  <input type="number" min="0" step="10" className="form-control form-control-sm"
                         value={monthly[i]}
                         onChange={e => setMonth(i, e.target.value)} />
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── Paramètres techniques ── */}
        <div className="gen-card">
          <div className="gen-card-header">⚡ Paramètres Techniques</div>
          <div className="gen-card-body">
            <div className="gen-grid">
              <div className="form-group">
                <label className="form-label">Nombre de panneaux <span className="req">*</span></label>
                <input type="number" min="1" max="500" step="1" className="form-control"
                       placeholder="ex: 14" value={nbPanneaux}
                       onChange={e => setNbPanneaux(e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Puissance Panneau (W)</label>
                <input type="number" min="100" max="1000" step="10" className="form-control"
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

        {/* ── Aperçu de la simulation ── */}
        <div className="gen-card">
          <div className="gen-card-header">📊 Aperçu de la Simulation</div>
          <div className="gen-card-body">
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
                          <select className="form-select form-select-sm" value={l.produit}
                                  onChange={e => onProduitChange(l._key, e.target.value)}>
                            <option value="">— Produit —</option>
                            {produits.map(p => (
                              <option key={p.id} value={p.id}>{p.nom}</option>
                            ))}
                          </select>
                        </td>
                        <td>
                          <input type="number" min="0" step="1"
                                 className="form-control form-control-sm ta-right" value={l.quantite}
                                 onChange={e => setLine(l._key, 'quantite', e.target.value)} />
                        </td>
                        <td>
                          <input type="number" min="0" step="100"
                                 className="form-control form-control-sm ta-right" value={l.prix_unit_ttc}
                                 onChange={e => setLine(l._key, 'prix_unit_ttc', e.target.value)} />
                        </td>
                        <td className="line-total">{formatMoney(lineTtc)}</td>
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
                <input type="number" min="0" max="100" step="5" className="gen-discount-input"
                       value={discountPct} onChange={e => setDiscountPct(e.target.value)} />
                <span style={{ fontWeight: 700 }}>%</span>
              </div>
              <div className="gen-total-item gen-total-inline">
                <span className="gen-total-label">TVA</span>
                <input type="number" min="0" max="100" step="0.01" className="gen-discount-input"
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

        {errors.submit && <div className="form-error-box">{errors.submit}</div>}

        {/* ── Création ── */}
        <div className="gen-card">
          <div className="gen-card-header">📄 Création du Devis</div>
          <div className="gen-card-body">
            <p className="gen-hint">
              Vérifiez les informations ci-dessus puis créez le devis. Le PDF premium
              3 pages se génère ensuite depuis la liste des devis (bouton « PDF »).
            </p>
            <div className="gen-actions-right">
              <button type="button" className="btn btn-outline"
                      onClick={() => navigate('/ventes/devis')}>
                Annuler
              </button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? 'Création...' : '☀️ Créer le devis'}
              </button>
            </div>
          </div>
        </div>
      </form>
    </div>
  )
}
