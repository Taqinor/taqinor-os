import { useCallback, useEffect, useMemo, useState } from 'react'
import { ORDRE_CALQUES, lireEtatCalques, ecrireEtatCalques } from './calques'

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
   panneau ne les remplace pas — un calque que l'hôte ne déclare pas
   (`disponibles`) n'est simplement pas listé : rien à basculer, rien à inventer.

   PERSISTANCE PAR UTILISATEUR : `calques.js` range l'état sous une clé qui porte
   l'identifiant de l'utilisateur ; un navigateur qui refuse le stockage repart de
   l'état par défaut, sans jamais lever.
   ========================================================================== */

/**
 * @param {string[]} disponibles  identifiants des calques que l'hôte sait piloter.
 *                                Absent ⇒ tous. Un calque non disponible n'est PAS listé.
 * @param {(id: string, etat: {visible: boolean, opacite: number}) => void} onChange
 * @param {string|number} utilisateurId  clé de persistance PAR UTILISATEUR.
 */
export default function PanneauCalques({ disponibles, onChange, utilisateurId, stockage }) {
  const listes = useMemo(
    () => ORDRE_CALQUES.filter((c) => !disponibles || disponibles.includes(c.id)),
    [disponibles],
  )
  const [etat, setEtat] = useState(() => lireEtatCalques(utilisateurId, stockage))

  // À l'ouverture, l'hôte reçoit l'état RESTAURÉ : sinon la carte afficherait
  // l'état par défaut pendant que le panneau montre l'état mémorisé.
  useEffect(() => {
    for (const c of listes) onChange?.(c.id, etat[c.id])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const appliquer = useCallback(
    (id, patch) => {
      setEtat((prev) => {
        const suivant = { ...prev, [id]: { ...prev[id], ...patch } }
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
      <ul className="flex flex-col gap-2">
        {listes.map((c, i) => {
          const e = etat[c.id]
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
    </section>
  )
}
