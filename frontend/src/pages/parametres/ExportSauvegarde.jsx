import { useEffect, useRef, useState } from 'react'
import { Download, Archive, Settings, Upload } from 'lucide-react'
import PageHeader from '../../components/layout/PageHeader'
import {
  Card, CardContent, Button, Checkbox, Segmented, Spinner, toast,
} from '../../ui'
import api from '../../api/axios'
import importApi, { downloadBlob, filenameFromResponse } from '../../api/importApi'

const today = () => new Date().toISOString().slice(0, 10)

// N97 — Export configurable & sauvegarde complète (admin uniquement).
// L'utilisateur choisit les objets + le format et télécharge un fichier par
// objet OU une archive ZIP. Les prix d'achat / marges ne sont jamais inclus
// (garanti côté serveur).
export default function ExportSauvegarde() {
  const [objects, setObjects] = useState([])
  const [formats, setFormats] = useState([])
  const [selected, setSelected] = useState(() => new Set())
  const [format, setFormat] = useState('csv')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [denied, setDenied] = useState(false)
  // FG24 — export/import de la configuration entre sociétés.
  const [cfgBusy, setCfgBusy] = useState(false)
  const [cfgOverwrite, setCfgOverwrite] = useState(false)
  const cfgFileRef = useRef(null)

  const exportConfig = async () => {
    setCfgBusy(true)
    try {
      const { data } = await api.get('/parametres/config-export/')
      const blob = new Blob([JSON.stringify(data, null, 2)],
        { type: 'application/json' })
      downloadBlob(blob, `configuration_${today()}.json`)
    } catch {
      toast.error('L’export de configuration a échoué.')
    } finally { setCfgBusy(false) }
  }

  const importConfig = async (file) => {
    if (!file) return
    setCfgBusy(true)
    try {
      const text = await file.text()
      const bundle = JSON.parse(text)
      const mode = cfgOverwrite ? '?mode=overwrite' : ''
      await api.post(`/parametres/config-import/${mode}`, bundle)
      toast.success('Configuration importée.')
    } catch {
      toast.error('Fichier de configuration invalide ou import refusé.')
    } finally {
      setCfgBusy(false)
      if (cfgFileRef.current) cfgFileRef.current.value = ''
    }
  }

  useEffect(() => {
    importApi.getExportObjects()
      .then((r) => {
        const objs = r.data.objects || []
        setObjects(objs)
        setFormats(r.data.formats || [])
        setFormat(r.data.default_format || 'csv')
        // Par défaut : tout coché (sauvegarde complète prête en un clic).
        setSelected(new Set(objs.map((o) => o.key)))
      })
      .catch((e) => {
        if (e?.response?.status === 403) setDenied(true)
        else toast.error('Service d’export indisponible.')
      })
      .finally(() => setLoading(false))
  }, [])

  const toggle = (key) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const allSelected = objects.length > 0 && selected.size === objects.length
  const toggleAll = () =>
    setSelected(allSelected ? new Set() : new Set(objects.map((o) => o.key)))

  const exportOne = async (key) => {
    setBusy(true)
    try {
      const res = await importApi.exportObject(key, format)
      downloadBlob(res.data, filenameFromResponse(res, `${key}_${today()}.${format}`))
    } catch {
      toast.error('L’export a échoué.')
    } finally {
      setBusy(false)
    }
  }

  const sauvegarder = async () => {
    if (selected.size === 0) {
      toast.error('Sélectionnez au moins un objet.')
      return
    }
    setBusy(true)
    try {
      const res = await importApi.sauvegarde([...selected], format)
      downloadBlob(res.data, filenameFromResponse(res, `sauvegarde_${today()}.zip`))
    } catch {
      toast.error('La sauvegarde a échoué.')
    } finally {
      setBusy(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Spinner />
      </div>
    )
  }

  if (denied) {
    return (
      <div className="p-4 sm:p-6">
        <PageHeader title="Export & sauvegarde" />
        <Card>
          <CardContent className="pt-5 text-sm text-muted-foreground">
            Accès réservé aux administrateurs.
          </CardContent>
        </Card>
      </div>
    )
  }

  const formatOptions = formats.map((f) => ({ value: f.key, label: f.label }))

  return (
    <div className="p-4 sm:p-6">
      <PageHeader
        title="Export & sauvegarde"
        subtitle={
          'Exportez les données de votre société (clients, leads, '
          + 'devis, factures, chantiers, stock…) ou générez une '
          + 'sauvegarde complète (ZIP). Les prix d’achat et marges ne '
          + 'sont jamais inclus.'
        }
        actions={
          <Button onClick={sauvegarder} loading={busy} disabled={busy || selected.size === 0}>
            <Archive className="size-4" aria-hidden="true" />
            Sauvegarde complète (ZIP)
          </Button>
        }
      />

      <Card className="mt-4">
        <CardContent className="pt-5 space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm font-medium">Format :</span>
            <Segmented
              options={formatOptions}
              value={format}
              onChange={setFormat}
            />
            <span className="text-sm text-muted-foreground">
              {selected.size} objet(s) sélectionné(s)
            </span>
          </div>

          <div className="rounded-lg border border-border divide-y divide-border">
            <label className="flex items-center gap-3 px-3 py-2 text-sm font-medium">
              <Checkbox
                checked={allSelected}
                onCheckedChange={toggleAll}
                aria-label="Tout sélectionner"
              />
              Tout sélectionner
            </label>
            {objects.map((o) => (
              <div key={o.key} className="flex items-center gap-3 px-3 py-2">
                <Checkbox
                  checked={selected.has(o.key)}
                  onCheckedChange={() => toggle(o.key)}
                  aria-label={`Sélectionner ${o.label}`}
                />
                <span className="flex-1 text-sm">{o.label}</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => exportOne(o.key)}
                  disabled={busy}
                >
                  <Download className="size-3.5" aria-hidden="true" />
                  Exporter
                </Button>
              </div>
            ))}
            {objects.length === 0 && (
              <div className="px-3 py-8 text-center text-sm text-muted-foreground">
                Aucun objet exportable.
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* FG24 — Configuration (réplication entre sociétés). Jamais de secrets
          ni de données métier ; import additif (admin uniquement). */}
      <Card className="mt-4">
        <CardContent className="pt-5 space-y-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <Settings className="h-4 w-4" /> Configuration (réplication entre sociétés)
          </div>
          <p className="text-[12.5px] text-muted-foreground">
            Exporte/importe la <strong>configuration</strong> reproductible
            (profil métier, rôles personnalisés, modèles de message, règles
            d’automatisation, statuts, textes de documents) — jamais les
            secrets (RIB, clés) ni les données métier. L’import est additif :
            « fusionner » n’écrase rien, « écraser » met à jour l’existant.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="outline" onClick={exportConfig} loading={cfgBusy}>
              <Download className="h-4 w-4" /> Exporter la configuration
            </Button>
            <input
              ref={cfgFileRef} type="file" accept="application/json,.json"
              className="hidden"
              onChange={(e) => importConfig(e.target.files?.[0])}
            />
            <Button
              variant="outline"
              onClick={() => cfgFileRef.current?.click()}
              loading={cfgBusy}
            >
              <Upload className="h-4 w-4" /> Importer un fichier
            </Button>
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <input type="checkbox" checked={cfgOverwrite}
                     onChange={(e) => setCfgOverwrite(e.target.checked)} />
              Écraser l’existant
            </label>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
