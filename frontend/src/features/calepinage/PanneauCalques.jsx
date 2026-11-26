import { useCallback, useEffect, useEffectEvent, useMemo, useRef, useState } from 'react'
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

/** T4-X7-015 (rejeu) — relecture bornée d'un panneau visible encore vide (carte pas encore dessinée). */
const RELECTURE_MS = 500
const RELECTURES_MAX = 20

/**
 * @param {{calquesDisponibles?: () => string[]}|null} [builderApi]  l'API du
 *        constructeur (CALX3, `builderApiActuel` côté écran) : SEULE source des
 *        calques réellement installés sur la scène. Absente, pas encore prête,
 *        ou sans `calquesDisponibles` ⇒ aucun calque proposé (état vide).
 * @param {(id: string, etat: {visible: boolean, opacite: number}) => void} onChange
 * @param {string|number} utilisateurId  clé de persistance PAR UTILISATEUR.
 */
export default function PanneauCalques({ builderApi, onChange, utilisateurId, stockage }) {
  // T4-X7-015 — le panneau vit dans la feuille « Avancé », montée dès le départ mais CACHÉE : la liste lue à ce
  // moment-là (carte pas encore dessinée) restait vide à vie. On la relit quand le panneau DEVIENT VISIBLE
  // (ouverture de la feuille) : événement de mise en page, aucune minuterie.
  const racine = useRef(null)
  const [lecture, setLecture] = useState(0)
  useEffect(() => {
    const noeud = racine.current
    if (!noeud || typeof ResizeObserver === 'undefined') return undefined
    const obs = new ResizeObserver(() => { if (noeud.offsetWidth > 0 || noeud.offsetHeight > 0) setLecture((n) => n + 1) })
    obs.observe(noeud)
    return () => obs.disconnect()
  }, [])
  // CALX54 — ce que la scène porte VRAIMENT, jamais les dix identifiants
  // statiques. `calquesDisponibles` est APPELÉE (pas seulement lue) : une
  // fonction absente, ou qui lève, rend une liste vide plutôt qu'une exception.
  const disponibles = useMemo(() => {
    void lecture // T4-X7-015 : relecture déclenchée à l'ouverture de la feuille
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
  }, [builderApi, lecture])

  // T4-X7-015 (rejeu R5B, 26/11) — ouverte par un lien profond juste après le chargement, la feuille devient visible AVANT
  // que la carte n'ait installé ses couches : la relecture d'ouverture tombait sur une liste vide et plus rien ne la
  // relisait (« Aucun calque disponible », 4 calques par le bouton Avancé). Tant que le panneau est VISIBLE et VIDE : relu
  // toutes les 500 ms, au plus 20 fois (10 s) — borné, arrêté dès qu'un calque paraît ou que le panneau se cache.
  const essais = useRef(0)
  useEffect(() => {
    const noeud = racine.current
    const visible = Boolean(noeud) && (noeud.offsetWidth > 0 || noeud.offsetHeight > 0)
    if (!visible || disponibles.length > 0 || essais.current >= RELECTURES_MAX) return undefined
    const minuteur = setTimeout(() => { essais.current += 1; setLecture((n) => n + 1) }, RELECTURE_MS)
    return () => clearTimeout(minuteur)
  }, [lecture, disponibles])

  // T4-X7-015 (rejeu R6) — la bascule « Électrique » n'apparaissait pas : la liste est lue à l'ouverture de la feuille, or le
  // premier organe se pose (Équipements électriques) PENDANT que la feuille reste ouverte — rien ne relisait la liste. À
  // l'approche du panneau (survol, focus), la disponibilité de la couche est relue ; la liste ne l'est que si elle a changé.
  // Événement d'interface, aucune minuterie, aucun sondage.
  const electriqueListee = disponibles.includes(CALQUE_ELECTRIQUE.id)
  const relireElectrique = () => {
    let disponible = false
    try { disponible = Boolean(builderApi?.electrique?.calqueDisponible?.()) } catch { disponible = false }
    if (disponible !== electriqueListee) setLecture((n) => n + 1)
  }

  const listes = useMemo(
    () => CALQUES_DU_PANNEAU.filter((c) => disponibles.includes(c.id)),
    [disponibles],
  )
  const [etat, setEtat] = useState(() => lireEtatCalques(utilisateurId, stockage))

  // À l'ouverture ET à chaque relecture de la liste (le builder devient prêt),
  // l'hôte reçoit l'état RESTAURÉ des calques désormais proposés : sinon la
  // carte afficherait l'état par défaut pendant que le panneau montre l'état
  // mémorisé.
  const restituer = useEffectEvent(() => {
    for (const c of listes) {
      const e = etat[c.id] ?? ETAT_PAR_DEFAUT
      // T4-X7-015 — la couche électrique a sa propre règle d'étape (la scène l'affiche à l'étape Électrique seulement) :
      // son état PAR DÉFAUT n'est jamais poussé à l'ouverture (il la montrerait à une étape où la scène la cache). Seul un
      // réglage de l'utilisateur (masquée, opacité) est restitué ; aucun changement visible avant qu'il ne touche à la case.
      if (c.id === CALQUE_ELECTRIQUE.id && e.visible && e.opacite === 1) continue
      onChange?.(c.id, e)
    }
  })
  useEffect(() => { restituer() }, [listes])

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
    <section ref={racine} data-testid="pc-panneau" aria-label="Calques" className="border border-border bg-card p-3"
      onPointerEnter={relireElectrique} onFocusCapture={relireElectrique}>
      <h3 className="text-xs font-semibold uppercase tracking-wide mb-2 text-muted-foreground">Calques</h3>
      {listes.length === 0 ? (
        // CALX54 — état vide EXPLICITE : le constructeur n'est pas encore prêt,
        // ou aucun calque n'est encore installé sur la scène — jamais une liste
        // statique inventée pour combler le vide.
        <p className="text-sm text-muted-foreground" data-testid="pc-vide">
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
