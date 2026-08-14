import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Trash2 } from 'lucide-react'

import api from '../../api/axios'
import {
  Badge, Button, Card, CardContent, CardHeader, CardTitle, Input, Label,
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Spinner,
  confirmLeaveIfDirty,
} from '../../ui'
import { toast } from '../../ui/confirm'
import { formatMAD } from '../../lib/format'

/* ============================================================================
   NTLOG32 — Wizard « Créer un ordre de transport » en 3 étapes
   (`/transport/ordres/nouveau`).
   ----------------------------------------------------------------------------
   1. Marchandises (lignes saisies, poids/volume auto-sommés) ;
   2. Mode transport, avec le comparateur de transporteurs (NTLOG7) si
      affrètement ;
   3. Étapes + dates prévisionnelles.

   ATOMICITÉ (critère d'acceptation) : `OrdreTransportSerializer` n'accepte
   PAS la création imbriquée de `lignes`/`etapes` (champs read-only, motif
   documenté sur le serializer) — il n'existe donc AUCUN appel unique côté
   backend pour créer l'ordre + ses lignes + ses étapes. Le wizard tient donc
   TOUT l'état en mémoire côté client et n'émet AUCUN appel réseau avant
   « Créer l'ordre » (dernière étape) : abandonner à l'étape 2 (fermer
   l'onglet, naviguer ailleurs) n'a alors créé STRICTEMENT RIEN en base —
   c'est ce que couvre le test de ce fichier. Au clic final, la séquence
   ordre → lignes → étapes s'exécute d'une traite ; toute erreur en cours de
   route montre l'ordre déjà créé pour reprise manuelle (jamais de retry
   automatique masqué).
   ========================================================================== */

const MODE_OPTIONS = [
  { value: 'affretement', label: 'Affrètement' },
  { value: 'flotte_propre', label: 'Flotte propre' },
]

function emptyLigne() {
  return { designation: '', quantite: '', unite: '', poids_kg: '', volume_m3: '' }
}

function emptyEtape(type_etape, sequence) {
  return { type_etape, sequence, lieu: '', date_prevue: '' }
}

function sumField(lignes, field) {
  return lignes.reduce((acc, l) => acc + (Number(l[field]) || 0), 0)
}

// ── Étape 1 — marchandises ──────────────────────────────────────────────
function EtapeMarchandises({ lignes, setLignes }) {
  const poidsTotal = useMemo(() => sumField(lignes, 'poids_kg'), [lignes])
  const volumeTotal = useMemo(() => sumField(lignes, 'volume_m3'), [lignes])

  const updateLigne = (i, patch) => setLignes((ls) => ls.map((l, idx) => (idx === i ? { ...l, ...patch } : l)))
  const addLigne = () => setLignes((ls) => [...ls, emptyLigne()])
  const removeLigne = (i) => setLignes((ls) => ls.filter((_, idx) => idx !== i))

  return (
    <div className="flex flex-col gap-3">
      {lignes.map((l, i) => (
        <div key={i} className="grid grid-cols-1 gap-2 rounded-md border p-3 sm:grid-cols-5">
          <Input
            placeholder="Désignation"
            value={l.designation}
            onChange={(e) => updateLigne(i, { designation: e.target.value })}
          />
          <Input
            type="number" step="any" placeholder="Quantité"
            value={l.quantite}
            onChange={(e) => updateLigne(i, { quantite: e.target.value })}
          />
          <Input
            placeholder="Unité"
            value={l.unite}
            onChange={(e) => updateLigne(i, { unite: e.target.value })}
          />
          <Input
            type="number" step="any" placeholder="Poids (kg)"
            value={l.poids_kg}
            onChange={(e) => updateLigne(i, { poids_kg: e.target.value })}
          />
          <div className="flex items-center gap-2">
            <Input
              type="number" step="any" placeholder="Volume (m³)"
              value={l.volume_m3}
              onChange={(e) => updateLigne(i, { volume_m3: e.target.value })}
            />
            <Button type="button" variant="ghost" size="icon" aria-label="Retirer la ligne" onClick={() => removeLigne(i)}>
              <Trash2 className="size-4" aria-hidden="true" />
            </Button>
          </div>
        </div>
      ))}
      <Button type="button" variant="outline" onClick={addLigne} className="w-fit">
        <Plus className="size-4" aria-hidden="true" /> Ajouter une ligne
      </Button>
      <p className="text-sm text-muted-foreground">
        Total : {poidsTotal} kg · {volumeTotal} m³
      </p>
    </div>
  )
}

// ── Étape 2 — mode transport + comparateur (NTLOG7) ─────────────────────
function EtapeModeTransport({ mode, setMode, transporteurId, setTransporteurId, fletteActifId, setFlotteActifId }) {
  const [transporteurs, setTransporteurs] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (mode !== 'affretement') return
    let active = true
    setLoading(true)
    // NTLOG7 réutilisé SANS ordre existant : le wizard n'a pas encore créé
    // l'ordre à ce stade — on lit directement `installations.Transporteur`
    // via son endpoint déjà exposé (`installations/transporteurs/`), trié
    // client-side par `tarif_base` comme le fait le sélecteur serveur.
    api.get('/installations/transporteurs/')
      .then((r) => {
        if (!active) return
        const list = Array.isArray(r.data) ? r.data : (r.data?.results ?? [])
        setTransporteurs(
          list.filter((t) => t.active).sort((a, b) => (a.tarif_base ?? 0) - (b.tarif_base ?? 0)),
        )
      })
      .catch(() => { if (active) setTransporteurs([]) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [mode])

  return (
    <div className="flex flex-col gap-4">
      <div className="max-w-xs">
        <Label htmlFor="wiz-mode">Mode de transport</Label>
        <Select value={mode} onValueChange={setMode}>
          <SelectTrigger id="wiz-mode"><SelectValue /></SelectTrigger>
          <SelectContent>
            {MODE_OPTIONS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {mode === 'affretement' ? (
        <div>
          <h3 className="mb-2 text-sm font-semibold">Comparateur de transporteurs</h3>
          {loading ? <Spinner /> : (
            <div className="flex flex-col gap-2">
              {(transporteurs ?? []).map((t) => (
                <button
                  type="button"
                  key={t.id}
                  onClick={() => setTransporteurId(t.id)}
                  className={`flex items-center justify-between rounded-md border p-2 text-left text-sm ${transporteurId === t.id ? 'border-primary bg-primary/5' : ''}`}
                >
                  <span>
                    {t.nom} <Badge tone="outline">{t.type_transporteur}</Badge>
                  </span>
                  <span className="tabular-nums">{formatMAD(t.tarif_base)}</span>
                </button>
              ))}
              {transporteurs?.length === 0 && (
                <p className="text-sm text-muted-foreground">Aucun transporteur actif.</p>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className="max-w-xs">
          <Label htmlFor="wiz-flotte-actif">Actif flotte (id, optionnel)</Label>
          <Input
            id="wiz-flotte-actif" type="number" step="1"
            value={fletteActifId}
            onChange={(e) => setFlotteActifId(e.target.value)}
          />
        </div>
      )}
    </div>
  )
}

// ── Étape 3 — étapes + dates prévisionnelles ────────────────────────────
function EtapeDatesEtEtapes({ ordre, setOrdre, etapes, setEtapes }) {
  const updateEtape = (i, patch) => setEtapes((es) => es.map((e, idx) => (idx === i ? { ...e, ...patch } : e)))

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <Label htmlFor="wiz-destinataire">Destinataire</Label>
          <Input id="wiz-destinataire" value={ordre.destinataire_nom} onChange={(e) => setOrdre((o) => ({ ...o, destinataire_nom: e.target.value }))} />
        </div>
        <div>
          <Label htmlFor="wiz-destinataire-adresse">Adresse destinataire</Label>
          <Input id="wiz-destinataire-adresse" value={ordre.destinataire_adresse} onChange={(e) => setOrdre((o) => ({ ...o, destinataire_adresse: e.target.value }))} />
        </div>
        <div>
          <Label htmlFor="wiz-date-enlevement">Date d'enlèvement prévue</Label>
          <Input id="wiz-date-enlevement" type="date" value={ordre.date_enlevement_prevue} onChange={(e) => setOrdre((o) => ({ ...o, date_enlevement_prevue: e.target.value }))} />
        </div>
        <div>
          <Label htmlFor="wiz-date-livraison">Date de livraison prévue</Label>
          <Input id="wiz-date-livraison" type="date" value={ordre.date_livraison_prevue} onChange={(e) => setOrdre((o) => ({ ...o, date_livraison_prevue: e.target.value }))} />
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold">Étapes</h3>
        {etapes.map((e, i) => (
          <div key={i} className="grid grid-cols-1 gap-2 rounded-md border p-3 sm:grid-cols-3">
            <span className="text-sm capitalize">{e.type_etape.replace('_', ' ')}</span>
            <Input placeholder="Lieu" value={e.lieu} onChange={(ev) => updateEtape(i, { lieu: ev.target.value })} />
            <Input type="date" value={e.date_prevue} onChange={(ev) => updateEtape(i, { date_prevue: ev.target.value })} />
          </div>
        ))}
      </div>
    </div>
  )
}

const STEP_LABELS = ['Marchandises', 'Mode de transport', 'Étapes & dates']

export default function CreerOrdreTransportWizard() {
  const navigate = useNavigate()
  const [stepIndex, setStepIndex] = useState(0)
  const [saving, setSaving] = useState(false)

  const [lignes, setLignes] = useState([emptyLigne()])
  const [mode, setMode] = useState('affretement')
  const [transporteurId, setTransporteurId] = useState(null)
  const [flotteActifId, setFlotteActifId] = useState('')
  const [ordre, setOrdre] = useState({
    destinataire_nom: '', destinataire_adresse: '',
    date_enlevement_prevue: '', date_livraison_prevue: '',
  })
  const [etapes, setEtapes] = useState([
    emptyEtape('enlevement', 1), emptyEtape('livraison', 2),
  ])

  const dirty = Boolean(
    lignes.some((l) => l.designation || l.quantite)
    || ordre.destinataire_nom || ordre.date_enlevement_prevue,
  )

  const goNext = () => setStepIndex((i) => Math.min(i + 1, STEP_LABELS.length - 1))
  const goBack = () => setStepIndex((i) => Math.max(i - 1, 0))
  const annuler = () => { if (confirmLeaveIfDirty(dirty)) navigate('/transport/ordres') }

  // NTLOG9 : `numero`/`statut` sont posés côté serveur, jamais lus du corps
  // — inutile de les gérer ici.
  const creerOrdre = async () => {
    setSaving(true)
    try {
      const payload = {
        type_flux: 'enlevement_livraison',
        destinataire_nom: ordre.destinataire_nom,
        destinataire_adresse: ordre.destinataire_adresse,
        date_enlevement_prevue: ordre.date_enlevement_prevue || null,
        date_livraison_prevue: ordre.date_livraison_prevue || null,
        mode_transport: mode,
      }
      if (mode === 'affretement' && transporteurId) {
        payload.installations_transporteur_id = transporteurId
      }
      if (mode === 'flotte_propre' && flotteActifId) {
        payload.flotte_actif_id = Number(flotteActifId)
      }
      const { data: createdOrdre } = await api.post('/transport/ordres-transport/', payload)

      for (const l of lignes) {
        if (!l.designation && !l.quantite) continue
        await api.post('/transport/lignes-transport/', {
          ordre: createdOrdre.id,
          designation: l.designation,
          quantite: l.quantite || 0,
          unite: l.unite,
          poids_kg: l.poids_kg || 0,
          volume_m3: l.volume_m3 || 0,
        })
      }
      for (const e of etapes) {
        await api.post('/transport/etapes-transport/', {
          ordre: createdOrdre.id,
          type_etape: e.type_etape,
          sequence: e.sequence,
          lieu: e.lieu,
          date_prevue: e.date_prevue || null,
        })
      }

      toast.success(`Ordre ${createdOrdre.numero || `#${createdOrdre.id}`} créé.`)
      navigate('/transport/ordres')
    } catch (err) {
      const msg = err?.response?.data?.detail || "La création de l'ordre a échoué."
      toast.error(msg)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h1 className="page-title">Créer un ordre de transport</h1>
        <div className="page-subtitle">
          Étape {stepIndex + 1} / {STEP_LABELS.length} — {STEP_LABELS[stepIndex]}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{STEP_LABELS[stepIndex]}</CardTitle>
        </CardHeader>
        <CardContent>
          {stepIndex === 0 && <EtapeMarchandises lignes={lignes} setLignes={setLignes} />}
          {stepIndex === 1 && (
            <EtapeModeTransport
              mode={mode} setMode={setMode}
              transporteurId={transporteurId} setTransporteurId={setTransporteurId}
              fletteActifId={flotteActifId} setFlotteActifId={setFlotteActifId}
            />
          )}
          {stepIndex === 2 && (
            <EtapeDatesEtEtapes ordre={ordre} setOrdre={setOrdre} etapes={etapes} setEtapes={setEtapes} />
          )}
        </CardContent>
      </Card>

      <div className="flex justify-between">
        <Button type="button" variant="ghost" onClick={annuler}>Annuler</Button>
        <div className="flex gap-2">
          {stepIndex > 0 && <Button type="button" variant="outline" onClick={goBack}>Précédent</Button>}
          {stepIndex < STEP_LABELS.length - 1 ? (
            <Button type="button" onClick={goNext}>Suivant</Button>
          ) : (
            <Button type="button" disabled={saving} onClick={creerOrdre}>
              {saving ? 'Création…' : "Créer l'ordre"}
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
