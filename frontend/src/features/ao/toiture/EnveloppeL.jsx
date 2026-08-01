/* AOF91 — Enveloppe en « L » : UNE surface continue, jamais deux rectangles.
   ----------------------------------------------------------------------------
   C'est le point sur lequel un relevé se perd le plus souvent. Une aile en L
   « c'est deux rectangles » — sauf que non : une rangée qui reste du côté de
   l'aile descend D'UN SEUL TENANT de la barre dans l'aile. Découper le L en deux
   rectangles indépendants oblige chaque morceau à reprendre ses propres rives au
   niveau de la jonction, et le reste de longueur de chaque morceau est perdu au
   lieu de s'additionner. C'est une perte SÈCHE, déjà prouvée côté moteur — et
   cet écran la CHIFFRE au lieu de la commenter.

   La saisie est donc paramétrique et produit un CONTOUR UNIQUE à six sommets :
   il n'existe à aucun moment deux objets qu'un écran ultérieur pourrait traiter
   séparément. */
import { useCallback, useMemo, useState } from 'react'
import { aireM2, contourSeCroise } from './repere'

/* ── Géométrie pure ─────────────────────────────────────────────────────────── */

export const L_REFERENCE = {
  barreLongueurM: 51.1,
  barreProfondeurM: 25.62,
  aileLongueurM: 18.0,
  aileProfondeurM: 12.0,
  coin: 'NE',
}

export const COINS = [
  { cle: 'NE', libelle: 'Nord-est' },
  { cle: 'NO', libelle: 'Nord-ouest' },
  { cle: 'SE', libelle: 'Sud-est' },
  { cle: 'SO', libelle: 'Sud-ouest' },
]

function nombre(v) {
  if (v === null || v === undefined || v === '') return null
  const n = Number(String(v).replace(',', '.'))
  return Number.isFinite(n) ? n : null
}

function m(n) {
  return Number(n).toFixed(2).replace('.', ',')
}

export function validerL(params = {}) {
  const motifs = []
  const L = nombre(params.barreLongueurM)
  const P = nombre(params.barreProfondeurM)
  const La = nombre(params.aileLongueurM)
  const Pa = nombre(params.aileProfondeurM)
  if (!(L > 0) || !(P > 0)) motifs.push('Barre incomplète : longueur et profondeur sont requises.')
  if (!(La > 0) || !(Pa > 0)) motifs.push("Aile incomplète : longueur et profondeur de l'aile sont requises.")
  if (L > 0 && La > 0 && La >= L) {
    motifs.push(
      `Aile (${m(La)} m) aussi longue que la barre (${m(L)} m) : c’est un rectangle, pas un L.`,
    )
  }
  return { valide: motifs.length === 0, motifs }
}

/**
 * LE contour — six sommets, un seul tenant. `coin` place l'aile ; le repère est
 * normalisé de sorte que le coin bas-gauche du rectangle englobant soit (0, 0).
 */
export function contourL(params = {}) {
  const L = nombre(params.barreLongueurM) ?? 0
  const P = nombre(params.barreProfondeurM) ?? 0
  const La = Math.min(nombre(params.aileLongueurM) ?? 0, L)
  const Pa = nombre(params.aileProfondeurM) ?? 0
  const coin = String(params.coin ?? 'NE').toUpperCase()
  const H = P + Pa

  let pts =
    coin[1] === 'E'
      ? [
          { x: 0, y: 0 },
          { x: L, y: 0 },
          { x: L, y: H },
          { x: L - La, y: H },
          { x: L - La, y: P },
          { x: 0, y: P },
        ]
      : [
          { x: 0, y: 0 },
          { x: L, y: 0 },
          { x: L, y: P },
          { x: La, y: P },
          { x: La, y: H },
          { x: 0, y: H },
        ]

  if (coin[0] === 'S') {
    // L'aile passe au sud : on retourne le repère et on rétablit le sens.
    pts = pts.map((p) => ({ x: p.x, y: H - p.y })).reverse()
  }
  return pts
}

/** Emprise E-O de l'aile, dans le repère du contour. */
export function empriseAile(params = {}) {
  const L = nombre(params.barreLongueurM) ?? 0
  const La = Math.min(nombre(params.aileLongueurM) ?? 0, L)
  return String(params.coin ?? 'NE').toUpperCase()[1] === 'E'
    ? { debut: L - La, fin: L }
    : { debut: 0, fin: La }
}

/**
 * Étendue N-S utile à l'abscisse `x` — la généralisation de `band()` au contour
 * concave. C'est elle qui prouve la continuité : sous l'aile, la bande va d'un
 * bord à l'autre SANS coupure.
 */
export function bandeL(params = {}, x) {
  const P = nombre(params.barreProfondeurM) ?? 0
  const Pa = nombre(params.aileProfondeurM) ?? 0
  const sud = String(params.coin ?? 'NE').toUpperCase()[0] === 'S'
  const aile = empriseAile(params)
  const sousAile = x >= aile.debut - 1e-9 && x <= aile.fin + 1e-9
  if (sousAile) return { ymin: 0, ymax: P + Pa, sousAile: true }
  return sud ? { ymin: Pa, ymax: Pa + P, sousAile: false } : { ymin: 0, ymax: P, sousAile: false }
}

/** Modules tenant dans une bande, rives comprises. */
export function modulesParBande(longueur, moduleM, riveM = 0.35) {
  const utile = Number(longueur) - 2 * Number(riveM)
  if (!(utile > 0) || !(Number(moduleM) > 0)) return 0
  return Math.floor(utile / Number(moduleM) + 1e-9)
}

/**
 * LA PREUVE CHIFFRÉE. Sous l'aile, un contour unique donne une bande de
 * (P + Pa) ; deux rectangles indépendants donnent P et Pa séparément, chacun
 * reprenant ses rives et perdant son reste. La différence, multipliée par le
 * nombre de bandes concernées, est la perte sèche du découpage.
 */
export function perteDuDecoupage(params = {}, { moduleM = 4.7, riveM = 0.35, pasM = 1.134 } = {}) {
  const P = nombre(params.barreProfondeurM) ?? 0
  const Pa = nombre(params.aileProfondeurM) ?? 0
  const aile = empriseAile(params)
  const largeurAile = Math.max(0, aile.fin - aile.debut)
  const bandes = pasM > 0 ? Math.floor((largeurAile - 2 * riveM) / pasM + 1e-9) : 0
  const continu = modulesParBande(P + Pa, moduleM, riveM)
  const decoupe = modulesParBande(P, moduleM, riveM) + modulesParBande(Pa, moduleM, riveM)
  const bandesSousAile = Math.max(0, bandes)
  return {
    bandesSousAile,
    continu,
    decoupe,
    parBande: continu - decoupe,
    perte: bandesSousAile * (continu - decoupe),
  }
}

/* ── Écran ──────────────────────────────────────────────────────────────────── */

export default function EnveloppeL({
  valeurInitiale = L_REFERENCE,
  moduleProfondeurM = 4.7,
  modulePasM = 1.134,
  riveM = 0.35,
  onValider,
}) {
  const [params, setParams] = useState(valeurInitiale)
  const [refus, setRefus] = useState(null)

  const majChamp = useCallback(
    (champ, valeur) => setParams((p) => ({ ...p, [champ]: valeur })),
    [],
  )

  const controle = useMemo(() => validerL(params), [params])
  const contour = useMemo(() => contourL(params), [params])
  const aile = useMemo(() => empriseAile(params), [params])
  const perte = useMemo(
    () => perteDuDecoupage(params, { moduleM: moduleProfondeurM, riveM, pasM: modulePasM }),
    [params, moduleProfondeurM, riveM, modulePasM],
  )

  const bandeSousAile = useMemo(
    () => bandeL(params, (aile.debut + aile.fin) / 2),
    [params, aile],
  )
  const bandeHorsAile = useMemo(
    () => bandeL(params, aile.debut > 0 ? aile.debut / 2 : aile.fin + 1),
    [params, aile],
  )

  const largeur = Math.max(...contour.map((p) => p.x), 1)
  const hauteur = Math.max(...contour.map((p) => p.y), 1)

  const valider = useCallback(() => {
    const c = validerL(params)
    if (!c.valide) {
      setRefus(c.motifs)
      return
    }
    const sommets = contourL(params)
    if (contourSeCroise(sommets)) {
      setRefus(['Contour refusé : les côtés se recoupent.'])
      return
    }
    setRefus(null)
    onValider?.({ ...params, sommets, aireM2: aireM2(sommets) })
  }, [params, onValider])

  return (
    <section className="ao-enveloppe-l" data-ao-enveloppe="l">
      <h3>Enveloppe en L</h3>

      <p className="ao-l-regle" data-ao-l-regle>
        Le L se saisit comme UNE surface continue. Jamais deux rectangles&nbsp;: une rangée
        qui reste du côté de l’aile descend d’un seul tenant de la barre dans l’aile, et
        le découpage est une perte sèche.
      </p>

      <div className="ao-l-parametres">
        <label className="ao-champ" htmlFor="ao-l-barre-longueur">
          <span>Barre — longueur (m)</span>
          <input
            id="ao-l-barre-longueur"
            className="form-control"
            type="text"
            inputMode="decimal"
            value={params.barreLongueurM ?? ''}
            onChange={(e) => majChamp('barreLongueurM', e.target.value)}
          />
        </label>
        <label className="ao-champ" htmlFor="ao-l-barre-profondeur">
          <span>Barre — profondeur (m)</span>
          <input
            id="ao-l-barre-profondeur"
            className="form-control"
            type="text"
            inputMode="decimal"
            value={params.barreProfondeurM ?? ''}
            onChange={(e) => majChamp('barreProfondeurM', e.target.value)}
          />
        </label>
        <label className="ao-champ" htmlFor="ao-l-aile-longueur">
          <span>Aile — longueur (m)</span>
          <input
            id="ao-l-aile-longueur"
            className="form-control"
            type="text"
            inputMode="decimal"
            value={params.aileLongueurM ?? ''}
            onChange={(e) => majChamp('aileLongueurM', e.target.value)}
          />
        </label>
        <label className="ao-champ" htmlFor="ao-l-aile-profondeur">
          <span>Aile — profondeur (m)</span>
          <input
            id="ao-l-aile-profondeur"
            className="form-control"
            type="text"
            inputMode="decimal"
            value={params.aileProfondeurM ?? ''}
            onChange={(e) => majChamp('aileProfondeurM', e.target.value)}
          />
        </label>
        <label className="ao-champ" htmlFor="ao-l-coin">
          <span>Coin de l’aile</span>
          <select
            id="ao-l-coin"
            className="form-select"
            value={params.coin ?? 'NE'}
            onChange={(e) => majChamp('coin', e.target.value)}
          >
            {COINS.map((c) => (
              <option key={c.cle} value={c.cle}>
                {c.libelle}
              </option>
            ))}
          </select>
        </label>
      </div>

      {refus && (
        <ul role="alert" data-ao-l-refus={refus.length}>
          {refus.map((motif) => (
            <li key={motif}>{motif}</li>
          ))}
        </ul>
      )}

      <svg
        viewBox={`-1 -1 ${largeur + 2} ${hauteur + 2}`}
        role="img"
        aria-label="Enveloppe en L, contour unique"
        data-ao-canvas="enveloppe-l"
      >
        {/* UN polygone. Il n'existe à aucun moment deux objets séparés. */}
        <polygon
          points={contour.map((p) => `${p.x},${p.y}`).join(' ')}
          className="ao-l-contour"
          data-ao-l-sommets={contour.length}
        />
        {/* La bande qui traverse : c'est elle que le découpage couperait en deux. */}
        <rect
          x={(aile.debut + aile.fin) / 2 - modulePasM / 2}
          y={bandeSousAile.ymin}
          width={modulePasM}
          height={bandeSousAile.ymax - bandeSousAile.ymin}
          className="ao-l-bande-traversante"
          data-ao-l-bande="traversante"
        />
      </svg>

      <p data-ao-l-aire={aireM2(contour).toFixed(2)}>
        Surface d’enveloppe&nbsp;: {m(aireM2(contour))} m² sur un contour de {contour.length}{' '}
        sommets — un seul tenant.
      </p>

      <p data-ao-l-bande-traversante={(bandeSousAile.ymax - bandeSousAile.ymin).toFixed(2)}>
        Sous l’aile, une bande fait {m(bandeSousAile.ymax - bandeSousAile.ymin)} m d’un seul
        tenant&nbsp;; hors de l’aile, {m(bandeHorsAile.ymax - bandeHorsAile.ymin)} m.
      </p>

      <p data-ao-l-perte={perte.perte}>
        Découpé en deux rectangles&nbsp;: {perte.decoupe} modules par bande au lieu de{' '}
        {perte.continu}, sur {perte.bandesSousAile} bandes —{' '}
        <strong>
          {perte.perte} module{perte.perte > 1 ? 's' : ''} de perte sèche
        </strong>
        .{' '}
        {perte.perte === 0
          ? 'À ces dimensions les restes tombent juste : le découpage ne coûte rien ICI, mais il coûte dès que la profondeur change — le contour reste d’un seul tenant.'
          : 'C’est autant de modules que le découpage ferait disparaître sans rien changer à la toiture.'}
      </p>

      {!controle.valide && (
        <p data-ao-l-incomplet>Complétez la barre et l’aile pour valider l’enveloppe.</p>
      )}

      <button type="button" onClick={valider} data-ao-l-valider>
        Valider l’enveloppe en L
      </button>
    </section>
  )
}
