import { useRef, useState, useEffect, useCallback } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import { FileUpload } from '../../ui/FileUpload'
import {
  processOcrStockDocument,
  clearStockOcrResult,
} from '../../features/ia/store/iaSlice'

// G26 — type/taille acceptés (inchangés vs. l'ancienne dropzone inline).
const STOCK_OCR_ACCEPT = 'image/jpeg,image/png,image/tiff,image/webp,application/pdf'
const STOCK_OCR_MAX_SIZE = 10 * 1024 * 1024 // 10 Mo
import {
  fetchProduits,
  fetchFournisseurs,
  fetchCategories,
  fetchMouvements,
} from '../../features/stock/store/stockSlice'
import stockApi from '../../api/stockApi'

const DOC_LABELS = {
  bon_livraison: 'Bon de livraison',
  facture_fournisseur: 'Facture fournisseur',
  autre: 'Autre document',
}

// ── Types de document (Step 0) ─────────────────────────────────────────────────
const DOC_TYPES = [
  {
    value: 'facture_achat',
    label: "Facture d'achat",
    desc: 'Facture reçue d\'un fournisseur avec montants HT et TVA',
    mouvement: 'entree',
    color: '#1d4ed8', bg: '#eff6ff', border: '#bfdbfe', activeBorder: '#1d4ed8',
    icon: (
      <svg width={28} height={28} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <line x1="16" y1="13" x2="8" y2="13"/>
        <line x1="16" y1="17" x2="8" y2="17"/>
        <polyline points="10 9 9 9 8 9"/>
      </svg>
    ),
  },
  {
    value: 'bon_livraison',
    label: 'Bon de livraison',
    desc: 'Livraison fournisseur (les prix peuvent être absents)',
    mouvement: 'entree',
    color: '#059669', bg: '#f0fdf4', border: '#bbf7d0', activeBorder: '#059669',
    icon: (
      <svg width={28} height={28} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
        <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
        <line x1="12" y1="22.08" x2="12" y2="12"/>
      </svg>
    ),
  },
  {
    value: 'bon_sortie',
    label: 'Bon de sortie',
    desc: 'Livraison à un client (sortie de stock)',
    mouvement: 'sortie',
    color: '#d97706', bg: '#fffbeb', border: '#fde68a', activeBorder: '#d97706',
    icon: (
      <svg width={28} height={28} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
        <rect x="1" y="3" width="15" height="13" rx="1"/>
        <path d="M16 8h4l3 3v5h-7V8z"/>
        <circle cx="5.5" cy="18.5" r="2.5"/>
        <circle cx="18.5" cy="18.5" r="2.5"/>
      </svg>
    ),
  },
  {
    value: 'autre',
    label: 'Autre document',
    desc: 'Transfert, inventaire ou document non standard',
    mouvement: null,
    color: '#64748b', bg: '#f8fafc', border: '#e2e8f0', activeBorder: '#64748b',
    icon: (
      <svg width={28} height={28} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" y1="8" x2="12" y2="12"/>
        <line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>
    ),
  },
]

// ── SVG helper ────────────────────────────────────────────────────────────────
function Ic({ size = 20, color = 'currentColor', sw = 1.8, children }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round"
      style={{ flexShrink: 0, display: 'block' }}>
      {children}
    </svg>
  )
}

// ── Stepper ───────────────────────────────────────────────────────────────────
function Stepper({ step }) {
  const steps = [
    { label: 'Type',       sub: 'Document' },
    { label: 'Upload',     sub: 'Fichier source' },
    { label: 'Validation', sub: 'Vérification' },
    { label: 'Résultats',  sub: 'Application stock' },
  ]
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', marginBottom: '2.25rem' }}>
      {steps.map((s, i) => {
        const n      = i + 1
        const done   = n < step
        const active = n === step
        const ringColor  = done ? '#059669' : active ? '#1d4ed8' : '#e2e8f0'
        const labelColor = active ? '#0f172a'  : done ? '#059669' : '#94a3b8'
        return (
          <div key={n} style={{ display: 'flex', alignItems: 'flex-start', flex: i < steps.length - 1 ? 1 : 'none' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, minWidth: 64 }}>
              <div style={{
                width: 34, height: 34, borderRadius: '50%',
                background: done ? '#059669' : active ? '#1d4ed8' : '#f8fafc',
                border: `2px solid ${ringColor}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'all 0.35s cubic-bezier(0.4,0,0.2,1)',
                boxShadow: active ? '0 0 0 4px rgba(29,78,216,0.12)' : 'none',
              }}>
                {done
                  ? <Ic size={14} color="#fff" sw={2.5}><polyline points="20 6 9 17 4 12"/></Ic>
                  : <span style={{ fontSize: 12, fontWeight: 700, color: active ? '#fff' : '#94a3b8' }}>{n}</span>
                }
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 11.5, fontWeight: active ? 600 : 400, color: labelColor, transition: 'color 0.3s', whiteSpace: 'nowrap' }}>
                  {s.label}
                </div>
                <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 1, whiteSpace: 'nowrap' }}>{s.sub}</div>
              </div>
            </div>
            {i < steps.length - 1 && (
              <div style={{ flex: 1, height: 2, margin: '16px 4px 0', background: '#e2e8f0', borderRadius: 1, overflow: 'hidden' }}>
                <div style={{
                  height: '100%', borderRadius: 1, background: '#059669',
                  width: done ? '100%' : '0%',
                  transition: 'width 0.5s cubic-bezier(0.4,0,0.2,1)',
                }}/>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Page principale ───────────────────────────────────────────────────────────
export default function OcrStockImport() {
  const dispatch   = useDispatch()
  const navigate   = useNavigate()
  const produitsRef     = useRef([])
  const fournisseursRef = useRef([])

  const role = useSelector((s) => s.auth.role)
  const { stockOcrResult, stockOcrDocType, stockOcrLoading, stockOcrError } = useSelector((s) => s.ia)
  const { produits, fournisseurs, categories } = useSelector((s) => s.stock)
  const categoriesRef = useRef([])

  useEffect(() => { produitsRef.current = produits }, [produits])
  useEffect(() => { fournisseursRef.current = fournisseurs }, [fournisseurs])
  useEffect(() => { categoriesRef.current = categories }, [categories])

  // step: 1=type, 2=upload, 3=validation, 4=résultats
  const [step, setStep] = useState(1)
  const [docType, setDocType] = useState(null)
  const [mouvementType, setMouvementType]             = useState('entree')
  const [refDocument, setRefDocument]                 = useState('')
  const [fournisseurMode, setFournisseurMode]         = useState('none')
  const [fournisseurId, setFournisseurId]             = useState('')
  const [nouveauFournisseurNom, setNouveauFournisseurNom] = useState('')
  const [lignes, setLignes]   = useState([])
  const [applying, setApplying] = useState(false)
  const [results, setResults]   = useState([])

  useEffect(() => {
    dispatch(fetchProduits())
    dispatch(fetchFournisseurs())
    dispatch(fetchCategories())
  }, [dispatch])

  // Restore step on mount: if scan is in-flight or failed while user navigated away
  useEffect(() => {
    if ((stockOcrLoading || stockOcrError) && stockOcrDocType) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setDocType(stockOcrDocType)
      setStep(2)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!stockOcrResult) return
const cp = produitsRef.current
    const cf = fournisseursRef.current
    const cc = categoriesRef.current
    // Restore docType from Redux so purchase-doc rules survive navigation
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (stockOcrDocType) setDocType(stockOcrDocType)
    // OCR mouvement_suggere takes priority; doc_type was already used as hint
    setMouvementType(stockOcrResult.mouvement_suggere || 'entree')
    setRefDocument(stockOcrResult.reference_document || '')
    const nomOcr = (stockOcrResult.fournisseur || '').toLowerCase().trim()
    if (!nomOcr) {
      setFournisseurMode('none')
    } else {
      const matched = cf.find(f => f.nom.toLowerCase().includes(nomOcr) || nomOcr.includes(f.nom.toLowerCase()))
      if (matched) { setFournisseurMode('existing'); setFournisseurId(String(matched.id)) }
      else { setFournisseurMode('new'); setNouveauFournisseurNom(stockOcrResult.fournisseur || '') }
    }
    setLignes((stockOcrResult.lignes || []).map((item, i) => {
      const refLower = (item.reference || '').toLowerCase().trim()
      const nomLower = (item.nom || '').toLowerCase().trim()
      let matched = null
      if (refLower) matched = cp.find(p => (p.sku || '').toLowerCase().trim() === refLower)
      if (!matched && nomLower.length > 2) matched = cp.find(p => p.nom.toLowerCase().includes(nomLower) || nomLower.includes(p.nom.toLowerCase()))

      // Fuzzy match catégorie suggérée contre catégories existantes
      const suggestion = item.categorie_suggeree ?? null
      const catMatch = suggestion
        ? (() => {
            const sug = suggestion.toLowerCase().trim()
            return cc.find(c => {
              const nom = c.nom.toLowerCase()
              return nom === sug || nom.includes(sug) || sug.includes(nom)
            }) ?? null
          })()
        : null

      // Fallback : si l'IA n'a pas suggéré, cherche par mots-clés dans le nom produit
      const keywordMatch = !suggestion
        ? (() => {
            const nom = (item.nom || '').toLowerCase().replace(/[()[\]]/g, ' ')
            let best = null, bestScore = 0
            for (const cat of cc) {
              const catWords = cat.nom.toLowerCase().split(/\s+/).filter(w => w.length >= 4)
              if (!catWords.length) continue
              const matched2 = catWords.filter(cw => nom.includes(cw.slice(0, -1))).length
              const score = matched2 / catWords.length
              if (score === 1.0 && score > bestScore) { bestScore = score; best = cat }
            }
            return best
          })()
        : null

      // Déterminer l'action et la source de la suggestion
      const isNewProduct = !matched  // action === 'create'
      let catAction = 'none', catId = '', catNomNew = '', catSource = null
      if (suggestion && catMatch) {
        catAction = 'existing'; catId = String(catMatch.id); catSource = 'ia'
      } else if (suggestion && !catMatch) {
        catAction = 'create'; catNomNew = suggestion; catSource = 'ia'
      } else if (!suggestion && keywordMatch) {
        catAction = 'existing'; catId = String(keywordMatch.id); catSource = 'keyword'
      } else if (isNewProduct) {
        // Aucune suggestion IA ni match → "Créer" vide plutôt qu'"Ignorer"
        catAction = 'create'; catNomNew = ''; catSource = null
      }

      return {
        id: i, ref_ocr: item.reference || '', nom_ocr: item.nom || '',
        quantite: Math.max(1, parseInt(item.quantite) || 1),
        prix_unitaire: item.prix_unitaire_ht > 0 ? String(item.prix_unitaire_ht) : '',
        action: matched ? 'match' : 'create',
        produit_id: matched ? String(matched.id) : '',
        tva: item.tva ?? null,
        update_tva: false,
        nouveau_nom: item.nom || '', nouveau_sku: item.reference || '',
        nouveau_prix_achat: item.prix_unitaire_ht > 0 ? String(item.prix_unitaire_ht) : '',
        nouveau_prix_vente: '',
        // Catégorie
        categorie_suggeree: suggestion,
        categorie_source: catSource,
        categorie_action: catAction,
        categorie_id: catId,
        categorie_nom_new: catNomNew,
      }
    }))
    setStep(3)
  }, [stockOcrResult]) // eslint-disable-line react-hooks/exhaustive-deps

  // Conservé pour usage futur (préfixe _ : non branché pour l'instant)
  const _fuzzyMatchCategorie = useCallback((suggestion) => {
    if (!suggestion) return null
    const sug = suggestion.toLowerCase().trim()
    const cats = categoriesRef.current
    return cats.find(c => {
      const nom = c.nom.toLowerCase()
      return nom === sug || nom.includes(sug) || sug.includes(nom)
    }) ?? null
  }, [])

  // Fallback : cherche une catégorie existante à partir des mots du nom produit
  // Conservé pour usage futur (préfixe _ : non branché pour l'instant)
  const _keywordMatchFromName = useCallback((productName) => {
    if (!productName) return null
    const nom = productName.toLowerCase().replace(/[()[\]]/g, ' ')
    const cats = categoriesRef.current
    let best = null
    let bestScore = 0
    for (const cat of cats) {
      const catWords = cat.nom.toLowerCase().split(/\s+/).filter(w => w.length >= 4)
      if (!catWords.length) continue
      const matched = catWords.filter(cw => nom.includes(cw.slice(0, -1))).length
      const score = matched / catWords.length
      if (score === 1.0 && score > bestScore) { bestScore = score; best = cat }
    }
    return best
  }, [])

  const handleSelectDocType = useCallback((type) => {
    setDocType(type.value)
    if (type.mouvement) setMouvementType(type.mouvement)
    setStep(2)
  }, [])

  const processFile = useCallback((file) => {
    if (!file) return
    dispatch(clearStockOcrResult())
    dispatch(processOcrStockDocument({ file, docType: docType || '' }))
  }, [dispatch, docType])

  const handleReset = () => {
    dispatch(clearStockOcrResult())
    setStep(1); setDocType(null); setLignes([]); setResults([])
  }

  const handleNewFile = () => {
    dispatch(clearStockOcrResult())
    setStep(2); setLignes([]); setResults([])
  }

  const updateLigne = (idx, updates) =>
    setLignes(prev => prev.map((l, i) => i === idx ? { ...l, ...updates } : l))

  const handleApply = async () => {
    setApplying(true)
    const log = []
    const categoryCache = {}  // nom → id, évite créations doublons dans un même import

    const resolveCategorie = async (ligne) => {
      if (ligne.categorie_action === 'existing' && ligne.categorie_id) {
        return parseInt(ligne.categorie_id)
      }
      if (ligne.categorie_action === 'create' && ligne.categorie_nom_new?.trim()) {
        const nom = ligne.categorie_nom_new.trim()
        if (categoryCache[nom]) return categoryCache[nom]
        try {
          const res = await stockApi.createCategorie({ nom })
          categoryCache[nom] = res.data.id
          return res.data.id
        } catch {
          // Catégorie déjà existante (race) → chercher par nom
          const existing = categoriesRef.current.find(
            c => c.nom.toLowerCase() === nom.toLowerCase()
          )
          if (existing) { categoryCache[nom] = existing.id; return existing.id }
        }
      }
      return null
    }

    try {
      let resolvedFournisseurId = null
      if (fournisseurMode === 'existing' && fournisseurId) {
        resolvedFournisseurId = parseInt(fournisseurId)
        const found = fournisseurs.find(f => f.id === resolvedFournisseurId)
        log.push({ ok: true, label: `Fournisseur "${found?.nom}"`, msg: 'Sélectionné' })
      } else if (fournisseurMode === 'new' && nouveauFournisseurNom.trim()) {
        try {
          const res = await stockApi.createFournisseur({ nom: nouveauFournisseurNom.trim() })
          resolvedFournisseurId = res.data.id
          log.push({ ok: true, label: `Fournisseur "${nouveauFournisseurNom.trim()}"`, msg: 'Créé' })
        } catch (e) {
          const msg = e.response?.data?.nom?.[0] ?? e.response?.data?.detail ?? 'Erreur inconnue'
          log.push({ ok: false, label: `Fournisseur "${nouveauFournisseurNom.trim()}"`, msg })
        }
      }
      for (const ligne of lignes) {
        const label = ligne.nom_ocr || ligne.ref_ocr || `Ligne #${ligne.id + 1}`
        if (ligne.action === 'skip') { log.push({ ok: null, label, msg: 'Ignoré' }); continue }
        let produitId = null
        if (ligne.action === 'match') {
          if (!ligne.produit_id) { log.push({ ok: false, label, msg: 'Aucun produit sélectionné' }); continue }
          produitId = parseInt(ligne.produit_id)
          const patchData = {}
          // Mettre à jour la catégorie du produit existant si une est choisie
          if (ligne.categorie_action !== 'none') {
            const catId = await resolveCategorie(ligne)
            if (catId) patchData.categorie_id = catId
          }
          // Mettre à jour la TVA si divergence et utilisateur a coché l'option
          if (ligne.update_tva && ligne.tva !== null && ligne.tva !== undefined) {
            patchData.tva = ligne.tva
          }
          // Assigner le fournisseur si le produit n'en a pas encore
          if (resolvedFournisseurId) {
            const existingProd = produitsRef.current.find(p => p.id === produitId)
            if (!existingProd?.fournisseur) patchData.fournisseur_id = resolvedFournisseurId
          }
          if (Object.keys(patchData).length > 0) {
            try { await stockApi.patchProduit(produitId, patchData) } catch { /* patch optionnel */ }
          }
        } else {
          if (!ligne.nouveau_nom.trim()) { log.push({ ok: false, label, msg: 'Nom du produit requis' }); continue }
          const isPurchaseDoc = docType === 'facture_achat' || docType === 'bon_livraison'
          const prixAchat = parseFloat(ligne.nouveau_prix_achat) || 0
          const prixVente = isPurchaseDoc
            ? (parseFloat(ligne.nouveau_prix_vente) || 0)
            : (parseFloat(ligne.nouveau_prix_vente) || prixAchat)
          if (!isPurchaseDoc && prixVente <= 0) { log.push({ ok: false, label, msg: 'Prix de vente requis (> 0)' }); continue }
          try {
            const catId = await resolveCategorie(ligne)
            const payload = { nom: ligne.nouveau_nom.trim(), prix_achat: prixAchat, prix_vente: prixVente, quantite_stock: 0, seuil_alerte: 0 }
            if (ligne.nouveau_sku.trim()) payload.sku = ligne.nouveau_sku.trim()
            if (resolvedFournisseurId) payload.fournisseur_id = resolvedFournisseurId
            if (ligne.tva != null) payload.tva = ligne.tva
            if (catId) payload.categorie_id = catId
            const res = await stockApi.createProduit(payload)
            produitId = res.data.id
          } catch (e) {
            const d = e.response?.data
            log.push({ ok: false, label, msg: `Création produit : ${d?.nom?.[0] ?? d?.sku?.[0] ?? d?.detail ?? JSON.stringify(d ?? e.message)}` })
            continue
          }
        }
        try {
          const res = await stockApi.createMouvement({ produit: produitId, type_mouvement: mouvementType, quantite: ligne.quantite, reference: refDocument.trim() || null, note: `Import OCR${ligne.ref_ocr ? ' — ' + ligne.ref_ocr : ''}` })
          const mv = res.data
          const delta = mv.quantite_apres - mv.quantite_avant
          const typeLabel = mouvementType === 'entree' ? 'Entrée' : mouvementType === 'sortie' ? 'Sortie' : 'Ajust.'
          const prev = log[log.length - 1]
          if (prev && prev.label === label && prev.ok === true) {
            prev.msg += ` — ${typeLabel} ${delta >= 0 ? '+' : ''}${delta} (stock : ${mv.quantite_avant} → ${mv.quantite_apres})`
          } else {
            log.push({ ok: true, label, msg: `${typeLabel} ${delta >= 0 ? '+' : ''}${delta} (stock : ${mv.quantite_avant} → ${mv.quantite_apres})` })
          }
        } catch (e) {
          const d = e.response?.data
          log.push({ ok: false, label, msg: `Mouvement : ${d?.detail ?? d?.quantite?.[0] ?? d?.non_field_errors?.[0] ?? JSON.stringify(d ?? e.message)}` })
        }
      }
    } finally {
      setResults(log); setApplying(false); setStep(4)
      dispatch(fetchProduits()); dispatch(fetchFournisseurs()); dispatch(fetchCategories()); dispatch(fetchMouvements())
    }
  }

  if (role !== 'responsable' && role !== 'admin') {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
        Accès réservé aux responsables et administrateurs.
      </div>
    )
  }

  const currentDocType = DOC_TYPES.find(t => t.value === docType)

  return (
    <div style={{ padding: '1.5rem', maxWidth: 860, margin: '0 auto' }}>

      {/* Page header */}
      <div style={{ marginBottom: '1.75rem' }}>
        <h2 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 700, color: '#0f172a' }}>
          Import OCR — Stock
        </h2>
        <p style={{ margin: '4px 0 0', fontSize: '0.82rem', color: '#64748b' }}>
          Choisissez le type de document puis scannez-le pour mettre à jour le stock automatiquement.
        </p>
      </div>

      <Stepper step={step} />

      <div key={step} style={{ animation: 'ocrStepIn 0.32s cubic-bezier(0.16,1,0.3,1) both' }}>
        {step === 1 && (
          <Step0DocType
            selectedValue={docType}
            onSelect={handleSelectDocType}
          />
        )}
        {step === 2 && (
          <Step1Upload
            loading={stockOcrLoading} error={stockOcrError}
            onFile={processFile}
            onReset={handleReset}
            docType={currentDocType}
          />
        )}
        {step === 3 && stockOcrResult && (
          <Step2Validate
            result={stockOcrResult} produits={produits} fournisseurs={fournisseurs} categories={categories}
            mouvementType={mouvementType} setMouvementType={setMouvementType}
            refDocument={refDocument} setRefDocument={setRefDocument}
            fournisseurMode={fournisseurMode} setFournisseurMode={setFournisseurMode}
            fournisseurId={fournisseurId} setFournisseurId={setFournisseurId}
            nouveauFournisseurNom={nouveauFournisseurNom} setNouveauFournisseurNom={setNouveauFournisseurNom}
            lignes={lignes} updateLigne={updateLigne}
            onReset={handleReset} onApply={handleApply} applying={applying}
            docType={docType}
          />
        )}
        {step === 4 && (
          <Step3Results results={results} onReset={handleReset}
            onNewFile={handleNewFile}
            onViewMovements={() => navigate('/stock/mouvements')}
          />
        )}
      </div>

      <style>{`
        @keyframes ocrStepIn {
          from { opacity: 0; transform: translateY(14px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes ocrSpin {
          to { transform: rotate(360deg); }
        }
        @keyframes ocrPulse {
          0%,100% { opacity: 1; } 50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  )
}

// ── Étape 0 : Sélection du type de document ───────────────────────────────────
function Step0DocType({ selectedValue, onSelect }) {
  return (
    <div>
      <div style={{ marginBottom: '1.25rem' }}>
        <p style={{ margin: 0, fontSize: '0.9rem', fontWeight: 600, color: '#1e293b' }}>
          Quel type de document allez-vous importer ?
        </p>
        <p style={{ margin: '4px 0 0', fontSize: '0.8rem', color: '#94a3b8' }}>
          Ce choix aide l'IA à mieux extraire les informations et pré-configure le mouvement de stock.
        </p>
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))',
        gap: '0.85rem',
      }}>
        {DOC_TYPES.map(type => {
          const isSelected = selectedValue === type.value
          return (
            <button
              key={type.value}
              type="button"
              onClick={() => onSelect(type)}
              style={{
                position: 'relative',
                display: 'flex', flexDirection: 'column', alignItems: 'flex-start',
                gap: '0.75rem', padding: '1.25rem',
                borderRadius: 14, cursor: 'pointer', textAlign: 'left',
                border: `2px solid ${isSelected ? type.activeBorder : type.border}`,
                background: isSelected ? type.bg : '#fff',
                transition: 'all 0.18s cubic-bezier(0.4,0,0.2,1)',
                boxShadow: isSelected ? `0 0 0 3px ${type.color}22` : '0 1px 3px rgba(0,0,0,0.06)',
                transform: isSelected ? 'translateY(-1px)' : 'translateY(0)',
              }}
              onMouseEnter={e => { if (!isSelected) e.currentTarget.style.borderColor = type.activeBorder }}
              onMouseLeave={e => { if (!isSelected) e.currentTarget.style.borderColor = type.border }}
            >
              {/* Icon */}
              <div style={{
                width: 48, height: 48, borderRadius: 12,
                background: isSelected ? type.bg : '#f8fafc',
                border: `1.5px solid ${isSelected ? type.border : '#e2e8f0'}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: isSelected ? type.color : '#94a3b8',
                transition: 'all 0.18s',
              }}>
                {type.icon}
              </div>

              {/* Text */}
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: isSelected ? type.color : '#1e293b', marginBottom: 3 }}>
                  {type.label}
                </div>
                <div style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.4 }}>
                  {type.desc}
                </div>
              </div>

              {/* Mouvement badge */}
              {type.mouvement && (
                <div style={{
                  alignSelf: 'flex-start',
                  padding: '2px 10px', borderRadius: 20,
                  background: type.mouvement === 'entree' ? '#f0fdf4' : '#fffbeb',
                  border: `1px solid ${type.mouvement === 'entree' ? '#bbf7d0' : '#fde68a'}`,
                  fontSize: 11, fontWeight: 500,
                  color: type.mouvement === 'entree' ? '#15803d' : '#a16207',
                }}>
                  {type.mouvement === 'entree' ? '↑ Entrée stock' : '↓ Sortie stock'}
                </div>
              )}

              {/* Selected checkmark */}
              {isSelected && (
                <div style={{
                  position: 'absolute', top: 10, right: 10,
                  width: 20, height: 20, borderRadius: '50%',
                  background: type.color,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <svg width={11} height={11} viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                </div>
              )}
            </button>
          )
        })}
      </div>

      <p style={{ marginTop: '1.25rem', fontSize: '0.78rem', color: '#cbd5e1', textAlign: 'center' }}>
        Cliquez sur un type pour passer à l'étape suivante
      </p>
    </div>
  )
}

// ── Étape 1 (ex-Step1) : Upload ───────────────────────────────────────────────
function Step1Upload({ loading, error, onFile, onReset, docType }) {

  if (loading) return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      minHeight: 280, gap: 20,
    }}>
      <div style={{
        width: 52, height: 52, borderRadius: '50%',
        border: '3px solid #e2e8f0', borderTopColor: '#1d4ed8',
        animation: 'ocrSpin 0.8s linear infinite',
      }}/>
      <div style={{ textAlign: 'center' }}>
        <p style={{ margin: 0, fontWeight: 600, fontSize: '0.95rem', color: '#1e293b' }}>
          Analyse OCR en cours
        </p>
        <p style={{ margin: '5px 0 0', fontSize: '0.8rem', color: '#94a3b8', animation: 'ocrPulse 1.8s ease infinite' }}>
          Extraction des produits, quantités et références…
        </p>
      </div>
      <div style={{ display: 'flex', gap: 20, marginTop: 4 }}>
        {['Lecture document', 'Détection produits', 'Structuration'].map((label, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: '#94a3b8' }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#cbd5e1', animation: `ocrPulse 1.8s ease ${i * 0.4}s infinite` }}/>
            {label}
          </div>
        ))}
      </div>
    </div>
  )

  if (error && !loading) return (
    <div style={{
      background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 12,
      padding: '1.5rem', display: 'flex', gap: 14, alignItems: 'flex-start',
    }}>
      <div style={{
        width: 40, height: 40, borderRadius: 10, background: '#fee2e2',
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
      }}>
        <Ic size={20} color="#dc2626">
          <circle cx="12" cy="12" r="10"/>
          <line x1="15" y1="9" x2="9" y2="15"/>
          <line x1="9" y1="9" x2="15" y2="15"/>
        </Ic>
      </div>
      <div style={{ flex: 1 }}>
        <p style={{ margin: '0 0 4px', fontWeight: 600, fontSize: '0.9rem', color: '#b91c1c' }}>
          Erreur d'analyse
        </p>
        <p style={{ margin: '0 0 12px', fontSize: '0.82rem', color: '#dc2626' }}>
          {typeof error === 'string' ? error : JSON.stringify(error)}
        </p>
        <button
          onClick={onReset}
          style={{
            padding: '6px 16px', borderRadius: 8, border: '1.5px solid #fca5a5',
            background: '#fff', color: '#dc2626', fontSize: 13, fontWeight: 500,
            cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6,
          }}
        >
          <Ic size={14} color="#dc2626"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3"/></Ic>
          Recommencer
        </button>
      </div>
    </div>
  )

  return (
    <div>
      {/* Doc type reminder */}
      {docType && (
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 8,
          padding: '6px 14px', borderRadius: 20, marginBottom: '1rem',
          background: docType.bg, border: `1.5px solid ${docType.border}`,
          fontSize: 13, fontWeight: 500, color: docType.color,
        }}>
          <span style={{ display: 'flex', color: docType.color }}>{docType.icon}</span>
          {docType.label}
          <button onClick={onReset} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, marginLeft: 4, display: 'flex', color: '#94a3b8', fontSize: 11 }}>
            ✕ changer
          </button>
        </div>
      )}

      {/* G26 — primitif FileUpload ; même dispatch OCR (onFile → processFile). */}
      <FileUpload
        accept={STOCK_OCR_ACCEPT}
        maxSize={STOCK_OCR_MAX_SIZE}
        onFiles={(files) => onFile(files[0])}
      />
    </div>
  )
}

// ── Étape 2 (ex-Step2) : Validation ───────────────────────────────────────────
function Step2Validate({
  result, produits, fournisseurs, categories,
  mouvementType, setMouvementType, refDocument, setRefDocument,
  fournisseurMode, setFournisseurMode, fournisseurId, setFournisseurId,
  nouveauFournisseurNom, setNouveauFournisseurNom,
  lignes, updateLigne, onReset, onApply, applying,
  docType,
}) {
  const showFournisseur = docType !== 'bon_sortie'
  // For purchase/delivery docs, prix_vente is not required (falls back to prix_achat)
  const requiresPrixVente = docType === 'bon_sortie' || docType === 'autre' || !docType

  const hasErrors = lignes.filter(l => l.action !== 'skip').some(l => {
    if (l.action === 'match' && !l.produit_id) return true
    if (l.action === 'create') {
      if (!l.nouveau_nom.trim()) return true
      if (requiresPrixVente && !(parseFloat(l.nouveau_prix_vente) > 0)) return true
    }
    return false
  })
  const pct = Math.round(result.confiance * 100)
  const confColor = pct >= 80 ? { bg: '#f0fdf4', text: '#166534', dot: '#16a34a' }
    : pct >= 50   ? { bg: '#fefce8', text: '#854d0e', dot: '#ca8a04' }
    :               { bg: '#fef2f2', text: '#991b1b', dot: '#dc2626' }

  const docTypeCfg = DOC_TYPES.find(t => t.value === docType)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>

      {/* ── Document info card ── */}
      <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e2e8f0', padding: '1.1rem 1.25rem' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8, marginBottom: '1rem' }}>
          {/* Doc type chosen badge */}
          {docTypeCfg && (
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: 5,
              padding: '3px 10px', borderRadius: 20, fontSize: 12, fontWeight: 500,
              background: docTypeCfg.bg, color: docTypeCfg.color,
              border: `1px solid ${docTypeCfg.border}`,
            }}>
              {docTypeCfg.label}
            </span>
          )}
          {/* OCR document type badge */}
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            padding: '3px 10px', borderRadius: 20, fontSize: 12, fontWeight: 500,
            background: '#eff6ff', color: '#1d4ed8',
          }}>
            <Ic size={12} color="#1d4ed8" sw={2}>
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </Ic>
            {DOC_LABELS[result.type_document] ?? result.type_document}
          </span>

          {/* Confidence badge */}
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            padding: '3px 10px', borderRadius: 20, fontSize: 12, fontWeight: 500,
            background: confColor.bg, color: confColor.text,
          }}>
            <div style={{ width: 7, height: 7, borderRadius: '50%', background: confColor.dot }}/>
            Confiance {pct}%
          </span>

          <span style={{ fontSize: 12, color: '#94a3b8', marginLeft: 'auto' }}>
            {lignes.length} ligne{lignes.length > 1 ? 's' : ''} détectée{lignes.length > 1 ? 's' : ''}
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.85rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 5 }}>
              Type de mouvement
            </label>
            <select className="form-select" value={mouvementType} onChange={e => setMouvementType(e.target.value)}>
              <option value="entree">Entrée (ajoute au stock)</option>
              <option value="sortie">Sortie (retire du stock)</option>
              <option value="ajustement">Ajustement (fixe le stock)</option>
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 5 }}>
              Référence document
            </label>
            <input className="form-control" value={refDocument} onChange={e => setRefDocument(e.target.value)} placeholder="N° BL, facture…"/>
          </div>
        </div>
      </div>

      {/* ── Fournisseur card — masqué pour bon de sortie ── */}
      {showFournisseur && (
        <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e2e8f0', padding: '1.1rem 1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: '0.85rem' }}>
            <Ic size={15} color="#64748b">
              <rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>
            </Ic>
            <span style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Fournisseur</span>
            {result.fournisseur && (
              <span style={{ fontSize: 12, color: '#94a3b8' }}>— détecté : « {result.fournisseur} »</span>
            )}
          </div>

          <div style={{ display: 'flex', gap: 6, marginBottom: '0.85rem', flexWrap: 'wrap' }}>
            {[
              { value: 'existing', label: 'Fournisseur existant' },
              { value: 'new',      label: 'Nouveau fournisseur' },
              { value: 'none',     label: 'Sans fournisseur' },
            ].map(opt => (
              <button key={opt.value} type="button" onClick={() => setFournisseurMode(opt.value)} style={{
                padding: '5px 14px', borderRadius: 20, cursor: 'pointer', fontSize: 12.5, fontWeight: 500,
                border: `1.5px solid ${fournisseurMode === opt.value ? '#1d4ed8' : '#e2e8f0'}`,
                background: fournisseurMode === opt.value ? '#eff6ff' : '#fff',
                color: fournisseurMode === opt.value ? '#1d4ed8' : '#64748b',
                transition: 'all 0.15s',
              }}>{opt.label}</button>
            ))}
          </div>

          {fournisseurMode === 'existing' && (
            <select className="form-select" value={fournisseurId} onChange={e => setFournisseurId(e.target.value)}>
              <option value="">— Sélectionner un fournisseur —</option>
              {fournisseurs.map(f => <option key={f.id} value={f.id}>{f.nom}</option>)}
            </select>
          )}
          {fournisseurMode === 'new' && (
            <input className="form-control" value={nouveauFournisseurNom} onChange={e => setNouveauFournisseurNom(e.target.value)} placeholder="Nom du fournisseur"/>
          )}
        </div>
      )}

      {/* ── Lignes produits ── */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: '0.75rem' }}>
          <Ic size={15} color="#64748b">
            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
            <polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>
          </Ic>
          <span style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>
            Lignes produits ({lignes.length})
          </span>
        </div>

        {lignes.length === 0 ? (
          <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 10, padding: '1rem 1.25rem', fontSize: 13, color: '#92400e', display: 'flex', gap: 8, alignItems: 'center' }}>
            <Ic size={16} color="#d97706"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></Ic>
            Aucune ligne produit détectée. Vérifiez la qualité du document.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {lignes.map((ligne, idx) => (
              <LigneCard key={ligne.id} ligne={ligne} produits={produits} categories={categories} onChange={u => updateLigne(idx, u)} docType={docType}/>
            ))}
          </div>
        )}
      </div>

      {/* ── Actions ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '1rem', borderTop: '1px solid #f1f5f9' }}>
        <button onClick={onReset} disabled={applying} style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          padding: '8px 16px', borderRadius: 8, border: '1.5px solid #e2e8f0',
          background: '#fff', color: '#64748b', fontSize: 13.5, fontWeight: 500,
          cursor: applying ? 'not-allowed' : 'pointer', opacity: applying ? 0.5 : 1,
        }}>
          <Ic size={14} color="#64748b"><polyline points="15 18 9 12 15 6"/></Ic>
          Recommencer
        </button>
        <button onClick={onApply} disabled={applying || hasErrors || lignes.length === 0} style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          padding: '9px 22px', borderRadius: 8, border: 'none',
          background: (applying || hasErrors || lignes.length === 0) ? '#93c5fd' : 'linear-gradient(135deg,#1d4ed8,#2563eb)',
          color: '#fff', fontSize: 13.5, fontWeight: 600,
          cursor: (applying || hasErrors || lignes.length === 0) ? 'not-allowed' : 'pointer',
          boxShadow: (applying || hasErrors || lignes.length === 0) ? 'none' : '0 4px 14px rgba(29,78,216,0.35)',
          transition: 'opacity 0.2s',
        }}>
          {applying
            ? <><div style={{ width: 14, height: 14, border: '2px solid rgba(255,255,255,0.4)', borderTopColor: '#fff', borderRadius: '50%', animation: 'ocrSpin 0.7s linear infinite' }}/> Application en cours…</>
            : <>Appliquer les mouvements <Ic size={14} color="#fff"><polyline points="9 18 15 12 9 6"/></Ic></>
          }
        </button>
      </div>
    </div>
  )
}

// ── Carte ligne produit ───────────────────────────────────────────────────────
function LigneCard({ ligne, produits, categories, onChange, docType }) {
  const isPurchase = docType === 'facture_achat' || docType === 'bon_livraison'
  const hasMatchError  = ligne.action === 'match' && !ligne.produit_id
  const hasCreateError = ligne.action === 'create' && (
    !ligne.nouveau_nom.trim() ||
    (!isPurchase && !(parseFloat(ligne.nouveau_prix_vente) > 0))
  )
  const isSkipped = ligne.action === 'skip'

  const matchedProduit = (ligne.action === 'match' && ligne.produit_id)
    ? produits.find(p => String(p.id) === ligne.produit_id)
    : null
  const produitTva = matchedProduit ? (matchedProduit.tva != null ? Number(matchedProduit.tva) : null) : null
  const ocrTva = (ligne.tva !== null && ligne.tva !== undefined) ? Number(ligne.tva) : null
  const tvaDivergence = matchedProduit && ocrTva !== null && produitTva !== ocrTva

  const ACTION_CFG = {
    match:  { label: 'Associer',    activeColor: '#1d4ed8', activeBg: '#eff6ff' },
    create: { label: 'Créer',       activeColor: '#059669', activeBg: '#f0fdf4' },
    skip:   { label: 'Ignorer',     activeColor: '#64748b', activeBg: '#f8fafc' },
  }

  return (
    <div style={{
      background: isSkipped ? '#f8fafc' : '#fff',
      borderRadius: 12,
      border: `1.5px solid ${hasMatchError || hasCreateError ? '#fca5a5' : isSkipped ? '#e2e8f0' : '#e2e8f0'}`,
      padding: '1rem 1.1rem',
      opacity: isSkipped ? 0.6 : 1,
      transition: 'opacity 0.2s, border-color 0.2s',
    }}>
      {/* Header: OCR info + quantity */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: '0.85rem' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6 }}>
            {ligne.ref_ocr && (
              <span style={{ padding: '2px 8px', borderRadius: 5, background: '#f1f5f9', fontSize: 11, fontFamily: 'monospace', color: '#475569' }}>
                {ligne.ref_ocr}
              </span>
            )}
            <span style={{ fontSize: 14, fontWeight: 600, color: '#1e293b' }}>
              {ligne.nom_ocr || '—'}
            </span>
          </div>
          {ligne.prix_unitaire && (
            <p style={{ margin: '3px 0 0', fontSize: 11.5, color: '#94a3b8' }}>
              Prix achat HT détecté : {ligne.prix_unitaire} DH
              {ligne.tva != null && (
                <span style={{ marginLeft: 6, color: '#0ea5e9' }}>
                  · TVA {ligne.tva}% · TTC {(parseFloat(ligne.prix_unitaire) * (1 + ligne.tva / 100)).toFixed(2)} DH
                </span>
              )}
            </p>
          )}
        </div>
        <div style={{ flexShrink: 0, textAlign: 'right' }}>
          <label style={{ display: 'block', fontSize: 11, color: '#94a3b8', fontWeight: 500, marginBottom: 4 }}>Qté</label>
          <input
            type="number" min="1" step="1"
            className="form-control"
            style={{ width: 72, textAlign: 'right' }}
            value={ligne.quantite}
            onChange={e => onChange({ quantite: Math.max(1, parseInt(e.target.value) || 1) })}
          />
        </div>
      </div>

      {/* Action pill selector */}
      <div style={{ display: 'flex', gap: 6, marginBottom: '0.85rem' }}>
        {Object.entries(ACTION_CFG).map(([value, cfg]) => {
          const isActive = ligne.action === value
          return (
            <button key={value} type="button" onClick={() => onChange({ action: value })} style={{
              padding: '4px 13px', borderRadius: 20, cursor: 'pointer',
              fontSize: 12, fontWeight: 500,
              border: `1.5px solid ${isActive ? cfg.activeColor : '#e2e8f0'}`,
              background: isActive ? cfg.activeBg : '#fff',
              color: isActive ? cfg.activeColor : '#64748b',
              transition: 'all 0.15s',
            }}>{cfg.label}</button>
          )
        })}
      </div>

      {/* Match: select existing product */}
      {ligne.action === 'match' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <select
            className={`form-select${hasMatchError ? ' is-invalid' : ''}`}
            value={ligne.produit_id}
            onChange={e => onChange({ produit_id: e.target.value })}
          >
            <option value="">— Sélectionner un produit existant —</option>
            {produits.map(p => (
              <option key={p.id} value={p.id}>{p.nom}{p.sku ? ` (${p.sku})` : ''} — stock : {p.quantite_stock}</option>
            ))}
          </select>
          {hasMatchError && <p style={{ margin: '4px 0 0', fontSize: 11.5, color: '#dc2626' }}>Sélectionnez un produit existant</p>}

          {/* Fournisseur existant du produit */}
          {matchedProduit?.fournisseur && (
            <div style={{ padding: '5px 10px', background: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: 6, fontSize: 11.5, color: '#0369a1', display: 'flex', alignItems: 'center', gap: 5 }}>
              <Ic size={12} color="#0ea5e9"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></Ic>
              Fournisseur enregistré : <strong style={{ marginLeft: 3 }}>{matchedProduit.fournisseur.nom}</strong>
            </div>
          )}

          {/* Divergence TVA */}
          {tvaDivergence && (
            <div style={{ padding: '0.65rem 0.9rem', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#92400e', fontWeight: 600 }}>
                <Ic size={13} color="#d97706"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></Ic>
                Divergence TVA — produit enregistré : {produitTva != null ? `${produitTva}%` : 'sans TVA'} · document détecte : {ocrTva}%
              </div>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#78350f', cursor: 'pointer' }}>
                <input type="checkbox" checked={!!ligne.update_tva} onChange={e => onChange({ update_tva: e.target.checked })}/>
                Mettre à jour la TVA du produit à {ocrTva}%
              </label>
            </div>
          )}
        </div>
      )}

      {/* Catégorie — toujours visible pour "create", visible pour "match" si suggestion */}
      {ligne.action !== 'skip' && (ligne.action === 'create' || ligne.categorie_suggeree || ligne.categorie_source === 'keyword') && (
        <div style={{ marginTop: 8, padding: '0.75rem 0.9rem', background: '#fafafa', borderRadius: 8, border: '1px solid #e2e8f0' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 11.5, fontWeight: 600, color: '#374151' }}>Catégorie</span>
            {ligne.categorie_source === 'ia' && ligne.categorie_suggeree && (
              <span style={{ fontSize: 11, color: '#94a3b8' }}>— IA suggère : « {ligne.categorie_suggeree} »</span>
            )}
            {ligne.categorie_source === 'keyword' && ligne.categorie_action === 'existing' && (
              <span style={{ fontSize: 11, color: '#0ea5e9' }}>
                — Détecté depuis le nom du produit
              </span>
            )}
          </div>
          <div style={{ display: 'flex', gap: 5, marginBottom: 6, flexWrap: 'wrap' }}>
            {[
              { value: 'existing', label: 'Existante' },
              { value: 'create',   label: 'Créer' },
              { value: 'none',     label: 'Ignorer' },
            ].map(opt => (
              <button key={opt.value} type="button"
                onClick={() => onChange({ categorie_action: opt.value })}
                style={{
                  padding: '3px 11px', borderRadius: 20, cursor: 'pointer', fontSize: 11.5, fontWeight: 500,
                  border: `1.5px solid ${ligne.categorie_action === opt.value ? '#7c3aed' : '#e2e8f0'}`,
                  background: ligne.categorie_action === opt.value ? '#f5f3ff' : '#fff',
                  color: ligne.categorie_action === opt.value ? '#7c3aed' : '#64748b',
                  transition: 'all 0.15s',
                }}>{opt.label}</button>
            ))}
          </div>
          {ligne.categorie_action === 'existing' && (
            <select className="form-select" style={{ fontSize: 12.5 }}
              value={ligne.categorie_id}
              onChange={e => onChange({ categorie_id: e.target.value })}>
              <option value="">— Sélectionner une catégorie —</option>
              {categories.map(c => <option key={c.id} value={c.id}>{c.nom}</option>)}
            </select>
          )}
          {ligne.categorie_action === 'create' && (
            <input className="form-control" style={{ fontSize: 12.5 }}
              value={ligne.categorie_nom_new}
              onChange={e => onChange({ categorie_nom_new: e.target.value })}
              placeholder="Nom de la nouvelle catégorie" />
          )}
        </div>
      )}

      {/* Create: new product form */}
      {ligne.action === 'create' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.7rem', background: '#f8fafc', borderRadius: 10, padding: '0.85rem', marginTop: 2 }}>
          <div style={{ gridColumn: '1 / -1' }}>
            <label style={{ display: 'block', fontSize: 11.5, fontWeight: 600, color: '#374151', marginBottom: 4 }}>Nom <span style={{ color: '#dc2626' }}>*</span></label>
            <input className="form-control" value={ligne.nouveau_nom} onChange={e => onChange({ nouveau_nom: e.target.value })} placeholder="Nom du produit"/>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 11.5, fontWeight: 600, color: '#374151', marginBottom: 4 }}>SKU / Référence</label>
            <input className="form-control" value={ligne.nouveau_sku} onChange={e => onChange({ nouveau_sku: e.target.value })} placeholder="ART-001"/>
            {!ligne.ref_ocr && (
              <p style={{ margin: '3px 0 0', fontSize: 11, color: '#94a3b8' }}>
                Aucun code article dans le document — saisissez-en un manuellement si disponible.
              </p>
            )}
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 11.5, fontWeight: 600, color: '#374151', marginBottom: 4 }}>
              Prix achat HT (DH)
              {ligne.tva != null && (
                <span style={{ marginLeft: 6, fontWeight: 400, color: '#6b7280' }}>
                  · TVA {ligne.tva}%
                  {parseFloat(ligne.nouveau_prix_achat) > 0 && (
                    <span style={{ color: '#0ea5e9' }}>
                      {' '}→ TTC {(parseFloat(ligne.nouveau_prix_achat) * (1 + ligne.tva / 100)).toFixed(2)} DH
                    </span>
                  )}
                </span>
              )}
            </label>
            <input type="number" min="0" step="0.01" className="form-control" value={ligne.nouveau_prix_achat} onChange={e => onChange({ nouveau_prix_achat: e.target.value })} placeholder="0.00"/>
          </div>
          {isPurchase ? (
            <div style={{ gridColumn: '1 / -1' }}>
              <div style={{
                padding: '8px 12px', borderRadius: 8,
                background: '#f0fdf4', border: '1px solid #bbf7d0',
                fontSize: 11.5, color: '#15803d', display: 'flex', alignItems: 'center', gap: 6,
              }}>
                <svg width={13} height={13} viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                Prix de vente à définir plus tard selon votre marge
                {parseFloat(ligne.nouveau_prix_achat) > 0 && (
                  <span style={{ marginLeft: 4, color: '#64748b' }}>
                    (achat HT : {parseFloat(ligne.nouveau_prix_achat).toFixed(2)} DH)
                  </span>
                )}
              </div>
            </div>
          ) : (
            <div style={{ gridColumn: '1 / -1' }}>
              <label style={{ display: 'block', fontSize: 11.5, fontWeight: 600, color: '#374151', marginBottom: 4 }}>
                Prix vente (DH) <span style={{ color: '#dc2626' }}>*</span>
                <span style={{ marginLeft: 6, fontWeight: 400, fontSize: 11, color: '#9ca3af' }}>— selon votre marge</span>
              </label>
              <input type="number" min="0" step="0.01"
                className={`form-control${hasCreateError && !(parseFloat(ligne.nouveau_prix_vente) > 0) ? ' is-invalid' : ''}`}
                value={ligne.nouveau_prix_vente} onChange={e => onChange({ nouveau_prix_vente: e.target.value })} placeholder="Saisir votre prix de vente..."/>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Étape 3 (ex-Step3) : Résultats ───────────────────────────────────────────
function Step3Results({ results, onReset, onNewFile, onViewMovements }) {
  const successCount = results.filter(r => r.ok === true).length
  const errorCount   = results.filter(r => r.ok === false).length
  const skipCount    = results.filter(r => r.ok === null).length
  const allOk        = errorCount === 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>

      {/* Summary banner */}
      <div style={{
        borderRadius: 14, padding: '1.5rem',
        background: allOk ? 'linear-gradient(135deg,#f0fdf4,#dcfce7)' : 'linear-gradient(135deg,#fffbeb,#fef9c3)',
        border: `1px solid ${allOk ? '#bbf7d0' : '#fde68a'}`,
        display: 'flex', alignItems: 'center', gap: 16,
      }}>
        <div style={{
          width: 52, height: 52, borderRadius: 14, flexShrink: 0,
          background: allOk ? '#16a34a' : '#d97706',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          {allOk
            ? <Ic size={26} color="#fff" sw={2.5}><polyline points="20 6 9 17 4 12"/></Ic>
            : <Ic size={26} color="#fff" sw={2}><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></Ic>
          }
        </div>
        <div>
          <p style={{ margin: 0, fontWeight: 700, fontSize: '1rem', color: allOk ? '#166534' : '#92400e' }}>
            {allOk ? 'Import réussi' : `Import terminé avec ${errorCount} erreur${errorCount > 1 ? 's' : ''}`}
          </p>
          <div style={{ display: 'flex', gap: 16, marginTop: 6 }}>
            <span style={{ fontSize: 12.5, color: '#16a34a', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
              <Ic size={13} color="#16a34a" sw={2.5}><polyline points="20 6 9 17 4 12"/></Ic>
              {successCount} succès
            </span>
            {errorCount > 0 && (
              <span style={{ fontSize: 12.5, color: '#dc2626', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
                <Ic size={13} color="#dc2626" sw={2}><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></Ic>
                {errorCount} erreur{errorCount > 1 ? 's' : ''}
              </span>
            )}
            {skipCount > 0 && (
              <span style={{ fontSize: 12.5, color: '#94a3b8', fontWeight: 500 }}>
                {skipCount} ignoré{skipCount > 1 ? 's' : ''}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Results list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {results.map((r, i) => (
          <div key={i} style={{
            display: 'flex', alignItems: 'flex-start', gap: 12,
            padding: '0.75rem 1rem', borderRadius: 10,
            background: r.ok === true ? '#f0fdf4' : r.ok === false ? '#fef2f2' : '#f8fafc',
            border: `1px solid ${r.ok === true ? '#bbf7d0' : r.ok === false ? '#fecaca' : '#e2e8f0'}`,
          }}>
            <div style={{
              width: 26, height: 26, borderRadius: 8, flexShrink: 0,
              background: r.ok === true ? '#dcfce7' : r.ok === false ? '#fee2e2' : '#f1f5f9',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              {r.ok === true  && <Ic size={13} color="#16a34a" sw={2.5}><polyline points="20 6 9 17 4 12"/></Ic>}
              {r.ok === false && <Ic size={13} color="#dc2626" sw={2}><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></Ic>}
              {r.ok === null  && <Ic size={13} color="#94a3b8" sw={2}><polyline points="9 18 15 12 9 6"/></Ic>}
            </div>
            <div>
              <span style={{ fontWeight: 600, fontSize: 13, color: r.ok === true ? '#166534' : r.ok === false ? '#991b1b' : '#64748b' }}>
                {r.label}
              </span>
              <span style={{ fontSize: 12.5, color: r.ok === true ? '#15803d' : r.ok === false ? '#b91c1c' : '#94a3b8', marginLeft: 8 }}>
                — {r.msg}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: 10, paddingTop: '0.5rem', flexWrap: 'wrap' }}>
        <button onClick={onViewMovements} style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          padding: '9px 20px', borderRadius: 8, border: 'none',
          background: 'linear-gradient(135deg,#1d4ed8,#2563eb)',
          color: '#fff', fontSize: 13.5, fontWeight: 600, cursor: 'pointer',
          boxShadow: '0 4px 14px rgba(29,78,216,0.3)',
        }}>
          <Ic size={15} color="#fff">
            <polyline points="17 1 21 5 17 9"/>
            <path d="M3 11V9a4 4 0 0 1 4-4h14"/>
            <polyline points="7 23 3 19 7 15"/>
            <path d="M21 13v2a4 4 0 0 1-4 4H3"/>
          </Ic>
          Voir les mouvements
        </button>
        <button onClick={onNewFile} style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          padding: '9px 20px', borderRadius: 8, border: '1.5px solid #e2e8f0',
          background: '#fff', color: '#475569', fontSize: 13.5, fontWeight: 500, cursor: 'pointer',
        }}>
          <Ic size={15} color="#475569">
            <polyline points="16 16 12 12 8 16"/>
            <line x1="12" y1="12" x2="12" y2="21"/>
            <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/>
          </Ic>
          Nouveau fichier (même type)
        </button>
        <button onClick={onReset} style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          padding: '9px 20px', borderRadius: 8, border: '1.5px solid #e2e8f0',
          background: '#fff', color: '#475569', fontSize: 13.5, fontWeight: 500, cursor: 'pointer',
        }}>
          <Ic size={15} color="#475569"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3"/></Ic>
          Nouvel import
        </button>
      </div>
    </div>
  )
}
