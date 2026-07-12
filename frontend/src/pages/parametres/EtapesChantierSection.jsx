// CH5 — Onglet « Étapes chantier » de la page Paramètres : le Directeur
// configure le cycle de vie des chantiers (gates). Sur le modèle CH1, il peut
// ajouter / retirer / réordonner les étapes, marquer chacune bloquante ou
// consultative et attacher ses éléments requis (checklist, photos, séries,
// essais, matériel, dossier 82-21, pack de remise).
//
// La CONFIGURATION est réservée au Directeur (le backend re-vérifie) : un
// non-Directeur voit le flux en lecture seule. Section autonome (elle charge et
// enregistre ses propres données, sans le bouton « Enregistrer » global). Tout
// le texte est en français ; les clés techniques restent en anglais.
import { useEffect, useState } from 'react'
import { useHasPermission, useIsAdmin } from '../../hooks/useHasPermission'
import { Plus, Trash2, ChevronUp, ChevronDown, AlertCircle, Lock } from 'lucide-react'
import installationsApi from '../../api/installationsApi'
import {
  Card, CardContent, Input, Button, IconButton, Badge, Spinner, EmptyState,
} from '../../ui'
import { SectionTitle } from './peComponents'
import { toast } from '../../ui/confirm'

// Les exigences attachables à un gate (miroir des champs `exige_*` serveur).
const EXIGENCES = [
  ['exige_checklist', 'Checklist complète'],
  ['exige_photos', 'Photos requises'],
  ['exige_series', 'N° de série relevés'],
  ['exige_tests', 'Recette IEC 62446-1'],
  ['exige_materiel', 'Matériel disponible'],
  ['exige_dossier', 'Dossier loi 82-21'],
  ['exige_pack', 'Pack de remise'],
]

// Clé technique stable dérivée d'un libellé (anglais/ASCII, sans accents).
const slugify = (s) => s.trim().toLowerCase()
  .normalize('NFD').replace(/[̀-ͯ]/g, '')
  .replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 40)

export default function EtapesChantierSection() {
  // Le Directeur (ou un compte admin hérité) peut configurer ; sinon lecture.
  // Les deux hooks sont appelés inconditionnellement (règle des hooks).
  const isDirecteur = useHasPermission(null, ['Directeur'])
  const isAdmin = useIsAdmin()
  const canEdit = isDirecteur || isAdmin

  const [stages, setStages] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [newLibelle, setNewLibelle] = useState('')

  const load = () => installationsApi.getStagesChantier()
    .then(r => { setStages(r.data.results ?? r.data); setLoadError(false) })
    .catch(() => setLoadError(true))
    .finally(() => setLoading(false))
  useEffect(() => { load() }, [])

  const addStage = async () => {
    const libelle = newLibelle.trim()
    if (!libelle) return
    try {
      await installationsApi.saveStageChantier(null, {
        cle: slugify(libelle) || `etape_${Date.now()}`,
        libelle, ordre: stages.length,
      })
      setNewLibelle(''); load()
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Ajout impossible.') }
  }
  const renameStage = async (s, libelle) => {
    if (!libelle.trim() || libelle === s.libelle) return
    try { await installationsApi.saveStageChantier(s.id, { libelle }); load() }
    catch { /* */ }
  }
  const toggleBloquant = async (s) => {
    try { await installationsApi.saveStageChantier(s.id, { bloquant: !s.bloquant }); load() }
    catch { /* */ }
  }
  const toggleActif = async (s) => {
    try { await installationsApi.saveStageChantier(s.id, { actif: !s.actif }); load() }
    catch { /* */ }
  }
  const toggleExigence = async (s, key) => {
    try { await installationsApi.saveStageChantier(s.id, { [key]: !s[key] }); load() }
    catch { /* */ }
  }
  const moveStage = async (idx, dir) => {
    const j = idx + dir
    if (j < 0 || j >= stages.length) return
    const a = stages[idx]; const b = stages[j]
    try {
      await Promise.all([
        installationsApi.saveStageChantier(a.id, { ordre: b.ordre }),
        installationsApi.saveStageChantier(b.id, { ordre: a.ordre }),
      ])
      load()
    } catch { /* */ }
  }
  const delStage = async (s) => {
    if (!window.confirm(`Supprimer l'étape « ${s.libelle} » ?`)) return
    try { await installationsApi.deleteStageChantier(s.id); load() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Suppression impossible (étape système ?).') }
  }

  if (loading) return <Spinner />
  if (loadError) {
    return (
      <Card>
        <CardContent className="py-8 text-center space-y-3">
          <AlertCircle className="mx-auto text-destructive" />
          <p>Impossible de charger les étapes.</p>
          <Button onClick={load}>Réessayer</Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <SectionTitle
        title="Étapes du chantier (gates)"
        subtitle="Le cycle de vie configurable des chantiers. Une étape bloquante ne se franchit que si ses éléments requis sont réunis et les points d'arrêt QHSE levés."
      />

      {!canEdit && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Lock size={14} />
          Configuration réservée au Directeur — lecture seule.
        </div>
      )}

      {stages.length === 0 ? (
        <EmptyState title="Aucune étape définie" />
      ) : (
        <div className="space-y-2">
          {stages.map((s, idx) => (
            <Card key={s.id} className={s.actif ? '' : 'opacity-60'}>
              <CardContent className="py-3 space-y-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground w-6">{idx + 1}</span>
                  <Input
                    defaultValue={s.libelle}
                    disabled={!canEdit}
                    onBlur={(e) => canEdit && renameStage(s, e.target.value)}
                    className="flex-1"
                  />
                  {s.protege && <Badge variant="secondary">Système</Badge>}
                  <Badge variant={s.bloquant ? 'destructive' : 'outline'}>
                    {s.bloquant ? 'Bloquant' : 'Consultatif'}
                  </Badge>
                  {s.statut_legacy_display && (
                    <Badge variant="outline">{s.statut_legacy_display}</Badge>
                  )}
                  {canEdit && (
                    <>
                      <IconButton aria-label="Monter"
                        onClick={() => moveStage(idx, -1)} disabled={idx === 0}>
                        <ChevronUp size={16} />
                      </IconButton>
                      <IconButton aria-label="Descendre"
                        onClick={() => moveStage(idx, 1)}
                        disabled={idx === stages.length - 1}>
                        <ChevronDown size={16} />
                      </IconButton>
                      <Button variant="ghost" size="sm"
                        onClick={() => toggleBloquant(s)}>
                        {s.bloquant ? 'Rendre consultatif' : 'Rendre bloquant'}
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => toggleActif(s)}>
                        {s.actif ? 'Désactiver' : 'Activer'}
                      </Button>
                      {!s.protege && (
                        <IconButton aria-label="Supprimer" onClick={() => delStage(s)}>
                          <Trash2 size={16} />
                        </IconButton>
                      )}
                    </>
                  )}
                </div>
                {s.bloquant && (
                  <div className="flex flex-wrap gap-2 pl-8">
                    {EXIGENCES.map(([key, label]) => (
                      <button
                        key={key}
                        type="button"
                        disabled={!canEdit}
                        onClick={() => canEdit && toggleExigence(s, key)}
                        className={`text-xs px-2 py-1 rounded border ${
                          s[key]
                            ? 'bg-primary/10 border-primary text-primary'
                            : 'border-muted text-muted-foreground'
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {canEdit && (
        <div className="flex gap-2">
          <Input
            placeholder="Nouvelle étape…"
            value={newLibelle}
            onChange={(e) => setNewLibelle(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addStage()}
          />
          <Button onClick={addStage}><Plus size={16} /> Ajouter</Button>
        </div>
      )}
    </div>
  )
}
