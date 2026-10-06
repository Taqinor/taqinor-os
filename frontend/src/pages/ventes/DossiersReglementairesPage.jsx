import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import ventesApi from '../../api/ventesApi'
import PageHeader from '../../components/layout/PageHeader'
import {
  Badge, Button, Card, CardContent, EmptyState, Input, Label, Segmented,
  Skeleton,
} from '../../ui'
import { formatDateTime } from '../../lib/format'

/* ============================================================================
   WIR104 — Écran unique du cluster réglementaire / mise en service de ventes.
   ----------------------------------------------------------------------------
   Décision de localité consignée en tête de `apps/ventes/models_regulatory.py` :
   ce cluster RESTE dans `ventes` (dossier réglementaire de l'affaire, déposé
   chez ONEE/ANRE/le distributeur) — `installations` porte, elle, l'exécution
   physique (CommissioningRecord, HandoverPack…). Les deux cycles de vie sont
   distincts et ne fusionnent pas.

   Conséquence : ces ~13 ViewSets étaient complets, testés… et SANS AUCUN
   consommateur. Cet écran est ce consommateur : une liste en lecture par
   ressource, avec un rendu générique (aucune colonne inventée — on affiche les
   champs réellement renvoyés par le serveur). Aucun montant d'achat ni marge
   n'est demandé ni rendu.
   ========================================================================== */

// Liste BLANCHE des ressources — le segment de chemin ne vient jamais d'une
// saisie utilisateur.
const RESSOURCES = [
  { value: 'dossiers-reglementaires', label: 'Dossiers', tag: 'FG268' },
  { value: 'dossiers-checklist', label: 'Checklists', tag: 'FG268' },
  { value: 'dossiers-echanges', label: 'Échanges opérateur', tag: 'FG269' },
  { value: 'subventions', label: 'Subventions', tag: 'FG270' },
  { value: 'regularisations-8221', label: 'Régularisation 82-21', tag: 'FG271' },
  { value: 'recettes-mes', label: 'Recette IEC 62446', tag: 'FG274' },
  { value: 'courbes-iv', label: 'Courbes I-V', tag: 'FG275' },
  { value: 'packs-asbuilt', label: 'Packs as-built', tag: 'FG276' },
  { value: 'attestations-conformite', label: 'Attestations conformité', tag: 'FG277' },
  { value: 'tests-pr-reception', label: 'Tests PR réception', tag: 'FG278' },
  { value: 'attestations-re', label: 'Attestations RE', tag: 'FG287' },
  { value: 'calepinages', label: 'Calepinages', tag: 'FG245' },
]

// Colonnes rendues, dans cet ordre, UNIQUEMENT si la ressource les renvoie.
const COLONNES_PREFEREES = [
  'reference', 'nom', 'libelle', 'designation', 'etape', 'type',
  'operateur', 'regime', 'statut', 'echeance', 'date', 'date_creation',
]

/* ── WIR224/FG273 — Calendrier réglementaire : les alertes d'expiration ─────
   `GET /ventes/calendrier-reglementaire/` agrège depuis toujours les échéances
   des dossiers (pièces de checklist datées, dépôts en instruction, validité
   d'un accord) et calcule LUI-MÊME le statut d'alerte. Rien ne le lisait :
   l'écran ne montrait que des listes brutes, et une échéance dépassée n'était
   visible NULLE PART.

   Les trois statuts viennent du SERVEUR (`statut_alerte`), jamais d'un calcul
   de date refait ici : le seuil « imminent » est un réglage serveur
   (`?seuil=`), le refaire côté écran le ferait diverger au premier changement.
   Le filtre recharge donc AUSSI du serveur (`?statut=`) plutôt que de filtrer
   une liste déjà rendue. */
const STATUTS_ALERTE = [
  { value: 'expire', label: 'Expiré', tone: 'danger' },
  { value: 'imminent', label: 'Imminent', tone: 'warning' },
  { value: 'a_venir', label: 'À venir', tone: 'info' },
]

const TON_ALERTE = Object.fromEntries(
  STATUTS_ALERTE.map((s) => [s.value, s.tone]))
const LIBELLE_ALERTE = Object.fromEntries(
  STATUTS_ALERTE.map((s) => [s.value, s.label]))

/* ── CHT26 — File de travail : dossiers réglementaires groupés par statut ──
   Le tableau générique ci-dessus liste UNE ressource à la fois sans jamais
   dire où porter l'attention en premier. Cette vue groupe les dossiers
   (FG268) par les 7 statuts canoniques (models_regulatory.py) et les trie
   par urgence — le statut d'alerte déjà calculé par le calendrier (CHT25 y
   ajoute la prochaine action explicite), jamais un recalcul de date ici. */
const STATUTS_DOSSIER = [
  { value: 'en_constitution', label: 'En constitution' },
  { value: 'depose', label: 'Déposé' },
  { value: 'en_instruction', label: 'En instruction' },
  { value: 'complement_demande', label: 'Complément demandé' },
  { value: 'approuve', label: 'Approuvé' },
  { value: 'refuse', label: 'Refusé' },
  { value: 'comptage_pose', label: 'Comptage posé' },
]

const VUES = [
  { value: 'tableau', label: 'Tableau' },
  { value: 'file', label: 'File de travail' },
]

const ORDRE_URGENCE = { expire: 0, imminent: 1, a_venir: 2 }

// La plus urgente échéance liée à un dossier, toutes origines confondues
// (pièce de checklist, dépôt en instruction, validité d'accord, prochaine
// action explicite CHT25) — ``null`` si le dossier n'a aucune échéance.
const urgenceDossier = (dossierId, echeances) => {
  let pire = null
  for (const e of echeances) {
    if (String(e.dossier_id) !== String(dossierId)) continue
    const rang = ORDRE_URGENCE[e.statut_alerte] ?? 3
    if (!pire || rang < pire.rang ||
        (rang === pire.rang && e.date_echeance < pire.date_echeance)) {
      pire = { rang, ...e }
    }
  }
  return pire
}

// Jours restants : le serveur les compte (négatif = dépassé). On ne recalcule
// jamais une date ici.
const renduJours = (jours) => {
  if (jours == null) return '—'
  if (jours < 0) return `en retard de ${Math.abs(jours)} j`
  if (jours === 0) return "aujourd'hui"
  return `dans ${jours} j`
}

const estAffichable = (v) =>
  v == null || ['string', 'number', 'boolean'].includes(typeof v)

const rendu = (v) => {
  if (v == null || v === '') return '—'
  if (typeof v === 'boolean') return v ? 'Oui' : 'Non'
  if (typeof v === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(v)) {
    return formatDateTime(v)
  }
  return String(v)
}

/* ── CIQ638 — Détail 82-21 d'un dossier : régime sourcé, pièces par étape avec
   leur source, étude, capacité, convention, exploitation, échéance des
   travaux, équipements figés et alertes de modification. Tout vient du
   SERVEUR (`regime`, `pieces`, `resume` du contrat `dossier_8221.json`) :
   aucune date, aucun délai, aucun régime n'est recalculé ici. */
const ETAPES_PIECES = [
  { value: 'depot', label: 'Dépôt' },
  { value: 'etude', label: 'Étude du distributeur' },
  { value: 'convention', label: 'Convention' },
  { value: 'comptage', label: 'Comptage' },
  { value: 'exploitation', label: 'Exploitation' },
  { value: 'travaux', label: 'Travaux' },
]

const GUICHETS = {
  distributeur: 'Distributeur (ONEE ou SRM régionale)',
  services_deconcentres_energie: "Services déconcentrés de l'énergie",
}

const CONCLUSIONS = [
  { value: '', label: '—' },
  { value: 'favorable', label: 'Favorable' },
  { value: 'alternative', label: 'Solution alternative proposée' },
  { value: 'refus', label: 'Refus' },
]

const ETATS_CAPACITE = [
  { value: '', label: '—' },
  { value: 'provisoire', label: 'Réservée provisoirement' },
  { value: 'definitive', label: 'Réservée définitivement' },
]

const REGLAGES = [
  { value: '', label: 'Non renseigné' },
  { value: 'oui', label: 'Oui' },
  { value: 'non', label: 'Non' },
]

// Champs saisis du dossier (écrits tels quels, jamais calculés ici).
const CHAMPS_DATE_DOSSIER = [
  ['etude_frais_notifies_le', "Frais d'étude notifiés le", (r) => r.etude?.frais_notifies_le],
  ['etude_payee_le', 'Étude payée le', (r) => r.etude?.payee_le],
  ['capacite_date', 'Capacité réservée le', (r) => r.capacite?.date],
  ['convention_signee_le', 'Convention signée le', (r) => r.convention_signee_le],
  ['demande_exploitation_le', "Demande d'exploitation le", (r) => r.demande_exploitation_le],
  ['accord_exploitation_le', "Accord d'exploitation le", (r) => r.accord_exploitation_le],
]

const versTexte = (v) => (v == null ? '' : String(v))

const reglagesVersTexte = (v) => {
  if (v === true) return 'oui'
  if (v === false) return 'non'
  // Le résumé peut porter le texte saisi d'après l'étude : présent = « oui ».
  return v ? 'oui' : ''
}

// L'état du formulaire est lu du dossier (champs saisis) et, à défaut, du
// `resume` du contrat.
function etatDepuisDossier(d) {
  const resume = d.resume || {}
  const etat = {}
  for (const [cle, , lire] of CHAMPS_DATE_DOSSIER) {
    etat[cle] = versTexte(d[cle] ?? lire(resume))
  }
  etat.etude_conclusion = versTexte(d.etude_conclusion ?? resume.etude?.conclusion)
  etat.capacite_etat = versTexte(d.capacite_etat ?? resume.capacite?.etat)
  etat.etude_reglages_imposes = reglagesVersTexte(
    d.etude_reglages_imposes !== undefined
      ? d.etude_reglages_imposes
      : resume.etude?.reglages_imposes)
  return etat
}

function payloadDepuisEtat(etat) {
  const payload = {}
  for (const [cle] of CHAMPS_DATE_DOSSIER) payload[cle] = etat[cle] || null
  payload.etude_conclusion = etat.etude_conclusion || null
  payload.capacite_etat = etat.capacite_etat || null
  payload.etude_reglages_imposes = etat.etude_reglages_imposes === 'oui' ? true
    : etat.etude_reglages_imposes === 'non' ? false : null
  return payload
}

function guichetRendu(regime) {
  if (!regime?.guichet) return '—'
  const nom = GUICHETS[regime.guichet] || regime.guichet
  return regime.guichet_statut === 'a_confirmer' ? `${nom} — à confirmer` : nom
}

function piecesParEtape(pieces) {
  const connues = ETAPES_PIECES.map((e) => e.value)
  const groupes = ETAPES_PIECES.map((e) => ({
    ...e, pieces: pieces.filter((p) => p.etape === e.value),
  }))
  const autres = pieces.filter((p) => !connues.includes(p.etape))
  if (autres.length > 0) groupes.push({ value: 'autre', label: 'Autres', pieces: autres })
  return groupes.filter((g) => g.pieces.length > 0)
}

function DossierDetail82({ dossier, onSaved, onClose }) {
  const [etat, setEtat] = useState(() => etatDepuisDossier(dossier))
  const [busy, setBusy] = useState(false)
  const [erreurs, setErreurs] = useState({})
  const [erreurGenerale, setErreurGenerale] = useState(null)
  const resume = dossier.resume || {}
  const regime = dossier.regime || null
  const pieces = dossier.pieces || []
  const manquantes = resume.pieces_manquantes || []
  const equipements = resume.equipements_figes || []
  const alertes = resume.alertes_modification || []
  const champ = (cle) => (valeur) => setEtat((p) => ({ ...p, [cle]: valeur }))

  const enregistrer = async () => {
    setBusy(true)
    setErreurs({})
    setErreurGenerale(null)
    try {
      const r = await ventesApi.patchReglementaire(
        'dossiers-reglementaires', dossier.id, payloadDepuisEtat(etat))
      onSaved?.(r.data)
    } catch (err) {
      const data = err?.response?.data
      // Erreurs de validation : sous le champ fautif ; le reste en bandeau.
      if (data && typeof data === 'object' && !data.detail) {
        const parChamp = {}
        for (const [k, v] of Object.entries(data)) {
          parChamp[k] = Array.isArray(v) ? v.join(' ') : String(v)
        }
        setErreurs(parChamp)
      } else {
        setErreurGenerale(data?.detail || "L'enregistrement du dossier a échoué.")
      }
    } finally {
      setBusy(false)
    }
  }

  const erreurSous = (cle) => (erreurs[cle]
    ? <p className="form-error" role="alert">{erreurs[cle]}</p> : null)

  return (
    <div className="mt-3 flex w-full flex-col gap-4 rounded-lg border border-border p-3"
         data-testid="dossier-detail-8221">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="m-0 text-sm font-semibold text-foreground">Dossier loi 82-21</h4>
        <Button type="button" size="sm" variant="ghost" onClick={onClose}>Fermer</Button>
      </div>

      {regime && (
        <section aria-label="Régime 82-21" className="flex flex-col gap-1 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-foreground">{regime.libelle}</span>
            {regime.a_qualifier && <Badge tone="warning">À qualifier</Badge>}
          </div>
          <span className="text-muted-foreground">Base : {regime.base}</span>
          <span className="text-muted-foreground">Guichet : {guichetRendu(regime)}</span>
          {regime.puissance_retenue_kw != null && (
            <span className="text-muted-foreground">
              Puissance retenue : {regime.puissance_retenue_kw} kW
              {regime.base_puissance === 'a_confirmer_avec_le_distributeur'
                ? ' (base à confirmer avec le distributeur)' : ''}
            </span>
          )}
        </section>
      )}

      {alertes.length > 0 && (
        <ul className="m-0 flex list-none flex-col gap-1 p-0" aria-label="Alertes de modification">
          {alertes.map((a) => (
            <li key={`${a.code}-${a.message}`} role="alert"
                className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm">
              {a.message}
              {a.base && <span className="ml-1 text-muted-foreground">({a.base})</span>}
            </li>
          ))}
        </ul>
      )}

      <section aria-label="Pièces du dossier" className="flex flex-col gap-3">
        {piecesParEtape(pieces).map((g) => (
          <div key={g.value} data-etape={g.value}>
            <h5 className="m-0 mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {g.label}
            </h5>
            <ul className="m-0 flex list-none flex-col gap-1 p-0">
              {g.pieces.map((pc) => (
                <li key={pc.code} className="flex flex-wrap items-baseline gap-x-2 text-sm">
                  <span className="text-foreground">{pc.label}</span>
                  {pc.obligatoire && <Badge tone="neutral">Obligatoire</Badge>}
                  {manquantes.includes(pc.code) && <Badge tone="warning">Manquante</Badge>}
                  {pc.statut && <Badge tone="info">{pc.statut.replace(/_/g, ' ')}</Badge>}
                  <span className="text-xs text-muted-foreground">Source : {pc.source}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </section>

      <form noValidate className="flex flex-col gap-3" onSubmit={(e) => e.preventDefault()}>
        <div className="grid gap-3 sm:grid-cols-3">
          {CHAMPS_DATE_DOSSIER.map(([cle, libelle]) => (
            <div key={cle} className="flex flex-col gap-1.5">
              <Label htmlFor={`dossier-${cle}`}>{libelle}</Label>
              <Input id={`dossier-${cle}`} type="date" value={etat[cle]}
                     onChange={(e) => champ(cle)(e.target.value)} />
              {erreurSous(cle)}
            </div>
          ))}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="dossier-etude_conclusion">Conclusion de l'étude</Label>
            <select id="dossier-etude_conclusion" className="form-control"
                    value={etat.etude_conclusion}
                    onChange={(e) => champ('etude_conclusion')(e.target.value)}>
              {CONCLUSIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            {erreurSous('etude_conclusion')}
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="dossier-etude_reglages_imposes">Réglages imposés par l'étude</Label>
            <select id="dossier-etude_reglages_imposes" className="form-control"
                    value={etat.etude_reglages_imposes}
                    onChange={(e) => champ('etude_reglages_imposes')(e.target.value)}>
              {REGLAGES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            {erreurSous('etude_reglages_imposes')}
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="dossier-capacite_etat">Capacité réservée</Label>
            <select id="dossier-capacite_etat" className="form-control"
                    value={etat.capacite_etat}
                    onChange={(e) => champ('capacite_etat')(e.target.value)}>
              {ETATS_CAPACITE.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            {erreurSous('capacite_etat')}
          </div>
        </div>
        {erreurGenerale && <p className="form-error" role="alert">{erreurGenerale}</p>}
        <div>
          <Button type="button" size="sm" loading={busy} onClick={enregistrer}>
            Enregistrer le dossier
          </Button>
        </div>
      </form>

      {/* Dates dérivées par le SERVEUR (décret 2.25.100) : jamais recalculées. */}
      <section aria-label="Échéances du dossier" className="flex flex-col gap-1 text-sm">
        {resume.etude?.paiement_limite_le && (
          <span>Paiement de l'étude avant le {resume.etude.paiement_limite_le}
            <span className="text-muted-foreground"> (décret 2.25.100 art. 13)</span>
          </span>
        )}
        {resume.travaux_limite_le && (
          <span data-testid="echeance-travaux">
            Échéance des travaux : {resume.travaux_limite_le}
            <span className="text-muted-foreground">
              {' '}(accord : art. 14 ; déclaration : art. 8, décret 2.25.100)
            </span>
          </span>
        )}
      </section>

      {equipements.length > 0 && (
        <section aria-label="Équipements figés" className="flex flex-col gap-1 text-sm">
          <h5 className="m-0 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Équipements figés au dépôt
          </h5>
          <ul className="m-0 flex list-none flex-col gap-0.5 p-0">
            {equipements.map((e, i) => (
              <li key={`${e.fabricant}-${e.modele}-${i}`}>
                {e.fabricant} {e.modele} × {e.quantite}
                {e.puissance != null && ` — puissance ${e.puissance}`}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

// La recette se saisit UNE SEULE FOIS, sur la fiche chantier (propriétaire
// unique, CIQ6) : ces trois onglets ne sont plus une seconde saisie.
const RESSOURCES_RECETTE_CHANTIER = ['recettes-mes', 'courbes-iv', 'tests-pr-reception']

export default function DossiersReglementairesPage() {
  const [vue, setVue] = useState('tableau')
  const [ressource, setRessource] = useState(RESSOURCES[0].value)
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  // CHT26 — snapshot STABLE des dossiers (FG268), indépendant de la
  // ressource actuellement choisie dans le Segmented ci-dessous : la
  // ressource PAR DÉFAUT étant déjà `dossiers-reglementaires`, l'effet de
  // montage ci-dessous l'alimente SANS appel réseau supplémentaire.
  const [dossiers, setDossiers] = useState([])
  const [dossiersLoading, setDossiersLoading] = useState(true)
  const [dossiersError, setDossiersError] = useState(false)
  // CIQ638 — dossier dont le détail 82-21 est ouvert (File de travail) ; la
  // version force la ré-ouverture du formulaire depuis la réponse serveur.
  const [detailId, setDetailId] = useState(null)
  const [detailVersion, setDetailVersion] = useState(0)
  // Ignore une réponse devenue obsolète (ressource changée entre-temps) —
  // même rôle que le drapeau `active` d'un effet, partagé entre le montage
  // et `changerRessource`.
  const latestRef = useRef(ressource)

  // Changement de ressource : déclenché par le handler du Segmented (jamais
  // un effet keyé sur `ressource`) — le reset loading/erreur est synchrone
  // mais part d'un gestionnaire d'événement, jamais d'un effet
  // (react-hooks/set-state-in-effect ; même motif que RentabiliteActif.jsx
  // `selectionner`/`charger`, pages/immobilier).
  const changerRessource = (v) => {
    setRessource(v)
    latestRef.current = v
    setLoading(true)
    setError(false)
    ventesApi.getReglementaire(v)
      .then((r) => {
        if (latestRef.current !== v) return
        const data = r.data
        setRows(Array.isArray(data) ? data : (data?.results || []))
      })
      .catch(() => { if (latestRef.current === v) { setRows([]); setError(true) } })
      .finally(() => { if (latestRef.current === v) setLoading(false) })
  }

  // Chargement de la ressource par défaut au montage : `loading`/`error`
  // démarrent déjà à leurs valeurs de chargement (true/false, comme
  // PatrimoineTree.jsx) — aucun reset synchrone n'est donc nécessaire ici ;
  // les changements ultérieurs passent par `changerRessource` ci-dessus.
  useEffect(() => {
    const v = RESSOURCES[0].value
    ventesApi.getReglementaire(v)
      .then((r) => {
        if (latestRef.current !== v) return
        const data = r.data
        const liste = Array.isArray(data) ? data : (data?.results || [])
        setRows(liste)
        // CHT26 — `v` est déjà `dossiers-reglementaires` : même réponse,
        // capturée à part pour la File de travail (voir le commentaire
        // sur `dossiers` plus haut).
        setDossiers(liste)
        setDossiersError(false)
      })
      .catch(() => {
        if (latestRef.current === v) {
          setRows([]); setError(true)
          setDossiers([]); setDossiersError(true)
        }
      })
      .finally(() => {
        if (latestRef.current === v) { setLoading(false); setDossiersLoading(false) }
      })
  }, [])

  /* ── WIR224 — Panneau « Échéances à venir » ────────────────────────────
     Même discipline que `changerRessource` ci-dessus : le rechargement part
     d'un GESTIONNAIRE D'ÉVÉNEMENT (jamais d'un effet keyé sur le filtre), et
     un `latestFiltreRef` ignore une réponse devenue obsolète. */
  const [echeances, setEcheances] = useState([])
  // Compteurs de la vue NON filtrée : le serveur ne résume que les lignes
  // qu'il renvoie, donc filtrer écraserait les compteurs par des 0 — ils sont
  // conservés à part et ne bougent qu'au chargement complet.
  const [resume, setResume] = useState(null)
  const [filtreAlerte, setFiltreAlerte] = useState(null)
  const [calLoading, setCalLoading] = useState(true)
  const [calError, setCalError] = useState(false)
  const latestFiltreRef = useRef(null)
  // CHT26 — TOUTES les échéances (jamais tronquées par le filtre d'alerte
  // ci-dessus) : la File de travail en a besoin pour classer CHAQUE dossier
  // par urgence, quel que soit le filtre actif dans le panneau au-dessus.
  const [echeancesToutes, setEcheancesToutes] = useState([])

  const chargerCalendrier = (statut) => {
    latestFiltreRef.current = statut
    const params = statut ? { statut } : undefined
    return ventesApi.getCalendrierReglementaire(params)
      .then((r) => {
        if (latestFiltreRef.current !== statut) return
        setEcheances(r.data?.echeances ?? [])
        // Seule la vue COMPLÈTE fait autorité pour les compteurs.
        if (!statut) {
          setResume(r.data?.resume ?? null)
          setEcheancesToutes(r.data?.echeances ?? [])
        }
        setCalError(false)
      })
      .catch(() => {
        if (latestFiltreRef.current !== statut) return
        setEcheances([])
        setCalError(true)
      })
      .finally(() => { if (latestFiltreRef.current === statut) setCalLoading(false) })
  }

  const changerFiltreAlerte = (statut) => {
    const cible = filtreAlerte === statut ? null : statut
    setFiltreAlerte(cible)
    setCalLoading(true)
    chargerCalendrier(cible)
  }

  useEffect(() => { chargerCalendrier(null) }, [])

  // Colonnes dérivées des données réelles (jamais d'un schéma deviné).
  const colonnes = useMemo(() => {
    if (rows.length === 0) return []
    const dispo = Object.keys(rows[0]).filter((k) => estAffichable(rows[0][k]))
    const choisies = COLONNES_PREFEREES.filter((k) => dispo.includes(k))
    return choisies.length > 0 ? choisies : dispo.slice(0, 5)
  }, [rows])

  const courante = RESSOURCES.find((r) => r.value === ressource)

  // CHT26 — dossiers groupés par statut (les 7 canoniques), triés par
  // urgence au sein de chaque groupe (le plus urgent d'abord, puis la date
  // d'échéance croissante, puis les dossiers sans échéance en dernier).
  const dossiersParStatut = useMemo(() => {
    const groupes = Object.fromEntries(STATUTS_DOSSIER.map((s) => [s.value, []]))
    for (const d of dossiers) {
      if (groupes[d.statut]) groupes[d.statut].push(d)
    }
    for (const cle of Object.keys(groupes)) {
      groupes[cle] = [...groupes[cle]].sort((a, b) => {
        const ua = urgenceDossier(a.id, echeancesToutes)
        const ub = urgenceDossier(b.id, echeancesToutes)
        const ra = ua ? ua.rang : 3
        const rb = ub ? ub.rang : 3
        if (ra !== rb) return ra - rb
        if (ua?.date_echeance && ub?.date_echeance) {
          return ua.date_echeance < ub.date_echeance ? -1
            : ua.date_echeance > ub.date_echeance ? 1 : 0
        }
        if (ua?.date_echeance) return -1
        if (ub?.date_echeance) return 1
        return 0
      })
    }
    return groupes
  }, [dossiers, echeancesToutes])

  const dossierEnregistre = (maj) => {
    if (!maj?.id) return
    setDossiers((prev) => prev.map((d) => (d.id === maj.id ? { ...d, ...maj } : d)))
    setRows((prev) => (ressource === 'dossiers-reglementaires'
      ? prev.map((d) => (d.id === maj.id ? { ...d, ...maj } : d)) : prev))
    setDetailVersion((v) => v + 1)
  }

  const ouvrirDossierDansLeTableau = () => {
    setVue('tableau')
    changerRessource('dossiers-reglementaires')
  }

  return (
    <div className="page">
      <PageHeader
        title="Dossiers réglementaires & mise en service"
        subtitle="Dossiers de raccordement, checklists, échanges opérateur, subventions, régularisation 82-21, recette IEC 62446, courbes I-V, packs as-built et attestations."
      />

      <Segmented
        options={VUES}
        value={vue}
        onChange={setVue}
        aria-label="Vue des dossiers réglementaires"
        className="mb-4"
      />

      {/* ── WIR224/FG273 — Échéances à venir (alertes d'expiration) ──────── */}
      <Card className="mb-4">
        <CardContent>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="m-0 text-base font-semibold text-foreground">
              Échéances à venir
            </h2>
            <div role="group" aria-label="Filtrer par statut d’alerte"
                 className="flex flex-wrap items-center gap-1.5">
              {STATUTS_ALERTE.map((s) => (
                <Button
                  key={s.value}
                  type="button" size="sm"
                  variant={filtreAlerte === s.value ? 'default' : 'outline'}
                  aria-pressed={filtreAlerte === s.value}
                  onClick={() => changerFiltreAlerte(s.value)}
                >
                  {s.label}
                  <Badge tone={s.tone} className="ml-1.5">
                    {resume?.[s.value] ?? 0}
                  </Badge>
                </Button>
              ))}
              {filtreAlerte && (
                <Button type="button" size="sm" variant="ghost"
                        onClick={() => changerFiltreAlerte(filtreAlerte)}>
                  Tout afficher
                </Button>
              )}
            </div>
          </div>

          {calLoading && <Skeleton className="h-20" />}
          {!calLoading && calError && (
            <EmptyState
              title="Calendrier indisponible"
              description="Les échéances réglementaires n’ont pas pu être chargées."
            />
          )}
          {!calLoading && !calError && echeances.length === 0 && (
            <EmptyState
              title="Aucune échéance"
              description={filtreAlerte
                ? `Aucune échéance « ${LIBELLE_ALERTE[filtreAlerte]} » pour votre société.`
                : 'Aucune échéance réglementaire suivie pour votre société.'}
            />
          )}
          {!calLoading && !calError && echeances.length > 0 && (
            <ul className="m-0 flex list-none flex-col gap-1.5 p-0"
                aria-label="Échéances réglementaires">
              {echeances.map((e) => (
                <li
                  key={`${e.type}-${e.dossier_id}-${e.date_echeance}-${e.libelle}`}
                  data-statut={e.statut_alerte}
                  className={`flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded-lg border px-3 py-2 text-sm ${
                    e.statut_alerte === 'expire'
                      ? 'border-destructive/40 bg-destructive/10'
                      : 'border-border'
                  }`}
                >
                  <Badge tone={TON_ALERTE[e.statut_alerte] ?? 'neutral'}>
                    {LIBELLE_ALERTE[e.statut_alerte] ?? e.statut_alerte}
                  </Badge>
                  <span className="font-medium text-foreground">{e.libelle}</span>
                  <span className="tabular-nums text-muted-foreground">
                    {e.date_echeance}
                  </span>
                  <span className="text-muted-foreground">
                    {renduJours(e.jours_restants)}
                  </span>
                  {e.relance_due && (
                    <Badge tone="warning">Relance due</Badge>
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {vue === 'tableau' && (
        <>
          <Segmented
            options={RESSOURCES.map((r) => ({ value: r.value, label: r.label }))}
            value={ressource}
            onChange={changerRessource}
            aria-label="Ressource réglementaire"
          />

          {RESSOURCES_RECETTE_CHANTIER.includes(ressource) && (
            <p className="mt-4 text-sm text-muted-foreground" data-testid="recette-sur-chantier">
              La recette de ce chantier se saisit sur la fiche chantier.{' '}
              <Link to={`/chantiers${rows.find((r) => r.chantier)
                ? `?id=${rows.find((r) => r.chantier).chantier}` : ''}`}
                    className="underline">
                Ouvrir la fiche chantier
              </Link>
            </p>
          )}

          <Card className="mt-4">
            <CardContent className="p-0">
              {loading && <Skeleton className="m-4 h-24" />}
              {!loading && error && (
                <EmptyState
                  title="Chargement impossible"
                  description={`La ressource « ${courante?.label} » n'a pas pu être chargée.`}
                />
              )}
              {!loading && !error && rows.length === 0 && (
                <EmptyState
                  title="Aucun élément"
                  description={`Aucun enregistrement « ${courante?.label} » (${courante?.tag}) pour votre société.`}
                />
              )}
              {!loading && !error && rows.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-sm"
                    aria-label={`Liste ${courante?.label}`}>
                    <thead>
                      <tr className="border-b border-border">
                        {colonnes.map((c) => (
                          <th key={c} scope="col"
                            className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            {c.replace(/_/g, ' ')}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row, i) => (
                        <tr key={row.id ?? i} className="border-b border-border/60 last:border-b-0">
                          {colonnes.map((c) => (
                            <td key={c} className="px-3 py-2 text-foreground">
                              {rendu(row[c])}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {/* ── CHT26 — File de travail : dossiers groupés par statut, triés par
           urgence ─────────────────────────────────────────────────────── */}
      {vue === 'file' && (
        <div className="mt-4 flex flex-col gap-4"
             aria-label="File de travail des dossiers réglementaires">
          {dossiersLoading && <Skeleton className="h-24" />}
          {!dossiersLoading && dossiersError && (
            <EmptyState
              title="File de travail indisponible"
              description="Les dossiers réglementaires n’ont pas pu être chargés."
            />
          )}
          {!dossiersLoading && !dossiersError && STATUTS_DOSSIER.map((s) => {
            const groupe = dossiersParStatut[s.value] || []
            return (
              <Card key={s.value} data-statut-groupe={s.value}>
                <CardContent>
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <h3 className="m-0 text-sm font-semibold text-foreground">
                      {s.label}
                    </h3>
                    <Badge tone="neutral">{groupe.length}</Badge>
                  </div>
                  {groupe.length === 0 ? (
                    <p className="m-0 text-sm text-muted-foreground">
                      Aucun dossier.
                    </p>
                  ) : (
                    <ul className="m-0 flex list-none flex-col gap-1.5 p-0"
                        aria-label={`Dossiers — ${s.label}`}>
                      {groupe.map((d) => {
                        const urg = urgenceDossier(d.id, echeancesToutes)
                        return (
                          <li key={d.id} data-dossier-id={d.id}
                            className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-border px-3 py-2 text-sm">
                            {urg && (
                              <Badge tone={TON_ALERTE[urg.statut_alerte] ?? 'neutral'}>
                                {LIBELLE_ALERTE[urg.statut_alerte] ?? urg.statut_alerte}
                              </Badge>
                            )}
                            <span className="font-medium text-foreground">
                              {d.reference_dossier || `Devis ${d.devis}`}
                            </span>
                            {urg && (
                              <span className="text-muted-foreground">
                                {urg.libelle} — {urg.date_echeance}
                              </span>
                            )}
                            <Button type="button" size="sm" variant="ghost"
                                    onClick={ouvrirDossierDansLeTableau}>
                              Voir le dossier
                            </Button>
                            <Button type="button" size="sm" variant="ghost"
                                    aria-expanded={detailId === d.id}
                                    onClick={() => setDetailId(detailId === d.id ? null : d.id)}>
                              Détail 82-21
                            </Button>
                            {d.chantier && (
                              <Link to={`/chantiers?id=${d.chantier}`}
                                    className="text-sm underline">
                                Voir le chantier
                              </Link>
                            )}
                            {detailId === d.id && (
                              <DossierDetail82
                                key={`${d.id}-${detailVersion}`}
                                dossier={d}
                                onSaved={dossierEnregistre}
                                onClose={() => setDetailId(null)}
                              />
                            )}
                          </li>
                        )
                      })}
                    </ul>
                  )}
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
