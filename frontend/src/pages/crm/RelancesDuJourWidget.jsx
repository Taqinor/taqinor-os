import { Fragment, useEffect, useState } from 'react'
import { CalendarClock } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import crmApi from '../../api/crmApi'
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent, Spinner, Segmented,
  Button, Input,
} from '../../ui'
import RelanceEtapeRow from '../../features/crm/relances/RelanceEtapeRow'
import ToucheMessageDialog from './ToucheMessageDialog'
import { toastError } from '../../lib/toast'

/* ============================================================================
   RELANCE FOUNDATION / MRY14 — panneau « Relances du jour » v2 (plan de
   relance structuré multi-touches, crm.RelanceEtape). Liste les étapes dues
   AUJOURD'HUI + EN RETARD (scope=all par défaut, mêmes règles de portée que
   le reste du CRM — voir crm.selectors.relance_etapes_dues). Trois cadences
   nommées (contact/après devis/réveil, MRY4/MRY5) : message prêt + WhatsApp
   (MRY13, aperçu-puis-clic, décision D5 — AUCUN envoi automatique), appel
   (`tel:`), Fait (avec issue/note/rappel — MRY10, déclenche les règles
   d'arrêt de MRY9), Sauter, Reporter (décale cette touche ET les suivantes,
   MRY10).

   MRY31 — `RelanceEtapeRow` (badges + panneaux Fait/Sauter/Reporter) est
   désormais EXTRAIT dans `features/crm/relances/RelanceEtapeRow.jsx`, partagé
   avec l'écran « Suivi des relances » et la frise de la fiche lead (MRY32).
   Ce widget l'importe tel quel — comportement/markup INCHANGÉS.

   MRY32 — sélecteur « Aujourd'hui + retard | Demain | 7 jours » (scopes
   `all`/`tomorrow`/`week` de MRY30). CAD44 (TRANCHÉ 21/09/2026, MRY32
   rouverte) : une ligne dont l'échéance tombe APRÈS aujourd'hui n'est plus en
   lecture seule — Appeler, WhatsApp et Reporter y sont actionnables (agir en
   avance), « Fait » et « Sauter » restent verrouillés (`enAvance`) : on ne
   coche jamais une touche qui n'a pas encore eu lieu. La frise de la fiche
   applique la MÊME règle.

   CAD117 — « X leads sans cadence » : le seul filet existant était le
   panneau Adhérence (`AdherenceRelancesPanel.jsx`, section « Leads sans
   touche due »), invisible tant qu'on n'ouvre pas cet écran-là. Le compteur
   ci-dessous lit le MÊME sélecteur serveur (`kpi_adherence.leads_sans_touche`,
   `GET relance-etapes/kpi-adherence/`) — jamais recompté ici — et ouvre la
   même liste en lecture seule, à côté des relances du jour. Aucun démarrage
   de cadence en masse depuis ce compteur (garde-fou de la tâche).

   CAD50 — « Annuler »/« Arrêter » n'existaient que sur la fiche du lead.
   « Arrêter la cadence » (`crmApi.arreterCadence`, motif obligatoire — même
   contrat que `SectionPipeline.jsx RelanceCadenceControls`) se pose sur
   CHAQUE ligne : ce cockpit ne montre que des touches `a_faire`, donc une
   cadence toujours ouverte à arrêter. « Annuler » (retour arrière à 24h,
   `crmApi.annulerRelanceEtape`) n'a en revanche RIEN à annuler dans la liste
   ci-dessous par construction : le serveur ne sert ici que des étapes encore
   `a_faire` (`crm.selectors.relance_etapes_dues`), jamais fait/sautée. La
   touche que Meryem vient de traiter DANS CETTE session est donc suivie à
   part (`justeTraitees`, peuplée par `traiter()` sur Fait/Sauter, retirée au
   clic « Annuler ») — c'est elle, et seulement elle, qui porte « Annuler »
   ici.
   ========================================================================== */

const SCOPES = [
  { value: 'all', label: "Aujourd'hui + retard" },
  { value: 'tomorrow', label: 'Demain' },
  { value: 'week', label: '7 jours' },
]

// Casablanca EXPLICITE (jamais le fuseau du navigateur) — même trick que
// `RelancesSuiviPage.jsx`/`LeadCard.jsx` (`en-CA` -> AAAA-MM-JJ, comparable
// par simple ordre de chaîne). Copié plutôt qu'importé (même motif que
// `CadenceFrise.jsx heureDueAt` — deux dérivations de présentation
// indépendantes du même state, pas une logique métier partagée).
function todayCasa() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Casablanca' }).format(new Date())
}

// CAD50 — « Arrêter la cadence » depuis la ligne, motif OBLIGATOIRE (même
// contrat que `SectionPipeline.jsx RelanceCadenceControls`, jamais recopié —
// deux petits composants indépendants sur le même appel serveur). Rendu en
// `<li>` SIBLING de `RelanceEtapeRow` (jamais À L'INTÉRIEUR : ce composant
// est possédé par une autre lane) — les deux sont des enfants directs du même
// `<ul>` via un `Fragment` keyé.
function ArreterCadenceControl({ leadId, onArreter }) {
  const [ouvert, setOuvert] = useState(false)
  const [motif, setMotif] = useState('')
  const [busy, setBusy] = useState(false)

  if (leadId == null) return null

  const confirmer = async () => {
    const m = motif.trim()
    if (!m) return
    setBusy(true)
    try {
      const ok = await onArreter(leadId, m)
      if (ok) { setOuvert(false); setMotif('') }
    } finally {
      setBusy(false)
    }
  }

  return (
    <li className="flex flex-wrap items-center gap-1.5 pb-1 pl-1" data-testid="cad50-arreter">
      {!ouvert ? (
        <Button
          type="button" size="sm" variant="outline" disabled={busy}
          onClick={() => setOuvert(true)}
        >
          Arrêter la cadence
        </Button>
      ) : (
        <>
          <Input
            placeholder="Motif d'arrêt (obligatoire)" value={motif}
            onChange={(e) => setMotif(e.target.value)}
            data-testid="cad50-arreter-motif"
          />
          <Button
            type="button" size="sm" variant="outline" disabled={busy}
            onClick={() => { setOuvert(false); setMotif('') }}
          >
            Annuler
          </Button>
          <Button type="button" size="sm" disabled={busy || !motif.trim()} onClick={confirmer}>
            Confirmer
          </Button>
        </>
      )}
    </li>
  )
}

// CAD99 — seuil de retard INITIAL de la liste « cadences échues à clore ».
// Le sélecteur CAD75 exige que l'APPELANT fournisse ce nombre et l'affiche :
// ni la tâche ni un réglage société ne le portent. C'est une valeur
// d'AFFICHAGE, visible et modifiable à l'écran (« en retard de plus de N
// jours »), jamais une règle métier — elle ne ferme rien, ne déplace rien.
const SEUIL_ECHUES_DEFAUT = 7

// CAD99 — la liste des dossiers dont la cadence est ÉCHUE et que personne n'a
// clos (moitié écran de CAD75). LECTURE SEULE : chaque ligne ouvre la fiche
// du lead, où la décision humaine se prend — aucun bouton de clôture ici
// (garde-fou de la tâche). Absente quand le serveur ne renvoie rien.
function CadencesEchues({ navigate }) {
  const [seuil, setSeuil] = useState(SEUIL_ECHUES_DEFAUT)
  const [lignes, setLignes] = useState([])
  const [ouvert, setOuvert] = useState(false)

  useEffect(() => {
    let active = true
    // Garde défensive (même motif que CAD117) : les suites existantes
    // mockent `crmApi` sans `getCadencesEchues` — la section se tait.
    const requete = typeof crmApi.getCadencesEchues === 'function'
      ? crmApi.getCadencesEchues({ jours: seuil })
      : Promise.reject(new Error('getCadencesEchues indisponible'))
    requete
      .then((r) => { if (active) setLignes(r.data?.results ?? []) })
      .catch(() => { if (active) setLignes([]) })
    return () => { active = false }
  }, [seuil])

  if (lignes.length === 0) return null
  return (
    <div className="mb-3" data-testid="cad99-cadences-echues">
      <button
        type="button"
        className="text-xs font-medium text-warning hover:underline"
        aria-expanded={ouvert}
        onClick={() => setOuvert((o) => !o)}
      >
        {lignes.length} cadence{lignes.length > 1 ? 's' : ''} échue{lignes.length > 1 ? 's' : ''} à clore
      </button>
      {ouvert && (
        <div className="mt-1.5 flex flex-col gap-1.5">
          <label className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
            Dernière touche en retard de plus de
            <Input
              type="number" min={0} step="1" className="w-16"
              aria-label="Retard de plus de (jours)"
              value={seuil}
              onChange={(e) => {
                const n = Number.parseInt(e.target.value, 10)
                if (Number.isFinite(n) && n >= 0) setSeuil(n)
              }}
            />
            jours — personne n’a clos ces dossiers : ouvrez-les pour décider (aucune clôture automatique).
          </label>
          <ul className="flex flex-col gap-1">
            {lignes.map((ligne) => (
              <li key={ligne.etape_id}>
                <button
                  type="button"
                  className="w-full rounded-md border border-border p-1.5 text-left text-xs hover:bg-muted"
                  onClick={() => navigate(`/crm/leads?lead=${ligne.lead_id}`)}
                >
                  <span className="font-medium">{ligne.lead}</span>
                  {ligne.ville ? ` · ${ligne.ville}` : ''}
                  {` · ${ligne.libelle} · en retard de ${ligne.jours_de_retard} j`}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export default function RelancesDuJourWidget() {
  const navigate = useNavigate()
  const [scope, setScope] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [etapes, setEtapes] = useState([])
  const [busyId, setBusyId] = useState(null)
  const [messageEtape, setMessageEtape] = useState(null)
  // CAD117 — indépendant du scope ci-dessus (« sans cadence » n'a pas de
  // notion d'échéance) : une seule lecture au montage, repliée par défaut.
  const [sansCadence, setSansCadence] = useState([])
  const [sansCadenceOuvert, setSansCadenceOuvert] = useState(false)
  // CAD50 — étapes traitées (Fait/Sauter) DANS CETTE session, offertes au
  // retour arrière (`annulerRelanceEtape`, fenêtre serveur 24h — voir la note
  // d'en-tête). Purement local : le serveur ne renvoie plus ces étapes une
  // fois traitées (`relance_etapes_dues` ne sert que du `a_faire`).
  const [justeTraitees, setJusteTraitees] = useState([])

  useEffect(() => {
    let active = true
    // Garde défensive (même motif que `JournalRelance.jsx getJournalRelance`) :
    // les suites existantes mockent `crmApi` avec un sous-ensemble de méthodes
    // qui ne connaît pas encore `getKpiAdherence` — le compteur doit alors se
    // taire exactement comme sur une panne réseau, jamais lever une TypeError.
    const requete = typeof crmApi.getKpiAdherence === 'function'
      ? crmApi.getKpiAdherence({ jours: 30 })
      : Promise.reject(new Error('getKpiAdherence indisponible'))
    requete
      .then((r) => { if (active) setSansCadence(r.data?.leads_sans_touche ?? []) })
      .catch(() => { if (active) setSansCadence([]) })
    return () => { active = false }
  }, [])

  const charger = () => {
    let active = true
    crmApi.getRelanceEtapesDues({ scope })
      .then((r) => { if (active) setEtapes(r.data?.results ?? []) })
      .catch(() => { if (active) setError(true) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }

  useEffect(() => {
    queueMicrotask(() => setLoading(true))
    return charger()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `charger` referme `scope`, déjà en dépendance ; l'ajouter provoquerait la même relecture à chaque rendu sans rien changer.
  }, [scope])

  const retirer = (id) => setEtapes((prev) => prev.filter((e) => e.id !== id))

  const traiter = async (id, action, payload) => {
    setBusyId(id)
    try {
      let res
      if (action === 'fait') res = await crmApi.marquerRelanceEtapeFait(id, payload)
      else if (action === 'sauter') res = await crmApi.marquerRelanceEtapeSautee(id, payload)
      else if (action === 'reporter') res = await crmApi.reporterRelanceEtape(id, payload)
      // CAD50 — Fait/Sauter : la touche quitte cette liste (retirer), mais
      // reste offerte au retour arrière (`justeTraitees`) — Reporter, lui,
      // ne clôt rien, rien à annuler.
      if (action === 'fait' || action === 'sauter') {
        const etape = etapes.find((e) => e.id === id)
        if (etape) setJusteTraitees((prev) => [...prev.filter((e) => e.id !== id), etape])
      }
      retirer(id)
      // MRY9/MRY11 — une action peut faire naître une NOUVELLE touche due
      // (report, clôture de cadence…) : refetch silencieux, jamais bloquant.
      setTimeout(() => { charger() }, 1000)
      return res?.data
    } catch (err) {
      // CKP4 — un canal APPEL clôturé « Fait » sans issue renvoie 400
      // `{erreurs: {outcome}}` : ce champ s'affiche SOUS le contrôle
      // (`RelanceEtapeRow`, promesse rejetée ci-dessous), jamais un toast
      // générique qui masquerait le champ fautif.
      const champOutcome = action === 'fait' && err?.response?.status === 400
        ? err?.response?.data?.erreurs?.outcome : null
      // F2 — l'échec n'est plus MUET : la ligne reste (retirer() jamais
      // appelé ici) et redevient cliquable (busyId remis à null ci-dessous),
      // mais l'agent doit être PRÉVENU que son geste n'a rien fait.
      if (!champOutcome) toastError('Action impossible pour le moment.')
      if (action === 'fait') throw err
      return undefined
    } finally {
      setBusyId(null)
    }
  }

  // CAD50 — retour arrière (24h, refus motivé du serveur au-delà — voir
  // `apps/crm/services.py annuler_touche_relance`) : la touche redevient
  // `a_faire`, donc un refetch la fait réapparaître dans la liste normale.
  const annulerTouche = async (id) => {
    try {
      await crmApi.annulerRelanceEtape(id)
      setJusteTraitees((prev) => prev.filter((e) => e.id !== id))
      charger()
    } catch {
      toastError('Annulation impossible pour le moment.')
    }
  }

  // CAD50 — motif OBLIGATOIRE porté par `ArreterCadenceControl` (même contrat
  // que `SectionPipeline.jsx`). Un refetch retire les touches désormais
  // arrêtées de la liste. Renvoie `true`/`false` (jamais un throw non
  // capturé) : le contrôle referme SEULEMENT sur succès, même patron que
  // `RelanceCadenceControls.arreter` de `SectionPipeline.jsx`.
  const arreterCadenceLead = async (leadId, motif) => {
    try {
      await crmApi.arreterCadence(leadId, { motif })
      charger()
      return true
    } catch {
      toastError('Arrêt de la cadence impossible pour le moment.')
      return false
    }
  }

  return (
    <Card data-testid="relances-du-jour-widget">
      <CardHeader className="flex-row items-start justify-between gap-2 space-y-0">
        <div>
          <CardTitle className="flex items-center gap-2">
            <CalendarClock className="h-4 w-4" /> Relances du jour
          </CardTitle>
          <CardDescription>
            Étapes de plan de relance dues aujourd&apos;hui ou en retard.
          </CardDescription>
        </div>
        {/* MRY31 — porte vers l'écran « Suivi des relances » (tous jours,
            tous statuts, filtre Responsable) — ce widget reste volontairement
            limité à aujourd'hui + retard. */}
        <Link to="/crm/relances" className="shrink-0 text-xs font-medium text-primary hover:underline">
          Voir le suivi
        </Link>
      </CardHeader>
      <CardContent>
        <Segmented
          className="mb-3" size="sm" options={SCOPES} value={scope} onChange={setScope}
        />
        {/* CAD117 — lecture seule : ouvre/replie la liste, ne démarre jamais
            rien. Absent quand `sansCadence` est vide (rien à signaler). */}
        {sansCadence.length > 0 && (
          <div className="mb-3" data-testid="cad117-sans-cadence">
            <button
              type="button"
              className="text-xs font-medium text-primary hover:underline"
              onClick={() => setSansCadenceOuvert((o) => !o)}
            >
              {sansCadence.length} lead{sansCadence.length > 1 ? 's' : ''} sans cadence
            </button>
            {sansCadenceOuvert && (
              <ul className="mt-1.5 flex flex-col gap-1">
                {sansCadence.map((lead) => (
                  <li key={lead.lead_id}>
                    <button
                      type="button"
                      className="w-full rounded-md border border-border p-1.5 text-left text-xs hover:bg-muted"
                      onClick={() => navigate(`/crm/leads?lead=${lead.lead_id}`)}
                    >
                      <span className="font-medium">{lead.nom}</span>
                      {lead.ville ? ` · ${lead.ville}` : ''}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        {/* CAD99 — les cadences échues que personne n'a closes (CAD75),
            en lecture seule, à côté du compteur « sans cadence ». */}
        <CadencesEchues navigate={navigate} />
        {/* CAD50 — retour arrière : les touches traitées DANS CETTE session
            (Fait/Sauter), fenêtre serveur 24h. Disparaît dès qu'annulée OU
            dès que le refetch confirme la clôture (`justeTraitees` filtré). */}
        {justeTraitees.length > 0 && (
          <ul className="mb-3 flex flex-col gap-1" data-testid="cad50-annuler-liste">
            {justeTraitees.map((etape) => (
              <li
                key={etape.id}
                className="flex items-center justify-between gap-2 rounded-md border border-border p-1.5 text-xs"
              >
                <span>
                  <span className="font-medium">{etape.lead_nom}</span>
                  {' — '}
                  {etape.statut_libelle || (etape.statut === 'sautee' ? 'Sautée' : 'Faite')}
                </span>
                <Button type="button" size="sm" variant="outline" onClick={() => annulerTouche(etape.id)}>
                  Annuler
                </Button>
              </li>
            ))}
          </ul>
        )}
        {loading ? (
          <Spinner />
        ) : error ? (
          <p className="text-sm text-muted-foreground">Indisponible pour le moment.</p>
        ) : etapes.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Aucune touche due — les cadences démarrent seules à l&apos;arrivée d&apos;un lead.
          </p>
        ) : (
          <ul className="space-y-2">
            {etapes.map((etape) => (
              <Fragment key={etape.id}>
                <RelanceEtapeRow
                  etape={etape} busyId={busyId} navigate={navigate}
                  enAvance={etape.due_date > todayCasa()}
                  onFait={(id, payload) => traiter(id, 'fait', payload)}
                  onSauter={(id, note) => traiter(id, 'sauter', note)}
                  onReporter={(id, dueAt) => traiter(id, 'reporter', dueAt)}
                  onOuvrirMessage={setMessageEtape}
                  // CAD101 — « pièce reçue » : la touche est close et une étape
                  // « préparer le devis » est née — la file est relue.
                  onPieceRecue={(id) => { retirer(id); charger() }}
                />
                <ArreterCadenceControl leadId={etape.lead} onArreter={arreterCadenceLead} />
              </Fragment>
            ))}
          </ul>
        )}
      </CardContent>
      <ToucheMessageDialog
        etape={messageEtape}
        open={!!messageEtape}
        onOpenChange={(o) => { if (!o) setMessageEtape(null) }}
        onSent={() => { charger() }}
        // CAD63 — la langue du client vient d'être enregistrée depuis
        // l'aperçu : la file est relue (`lead_langue` a changé).
        onLangueEnregistree={() => { charger() }}
      />
    </Card>
  )
}
