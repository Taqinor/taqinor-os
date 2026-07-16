import { useEffect, useState } from 'react'
import crmApi from '../../../api/crmApi'
import { Badge, Button, Spinner } from '../../../ui'
import { ResponsiveDialog } from '../../../ui/ResponsiveDialog'
import { formatDateTime, formatMAD } from '../../../lib/format'

// WR9 — fiche « Parcours » d'un lead (lecture seule) :
//  - FG204 : timeline multi-touch (points de contact + attribution
//    first-touch / last-touch + coût total) ;
//  - FG38  : correspondance avec un Client existant (retour client).
// Les données viennent des endpoints scopés société — aucun calcul local.

const fmtDateTime = (iso) => formatDateTime(iso)

const fmtMAD = (v) => formatMAD(v)

export default function LeadInsightsDialog({ lead, onClose }) {
  const [touches, setTouches] = useState(null)
  const [matches, setMatches] = useState(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let alive = true
    Promise.all([
      crmApi.getLeadPointsContact(lead.id),
      crmApi.getLeadClientMatch(lead.id),
    ])
      .then(([t, m]) => {
        if (!alive) return
        setTouches(t.data)
        setMatches(Array.isArray(m.data) ? m.data : [])
      })
      .catch(() => { if (alive) setError(true) })
    return () => { alive = false }
  }, [lead.id])

  const loading = !error && (touches == null || matches == null)

  return (
    // VX182 — shell fait-main remplacé par ResponsiveDialog (Escape + focus-
    // trap + bottom-sheet mobile) ; en-tête/pied conservés à l'identique.
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Parcours du lead — {lead.nom ?? '—'}</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
        <div className="modal-body">
          {loading && (
            <p className="page-loading"><Spinner /> Chargement du parcours…</p>
          )}
          {error && (
            <p className="page-error">
              Impossible de charger le parcours — réessayez.
            </p>
          )}

          {matches != null && matches.length > 0 && (
            <section className="mb-4" data-testid="lead-client-match">
              <h4 className="font-medium mb-2">Client existant détecté</h4>
              <p className="mb-2 text-xs text-muted-foreground">
                Ce lead correspond à un client déjà connu (même téléphone ou
                email) — probablement un retour client.
              </p>
              <ul className="flex flex-col gap-1.5">
                {matches.map((c) => (
                  <li key={c.id}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border p-2 text-sm">
                    <span className="font-medium">{c.nom}</span>
                    <span className="text-xs text-muted-foreground">
                      {c.nb_devis} devis · {c.nb_chantiers} chantier(s)
                      {c.email ? ` · ${c.email}` : ''}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {touches != null && (
            <section data-testid="lead-touchpoints">
              <h4 className="font-medium mb-2">
                Points de contact <span className="count-badge">{touches.count}</span>
              </h4>
              {touches.count === 0 ? (
                <p className="text-muted-foreground">
                  Aucun point de contact enregistré pour ce lead.
                </p>
              ) : (
                <>
                  <p className="mb-2 text-xs text-muted-foreground">
                    Premier contact : {touches.first_touch?.canal_libelle
                      ?? touches.first_touch?.canal ?? '—'}
                    {' · '}Dernier : {touches.last_touch?.canal_libelle
                      ?? touches.last_touch?.canal ?? '—'}
                    {touches.cout_total != null
                      ? ` · Coût total : ${fmtMAD(touches.cout_total)}` : ''}
                  </p>
                  <ul className="flex flex-col gap-1.5">
                    {(touches.timeline ?? []).map((p) => (
                      <li key={p.id}
                          className="rounded-lg border border-border p-2 text-sm">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="flex items-center gap-1.5 font-medium">
                            <Badge tone="neutral">{p.canal_libelle ?? p.canal}</Badge>
                            {p.source || ''}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {fmtDateTime(p.date_contact)}
                          </span>
                        </div>
                        {p.detail && (
                          <p className="mt-1 text-xs text-muted-foreground">{p.detail}</p>
                        )}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </section>
          )}
        </div>
        <div className="modal-footer">
          <Button onClick={onClose}>Fermer</Button>
        </div>
    </ResponsiveDialog>
  )
}
