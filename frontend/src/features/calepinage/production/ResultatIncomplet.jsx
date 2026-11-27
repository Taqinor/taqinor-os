import { Link } from 'react-router-dom'
import { Icone } from '../atelier/coque/primitives'
import { lienManque, lienEtape } from './lienManque'
import { BandeauBorneHaute } from './BandeauProvenanceProduction'
import { estIncomplet } from './BandeauProvenanceProduction.helpers'
import { nomDePerte } from './nomsPertes'
import { kwh } from './ResultatHeros.helpers'
import { GrosChiffre } from './TuilesResultat'
import { compteDuResultat } from './ResultatIncomplet.helpers'

/* ACAL700 / ACAL1833 — L'ÉTAT « RÉSULTAT INCOMPLET » (maquette v2 ResultatsIncomplet.dc.html) :
   un plafond, pas un résultat. Tout est SERVI (`production.total`, `cascade.a_renseigner`,
   `cascade.postes_lisibles`, `pose`, parcours) — aucune valeur chiffrée n'est écrite ici. Résultat
   complet : rien. Sans lignes `a_renseigner` servies, repli sur l'ancien bandeau « borne haute ».
   Niveau essentiel. « Renseigner » ouvre le champ par le mécanisme d'ACAL397.
   Mise en page de la maquette v2 : deux colonnes — à gauche la carte bleu nuit « au plus » (pilule
   « Plafond », étapes du calcul en N segments, pertes qui manquent), « Ce qui est déjà sûr » en 2 × 2
   tuiles et l'indice de performance ABSENT ; à droite « Pour un résultat complet » et les « Années
   basses » ABSENTES (un bloc dont la donnée n'existe pas dit qu'il manque, il n'invente rien). La barre
   « N étapes sur M » n'existe que si le serveur sert les deux nombres (`a_renseigner`). */

const RAISON = {
  reglage_societe: 'Aucune valeur pour votre société',
  fiche_panneau: 'Absent de la fiche du panneau',
}

/* ACAL1940 — les étapes qui lisent la fiche de l'ONDULEUR : sans onduleur désigné (le parcours sert `materiel_designe`
   qui le nomme), leur ligne dit « Aucun onduleur désigné » au lieu de « Absent de la fiche du panneau ». */
const ETAPES_ONDULEUR = new Set(['mppt', 'onduleur', 'ecretage'])
const sansOnduleurDesigne = (parcours) => (parcours?.manque || [])
  .some((m) => m?.code === 'materiel_designe' && /onduleur/i.test(m?.message || ''))

/** « Remplir les 3 réglages vides » quand « Remplir » les remplit tous ; sinon « Remplir 1 des 3 réglages vides ». */
function libelleRemplir(compte) {
  const n = compte.remplissables.length
  if (n === compte.reglagesVides) return `Remplir ${n > 1 ? `les ${n} réglages vides` : 'le réglage vide'}`
  return `Remplir ${n} des ${compte.reglagesVides} réglages vides`
}

/** La page Démarrage rapide, avec CES réglages seuls cochés : elle annonce le même nombre. */
const lienDemarrage = (compte) => `/calepinage/reglages/demarrage-rapide?reglages=${compte.remplissables.join(',')}`

function phraseDuCompte(compte) {
  const total = compte.pertes
  return `${total} ${total > 1 ? 'pertes ne sont pas encore comptées' : 'perte n’est pas encore comptée'}.`
}

/* La part de ce compte qu'on règle ICI (les lignes de la liste) — dite à côté, pas dans la phrase de 14 px
   qui doit tenir sur UNE ligne comme celle de la maquette. */
function partIci(compte) {
  const { pertes: total, lignes: ici } = compte
  return ici === total ? `${total > 1 ? 'Toutes sont' : 'Elle est'} à renseigner ici.` : `${ici} à renseigner ici.`
}

function Valeur({ etiquette, valeur, ton = null, aRenseigner = false }) {
  return (
    <div className="cal-resinc-tuile" data-ton={ton || undefined} data-a-renseigner={aRenseigner ? 'oui' : undefined}>
      <span className="cal-resinc-tuile-label">{etiquette}</span>
      <span className="cal-resinc-tuile-valeur">{valeur}</span>
    </div>
  )
}

/* « Ce qui est déjà sûr » — 2 × 2 tuiles. Une tuile dont la donnée n'est pas servie dit « à renseigner » (ACAL1833,
   « Ombres proches ») ; « Raccordement » n'existe que si l'étape électrique est faite (jamais « Conforme » supposé).
   `avecNote` : la phrase sous les tuiles (état « pas encore simulé », qui n'a pas les deux blocs absents). */
export function CeQuiEstSur({ data, parcours, avecNote = true }) {
  const electrique = (parcours?.etapes || []).find((e) => e.cle === 'electrique')
  const ombres = (data?.cascade?.postes_lisibles?.postes || [])
    .find((p) => p.poste === 'ombres_proches' && p.statut === 'compte')
  // Item 14 (T4-U1-023) — des objets hauts sont posés mais leur ombre n'est pas comptée : « à compter », jamais « à renseigner ».
  const ombresAMesurer = (parcours?.manque || []).some((m) => m?.code === 'ombres_non_mesurees')
  const modules = data?.pose?.total_modules
  // Le kWc dit à côté des panneaux POSÉS est celui de la pose (un fait servi, même sans simulation) : depuis
  // ACAL1602 `production.total.kwc` ne compte que les panneaux raccordés — il ne se lit ici qu'à défaut.
  const kwc = data?.pose?.kwc ?? data?.production?.total?.kwc
  return (
    <section className="cal-res-carte cal-resinc-sur-carte" data-testid="acal700-sur">
      <div className="cal-resinc-sur-tete">
        <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" className="cal-resinc-sur-coche">
          <circle cx="12" cy="12" r="10" className="cal-resinc-sur-fond" />
          <path d="M7.5 12.5l3 3 6-6.5" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <h2 className="cal-res-titre">Ce qui est déjà sûr</h2>
      </div>
      <div className="cal-resinc-sur">
        {modules !== null && modules !== undefined && (
          <Valeur etiquette="Panneaux" valeur={<GrosChiffre valeur={modules} decimals={0} />} />
        )}
        {kwc !== null && kwc !== undefined && (
          <Valeur etiquette="Puissance" valeur={<GrosChiffre valeur={kwc} decimals={2} unite="kWc" />} />
        )}
        {electrique?.etat === 'fait' && (
          <Valeur etiquette="Raccordement" ton="ok" valeur={(
            <span className="cal-resinc-conforme">
              <svg width="26" height="26" viewBox="0 0 24 24" aria-hidden="true">
                <circle cx="12" cy="12" r="11" fill="currentColor" />
                <path d="M7 12.5l3.2 3.2L17 9" fill="none" stroke="var(--cal-surface)" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Conforme
            </span>
          )} />
        )}
        {ombres
          ? <Valeur etiquette="Ombres proches" valeur={<GrosChiffre valeur={ombres.perte_pct} decimals={1} unite="%" signe="− " />} />
          : <Valeur etiquette="Ombres proches" aRenseigner valeur={<span className="cal-resinc-a-renseigner">{ombresAMesurer ? 'à compter' : 'à renseigner'}</span>} />}
      </div>
      {avecNote && (
        <p className="cal-res-sourdine" data-testid="acal700-note">
          Les années basses (9 fois sur 10 au-dessus) et l'indice de performance s'affichent dès que le résultat est complet.
        </p>
      )}
    </section>
  )
}

/* « Étapes du calcul » : N segments (N = `etapes_a_compter` servi), les `etapes_comptees` premiers pleins, les
   autres en tirets ; au-delà de 48 étapes, une piste continue. Rien si le serveur ne sert pas les deux nombres. */
function Progression({ aRenseigner }) {
  const faites = aRenseigner?.etapes_comptees
  const sur = aRenseigner?.etapes_a_compter
  if (typeof faites !== 'number' || typeof sur !== 'number' || sur <= 0) return null
  const largeur = Math.max(0, Math.min(100, (faites / sur) * 100))
  return (
    <div className="cal-resinc-progres" data-testid="acal700-progression">
      <div className="cal-resinc-progres-tete">
        <span className="cal-res-tuile-label">Étapes du calcul</span>
        <span className="cal-resinc-progres-compte">{`${faites} ${faites > 1 ? 'étapes' : 'étape'} sur ${sur}`}</span>
      </div>
      {sur <= 48
        ? (
          <div className="cal-resinc-segments" aria-hidden="true">
            {Array.from({ length: sur }, (_, i) => <span key={i} data-fait={i < faites ? 'oui' : 'non'} />)}
          </div>
        )
        : <div className="cal-resinc-piste" aria-hidden="true"><span style={{ width: `${largeur}%` }} /></div>}
    </div>
  )
}

function LienRemplir({ compte }) {
  return compte.remplissables.length > 0
    ? <Link to={lienDemarrage(compte)} className="cal-resinc-remplir">{libelleRemplir(compte)}</Link>
    : <Link to="/calepinage/reglages" className="cal-resinc-remplir">Saisir mes mesures</Link>
}

function BlocAbsent({ titre, phrase, compte, children, classe }) {
  return (
    <section className={`cal-resinc-absent cal-resinc-absent-${classe}`} data-testid={`acal1833-absent-${classe}`}>
      {children}
      <div className="cal-resinc-absent-texte">
        <div className="cal-resinc-absent-tete">
          <span className="cal-resinc-absent-titre">{titre}</span>
          <span className="cal-resinc-pastille-vide">À renseigner</span>
        </div>
        <span className="cal-resinc-absent-phrase">{phrase}</span>
        <LienRemplir compte={compte} />
      </div>
    </section>
  )
}

function IndiceAbsent({ compte }) {
  return (
    <BlocAbsent titre="Indice de performance" phrase="S'affiche dès que le résultat est complet." compte={compte}
      classe="indice">
      <svg width="120" height="66" viewBox="0 0 120 66" aria-hidden="true" className="cal-resinc-jauge">
        <path d="M10 60a50 50 0 01100 0" fill="none" className="cal-resinc-jauge-piste" strokeWidth="12" strokeLinecap="round" />
        <path d="M10 60a50 50 0 01100 0" fill="none" className="cal-resinc-jauge-trait" strokeWidth="1.5" strokeDasharray="3 5" />
        <text x="60" y="58" textAnchor="middle" fontSize="22" fontWeight="700" className="cal-resinc-jauge-tiret">—</text>
      </svg>
    </BlocAbsent>
  )
}

function AnneesBassesAbsentes({ compte }) {
  return (
    <BlocAbsent titre="Années basses" phrase="9 fois sur 10 au-dessus. S'affiche dès que le résultat est complet."
      compte={compte} classe="annees">
      <div className="cal-resinc-hachures" aria-hidden="true">
        {[38, 54, 70, 54, 38].map((h, i) => <span key={i} style={{ height: `${h}%` }} />)}
      </div>
    </BlocAbsent>
  )
}

/* « Démarrage rapide » : MÊME décompte que la page Démarrage rapide — « Remplir » ne remplit que les réglages
   pour lesquels une valeur publiée existe ; ceux qu'il laisse sans valeur ne sont jamais annoncés comme « à remplir ». */
function DemarrageRapideBloc({ compte }) {
  const remplissables = compte.remplissables.length
  const texte = remplissables > 0
    ? `${libelleRemplir(compte)} avec des valeurs publiées, chacune avec sa source. Vous pourrez les remplacer par vos mesures.`
    : 'Aucune valeur publiée n’existe pour ces réglages : le démarrage rapide ne peut pas les remplir, saisissez vos mesures.'
  return (
    <div className="cal-resinc-demarrage" data-testid="acal700-demarrage">
      <svg width="40" height="40" viewBox="0 0 40 40" aria-hidden="true" className="cal-resinc-eclair">
        <circle cx="20" cy="20" r="19" className="cal-resinc-eclair-fond" />
        <path d="M22 9l-9 13h7l-2 9 9-13h-7z" className="cal-resinc-eclair-trait" strokeWidth="1.2" strokeLinejoin="round" />
      </svg>
      <span className="cal-resinc-demarrage-texte">
        <strong>Démarrage rapide</strong>
        <span data-testid="acal700-demarrage-texte">{texte}</span>
      </span>
      {remplissables > 0 ? (
        <Link to={lienDemarrage(compte)} className="cal-res-cta"
          data-testid="acal700-lien-reglages">
          Voir les valeurs
          <Icone nom="suivant" taille={18} epaisseur={2.4} />
        </Link>
      ) : (
        // Rien à remplir : pas de bouton or qui promet des valeurs — un lien discret vers la page des réglages.
        <Link to="/calepinage/reglages" className="cal-resinc-discret" data-testid="acal700-lien-reglages">
          Saisir mes mesures
        </Link>
      )}
    </div>
  )
}

const MAX_PASTILLES = 4

/* ACAL1939 — « Voir les étapes » ouvre le détail PUIS y défile, une fois monté (requestAnimationFrame) : défiler
   avant le montage s'arrêtait à la hauteur de la page d'alors, seul le titre du détail se voyait. */
function voirLesEtapes(onVoirEtapes) {
  onVoirEtapes()
  globalThis.requestAnimationFrame?.(() => {
    globalThis.document?.querySelector('[data-zone="avance"]')?.scrollIntoView?.({ block: 'start' })
  })
}

export default function ResultatIncomplet({ calepinageId, data, parcours = null, onVoirEtapes = null, nomProduction = null }) {
  const total = data?.production?.total
  // Relecture E5 M1 — la conception servie à côté : la production de la POSE porte son nom exact.
  const nom = nomProduction ?? 'Production la première année'
  if (!estIncomplet(total)) return null
  const aRenseigner = data?.cascade?.a_renseigner
  const lignes = Array.isArray(aRenseigner?.lignes) ? aRenseigner.lignes : []
  if (lignes.length === 0) return <BandeauBorneHaute total={total} />
  const manquantes = lignes.slice(0, MAX_PASTILLES).map((l) => nomDePerte(l.etape, l.libelle).nom)
  // Le compte annoncé (« N pertes ») égale les lignes listées, sinon « et K autres » avec « Voir les étapes ».
  const compte = compteDuResultat(aRenseigner)
  const { autres, reglagesVides: societe } = compte
  const sansOnduleur = sansOnduleurDesigne(parcours)
  return (
    <div className="cal-resinc" data-testid="acal700-incomplet">
      <div className="cal-resinc-haut">
        <div className="cal-resinc-colonne">
          <section className="cal-res-tuile cal-resinc-plafond" aria-label={`${nom}, au plus`}>
            <div className="cal-resinc-plafond-tete">
              <p className="cal-res-tuile-label m-0" data-testid="acal700-etiquette">
                {`${nom} · au plus`}
              </p>
              <span className="cal-resinc-pilule-plafond">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6"
                  strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 5v14M6 13l6 6 6-6" /></svg>
                Plafond
              </span>
            </div>
            <p className="cal-res-tuile-valeur m-0" data-testid="acal700-valeur">
              {typeof total.p50_kwh === 'number'
                ? <GrosChiffre valeur={total.p50_kwh} decimals={0} unite="kWh" /> : kwh(total.p50_kwh)}
            </p>
            <p className="cal-resinc-phrase" data-testid="acal700-plafond" title={partIci(compte)}>
              {`C'est un plafond : ${phraseDuCompte(compte)} Le chiffre réel sera plus bas.`}
            </p>
            <Progression aRenseigner={aRenseigner} />
            <div className="cal-resinc-manques" data-testid="acal1833-manques">
              {manquantes.map((nom, i) => <span key={`${nom}-${i}`} className="cal-resinc-manque">{nom}</span>)}
            </div>
          </section>
          <CeQuiEstSur data={data} parcours={parcours} avecNote={false} />
          <IndiceAbsent compte={compte} />
        </div>
        <div className="cal-resinc-colonne">
          <section className="cal-res-carte" data-testid="acal700-liste">
            <div className="cal-res-entete">
              <h1 className="cal-res-titre">Pour un résultat complet</h1>
              <span className="cal-res-sourdine cal-resinc-compteur" data-testid="acal1833-compteur">
                {societe === lignes.length
                  ? `${societe} ${societe > 1 ? 'réglages vides' : 'réglage vide'}`
                  : `${lignes.length} à renseigner`}
              </span>
            </div>
            <ol className="cal-resinc-liste">
              {lignes.map((ligne, i) => (
                <li key={`${ligne.etape}-${ligne.cle}`} className="cal-resinc-ligne" data-testid="acal700-ligne">
                  <span className="cal-resinc-rang" aria-hidden="true">{i + 1}</span>
                  <span className="cal-resinc-texte">
                    <span className="cal-resinc-nom" title={nomDePerte(ligne.etape, ligne.libelle).technique || undefined}>
                      {nomDePerte(ligne.etape, ligne.libelle).nom}
                    </span>
                    {RAISON[ligne.nature] && (
                      <span className="cal-resinc-raison">
                        {sansOnduleur && ETAPES_ONDULEUR.has(ligne.etape) ? 'Aucun onduleur désigné' : (ligne.motif || RAISON[ligne.nature])}
                      </span>
                    )}
                  </span>
                  <Link to={sansOnduleur && ETAPES_ONDULEUR.has(ligne.etape)
                    ? lienEtape(calepinageId, 'electrique') : lienManque(calepinageId, ligne.cible)}
                  className="cal-resinc-bouton" data-testid="acal700-renseigner">
                    {sansOnduleur && ETAPES_ONDULEUR.has(ligne.etape) ? 'Désigner' : 'Renseigner'}
                  </Link>
                </li>
              ))}
              {autres > 0 && (
                <li className="cal-resinc-ligne cal-resinc-autres" data-testid="acal700-autres">
                  <span className="cal-resinc-texte">
                    <span className="cal-resinc-nom">{`et ${autres} ${autres > 1 ? 'autres' : 'autre'}`}</span>
                    <span className="cal-resinc-raison">{`${autres > 1 ? 'pertes pas encore comptées' : 'perte pas encore comptée'}, dans le détail du calcul`}</span>
                  </span>
                  {onVoirEtapes && (
                    <button type="button" className="cal-resinc-bouton" onClick={() => voirLesEtapes(onVoirEtapes)}>Voir les étapes</button>
                  )}
                </li>
              )}
            </ol>
            <DemarrageRapideBloc compte={compte} />
          </section>
          <AnneesBassesAbsentes compte={compte} />
        </div>
      </div>
    </div>
  )
}
