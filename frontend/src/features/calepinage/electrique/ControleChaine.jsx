import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import { Button, Card, Label, Spinner } from '../../../ui'
import RetourAtelier from '../atelier/RetourAtelier'
import { refusParChamp } from './entreeElectrique'
import { volts } from './tensionsChaines'

/* ============================================================================
   ACAL628 — « CONTRÔLE RAPIDE D'UNE CHAÎNE » : un module, un onduleur, N modules et les deux
   températures SAISIES ; le serveur (`POST calepinages/controle-chaine/`, ACAL627) rend le verdict
   sans rien dessiner ni écrire. Les produits viennent des candidats de l'entrée électrique (même
   liste que « Matériel »). Aucun chiffre calculé ici : valeurs, bornes (phrase servie) et fenêtre
   « de x à y modules » sont celles du serveur. Le dernier essai se garde dans `sessionStorage`.
   ========================================================================== */

const CLE_SESSION = 'cal-controle-chaine-dernier'
const CHAMPS = [
  { cle: 'nombre_modules', libelle: 'Nombre de modules dans la chaîne' },
  { cle: 'temperature_min_c', libelle: 'Température la plus froide (°C)' },
  { cle: 'temperature_max_c', libelle: 'Température la plus chaude (°C)' },
]
const ETATS = {
  ok: { icone: '✔', mot: 'Conforme', classe: 'text-success-text' },
  attention: { icone: '⚠', mot: 'À surveiller', classe: 'text-warning' },
  refus: { icone: '✖', mot: 'Ne convient pas', classe: 'text-destructive' },
}

const lireSession = () => {
  try { return JSON.parse(window.sessionStorage.getItem(CLE_SESSION) || 'null') ?? {} } catch { return {} }
}
const ecrireSession = (valeurs) => {
  try { window.sessionStorage.setItem(CLE_SESSION, JSON.stringify(valeurs)) } catch { /* mémoire du navigateur absente : sans effet */ }
}

export default function ControleChaine({ calepinageId } = {}) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute
  const [candidats, setCandidats] = useState(null)
  const [saisie, setSaisie] = useState(() => ({ module_produit: '', onduleur_produit: '', nombre_modules: '', temperature_min_c: '', temperature_max_c: '', ...lireSession() }))
  const [erreurs, setErreurs] = useState({})
  const [verdict, setVerdict] = useState(null)
  const [enCours, setEnCours] = useState(false)

  useEffect(() => {
    calepinageApi.calepinages.entreeElectrique(id)
      .then((res) => setCandidats(res?.data?.candidats ?? {}))
      .catch(() => setCandidats({}))
  }, [id])

  const changer = (cle, valeur) => setSaisie((s) => ({ ...s, [cle]: valeur }))

  const controler = (evenement) => {
    evenement.preventDefault()
    const manquants = {}
    for (const [cle, texte] of [['module_produit', 'Choisissez un module.'], ['onduleur_produit', 'Choisissez un onduleur.']]) {
      if (!saisie[cle]) manquants[cle] = texte
    }
    for (const { cle, libelle } of CHAMPS) {
      if (String(saisie[cle]).trim() === '') manquants[cle] = `« ${libelle} » est à saisir.`
    }
    setErreurs(manquants)
    if (Object.keys(manquants).length > 0) return
    ecrireSession(saisie)
    setEnCours(true)
    const nombre = (cle) => Number(String(saisie[cle]).replace(',', '.'))
    calepinageApi.calepinages.controleChaine({
      module_produit: Number(saisie.module_produit),
      onduleur_produit: Number(saisie.onduleur_produit),
      nombre_modules: nombre('nombre_modules'),
      temperature_min_c: nombre('temperature_min_c'),
      temperature_max_c: nombre('temperature_max_c'),
    })
      .then((res) => { setVerdict(res?.data ?? null) })
      .catch((err) => {
        setVerdict(null)
        const parChamp = refusParChamp(err?.response?.data)
        setErreurs(Object.keys(parChamp).length ? parChamp : { general: 'Contrôle indisponible : le serveur n’a pas répondu.' })
      })
      .finally(() => setEnCours(false))
  }

  const etat = (c) => (c.conforme ? ETATS.ok : (c.bloquant ? ETATS.refus : ETATS.attention))
  const refus = (verdict?.controles ?? []).find((c) => !c.conforme && c.bloquant)
  const ligneErreur = (cle) => (erreurs[cle]
    ? <p role="alert" className="text-xs text-destructive" data-testid={`acal628-erreur-${cle}`}>{erreurs[cle]}</p>
    : null)

  return (
    <>
      <RetourAtelier calepinageId={id} cle="controle-chaine" />
      <Card className="flex flex-col gap-3 p-4" data-testid="acal628-panneau">
        <h2 className="text-base font-semibold">Contrôle rapide d’une chaîne</h2>
        <p className="text-sm text-muted-foreground">Combien de modules sur cet onduleur ? Rien n’est dessiné ni enregistré.</p>
        {!candidats ? <Spinner /> : (
          <form className="flex flex-col gap-3" onSubmit={controler} noValidate data-testid="acal628-formulaire">
            {[['module_produit', 'Module', 'modules'], ['onduleur_produit', 'Onduleur', 'onduleurs']].map(([cle, libelle, liste]) => (
              <div key={cle} className="flex flex-col gap-1">
                <Label htmlFor={`acal628-${cle}`}>{libelle}</Label>
                <select id={`acal628-${cle}`} value={saisie[cle]} onChange={(e) => changer(cle, e.target.value)}
                  aria-invalid={erreurs[cle] ? 'true' : undefined}
                  className="min-h-11 w-full rounded border border-border bg-background px-2 text-sm text-foreground">
                  <option value="">— choisir —</option>
                  {(candidats[liste] ?? []).filter((c) => c.fiche_complete !== false).map((c) => (
                    <option key={c.id} value={c.id}>{c.libelle}{c.marque ? ` (${c.marque})` : ''}</option>
                  ))}
                </select>
                {ligneErreur(cle)}
              </div>
            ))}
            {CHAMPS.map(({ cle, libelle }) => (
              <div key={cle} className="flex flex-col gap-1">
                <Label htmlFor={`acal628-${cle}`}>{libelle}</Label>
                <input id={`acal628-${cle}`} type="text" inputMode="decimal" value={saisie[cle]} onChange={(e) => changer(cle, e.target.value)}
                  aria-invalid={erreurs[cle] ? 'true' : undefined}
                  className="min-h-11 w-40 rounded border border-border bg-background px-2 text-sm text-foreground" />
                {ligneErreur(cle)}
              </div>
            ))}
            {ligneErreur('general')}
            <div><Button type="submit" disabled={enCours} className="min-h-11" data-testid="acal628-controler">Contrôler la chaîne</Button></div>
          </form>
        )}
        {verdict && (
          <section className="flex flex-col gap-2" data-testid="acal628-verdict" role="status">
            {refus
              ? <p className={`text-sm font-semibold ${ETATS.refus.classe}`} data-testid="acal628-titre">{ETATS.refus.icone} Trop haut : {volts(refus.valeur)} — {refus.borne}</p>
              : <p className="text-sm font-semibold" data-testid="acal628-titre">{verdict.verdict === 'indetermine' ? 'Contrôle impossible : fiche à compléter.' : 'Aucune limite bloquante dépassée.'}</p>}
            <ul className="flex flex-col gap-1">
              {(verdict.controles ?? []).map((c) => (
                <li key={c.code} className={`text-sm ${etat(c).classe}`} data-testid={`acal628-controle-${c.code}`}>
                  {etat(c).icone} {etat(c).mot} — {c.libelle} : {volts(c.valeur)} ({c.borne})
                </li>
              ))}
            </ul>
            {verdict.longueur_min != null && verdict.longueur_max != null && (
              <p className="text-sm text-foreground" data-testid="acal628-fenetre">de {verdict.longueur_min} à {verdict.longueur_max} modules par chaîne</p>
            )}
            {(verdict.manquantes ?? []).map((m) => <p key={m} className="text-sm text-muted-foreground">{m}</p>)}
          </section>
        )}
      </Card>
    </>
  )
}
