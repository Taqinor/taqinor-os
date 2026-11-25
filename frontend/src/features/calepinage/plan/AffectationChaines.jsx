import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { Button, Card, Spinner } from '../../../ui'
import RetourAtelier from '../atelier/RetourAtelier'
import { affectationComplete, couleurParModule, drapeauOptimiseur, libelleGroupe, marquerModules } from './AffectationChaines.helpers'
import { phrasesChaines } from '../electrique/tensionsChaines'
import { etatAffiche, libelleEtat } from '../electrique/etatVerdict'
import ImportAffectation from './ImportAffectation'

/* ACAL44 — le motif d'un bouton d'écriture en lecture seule (devis lié figé). */
const MOTIF_LECTURE_SEULE = 'Conception figée : révisez le devis (nouvelle version) pour la modifier.'

/* « Relancer l'affectation automatique » : UNE requête (l'affectation manuelle vidée), partagée par
   l'écran ci-dessous et la barre de la carte de l'étape Électrique (« Raccorder automatiquement »).
   Rend le résultat recalculé ; un refus rend `{champ: motif}` (le serveur NOMME le champ). */
function relancerAffectationAuto(id) {
  return calepinageApi.calepinages.enregistrerEntreeElectrique(id, { affectation_manuelle: [] })
}
function refusAffectation(err, defaut) {
  const corps = err?.response?.data
  return corps && typeof corps === 'object' ? corps : { affectation_manuelle: defaut }
}
const REFUS_AUTO = 'Rétablissement refusé par le serveur.'

/** Item 12 (T4-U4-012) — des chaînes formées ne sont pas pour autant BONNES : les verdicts servis non conformes de la
    réponse (`electrique.verdicts[]`, conforme === false — ex. chaîne trop courte, MPPT hors plage par forte chaleur) et les
    alertes servies (`electrique.alertes[]`, si le serveur les publie) sont dits avec SES mots. `[]` quand tout est bon. */
function alertesDuRaccordement(electrique) {
  const verdicts = (Array.isArray(electrique?.verdicts) ? electrique.verdicts : [])
    .filter((v) => v && v.conforme === false)
    .map((v) => (typeof v.detail === 'string' && v.detail.trim()) || v.libelle)
  const alertes = (Array.isArray(electrique?.alertes) ? electrique.alertes : [])
    .map((a) => (typeof a === 'string' ? a : (a?.libelle || a?.detail || null)))
  return [...new Set([...verdicts, ...alertes].filter((t) => typeof t === 'string' && t.trim()))]
}

/** T4-U4-018 — les causes SERVIES par l'évaluation (`manquantes`, puis `bloquants`, `alertes`) et les alertes de la
    réponse du raccordement, chacune une fois, telles quelles. */
function causesServies(evaluation, alertesReponse = []) {
  const phrases = (cle) => (Array.isArray(evaluation?.[cle]) ? evaluation[cle] : [])
  return [...new Set([...phrases('manquantes'), ...phrases('bloquants'), ...phrases('alertes'), ...alertesReponse]
    .filter((t) => typeof t === 'string' && t.trim()))]
}

/** ACAL1536 — la phrase qui dit pourquoi aucune chaîne n'est apparue, d'après les rôles absents servis. */
function causeSansChaine(absents) {
  const manque = absents ?? []
  if (manque.includes('module')) return 'Choisissez d’abord le module de ce toit (module non désigné pour l’électrique).'
  if (manque.includes('onduleur')) return 'Choisissez d’abord l’onduleur : sans lui, aucune chaîne n’est formée.'
  return 'Aucune chaîne n’a pu être formée : vérifiez le module et l’onduleur choisis.'
}

/* Maquette Électrique (22/11) — LA BARRE D'ACTIONS POSÉE SUR LA CARTE (`cal-elec-actions-carte`).
   « Raccorder automatiquement » = le MÊME geste que « Relancer l'affectation automatique » ci-dessous
   (même requête, même confirmation quand une affectation faite à la main serait effacée, refus du
   serveur affichés tels quels) ; « Modifier une chaîne » ouvre l'écran d'affectation (`onModifier`).
   « Déplacer l'onduleur » n'est PAS proposé : aucune position d'onduleur n'est enregistrée (D-ACAL-70). */
export function BarreRaccordement({
  calepinageId, manuelles = false, lectureSeule = false, onRaccorde, onModifier,
}) {
  const [arme, setArme] = useState(false)
  const [enCours, setEnCours] = useState(false)
  const [refus, setRefus] = useState(null)
  const raccorder = () => {
    if (manuelles && !arme) { setArme(true); return }
    setArme(false)
    setRefus(null)
    setEnCours(true)
    relancerAffectationAuto(calepinageId)
      .then((r) => {
        onRaccorde?.(r.data)
        // ACAL1536 — 200 sans chaîne : la CAUSE est dite (matériel absent servi par `entree-electrique`).
        if ((r.data?.electrique?.affectation ?? []).some((l) => l?.chaine != null)) {
          const alertes = alertesDuRaccordement(r.data?.electrique)
          if (alertes.length) setRefus(['Chaînes formées, mais à revoir :', ...alertes])
          return undefined
        }
        // T4-U4-018 — aucune chaîne : la cause SERVIE (`manquantes` de la conception — matériel non désigné ou fiche
        // incomplète — puis bloquants/alertes, et les alertes de la réponse), jamais une phrase devinée ici. Le serveur
        // câble pans, champs au sol et ombrières (`chaines.py::_pans_poses`). Rien de servi : repli ACAL1536.
        const alertesReponse = alertesDuRaccordement(r.data?.electrique)
        return Promise.resolve(calepinageApi.calepinages.evaluerElectrique?.(calepinageId, {}))
          .then((ev) => causesServies(ev?.data, alertesReponse))
          .catch(() => alertesReponse)
          .then((causes) => {
            if (causes.length) { setRefus(['Aucune chaîne formée :', ...causes]); return undefined }
            return Promise.resolve(calepinageApi.calepinages.entreeElectrique?.(calepinageId))
              .then((e) => setRefus([causeSansChaine(e?.data?.absents)]))
              .catch(() => setRefus([causeSansChaine(null)]))
          })
      })
      .catch((err) => setRefus(Object.values(refusAffectation(err, REFUS_AUTO)).map(String)))
      .finally(() => setEnCours(false))
  }
  return (
    <div className="cel-barre" data-testid="cal-elec-actions-carte">
      {(arme || refus) && (
        <div className="cel-barre-message" role={refus ? 'alert' : 'status'}>
          {arme && <p>L’affectation faite à la main sera effacée. Confirmez pour continuer.</p>}
          {(refus ?? []).map((m) => <p key={m} className="cel-refus font-semibold">{m}</p>)}
        </div>
      )}
      <div role="toolbar" aria-label="Outils du raccordement" className="cel-barre-outils">
        <button type="button" className="cel-barre-principal" onClick={raccorder}
          disabled={lectureSeule || enCours} title={lectureSeule ? MOTIF_LECTURE_SEULE : undefined}>
          {arme ? 'Confirmer : effacer l’affectation manuelle' : 'Raccorder automatiquement'}
        </button>
        <button type="button" className="cel-barre-texte" onClick={onModifier}>Modifier une chaîne</button>
      </div>
    </div>
  )
}

/* ── L'ÉTAT LOCAL : la proposition, rien d'autre ───────────────────────── */

/** Les lignes manuelles ENREGISTRÉES, relues dans la table serveur. */
function manuellesDuServeur(lignes) {
  const proposition = new Map()
  for (const ligne of lignes || []) {
    if (ligne?.source !== 'affectation manuelle') continue
    proposition.set(ligne.module, marquerModules([ligne], drapeauOptimiseur(ligne))[0])
  }
  return proposition
}

/** La table AFFICHÉE = table serveur + proposition locale par-dessus. */
function tableAffichee(lignes, proposition) {
  return (lignes || []).map((ligne) => {
    const impose = proposition.get(ligne.module)
    if (!impose) return ligne
    const affichee = {
      ...ligne,
      chaine: impose.chaine,
      mppt: impose.mppt,
      onduleur: impose.onduleur,
      optimiseur: impose.optimiseur,
      source: 'affectation manuelle',
    }
    // ACAL725 — le drapeau proposé remplace celui servi ; absent de la proposition ⇒ absent de la ligne.
    if (!('optimiseur' in impose)) delete affichee.optimiseur
    return affichee
  })
}

/** Un entier strictement positif saisi, ou `null` (module décâblé). */
function numeroSaisi(texte) {
  const brut = String(texte ?? '').trim()
  if (brut === '') return null
  const n = Number(brut)
  return Number.isInteger(n) && n > 0 ? n : undefined
}

export default function AffectationChaines({ calepinageId, lectureSeule = false }) {
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
  const [optimiseur, setOptimiseur] = useState('inchange') // ACAL725 — 'inchange' | 'oui' | 'non'
  const [erreursChamp, setErreursChamp] = useState({})
  const [verdict, setVerdict] = useState(null)
  const [verdictEnVol, setVerdictEnVol] = useState(false)
  const [armeAuto, setArmeAuto] = useState(false)
  const [enregistre, setEnregistre] = useState(null)
  /* ACAL266 — les affectations OBSOLÈTES (module retiré ou pan supprimé,
     `electrique.affectation_obsolete`) ne sont JAMAIS élaguées en silence :
     leurs lignes ENREGISTRÉES (relues sur `entree-electrique/`) repartent à
     chaque enregistrement, tant que l'utilisateur ne les a pas retirées par
     le geste nommé « Retirer l'affectation obsolète <module> ». */
  const [stockees, setStockees] = useState(() => new Map())
  const [retirees, setRetirees] = useState(() => new Set())

  const glisse = useRef(false)

  const lignesServeur = useMemo(
    () => resultat?.electrique?.affectation || [], [resultat],
  )
  const obsoletes = useMemo(
    () => resultat?.electrique?.affectation_obsolete || [], [resultat],
  )
  useEffect(() => {
    if (!obsoletes.length) return undefined
    let monte = true
    calepinageApi.calepinages.entreeElectrique(id)
      .then((r) => {
        if (!monte) return
        const parModule = new Map()
        for (const ligne of r?.data?.entree?.affectation_manuelle || []) {
          if (ligne?.module) parModule.set(ligne.module, ligne)
        }
        setStockees(parModule)
      })
      .catch(() => { /* lecture best-effort : la ligne reste affichée */ })
    return () => { monte = false }
  }, [id, obsoletes])
  const lignes = useMemo(
    () => tableAffichee(lignesServeur, editions), [lignesServeur, editions],
  )
  const { couleurs, legende } = useMemo(
    () => couleurParModule(lignes, mode), [lignes, mode],
  )

  /* CALX16 — LA CHAÎNE LA PLUS FAIBLE EN OMBRAGE, telle que le serveur la
     DÉSIGNE (`electrique.chaine_la_plus_faible`, contrat
     `calepinage_resultat.json`). Rien n'est calculé ici : ni l'accès solaire,
     ni l'écart, ni la chaîne retenue. La clé est CONDITIONNELLE — absente
     quand le document ne porte aucun accès solaire par module, auquel cas le
     motif est déjà dans `avertissements` et rien n'est teinté (un module sans
     accès calculé n'est pas un module non ombré). */
  const chaineFaible = resultat?.electrique?.chaine_la_plus_faible || null
  const estFaible = useCallback(
    (ligne) => Boolean(chaineFaible)
      && ligne.chaine === chaineFaible.chaine
      && ligne.pan === chaineFaible.pan,
    [chaineFaible],
  )

  const appliquerResultat = useCallback((donnees) => {
    setSurcharge(donnees)
    setEditions(new Map())
    setSelection(new Set())
    setVerdict(null)
    setRetirees(new Set())
  }, [])

  /* ── LE VERDICT EN DIRECT, ANTI-REBOND ───────────────────────────────────
     Rien n'est persisté par cet appel : la garde de `evaluer-electrique` est
     en LECTURE. Proposition vide ⇒ aucun appel (il n'y a rien à verdicter). */
  /* L'affectation manuelle COMPLÈTE envoyée au serveur : celle déjà
     enregistrée (relue dans la table) + les éditions en cours par-dessus.
     Sans cette union, enregistrer une chaîne effacerait les précédentes. */
  const lignesProposees = useMemo(() => {
    const par_module = manuellesDuServeur(lignesServeur)
    // ACAL266 — les obsolètes ENREGISTRÉES repartent telles quelles, sauf
    // celles retirées par le geste nommé.
    for (const { module } of obsoletes) {
      if (retirees.has(module)) continue
      const stockee = stockees.get(module)
      if (stockee) par_module.set(module, marquerModules([stockee], drapeauOptimiseur(stockee))[0])
    }
    editions.forEach((ligne, module) => par_module.set(module, ligne))
    return Array.from(par_module.values())
  }, [lignesServeur, editions, obsoletes, stockees, retirees])

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

  /* ACAL647 — les modules ombrés à proposer pour un optimiseur : la LISTE vient du serveur
     (`modules_sous_seuil`, d'après le seuil société) ; rien n'est calculé ici. Relue à l'ouverture
     et après chaque enregistrement. */
  const [proposes, setProposes] = useState([])
  const [publication, setPublication] = useState(null) // ACAL1535 — l'état du dossier ENREGISTRÉ
  useEffect(() => {
    let monte = true
    Promise.resolve(calepinageApi.calepinages.evaluerElectrique(id, {}))
      .then((r) => {
        if (!monte) return
        setProposes(r?.data?.modules_sous_seuil || [])
        setPublication(r?.data?.publication || null)
      })
      .catch(() => { if (monte) { setProposes([]); setPublication(null) } })
    return () => { monte = false }
  }, [id, surcharge])

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
    // ACAL725 — « inchangé » garde le drapeau que le module porte déjà (absent s'il n'en a pas).
    const actuel = new Map(lignes.map((l) => [l.module, drapeauOptimiseur(l)]))
    setEditions((precedente) => {
      const suivante = new Map(precedente)
      selection.forEach((module) => {
        const valeur = { oui: true, non: false }[optimiseur] ?? actuel.get(module)
        const [ligne] = marquerModules(
          [{ module, chaine: numeroChaine, mppt: numeroMppt, onduleur: numeroOnduleur }], valeur)
        suivante.set(module, ligne)
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

  // ACAL647 — les proposés qui n'ont pas déjà le drapeau : « Les équiper » les marque EN BLOC
  // (`marquerModules`, ACAL725), numéros de chaîne / entrée / onduleur gardés, et enregistre.
  const aEquiper = lignes.filter((l) => proposes.includes(l.module) && drapeauOptimiseur(l) !== true)
  const equiper = () => {
    setErreursChamp({})
    const marques = marquerModules(aEquiper, true)
    calepinageApi.calepinages.enregistrerEntreeElectrique(id, {
      affectation_manuelle: affectationComplete(lignes, lignesProposees, marques),
    })
      .then((r) => {
        appliquerResultat(r.data)
        setEnregistre('Modules équipés d’un optimiseur.')
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
    relancerAffectationAuto(id)
      .then((r) => {
        appliquerResultat(r.data)
        setEnregistre('Affectation automatique rétablie.')
      })
      .catch((err) => setErreursChamp(refusAffectation(err, REFUS_AUTO)))
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
  // ACAL935 — l'état se lit comme au cadre du devis (mêmes mots : `etatVerdict.js`) ;
  // un serveur sans `etat` garde l'ancienne lecture du verdict à quatre mots.
  const etatLu = verdict && (verdict.etat
    ? etatAffiche(verdict, publication)
    : libelleEtat(
      { bloquant: 'bloquant', indetermine: 'a_completer' }[verdict.verdict] || 'pret',
      verdict.verdict === 'bloquant' ? bloquants.length : (verdict.manquantes || []).length))
  const alertes = verdict?.alertes || []
  const aProposition = editions.size > 0 || retirees.size > 0
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

      {/* ACAL266 — les affectations OBSOLÈTES, avec leur motif : gardées
          jusqu'au geste nommé, jamais élaguées en silence au POST. */}
      {obsoletes.length
        ? (
          <section className="flex flex-col gap-1" data-testid="acal266-obsoletes">
            <p className="text-sm font-medium">Affectations obsolètes</p>
            {obsoletes.map(({ module, motif }) => (
              <div
                key={module}
                className="flex flex-wrap items-center gap-2 text-xs"
                data-testid={`acal266-obsolete-${module}`}
              >
                <span>{`${module} — ${motif}`}</span>
                {retirees.has(module)
                  ? <span className="text-muted-foreground">retirée (à enregistrer)</span>
                  : (
                    <Button
                      type="button"
                      variant="outline"
                      disabled={lectureSeule}
                      onClick={() => setRetirees((avant) => new Set(avant).add(module))}
                      data-testid={`acal266-retirer-${module}`}
                    >
                      {`Retirer l’affectation obsolète ${module}`}
                    </Button>
                  )}
              </div>
            ))}
          </section>
        )
        : null}

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
                data-chaine-faible={estFaible(ligne) ? 'oui' : 'non'}
                data-optimiseur={ligne.optimiseur === true ? 'oui' : 'non'}
                aria-pressed={selection.has(ligne.module)}
                aria-label={ligne.optimiseur === true ? `${ligne.module.split('#').pop()} — optimiseur` : undefined}
                title={`${ligne.module} — ${libelleGroupe(ligne, mode)} (${ligne.source})${
                  ligne.optimiseur === true ? ' — optimiseur' : ''
                }${estFaible(ligne) ? ' — chaîne la plus faible en ombrage' : ''}`}
                style={{ backgroundColor: couleurs.get(ligne.module) || undefined }}
                className={`h-7 w-12 rounded text-xs text-foreground ${
                  selection.has(ligne.module) ? 'ring-2 ring-foreground' : ''
                } ${ligne.optimiseur === true ? 'border-2 border-solid border-primary' : ''} ${
                  estFaible(ligne) ? 'outline outline-2 outline-dashed outline-amber-500' : ''}`}
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
        {/* ACAL725 — l'électronique AU MODULE : inchangé / oui / non, posé avec la sélection. */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground" htmlFor="cal234-optimiseur">Optimiseur</label>
          <select id="cal234-optimiseur" data-testid="cal234-champ-optimiseur" value={optimiseur}
            onChange={(e) => setOptimiseur(e.target.value)}
            className="min-h-11 rounded border border-border bg-background px-2 text-sm">
            <option value="inchange">Inchangé</option>
            <option value="oui">Oui</option>
            <option value="non">Non</option>
          </select>
          {erreursChamp.optimiseur
            ? <p className="text-xs text-destructive" data-testid="cal234-erreur-optimiseur">{String(erreursChamp.optimiseur)}</p>
            : null}
        </div>
        <Button type="button" onClick={affecterSelection} data-testid="cal234-affecter">
          Affecter la sélection
        </Button>
      </div>

      {aEquiper.length > 0
        ? (
          <section className="flex flex-wrap items-center gap-3" data-testid="acal647-proposition">
            <p className="text-sm" data-testid="acal647-phrase">
              {aEquiper.length === 1
                ? '1 module ombré pourrait recevoir un optimiseur'
                : `${aEquiper.length} modules ombrés pourraient recevoir un optimiseur`}
            </p>
            <Button type="button" className="min-h-11" onClick={equiper} disabled={lectureSeule}
              title={lectureSeule ? MOTIF_LECTURE_SEULE : undefined} data-testid="acal647-equiper">
              Les équiper
            </Button>
          </section>
        )
        : null}

      {/* ACAL631 — un CSV valide REMPLIT la proposition (rien n'est enregistré avant « Enregistrer »). */}
      <ImportAffectation
        calepinageId={id}
        onProposer={(lignes) => {
          setEditions((precedente) => new Map([...precedente, ...lignes.map((l) => [l.module, l])]))
          setEnregistre(null)
        }}
      />

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
              {etatLu?.libelle}
            </p>
          )
          : null}
        {/* ACAL619 — la tension de chaque chaîne affectée dans cette session, d'après `chaines[]` servi. */}
        {phrasesChaines(verdict?.chaines, new Set([...editions.values()].map((e) => e.chaine))).map((phrase) => (
          <p key={phrase} role="status" className="text-sm text-foreground" data-testid="acal619-bulle">{phrase}</p>
        ))}
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
          .filter(([code]) => !['chaine', 'mppt', 'onduleur', 'optimiseur', 'selection'].includes(code))
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
          disabled={lectureSeule || !aProposition || bloquants.length > 0}
          title={lectureSeule ? MOTIF_LECTURE_SEULE : undefined}
          data-testid="cal234-enregistrer"
        >
          Enregistrer l’affectation manuelle
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={relancerAuto}
          disabled={lectureSeule}
          title={lectureSeule ? MOTIF_LECTURE_SEULE : undefined}
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

      {/* CALX16 — LA CHAÎNE À REGARDER, ET CE QUE CE SIGNAL N'EST PAS.
          La légende le dit en toutes lettres : c'est un signal de CÂBLAGE
          (le courant d'une série est celui de son module le plus faible),
          pas une perte d'énergie — l'énergie de l'ombrage est publiée dans
          le diagramme de pertes, jamais ici. La méthode est RECOPIÉE du
          serveur : l'écran n'en reformule rien. */}
      {chaineFaible
        ? (
          <section
            className="flex flex-col gap-1 rounded border border-amber-500/60 p-3 text-xs"
            data-testid="calx16-chaine-faible"
          >
            <p className="font-medium">
              Chaîne la plus faible en ombrage :
              {' '}
              <span data-testid="calx16-chaine">
                {`chaîne ${chaineFaible.chaine} (${chaineFaible.pan})`}
              </span>
            </p>
            <p className="text-muted-foreground" data-testid="calx16-module">
              {`Module le plus mal exposé : ${chaineFaible.module}`}
              {chaineFaible.acces_solaire === null
                || chaineFaible.acces_solaire === undefined
                ? ''
                : ` — accès solaire ${Math.round(chaineFaible.acces_solaire * 1000) / 10} %`}
            </p>
            <p className="text-muted-foreground" data-testid="calx16-methode">
              {chaineFaible.methode}
            </p>
            <p className="text-muted-foreground" data-testid="calx16-legende">
              Signal de câblage, pas une perte d’énergie : aucun kWh n’est
              retiré de la production à cause de ce repère. L’énergie de
              l’ombrage est publiée par le diagramme de pertes.
            </p>
          </section>
        )
        : null}
    </Card>
    </>
  )
}
