/* eslint-disable react-refresh/only-export-components --
   Le registre (`REGISTRE_SIMULATION`/`REGISTRE_ELECTRIQUE_SOCIETE`) est une
   table de données lue par le test jumeau (« une ligne par clé du registre »)
   ET par l'écran par défaut : la sortir dans un `.js` voisin séparerait la
   table de son unique lecteur pour satisfaire une règle de fast-refresh qui
   ne s'applique pas à une constante — même dérogation que `commun/Provenance
   .jsx` et `module.config.jsx` du même module. */
import { useEffect, useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'
import { useHasPermission } from '../../../hooks/useHasPermission'
import { Badge, Card, Spinner } from '../../../ui'

/* ============================================================================
   CALX69 — DONNER UNE SAISIE AUX RÉGLAGES DE SIMULATION ET D'ÉLECTRIQUE,
   AVEC PROVENANCE OBLIGATOIRE.
   ----------------------------------------------------------------------------
   CONSTAT (vérifié cette session). `PUT /api/django/calepinage/parametres/`
   écrit déjà toute section admise (`views/parametres.py`), mais le seul
   composant qui l'appelle en écriture est `Bibliotheque.jsx` (CALX43, sections
   `presets`/`favoris_materiel`) : les deux sections ouvertes par CALX145
   (`simulation`, `electrique_societe`) n'avaient AUCUNE porte de saisie —
   chaque étape de la chaîne de pertes et chaque contrôle électrique qui en
   dépend restait donc condamné à l'« omis » faute d'écran pour les renseigner.

   LE REGISTRE N'EST PAS SERVI PAR LE GET (constat vérifié, gap signalé).
   `views/parametres.py::_forme_reglages` déclare `simulation` et
   `electrique_societe` en `DictField()` NU — le libellé français, l'unité et
   la référence doctrinale de chaque clé ne sont publiés NULLE PART par
   l'API : ils ne vivent que dans `services/parametres_cles.py`
   (`CLES_SIMULATION`, `CLES_ELECTRIQUE_SOCIETE`), un module Python que cet
   écran ne peut pas importer. Le contrat committé
   (`contract_samples/parametres_calepinage.json`) ne porte lui aussi que DEUX
   exemples de valeurs, jamais la liste complète des clés admises. Cette lane
   étant strictement frontend (aucun fichier backend touché), les deux tables
   ci-dessous redéclarent donc, DANS L'ORDRE où le serveur les déclare, les
   clés et leur libellé/unité/référence — un doublon assumé, pas inventé
   (chaque valeur est recopiée du fichier serveur). LE GAP POUR UNE TÂCHE
   BACKEND FUTURE : servir ces deux tables depuis `GET parametres/` (par
   exemple sous une clé `registre`, comme `kits` l'est déjà pour CAL246)
   éviterait cette redéclaration et la garantie qu'elle reste à jour serait
   alors mécanique plutôt que manuelle.

   LA DISCIPLINE DE SAISIE, IDENTIQUE À CELLE DU SERVEUR
   (`services/parametres.py::_normaliser_section_a_registre`) :
     * une clé JAMAIS entamée (valeur, source ET référence toutes vides) est
       OMISE de l'envoi — rien n'est inventé, le comportement d'aujourd'hui
       reste inchangé pour elle ;
     * une clé ENTAMÉE (au moins un des trois champs rempli) sans valeur, ou
       sans provenance choisie, est REFUSÉE avant tout envoi réseau — l'erreur
       se pose SOUS la clé fautive et le bandeau la NOMME (règle fondateur du
       08/09/2026) ;
     * le refus 400 du serveur (qui nomme lui aussi la clé fautive) atterrit
       exactement au même endroit.
   Les valeurs CITÉES des logiciels concurrents (la référence doctrinale du
   registre, ex. la tolérance PV*SOL) sont affichées comme un simple REPÈRE
   sous chaque ligne — jamais copiées dans le champ « valeur » : la saisie
   reste toujours celle, et seulement celle, que la société a tapée.
   ========================================================================== */

//: `services/parametres_cles.py::SOURCES_ADMISES` — les QUATRE provenances
//: admises par le serveur ; toute autre chaîne est refusée en la nommant.
const SOURCES = [
  ['societe', 'Réglage société'],
  ['mesure', 'Mesure'],
  ['saisie', 'Saisie'],
  ['texte', 'Texte cité'],
]

//: `services/parametres_cles.py::CLES_SIMULATION` — `[clé, libellé, unité,
//: référence doctrinale]`, une ligne par clé, DANS L'ORDRE DÉCLARÉ CÔTÉ
//: SERVEUR.
export const REGISTRE_SIMULATION = [
  ['fenetre_annees', 'Fenêtre d’années météo', 'années', 'PVGIS — seriescalc, fenêtre pluriannuelle'],
  ['mode_meteo', 'Mode météo (année type ou fenêtre pluriannuelle)', '', 'HelioScope — TMY weather file primer'],
  ['modele_iam', 'Modèle d’incidence (IAM)', '', 'PVsyst — Array incidence loss (IAM)'],
  ['b0_iam', 'Coefficient b0 du modèle ASHRAE', '', 'PVsyst — Array incidence loss (IAM)'],
  ['sigma_modele_pct', 'Incertitude de simulation (σ modèle)', '%', 'PVsyst — P50/P90 evaluations'],
  ['sigma_biais_meteo_pct', 'Biais long terme de la source météo (σ)', '%', 'PVsyst — P50/P90 evaluations'],
  ['sigma_meteo_saisi_pct', 'Variabilité interannuelle saisie (σ météo)', '%', 'PVsyst — P50/P90 evaluations'],
  ['tolerance_validation_pct', 'Tolérance d’écart admise face à PVGIS', '%', 'Décision fondateur 21/09/2026 — aucun verdict sans tolérance saisie'],
  ['resolution_minutes', 'Pas de temps de la simulation', 'minutes', 'PVGIS — seriescalc, pas horaire'],
  ['albedo_mensuel', 'Albédo du sol, mois par mois', '', 'PVsyst — Array and system losses'],
  ['annees_exploitation', 'Durée d’exploitation simulée', 'années', 'PVsyst — Array and system losses'],
  ['regle_qualite_module', 'Règle de qualité module (tolérance de puissance)', '', 'PVsyst — Module quality losses'],
  ['lid_par_techno', 'Perte LID déclarée par technologie de cellule', '%', 'PVsyst — LID loss (aucune valeur par défaut proposée)'],
  ['mismatch_fabricant_pct', 'Mismatch de fabrication entre modules', '%', 'PVsyst — Array and system losses'],
  ['modele_degradation', 'Modèle de dégradation pluriannuelle', '', 'PVsyst — Array and system losses'],
  ['thermique_par_pose', 'Coefficients Uc/Uv par type de pose', 'W/m²K et W/m³sK', 'PVsyst — Array thermal losses (Faiman)'],
  ['attenuation_horizon', 'Atténuation appliquée au profil d’horizon', '', 'PVGIS — printhorizon, profil DEM'],
]

//: `services/parametres_cles.py::CLES_ELECTRIQUE_SOCIETE` — même forme,
//: même discipline d'ajout que ci-dessus.
export const REGISTRE_ELECTRIQUE_SOCIETE = [
  ['tolerance_polystring_acceptable_pct', 'Tolérance de polystring acceptable', '%', 'PV*SOL — Configuration check (valeur du logiciel citée en repère, jamais préremplie)'],
  ['tolerance_polystring_bloquante_pct', 'Tolérance de polystring bloquante', '%', 'PV*SOL — Configuration check (valeur du logiciel citée en repère, jamais préremplie)'],
  ['seuil_desequilibre_pct', 'Seuil de déséquilibre entre chaînes', '%', 'PV*SOL — Configuration check'],
  ['borne_usuelle_dc_ac', 'Borne usuelle du rapport DC/AC', '', 'PV*SOL — Configuration check'],
  ['seuil_alerte_dc_ac', 'Seuil d’alerte du rapport DC/AC', '', 'PV*SOL — Configuration check'],
  ['correspondances_nomenclature', 'Correspondances de nomenclature du bordereau', '', 'Réglage société — aucun code article n’est deviné'],
  ['regle_bom_structure', 'Règle de sortie de la structure hors bordereau électrique', '', 'Décision fondateur 21/09/2026 — la structure sort du bordereau électrique'],
  ['cos_phi_par_defaut', 'Cos φ retenu à défaut de mesure', '', 'Réglage société — aucune valeur n’est supposée'],
]

const SECTIONS = [
  ['simulation', 'Simulation', REGISTRE_SIMULATION],
  ['electrique_societe', 'Électrique — société', REGISTRE_ELECTRIQUE_SOCIETE],
]

const LIGNE_VIDE = { valeurTexte: '', source: '', reference: '' }

/** Le libellé français d'une clé, cherché dans les deux registres. */
function libelleDe(cle) {
  for (const [, , registre] of SECTIONS) {
    const trouve = registre.find(([c]) => c === cle)
    if (trouve) return trouve[1]
  }
  return cle
}

/** Le texte affiché dans le champ « valeur », depuis ce que le serveur sert. */
function texteDeValeur(valeur) {
  if (valeur === undefined || valeur === null) return ''
  if (typeof valeur === 'string') return valeur
  return JSON.stringify(valeur)
}

/** La valeur ENVOYÉE, depuis le texte tapé — nombre, table (JSON) ou texte
 *  brut selon ce que l'utilisateur a tapé, jamais un type deviné à l'avance. */
function valeurDepuisTexte(texte) {
  try {
    return JSON.parse(texte)
  } catch {
    return texte
  }
}

/** Les brouillons `{clé: {valeurTexte, source, reference}}` d'une section,
 *  une entrée par clé du REGISTRE — une clé non saisie reste VIDE, jamais
 *  complétée d'une valeur par défaut. */
function lignesDepuis(registre, section) {
  const servi = section && typeof section === 'object' ? section : {}
  const lignes = {}
  for (const [cle] of registre) {
    const existant = servi[cle]
    lignes[cle] = existant && typeof existant === 'object'
      ? {
        valeurTexte: texteDeValeur(existant.valeur),
        source: typeof existant.source === 'string' ? existant.source : '',
        reference: typeof existant.reference === 'string' ? existant.reference : '',
      }
      : { ...LIGNE_VIDE }
  }
  return lignes
}

/** La section ENVOYABLE au serveur + les erreurs de saisie, AVANT tout envoi
 *  réseau. Une clé jamais entamée est OMISE ; une clé entamée sans valeur ou
 *  sans source est REFUSÉE, jamais envoyée à moitié remplie. */
function validerSection(registre, lignes) {
  const section = {}
  const erreurs = {}
  for (const [cle, libelle] of registre) {
    const ligne = lignes[cle] || LIGNE_VIDE
    const valeurTexte = (ligne.valeurTexte || '').trim()
    const source = (ligne.source || '').trim()
    const reference = (ligne.reference || '').trim()
    if (!valeurTexte && !source && !reference) continue
    if (!valeurTexte) {
      erreurs[cle] = `« ${libelle} » doit porter une valeur : une clé `
        + 'entamée sans valeur ne règle rien. Videz aussi sa source pour '
        + 'revenir au comportement d’aujourd’hui.'
      continue
    }
    if (!source) {
      erreurs[cle] = `« ${libelle} » doit porter sa provenance « source » : `
        + 'aucune valeur n’est admise sans elle. Provenances admises : '
        + 'societe, mesure, saisie, texte.'
      continue
    }
    section[cle] = { valeur: valeurDepuisTexte(valeurTexte), source, reference }
  }
  return { section, erreurs }
}

function LigneReglage({
  cle, libelle, unite, reference, ligne, erreur, disabled, onChange,
}) {
  const majer = (champ, valeur) => onChange(cle, champ, valeur)
  return (
    <fieldset className="mt-4 border-t border-border/60 pt-4" data-testid={`calx69-ligne-${cle}`}>
      <legend className="text-sm font-semibold text-foreground">
        {libelle}{unite ? ` (${unite})` : ''}
      </legend>
      {reference && (
        <p className="text-xs text-muted-foreground" data-testid={`calx69-aide-${cle}`}>
          {reference}
        </p>
      )}
      <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <label className="block" data-testid={`calx69-valeur-${cle}`}>
          <span className="text-xs text-muted-foreground">Valeur</span>
          <input
            type="text"
            id={`calx69-${cle}`}
            value={ligne.valeurTexte}
            disabled={disabled}
            aria-invalid={erreur ? 'true' : undefined}
            aria-describedby={erreur ? `calx69-erreur-${cle}` : undefined}
            onChange={(e) => majer('valeurTexte', e.target.value)}
            className="mt-0.5 block w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground"
          />
        </label>
        <label className="block" data-testid={`calx69-source-${cle}`}>
          <span className="text-xs text-muted-foreground">Source</span>
          <select
            value={ligne.source}
            disabled={disabled}
            onChange={(e) => majer('source', e.target.value)}
            className="mt-0.5 block w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground"
          >
            <option value="">— aucune —</option>
            {SOURCES.map(([code, label]) => <option key={code} value={code}>{label}</option>)}
          </select>
        </label>
        <label className="block" data-testid={`calx69-reference-${cle}`}>
          <span className="text-xs text-muted-foreground">Référence (facultatif)</span>
          <input
            type="text"
            value={ligne.reference}
            disabled={disabled}
            onChange={(e) => majer('reference', e.target.value)}
            className="mt-0.5 block w-full border border-border bg-transparent px-2 py-1 text-sm text-foreground"
          />
        </label>
      </div>
      {erreur && (
        <p
          id={`calx69-erreur-${cle}`}
          data-testid={`calx69-erreur-${cle}`}
          role="alert"
          className="mt-2 text-xs text-destructive"
        >
          {erreur}
        </p>
      )}
    </fieldset>
  )
}

export default function ReglagesSimulation() {
  const peutGerer = useHasPermission('calepinage_gerer')

  const [lignesSimulation, setLignesSimulation] = useState({})
  const [lignesElectrique, setLignesElectrique] = useState({})
  const [chargement, setChargement] = useState(true)
  const [erreurChargement, setErreurChargement] = useState(null)
  const [erreurs, setErreurs] = useState({})
  const [message, setMessage] = useState(null)
  const [enregistrement, setEnregistrement] = useState(false)

  useEffect(() => {
    let annule = false
    Promise.resolve(calepinageApi.parametres.get())
      .then((res) => {
        if (annule) return
        const data = res?.data ?? {}
        setLignesSimulation(lignesDepuis(REGISTRE_SIMULATION, data.simulation))
        setLignesElectrique(lignesDepuis(REGISTRE_ELECTRIQUE_SOCIETE, data.electrique_societe))
      })
      .catch(() => {
        if (!annule) {
          setErreurChargement('Réglages indisponibles : la page n’a pas pu être chargée.')
        }
      })
      .finally(() => { if (!annule) setChargement(false) })
    return () => { annule = true }
  }, [])

  const changer = (setter) => (cle, champ, valeur) => setter(
    (lignes) => ({ ...lignes, [cle]: { ...(lignes[cle] || LIGNE_VIDE), [champ]: valeur } }),
  )
  const changerSimulation = changer(setLignesSimulation)
  const changerElectrique = changer(setLignesElectrique)

  const enregistrer = async () => {
    const simulation = validerSection(REGISTRE_SIMULATION, lignesSimulation)
    const electrique = validerSection(REGISTRE_ELECTRIQUE_SOCIETE, lignesElectrique)
    const toutesErreurs = { ...simulation.erreurs, ...electrique.erreurs }
    setMessage(null)
    if (Object.keys(toutesErreurs).length > 0) {
      setErreurs(toutesErreurs)
      return
    }
    setErreurs({})
    setEnregistrement(true)
    try {
      await calepinageApi.parametres.update({ simulation: simulation.section })
      const res = await calepinageApi.parametres.update(
        { electrique_societe: electrique.section },
      )
      const data = res?.data ?? {}
      setLignesSimulation(lignesDepuis(REGISTRE_SIMULATION, data.simulation))
      setLignesElectrique(lignesDepuis(REGISTRE_ELECTRIQUE_SOCIETE, data.electrique_societe))
      setMessage('Réglages enregistrés.')
    } catch (e) {
      const corps = e?.response?.data
      if (corps && typeof corps === 'object') {
        const mappees = {}
        for (const [champ, valeur] of Object.entries(corps)) {
          mappees[champ] = Array.isArray(valeur) ? valeur.join(' ') : String(valeur)
        }
        setErreurs(mappees)
      } else {
        setErreurs({ _general: 'Le serveur n’a rendu aucun motif : rien n’a été enregistré.' })
      }
    } finally {
      setEnregistrement(false)
    }
  }

  if (chargement) {
    return <div className="page" data-testid="calx69-ecran"><Spinner /></div>
  }
  if (erreurChargement) {
    return (
      <div className="page" data-testid="calx69-ecran">
        <p role="alert" className="text-sm text-destructive" data-testid="calx69-erreur-chargement">
          {erreurChargement}
        </p>
      </div>
    )
  }

  const champsFautifs = Object.keys(erreurs)
  const lignesParSection = { simulation: lignesSimulation, electrique_societe: lignesElectrique }
  const changerParSection = { simulation: changerSimulation, electrique_societe: changerElectrique }

  return (
    <div className="page" data-testid="calx69-ecran">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h1 className="text-lg font-semibold text-foreground">
          Réglages de simulation et d’électrique
        </h1>
        {!peutGerer && (
          <Badge variant="outline" data-testid="calx69-lecture-seule">Lecture seule</Badge>
        )}
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        Chaque valeur saisie porte sa provenance : sans elle, elle n’est pas
        enregistrée. Une clé non saisie reste omise — chaque étape de
        simulation ou contrôle électrique qui en dépend l’affiche comme telle,
        jamais un forfait. Les repères sous chaque ligne sont ceux publiés par
        les logiciels du marché, cités à titre d’aide : ils ne sont jamais
        recopiés dans la valeur.
      </p>

      {champsFautifs.length > 0 && (
        <p
          role="alert"
          data-testid="calx69-bandeau"
          className="mt-3 rounded border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          Réglages incomplets — à corriger :{' '}
          {champsFautifs.map((cle, i) => (
            <span key={cle}>
              {i > 0 && ', '}
              <a href={`#calx69-${cle}`} className="underline">{libelleDe(cle)}</a>
            </span>
          ))}
        </p>
      )}

      {SECTIONS.map(([section, titre, registre]) => (
        <Card key={section} className="mt-5 p-4" data-testid={`calx69-section-${section}`}>
          <h2 className="text-base font-semibold text-foreground">{titre}</h2>
          {registre.map(([cle, libelle, unite, reference]) => (
            <LigneReglage
              key={cle}
              cle={cle}
              libelle={libelle}
              unite={unite}
              reference={reference}
              ligne={lignesParSection[section][cle] || LIGNE_VIDE}
              erreur={erreurs[cle]}
              disabled={!peutGerer || enregistrement}
              onChange={changerParSection[section]}
            />
          ))}
        </Card>
      ))}

      {peutGerer ? (
        <button
          type="button"
          disabled={enregistrement}
          data-testid="calx69-enregistrer"
          className="mt-4 text-sm font-semibold underline"
          onClick={enregistrer}
        >
          {enregistrement ? 'Enregistrement…' : 'Enregistrer les réglages'}
        </button>
      ) : (
        <p className="mt-4 text-xs text-muted-foreground">
          Sans le droit « gérer le calepinage », la saisie n’est pas proposée
          ici.
        </p>
      )}

      {erreurs._general && (
        <p role="alert" className="mt-2 text-xs text-destructive" data-testid="calx69-erreur-generale">
          {erreurs._general}
        </p>
      )}
      {message && (
        <p role="status" className="mt-3 text-sm text-muted-foreground" data-testid="calx69-message">
          {message}
        </p>
      )}
    </div>
  )
}
