import { useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'
import { Button, Card } from '../../../ui'

/* ============================================================================
   ACAL572 — L'ÉCRAN RÉGLAGES « LESTAGE » (toit plat lesté).
   ----------------------------------------------------------------------------
   Les lignes viennent du registre SERVI (`GET parametres/` → `registre.lestage`,
   `[{cle, libelle, unite, texte, bloc}]`, bâti par le serveur depuis
   `services/lestage.py::PARAMETRES` et `services/lestage_zones.py`) : aucune
   liste ici. `bloc` = `global` (clé à plat de la section) ou `zones_de_pose`
   (objet imbriqué). Chaque valeur se saisit AVEC sa source (« notice K2 ») ;
   une ligne vide n'est pas envoyée.

   LE SERVEUR REMPLACE LA SECTION `lestage` ENTIÈRE : l'envoi repart donc de la
   section TELLE QUE SERVIE (zones de vent, zone par défaut, valeurs saisies
   ailleurs…) et ne change que les lignes de cet écran — jamais seulement les
   clés modifiées, qui effacerait `zones`. Ni pesanteur ni masse volumique de
   l'air ne sont demandées (constantes physiques, ACAL939).

   Hooks : la carte porte `id="lestage"`, chaque ligne `id="lestage-<cle>"`
   (clé du registre, stable) — le lien profond `#lestage-<cle>` ouvre la ligne.
   ========================================================================== */

const CLASSE_CHAMP = 'mt-0.5 block min-h-[44px] w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground'

/** L'entrée servie d'une ligne : à plat, ou dans `zones_de_pose`. */
function entreeServie(servi, r) {
  const bloc = r.bloc === 'zones_de_pose' ? servi?.zones_de_pose : servi
  const entree = bloc?.[r.cle]
  return entree && typeof entree === 'object' ? entree : null
}

function lignesDepuis(registre, servi) {
  return Object.fromEntries(registre.map((r) => {
    const entree = entreeServie(servi, r)
    return [r.cle, {
      valeur: entree?.valeur == null ? '' : String(entree.valeur),
      source: typeof entree?.source === 'string' ? entree.source : '',
    }]
  }))
}

/** Le refus serveur `{<clé>: motif}` ou `{lestage: {<clé>: motif}}` ramené
 *  aux lignes ; `zones_de_pose.<clé>` perd son préfixe. */
function refusParLigne(corps, registre) {
  const cles = new Set(registre.map((r) => r.cle))
  const parLigne = {}
  let general = null
  const poser = (champ, motif) => {
    const texte = Array.isArray(motif) ? motif.join(' ') : String(motif)
    const cle = String(champ).replace(/^zones_de_pose\./, '')
    if (cles.has(cle)) parLigne[cle] = texte
    else general = texte
  }
  for (const [champ, valeur] of Object.entries(corps && typeof corps === 'object' ? corps : {})) {
    if (valeur && typeof valeur === 'object' && !Array.isArray(valeur)) {
      for (const [cle, motif] of Object.entries(valeur)) poser(cle, motif)
    } else {
      poser(champ, valeur)
    }
  }
  return { parLigne, general }
}

export default function ReglagesLestage({ registre, servi, peutGerer }) {
  const [lignes, setLignes] = useState(() => lignesDepuis(registre, servi))
  const [dernierServi, setDernierServi] = useState(servi ?? {})
  const [erreurs, setErreurs] = useState({})
  const [general, setGeneral] = useState(null)
  const [message, setMessage] = useState(null)
  const [envoi, setEnvoi] = useState(false)
  if (!Array.isArray(registre) || registre.length === 0) return null

  const changer = (cle, champ, valeur) => setLignes((courant) => ({
    ...courant, [cle]: { ...courant[cle], [champ]: valeur },
  }))

  const enregistrer = async () => {
    setMessage(null)
    setGeneral(null)
    const section = { ...dernierServi }
    const pose = { ...(dernierServi.zones_de_pose ?? {}) }
    const refus = {}
    for (const r of registre) {
      const { valeur, source } = lignes[r.cle]
      const cible = r.bloc === 'zones_de_pose' ? pose : section
      if (!valeur.trim() && !source.trim()) {
        delete cible[r.cle]
        continue
      }
      const nombre = Number(valeur.trim().replace(',', '.'))
      if (!r.texte && valeur.trim() && !Number.isFinite(nombre)) {
        refus[r.cle] = `« ${r.libelle} » doit être un nombre.`
        continue
      }
      let envoyee = null
      if (valeur.trim()) envoyee = r.texte ? valeur.trim() : nombre
      cible[r.cle] = { valeur: envoyee, source: source.trim() }
    }
    if (Object.keys(refus).length > 0) {
      setErreurs(refus)
      return
    }
    if (Object.keys(pose).length > 0) section.zones_de_pose = pose
    else delete section.zones_de_pose
    setErreurs({})
    setEnvoi(true)
    try {
      const res = await calepinageApi.parametres.update({ lestage: section })
      const relu = res?.data?.lestage ?? section
      setDernierServi(relu)
      setLignes(lignesDepuis(registre, relu))
      setMessage('Réglages de lestage enregistrés.')
    } catch (e) {
      const { parLigne, general: autre } = refusParLigne(e?.response?.data, registre)
      setErreurs(parLigne)
      setGeneral(Object.keys(parLigne).length > 0 ? null
        : (autre || 'Le serveur n’a rendu aucun motif : rien n’a été enregistré.'))
    } finally {
      setEnvoi(false)
    }
  }

  const blocs = [
    ['global', 'Paramètres de la feuille de lestage'],
    ['zones_de_pose', 'Zones de pose (rive et coin)'],
  ]

  return (
    <Card id="lestage" className="mt-5 p-4" data-testid="acal572-lestage">
      <h2 className="text-base font-semibold text-foreground">Lestage (toit plat lesté)</h2>
      <p className="mt-1 text-xs text-muted-foreground">
        Chaque valeur porte sa source (la référence du texte appliqué, par
        exemple la notice du fabricant). Une ligne laissée vide n’est pas
        enregistrée : la feuille de lestage la nomme comme manquante, sans
        valeur supposée.
      </p>
      <form noValidate onSubmit={(e) => { e.preventDefault(); enregistrer() }}>
        {blocs.map(([bloc, titre]) => {
          const rangees = registre.filter((r) => r.bloc === bloc)
          if (rangees.length === 0) return null
          return (
            <fieldset key={bloc} className="mt-4 border-t border-border/60 pt-3"
              data-testid={`acal572-bloc-${bloc}`}>
              <legend className="text-sm font-semibold text-foreground">{titre}</legend>
              {rangees.map((r) => (
                <div key={r.cle} className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2"
                  data-testid={`acal572-ligne-${r.cle}`}>
                  <label className="block text-xs text-muted-foreground" htmlFor={`lestage-${r.cle}`}>
                    {r.libelle}{r.unite ? ` (${r.unite})` : ''}
                    <input
                      id={`lestage-${r.cle}`}
                      type={r.texte ? 'text' : 'number'}
                      step={r.texte ? undefined : 'any'}
                      value={lignes[r.cle].valeur}
                      disabled={!peutGerer || envoi}
                      aria-invalid={erreurs[r.cle] ? 'true' : undefined}
                      aria-describedby={erreurs[r.cle] ? `acal572-erreur-${r.cle}` : undefined}
                      onChange={(e) => changer(r.cle, 'valeur', e.target.value)}
                      className={CLASSE_CHAMP}
                    />
                  </label>
                  <label className="block text-xs text-muted-foreground">
                    Source
                    <input
                      type="text"
                      value={lignes[r.cle].source}
                      disabled={!peutGerer || envoi}
                      data-testid={`acal572-source-${r.cle}`}
                      onChange={(e) => changer(r.cle, 'source', e.target.value)}
                      className={CLASSE_CHAMP}
                    />
                  </label>
                  {erreurs[r.cle] && (
                    <p id={`acal572-erreur-${r.cle}`} role="alert"
                      className="text-xs text-destructive sm:col-span-2"
                      data-testid={`acal572-erreur-${r.cle}`}>
                      {erreurs[r.cle]}
                    </p>
                  )}
                </div>
              ))}
            </fieldset>
          )
        })}
        {peutGerer && (
          <Button type="submit" size="sm" variant="outline" className="mt-4 min-h-[44px]"
            disabled={envoi} data-testid="acal572-enregistrer">
            {envoi ? 'Enregistrement…' : 'Enregistrer le lestage'}
          </Button>
        )}
      </form>
      {general && (
        <p role="alert" className="mt-2 text-xs text-destructive" data-testid="acal572-erreur-generale">{general}</p>
      )}
      {message && (
        <p role="status" className="mt-2 text-xs text-muted-foreground" data-testid="acal572-message">{message}</p>
      )}
    </Card>
  )
}
