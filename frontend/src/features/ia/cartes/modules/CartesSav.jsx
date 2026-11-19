import { formatDate, formatDateTime, formatNumber } from '../../../../lib/format'
import { EQUIP_STATUT_LABELS } from '../../../sav/equipement'
import { TICKET_PRIORITE_LABELS, TICKET_STATUS_LABELS } from '../../../sav/ticketStatuses'
import { BoutonLien, Citation, Geste, Rangee, SurTotal, Titre, Vide, libelle } from './partsGestion'

/* Copilote vague 2 (CRT-B) — cartes du domaine « après-vente ». Tout vient du serveur ;
   la garantie affichée est la garantie EFFECTIVE qu'il a calculée. */

// `parc_client` — le parc installé d'un client (action `sav.parc.chercher`) : retrouver le bon
// équipement avant d'ouvrir un ticket. Plusieurs clients : on les montre tous, l'assistant demande.
function EquipementParc({ e }) {
  return (
    <li className="min-w-0 break-words text-xs">
      <span className="font-medium">{e.produit}</span>
      {e.marque ? ` · ${e.marque}` : ''}
      <span className="block text-muted-foreground">
        {[e.numero_serie, libelle(EQUIP_STATUT_LABELS, e.statut),
          e.sous_garantie ? `sous garantie jusqu’au ${formatDate(e.fin_garantie_effective)}` : 'hors garantie']
          .filter(Boolean).join(' · ')}
      </span>
    </li>
  )
}

function ClientParc({ c }) {
  return (
    <Rangee titre={c.nom} detail={c.telephone || ''}>
      {c.chantiers?.length > 0 && (
        <p className="mt-1 break-words text-xs">Chantiers : {c.chantiers.map((x) => x.reference).join(', ')}</p>
      )}
      {c.contrat_actif && (
        <p className="mt-1 text-xs">Contrat de maintenance actif jusqu’au {formatDate(c.contrat_actif.fin)}</p>
      )}
      {c.equipements?.length > 0 ? (
        <ul className="mt-1 space-y-1">{c.equipements.map((e) => <EquipementParc key={e.equipement_id} e={e} />)}</ul>
      ) : (
        <p className="mt-1 text-xs text-muted-foreground">Aucun équipement installé enregistré.</p>
      )}
      {c.tickets_ouverts?.length > 0 && (
        <div className="mt-1.5">
          <p className="text-xs font-semibold">Tickets ouverts</p>
          {c.tickets_ouverts.map((t) => (
            <div key={t.ticket_id}>
              <p className="break-words text-xs">
                {t.reference} · {libelle(TICKET_STATUS_LABELS, t.statut)}
              </p>
              <BoutonLien lien={t.lien} texte={`Ouvrir ${t.reference}`} />
            </div>
          ))}
        </div>
      )}
      <Geste cle={c.a_faire} />
      <BoutonLien lien={c.lien} texte="Ouvrir la fiche client" />
    </Rangee>
  )
}

function CarteParcClient({ carte }) {
  const d = carte.donnees ?? {}
  const clients = d.clients ?? []
  if (!clients.length) return <Vide texte="Aucun client trouvé : la création d’un client se fait à l’écran." />
  return (
    <div className="min-w-0">
      <Titre>Parc client ({d.total ?? clients.length})</Titre>
      <ul className="space-y-2">{clients.map((c) => <ClientParc key={c.client_id} c={c} />)}</ul>
      <SurTotal affiches={clients.length} total={d.total} />
    </div>
  )
}

const PRIORITES = TICKET_PRIORITE_LABELS
const TYPES_TICKET = Object.freeze({ correctif: 'Correctif', preventif: 'Préventif' })
const GENRES_ACTIVITE = Object.freeze({
  creation: 'Création', modification: 'Modification', note: 'Note', email: 'E-mail', whatsapp: 'WhatsApp', appel: 'Appel',
})
const OPERATIONS_PIECE = Object.freeze({ pose: 'Posée', retrait: 'Retirée', recyclage: 'Recyclée' })

// `liste_tickets` — la file SAV (action `sav.tickets.chercher`), en retard de SLA d'abord :
// l'ordre est celui du serveur. Les textes du client n'y figurent pas.
function CarteListeTickets({ carte }) {
  const d = carte.donnees ?? {}
  const lignes = d.lignes ?? []
  if (!lignes.length) return <Vide texte="Aucun ticket ne correspond." />
  return (
    <div className="min-w-0">
      <Titre>Tickets ({d.total ?? lignes.length})</Titre>
      <ul className="space-y-2">
        {lignes.map((t) => (
          <Rangee key={t.ticket_id} titre={`${t.reference} — ${t.client_nom}`}
            detail={[t.equipement, libelle(TICKET_STATUS_LABELS, t.statut),
              `priorité ${libelle(PRIORITES, t.priorite).toLowerCase()}`,
              t.sla_due_at ? `échéance ${formatDate(t.sla_due_at)}` : '',
              t.sous_garantie ? 'sous garantie' : ''].filter(Boolean).join(' · ')}>
            {t.en_retard_sla && <p className="text-xs font-medium text-destructive">En retard sur l’échéance de service.</p>}
            <Geste cle={t.a_faire} />
            <BoutonLien lien={t.lien} texte="Ouvrir le ticket" />
          </Rangee>
        ))}
      </ul>
      <SurTotal affiches={lignes.length} total={d.total} />
      <BoutonLien lien={d.lien} texte="Tickets à traiter" />
    </div>
  )
}

// `fiche_ticket` — la fiche compacte d'un ticket (action `sav.ticket.fiche`). La description et
// les textes d'activité sont écrits par des TIERS (client, terrain) : texte brut, cité, coupé.
function CarteFicheTicket({ carte }) {
  const d = carte.donnees ?? {}
  const eq = d.equipement
  return (
    <div className="min-w-0">
      <Titre>{d.reference} — {d.statut_libelle || libelle(TICKET_STATUS_LABELS, d.statut)}</Titre>
      <p className="break-words text-xs text-muted-foreground">
        {[d.client?.nom, `priorité ${libelle(PRIORITES, d.priorite).toLowerCase()}`, libelle(TYPES_TICKET, d.type),
          d.installation?.reference, d.technicien ? `technicien ${d.technicien}` : ''].filter(Boolean).join(' · ')}
      </p>
      {eq && (
        <p className="mt-1 break-words text-xs">
          {eq.produit} · {eq.numero_serie} · {eq.sous_garantie
            ? `sous garantie jusqu’au ${formatDate(eq.fin_garantie_effective)}` : 'hors garantie'}
        </p>
      )}
      {d.sla && (
        <p className={`mt-1 text-xs ${d.sla.en_retard ? 'font-medium text-destructive' : ''}`}>
          Échéance {formatDate(d.sla.due_at)}{d.sla.en_retard ? ' — en retard' : ''}
        </p>
      )}
      {d.description && (
        <div className="mt-2">
          <p className="text-xs font-semibold">Description du client</p>
          <Citation texte={d.description} />
        </div>
      )}
      {d.pieces?.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-xs">
          {d.pieces.map((p, i) => (
            <li key={i} className="break-words">
              {[libelle(OPERATIONS_PIECE, p.operation) || '', p.produit, `× ${formatNumber(p.quantite)}`].filter(Boolean).join(' ')}
            </li>
          ))}
        </ul>
      )}
      {d.activites?.length > 0 && (
        <ul className="mt-2 space-y-1.5">
          {d.activites.map((a, i) => (
            <li key={i} className="min-w-0 text-xs">
              <span className="text-muted-foreground">
                {[libelle(GENRES_ACTIVITE, a.type), formatDateTime(a.le), a.par].filter(Boolean).join(' · ')}
              </span>
              <Citation texte={a.texte} />
            </li>
          ))}
        </ul>
      )}
      <Geste cle={d.a_faire} />
      <BoutonLien lien={d.lien} texte="Ouvrir le ticket" />
    </div>
  )
}

const CARTES_SAV = Object.freeze({
  parc_client: CarteParcClient,
  liste_tickets: CarteListeTickets,
  fiche_ticket: CarteFicheTicket,
})
export default CARTES_SAV
