/* AOF86 — Panneau « Fermetures » : le VERROU MÉTIER de l'atelier.
   ----------------------------------------------------------------------------
   Pour chaque chaîne de cotes : la somme calculée des segments, la cote mesurée
   totale, le RÉSIDU en mètres ET en pourcentage, la tolérance propre à la
   chaîne, et le statut OK / ÉCART — exactement le comportement de la fermeture
   (`closure`) du solveur : |mesurée − somme| ≤ tolérance ⇒ OK, sinon ÉCART.

   Deux sorties, jamais trois :
     • COMPENSER AU PRORATA (spread) — la répartition est DEMANDÉE AU SERVEUR
       (`ChaineCotesViewSet.compensation`, WIR205) et rendue telle quelle.
       L'écran ne refait PLUS le produit en croix : deux arrondis concurrents
       (ici et dans `services.proposer_compensation_prorata`) finissaient par
       montrer un « après » qui n'était pas celui qu'on enregistrait. L'aperçu
       AVANT/APRÈS reste obligatoire avant d'appliquer : on ne réécrit pas un
       relevé dans le dos de celui qui l'a fait.
     • ACCEPTER L'ÉCART — avec un motif ÉCRIT, obligatoire, persisté et visible
       ensuite en permanence sur la chaîne.

   Tant qu'une chaîne reste en ÉCART NON ARBITRÉ, on ne passe pas au calepinage.
   Un calepinage posé sur une toiture qui ne referme pas est un calepinage faux —
   et il a l'air juste, ce qui est pire. Le blocage nomme les chaînes fautives. */
import { useCallback, useMemo, useState } from 'react'

function nombre(valeur) {
  const n = Number(String(valeur ?? '').replace(',', '.'))
  return Number.isFinite(n) ? n : 0
}

/* Fermeture d'une chaîne — la même règle que le solveur, appliquée à l'écran. */
function fermeture(chaine) {
  const somme = (chaine.segments || []).reduce((t, s) => t + nombre(s.valeur), 0)
  const mesuree = nombre(chaine.coteMesuree)
  const tolerance = nombre(chaine.tolerance)
  const residu = mesuree - somme
  const residuPct = mesuree !== 0 ? (residu / mesuree) * 100 : 0
  const statut = Math.abs(residu) <= tolerance ? 'OK' : 'ECART'
  return { somme, mesuree, tolerance, residu, residuPct, statut }
}

/* Une chaîne est ARBITRÉE si elle referme dans sa tolérance, ou si l'écart a été
   explicitement accepté avec un motif écrit. Rien d'autre ne compte. */
function estArbitree(chaine) {
  if (fermeture(chaine).statut === 'OK') return true
  const a = chaine.arbitrage
  return Boolean(a && a.type === 'accepte' && String(a.motif || '').trim().length > 0)
}

const MSG_SANS_SERVEUR =
  'Compensation indisponible : cet écran n’a aucun moyen de la DEMANDER au '
  + 'serveur. Rien n’est proposé — un prorata calculé ici ne serait pas celui '
  + 'qui serait enregistré.'

const MSG_RIEN_A_REPARTIR =
  'Le serveur ne propose aucune répartition pour cette chaîne (résidu nul, ou '
  + 'somme des segments nulle). Rien n’a été modifié.'

export default function FermeturesPanel({
  chaines = [], onChaines, onCalepiner, onCompenser,
}) {
  // `apercu` porte la RÉPONSE SERVEUR telle quelle :
  // { idChaine, residuM, segments: [{index, libelle, valeur_m,
  //   valeur_proposee_m, delta_m}] }
  const [apercu, setApercu] = useState(null)
  const [motifs, setMotifs] = useState({})
  const [erreur, setErreur] = useState(null)
  const [enCours, setEnCours] = useState(null)

  const lignes = useMemo(
    () => chaines.map((c) => ({ chaine: c, ...fermeture(c), arbitree: estArbitree(c) })),
    [chaines],
  )

  const bloquantes = lignes.filter((l) => !l.arbitree)
  const peutCalepiner = bloquantes.length === 0

  /* La proposition vient du SERVEUR — jamais d'un produit en croix local. Le
     parent (`ToituresPage`) fournit `onCompenser` : il appelle
     `aoApi.chaines.compensation(id)` et lève une erreur NOMMÉE quand la chaîne
     n'existe pas encore côté serveur (rien à compenser tant qu'elle n'est pas
     enregistrée). */
  const preparerProrata = useCallback(
    async (chaine) => {
      setErreur(null)
      setApercu(null)
      if (typeof onCompenser !== 'function') {
        setErreur(MSG_SANS_SERVEUR)
        return
      }
      setEnCours(chaine.id)
      try {
        const proposition = await onCompenser(chaine)
        const segments = proposition?.segments ?? []
        if (!segments.length) {
          setErreur(MSG_RIEN_A_REPARTIR)
          return
        }
        setApercu({
          idChaine: chaine.id,
          residuM: proposition.residu_m,
          segments,
        })
      } catch (e) {
        setErreur(e?.message || 'Compensation refusée par le serveur.')
      } finally {
        setEnCours(null)
      }
    },
    [onCompenser],
  )

  /* Applique la proposition SERVEUR aux segments locaux, PAR INDEX (c'est la
     clé que le serveur renvoie ; un appariement par libellé casserait sur deux
     segments homonymes). Les segments non cités par la proposition — ceux dont
     la valeur est absente côté serveur — ne sont pas touchés. */
  const appliquerProrata = useCallback(() => {
    if (!apercu) return
    const parIndex = new Map(apercu.segments.map((s) => [s.index, s]))
    onChaines?.(
      chaines.map((c) =>
        c.id === apercu.idChaine
          ? {
              ...c,
              segments: (c.segments || []).map((s, i) => {
                const propose = parIndex.get(i)
                return propose
                  ? { ...s, valeur: nombre(propose.valeur_proposee_m) }
                  : s
              }),
              arbitrage: { type: 'compense', horodatage: new Date().toISOString() },
            }
          : c,
      ),
    )
    setApercu(null)
  }, [apercu, chaines, onChaines])

  const accepterEcart = useCallback(
    (chaine) => {
      const motif = String(motifs[chaine.id] || '').trim()
      if (!motif) return
      onChaines?.(
        chaines.map((c) =>
          c.id === chaine.id
            ? {
                ...c,
                arbitrage: { type: 'accepte', motif, horodatage: new Date().toISOString() },
              }
            : c,
        ),
      )
    },
    [motifs, chaines, onChaines],
  )

  return (
    <section className="ao-fermetures" data-ao-fermetures>
      <h3>Fermetures</h3>

      {erreur && (
        <p role="alert" className="ao-fermeture-erreur" data-ao-fermeture-erreur>
          {erreur}
        </p>
      )}

      <table className="data-table ao-fermetures-table">
        <caption>Une ligne par chaîne : somme, cote mesurée, résidu, tolérance, statut</caption>
        <thead>
          <tr>
            <th scope="col">Chaîne</th>
            <th scope="col">Somme (m)</th>
            <th scope="col">Mesurée (m)</th>
            <th scope="col">Résidu (m)</th>
            <th scope="col">Résidu (%)</th>
            <th scope="col">Tolérance (m)</th>
            <th scope="col">Statut</th>
          </tr>
        </thead>
        <tbody>
          {lignes.map(({ chaine, somme, mesuree, residu, residuPct, tolerance, statut }) => (
            <tr key={chaine.id} data-ao-fermeture={chaine.id} data-ao-fermeture-statut={statut}>
              <th scope="row">{chaine.nom}</th>
              <td>{somme.toFixed(3)}</td>
              <td>{mesuree.toFixed(3)}</td>
              <td data-ao-fermeture-residu={chaine.id}>{residu.toFixed(3)}</td>
              <td data-ao-fermeture-residu-pct={chaine.id}>{residuPct.toFixed(2)} %</td>
              <td>{tolerance.toFixed(2)}</td>
              <td>{statut === 'OK' ? 'OK' : 'ÉCART'}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {lignes
        .filter((l) => l.statut === 'ECART')
        .map(({ chaine, residu }) => (
          <div className="ao-fermeture-arbitrage" key={chaine.id} data-ao-arbitrage={chaine.id}>
            <h4>
              {chaine.nom} — écart de {residu.toFixed(3)} m à arbitrer
            </h4>

            <button
              type="button"
              onClick={() => preparerProrata(chaine)}
              disabled={enCours === chaine.id}
              data-ao-fermeture-prorata={chaine.id}
            >
              Compenser au prorata — {chaine.nom}
            </button>

            {apercu?.idChaine === chaine.id && (
              <div className="ao-fermeture-apercu" data-ao-fermeture-apercu>
                <table className="data-table">
                  <caption>
                    Avant / après compensation — répartition proposée par le
                    serveur (résidu {nombre(apercu.residuM).toFixed(3)} m)
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Segment</th>
                      <th scope="col">Avant (m)</th>
                      <th scope="col">Après (m)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {apercu.segments.map((s) => (
                      <tr key={s.index}>
                        <th scope="row">{s.libelle}</th>
                        <td>{nombre(s.valeur_m).toFixed(3)}</td>
                        <td>{nombre(s.valeur_proposee_m).toFixed(3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <button type="button" onClick={appliquerProrata} data-ao-fermeture-appliquer>
                  Appliquer la compensation
                </button>
                <button type="button" onClick={() => setApercu(null)}>
                  Annuler
                </button>
              </div>
            )}

            <label className="ao-champ" htmlFor={`${chaine.id}-motif`}>
              <span>Motif d&apos;acceptation de l&apos;écart</span>
              <textarea
                id={`${chaine.id}-motif`}
                className="form-control"
                value={motifs[chaine.id] || ''}
                onChange={(e) => setMotifs((m) => ({ ...m, [chaine.id]: e.target.value }))}
              />
            </label>
            <button
              type="button"
              onClick={() => accepterEcart(chaine)}
              disabled={!String(motifs[chaine.id] || '').trim()}
              data-ao-fermeture-accepter={chaine.id}
            >
              Accepter l&apos;écart — {chaine.nom}
            </button>
          </div>
        ))}

      {/* Motif d'acceptation PERSISTÉ et visible en permanence. */}
      {chaines
        .filter((c) => c.arbitrage?.type === 'accepte')
        .map((c) => (
          <p key={c.id} className="ao-fermeture-motif" data-ao-fermeture-motif={c.id}>
            {c.nom} — écart accepté&nbsp;: {c.arbitrage.motif}
          </p>
        ))}

      {!peutCalepiner && (
        <p role="alert" className="ao-fermetures-verrou" data-ao-fermetures-verrou>
          Calepinage bloqué&nbsp;: {bloquantes.map((l) => l.chaine.nom).join(', ')}
          {bloquantes.length > 1 ? ' sont en écart non arbitré' : ' est en écart non arbitré'}.
          Compensez au prorata, ou acceptez l&apos;écart avec un motif écrit.
        </p>
      )}

      <button
        type="button"
        disabled={!peutCalepiner}
        onClick={() => onCalepiner?.()}
        data-ao-fermetures-calepiner
      >
        Passer au calepinage
      </button>
    </section>
  )
}
