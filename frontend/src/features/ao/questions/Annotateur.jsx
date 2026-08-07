import { useCallback, useEffect, useRef, useState } from 'react'
import { ImagePlus, Trash2 } from 'lucide-react'
import { Card, Button, EmptyState } from '../../../ui'
import RepereMarker, { lettreDe, deplacer, redimensionner, RAYON_MIN } from './RepereMarker'

/* ============================================================================
   AOF106 — Annotateur d'image : poser des repères (cercle rouge + lettre).
   ----------------------------------------------------------------------------
   La méthode est VALIDÉE PAR LE CLIENT : il répond sur l'image, pas sur du
   texte abstrait. L'outil doit donc être RAPIDE (Done : 10 repères en moins de
   deux minutes) — un clic = un repère, sans dialogue intermédiaire.

   ── L'IMAGE DE FOND ───────────────────────────────────────────────────────
   Trois sources, toutes traitées identiquement comme une URL/data-URL :
     • une photo, chargée ici (`<input type="file">` → data-URL) ;
     • une page de PDF rasterisée (AOF79, lane document) — passée en `imageSrc` ;
     • l'export d'une vue d'atelier par `svgToPng` (AOF75, lane studio) —
       passé en `imageSrc`.
   Les deux dernières briques appartiennent à d'AUTRES lanes : elles sont
   INJECTÉES par la prop `imageSrc`, jamais importées (un import statique vers
   un fichier non encore livré casserait le build de l'app).

   ── COORDONNÉES ───────────────────────────────────────────────────────────
   Tout est stocké en UNITÉS DE VIEWBOX (0..`TAILLE`), jamais en pixels : le
   rendu reste net à n'importe quelle résolution d'export (Done : « rendu net
   en haute résolution ») et un redimensionnement d'écran ne bouge aucun repère.

   ── RENUMÉROTATION ────────────────────────────────────────────────────────
   La lettre n'est jamais stockée (voir `RepereMarker.lettreDe`) : elle est
   dérivée de l'index. Supprimer un repère renumérote donc TOUT, mécaniquement.
   ========================================================================== */

export const TAILLE = 1000 // côté du viewBox (unités d'annotation)
const RAYON_DEFAUT = 46

const clamp = (v, min, max) => Math.min(Math.max(v, min), max)

// Conversion pointeur → unités de viewBox. GARDE ANTI-NaN : un conteneur de
// taille 0 (élément caché, environnement de test sans layout) retomberait sur
// une division par zéro — on utilise alors l'échelle 1:1 du viewBox.
function versViewBox(svg, clientX, clientY) {
  const rect = svg.getBoundingClientRect()
  const l = rect.width || TAILLE
  const h = rect.height || TAILLE
  return {
    x: clamp(((clientX - rect.left) / l) * TAILLE, 0, TAILLE),
    y: clamp(((clientY - rect.top) / h) * TAILLE, 0, TAILLE),
  }
}

let compteur = 0
const nouvelId = () => { compteur += 1; return `rp-${compteur}` }

export function Annotateur({
  imageSrc = null,
  reperesInitiaux = [],
  onChange,
  onOuvrirFiche,
  // PACT170 — `onSvgRef` expose le NŒUD SVG (image de fond + repères) à
  // l'appelant, pour que l'export « prêt à coller » (AOF107) puisse le
  // rasteriser avec `svgToPng` (AOF75). Sans lui, l'export ne pouvait porter
  // que la photo NUE : la liste numérotée aurait renvoyé à des repères
  // invisibles sur l'image — exactement ce que la méthode évite.
  // C'est un RAPPEL, pas un objet ref : muter la ref d'un parent depuis un
  // enfant est un écrit sur une prop (refusé par `react-hooks/immutability`).
  // Le parent reçoit le nœud et le range dans SA propre ref.
  onSvgRef = null,
  legende = 'Cliquez sur l’image pour poser un repère.',
}) {
  const svgRef = useRef(null)
  const glisseRef = useRef(null)
  const [image, setImage] = useState(imageSrc)
  const [reperes, setReperes] = useState(reperesInitiaux)
  const [selection, setSelection] = useState(null)

  // `image` combine la prop `imageSrc` ET une éventuelle surcharge locale
  // (fichier chargé via `chargerFichier`) : quand `imageSrc` change (nouvelle
  // source injectée par un appelant), on resynchronise — ajustement pendant
  // le rendu (pattern React recommandé) plutôt qu'un `useEffect`, qui
  // provoquerait un rendu en cascade évitable.
  const [derniereImageSrc, setDerniereImageSrc] = useState(imageSrc)
  if (imageSrc !== derniereImageSrc) {
    setDerniereImageSrc(imageSrc)
    setImage(imageSrc)
  }

  // `onChange` est notifié à chaque changement de la LISTE, jamais à chaque
  // rendu du parent : un appelant qui passe une lambda inline ne doit pas
  // déclencher une boucle de rendu.
  const onChangeRef = useRef(onChange)
  useEffect(() => { onChangeRef.current = onChange })
  useEffect(() => { onChangeRef.current?.(reperes) }, [reperes])

  const chargerFichier = (e) => {
    const fichier = e.target.files?.[0]
    if (!fichier) return
    const lecteur = new FileReader()
    lecteur.onload = () => setImage(String(lecteur.result))
    lecteur.readAsDataURL(fichier)
  }

  const ajouter = useCallback((x, y) => {
    const id = nouvelId()
    setReperes((prev) => [...prev, { id, x, y, r: RAYON_DEFAUT }])
    setSelection(id)
  }, [])

  // UN clic = UN repère (aucun dialogue intermédiaire : c'est la condition du
  // « 10 repères en moins de deux minutes »).
  const poser = (e) => {
    if (!svgRef.current) return
    const { x, y } = versViewBox(svgRef.current, e.clientX, e.clientY)
    ajouter(x, y)
  }

  // Voie clavier : le repère naît au centre, puis se place aux flèches.
  const poserAuCentre = () => ajouter(TAILLE / 2, TAILLE / 2)

  const supprimer = useCallback((id) => {
    setReperes((prev) => prev.filter((r) => r.id !== id))
    setSelection((prev) => (prev === id ? null : prev))
  }, [])

  const deplacerRepere = useCallback((id, delta) => {
    setReperes((prev) => prev.map((r) => (r.id === id ? deplacer(r, delta, TAILLE) : r)))
  }, [])

  const redimensionnerRepere = useCallback((id, delta) => {
    setReperes((prev) => prev.map((r) => (r.id === id ? redimensionner(r, delta) : r)))
  }, [])

  const debutGlisser = useCallback((id) => {
    glisseRef.current = id
    setSelection(id)
  }, [])

  const glisser = (e) => {
    const id = glisseRef.current
    if (!id || !svgRef.current) return
    const { x, y } = versViewBox(svgRef.current, e.clientX, e.clientY)
    setReperes((prev) => prev.map((r) => (r.id === id ? { ...r, x, y } : r)))
  }

  const finGlisser = () => { glisseRef.current = null }

  if (!image) {
    return (
      <Card className="flex flex-col gap-3 p-4">
        <EmptyState
          icon={ImagePlus}
          title="Aucune image à annoter"
          description="Chargez une photo, une page de plan rasterisée, ou l’export d’une vue d’atelier."
        />
        <input
          type="file"
          accept="image/*"
          aria-label="Charger une image à annoter"
          onChange={chargerFichier}
          className="mx-auto text-sm"
        />
      </Card>
    )
  }

  return (
    <Card className="flex flex-col gap-3 p-4 lg:flex-row">
      <div className="min-w-0 flex-1">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-muted-foreground">{legende}</p>
          {/* Voie CLAVIER d'ajout : sans elle, poser un repère exigerait une
              souris — le gate a11y (AOF188) refuserait l'écran. */}
          <Button size="sm" variant="outline" onClick={poserAuCentre}>
            Ajouter un repère
          </Button>
        </div>
        <svg
          ref={(noeud) => {
            svgRef.current = noeud
            if (onSvgRef) onSvgRef(noeud)
          }}
          viewBox={`0 0 ${TAILLE} ${TAILLE}`}
          className="w-full rounded-md border border-border bg-muted/20"
          role="group"
          aria-label="Annotateur d’image — cliquez pour poser un repère"
          onClick={poser}
          onPointerMove={glisser}
          onPointerUp={finGlisser}
          onPointerLeave={finGlisser}
        >
          <image href={image} x="0" y="0" width={TAILLE} height={TAILLE} preserveAspectRatio="xMidYMid meet" />
          {reperes.map((r, i) => (
            <RepereMarker
              key={r.id}
              repere={r}
              lettre={lettreDe(i)}
              selectionne={selection === r.id}
              onSelect={setSelection}
              onDeplacer={deplacerRepere}
              onRedimensionner={redimensionnerRepere}
              onSupprimer={supprimer}
              onDebutGlisser={debutGlisser}
            />
          ))}
        </svg>
      </div>

      {/* Liste latérale SYNCHRONISÉE — la lettre y est la même qu'au dessin
          puisqu'elle est dérivée du MÊME index. */}
      <div className="w-full shrink-0 lg:w-56">
        <p className="mb-2 text-sm font-medium">
          {`${reperes.length} repère(s)`}
        </p>
        {reperes.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucun repère posé.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {reperes.map((r, i) => (
              <li key={r.id} className="flex items-center justify-between gap-2 text-sm">
                {/* Nom accessible DISTINCT de celui du repère dessiné (`Repère
                    X`) : deux éléments portant le même nom rendraient toute
                    spec e2e ambiguë (mode strict Playwright). */}
                <Button
                  size="sm"
                  variant={selection === r.id ? 'secondary' : 'ghost'}
                  aria-label={`Ouvrir la fiche du repère ${lettreDe(i)}`}
                  onClick={() => (onOuvrirFiche ? onOuvrirFiche(r.id, lettreDe(i)) : setSelection(r.id))}
                >
                  {`Repère ${lettreDe(i)}`}
                </Button>
                <Button
                  size="icon-sm"
                  variant="ghost"
                  aria-label={`Supprimer le repère ${lettreDe(i)}`}
                  onClick={() => supprimer(r.id)}
                >
                  <Trash2 size={14} aria-hidden="true" />
                </Button>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-3 text-xs text-muted-foreground">
          {`Au clavier : flèches pour déplacer, + / - pour redimensionner (rayon minimum ${RAYON_MIN}), Suppr pour supprimer.`}
        </p>
      </div>
    </Card>
  )
}

export default Annotateur
