import { useState } from 'react'
import { Shuffle } from 'lucide-react'
import adsengineApi from './adsengineApi'

/* ============================================================================
   PUB118 — Bouton « Recombiner (DCO) » — le premier « mes pubs créent des pubs ».
   ----------------------------------------------------------------------------
   Un clic PROPOSE une ad à spec créative dynamique, bâtie UNIQUEMENT sur les
   visuels et les textes de vos créatifs déjà diffusés et GAGNANTS (miroirs) :
   aucune clé externe, aucune dépense, aucun contenu inventé. Rien n'est publié —
   la proposition part dans la boîte d'approbation et l'ad naîtra PAUSED.

   JAMAIS d'automatisme : ce bouton est le seul déclencheur (aucun beat ne
   recombine tout seul). Les refus métier du backend (l'ad set a déjà un signal,
   exclusion mutuelle DCO ↔ rotation multi-ads, aucun créatif gagnant à
   recombiner) sont affichés TELS QUELS, en français.
   ========================================================================== */

export default function DcoRecombineButton({ adsetMetaId, adsetName, onProposed }) {
  const [busy, setBusy] = useState(false)
  const [erreur, setErreur] = useState('')
  const [succes, setSucces] = useState('')

  if (!adsetMetaId) return null

  const recombiner = () => {
    setBusy(true)
    setErreur('')
    setSucces('')
    // `suppressErrorToast` : la raison métier FR du backend est montrée ICI,
    // à côté du bouton (un toast générique la remplacerait par « Erreur »).
    adsengineApi.dco.recombine(adsetMetaId, { suppressErrorToast: true })
      .then(() => {
        setSucces("Recombinaison proposée : retrouvez-la dans les approbations "
          + "(l'ad naîtra en pause).")
        onProposed?.()
      })
      .catch((err) => {
        setErreur(err?.response?.data?.detail
          || "Recombinaison impossible pour le moment. Rien n'a été proposé.")
      })
      .finally(() => setBusy(false))
  }

  return (
    <div className="ae-dco-recombine" data-testid="ae-dco-recombine"
      style={{ marginTop: '0.6rem' }}>
      <button type="button" className="btn btn-light"
        data-testid="ae-dco-recombine-button" disabled={busy}
        onClick={recombiner}
        title={adsetName
          ? `Recombiner les créatifs gagnants sur l'ad set « ${adsetName} »`
          : 'Recombiner les créatifs gagnants de cet ad set'}
        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
        <Shuffle size={14} aria-hidden="true" />
        {busy ? 'Recombinaison…' : 'Recombiner (DCO)'}
      </button>
      {erreur && (
        <p role="alert" data-testid="ae-dco-recombine-error"
          style={{ color: '#dc2626', margin: '0.4rem 0 0', fontSize: '0.85rem' }}>
          {erreur}
        </p>
      )}
      {succes && (
        <p data-testid="ae-dco-recombine-ok"
          style={{ color: '#047857', margin: '0.4rem 0 0', fontSize: '0.85rem' }}>
          {succes}
        </p>
      )}
    </div>
  )
}
