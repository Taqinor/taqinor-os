import { useEffect, useState } from 'react'
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

const COLONNES = 'grid-cols-[64px_1.3fr_1.35fr_0.8fr_1fr]'

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
        className="peer absolute inset-0 m-0 cursor-pointer opacity-0 disabled:cursor-default"
      />
      {rempli ? (
        <span className="flex h-[22px] w-[22px] items-center justify-center rounded-md bg-foreground text-background peer-focus-visible:ring-2 peer-focus-visible:ring-ring" aria-hidden="true">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5" /></svg>
        </span>
      ) : (
        <span className="h-[22px] w-[22px] rounded-md border-[1.5px] border-border bg-card peer-focus-visible:ring-2 peer-focus-visible:ring-ring" aria-hidden="true" />
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
            className="inline-flex min-h-[44px] items-center gap-1 text-sm text-info underline-offset-2 hover:underline"
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
        <span className="text-xs text-muted-foreground">Gardés vides tant qu’aucune page publiée ne donne de valeur</span>
      </span>
      <span className="flex flex-col pr-3">
        <span className="font-semibold text-warning-text">Aucune valeur publiée — à saisir par vous</span>
        <span className="text-xs text-muted-foreground">Rien n’est proposé : une valeur tapée de mémoire serait inventée</span>
      </span>
      <span className="text-muted-foreground">—</span>
      <span className="flex items-center gap-3">
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <CircleDashed size={16} className="flex-none" aria-hidden="true" />
          Vide
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
      .then((res) => { if (!annule) setProfil(res?.data ?? null) })
      .catch(() => { if (!annule) setErreur('Profil de départ indisponible.') })
    return () => { annule = true }
  }, [lecture])

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

  return (
    <Card className={seul ? 'space-y-5 border-0 bg-transparent p-0 shadow-none' : 'mt-5 space-y-4 p-4'}
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
          restent à l'écran, comme la maquette, quel que soit le nombre de réglages. */}
      <section aria-label="Réglages proposés"
        className={`overflow-auto rounded-[14px] border border-border bg-card ${seul ? 'min-h-[240px] max-h-[calc(100dvh-23rem)]' : ''}`}>
        <div className="min-w-[760px]">
          <div className={`sticky top-0 z-10 grid ${COLONNES} h-11 items-center border-b border-border bg-background px-2 pr-5 text-xs font-semibold text-muted-foreground`}>
            <span className="text-center">Remplir</span><span>Réglage</span><span>Valeur proposée</span>
            <span>Source</span><span>État</span>
          </div>
          {valeurs.map((v) => (
            <LigneProfil key={`${v.section}-${v.cle}`} v={v} reglages={reglages} peut={peut}
              coche={!decoches.has(v.cle)} onBascule={() => basculer(v.cle)} />
          ))}
          {sansSource.length > 0 && <LigneSansSource sansSource={sansSource} />}
          {sansSource.length > 0 && (
        <details className="border-t border-border px-4 py-2 text-xs" data-testid="acal405-sans-source">
          <summary className="cursor-pointer text-muted-foreground">
            {sansSource.length} réglages sans valeur publiée (laissés vides)
          </summary>
          <ul className="mt-1 space-y-1">
            {sansSource.map((s) => <li key={`${s.section}-${s.cle}`}>{nomSansSource(s.cle)} — {s.motif}</li>)}
          </ul>
        </details>
          )}
        </div>
      </section>

      <div className="flex flex-wrap items-center gap-4">
        <span className="flex min-w-[260px] flex-1 items-start gap-2.5 text-sm leading-snug text-muted-foreground">
          <Info size={18} className="mt-0.5 flex-none" aria-hidden="true" />
          Tant qu’une valeur publiée sert, le résultat porte la mention « valeur publiée, non mesurée ».
          Tout reste modifiable dans Réglages › Calepinage.
        </span>
        {peut && (
          <Button
            type="button"
            variant="ghost"
            disabled={occupe}
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
            disabled={occupe || nbChoisies === 0}
            className="h-12 rounded-[10px] px-[22px] text-base"
            data-testid="acal405-appliquer"
            onClick={() => agir(
              () => calepinageApi.parametres.appliquerProfilDepart(choisies),
              (d) => `${(d.appliquees || []).length} valeurs appliquées`,
            )}
          >
            {nbVides === 0 ? 'Aucun réglage vide à remplir'
              : (nbChoisies === 0 ? 'Aucun réglage coché'
                : `Remplir ${nbChoisies === 1 ? 'le réglage' : `les ${nbChoisies} réglages`} ${nbChoisies === nbVides ? 'vide' : 'coché'}${nbChoisies === 1 ? '' : 's'}`)}
          </Button>
        )}
      </div>
      {message && (
        <p role="status" className="text-sm text-muted-foreground" data-testid="acal405-message">{message}</p>
      )}
    </Card>
  )
}
