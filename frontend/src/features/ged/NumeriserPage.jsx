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
import {
  Card, CardContent, Button, EmptyState, Select, SelectTrigger, SelectValue,
  SelectContent, SelectItem, Input, Textarea, toast, FloatingActionButton,
} from '../../ui'
import CameraCapture from '../pwa/CameraCapture.jsx'
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

  const addPhoto = (file) => {
    setPages((prev) => [...prev, makeCapturedPage(nextPageId++, file)])
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

  const hasCabinet = cabinetId != null

  return (
    <div className="page">
      <div className="mb-4">
        <h1 className="text-xl font-semibold">Numériser</h1>
        <p className="text-[12.5px] text-muted-foreground">
          Prenez des photos successives à la caméra du téléphone — elles seront
          assemblées en un seul PDF et classées dans le dossier choisi.
        </p>
      </div>

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
