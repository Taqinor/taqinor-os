import { useCallback, useEffect, useRef, useState } from 'react'
import { LocateFixed, ShieldAlert } from 'lucide-react'
import { Switch } from '../../ui'
import installationsApi from '../../api/installationsApi'

/* ============================================================================
   NTMOB9 — « Ma journée » : suivi de position `watchPosition` derrière un
   consentement explicite, limité à la session d'intervention OUVERTE.
   ----------------------------------------------------------------------------
   GARDE 2026-07-18 (WIR80/XFSM23) : le consentement DURABLE (`GpsConsentRecord`)
   est réservé responsable/admin (établi une fois, hors de ce module) — CE
   composant n'en pose jamais, il propose seulement au TECHNICIEN un
   interrupteur EXPLICITE, jamais activé par défaut, jamais de tracking
   silencieux. Activer l'interrupteur démarre `navigator.geolocation.
   watchPosition` UNIQUEMENT pendant que l'intervention est « en route » ou
   « sur site » (jamais en tâche de fond permanente) ; chaque position est
   remontée via `positions-techniciens/ping/`, qui calcule le géofencing
   SERVEUR. Un refus serveur (403 — aucun consentement actif enregistré pour
   ce technicien) coupe proprement l'interrupteur et bascule sur le message
   invitant au pointage manuel (F6, déjà possible dans Ma journée — coexiste,
   jamais remplacé).
   ========================================================================== */

// Session ouverte = le technicien est en déplacement ou sur place (F3).
const STATUTS_SESSION_OUVERTE = ['en_route', 'sur_site']

// Throttle : au plus une remontée par minute (watchPosition peut déclencher
// bien plus souvent selon l'appareil) — jamais un ping par évènement brut.
const PING_MIN_INTERVAL_MS = 60 * 1000

export default function GpsTrackingToggle({ intervention }) {
  const [actif, setActif] = useState(false)
  const [erreur, setErreur] = useState(null)
  const dernierEnvoiRef = useRef(0)

  const sessionOuverte = STATUTS_SESSION_OUVERTE.includes(intervention?.statut)
  const interventionId = intervention?.id

  // Appelé par le callback `watchPosition` (asynchrone, jamais synchrone
  // dans le corps de l'effet) — seul endroit où `Date.now()` est lu.
  const surPosition = useCallback((position) => {
    const maintenant = Date.now()
    if (maintenant - dernierEnvoiRef.current < PING_MIN_INTERVAL_MS) return
    dernierEnvoiRef.current = maintenant
    installationsApi.pingPosition({
      lat: position.coords.latitude,
      lng: position.coords.longitude,
      accuracy_m: position.coords.accuracy ?? undefined,
      intervention: interventionId,
    }).catch((err) => {
      if (err?.response?.status === 403) {
        setActif(false)
        setErreur(
          "Suivi non activé pour vous par un responsable — utilisez le pointage manuel.")
      }
    })
  }, [interventionId])

  // Valeur dérivée à chaque rendu (jamais un state) : évite tout
  // `setState` synchrone dans le corps de l'effet ci-dessous.
  const geoDisponible = typeof navigator !== 'undefined' && !!navigator.geolocation

  useEffect(() => {
    if (!actif || !sessionOuverte || !geoDisponible) return undefined
    const watchId = navigator.geolocation.watchPosition(
      surPosition,
      () => setErreur(
        'Position indisponible — vérifiez que la géolocalisation est autorisée.'),
      { enableHighAccuracy: false, maximumAge: 30000 },
    )
    // Jamais en tâche de fond permanente : coupé dès que l'interrupteur
    // repasse à off, que la session se ferme (statut hors liste), ou que le
    // panneau se démonte.
    return () => navigator.geolocation.clearWatch(watchId)
  }, [actif, sessionOuverte, geoDisponible, surPosition])

  if (!sessionOuverte) return null

  return (
    <div className="flex flex-col gap-1 pt-1" data-testid="gps-tracking-toggle">
      <label className="flex items-center gap-2 text-[12px] text-muted-foreground">
        <Switch
          checked={actif}
          disabled={!geoDisponible}
          onCheckedChange={(v) => { setActif(v); setErreur(null) }}
          aria-label="Activer le suivi de position pendant cette intervention"
        />
        <span className="flex items-center gap-1">
          <LocateFixed className="size-3.5" aria-hidden="true" />
          Activer le suivi de position pendant cette intervention (avec votre accord)
        </span>
      </label>
      {!geoDisponible && (
        <p className="flex items-center gap-1 text-[12px] text-warning" role="status">
          <ShieldAlert className="size-3.5" aria-hidden="true" />
          Géolocalisation indisponible sur cet appareil — utilisez le pointage manuel.
        </p>
      )}
      {geoDisponible && erreur && (
        <p className="flex items-center gap-1 text-[12px] text-warning" role="status">
          <ShieldAlert className="size-3.5" aria-hidden="true" /> {erreur}
        </p>
      )}
    </div>
  )
}
