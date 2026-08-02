/* AOF89 — Outil de saisie des ZONES (interdite / réservée / préférée).
   ----------------------------------------------------------------------------
   Le moteur porte QUATRE natures de contour : l'enveloppe (saisie par l'outil de
   tracé), la zone INTERDITE polygonale (servitude, bande coupe-feu, ombre portée
   déclarée), la zone RÉSERVÉE à un usage futur, et la zone PRÉFÉRÉE qui ne sert
   qu'au départage entre plans de pose équivalents. Un éditeur d'obstacles qui ne
   sait dessiner que des rectangles rendrait trois de ces quatre natures
   INATTEIGNABLES depuis l'écran — donc du code mort dans le moteur. D'où cet
   outil polygone dédié.

   LA RÈGLE QU'ON N'ARRÊTE PAS DE RAPPELER : une zone PRÉFÉRÉE ne change JAMAIS
   le compte. Elle départage deux plans qui posent le même nombre de panneaux,
   c'est tout. Seules l'interdite et la réservée retirent de la surface posable.
   L'écran l'affiche en permanence et le prouve : la surface retirée n'augmente
   pas d'un mètre carré quand on ajoute une zone préférée.

   La légende est GÉNÉRÉE depuis les natures réellement présentes — une légende
   figée finit toujours par annoncer une nature qui n'est pas sur la planche. */
import { useCallback, useId, useMemo, useState } from 'react'
import { aireM2, contourSeCroise } from './repere'

const NATURES_ZONE = [
  {
    cle: 'interdite',
    libelle: 'Zone interdite',
    aide: 'Servitude, bande coupe-feu, ombre portée déclarée — retire de la surface posable.',
    retireDeLaSurface: true,
  },
  {
    cle: 'reservee',
    libelle: 'Zone réservée',
    aide: 'Réservée à un usage futur — retire de la surface posable.',
    retireDeLaSurface: true,
  },
  {
    cle: 'preferee',
    libelle: 'Zone préférée',
    aide: 'Bonus de départage entre plans équivalents — ne change JAMAIS le compte.',
    retireDeLaSurface: false,
  },
]

function natureParCle(cle) {
  return NATURES_ZONE.find((n) => n.cle === cle) ?? NATURES_ZONE[0]
}

function nombre(v) {
  const n = Number(String(v ?? '').replace(',', '.'))
  return Number.isFinite(n) ? n : null
}

let compteur = 0

export default function OutilsZones({
  zonesInitiales = [],
  compteServeur = null,
  metresParPixel = 0.05,
  onChange,
}) {
  const [zones, setZones] = useState(zonesInitiales)
  const [nature, setNature] = useState('interdite')
  const [brouillon, setBrouillon] = useState([])
  const [saisieX, setSaisieX] = useState('')
  const [saisieY, setSaisieY] = useState('')
  const [erreur, setErreur] = useState('')
  // Identifiants UNIQUES par instance : deux OutilsZones montés côte à côte
  // partageaient le même id, donc le htmlFor du second pointait sur le champ du
  // premier — son propre <input> n'était plus étiqueté du tout.
  const idSaisie = useId()

  const publier = useCallback(
    (suivantes) => {
      setZones(suivantes)
      onChange?.(suivantes)
    },
    [onChange],
  )

  const ajouterPoint = useCallback((point) => {
    setBrouillon((prec) => [...prec, point])
    setErreur('')
  }, [])

  const ajouterPointSaisi = useCallback(() => {
    const x = nombre(saisieX)
    const y = nombre(saisieY)
    if (x === null || y === null) {
      setErreur('Saisissez deux coordonnées en mètres (x et y).')
      return
    }
    ajouterPoint({ x, y })
    setSaisieX('')
    setSaisieY('')
  }, [saisieX, saisieY, ajouterPoint])

  const cliquerPlan = useCallback(
    (e) => {
      const boite = e.currentTarget.getBoundingClientRect()
      ajouterPoint({
        x: (e.clientX - boite.left) * metresParPixel,
        y: (e.clientY - boite.top) * metresParPixel,
      })
    },
    [ajouterPoint, metresParPixel],
  )

  const terminerZone = useCallback(() => {
    if (brouillon.length < 3) {
      setErreur('Une zone polygonale demande au moins trois points.')
      return
    }
    if (contourSeCroise(brouillon)) {
      setErreur('Zone refusée : le contour se recoupe.')
      return
    }
    compteur += 1
    publier([
      ...zones,
      {
        id: `zone-${compteur}`,
        nature,
        nom: `${natureParCle(nature).libelle} ${zones.filter((z) => z.nature === nature).length + 1}`,
        sommets: brouillon,
        aireM2: aireM2(brouillon),
      },
    ])
    setBrouillon([])
    setErreur('')
  }, [brouillon, nature, zones, publier])

  const supprimerZone = useCallback(
    (id) => publier(zones.filter((z) => z.id !== id)),
    [zones, publier],
  )

  const changerNature = useCallback(
    (id, cle) => publier(zones.map((z) => (z.id === id ? { ...z, nature: cle } : z))),
    [zones, publier],
  )

  /* Surface RETIRÉE de la posable : interdites + réservées uniquement. Les
     préférées sont volontairement absentes de cette somme — c'est la preuve à
     l'écran que leur ajout ne change pas le compte. */
  const surfaceRetiree = useMemo(
    () =>
      zones
        .filter((z) => natureParCle(z.nature).retireDeLaSurface)
        .reduce((t, z) => t + aireM2(z.sommets), 0),
    [zones],
  )

  const surfacePreferee = useMemo(
    () =>
      zones
        .filter((z) => z.nature === 'preferee')
        .reduce((t, z) => t + aireM2(z.sommets), 0),
    [zones],
  )

  // Légende générée depuis les natures RÉELLEMENT présentes.
  const legende = useMemo(
    () => NATURES_ZONE.filter((n) => zones.some((z) => z.nature === n.cle)),
    [zones],
  )

  return (
    <section className="ao-zones" data-ao-zones={zones.length}>
      <h3>Zones</h3>

      <div className="ao-zones-barre" role="group" aria-label="Nature de la zone à tracer">
        {NATURES_ZONE.map((n) => (
          <button
            key={n.cle}
            type="button"
            aria-pressed={nature === n.cle}
            onClick={() => setNature(n.cle)}
            data-ao-zone-outil={n.cle}
          >
            {n.libelle}
          </button>
        ))}
      </div>

      <p className="ao-zones-regle" data-ao-zones-regle>
        Une zone préférée ne change JAMAIS le compte&nbsp;: elle sert uniquement à départager
        deux plans de pose qui posent le même nombre de panneaux.
      </p>

      <div className="ao-zones-saisie">
        <label className="ao-champ" htmlFor={`${idSaisie}-x`}>
          <span>Point x (m)</span>
          <input
            id={`${idSaisie}-x`}
            className="form-control"
            type="text"
            inputMode="decimal"
            value={saisieX}
            onChange={(e) => setSaisieX(e.target.value)}
          />
        </label>
        <label className="ao-champ" htmlFor={`${idSaisie}-y`}>
          <span>Point y (m)</span>
          <input
            id={`${idSaisie}-y`}
            className="form-control"
            type="text"
            inputMode="decimal"
            value={saisieY}
            onChange={(e) => setSaisieY(e.target.value)}
          />
        </label>
        <button type="button" onClick={ajouterPointSaisi} data-ao-zone-ajouter-point>
          Ajouter le point
        </button>
        <button type="button" onClick={terminerZone} data-ao-zone-terminer>
          Terminer la zone ({brouillon.length} points)
        </button>
      </div>

      {erreur && (
        <p role="alert" data-ao-zone-erreur>
          {erreur}
        </p>
      )}

      <svg
        className="ao-zones-planche"
        viewBox="0 0 60 60"
        role="application"
        aria-label="Planche des zones — cliquez pour poser un point"
        onClick={cliquerPlan}
        data-ao-zones-planche
      >
        {zones.map((z) => (
          <polygon
            key={z.id}
            points={z.sommets.map((s) => `${s.x},${s.y}`).join(' ')}
            className={`ao-zone ao-zone-${z.nature}`}
            data-ao-zone={z.id}
            data-ao-zone-nature={z.nature}
          />
        ))}
        {brouillon.length > 0 && (
          <polyline
            points={brouillon.map((p) => `${p.x},${p.y}`).join(' ')}
            className="ao-zone-brouillon"
            fill="none"
            data-ao-zone-brouillon={brouillon.length}
          />
        )}
      </svg>

      {legende.length > 0 && (
        <ul className="ao-zones-legende" data-ao-zones-legende={legende.length}>
          {legende.map((n) => (
            <li key={n.cle} data-ao-zone-legende={n.cle}>
              <span className={`ao-zone-pastille ao-zone-${n.cle}`} aria-hidden="true" />
              {n.libelle} — {n.aide}
            </li>
          ))}
        </ul>
      )}

      <p data-ao-zones-surface-retiree={surfaceRetiree.toFixed(2)}>
        Surface retirée du posable&nbsp;: {surfaceRetiree.toFixed(2)} m² — dont{' '}
        {surfacePreferee.toFixed(2)} m² de zones préférées, qui ne retirent RIEN.
      </p>

      {compteServeur !== null && (
        <p data-ao-zones-compte={compteServeur}>
          Compte du moteur&nbsp;: {compteServeur} panneaux.
        </p>
      )}

      <table className="data-table ao-zones-table">
        <caption>Zones saisies</caption>
        <thead>
          <tr>
            <th scope="col">Zone</th>
            <th scope="col">Nature</th>
            <th scope="col">Aire (m²)</th>
            <th scope="col">Action</th>
          </tr>
        </thead>
        <tbody>
          {zones.map((z) => (
            <tr key={z.id} data-ao-zone-ligne={z.id}>
              <th scope="row">{z.nom}</th>
              <td>
                <select
                  className="form-select"
                  value={z.nature}
                  aria-label={`Nature de ${z.nom}`}
                  onChange={(e) => changerNature(z.id, e.target.value)}
                >
                  {NATURES_ZONE.map((n) => (
                    <option key={n.cle} value={n.cle}>
                      {n.libelle}
                    </option>
                  ))}
                </select>
              </td>
              <td>{aireM2(z.sommets).toFixed(2)}</td>
              <td>
                <button type="button" onClick={() => supprimerZone(z.id)}>
                  Supprimer {z.nom}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
