/* eslint-disable react-refresh/only-export-components --
   `AFFECTATION_PALETTE`, `AFFECTATION_UNASSIGNED` et `couleurParModule` sont
   des constantes/fonctions PURES : le test jumeau les confronte, valeur par
   valeur, à la palette de `apps/web/src/scripts/roofPro11/scene3d.ts` (CAL126)
   pour qu'un module teinté ici ait EXACTEMENT la couleur qu'il a dans la 3D.
   Les sortir dans un `.js` voisin séparerait la table de son unique lecteur
   pour satisfaire une règle de fast-refresh qui ne s'applique pas à une
   constante — même dérogation que `module.config.jsx` du même module. */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { Button, Card, Spinner } from '../../../ui'
import RetourAtelier from '../atelier/RetourAtelier'

/* ============================================================================
   CAL234 — AFFECTER LES CHAÎNES À LA MAIN, AVEC LE VERDICT EN DIRECT.
   ----------------------------------------------------------------------------
   LE TROU QU'IL BOUCHE. CAL124 affecte AUTOMATIQUEMENT et CAL126 dessine le
   résultat, mais rien ne permettait à un installateur de CORRIGER
   l'affectation : le plan automatique était à prendre ou à laisser. Or
   sélectionner une suite de modules pour en faire une chaîne est le geste de
   base des outils comparés. Cet écran le donne : on GLISSE sur les modules,
   on les affecte à une chaîne / une entrée MPPT, et le serveur dit
   immédiatement si ça tient.

   AUCUN DIMENSIONNEMENT CÔTÉ ÉCRAN — C'EST LA RÈGLE CENTRALE.
   Cet écran ne calcule NI une longueur de chaîne admissible, NI une tension à
   froid, NI un nombre de chaînes par entrée. Il ne fait que deux choses :
     1. il AFFICHE la table d'affectation SERVEUR (`electrique.affectation`,
        contrat `calepinage_resultat.json`, CAL125), ligne par ligne, avec sa
        `source` (« automatique » ou « affectation manuelle ») ;
     2. il PROPOSE une affectation au serveur et RECOPIE son verdict.
   Un écran qui re-partitionnerait produirait une AUTRE partition que celle qui
   a été dimensionnée — exactement le raisonnement déjà écrit dans CAL126.

   LES DEUX CHEMINS, UNE SEULE FORME DE DONNÉE (posée par la moitié backend).
     * `POST calepinages/<pk>/evaluer-electrique/` avec
       `{ entree_electrique: { affectation_manuelle: [...] } }` : VERDICTE sans
       rien persister (garde en LECTURE). C'est l'appel anti-rebond du glissé.
     * `POST calepinages/<pk>/entree-electrique/` avec
       `{ affectation_manuelle: [...] }` : ENREGISTRE, et répond avec le
       `resultat` recalculé — les lignes touchées y portent alors
       `source: « affectation manuelle »`. Aucun second appel n'est enchaîné.
   Une ligne d'affectation est `{module, chaine, mppt, onduleur}` — les quatre
   seules clés admises par `normaliser_affectation_imposee`.

   LE REFUS VIENT DU SERVEUR, TOUJOURS. Les bloquants sont RECOPIÉS tels quels
   (ils NOMMENT la contrainte, le pan et la chaîne) ; un refus 400 est affiché
   SOUS le champ que le serveur nomme (règle fondateur du 08/09/2026 : jamais
   un « non enregistré » générique). L'écran n'invente aucun message.

   RELANCER L'AUTOMATIQUE NE PEUT PAS ÊTRE ACCIDENTEL. Effacer une affectation
   faite à la main demande une CONFIRMATION explicite : le premier clic arme,
   le second exécute. C'est la garantie exigée par le Done de la tâche.

   CALX53 — LES AVERTISSEMENTS DU SERVEUR SONT AFFICHÉS, PAS AVALÉS.
   `resultat.avertissements` (contrat `calepinage_resultat.json`) est rendu EN
   HAUT du panneau, avant la grille et les bornes de chaîne : c'est là que le
   serveur NOMME, par exemple, un coefficient de température non sourcé —
   `temp_coeff_voc_pct_c` / `temp_coeff_pmax_pct_c` tombés sur le défaut du
   noyau. Les bornes restent calculées ; l'utilisateur sait seulement qu'elles
   reposent sur une valeur que sa fiche produit ne publie pas. Les messages
   sont RECOPIÉS tels quels — cet écran n'en reformule ni n'en filtre aucun.
   ========================================================================== */

/* ── LA TEINTE DES CHAÎNES — MIROIR EXACT DE CAL126 ────────────────────────
   Ces valeurs sont celles de `AFFECTATION_PALETTE` / `AFFECTATION_UNASSIGNED`
   de `apps/web/src/scripts/roofPro11/scene3d.ts`. Les deux projets (portail
   Vite et site Astro) ne partagent aucun module : le seul moyen d'empêcher la
   dérive est de la VÉRIFIER, ce que fait le test jumeau en relisant le source
   TypeScript. Un module doit avoir la même couleur ici et dans la 3D, sans
   quoi l'installateur croit corriger une chaîne et en corrige une autre. */
export const AFFECTATION_PALETTE = [
  'rgb(36, 130, 214)', // bleu
  'rgb(232, 125, 33)', // orange
  'rgb(46, 163, 89)', // vert
  'rgb(184, 64, 158)', // magenta
  'rgb(0, 153, 158)', // sarcelle
  'rgb(212, 61, 71)', // rouge
  'rgb(115, 102, 199)', // violet
  'rgb(153, 133, 26)', // ocre
]

/** GRIS des modules NON affectés — jamais une couleur de groupe. */
export const AFFECTATION_UNASSIGNED = 'rgb(140, 143, 148)'

/** Clé de groupe d'une ligne. `null` = module non affecté (gris). */
export function cleGroupe(ligne, mode) {
  if (mode === 'chaine') return ligne.chaine == null ? null : `c${ligne.chaine}`
  if (ligne.mppt == null) return null
  return `o${ligne.onduleur ?? 1}m${ligne.mppt}`
}

/** Libellé lisible d'un groupe, pour la légende. */
export function libelleGroupe(ligne, mode) {
  if (mode === 'chaine') {
    return ligne.chaine == null ? 'Non affecté' : `Chaîne ${ligne.chaine}`
  }
  if (ligne.mppt == null) return 'Non affecté'
  return ligne.onduleur == null
    ? `MPPT ${ligne.mppt}`
    : `Onduleur ${ligne.onduleur} — MPPT ${ligne.mppt}`
}

/**
 * `module -> couleur` + légende, construits sur la SEULE table servie.
 * Ordre de première apparition, « Non affecté » en dernier — comme CAL126.
 */
export function couleurParModule(lignes, mode) {
  const couleurs = new Map()
  const parCle = new Map()
  const ordre = []
  let prochaine = 0
  for (const ligne of lignes || []) {
    if (!ligne || typeof ligne.module !== 'string') continue
    const cle = cleGroupe(ligne, mode)
    let entree = parCle.get(cle)
    if (!entree) {
      const couleur = cle == null
        ? AFFECTATION_UNASSIGNED
        : AFFECTATION_PALETTE[prochaine++ % AFFECTATION_PALETTE.length]
      entree = { cle, libelle: libelleGroupe(ligne, mode), couleur, nombre: 0 }
      parCle.set(cle, entree)
      ordre.push(cle)
    }
    entree.nombre += 1
    couleurs.set(ligne.module, entree.couleur)
  }
  const legende = ordre
    .map((c) => parCle.get(c))
    .sort((a, b) => (a.cle === null ? 1 : 0) - (b.cle === null ? 1 : 0))
  return { couleurs, legende }
}

/* ── L'ÉTAT LOCAL : la proposition, rien d'autre ───────────────────────── */

/** Les lignes manuelles ENREGISTRÉES, relues dans la table serveur. */
function manuellesDuServeur(lignes) {
  const proposition = new Map()
  for (const ligne of lignes || []) {
    if (ligne?.source !== 'affectation manuelle') continue
    proposition.set(ligne.module, {
      module: ligne.module,
      chaine: ligne.chaine ?? null,
      mppt: ligne.mppt ?? null,
      onduleur: ligne.onduleur ?? null,
    })
  }
  return proposition
}

/** La table AFFICHÉE = table serveur + proposition locale par-dessus. */
function tableAffichee(lignes, proposition) {
  return (lignes || []).map((ligne) => {
    const impose = proposition.get(ligne.module)
    if (!impose) return ligne
    return {
      ...ligne,
      chaine: impose.chaine,
      mppt: impose.mppt,
      onduleur: impose.onduleur,
      source: 'affectation manuelle',
    }
  })
}

/** Un entier strictement positif saisi, ou `null` (module décâblé). */
function numeroSaisi(texte) {
  const brut = String(texte ?? '').trim()
  if (brut === '') return null
  const n = Number(brut)
  return Number.isInteger(n) && n > 0 ? n : undefined
}

export default function AffectationChaines({ calepinageId }) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute

  /* Le `resultat` SERVEUR. `surcharge` est la réponse du dernier
     enregistrement (`entree-electrique/` répond avec le résultat recalculé) :
     aucun second appel n'est enchaîné pour le relire. */
  const { data: servi, loading: chargement, error: erreur } = useResource(
    () => calepinageApi.calepinages.resultat(id), id,
    { select: (r) => r.data, errorMessage: 'Affectation indisponible.' },
  )
  const [surcharge, setSurcharge] = useState(null)
  const resultat = surcharge ?? servi

  const [mode, setMode] = useState('chaine')
  const [selection, setSelection] = useState(() => new Set())
  /* `editions` = les affectations posées À LA MAIN dans cette session, PAS
     encore enregistrées. Les lignes déjà enregistrées, elles, sont lues dans
     la table serveur (elles y portent `source: « affectation manuelle »`) —
     aucune copie locale d'un état que le serveur détient déjà. */
  const [editions, setEditions] = useState(() => new Map())
  const [chaine, setChaine] = useState('')
  const [mppt, setMppt] = useState('')
  const [onduleur, setOnduleur] = useState('')
  const [erreursChamp, setErreursChamp] = useState({})
  const [verdict, setVerdict] = useState(null)
  const [verdictEnVol, setVerdictEnVol] = useState(false)
  const [armeAuto, setArmeAuto] = useState(false)
  const [enregistre, setEnregistre] = useState(null)

  const glisse = useRef(false)

  const lignesServeur = useMemo(
    () => resultat?.electrique?.affectation || [], [resultat],
  )
  const lignes = useMemo(
    () => tableAffichee(lignesServeur, editions), [lignesServeur, editions],
  )
  const { couleurs, legende } = useMemo(
    () => couleurParModule(lignes, mode), [lignes, mode],
  )

  const appliquerResultat = useCallback((donnees) => {
    setSurcharge(donnees)
    setEditions(new Map())
    setSelection(new Set())
    setVerdict(null)
  }, [])

  /* ── LE VERDICT EN DIRECT, ANTI-REBOND ───────────────────────────────────
     Rien n'est persisté par cet appel : la garde de `evaluer-electrique` est
     en LECTURE. Proposition vide ⇒ aucun appel (il n'y a rien à verdicter). */
  /* L'affectation manuelle COMPLÈTE envoyée au serveur : celle déjà
     enregistrée (relue dans la table) + les éditions en cours par-dessus.
     Sans cette union, enregistrer une chaîne effacerait les précédentes. */
  const lignesProposees = useMemo(() => {
    const par_module = manuellesDuServeur(lignesServeur)
    editions.forEach((ligne, module) => par_module.set(module, ligne))
    return Array.from(par_module.values())
  }, [lignesServeur, editions])

  useEffect(() => {
    // Aucune édition en cours ⇒ rien à verdicter (et rien à effacer : le
    // verdict affiché est déjà conditionné par `aProposition`).
    if (editions.size === 0) return undefined
    let monte = true
    const minuteur = setTimeout(() => {
      if (!monte) return
      setVerdictEnVol(true)
      calepinageApi.calepinages.evaluerElectrique(id, {
        entree_electrique: { affectation_manuelle: lignesProposees },
      })
        .then((r) => { if (monte) setVerdict(r.data) })
        .catch((err) => {
          if (!monte) return
          // Un 400 NOMME son champ : on le rend sous ce champ-là.
          const corps = err?.response?.data
          if (corps && typeof corps === 'object') setErreursChamp(corps)
          setVerdict(null)
        })
        .finally(() => { if (monte) setVerdictEnVol(false) })
    }, 300)
    return () => { monte = false; clearTimeout(minuteur) }
  }, [id, editions, lignesProposees])

  /* ── LE GESTE : GLISSER SUR LES MODULES ─────────────────────────────── */
  const basculer = useCallback((module, additif) => {
    setSelection((precedente) => {
      const suivante = new Set(additif ? precedente : [])
      if (additif && precedente.has(module)) suivante.delete(module)
      else suivante.add(module)
      return suivante
    })
  }, [])

  useEffect(() => {
    const relacher = () => { glisse.current = false }
    window.addEventListener('pointerup', relacher)
    return () => window.removeEventListener('pointerup', relacher)
  }, [])

  const affecterSelection = () => {
    const numeroChaine = numeroSaisi(chaine)
    const numeroMppt = numeroSaisi(mppt)
    const numeroOnduleur = numeroSaisi(onduleur)
    const erreurs = {}
    if (numeroChaine === undefined) {
      erreurs.chaine = 'Le numéro de chaîne doit être un entier strictement positif.'
    }
    if (numeroMppt === undefined) {
      erreurs.mppt = 'Le numéro d’entrée MPPT doit être un entier strictement positif.'
    }
    if (numeroOnduleur === undefined) {
      erreurs.onduleur = 'Le numéro d’onduleur doit être un entier strictement positif.'
    }
    if (selection.size === 0) {
      erreurs.selection = 'Aucun module sélectionné : glissez sur les modules à affecter.'
    }
    setErreursChamp(erreurs)
    if (Object.keys(erreurs).length > 0) return
    setEditions((precedente) => {
      const suivante = new Map(precedente)
      selection.forEach((module) => {
        suivante.set(module, {
          module,
          chaine: numeroChaine,
          mppt: numeroMppt,
          onduleur: numeroOnduleur,
        })
      })
      return suivante
    })
    setEnregistre(null)
  }

  const enregistrer = () => {
    setErreursChamp({})
    calepinageApi.calepinages.enregistrerEntreeElectrique(id, {
      affectation_manuelle: lignesProposees,
    })
      .then((r) => {
        appliquerResultat(r.data)
        setEnregistre('Affectation manuelle enregistrée.')
      })
      .catch((err) => {
        const corps = err?.response?.data
        setErreursChamp(corps && typeof corps === 'object'
          ? corps
          : { affectation_manuelle: 'Enregistrement refusé par le serveur.' })
      })
  }

  const relancerAuto = () => {
    if (!armeAuto) { setArmeAuto(true); return }
    setArmeAuto(false)
    setErreursChamp({})
    calepinageApi.calepinages.enregistrerEntreeElectrique(id, {
      affectation_manuelle: [],
    })
      .then((r) => {
        appliquerResultat(r.data)
        setEnregistre('Affectation automatique rétablie.')
      })
      .catch((err) => {
        const corps = err?.response?.data
        setErreursChamp(corps && typeof corps === 'object'
          ? corps
          : { affectation_manuelle: 'Rétablissement refusé par le serveur.' })
      })
  }

  if (chargement) {
    return (
      <>
        <RetourAtelier calepinageId={id} />
        <Spinner />
      </>
    )
  }
  if (erreur) {
    return (
      <>
        <RetourAtelier calepinageId={id} />
        <p className="text-sm text-destructive" data-testid="cal234-erreur">{erreur}</p>
      </>
    )
  }

  const parPan = new Map()
  lignes.forEach((ligne) => {
    const pan = ligne.pan || '—'
    if (!parPan.has(pan)) parPan.set(pan, [])
    parPan.get(pan).push(ligne)
  })

  const bloquants = verdict?.bloquants || []
  const alertes = verdict?.alertes || []
  const aProposition = editions.size > 0
  // CALX53 — les avertissements publiés AVEC le résultat (coefficients de
  // température non sourcés, exemplaire d'onduleur non nommé…).
  const avertissements = resultat?.avertissements || []

  return (
    <>
      <RetourAtelier calepinageId={id} />
      <Card className="flex flex-col gap-4 p-4" data-testid="cal234-ecran">
      <header className="flex flex-col gap-1">
        <h2 className="text-base font-semibold">Affectation des chaînes</h2>
        <p className="text-sm text-muted-foreground">
          Glissez sur les modules pour les sélectionner, puis affectez-les à une
          chaîne. Le serveur vérifie la contrainte à chaque modification ; rien
          n’est enregistré tant que vous ne validez pas.
        </p>
      </header>

      {/* CALX53 — AVANT la grille et les bornes : ce que le serveur avertit
          sur les données qui ont servi à les calculer. RECOPIÉ mot pour mot. */}
      {avertissements.length
        ? (
          <section className="flex flex-col gap-1" data-testid="calx53-avertissements">
            {avertissements.map((message) => (
              <p
                key={message}
                className="rounded border border-border bg-muted/40 px-2 py-1 text-xs text-muted-foreground"
                data-testid="calx53-avertissement"
              >
                {message}
              </p>
            ))}
          </section>
        )
        : null}

      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant={mode === 'chaine' ? 'default' : 'outline'}
          onClick={() => setMode('chaine')}
          data-testid="cal234-mode-chaine"
        >
          Teinter par chaîne
        </Button>
        <Button
          type="button"
          variant={mode === 'mppt' ? 'default' : 'outline'}
          onClick={() => setMode('mppt')}
          data-testid="cal234-mode-mppt"
        >
          Teinter par MPPT
        </Button>
      </div>

      {/* LA GRILLE — un bouton par module, teinté par la table SERVEUR. */}
      {Array.from(parPan.entries()).map(([pan, modules]) => (
        <section key={pan} className="flex flex-col gap-1" data-testid={`cal234-pan-${pan}`}>
          <p className="text-xs font-medium text-muted-foreground">{pan}</p>
          <div className="flex flex-wrap gap-1">
            {modules.map((ligne) => (
              <button
                key={ligne.module}
                type="button"
                data-testid={`cal234-module-${ligne.module}`}
                data-selectionne={selection.has(ligne.module) ? 'oui' : 'non'}
                data-source={ligne.source}
                aria-pressed={selection.has(ligne.module)}
                title={`${ligne.module} — ${libelleGroupe(ligne, mode)} (${ligne.source})`}
                style={{ backgroundColor: couleurs.get(ligne.module) || AFFECTATION_UNASSIGNED }}
                className={`h-7 w-12 rounded text-[10px] text-white ${
                  selection.has(ligne.module) ? 'ring-2 ring-foreground' : ''
                }`}
                onPointerDown={(e) => {
                  glisse.current = true
                  basculer(ligne.module, e.shiftKey || e.ctrlKey || e.metaKey)
                }}
                onPointerOver={() => {
                  // LE GLISSÉ : survoler pendant que le bouton est enfoncé
                  // AJOUTE le module à la sélection (jamais ne l'enlève).
                  if (!glisse.current) return
                  setSelection((precedente) => {
                    if (precedente.has(ligne.module)) return precedente
                    const suivante = new Set(precedente)
                    suivante.add(ligne.module)
                    return suivante
                  })
                }}
                onPointerUp={() => { glisse.current = false }}
              >
                {ligne.module.split('#').pop()}
              </button>
            ))}
          </div>
        </section>
      ))}

      <p className="text-sm" data-testid="cal234-selection">
        {selection.size === 0
          ? 'Aucun module sélectionné.'
          : `${selection.size} module(s) sélectionné(s).`}
      </p>
      {erreursChamp.selection
        ? <p className="text-sm text-destructive" data-testid="cal234-erreur-selection">{erreursChamp.selection}</p>
        : null}

      <div className="flex flex-wrap items-end gap-3">
        {[
          ['chaine', 'Chaîne', chaine, setChaine],
          ['mppt', 'Entrée MPPT', mppt, setMppt],
          ['onduleur', 'Onduleur', onduleur, setOnduleur],
        ].map(([code, libelle, valeur, poser]) => (
          <div key={code} className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground" htmlFor={`cal234-${code}`}>
              {libelle}
            </label>
            <input
              id={`cal234-${code}`}
              data-testid={`cal234-champ-${code}`}
              value={valeur}
              onChange={(e) => poser(e.target.value)}
              className="w-24 rounded border border-border px-2 py-1 text-sm"
              inputMode="numeric"
            />
            {/* L'ERREUR SOUS LE CHAMP QU'ELLE CONCERNE, jamais un bandeau vague. */}
            {erreursChamp[code]
              ? (
                <p className="text-xs text-destructive" data-testid={`cal234-erreur-${code}`}>
                  {erreursChamp[code]}
                </p>
              )
              : null}
          </div>
        ))}
        <Button type="button" onClick={affecterSelection} data-testid="cal234-affecter">
          Affecter la sélection
        </Button>
      </div>

      {/* LE VERDICT — RECOPIÉ du serveur, jamais reformulé. */}
      <section className="flex flex-col gap-1" data-testid="cal234-verdict">
        {!aProposition
          ? <p className="text-sm text-muted-foreground">Affectation automatique : aucune proposition manuelle en cours.</p>
          : null}
        {aProposition && verdictEnVol
          ? <p className="text-sm text-muted-foreground" data-testid="cal234-verdict-en-vol">Vérification en cours…</p>
          : null}
        {verdict
          ? (
            <p className="text-sm" data-testid="cal234-verdict-etat">
              Verdict du serveur :
              {' '}
              {verdict.verdict}
            </p>
          )
          : null}
        {bloquants.map((motif) => (
          <p key={motif} className="text-sm text-destructive" data-testid="cal234-bloquant">{motif}</p>
        ))}
        {alertes.map((motif) => (
          <p key={motif} className="text-sm text-muted-foreground" data-testid="cal234-alerte">{motif}</p>
        ))}
        {/* TOUT refus serveur est rendu, y compris sous une clé que cet écran
            ne connaît pas (`entree_electrique`, `temperatures`, …) : un 400
            SILENCIEUX serait exactement le « non enregistré » générique que la
            règle fondateur du 08/09/2026 interdit. Les clés déjà rendues sous
            leur propre champ ne sont pas répétées ici. */}
        {Object.entries(erreursChamp)
          .filter(([code]) => !['chaine', 'mppt', 'onduleur', 'selection'].includes(code))
          .map(([code, message]) => (
            <p
              key={code}
              className="text-sm text-destructive"
              data-testid={code === 'affectation_manuelle' ? 'cal234-erreur-affectation' : `cal234-erreur-${code}`}
            >
              {String(message)}
            </p>
          ))}
      </section>

      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="button"
          onClick={enregistrer}
          disabled={!aProposition || bloquants.length > 0}
          data-testid="cal234-enregistrer"
        >
          Enregistrer l’affectation manuelle
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={relancerAuto}
          data-testid="cal234-relancer-auto"
        >
          {armeAuto
            ? 'Confirmer : effacer l’affectation manuelle'
            : 'Relancer l’affectation automatique'}
        </Button>
        {armeAuto
          ? (
            <p className="text-sm text-destructive" data-testid="cal234-confirmation-auto">
              L’affectation faite à la main sera effacée. Confirmez pour continuer.
            </p>
          )
          : null}
        {enregistre
          ? <p className="text-sm text-muted-foreground" data-testid="cal234-enregistre">{enregistre}</p>
          : null}
      </div>

      <ul className="flex flex-wrap gap-3 text-xs" data-testid="cal234-legende">
        {legende.map((entree) => (
          <li key={entree.cle ?? 'non-affecte'} className="flex items-center gap-1">
            <span
              className="inline-block h-3 w-3 rounded"
              style={{ backgroundColor: entree.couleur }}
            />
            {entree.libelle}
            {' '}
            (
            {entree.nombre}
            )
          </li>
        ))}
      </ul>
    </Card>
    </>
  )
}
