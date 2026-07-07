import { useCallback, useEffect, useMemo, useState } from 'react'
import { Check, X, Send } from 'lucide-react'
import {
  Card, Button, Spinner, EmptyState, Badge, DataTable, Input, Label,
  Tabs, TabsList, TabsTrigger, TabsContent, toast,
} from '../../../ui'
import { formatMAD, formatNumber, formatDate } from '../../../lib/format'
import gestionProjetApi from '../../../api/gestionProjetApi'
import { errMessage, StatutTimesheet } from '../constants'

/* XPRJ7-8/ZPRJ5-6 — Workflow d'approbation des feuilles de temps
   (soumettre/approuver/rejeter) + tableaux de bord temps (manquants, écart
   heures attendues/saisies, classement de saisie, rapprochement pointages
   RH ↔ temps projet, rapport multi-dimensions). Toutes les données sont
   INTERNES — jamais rendues dans un document client. */

function todayISO(offset = 0) {
  const d = new Date()
  d.setDate(d.getDate() + offset)
  return d.toISOString().slice(0, 10)
}

export default function TimesheetsTab({ timesheets, onChanged }) {
  const [busyId, setBusyId] = useState(null)
  const [debut, setDebut] = useState(todayISO(-30))
  const [fin, setFin] = useState(todayISO())
  const [manquants, setManquants] = useState(null)
  const [classement, setClassement] = useState(null)
  const [rapprochement, setRapprochement] = useState(null)
  const [rapport, setRapport] = useState(null)
  const [loadingRapports, setLoadingRapports] = useState(false)

  const soumettre = async (t) => {
    setBusyId(t.id)
    try {
      await gestionProjetApi.soumettreTimesheet(t.id)
      toast.success('Feuille de temps soumise.')
      onChanged?.()
    } catch (err) {
      toast.error(errMessage(err, 'Soumission impossible.'))
    } finally {
      setBusyId(null)
    }
  }

  const approuver = async (t) => {
    setBusyId(t.id)
    try {
      await gestionProjetApi.approuverTimesheet(t.id)
      toast.success('Feuille de temps approuvée.')
      onChanged?.()
    } catch (err) {
      toast.error(errMessage(err, 'Approbation impossible.'))
    } finally {
      setBusyId(null)
    }
  }

  const rejeter = async (t) => {
    const motif = window.prompt('Motif du rejet (optionnel) :', '') ?? ''
    setBusyId(t.id)
    try {
      await gestionProjetApi.rejeterTimesheet(t.id, { motif })
      toast.success('Feuille de temps rejetée.')
      onChanged?.()
    } catch (err) {
      toast.error(errMessage(err, 'Rejet impossible.'))
    } finally {
      setBusyId(null)
    }
  }

  const loadRapports = useCallback(async () => {
    if (!debut || !fin) return
    setLoadingRapports(true)
    try {
      const [m, c, r, rp] = await Promise.all([
        gestionProjetApi.getTempsManquants({ debut, fin }).catch(() => ({ data: null })),
        gestionProjetApi.getClassementTemps({ debut, fin }).catch(() => ({ data: null })),
        gestionProjetApi.getRapprochementTemps({ debut, fin }).catch(() => ({ data: null })),
        gestionProjetApi.getRapportTemps({ debut, fin, group_by: 'ressource' }).catch(() => ({ data: null })),
      ])
      setManquants(m.data)
      setClassement(c.data)
      setRapprochement(r.data)
      setRapport(rp.data)
    } finally {
      setLoadingRapports(false)
    }
  }, [debut, fin])

  useEffect(() => {
    let alive = true
    ;(async () => { if (alive) await loadRapports() })()
    return () => { alive = false }
  }, [loadRapports])

  const classementLignes = useMemo(
    () => classement?.lignes ?? classement?.classement ?? [],
    [classement],
  )

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-4 sm:p-5">
        <DataTable
          data={timesheets}
          getRowId={(t) => t.id}
          columns={[
            { id: 'date', header: 'Date', searchable: false, accessor: (t) => t.date || '', cell: (v) => v ? formatDate(v) : '—' },
            { id: 'projet', header: 'Projet', accessor: (t) => t.projet_code || `#${t.projet}` },
            { id: 'ressource', header: 'Ressource', accessor: (t) => t.ressource_nom || `#${t.ressource}` },
            { id: 'heures', header: 'Heures', align: 'right', numeric: true, searchable: false, accessor: (t) => Number(t.heures ?? 0), cell: (v) => formatNumber(v) },
            { id: 'cout', header: 'Coût (interne)', align: 'right', numeric: true, searchable: false, accessor: (t) => Number(t.cout ?? 0), cell: (_v, t) => (t.cout ? formatMAD(t.cout) : '—') },
            { id: 'statut', header: 'Statut', searchable: false, accessor: (t) => t.statut, cell: (v) => <StatutTimesheet status={v} /> },
          ]}
          rowActions={(t) => (busyId === t.id ? [] : [
            t.statut === 'brouillon' && { id: 'soumettre', label: 'Soumettre', icon: Send, onClick: () => soumettre(t) },
            t.statut === 'soumise' && { id: 'approuver', label: 'Approuver', icon: Check, onClick: () => approuver(t) },
            t.statut === 'soumise' && { id: 'rejeter', label: 'Rejeter', icon: X, destructive: true, onClick: () => rejeter(t) },
          ].filter(Boolean))}
          exportName="timesheets"
          emptyTitle="Aucune feuille de temps"
          emptyDescription="Le coût est figé côté serveur (interne, jamais client)."
        />
      </Card>

      <Card className="p-4 sm:p-5">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <h3 className="font-display text-base font-semibold">Tableaux de bord des temps</h3>
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="ts-debut">Début</Label>
              <Input id="ts-debut" type="date" value={debut} onChange={(e) => setDebut(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="ts-fin">Fin</Label>
              <Input id="ts-fin" type="date" value={fin} onChange={(e) => setFin(e.target.value)} />
            </div>
          </div>
        </div>

        {loadingRapports ? (
          <div className="flex justify-center p-6"><Spinner /></div>
        ) : (
          <Tabs defaultValue="manquants">
            <TabsList className="flex-wrap">
              <TabsTrigger value="manquants">Manquants</TabsTrigger>
              <TabsTrigger value="classement">Classement</TabsTrigger>
              <TabsTrigger value="rapprochement">Rapprochement RH</TabsTrigger>
              <TabsTrigger value="rapport">Rapport</TabsTrigger>
            </TabsList>

            <TabsContent value="manquants">
              {(manquants?.lignes ?? []).length ? (
                <DataTable
                  data={manquants.lignes}
                  getRowId={(l) => l.ressource_id}
                  searchable={false}
                  columns={[
                    { id: 'ressource', header: 'Ressource', accessor: (l) => l.ressource_nom },
                    { id: 'attendus', header: 'Jours attendus', align: 'right', numeric: true, accessor: (l) => l.jours_attendus },
                    { id: 'saisis', header: 'Jours saisis', align: 'right', numeric: true, accessor: (l) => l.jours_saisis },
                    { id: 'manquants', header: 'Jours manquants', align: 'right', numeric: true, accessor: (l) => (l.jours_manquants ?? []).length, cell: (v) => <Badge tone={v > 0 ? 'warning' : 'success'}>{v}</Badge> },
                  ]}
                  emptyTitle="Aucune donnée"
                />
              ) : <EmptyState title="Aucune donnée" description="Aucune donnée de temps manquant sur cette période." />}
            </TabsContent>

            <TabsContent value="classement">
              {classementLignes.length ? (
                <DataTable
                  data={classementLignes}
                  getRowId={(l, i) => l.ressource_id ?? i}
                  searchable={false}
                  columns={[
                    { id: 'ressource', header: 'Ressource', accessor: (l) => l.ressource_nom ?? l.nom },
                    { id: 'heures', header: 'Heures saisies', align: 'right', numeric: true, accessor: (l) => Number(l.heures ?? 0), cell: (v) => formatNumber(v) },
                    { id: 'completude', header: 'Complétude', align: 'right', numeric: true, accessor: (l) => Number(l.completude_pct ?? l.completude ?? 0), cell: (v) => `${v} %` },
                  ]}
                  emptyTitle="Aucune donnée"
                />
              ) : <EmptyState title="Aucune donnée" description="Aucun classement disponible sur cette période." />}
            </TabsContent>

            <TabsContent value="rapprochement">
              {(rapprochement?.ecarts ?? []).length ? (
                <DataTable
                  data={rapprochement.ecarts}
                  getRowId={(e, i) => `${e.ressource_id}-${e.date}-${i}`}
                  searchable={false}
                  columns={[
                    { id: 'ressource', header: 'Ressource', accessor: (e) => e.ressource_nom },
                    { id: 'date', header: 'Date', accessor: (e) => e.date, cell: (v) => formatDate(v) },
                    { id: 'type', header: 'Écart', accessor: (e) => e.type_ecart, cell: (v) => <Badge tone="warning">{v}</Badge> },
                    { id: 'pointees', header: 'H. pointées', align: 'right', numeric: true, accessor: (e) => Number(e.heures_pointees ?? 0) },
                    { id: 'imputees', header: 'H. imputées', align: 'right', numeric: true, accessor: (e) => Number(e.heures_imputees ?? 0) },
                  ]}
                  emptyTitle="Aucun écart"
                />
              ) : <EmptyState title="Aucun écart" description="Aucun écart pointage/temps projet détecté (ou pointage RH non exposé)." />}
            </TabsContent>

            <TabsContent value="rapport">
              {(rapport?.lignes ?? []).length ? (
                <>
                  <DataTable
                    data={rapport.lignes}
                    getRowId={(l) => l.cle}
                    searchable={false}
                    columns={[
                      { id: 'libelle', header: 'Ressource', accessor: (l) => l.libelle },
                      { id: 'heures', header: 'Heures', align: 'right', numeric: true, accessor: (l) => Number(l.heures ?? 0), cell: (v) => formatNumber(v) },
                      { id: 'facturables', header: 'Heures facturables', align: 'right', numeric: true, accessor: (l) => Number(l.heures_facturables ?? 0), cell: (v) => formatNumber(v) },
                    ]}
                    emptyTitle="Aucune donnée"
                  />
                  <p className="mt-2 text-xs text-muted-foreground">
                    Total : {formatNumber(rapport.total_heures)} h dont {formatNumber(rapport.total_heures_facturables)} h facturables.
                  </p>
                </>
              ) : <EmptyState title="Aucune donnée" description="Aucune heure loguée sur cette période." />}
            </TabsContent>
          </Tabs>
        )}
      </Card>
    </div>
  )
}
