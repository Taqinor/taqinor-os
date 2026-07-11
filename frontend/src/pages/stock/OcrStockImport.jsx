import { useRef, useState, useEffect, useCallback } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import {
  FileText, Truck, PackageMinus, HelpCircle, Check, X, AlertCircle, AlertTriangle,
  ChevronLeft, ChevronRight, RefreshCw, Building2, Repeat, Upload, ArrowDownUp,
} from 'lucide-react'
import { FileUpload } from '../../ui/FileUpload'
import { formatMAD } from '../../lib/format'
import {
  Button, Badge, Spinner, Card, EmptyState,
  Input, Segmented, Checkbox,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
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
import { useCanCreateProduit, useIsAdminOrResponsable } from '../../hooks/useHasPermission'

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
    desc: "Facture reçue d'un fournisseur avec montants HT et TVA",
    mouvement: 'entree',
    icon: FileText,
  },
  {
    value: 'bon_livraison',
    label: 'Bon de livraison',
    desc: 'Livraison fournisseur (les prix peuvent être absents)',
    mouvement: 'entree',
    icon: Truck,
  },
  {
    value: 'bon_sortie',
    label: 'Bon de sortie',
    desc: 'Livraison à un client (sortie de stock)',
    mouvement: 'sortie',
    icon: PackageMinus,
  },
  {
    value: 'autre',
    label: 'Autre document',
    desc: 'Transfert, inventaire ou document non standard',
    mouvement: null,
    icon: HelpCircle,
  },
]

// ── Stepper ───────────────────────────────────────────────────────────────────
function Stepper({ step }) {
  const steps = [
    { label: 'Type',       sub: 'Document' },
    { label: 'Upload',     sub: 'Fichier source' },
    { label: 'Validation', sub: 'Vérification' },
    { label: 'Résultats',  sub: 'Application stock' },
  ]
  return (
    <ol className="mb-8 flex items-start">
      {steps.map((s, i) => {
        const n = i + 1
        const done = n < step
        const active = n === step
        return (
          <li key={n} className={`flex items-start ${i < steps.length - 1 ? 'flex-1' : ''}`}>
            <div className="flex min-w-16 flex-col items-center gap-1.5">
              <span className={[
                'flex size-9 items-center justify-center rounded-full border-2 text-xs font-bold transition-colors',
                done ? 'border-success bg-success text-success-foreground'
                  : active ? 'border-primary bg-primary text-primary-foreground ring-4 ring-primary/15'
                    : 'border-border bg-muted text-muted-foreground',
              ].join(' ')}>
                {done ? <Check className="size-4" /> : n}
              </span>
              <span className="text-center">
                <span className={`block text-xs ${active ? 'font-semibold text-foreground' : done ? 'text-success' : 'text-muted-foreground'}`}>
                  {s.label}
                </span>
                <span className="block text-[10px] text-muted-foreground">{s.sub}</span>
              </span>
            </div>
            {i < steps.length - 1 && (
              <span className="mx-1 mt-4 h-0.5 flex-1 overflow-hidden rounded bg-border">
                <span className={`block h-full rounded bg-success transition-[width] duration-500 ${done ? 'w-full' : 'w-0'}`} />
              </span>
            )}
          </li>
        )
      })}
    </ol>
  )
}

// ── Page principale ───────────────────────────────────────────────────────────
export default function OcrStockImport() {
  const dispatch   = useDispatch()
  const navigate   = useNavigate()
  const produitsRef     = useRef([])
  const fournisseursRef = useRef([])
  // Fournisseur déjà résolu/créé lors d'une première application, réutilisé lors
  // d'un réessai ciblé des échecs pour ne pas le recréer en double (750).
  const resolvedFournisseurRef = useRef(null)

  // ARC47 — accès à l'écran gaté via le hook partagé (responsable/admin).
  const canAccess = useIsAdminOrResponsable()
  // QG5 — la création de produit (ligne « Créer ») est réservée à Directeur +
  // Commercial responsable (miroir UX de la garde backend QG4) ; les autres
  // rôles autorisés à voir cet écran (responsable/admin) ne peuvent que
  // rapprocher un produit existant ou ignorer la ligne.
  const canCreateProduit = useCanCreateProduit()
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
  // 751 — pour un document d'achat, créer un bon de commande fournisseur REÇU
  // (réception en bloc) au lieu de mouvements d'entrée isolés. Off par défaut.
  const [creerBcf, setCreerBcf] = useState(false)

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
        // QG5 — un rôle non autorisé à créer un produit ne doit jamais démarrer
        // sur l'action « create » par défaut (produit non trouvé) : on retombe
        // sur « skip » plutôt que de proposer une action qu'il ne peut pas voir.
        action: matched ? 'match' : (canCreateProduit ? 'create' : 'skip'),
        produit_id: matched ? String(matched.id) : '',
        tva: item.tva ?? null,
        update_tva: false,
        nouveau_nom: item.nom || '', nouveau_sku: item.reference || '',
        nouveau_prix_achat: item.prix_unitaire_ht > 0 ? String(item.prix_unitaire_ht) : '',
        // Suggestion de prix de vente = prix d'achat OCR (modifiable) — évite
        // l'erreur « Prix de vente requis » pour les docs non-achat.
        nouveau_prix_vente: item.prix_unitaire_ht > 0 ? String(item.prix_unitaire_ht) : '',
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
    setCreerBcf(false); resolvedFournisseurRef.current = null
  }

  const handleNewFile = () => {
    dispatch(clearStockOcrResult())
    setStep(2); setLignes([]); setResults([])
    setCreerBcf(false); resolvedFournisseurRef.current = null
  }

  const updateLigne = (idx, updates) =>
    setLignes(prev => prev.map((l, i) => i === idx ? { ...l, ...updates } : l))

  // `retryIds` (Set d'identifiants de ligne) limite l'application aux seules
  // lignes demandées — utilisé pour « Réessayer les échecs » sans rejouer les
  // lignes déjà réussies (750).
  const handleApply = async (retryArg = null) => {
    // onClick passe l'événement : on ne retient un argument que si c'est un Set
    // d'identifiants de ligne (réessai ciblé des échecs).
    const retryIds = retryArg instanceof Set ? retryArg : null
    setApplying(true)
    const log = []
    const categoryCache = {}  // nom → id, évite créations doublons dans un même import
    const lignesACibler = retryIds
      ? lignes.filter(l => retryIds.has(l.id))
      : lignes

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
      if (retryIds && resolvedFournisseurRef.current != null) {
        // Réessai : on réutilise le fournisseur déjà résolu (pas de re-création
        // ni d'entrée de journal en double).
        resolvedFournisseurId = resolvedFournisseurRef.current
      } else if (fournisseurMode === 'existing' && fournisseurId) {
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
      resolvedFournisseurRef.current = resolvedFournisseurId
      // 751 — mode BCF : on collecte les lignes résolues plutôt que de créer des
      // mouvements isolés ; le BCF est créé/reçu après la boucle (réception en
      // bloc = mouvements d'ENTRÉE côté serveur). Réservé aux docs d'achat avec
      // un fournisseur résolu.
      const isPurchaseDoc = docType === 'facture_achat' || docType === 'bon_livraison'
      const modeBcf = creerBcf && isPurchaseDoc && resolvedFournisseurId
      const bcfLignes = []  // { produit, quantite, prix_achat_unitaire, label, ligneId }
      for (const ligne of lignesACibler) {
        const label = ligne.nom_ocr || ligne.ref_ocr || `Ligne #${ligne.id + 1}`
        // chaque entrée de ligne porte son ligneId pour permettre le réessai ciblé
        const push = (entry) => log.push({ ligneId: ligne.id, ...entry })
        if (ligne.action === 'skip') { push({ ok: null, label, msg: 'Ignoré' }); continue }
        let produitId = null
        if (ligne.action === 'match') {
          if (!ligne.produit_id) { push({ ok: false, label, msg: 'Aucun produit sélectionné' }); continue }
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
          if (!ligne.nouveau_nom.trim()) { push({ ok: false, label, msg: 'Nom du produit requis' }); continue }
          const prixAchat = parseFloat(ligne.nouveau_prix_achat) || 0
          const prixVente = isPurchaseDoc
            ? (parseFloat(ligne.nouveau_prix_vente) || 0)
            : (parseFloat(ligne.nouveau_prix_vente) || prixAchat)
          if (!isPurchaseDoc && prixVente <= 0) { push({ ok: false, label, msg: 'Prix de vente requis (> 0)' }); continue }
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
            push({ ok: false, label, msg: `Création produit : ${d?.nom?.[0] ?? d?.sku?.[0] ?? d?.detail ?? JSON.stringify(d ?? e.message)}` })
            continue
          }
        }
        if (modeBcf) {
          // On diffère l'entrée de stock : la ligne rejoint le BCF, reçu en bloc
          // après la boucle. Le prix d'achat unitaire vient du produit résolu.
          const prod = produitsRef.current.find(p => p.id === produitId)
          const prixAchatU = parseFloat(ligne.nouveau_prix_achat)
            || (prod ? parseFloat(prod.prix_achat) : 0) || 0
          bcfLignes.push({
            produit: produitId, quantite: ligne.quantite,
            prix_achat_unitaire: prixAchatU, label, ligneId: ligne.id,
          })
          continue
        }
        try {
          // Référence du mouvement : saisie utilisateur, sinon référence
          // document détectée par l'OCR (752), sinon aucune.
          const refMouvement = refDocument.trim() || (stockOcrResult?.reference_document || '').trim() || null
          const res = await stockApi.createMouvement({ produit: produitId, type_mouvement: mouvementType, quantite: ligne.quantite, reference: refMouvement, note: `Import OCR${ligne.ref_ocr ? ' — ' + ligne.ref_ocr : ''}` })
          const mv = res.data
          const delta = mv.quantite_apres - mv.quantite_avant
          const typeLabel = mouvementType === 'entree' ? 'Entrée' : mouvementType === 'sortie' ? 'Sortie' : 'Ajust.'
          const prev = log[log.length - 1]
          if (prev && prev.label === label && prev.ok === true) {
            prev.msg += ` — ${typeLabel} ${delta >= 0 ? '+' : ''}${delta} (stock : ${mv.quantite_avant} → ${mv.quantite_apres})`
          } else {
            push({ ok: true, label, msg: `${typeLabel} ${delta >= 0 ? '+' : ''}${delta} (stock : ${mv.quantite_avant} → ${mv.quantite_apres})` })
          }
        } catch (e) {
          const d = e.response?.data
          push({ ok: false, label, msg: `Mouvement : ${d?.detail ?? d?.quantite?.[0] ?? d?.non_field_errors?.[0] ?? JSON.stringify(d ?? e.message)}` })
        }
      }

      // 751 — création + réception du BCF une fois toutes les lignes résolues.
      if (modeBcf && bcfLignes.length > 0) {
        try {
          const refDoc = refDocument.trim() || (stockOcrResult?.reference_document || '').trim()
          const created = await stockApi.createBonCommandeFournisseur({
            fournisseur: resolvedFournisseurId,
            note: `Import OCR${refDoc ? ' — ' + refDoc : ''}`,
            lignes: bcfLignes.map(l => ({
              produit: l.produit, quantite: l.quantite,
              prix_achat_unitaire: l.prix_achat_unitaire,
            })),
          })
          const bcf = created.data
          await stockApi.envoyerBcf(bcf.id)
          // Réception totale : chaque ligne du BCF à sa quantité commandée.
          // Source autoritative des lignes : si la réponse de création ne les
          // renvoie pas, on re-fetch le BCF créé — sinon on enverrait une
          // réception vide (BCF resté « envoyé », stock jamais incrémenté).
          let bcfLignesSrc = bcf.lignes
          if (!Array.isArray(bcfLignesSrc) || bcfLignesSrc.length === 0) {
            const refetched = await stockApi.getBonCommandeFournisseur(bcf.id)
            bcfLignesSrc = refetched.data?.lignes ?? []
          }
          const receptions = bcfLignesSrc.map(l => ({
            ligne: l.id, quantite: l.quantite,
          }))
          if (receptions.length === 0) {
            // Aucune ligne autoritative : ne PAS marquer « Reçu » (le stock
            // n'a pas bougé) — on remonte un échec rejouable.
            for (const l of bcfLignes) {
              log.push({ ligneId: l.ligneId, ok: false, label: l.label,
                msg: `BCF ${bcf.reference} créé mais réception impossible (aucune ligne).` })
            }
          } else {
            await stockApi.recevoirBcf(bcf.id, receptions)
            for (const l of bcfLignes) {
              log.push({ ligneId: l.ligneId, ok: true, label: l.label,
                msg: `Reçu via le bon de commande ${bcf.reference}` })
            }
          }
        } catch (e) {
          const d = e.response?.data
          const msg = `BCF : ${d?.detail ?? JSON.stringify(d ?? e.message)}`
          for (const l of bcfLignes) {
            log.push({ ligneId: l.ligneId, ok: false, label: l.label, msg })
          }
        }
      }
    } finally {
      if (retryIds) {
        // Réessai ciblé : on remplace, dans le journal existant, les entrées des
        // lignes rejouées par leur nouveau résultat (les autres restent intactes).
        setResults(prev => [
          ...prev.filter(r => !retryIds.has(r.ligneId)),
          ...log,
        ])
      } else {
        setResults(log)
      }
      setApplying(false); setStep(4)
      dispatch(fetchProduits()); dispatch(fetchFournisseurs()); dispatch(fetchCategories()); dispatch(fetchMouvements())
    }
  }

  if (!canAccess) {
    return (
      <div className="ui-root px-6 py-12">
        <EmptyState icon={AlertTriangle} title="Accès restreint"
                    description="Accès réservé aux responsables et administrateurs." />
      </div>
    )
  }

  const currentDocType = DOC_TYPES.find(t => t.value === docType)

  return (
    <div className="ui-root mx-auto max-w-3xl px-4 py-6 sm:px-5">
      {/* Page header */}
      <div className="mb-6">
        <h2 className="font-display text-xl font-semibold tracking-tight">Import OCR — Stock</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Choisissez le type de document puis scannez-le pour mettre à jour le stock automatiquement.
        </p>
      </div>

      <Stepper step={step} />

      <div>
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
            docType={docType} creerBcf={creerBcf} setCreerBcf={setCreerBcf}
            canCreateProduit={canCreateProduit}
          />
        )}
        {step === 4 && (
          <Step3Results results={results} onReset={handleReset}
            onNewFile={handleNewFile}
            onViewMovements={() => navigate('/stock/mouvements')}
            applying={applying}
            onRetryFailed={() => {
              const ids = new Set(
                results.filter(r => r.ok === false && r.ligneId != null)
                  .map(r => r.ligneId))
              if (ids.size) handleApply(ids)
            }}
          />
        )}
      </div>
    </div>
  )
}

// ── Étape 0 : Sélection du type de document ───────────────────────────────────
function Step0DocType({ selectedValue, onSelect }) {
  return (
    <div>
      <div className="mb-5">
        <p className="text-sm font-semibold text-foreground">Quel type de document allez-vous importer ?</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Ce choix aide l&apos;IA à mieux extraire les informations et pré-configure le mouvement de stock.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {DOC_TYPES.map(type => {
          const isSelected = selectedValue === type.value
          const Icon = type.icon
          return (
            <button
              key={type.value}
              type="button"
              onClick={() => onSelect(type)}
              aria-pressed={isSelected}
              className={[
                'relative flex flex-col items-start gap-3 rounded-xl border p-5 text-left transition-colors',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                isSelected ? 'border-primary bg-primary/5 ring-1 ring-primary/30' : 'border-border bg-card hover:border-primary/40 hover:bg-accent',
              ].join(' ')}
            >
              <span className={`flex size-12 items-center justify-center rounded-xl ${isSelected ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'}`}>
                <Icon className="size-6" aria-hidden="true" />
              </span>
              <div className="flex-1">
                <div className={`text-sm font-semibold ${isSelected ? 'text-primary' : 'text-foreground'}`}>{type.label}</div>
                <div className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{type.desc}</div>
              </div>
              {type.mouvement && (
                <Badge tone={type.mouvement === 'entree' ? 'success' : 'warning'}>
                  {type.mouvement === 'entree' ? '↑ Entrée stock' : '↓ Sortie stock'}
                </Badge>
              )}
              {isSelected && (
                <span className="absolute right-3 top-3 flex size-5 items-center justify-center rounded-full bg-primary text-primary-foreground">
                  <Check className="size-3" />
                </span>
              )}
            </button>
          )
        })}
      </div>

      <p className="mt-5 text-center text-xs text-muted-foreground">
        Cliquez sur un type pour passer à l&apos;étape suivante
      </p>
    </div>
  )
}

// ── Étape 1 (ex-Step1) : Upload ───────────────────────────────────────────────
function Step1Upload({ loading, error, onFile, onReset, docType }) {
  if (loading) return (
    <div className="flex min-h-72 flex-col items-center justify-center gap-5">
      <Spinner className="size-12 text-primary" />
      <div className="text-center">
        <p className="text-sm font-semibold text-foreground">Analyse OCR en cours</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Extraction des produits, quantités et références…
        </p>
      </div>
      <div className="flex flex-wrap justify-center gap-4 text-xs text-muted-foreground">
        {['Lecture document', 'Détection produits', 'Structuration'].map((label) => (
          <span key={label} className="inline-flex items-center gap-1.5">
            <span className="size-1.5 rounded-full bg-muted-foreground/60" />{label}
          </span>
        ))}
      </div>
    </div>
  )

  if (error && !loading) return (
    <Card className="flex items-start gap-3 border-destructive/40 bg-destructive/5 p-5">
      <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-destructive/10 text-destructive">
        <AlertCircle className="size-5" />
      </span>
      <div className="flex-1">
        <p className="text-sm font-semibold text-destructive">Erreur d&apos;analyse</p>
        <p className="mt-1 text-sm text-destructive/90">
          {typeof error === 'string' ? error : JSON.stringify(error)}
        </p>
        <Button variant="outline" size="sm" className="mt-3" onClick={onReset}>
          <RefreshCw /> Recommencer
        </Button>
      </div>
    </Card>
  )

  return (
    <div className="flex flex-col gap-4">
      {docType && (
        <div className="flex items-center gap-2">
          <Badge tone="primary"><docType.icon className="size-3" /> {docType.label}</Badge>
          <Button variant="ghost" size="sm" onClick={onReset}>
            <X /> changer
          </Button>
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
  docType, creerBcf, setCreerBcf, canCreateProduit,
}) {
  const showFournisseur = docType !== 'bon_sortie'
  const isPurchaseDoc = docType === 'facture_achat' || docType === 'bon_livraison'
  // For purchase/delivery docs, prix_vente is not required (falls back to prix_achat)
  const requiresPrixVente = docType === 'bon_sortie' || docType === 'autre' || !docType

  // 748 — collision d'unicité : plusieurs lignes « create » au même SKU.
  const skuCollisions = (() => {
    const counts = {}
    for (const l of lignes) {
      if (l.action !== 'create') continue
      const sku = (l.nouveau_sku || '').trim().toLowerCase()
      if (!sku) continue
      counts[sku] = (counts[sku] || 0) + 1
    }
    return new Set(Object.keys(counts).filter(k => counts[k] > 1))
  })()

  const hasErrors = lignes.filter(l => l.action !== 'skip').some(l => {
    if (l.action === 'match' && !l.produit_id) return true
    if (l.action === 'create') {
      if (!l.nouveau_nom.trim()) return true
      if (requiresPrixVente && !(parseFloat(l.nouveau_prix_vente) > 0)) return true
      if ((l.nouveau_sku || '').trim() && skuCollisions.has((l.nouveau_sku || '').trim().toLowerCase())) return true
    }
    return false
  })
  const pct = Math.round(result.confiance * 100)
  const confTone = pct >= 80 ? 'success' : pct >= 50 ? 'warning' : 'danger'

  const docTypeCfg = DOC_TYPES.find(t => t.value === docType)

  return (
    <div className="flex flex-col gap-4">
      {/* ── Document info card ── */}
      <Card className="p-4 sm:p-5">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          {docTypeCfg && <Badge tone="primary">{docTypeCfg.label}</Badge>}
          <Badge tone="info">
            <FileText className="size-3" />
            {DOC_LABELS[result.type_document] ?? result.type_document}
          </Badge>
          <Badge tone={confTone}>Confiance {pct}%</Badge>
          <span className="ml-auto text-xs text-muted-foreground">
            {lignes.length} ligne{lignes.length > 1 ? 's' : ''} détectée{lignes.length > 1 ? 's' : ''}
          </span>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-foreground" htmlFor="ocr-mvt">Type de mouvement</label>
            <Select value={mouvementType} onValueChange={setMouvementType}>
              <SelectTrigger id="ocr-mvt"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="entree">Entrée (ajoute au stock)</SelectItem>
                <SelectItem value="sortie">Sortie (retire du stock)</SelectItem>
                <SelectItem value="ajustement">Ajustement (fixe le stock)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-foreground" htmlFor="ocr-ref">Référence document</label>
            <Input id="ocr-ref" value={refDocument} onChange={e => setRefDocument(e.target.value)} placeholder="N° BL, facture…" />
          </div>
        </div>
        {/* 751 — créer un bon de commande fournisseur reçu au lieu d'entrées
            isolées (doc d'achat uniquement ; nécessite un fournisseur). */}
        {isPurchaseDoc && (
          <label className="mt-3 flex items-start gap-2 rounded-lg border border-border bg-muted/30 p-3 text-sm">
            <Checkbox checked={creerBcf} onCheckedChange={(v) => setCreerBcf(!!v)} className="mt-0.5" />
            <span>
              <span className="font-medium text-foreground">Créer un bon de commande fournisseur reçu</span>
              <span className="block text-xs text-muted-foreground">
                Au lieu de mouvements d&apos;entrée isolés, génère un BCF reçu (traçable, lié au fournisseur).
                Sélectionnez un fournisseur ci-dessous.
              </span>
            </span>
          </label>
        )}
      </Card>

      {/* ── Fournisseur card — masqué pour bon de sortie ── */}
      {showFournisseur && (
        <Card className="p-4 sm:p-5">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <Building2 className="size-4 text-muted-foreground" />
            <span className="text-sm font-semibold text-foreground">Fournisseur</span>
            {result.fournisseur && (
              <span className="text-xs text-muted-foreground">— détecté : « {result.fournisseur} »</span>
            )}
          </div>

          <Segmented
            size="sm"
            className="mb-3 flex-wrap"
            value={fournisseurMode}
            onChange={setFournisseurMode}
            options={[
              { value: 'existing', label: 'Fournisseur existant' },
              { value: 'new',      label: 'Nouveau fournisseur' },
              { value: 'none',     label: 'Sans fournisseur' },
            ]}
          />

          {fournisseurMode === 'existing' && (
            <Select value={fournisseurId || '__none'} onValueChange={(v) => setFournisseurId(v === '__none' ? '' : v)}>
              <SelectTrigger><SelectValue placeholder="— Sélectionner un fournisseur —" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none">— Sélectionner un fournisseur —</SelectItem>
                {fournisseurs.map(f => <SelectItem key={f.id} value={String(f.id)}>{f.nom}</SelectItem>)}
              </SelectContent>
            </Select>
          )}
          {fournisseurMode === 'new' && (
            <Input value={nouveauFournisseurNom} onChange={e => setNouveauFournisseurNom(e.target.value)} placeholder="Nom du fournisseur" />
          )}
        </Card>
      )}

      {/* ── Lignes produits ── */}
      <div>
        <div className="mb-3 flex items-center gap-2">
          <Truck className="size-4 text-muted-foreground" />
          <span className="text-sm font-semibold text-foreground">Lignes produits ({lignes.length})</span>
        </div>

        {lignes.length === 0 ? (
          <div className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning">
            <AlertTriangle className="size-4 shrink-0" />
            Aucune ligne produit détectée. Vérifiez la qualité du document.
          </div>
        ) : (
          <div className="flex flex-col gap-2.5">
            {lignes.map((ligne, idx) => (
              <LigneCard key={ligne.id} ligne={ligne} produits={produits} categories={categories} onChange={u => updateLigne(idx, u)} docType={docType} canCreateProduit={canCreateProduit} />
            ))}
          </div>
        )}
      </div>

      {skuCollisions.size > 0 && (
        <div className="flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning">
          <AlertTriangle className="size-4 shrink-0" />
          <span>
            Plusieurs lignes « Créer » partagent le même SKU
            ({[...skuCollisions].join(', ')}). Corrigez ou différenciez ces
            références avant d&apos;appliquer (le SKU doit être unique).
          </span>
        </div>
      )}

      {/* ── Actions ── */}
      <div className="flex items-center justify-between gap-2 border-t border-border pt-4">
        <Button variant="outline" onClick={onReset} disabled={applying}>
          <ChevronLeft /> Recommencer
        </Button>
        <Button onClick={onApply} loading={applying} disabled={hasErrors || lignes.length === 0}>
          {applying
            ? 'Application en cours…'
            : <>{creerBcf && isPurchaseDoc ? 'Créer le bon de commande reçu' : 'Appliquer les mouvements'} <ChevronRight /></>}
        </Button>
      </div>
    </div>
  )
}

// ── Carte ligne produit ───────────────────────────────────────────────────────
function LigneCard({ ligne, produits, categories, onChange, docType, canCreateProduit = true }) {
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

  // QG5 — l'option « Créer » (nouveau produit) n'apparaît que pour les rôles
  // autorisés à créer un produit ; les autres ne voient que Associer/Ignorer.
  const ACTION_OPTS = [
    { value: 'match',  label: 'Associer' },
    ...(canCreateProduit ? [{ value: 'create', label: 'Créer' }] : []),
    { value: 'skip',   label: 'Ignorer' },
  ]
  const CAT_OPTS = [
    { value: 'existing', label: 'Existante' },
    { value: 'create',   label: 'Créer' },
    { value: 'none',     label: 'Ignorer' },
  ]

  return (
    <Card className={[
      'p-4',
      hasMatchError || hasCreateError ? 'border-destructive/50' : '',
      isSkipped ? 'opacity-60' : '',
    ].join(' ')}>
      {/* Header: OCR info + quantity */}
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            {ligne.ref_ocr && (
              <span className="rounded bg-muted px-2 py-0.5 font-mono text-xs text-muted-foreground">{ligne.ref_ocr}</span>
            )}
            <span className="text-sm font-semibold text-foreground">{ligne.nom_ocr || '—'}</span>
          </div>
          {ligne.prix_unitaire && (
            <p className="mt-1 text-xs text-muted-foreground">
              Prix achat HT détecté : {ligne.prix_unitaire} DH
              {ligne.tva != null && (
                <span className="ml-1.5 text-info">
                  · TVA {ligne.tva}% · TTC {formatMAD(parseFloat(ligne.prix_unitaire) * (1 + ligne.tva / 100), { withSymbol: false })} DH
                </span>
              )}
            </p>
          )}
        </div>
        <div className="shrink-0 text-right">
          <label className="mb-1 block text-xs text-muted-foreground" htmlFor={`qte-${ligne.id}`}>Qté</label>
          <Input
            id={`qte-${ligne.id}`} type="number" min="1" step="1" inputMode="numeric"
            className="h-9 w-20 text-right"
            value={ligne.quantite}
            onChange={e => onChange({ quantite: Math.max(1, parseInt(e.target.value) || 1) })}
          />
        </div>
      </div>

      {/* Action selector */}
      <Segmented
        size="sm"
        className="mb-3"
        value={ligne.action}
        onChange={(v) => onChange({ action: v })}
        options={ACTION_OPTS}
      />

      {/* Match: select existing product */}
      {ligne.action === 'match' && (
        <div className="flex flex-col gap-2">
          <Select value={ligne.produit_id || '__none'} onValueChange={(v) => onChange({ produit_id: v === '__none' ? '' : v })}>
            <SelectTrigger invalid={hasMatchError}>
              <SelectValue placeholder="— Sélectionner un produit existant —" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__none">— Sélectionner un produit existant —</SelectItem>
              {produits.map(p => (
                <SelectItem key={p.id} value={String(p.id)}>
                  {p.nom}{p.sku ? ` (${p.sku})` : ''} — stock : {p.quantite_stock}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {hasMatchError && <p className="text-xs text-destructive">Sélectionnez un produit existant</p>}

          {matchedProduit?.fournisseur && (
            <div className="flex items-center gap-1.5 rounded-md border border-info/30 bg-info/10 px-2.5 py-1.5 text-xs text-info">
              <Building2 className="size-3.5" />
              Fournisseur enregistré : <strong>{matchedProduit.fournisseur.nom}</strong>
            </div>
          )}

          {tvaDivergence && (
            <div className="flex flex-col gap-1.5 rounded-lg border border-warning/30 bg-warning/10 p-3">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-warning">
                <AlertCircle className="size-3.5" />
                Divergence TVA — produit enregistré : {produitTva != null ? `${produitTva}%` : 'sans TVA'} · document détecte : {ocrTva}%
              </div>
              <label className="flex cursor-pointer items-center gap-2 text-xs text-foreground">
                <input type="checkbox" checked={!!ligne.update_tva} onChange={e => onChange({ update_tva: e.target.checked })} />
                Mettre à jour la TVA du produit à {ocrTva}%
              </label>
            </div>
          )}
        </div>
      )}

      {/* Catégorie — toujours visible pour "create", visible pour "match" si suggestion */}
      {ligne.action !== 'skip' && (ligne.action === 'create' || ligne.categorie_suggeree || ligne.categorie_source === 'keyword') && (
        <div className="mt-2 rounded-lg border border-border bg-muted/40 p-3">
          <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
            <span className="text-xs font-semibold text-foreground">Catégorie</span>
            {ligne.categorie_source === 'ia' && ligne.categorie_suggeree && (
              <span className="text-xs text-muted-foreground">— IA suggère : « {ligne.categorie_suggeree} »</span>
            )}
            {ligne.categorie_source === 'keyword' && ligne.categorie_action === 'existing' && (
              <span className="text-xs text-info">— Détecté depuis le nom du produit</span>
            )}
          </div>
          <Segmented
            size="sm"
            className="mb-2"
            value={ligne.categorie_action}
            onChange={(v) => onChange({ categorie_action: v })}
            options={CAT_OPTS}
          />
          {ligne.categorie_action === 'existing' && (
            <Select value={ligne.categorie_id || '__none'} onValueChange={(v) => onChange({ categorie_id: v === '__none' ? '' : v })}>
              <SelectTrigger><SelectValue placeholder="— Sélectionner une catégorie —" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none">— Sélectionner une catégorie —</SelectItem>
                {categories.map(c => <SelectItem key={c.id} value={String(c.id)}>{c.nom}</SelectItem>)}
              </SelectContent>
            </Select>
          )}
          {ligne.categorie_action === 'create' && (
            <Input value={ligne.categorie_nom_new} onChange={e => onChange({ categorie_nom_new: e.target.value })}
                   placeholder="Nom de la nouvelle catégorie" />
          )}
        </div>
      )}

      {/* Create: new product form */}
      {ligne.action === 'create' && (
        <div className="mt-2 grid gap-3 rounded-lg bg-muted/40 p-3 sm:grid-cols-2">
          <div className="sm:col-span-2 flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-foreground" htmlFor={`nom-${ligne.id}`}>
              Nom <span className="text-destructive">*</span>
            </label>
            <Input id={`nom-${ligne.id}`} invalid={hasCreateError && !ligne.nouveau_nom.trim()}
                   value={ligne.nouveau_nom} onChange={e => onChange({ nouveau_nom: e.target.value })} placeholder="Nom du produit" />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-foreground" htmlFor={`sku-${ligne.id}`}>SKU / Référence</label>
            <Input id={`sku-${ligne.id}`} value={ligne.nouveau_sku} onChange={e => onChange({ nouveau_sku: e.target.value })} placeholder="ART-001" />
            {!ligne.ref_ocr && (
              <p className="text-xs text-muted-foreground">
                Aucun code article dans le document — saisissez-en un manuellement si disponible.
              </p>
            )}
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-foreground" htmlFor={`achat-${ligne.id}`}>
              Prix achat HT (DH)
              {ligne.tva != null && (
                <span className="ml-1.5 font-normal text-muted-foreground">
                  · TVA {ligne.tva}%
                  {parseFloat(ligne.nouveau_prix_achat) > 0 && (
                    <span className="text-info"> → TTC {formatMAD(parseFloat(ligne.nouveau_prix_achat) * (1 + ligne.tva / 100), { withSymbol: false })} DH</span>
                  )}
                </span>
              )}
            </label>
            <Input id={`achat-${ligne.id}`} type="number" min="0" step="0.01" inputMode="decimal"
                   value={ligne.nouveau_prix_achat} onChange={e => onChange({ nouveau_prix_achat: e.target.value })} placeholder="0.00" />
          </div>
          {isPurchase ? (
            <div className="sm:col-span-2">
              <div className="flex items-center gap-1.5 rounded-md border border-success/30 bg-success/10 px-3 py-2 text-xs text-success">
                <AlertCircle className="size-3.5" />
                Prix de vente à définir plus tard selon votre marge
                {parseFloat(ligne.nouveau_prix_achat) > 0 && (
                  <span className="text-muted-foreground">(achat HT : {formatMAD(ligne.nouveau_prix_achat, { withSymbol: false })} DH)</span>
                )}
              </div>
            </div>
          ) : (
            <div className="sm:col-span-2 flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-foreground" htmlFor={`vente-${ligne.id}`}>
                Prix vente (DH) <span className="text-destructive">*</span>
                <span className="ml-1.5 font-normal text-muted-foreground">— selon votre marge</span>
              </label>
              <Input id={`vente-${ligne.id}`} type="number" min="0" step="0.01" inputMode="decimal"
                     invalid={hasCreateError && !(parseFloat(ligne.nouveau_prix_vente) > 0)}
                     value={ligne.nouveau_prix_vente} onChange={e => onChange({ nouveau_prix_vente: e.target.value })} placeholder="Saisir votre prix de vente…" />
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

// ── Étape 3 (ex-Step3) : Résultats ───────────────────────────────────────────
// Une ligne de résultat (réutilisée par les groupes succès/échecs/ignorés).
function ResultRow({ r }) {
  return (
    <div className={[
      'flex items-start gap-3 rounded-lg border px-3 py-2.5 text-sm',
      r.ok === true ? 'border-success/30 bg-success/10'
        : r.ok === false ? 'border-destructive/30 bg-destructive/10'
          : 'border-border bg-muted/40',
    ].join(' ')}>
      <span className={[
        'flex size-6 shrink-0 items-center justify-center rounded-md',
        r.ok === true ? 'bg-success/20 text-success'
          : r.ok === false ? 'bg-destructive/20 text-destructive'
            : 'bg-muted text-muted-foreground',
      ].join(' ')}>
        {r.ok === true && <Check className="size-3.5" />}
        {r.ok === false && <X className="size-3.5" />}
        {r.ok === null && <ChevronRight className="size-3.5" />}
      </span>
      <div>
        <span className={`font-semibold ${r.ok === true ? 'text-success' : r.ok === false ? 'text-destructive' : 'text-muted-foreground'}`}>
          {r.label}
        </span>
        <span className="ml-2 text-muted-foreground">— {r.msg}</span>
      </div>
    </div>
  )
}

function Step3Results({ results, onReset, onNewFile, onViewMovements, onRetryFailed, applying }) {
  // 750 — groupe les résultats par statut (réussis / échoués / ignorés).
  const reussis = results.filter(r => r.ok === true)
  const echoues = results.filter(r => r.ok === false)
  const ignores = results.filter(r => r.ok === null)
  const successCount = reussis.length
  const errorCount   = echoues.length
  const skipCount    = ignores.length
  const allOk        = errorCount === 0
  // Seuls les échecs RATTACHÉS à une ligne (ligneId) sont rejouables.
  const retryable = echoues.some(r => r.ligneId != null)

  return (
    <div className="flex flex-col gap-4">
      {/* Summary banner */}
      <Card className={`flex items-center gap-4 p-5 ${allOk ? 'border-success/30 bg-success/10' : 'border-warning/30 bg-warning/10'}`}>
        <span className={`flex size-12 shrink-0 items-center justify-center rounded-xl ${allOk ? 'bg-success text-success-foreground' : 'bg-warning text-warning-foreground'}`}>
          {allOk ? <Check className="size-6" /> : <AlertCircle className="size-6" />}
        </span>
        <div>
          <p className={`text-base font-bold ${allOk ? 'text-success' : 'text-warning'}`}>
            {allOk ? 'Import réussi' : `Import terminé avec ${errorCount} erreur${errorCount > 1 ? 's' : ''}`}
          </p>
          <div className="mt-1.5 flex flex-wrap gap-3 text-xs">
            <span className="inline-flex items-center gap-1 font-semibold text-success">
              <Check className="size-3.5" /> {successCount} succès
            </span>
            {errorCount > 0 && (
              <span className="inline-flex items-center gap-1 font-semibold text-destructive">
                <X className="size-3.5" /> {errorCount} erreur{errorCount > 1 ? 's' : ''}
              </span>
            )}
            {skipCount > 0 && (
              <span className="font-medium text-muted-foreground">{skipCount} ignoré{skipCount > 1 ? 's' : ''}</span>
            )}
          </div>
        </div>
      </Card>

      {/* Échecs en premier, avec réessai ciblé */}
      {echoues.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wide text-destructive">
              Échecs ({errorCount})
            </span>
            {retryable && (
              <Button size="sm" variant="outline" onClick={onRetryFailed} disabled={applying}>
                <Repeat /> {applying ? 'Réessai en cours…' : 'Réessayer les échecs'}
              </Button>
            )}
          </div>
          {echoues.map((r, i) => <ResultRow key={`e${i}`} r={r} />)}
        </div>
      )}

      {/* Réussis */}
      {reussis.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <span className="text-xs font-semibold uppercase tracking-wide text-success">
            Réussis ({successCount})
          </span>
          {reussis.map((r, i) => <ResultRow key={`s${i}`} r={r} />)}
        </div>
      )}

      {/* Ignorés */}
      {ignores.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Ignorés ({skipCount})
          </span>
          {ignores.map((r, i) => <ResultRow key={`i${i}`} r={r} />)}
        </div>
      )}

      {/* Actions */}
      <div className="flex flex-wrap gap-2 pt-1">
        <Button onClick={onViewMovements}>
          <ArrowDownUp /> Voir les mouvements
        </Button>
        <Button variant="outline" onClick={onNewFile}>
          <Upload /> Nouveau fichier (même type)
        </Button>
        <Button variant="outline" onClick={onReset}>
          <Repeat /> Nouvel import
        </Button>
      </div>
    </div>
  )
}
