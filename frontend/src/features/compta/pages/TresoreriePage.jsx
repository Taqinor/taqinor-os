import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTabParam } from '../components/useTabParam'
import { Plus, Pencil, RefreshCw, BookOpen, Send, Landmark, Download } from 'lucide-react'
import { ListShell } from '../../../ui/module'
import {
  Button, Segmented, Card, EmptyState, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Input, Label,
} from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
// NTTRE20 — kit graphique marque (recharts + tokens) pour la courbe d'écart
// résiduel des rapprochements clôturés.
import { AreaSansAxe, ChartFrame } from '../../../ui/charts'
// APX33 — le tableau PARTAGÉ de la compta (tri + export CSV) remplace les
// tables écrites à la main.
import ComptaTable from '../ComptaTable'
import comptaApi from '../../../api/comptaApi'
import useComptaList from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'
// NTTRE21 — journal de trésorerie imprimable (carte autonome, hors `pages/`
// pour ne pas gonfler cet écran déjà dense).
import JournalTresorerieCard from '../components/JournalTresorerieCard.jsx'
// WIR254 — l'analyse des frais bancaires réutilise le rendu générique
// d'EtatsPage au lieu d'en réinventer un pour ce seul écran.
import { EtatRender } from './EtatsPage.jsx'

/* ============================================================================
   UX6 — Trésorerie & prévisionnel.
   ----------------------------------------------------------------------------
   Onglets : comptes de trésorerie (banques), caisses, virements internes et
   lignes prévisionnelles. CRUD par onglet. Endpoints /compta/tresorerie/,
   /caisses/, /virements/, /previsionnel/. Onglet « Position » = lecture seule
   (FG122/FG126) : position consolidée + projection nette et prévisionnel
   roulant 13 semaines (GET /compta/etats/position-tresorerie/ et
   /compta/etats/previsionnel-tresorerie/).
   ========================================================================== */

const TABS = [
  { value: 'tresorerie', label: 'Comptes' },
  { value: 'caisses', label: 'Caisses' },
  { value: 'virements', label: 'Virements' },
  { value: 'previsionnel', label: 'Prévisionnel' },
  { value: 'position', label: 'Position & projection' },
  // AUDV02 — la fiche d'un compte de TIERS : encours réel + lignes non
  // lettrées. Onglet en LECTURE SEULE, comme « Position & projection ».
  { value: 'fiche-tiers', label: 'Fiche tiers' },
]

// AUDV02 — un compte de TIERS au sens du CGNC : classe 3 (créances, dont
// clients 342x) et classe 4 (dettes, dont fournisseurs 441x). Filtrer ici
// évite de proposer les 400+ comptes du plan pour une question qui ne porte
// que sur les comptes lettrables.
const CLASSES_TIERS = ['3', '4']

// AUDV01 — libellés des NATURES de ligne publiées par
// `apps/compta/selectors.py::previsionnel_tresorerie` (clé `type`). Un type
// inconnu s'affiche tel quel plutôt que de disparaître : mieux vaut un mot
// technique visible qu'une ligne muette.
const NATURE_MOUVEMENT = {
  prevu: 'Prévision saisie',
  effet: 'Effet',
  echeance_emprunt: 'Échéance emprunt',
}

const RESOURCE = {
  tresorerie: comptaApi.tresorerie,
  caisses: comptaApi.caisses,
  virements: comptaApi.virements,
  previsionnel: comptaApi.previsionnel,
}

const FIELDS = {
  tresorerie: [
    { name: 'libelle', label: 'Libellé', required: true },
    { name: 'banque', label: 'Banque' },
    { name: 'rib', label: 'RIB' },
    { name: 'iban', label: 'IBAN' },
    { name: 'solde_initial', label: 'Solde initial', type: 'number' },
  ],
  caisses: [
    { name: 'libelle', label: 'Libellé', required: true },
    { name: 'responsable', label: 'Responsable' },
    { name: 'solde_initial', label: 'Solde initial', type: 'number' },
  ],
  virements: [
    { name: 'date_virement', label: 'Date', type: 'date', required: true },
    { name: 'montant', label: 'Montant', type: 'number', required: true },
    { name: 'libelle', label: 'Libellé' },
    { name: 'reference', label: 'Référence' },
  ],
  previsionnel: [
    { name: 'libelle', label: 'Libellé', required: true },
    { name: 'date_prevue', label: 'Date prévue', type: 'date', required: true },
    { name: 'montant', label: 'Montant', type: 'number', required: true },
    { name: 'commentaire', label: 'Commentaire' },
  ],
}

const money = (v) => formatMAD(v)

const COLUMNS = {
  tresorerie: [
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'banque', header: 'Banque', accessor: (r) => r.banque || '—' },
    { id: 'rib', header: 'RIB', accessor: (r) => r.rib || '—',
      cell: (v) => <span className="font-mono text-xs">{v}</span> },
    { id: 'solde', header: 'Solde initial', accessor: (r) => Number(r.solde_initial) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
  ],
  caisses: [
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'responsable', header: 'Responsable', accessor: (r) => r.responsable || '—' },
    { id: 'solde', header: 'Solde courant', accessor: (r) => Number(r.solde_courant ?? r.solde_initial) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
  ],
  virements: [
    { id: 'date', header: 'Date', accessor: (r) => r.date_virement, searchable: false,
      cell: (v) => formatDate(v) },
    { id: 'source', header: 'Source', accessor: (r) => r.source_libelle || '—' },
    { id: 'dest', header: 'Destination', accessor: (r) => r.destination_libelle || '—' },
    { id: 'montant', header: 'Montant', accessor: (r) => Number(r.montant) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
  ],
  previsionnel: [
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'categorie', header: 'Catégorie', accessor: (r) => r.categorie_display || r.categorie || '—' },
    { id: 'date', header: 'Date prévue', accessor: (r) => r.date_prevue, searchable: false,
      cell: (v) => formatDate(v) },
    { id: 'montant', header: 'Montant', accessor: (r) => Number(r.montant) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
  ],
}

// WIR254 — NTFIN? / analyse_frais_bancaires : `etats/frais-bancaires`
// (commissions/agios par compte de trésorerie sur une période) n'avait aucun
// client ni écran.
function FraisBancairesCard() {
  const [debut, setDebut] = useState('')
  const [fin, setFin] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  const charger = () => {
    setLoading(true)
    comptaApi.etats.fraisBancaires({ debut: debut || undefined, fin: fin || undefined })
      .then((res) => setData(res.data))
      .catch(() => toast.error('Analyse des frais bancaires indisponible.'))
      .finally(() => setLoading(false))
  }

  return (
    <Card className="p-4 sm:p-5">
      <h3 className="mb-3 font-display text-base font-semibold">Frais bancaires (période)</h3>
      <div className="mb-3 flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <Label htmlFor="fb-debut">Du</Label>
          <Input id="fb-debut" type="date" value={debut} onChange={(e) => setDebut(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="fb-fin">Au</Label>
          <Input id="fb-fin" type="date" value={fin} onChange={(e) => setFin(e.target.value)} />
        </div>
        <Button variant="outline" size="sm" onClick={charger}>Charger</Button>
      </div>
      {loading ? (
        <p className="py-4 text-center text-sm text-muted-foreground">Chargement…</p>
      ) : data ? (
        <EtatRender data={data} />
      ) : (
        <EmptyState title="Aucune donnée chargée" description="Choisissez une période puis cliquez sur Charger." />
      )}
    </Card>
  )
}

/* NTTRE20 — Historique visuel des rapprochements CLÔTURÉS : par mois, le
   nombre de lignes de relevé restées « non pointées » à la clôture. Indicateur
   de QUALITÉ du rapprochement dans le temps (une courbe qui remonte signale
   des clôtures de plus en plus permissives). Lecture seule sur des données
   déjà en base — aucun calcul côté écran. */
function QualiteRapprochementsCard() {
  const [data, setData] = useState(null)

  useEffect(() => {
    let vivant = true
    comptaApi.etats.qualiteRapprochements()
      .then((res) => { if (vivant) setData(res.data) })
      .catch(() => { if (vivant) setData(null) })
    return () => { vivant = false }
  }, [])

  const mois = data?.mois || []
  const points = mois.map((m) => ({
    label: m.mois,
    value: Number(m.lignes_non_pointees) || 0,
    rapprochements: Number(m.rapprochements) || 0,
  }))

  return (
    <Card className="p-4 sm:p-5">
      <h3 className="mb-3 font-display text-base font-semibold">
        Qualité des rapprochements clôturés
      </h3>
      {!points.length ? (
        <EmptyState
          title="Aucun rapprochement clôturé"
          description="La courbe apparaîtra dès le premier rapprochement clôturé."
        />
      ) : (
        <ChartFrame
          label="Lignes de relevé restées non pointées à la clôture, par mois"
          columns={[
            { key: 'label', header: 'Mois' },
            { key: 'rapprochements', header: 'Rapprochements clôturés', align: 'right' },
            { key: 'value', header: 'Lignes non pointées', align: 'right' },
          ]}
          rows={points}
          getRowKey={(p) => p.label}
        >
          <AreaSansAxe
            data={points}
            tone="warning"
            height={180}
            name="Lignes non pointées"
          />
        </ChartFrame>
      )}
    </Card>
  )
}

// Onglet lecture seule : position consolidée + prévisionnel roulant.
function PositionPanel() {
  const [position, setPosition] = useState(null)
  const [previsionnel, setPrevisionnel] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([
      comptaApi.etats.positionTresorerie(),
      comptaApi.etats.previsionnelTresorerie(),
    ])
      .then(([pos, prev]) => {
        setPosition(pos.data)
        setPrevisionnel(prev.data)
      })
      .catch(() => toast.error('Impossible de charger la position de trésorerie.'))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => load(), [load])

  // NTTRE19 — export du prévisionnel 13 semaines en classeur pour le banquier.
  const exporterXlsx = async () => {
    try {
      const res = await comptaApi.etats.previsionnelTresorerieXlsx()
      const blob = res.data instanceof Blob ? res.data : new Blob([res.data])
      comptaApi.downloadBlob(blob, 'previsionnel-tresorerie.xlsx')
    } catch {
      toast.error('Export du prévisionnel indisponible.')
    }
  }

  if (loading) {
    return <p className="py-8 text-center text-sm text-muted-foreground">Chargement…</p>
  }

  const comptes = position?.comptes || []
  const semaines = previsionnel?.semaines || previsionnel?.lignes || []
  // AUDV01 / DRAFT165-34 — le détail NOMMÉ des mouvements prévus. Le serveur
  // publie déjà `semaines[].lignes[]` (contrat committé
  // apps/compta/contract_samples/previsionnel_tresorerie.json) mais l'écran ne
  // lisait que les totaux : une échéance d'emprunt (XACC14) était fondue dans
  // « Sorties » sans le moindre libellé — le comptable voyait le montant sans
  // jamais savoir d'où il venait. Aucun calcul ici : on aplatit, on affiche.
  const mouvements = semaines.flatMap((s) => (s.lignes || []))

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-4 sm:p-5">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="font-display text-base font-semibold">Position consolidée</h3>
          <Button variant="outline" size="sm" onClick={load}><RefreshCw className="size-4" /> Actualiser</Button>
        </div>
        {!comptes.length ? (
          <EmptyState title="Aucune donnée" description="Aucun compte de trésorerie." />
        ) : (
          <div>
            <ComptaTable
              aria-label="Position consolidée"
              exportName="position-consolidee"
              rows={comptes}
              getRowKey={(c, i) => c.id ?? i}
              columns={[
                { key: 'libelle', label: 'Compte', sortValue: (c) => c.libelle || `Compte #${c.id}`,
                  cell: (c) => c.libelle || `Compte #${c.id}` },
                { key: 'solde', label: 'Solde', align: 'right', numeric: true,
                  sortValue: (c) => Number(c.solde) || 0, cell: (c) => formatMAD(c.solde) },
              ]}
            />
            <div className="mt-3 flex items-center justify-between rounded-lg border px-3 py-2 text-sm">
              <span className="text-muted-foreground">Total</span>
              <strong className="tabular-nums">{formatMAD(position.total)}</strong>
            </div>
          </div>
        )}
      </Card>

      <Card className="p-4 sm:p-5">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h3 className="font-display text-base font-semibold">Prévisionnel roulant (13 semaines)</h3>
          {/* NTTRE19 — classeur .xlsx pour le banquier : une colonne par
              semaine + la ligne « Solde projeté », mêmes chiffres qu'ici. */}
          <Button variant="outline" size="sm" onClick={exporterXlsx}>
            <Download className="size-4" /> Exporter (xlsx)
          </Button>
        </div>
        {/* WIR182 — NTTRE18 : bandeau d'alerte quand le solde projeté passe
            sous zéro (`date_rupture_estimee`, apps/compta/selectors.py). */}
        {previsionnel?.date_rupture_estimee && (
          <div className="mb-3 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            Rupture de trésorerie estimée le {formatDate(previsionnel.date_rupture_estimee)}.
          </div>
        )}
        {!semaines.length ? (
          <EmptyState title="Aucune donnée" description="Aucune ligne prévisionnelle." />
        ) : (
          <ComptaTable
            aria-label="Prévisionnel roulant"
            exportName="previsionnel-13-semaines"
            rows={semaines}
            getRowKey={(s, i) => i}
            columns={[
              { key: 'semaine', label: 'Semaine',
                sortValue: (s) => s.date_debut || s.semaine || '',
                cell: (s, i) => s.date_debut || s.semaine || `S${i + 1}` },
              { key: 'entrees', label: 'Entrées', align: 'right', numeric: true,
                sortValue: (s) => Number(s.entrees) || 0, cell: (s) => formatMAD(s.entrees) },
              { key: 'sorties', label: 'Sorties', align: 'right', numeric: true,
                sortValue: (s) => Number(s.sorties) || 0, cell: (s) => formatMAD(s.sorties) },
              { key: 'flux_net', label: 'Flux net', align: 'right', numeric: true,
                sortValue: (s) => Number(s.flux_net) || 0, cell: (s) => formatMAD(s.flux_net) },
              // WIR182 — la SEULE clé réelle du serveur est `solde_fin`
              // (apps/compta/selectors.py::previsionnel_tresorerie) ; l'écran
              // lisait `solde_projete`, qui n'a jamais existé → « — » figé.
              { key: 'solde_fin', label: 'Solde projeté', align: 'right', numeric: true,
                sortValue: (s) => Number(s.solde_fin) || 0, cell: (s) => formatMAD(s.solde_fin) },
            ]}
          />
        )}

        {mouvements.length > 0 && (
          <div className="mt-4">
            <h4 className="mb-2 text-sm font-medium">Détail des mouvements prévus</h4>
            <ComptaTable
              aria-label="Détail des mouvements prévus"
              exportName="previsionnel-mouvements"
              rows={mouvements}
              getRowKey={(m, i) => i}
              columns={[
                { key: 'date', label: 'Date', sortValue: (m) => m.date || '',
                  cell: (m) => formatDate(m.date) },
                { key: 'libelle', label: 'Libellé', cell: (m) => m.libelle || '—' },
                { key: 'type', label: 'Nature',
                  cell: (m) => NATURE_MOUVEMENT[m.type] || m.type || '—' },
                { key: 'montant', label: 'Montant', align: 'right', numeric: true,
                  sortValue: (m) => Number(m.montant) || 0,
                  cell: (m) => formatMAD(m.montant) },
              ]}
            />
          </div>
        )}
      </Card>

      <RibInvalidesCard />

      {/* NTTRE21 — journal chronologique d'un compte + export PDF. Les comptes
          déjà chargés par la position consolidée alimentent le sélecteur : pas
          d'appel supplémentaire pour lister les comptes. */}
      <JournalTresorerieCard comptes={comptes} />

      <QualiteRapprochementsCard />

      <FraisBancairesCard />
    </div>
  )
}

/* AUDV02 / XACC24 (DRAFT165-16) — alerte RIB à clé mod-97 fausse.
   `selectors.comptes_tresorerie_rib_invalides` existait sans aucun appelant :
   un virement partait sur un RIB faux et l'erreur ne se voyait qu'au rejet
   par la banque, des semaines plus tard. WARNING pur — rien n'est bloqué ici,
   et la carte DISPARAÎT quand tout est conforme (pas de bandeau vert inutile
   qui ferait du bruit dans un écran déjà dense). */
function RibInvalidesCard() {
  const [alerte, setAlerte] = useState(null)

  useEffect(() => {
    let vivant = true
    comptaApi.tresorerie.ribInvalides()
      .then((res) => { if (vivant) setAlerte(res.data) })
      .catch(() => { if (vivant) setAlerte(null) })
    return () => { vivant = false }
  }, [])

  if (!alerte?.nb) return null
  return (
    <Card className="border-destructive/40 bg-destructive/5 p-4 sm:p-5">
      <h3 className="mb-2 font-display text-base font-semibold text-destructive">
        RIB à vérifier ({alerte.nb})
      </h3>
      <p className="mb-3 text-sm text-muted-foreground">
        Ces comptes portent un RIB dont la clé de contrôle est fausse. Un
        virement émis vers l’un d’eux sera rejeté par la banque.
      </p>
      <ComptaTable
        aria-label="Comptes au RIB invalide"
        exportName="rib-invalides"
        rows={alerte.comptes}
        getRowKey={(c) => c.id}
        columns={[
          { key: 'libelle', label: 'Compte', cell: (c) => c.libelle },
          { key: 'rib', label: 'RIB', cell: (c) => c.rib },
          { key: 'erreurs', label: 'Anomalie',
            cell: (c) => (c.erreurs || []).join(' ') || '—' },
        ]}
      />
    </Card>
  )
}

/* AUDV02 / COMPTA22 (DRAFT165-9+10) — fiche d'un compte de TIERS.
   `encours_tiers` et `lignes_non_lettrees` existaient sans écran : « combien
   ce client me doit-il VRAIMENT ? » n'avait pas de réponse, le solde brut du
   compte comptant aussi les lignes déjà appariées. Lecture seule — aucun
   lettrage n'est posé d'ici. */
function FicheTiersPanel() {
  const [comptes, setComptes] = useState([])
  const [compteId, setCompteId] = useState('')
  const [fiche, setFiche] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let vivant = true
    comptaApi.comptes.list({ page_size: 500 })
      .then((res) => {
        if (!vivant) return
        const liste = Array.isArray(res.data) ? res.data : (res.data?.results || [])
        setComptes(liste.filter(
          (c) => CLASSES_TIERS.includes(String(c.numero || '').charAt(0))))
      })
      .catch(() => { if (vivant) setComptes([]) })
    return () => { vivant = false }
  }, [])

  const charger = async (id) => {
    setCompteId(id)
    setFiche(null)
    if (!id) return
    setLoading(true)
    try {
      const res = await comptaApi.comptes.ficheTiers(id)
      setFiche(res.data)
    } catch {
      toast.error('Fiche tiers indisponible.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="p-4 sm:p-5">
      <div className="mb-3 flex flex-wrap items-end gap-2">
        <div className="flex flex-col gap-1">
          <Label htmlFor="fiche-tiers-compte">Compte de tiers</Label>
          <select
            id="fiche-tiers-compte"
            value={compteId}
            onChange={(e) => charger(e.target.value)}
            className="h-9 rounded-md border border-border bg-card px-3 text-sm"
          >
            <option value="">Choisir un compte…</option>
            {comptes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.numero} — {c.intitule}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading && (
        <p className="py-6 text-center text-sm text-muted-foreground">Chargement…</p>
      )}

      {!loading && fiche && (
        <>
          <div className="mb-3 flex items-center justify-between rounded-lg border px-3 py-2 text-sm">
            <span className="text-muted-foreground">
              Encours (lignes non lettrées uniquement)
            </span>
            <strong className="tabular-nums">{formatMAD(fiche.encours)}</strong>
          </div>
          {fiche.nb_lignes_non_lettrees === 0 ? (
            <EmptyState
              title="Tout est lettré"
              description="Aucune ligne ouverte sur ce compte : rien ne reste dû."
            />
          ) : (
            <ComptaTable
              aria-label="Lignes non lettrées"
              exportName="lignes-non-lettrees"
              rows={fiche.lignes_non_lettrees}
              getRowKey={(l) => l.id}
              columns={[
                { key: 'date_ecriture', label: 'Date',
                  sortValue: (l) => l.date_ecriture || '',
                  cell: (l) => formatDate(l.date_ecriture) },
                { key: 'reference', label: 'Pièce', cell: (l) => l.reference || '—' },
                { key: 'libelle', label: 'Libellé', cell: (l) => l.libelle || '—' },
                { key: 'debit', label: 'Débit', align: 'right', numeric: true,
                  sortValue: (l) => Number(l.debit) || 0,
                  cell: (l) => formatMAD(l.debit) },
                { key: 'credit', label: 'Crédit', align: 'right', numeric: true,
                  sortValue: (l) => Number(l.credit) || 0,
                  cell: (l) => formatMAD(l.credit) },
              ]}
            />
          )}
        </>
      )}
    </Card>
  )
}

// FG124 — Journal d'espèces d'une caisse : mouvements + clôture (cash count).
function CaisseJournalDialog({ caisse, onClose }) {
  const [journal, setJournal] = useState(null)
  const [loading, setLoading] = useState(true)
  const [montant, setMontant] = useState('')
  const [motif, setMotif] = useState('')
  const [sens, setSens] = useState('entree')
  const [soldeCompte, setSoldeCompte] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    comptaApi.caisses.mouvementList(caisse.id)
      .then((res) => setJournal(res.data))
      .catch(() => toast.error('Journal de caisse indisponible.'))
      .finally(() => setLoading(false))
  }, [caisse.id])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => load(), [load])

  const enregistrerMouvement = async () => {
    if (!(Number(montant) > 0)) {
      toast.error('Saisissez un montant positif.')
      return
    }
    try {
      await comptaApi.caisses.mouvementCreer(caisse.id, {
        sens, montant: Number(montant), motif,
        date_mouvement: new Date().toISOString().slice(0, 10),
      })
      toast.success('Mouvement enregistré.')
      setMontant('')
      setMotif('')
      load()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Enregistrement impossible.'))
    }
  }

  const cloturer = async () => {
    if (soldeCompte === '') {
      toast.error('Saisissez le solde compté avant de clôturer.')
      return
    }
    try {
      await comptaApi.caisses.cloturer(caisse.id, {
        date_cloture: new Date().toISOString().slice(0, 10),
        solde_compte: Number(soldeCompte),
      })
      toast.success('Caisse clôturée.')
      setSoldeCompte('')
      load()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Clôture impossible.'))
    }
  }

  const mouvements = Array.isArray(journal) ? journal : (journal?.mouvements || [])

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Journal de caisse — {caisse.libelle}</DialogTitle>
        </DialogHeader>
        {loading ? (
          <p className="py-6 text-center text-sm text-muted-foreground">Chargement…</p>
        ) : !mouvements.length ? (
          <EmptyState title="Aucun mouvement" description="Aucun mouvement d’espèces enregistré." />
        ) : (
          <div className="max-h-60 overflow-y-auto">
            <ComptaTable
              aria-label="Journal de caisse"
              exportName="journal-caisse"
              rows={mouvements}
              getRowKey={(m, i) => m.id ?? i}
              columns={[
                { key: 'date', label: 'Date',
                  sortValue: (m) => m.date || m.date_mouvement || '',
                  cell: (m) => formatDate(m.date || m.date_mouvement) },
                { key: 'sens', label: 'Sens',
                  cell: (m) => (m.sens === 'entree' ? 'Entrée' : 'Sortie') },
                { key: 'motif', label: 'Motif', cell: (m) => m.motif || '—' },
                { key: 'montant', label: 'Montant', align: 'right', numeric: true,
                  sortValue: (m) => Number(m.montant) || 0, cell: (m) => formatMAD(m.montant) },
              ]}
            />
          </div>
        )}

        <div className="flex flex-col gap-2 rounded-lg border p-3">
          <span className="text-sm font-semibold">Nouveau mouvement</span>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            <select
              className="h-[var(--control-h)] rounded-md border border-input bg-card px-[var(--control-px)] text-sm"
              value={sens} onChange={(e) => setSens(e.target.value)}
            >
              <option value="entree">Entrée</option>
              <option value="sortie">Sortie</option>
            </select>
            <Input type="number" step="any" placeholder="Montant" value={montant}
                   onChange={(e) => setMontant(e.target.value)} />
            <Input placeholder="Motif" value={motif} onChange={(e) => setMotif(e.target.value)} />
          </div>
          <Button size="sm" className="w-fit" onClick={enregistrerMouvement}>
            <Plus className="size-4" /> Enregistrer le mouvement
          </Button>
        </div>

        <div className="flex flex-col gap-2 rounded-lg border p-3">
          <span className="text-sm font-semibold">Clôture (comptage physique)</span>
          <div className="flex flex-wrap items-end gap-2">
            <div className="flex flex-col gap-1">
              <Label htmlFor="cc-solde">Solde compté</Label>
              <Input id="cc-solde" type="number" step="any" value={soldeCompte}
                     onChange={(e) => setSoldeCompte(e.target.value)} />
            </div>
            <Button variant="outline" size="sm" onClick={cloturer}>
              <Send className="size-4" /> Clôturer la caisse
            </Button>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Fermer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function TresoreriePage() {
  const [tab, setTab] = useTabParam('tresorerie')  // VX231(c) — onglet persisté (?onglet=)
  const [dialog, setDialog] = useState(null)
  const [caisseJournal, setCaisseJournal] = useState(null)

  const isPosition = tab === 'position'
  const isFicheTiers = tab === 'fiche-tiers'
  // AUDV02 — les deux onglets de LECTURE n'ont pas de ressource CRUD : on
  // charge une liste inoffensive plutôt que d'indexer `RESOURCE` avec un
  // onglet absent (ce qui planterait tout l'écran sur un `.list` de undefined).
  const isLecture = isPosition || isFicheTiers
  const list = useComptaList(
    isLecture ? comptaApi.exercices.list : RESOURCE[tab].list, undefined)

  // FG125 — poste l'écriture équilibrée du virement interne au grand livre.
  const posterVirement = async (row) => {
    try {
      await comptaApi.virements.poster(row.id)
      toast.success('Virement posté.')
      list.reload()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Postage impossible.'))
    }
  }

  const rowActions = (row) => {
    const acts = [{ id: 'edit', label: 'Éditer', icon: Pencil, onClick: () => setDialog({ row }) }]
    if (tab === 'caisses') {
      acts.unshift({
        id: 'journal', label: 'Journal & clôture', icon: BookOpen,
        onClick: () => setCaisseJournal(row),
      })
    }
    if (tab === 'virements' && !row.posted) {
      acts.unshift({
        id: 'poster', label: 'Poster', icon: Landmark, onClick: () => posterVirement(row),
      })
    }
    return acts
  }

  const submit = (payload) => {
    const api = RESOURCE[tab]
    return dialog?.row ? api.update(dialog.row.id, payload) : api.create(payload)
  }

  const singular = useMemo(() => ({
    tresorerie: 'compte', caisses: 'caisse',
    virements: 'virement', previsionnel: 'ligne',
  }[tab]), [tab])

  return (
    <div className="page">
      <div className="page-header">
        <h2>Trésorerie & prévisionnel</h2>
        {!isLecture && (
          <div className="page-header-actions">
            <Button onClick={() => setDialog({ row: null })}>
              <Plus /> Nouveau {singular}
            </Button>
          </div>
        )}
      </div>

      <div className="mb-3">
        <Segmented options={TABS} value={tab} onChange={setTab} aria-label="Onglet trésorerie" />
      </div>

      {isPosition && <PositionPanel />}
      {isFicheTiers && <FicheTiersPanel />}
      {!isLecture && (
        <ListShell
          hideHeader
          title={TABS.find((t) => t.value === tab).label}
          columns={COLUMNS[tab]}
          rows={list.rows}
          loading={list.loading}
          error={list.error}
          rowActions={rowActions}
          exportName={tab}
          emptyTitle="Aucun élément"
          emptyDescription="Rien à afficher pour cet onglet."
        />
      )}

      {dialog && !isLecture && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title={dialog.row ? `Modifier le ${singular}` : `Nouveau ${singular}`}
          fields={FIELDS[tab]}
          initial={dialog.row}
          onSubmit={submit}
          onSaved={list.reload}
        />
      )}

      {caisseJournal && (
        <CaisseJournalDialog caisse={caisseJournal} onClose={() => setCaisseJournal(null)} />
      )}
    </div>
  )
}
