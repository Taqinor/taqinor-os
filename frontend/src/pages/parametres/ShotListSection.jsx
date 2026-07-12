// F7/F8 — Onglet « Documentation terrain » de la page Paramètres : la SHOT LIST
// des prises de vue guidées d'une intervention. Chaque créneau définit une vue
// attendue, groupée par phase (avant/pendant/après). `Obligatoire` pilote
// l'application F8 : une intervention ne peut passer à « Terminée » tant qu'un
// créneau obligatoire n'a pas au moins une photo.
//
// Section autonome : charge ses propres données et s'enregistre seule (sans le
// bouton « Enregistrer » global). Texte en français ; clés techniques en anglais.
import { useEffect, useState } from 'react'
import { Plus, Trash2, ChevronUp, ChevronDown, AlertCircle } from 'lucide-react'
import installationsApi from '../../api/installationsApi'
import {
  Card, CardContent, Input, Button, IconButton, Badge, Spinner, EmptyState,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { SectionTitle } from './peComponents'
import { toast } from '../../ui/confirm'

const PHASES = [
  ['avant', 'Avant'],
  ['pendant', 'Pendant'],
  ['apres', 'Après'],
]
const PHASE_LABELS = Object.fromEntries(PHASES)

// Clé technique stable dérivée d'un libellé (anglais/ASCII, sans accents).
const slugify = (s) => s.trim().toLowerCase()
  .normalize('NFD').replace(/[̀-ͯ]/g, '')
  .replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 40)

export default function ShotListSection() {
  const [slots, setSlots] = useState([])
  const [loading, setLoading] = useState(true)
  // ERR62 — un échec de chargement affiche une erreur + Réessayer (pas un état
  // « vide » trompeur faisant croire qu'aucun créneau n'existe).
  const [loadError, setLoadError] = useState(false)
  const [newLibelle, setNewLibelle] = useState('')
  const [newPhase, setNewPhase] = useState('avant')

  const load = () => installationsApi.getShotlistSlots()
    .then((r) => { setSlots(r.data.results ?? r.data); setLoadError(false) })
    .catch(() => setLoadError(true))
    .finally(() => setLoading(false))
  useEffect(() => { load() }, [])

  const add = async () => {
    const libelle = newLibelle.trim()
    if (!libelle) return
    try {
      await installationsApi.saveShotlistSlot(null, {
        cle: slugify(libelle) || `shot_${Date.now()}`,
        libelle, phase: newPhase, ordre: slots.length,
      })
      setNewLibelle(''); setNewPhase('avant'); load()
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Ajout impossible.') }
  }
  const rename = async (s, libelle) => {
    if (!libelle.trim() || libelle === s.libelle) return
    try { await installationsApi.saveShotlistSlot(s.id, { libelle }); load() }
    catch { /* */ }
  }
  const setPhase = async (s, phase) => {
    try { await installationsApi.saveShotlistSlot(s.id, { phase }); load() } catch { /* */ }
  }
  const toggleObligatoire = async (s) => {
    try { await installationsApi.saveShotlistSlot(s.id, { obligatoire: !s.obligatoire }); load() }
    catch { /* */ }
  }
  const toggleActif = async (s) => {
    try { await installationsApi.saveShotlistSlot(s.id, { actif: !s.actif }); load() } catch { /* */ }
  }
  const move = async (idx, dir) => {
    const j = idx + dir
    if (j < 0 || j >= slots.length) return
    const a = slots[idx]; const b = slots[j]
    try {
      await Promise.all([
        installationsApi.saveShotlistSlot(a.id, { ordre: b.ordre }),
        installationsApi.saveShotlistSlot(b.id, { ordre: a.ordre }),
      ])
      load()
    } catch { /* */ }
  }
  const del = async (s) => {
    if (!window.confirm(`Supprimer le créneau « ${s.libelle} » ?`)) return
    try { await installationsApi.deleteShotlistSlot(s.id); load() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Suppression impossible (créneau protégé ?).') }
  }

  if (loading) return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <Spinner className="size-4 text-primary" /> Chargement…
    </p>
  )

  if (loadError) return (
    <div className="flex flex-col items-start gap-2">
      <p className="flex items-center gap-2 text-sm text-destructive">
        <AlertCircle className="size-4" aria-hidden="true" />
        Shot list indisponible (serveur ?).
      </p>
      <Button type="button" size="sm" variant="outline" onClick={load}>Réessayer</Button>
    </div>
  )

  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle label="Documentation terrain — Shot list"
          icon={<><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></>}/>
        <p className="mb-3.5 text-[11.5px] text-muted-foreground">
          Composez la liste des prises de vue attendues lors d'une intervention,
          groupées par phase (avant / pendant / après). Un créneau marqué
          « Obligatoire » doit avoir au moins une photo avant que l'intervention
          puisse passer à « Terminée ». Désactiver un créneau le retire des
          nouvelles interventions sans toucher à l'historique.
        </p>

        <div className="flex flex-col gap-2">
          {slots.length === 0 && (
            <EmptyState title="Aucun créneau"
              description="Ajoutez votre premier créneau de shot list ci-dessous." className="py-6" />
          )}
          {slots.map((s, i) => (
            <div key={s.id} className="flex flex-wrap items-center gap-1.5 rounded-lg border border-border p-2">
              {/* ERR102 — re-monte le champ si le serveur normalise le libellé. */}
              <Input key={s.libelle} className={['min-w-[140px] flex-[1_1_140px]', s.actif ? '' : 'opacity-50'].join(' ')}
                defaultValue={s.libelle} onBlur={(e) => rename(s, e.target.value)} />
              <div className="w-[120px]">
                <Select value={s.phase} onValueChange={(v) => setPhase(s, v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {PHASES.map(([v, lbl]) => (
                      <SelectItem key={v} value={v}>{lbl}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button type="button" size="sm"
                variant={s.obligatoire ? 'default' : 'outline'}
                title="Photo requise pour passer à « Terminée »"
                onClick={() => toggleObligatoire(s)}>
                Obligatoire
              </Button>
              <div className="ml-auto flex items-center gap-1">
                <IconButton size="sm" variant="ghost" label="Monter"
                  disabled={i === 0} onClick={() => move(i, -1)}>
                  <ChevronUp className="size-4" aria-hidden="true" />
                </IconButton>
                <IconButton size="sm" variant="ghost" label="Descendre"
                  disabled={i === slots.length - 1} onClick={() => move(i, 1)}>
                  <ChevronDown className="size-4" aria-hidden="true" />
                </IconButton>
                <Button type="button" size="sm"
                  variant={s.actif ? 'success' : 'secondary'}
                  title={s.actif ? 'Désactiver' : 'Activer'}
                  onClick={() => toggleActif(s)}>
                  {s.actif ? 'Actif' : 'Inactif'}
                </Button>
                {s.protege ? (
                  <Badge tone="info">système</Badge>
                ) : (
                  <IconButton size="sm" variant="outline" label="Supprimer le créneau"
                    className="text-destructive hover:text-destructive"
                    onClick={() => del(s)}>
                    <Trash2 className="size-4" aria-hidden="true" />
                  </IconButton>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* ── Ajout d'un créneau ── */}
        <div className="mt-3 flex flex-wrap gap-1.5">
          <Input className="min-w-[160px] flex-[1_1_160px]" placeholder="Nouveau créneau (ex. Toiture après pose)"
            value={newLibelle} onChange={(e) => setNewLibelle(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add() } }} />
          <div className="w-[140px]">
            <Select value={newPhase} onValueChange={setNewPhase}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {PHASES.map(([v]) => (
                  <SelectItem key={v} value={v}>{PHASE_LABELS[v]}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button type="button" onClick={add}>
            <Plus className="size-4" aria-hidden="true" /> Ajouter
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
