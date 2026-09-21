import { AlertTriangle, Eye } from 'lucide-react'

/* ============================================================================
   ANALYT1 — Panneau « Lecture par le client » de la fiche devis.
   ----------------------------------------------------------------------------
   SOLMVP41 — le suivi marketing (`marketing.OuverturePartage` « vu le … » +
   `marketing.RelanceDevisAbandonne`, via `ventesApi.getSuiviPartageDevis`)
   est parti avec l'app marketing (Groupe SOLMVP) : son endpoint
   `/ventes/devis/{id}/suivi-partage/` n'existe plus côté serveur. Seule reste
   la lecture ANALYT1 ci-dessous (`ventesApi.getLectureClientDevis`,
   `/ventes/devis/{id}/lecture-client/`, endpoint intact) : visites par
   section de la proposition web, aucun montant/coût/marge rendu ici.
   ========================================================================== */

// ANALYT1 (audit item 64, 26/08/2026) — libellés FR des sections suivies sur
// la proposition web, miroir de `ENGAGEMENT_SECTION_LABELS` côté serveur
// (apps/ventes/public_views.py) ET de `ENGAGEMENT_LABELS` (DevisList.jsx —
// résumé temps/section, surface DISTINCTE et non gardée par rôle).
// (le miroir est verifie par les tests du panneau — pas de marqueur source-choix :
// la constante serveur est un dict de libelles, pas une liste de valeurs que la
// garde check_choices_declares sait parser ; revue Fable B3, 26/08/2026)
const LECTURE_CLIENT_SECTION_LABELS = {
  hero: 'accueil', prix: 'prix', etude: 'étude', garanties: 'garanties',
  signature: 'signature', tailles: 'tailles (Éco/Recommandé/Max)',
  options: 'options', graphs: 'production', economies: 'économies',
  calepinage: 'calepinage 3D', sld: 'schéma électrique',
}

/**
 * ANALYT1 — bloc « Lecture par le client » : visites DISTINCTES par section
 * de la proposition en ligne + l'alerte de friction (section relue au-delà
 * du seuil). Analytics INTERNES UNIQUEMENT — jamais un chiffre montré au
 * client, jamais une promesse de conversion (aucun taux affiché). `null`/
 * absent (rôle non responsable/admin, aucun beacon reçu) ⇒ rendu strictement
 * inchangé : ce bloc entier ne s'affiche pas.
 */
function LectureClientBlock({ lectureClient }) {
  const sections = lectureClient?.sections || {}
  const entries = Object.entries(sections)
    .filter(([, v]) => (v?.visits || 0) > 0 || (v?.seconds || 0) > 0)
    .sort((a, b) => (b[1]?.visits || 0) - (a[1]?.visits || 0))
  const friction = lectureClient?.friction || null

  if (entries.length === 0 && !friction) return null

  return (
    <div className="flex items-start gap-2">
      <Eye className="mt-0.5 size-3.5 text-muted-foreground" aria-hidden="true" />
      <div className="min-w-0">
        <p className="text-xs font-medium text-muted-foreground">
          Lecture par le client
        </p>
        {entries.length > 0 && (
          <ul className="mt-1 space-y-0.5 text-sm text-muted-foreground">
            {entries.map(([key, v]) => (
              <li key={key}>
                {LECTURE_CLIENT_SECTION_LABELS[key] || key}
                {v.visits > 1
                  ? ` — relu ${v.visits}×`
                  : v.visits === 1 ? ' — 1 visite' : ' — consulté'}
              </li>
            ))}
          </ul>
        )}
        {friction && (
          <p className="mt-1 flex items-start gap-1 text-sm font-medium text-warning">
            <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            Signal de friction — section «{' '}
            {LECTURE_CLIENT_SECTION_LABELS[friction.section] || friction.section}
            {' »'} relue plusieurs fois : un appel peut débloquer la décision.
          </p>
        )}
      </div>
    </div>
  )
}

export default function DevisSuiviPartagePanel({ lectureClient }) {
  return <LectureClientBlock lectureClient={lectureClient} />
}
