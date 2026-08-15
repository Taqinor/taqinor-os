// XGED12 — Capture mobile photo → PDF multi-pages classé en GED.
//
// Écran « Numériser » : prises de photos successives à la caméra (réutilise
// `CameraCapture` — même composant `getUserMedia` que FG385 côté
// interventions), recadrage/rotation CÔTÉ CLIENT via canvas (`capture.js`),
// puis upload multipart de toutes les photos vers `documents/assembler-photos/`
// — l'assemblage en UN SEUL PDF multi-pages se fait CÔTÉ SERVEUR (Pillow, déjà
// pinné). Passe par le MÊME chemin que le téléversement existant (U14) : le
// PDF assemblé devient un Document + version 1 dans le dossier choisi, avec
// les métadonnées saisies sur le terrain (nom/description).
import { useEffect, useMemo, useState } from 'react'
import {
  Camera, Trash2, RotateCw, Loader2, FileText, Upload, X,
} from 'lucide-react'
import gedApi from '../../api/gedApi'
// APX32 (e) — en-tête UNIQUE de l'app (VX28), fin du 4ᵉ idiome.
import { PageHeader } from '../../ui/PageHeader'
import {
  Card, CardContent, Button, EmptyState, Select, SelectTrigger, SelectValue,
  SelectContent, SelectItem, Input, Textarea, toast, FloatingActionButton,
} from '../../ui'
import CameraCapture from '../pwa/CameraCapture.jsx'
import { compressPhotoForUpload } from '../../pages/preferences/prefs'
import { buildFolderTree, flattenVisible } from './tree.js'
import {
  makeCapturedPage, rotatePageInList, removePageFromList, rotateImageBlob,
} from './capture.js'

const rows = (r) => r?.data?.results ?? r?.data ?? []

const errText = (e, fallback) => {
  const d = e?.response?.data
  if (typeof d === 'string') return d
  if (d && typeof d === 'object') {
    const first = d.detail ?? Object.values(d)[0]
    if (Array.isArray(first)) return String(first[0])
    if (first) return String(first)
  }
  return fallback
}

let nextPageId = 1

export default function NumeriserPage() {
  const [cabinets, setCabinets] = useState([])
  const [cabinetId, setCabinetId] = useState(null)
  const [folders, setFolders] = useState([])
  const [folderId, setFolderId] = useState('')

  const [pages, setPages] = useState([]) // [{id, file, rotation}]
  const [cameraOpen, setCameraOpen] = useState(false)
  const [nom, setNom] = useState('')
  const [description, setDescription] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  // WIR249/GED31 — numérisation par LOT : N fichiers déjà scannés en un appel.
  // WIR249/GED32 — import en MASSE : un CSV de métadonnées (+ ZIP de binaires).
  // Les deux renvoient un rapport `erreurs` PAR LIGNE : on l'affiche, on ne
  // le tait jamais derrière un « import terminé ».
  const [lotFiles, setLotFiles] = useState([])
  const [csvFile, setCsvFile] = useState(null)
  const [zipFile, setZipFile] = useState(null)
  const [rapport, setRapport] = useState(null) // { titre, crees, erreurs: [] }

  useEffect(() => {
    let alive = true
    gedApi.getCabinets()
      .then((r) => {
        if (!alive) return
        const list = rows(r)
        setCabinets(list)
        if (list.length) setCabinetId((c) => c ?? list[0].id)
      })
      .catch(() => { if (alive) setError('Impossible de charger les armoires.') })
    return () => { alive = false }
  }, [])

  useEffect(() => {
    if (cabinetId == null) return
    let alive = true
    gedApi.getDossiers({ cabinet: cabinetId })
      .then((r) => { if (alive) setFolders(rows(r)) })
      .catch(() => { if (alive) setFolders([]) })
    return () => { alive = false }
  }, [cabinetId])

  const folderOptions = useMemo(() => {
    const tree = buildFolderTree(folders)
    return flattenVisible(tree, new Set(folders.map((f) => f.id)))
  }, [folders])

  // NTMOB12 — compresse AVANT d'ajouter à la liste (respecte la préférence
  // « Qualité photo », Mes préférences) : réduit la consommation data et
  // accélère l'upload final, la rotation (submit) opère sur le fichier déjà
  // compressé sans perte perceptible supplémentaire.
  const addPhoto = async (file) => {
    const compressed = await compressPhotoForUpload(file)
    setPages((prev) => [...prev, makeCapturedPage(nextPageId++, compressed)])
    setCameraOpen(false)
  }

  const rotate = (id) => setPages((prev) => rotatePageInList(prev, id))
  const remove = (id) => setPages((prev) => removePageFromList(prev, id))

  const submit = async (e) => {
    e.preventDefault()
    if (!folderId || pages.length === 0 || busy) return
    setBusy(true)
    try {
      // Applique la rotation choisie côté client (canvas) AVANT l'envoi — le
      // serveur reçoit des photos déjà orientées, il ne fait qu'assembler.
      const photos = await Promise.all(
        pages.map((p) => (p.rotation === 0
          ? Promise.resolve(p.file)
          : rotateImageBlob(p.file, p.rotation))))
      const resp = await gedApi.assemblerPhotos({
        folder: folderId, photos, nom: nom.trim(), description: description.trim(),
      })
      toast.success(
        `PDF de ${pages.length} page${pages.length > 1 ? 's' : ''} classé dans la GED.`)
      setPages([])
      setNom('')
      setDescription('')
      return resp
    } catch (err) {
      toast.error(errText(err, 'Assemblage impossible.'))
    } finally {
      setBusy(false)
    }
  }

  // WIR249/GED31 — dépôt d'un LOT de fichiers déjà numérisés (multipart, clé
  // `files` répétée : c'est ce que `request.FILES.getlist('files')` lit).
  const submitLot = async () => {
    if (!folderId || lotFiles.length === 0 || busy) return
    setBusy(true); setRapport(null)
    try {
      const fd = new FormData()
      fd.append('folder', folderId)
      lotFiles.forEach((f) => fd.append('files', f))
      const resp = await gedApi.scanLot(fd)
      const documents = resp?.data?.documents || []
      const erreurs = resp?.data?.erreurs || []
      setRapport({ titre: 'Numérisation par lot', crees: documents.length, erreurs })
      if (documents.length) toast.success(`${documents.length} document(s) déposé(s).`)
      if (erreurs.length) toast.error(`${erreurs.length} fichier(s) refusé(s).`)
      setLotFiles([])
    } catch (err) {
      toast.error(errText(err, 'Dépôt du lot impossible.'))
    } finally { setBusy(false) }
  }

  // WIR249/GED32 — import en MASSE depuis un CSV (+ ZIP optionnel de binaires).
  const submitImportMasse = async () => {
    if (!folderId || !csvFile || busy) return
    setBusy(true); setRapport(null)
    try {
      const fd = new FormData()
      fd.append('folder', folderId)
      fd.append('csv', csvFile)
      if (zipFile) fd.append('zip', zipFile)
      const resp = await gedApi.importMasse(fd)
      const crees = resp?.data?.crees ?? (resp?.data?.documents || []).length
      const erreurs = resp?.data?.erreurs || []
      setRapport({ titre: 'Import en masse', crees, erreurs })
      if (crees) toast.success(`${crees} document(s) créé(s).`)
      if (erreurs.length) toast.error(`${erreurs.length} ligne(s) en erreur.`)
      setCsvFile(null); setZipFile(null)
    } catch (err) {
      toast.error(errText(err, 'Import en masse impossible.'))
    } finally { setBusy(false) }
  }

  const hasCabinet = cabinetId != null

  return (
    <div className="page">
      {/* APX32 (e) — 4ᵉ idiome d'en-tête du repo (`<h1>` nu + `<p>` en taille
          arbitraire) : l'en-tête UNIQUE de l'app (VX28). */}
      <PageHeader
        className="mb-4"
        icon={Camera}
        title="Numériser"
        subtitle="Prenez des photos successives à la caméra du téléphone — elles seront assemblées en un seul PDF et classées dans le dossier choisi."
      />

      {error ? (
        <EmptyState title="Erreur" description={error} />
      ) : (
        <div className="grid gap-4 md:grid-cols-[minmax(240px,340px)_1fr]">
          <Card>
            <CardContent className="flex flex-col gap-3 p-4">
              <label className="grid gap-1 text-[13px]">
                <span className="text-muted-foreground">Armoire</span>
                <Select value={cabinetId != null ? String(cabinetId) : ''}
                  onValueChange={(v) => { setCabinetId(Number(v)); setFolderId('') }}>
                  <SelectTrigger aria-label="Choisir l'armoire">
                    <SelectValue placeholder="Armoire" />
                  </SelectTrigger>
                  <SelectContent>
                    {cabinets.map((c) => (
                      <SelectItem key={c.id} value={String(c.id)}>{c.nom}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </label>

              <label className="grid gap-1 text-[13px]">
                <span className="text-muted-foreground">Dossier de destination</span>
                <Select value={folderId ? String(folderId) : ''}
                  onValueChange={(v) => setFolderId(Number(v))}
                  disabled={!hasCabinet}>
                  <SelectTrigger aria-label="Choisir le dossier">
                    <SelectValue placeholder="Dossier" />
                  </SelectTrigger>
                  <SelectContent>
                    {folderOptions.map((f) => (
                      <SelectItem key={f.id} value={String(f.id)}>
                        {'  '.repeat(f.depth)}{f.nom}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </label>

              <Input aria-label="Nom du document"
                placeholder="Nom du document (ex. Chantier Casablanca)"
                value={nom} onChange={(e) => setNom(e.target.value)} />
              <Textarea aria-label="Description" rows={2}
                placeholder="Description / métadonnées de terrain (optionnel)"
                value={description} onChange={(e) => setDescription(e.target.value)} />
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              {cameraOpen ? (
                <CameraCapture
                  onCapture={addPhoto}
                  onClose={() => setCameraOpen(false)}
                  filename={`page-${pages.length + 1}.jpg`}
                />
              ) : (
                <Button onClick={() => setCameraOpen(true)} disabled={!hasCabinet}>
                  <Camera className="size-4" aria-hidden="true" />
                  {pages.length === 0 ? 'Prendre la première photo' : 'Ajouter une photo'}
                </Button>
              )}

              {pages.length === 0 ? (
                <p className="mt-4 text-[13px] text-muted-foreground">
                  Aucune photo pour l'instant. Chaque photo devient une page du
                  PDF final, dans l'ordre de capture.
                </p>
              ) : (
                <ul className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {pages.map((p, idx) => (
                    <li key={p.id}
                      className="relative overflow-hidden rounded-lg border border-border bg-muted/30">
                      <img
                        src={URL.createObjectURL(p.file)}
                        alt={`Page ${idx + 1}`}
                        style={{ transform: `rotate(${p.rotation}deg)` }}
                        loading="lazy"
                        className="aspect-[3/4] w-full object-cover" />
                      <span className="absolute left-1 top-1 rounded bg-black/60 px-1.5 py-0.5 text-[11px] text-white">
                        Page {idx + 1}
                      </span>
                      <div className="absolute right-1 top-1 flex gap-1">
                        <button type="button" title="Pivoter"
                          onClick={() => rotate(p.id)}
                          className="rounded-full bg-black/60 p-1 text-white">
                          <RotateCw className="size-3.5" aria-hidden="true" />
                        </button>
                        <button type="button" title="Supprimer"
                          onClick={() => remove(p.id)}
                          className="rounded-full bg-black/60 p-1 text-white">
                          <X className="size-3.5" aria-hidden="true" />
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}

              <div className="mt-4 flex items-center gap-2">
                <Button variant="default" onClick={submit}
                  disabled={!folderId || pages.length === 0 || busy}>
                  {busy
                    ? <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                    : <Upload className="size-4" aria-hidden="true" />}
                  Assembler en PDF et classer ({pages.length})
                </Button>
                {pages.length > 0 && !busy && (
                  <Button variant="ghost" onClick={() => setPages([])}>
                    <Trash2 className="size-4" aria-hidden="true" /> Tout effacer
                  </Button>
                )}
              </div>
              {!folderId && pages.length > 0 && (
                <p className="mt-2 flex items-center gap-1 text-[12.5px] text-muted-foreground">
                  <FileText className="size-3.5" aria-hidden="true" />
                  Choisissez un dossier de destination avant d'assembler.
                </p>
              )}
            </CardContent>
          </Card>

          {/* WIR249/GED31+GED32 — deux entrées de MASSE, à côté de la capture
              photo : un lot de fichiers déjà scannés, et un CSV de métadonnées.
              Elles partagent le dossier de destination choisi à gauche. */}
          <Card className="md:col-span-2">
            <CardContent className="grid gap-4 p-4 md:grid-cols-2">
              <div className="grid gap-2">
                <h3 className="text-sm font-semibold">Déposer un lot de fichiers</h3>
                <p className="text-[12.5px] text-muted-foreground">
                  Plusieurs fichiers déjà numérisés, en un seul envoi. Un fichier
                  au format refusé est signalé sans bloquer les autres.
                </p>
                <input type="file" multiple aria-label="Fichiers du lot"
                  data-testid="ged-scanlot-files"
                  onChange={(e) => setLotFiles(Array.from(e.target.files || []))} />
                <Button data-testid="ged-scanlot-submit" onClick={submitLot}
                  disabled={!folderId || lotFiles.length === 0 || busy}>
                  {busy
                    ? <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                    : <Upload className="size-4" aria-hidden="true" />}
                  Déposer le lot ({lotFiles.length})
                </Button>
              </div>

              <div className="grid gap-2">
                <h3 className="text-sm font-semibold">Import en masse (CSV)</h3>
                <p className="text-[12.5px] text-muted-foreground">
                  Une ligne par document (colonnes nom, description, fichier).
                  Le ZIP est optionnel : il fournit les binaires appariés par la
                  colonne « fichier ».
                </p>
                <input type="file" accept=".csv,text/csv" aria-label="Fichier CSV"
                  data-testid="ged-import-csv"
                  onChange={(e) => setCsvFile(e.target.files?.[0] || null)} />
                <input type="file" accept=".zip" aria-label="Archive ZIP (optionnelle)"
                  data-testid="ged-import-zip"
                  onChange={(e) => setZipFile(e.target.files?.[0] || null)} />
                <Button data-testid="ged-import-submit" onClick={submitImportMasse}
                  disabled={!folderId || !csvFile || busy}>
                  {busy
                    ? <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                    : <Upload className="size-4" aria-hidden="true" />}
                  Importer
                </Button>
              </div>

              {/* Le rapport d'erreurs LIGNE PAR LIGNE, jamais masqué. */}
              {rapport && (
                <div className="md:col-span-2" data-testid="ged-masse-rapport">
                  <p className="text-[13px]">
                    {rapport.titre} — {rapport.crees} document(s) créé(s),{' '}
                    {rapport.erreurs.length} erreur(s).
                  </p>
                  {rapport.erreurs.length > 0 && (
                    <ul className="mt-1 grid gap-0.5 text-[12.5px] text-destructive">
                      {rapport.erreurs.map((e, i) => (
                        <li key={i} data-testid="ged-masse-erreur">
                          {e.fichier || e.ligne || e.nom || '—'} : {e.erreur || e.detail || 'refusé'}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* VX42 — FAB : le pouce vit dans le tiers bas de l'écran sur le
          terrain. Masqué le temps que la caméra est déjà ouverte ou tant
          qu'aucune armoire n'est choisie. Libellé DISTINCT du bouton inline
          « Prendre la première photo »/« Ajouter une photo » (même action,
          mais un nom accessible différent — deux boutons identiques
          coexistent à l'écran, un test `getByRole` sur l'un ne doit jamais
          matcher les deux). */}
      {hasCabinet && !cameraOpen && (
        <FloatingActionButton
          label="Photo (caméra)"
          icon={<Camera className="size-5" aria-hidden="true" />}
          onClick={() => setCameraOpen(true)} />
      )}
    </div>
  )
}
