// SPL215 — onglets de vue de l'atelier : calques (CAL103), onglets 3D/2D (CAL104)
// et export image HD (CAL180), déplacés VERBATIM depuis pages/ventes/ToitureDesign.jsx
// (move only : le JSX est inchangé ; seuls l'enveloppe du composant et les
// imports sont ajoutés, l'état arrive en props NOMMÉES).
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import PanneauCalques from '../PanneauCalques'
import Vue2DPlan from '../Vue2DPlan'
import { FACTEURS_HD } from '../exportImage'
import { exporterVideoOrbite } from '../exportVideo' // ACAL896
import { useModeExpert } from './modeExpert'

const VUES_CAMERA = [
  ['dessus', 'Dessus', 'cal-vue-dessus'],
  ['sud', 'Sud', 'cal-vue-sud'],
  ['trois-quarts', '3/4', 'cal-vue-trois-quarts'],
  ['face-panneaux', 'Face aux panneaux', 'cal-vue-face-panneaux'],
]

export default function OutilsVue({
  builderReady, utilisateurCourantId, builderApiActuel, builderApi, chipClass,
  vue2d, setVue2d, plan2d, panId2d, ouvrirVue2d,
  hdBusy, hdMessage, exporterHd, gltfBusy, gltfMessage, exporterGltf,
}) {
  const [expert] = useModeExpert()
  // ACAL896 — « Vidéo 10 s » : état local du bouton (ToitureDesign.jsx n'est pas touché).
  const { id: reference } = useParams()
  const [videoMessage, setVideoMessage] = useState(null) // null = au repos ; sinon le texte affiché
  const [videoBusy, setVideoBusy] = useState(false)
  const lancerVideo = async () => {
    setVideoBusy(true)
    setVideoMessage('Enregistrement… (0 s)')
    const res = await exporterVideoOrbite(builderApi, {
      reference, surProgres: (s) => setVideoMessage(`Enregistrement… (${s} s)`),
    })
    setVideoMessage(res.ok ? `Vidéo enregistrée : ${res.nom}` : res.motif)
    setVideoBusy(false)
  }
  return (
    <>
        {/* CAL103 — PANNEAU DE CALQUES : une seule liste pour imagerie, cadastre,
            photo calée, plan importé, tracé client, obstacles, zones, panneaux,
            ombres et mesures — visibilité + opacité, dans un ordre de rendu
            déterminé. Monté dès que le builder expose son API (sans elle, il n'y
            aurait rien à piloter).
            CALX54 — `builderApi` (ci-dessous) est l'OBJET posé par `onApiReady`
            (`builderApiActuel`, même raison que CALX8 pour `AtelierPanneaux` :
            `builderApi.current` est une réf, illisible pendant le rendu) — le
            panneau lit lui-même `calquesDisponibles()` dessus pour n'afficher
            que les calques réellement installés sur la scène. */}
        {builderReady && (
          <div className="mt-4" data-testid="cal-panneau-calques">
            <PanneauCalques
              utilisateurId={utilisateurCourantId}
              builderApi={builderApiActuel}
              onChange={(id, etat) => {
                // CALX22x câblage — le calque « Électrique » vit dans la couche 3D du
                // constructeur (`electrique3d.ts`), pas sur la carte : le `setLayerState`
                // général route TOUT vers `mapDraw.setLayerState`, qui ne le connaît pas
                // (rend `false`, rien ne bascule). On route au plus près du builder, sur
                // l'identifiant que SA couche déclare elle-même (`idCalque`) — jamais une
                // chaîne recopiée ici.
                const electrique = builderApi.current?.electrique
                if (electrique && id === electrique.idCalque) electrique.setLayerState(id, etat)
                else builderApi.current?.setLayerState?.(id, etat)
              }}
            />
          </div>
        )}

        {/* CAL104 — ONGLETS 3D / 2D PLAN. La 3D n'est JAMAIS démontée (elle reste
            dans le DOM, simplement masquée) : basculer d'onglet ne re-boote pas le
            builder, donc ni la sélection ni l'historique ne sont perdus. */}
        {builderReady && (
          <div className="mt-4" data-testid="cal-onglets-vue">
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                className={chipClass}
                aria-pressed={!vue2d}
                data-testid="cal-onglet-3d"
                onClick={() => setVue2d(false)}
              >
                Vue 3D
              </button>
              <button
                type="button"
                className={chipClass}
                aria-pressed={vue2d}
                data-testid="cal-onglet-2d"
                onClick={ouvrirVue2d}
              >
                Vue 2D — plan
              </button>
            </div>
            {/* ACAL435 — vues de caméra prêtes (masquées en vue 2D) */}
            {!vue2d && (
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Vue</span>
                {VUES_CAMERA.map(([nom, libelle, hook]) => (
                  <button
                    key={nom}
                    type="button"
                    className={chipClass}
                    data-testid={hook}
                    onClick={() => builderApi.current?.appliquerVue?.(nom)}
                  >
                    {libelle}
                  </button>
                ))}
              </div>
            )}
            {vue2d && (
              <div className="mt-2">
                <Vue2DPlan plan={plan2d} compte3d={plan2d?.panelCount ?? null} panId={panId2d} />
              </div>
            )}
          </div>
        )}

        {/* CAL180 — EXPORT IMAGE HD : la scène rendue hors écran à 2× ou 3×, remise
            au navigateur. Aucun PNG n'est posté ici et l'affiche client existante
            reste strictement inchangée. */}
        {builderReady && (
          <div className="mt-4 flex flex-wrap items-center gap-2" data-testid="cal-export-hd">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Image HD</span>
            {FACTEURS_HD.map((f) => (
              <button
                key={f}
                type="button"
                className={chipClass}
                disabled={hdBusy}
                data-testid={`cal-export-hd-${f}`}
                onClick={() => exporterHd(f)}
              >
                {`Exporter ${f}×`}
              </button>
            ))}
            {hdMessage && <span className="text-xs text-muted-foreground" data-testid="cal-export-hd-message">{hdMessage}</span>}
            {/* ACAL537 — scène 3D en glTF (.glb) pour un architecte : niveau expert. */}
            {expert && (
              <button
                type="button"
                className={chipClass}
                disabled={gltfBusy}
                data-testid="cal-export-gltf"
                onClick={exporterGltf}
              >
                Exporter la 3D (glTF)
              </button>
            )}
            {gltfMessage && <span className="text-xs text-muted-foreground" data-testid="cal-export-gltf-message">{gltfMessage}</span>}
            {/* ACAL896 — une orbite de 10 s enregistrée puis téléchargée (WhatsApp) : niveau expert, aucun prix. */}
            {expert && (
              <button
                type="button"
                className={chipClass}
                disabled={videoBusy}
                data-testid="cal-video-orbite"
                onClick={lancerVideo}
              >
                Vidéo 10 s
              </button>
            )}
            {videoMessage && <span className="text-xs text-muted-foreground" data-testid="cal-video-orbite-message" role="status">{videoMessage}</span>}
          </div>
        )}
    </>
  )
}
