import { useEffect, useMemo, useRef, useState } from 'react'
import ventesApi from '../../api/ventesApi'
import PageHeader from '../../components/layout/PageHeader'
import { Badge, Button, Card, CardContent, EmptyState, Segmented, Skeleton } from '../../ui'
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

export default function DossiersReglementairesPage() {
  const [ressource, setRessource] = useState(RESSOURCES[0].value)
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
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
        setRows(Array.isArray(data) ? data : (data?.results || []))
      })
      .catch(() => { if (latestRef.current === v) { setRows([]); setError(true) } })
      .finally(() => { if (latestRef.current === v) setLoading(false) })
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

  const chargerCalendrier = (statut) => {
    latestFiltreRef.current = statut
    const params = statut ? { statut } : undefined
    return ventesApi.getCalendrierReglementaire(params)
      .then((r) => {
        if (latestFiltreRef.current !== statut) return
        setEcheances(r.data?.echeances ?? [])
        // Seule la vue COMPLÈTE fait autorité pour les compteurs.
        if (!statut) setResume(r.data?.resume ?? null)
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

  return (
    <div className="page">
      <PageHeader
        title="Dossiers réglementaires & mise en service"
        subtitle="Dossiers de raccordement, checklists, échanges opérateur, subventions, régularisation 82-21, recette IEC 62446, courbes I-V, packs as-built et attestations."
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

      <Segmented
        options={RESSOURCES.map((r) => ({ value: r.value, label: r.label }))}
        value={ressource}
        onChange={changerRessource}
        aria-label="Ressource réglementaire"
      />

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
    </div>
  )
}
