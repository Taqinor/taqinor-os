import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { CircleCheck, CircleDashed, ExternalLink, Info } from 'lucide-react'
import calepinageApi from '../../../api/calepinageApi'
import { useHasPermission } from '../../../hooks/useHasPermission'
import { Button, Card } from '../../../ui'
import {
  dateFr, libelleReglage, nomSansSource, precisionValeur, sourceCourte, valeurLisible,
} from './profilDepart'

/* ============================================================================
   ACAL405 (D-ACAL-31) — « DÉMARRAGE RAPIDE » : LES VALEURS PUBLIÉES PROPOSÉES.
   ----------------------------------------------------------------------------
   `GET calepinages/profil-depart/` (ACAL403, contrat
   `calepinage_profil_depart.json`) sert `{valeurs, sans_source}`. AUCUNE valeur
   n'est écrite ici : « Remplir les N réglages vides » appelle `POST` (le serveur
   ne touche que les clés VIDES), puis `onChange` fait relire les réglages. L'état
   de chaque valeur est celui que le serveur SERT (`etat` : `a_appliquer`,
   `posee_par_profil`, `deja_saisie`, lu par la référence écrite du profil) ; à
   défaut, il se lit sur les réglages SERVIS, jamais sur un brouillon. Le profil
   est relu après chaque geste.

   MAQUETTE « Démarrage rapide » : un tableau Remplir · Réglage · Valeur proposée ·
   Source · État. Les réglages portent un NOM en français courant, la valeur son
   unité à la française, la source son éditeur (« PVsyst · ouvrir ») ; la citation
   complète reste dans la ligne (dépliable) et en infobulle. Jamais de JSON, jamais
   une clé technique. Les cases « Remplir » CHOISISSENT : cochées par défaut sur chaque réglage vide, le
   geste envoie la liste des clés cochées (`POST profil-depart/` avec `cles`) ; une valeur déjà en place
   n'a pas de case active (jamais écrasée).
   ========================================================================== */

const saisie = (reglages, { section, cle }) => {
  const ligne = reglages?.[section]?.[cle]
  return Boolean(ligne) && typeof ligne === 'object'
    && ligne.valeur !== null && ligne.valeur !== undefined
}

/** L'état de la ligne : `a_appliquer` | `posee_par_profil` | `deja_saisie`. */
const etatDe = (v, reglages) => v.etat ?? (saisie(reglages, v) ? 'deja_saisie' : 'a_appliquer')

/* Les colonnes de la maquette (64 px · 1,3 · 1,35 · 0,8 · 1 fr) sur 1 344 px. Dans le cadre ERP la page n'a que
   ~1 136 px : « Réglage » reçoit une part plus large pour que les libellés ne se replient pas. */
const COLONNES = 'grid-cols-[64px_minmax(0,1.55fr)_minmax(0,1.25fr)_minmax(0,0.75fr)_minmax(0,1.05fr)]'

function Etat({ v, etat, reglages }) {
  const saisi = reglages?.[v.section]?.[v.cle]
  if (etat === 'deja_saisie') {
    const sienne = saisi && typeof saisi === 'object' && saisi.valeur !== undefined && saisi.valeur !== null
      ? ` (${valeurLisible(saisi.valeur, v.unite)})` : ''
    return (
      <span className="flex items-center gap-1.5 font-medium text-success-text" data-testid={`acal405-etat-${v.cle}`}>
        <CircleCheck size={16} className="flex-none" aria-hidden="true" />
        {`Déjà renseigné par vous${sienne} — conservé`}
      </span>
    )
  }
  if (etat === 'posee_par_profil') {
    return (
      <span className="flex items-center gap-1.5 font-medium text-foreground" data-testid={`acal405-etat-${v.cle}`}>
        <CircleCheck size={16} className="flex-none text-success-text" aria-hidden="true" />
        Posée par le profil (retirable)
      </span>
    )
  }
  return (
    <span className="flex items-center gap-1.5 text-muted-foreground" data-testid={`acal405-etat-${v.cle}`}>
      <CircleDashed size={16} className="flex-none" aria-hidden="true" />
      Vide
    </span>
  )
}

/** La case « Remplir » (maquette) : cochée = sera remplie. Active seulement sur un réglage vide — une valeur
    déjà en place n'est jamais remplacée (case vide, inactive). */
/* Le bord de la case d'une valeur déjà en place : le gris soutenu de la maquette (rgb 138,148,181), dérivé du jeton.
   La maquette la laisse active (« Remplacer votre valeur ») ; D-ACAL-31 (« rien n'est écrasé ») l'éteint, visible. */
const BORD_CASE_EN_PLACE = 'border-[color:color-mix(in_srgb,var(--muted-foreground)_62%,var(--border))]'

function CaseRemplir({ etat, nom, coche, actif, onBascule }) {
  const rempli = etat === 'a_appliquer' && coche
  return (
    <label className="relative mx-auto flex h-11 w-11 items-center justify-center">
      <input
        type="checkbox"
        checked={rempli}
        disabled={!actif}
        onChange={onBascule}
        aria-label={etat === 'a_appliquer' ? `Remplir : ${nom}` : `Déjà en place, non remplacé : ${nom}`}
        title={etat === 'a_appliquer' ? undefined : 'Déjà en place : jamais remplacé par une valeur publiée (D-ACAL-31)'}
        className="peer absolute inset-0 m-0 cursor-pointer opacity-0 disabled:cursor-default"
      />
      {rempli ? (
        <span className="flex h-[22px] w-[22px] items-center justify-center rounded-md bg-foreground text-background peer-focus-visible:ring-2 peer-focus-visible:ring-ring" aria-hidden="true">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5" /></svg>
        </span>
      ) : (
        <span className={`h-[22px] w-[22px] rounded-md border-[1.5px] bg-card peer-focus-visible:ring-2 peer-focus-visible:ring-ring ${actif ? 'border-border' : BORD_CASE_EN_PLACE}`} aria-hidden="true" />
      )}
    </label>
  )
}

function LigneProfil({ v, reglages, coche, peut, onBascule }) {
  const { nom, aide } = libelleReglage(v.cle)
  const etat = etatDe(v, reglages)
  const precision = precisionValeur(v.valeur)
  const citation = `${v.reference} — ${v.url} — lu le ${dateFr(v.date_lecture)}`
  return (
    <div
      className={`grid ${COLONNES} items-center border-b border-border px-2 pr-5 text-sm min-h-[60px]`}
      data-testid={`acal405-valeur-${v.cle}`}
    >
      <CaseRemplir etat={etat} nom={nom} coche={coche} actif={peut && etat === 'a_appliquer'} onBascule={onBascule} />
      <span className="flex flex-col pr-3">
        <span className="font-semibold">{nom}</span>
        {aide ? <span className="text-xs text-muted-foreground">{aide}</span> : null}
      </span>
      <span className="flex flex-col pr-3">
        <span className="font-display text-base font-semibold tabular-nums">{valeurLisible(v.valeur, v.unite)}</span>
        {precision ? <span className="text-xs text-muted-foreground">{precision}</span> : null}
      </span>
      <span className="flex flex-col pr-3">
        {/* La citation complète (page, URL entière, date de lecture) : en infobulle et pour les lecteurs
            d'écran — plus de ligne dépliable qui allongerait chaque rangée. */}
        <span className="flex items-center gap-2" title={citation}>
          <span className="font-semibold">{sourceCourte(v.reference)}</span>
          <a href={v.url} target="_blank" rel="noreferrer"
            className="inline-flex min-h-[44px] items-center gap-1 text-sm text-info underline underline-offset-2 hover:text-foreground"
            aria-label={`Ouvrir la source : ${sourceCourte(v.reference)}`}>
            ouvrir<ExternalLink size={14} aria-hidden="true" />
          </a>
          <span className="sr-only" data-testid={`acal405-citation-${v.cle}`}>{`Citation complète : ${citation}`}</span>
        </span>
      </span>
      <Etat v={v} etat={etat} reglages={reglages} />
    </div>
  )
}

/** La lecture du profil est en cours : des lignes grises à la place des réglages (aucune annonce de résultat). */
function LignesEnLecture() {
  return Array.from({ length: 6 }, (_, rang) => (
    <div key={rang} className={`grid ${COLONNES} min-h-[60px] animate-pulse items-center border-b border-border px-2 pr-5`}
      aria-hidden="true" data-testid="acal405-ligne-en-lecture">
      <span className="mx-auto h-[22px] w-[22px] rounded-md bg-muted" />
      <span className="flex flex-col gap-1.5 pr-3"><span className="h-4 w-3/5 rounded bg-muted" /><span className="h-3 w-4/5 rounded bg-muted" /></span>
      <span className="h-5 w-1/3 rounded bg-muted" />
      <span className="h-4 w-1/2 rounded bg-muted" />
      <span className="h-4 w-2/3 rounded bg-muted" />
    </div>
  ))
}

/** Le réglage tapé À LA MAIN : aucune valeur publiée n'existe, la ligne le dit et mène à la saisie. */
function LigneSansSource({ sansSource }) {
  return (
    <div className={`grid ${COLONNES} items-center bg-muted/30 px-2 pr-5 text-sm min-h-[60px]`}>
      <label className="relative mx-auto flex h-11 w-11 items-center justify-center">
        <input type="checkbox" disabled aria-label="Aucune valeur publiée : à saisir par vous"
          className="absolute inset-0 m-0 opacity-0" />
        <span className="h-[22px] w-[22px] rounded-md border-[1.5px] border-dashed border-border bg-muted" aria-hidden="true" />
      </label>
      <span className="flex flex-col pr-3">
        <span className="font-semibold">{`${sansSource.length} autres réglages`}</span>
        <span className="text-xs text-muted-foreground">Rien n’est proposé tant qu’aucune page publiée ne donne de valeur</span>
      </span>
      <span className="flex flex-col pr-3">
        <span className="font-semibold text-warning-text">Aucune valeur publiée — à saisir par vous</span>
        <span className="text-xs text-muted-foreground">Rien n’est proposé : une valeur tapée de mémoire serait inventée</span>
      </span>
      <span className="text-muted-foreground">—</span>
      <span className="flex items-center gap-3">
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <CircleDashed size={16} className="flex-none" aria-hidden="true" />
          À saisir
        </span>
        <a href="/calepinage/reglages#calx69-section-simulation"
          className="flex h-11 items-center rounded-[10px] border border-border px-3.5 font-semibold text-foreground no-underline hover:bg-muted"
          data-testid="acal405-saisir">
          Saisir
        </a>
      </span>
    </div>
  )
}

export default function DemarrageRapide({ reglages, peutApprouver, onChange, autonome }) {
  const [profil, setProfil] = useState(null)
  const [erreur, setErreur] = useState(null)
  // La LECTURE du profil (≈ 8 s sous charge) : en cours tant que ni profil ni échec ; l'échec a sa place dans le tableau.
  const [echecLecture, setEchecLecture] = useState(false)
  const [message, setMessage] = useState(null)
  const [occupe, setOccupe] = useState(false)
  // Les clés DÉCOCHÉES par la personne : tout réglage vide est coché d'office (maquette).
  const [decoches, setDecoches] = useState(() => new Set())
  const basculer = (cle) => setDecoches((avant) => {
    const apres = new Set(avant)
    if (apres.has(cle)) apres.delete(cle)
    else apres.add(cle)
    return apres
  })

  const [lecture, setLecture] = useState(0)
  // Le droit d'approuver : celui que l'appelant donne, à défaut celui de la personne connectée
  // (l'écran seul, `/calepinage/reglages/demarrage-rapide`, n'a pas d'appelant).
  const droit = useHasPermission('calepinage_approuver')
  const peut = peutApprouver ?? droit
  // Seul sur sa route : titre de page et fil d'Ariane ; dans Réglages : une carte parmi les autres.
  const seul = autonome ?? (typeof window !== 'undefined'
    && /\/demarrage-rapide\/?$/.test(window.location.pathname))

  useEffect(() => {
    let annule = false
    Promise.resolve(calepinageApi.parametres.profilDepart())
      .then((res) => { if (!annule) { setProfil(res?.data ?? null); setEchecLecture(false) } })
      .catch(() => { if (!annule) setEchecLecture(true) })
    return () => { annule = true }
  }, [lecture])
  const relire = () => { setEchecLecture(false); setProfil(null); setLecture((n) => n + 1) }

  // Seul sur sa route : la page est une colonne qui remplit la fenêtre (titre, tableau qui défile dans sa carte,
  // pied collé en bas — maquette), quelle que soit la hauteur de la fenêtre.
  const racine = useRef(null)
  const [hauteur, setHauteur] = useState(null)
  useLayoutEffect(() => {
    if (!seul) return undefined
    const mesurer = () => {
      const haut = racine.current?.getBoundingClientRect().top ?? 0
      setHauteur(Math.max(360, Math.floor(window.innerHeight - haut - 24)))
    }
    mesurer()
    window.addEventListener('resize', mesurer)
    return () => window.removeEventListener('resize', mesurer)
  }, [seul])

  const agir = async (appel, phrase) => {
    setOccupe(true)
    setMessage(null)
    setErreur(null)
    try {
      const res = await appel()
      setMessage(phrase(res?.data ?? {}))
      setLecture((n) => n + 1)
      await onChange?.()
    } catch (e) {
      const detail = e?.response?.data?.detail
      setErreur(typeof detail === 'string' && detail
        ? detail : 'Le geste n’a pas pu être fait : rien n’a changé.')
    } finally {
      setOccupe(false)
    }
  }

  const valeurs = Array.isArray(profil?.valeurs) ? profil.valeurs : []
  const sansSource = Array.isArray(profil?.sans_source) ? profil.sans_source : []
  // N : les réglages vides que « Remplir » va réellement remplir (lus sur l'état servi).
  const vides = valeurs.filter((v) => etatDe(v, reglages) === 'a_appliquer')
  const nbVides = vides.length
  const choisies = vides.filter((v) => !decoches.has(v.cle)).map((v) => v.cle)
  const nbChoisies = choisies.length
  const Titre = seul ? 'h1' : 'h2'
  const enLecture = profil === null && !echecLecture

  const libelleAppliquer = () => {
    if (enLecture || echecLecture) return 'Remplir les réglages vides'
    if (nbVides === 0) return 'Aucun réglage à remplir'
    if (nbChoisies === 0) return 'Aucun réglage coché'
    return `Remplir ${nbChoisies === 1 ? 'le réglage' : `les ${nbChoisies} réglages`} ${nbChoisies === nbVides ? 'vide' : 'coché'}${nbChoisies === 1 ? '' : 's'}`
  }

  return (
    <Card ref={racine}
      className={seul ? 'flex flex-col gap-5 border-0 bg-transparent p-0 shadow-none' : 'mt-5 space-y-4 p-4'}
      style={seul && hauteur ? { height: hauteur } : undefined}
      data-testid="acal405-demarrage">
      {autonome === true ? (
        <nav aria-label="Fil d’Ariane" className="flex items-center gap-3 text-sm text-muted-foreground">
          <a href="/calepinage/reglages" className="text-muted-foreground no-underline hover:underline">Réglages</a>
          <span aria-hidden="true">/</span>
          <a href="/calepinage" className="text-muted-foreground no-underline hover:underline">Calepinage</a>
          <span aria-hidden="true">/</span>
          <span className="font-semibold text-foreground" aria-current="page">Démarrage rapide</span>
        </nav>
      ) : null}
      <div className="flex flex-col gap-1.5">
        <Titre className={seul ? 'font-display text-h2 font-semibold text-foreground' : 'text-base font-semibold text-foreground'}>
          Démarrage rapide
        </Titre>
        <p className={`max-w-[860px] text-muted-foreground ${seul ? 'text-base leading-normal' : 'text-xs'}`}>
          Les réglages encore vides peuvent recevoir une valeur publiée par un logiciel de référence,
          toujours affichée avec sa source.<br />
          Vous la remplacerez par vos propres mesures quand vous les aurez ; ce que vous avez déjà
          saisi n’est jamais écrasé.
        </p>
      </div>
      {erreur && (
        <p role="alert" className="text-xs text-destructive" data-testid="acal405-erreur">{erreur}</p>
      )}

      {/* Le tableau défile DANS sa carte (en-tête collé) : le titre en haut et le pied (boutons) en bas
          restent à l'écran, comme la maquette, quelle que soit la hauteur de la fenêtre. */}
      <section aria-label="Réglages proposés" aria-busy={enLecture}
        className={`overflow-auto rounded-[14px] border border-border bg-card ${seul ? 'min-h-[180px] min-w-0 shrink' : ''}`}>
        <div className="min-w-[760px]">
          <div className={`sticky top-0 z-10 grid ${COLONNES} h-11 items-center border-b border-border bg-background px-2 pr-5 text-xs font-semibold text-muted-foreground`}>
            <span className="text-center">Remplir</span><span>Réglage</span><span>Valeur proposée</span>
            <span>Source</span><span>État</span>
          </div>
          {enLecture ? <LignesEnLecture /> : null}
          {echecLecture ? (
            <div role="alert" className="flex flex-col items-start gap-3 px-6 py-8 text-sm" data-testid="acal405-echec-lecture">
              <span className="text-foreground">Les réglages proposés n’ont pas pu être lus.</span>
              <Button type="button" variant="outline" className="h-11 rounded-[10px]" onClick={relire}
                data-testid="acal405-reessayer">
                Réessayer
              </Button>
            </div>
          ) : null}
          {valeurs.map((v) => (
            <LigneProfil key={`${v.section}-${v.cle}`} v={v} reglages={reglages} peut={peut}
              coche={!decoches.has(v.cle)} onBascule={() => basculer(v.cle)} />
          ))}
          {sansSource.length > 0 && <LigneSansSource sansSource={sansSource} />}
          {sansSource.length > 0 && (
        <details className="border-t border-border px-4 py-2 text-xs" data-testid="acal405-sans-source">
          <summary className="cursor-pointer text-muted-foreground">
            {sansSource.length} réglages sans valeur publiée (à saisir par vous)
          </summary>
          <ul className="mt-1 space-y-1">
            {sansSource.map((s) => <li key={`${s.section}-${s.cle}`}>{nomSansSource(s.cle)} — {s.motif}</li>)}
          </ul>
        </details>
          )}
        </div>
      </section>

      <div className="mt-auto flex flex-none flex-wrap items-center gap-4">
        <span className="flex min-w-[260px] flex-1 items-start gap-2.5 text-sm leading-snug text-muted-foreground">
          <Info size={18} className="mt-0.5 flex-none" aria-hidden="true" />
          Tant qu’une valeur publiée sert, le résultat porte la mention « valeur publiée, non mesurée ».
          Tout reste modifiable dans Réglages › Calepinage.
        </span>
        {peut && (
          <Button
            type="button"
            variant="ghost"
            disabled={occupe || enLecture || echecLecture}
            className="h-11 rounded-[10px] px-3 text-sm text-muted-foreground"
            data-testid="acal405-retirer"
            onClick={() => agir(
              () => calepinageApi.parametres.retirerProfilDepart(),
              (d) => `${(d.retirees || []).length} valeurs retirées`,
            )}
          >
            Retirer le profil
          </Button>
        )}
        <a
          href="/calepinage/reglages#calx69-section-simulation"
          className="flex h-12 items-center rounded-[10px] border border-border bg-card px-5 text-base font-semibold text-foreground no-underline hover:bg-muted"
          data-testid="acal405-saisir-main"
        >
          Tout saisir à la main
        </a>
        {peut && (
          <Button
            type="button"
            disabled={occupe || enLecture || echecLecture || nbChoisies === 0}
            className="h-12 rounded-[10px] px-[22px] text-base"
            data-testid="acal405-appliquer"
            onClick={() => agir(
              () => calepinageApi.parametres.appliquerProfilDepart(choisies),
              (d) => `${(d.appliquees || []).length} valeurs appliquées`,
            )}
          >
            {libelleAppliquer()}
          </Button>
        )}
      </div>
      {message && (
        <p role="status" className="text-sm text-muted-foreground" data-testid="acal405-message">{message}</p>
      )}
    </Card>
  )
}
