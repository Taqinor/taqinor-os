import { useEffect, useMemo, useRef, useState } from 'react'
import {
  LogOut, Upload, Download, Pencil, MonitorSmartphone, Ban, History, ShieldCheck,
  CalendarPlus,
} from 'lucide-react'
import { ListShell } from '../../ui/module'
import {
  Segmented, Button, Badge, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input,
} from '../../ui'
import { useConfirmDialog } from '../../ui/confirm'
import { formatNumber, formatDate, formatDateTime } from '../../lib/format'
import { rowsToCSV, exportFileName } from '../../ui/datatable/csv.js'
import rhApi from '../../api/rhApi'

/* ============================================================================
   UX24 — Temps & présence.
   ----------------------------------------------------------------------------
   Vues : Pointages (arrivée/départ), Roster (affectations d'équipe), Présences
   chantier, Heures supplémentaires. Le pointage départ passe par l'@action
   serveur (durée calculée côté serveur). Export paie déclenché depuis la barre
   d'actions.
   ========================================================================== */

const VUES = [
  { value: 'pointages', label: 'Pointages' },
  { value: 'roster', label: 'Roster' },
  { value: 'presences', label: 'Présences chantier' },
  { value: 'heures_supp', label: 'Heures supp.' },
  { value: 'devices', label: 'Kiosque' },
  // ZRH6 — absents non justifiés du jour ; ZRH18 — rapport de présence.
  { value: 'absents', label: 'Absents du jour' },
  // WIR195 — les incidents (FG171) étaient un trou noir d'écriture : créés
  // depuis « Absents du jour », jamais relisibles ni justifiables. Ils ont
  // désormais leur vue, avec la régularisation par motif.
  { value: 'incidents', label: 'Incidents de présence' },
  { value: 'rapport', label: 'Rapport de présence' },
]

/* PACT19 — colonnes du CSV « Export paie ». La forme vient du serveur
   (`selectors.heures_supp_pour_paie` : employe_id / hs_25 / hs_50 / hs_100 /
   total_hs / montant_majore) — jamais inventée ici. */
const COLONNES_EXPORT_PAIE = [
  { id: 'employe_id', header: 'Employé (id)' },
  { id: 'hs_25', header: 'HS 25%' },
  { id: 'hs_50', header: 'HS 50%' },
  { id: 'hs_100', header: 'HS 100%' },
  { id: 'total_hs', header: 'Total HS' },
  { id: 'montant_majore', header: 'Montant majoré' },
]

/* ZRH18 — période par défaut du rapport de présence : du 1er du mois à
   aujourd'hui (bornes YYYY-MM-DD attendues par le serveur). */
function aujourdHui() {
  return new Date().toISOString().slice(0, 10)
}
function debutMois() {
  return `${aujourdHui().slice(0, 7)}-01`
}

export default function Temps() {
  const { confirmDelete } = useConfirmDialog()
  const [vue, setVue] = useState('pointages')
  const [pointages, setPointages] = useState([])
  const [roster, setRoster] = useState([])
  const [presences, setPresences] = useState([])
  const [heuresSupp, setHeuresSupp] = useState([])
  const [devices, setDevices] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [correctionFor, setCorrectionFor] = useState(null)
  // XRH11 — historique immuable des corrections du pointage consulté.
  const [historiqueFor, setHistoriqueFor] = useState(null)
  // ZRH6 — absents non justifiés du jour ; ZRH18 — rapport de présence.
  const [absents, setAbsents] = useState([])
  const [rapport, setRapport] = useState(null)
  // WIR238 — écriture du roster + conflits de congé des 30 prochains jours.
  const [employes, setEmployes] = useState([])
  const [conflitsRoster, setConflitsRoster] = useState([])
  const [affectationFor, setAffectationFor] = useState(null)
  const [affectationOpen, setAffectationOpen] = useState(false)
  // WIR195 — incidents de présence (FG171) + compteur par employé.
  const [incidents, setIncidents] = useState([])
  const [compteurIncidents, setCompteurIncidents] = useState([])
  const [justifierFor, setJustifierFor] = useState(null)
  const [nouveauToken, setNouveauToken] = useState(null)
  const fileRef = useRef(null)

  const recharger = () => {
    let vivant = true
    setLoading(true)
    setError(null)
    Promise.all([
      rhApi.getPointages(),
      rhApi.getRoster(),
      rhApi.getPresencesChantier(),
      rhApi.getHeuresSupp(),
      rhApi.getDevicesKiosque(),
      rhApi.getAbsentsNonJustifies(),
      rhApi.getRapportPresence({ debut: debutMois(), fin: aujourdHui() }),
      // WIR195 — incidents de présence + compteur (période serveur par défaut).
      rhApi.getIncidentsPresence(),
      rhApi.getCompteurIncidentsPresence(),
      // WIR238 — conflits de congé du roster (fenêtre serveur : 30 jours) +
      // référentiel employés (cible d'une nouvelle affectation).
      rhApi.getConflitsRoster(),
      rhApi.getEmployes(),
    ])
      .then(([pRes, rRes, prRes, hRes, dRes, aRes, rapRes, incRes, cptRes,
        cfRes, empRes]) => {
        if (!vivant) return
        setIncidents(unwrap(incRes?.data))
        setCompteurIncidents(unwrap(cptRes?.data))
        setConflitsRoster(unwrap(cfRes?.data))
        setEmployes(unwrap(empRes?.data))
        setPointages(unwrap(pRes.data))
        setRoster(unwrap(rRes.data))
        setPresences(unwrap(prRes.data))
        setHeuresSupp(unwrap(hRes.data))
        setDevices(unwrap(dRes.data))
        setAbsents(unwrap(aRes.data))
        setRapport(rapRes.data)
      })
      .catch(() => {
        if (!vivant) return
        setError('Impossible de charger les temps & présences.')
        toast.error('Impossible de charger les temps & présences.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }

  // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
  useEffect(recharger, [])

  const pointerDepart = async (p) => {
    try {
      await rhApi.pointagerDepart(p.id)
      toast.success('Départ pointé.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Pointage impossible.')
    }
  }

  // XRH13 — import CSV pointeuse externe.
  const importerCsv = async (e) => {
    const file = e.target.files?.[0]
    if (fileRef.current) fileRef.current.value = ''
    if (!file) return
    try {
      const res = await rhApi.importPointageCsv(file)
      const d = res.data || {}
      const crees = d.crees ?? d.imported ?? 0
      const erreurs = Array.isArray(d.erreurs) ? d.erreurs.length : (d.erreurs ?? 0)
      toast.success(`Import terminé : ${crees} pointage(s)${erreurs ? `, ${erreurs} erreur(s)` : ''}.`)
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Import du CSV impossible.')
    }
  }

  // XRH10 — émettre un nouveau device kiosque (token affiché une seule fois).
  const emettreDevice = async () => {
    const label = window.prompt('Nom du device (ex. « Tablette entrée atelier ») ?')
    if (label === null) return
    try {
      const res = await rhApi.emettreDeviceKiosque({ label })
      setNouveauToken({ label: res.data?.label || label, token: res.data?.token })
      recharger()
    } catch {
      toast.error('Émission du device impossible.')
    }
  }

  const revoquerDevice = async (d) => {
    const ok = await confirmDelete({
      title: 'Révoquer ce device ?',
      description: 'Le kiosque associé ne pourra plus pointer.',
      confirmLabel: 'Révoquer',
    })
    if (!ok) return
    try {
      await rhApi.revoquerDeviceKiosque(d.id)
      toast.success('Device révoqué.')
      recharger()
    } catch {
      toast.error('Révocation impossible.')
    }
  }

  // PACT19 — « Export paie » : le bouton appelait `/rh/pointages/export-paie/`,
  // qui n'existe pas. L'action réelle vit sur `HeuresSuppViewSet`
  // (`/rh/heures-supp/export-paie/`, apps/rh/views.py) et renvoie les totaux
  // d'heures supplémentaires majorées PAR EMPLOYÉ — c'est donc une sortie de
  // la vue « Heures supp. », pas de la vue « Pointages » : le bouton y a été
  // déplacé. Et il TÉLÉCHARGE désormais réellement le fichier qu'il annonce,
  // au lieu de n'afficher qu'un compte (un bouton doit faire ce qu'il dit).
  const [exportEnCours, setExportEnCours] = useState(false)

  const exporterPaie = async () => {
    setExportEnCours(true)
    try {
      const res = await rhApi.exportPaieHeuresSupp()
      const rows = unwrap(res.data)
      if (rows.length === 0) {
        toast.info('Aucune heure supplémentaire à exporter sur la période.')
        return
      }
      telechargerCsv(rows, COLONNES_EXPORT_PAIE, 'export-paie-heures-supp')
      toast.success(`Export paie téléchargé : ${rows.length} employé(s).`)
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Export paie impossible.')
    } finally {
      setExportEnCours(false)
    }
  }

  const pointageColumns = useMemo(() => [
    {
      id: 'employe',
      header: 'Employé',
      width: 180,
      accessor: (p) => p.employe_nom || String(p.employe || ''),
      cell: (v) => <span className="font-medium">{v || '—'}</span>,
    },
    {
      id: 'arrivee',
      header: 'Arrivée',
      width: 160,
      searchable: false,
      accessor: (p) => p.heure_arrivee || '',
      cell: (v) => (v ? formatDateTime(v) : '—'),
    },
    {
      id: 'depart',
      header: 'Départ',
      width: 160,
      searchable: false,
      accessor: (p) => p.heure_depart || '',
      cell: (v) => (v ? formatDateTime(v) : '—'),
    },
    {
      id: 'duree',
      header: 'Durée',
      width: 100,
      align: 'right',
      searchable: false,
      accessor: (p) => Number(p.duree_minutes ?? 0),
      cell: (v) => (v ? `${formatNumber(v / 60, { decimals: 1 })} h` : '—'),
    },
    {
      id: 'type',
      header: 'Type',
      width: 110,
      accessor: (p) => p.type_pointage_display || p.type_pointage || '',
      cell: (v) => v || '—',
    },
  ], [])

  const pointageActions = (p) => {
    const actions = []
    if (p.heure_arrivee && !p.heure_depart) {
      actions.push({ id: 'depart', label: 'Pointer le départ', icon: LogOut, onClick: () => pointerDepart(p) })
    }
    // XRH11 — corriger un pointage (motif obligatoire, audit immuable serveur).
    actions.push({ id: 'corriger', label: 'Corriger', icon: Pencil, onClick: () => setCorrectionFor(p) })
    // XRH11 — consulter l'audit immuable des corrections (lecture seule).
    actions.push({ id: 'historique', label: 'Historique des corrections', icon: History, onClick: () => setHistoriqueFor(p) })
    return actions
  }

  const deviceColumns = useMemo(() => [
    { id: 'label', header: 'Device', width: 220, accessor: (d) => d.label || '', cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'cree', header: 'Créé le', width: 140, searchable: false, accessor: (d) => d.date_creation || '', cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'actif', header: 'Actif', width: 100, accessor: (d) => (d.actif ? 'oui' : 'non'), cell: (_v, d) => <Badge tone={d.actif ? 'success' : 'neutral'}>{d.actif ? 'Actif' : 'Révoqué'}</Badge> },
  ], [])

  // ZRH6 — un absent non justifié devient un incident de présence en un clic.
  const genererIncident = async (a) => {
    try {
      await rhApi.genererIncidentAbsence({ employe: a.employe_id })
      toast.success('Incident d’absence créé.')
      recharger()
      // WIR195 — bascule sur la vue qui montre ce qui vient d'être créé : un
      // incident écrit sans être relu était le trou noir de cet écran.
      setVue('incidents')
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Création impossible.')
    }
  }

  // WIR195 — colonnes des incidents de présence (clés du sérialiseur serveur).
  const incidentColumns = useMemo(() => [
    { id: 'employe', header: 'Employé', width: 180, accessor: (i) => i.employe_nom || String(i.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'type', header: 'Type', width: 160, accessor: (i) => i.type_incident_display || i.type_incident || '', cell: (v) => v || '—' },
    { id: 'date', header: 'Date', width: 120, searchable: false, accessor: (i) => i.date || '', cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'retard', header: 'Retard (min)', width: 120, align: 'right', numeric: true, searchable: false, accessor: (i) => Number(i.minutes_retard ?? 0), cell: (v) => (v ? v : '—') },
    { id: 'motif', header: 'Motif', width: 200, accessor: (i) => i.motif || '', cell: (v) => v || '—' },
    { id: 'justifie', header: 'Statut', width: 130, accessor: (i) => (i.justifie ? 'justifie' : 'a justifier'), cell: (_v, i) => (i.justifie ? <Badge tone="success">Justifié</Badge> : <Badge tone="warning">À justifier</Badge>) },
  ], [])

  const incidentActions = (i) => (i.justifie
    ? []
    : [{ id: 'justifier', label: 'Justifier', icon: ShieldCheck, onClick: () => setJustifierFor(i) }])

  const absentColumns = useMemo(() => [
    { id: 'nom', header: 'Employé', width: 220, accessor: (a) => a.nom || '', cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'matricule', header: 'Matricule', width: 140, accessor: (a) => a.matricule || '', cell: (v) => v || '—' },
  ], [])

  const absentActions = (a) => [
    { id: 'incident', label: 'Créer un incident d’absence', icon: Ban, onClick: () => genererIncident(a) },
  ]

  // ZRH18 — colonnes du rapport de présence (clés du sélecteur serveur).
  const rapportColumns = useMemo(() => [
    { id: 'nom', header: 'Employé', width: 200, accessor: (r) => r.nom || '', cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'jours', header: 'Jours pointés', width: 130, align: 'right', numeric: true, searchable: false, accessor: (r) => Number(r.jours_pointes ?? 0), cell: (v) => v },
    { id: 'heures', header: 'Heures', width: 110, align: 'right', numeric: true, searchable: false, accessor: (r) => Number(r.heures_totales ?? 0), cell: (v) => `${formatNumber(v, { decimals: 1 })} h` },
    { id: 'hs', header: 'Heures supp.', width: 130, align: 'right', numeric: true, searchable: false, accessor: (r) => Number(r.heures_supp ?? 0), cell: (v) => formatNumber(v, { decimals: 1 }) },
    { id: 'absences', header: 'Absences', width: 110, align: 'right', numeric: true, searchable: false, accessor: (r) => Number(r.jours_absence ?? 0), cell: (v) => v },
    { id: 'taux', header: 'Taux de présence', width: 150, align: 'right', numeric: true, searchable: false, accessor: (r) => Number(r.taux_presence_pct ?? 0), cell: (v) => `${formatNumber(v, { decimals: 1 })} %` },
  ], [])

  const deviceActions = (d) => (d.actif
    ? [{ id: 'revoquer', label: 'Révoquer', icon: Ban, destructive: true, onClick: () => revoquerDevice(d) }]
    : [])

  const rosterColumns = useMemo(() => [
    { id: 'employe', header: 'Employé', width: 180, accessor: (r) => r.employe_nom || String(r.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'equipe', header: 'Équipe', width: 140, accessor: (r) => r.equipe || '', cell: (v) => v || '—' },
    { id: 'date', header: 'Date', width: 120, searchable: false, accessor: (r) => r.date || '', cell: (v) => formatDate(v) },
    { id: 'creneau', header: 'Créneau', width: 120, accessor: (r) => r.creneau_display || r.creneau || '', cell: (v) => v || '—' },
    // WIR238 — `conflit_conge` est calculé par le serveur à chaque écriture
    // (congé VALIDÉ couvrant le jour) : l'afficher est la seule façon de voir
    // qu'on planifie quelqu'un en congé.
    {
      id: 'conflit',
      header: 'Conflit congé',
      width: 140,
      accessor: (r) => (r.conflit_conge ? 'conflit' : ''),
      cell: (_v, r) => (r.conflit_conge
        ? <Badge tone="danger">Congé validé</Badge>
        : '—'),
    },
  ], [])

  // WIR238 — une affectation existante s'édite (le serveur recalcule semaine
  // et conflit à chaque mise à jour).
  const rosterActions = (r) => [
    { id: 'editer', label: 'Modifier', icon: Pencil, onClick: () => setAffectationFor(r) },
  ]

  const presenceColumns = useMemo(() => [
    { id: 'employe', header: 'Employé', width: 180, accessor: (p) => p.employe_nom || String(p.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'chantier', header: 'Chantier', width: 140, accessor: (p) => String(p.installation_id ?? ''), cell: (v) => v || '—' },
    { id: 'date', header: 'Date', width: 120, searchable: false, accessor: (p) => p.date || '', cell: (v) => formatDate(v) },
    { id: 'statut', header: 'Statut', width: 130, accessor: (p) => p.statut_display || p.statut || '', cell: (v) => v || '—' },
    // XRH12 — drapeau géofence posé côté serveur à l'émargement (jamais
    // bloquant : le GPS terrain est imprécis, c'est un signal à vérifier).
    {
      id: 'geofence',
      header: 'Géofence',
      width: 130,
      accessor: (p) => (p.hors_zone ? 'hors zone' : (p.emarge ? 'dans la zone' : '')),
      cell: (_v, p) => {
        if (!p.emarge) return '—'
        return p.hors_zone
          ? <Badge tone="warning">Hors zone</Badge>
          : <Badge tone="success">Dans la zone</Badge>
      },
    },
  ], [])

  /* WIR239 — l'@action `emarger` d'une présence chantier n'avait AUCUN
     appelant : `emarge` ne pouvait jamais devenir vrai, donc la colonne
     « Géofence » affichait « — » pour l'éternité. L'émarger la fait passer à
     « Dans la zone » (ou « Hors zone » si le serveur flague le géofence — un
     signal, jamais un blocage). */
  const emargerPresence = async (p) => {
    try {
      await rhApi.emargerPresenceChantier(p.id)
      toast.success('Présence émargée.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Émargement impossible.')
    }
  }

  const presenceActions = (p) => (p.emarge
    ? []
    : [{ id: 'emarger', label: 'Émarger', icon: ShieldCheck, onClick: () => emargerPresence(p) }])

  const heuresColumns = useMemo(() => [
    { id: 'employe', header: 'Employé', width: 180, accessor: (h) => h.employe_nom || String(h.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'date', header: 'Date', width: 120, searchable: false, accessor: (h) => h.date || '', cell: (v) => formatDate(v) },
    { id: 'total_hs', header: 'Total HS', width: 100, align: 'right', numeric: true, searchable: false, accessor: (h) => Number(h.total_hs ?? 0), cell: (v) => `${formatNumber(v, { decimals: 1 })} h` },
    { id: 'hs_25', header: 'HS 25%', width: 90, align: 'right', numeric: true, searchable: false, accessor: (h) => Number(h.hs_25 ?? 0), cell: (v) => formatNumber(v, { decimals: 1 }) },
    { id: 'hs_50', header: 'HS 50%', width: 90, align: 'right', numeric: true, searchable: false, accessor: (h) => Number(h.hs_50 ?? 0), cell: (v) => formatNumber(v, { decimals: 1 }) },
  ], [])

  const pointagesActions = (
    <div className="flex items-center gap-2">
      <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden" onChange={importerCsv} />
      <Button variant="outline" onClick={() => fileRef.current?.click()}>
        <Upload size={15} strokeWidth={1.75} aria-hidden="true" />
        Importer CSV
      </Button>
    </div>
  )

  // PACT19 — l'export vit avec la donnée qu'il exporte (heures supp. majorées).
  const heuresSuppActions = (
    <Button variant="outline" onClick={exporterPaie} disabled={exportEnCours}>
      <Download size={15} strokeWidth={1.75} aria-hidden="true" />
      {exportEnCours ? 'Export en cours…' : 'Export paie (CSV)'}
    </Button>
  )

  const config = {
    pointages: { title: 'Pointages', columns: pointageColumns, rows: pointages, rowActions: pointageActions, exportName: 'pointages',
      actions: pointagesActions },
    roster: { title: 'Roster', columns: rosterColumns, rows: roster, rowActions: rosterActions, exportName: 'roster',
      actions: (
        <Button onClick={() => setAffectationOpen(true)}>
          <CalendarPlus size={15} strokeWidth={1.75} aria-hidden="true" />
          Nouvelle affectation
        </Button>
      ) },
    presences: { title: 'Présences chantier', columns: presenceColumns, rows: presences, rowActions: presenceActions, exportName: 'presences-chantier' },
    heures_supp: { title: 'Heures supplémentaires', columns: heuresColumns, rows: heuresSupp, exportName: 'heures-supp',
      actions: heuresSuppActions },
    devices: { title: 'Devices kiosque', columns: deviceColumns, rows: devices, rowActions: deviceActions, exportName: 'devices-kiosque',
      actions: <Button variant="outline" onClick={emettreDevice}><MonitorSmartphone size={15} strokeWidth={1.75} aria-hidden="true" />Émettre un device</Button> },
    // ZRH6 — absents non justifiés du jour (aucun pointage NI congé validé).
    absents: { title: 'Absents non justifiés (aujourd’hui)', columns: absentColumns, rows: absents, rowActions: absentActions, exportName: 'absents-non-justifies' },
    // WIR195 — incidents de présence : relisibles ET régularisables.
    incidents: { title: 'Incidents de présence', columns: incidentColumns, rows: incidents, rowActions: incidentActions, exportName: 'incidents-presence' },
    // ZRH18 — rapport de présence & heures supp. du mois en cours.
    rapport: { title: 'Rapport de présence (mois en cours)', columns: rapportColumns, rows: rapport?.par_employe ?? [], exportName: 'rapport-presence' },
  }[vue]

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>Temps & présence</h2>
      </div>

      <Segmented options={VUES} value={vue} onChange={setVue} aria-label="Vue temps & présence" />

      {/* WIR238 — bandeau des conflits de congé sur les 30 jours à venir
          (`/rh/roster/conflits/`, fenêtre posée par le serveur) : planifier
          quelqu'un sur un congé VALIDÉ ne peut pas rester silencieux. */}
      {vue === 'roster' && conflitsRoster.length > 0 && (
        <div className="rounded-lg border border-danger/40 bg-card px-3 py-2 text-sm" role="alert">
          <p className="font-medium">
            {conflitsRoster.length} affectation(s) en conflit de congé sur les 30 prochains jours
          </p>
          <ul className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
            {conflitsRoster.map((c) => (
              <li key={c.id}>
                {c.employe_nom || `Employé #${c.employe}`} — {formatDate(c.date)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* WIR195 — compteur d'incidents par employé (serveur, 90 j par défaut) :
          le pilotage disciplinaire lit une agrégation, jamais un calcul client. */}
      {vue === 'incidents' && compteurIncidents.length > 0 && (
        <div className="rounded-lg border border-border bg-card px-3 py-2 text-sm">
          <p className="font-medium">Incidents non justifiés par employé (90 derniers jours)</p>
          {/* Le sélecteur `compteur_incidents` renvoie employe_id + total (pas
              de nom) : le libellé vient des incidents DÉJÀ chargés, jamais
              d'un nom inventé. */}
          <ul className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
            {compteurIncidents.map((c) => (
              <li key={c.employe_id}>
                {(incidents.find((i) => i.employe === c.employe_id)?.employe_nom)
                  || `Employé #${c.employe_id}`} : <Badge tone="warning">{c.total ?? 0}</Badge>
              </li>
            ))}
          </ul>
        </div>
      )}

      <ListShell
        title={config.title}
        columns={config.columns}
        rows={config.rows}
        loading={loading}
        error={error}
        searchable
        rowActions={config.rowActions}
        actions={config.actions}
        exportName={config.exportName}
        emptyTitle="Aucune ligne"
        emptyDescription="Aucune donnée pour cette vue."
      />

      {correctionFor && (
        <CorrectionDialog
          pointage={correctionFor}
          onClose={() => setCorrectionFor(null)}
          onSaved={() => { setCorrectionFor(null); recharger() }}
        />
      )}
      {historiqueFor && (
        <HistoriqueCorrectionsDialog
          pointage={historiqueFor}
          onClose={() => setHistoriqueFor(null)}
        />
      )}
      {(affectationOpen || affectationFor) && (
        <AffectationRosterDialog
          affectation={affectationFor}
          employes={employes}
          onClose={() => { setAffectationOpen(false); setAffectationFor(null) }}
          onSaved={() => { setAffectationOpen(false); setAffectationFor(null); recharger() }}
        />
      )}
      {justifierFor && (
        <JustifierIncidentDialog
          incident={justifierFor}
          onClose={() => setJustifierFor(null)}
          onSaved={() => { setJustifierFor(null); recharger() }}
        />
      )}
      {nouveauToken && (
        <TokenDialog data={nouveauToken} onClose={() => setNouveauToken(null)} />
      )}
    </div>
  )
}

/* ── XRH11 — Historique IMMUABLE des corrections d'un pointage (lecture) ── */
function HistoriqueCorrectionsDialog({ pointage, onClose }) {
  const [lignes, setLignes] = useState([])
  const [chargement, setChargement] = useState(true)
  const [erreur, setErreur] = useState(null)

  useEffect(() => {
    let vivant = true
    rhApi.getCorrectionsPointage(pointage.id)
      .then((res) => {
        if (!vivant) return
        const d = res.data
        setLignes(Array.isArray(d) ? d : (d?.results ?? []))
      })
      .catch(() => { if (vivant) setErreur('Historique indisponible.') })
      .finally(() => { if (vivant) setChargement(false) })
    return () => { vivant = false }
  }, [pointage.id])

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Historique des corrections</DialogTitle>
        </DialogHeader>
        {chargement && <p className="text-sm text-muted-foreground">Chargement…</p>}
        {erreur && <p className="text-sm text-danger">{erreur}</p>}
        {!chargement && !erreur && lignes.length === 0 && (
          <p className="text-sm text-muted-foreground">Aucune correction sur ce pointage.</p>
        )}
        {lignes.length > 0 && (
          <ul className="flex flex-col gap-3">
            {lignes.map((c) => (
              <li key={c.id} className="rounded-md border border-border p-3 text-sm">
                <div className="font-medium">{c.champ}</div>
                <div className="text-muted-foreground">
                  {(c.ancienne_valeur || '—')} → {(c.nouvelle_valeur || '—')}
                </div>
                <div className="text-xs text-muted-foreground">
                  Motif : {c.motif || '—'}
                  {c.auteur_nom ? ` · ${c.auteur_nom}` : ''}
                  {c.date_creation ? ` · ${formatDateTime(c.date_creation)}` : ''}
                </div>
              </li>
            ))}
          </ul>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Fermer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/* ── XRH11 — Corriger un pointage (motif obligatoire côté serveur) ── */
function CorrectionDialog({ pointage, onClose, onSaved }) {
  const toLocal = (iso) => {
    if (!iso) return ''
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return ''
    const pad = (n) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
  }
  const [arrivee, setArrivee] = useState(toLocal(pointage.heure_arrivee))
  const [depart, setDepart] = useState(toLocal(pointage.heure_depart))
  const [motif, setMotif] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!motif.trim()) { setServerError('Un motif est obligatoire.'); return }
    setSaving(true)
    setServerError(null)
    try {
      const payload = { motif }
      if (arrivee) payload.heure_arrivee = new Date(arrivee).toISOString()
      if (depart) payload.heure_depart = new Date(depart).toISOString()
      await rhApi.updatePointage(pointage.id, payload)
      toast.success('Pointage corrigé (audit conservé).')
      onSaved?.()
    } catch (err) {
      setServerError(err?.response?.data?.motif || err?.response?.data?.detail
        || 'Correction impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose?.() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Corriger le pointage — {pointage.employe_nom || `#${pointage.id}`}</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="co-arr">Arrivée</Label>
              <Input id="co-arr" type="datetime-local" value={arrivee} onChange={(e) => setArrivee(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="co-dep">Départ</Label>
              <Input id="co-dep" type="datetime-local" value={depart} onChange={(e) => setDepart(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="co-motif">Motif de la correction</Label>
            <Input id="co-motif" value={motif} onChange={(e) => setMotif(e.target.value)} placeholder="Obligatoire — tracé dans l’audit" />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Enregistrement…' : 'Corriger'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/* ── WIR238 (FG169) — Créer / modifier une affectation roster ─────────────────
   Le corps ne porte QUE ce que le client sait : employé, équipe, date,
   créneau, note. `semaine_du` et `conflit_conge` sont calculés par
   `services.appliquer_roster` à chaque écriture — les envoyer d'ici
   fabriquerait un conflit qui n'existe pas. `company` reste serveur. */
const CRENEAUX_ROSTER = [
  { value: 'journee', label: 'Journée' },
  { value: 'matin', label: 'Matin' },
  { value: 'apres_midi', label: 'Après-midi' },
]

function AffectationRosterDialog({ affectation, employes, onClose, onSaved }) {
  const edition = Boolean(affectation)
  const [employe, setEmploye] = useState(
    affectation?.employe != null ? String(affectation.employe) : '')
  const [equipe, setEquipe] = useState(affectation?.equipe || '')
  const [date, setDate] = useState(affectation?.date || '')
  const [creneau, setCreneau] = useState(affectation?.creneau || 'journee')
  const [note, setNote] = useState(affectation?.note || '')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const valide = Boolean(employe && equipe.trim() && date)

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      const payload = {
        employe, equipe: equipe.trim(), date, creneau, note: note || '',
      }
      if (edition) await rhApi.updateAffectationRoster(affectation.id, payload)
      else await rhApi.createAffectationRoster(payload)
      toast.success(edition ? 'Affectation mise à jour.' : 'Affectation créée.')
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || data?.equipe || data?.employe
        || 'Enregistrement de l’affectation impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose?.() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {edition ? 'Modifier l’affectation' : 'Nouvelle affectation'}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ar-employe">Employé</Label>
            <select id="ar-employe" value={employe} onChange={(e) => setEmploye(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm">
              <option value="">— Choisir —</option>
              {employes.map((em) => (
                <option key={em.id} value={em.id}>{em.nom} {em.prenom}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ar-equipe">Équipe</Label>
              <Input id="ar-equipe" value={equipe} onChange={(e) => setEquipe(e.target.value)} placeholder="Ex. Camionnette 2" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ar-date">Date</Label>
              <Input id="ar-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ar-creneau">Créneau</Label>
              <select id="ar-creneau" value={creneau} onChange={(e) => setCreneau(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm">
                {CRENEAUX_ROSTER.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ar-note">Note</Label>
            <Input id="ar-note" value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={!valide || saving}>
              {saving ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/* ── WIR195 (FG171) — Justifier un incident de présence (motif) ───────────────
   `justifie`, `justifie_par` et `justifie_le` sont posés CÔTÉ SERVEUR par
   l'action ; seul le motif remonte du client. */
function JustifierIncidentDialog({ incident, onClose, onSaved }) {
  const [motif, setMotif] = useState(incident.motif || '')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!motif.trim()) { setServerError('Un motif est obligatoire.'); return }
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.justifierIncidentPresence(incident.id, { motif: motif.trim() })
      toast.success('Incident justifié.')
      onSaved?.()
    } catch (err) {
      setServerError(err?.response?.data?.detail ?? 'Régularisation impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose?.() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>
            Justifier l’incident — {incident.employe_nom || `#${incident.id}`}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ji-motif">Motif de la régularisation</Label>
            <Input id="ji-motif" autoFocus value={motif} onChange={(e) => setMotif(e.target.value)}
              placeholder="Ex. Justificatif médical fourni" />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Enregistrement…' : 'Justifier'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/* ── XRH10 — Token de device affiché UNE seule fois ── */
function TokenDialog({ data, onClose }) {
  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose?.() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Device « {data.label} » émis</DialogTitle></DialogHeader>
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted-foreground">
            Copiez ce jeton maintenant : il ne sera plus jamais affiché. Il
            authentifie le kiosque (en-tête X-Kiosque-Token).
          </p>
          <code className="select-all break-all rounded-md border border-border bg-muted px-3 py-2 font-mono text-sm">
            {data.token || '—'}
          </code>
        </div>
        <DialogFooter>
          <Button type="button" onClick={onClose}>J’ai copié le jeton</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function unwrap(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  return []
}

/* PACT19 — téléchargement CSV côté client, même mécanique que l'export de
   `DataTable` (`rowsToCSV` + `exportFileName`, BOM UTF-8 pour Excel fr) :
   aucune sérialisation dupliquée, aucun endpoint de fichier à inventer. */
function telechargerCsv(rows, columns, base) {
  const blob = new Blob([rowsToCSV(rows, columns)],
    { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = exportFileName(base)
  a.click()
  URL.revokeObjectURL(url)
}
