import { Badge } from '../../../../ui'
import { formatDate, formatNumber } from '../../../../lib/format'
import {
  AFaire, BoutonEcran, Ligne, Rangee, SuiteListe, Titre, Vide,
} from './partsTerrain'

/* Copilote vague 2 (CRT-A) — cartes du domaine « chantiers » : `liste_chantiers` (liste
   compacte), `fiche_chantier` (état d'un chantier, aussi rendu après « planifier la pose »).
   Contrats : `assistant_chantiers`, `assistant_chantier_etat`, `chantier_planifier_pose`.
   Aucun prix ni coût n'existe dans ces charges utiles : la carte n'en affiche aucun. */

const STATUT = Object.freeze({
  signe: 'Signé',
  materiel_commande: 'Matériel commandé',
  planifie: 'Planifié',
  en_cours: 'En cours',
  installe: 'Installé',
  receptionne: 'Réceptionné',
  cloture: 'Clôturé',
})
const VUE = Object.freeze({
  en_cours: 'en cours', bloques: 'bloqués', poses_semaine: 'poses de la semaine',
})
const BLOCAGE = Object.freeze({
  sans_date: 'Pas de date de pose',
  sans_technicien: 'Pas de technicien',
  pose_sans_intervention: 'Pose sans intervention',
  pose_depassee: 'Date de pose dépassée',
  acompte_non_encaisse: 'Acompte non encaissé',
})
const INTERVENTION = Object.freeze({
  a_preparer: 'à préparer', prete: 'prête',
})

const sansTiret = (cle) => String(cle ?? '').replace(/_/g, ' ')
const statut = (cle) => STATUT[cle] ?? sansTiret(cle)

/** `liste_chantiers` : une rangée par chantier, blocages et prochain geste. */
export function CarteListeChantiers({ carte }) {
  const d = carte.donnees ?? {}
  const lignes = d.lignes ?? []
  return (
    <div className="min-w-0">
      <Titre>Chantiers {VUE[d.vue] ?? ''} ({formatNumber(d.total ?? lignes.length)})</Titre>
      {lignes.length === 0 ? (
        <Vide texte="Aucun chantier pour cette recherche." />
      ) : (
        <ul className="space-y-2">
          {lignes.map((c) => (
            <Rangee key={c.id} titre={`${c.reference} — ${c.client_nom}`}
              detail={[statut(c.statut),
                c.date_pose_prevue ? `pose le ${formatDate(c.date_pose_prevue)}` : 'pose sans date',
                c.technicien_nom || 'sans technicien'].join(' · ')}>
              {c.blocages?.length > 0 && (
                <p className="mt-1 flex flex-wrap gap-1.5">
                  {c.blocages.map((b) => <Badge key={b} tone="warning">{BLOCAGE[b] ?? sansTiret(b)}</Badge>)}
                </p>
              )}
              <AFaire cle={c.a_faire} />
              <BoutonEcran chemin={c.lien} libelle="Ouvrir le chantier" />
            </Rangee>
          ))}
        </ul>
      )}
      <SuiteListe total={d.total} affiche={lignes.length} />
      {d.note && <p className="mt-1.5 break-words text-xs text-muted-foreground">{d.note}</p>}
      <BoutonEcran chemin={d.lien} libelle="Tous les chantiers" />
    </div>
  )
}

function Pose({ p }) {
  if (!p) return null
  const i = p.intervention_pose
  return (
    <>
      <Ligne etiquette="Pose prévue">
        {p.date_pose_prevue ? formatDate(p.date_pose_prevue) : 'pas de date'}
        {p.date_pose_fin_prevue ? ` → ${formatDate(p.date_pose_fin_prevue)}` : ''}
      </Ligne>
      <Ligne etiquette="Technicien">{p.technicien?.nom || 'non assigné'}</Ligne>
      <Ligne etiquette="Intervention de pose">
        {i
          ? `le ${formatDate(i.date_prevue)} · ${i.technicien_nom}${i.statut ? ` · ${INTERVENTION[i.statut] ?? sansTiret(i.statut)}` : ''}`
          : 'aucune'}
      </Ligne>
    </>
  )
}

function Materiel({ m }) {
  if (!m) return null
  const manques = m.manques ?? []
  return (
    <>
      <Ligne etiquette="Matériel">
        {formatNumber(m.nb_lignes)} lignes · {formatNumber(m.nb_recues)} reçues
        {' '}· {formatNumber(m.nb_en_commande)} en commande · {formatNumber(m.nb_manques)} en manque
        {m.bcf_brouillons > 0 ? ` · ${formatNumber(m.bcf_brouillons)} commande(s) fournisseur en brouillon` : ''}
      </Ligne>
      {manques.length > 0 && (
        <ul className="mt-0.5 list-disc pl-5 text-xs text-muted-foreground">
          {manques.map((x) => (
            <li key={x.produit_id} className="break-words">{x.designation} : manque {formatNumber(x.manque)}</li>
          ))}
        </ul>
      )}
    </>
  )
}

/** `fiche_chantier` : l'état d'un chantier — prêt à poser ? et pourquoi. */
export function CarteFicheChantier({ carte }) {
  const d = carte.donnees ?? {}
  const raisons = d.raisons ?? []
  const suite = d.prochaine_etape
  const liens = d.liens ?? {}
  return (
    <div className="min-w-0">
      <Titre>{d.reference} — {d.client_nom}</Titre>
      <p className="-mt-1 mb-1 flex flex-wrap gap-1.5">
        <Badge tone="neutral">{d.statut_libelle || statut(d.statut)}</Badge>
        {d.annule && <Badge tone="danger">Annulé</Badge>}
        <Badge tone={d.pret_a_poser ? 'success' : 'warning'}>
          {d.pret_a_poser ? 'Prêt à poser' : 'Pas prêt à poser'}
        </Badge>
      </p>
      {raisons.length > 0 && (
        <ul className="list-disc pl-5 text-xs text-warning">
          {raisons.map((r) => <li key={r} className="break-words">{r}</li>)}
        </ul>
      )}
      {d.etape_courante && <Ligne etiquette="Étape">{d.etape_courante.libelle}</Ligne>}
      <Pose p={d.planning} />
      <Materiel m={d.materiel} />
      {d.acompte && (
        <Ligne etiquette="Acompte">
          {d.acompte.exige ? (d.acompte.encaisse ? 'exigé, encaissé' : 'exigé, pas encore encaissé') : 'non exigé'}
        </Ligne>
      )}
      {suite && (
        <Ligne etiquette="Étape suivante">
          {sansTiret(suite.cle)} · {suite.bloquante ? 'bloquée' : 'possible'}
          {suite.raisons?.length > 0 ? ` (${suite.raisons.join(' ; ')})` : ''}
        </Ligne>
      )}
      <AFaire cle={d.a_faire} />
      <div className="flex flex-wrap gap-2">
        <BoutonEcran chemin={liens.chantier ?? d.lien} libelle="Ouvrir le chantier" />
        <BoutonEcran chemin={liens.approvisionnement} libelle="Approvisionnement" />
        <BoutonEcran chemin={liens.intervention_pose} libelle="Intervention de pose" />
      </div>
    </div>
  )
}

const CARTES_CHANTIERS = Object.freeze({
  liste_chantiers: CarteListeChantiers,
  fiche_chantier: CarteFicheChantier,
})
export default CARTES_CHANTIERS
