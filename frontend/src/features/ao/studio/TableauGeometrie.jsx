import { useEffect, useRef, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { Button, IconButton } from '../../../ui'
import { PROVENANCE_ORDER, provenanceLabel } from '../provenance'
import { appliquerSiValide } from './snap'

/* ============================================================================
   AOF77 — Tableau de géométrie ÉDITABLE au clavier : la condition du gate a11y.
   ----------------------------------------------------------------------------
   Un éditeur graphique est un trou d'accessibilité par nature : `Selection`
   (AOF76) ne rend la géométrie manipulable qu'À LA SOURIS (poignées, pointer
   events). Ce tableau est la SECONDE VOIE, sans laquelle un utilisateur clavier
   ne peut ni créer ni corriger un sommet ou un obstacle — condition du plancher
   AA, pas un bonus.

   **Historique PARTAGÉ.** Ce composant appelle `onGeometrie(points, libelle)`
   avec EXACTEMENT le même contrat que `Selection.jsx` (AOF76) : le propriétaire
   de l'atelier branche les deux voies sur le MÊME `appliquer` d'`useHistoire`
   (AOF76 encore) — un « annuler » défait donc indifféremment un geste de
   souris ou une saisie de tableau.

   **Garde de validité asymétrique, et c'est DÉLIBÉRÉ.** `Selection.jsx` gate
   TOUTE transformation par `appliquerSiValide` parce qu'elle opère sur un
   contour DÉJÀ VALIDE (déplacer/redimensionner/pivoter ne doit jamais le
   casser). Ce tableau doit AUSSI permettre de CONSTRUIRE un contour depuis
   zéro : trois sommets ajoutés par défaut sur une même droite (aire nulle)
   sont un état de TRAVAIL EN COURS, pas une géométrie qu'on s'apprête à
   publier. La porte se pose donc différemment :
     · AJOUTER un sommet est TOUJOURS accepté (on étend un tracé en cours) ;
     · MODIFIER (x/y d'un sommet existant) ou SUPPRIMER passe par la MÊME
       garde que la souris dès que le contour compte ≥ 3 sommets — en dessous,
       ce n'est pas encore un contour publiable, la garder serait un faux refus.
   Aucune voie ne peut donc jamais laisser une manipulation d'un contour DÉJÀ
   VALIDE produire un nœud papillon ou une aire nulle.

   **Obstacles : rectangle (x0, x1, y0, y1) + dégagement + provenance.** C'est
   la forme CANONIQUE du modèle serveur (`ObstacleAO.rect_x0_m…rect_y1_m`,
   `apps/ao/models.py`) — le format le plus courant, éditable sans outil de
   dessin. `provenance.js` (AOF9) reste la SEULE source de vérité du vocabulaire
   de provenance : ce fichier ne le réinvente pas.
   ========================================================================== */

const MIN_SOMMETS_PUBLIABLE = 3

function versNombre(valeur) {
  if (valeur === '' || valeur == null) return null
  const n = Number(String(valeur).replace(',', '.'))
  return Number.isFinite(n) ? n : null
}

export function lettreDe(index) {
  const i = Math.max(0, Math.trunc(Number(index) || 0))
  return String.fromCharCode(65 + (i % 26)) + (i >= 26 ? String(Math.floor(i / 26)) : '')
}

/**
 * Garde d'ÉDITION/SUPPRESSION d'un sommet EXISTANT. En dessous de 3 sommets,
 * le contour est un brouillon (aucune aire ni auto-intersection à défendre) :
 * on laisse passer. À partir de 3, c'est EXACTEMENT `appliquerSiValide` de
 * `Selection.jsx` — la même porte, quelle que soit la voie.
 */
export function appliquerEditionGeometrie(avant, apres) {
  if (!Array.isArray(apres) || apres.length < MIN_SOMMETS_PUBLIABLE) {
    return { points: apres, valide: true, raison: null, message: null }
  }
  return appliquerSiValide(avant, apres)
}

/** Validité d'un obstacle rectangle — `null` si conforme, message FR sinon. */
export function verifierObstacleRectangle(obstacle) {
  const x0 = versNombre(obstacle?.rectX0M)
  const x1 = versNombre(obstacle?.rectX1M)
  const y0 = versNombre(obstacle?.rectY0M)
  const y1 = versNombre(obstacle?.rectY1M)
  if (x0 != null && x1 != null && x1 <= x0) {
    return 'x1 doit être strictement supérieur à x0.'
  }
  if (y0 != null && y1 != null && y1 <= y0) {
    return 'y1 doit être strictement supérieur à y0.'
  }
  const degagement = versNombre(obstacle?.degagementM)
  if (degagement != null && degagement < 0) {
    return 'Le dégagement ne peut pas être négatif.'
  }
  return null
}

function Champ({ id, label, value, onChange, onBlur, disabled }) {
  return (
    <div className="flex min-w-[5.5rem] flex-col gap-0.5">
      <label htmlFor={id} className="sr-only">{label}</label>
      <input
        id={id}
        type="text"
        inputMode="decimal"
        autoComplete="off"
        aria-label={label}
        disabled={disabled}
        className="h-8 w-full rounded-md border border-input bg-card px-2 text-sm text-foreground shadow-ui-xs focus-ring disabled:cursor-not-allowed disabled:opacity-60"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
      />
    </div>
  )
}

// Buffer de saisie LOCAL par cellule : une valeur intermédiaire non-finie
// (« -», « 1,», champ vidé) ne doit jamais être écrasée par la prop tant que
// l'utilisateur n'a pas produit un nombre valide — sinon taper « - » puis
// « 5 » réinitialiserait le champ entre les deux frappes.
function useBrouillon(valeurExterne) {
  const [brouillon, setBrouillon] = useState(() => (valeurExterne == null ? '' : String(valeurExterne)))
  const derniereExterne = useRef(valeurExterne)
  useEffect(() => {
    if (derniereExterne.current !== valeurExterne) {
      derniereExterne.current = valeurExterne
      setBrouillon(valeurExterne == null ? '' : String(valeurExterne))
    }
  }, [valeurExterne])
  return [brouillon, setBrouillon]
}

function ChampNombre({
  id, label, valeurExterne, onValide, onTerminer, disabled,
}) {
  const [brouillon, setBrouillon] = useBrouillon(valeurExterne)
  return (
    <Champ
      id={id}
      label={label}
      value={brouillon}
      disabled={disabled}
      onChange={(texte) => {
        setBrouillon(texte)
        const n = versNombre(texte)
        if (n != null) onValide(n)
      }}
      onBlur={onTerminer}
    />
  )
}

export function TableauGeometrie({
  points = [],
  obstacles = [],
  onGeometrie,
  onRefus,
  onObstacles,
  onRefusObstacle,
  onTerminer,
  provenances = PROVENANCE_ORDER,
}) {
  const [annonce, setAnnonce] = useState('')
  const compteRef = useRef({ sommets: points.length, obstacles: obstacles.length })

  // Annonce `aria-live` — UNIQUEMENT quand un COMPTE change (pas à chaque
  // frappe qui ne fait que déplacer un sommet déjà existant).
  useEffect(() => {
    const avant = compteRef.current
    if (avant.sommets !== points.length || avant.obstacles !== obstacles.length) {
      compteRef.current = { sommets: points.length, obstacles: obstacles.length }
      setAnnonce(
        `${points.length} sommet${points.length > 1 ? 's' : ''} — `
        + `${obstacles.length} obstacle${obstacles.length > 1 ? 's' : ''}.`,
      )
    }
  }, [points.length, obstacles.length])

  // ── Sommets ────────────────────────────────────────────────────────────
  // `fusion` : les frappes successives dans LA MÊME cellule (« 1 » puis « 0 »
  // pour saisir 10) fusionnent en UN SEUL cran d'annulation — même contrat
  // que le glissement continu de `Selection.jsx` (AOF76). La fusion se ferme
  // au `blur` du champ (`onTerminer`, câblé sur `Champ.onBlur`).
  const majSommet = (index, axe, valeur) => {
    const suivants = points.map((p, i) => (i === index ? { ...p, [axe]: valeur } : p))
    const r = appliquerEditionGeometrie(points, suivants)
    if (!r.valide) { onRefus?.(r.message); return }
    onGeometrie?.(r.points, `Modifier ${axe} du sommet ${lettreDe(index)}`, { fusion: `tableau-sommet-${index}-${axe}` })
  }

  const ajouterSommet = () => {
    const dernier = points[points.length - 1] ?? { x: -1, y: -1 }
    const suivant = { x: dernier.x + 1, y: dernier.y + 1 }
    // AJOUT toujours accepté : voir le commentaire d'en-tête (garde asymétrique).
    onGeometrie?.([...points, suivant], `Ajouter le sommet ${lettreDe(points.length)}`)
  }

  const supprimerSommet = (index) => {
    const suivants = points.filter((_, i) => i !== index)
    const r = appliquerEditionGeometrie(points, suivants)
    if (!r.valide) { onRefus?.(r.message); return }
    onGeometrie?.(r.points, `Supprimer le sommet ${lettreDe(index)}`)
  }

  // ── Obstacles ──────────────────────────────────────────────────────────
  const majObstacle = (id, patch) => {
    const suivants = obstacles.map((o) => (o.id === id ? { ...o, ...patch } : o))
    const message = verifierObstacleRectangle(suivants.find((o) => o.id === id))
    if (message) { onRefusObstacle?.(message); return }
    const champ = Object.keys(patch)[0]
    onObstacles?.(suivants, 'Modifier un obstacle', { fusion: `tableau-obstacle-${id}-${champ}` })
  }

  const ajouterObstacle = () => {
    const repere = lettreDe(obstacles.length)
    const nouvel = {
      id: `obs-${repere}-${Date.now()}`,
      repere,
      rectX0M: 0,
      rectX1M: 1,
      rectY0M: 0,
      rectY1M: 1,
      degagementM: null,
      provenance: provenances[0],
    }
    onObstacles?.([...obstacles, nouvel], `Ajouter l'obstacle ${repere}`)
  }

  const supprimerObstacle = (id) => {
    onObstacles?.(obstacles.filter((o) => o.id !== id), 'Supprimer un obstacle')
  }

  return (
    <div className="flex flex-col gap-4" data-tableau-geometrie={`${points.length}:${obstacles.length}`}>
      <p role="status" aria-live="polite" className="text-xs text-muted-foreground">
        {annonce || `${points.length} sommet${points.length > 1 ? 's' : ''} — ${obstacles.length} obstacle${obstacles.length > 1 ? 's' : ''}.`}
      </p>

      {/* ── Sommets ──────────────────────────────────────────────────────── */}
      <section className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Sommets</h4>
          <Button size="sm" variant="outline" onClick={ajouterSommet}>
            <Plus aria-hidden="true" size={14} />
            Ajouter un sommet
          </Button>
        </div>
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full min-w-[20rem] border-collapse text-sm">
            <caption className="sr-only">Sommets du contour, éditables en mètres.</caption>
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th scope="col" className="py-1.5 pl-2 font-medium">Sommet</th>
                <th scope="col" className="py-1.5 pl-2 font-medium">x (m)</th>
                <th scope="col" className="py-1.5 pl-2 font-medium">y (m)</th>
                <th scope="col" className="py-1.5 pl-2 pr-2 font-medium">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {points.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-2 pl-2 text-muted-foreground">
                    Aucun sommet — ajoutez-en un pour commencer le contour.
                  </td>
                </tr>
              )}
              {points.map((p, i) => {
                const lettre = lettreDe(i)
                return (
                  <tr key={`sommet-${i}`} className="border-b border-border/60 last:border-b-0">
                    <th scope="row" className="py-1.5 pl-2 text-left font-medium">{lettre}</th>
                    <td className="py-1.5 pl-2">
                      <ChampNombre
                        id={`ao-geo-sommet-${i}-x`}
                        label={`x (m) — Sommet ${lettre}`}
                        valeurExterne={p.x}
                        onValide={(n) => majSommet(i, 'x', n)}
                        onTerminer={onTerminer}
                      />
                    </td>
                    <td className="py-1.5 pl-2">
                      <ChampNombre
                        id={`ao-geo-sommet-${i}-y`}
                        label={`y (m) — Sommet ${lettre}`}
                        valeurExterne={p.y}
                        onValide={(n) => majSommet(i, 'y', n)}
                        onTerminer={onTerminer}
                      />
                    </td>
                    <td className="py-1.5 pl-2 pr-2 text-right">
                      <IconButton
                        label={`Supprimer le sommet ${lettre}`}
                        size="icon-sm"
                        onClick={() => supprimerSommet(i)}
                      >
                        <Trash2 size={14} aria-hidden="true" />
                      </IconButton>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* ── Obstacles ────────────────────────────────────────────────────── */}
      <section className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Obstacles</h4>
          <Button size="sm" variant="outline" onClick={ajouterObstacle}>
            <Plus aria-hidden="true" size={14} />
            Ajouter un obstacle
          </Button>
        </div>
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full min-w-[36rem] border-collapse text-sm">
            <caption className="sr-only">
              Obstacles rectangulaires : x0, x1, y0, y1, dégagement, provenance.
            </caption>
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th scope="col" className="py-1.5 pl-2 font-medium">Repère</th>
                <th scope="col" className="py-1.5 pl-2 font-medium">x0 (m)</th>
                <th scope="col" className="py-1.5 pl-2 font-medium">x1 (m)</th>
                <th scope="col" className="py-1.5 pl-2 font-medium">y0 (m)</th>
                <th scope="col" className="py-1.5 pl-2 font-medium">y1 (m)</th>
                <th scope="col" className="py-1.5 pl-2 font-medium">Dégagement (m)</th>
                <th scope="col" className="py-1.5 pl-2 font-medium">Provenance</th>
                <th scope="col" className="py-1.5 pl-2 pr-2 font-medium">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {obstacles.length === 0 && (
                <tr>
                  <td colSpan={8} className="py-2 pl-2 text-muted-foreground">
                    Aucun obstacle — ajoutez-en un pour le relevé.
                  </td>
                </tr>
              )}
              {obstacles.map((o) => (
                <tr key={o.id} className="border-b border-border/60 last:border-b-0">
                  <th scope="row" className="py-1.5 pl-2 text-left font-medium">{o.repere}</th>
                  <td className="py-1.5 pl-2">
                    <ChampNombre
                      id={`ao-geo-obs-${o.id}-x0`}
                      label={`x0 (m) — Obstacle ${o.repere}`}
                      valeurExterne={o.rectX0M}
                      onValide={(n) => majObstacle(o.id, { rectX0M: n })}
                      onTerminer={onTerminer}
                    />
                  </td>
                  <td className="py-1.5 pl-2">
                    <ChampNombre
                      id={`ao-geo-obs-${o.id}-x1`}
                      label={`x1 (m) — Obstacle ${o.repere}`}
                      valeurExterne={o.rectX1M}
                      onValide={(n) => majObstacle(o.id, { rectX1M: n })}
                      onTerminer={onTerminer}
                    />
                  </td>
                  <td className="py-1.5 pl-2">
                    <ChampNombre
                      id={`ao-geo-obs-${o.id}-y0`}
                      label={`y0 (m) — Obstacle ${o.repere}`}
                      valeurExterne={o.rectY0M}
                      onValide={(n) => majObstacle(o.id, { rectY0M: n })}
                      onTerminer={onTerminer}
                    />
                  </td>
                  <td className="py-1.5 pl-2">
                    <ChampNombre
                      id={`ao-geo-obs-${o.id}-y1`}
                      label={`y1 (m) — Obstacle ${o.repere}`}
                      valeurExterne={o.rectY1M}
                      onValide={(n) => majObstacle(o.id, { rectY1M: n })}
                      onTerminer={onTerminer}
                    />
                  </td>
                  <td className="py-1.5 pl-2">
                    <ChampNombre
                      id={`ao-geo-obs-${o.id}-degagement`}
                      label={`Dégagement (m) — Obstacle ${o.repere}`}
                      valeurExterne={o.degagementM}
                      onValide={(n) => majObstacle(o.id, { degagementM: n })}
                      onTerminer={onTerminer}
                    />
                  </td>
                  <td className="py-1.5 pl-2">
                    <label htmlFor={`ao-geo-obs-${o.id}-provenance`} className="sr-only">
                      {`Provenance — Obstacle ${o.repere}`}
                    </label>
                    <select
                      id={`ao-geo-obs-${o.id}-provenance`}
                      aria-label={`Provenance — Obstacle ${o.repere}`}
                      className="h-8 w-full rounded-md border border-input bg-card px-1.5 text-sm text-foreground shadow-ui-xs focus-ring"
                      value={o.provenance}
                      onChange={(e) => majObstacle(o.id, { provenance: e.target.value })}
                    >
                      {provenances.map((cle) => (
                        <option key={cle} value={cle}>{provenanceLabel(cle)}</option>
                      ))}
                    </select>
                  </td>
                  <td className="py-1.5 pl-2 pr-2 text-right">
                    <IconButton
                      label={`Supprimer l'obstacle ${o.repere}`}
                      size="icon-sm"
                      onClick={() => supprimerObstacle(o.id)}
                    >
                      <Trash2 size={14} aria-hidden="true" />
                    </IconButton>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

export default TableauGeometrie
