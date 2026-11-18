import { useContext, useEffect, useState } from 'react'
import { ReactReduxContext } from 'react-redux'
import { Check, ChevronDown } from 'lucide-react'
import api from '../../../api/axios'
import { creerJeton, listerJetons, revoquerJeton, testerNotification } from '../../../api/tachesApi'
import { frenchError } from '../../../lib/frenchError'
import { pushSupported, subscribeToPush } from '../../pwa/pushSubscribe'
import { jourCourt } from '../lib/textes'
import { Agendas } from '../reglages/Rubriques'
import { scriptPour } from './scriptTuile'

/* ============================================================================
   TCH109 — « Mon iPhone » (Réglages → /taches/reglages/iphone) : cinq étapes repliables, chacune
   change d'état sur SA donnée : permission des notifications, dernier usage du jeton `flux`,
   `capture`, `tuile`, route d'accueil mémorisée. Jetons : Créer, Copier mon jeton, Régénérer,
   Révoquer, « Dernier usage ». Le jeton en clair n'est rendu qu'UNE fois (`POST jetons/`) : il vit
   dans l'état du composant, jamais dans `localStorage` ni dans une adresse de l'application, et
   disparaît dès qu'il est copié. Un jeton perdu se régénère.
   Textes : reference/textes.md §7 ; spec-6b-iphone.md ; maquettes mon-iphone.html.
   ========================================================================== */

const ROUTE_ACCUEIL = '/taches/aujourdhui'
const COPIE_FAITE = "Copié. Il ne sera plus affiché : colle-le maintenant."
const PERDU = 'Perdu ? Régénère-le.'
const PHRASES_PUSH = {
  granted: 'Actives sur cet appareil.',
  default: 'Pas encore autorisées.',
  denied: "Refusées : Réglages de l'iPhone → Notifications → Taqinor → Autoriser.",
  unsupported: "Ouvre l'ERP depuis son icône pour les activer.",
  unconfigured: 'Pas configurées sur ce serveur : demande à l\'administrateur.',
}

const messageDe = (err, champ) => {
  const brut = err?.response?.data?.[champ]
  return Array.isArray(brut) && brut.length > 0 ? String(brut[0]) : frenchError(err, 'Réessaie dans un instant.')
}

const lireTexte = (valeur, motif) => motif.exec(String(valeur ?? ''))

/** « Dernier usage : jeu. 19 09:41 » : le jour et l'heure sont lus dans le texte ISO du serveur. */
function dernierUsage(jeton) {
  const trouve = lireTexte(jeton.dernier_usage_le, /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/)
  return trouve ? `Dernier usage : ${jourCourt(trouve[1])} ${trouve[2]}` : 'Jamais utilisé'
}

async function copier(texte) {
  try {
    await navigator.clipboard.writeText(texte)
    return true
  } catch (err) {
    console.warn('MonIphone.copier : copie refusée', err)
    return false
  }
}

function permissionNotifications() {
  if (!pushSupported()) return 'unsupported'
  return window.Notification.permission
}

/* ── Un jeton : créer → copier (une seule fois) → régénérer / révoquer ───────────────────────── */

function BlocJeton({ usage, jeton, revele, copie, libelleCreer, libelleCopie, valeurCopiee, onCreer, onCopie, onRevoquer, erreur }) {
  const [confirme, setConfirme] = useState(false)
  const [echecCopie, setEchecCopie] = useState(false)

  const copierLeJeton = async () => {
    const ok = await copier(valeurCopiee(revele))
    setEchecCopie(!ok)
    if (ok) onCopie(usage)
  }
  const regenerer = () => { setConfirme(false); onCreer(usage) }

  return (
    <div className="ep-jeton">
      {revele ? <code className="ep-jeton-valeur">{revele.jeton}</code> : null}
      <div className="ep-jeton-actions">
        {!jeton ? <button type="button" className="bouton second" onClick={() => onCreer(usage)}>{libelleCreer}</button> : null}
        {revele ? <button type="button" className="bouton plein" onClick={copierLeJeton}>{libelleCopie}</button> : null}
        {jeton ? <button type="button" className="bouton second" onClick={() => setConfirme(true)}>Régénérer</button> : null}
        {jeton ? <button type="button" className="bouton second" onClick={() => onRevoquer(jeton)}>Révoquer</button> : null}
      </div>
      {jeton ? <p className="rassure">{`${dernierUsage(jeton)} · ${jeton.prefixe}…`}</p> : null}
      {jeton && !revele ? <p className="rassure">{`${PERDU} Pour couper l'accès : « Révoquer » ; il cesse de marcher tout de suite.`}</p> : null}
      {copie ? <p className="rassure" role="status">{COPIE_FAITE}</p> : null}
      {echecCopie ? <p className="es-erreur" role="alert">Copie impossible : sélectionne le jeton et copie-le à la main.</p> : null}
      {confirme ? (
        <div role="alertdialog" aria-label="Régénérer ?">
          <p className="ep-phrase">Régénérer ? L'ancien cesse de marcher tout de suite.</p>
          <div className="ep-jeton-actions">
            <button type="button" className="bouton second" onClick={() => setConfirme(false)}>Fermer</button>
            <button type="button" className="bouton plein" onClick={regenerer}>Régénérer</button>
          </div>
        </div>
      ) : null}
      {erreur ? <p className="es-erreur" role="alert">{erreur}</p> : null}
    </div>
  )
}

/* ── Une étape repliable ─────────────────────────────────────────────────────────────────────── */

function Etape({ numero, titre, fait, ouverte, onBasculer, children }) {
  const classe = fait ? 'fait' : (ouverte ? 'encours' : '')
  return (
    <li>
      <button type="button" className={`ep-etape-i ${classe}`.trim()} aria-expanded={ouverte} onClick={onBasculer}>
        <span className="num chiffres">{fait ? <Check className="i" aria-hidden="true" /> : numero}</span>
        <span><b>{titre}</b><span className="etat">{fait ? 'Fait' : 'À faire'}</span></span>
        <span className="chevron"><ChevronDown className="i i-16" aria-hidden="true" style={ouverte ? { transform: 'rotate(180deg)' } : undefined} /></span>
      </button>
      {ouverte ? <div className="ep-etape-ouverte">{children}</div> : null}
    </li>
  )
}

/* ── Étape 1 : notifications ─────────────────────────────────────────────────────────────────── */

function EtapeNotifications({ etat, onAutoriser, onTest, test, reglages, onReglage, erreur }) {
  const [repondu, setRepondu] = useState(null)
  const choisir = (valeur) => { setRepondu(valeur); onReglage('titres_notifications', valeur) }
  const choix = repondu ?? (reglages?.titres_notifications_demande ? Boolean(reglages.titres_notifications) : null)
  return (
    <>
      <ol>
        <li>Ouvre l'ERP depuis son icône sur l'écran d'accueil, pas depuis Safari. Pas d'icône ? Dans Safari, touche le bouton Partager, puis « Sur l'écran d'accueil ». Il faut iOS 16.4 ou plus récent.</li>
        <li>Touche « Autoriser les notifications », puis « Autoriser » quand l'iPhone le demande.</li>
        <li>{"« Montrer le titre sur l'écran verrouillé ? » · sans réponse, seulement des nombres."}</li>
        <li>Touche « Envoyer un test » : une notification « Test des notifications » doit arriver.</li>
      </ol>
      <p className="ep-phrase" role="status">{PHRASES_PUSH[etat]}</p>
      <div className="ep-jeton-actions">
        <button type="button" className="bouton plein" onClick={onAutoriser}>Autoriser les notifications</button>
        <button type="button" className="bouton second" onClick={() => choisir(true)} aria-pressed={choix === true}>Oui</button>
        <button type="button" className="bouton second" onClick={() => choisir(false)} aria-pressed={choix === false}>Non</button>
        <button type="button" className="bouton second" onClick={onTest}>Envoyer un test</button>
      </div>
      {erreur.titres_notifications ? <p className="es-erreur" role="alert">{erreur.titres_notifications}</p> : null}
      {test ? <p className={test.ok ? 'rassure' : 'es-erreur'} role={test.ok ? 'status' : 'alert'}>{test.texte}</p> : null}
    </>
  )
}

/* ── Étape 3 : Siri ──────────────────────────────────────────────────────────────────────────── */

const RECETTE_SIRI = [
  'Ouvre l\'app Raccourcis, touche « + », nomme le raccourci « Nouvelle tâche ».',
  'Ajoute l\'action « Dicter du texte ».',
  'Ajoute l\'action « Obtenir le contenu de l\'URL » ; colle l\'adresse (« Copier l\'adresse » ici) ; « Afficher plus » : Méthode « POST » ; En-têtes : ajoute « Authorization » et colle « Bearer » suivi de ton jeton (« Copier mon jeton » ici) ; Corps de la requête « JSON » : un champ texte « titre » = « Texte dicté ».',
  'Ajoute l\'action « Afficher le résultat ». Touche OK.',
  'Essaie : « Dis Siri, nouvelle tâche », puis « appeler le fournisseur demain 10 h ».',
]

function RecetteSiri({ adresse }) {
  const [copiee, setCopiee] = useState(false)
  const copierAdresse = async () => { setCopiee(await copier(adresse)) }
  return (
    <>
      <ol>{RECETTE_SIRI.map((ligne) => <li key={ligne}>{ligne}</li>)}</ol>
      <button type="button" className="bouton second" onClick={copierAdresse}>Copier l'adresse</button>
      {copiee ? <p className="rassure" role="status">Adresse copiée.</p> : null}
      <p className="rassure">Les noms des actions peuvent différer légèrement selon la version d'iOS.</p>
      <p className="rassure">Sans réseau, la dictée est perdue.</p>
      <p className="rassure">Pour ranger dans un projet, commence par « projet » et son nom : « projet Maison acheter du lait ».</p>
    </>
  )
}

function EtapeSiri({ urlRaccourci, bloc }) {
  const [main, setMain] = useState(!urlRaccourci)
  const adresse = `${window.location.origin}/api/django/taches/capture/?reponse=texte`
  return (
    <>
      {urlRaccourci ? (
        <>
          <p className="ep-phrase">Touche « Installer le raccourci » : l'app Raccourcis s'ouvre. Touche « Ajouter le raccourci » ; quand il demande ton jeton, reviens ici, touche « Copier mon jeton » et colle-le.</p>
          <a className="bouton plein ep-large" href={urlRaccourci} target="_blank" rel="noopener noreferrer">Installer le raccourci</a>
          <p className="rassure">Le raccourci ne contient jamais ton jeton : il te le demande à l'installation.</p>
          <button type="button" className="ep-alamain" aria-expanded={main} onClick={() => setMain(!main)}>
            <span>Le faire à la main</span><ChevronDown className="i i-16" aria-hidden="true" />
          </button>
        </>
      ) : null}
      {main ? <RecetteSiri adresse={adresse} /> : null}
      {bloc}
    </>
  )
}

/* ── Étape 2 : calendrier ────────────────────────────────────────────────────────────────────── */

function EtapeCalendrier({ bloc, revele }) {
  return (
    <>
      <p className="ep-phrase">{"D'abord, dans l'autre sens (le plus utile) : « Mes agendas » — ajoute l'adresse de ton agenda Microsoft 365, Google ou iCloud (3 au plus). Ensuite :"}</p>
      <Agendas />
      <ol>
        <li>Touche « Créer le lien du calendrier », puis « S'abonner » : l'iPhone propose de s'abonner ; accepte.</li>
        <li>Si rien ne s'ouvre : « Copier le lien », puis Réglages de l'iPhone → Calendrier (ou Apps → Calendrier) → Comptes → Ajouter un compte → Autre → « Ajouter un calendrier avec abonnement », colle, Suivant, Enregistrer. Les noms exacts peuvent varier selon la version d'iOS.</li>
        <li>Sur l'écran d'accueil : appui long → « + » → Calendrier → Ajouter.</li>
      </ol>
      {bloc}
      {revele ? <a className="bouton plein ep-large" href={revele.webcal}>{"S'abonner"}</a> : null}
      <p className="rassure">L'iPhone met le calendrier à jour quand il le décide : de quelques minutes à quelques heures. Une tâche cochée disparaît à la mise à jour suivante.</p>
      <p className="rassure">Ce lien vaut une clé : ne le partage pas.</p>
    </>
  )
}

/* ── Étape 4 : tuile ─────────────────────────────────────────────────────────────────────────── */

function CopierLeScript() {
  const [etat, setEtat] = useState('')
  const copierScript = async () => {
    setEtat((await copier(scriptPour(window.location.origin))) ? 'copie' : 'echec')
  }
  return (
    <>
      <button type="button" className="bouton second" onClick={copierScript}>Copier le script</button>
      {etat === 'copie' ? <p className="rassure" role="status">Script copié. Il ne contient pas ton jeton.</p> : null}
      {etat === 'echec' ? <p className="es-erreur" role="alert">Copie impossible : réessaie.</p> : null}
    </>
  )
}

function EtapeTuile({ bloc }) {
  return (
    <>
      <ol>
        <li>App Store → Scriptable (gratuite).</li>
        <li>Ici : « Créer le jeton de la tuile », puis « Copier le script ».</li>
        <li>Dans Scriptable : « + », colle, nomme le script « Tâches ».</li>
        <li>Touche ▶ ; colle ton jeton quand il est demandé (« Copier mon jeton » ici).</li>
        <li>Écran d'accueil → appui long → « + » → Scriptable → grande taille → Ajouter ; touche la tuile en mode modification → Script : « Tâches ».</li>
      </ol>
      {bloc}
      <CopierLeScript />
      <p className="rassure">{"Toucher la tuile ouvre Aujourd'hui (parfois dans Safari, qui peut te demander de te connecter)."}</p>
      <p className="rassure">La tuile se met à jour quand l'iPhone le décide ; l'heure de mise à jour est écrite en bas.</p>
    </>
  )
}

/* ── Étape 5 : accueil ───────────────────────────────────────────────────────────────────────── */

function EtapeAccueil({ onAccueil, erreur }) {
  return (
    <>
      <p className="ep-phrase">{"L'icône de l'ERP ouvrira Aujourd'hui."}</p>
      <button type="button" className="bouton plein ep-large" onClick={onAccueil}>En faire mon accueil</button>
      {erreur ? <p className="es-erreur" role="alert">{erreur}</p> : null}
    </>
  )
}

/* ── Ce qui est visible ──────────────────────────────────────────────────────────────────────── */

const VISIBLES = [
  ['titres_calendrier', 'Titres dans le calendrier'],
  ['titres_tuile', 'Titres sur la tuile'],
  ['titres_notifications', "Titres sur l'écran verrouillé"],
]

function CeQuiEstVisible({ reglages, onReglage, erreur }) {
  return (
    <section className="section">
      <h2 className="section-titre"><span>Ce qui est visible</span></h2>
      <div className="ep-interrupteurs">
        {VISIBLES.map(([champ, libelle]) => (
          <div key={champ}>
            <div className="ep-inter">
              <span>{libelle}</span>
              <button type="button" className="interrupteur" role="switch" aria-checked={Boolean(reglages?.[champ])}
                aria-label={libelle} onClick={() => onReglage(champ, !reglages?.[champ])} />
            </div>
            {erreur[champ] && champ !== 'titres_notifications' ? <p className="es-erreur" role="alert">{erreur[champ]}</p> : null}
          </div>
        ))}
      </div>
      <p className="ep-intro">{"Une tâche confidentielle n'y apparaît jamais par son titre."}</p>
    </section>
  )
}

/* ── L'écran ─────────────────────────────────────────────────────────────────────────────────── */

const actif = (jetons, usage) => jetons.find((j) => j.usage === usage && !j.revoque_le) ?? null
const utilise = (jeton) => Boolean(jeton?.dernier_usage_le)

function useJetons() {
  const [jetons, setJetons] = useState([])
  const [reveles, setReveles] = useState({})
  const [copies, setCopies] = useState({})
  const [erreurs, setErreurs] = useState({})
  const [echec, setEchec] = useState(false)
  const [pret, setPret] = useState(false)

  useEffect(() => {
    let vivant = true
    listerJetons()
      // liste fermée, plafonnée par le serveur (une fiche par usage) : jamais de page suivante
      .then((reponse) => { if (vivant) { const { results } = reponse.data; setJetons(results); setPret(true) } })
      .catch(() => { if (vivant) { setEchec(true); setPret(true) } })
    return () => { vivant = false }
  }, [])

  const poser = (usage, message) => setErreurs((anciennes) => ({ ...anciennes, [usage]: message }))
  const creer = async (usage) => {
    poser(usage, '')
    try {
      const { data } = await creerJeton({ usage, libelle: '' })
      const { jeton, url, webcal, ...fiche } = data
      setReveles((r) => ({ ...r, [usage]: { jeton, url, webcal } }))
      setCopies((c) => ({ ...c, [usage]: false }))
      setJetons((liste) => [...liste.filter((j) => j.usage !== usage), fiche])
    } catch (err) { poser(usage, messageDe(err, 'usage')) }
  }
  const revoquer = async (fiche) => {
    poser(fiche.usage, '')
    try {
      await revoquerJeton(fiche.id)
      setJetons((liste) => liste.filter((j) => j.id !== fiche.id))
      setReveles((r) => ({ ...r, [fiche.usage]: null }))
    } catch (err) { poser(fiche.usage, messageDe(err, 'detail')) }
  }
  const copie = (usage) => {
    setReveles((r) => ({ ...r, [usage]: null }))
    setCopies((c) => ({ ...c, [usage]: true }))
  }
  return { jetons, reveles, copies, erreurs, echec, pret, creer, revoquer, copie }
}

// `etapeDemandee` : numéro (0-4) d'une étape à ouvrir d'emblée, en plus de celle du départ (adresse `?etape=calendrier`).
export default function MonIphone({ reglages, onReglage, erreur = {}, etapeDemandee = null }) {
  const contexte = useContext(ReactReduxContext)
  const accueilServeur = contexte?.store.getState().auth?.user?.mobile_home_route === ROUTE_ACCUEIL
  const jetons = useJetons()
  const [permission, setPermission] = useState(permissionNotifications)
  const [test, setTest] = useState(null)
  const [accueilFait, setAccueilFait] = useState(false)
  const [erreurAccueil, setErreurAccueil] = useState('')
  const [choix, setChoix] = useState({})
  const [depart, setDepart] = useState(null)

  const autoriser = async () => {
    const resultat = await subscribeToPush()
    if (resultat.ok) setPermission('granted')
    else if (resultat.reason === 'denied') setPermission('denied')
    else setPermission(resultat.reason === 'unconfigured' ? 'unconfigured' : permissionNotifications())
  }
  const envoyerTest = async () => {
    setTest(null)
    try {
      await testerNotification()
      setTest({ ok: true, texte: 'Une notification « Test des notifications » doit arriver.' })
    } catch (err) { setTest({ ok: false, texte: messageDe(err, 'detail') }) }
  }
  const faireAccueil = async () => {
    setErreurAccueil('')
    try {
      await api.post('/auth/mobile-home-route/', { route: ROUTE_ACCUEIL })
      setAccueilFait(true)
    } catch (err) { setErreurAccueil(frenchError(err, "Impossible d'en faire ton accueil. Réessaie.")) }
  }

  const flux = actif(jetons.jetons, 'flux')
  const faits = [permission === 'granted', utilise(flux), utilise(actif(jetons.jetons, 'capture')),
    utilise(actif(jetons.jetons, 'tuile')), accueilFait || accueilServeur]
  const premier = faits.indexOf(false)
  // Les étapes déjà faites À L'OUVERTURE sont repliées ; une étape qu'on vient de faire reste ouverte (Envoyer un test).
  if (jetons.pret && depart === null) setDepart(premier)
  const nombre = faits.filter(Boolean).length
  const ouverteParDefaut = (i) => i === (depart ?? 0) || i === etapeDemandee
  const bloc = (usage, libelleCreer, libelleCopie, valeurCopiee) => (
    <BlocJeton usage={usage} jeton={actif(jetons.jetons, usage)} revele={jetons.reveles[usage]} copie={jetons.copies[usage]}
      libelleCreer={libelleCreer} libelleCopie={libelleCopie} valeurCopiee={valeurCopiee}
      onCreer={jetons.creer} onCopie={jetons.copie} onRevoquer={jetons.revoquer} erreur={jetons.erreurs[usage]} />
  )
  const contenus = [
    <EtapeNotifications key="1" etat={permission} onAutoriser={autoriser} onTest={envoyerTest} test={test}
      reglages={reglages} onReglage={onReglage} erreur={erreur} />,
    <EtapeCalendrier key="2" revele={jetons.reveles.flux}
      bloc={bloc('flux', 'Créer le lien du calendrier', 'Copier le lien', (r) => r.url)} />,
    <EtapeSiri key="3" urlRaccourci={reglages?.raccourci_siri_url ?? ''}
      bloc={bloc('capture', 'Créer le jeton', 'Copier mon jeton', (r) => r.jeton)} />,
    <EtapeTuile key="4" bloc={bloc('tuile', 'Créer le jeton de la tuile', 'Copier mon jeton', (r) => r.jeton)} />,
    <EtapeAccueil key="5" onAccueil={faireAccueil} erreur={erreurAccueil} />,
  ]
  const TITRES = ['Recevoir les notifications', 'Voir tes tâches dans le Calendrier', 'Dicter à Siri',
    'Installer la grande tuile', "Ouvrir Aujourd'hui depuis l'icône"]

  return (
    <div>
      <p className="ep-intro">Cinq étapes, à faire une fois. Chacune se replie quand elle est faite.</p>
      <div className="ep-progres-etapes chiffres">
        <span>{`${nombre} sur 5`}</span>
        <div className="ep-barre-avance" role="img" aria-label={`${nombre} étapes sur 5 faites`}><i style={{ '--avance': nombre / 5 }} /></div>
      </div>
      {jetons.echec ? <p className="es-erreur es-aide" role="alert">Pas à jour</p> : null}
      <ol className="ep-etapes">
        {TITRES.map((titre, i) => (
          <Etape key={titre} numero={i + 1} titre={titre} fait={faits[i]} ouverte={choix[i] ?? ouverteParDefaut(i)}
            onBasculer={() => setChoix((c) => ({ ...c, [i]: !(c[i] ?? ouverteParDefaut(i)) }))}>
            {contenus[i]}
          </Etape>
        ))}
      </ol>
      <CeQuiEstVisible reglages={reglages} onReglage={onReglage} erreur={erreur} />
    </div>
  )
}
