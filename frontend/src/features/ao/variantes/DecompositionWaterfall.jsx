import { useMemo, useRef, useState } from 'react'
import { ShieldCheck, ShieldAlert, Download } from 'lucide-react'
import { Card, Button } from '../../../ui'
import { formatNumber } from '../../../lib/format'

/* ============================================================================
   AOF104 — Échelle de décomposition (waterfall) A→H, AVEC GARDE D'HONNÊTETÉ.
   ----------------------------------------------------------------------------
   Raconte le passage du calcul HISTORIQUE au calcul COURANT marche par marche
   (« 112 → 126 » sur le cas réel), chaque marche portant sa lettre, son
   libellé et son delta SIGNÉ. Tous ces chiffres viennent du serveur
   (`GET /ao/variantes/:id/decomposition/`, AOF11) : ce composant ne calcule
   que la GÉOMÉTRIE du dessin, jamais une valeur métier.

   ── LA GARDE D'HONNÊTETÉ (le cœur de la tâche) ────────────────────────────
   Le serveur signale, marche par marche (`reproduit: false`) et globalement
   (`verifie: false`), qu'une marche NE REPRODUIT PAS le chiffre qu'elle doit
   reproduire. Dans ce cas :
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

// eslint-disable-next-line react-refresh/only-export-components -- logique pure co-localisée (testable), même motif que DevisTab.devisTrackCurrent
export function marchesNonReproduites(marches = []) {
  return marches.filter((m) => m.reproduit === false)
}

// Barres du waterfall : positions calculées depuis les valeurs SERVEUR.
// eslint-disable-next-line react-refresh/only-export-components -- logique pure co-localisée (testable), même motif que DevisTab.devisTrackCurrent
export function geometrie({ depart, marches = [] }) {
  const valeurs = [depart?.valeur ?? 0]
  let courant = depart?.valeur ?? 0
  const barres = marches.map((m) => {
    const avant = courant
    const apres = m.valeur_apres != null ? m.valeur_apres : avant + (m.delta ?? 0)
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
    ySocle: y(depart?.valeur ?? 0),
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
  const fautives = useMemo(() => marchesNonReproduites(marches), [marches])
  // Le serveur reste l'autorité : `verifie === false` OU une marche fautive.
  const verifie = decomposition?.verifie !== false && fautives.length === 0
  const geo = useMemo(() => geometrie({ depart, marches }), [depart, marches])

  const motifBlocage = verifie
    ? null
    : `Récit non vérifié — ${formatNumber(fautives.length || 1, { decimals: 0 })} marche(s) ne reproduisent pas le chiffre attendu.`

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

  if (!depart || !marches.length) {
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
          <p className="mt-0.5 text-sm text-muted-foreground">
            {`${depart.libelle} ${formatNumber(depart.valeur, { decimals: 0 })} `}
            &rarr;
            {` ${arrivee?.libelle ?? 'Calcul courant'} ${formatNumber(arrivee?.valeur ?? geo.total, { decimals: 0 })}`}
          </p>
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
              ? `Marche(s) fautive(s) : ${fautives.map((m) => `${m.lettre} — ${m.libelle}`).join(' ; ')}.`
              : 'Le serveur signale que ce récit ne reproduit pas le calcul historique.'}
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
            + `${formatNumber(depart.valeur, { decimals: 0 })} à ${formatNumber(arrivee?.valeur ?? geo.total, { decimals: 0 })}.`}
          className="max-w-none"
        >
          <line
            x1="0" x2={geo.largeur} y1={geo.ySocle} y2={geo.ySocle}
            style={{ stroke: 'var(--border)' }} strokeDasharray="4 4"
          />
          {geo.barres.map((b) => (
            <g key={b.lettre} data-marche={b.lettre}>
              <rect
                x={b.x} y={b.y} width={MARCHE_L} height={b.hauteur} rx="3"
                style={{
                  fill: b.reproduit === false
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
                {b.lettre}
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
