import { useState, useCallback, useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import {
  FileText, Inbox, AlertCircle, Check, Copy, RefreshCw, Save, Trash2, ChevronDown,
  UserPlus, FilePlus, Receipt,
} from 'lucide-react'
import {
  Button,
  Badge,
  Spinner,
  Card,
  CardContent,
  EmptyState,
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from '../../ui'
import { FileUpload } from '../../ui/FileUpload'
import { cn } from '../../lib/cn'
import publicapiApi from '../../api/publicapiApi'
import stockApi from '../../api/stockApi'
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
  const tone = pct >= 80 ? 'success' : pct >= 50 ? 'warning' : 'danger'
  return <Badge tone={tone}>Confiance : {pct}%</Badge>
}

function TypeBadge({ type }) {
  return <Badge tone="info">{TYPE_LABELS[type] ?? type}</Badge>
}

// ── Onglet Analyser ───────────────────────────────────────────────────────────
function AnalyseTab({ canSave }) {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const { ocrResult, ocrLoading, ocrError, savedDocumentId, saveLoading, saveError } =
    useSelector((s) => s.ia)

  const [currentFile, setCurrentFile] = useState(null)
  const [copied, setCopied] = useState(false)
  // FG106 — création d'un lead / brouillon de devis depuis le document OCR.
  const [crmLoading, setCrmLoading] = useState(false)
  const [crmDone, setCrmDone] = useState(null) // { mode, devisReference? }
  // XACC36 — brouillon de facture d'achat depuis un document OCR
  // « facture_fournisseur »/« facture_achat ».
  const [factureLoading, setFactureLoading] = useState(false)
  const [factureDone, setFactureDone] = useState(null)
  const [factureError, setFactureError] = useState(null)

  const processFile = useCallback((file) => {
    if (!file) return
    setCurrentFile(file)
    dispatch(processOcrDocument(file))
  }, [dispatch])

  const handleReset = () => {
    dispatch(clearOcrResult())
    setCurrentFile(null)
    setCopied(false)
    setCrmDone(null)
    setFactureDone(null)
    setFactureError(null)
  }

  // XACC36 — POSTe les champs extraits + le scan d'origine vers le SINK
  // stock, qui matche le fournisseur (ICE puis nom) et crée un brouillon de
  // facture d'achat. Dégrade proprement (message clair) si aucun fournisseur
  // ne matche — la saisie manuelle reste intacte.
  const createFactureFromDocument = async () => {
    if (!ocrResult) return
    setFactureLoading(true)
    setFactureError(null)
    try {
      const r = await stockApi.factureFournisseurDepuisOcr({
        fields: ocrResult.donnees_structurees ?? {},
        file: currentFile,
      })
      setFactureDone({
        id: r.data.id,
        reference: r.data.reference,
        doublon: r.data.doublon_warning ?? null,
      })
    } catch (e) {
      setFactureError(
        e?.response?.data?.detail ?? 'Création de la facture impossible depuis ce document.')
    } finally {
      setFactureLoading(false)
    }
  }

  // FG106 — POSTe les champs extraits vers la passerelle CRM/ventes côté
  // serveur (qui crée un lead, ou un lead + brouillon de devis). On ne quitte
  // l'écran que sur action explicite « Ouvrir ».
  const createFromDocument = async (mode) => {
    if (!ocrResult) return
    setCrmLoading(true)
    try {
      const r = await publicapiApi.ocrToCrm({
        mode,
        fields: ocrResult.donnees_structurees ?? {},
      })
      setCrmDone({
        mode,
        leadId: r.data.lead_id,
        devisReference: r.data.devis_reference,
      })
    } catch (e) {
      alert(e?.response?.data?.detail ?? 'Création impossible depuis ce document.')
    } finally {
      setCrmLoading(false)
    }
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
    <div className="space-y-4">
      {/* Zone de dépôt (G26 — primitif FileUpload ; même dispatch OCR) */}
      {!ocrResult && !ocrLoading && (
        <FileUpload
          accept={OCR_ACCEPT}
          maxSize={OCR_MAX_SIZE}
          onFiles={(files) => processFile(files[0])}
          hint="JPEG, PNG, TIFF, WebP ou PDF — 10 Mo maximum"
        />
      )}

      {ocrLoading && (
        <div className="flex flex-col items-center gap-3 py-12 text-muted-foreground">
          <Spinner className="size-7 text-primary" />
          <p className="text-sm">Analyse OCR en cours…</p>
        </div>
      )}

      {ocrError && !ocrLoading && (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-3 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          <AlertCircle className="size-4 shrink-0" aria-hidden="true" />
          <span>{typeof ocrError === 'string' ? ocrError : JSON.stringify(ocrError)}</span>
          <Button variant="ghost" size="sm" className="ml-auto" onClick={handleReset}>
            <RefreshCw /> Réessayer
          </Button>
        </div>
      )}

      {ocrResult && (
        <div className="space-y-5">
          {/* En-tête */}
          <div className="flex flex-wrap items-center gap-2.5">
            <TypeBadge type={ocrResult.type_document} />
            <ConfidenceBadge value={ocrResult.confiance} />
            {currentFile && (
              <span className="text-xs text-muted-foreground">{currentFile.name}</span>
            )}
          </div>

          {/* Données structurées */}
          {Object.keys(donnees).some(k => k !== 'lignes' && donnees[k] != null) && (
            <Card>
              <CardContent className="p-0">
                <p className="border-b border-border px-4 py-2.5 text-sm font-semibold text-foreground">
                  Données extraites
                </p>
                <table className="w-full text-sm">
                  <tbody>
                    {Object.entries(FIELD_LABELS).map(([key, label]) => {
                      const val = donnees[key]
                      if (val == null) return null
                      return (
                        <tr key={key} className="border-b border-border last:border-0">
                          <td className="w-44 bg-muted/50 px-4 py-2 font-medium text-muted-foreground">{label}</td>
                          <td className="px-4 py-2 text-foreground">{String(val)}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          )}

          {/* Lignes */}
          {lignes.length > 0 && (
            <Card>
              <CardContent className="p-0">
                <p className="border-b border-border px-4 py-2.5 text-sm font-semibold text-foreground">
                  Lignes ({lignes.length})
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50 text-xs uppercase text-muted-foreground">
                      <tr>
                        <th className="px-4 py-2 text-left font-medium">Description</th>
                        <th className="px-4 py-2 text-right font-medium">Qté</th>
                        <th className="px-4 py-2 text-right font-medium">P.U.</th>
                        <th className="px-4 py-2 text-right font-medium">Montant</th>
                      </tr>
                    </thead>
                    <tbody>
                      {lignes.map((l, i) => (
                        <tr key={i} className="border-t border-border">
                          <td className="px-4 py-2 text-foreground">{l.description ?? '—'}</td>
                          <td className="px-4 py-2 text-right text-foreground">{l.quantite ?? '—'}</td>
                          <td className="px-4 py-2 text-right text-foreground">{l.prix_unitaire ?? '—'}</td>
                          <td className="px-4 py-2 text-right text-foreground">{l.montant ?? '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Texte brut */}
          <div>
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-foreground">Texte brut</h3>
              <Button variant="ghost" size="sm" onClick={handleCopy}>
                {copied ? <Check /> : <Copy />}
                {copied ? 'Copié !' : 'Copier'}
              </Button>
            </div>
            <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap break-words rounded-lg border border-border bg-muted/50 p-4 text-xs text-muted-foreground">
              {ocrResult.texte_brut || '(aucun texte extrait)'}
            </pre>
          </div>

          {/* Actions */}
          <div className="flex flex-wrap items-center gap-3 pt-1">
            {canSave && (
              <>
                {savedDocumentId ? (
                  <Badge tone="success" className="gap-1.5 px-3 py-1.5 text-sm">
                    <Check className="size-4" aria-hidden="true" />
                    Document enregistré (ID #{savedDocumentId})
                  </Badge>
                ) : (
                  <Button variant="success" size="sm" onClick={handleSave} loading={saveLoading}>
                    {!saveLoading && <Save />}
                    {saveLoading ? 'Enregistrement…' : 'Valider et enregistrer'}
                  </Button>
                )}
                {saveError && <span className="text-sm text-destructive">{saveError}</span>}
              </>
            )}
            {/* FG106 — créer un lead / brouillon de devis depuis ce document */}
            {canSave && !crmDone && (
              <>
                <Button
                  variant="outline" size="sm"
                  onClick={() => createFromDocument('lead')}
                  loading={crmLoading}
                >
                  {!crmLoading && <UserPlus />} Créer un lead
                </Button>
                <Button
                  variant="outline" size="sm"
                  onClick={() => createFromDocument('devis')}
                  loading={crmLoading}
                >
                  {!crmLoading && <FilePlus />} Brouillon de devis
                </Button>
              </>
            )}
            {crmDone && (
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="success" className="gap-1.5 px-3 py-1.5 text-sm">
                  <Check className="size-4" aria-hidden="true" />
                  {crmDone.mode === 'devis'
                    ? `Lead + devis brouillon créés${crmDone.devisReference ? ` (${crmDone.devisReference})` : ''}`
                    : 'Lead brouillon créé'}
                </Badge>
                <Button
                  variant="ghost" size="sm"
                  onClick={() => navigate(crmDone.mode === 'devis' ? '/ventes/devis' : '/crm/leads')}
                >
                  {crmDone.mode === 'devis' ? 'Ouvrir les devis' : 'Ouvrir les leads'}
                </Button>
              </div>
            )}
            {/* XACC36 — créer un brouillon de facture d'achat (fournisseur
                matché par ICE puis nom) depuis ce document OCR */}
            {canSave && !factureDone && (
              <Button
                variant="outline" size="sm"
                onClick={createFactureFromDocument}
                loading={factureLoading}
              >
                {!factureLoading && <Receipt />} Créer facture d'achat
              </Button>
            )}
            {factureError && !factureDone && (
              <span className="text-sm text-destructive">{factureError}</span>
            )}
            {factureDone && (
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={factureDone.doublon ? 'warning' : 'success'} className="gap-1.5 px-3 py-1.5 text-sm">
                  <Check className="size-4" aria-hidden="true" />
                  {factureDone.doublon
                    ? `Facture brouillon créée (${factureDone.reference}) — doublon possible détecté`
                    : `Facture brouillon créée (${factureDone.reference})`}
                </Badge>
                <Button
                  variant="ghost" size="sm"
                  onClick={() => navigate('/stock/factures-fournisseur')}
                >
                  Ouvrir les factures fournisseur
                </Button>
              </div>
            )}
            <Button variant="outline" size="sm" onClick={handleReset}>
              <RefreshCw /> Analyser un autre fichier
            </Button>
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
    <div className="flex justify-center py-12">
      <Spinner className="size-6 text-primary" />
    </div>
  )

  if (docsError) return (
    <div
      role="alert"
      className="flex items-center gap-3 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
    >
      <AlertCircle className="size-4 shrink-0" aria-hidden="true" />
      Erreur : {docsError}
    </div>
  )

  if (documents.length === 0) return (
    <EmptyState
      icon={Inbox}
      title="Aucun document enregistré"
      description="Les documents que vous validez dans l'onglet « Analyser » apparaîtront ici."
    />
  )

  return (
    <div className="space-y-2">
      {documents.map((doc) => {
        const isOpen = expanded === doc.id
        const d = doc.donnees_structurees ?? {}
        return (
          <Card key={doc.id} className="overflow-hidden">
            {/* Ligne principale */}
            <button
              type="button"
              className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-accent"
              onClick={() => setExpanded(isOpen ? null : doc.id)}
              aria-expanded={isOpen}
            >
              <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
                <FileText className="size-4" aria-hidden="true" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-foreground">{doc.filename}</p>
                <p className="text-xs text-muted-foreground">
                  {new Date(doc.created_at).toLocaleString('fr-FR')} — {doc.username}
                </p>
              </div>
              <div className="hidden shrink-0 items-center gap-2 sm:flex">
                <TypeBadge type={doc.type_document} />
                <ConfidenceBadge value={doc.confiance} />
              </div>
              {canDelete && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="shrink-0 text-destructive hover:text-destructive"
                  onClick={(e) => { e.stopPropagation(); handleDelete(doc.id) }}
                >
                  <Trash2 />
                  <span className="sr-only sm:not-sr-only">Supprimer</span>
                </Button>
              )}
              <ChevronDown
                className={cn(
                  'size-4 shrink-0 text-muted-foreground transition-transform',
                  isOpen && 'rotate-180',
                )}
                aria-hidden="true"
              />
            </button>

            {/* Détail déroulant */}
            {isOpen && (
              <div className="space-y-3 border-t border-border bg-muted/40 px-4 py-3">
                <div className="flex flex-wrap items-center gap-2 sm:hidden">
                  <TypeBadge type={doc.type_document} />
                  <ConfidenceBadge value={doc.confiance} />
                </div>
                {Object.keys(d).some(k => k !== 'lignes' && d[k] != null) && (
                  <table className="w-full text-xs">
                    <tbody>
                      {Object.entries(FIELD_LABELS).map(([key, label]) => {
                        const val = d[key]
                        if (val == null) return null
                        return (
                          <tr key={key} className="border-b border-border last:border-0">
                            <td className="w-36 py-1 font-medium text-muted-foreground">{label}</td>
                            <td className="py-1 text-foreground">{String(val)}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                )}
                {(d.lignes ?? []).length > 0 && (
                  <p className="text-xs text-muted-foreground">{d.lignes.length} ligne(s) de détail</p>
                )}
              </div>
            )}
          </Card>
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
    <div className="ui-root space-y-4">
      <div>
        <h2 className="font-display text-lg font-semibold tracking-tight text-foreground">
          Traitement OCR
        </h2>
        <p className="text-sm text-muted-foreground">
          Extraction de données depuis vos factures, devis et bons.
        </p>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="analyse">Analyser un document</TabsTrigger>
          <TabsTrigger value="documents">Documents sauvegardés</TabsTrigger>
        </TabsList>
        <TabsContent value="analyse">
          <AnalyseTab canSave={canSave} />
        </TabsContent>
        <TabsContent value="documents">
          <DocumentsTab canDelete={canSave} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
