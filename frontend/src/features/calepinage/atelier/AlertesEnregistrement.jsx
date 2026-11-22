import {
  MESSAGE_DEROGATION_RESERVEE, texteBloquant,
} from '../refusDevis'

/* Coque (22/11) — les ALERTES D'ENREGISTREMENT de l'atelier, DÉPLACÉES VERBATIM depuis
   pages/ventes/ToitureDesign.jsx (move only) : refus électrique de la resynchro du devis
   (`cal-sync-bloquants`, « Passer outre »), conception modifiée ailleurs (`cal-document-modifie`),
   révision possible (`pv21-reviser`) et devis figé (`cal-conflit-lecture-seule`). Textes du SERVEUR. */
export default function AlertesEnregistrement({
  bloquageSync, motifDerogation, setMotifDerogation, motifDerogationErreur, setMotifDerogationErreur,
  passerOutreSync, sending, documentModifie, rechargerAtelier, conflit, devisId, reviser, devisReference,
}) {
  return (
    <>
          {/* Lot 2 critique #29 — refus ÉLECTRIQUE de la resynchro du devis :
              les bloquants du serveur, mot pour mot ; « Passer outre »
              seulement pour un approbateur (droit SERVI par le détail). */}
          {bloquageSync?.bloquants && (
            <div className="mt-4 border border-alert-300/40 p-4" data-testid="cal-sync-bloquants">
              <ul className="space-y-1 text-sm text-destructive">
                {bloquageSync.bloquants.map((b, i) => (
                  <li key={`${b?.code ?? 'b'}-${i}`} data-testid="cal-sync-bloquant">
                    {texteBloquant(b)}
                    {b?.detail && <span className="block text-xs text-muted-foreground">{b.detail}</span>}
                  </li>
                ))}
              </ul>
              {bloquageSync.derogationPossible && (bloquageSync.peutDeroger ? (
                <div className="mt-3 space-y-2">
                  <label className="block text-xs text-foreground" htmlFor="cal-sync-motif">
                    Motif de la dérogation
                  </label>
                  <textarea
                    id="cal-sync-motif"
                    value={motifDerogation}
                    onChange={(e) => { setMotifDerogation(e.target.value); setMotifDerogationErreur(null) }}
                    data-testid="cal-sync-motif"
                    className="w-full border border-border bg-transparent p-2 text-sm"
                  />
                  {motifDerogationErreur && (
                    <p className="text-xs text-destructive" role="alert" data-testid="cal-sync-motif-erreur">
                      {motifDerogationErreur}
                    </p>
                  )}
                  <button type="button" onClick={passerOutreSync} disabled={sending}
                    data-testid="cal-sync-passer-outre"
                    className="inline-flex items-center gap-2 border border-alert-300 px-4 py-2 text-sm font-bold text-destructive disabled:cursor-not-allowed disabled:opacity-60">
                    Passer outre et resynchroniser
                  </button>
                </div>
              ) : (
                <p className="mt-2 text-xs text-muted-foreground" data-testid="cal-sync-derogation-reservee">
                  {MESSAGE_DEROGATION_RESERVEE}
                </p>
              ))}
            </div>
          )}

          {/* ACAL23 — 409 `document_modifie` : modifiée AILLEURS, rien n'est
              écrasé ; distinct du verrou ci-dessous. */}
          {documentModifie && (
            <div className="mt-4 border border-brass-400/40 p-4" data-testid="cal-document-modifie">
              <p className="text-sm text-primary-text" role="alert">
                La conception a été modifiée ailleurs (onglet, autre navigateur) — rechargez avant
                d’enregistrer.
              </p>
              <p className="mt-1 text-xs text-foreground">{documentModifie.detail}</p>
              <button type="button" onClick={rechargerAtelier}
                className="mt-3 inline-flex items-center border border-brass-400/60 px-4 py-2 text-sm font-semibold text-primary-text"
                data-testid="cal-document-modifie-recharger">
                Recharger
              </button>
            </div>
          )}

          {/* ACAL37 — 409 RÉVISABLE de la resynchronisation du devis : le bon
              geste est une NOUVELLE version (même `reviserEtOuvrir`). */}
          {conflit?.revision_possible && devisId && (
            <div className="mt-4 border border-brass-400/40 p-4" data-testid="pv21-reviser">
              <p className="text-sm text-foreground" role="status">{conflit.detail}</p>
              <button type="button" onClick={() => reviser(devisId, devisReference)} disabled={sending}
                className="mt-3 inline-flex items-center gap-2 border border-brass-400 px-5 py-3 text-base font-bold text-primary-text disabled:cursor-not-allowed disabled:opacity-60">
                Réviser (v2)
              </button>
            </div>
          )}

          {/* 409 : le devis lié est figé (accepté, refusé, expiré ou remplacé) — motif du SERVEUR. */}
          {conflit && !conflit.revision_possible && (
            <div className="mt-4 border border-alert-300/40 p-4" data-testid="cal-conflit-lecture-seule">
              <p className="text-xs font-semibold uppercase tracking-wide text-destructive">Lecture seule</p>
              <p className="mt-2 text-sm text-destructive" role="alert">{conflit.detail}</p>
            </div>
          )}
    </>
  )
}
