import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { SlidersHorizontal } from 'lucide-react'
import calepinageApi from '../../../api/calepinageApi'
import { Button, Card, Input, Label, Spinner } from '../../../ui'
import RetourAtelier from '../atelier/RetourAtelier'
import { refusParChamp } from './entreeElectrique'
import { CHAMPS, EXIGENCE, GRANDEURS, corpsDeSaisie, depuisEntree } from './SaisiesElectriques.helpers'

/* ============================================================================
   ACAL153 — L'ONGLET « SAISIES ÉLECTRIQUES » DE L'ATELIER.
   ----------------------------------------------------------------------------
   Températures du site, longueurs de liaison, phases, régime de neutre, transformateur,
   exigence du marché et options du calcul — pré-remplis depuis l'entrée STOCKÉE
   (`GET entree-electrique/`), postés par `POST entree-electrique/` (fusion par clé côté
   serveur). Le refus d'un champ s'affiche SOUS ce champ, mot pour mot ; un champ vidé
   envoie `null`, JAMAIS 0. Aucun calcul, aucun appel stock côté écran.
   ========================================================================== */

const idChamp = (cle) => `acal153-champ-${cle}`

function Champ({ cle, libelle, unite, genre, valeur, erreur, onChange, id = idChamp(cle) }) {
  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor={id}>{unite ? `${libelle} (${unite})` : libelle}</Label>
      {genre === 'booleen'
        ? (
          <select
            id={id}
            value={valeur}
            onChange={(e) => onChange(e.target.value)}
            aria-invalid={erreur ? 'true' : undefined}
            className="w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white"
          >
            <option value="">— non précisé —</option>
            <option value="oui">oui</option>
            <option value="non">non</option>
          </select>
        )
        : (
          <Input
            id={id}
            type={genre === 'nombre' ? 'number' : 'text'}
            step={genre === 'nombre' ? 'any' : undefined}
            invalid={Boolean(erreur)}
            aria-describedby={erreur ? `${id}-erreur` : undefined}
            value={valeur}
            onChange={(e) => onChange(e.target.value)}
          />
        )}
      {erreur
        ? <p id={`${id}-erreur`} className="text-xs text-destructive" data-testid={`acal153-erreur-${cle}`}>{erreur}</p>
        : null}
    </div>
  )
}

export default function SaisiesElectriques({ calepinageId, lectureSeule = false } = {}) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute

  const [entree, setEntree] = useState(null)
  const [saisie, setSaisie] = useState(null)
  const [erreurLecture, setErreurLecture] = useState(null)
  const [erreurs, setErreurs] = useState({})
  const [enregistrement, setEnregistrement] = useState(false)

  const lire = useCallback(() => calepinageApi.calepinages.entreeElectrique(id)
    .then((res) => {
      const lue = res?.data?.entree ?? {}
      setEntree(lue)
      setSaisie(depuisEntree(lue))
      setErreurLecture(null)
    })
    .catch(() => setErreurLecture('Saisies électriques indisponibles.')), [id])

  useEffect(() => { lire() }, [lire])

  const poser = (cle, valeur) => setSaisie((s) => ({ ...s, [cle]: valeur }))
  const poserSous = (bloc, cle, valeur) => setSaisie((s) => ({ ...s, [bloc]: { ...s[bloc], [cle]: valeur } }))
  const poserGrandeur = (cle, champ, valeur) => setSaisie((s) => ({
    ...s,
    transformateur: { ...s.transformateur, [cle]: { ...s.transformateur[cle], [champ]: valeur } },
  }))

  const enregistrer = (evenement) => {
    evenement.preventDefault()
    setEnregistrement(true)
    setErreurs({})
    calepinageApi.calepinages.enregistrerEntreeElectrique(id, corpsDeSaisie(saisie, entree))
      .then(() => lire())
      .catch((err) => {
        const parChamp = refusParChamp(err?.response?.data)
        setErreurs(Object.keys(parChamp).length
          ? parChamp
          : { saisies: 'Saisies non enregistrées : le serveur n’a pas accepté la saisie.' })
      })
      .finally(() => setEnregistrement(false))
  }

  if (erreurLecture) {
    return (
      <>
        <RetourAtelier calepinageId={id} cle="saisies-electriques" />
        <p className="text-sm text-destructive" data-testid="acal153-erreur">{erreurLecture}</p>
      </>
    )
  }
  if (!saisie) {
    return (
      <>
        <RetourAtelier calepinageId={id} cle="saisies-electriques" />
        <Spinner />
      </>
    )
  }
  const groupes = [...new Set(CHAMPS.map((c) => c.groupe))]

  // Un refus s'affiche SOUS son champ ; celui qu'aucun champ ne porte reste en bandeau.
  const connues = new Set([
    ...CHAMPS.flatMap((c) => (c.dans ? [`${c.dans}.${c.cle}`, c.dans] : [c.cle])),
    'exigence_marche', ...EXIGENCE.map((c) => `exigence_marche.${c.cle}`),
    'transformateur', 'transformateur.declare',
    ...GRANDEURS.flatMap((g) => ['', '.valeur', '.source', '.reference'].map((s) => `transformateur.${g.cle}${s}`)),
  ])
  const sansChamp = Object.entries(erreurs).filter(([cle]) => !connues.has(cle))
  const erreurDe = (c) => erreurs[c.dans ? `${c.dans}.${c.cle}` : c.cle] ?? (c.dans ? erreurs[c.dans] : undefined)
  const erreurGrandeur = (cle) => ['.valeur', '.source', '.reference', '']
    .map((s) => erreurs[`transformateur.${cle}${s}`]).find(Boolean)

  return (
    <>
      <RetourAtelier calepinageId={id} cle="saisies-electriques" />
      <Card className="flex flex-col gap-4 p-4" data-testid="acal153-panneau">
        <header className="flex items-center gap-2">
          <SlidersHorizontal size={16} aria-hidden="true" />
          <div className="flex flex-col gap-1">
            <h2 className="text-base font-semibold">Saisies électriques</h2>
            <p className="text-sm text-muted-foreground">
              Ce que le calcul électrique ne peut pas deviner : relu du serveur, jamais complété ici.
              Un champ laissé vide reste « non saisi ».
            </p>
          </div>
        </header>

        {sansChamp.length
          ? (
            <p role="alert" className="text-sm text-destructive" data-testid="acal153-bandeau">
              {sansChamp.map(([cle, message]) => `${cle} : ${message}`).join(' ')}
            </p>
          ) : null}

        <form className="flex flex-col gap-4" onSubmit={enregistrer} data-testid="acal153-formulaire">
          {groupes.map((groupe) => (
            <fieldset key={groupe} className="flex flex-col gap-3">
              <legend className="tech-label text-lune-faint">{groupe}</legend>
              <div className="grid gap-3 sm:grid-cols-2">
                {CHAMPS.filter((c) => c.groupe === groupe).map((c) => (
                  <Champ
                    key={c.cle}
                    cle={c.cle}
                    libelle={c.libelle}
                    unite={c.unite}
                    genre={c.genre}
                    valeur={saisie[c.cle]}
                    erreur={erreurDe(c)}
                    onChange={(v) => poser(c.cle, v)}
                  />
                ))}
              </div>
            </fieldset>
          ))}

          <fieldset className="flex flex-col gap-3" data-testid="acal153-exigence">
            <legend className="tech-label text-lune-faint">Exigence du marché</legend>
            <div className="grid gap-3 sm:grid-cols-3">
              {EXIGENCE.map((c) => (
                <Champ
                  key={c.cle}
                  id={idChamp(`exigence-${c.cle}`)}
                  cle={`exigence_marche.${c.cle}`}
                  libelle={c.libelle}
                  genre={c.genre}
                  valeur={saisie.exigence[c.cle]}
                  erreur={erreurs[`exigence_marche.${c.cle}`] ?? erreurs.exigence_marche}
                  onChange={(v) => poserSous('exigence', c.cle, v)}
                />
              ))}
            </div>
          </fieldset>

          <fieldset className="flex flex-col gap-3" data-testid="acal153-transformateur">
            <legend className="tech-label text-lune-faint">Transformateur</legend>
            <Champ
              id={idChamp('transformateur-declare')}
              cle="transformateur.declare"
              libelle="Un transformateur est déclaré"
              genre="booleen"
              valeur={saisie.transformateur.declare}
              erreur={erreurs['transformateur.declare'] ?? erreurs.transformateur}
              onChange={(v) => poserSous('transformateur', 'declare', v)}
            />
            {GRANDEURS.map((g) => (
              <div key={g.cle} className="flex flex-col gap-1" data-testid={`acal153-grandeur-${g.cle}`}>
                <div className="grid gap-3 sm:grid-cols-3">
                  {['valeur', 'source', 'reference'].map((champ) => (
                    <div key={champ} className="flex flex-col gap-1">
                      <Label htmlFor={idChamp(`${g.cle}-${champ}`)}>
                        {champ === 'valeur' ? `${g.libelle} (${g.unite})` : `${g.libelle} — ${champ === 'source' ? 'source' : 'référence'}`}
                      </Label>
                      <Input
                        id={idChamp(`${g.cle}-${champ}`)}
                        type={champ === 'valeur' ? 'number' : 'text'}
                        step={champ === 'valeur' ? 'any' : undefined}
                        invalid={Boolean(erreurs[`transformateur.${g.cle}.${champ}`])}
                        value={saisie.transformateur[g.cle][champ]}
                        onChange={(e) => poserGrandeur(g.cle, champ, e.target.value)}
                      />
                    </div>
                  ))}
                </div>
                {erreurGrandeur(g.cle)
                  ? <p className="text-xs text-destructive" data-testid={`acal153-erreur-${g.cle}`}>{erreurGrandeur(g.cle)}</p>
                  : null}
              </div>
            ))}
          </fieldset>

          <div>
            <Button type="submit" disabled={enregistrement || lectureSeule} data-testid="acal153-enregistrer">
              {enregistrement ? 'Enregistrement…' : 'Enregistrer les saisies'}
            </Button>
          </div>
        </form>
      </Card>
    </>
  )
}
