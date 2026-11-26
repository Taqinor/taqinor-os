import { useEffect, useRef, useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'
import { useHasPermission } from '../../../hooks/useHasPermission'
import { Button, Card, Input, Label, Spinner } from '../../../ui'
import { OBSTACLE_TYPES } from '@roofpro/types'

/* ============================================================================
   ACAL488 — L'ONGLET « DÉTECTION DU TOIT » : le serveur PROPOSE un contour,
   l'utilisateur confirme (D-ACAL-33).
   ----------------------------------------------------------------------------
   Contrat `calepinage_detection_toit.json` (ACAL391, serveur ACAL485) :
   `GET detection-toit/` dit si la détection est disponible et quelles origines
   d'image elle accepte ; `POST` (multipart `image`, `emprise` JSON, `origine`)
   rend une PROPOSITION `{contour_lnglat, pans[]}` « à confirmer ». Rien n'est
   posé tant que l'utilisateur n'a pas cliqué « Utiliser ce contour » : le pan
   naît par `builderApi.ajouterPanDepuisContour` (même validateur, même refus de
   croisement que le tracé) et ne s'enregistre que par « Enregistrer le
   calepinage ». Un échec, un 503 ou une attente annulée laisse le tracé manuel
   intact.

   Origine `carte` : seulement si le serveur l'accepte ET que l'atelier sait
   capturer sa carte (`builderApi.capturerCarte() → {blob, emprise}`) ; sinon
   « Choisir une photo ou un plan » (origine `importee`, emprise saisie).
   ========================================================================== */
const COINS = ['ouest', 'sud', 'est', 'nord']
const MSG_INDISPO = 'Détection automatique non activée : tracez le toit à la main'
const MSG_CAPTURE = 'La capture de la carte n’est pas possible ici'

export default function PanneauDetectionToit({ calepinageId, builderApi = null, lectureSeule = false }) {
  const peutGerer = useHasPermission('calepinage_gerer')
  const [dispo, setDispo] = useState(null)
  const [emprise, setEmprise] = useState({ ouest: '', sud: '', est: '', nord: '' })
  const [attente, setAttente] = useState(false)
  const [proposition, setProposition] = useState(null)
  const [message, setMessage] = useState(null)
  const [refus, setRefus] = useState([])
  const [coches, setCoches] = useState([])
  const controle = useRef(null)
  const fichier = useRef(null)

  useEffect(() => {
    let vivant = true
    Promise.resolve(calepinageApi.calepinages.detectionToitDisponible(calepinageId))
      .then((res) => { if (vivant) setDispo(res?.data ?? { disponible: false }) })
      .catch(() => { if (vivant) setDispo({ disponible: false }) })
    return () => { vivant = false; controle.current?.abort() }
  }, [calepinageId])

  const envoyer = (image, origine, corpsEmprise) => {
    const corps = new FormData()
    corps.append('image', image)
    corps.append('origine', origine)
    corps.append('emprise', JSON.stringify(corpsEmprise))
    controle.current = new AbortController()
    setAttente(true)
    setMessage(null)
    setProposition(null)
    setCoches([])
    setRefus([])
    Promise.resolve(calepinageApi.calepinages.detectionToit(calepinageId, corps, { signal: controle.current.signal }))
      .then((res) => setProposition(res?.data?.propositions ?? null))
      .catch((e) => {
        if (e?.code === 'ERR_CANCELED' || e?.name === 'CanceledError') setMessage('Détection annulée : le tracé manuel est intact.')
        else setMessage(e?.response?.data?.detail || 'La détection a échoué : tracez le toit à la main.')
      })
      .finally(() => setAttente(false))
  }

  const detecterCarte = async () => {
    const capture = await Promise.resolve(builderApi?.capturerCarte?.()).catch(() => null)
    if (!capture?.blob || !capture?.emprise) { setMessage(MSG_CAPTURE); return }
    envoyer(capture.blob, 'carte', capture.emprise)
  }

  const choisi = (e) => {
    const image = e.target.files?.[0]
    if (!image) return
    const nombres = Object.fromEntries(COINS.map((c) => [c, Number(emprise[c])]))
    if (COINS.some((c) => emprise[c] === '' || !Number.isFinite(nombres[c]))) {
      setMessage('Renseignez d’abord l’emprise de l’image (ouest, sud, est, nord, en degrés).')
      return
    }
    envoyer(image, 'importee', nombres)
  }

  const utiliser = () => {
    const pans = proposition?.pans?.length ? proposition.pans.map((p) => p.contour_lnglat) : [proposition?.contour_lnglat]
    const motifs = []
    let poses = 0
    for (const contour of pans) {
      const verdict = builderApi?.ajouterPanDepuisContour?.(contour)
      if (verdict?.ok) poses += 1
      else motifs.push(verdict?.motif || 'Le contour n’a pas pu être posé comme pan.')
    }
    setRefus(motifs)
    setMessage(poses ? `${poses} pan(s) posé(s) : enregistrez le calepinage pour les conserver.` : null)
  }

  // ACAL531 — les obstacles proposés ne sont posés QUE sur « Utiliser les obstacles cochés » : provenance
  // DEVINE (non engageable), hauteur vide, décidées par l'atelier (`ajouterObstacleDepuisContour`).
  const obstacles = proposition?.obstacles ?? []
  const libelleObstacle = (o, i) => `${OBSTACLE_TYPES.find((t) => t.id === o.type)?.label ?? 'Obstacle'} ${i + 1}`
  const utiliserObstacles = () => {
    const motifs = []
    let poses = 0
    for (const i of coches) {
      const verdict = builderApi?.ajouterObstacleDepuisContour?.(obstacles[i].contour_lnglat, obstacles[i].type)
      if (verdict?.ok) poses += 1
      else motifs.push(`${libelleObstacle(obstacles[i], i)} : ${verdict?.motif || 'l’obstacle n’a pas pu être posé.'}`)
    }
    setRefus(motifs)
    setCoches([])
    setMessage(poses ? `${poses} obstacle(s) posé(s) : à vérifier sur le toit, puis enregistrez le calepinage.` : null)
  }

  if (!dispo) return <Spinner />
  if (!dispo.disponible) {
    return <p className="text-sm" data-testid="cal-detection-indisponible">{dispo.motif ? `${dispo.motif} ` : ''}{MSG_INDISPO}.</p>
  }
  const origines = dispo.origines_acceptees ?? []
  const carte = origines.includes('carte') && !!builderApi?.capturerCarte
  const actif = peutGerer && !lectureSeule && !attente

  return (
    <Card className="space-y-3 p-4" data-testid="cal-detection-panneau">
      <p className="text-sm text-muted-foreground">
        Le serveur propose un contour « à confirmer » ; rien n’est posé avant « Utiliser ce contour ».
      </p>
      {carte && (
        <Button onClick={detecterCarte} disabled={!actif} data-testid="cal-detection-carte">Détecter le toit</Button>
      )}
      {origines.includes('importee') && (
        <div className="flex flex-wrap items-end gap-2" data-testid="cal-detection-emprise">
          {COINS.map((c) => (
            <div key={c}>
              <Label htmlFor={`cal-detection-${c}`}>{c} (°)</Label>
              <Input
                id={`cal-detection-${c}`} type="number" step="any" value={emprise[c]}
                onChange={(e) => setEmprise((a) => ({ ...a, [c]: e.target.value }))}
              />
            </div>
          ))}
          <input ref={fichier} type="file" accept="image/png,image/jpeg" hidden onChange={choisi} data-testid="cal-detection-fichier" />
          <Button onClick={() => fichier.current?.click()} disabled={!actif} data-testid="cal-detection-choisir">
            Choisir une photo ou un plan
          </Button>
        </div>
      )}
      {attente && (
        <div className="flex items-center gap-2">
          <Spinner />
          <Button variant="outline" onClick={() => controle.current?.abort()} data-testid="cal-detection-annuler">Annuler</Button>
        </div>
      )}
      {message && <p className="text-sm" role="status" data-testid="cal-detection-message">{message}</p>}
      {refus.map((m, i) => <p key={i} className="text-sm text-danger" role="alert" data-testid="cal-detection-refus">{m}</p>)}
      {proposition && (
        <div className="space-y-2" data-testid="cal-detection-proposition">
          <p className="text-sm">
            Proposition à confirmer : {proposition.pans?.length || 1} pan(s) détecté(s).
          </p>
          <Button onClick={utiliser} disabled={!actif || !builderApi?.ajouterPanDepuisContour} data-testid="cal-detection-utiliser">
            Utiliser ce contour
          </Button>
          {obstacles.length > 0 && (
            <fieldset className="space-y-2">
              <legend className="text-sm font-medium">Obstacles proposés</legend>
              {obstacles.map((o, i) => (
                <label key={i} className="flex min-h-11 items-center gap-2 text-sm">
                  {/* ACAL1446 — zone cliquable 44 × 44 autour de la case (dessin 20 px inchangé). */}
                  <span className="inline-flex size-11 shrink-0 items-center justify-center" data-testid="cal-detection-obstacle-cible">
                    <input
                      type="checkbox" className="size-5" data-testid="cal-detection-obstacle"
                      checked={coches.includes(i)} disabled={!actif}
                      onChange={(e) => setCoches((c) => (e.target.checked ? [...c, i] : c.filter((x) => x !== i)))}
                    />
                  </span>
                  <span>{libelleObstacle(o, i)} <span className="text-muted-foreground">— proposé par l’IA — à vérifier sur le toit</span></span>
                </label>
              ))}
              <Button
                onClick={utiliserObstacles}
                disabled={!actif || coches.length === 0 || !builderApi?.ajouterObstacleDepuisContour}
                data-testid="cal-detection-obstacles-utiliser"
              >
                Utiliser les obstacles cochés
              </Button>
            </fieldset>
          )}
        </div>
      )}
    </Card>
  )
}
