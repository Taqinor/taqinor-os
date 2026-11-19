import { Badge } from '../../../../ui'
import { formatDate, formatDateTime, formatNumber } from '../../../../lib/format'
import {
  AFaire, BoutonEcran, Citation, Ligne, Rangee, SuiteListe, Titre, Vide,
} from './partsTerrain'

/* Copilote vague 2 (CRT-A) — cartes du domaine « visites » : `liste_visites` (agenda),
   `fiche_visite` (résumé d'une visite, aussi rendu après une annulation), `charge_equipe`
   (charge au jour près). Contrats : `assistant_agenda`, `assistant_visite_resume`,
   `visite_annuler`, `assistant_charge`. Le retour et les mesures du terrain sont du
   contenu saisi par un tiers : texte brut, présenté comme cité. */

const STATUT = Object.freeze({
  brouillon: 'À planifier',
  en_cours: 'En cours',
  terminee: 'Terminée',
  validee: 'Validée',
  a_refaire: 'À refaire',
  annulee: 'Annulée',
})
const FILTRE = Object.freeze({
  tout: 'toutes',
  sans_technicien: 'sans technicien',
  a_valider: 'à valider',
  en_retard: 'en retard',
  a_refaire: 'à refaire',
})
const TONS = Object.freeze({
  validee: 'success', terminee: 'info', en_cours: 'info', a_refaire: 'warning', annulee: 'neutral',
})

const statut = (cle) => STATUT[cle] ?? String(cle ?? '').replace(/_/g, ' ')

function Totaux({ t }) {
  if (!t) return null
  const parts = [
    [t.planifiees, 'planifiée(s)'], [t.sans_technicien, 'sans technicien'],
    [t.a_valider, 'à valider'], [t.en_retard, 'en retard'], [t.a_refaire, 'à refaire'],
  ].filter(([n]) => n != null)
  return (
    <p className="mb-2 break-words text-xs text-muted-foreground">
      {parts.map(([n, texte]) => `${formatNumber(n)} ${texte}`).join(' · ')}
    </p>
  )
}

/** `liste_visites` : l'agenda, une rangée par visite avec son prochain geste. */
export function CarteListeVisites({ carte }) {
  const d = carte.donnees ?? {}
  const lignes = d.lignes ?? []
  const filtre = d.filtre && d.filtre !== 'tout' ? ` — ${FILTRE[d.filtre] ?? d.filtre}` : ''
  return (
    <div className="min-w-0">
      <Titre>Visites du {formatDate(d.du)} au {formatDate(d.au)}{filtre}</Titre>
      <Totaux t={d.totaux} />
      {lignes.length === 0 ? (
        <Vide texte="Aucune visite pour cette recherche." />
      ) : (
        <ul className="space-y-2">
          {lignes.map((v) => (
            <Rangee key={v.id} titre={v.lead_nom || 'Visite'}
              detail={[v.ville, v.date_prevue ? `prévue le ${formatDate(v.date_prevue)}` : 'sans date',
                v.commercial?.nom ? `avec ${v.commercial.nom}` : 'sans technicien'].filter(Boolean).join(' · ')}>
              <p className="mt-1 flex flex-wrap gap-1.5">
                <Badge tone={TONS[v.statut] ?? 'neutral'}>{statut(v.statut)}</Badge>
                {v.en_retard && <Badge tone="danger">En retard</Badge>}
                {v.manquants_count > 0 && <Badge tone="warning">{formatNumber(v.manquants_count)} manquant(s)</Badge>}
              </p>
              <AFaire cle={v.a_faire} />
              <BoutonEcran chemin={v.lien} libelle="Ouvrir la visite" />
            </Rangee>
          ))}
        </ul>
      )}
      <SuiteListe total={d.totaux?.planifiees} affiche={lignes.length} />
      <BoutonEcran chemin={d.lien} libelle="Toutes les visites" />
    </div>
  )
}

function Jalons({ j }) {
  if (!j) return null
  const items = [
    ['En route', j.en_route_le], ['Arrivé', j.arrivee_le], ['Validée', j.validee_le],
  ].filter(([, v]) => v)
  if (!items.length) return null
  return (
    <Ligne etiquette="Déroulé">
      {items.map(([nom, v]) => `${nom} ${formatDateTime(v)}`).join(' · ')}
    </Ligne>
  )
}

/** `fiche_visite` : l'état d'une visite (la même forme après annulation). */
export function CarteFicheVisite({ carte }) {
  const d = carte.donnees ?? {}
  const manquants = d.completude?.manquants ?? []
  const refaire = d.photos?.a_refaire ?? []
  const liens = d.liens ?? {}
  return (
    <div className="min-w-0">
      <Titre>{d.lead?.nom || 'Visite'}{d.lead?.ville ? ` — ${d.lead.ville}` : ''}</Titre>
      <p className="-mt-1 mb-1 flex flex-wrap gap-1.5">
        <Badge tone={TONS[d.statut] ?? 'neutral'}>{d.statut_libelle || statut(d.statut)}</Badge>
        {d.modifiable === false && <Badge tone="neutral">Non modifiable</Badge>}
      </p>
      <Ligne etiquette="Prévue">{d.date_prevue ? formatDate(d.date_prevue) : 'pas de date'}</Ligne>
      {d.date_realisee && <Ligne etiquette="Réalisée">{formatDateTime(d.date_realisee)}</Ligne>}
      <Ligne etiquette="Technicien">{d.commercial?.nom || 'non assigné'}</Ligne>
      <Jalons j={d.jalons} />
      {d.completude && (
        <Ligne etiquette="Relevé">
          {d.completude.complet ? 'complet' : `${formatNumber(d.completude.nb_manquants)} élément(s) manquant(s)`}
        </Ligne>
      )}
      {manquants.length > 0 && (
        <ul className="mt-0.5 list-disc pl-5 text-xs text-muted-foreground">
          {manquants.map((m) => <li key={m} className="break-words">{m}</li>)}
        </ul>
      )}
      {d.photos && (
        <Ligne etiquette="Photos">
          {formatNumber(d.photos.nb)}
          {refaire.length > 0 ? ` · à refaire : ${refaire.map((p) => `${p.slot} (${p.motif})`).join(', ')}` : ''}
        </Ligne>
      )}
      {d.qualification && (
        <div className="mt-1.5 text-xs">
          <p className="break-words">{d.qualification.phrase}</p>
          {d.qualification.conseil && <p className="break-words text-muted-foreground">{d.qualification.conseil}</p>}
          {d.qualification.devis_a_reprendre && <p className="font-medium">Le devis est à reprendre.</p>}
        </div>
      )}
      <Citation titre="Retour du terrain (texte saisi, cité tel quel)" texte={d.retour_terrain} />
      <Citation titre="Mesures du terrain (texte saisi, cité tel quel)" texte={d.mesures_cles} />
      <AFaire cle={d.a_faire} />
      <div className="flex flex-wrap gap-2">
        <BoutonEcran chemin={liens.visite ?? d.lien} libelle="Ouvrir la visite" />
        <BoutonEcran chemin={liens.calage} libelle="Calage" />
        <BoutonEcran chemin={liens.revue} libelle="Revue des visites" />
      </div>
    </div>
  )
}

function JourCharge({ j }) {
  return (
    <li className="break-words text-xs">
      <span className="text-muted-foreground">{formatDate(j.date)} : </span>
      {j.indisponible ? 'indisponible' : `${formatNumber(j.visites)} visite(s) · ${formatNumber(j.interventions)} intervention(s)`}
    </li>
  )
}

/** `charge_equipe` : la charge de chaque personne, jour par jour — jamais un « créneau libre ». */
export function CarteChargeEquipe({ carte }) {
  const d = carte.donnees ?? {}
  const lignes = d.lignes ?? []
  return (
    <div className="min-w-0">
      <Titre>Charge de l’équipe dès le {formatDate(d.du)} ({formatNumber(d.jours)} j)</Titre>
      {d.note && <p className="mb-2 break-words text-xs text-muted-foreground">{d.note}</p>}
      {lignes.length === 0 ? (
        <Vide texte="Personne à afficher." />
      ) : (
        <ul className="space-y-2">
          {lignes.map((p) => (
            <Rangee key={p.id} titre={p.moi ? `${p.nom} (vous)` : p.nom}>
              <ul className="mt-1 space-y-0.5">
                {(p.par_jour ?? []).map((j) => <JourCharge key={j.date} j={j} />)}
              </ul>
            </Rangee>
          ))}
        </ul>
      )}
      <AFaire cle={d.a_faire} />
      <BoutonEcran chemin={d.lien} libelle="Planifier les visites" />
    </div>
  )
}

const CARTES_VISITES = Object.freeze({
  liste_visites: CarteListeVisites,
  fiche_visite: CarteFicheVisite,
  charge_equipe: CarteChargeEquipe,
})
export default CARTES_VISITES
