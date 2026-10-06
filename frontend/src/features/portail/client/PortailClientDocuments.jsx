import { useEffect, useState } from 'react'
import { FolderOpen } from 'lucide-react'
import portailApi from '../../../api/portailApi'
import {
  Button, Card, EmptyState, Input, Spinner,
} from '../../../ui'
import { formatDate } from '../../../lib/format'

/* ============================================================================
   ADOC135 (D-ADOC-1) — « Mes documents » du portail client.
   ----------------------------------------------------------------------------
   Contrat `mes_documents.json` : documents GED partagés avec le client, avec la
   VERSION EN VIGUEUR (`version_numero`) et sa date (`version_date`, jamais
   `date_creation`) — ce que le client voit = ce que contient le fichier
   téléchargé. Téléchargement = GET `/mes-documents/<id>/telecharger/` ; dépôt
   d'un justificatif = POST multipart `/mes-documents/` (company/client forcés
   côté serveur ; un compte lecture seule reçoit le 403 dont le message est
   affiché tel quel).
   ========================================================================== */

const TYPES_DEPOT = [
  { value: 'facture_onee', label: 'Facture ONEE' },
  { value: 'plan', label: 'Plan' },
  { value: 'autre', label: 'Autre justificatif' },
]

export default function PortailClientDocuments() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)
  const [fichier, setFichier] = useState(null)
  const [typeDoc, setTypeDoc] = useState('autre')
  const [libelle, setLibelle] = useState('')
  const [envoi, setEnvoi] = useState(false)
  const [messageDepot, setMessageDepot] = useState(null)
  const [erreurDepot, setErreurDepot] = useState(null)

  const charger = () => {
    portailApi.documents.liste()
      .then((r) => { setRows(r.data?.results ?? []); setErreur(false) })
      .catch(() => setErreur(true))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    Promise.resolve().then(charger)
  }, [])

  const deposer = async (e) => {
    e.preventDefault()
    if (!fichier) return
    const form = e.target
    setMessageDepot(null)
    setErreurDepot(null)
    setEnvoi(true)
    try {
      const corps = new FormData()
      corps.append('fichier', fichier)
      corps.append('type_document', typeDoc)
      if (libelle.trim()) corps.append('libelle', libelle.trim())
      await portailApi.documents.deposer(corps)
      setMessageDepot('Justificatif déposé. Merci !')
      setFichier(null)
      setLibelle('')
      form.reset?.()
      charger()
    } catch (err) {
      const d = err?.response?.data
      setErreurDepot(d?.detail
        || (d && Object.values(d).flat().join(' '))
        || "Le dépôt n'a pas abouti.")
    } finally {
      setEnvoi(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner /> Chargement de vos documents…
      </div>
    )
  }

  if (erreur) {
    return (
      <EmptyState
        title="Documents indisponibles"
        description="Vos documents n’ont pas pu être chargés. Réessayez plus tard."
      />
    )
  }

  return (
    <>
      <div className="flex items-center gap-2">
        <FolderOpen className="size-5 text-muted-foreground" aria-hidden="true" />
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Mes documents
        </h1>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="Aucun document"
          description="Aucun document n’est partagé avec vous pour le moment."
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {rows.map((d) => (
            <Card key={d.id} className="flex flex-wrap items-start justify-between gap-3 p-4">
              <div>
                <p className="font-medium">{d.nom}</p>
                {d.reference ? (
                  <p className="text-xs text-muted-foreground">{d.reference}</p>
                ) : null}
                {d.version_numero != null && d.version_date ? (
                  <p className="text-xs text-muted-foreground"
                     data-testid={`document-version-${d.id}`}>
                    Version {d.version_numero} — mis à jour le {formatDate(d.version_date)}
                  </p>
                ) : null}
              </div>
              <Button asChild variant="outline" size="sm">
                <a href={portailApi.documents.telechargerUrl(d.id)}>
                  Télécharger
                </a>
              </Button>
            </Card>
          ))}
        </ul>
      )}

      <Card className="p-4">
        <form onSubmit={deposer} className="flex flex-col gap-3">
          <h2 className="font-medium">Déposer un justificatif</h2>
          <label className="flex flex-col gap-1.5 text-sm">
            Type de document
            <select value={typeDoc} onChange={(e) => setTypeDoc(e.target.value)}
                    className="h-9 rounded-md border border-border bg-background px-2">
              {TYPES_DEPOT.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-sm">
            Libellé (facultatif)
            <Input value={libelle} onChange={(e) => setLibelle(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1.5 text-sm">
            Fichier
            <input type="file" aria-label="Fichier"
                   onChange={(e) => setFichier(e.target.files?.[0] ?? null)} />
          </label>
          {messageDepot ? (
            <p className="text-sm text-emerald-600" role="status">{messageDepot}</p>
          ) : null}
          {erreurDepot ? (
            <p className="text-sm text-destructive" role="alert">{erreurDepot}</p>
          ) : null}
          <Button type="submit" disabled={envoi || !fichier}>
            {envoi ? 'Envoi…' : 'Déposer'}
          </Button>
        </form>
      </Card>
    </>
  )
}
