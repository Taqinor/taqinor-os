import { formatDate } from '../../../../lib/format'
import { EQUIP_STATUT_LABELS } from '../../../sav/equipement'
import { TICKET_STATUS_LABELS } from '../../../sav/ticketStatuses'
import { BoutonLien, Geste, Rangee, SurTotal, Titre, Vide, libelle } from './partsGestion'

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

const CARTES_SAV = Object.freeze({
  parc_client: CarteParcClient,
})
export default CARTES_SAV
