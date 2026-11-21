import { useCallback, useEffect, useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'
import { useHasPermission } from '../../../hooks/useHasPermission'
import { Button, Card } from '../../../ui'
import { useConfirmDialog } from '../../../ui/confirm'

/* ============================================================================
   ACAL559 — « RÉGLAGES › CALEPINAGE › SYSTÈMES DE FIXATION ».
   ----------------------------------------------------------------------------
   Le catalogue de la société (contrat `calepinage_systemes_fixation.json`,
   routes ACAL558) : un système (code, libellé, fabricant, mode de pose,
   PROVENANCE) et ses composants (rôle, libellé, unité, produit du stock
   facultatif, règle de quantité, SOURCE). L'onglet Fixation de chaque
   calepinage en tire la nomenclature ; rien n'est pré-rempli (D12).
   Un refus 400 nomme le champ par son chemin (`provenance`,
   `composants[1].source`) : il est rendu SOUS ce champ. Les nombres de la
   règle se saisissent tels quels (`step="any"`, `noValidate`), jamais
   arrondis. Réglages société, niveau expert, hors parcours guidé.
   ========================================================================== */

//: `SystemeFixation.ModePose` (models.py) — même ordre.
const MODES_POSE = [
  ['toiture_inclinee', 'Toiture inclinée'], ['bac_acier', 'Bac acier'],
  ['toit_plat_leste', 'Toit plat — lesté'], ['toit_plat_fixe', 'Toit plat — fixé'],
  ['sol', 'Au sol'], ['ombriere', 'Ombrière'], ['autre', 'Autre'],
]
//: `ComposantFixation.Role` (models.py).
const ROLES = [
  ['rail', 'Rail'], ['pince_milieu', 'Pince de milieu'], ['pince_fin', 'Pince de fin'],
  ['crochet', 'Crochet'], ['embout', 'Embout'], ['lest', 'Lest'], ['visserie', 'Visserie'],
]
//: `catalogue_fixation.BASES` + « quantité d'un autre composant » (`role:<rôle>`).
const BASES = [
  ['', 'aucune (règle non saisie)'], ['modules', 'modules posés'], ['rangees', 'rangées'],
  ['pans', 'pans'], ['jonctions', 'jonctions entre modules voisins'],
  ['extremites', 'extrémités de rangées'], ['longueur_rangees_m', 'longueur des rangées (m)'],
  ...ROLES.map(([role, libelle]) => [`role:${role}`, `quantité du composant « ${libelle} »`]),
]

//: ACAL566 — `catalogue_fixation.COUVERTURES` (= `Lead.TypeToiture`), même ordre.
const COUVERTURES = [
  ['terrasse_beton', 'Terrasse béton'], ['tole_metal', 'Tôle/Métal'], ['tuiles', 'Tuiles'],
  ['bac_acier', 'Bac acier'], ['fibrociment', 'Fibrociment'], ['autre', 'Autre'],
]

const COMPOSANT_NEUF = {
  role: 'rail', libelle: '', unite: '', produit_id: '', source: '',
  base: '', facteur: '', diviseur: '', libelle_facteur: '', libelle_diviseur: '',
}
//: ACAL568 — les valeurs de pose déclarées (mm), `SystemeFixation.controles_pose`.
const CONTROLES_POSE = [
  ['distance_rail_bord_mm', 'Distance rail-bord (mm)'],
  ['porte_a_faux_rail_mm', 'Porte-à-faux du rail (mm)'],
  ['porte_a_faux_max_mm', 'Porte-à-faux admis (mm)'],
]
const CONTROLES_NEUFS = { distance_rail_bord_mm: '', porte_a_faux_rail_mm: '', porte_a_faux_max_mm: '', source: '' }
const SYSTEME_NEUF = {
  code: '', libelle: '', fabricant: '', mode_pose: 'toiture_inclinee', provenance: '', couvertures: [],
  controles_pose: CONTROLES_NEUFS,
}
const CHAMP = 'min-h-11 rounded border border-border bg-background px-2 text-sm'

const texte = (v) => (Array.isArray(v) ? v.join(' ') : String(v))
const libelleDe = (liste, cle) => (liste.find(([c]) => c === cle) || [cle, cle])[1]

/** Un nombre saisi est envoyé tel quel ; vide = paramètre déclaré non saisi. */
function nombreOuNull(saisie) {
  const brut = String(saisie ?? '').trim().replace(',', '.')
  return brut === '' ? null : Number(brut)
}

/** Les contrôles de pose saisis → l'objet du contrat (une valeur vide est omise). */
function controlesVersContrat(saisis) {
  const sortie = {}
  CONTROLES_POSE.forEach(([cle]) => {
    const n = nombreOuNull(saisis?.[cle])
    if (n !== null) sortie[cle] = n
  })
  const source = String(saisis?.source ?? '').trim()
  if (source) sortie.source = source
  return sortie
}

/** Le contrat servi → les champs de saisie (les nombres restent du texte). */
function controlesDepuisContrat(servis) {
  const vers = (v) => (v === null || v === undefined ? '' : String(v))
  return { ...CONTROLES_NEUFS, ...Object.fromEntries(Object.entries(servis || {}).map(([k, v]) => [k, vers(v)])) }
}

/** La ligne d'écran → le composant du contrat (`ordre` = rang, posé par le serveur). */
function versContrat(c) {
  const regle = {}
  if (c.base) {
    regle.base = c.base
    if (c.facteur !== '' || c.libelle_facteur) regle.facteur = nombreOuNull(c.facteur)
    if (c.diviseur !== '' || c.libelle_diviseur) regle.diviseur = nombreOuNull(c.diviseur)
    if (c.libelle_facteur) regle.libelle_facteur = c.libelle_facteur
    if (c.libelle_diviseur) regle.libelle_diviseur = c.libelle_diviseur
  }
  return {
    role: c.role, libelle: c.libelle, unite: c.unite, source: c.source,
    produit_id: nombreOuNull(c.produit_id), regle,
  }
}

/** Le composant servi → la ligne d'écran (les nombres restent du texte saisi). */
function depuisContrat(c) {
  const r = c.regle || {}
  const vers = (v) => (v === null || v === undefined ? '' : String(v))
  return {
    role: c.role, libelle: c.libelle, unite: c.unite, source: c.source,
    produit_id: vers(c.produit_id), base: r.base || '', facteur: vers(r.facteur),
    diviseur: vers(r.diviseur), libelle_facteur: r.libelle_facteur || '',
    libelle_diviseur: r.libelle_diviseur || '',
  }
}

function SousLeChamp({ erreurs, chemin }) {
  if (!erreurs[chemin]) return null
  return <span className="text-xs text-destructive" data-testid={`acal559-erreur-${chemin}`}>{texte(erreurs[chemin])}</span>
}

function Saisie({ id, libelle, erreurs, chemin, valeur, onSaisie, liste, ...attributs }) {
  return (
    <label htmlFor={id} className="flex flex-col gap-1 text-sm">
      {libelle}
      {liste ? (
        <select id={id} value={valeur} onChange={(e) => onSaisie(e.target.value)} className={CHAMP}>
          {liste.map(([cle, lib]) => <option key={cle || 'vide'} value={cle}>{lib}</option>)}
        </select>
      ) : (
        <input id={id} value={valeur} onChange={(e) => onSaisie(e.target.value)} className={CHAMP} {...attributs} />
      )}
      <SousLeChamp erreurs={erreurs} chemin={chemin} />
    </label>
  )
}

function Formulaire({ initial, onFini }) {
  const [systeme, setSysteme] = useState(initial?.systeme || SYSTEME_NEUF)
  const [composants, setComposants] = useState(initial?.composants || [{ ...COMPOSANT_NEUF }])
  const [erreurs, setErreurs] = useState({})
  const [enVol, setEnVol] = useState(false)
  const poser = (cle) => (v) => setSysteme((s) => ({ ...s, [cle]: v }))
  const poserComposant = (rang, cle) => (v) => setComposants((l) => l.map(
    (c, i) => (i === rang ? { ...c, [cle]: v } : c)))

  const enregistrer = (e) => {
    e.preventDefault()
    setErreurs({})
    setEnVol(true)
    const corps = {
      ...systeme, controles_pose: controlesVersContrat(systeme.controles_pose), composants: composants.map(versContrat),
    }
    const appel = initial?.id
      ? calepinageApi.systemesFixation.modifier(initial.id, corps)
      : calepinageApi.systemesFixation.creer(corps)
    appel.then(() => onFini()).catch((err) => {
      const donnees = err?.response?.data
      setErreurs(donnees && typeof donnees === 'object' ? donnees : { detail: 'Enregistrement refusé par le serveur.' })
    }).finally(() => setEnVol(false))
  }

  const rendus = new Set(['code', 'libelle', 'fabricant', 'mode_pose', 'provenance', 'couvertures', 'controles_pose'])
  const poserControle = (cle) => (v) => setSysteme((s) => ({ ...s, controles_pose: { ...s.controles_pose, [cle]: v } }))
  composants.forEach((_c, i) => ['role', 'libelle', 'unite', 'produit_id', 'regle', 'source']
    .forEach((cle) => rendus.add(`composants[${i}].${cle}`)))
  const id = (suffixe) => `acal559-${suffixe}`

  return (
    <form noValidate onSubmit={enregistrer} className="flex flex-col gap-3" data-testid="acal559-formulaire">
      <h2 className="text-base font-semibold">{initial?.id ? 'Modifier le système' : 'Ajouter un système'}</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <Saisie id={id('code')} libelle="Code" chemin="code" erreurs={erreurs} valeur={systeme.code} onSaisie={poser('code')} />
        <Saisie id={id('libelle')} libelle="Libellé" chemin="libelle" erreurs={erreurs} valeur={systeme.libelle} onSaisie={poser('libelle')} />
        <Saisie id={id('fabricant')} libelle="Fabricant" chemin="fabricant" erreurs={erreurs} valeur={systeme.fabricant} onSaisie={poser('fabricant')} />
        <Saisie id={id('mode-pose')} libelle="Mode de pose" chemin="mode_pose" erreurs={erreurs} valeur={systeme.mode_pose} onSaisie={poser('mode_pose')} liste={MODES_POSE} />
      </div>
      <Saisie id={id('provenance')} libelle="Provenance (notice du fabricant, référence du document)" chemin="provenance"
        erreurs={erreurs} valeur={systeme.provenance} onSaisie={poser('provenance')} />
      <fieldset className="flex flex-col gap-1" data-testid="acal566-couvertures">
        <legend className="text-sm">Toitures servies (proposé d’après le toit du lead)</legend>
        <div className="flex flex-wrap gap-x-4">
          {COUVERTURES.map(([cle, libelle]) => (
            <label key={cle} className="flex min-h-11 items-center gap-2 text-sm">
              <input type="checkbox" checked={systeme.couvertures.includes(cle)} data-testid={`acal566-couverture-${cle}`}
                onChange={(e) => poser('couvertures')(e.target.checked
                  ? [...systeme.couvertures, cle] : systeme.couvertures.filter((c) => c !== cle))} />
              {libelle}
            </label>
          ))}
        </div>
        <SousLeChamp erreurs={erreurs} chemin="couvertures" />
      </fieldset>

      <fieldset className="flex flex-col gap-1" data-testid="acal568-controles-pose">
        <legend className="text-sm">Contrôles de pose (expert, facultatif — valeurs de la notice, en mm)</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {CONTROLES_POSE.map(([cle, libelle]) => (
            <Saisie key={cle} id={id(`pose-${cle}`)} libelle={libelle} chemin="controles_pose" erreurs={{}}
              valeur={systeme.controles_pose[cle]} onSaisie={poserControle(cle)} type="number" step="any" inputMode="decimal" />
          ))}
          <Saisie id={id('pose-source')} libelle="Source des valeurs (obligatoire dès qu’un nombre est saisi)" chemin="controles_pose"
            erreurs={erreurs} valeur={systeme.controles_pose.source} onSaisie={poserControle('source')} />
        </div>
      </fieldset>

      <fieldset className="flex flex-col gap-3" data-testid="acal559-composants">
        <legend className="text-sm font-medium">Composants et règle de quantité</legend>
        {composants.map((c, i) => {
          const ch = (cle) => `composants[${i}].${cle}`
          const p = (cle) => poserComposant(i, cle)
          return (
            <div key={i} className="grid gap-2 border-t border-border/60 pt-2 sm:grid-cols-3" data-testid={`acal559-composant-${i}`}>
              <Saisie id={id(`c${i}-role`)} libelle="Rôle" chemin={ch('role')} erreurs={erreurs} valeur={c.role} onSaisie={p('role')} liste={ROLES} />
              <Saisie id={id(`c${i}-libelle`)} libelle="Libellé" chemin={ch('libelle')} erreurs={erreurs} valeur={c.libelle} onSaisie={p('libelle')} />
              <Saisie id={id(`c${i}-unite`)} libelle="Unité (u, m, kg…)" chemin={ch('unite')} erreurs={erreurs} valeur={c.unite} onSaisie={p('unite')} />
              <Saisie id={id(`c${i}-produit`)} libelle="Produit du stock (identifiant, facultatif)" chemin={ch('produit_id')} erreurs={erreurs}
                valeur={c.produit_id} onSaisie={p('produit_id')} type="number" step="any" inputMode="numeric" />
              <Saisie id={id(`c${i}-base`)} libelle="Grandeur de base" chemin={ch('regle')} erreurs={erreurs} valeur={c.base} onSaisie={p('base')} liste={BASES} />
              <Saisie id={id(`c${i}-source`)} libelle="Source (notice, référence)" chemin={ch('source')} erreurs={erreurs} valeur={c.source} onSaisie={p('source')} />
              <Saisie id={id(`c${i}-facteur`)} libelle="Multiplié par" chemin={`${ch('regle')}.facteur`} erreurs={erreurs}
                valeur={c.facteur} onSaisie={p('facteur')} type="number" step="any" inputMode="decimal" />
              <Saisie id={id(`c${i}-libelle-facteur`)} libelle="… qui représente" chemin={`${ch('regle')}.libelle_facteur`} erreurs={erreurs}
                valeur={c.libelle_facteur} onSaisie={p('libelle_facteur')} placeholder="rails par rangée" />
              <span />
              <Saisie id={id(`c${i}-diviseur`)} libelle="Divisé par" chemin={`${ch('regle')}.diviseur`} erreurs={erreurs}
                valeur={c.diviseur} onSaisie={p('diviseur')} type="number" step="any" inputMode="decimal" />
              <Saisie id={id(`c${i}-libelle-diviseur`)} libelle="… qui représente" chemin={`${ch('regle')}.libelle_diviseur`} erreurs={erreurs}
                valeur={c.libelle_diviseur} onSaisie={p('libelle_diviseur')} placeholder="entraxe des crochets (m)" />
              <div className="flex items-end">
                <Button type="button" variant="outline" onClick={() => setComposants((l) => l.filter((_x, j) => j !== i))}>
                  Retirer ce composant
                </Button>
              </div>
            </div>
          )
        })}
        <SousLeChamp erreurs={erreurs} chemin="composants" />
        <Button type="button" variant="outline" onClick={() => setComposants((l) => [...l, { ...COMPOSANT_NEUF }])}>
          Ajouter un composant
        </Button>
      </fieldset>

      {/* Un refus que le formulaire ne rend pas champ par champ reste AFFICHÉ. */}
      {Object.entries(erreurs).filter(([cle]) => !rendus.has(cle)).map(([cle, message]) => (
        <p key={cle} className="text-xs text-destructive" data-testid={`acal559-erreur-${cle}`}>{texte(message)}</p>
      ))}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={enVol} data-testid="acal559-enregistrer">
          {enVol ? 'Enregistrement…' : 'Enregistrer le système'}
        </Button>
        {initial?.id && <Button type="button" variant="outline" onClick={() => onFini(false)}>Annuler</Button>}
      </div>
    </form>
  )
}

function LigneSysteme({ systeme, peutGerer, onModifier, onChange }) {
  const [erreur, setErreur] = useState(null)
  const { confirmDelete } = useConfirmDialog()
  const refus = (err) => {
    const donnees = err?.response?.data
    setErreur(donnees && typeof donnees === 'object'
      ? Object.values(donnees).map(texte).join(' ') : 'Action refusée par le serveur.')
  }
  const basculer = () => {
    setErreur(null)
    calepinageApi.systemesFixation.modifier(systeme.id, { actif: !systeme.actif }).then(onChange).catch(refus)
  }
  const supprimer = async () => {
    if (!(await confirmDelete({
      title: `Supprimer le système « ${systeme.libelle} » ?`,
      description: 'Les calepinages qui l’utilisaient n’auront plus de système choisi.',
    }))) return
    setErreur(null)
    calepinageApi.systemesFixation.supprimer(systeme.id).then(onChange).catch(refus)
  }
  return (
    <li className="flex flex-col gap-1 border-t border-border/60 pt-2" data-testid={`acal559-systeme-${systeme.id}`}>
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="text-sm font-medium">{systeme.libelle}</span>
        <span className="text-xs text-muted-foreground">
          {[systeme.fabricant, libelleDe(MODES_POSE, systeme.mode_pose), systeme.code].filter(Boolean).join(' · ')}
        </span>
        {!systeme.actif && <span className="text-xs text-muted-foreground">désactivé</span>}
      </div>
      <p className="text-xs text-muted-foreground">
        {systeme.composants.length === 0
          ? 'Aucun composant.'
          : systeme.composants.map((c) => `${c.libelle} (${libelleDe(ROLES, c.role)}, ${c.unite})`).join(' ; ')}
      </p>
      <p className="text-xs text-muted-foreground">{`Provenance : ${systeme.provenance}`}</p>
      {peutGerer && (
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" onClick={() => onModifier(systeme)} data-testid={`acal559-modifier-${systeme.id}`}>Modifier</Button>
          <Button type="button" variant="outline" onClick={basculer} data-testid={`acal559-basculer-${systeme.id}`}>
            {systeme.actif ? 'Désactiver' : 'Réactiver'}
          </Button>
          <Button type="button" variant="outline" onClick={supprimer} data-testid={`acal559-supprimer-${systeme.id}`}>Supprimer</Button>
        </div>
      )}
      {erreur && <p className="text-xs text-destructive" data-testid={`acal559-erreur-systeme-${systeme.id}`}>{erreur}</p>}
    </li>
  )
}

export default function ReglagesFixation() {
  const peutGerer = useHasPermission('calepinage_gerer')
  const [systemes, setSystemes] = useState(null)
  const [erreurChargement, setErreurChargement] = useState(null)
  // `edition` : null = ajout ; sinon le système en cours de modification. La
  // clé change à chaque ouverture pour repartir d'un formulaire neuf.
  const [edition, setEdition] = useState({ cle: 0, initial: null })

  const charger = useCallback(() => {
    calepinageApi.systemesFixation.liste()
      .then((r) => { setSystemes(r.data?.systemes || []); setErreurChargement(null) })
      .catch(() => setErreurChargement('Systèmes de fixation indisponibles.'))
  }, [])
  useEffect(() => { charger() }, [charger])

  const ouvrir = (systeme) => setEdition((e) => ({
    cle: e.cle + 1,
    initial: systeme ? {
      id: systeme.id,
      systeme: { code: systeme.code, libelle: systeme.libelle, fabricant: systeme.fabricant,
        mode_pose: systeme.mode_pose, provenance: systeme.provenance,
        couvertures: Array.isArray(systeme.couvertures) ? systeme.couvertures : [],
        controles_pose: controlesDepuisContrat(systeme.controles_pose) },
      composants: systeme.composants.map(depuisContrat),
    } : null,
  }))
  const fini = (recharger = true) => { ouvrir(null); if (recharger) charger() }

  return (
    <div className="page flex flex-col gap-4" data-testid="acal559-ecran">
      <div className="flex flex-col gap-1">
        <a href="/calepinage/reglages" className="text-xs underline">← Réglages simulation</a>
        <h1 className="text-lg font-semibold text-foreground">Systèmes de fixation</h1>
        <p className="text-sm text-muted-foreground">
          Chaque système est saisi par la société depuis la notice de son fabricant. L’onglet
          Fixation de chaque calepinage en calcule les quantités.
        </p>
      </div>
      <Card className="p-4">
        {erreurChargement && <p className="text-sm text-destructive">{erreurChargement}</p>}
        {systemes && systemes.length === 0 && (
          <p className="text-sm text-muted-foreground" data-testid="acal559-vide">
            Aucun système de fixation : la nomenclature n’est pas calculée tant qu’aucun n’est saisi.
          </p>
        )}
        {systemes && systemes.length > 0 && (
          <ul className="flex flex-col gap-2" data-testid="acal559-liste">
            {systemes.map((s) => (
              <LigneSysteme key={s.id} systeme={s} peutGerer={peutGerer} onModifier={ouvrir} onChange={charger} />
            ))}
          </ul>
        )}
      </Card>
      {peutGerer && (
        <Card className="p-4">
          <Formulaire key={edition.cle} initial={edition.initial} onFini={fini} />
        </Card>
      )}
    </div>
  )
}
