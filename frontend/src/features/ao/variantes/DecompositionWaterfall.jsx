import { useMemo, useRef, useState } from 'react'
import { ShieldCheck, ShieldAlert, Download } from 'lucide-react'
import { Card, Button } from '../../../ui'
import { formatNumber } from '../../../lib/format'

/* ============================================================================
   AOF104 — Échelle de décomposition (waterfall) A→H, AVEC GARDE D'HONNÊTETÉ.
   ----------------------------------------------------------------------------
   Raconte le passage du calcul HISTORIQUE au calcul COURANT marche par marche
   (« 112 → 126 » sur le cas réel), chaque marche portant son code, son
   libellé et son delta SIGNÉ. Tous ces chiffres viennent du serveur : ce
   composant ne calcule que la GÉOMÉTRIE du dessin, jamais une valeur métier.

   ── D'OÙ VIENNENT LES CHIFFRES, ET LA FORME RÉELLE (RÉPARATION 07/08/2026,
      PACT172) ─────────────────────────────────────────────────────────────
   L'endpoint est `GET /ao/calepinage/variantes/:id/marches/` (AOF62,
   `calepinage_service.calculer_marches`, `aoApi.variantes.decomposition()`).
   Ce composant a longtemps attendu `depart.valeur`, `marche.lettre`,
   `marche.valeur_apres`, `marche.reproduit` et `decomposition.verifie` —
   une forme qui n'a JAMAIS existé côté serveur. La forme RÉELLE, lue dans
   `core/calepinage/echelle.py` :
     { recit, depart: <int>, arrivee: <int>, gain_total: <int>,
       honnete: <bool>, motifs: [<string>…],
       marches: [{code, libelle, modules, delta, attendu}] }
   `recit` (`Echelle.recit()`) et les `motifs` (`verifier_honnetete()`) sont
   des phrases COMPLÈTES déjà rédigées côté serveur — ce composant les AFFICHE,
   il ne compose plus rien. `depart`/`arrivee` sont des ENTIERS, pas des objets
   `{libelle, valeur}` : brancher tel quel sans corriger la lecture aurait
   laissé le bandeau d'honnêteté INERTE (`decomposition?.verifie !== false`
   vaut toujours vrai sur un payload qui ne porte jamais `verifie`) — un
   « Reproduit l'ancien calcul ✓ » qui pourrait mentir devant un maître
   d'ouvrage, exactement le risque que cette garde existe pour supprimer.

   ── LA GARDE D'HONNÊTETÉ (le cœur de la tâche) ────────────────────────────
   Une marche est FAUTIVE quand le serveur lui a déclaré un `attendu` (issu
   d'un ancien calcul figé) que le moteur COURANT ne reproduit plus
   (`marche.modules !== marche.attendu`) ; `honnete` (calculé serveur) reflète
   la même vérité au niveau du récit entier. Dans ce cas :
     • un bandeau rouge « récit non vérifié — ne pas publier » s'affiche,
     • les marches fautives sont NOMMÉES,
     • l'export du panneau est BLOQUÉ, et le bouton porte SON MOTIF (jamais un
       bouton grisé sans explication).
   Sans cette garde, le récit « 112 → 126 » peut devenir silencieusement faux
   devant un maître d'ouvrage — c'est exactement le risque que cette tâche
   supprime.

   ── EXPORT EN IMAGE ───────────────────────────────────────────────────────
   La conversion SVG → PNG est la brique partagée AOF75
   (`features/ao/studio/svgToPng.js`), propriété de la lane `frontend/ao-studio`
   et non livrée par cette lane : elle est INJECTÉE (`exporterImage`) plutôt
   qu'importée — un import statique vers un fichier non encore livré casserait
   le build. Sans exporteur, le bouton d'export est absent (jamais un bouton
   mort).
   ========================================================================== */

// Géométrie du dessin (unités SVG). Aucune de ces valeurs n'est métier.
const MARCHE_L = 84
const MARCHE_ECART = 12
const HAUTEUR = 260
const MARGE_HAUT = 28
const MARGE_BAS = 64

const signe = (v) => (v > 0 ? `+${formatNumber(v, { decimals: 0 })}` : formatNumber(v, { decimals: 0 }))

// Marches FAUTIVES : un `attendu` a été déclaré et le moteur courant ne le
// reproduit plus. Une marche sans `attendu` (aucune attente figée) n'est
// JAMAIS traitée comme fautive.
// eslint-disable-next-line react-refresh/only-export-components -- logique pure co-localisée (testable), même motif que DevisTab.devisTrackCurrent
export function marchesFautives(marches = []) {
  return marches.filter((m) => m.attendu != null && m.modules !== m.attendu)
}

// Barres du waterfall : positions calculées depuis les valeurs SERVEUR.
// `depart` est un NOMBRE (voir en-tête) ; `marche.modules` porte déjà l'état
// CUMULATIF après la marche (même rôle que l'ancien `valeur_apres`).
// eslint-disable-next-line react-refresh/only-export-components -- logique pure co-localisée (testable), même motif que DevisTab.devisTrackCurrent
export function geometrie({ depart = 0, marches = [] }) {
  const valeurs = [depart]
  let courant = depart
  const barres = marches.map((m) => {
    const avant = courant
    const apres = m.modules != null ? m.modules : avant + (m.delta ?? 0)
    courant = apres
    valeurs.push(apres)
    return { ...m, avant, apres }
  })
  const min = Math.min(...valeurs)
  const max = Math.max(...valeurs)
  const etendue = max - min || 1
  const utile = HAUTEUR - MARGE_HAUT - MARGE_BAS
  const y = (v) => MARGE_HAUT + utile - ((v - min) / etendue) * utile
  return {
    barres: barres.map((b, i) => {
      const yA = y(b.avant)
      const yB = y(b.apres)
      return {
        ...b,
        x: i * (MARCHE_L + MARCHE_ECART),
        y: Math.min(yA, yB),
        hauteur: Math.max(Math.abs(yB - yA), 2),
        monte: b.apres >= b.avant,
      }
    }),
    largeur: Math.max(marches.length * (MARCHE_L + MARCHE_ECART) - MARCHE_ECART, MARCHE_L),
    ySocle: y(depart),
    yFin: y(courant),
    total: courant,
  }
}

export function DecompositionWaterfall({ decomposition, exporterImage = null, onExporte }) {
  const svgRef = useRef(null)
  const [exportEnCours, setExportEnCours] = useState(false)

  const depart = decomposition?.depart
  const arrivee = decomposition?.arrivee
  const marches = useMemo(() => decomposition?.marches ?? [], [decomposition])
  const fautives = useMemo(() => marchesFautives(marches), [marches])
  // Le serveur reste l'autorité : `honnete === false` (déclaré) OU une marche
  // fautive (attendu déclaré et non reproduit) suffit à lever le bandeau.
  const verifie = decomposition?.honnete !== false && fautives.length === 0
  const geo = useMemo(() => geometrie({ depart: depart ?? 0, marches }), [depart, marches])

  const motifBlocage = verifie
    ? null
    : (decomposition?.motifs?.length
      ? decomposition.motifs.join(' ')
      : `Récit non vérifié — ${formatNumber(fautives.length || 1, { decimals: 0 })} marche(s) ne reproduisent pas le chiffre attendu.`)

  const exporter = async () => {
    if (!verifie || typeof exporterImage !== 'function' || !svgRef.current) return
    setExportEnCours(true)
    try {
      const image = await exporterImage(svgRef.current, { largeur: 1000 })
      onExporte?.(image)
    } finally {
      setExportEnCours(false)
    }
  }

  if (depart == null || !marches.length) {
    return (
      <Card className="p-4 text-sm text-muted-foreground">
        Décomposition indisponible : le serveur n’a renvoyé aucune marche.
      </Card>
    )
  }

  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="font-display text-lg font-semibold tracking-tight">Décomposition du compte</h2>
          {/* Récit GÉNÉRÉ par le serveur (`Echelle.recit()`) — jamais composé ici. */}
          <p className="mt-0.5 text-sm text-muted-foreground">{decomposition?.recit}</p>
        </div>
        {verifie ? (
          <span className="inline-flex items-center gap-1.5 rounded-md bg-success/10 px-2 py-1 text-xs font-medium text-success">
            <ShieldCheck size={14} aria-hidden="true" /> Reproduit l’ancien calcul ✓
          </span>
        ) : null}
      </div>

      {/* ── Bandeau d'échec : rouge, NOMMANT les marches fautives ─────────── */}
      {!verifie && (
        <div role="alert" className="flex flex-col gap-1 rounded-md border border-destructive bg-destructive/10 p-3">
          <p className="flex items-center gap-1.5 text-sm font-semibold text-destructive">
            <ShieldAlert size={16} aria-hidden="true" /> Récit non vérifié — ne pas publier
          </p>
          <p className="text-sm text-destructive">
            {fautives.length
              ? `Marche(s) fautive(s) : ${fautives.map((m) => `${m.code} — ${m.libelle}`).join(' ; ')}.`
              : motifBlocage}
          </p>
        </div>
      )}

      {/* ── Le waterfall ─────────────────────────────────────────────────── */}
      <div className="-mx-1 overflow-x-auto px-1">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${geo.largeur} ${HAUTEUR}`}
          width={geo.largeur}
          height={HAUTEUR}
          role="img"
          aria-label={`Décomposition en ${formatNumber(marches.length, { decimals: 0 })} marches, de `
            + `${formatNumber(depart, { decimals: 0 })} à ${formatNumber(arrivee ?? geo.total, { decimals: 0 })}.`}
          className="max-w-none"
        >
          <line
            x1="0" x2={geo.largeur} y1={geo.ySocle} y2={geo.ySocle}
            style={{ stroke: 'var(--border)' }} strokeDasharray="4 4"
          />
          {geo.barres.map((b) => (
            <g key={b.code} data-marche={b.code}>
              <rect
                x={b.x} y={b.y} width={MARCHE_L} height={b.hauteur} rx="3"
                style={{
                  fill: fautives.some((f) => f.code === b.code)
                    ? 'var(--destructive)'
                    : b.monte ? 'var(--success)' : 'var(--warning)',
                }}
              />
              <text
                x={b.x + MARCHE_L / 2} y={b.y - 6} textAnchor="middle"
                style={{ fill: 'var(--foreground)', fontSize: '13px', fontWeight: 600 }}
              >
                {signe(b.delta ?? b.apres - b.avant)}
              </text>
              <text
                x={b.x + MARCHE_L / 2} y={HAUTEUR - MARGE_BAS + 20} textAnchor="middle"
                style={{ fill: 'var(--foreground)', fontSize: '13px', fontWeight: 700 }}
              >
                {b.code}
              </text>
              <text
                x={b.x + MARCHE_L / 2} y={HAUTEUR - MARGE_BAS + 38} textAnchor="middle"
                style={{ fill: 'var(--muted-foreground)', fontSize: '11px' }}
              >
                {b.libelle}
              </text>
            </g>
          ))}
        </svg>
      </div>

      {/* ── Export : bloqué AVEC son motif, jamais un bouton grisé muet ───── */}
      {typeof exporterImage === 'function' && (
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="outline" disabled={!verifie || exportEnCours} onClick={exporter}>
            <Download size={14} aria-hidden="true" />
            {verifie ? 'Exporter pour la planche' : 'Export bloqué'}
          </Button>
          {motifBlocage && <span className="text-xs text-destructive">{motifBlocage}</span>}
        </div>
      )}
    </Card>
  )
}

export default DecompositionWaterfall
