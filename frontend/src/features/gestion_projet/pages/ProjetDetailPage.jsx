import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Pencil, Link2, CheckCircle2, Plus } from 'lucide-react'
import { DetailShell } from '../../../ui/module'
import {
  Button, Spinner, EmptyState, DefinitionList, Badge, toast, DataTable,
} from '../../../ui'
import { useConfirmDialog } from '../../../ui/confirm'
import { formatMAD, formatDate, formatDateTime } from '../../../lib/format'
import gestionProjetApi from '../../../api/gestionProjetApi'
import {
  StatutProjet, PROJET_TRANSITIONS, TYPES_CIBLE, errMessage,
} from '../constants'
import ProjetFormDialog from '../components/ProjetFormDialog'
import LienFormDialog from '../components/LienFormDialog'
import ClotureDialog from '../components/ClotureDialog'

/* UX38 — Détail projet : entête + statut, transitions GARDÉES (miroir de la
   machine à états serveur), onglets Résumé / Liens / Historique / Clôture. */

export default function ProjetDetailPage() {
  const { id } = useParams()
  const { confirmDelete } = useConfirmDialog()
  const [projet, setProjet] = useState(null)
  const [liens, setLiens] = useState([])
  const [historique, setHistorique] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [showEdit, setShowEdit] = useState(false)
  const [showLien, setShowLien] = useState(false)
  const [showCloture, setShowCloture] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [p, l, h] = await Promise.all([
        gestionProjetApi.getProjet(id),
        gestionProjetApi.getProjetLiens(id).catch(() => ({ data: [] })),
        gestionProjetApi.getProjetHistorique(id).catch(() => ({ data: [] })),
      ])
      setProjet(p.data)
      setLiens(Array.isArray(l.data) ? l.data : l.data?.results ?? [])
      setHistorique(Array.isArray(h.data) ? h.data : h.data?.results ?? [])
    } catch (err) {
      setError(errMessage(err, 'Projet introuvable.'))
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    let alive = true
    ;(async () => { if (alive) await load() })()
    return () => { alive = false }
  }, [load])

  const runTransition = async (t) => {
    setBusy(true)
    try {
      const res = await gestionProjetApi[t.api](id)
      setProjet(res.data)
      await gestionProjetApi.getProjetHistorique(id)
        .then((h) => setHistorique(Array.isArray(h.data) ? h.data : h.data?.results ?? []))
        .catch(() => {})
      toast.success(`Projet ${t.label.toLowerCase()}.`)
    } catch (err) {
      toast.error(errMessage(err, 'Transition refusée.'))
    } finally {
      setBusy(false)
    }
  }

  const deleteLien = async (lien) => {
    const ok = await confirmDelete({
      title: 'Supprimer ce lien ?',
      description: 'Le lien est retiré du projet (la pièce cible n\'est pas supprimée).',
    })
    if (!ok) return
    try {
      await gestionProjetApi.deleteLien(lien.id)
      setLiens((rows) => rows.filter((r) => r.id !== lien.id))
      toast.success('Lien supprimé.')
    } catch (err) {
      toast.error(errMessage(err, 'Suppression impossible.'))
    }
  }

  if (loading) {
    return <div className="flex justify-center p-10"><Spinner /></div>
  }
  if (error || !projet) {
    return (
      <EmptyState
        title="Projet introuvable"
        description={error || 'Ce projet n\'existe pas ou a été supprimé.'}
        action={<Button variant="outline" onClick={load}>Réessayer</Button>}
      />
    )
  }

  // Transitions disponibles selon le statut courant (garde côté client, la
  // garde d'autorité restant côté serveur).
  const available = PROJET_TRANSITIONS.filter((t) => t.from.includes(projet.statut))

  const resume = (
    <div className="flex flex-col gap-4">
      <DefinitionList
        items={[
          { term: 'Code', description: projet.code || '—' },
          { term: 'Client (id CRM)', description: projet.client_id ?? '—' },
          { term: 'Début', description: projet.date_debut ? formatDate(projet.date_debut) : '—' },
          { term: 'Fin prévue', description: projet.date_fin_prevue ? formatDate(projet.date_fin_prevue) : '—' },
          { term: 'Budget total', description: projet.budget_total ? formatMAD(projet.budget_total) : '—' },
          { term: 'Créé le', description: projet.date_creation ? formatDateTime(projet.date_creation) : '—' },
        ]}
      />
      {projet.description && (
        <p className="whitespace-pre-wrap text-sm text-muted-foreground">{projet.description}</p>
      )}
    </div>
  )

  const liensTab = (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" variant="outline" onClick={() => setShowLien(true)}>
          <Plus /> Lier une pièce
        </Button>
      </div>
      <DataTable
        data={liens}
        getRowId={(l) => l.id}
        searchable={false}
        columns={[
          {
            id: 'type',
            header: 'Type',
            accessor: (l) => l.type_cible_display || l.type_cible,
            cell: (v) => <Badge tone="info">{v}</Badge>,
          },
          { id: 'cible_id', header: 'Réf.', accessor: (l) => l.cible_id, cell: (v) => <span className="font-mono text-xs">#{v}</span> },
          { id: 'libelle', header: 'Libellé', accessor: (l) => l.libelle || '—' },
        ]}
        rowActions={(l) => [{
          id: 'del', label: 'Supprimer', destructive: true, onClick: () => deleteLien(l),
        }]}
        emptyTitle="Aucun lien"
        emptyDescription="Reliez un devis, une facture, un ticket SAV ou un achat à ce projet."
      />
    </div>
  )

  const histoTab = historique.length ? (
    <ol className="flex flex-col gap-2">
      {historique.map((h) => (
        <li key={h.id} className="flex items-center gap-2 text-sm">
          <StatutProjet status={h.old_value} />
          <span className="text-muted-foreground">→</span>
          <StatutProjet status={h.new_value} />
          <span className="ml-auto text-xs text-muted-foreground">
            {h.auteur_nom || 'système'} · {h.date_creation ? formatDateTime(h.date_creation) : ''}
          </span>
        </li>
      ))}
    </ol>
  ) : (
    <EmptyState title="Aucune transition" description="L'historique des changements de statut apparaîtra ici." />
  )

  const clotureTab = (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">
        La clôture enregistre le retour d'expérience et passe le projet à « Terminé ».
      </p>
      <div>
        <Button
          variant="outline"
          disabled={projet.statut === 'annule'}
          onClick={() => setShowCloture(true)}
        >
          <CheckCircle2 /> Clôturer le projet
        </Button>
      </div>
    </div>
  )

  return (
    <>
      <DetailShell
        title={projet.nom}
        subtitle={projet.code}
        status={projet.statut}
        statusPill={StatutProjet}
        backTo="/projets"
        actions={(
          <div className="flex flex-wrap items-center gap-2">
            {available.map((t) => (
              <Button
                key={t.key}
                size="sm"
                variant={t.key === 'annuler' ? 'outline' : 'default'}
                disabled={busy}
                onClick={() => runTransition(t)}
              >
                {t.label}
              </Button>
            ))}
            <Button size="sm" variant="outline" onClick={() => setShowEdit(true)}>
              <Pencil /> Modifier
            </Button>
          </div>
        )}
        tabs={[
          { value: 'resume', label: 'Résumé', content: resume },
          { value: 'liens', label: 'Liens', count: liens.length, content: liensTab },
          { value: 'historique', label: 'Historique', count: historique.length, content: histoTab },
          { value: 'cloture', label: 'Clôture', content: clotureTab },
        ]}
      />
      {showEdit && (
        <ProjetFormDialog
          projet={projet}
          onClose={() => setShowEdit(false)}
          onSaved={(p) => { setShowEdit(false); setProjet(p); toast.success('Projet mis à jour.') }}
        />
      )}
      {showLien && (
        <LienFormDialog
          projetId={projet.id}
          typesCible={TYPES_CIBLE}
          onClose={() => setShowLien(false)}
          onSaved={(l) => { setShowLien(false); setLiens((r) => [...r, l]); toast.success('Lien ajouté.') }}
        />
      )}
      {showCloture && (
        <ClotureDialog
          projetId={projet.id}
          onClose={() => setShowCloture(false)}
          onSaved={() => { setShowCloture(false); toast.success('Projet clôturé.'); load() }}
        />
      )}
    </>
  )
}
