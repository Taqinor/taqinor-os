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

/** Vrai quand l'ERP tourne depuis son icône de l'écran d'accueil (mode autonome, Safari ou autre navigateur). */
function installee() {
  const autonome = typeof window.matchMedia === 'function' && window.matchMedia('(display-mode: standalone)')?.matches
  return Boolean(autonome || window.navigator.standalone === true)
}

function permissionNotifications() {
  if (!pushSupported()) return 'unsupported'
  return window.Notification.permission
}

// Passe visuelle — les marches d'une étape sont numérotées (textes.md §7) : `list-decimal` rend les numéros que la
// remise à zéro des listes de l'ERP (`ol { list-style: none }`) effaçait.

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
      {jeton && !revele ? <p className="rassure">{`${PERDU} Pour couper l'accès : «\u00A0Révoquer\u00A0» ; il cesse de marcher tout de suite.`}</p> : null}
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

/* ── Avant les étapes : mettre l'ERP sur l'écran d'accueil (R2-126) ──────────────────────────── */

/** Les notifications et l'icône d'accueil exigent que l'ERP soit sur l'écran d'accueil : c'est la première chose
 *  de l'écran, nommée, avec « Fait » quand on l'ouvre déjà depuis son icône (R2-126, S1 n°14). */
function MettreSurAccueil({ fait }) {
  return (
    <section className="section ep-installer" aria-label="Mettre Tâches sur l'écran d'accueil">
      <h2 className="section-titre">
        <span>Mettre Tâches sur l'écran d'accueil</span>
        <span className="compte">{fait ? 'Fait' : 'À faire'}</span>
      </h2>
      <div className="ep-etape-ouverte">
      {fait ? <p className="rassure">Tu l'ouvres depuis son icône.</p> : (
        <>
          <ol className="list-decimal">
            <li>Dans Safari, touche le bouton Partager.</li>
            <li>{"Touche «\u00A0Sur l'écran d'accueil\u00A0», puis «\u00A0Ajouter\u00A0»."}</li>
            <li>Ouvre ensuite l'ERP depuis son icône, pas depuis Safari.</li>
          </ol>
          <p className="rassure">Il faut iOS 16.4 ou plus récent pour les notifications.</p>
        </>
      )}
      </div>
    </section>
  )
}

/* ── Étape 1 : notifications ─────────────────────────────────────────────────────────────────── */

function EtapeNotifications({ etat, onAutoriser, onTest, test, reglages, onReglage, erreur }) {
  const [repondu, setRepondu] = useState(null)
  const choisir = (valeur) => { setRepondu(valeur); onReglage('titres_notifications', valeur) }
  const choix = repondu ?? (reglages?.titres_notifications_demande ? Boolean(reglages.titres_notifications) : null)
  return (
    <>
      <ol className="list-decimal">
        <li>{"Ouvre l'ERP depuis son icône sur l'écran d'accueil, pas depuis Safari (pas d'icône : «\u00A0Mettre Tâches sur l'écran d'accueil\u00A0», plus haut)."}</li>
        <li>Touche «&nbsp;Autoriser les notifications&nbsp;», puis «&nbsp;Autoriser&nbsp;» quand l'iPhone le demande.</li>
        <li>{"«\u00A0Montrer le titre sur l'écran verrouillé ?\u00A0» · sans réponse, seulement des nombres."}</li>
        <li>Touche «&nbsp;Envoyer un test&nbsp;» : une notification «&nbsp;Test des notifications&nbsp;» doit arriver.</li>
      </ol>
      <p className="ep-phrase" role="status">{PHRASES_PUSH[etat]}</p>
      <div className="ep-jeton-actions">
        <button type="button" className="bouton plein" onClick={onAutoriser}>Autoriser les notifications</button>
      </div>
      {/* R2-130 : « Oui / Non » répond à une question, écrite juste au-dessus (plus à côté d'« Autoriser ») */}
      <p className="ep-phrase" id="question-titres">Montrer le titre sur l'écran verrouillé ?</p>
      <div className="ep-jeton-actions" role="group" aria-labelledby="question-titres">
        <button type="button" className="bouton second" onClick={() => choisir(true)} aria-pressed={choix === true}>Oui</button>
        <button type="button" className="bouton second" onClick={() => choisir(false)} aria-pressed={choix === false}>Non</button>
      </div>
      <div className="ep-jeton-actions">
        <button type="button" className="bouton second" onClick={onTest}>Envoyer un test</button>
      </div>
      {erreur.titres_notifications ? <p className="es-erreur" role="alert">{erreur.titres_notifications}</p> : null}
      {test ? <p className={test.ok ? 'rassure' : 'es-erreur'} role={test.ok ? 'status' : 'alert'}>{test.texte}</p> : null}
    </>
  )
}

/* ── Étape 3 : Siri ──────────────────────────────────────────────────────────────────────────── */

const RECETTE_SIRI = [
  'Ouvre l\'app Raccourcis, touche «\u00A0+\u00A0», nomme le raccourci «\u00A0Nouvelle tâche\u00A0».',
  'Ajoute l\'action «\u00A0Dicter du texte\u00A0».',
  'Ajoute l\'action «\u00A0Obtenir le contenu de l\'URL\u00A0» ; colle l\'adresse («\u00A0Copier l\'adresse\u00A0» ici) ; «\u00A0Afficher plus\u00A0» : Méthode «\u00A0POST\u00A0» ; En-têtes : ajoute «\u00A0Authorization\u00A0» et colle «\u00A0Bearer\u00A0» suivi de ton jeton («\u00A0Copier mon jeton\u00A0» ici) ; Corps de la requête «\u00A0JSON\u00A0» : un champ texte «\u00A0titre\u00A0» = «\u00A0Texte dicté\u00A0».',
  'Ajoute l\'action «\u00A0Afficher le résultat\u00A0». Touche OK.',
  'Essaie : «\u00A0Dis Siri, nouvelle tâche\u00A0», puis «\u00A0appeler le fournisseur demain 10 h\u00A0».',
]

function RecetteSiri({ adresse }) {
  const [copiee, setCopiee] = useState(false)
  const copierAdresse = async () => { setCopiee(await copier(adresse)) }
  return (
    <>
      <ol className="list-decimal">{RECETTE_SIRI.map((ligne) => <li key={ligne}>{ligne}</li>)}</ol>
      <button type="button" className="bouton second" onClick={copierAdresse}>Copier l'adresse</button>
      {copiee ? <p className="rassure" role="status">Adresse copiée.</p> : null}
      <p className="rassure">Les noms des actions peuvent différer légèrement selon la version d'iOS.</p>
      <p className="rassure">Sans réseau, la dictée est perdue.</p>
      <p className="rassure">Pour ranger dans un projet, commence par «&nbsp;projet&nbsp;» et son nom : «&nbsp;projet Maison acheter du lait&nbsp;».</p>
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
          <p className="ep-phrase">Touche «&nbsp;Installer le raccourci&nbsp;» : l'app Raccourcis s'ouvre. Touche «&nbsp;Ajouter le raccourci&nbsp;» ; quand il demande ton jeton, reviens ici, touche «&nbsp;Copier mon jeton&nbsp;» et colle-le.</p>
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
      <p className="ep-phrase">{"D'abord, dans l'autre sens (le plus utile) : «\u00A0Mes agendas\u00A0» — ajoute l'adresse de ton agenda Microsoft 365, Google ou iCloud (3 au plus). Ensuite :"}</p>
      <Agendas />
      <ol className="list-decimal">
        <li>Touche «&nbsp;Créer le lien du calendrier&nbsp;», puis «&nbsp;S'abonner&nbsp;» : l'iPhone propose de s'abonner ; accepte.</li>
        <li>Si rien ne s'ouvre : «&nbsp;Copier le lien&nbsp;», puis Réglages de l'iPhone → Calendrier (ou Apps → Calendrier) → Comptes → Ajouter un compte → Autre → «&nbsp;Ajouter un calendrier avec abonnement&nbsp;», colle, Suivant, Enregistrer. Les noms exacts peuvent varier selon la version d'iOS.</li>
        <li>Sur l'écran d'accueil : appui long → «&nbsp;+&nbsp;» → Calendrier → Ajouter.</li>
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
      <ol className="list-decimal">
        <li>App Store → Scriptable (gratuite).</li>
        <li>Ici : «&nbsp;Créer le jeton de la tuile&nbsp;», puis «&nbsp;Copier le script&nbsp;».</li>
        <li>Dans Scriptable : «&nbsp;+&nbsp;», colle, nomme le script «&nbsp;Tâches&nbsp;».</li>
        <li>Touche ▶ ; colle ton jeton quand il est demandé («&nbsp;Copier mon jeton&nbsp;» ici).</li>
        <li>Écran d'accueil → appui long → «&nbsp;+&nbsp;» → Scriptable → grande taille → Ajouter ; touche la tuile en mode modification → Script : «&nbsp;Tâches&nbsp;».</li>
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
      setTest({ ok: true, texte: 'Une notification «\u00A0Test des notifications\u00A0» doit arriver.' })
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
      <MettreSurAccueil fait={installee()} />
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
