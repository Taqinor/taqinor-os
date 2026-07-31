import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { FileDown } from 'lucide-react'

import { DetailShell } from '../../ui/module'
import { Badge, Button, Card, Progress, buttonVariants, toast } from '../../ui'
import { cn } from '../../lib/cn'
import migrationApi from '../../api/migrationApi'
import {
  ENTITES, STATUTS_LOT, STATUTS_PROJET, errMessage, labelSource,
} from './constants'

/* ============================================================================
   NTMIG17 — Assistant de migration pas-à-pas (4 étapes par lot).
   ----------------------------------------------------------------------------
   1. choisir les entités  -> crée un LotMigration par entité cochée ;
   2. « Analyser »         -> dry-run STRICT (rien écrit en cible) + comptages ;
   3. « Charger »          -> commit délégué au moteur dataimport ;
   4. « Réconcilier »      -> rapport comptages source vs cible affiché ici.

   L'étape 2 affiche explicitement ce que le fichier NE remplacera PAS : le
   chargement est en remplissage seul côté serveur, l'écran le dit pour qu'un
   intégrateur ne croie jamais avoir écrasé (ou pas) sans le savoir.

   NOTE : le choix d'un « kit » de mappings prédéfinis (NTMIG8/12/13) n'est pas
   proposé — le registre de kits n'existe pas encore. Le fichier passe par le
   mapping automatique du moteur d'import ; le sélecteur viendra avec les kits,
   il n'est pas simulé ici.
   ========================================================================== */

const ETAPES_LOT = ['en_attente', 'analyse', 'charge', 'reconcilie']

function progressionLot(statut) {
  const i = ETAPES_LOT.indexOf(statut)
  if (i < 0) return 0
  return Math.round((i / (ETAPES_LOT.length - 1)) * 100)
}

export default function MigrationWizard() {
  const { id } = useParams()
  const [projet, setProjet] = useState(null)
  const [lots, setLots] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [bloquants, setBloquants] = useState([])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [p, l] = await Promise.all([
        migrationApi.getProjet(id),
        migrationApi.listLots(id),
      ])
      setProjet(p?.data ?? null)
      const data = l?.data
      setLots(Array.isArray(data) ? data : data?.results ?? [])
    } catch (err) {
      setError(errMessage(err, 'Impossible de charger ce projet de migration.'))
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    let alive = true
    ;(async () => {
      if (alive) await load()
    })()
    return () => {
      alive = false
    }
  }, [load])

  const terminer = async () => {
    setBloquants([])
    try {
      await migrationApi.terminerProjet(id)
      toast.success('Projet de migration clôturé.')
      await load()
    } catch (err) {
      const ecarts = err?.response?.data?.ecarts
      if (Array.isArray(ecarts) && ecarts.length) setBloquants(ecarts)
      toast.error(errMessage(err, 'Clôture refusée.'))
    }
  }

  if (loading) return <p className="p-4 text-sm text-muted-foreground">Chargement…</p>
  if (error) return <p className="p-4 text-sm text-destructive">{error}</p>
  if (!projet) return null

  const reconcilies = lots.filter((l) => l.statut === 'reconcilie').length

  return (
    <DetailShell
      title={projet.nom}
      subtitle={`Source ${labelSource(projet.source)} — ${reconcilies} / ${lots.length} lot(s) réconcilié(s)`}
      status={STATUTS_PROJET[projet.statut] || projet.statut}
      backTo="/migration"
      backLabel="Projets de migration"
      actions={(
        <div className="flex gap-2">
          <a
            className={cn(buttonVariants({ variant: 'outline' }))}
            href={migrationApi.rapportUrl(id)}
            target="_blank"
            rel="noreferrer"
          >
            <FileDown className="size-4" aria-hidden="true" />
            {' '}PV de migration
          </a>
          <Button onClick={terminer} disabled={projet.statut === 'termine'}>
            Terminer le projet
          </Button>
        </div>
      )}
    >
      <div className="flex flex-col gap-4">
        {bloquants.length > 0 && (
          <Card className="border-destructive/40 p-4">
            <h3 className="text-sm font-semibold text-destructive">
              Clôture refusée — écarts bloquants
            </h3>
            <ul className="mt-2 flex flex-col gap-1 text-sm">
              {bloquants.map((b) => (
                <li key={b.lot}>
                  <span className="font-medium">{b.entite}</span>{' : '}
                  {(b.ecarts || []).map((e) => e.detail || e.type).join(' · ')}
                </li>
              ))}
            </ul>
          </Card>
        )}

        <EtapeEntites projetId={id} lots={lots} onChanged={load} />

        {lots.map((lot) => (
          <LotCard key={lot.id} lot={lot} onChanged={load} />
        ))}
      </div>
    </DetailShell>
  )
}

/* -------- Étape 1 : choisir les entités à migrer -------- */
function EtapeEntites({ projetId, lots, onChanged }) {
  const [selection, setSelection] = useState([])
  const [saving, setSaving] = useState(false)
  const dejaPris = new Set(lots.map((l) => l.entite))
  const disponibles = ENTITES.filter((e) => !dejaPris.has(e.value))

  if (disponibles.length === 0) return null

  const toggle = (value) => {
    setSelection((prev) => (
      prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value]
    ))
  }

  const creer = async () => {
    if (selection.length === 0) return
    setSaving(true)
    try {
      // `ordre` = rang de déclaration de l'entité : un ordre STABLE, pas un
      // tri de dépendances (le tri topologique est la tâche NTMIG3 ; on ne le
      // simule pas ici). Création séquentielle pour que l'ordre soit
      // déterministe même si le serveur répond dans le désordre.
      for (const value of selection) {
        const ordre = ENTITES.findIndex((e) => e.value === value)
        await migrationApi.createLot({ projet: projetId, entite: value, ordre })
      }
      toast.success(`${selection.length} lot(s) créé(s).`)
      setSelection([])
      await onChanged()
    } catch (err) {
      toast.error(errMessage(err, 'Création des lots impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold">Étape 1 — Entités à migrer</h3>
      <div className="mt-3 flex flex-wrap gap-3">
        {disponibles.map((e) => (
          <label key={e.value} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={selection.includes(e.value)}
              onChange={() => toggle(e.value)}
            />
            {e.label}
          </label>
        ))}
      </div>
      <div className="mt-3">
        <Button size="sm" onClick={creer} disabled={saving || selection.length === 0}>
          {saving ? 'Création…' : 'Créer les lots'}
        </Button>
      </div>
    </Card>
  )
}

/* -------- Étapes 2 à 4 : analyser -> charger -> réconcilier -------- */
function LotCard({ lot, onChanged }) {
  const [fichier, setFichier] = useState(null)
  const [apercu, setApercu] = useState(null)
  const [busy, setBusy] = useState('')
  const [motif, setMotif] = useState(null)
  const rapport = lot.dernier_rapport

  const exigeFichier = () => {
    if (!fichier) {
      toast.error('Choisissez d\'abord un fichier source.')
      return false
    }
    return true
  }

  const analyser = async () => {
    if (!exigeFichier()) return
    setBusy('analyse')
    try {
      const res = await migrationApi.analyserLot(lot.id, fichier)
      setApercu(res?.data ?? null)
      await onChanged()
    } catch (err) {
      toast.error(errMessage(err, 'Analyse impossible.'))
    } finally {
      setBusy('')
    }
  }

  const charger = async () => {
    if (!exigeFichier()) return
    setBusy('charge')
    try {
      await migrationApi.chargerLot(lot.id, fichier)
      toast.success('Lot chargé.')
      await onChanged()
    } catch (err) {
      toast.error(errMessage(err, 'Chargement impossible.'))
    } finally {
      setBusy('')
    }
  }

  const reconcilier = async () => {
    setBusy('reconcilie')
    try {
      await migrationApi.reconcilierLot(lot.id)
      await onChanged()
    } catch (err) {
      toast.error(errMessage(err, 'Réconciliation impossible.'))
    } finally {
      setBusy('')
    }
  }

  const deroger = async () => {
    if (!motif || !motif.trim()) {
      toast.error('Une dérogation exige un motif : il figurera sur le PV.')
      return
    }
    try {
      await migrationApi.derogerLot(lot.id, motif.trim())
      toast.success('Dérogation enregistrée.')
      setMotif(null)
      await onChanged()
    } catch (err) {
      toast.error(errMessage(err, 'Dérogation refusée.'))
    }
  }

  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{lot.entite}</h3>
        <Badge tone={lot.statut === 'reconcilie' ? 'success' : undefined}>
          {STATUTS_LOT[lot.statut] || lot.statut}
        </Badge>
      </div>
      <Progress
        className="mt-2"
        value={progressionLot(lot.statut)}
        aria-label={`Avancement du lot ${lot.entite}`}
      />

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <input
          type="file"
          accept=".csv,.xlsx,.xls"
          aria-label={`Fichier source du lot ${lot.entite}`}
          onChange={(e) => setFichier(e.target.files?.[0] ?? null)}
          className="text-sm"
        />
        <Button size="sm" variant="outline" onClick={analyser} disabled={busy !== ''}>
          {busy === 'analyse' ? 'Analyse…' : 'Analyser'}
        </Button>
        <Button size="sm" onClick={charger} disabled={busy !== ''}>
          {busy === 'charge' ? 'Chargement…' : 'Charger'}
        </Button>
        <Button size="sm" variant="outline" onClick={reconcilier} disabled={busy !== ''}>
          {busy === 'reconcilie' ? 'Réconciliation…' : 'Réconcilier'}
        </Button>
      </div>

      {apercu && (
        <div className="mt-3 rounded-md bg-muted/50 p-3 text-sm">
          <p>
            Étape 2 — aperçu (rien n&apos;a été écrit) :
            {' '}
            <strong>{apercu.total_lignes}</strong> ligne(s) source.
          </p>
          {apercu.non_mappees?.length > 0 && (
            <p className="mt-1 text-muted-foreground">
              Colonnes non mappées : {apercu.non_mappees.join(', ')}
            </p>
          )}
          <p className="mt-1 text-muted-foreground">
            {apercu.ecrasements_total
              ? `${apercu.ecrasements_total} valeur(s) déjà saisie(s) diffèrent de la source — `
                + 'elles seront CONSERVÉES (chargement en remplissage seul).'
              : 'Aucune valeur déjà saisie ne serait remplacée.'}
          </p>
        </div>
      )}

      {rapport && (
        <div className="mt-3 rounded-md border p-3 text-sm">
          <div className="flex items-center gap-2">
            <strong>Étape 4 — réconciliation</strong>
            <Badge tone={rapport.conforme ? 'success' : 'danger'}>
              {rapport.conforme ? 'Conforme' : 'Écarts détectés'}
            </Badge>
          </div>
          <p className="mt-1">
            Source {rapport.nb_source} · créés {rapport.nb_cible_crees} ·
            {' '}mis à jour {rapport.nb_cible_existants} ·
            {' '}erreurs {rapport.nb_erreurs}
          </p>
          {rapport.ecarts?.length > 0 && (
            <ul className="mt-1 list-disc pl-5 text-muted-foreground">
              {rapport.ecarts.map((e, i) => (
                <li key={i}>{e.detail || e.type}</li>
              ))}
            </ul>
          )}
          {!rapport.conforme && !lot.derogation_reconcile && (
            motif === null ? (
              <Button
                size="sm"
                variant="outline"
                className="mt-2"
                onClick={() => setMotif('')}
              >
                Déroger (avec motif)
              </Button>
            ) : (
              <div className="mt-2 flex flex-col gap-2">
                <label className="text-xs text-muted-foreground" htmlFor={`mig-motif-${lot.id}`}>
                  Motif de la dérogation (obligatoire — il figurera sur le PV)
                </label>
                <textarea
                  id={`mig-motif-${lot.id}`}
                  className="min-h-16 rounded-md border border-border bg-background p-2 text-sm"
                  value={motif}
                  onChange={(e) => setMotif(e.target.value)}
                />
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => setMotif(null)}>
                    Annuler
                  </Button>
                  <Button size="sm" onClick={deroger}>
                    Enregistrer la dérogation
                  </Button>
                </div>
              </div>
            )
          )}
        </div>
      )}

      {lot.derogation_reconcile && (
        <p className="mt-2 text-sm text-amber-700 dark:text-amber-400">
          Dérogation accordée{lot.derogation_par_nom ? ` par ${lot.derogation_par_nom}` : ''}
          {lot.derogation_motif ? ` — ${lot.derogation_motif}` : ''}
        </p>
      )}
    </Card>
  )
}
