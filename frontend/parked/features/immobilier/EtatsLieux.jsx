import { useEffect, useState } from 'react'
import { ClipboardCheck, Plus, Upload } from 'lucide-react'
import api from '../../api/axios'
import immobilierApi from '../../api/immobilierApi'
import { Badge, Button, Label, toast } from '../../ui'

/* ============================================================================
   PACT77 — États des lieux d'entrée et de sortie.
   ----------------------------------------------------------------------------
   NTPRO15/16 (`apps/immobilier`) livraient déjà ``EtatLieuxImmo``/
   ``PieceEtatLieux``/``ElementEtatLieux``/``PhotoEtatLieux`` SANS AUCUN écran.
   Trois points contractuels côté backend, tenus tels quels ici :
   - la CRÉATION (``POST /immobilier/etats-lieux/``) pré-remplit la grille
     depuis le type de local — pièces et éléments sont créés AUTOMATIQUEMENT ;
   - pièces/éléments ne se créent JAMAIS directement (``pieces-etat-lieux/``
     et ``elements-etat-lieux/`` n'acceptent que GET/PATCH côté serveur) —
     seuls leur état et leur commentaire s'éditent ici ;
   - un élément de SORTIE embarque déjà ses photos d'ENTRÉE comparables
     (``photos_entree``, calculées côté serveur) — jamais recalculées ici.
   ========================================================================== */

const listOf = (data) => (Array.isArray(data) ? data : (data?.results ?? []))

const ETATS = [
  { value: 'neuf', label: 'Neuf' },
  { value: 'bon', label: 'Bon' },
  { value: 'usage_normal', label: 'Usage normal' },
  { value: 'degrade', label: 'Dégradé' },
]

export default function EtatsLieux() {
  const [baux, setBaux] = useState([])
  const [bailId, setBailId] = useState('')
  const [moment, setMoment] = useState('entree')
  const [etatsLieux, setEtatsLieux] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [loadingListe, setLoadingListe] = useState(false)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    immobilierApi.baux.list()
      .then((r) => setBaux(listOf(r.data)))
      .catch(() => toast.error('Impossible de charger les baux.'))
  }, [])

  const chargerListe = (bail) => {
    if (!bail) { setEtatsLieux([]); return }
    setLoadingListe(true)
    api.get('/immobilier/etats-lieux/', { params: { bail } })
      .then((r) => setEtatsLieux(listOf(r.data)))
      .catch(() => toast.error('Impossible de charger les états des lieux de ce bail.'))
      .finally(() => setLoadingListe(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset de la sélection au changement de bail
    setSelectedId(null)
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset du détail au changement de bail
    setDetail(null)
    chargerListe(bailId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bailId])

  const chargerDetail = (id) => {
    setSelectedId(id)
    setLoadingDetail(true)
    api.get(`/immobilier/etats-lieux/${id}/`)
      .then((r) => setDetail(r.data))
      .catch(() => toast.error('Impossible de charger cet état des lieux.'))
      .finally(() => setLoadingDetail(false))
  }

  const creerEtatLieux = async () => {
    if (!bailId) { toast.error('Choisissez un bail.'); return }
    setCreating(true)
    try {
      const res = await api.post('/immobilier/etats-lieux/', {
        bail: Number(bailId), moment, date: new Date().toISOString().slice(0, 10),
      })
      toast.success('État des lieux créé, grille pré-remplie depuis le type de local.')
      chargerListe(bailId)
      chargerDetail(res.data.id)
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Création impossible.')
    } finally {
      setCreating(false)
    }
  }

  const majPiece = async (piece, patch) => {
    try {
      await api.patch(`/immobilier/pieces-etat-lieux/${piece.id}/`, patch)
      chargerDetail(selectedId)
    } catch {
      toast.error('Mise à jour de la pièce impossible.')
    }
  }

  const majElement = async (element, patch) => {
    try {
      await api.patch(`/immobilier/elements-etat-lieux/${element.id}/`, patch)
      chargerDetail(selectedId)
    } catch {
      toast.error('Mise à jour de l’élément impossible.')
    }
  }

  const ajouterPhoto = async (elementId, file) => {
    if (!file) return
    const form = new FormData()
    form.append('photo', file)
    try {
      await api.post(
        `/immobilier/etats-lieux/${selectedId}/elements/${elementId}/photos`,
        form,
        { headers: { 'Content-Type': 'multipart/form-data' } },
      )
      toast.success('Photo ajoutée.')
      chargerDetail(selectedId)
    } catch {
      toast.error("Impossible d'ajouter cette photo.")
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <ClipboardCheck className="size-5 text-muted-foreground" aria-hidden="true" />
        <h1 className="font-display text-xl font-semibold tracking-tight">États des lieux</h1>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="el-bail">Bail</Label>
          <select
            id="el-bail"
            value={bailId}
            onChange={(e) => setBailId(e.target.value)}
            className="h-9 rounded-md border border-border bg-card px-3 text-sm"
          >
            <option value="">Choisir un bail…</option>
            {baux.map((b) => (
              <option key={b.id} value={b.id}>
                {b.local_reference || `Local #${b.local}`} — {b.locataire_nom || `Locataire #${b.locataire}`}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="el-moment">Moment</Label>
          <select
            id="el-moment"
            value={moment}
            onChange={(e) => setMoment(e.target.value)}
            className="h-9 rounded-md border border-border bg-card px-3 text-sm"
          >
            <option value="entree">Entrée</option>
            <option value="sortie">Sortie</option>
          </select>
        </div>
        <Button size="sm" onClick={creerEtatLieux} disabled={creating || !bailId}>
          <Plus className="size-4" aria-hidden="true" /> {creating ? 'Création…' : 'Créer l’état des lieux'}
        </Button>
      </div>

      {bailId && (
        <div>
          <h2 className="mb-2 text-sm font-semibold">États des lieux de ce bail</h2>
          {loadingListe && <p className="text-sm text-muted-foreground">Chargement…</p>}
          {!loadingListe && etatsLieux.length === 0 && (
            <p className="text-sm text-muted-foreground">Aucun état des lieux pour ce bail.</p>
          )}
          <div className="flex flex-wrap gap-2">
            {etatsLieux.map((el) => (
              <Button
                key={el.id}
                variant={selectedId === el.id ? 'default' : 'outline'}
                size="sm"
                onClick={() => chargerDetail(el.id)}
              >
                {el.moment_display || el.moment} — {el.date}
                {el.statut === 'signe' && <Badge tone="success" className="ml-1.5">Signé</Badge>}
              </Button>
            ))}
          </div>
        </div>
      )}

      {loadingDetail && <p className="text-sm text-muted-foreground">Chargement de l’état des lieux…</p>}

      {detail && !loadingDetail && (
        <div className="flex flex-col gap-4" data-testid="etat-lieux-detail">
          <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm">
            <span className="font-medium">{detail.bail_local_reference}</span>
            {' — '}
            {detail.moment_display || detail.moment} du {detail.date}
          </div>

          {(detail.pieces || []).map((piece) => (
            <div key={piece.id} className="rounded-lg border border-border p-3" data-testid={`piece-${piece.id}`}>
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <span className="font-medium">{piece.nom_piece}</span>
                <div className="flex items-center gap-2">
                  <select
                    aria-label={`État général — ${piece.nom_piece}`}
                    value={piece.etat_general}
                    onChange={(e) => majPiece(piece, { etat_general: e.target.value })}
                    className="h-8 rounded-md border border-border bg-card px-2 text-xs"
                  >
                    {ETATS.map((s) => (
                      <option key={s.value} value={s.value}>{s.label}</option>
                    ))}
                  </select>
                </div>
              </div>
              <textarea
                aria-label={`Commentaire de la pièce — ${piece.nom_piece}`}
                defaultValue={piece.commentaire}
                onBlur={(e) => {
                  if (e.target.value !== piece.commentaire) majPiece(piece, { commentaire: e.target.value })
                }}
                placeholder="Commentaire de la pièce…"
                className="mb-2 w-full rounded-md border border-border bg-card p-2 text-sm"
                rows={2}
              />

              <div className="flex flex-col gap-2">
                {(piece.elements || []).map((el) => (
                  <div key={el.id} className="rounded-md border border-border/70 p-2" data-testid={`element-${el.id}`}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-sm font-medium">{el.element}</span>
                      <select
                        aria-label={`État — ${el.element}`}
                        value={el.etat}
                        onChange={(e) => majElement(el, { etat: e.target.value })}
                        className="h-8 rounded-md border border-border bg-card px-2 text-xs"
                      >
                        {ETATS.map((s) => (
                          <option key={s.value} value={s.value}>{s.label}</option>
                        ))}
                      </select>
                    </div>
                    <textarea
                      aria-label={`Commentaire — ${el.element}`}
                      defaultValue={el.commentaire}
                      onBlur={(e) => {
                        if (e.target.value !== el.commentaire) majElement(el, { commentaire: e.target.value })
                      }}
                      placeholder="Commentaire…"
                      className="mt-1 w-full rounded-md border border-border bg-card p-2 text-xs"
                      rows={1}
                    />
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <span>{(el.photos || []).length} photo(s)</span>
                      <label className="inline-flex cursor-pointer items-center gap-1 text-primary">
                        <Upload className="size-3.5" aria-hidden="true" />
                        Ajouter une photo
                        <input
                          type="file" accept="image/*" className="hidden"
                          aria-label={`Ajouter une photo — ${el.element}`}
                          onChange={(e) => ajouterPhoto(el.id, e.target.files?.[0])}
                        />
                      </label>
                      {/* NTPRO16 — comparaison automatique sur un état de SORTIE :
                          les photos D'ENTRÉE du MÊME élément, calculées côté
                          serveur, jamais recalculées ici. */}
                      {detail.moment === 'sortie' && (el.photos_entree || []).length > 0 && (
                        <span data-testid={`photos-entree-${el.id}`}>
                          — {el.photos_entree.length} photo(s) d’entrée comparables
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
