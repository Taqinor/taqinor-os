import { useEffect, useMemo, useRef, useState } from 'react'
import ventesApi from '../../api/ventesApi'
import PageHeader from '../../components/layout/PageHeader'
import { Card, CardContent, EmptyState, Segmented, Skeleton } from '../../ui'
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
