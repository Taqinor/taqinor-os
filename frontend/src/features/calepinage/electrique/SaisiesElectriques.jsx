/* eslint-disable react-refresh/only-export-components --
   `CHAMPS`, `GRANDEURS`, `depuisEntree` et `corpsDeSaisie` sont des tables et des fonctions
   PURES que le test confronte directement à l'exemple committé (même dérogation que
   `Raccordement.jsx`). */
import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { SlidersHorizontal } from 'lucide-react'
import calepinageApi from '../../../api/calepinageApi'
import { Button, Card, Input, Label, Spinner } from '../../../ui'
import RetourAtelier from '../atelier/RetourAtelier'
import { nombreOuNull, refusParChamp, texteOuNull } from './entreeElectrique'

/* ============================================================================
   ACAL153 — L'ONGLET « SAISIES ÉLECTRIQUES » DE L'ATELIER.
   ----------------------------------------------------------------------------
   Températures du site, longueurs de liaison, phases, régime de neutre, transformateur,
   exigence du marché et options du calcul — pré-remplis depuis l'entrée STOCKÉE
   (`GET entree-electrique/`), postés par `POST entree-electrique/` (fusion par clé côté
   serveur). Le refus d'un champ s'affiche SOUS ce champ, mot pour mot ; un champ vidé
   envoie `null`, JAMAIS 0. Aucun calcul, aucun appel stock côté écran.
   ========================================================================== */

/** Les champs à nombre ou texte simple, à plat dans l'entrée. `groupe` ordonne l'écran. */
export const CHAMPS = [
  { cle: 'temperature_min_c', libelle: 'Température minimale du site', unite: '°C', genre: 'nombre', groupe: 'Site' },
  { cle: 'temperature_max_c', libelle: 'Température maximale du site', unite: '°C', genre: 'nombre', groupe: 'Site' },
  { cle: 'dc_m', libelle: 'Longueur de liaison DC', unite: 'm', genre: 'nombre', groupe: 'Liaisons' },
  { cle: 'ac_m', libelle: 'Longueur de liaison AC', unite: 'm', genre: 'nombre', groupe: 'Liaisons' },
  { cle: 'descente_m', libelle: 'Descente de toiture', unite: 'm', genre: 'nombre', groupe: 'Liaisons', dans: 'cheminement' },
  { cle: 'coffret_vers_onduleur_m', libelle: 'Coffret vers onduleur', unite: 'm', genre: 'nombre', groupe: 'Liaisons', dans: 'cheminement' },
  { cle: 'onduleur_vers_tgbt_m', libelle: 'Onduleur vers TGBT', unite: 'm', genre: 'nombre', groupe: 'Liaisons', dans: 'cheminement' },
  { cle: 'phases', libelle: 'Phases du branchement', unite: '1 ou 3', genre: 'nombre', groupe: 'Réseau' },
  { cle: 'regime', libelle: 'Régime de neutre', unite: 'TT, TN ou IT', genre: 'texte', groupe: 'Réseau' },
  { cle: 'plafond_kwc_par_onduleur', libelle: 'Plafond de kWc par onduleur', unite: 'kWc', genre: 'nombre', groupe: 'Options' },
  { cle: 'longueur_chaine_forcee', libelle: 'Longueur de chaîne imposée', unite: 'modules', genre: 'nombre', groupe: 'Options' },
  { cle: 'zone_keraunique', libelle: 'Zone kéraunique', unite: '', genre: 'booleen', groupe: 'Options' },
  { cle: 'inclure_prise_terre', libelle: 'Inclure la prise de terre', unite: '', genre: 'booleen', groupe: 'Options' },
]

/** L'exigence du marché : un objet `{ratio_dc_ac_max, ratio_dc_ac_alerte, reference}`. */
export const EXIGENCE = [
  { cle: 'ratio_dc_ac_max', libelle: 'Ratio DC/AC maximal imposé', genre: 'nombre' },
  { cle: 'ratio_dc_ac_alerte', libelle: 'Seuil d’alerte DC/AC', genre: 'nombre' },
  { cle: 'reference', libelle: 'Référence du cahier des charges', genre: 'texte' },
]

/** Les trois grandeurs sourcées du transformateur. */
export const GRANDEURS = [
  { cle: 'perte_a_vide_kw', libelle: 'Perte à vide', unite: 'kW' },
  { cle: 'perte_en_charge_kw_nominale', libelle: 'Perte en charge nominale', unite: 'kW' },
  { cle: 'puissance_nominale_kw', libelle: 'Puissance nominale', unite: 'kW' },
]

const idChamp = (cle) => `acal153-champ-${cle}`
const enTexte = (v) => (v === null || v === undefined ? '' : String(v))

const BOOL_VERS_TEXTE = (v) => (v === true ? 'oui' : v === false ? 'non' : '')
const TEXTE_VERS_BOOL = (t) => (t === 'oui' ? true : t === 'non' ? false : null)
const estObjet = (v) => v !== null && typeof v === 'object' && !Array.isArray(v)

/** L'entrée stockée (GET) → l'état du formulaire, en chaînes : rien n'est inventé. */
export function depuisEntree(entree) {
  const e = entree ?? {}
  const saisie = { exigence: {}, transformateur: { declare: '' } }
  for (const { cle, genre, dans } of CHAMPS) {
    const brut = dans ? (estObjet(e[dans]) ? e[dans][cle] : null) : e[cle]
    saisie[cle] = genre === 'booleen' ? BOOL_VERS_TEXTE(brut) : enTexte(brut)
  }
  for (const { cle } of EXIGENCE) saisie.exigence[cle] = enTexte(estObjet(e.exigence_marche) ? e.exigence_marche[cle] : null)
  const t = estObjet(e.transformateur) ? e.transformateur : {}
  saisie.transformateur.declare = BOOL_VERS_TEXTE(t.declare)
  for (const { cle } of GRANDEURS) {
    const g = estObjet(t[cle]) ? t[cle] : {}
    saisie.transformateur[cle] = { valeur: enTexte(g.valeur), source: enTexte(g.source), reference: enTexte(g.reference) }
  }
  return saisie
}

const valeurPosee = (genre, texte) => {
  if (genre === 'booleen') return TEXTE_VERS_BOOL(texte)
  return genre === 'nombre' ? nombreOuNull(texte) : texteOuNull(texte)
}

/** Le bloc `cheminement` : fusionné sur l'existant, une clé vide et absente n'est pas créée. */
function cheminementPoste(saisie, entree) {
  const existant = estObjet(entree?.cheminement) ? entree.cheminement : null
  const champs = CHAMPS.filter((c) => c.dans === 'cheminement')
  const saisies = champs.filter((c) => String(saisie[c.cle] ?? '').trim() !== '')
  if (!existant && saisies.length === 0) return undefined
  const bloc = { ...(existant ?? {}) }
  for (const { cle } of champs) {
    const v = nombreOuNull(saisie[cle])
    if (v !== null || cle in bloc) bloc[cle] = v
  }
  return bloc
}

function exigencePosee(saisie, entree) {
  const existant = estObjet(entree?.exigence_marche) ? entree.exigence_marche : null
  const remplis = EXIGENCE.filter((c) => String(saisie.exigence[c.cle] ?? '').trim() !== '')
  if (remplis.length === 0) return existant ? null : undefined
  const bloc = { ...(existant ?? {}) }
  for (const { cle, genre } of EXIGENCE) {
    const v = valeurPosee(genre, saisie.exigence[cle])
    if (v !== null || cle in bloc) bloc[cle] = v
  }
  return bloc
}

function transformateurPoste(saisie, entree) {
  const t = saisie.transformateur
  const stocke = estObjet(entree?.transformateur) ? entree.transformateur : {}
  const rempli = GRANDEURS.some(({ cle }) => String(t[cle].valeur).trim() !== '' || String(t[cle].source).trim() !== '')
  if (t.declare === '' && !rempli) return undefined
  const bloc = { declare: TEXTE_VERS_BOOL(t.declare) ?? false }
  for (const { cle } of GRANDEURS) {
    const g = t[cle]
    const saisi = String(g.valeur).trim() !== '' || String(g.source).trim() !== '' || String(g.reference).trim() !== ''
    if (!saisi) {
      if (cle in stocke) bloc[cle] = null
      continue
    }
    const grandeur = { valeur: nombreOuNull(g.valeur), source: texteOuNull(g.source) }
    const reference = texteOuNull(g.reference)
    if (reference !== null || (estObjet(stocke[cle]) && 'reference' in stocke[cle])) grandeur.reference = reference
    bloc[cle] = grandeur
  }
  return bloc
}

/**
 * Le corps POSTÉ : les champs du formulaire seulement (la fusion par clé du serveur laisse
 * les autres intacts). Un champ vidé vaut `null`, jamais `0` ; une clé jamais saisie et
 * absente du stock n'est pas inventée — `entree` est l'entrée relue, qui sert de repère.
 */
export function corpsDeSaisie(saisie, entree) {
  const corps = {}
  for (const { cle, genre, dans } of CHAMPS) {
    if (dans) continue
    const v = valeurPosee(genre, saisie[cle])
    // Une valeur stockée que le formulaire ne sait pas lire (booléen attendu, autre chose
    // servi) n'est jamais écrasée par un « non précisé » : la clé n'est pas renvoyée.
    const illisible = genre === 'booleen' && v === null && entree != null
      && entree[cle] !== null && entree[cle] !== undefined && typeof entree[cle] !== 'boolean'
    if (illisible) continue
    if (v !== null || entree == null || cle in entree) corps[cle] = v
  }
  const cheminement = cheminementPoste(saisie, entree)
  if (cheminement !== undefined) corps.cheminement = cheminement
  const exigence = exigencePosee(saisie, entree)
  if (exigence !== undefined) corps.exigence_marche = exigence
  const transformateur = transformateurPoste(saisie, entree)
  if (transformateur !== undefined) corps.transformateur = transformateur
  return corps
}

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
