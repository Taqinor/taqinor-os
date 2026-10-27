import { useState } from 'react'
import { ShieldCheck, ShieldAlert } from 'lucide-react'
import { Button } from '../../ui'
import installationsApi from '../../api/installationsApi'
import { NoticeGeoloc } from './GpsTrackingToggle'

/* ============================================================================
   FONDATEUR 27/10/2026 — les techniciens sont des PRESTATAIRES externes qui
   utilisent l'application de la société : l'acceptation des conditions
   d'utilisation (géolocalisation pendant les missions) est une condition
   BLOQUANTE des écrans terrain — jamais cachée (loi 09-08 : la notice est lue
   AVANT tout suivi).

   Écran pleine page, sans bouton de fermeture : tant que `mon-consentement`
   répond `a_accepter`, seule la notice + « J'ai lu et j'accepte » est
   proposée ; l'accord (`mon-consentement/accepter`) rend la main à l'écran.
   `revoque` : l'accord a été retiré — l'accès aux missions est suspendu
   (droit de retrait de la notice v2), sans bouton.
   Les responsables / administrateurs n'y passent jamais : le serveur ne leur
   crée aucun consentement (`statut: 'absent'`).
   ========================================================================== */

/** Vrai quand la réponse de `mon-consentement` bloque les écrans terrain. */
// eslint-disable-next-line react-refresh/only-export-components -- prédicat pur co-localisé avec l'écran qu'il commande (D-ENF22)
export function consentementBloquant(consentement) {
  return ['a_accepter', 'revoque'].includes(consentement?.statut)
}

export default function ConsentementGpsBloquant({ consentement, onAccepte }) {
  const [busy, setBusy] = useState(false)
  const [erreur, setErreur] = useState(null)
  const retire = consentement?.statut === 'revoque'
  const notice = consentement?.notice ?? null

  const accepter = async () => {
    setBusy(true); setErreur(null)
    try {
      const r = await installationsApi.accepterConsentementGps()
      onAccepte?.(r?.data ?? null)
    } catch {
      setErreur('Accord non enregistré — vérifiez la connexion puis réessayez.')
    } finally { setBusy(false) }
  }

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-2xl flex-col justify-center p-3 sm:p-4"
      data-testid="gps-consentement-bloquant">
      <section className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4"
        role="region" aria-labelledby="gps-cgu-titre">
        <h1 id="gps-cgu-titre" className="flex items-center gap-2 text-base font-semibold">
          {retire
            ? <ShieldAlert className="size-5 text-warning" aria-hidden="true" />
            : <ShieldCheck className="size-5 text-primary" aria-hidden="true" />}
          Conditions d&apos;utilisation — géolocalisation pendant vos missions
        </h1>
        {retire ? (
          <p className="text-sm" data-testid="gps-consentement-retire">
            Votre accord a été retiré : l&apos;accès aux missions est suspendu.
            Adressez-vous à votre responsable.
          </p>
        ) : (
          <p className="text-sm font-medium">
            L&apos;accès aux missions nécessite votre accord.
          </p>
        )}
        <NoticeGeoloc notice={notice} />
        {erreur && <p className="text-[12px] text-warning" role="alert">{erreur}</p>}
        {!retire && (
          <Button onClick={accepter} loading={busy} disabled={busy}>
            J&apos;ai lu et j&apos;accepte
          </Button>
        )}
      </section>
    </div>
  )
}
