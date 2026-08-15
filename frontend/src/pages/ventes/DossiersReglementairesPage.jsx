import { useEffect, useMemo, useRef, useState } from 'react'
import ventesApi from '../../api/ventesApi'
import PageHeader from '../../components/layout/PageHeader'
import { Badge, Card, CardContent, EmptyState, Segmented, Skeleton } from '../../ui'
import { formatDate, formatDateTime } from '../../lib/format'

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

/* ── WIR224 / FG273 — Panneau « Échéances à venir » ──────────────────────────
   `GET /ventes/calendrier-reglementaire/` calculait déjà tout (statut d'alerte
   par échéance + résumé), et `getCalendrierReglementaire` était wrappé… mais
   AUCUN écran ne l'appelait : les alertes d'expiration n'étaient jamais rendues.
   Ce panneau est ce consommateur.

   Le statut vient à 100 % du SERVEUR (`statut_alerte`) : rien n'est recalculé
   ici à partir des dates — sinon l'écran et le serveur pourraient diverger sur
   le seuil « imminent » (paramétrable par `?seuil=`). Cliquer un compteur
   RECHARGE depuis le serveur avec `?statut=…` (le filtrage aussi est serveur),
   jamais un filtre local sur une liste déjà réduite. */
const ALERTES = [
  { cle: 'expire', label: 'Expiré', tone: 'destructive' },
  { cle: 'imminent', label: 'Imminent', tone: 'warning' },
  { cle: 'a_venir', label: 'À venir', tone: 'info' },
]

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

  /* ── WIR224 — état du panneau d'échéances (indépendant de la ressource
     affichée en dessous : c'est une vue transverse). ── */
  const [calendrier, setCalendrier] = useState(null)
  const [calLoading, setCalLoading] = useState(true)
  const [calError, setCalError] = useState(false)
  const [calStatut, setCalStatut] = useState(null) // null = tout
  // Le RÉSUMÉ vient du serveur. Sous filtre, le serveur ne résume que les
  // lignes filtrées : on retient donc le dernier résumé NON filtré pour que
  // les compteurs ne se vident pas sous le doigt de l'utilisateur.
  const [resume, setResume] = useState(null)
  const calRef = useRef(null)

  const chargerCalendrier = (statut) => {
    calRef.current = statut ?? null
    setCalLoading(true)
    setCalError(false)
    ventesApi.getCalendrierReglementaire(statut ? { statut } : undefined)
      .then((r) => {
        if (calRef.current !== (statut ?? null)) return
        setCalendrier(r.data || null)
        if (!statut && r.data?.resume) setResume(r.data.resume)
      })
      .catch(() => {
        if (calRef.current !== (statut ?? null)) return
        setCalendrier(null)
        setCalError(true)
      })
      .finally(() => {
        if (calRef.current === (statut ?? null)) setCalLoading(false)
      })
  }

  useEffect(() => {
    // Chargement initial du calendrier (aucun filtre) — même patron que le
    // chargement de la ressource par défaut ci-dessus : pas de reset d'état
    // synchrone dans l'effet, les changements passent par le handler.
    ventesApi.getCalendrierReglementaire()
      .then((r) => {
        if (calRef.current !== null) return
        setCalendrier(r.data || null)
        if (r.data?.resume) setResume(r.data.resume)
      })
      .catch(() => { if (calRef.current === null) setCalError(true) })
      .finally(() => { if (calRef.current === null) setCalLoading(false) })
  }, [])

  // Le compteur cliqué RECHARGE du serveur ; re-cliquer le même compteur
  // enlève le filtre (aucun état « filtré sur rien » possible).
  const basculerFiltreAlerte = (cle) => {
    const suivant = calStatut === cle ? null : cle
    setCalStatut(suivant)
    chargerCalendrier(suivant)
  }

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

      {/* ── WIR224 / FG273 — Échéances à venir (alertes d'expiration) ── */}
      <Card className="mt-4" data-testid="calendrier-reglementaire">
        <CardContent>
          <h2 className="text-base font-semibold text-foreground">Échéances à venir</h2>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Pièces datées, dépôts en instruction et validité des accords de raccordement.
            Les statuts sont calculés par le serveur.
          </p>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            {ALERTES.map(({ cle, label, tone }) => (
              <button
                key={cle}
                type="button"
                data-testid={`alerte-${cle}`}
                aria-pressed={calStatut === cle}
                onClick={() => basculerFiltreAlerte(cle)}
                className={`inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition-colors ${
                  calStatut === cle ? 'border-primary bg-primary/10' : 'border-border hover:bg-muted'
                }`}
              >
                <Badge tone={tone}>{label}</Badge>
                <span className="tabular-nums font-semibold">{resume?.[cle] ?? 0}</span>
              </button>
            ))}
            {calStatut && (
              <button
                type="button"
                onClick={() => basculerFiltreAlerte(calStatut)}
                className="text-sm text-muted-foreground underline underline-offset-2"
              >
                Tout afficher
              </button>
            )}
          </div>

          {calLoading && <Skeleton className="mt-3 h-16" />}
          {!calLoading && calError && (
            <p className="mt-3 text-sm text-muted-foreground" role="alert">
              Le calendrier réglementaire n&apos;a pas pu être chargé.
            </p>
          )}
          {!calLoading && !calError && (calendrier?.echeances ?? []).length === 0 && (
            <p className="mt-3 text-sm text-muted-foreground">
              Aucune échéance {calStatut ? `« ${ALERTES.find((a) => a.cle === calStatut)?.label} »` : ''} à ce jour.
            </p>
          )}
          {!calLoading && !calError && (calendrier?.echeances ?? []).length > 0 && (
            <ul className="mt-3 divide-y divide-border/60">
              {calendrier.echeances.map((e, i) => {
                const meta = ALERTES.find((a) => a.cle === e.statut_alerte)
                return (
                  <li key={`${e.type}-${e.dossier_id}-${i}`}
                      className="flex flex-wrap items-center gap-2 py-2 text-sm">
                    <Badge tone={meta?.tone ?? 'neutral'}>{meta?.label ?? e.statut_alerte}</Badge>
                    <span className="flex-1 text-foreground">{e.libelle}</span>
                    <span className="tabular-nums text-muted-foreground">
                      {formatDate(e.date_echeance)}
                    </span>
                    {typeof e.jours_restants === 'number' && (
                      <span className="tabular-nums text-xs text-muted-foreground">
                        {e.jours_restants < 0
                          ? `en retard de ${Math.abs(e.jours_restants)} j`
                          : `dans ${e.jours_restants} j`}
                      </span>
                    )}
                  </li>
                )
              })}
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
