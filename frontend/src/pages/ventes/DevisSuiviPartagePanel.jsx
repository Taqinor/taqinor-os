import { AlertTriangle, Eye, Send } from 'lucide-react'
import { formatDateTime } from '../../lib/format'

/* ============================================================================
   WIR96 — Panneau « Suivi du partage » de la fiche devis.
   ----------------------------------------------------------------------------
   Rend les deux traces marketing qui étaient jusqu'ici écrites nulle part et
   affichées nulle part :
     - `marketing.OuverturePartage` : « vu le JJ/MM à HH:MM » + nombre
       d'ouvertures du lien de proposition ;
     - `marketing.RelanceDevisAbandonne` : la liste des relances consignées.
   Données lues via `ventesApi.getSuiviPartageDevis` (agrégat serveur borné
   société). Aucun montant, aucun coût, aucune marge n'est rendu ici.
   ========================================================================== */

// ANALYT1 (audit item 64, 26/08/2026) — libellés FR des sections suivies sur
// la proposition web, miroir de `ENGAGEMENT_SECTION_LABELS` côté serveur
// (apps/ventes/public_views.py) ET de `ENGAGEMENT_LABELS` (DevisList.jsx —
// résumé temps/section, surface DISTINCTE et non gardée par rôle).
// source-choix: ventes.public_views.ENGAGEMENT_SECTION_LABELS
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

export default function DevisSuiviPartagePanel({ data, loading, lectureClient }) {
  if (loading) {
    return <p className="text-xs text-muted-foreground">Chargement…</p>
  }

  const ouverture = data?.ouverture || null
  const relances = data?.relances || []

  return (
    <div className="space-y-3">
      <div className="flex items-start gap-2">
        <Eye className="mt-0.5 size-3.5 text-muted-foreground" aria-hidden="true" />
        {ouverture ? (
          <p className="text-sm">
            Vu le{' '}
            <strong>
              {ouverture.premier_vu_le ? formatDateTime(ouverture.premier_vu_le) : '—'}
            </strong>
            {ouverture.dernier_vu_le
              && ouverture.dernier_vu_le !== ouverture.premier_vu_le && (
              <>
                {' · dernière consultation '}
                {formatDateTime(ouverture.dernier_vu_le)}
              </>
            )}
            {' · '}
            {ouverture.nb_ouvertures} ouverture{ouverture.nb_ouvertures > 1 ? 's' : ''}
          </p>
        ) : (
          <p className="text-sm text-muted-foreground">
            Lien de proposition jamais ouvert.
          </p>
        )}
      </div>

      <div className="flex items-start gap-2">
        <Send className="mt-0.5 size-3.5 text-muted-foreground" aria-hidden="true" />
        <div className="min-w-0">
          <p className="text-xs font-medium text-muted-foreground">
            Relances consignées
          </p>
          {relances.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucune relance consignée.</p>
          ) : (
            <ul className="mt-1 space-y-1 text-sm">
              {relances.map((r) => (
                <li key={r.id} className="flex flex-wrap items-baseline gap-x-2">
                  <span className="text-xs text-muted-foreground">
                    {r.date_relance ? formatDateTime(r.date_relance) : '—'}
                  </span>
                  <span>
                    {r.canal || 'canal inconnu'}
                    {r.jours_sans_reponse
                      ? ` · ${r.jours_sans_reponse} j sans réponse`
                      : ''}
                  </span>
                  {r.note && (
                    <span className="text-xs text-muted-foreground">{r.note}</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <LectureClientBlock lectureClient={lectureClient} />
    </div>
  )
}
