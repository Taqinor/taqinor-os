import { useCallback, useEffect, useMemo, useState } from 'react'
import { ORDRE_CALQUES, CALQUE_ELECTRIQUE_ID, lireEtatCalques, ecrireEtatCalques } from './calques'

/* ============================================================================
   CAL103 — LE PANNEAU DE CALQUES de l'atelier.
   ----------------------------------------------------------------------------
   Constat : les couches s'allumaient par des bascules DISPERSÉES et hétérogènes
   — le contour client (`rp9-toit-client-toggle`) et la photo calée
   (`rp9-photo-toit-toggle`) sur l'écran hôte, la carte d'accès solaire dans
   `shadingUi.ts`, les autres nulle part. Aucun panneau commun, et surtout aucun
   ORDRE de superposition maîtrisé : qui passe au-dessus de qui dépendait de
   l'ordre d'ajout des couches.

   Ce panneau regroupe les DIX calques de l'atelier avec, pour chacun, sa
   VISIBILITÉ et son OPACITÉ, dans l'ordre de rendu DÉTERMINÉ par `calques.js`
   (du fond vers le dessus), appliqué sur la carte par `mapDraw.setLayerState`.

   CE QUI NE CHANGE PAS : les bascules existantes continuent de fonctionner. Ce
   panneau ne les remplace pas — un calque que le constructeur ne déclare pas
   n'est simplement pas listé : rien à basculer, rien à inventer.

   CALX54 — N'OFFRIR QUE LES CALQUES RÉELLEMENT PRÉSENTS DANS LA SCÈNE. Constat :
   ce panneau proposait les DIX calques statiques de `calques.js` dès que l'hôte
   ne déclarait pas explicitement `disponibles` — « Parcellaire cadastral » et
   « Plan importé » restaient donc TOUJOURS proposés alors que rien ne les
   chargeait jamais. La SEULE source d'intention désormais : `builderApi`
   (`builderApiActuel`, CALX8), dont `calquesDisponibles()` (CALX3) rend les
   identifiants RÉELLEMENT installés sur la scène, dans l'ordre de rendu. Sans
   `builderApi`, avant qu'il ne soit prêt, ou si la scène ne porte encore aucun
   calque : liste vide, état vide affiché — jamais la liste statique en repli.
   Un identifiant que `calques.js` ne connaît pas est ignoré au filtre, jamais
   inventé. Relu à chaque fois que `builderApi` change d'identité (le builder
   devient prêt) — aucun sondage : pas de minuterie, pas de boucle.

   PERSISTANCE PAR UTILISATEUR : `calques.js` range l'état sous une clé qui porte
   l'identifiant de l'utilisateur ; un navigateur qui refuse le stockage repart de
   l'état par défaut, sans jamais lever.

   CALX221 — LE CALQUE « ÉLECTRIQUE », ONZIÈME ENTRÉE DU PANNEAU. Les dix calques
   de `calques.js` sont des couches de la CARTE (`mapDraw.setLayerState`) ; les
   organes et les cheminements électriques, eux, vivent dans la SCÈNE 3D
   (`apps/web/src/scripts/roofPro11/electrique3d.ts`). `calquesDisponibles()`
   n'interroge que la carte : elle ne peut donc pas voir ce calque-là. C'est la
   couche électrique du constructeur qui le déclare, et seulement quand le
   document porte `electrical` — tant qu'aucun organe n'est posé, aucune bascule
   n'apparaît, exactement comme pour un calque de carte non installé. Son
   identifiant est DÉCLARÉ UNE SEULE FOIS côté constructeur
   (`ID_CALQUE_ELECTRIQUE`) ; le test jumeau de cet écran relit ce source pour
   l'affirmer, faute de module partagé entre le portail Vite et le site Astro.
   ========================================================================== */

/** CALX221 — l'entrée « Électrique » du panneau. L'identifiant est `CALQUE_ELECTRIQUE_ID`
 *  (calques.js — CALX22x câblage : la SEULE copie frontend de la chaîne, mémorisée par
 *  utilisateur comme les dix autres) ; le libellé est celui affiché à l'utilisateur. Cet
 *  objet n'est PAS exporté (un fichier de composant n'exporte que des composants) : le
 *  test jumeau le vérifie par le rendu, avec l'identifiant lu dans le source TypeScript
 *  du constructeur. */
const CALQUE_ELECTRIQUE = { id: CALQUE_ELECTRIQUE_ID, label: 'Électrique' }

/** Les calques que ce panneau sait proposer : les dix de `calques.js` (couches de
 *  la carte), puis le calque électrique de la scène 3D, au-dessus d'eux. */
const CALQUES_DU_PANNEAU = [...ORDRE_CALQUES, CALQUE_ELECTRIQUE]

/** État d'ouverture d'un calque que `calques.js` ne connaît pas : visible, opaque
 *  — le comportement d'aujourd'hui, jamais un réglage inventé. */
const ETAT_PAR_DEFAUT = { visible: true, opacite: 1 }

/**
 * @param {{calquesDisponibles?: () => string[]}|null} [builderApi]  l'API du
 *        constructeur (CALX3, `builderApiActuel` côté écran) : SEULE source des
 *        calques réellement installés sur la scène. Absente, pas encore prête,
 *        ou sans `calquesDisponibles` ⇒ aucun calque proposé (état vide).
 * @param {(id: string, etat: {visible: boolean, opacite: number}) => void} onChange
 * @param {string|number} utilisateurId  clé de persistance PAR UTILISATEUR.
 */
export default function PanneauCalques({ builderApi, onChange, utilisateurId, stockage }) {
  // CALX54 — ce que la scène porte VRAIMENT, jamais les dix identifiants
  // statiques. `calquesDisponibles` est APPELÉE (pas seulement lue) : une
  // fonction absente, ou qui lève, rend une liste vide plutôt qu'une exception.
  const disponibles = useMemo(() => {
    try {
      const brut = builderApi?.calquesDisponibles?.()
      const liste = Array.isArray(brut) ? [...brut] : []
      // CALX221 — le calque électrique n'est pas une couche de la carte : il est
      // servi par la couche 3D du constructeur, et SEULEMENT si le document
      // porte `electrical` (aucun organe posé ⇒ aucune bascule).
      if (builderApi?.electrique?.calqueDisponible?.()) liste.push(CALQUE_ELECTRIQUE.id)
      return liste
    } catch {
      return []
    }
    // Ne se relit QUE quand `builderApi` change d'identité (le builder devient
    // prêt) — jamais à chaque rendu : sinon la carte serait interrogée en boucle.
  }, [builderApi])

  const listes = useMemo(
    () => CALQUES_DU_PANNEAU.filter((c) => disponibles.includes(c.id)),
    [disponibles],
  )
  const [etat, setEtat] = useState(() => lireEtatCalques(utilisateurId, stockage))

  // À l'ouverture ET à chaque relecture de la liste (le builder devient prêt),
  // l'hôte reçoit l'état RESTAURÉ des calques désormais proposés : sinon la
  // carte afficherait l'état par défaut pendant que le panneau montre l'état
  // mémorisé.
  useEffect(() => {
    for (const c of listes) onChange?.(c.id, etat[c.id] ?? ETAT_PAR_DEFAUT)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [listes])

  const appliquer = useCallback(
    (id, patch) => {
      setEtat((prev) => {
        const suivant = { ...prev, [id]: { ...ETAT_PAR_DEFAUT, ...prev[id], ...patch } }
        ecrireEtatCalques(utilisateurId, suivant, stockage)
        onChange?.(id, suivant[id])
        return suivant
      })
    },
    [onChange, utilisateurId, stockage],
  )

  return (
    <section data-testid="pc-panneau" aria-label="Calques" className="border border-white/10 bg-nuit-800 p-3">
      <h3 className="tech-label mb-2 text-lune-faint">Calques</h3>
      {listes.length === 0 ? (
        // CALX54 — état vide EXPLICITE : le constructeur n'est pas encore prêt,
        // ou aucun calque n'est encore installé sur la scène — jamais une liste
        // statique inventée pour combler le vide.
        <p className="text-sm text-lune-faint" data-testid="pc-vide">
          Aucun calque disponible pour le moment.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {listes.map((c, i) => {
            // CALX221 — un calque que `calques.js` ne connaît pas (l'électrique)
            // n'a pas d'état mémorisé : il s'ouvre visible et opaque.
            const e = etat[c.id] ?? ETAT_PAR_DEFAUT
            return (
              <li key={c.id} data-testid={`pc-calque-${c.id}`} data-rang={i} className="flex items-center gap-2 text-sm">
                <label className="flex flex-1 items-center gap-2">
                  <input
                    type="checkbox"
                    data-testid={`pc-visible-${c.id}`}
                    checked={e.visible}
                    onChange={(ev) => appliquer(c.id, { visible: ev.target.checked })}
                  />
                  <span>{c.label}</span>
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  aria-label={`Opacité — ${c.label}`}
                  data-testid={`pc-opacite-${c.id}`}
                  value={e.opacite}
                  onChange={(ev) => appliquer(c.id, { opacite: Number(ev.target.value) })}
                />
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
