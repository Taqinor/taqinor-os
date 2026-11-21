import { useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'
import { useHasPermission } from '../../../hooks/useHasPermission'
import { Card } from '../../../ui'
import { OBSTACLE_TYPES } from '@roofpro/types'
import { refusServeur } from '../commun/refusServeur'

/* ============================================================================
   ACAL494 — « GABARITS D'OBSTACLE » : la société range ici, une fois, ses
   obstacles types (souche, climatiseur…) que l'atelier pose ensuite par
   « Poser ce gabarit » (`roofPro11/types.ts::lireGabaritsObstacle`).

   ÉCRITURE — LE SERVEUR REMPLACE `zones_types` EN ENTIER : le corps du PUT
   porte donc TOUTE la section servie (gabarits de zone compris, clés
   comprises) ; seule l'entrée créée, modifiée ou supprimée change. Les
   entrées sans `forme` (gabarits de zone) ne s'affichent pas ici mais
   repartent telles quelles. Aucune cote n'a de valeur par défaut : le refus
   400 du serveur (`zones_types.<clé>.<champ>`) se pose sous son champ.
   ========================================================================== */

const FORMES = [{ id: 'rectangle', libelle: 'Rectangle' }, { id: 'cercle', libelle: 'Cercle' }]

const CHAMPS = [
  { cle: 'libelle', libelle: 'Nom du gabarit' },
  { cle: 'longueur_m', libelle: 'Longueur (m)', formes: ['rectangle'] },
  { cle: 'largeur_m', libelle: 'Largeur (m)', formes: ['rectangle'] },
  { cle: 'rayon_m', libelle: 'Rayon (m)', formes: ['cercle'] },
  { cle: 'hauteur_m', libelle: 'Hauteur (m)' },
  { cle: 'retrait_m', libelle: 'Dégagement (m)' },
  { cle: 'source', libelle: 'Source' },
]

const NOMBRES = ['longueur_m', 'largeur_m', 'rayon_m', 'hauteur_m', 'retrait_m']
const texteDe = (v) => (v === null || v === undefined ? '' : String(v).replace('.', ','))
const estObstacle = (e) => !!e && typeof e === 'object' && !Array.isArray(e) && !!e.forme
// ACAL495 — un gabarit de ZONE : un genre, ni forme ni type d'obstacle (même test que `lireGabaritsZone`).
const estZone = (e) => !!e && typeof e === 'object' && !Array.isArray(e) && !!e.genre && !e.forme && !e.type
const NATURES = [{ id: 'INTERDITE', libelle: 'Zone interdite' }, { id: 'RESERVEE', libelle: 'Zone réservée' }, { id: 'PREFEREE', libelle: 'Zone préférée' }]
const COTES = [{ id: 'nord', libelle: 'Nord' }, { id: 'sud', libelle: 'Sud' }, { id: 'est', libelle: 'Est' }, { id: 'ouest', libelle: 'Ouest' }, { id: 'perimetre', libelle: 'Tout le tour' }]
const CHAMPS_ZONE = [
  { cle: 'libelle', libelle: 'Nom de la zone' },
  { cle: 'largeur_m', libelle: 'Largeur de la bande (m)' },
  { cle: 'source', libelle: 'Source' },
]

const brouillonZone = (cle, e) => ({
  cle, nature: e?.nature ?? 'INTERDITE', cote: e?.cote ?? '',
  ...Object.fromEntries(['libelle', 'source', 'largeur_m'].map((c) => [c, texteDe(e?.[c])])),
})

/** L'entrée de zone envoyée : l'ancienne (clés non touchées) + les champs saisis ; un côté vide est omis (le serveur pose le tour). */
function zoneDe(b, ancienne) {
  const entree = { ...(ancienne || {}), genre: 'bande', nature: b.nature, libelle: b.libelle.trim(), source: b.source.trim() }
  if (b.cote) entree.cote = b.cote; else delete entree.cote
  const brut = b.largeur_m.trim()
  const n = Number(brut.replace(',', '.'))
  if (!brut) delete entree.largeur_m
  else entree.largeur_m = Number.isFinite(n) ? n : brut
  return entree
}

const cleDe = (libelle, prises) => {
  const base = (libelle || 'gabarit').normalize('NFD').replace(/[̀-ͯ]/g, '')
    .toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || 'gabarit'
  let cle = base
  for (let n = 2; prises.includes(cle); n += 1) cle = `${base}_${n}`
  return cle
}

const brouillonDe = (cle, e) => ({
  cle,
  type: e?.type ?? '',
  forme: e?.forme ?? 'rectangle',
  ...Object.fromEntries(['libelle', 'source', ...NOMBRES].map((c) => [c, texteDe(e?.[c])])),
})

/** L'entrée envoyée : l'ancienne entrée (clés non touchées) + les champs saisis, jamais une cote devinée. */
function entreeDe(brouillon, ancienne) {
  const entree = { ...(ancienne || {}), nature: 'INTERDITE', forme: brouillon.forme }
  if (brouillon.type) entree.type = brouillon.type; else delete entree.type
  for (const c of ['libelle', 'source']) entree[c] = (brouillon[c] || '').trim()
  for (const c of NOMBRES) {
    const brut = (brouillon[c] || '').trim()
    const n = Number(brut.replace(',', '.'))
    if (!brut) delete entree[c]
    else entree[c] = Number.isFinite(n) ? n : brut
  }
  const inutiles = brouillon.forme === 'cercle' ? ['longueur_m', 'largeur_m'] : ['rayon_m']
  inutiles.forEach((c) => delete entree[c])
  return entree
}

export default function ReglagesGabaritsObstacle({ zonesTypes = null }) {
  const peutGerer = useHasPermission('calepinage_gerer')
  const [servi, setServi] = useState(zonesTypes && typeof zonesTypes === 'object' ? zonesTypes : {})
  const [brouillon, setBrouillon] = useState(null)
  const [erreurs, setErreurs] = useState({})
  const [message, setMessage] = useState(null)
  const [enCours, setEnCours] = useState(false)

  const lignes = Object.entries(servi).filter(([, e]) => estObstacle(e))
  const zones = Object.entries(servi).filter(([, e]) => estZone(e))
  const [zone, setZone] = useState(null) // ACAL495
  const champsFautifs = Object.keys(erreurs).filter((c) => c !== '_general')

  const envoyer = async (section) => {
    setMessage(null)
    setErreurs({})
    setEnCours(true)
    try {
      await calepinageApi.parametres.update({ zones_types: section })
      const res = await calepinageApi.parametres.get()
      setServi(res?.data?.zones_types ?? section)
      setBrouillon(null)
      setZone(null)
      setMessage('Gabarits d’obstacle enregistrés.')
    } catch (e) {
      const { message: motif, champs } = refusServeur(e)
      const parChamp = {}
      for (const [cle, texte] of Object.entries(champs)) parChamp[cle.split('.').pop()] = texte
      setErreurs(Object.keys(parChamp).length ? parChamp : { _general: motif || 'Rien n’a été enregistré.' })
    } finally {
      setEnCours(false)
    }
  }

  const enregistrer = () => {
    const cle = brouillon.cle || cleDe(brouillon.libelle, Object.keys(servi))
    return envoyer({ ...servi, [cle]: entreeDe(brouillon, servi[brouillon.cle]) })
  }
  const enregistrerZone = () => {
    const cle = zone.cle || cleDe(zone.libelle, Object.keys(servi))
    return envoyer({ ...servi, [cle]: zoneDe(zone, servi[zone.cle]) })
  }
  const changerZone = (c, v) => setZone((b) => ({ ...b, [c]: v }))
  const supprimer = (cle) => {
    const reste = { ...servi }
    delete reste[cle]
    return envoyer(reste)
  }
  const changer = (c, v) => setBrouillon((b) => ({ ...b, [c]: v }))
  const bouton = 'inline-flex min-h-11 items-center px-3 text-sm font-semibold underline'

  return (
    <Card className="mt-5 p-4" data-testid="acal494-gabarits">
      <h2 className="text-base font-semibold text-foreground">Gabarits d’obstacle</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Vos obstacles types (souche, climatiseur…) : l’atelier les pose d’un geste. Un obstacle interdit la pose.
      </p>

      {lignes.length === 0 && (
        <p className="mt-3 text-sm text-muted-foreground" data-testid="acal494-vide">Aucun gabarit d’obstacle enregistré.</p>
      )}
      <ul className="mt-3 divide-y divide-border">
        {lignes.map(([cle, e]) => (
          <li key={cle} className="flex flex-wrap items-center justify-between gap-2 py-1" data-testid={`acal494-ligne-${cle}`}>
            <span className="text-sm text-foreground">
              {e.libelle || cle} — {e.forme === 'cercle' ? `rayon ${texteDe(e.rayon_m)} m` : `${texteDe(e.longueur_m)} × ${texteDe(e.largeur_m)} m`}
            </span>
            {peutGerer && (
              <span>
                <button type="button" className={bouton} disabled={enCours} data-testid={`acal494-modifier-${cle}`} onClick={() => { setErreurs({}); setBrouillon(brouillonDe(cle, e)) }}>Modifier</button>
                <button type="button" className={bouton} disabled={enCours} data-testid={`acal494-supprimer-${cle}`} onClick={() => supprimer(cle)}>Supprimer</button>
              </span>
            )}
          </li>
        ))}
      </ul>

      {peutGerer && !brouillon && (
        <button type="button" className={`${bouton} mt-2`} data-testid="acal494-nouveau" onClick={() => { setErreurs({}); setBrouillon(brouillonDe(null, null)) }}>
          Ajouter un gabarit
        </button>
      )}

      {brouillon && (
        <div className="mt-3" data-testid="acal494-formulaire">
          {champsFautifs.length > 0 && (
            <p role="alert" data-testid="acal494-bandeau" className="rounded border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              Gabarit refusé — à corriger : {champsFautifs.join(', ')}.
            </p>
          )}
          <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="block text-xs font-medium text-foreground">
              Forme
              <select value={brouillon.forme} onChange={(e) => changer('forme', e.target.value)} data-testid="acal494-champ-forme"
                className="mt-0.5 block min-h-11 w-full border border-border bg-transparent px-2 text-sm text-foreground">
                {FORMES.map((f) => <option key={f.id} value={f.id}>{f.libelle}</option>)}
              </select>
            </label>
            <label className="block text-xs font-medium text-foreground">
              Type
              <select value={brouillon.type} onChange={(e) => changer('type', e.target.value)} data-testid="acal494-champ-type"
                aria-invalid={erreurs.type ? 'true' : undefined}
                className="mt-0.5 block min-h-11 w-full border border-border bg-transparent px-2 text-sm text-foreground">
                <option value="">—</option>
                {OBSTACLE_TYPES.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
              </select>
              {erreurs.type && <span role="alert" className="block text-xs text-destructive">{erreurs.type}</span>}
            </label>
            {CHAMPS.filter((c) => !c.formes || c.formes.includes(brouillon.forme)).map(({ cle, libelle }) => (
              <label key={cle} className="block text-xs font-medium text-foreground" data-testid={`acal494-champ-${cle}`}>
                {libelle}
                <input type="text" value={brouillon[cle]} disabled={enCours} onChange={(e) => changer(cle, e.target.value)}
                  aria-invalid={erreurs[cle] ? 'true' : undefined}
                  className="mt-0.5 block min-h-11 w-full border border-border bg-transparent px-2 text-sm text-foreground" />
                {erreurs[cle] && <span role="alert" className="block text-xs text-destructive" data-testid={`acal494-erreur-${cle}`}>{erreurs[cle]}</span>}
              </label>
            ))}
          </div>
          <button type="button" className={bouton} disabled={enCours} data-testid="acal494-enregistrer" onClick={enregistrer}>
            {enCours ? 'Enregistrement…' : 'Enregistrer le gabarit'}
          </button>
          <button type="button" className={bouton} disabled={enCours} onClick={() => setBrouillon(null)}>Annuler</button>
        </div>
      )}

      <h3 className="mt-5 text-sm font-semibold text-foreground">Zones réglementaires</h3>
      {zones.length === 0 && <p className="mt-2 text-sm text-muted-foreground">Aucune zone enregistrée.</p>}
      <ul className="mt-2 divide-y divide-border">
        {zones.map(([cle, e]) => (
          <li key={cle} className="flex flex-wrap items-center justify-between gap-2 py-1" data-testid={`acal495-ligne-${cle}`}>
            <span className="text-sm text-foreground">
              {e.libelle || cle} — {e.genre === 'polygone' ? 'contour tracé dans l’atelier' : `bande de ${texteDe(e.largeur_m)} m`}
            </span>
            {peutGerer && (
              <span>
                {e.genre === 'bande' && (
                  <button type="button" className={bouton} disabled={enCours} data-testid={`acal495-modifier-${cle}`} onClick={() => { setErreurs({}); setZone(brouillonZone(cle, e)) }}>Modifier</button>
                )}
                <button type="button" className={bouton} disabled={enCours} data-testid={`acal495-supprimer-${cle}`} onClick={() => supprimer(cle)}>Supprimer</button>
              </span>
            )}
          </li>
        ))}
      </ul>
      {peutGerer && !zone && (
        <button type="button" className={`${bouton} mt-2`} data-testid="acal495-nouveau" onClick={() => { setErreurs({}); setZone(brouillonZone(null, null)) }}>Ajouter une zone</button>
      )}
      {zone && (
        <div className="mt-3" data-testid="acal495-formulaire">
          {champsFautifs.length > 0 && (
            <p role="alert" data-testid="acal495-bandeau" className="rounded border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              Zone refusée — à corriger : {champsFautifs.join(', ')}.
            </p>
          )}
          <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {[['nature', 'Nature', NATURES, false], ['cote', 'Côté', COTES, true]].map(([cle, libelle, options, vide]) => (
              <label key={cle} className="block text-xs font-medium text-foreground">
                {libelle}
                <select value={zone[cle]} onChange={(e) => changerZone(cle, e.target.value)} data-testid={`acal495-champ-${cle}`}
                  className="mt-0.5 block min-h-11 w-full border border-border bg-transparent px-2 text-sm text-foreground">
                  {vide && <option value="">—</option>}
                  {options.map((o) => <option key={o.id} value={o.id}>{o.libelle}</option>)}
                </select>
              </label>
            ))}
            {CHAMPS_ZONE.map(({ cle, libelle }) => (
              <label key={cle} className="block text-xs font-medium text-foreground" data-testid={`acal495-champ-${cle}`}>
                {libelle}
                <input type="text" value={zone[cle]} disabled={enCours} onChange={(e) => changerZone(cle, e.target.value)}
                  aria-invalid={erreurs[cle] ? 'true' : undefined}
                  className="mt-0.5 block min-h-11 w-full border border-border bg-transparent px-2 text-sm text-foreground" />
                {erreurs[cle] && <span role="alert" className="block text-xs text-destructive" data-testid={`acal495-erreur-${cle}`}>{erreurs[cle]}</span>}
              </label>
            ))}
          </div>
          <button type="button" className={bouton} disabled={enCours} data-testid="acal495-enregistrer" onClick={enregistrerZone}>
            {enCours ? 'Enregistrement…' : 'Enregistrer la zone'}
          </button>
          <button type="button" className={bouton} disabled={enCours} onClick={() => setZone(null)}>Annuler</button>
        </div>
      )}
      {erreurs._general && <p role="alert" className="mt-2 text-xs text-destructive" data-testid="acal494-erreur-generale">{erreurs._general}</p>}
      {message && <p role="status" className="mt-3 text-sm text-muted-foreground" data-testid="acal494-message">{message}</p>}
    </Card>
  )
}
