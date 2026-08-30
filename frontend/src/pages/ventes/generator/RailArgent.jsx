// QJR100 — LE RAIL D'ARGENT du générateur, extrait VERBATIM de
// `DevisGenerator.jsx` (ex-région « chaîne de totaux » sous la table).
// ---------------------------------------------------------------------------
// Il rend LA CHAÎNE D'ARGENT de l'écran, dans son ordre hiérarchisé VX138 :
//   brut (tier-1) → remise / TVA (tier-2) → totaux finaux (tier-3)
//   → prix par kWc vs prix cible → marge indicative (INTERNE).
//
// RÈGLE FONDATEUR PRÉSERVÉE VERBATIM : les trois `<input type="number">`
// déplacés ici (remise, TVA, prix cible) gardent `step="any"` — aucune valeur
// tapée n'est jamais rejetée ni « snappée ». Le formulaire porteur reste
// `noValidate` dans la coquille.
//
// RÈGLE #4 — `marge` et `Prix / kWc` sont des repères INTERNES au générateur :
// ils ne partent dans AUCUN rendu client (PDF, page publique). Ce composant ne
// les calcule pas, il les reçoit déjà chiffrés.
import { Button } from '../../../ui'
import { formatMoney } from '../../../features/ventes/solar'

export default function RailArgent({
  showSans, showAvec, sansRec, avecRec, totals,
  discountPct, setDiscountPct, remiseMax,
  tauxTva, setTauxTva,
  pkwc, prixCible, setPrixCible, applyPrixCible, kwp,
  marge, kpiTotal,
}) {
  return (
    <>
      {/* VX138 — chaîne de totaux hiérarchisée (paliers F121 existants) :
          brut (tier-1) → remise/TVA (tier-2) → total final (tier-3, le
          TTC retenu devient le point focal). */}
      <div className="gen-totals-row gen-tier-1">
        {showSans && (
          <div className="gen-total-item">
            <span className="gen-total-label">Total SANS batterie{sansRec ? ' ⭐' : ''}</span>
            <span className="gen-total-value">{formatMoney(totals.totalSansBrut)}</span>
          </div>
        )}
        {showAvec && (
          <div className="gen-total-item">
            <span className="gen-total-label">Total AVEC batterie{avecRec ? ' ⭐' : ''}</span>
            <span className="gen-total-value orange">{formatMoney(totals.totalAvecBrut)}</span>
          </div>
        )}
      </div>
      <div className="gen-totals-row gen-discount-row">
        <div className="gen-total-item gen-total-inline gen-tier-2">
          <span className="gen-total-label">Réduction</span>
          <input type="number" min="0" max="100" step="any" className="gen-discount-input"
                 value={discountPct} onChange={e => setDiscountPct(e.target.value)} />
          <span style={{ fontWeight: 700 }}>%</span>
          {remiseMax !== '' && parseFloat(discountPct) > parseFloat(remiseMax) && (
            /* VX17 — couleur d'avertissement via token de thème. */
            <span className="text-warning ml-1.5" style={{ fontSize: 11 }}>
              ⚠ au-delà de la limite conseillée ({remiseMax} %)
            </span>
          )}
        </div>
        <div className="gen-total-item gen-total-inline gen-tier-2">
          <span className="gen-total-label">TVA</span>
          <input type="number" min="0" max="100" step="any" className="gen-discount-input"
                 value={tauxTva} onChange={e => setTauxTva(e.target.value)} />
          <span style={{ fontWeight: 700 }}>%</span>
        </div>
        {parseFloat(discountPct) > 0 && showSans && (
          <div className="gen-total-item gen-tier-3">
            <span className="gen-total-label green">Total final SANS batterie</span>
            <span className="gen-total-value green">{formatMoney(totals.totalSans)}</span>
          </div>
        )}
        {parseFloat(discountPct) > 0 && showAvec && (
          <div className="gen-total-item gen-tier-3">
            <span className="gen-total-label green">Total final AVEC batterie</span>
            <span className="gen-total-value green">{formatMoney(totals.totalAvec)}</span>
          </div>
        )}
      </div>

      {/* ── Prix par kWc, prix cible et marge (écran uniquement) ── */}
      <div className="gen-totals-row gen-discount-row">
        {pkwc != null && (() => {
          // Repère vs cible société : vert si ≤ cible (bon), rouge si au-dessus.
          const cibleNum = parseFloat(prixCible)
          const hasCible = Number.isFinite(cibleNum) && cibleNum > 0
          const sousCible = hasCible ? pkwc <= cibleNum : null
          // VX17 — couleur via tokens de thème (success/destructive).
          const couleurCls = sousCible == null ? ''
            : (sousCible ? 'text-success' : 'text-destructive')
          return (
            <div className="gen-total-item">
              <span className="gen-total-label">Prix / kWc</span>
              <span className={`gen-total-value ${couleurCls}`}>
                {formatMoney(pkwc)}/kWc
              </span>
              {hasCible && (
                <span className={`gen-total-hint ${couleurCls}`} style={{ fontSize: 12 }}>
                  {sousCible
                    ? `≤ cible (${formatMoney(cibleNum)}/kWc)`
                    : `au-dessus de la cible (${formatMoney(cibleNum)}/kWc)`}
                </span>
              )}
            </div>
          )
        })()}
        <div className="gen-total-item gen-total-inline">
          <span className="gen-total-label">Prix cible / kWc</span>
          <input type="number" min="0" step="any" className="gen-discount-input"
                 style={{ width: 100 }} placeholder="ex: 9000"
                 value={prixCible} onChange={e => setPrixCible(e.target.value)} />
          <Button type="button" size="sm" variant="outline"
                  onClick={applyPrixCible}
                  disabled={!(kwp > 0) || prixCible === ''}>
            Appliquer via remise
          </Button>
        </div>
        {marge != null && (
          <div className="gen-total-item">
            {/* VX17 — couleurs via tokens de thème (text-success/destructive)
                plutôt qu'un hex codé en dur. */}
            <span className={`gen-total-label ${marge < 0 ? 'text-destructive' : 'text-success'}`}>
              Marge indicative (interne)
            </span>
            <span className={`gen-total-value ${marge < 0 ? 'text-destructive' : 'text-success'}`}>
              {formatMoney(marge)}
              {kpiTotal > 0 ? ` (${Math.round(marge / kpiTotal * 100)} %)` : ''}
            </span>
          </div>
        )}
      </div>
      {marge != null && marge < 0 && (
        <div className="mx-5 mb-4 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          Le total après remise est INFÉRIEUR au coût d'achat estimé — vous
          vendez à perte. Réduisez la remise ou le prix cible.
        </div>
      )}
    </>
  )
}
