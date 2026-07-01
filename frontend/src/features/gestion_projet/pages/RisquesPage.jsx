import { useCallback, useEffect, useState } from 'react'
import {
  Card, Button, Spinner, EmptyState, Badge, DataTable, Tabs, TabsList,
  TabsTrigger, TabsContent,
} from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import gestionProjetApi from '../../../api/gestionProjetApi'
import {
  errMessage, StatutRisque, StatutAction, PrioriteAction, StatutLot,
  CATEGORIES_RISQUE, TYPES_DOC,
} from '../constants'
import ProjetPicker from '../components/ProjetPicker'

/* UX42 — Risques, actions & CR : registre des risques, plan d'actions,
   comptes-rendus, documents/commentaires, modèles de projet, sous-traitants &
   lots. Tout est groupé sous onglets. Le `montant` des lots est INTERNE. */

const CAT_RISQUE = Object.fromEntries(CATEGORIES_RISQUE.map((c) => [c.value, c.label]))
const TYPE_DOC = Object.fromEntries(TYPES_DOC.map((c) => [c.value, c.label]))

export default function RisquesPage() {
  const [projetId, setProjetId] = useState('')
  const [state, setState] = useState({
    risques: [], actions: [], crs: [], documents: [], commentaires: [],
    modeles: [], sousTraitants: [], lots: [],
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const asList = (r) => (Array.isArray(r.data) ? r.data : r.data?.results ?? [])

  const load = useCallback(async (pid) => {
    setLoading(true)
    setError(null)
    try {
      // Modèles & sous-traitants sont société-scopés (indépendants du projet).
      const params = pid ? { projet: pid } : undefined
      const [ri, ac, cr, doc, com, mod, st, lo] = await Promise.all([
        pid ? gestionProjetApi.getRisques(params) : Promise.resolve({ data: [] }),
        pid ? gestionProjetApi.getActions(params) : Promise.resolve({ data: [] }),
        pid ? gestionProjetApi.getComptesRendus(params) : Promise.resolve({ data: [] }),
        pid ? gestionProjetApi.getDocuments(params) : Promise.resolve({ data: [] }),
        pid ? gestionProjetApi.getCommentaires(params) : Promise.resolve({ data: [] }),
        gestionProjetApi.getModeles(),
        gestionProjetApi.getSousTraitants(),
        pid ? gestionProjetApi.getLotsSousTraitance(params) : Promise.resolve({ data: [] }),
      ])
      setState({
        risques: asList(ri), actions: asList(ac), crs: asList(cr),
        documents: asList(doc), commentaires: asList(com), modeles: asList(mod),
        sousTraitants: asList(st), lots: asList(lo),
      })
    } catch (err) {
      setError(errMessage(err, 'Chargement impossible.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let alive = true
    ;(async () => { if (alive) await load(projetId) })()
    return () => { alive = false }
  }, [projetId, load])

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight">Risques, actions & CR</h1>
          <p className="text-sm text-muted-foreground">Registre des risques, plan d'actions, réunions, documents, modèles & sous-traitance.</p>
        </div>
        <ProjetPicker value={projetId} onChange={setProjetId} />
      </div>

      {loading ? (
        <div className="flex justify-center p-10"><Spinner /></div>
      ) : error ? (
        <EmptyState title="Erreur" description={error} action={<Button variant="outline" onClick={() => load(projetId)}>Réessayer</Button>} />
      ) : (
        <Tabs defaultValue="risques">
          <TabsList className="flex-wrap">
            <TabsTrigger value="risques">Risques</TabsTrigger>
            <TabsTrigger value="actions">Actions</TabsTrigger>
            <TabsTrigger value="cr">Comptes-rendus</TabsTrigger>
            <TabsTrigger value="documents">Documents</TabsTrigger>
            <TabsTrigger value="modeles">Modèles</TabsTrigger>
            <TabsTrigger value="sous-traitance">Sous-traitance</TabsTrigger>
          </TabsList>

          <TabsContent value="risques">
            <Card className="p-4 sm:p-5">
              <DataTable
                data={state.risques}
                getRowId={(r) => r.id}
                columns={[
                  { id: 'libelle', header: 'Risque', accessor: (r) => r.libelle, cell: (v) => <span className="font-medium">{v}</span> },
                  { id: 'categorie', header: 'Catégorie', searchable: false, accessor: (r) => CAT_RISQUE[r.categorie] ?? r.categorie },
                  { id: 'proba', header: 'P', align: 'right', numeric: true, searchable: false, accessor: (r) => r.probabilite },
                  { id: 'impact', header: 'I', align: 'right', numeric: true, searchable: false, accessor: (r) => r.impact },
                  { id: 'criticite', header: 'Criticité', align: 'right', numeric: true, searchable: false, accessor: (r) => r.criticite, cell: (v) => <Badge tone={v >= 15 ? 'danger' : v >= 8 ? 'warning' : 'neutral'}>{v}</Badge> },
                  { id: 'statut', header: 'Statut', searchable: false, accessor: (r) => r.statut, cell: (v) => <StatutRisque status={v} /> },
                ]}
                exportName="risques"
                emptyTitle="Aucun risque"
                emptyDescription={projetId ? 'Aucun risque enregistré pour ce projet.' : 'Sélectionnez un projet.'}
              />
            </Card>
          </TabsContent>

          <TabsContent value="actions">
            <Card className="p-4 sm:p-5">
              <DataTable
                data={state.actions}
                getRowId={(a) => a.id}
                columns={[
                  { id: 'libelle', header: 'Action', accessor: (a) => a.libelle, cell: (v) => <span className="font-medium">{v}</span> },
                  { id: 'priorite', header: 'Priorité', searchable: false, accessor: (a) => a.priorite, cell: (v) => <PrioriteAction status={v} /> },
                  { id: 'statut', header: 'Statut', searchable: false, accessor: (a) => a.statut, cell: (v) => <StatutAction status={v} /> },
                  { id: 'echeance', header: 'Échéance', searchable: false, accessor: (a) => a.echeance || '', cell: (v) => v ? formatDate(v) : '—' },
                ]}
                exportName="actions"
                emptyTitle="Aucune action"
                emptyDescription={projetId ? 'Aucune action pour ce projet.' : 'Sélectionnez un projet.'}
              />
            </Card>
          </TabsContent>

          <TabsContent value="cr">
            <Card className="p-4 sm:p-5">
              {state.crs.length ? (
                <ul className="flex flex-col gap-2">
                  {state.crs.map((c) => (
                    <li key={c.id} className="rounded-md border border-border p-3 text-sm">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{c.titre}</span>
                        <span className="ml-auto text-xs text-muted-foreground">{c.date_reunion ? formatDate(c.date_reunion) : ''}</span>
                      </div>
                      {c.lieu && <p className="text-xs text-muted-foreground">Lieu : {c.lieu}</p>}
                      {c.decisions && <p className="mt-1 whitespace-pre-wrap text-sm">{c.decisions}</p>}
                    </li>
                  ))}
                </ul>
              ) : <EmptyState title="Aucun compte-rendu" description={projetId ? 'Aucune réunion enregistrée.' : 'Sélectionnez un projet.'} />}
            </Card>
          </TabsContent>

          <TabsContent value="documents">
            <Card className="p-4 sm:p-5">
              <DataTable
                data={state.documents}
                getRowId={(d) => d.id}
                columns={[
                  { id: 'nom', header: 'Document', accessor: (d) => d.nom, cell: (v) => <span className="font-medium">{v}</span> },
                  { id: 'type', header: 'Type', searchable: false, accessor: (d) => TYPE_DOC[d.type_doc] ?? d.type_doc, cell: (v) => <Badge tone="info">{v}</Badge> },
                  { id: 'version', header: 'Version', align: 'right', numeric: true, searchable: false, accessor: (d) => d.derniere_version ?? 0 },
                  { id: 'nb', header: 'Révisions', align: 'right', numeric: true, searchable: false, accessor: (d) => (d.versions ?? []).length },
                ]}
                exportName="documents"
                emptyTitle="Aucun document"
                emptyDescription={projetId ? 'Aucun document versionné.' : 'Sélectionnez un projet.'}
              />
              {state.commentaires.length > 0 && (
                <div className="mt-4 border-t border-border pt-3">
                  <p className="mb-2 text-sm font-medium">Commentaires récents</p>
                  <ul className="flex flex-col gap-1 text-sm">
                    {state.commentaires.slice(0, 8).map((cm) => (
                      <li key={cm.id} className="flex gap-2">
                        <span className="text-muted-foreground">{cm.auteur_nom || '—'} :</span>
                        <span>{cm.texte}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </Card>
          </TabsContent>

          <TabsContent value="modeles">
            <Card className="p-4 sm:p-5">
              <DataTable
                data={state.modeles}
                getRowId={(m) => m.id}
                columns={[
                  { id: 'nom', header: 'Modèle', accessor: (m) => m.nom, cell: (v) => <span className="font-medium">{v}</span> },
                  { id: 'type', header: 'Type installation', searchable: false, accessor: (m) => m.type_installation_display || m.type_installation },
                  { id: 'nb', header: 'Tâches-types', align: 'right', numeric: true, searchable: false, accessor: (m) => m.nb_taches ?? (m.taches ?? []).length },
                  { id: 'actif', header: 'Actif', searchable: false, accessor: (m) => m.actif, cell: (v) => <Badge tone={v ? 'success' : 'neutral'}>{v ? 'Actif' : 'Inactif'}</Badge> },
                ]}
                exportName="modeles-projet"
                emptyTitle="Aucun modèle"
                emptyDescription="Créez des modèles de projet par type d'installation."
              />
            </Card>
          </TabsContent>

          <TabsContent value="sous-traitance">
            <Card className="p-4 sm:p-5">
              <h3 className="mb-2 font-display text-base font-semibold">Carnet de sous-traitants</h3>
              <DataTable
                data={state.sousTraitants}
                getRowId={(s) => s.id}
                columns={[
                  { id: 'nom', header: 'Sous-traitant', accessor: (s) => s.nom, cell: (v) => <span className="font-medium">{v}</span> },
                  { id: 'specialite', header: 'Spécialité', accessor: (s) => s.specialite || '—' },
                  { id: 'contact', header: 'Contact', accessor: (s) => s.contact || '—' },
                  { id: 'tel', header: 'Téléphone', searchable: false, accessor: (s) => s.telephone || '—' },
                  { id: 'actif', header: 'Actif', searchable: false, accessor: (s) => s.actif, cell: (v) => <Badge tone={v ? 'success' : 'neutral'}>{v ? 'Actif' : 'Inactif'}</Badge> },
                ]}
                exportName="sous-traitants"
                emptyTitle="Aucun sous-traitant"
                emptyDescription="Ajoutez des sous-traitants à votre carnet d'adresses."
              />
              <h3 className="mb-2 mt-5 font-display text-base font-semibold">Lots de sous-traitance</h3>
              <DataTable
                data={state.lots}
                getRowId={(l) => l.id}
                columns={[
                  { id: 'libelle', header: 'Lot', accessor: (l) => l.libelle, cell: (v) => <span className="font-medium">{v}</span> },
                  { id: 'st', header: 'Sous-traitant', accessor: (l) => l.sous_traitant_nom || `#${l.sous_traitant}` },
                  { id: 'montant', header: 'Montant (interne)', align: 'right', numeric: true, searchable: false, accessor: (l) => Number(l.montant ?? 0), cell: (_v, l) => (l.montant ? formatMAD(l.montant) : '—') },
                  { id: 'statut', header: 'Statut', searchable: false, accessor: (l) => l.statut, cell: (v) => <StatutLot status={v} /> },
                ]}
                exportName="lots-sous-traitance"
                emptyTitle="Aucun lot"
                emptyDescription={projetId ? 'Aucun lot confié pour ce projet.' : 'Sélectionnez un projet.'}
              />
            </Card>
          </TabsContent>
        </Tabs>
      )}
    </div>
  )
}
