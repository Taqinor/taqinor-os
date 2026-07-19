import { useCallback, useEffect, useRef, useState } from 'react'
import { FileText, Upload } from 'lucide-react'
import esgApi from '../../api/esgApi'
import recordsApi from '../../api/recordsApi'
import {
  Card, CardHeader, CardTitle, CardContent, Badge, Button, Input, Label,
  EmptyState,
} from '../../ui'

/* ============================================================================
   WIR130 — Registre des documents de politique RSE (NTESG13).
   Dépôt (métadonnées via `esg.documentsPolitique` + fichier via
   `records.Attachment`, cible `esg.documentpolitiqueesg`) et liste. Un document
   déposé alimente l'annexe du rapport ESG (NTESG4).
   ========================================================================== */

const TYPE_LABELS = {
  charte_ethique: 'Charte éthique',
  politique_environnementale: 'Politique environnementale',
  politique_diversite: 'Politique diversité',
  code_fournisseur: 'Code fournisseur',
}

const STATUT_TONE = { brouillon: 'neutral', publiee: 'success', obsolete: 'warning' }

export default function DocumentsPolitiqueSection() {
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({ libelle: '', type_document: 'charte_ethique' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const fileRef = useRef(null)

  const load = useCallback(() => {
    setLoading(true)
    esgApi.documentsPolitique.list()
      .then((res) => setDocuments(res.data?.results ?? res.data ?? []))
      .catch(() => setError("Impossible de charger les politiques."))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch-on-mount: reuses the shared `load` refresh helper
  useEffect(() => { load() }, [load])

  const deposer = async () => {
    setError('')
    if (!form.libelle.trim()) {
      setError('Le libellé est requis.')
      return
    }
    setSaving(true)
    try {
      const res = await esgApi.documentsPolitique.create({
        libelle: form.libelle.trim(),
        type_document: form.type_document,
      })
      const file = fileRef.current?.files?.[0]
      if (file) {
        await recordsApi.uploadAttachment('esg.documentpolitiqueesg', res.data.id, file)
      }
      setForm({ libelle: '', type_document: 'charte_ethique' })
      if (fileRef.current) fileRef.current.value = ''
      load()
    } catch {
      setError('Le dépôt a échoué.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className="mt-4">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileText size={18} strokeWidth={1.75} aria-hidden="true" />
          Politiques RSE (annexe du rapport)
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="mb-4 flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[12rem]">
            <Label htmlFor="doc-libelle">Libellé</Label>
            <Input
              id="doc-libelle" value={form.libelle}
              placeholder="ex : Charte éthique 2026"
              onChange={(e) => setForm((f) => ({ ...f, libelle: e.target.value }))}
            />
          </div>
          <div>
            <Label htmlFor="doc-type">Type</Label>
            <select
              id="doc-type" className="form-select"
              value={form.type_document}
              onChange={(e) => setForm((f) => ({ ...f, type_document: e.target.value }))}
            >
              {Object.entries(TYPE_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>
          <div>
            <Label htmlFor="doc-fichier">Fichier</Label>
            <input
              id="doc-fichier" ref={fileRef} type="file"
              aria-label="Fichier de politique"
            />
          </div>
          <Button size="sm" disabled={saving} onClick={deposer}>
            <Upload size={16} /> Déposer
          </Button>
        </div>
        {error && <p className="form-error mb-2" role="alert">{error}</p>}

        {loading ? (
          <p className="text-sm text-muted-foreground">Chargement…</p>
        ) : documents.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="Aucune politique déposée"
            description="Déposez une charte ou politique RSE pour l'annexer au rapport ESG."
            className="border-0 py-4"
          />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left">
                <th className="px-2 py-1">Libellé</th>
                <th className="px-2 py-1">Type</th>
                <th className="px-2 py-1">Statut</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((d) => (
                <tr key={d.id} className="border-b border-border/60">
                  <td className="px-2 py-1">{d.libelle}</td>
                  <td className="px-2 py-1">
                    {d.type_document_display || TYPE_LABELS[d.type_document] || d.type_document}
                  </td>
                  <td className="px-2 py-1">
                    <Badge tone={STATUT_TONE[d.statut] ?? 'neutral'}>
                      {d.statut_display || d.statut}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  )
}
