import { useState } from 'react'
import { LayoutTemplate } from 'lucide-react'
import aoApi from '../../../api/aoApi'
import useResource from '../../../hooks/useResource'
import { unwrapList } from '../../../api/resource'
import {
  Badge, Button, Card, Input, Label, Textarea,
  EmptyState, Skeleton, toast,
} from '../../../ui'
import { getApiError } from '../../../lib/apiError'

/* ============================================================================
   AUDV24 (DRAFT165-5, AOF140) — Planches d'implantation : indices AUTOMATIQUES.
   ----------------------------------------------------------------------------
   `PlancheAO`/`services.generer_indice_planche` existaient déjà (testés) mais
   AUCUN écran ne pouvait verser une révision : ce panneau est le PREMIER
   consommateur de l'action `planches/upload/`. L'indice n'est JAMAIS saisi —
   il est posé côté serveur depuis l'empreinte SHA-256 du fichier envoyé ; un
   même contenu réenvoyé ne crée rien (aucun indice fabriqué pour rien), un
   contenu différent incrémente l'indice et ARCHIVE l'ancienne version (visible
   ici via le badge « Archivée »).
   ========================================================================== */

const errMsg = (e, fallback) => getApiError(e, fallback).message

function Champ({ id, label, children }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
    </div>
  )
}

function UploadForm({ affaireId, onEnvoye }) {
  const [codeDocument, setCodeDocument] = useState('')
  const [motif, setMotif] = useState('')
  const [fichier, setFichier] = useState(null)
  const [envoi, setEnvoi] = useState(false)

  const soumettre = async (e) => {
    e.preventDefault()
    if (!codeDocument.trim() || !fichier) return
    setEnvoi(true)
    try {
      const { data } = await aoApi.planches.upload({
        appel_offre: affaireId, code_document: codeDocument.trim(),
        fichier, motif: motif.trim(),
      })
      toast.success(`Planche ${data.reference_complete} enregistrée.`)
      setMotif('')
      setFichier(null)
      onEnvoye()
    } catch (e2) {
      toast.error(errMsg(e2, 'Planche non enregistrée.'))
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <form onSubmit={soumettre} noValidate className="grid gap-3 sm:grid-cols-4">
      <Champ id="ao-planche-code" label="Code document">
        <Input id="ao-planche-code" value={codeDocument}
               onChange={(e) => setCodeDocument(e.target.value)}
               placeholder="ex. 05" />
      </Champ>
      <Champ id="ao-planche-fichier" label="Fichier">
        <input
          id="ao-planche-fichier" type="file" className="text-sm"
          onChange={(e) => setFichier(e.target.files?.[0] ?? null)}
        />
      </Champ>
      <Champ id="ao-planche-motif" label="Motif de révision — optionnel">
        <Textarea id="ao-planche-motif" rows={1} value={motif}
                  onChange={(e) => setMotif(e.target.value)} />
      </Champ>
      <div className="flex items-end">
        <Button type="submit" disabled={envoi || !codeDocument.trim() || !fichier}>
          {envoi ? 'Envoi…' : 'Verser la planche'}
        </Button>
      </div>
    </form>
  )
}

function LignePlanche({ planche }) {
  return (
    <li className="flex flex-wrap items-center gap-2 rounded-lg border border-border p-3">
      <span className="font-mono text-sm font-semibold">{planche.reference_complete}</span>
      <Badge tone={planche.statut === 'active' ? 'success' : 'neutral'}>
        {planche.statut === 'active' ? 'Active' : 'Archivée'}
      </Badge>
      {planche.motif_revision && (
        <span className="text-xs text-muted-foreground">{planche.motif_revision}</span>
      )}
    </li>
  )
}

export default function PlanchesPanel({ affaireId }) {
  const { data: planches, loading, error, refetch } = useResource(
    () => aoApi.planches.list({ appel_offre: affaireId }), affaireId,
    {
      initialData: [],
      select: unwrapList,
      errorMessage: 'Impossible de charger les planches.',
      enabled: Boolean(affaireId),
    },
  )

  if (!affaireId) {
    return (
      <EmptyState icon={LayoutTemplate} title="Planches indisponibles"
                  description="Choisissez d’abord un appel d’offres." />
    )
  }

  // Le plus récent en tête : code_document puis indice décroissant.
  const triees = [...planches].sort((a, b) => (
    a.code_document === b.code_document
      ? b.indice.localeCompare(a.indice)
      : a.code_document.localeCompare(b.code_document)
  ))

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="font-display text-base font-semibold">Planches d'implantation</h2>
        <p className="text-xs text-muted-foreground">
          L'indice s'incrémente automatiquement au versement d'un fichier différent — l'ancienne
          version reste consultable, archivée.
        </p>
      </div>

      <Card className="p-3">
        <UploadForm affaireId={affaireId} onEnvoye={refetch} />
      </Card>

      {loading && <Skeleton className="h-32 w-full" />}
      {error && (
        <EmptyState icon={LayoutTemplate} tone="error" title="Planches indisponibles" description={error} />
      )}
      {!loading && !error && (
        triees.length === 0 ? (
          <EmptyState icon={LayoutTemplate} title="Aucune planche"
                      description="Versez la première révision avec le formulaire ci-dessus." />
        ) : (
          <ul className="flex flex-col gap-2">
            {triees.map((p) => <LignePlanche key={p.id} planche={p} />)}
          </ul>
        )
      )}
    </div>
  )
}
