import { useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'
import { useHasPermission } from '../../../hooks/useHasPermission'
import { Card } from '../../../ui'

/* ============================================================================
   ACAL130 — « SITE & IMAGERIE » : LES RÉGLAGES DU SITE, SAISISSABLES.
   ----------------------------------------------------------------------------
   La section `imagerie` des réglages société (contrat `site_imagerie.json`,
   CAL46) n'avait AUCUN écran : pays, fournisseur, attribution, altitude (et sa
   source) et fuseau IANA ne se réglaient nulle part — d'où « fuseau du site
   non réglé » qui refuse la simulation (ACAL126/129), et la suggestion de
   pente IGN (pays `fr`) ou l'allée de l'atelier jamais débloquées.

   LE FUSEAU EFFECTIF est servi par le GET (`imagerie.site_effectif`, ACAL129 :
   `{fuseau, source, mention}`) avec sa provenance — fuseau d'imagerie, sinon
   celui du profil société. Rien n'est déduit ici.

   ÉCRITURE — LE SERVEUR REMPLACE `imagerie` EN ENTIER. Seules `simulation` et
   `electrique_societe` fusionnent par clé (`parametres_cles.REGISTRES`,
   ACAL132) ; la section `imagerie` est normalisée à ses huit clés, une clé
   absente de l'envoi redevient `null`. Envoyer « seulement les clés
   modifiées » EFFACERAIT donc les autres. Le corps part donc avec les huit
   clés déjà servies (`site_effectif`, clé DÉRIVÉE, exclue), les seules clés
   MODIFIÉES à l'écran étant remplacées : aucune clé non touchée n'est
   perdue (les listes `fournisseurs_autorises` et `calques_optionnels` passent
   inchangées), et un aller-retour sans geste renvoie la section à l'identique.
   Le refus 400 du serveur nomme la clé fautive : il se pose sous son champ.
   ========================================================================== */

//: Les clés de la section — `services/site.py::CLES` (contrat CAL46).
const CLES = [
  'pays', 'fournisseur_imagerie', 'fournisseurs_autorises', 'calques_optionnels',
  'attribution', 'altitude_m', 'source_altitude', 'fuseau',
]

//: Les champs SAISISSABLES ici (les deux listes restent celles du serveur).
const CHAMPS = [
  { cle: 'pays', libelle: 'Pays (code à deux lettres)', aide: 'Par exemple « ma » ou « fr » : borne le géocodage et ouvre la suggestion de pente IGN pour « fr ».' },
  { cle: 'fournisseur_imagerie', libelle: 'Fournisseur d’imagerie', aide: 'maptiler, mapbox ou ign_bd_ortho (France).' },
  { cle: 'attribution', libelle: 'Attribution légale', aide: 'Mention exigée par le fournisseur (obligatoire pour ign_bd_ortho).' },
  { cle: 'altitude_m', libelle: 'Altitude du site (m)', aide: 'Saisie : jamais devinée.' },
  { cle: 'source_altitude', libelle: 'Source de l’altitude', aide: 'D’où vient l’altitude saisie.' },
  { cle: 'fuseau', libelle: 'Fuseau horaire (IANA)', aide: 'Par exemple « Africa/Casablanca » : aucune heure légale n’est supposée.' },
]

const PROVENANCES = {
  imagerie: 'réglage imagerie',
  profil_societe: 'profil société',
}

const texteDe = (valeur) => (valeur === null || valeur === undefined ? '' : String(valeur))

/** Le brouillon (chaînes) d'une section servie. */
function brouillonDe(imagerie) {
  const section = imagerie && typeof imagerie === 'object' ? imagerie : {}
  const brouillon = {}
  for (const { cle } of CHAMPS) brouillon[cle] = texteDe(section[cle])
  return brouillon
}

/** La valeur ENVOYÉE pour un champ tapé : vide → `null` ; l'altitude part en
    nombre quand elle se lit comme tel (sinon telle quelle, le serveur refuse
    en nommant la clé). */
function valeurDeChamp(cle, texte) {
  const brut = (texte || '').trim()
  if (!brut) return null
  if (cle === 'altitude_m') {
    const nombre = Number(brut.replace(',', '.'))
    return Number.isFinite(nombre) ? nombre : brut
  }
  return brut
}

/** Le corps du PUT : les clés servies, les seules clés MODIFIÉES remplacées. */
function corpsImagerie(initial, brouillon, brouillonInitial) {
  const section = initial && typeof initial === 'object' ? initial : {}
  const corps = {}
  for (const cle of CLES) {
    if (cle in section) corps[cle] = section[cle]
  }
  for (const { cle } of CHAMPS) {
    if ((brouillon[cle] || '') !== (brouillonInitial[cle] || '')) {
      corps[cle] = valeurDeChamp(cle, brouillon[cle])
    }
  }
  return corps
}

/** Le refus 400 : `{champ: [motif]}` ou `{champ: motif}` (le serveur nomme la clé). */
function erreursDepuis(corps) {
  const erreurs = {}
  if (corps && typeof corps === 'object') {
    for (const [champ, valeur] of Object.entries(corps)) {
      erreurs[champ] = Array.isArray(valeur) ? valeur.join(' ') : String(valeur)
    }
  }
  return Object.keys(erreurs).length
    ? erreurs
    : { _general: 'Le serveur n’a rendu aucun motif : rien n’a été enregistré.' }
}

export default function ReglagesSite({ imagerie = null }) {
  const peutGerer = useHasPermission('calepinage_gerer')
  const [servi, setServi] = useState(imagerie)
  const [brouillon, setBrouillon] = useState(() => brouillonDe(imagerie))
  const [brouillonInitial, setBrouillonInitial] = useState(() => brouillonDe(imagerie))
  const [erreurs, setErreurs] = useState({})
  const [message, setMessage] = useState(null)
  const [enCours, setEnCours] = useState(false)

  const effectif = servi?.site_effectif || null

  const changer = (cle, valeur) => setBrouillon((courant) => ({ ...courant, [cle]: valeur }))

  const enregistrer = async () => {
    setMessage(null)
    setErreurs({})
    setEnCours(true)
    try {
      await calepinageApi.parametres.update({
        imagerie: corpsImagerie(servi, brouillon, brouillonInitial),
      })
      // Relecture : le PUT ne rend pas `site_effectif` (clé DÉRIVÉE du GET).
      const res = await calepinageApi.parametres.get()
      const relu = res?.data?.imagerie ?? null
      setServi(relu)
      setBrouillon(brouillonDe(relu))
      setBrouillonInitial(brouillonDe(relu))
      setMessage('Site et imagerie enregistrés.')
    } catch (e) {
      setErreurs(erreursDepuis(e?.response?.data))
    } finally {
      setEnCours(false)
    }
  }

  const champsFautifs = Object.keys(erreurs).filter((cle) => cle !== '_general')

  return (
    <Card className="mt-5 p-4" data-testid="acal130-site">
      <h2 className="text-base font-semibold text-foreground">Site &amp; imagerie</h2>

      <p className="mt-1 text-sm text-muted-foreground" data-testid="acal130-fuseau-effectif">
        {effectif?.fuseau
          ? (
            <>
              Fuseau effectif : <strong>{effectif.fuseau}</strong>
              {' '}(source : {PROVENANCES[effectif.source] || effectif.source || 'non publiée'})
              {effectif.mention ? ` — ${effectif.mention}` : ''}
            </>
          )
          : (effectif?.mention || 'Fuseau effectif non publié par le serveur.')}
      </p>

      {champsFautifs.length > 0 && (
        <p
          role="alert"
          data-testid="acal130-bandeau"
          className="mt-3 rounded border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          Réglages du site refusés — à corriger : {champsFautifs.join(', ')}.
        </p>
      )}

      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {CHAMPS.map(({ cle, libelle, aide }) => (
          <label key={cle} className="block" data-testid={`acal130-champ-${cle}`}>
            <span className="text-xs font-medium text-foreground">{libelle}</span>
            <input
              type="text"
              value={brouillon[cle]}
              disabled={!peutGerer || enCours}
              aria-invalid={erreurs[cle] ? 'true' : undefined}
              onChange={(e) => changer(cle, e.target.value)}
              className="mt-0.5 block w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground"
            />
            <span className="block text-xs text-muted-foreground">{aide}</span>
            {erreurs[cle] && (
              <span role="alert" className="block text-xs text-destructive" data-testid={`acal130-erreur-${cle}`}>
                {erreurs[cle]}
              </span>
            )}
          </label>
        ))}
      </div>

      {peutGerer && (
        <button
          type="button"
          disabled={enCours}
          data-testid="acal130-enregistrer"
          className="mt-4 text-sm font-semibold underline"
          onClick={enregistrer}
        >
          {enCours ? 'Enregistrement…' : 'Enregistrer le site'}
        </button>
      )}
      {erreurs._general && (
        <p role="alert" className="mt-2 text-xs text-destructive" data-testid="acal130-erreur-generale">
          {erreurs._general}
        </p>
      )}
      {message && (
        <p role="status" className="mt-3 text-sm text-muted-foreground" data-testid="acal130-message">
          {message}
        </p>
      )}
    </Card>
  )
}
