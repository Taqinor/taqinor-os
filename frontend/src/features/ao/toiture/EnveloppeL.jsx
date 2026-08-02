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
import {
  L_REFERENCE,
  COINS,
  m,
  validerL,
  contourL,
  empriseAile,
  bandeL,
  perteDuDecoupage,
} from './EnveloppeL.geometrie'

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
