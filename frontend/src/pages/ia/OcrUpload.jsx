import { useState, useCallback, useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { FileUpload } from '../../ui/FileUpload'
import {
  processOcrDocument,
  saveOcrDocument,
  clearOcrResult,
  fetchOcrDocuments,
  deleteOcrDocument,
} from '../../features/ia/store/iaSlice'

// G26 — type/taille acceptés (inchangés vs. l'ancienne dropzone inline).
const OCR_ACCEPT = 'image/jpeg,image/png,image/tiff,image/webp,application/pdf'
const OCR_MAX_SIZE = 10 * 1024 * 1024 // 10 Mo

const TYPE_LABELS = {
  facture: 'Facture',
  devis: 'Devis',
  bon_commande: 'Bon de commande',
  bon_livraison: 'Bon de livraison',
  autre: 'Autre',
}

const FIELD_LABELS = {
  numero: 'Numéro',
  date: 'Date',
  fournisseur: 'Fournisseur',
  client: 'Client',
  montant_ht: 'Montant HT',
  taux_tva: 'Taux TVA',
  montant_tva: 'Montant TVA',
  montant_ttc: 'Montant TTC',
  conditions_paiement: 'Conditions de paiement',
  iban: 'IBAN',
}

function ConfidenceBadge({ value }) {
  const pct = Math.round(value * 100)
  const color =
    pct >= 80 ? 'bg-green-100 text-green-800' :
    pct >= 50 ? 'bg-yellow-100 text-yellow-800' :
                'bg-red-100 text-red-800'
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${color}`}>
      Confiance : {pct}%
    </span>
  )
}

function TypeBadge({ type }) {
  return (
    <span className="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800">
      {TYPE_LABELS[type] ?? type}
    </span>
  )
}

// ── Onglet Analyser ───────────────────────────────────────────────────────────
function AnalyseTab({ canSave }) {
  const dispatch = useDispatch()
  const { ocrResult, ocrLoading, ocrError, savedDocumentId, saveLoading, saveError } =
    useSelector((s) => s.ia)

  const [currentFile, setCurrentFile] = useState(null)
  const [copied, setCopied] = useState(false)

  const processFile = useCallback((file) => {
    if (!file) return
    setCurrentFile(file)
    dispatch(processOcrDocument(file))
  }, [dispatch])

  const handleReset = () => {
    dispatch(clearOcrResult())
    setCurrentFile(null)
    setCopied(false)
  }

  const handleCopy = () => {
    if (ocrResult?.texte_brut) {
      navigator.clipboard.writeText(ocrResult.texte_brut).then(() => {
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      })
    }
  }

  const handleSave = () => {
    if (!ocrResult || !currentFile) return
    dispatch(saveOcrDocument({
      filename: currentFile.name,
      texte_brut: ocrResult.texte_brut,
      type_document: ocrResult.type_document ?? 'autre',
      confiance: ocrResult.confiance ?? 0,
      donnees_structurees: ocrResult.donnees_structurees ?? {},
    }))
  }

  const donnees = ocrResult?.donnees_structurees ?? {}
  const lignes = donnees.lignes ?? []

  return (
    <div className="mt-4">
      {/* Zone de dépôt (G26 — primitif FileUpload ; même dispatch OCR) */}
      {!ocrResult && !ocrLoading && (
        <FileUpload
          accept={OCR_ACCEPT}
          maxSize={OCR_MAX_SIZE}
          onFiles={(files) => processFile(files[0])}
        />
      )}

      {ocrLoading && (
        <div className="mt-8 flex flex-col items-center gap-3 text-gray-500">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
          <p className="text-sm">Analyse OCR en cours…</p>
        </div>
      )}

      {ocrError && !ocrLoading && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {typeof ocrError === 'string' ? ocrError : JSON.stringify(ocrError)}
          <button className="ml-3 underline text-red-600" onClick={handleReset}>Réessayer</button>
        </div>
      )}

      {ocrResult && (
        <div className="space-y-5">
          {/* En-tête */}
          <div className="flex flex-wrap items-center gap-3">
            <TypeBadge type={ocrResult.type_document} />
            <ConfidenceBadge value={ocrResult.confiance} />
            {currentFile && <span className="text-xs text-gray-500">{currentFile.name}</span>}
          </div>

          {/* Données structurées */}
          {Object.keys(donnees).some(k => k !== 'lignes' && donnees[k] != null) && (
            <div>
              <h3 className="mb-2 text-sm font-semibold text-gray-700">Données extraites</h3>
              <div className="overflow-hidden rounded-lg border border-gray-200">
                <table className="w-full text-sm">
                  <tbody>
                    {Object.entries(FIELD_LABELS).map(([key, label]) => {
                      const val = donnees[key]
                      if (val == null) return null
                      return (
                        <tr key={key} className="border-b border-gray-100 last:border-0">
                          <td className="w-44 bg-gray-50 px-4 py-2 font-medium text-gray-600">{label}</td>
                          <td className="px-4 py-2 text-gray-800">{String(val)}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Lignes */}
          {lignes.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold text-gray-700">Lignes ({lignes.length})</h3>
              <div className="overflow-x-auto rounded-lg border border-gray-200">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 text-xs uppercase text-gray-500">
                    <tr>
                      <th className="px-4 py-2 text-left">Description</th>
                      <th className="px-4 py-2 text-right">Qté</th>
                      <th className="px-4 py-2 text-right">P.U.</th>
                      <th className="px-4 py-2 text-right">Montant</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lignes.map((l, i) => (
                      <tr key={i} className="border-t border-gray-100">
                        <td className="px-4 py-2">{l.description ?? '—'}</td>
                        <td className="px-4 py-2 text-right">{l.quantite ?? '—'}</td>
                        <td className="px-4 py-2 text-right">{l.prix_unitaire ?? '—'}</td>
                        <td className="px-4 py-2 text-right">{l.montant ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Texte brut */}
          <div>
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-700">Texte brut</h3>
              <button className="text-xs text-blue-600 hover:underline" onClick={handleCopy}>
                {copied ? 'Copié !' : 'Copier'}
              </button>
            </div>
            <pre className="max-h-64 overflow-y-auto rounded-lg bg-gray-50 p-4 text-xs text-gray-700 whitespace-pre-wrap break-words border border-gray-200">
              {ocrResult.texte_brut || '(aucun texte extrait)'}
            </pre>
          </div>

          {/* Actions */}
          <div className="flex flex-wrap items-center gap-3 pt-2">
            {canSave && (
              <>
                {savedDocumentId ? (
                  <span className="rounded-lg bg-green-50 border border-green-200 px-4 py-2 text-sm text-green-700">
                    Document enregistré (ID #{savedDocumentId})
                  </span>
                ) : (
                  <button
                    className="btn btn-primary btn-sm disabled:opacity-50"
                    onClick={handleSave}
                    disabled={saveLoading}
                  >
                    {saveLoading ? 'Enregistrement…' : 'Valider et enregistrer'}
                  </button>
                )}
                {saveError && <span className="text-sm text-red-600">{saveError}</span>}
              </>
            )}
            <button className="btn btn-sm btn-outline" onClick={handleReset}>
              Analyser un autre fichier
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Onglet Documents sauvegardés ──────────────────────────────────────────────
function DocumentsTab({ canDelete }) {
  const dispatch = useDispatch()
  const { documents, docsLoading, docsError } = useSelector((s) => s.ia)
  const [expanded, setExpanded] = useState(null)

  useEffect(() => { dispatch(fetchOcrDocuments()) }, [dispatch])

  const handleDelete = (id) => {
    if (window.confirm('Supprimer ce document ?')) dispatch(deleteOcrDocument(id))
  }

  if (docsLoading) return (
    <div className="mt-8 flex justify-center">
      <div className="h-6 w-6 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
    </div>
  )

  if (docsError) return (
    <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      Erreur : {docsError}
    </div>
  )

  if (documents.length === 0) return (
    <div className="mt-10 flex flex-col items-center gap-2 text-gray-400">
      <span className="text-3xl">🗂️</span>
      <p className="text-sm">Aucun document enregistré pour l'instant.</p>
    </div>
  )

  return (
    <div className="mt-4 space-y-2">
      {documents.map((doc) => {
        const isOpen = expanded === doc.id
        const d = doc.donnees_structurees ?? {}
        return (
          <div key={doc.id} className="rounded-lg border border-gray-200 bg-white overflow-hidden">
            {/* Ligne principale */}
            <div
              className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-gray-50"
              onClick={() => setExpanded(isOpen ? null : doc.id)}
            >
              <span className="text-gray-400 text-xs w-8">#{doc.id}</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 truncate">{doc.filename}</p>
                <p className="text-xs text-gray-500">
                  {new Date(doc.created_at).toLocaleString('fr-FR')} — {doc.username}
                </p>
              </div>
              <TypeBadge type={doc.type_document} />
              <ConfidenceBadge value={doc.confiance} />
              {canDelete && (
                <button
                  className="ml-2 text-xs text-red-500 hover:text-red-700"
                  onClick={(e) => { e.stopPropagation(); handleDelete(doc.id) }}
                >
                  Supprimer
                </button>
              )}
              <span className="text-gray-400 text-xs">{isOpen ? '▲' : '▼'}</span>
            </div>

            {/* Détail déroulant */}
            {isOpen && (
              <div className="border-t border-gray-100 px-4 py-3 bg-gray-50 space-y-3">
                {Object.keys(d).some(k => k !== 'lignes' && d[k] != null) && (
                  <table className="w-full text-xs">
                    <tbody>
                      {Object.entries(FIELD_LABELS).map(([key, label]) => {
                        const val = d[key]
                        if (val == null) return null
                        return (
                          <tr key={key} className="border-b border-gray-100 last:border-0">
                            <td className="w-36 py-1 font-medium text-gray-500">{label}</td>
                            <td className="py-1 text-gray-800">{String(val)}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                )}
                {(d.lignes ?? []).length > 0 && (
                  <p className="text-xs text-gray-500">{d.lignes.length} ligne(s) de détail</p>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Page principale ───────────────────────────────────────────────────────────
export default function OcrUpload() {
  const [tab, setTab] = useState('analyse')
  const role = useSelector((s) => s.auth.role)
  const canSave = role === 'responsable' || role === 'admin'

  return (
    <div className="page">
      <div className="page-header">
        <h2>Traitement OCR</h2>
      </div>

      {/* Onglets */}
      <div className="mt-2 flex gap-1 border-b border-gray-200">
        {[
          { key: 'analyse', label: 'Analyser un document' },
          { key: 'documents', label: 'Documents sauvegardés' },
        ].map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors
              ${tab === key
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'analyse'
        ? <AnalyseTab canSave={canSave} />
        : <DocumentsTab canDelete={canSave} />
      }
    </div>
  )
}
