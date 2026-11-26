import { useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'
import { corpsSansBatterie, refusParChamp } from './entreeElectrique'

/* D-ACAL-157 — DÉSIGNER UNE BATTERIE À L'ÉTAPE ÉLECTRIQUE (même famille de composants que la carte de l'onduleur).
   Le catalogue est celui de `GET entree-electrique/` (`candidats.batteries`, sans prix) ; la nature « hybride » de
   l'onduleur désigné est décidée par le SERVEUR (`materiel.onduleur.hybride`), jamais devinée sur un nom. Le sélecteur
   n'est PROPOSÉ que pour un hybride (garde d'écran : le serveur, lui, ne juge pas l'onduleur à l'écriture), « Aucune »
   par défaut ; une batterie que le juge unique de ventes dit incompatible est grisée avec SES raisons (comme une
   fiche incomplète à la carte de l'onduleur). L'écriture remplace l'objet `batterie` entier côté serveur : l'écran renvoie
   l'objet RELU avec le seul changement. Désigner envoie TOUJOURS `packs` (valeur stockée, sinon 1) : stocké, écran et
   dessin comptent la même chose. Retirer la batterie qui ne laisse rien d'autre de saisi envoie `batterie: null` : l'entrée
   retrouve l'état « jamais désignée » (même empreinte de simulation). Un onduleur qui cesse d'être hybride alors qu'une
   batterie est désignée : l'écran le DIT et propose de la retirer, il ne l'efface pas. */

export default function CarteBatterie({ id, entree, lectureSeule, onApplique }) {
  const [enCours, setEnCours] = useState(false)
  const [refus, setRefus] = useState(null)
  const hybride = entree?.materiel?.onduleur?.hybride === true
  const stockee = entree?.entree?.batterie && typeof entree.entree.batterie === 'object' ? entree.entree.batterie : {}
  const candidats = entree?.candidats?.batteries ?? []
  const duDevis = entree?.candidats?.batterie_du_devis ?? null
  const choisie = stockee.produit ?? null
  const packsStockes = Number.isInteger(stockee.packs) && stockee.packs >= 1 ? stockee.packs : null
  // Ce que le dessin compte : les packs stockés, sinon (ancienne entrée) la quantité de la ligne du devis, sinon 1.
  const packs = packsStockes ?? duDevis?.packs ?? 1
  const nom = (produit) => candidats.find((c) => c.id === produit)?.libelle ?? `produit n° ${produit}`

  const enregistrer = (batterie) => {
    setEnCours(true)
    setRefus(null)
    return calepinageApi.calepinages.enregistrerEntreeElectrique(id, { batterie })
      .then(() => onApplique())
      .catch((err) => {
        const parChamp = refusParChamp(err?.response?.data)
        setRefus(parChamp['batterie.produit'] || parChamp.batterie || Object.values(parChamp)[0]
          || 'Batterie non enregistrée : le serveur a refusé ce choix.')
      })
      .finally(() => setEnCours(false))
  }
  const retirer = () => enregistrer(corpsSansBatterie(stockee))
  const choisir = (evenement) => (evenement.target.value === ''
    ? retirer()
    : enregistrer({ ...stockee, produit: Number(evenement.target.value), packs: packsStockes ?? 1 }))
  const regler = (nombre) => enregistrer({ ...stockee, packs: nombre })

  if (!hybride) {
    if (choisie == null) return null
    return (
      <section className="cel-onduleur cel-batterie" data-testid="cal-elec-batterie-inapplicable">
        <p className="cel-libelle">Batterie</p>
        <p role="status" className="cel-refus">
          {`L’onduleur désigné n’est pas un onduleur hybride : la batterie « ${nom(choisie)} » ne s’applique plus.`}
        </p>
        <button type="button" className="cel-lien" disabled={lectureSeule || enCours} onClick={retirer}>
          Retirer la batterie
        </button>
        {refus && <p role="alert" className="cel-refus">{refus}</p>}
      </section>
    )
  }

  return (
    <section className="cel-onduleur cel-batterie" data-testid="cal-elec-batterie">
      <label htmlFor="cel-batterie-choix" className="cel-libelle">Batterie</label>
      <div className="cel-choix" data-vide={choisie == null ? '1' : '0'}>
        <span className="cel-choix-texte" aria-hidden="true">
          <span className="cel-choix-nom">{choisie == null ? 'Aucune' : nom(choisie)}</span>
        </span>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="cel-choix-chevron">
          <path d="M6 9l6 6 6-6" />
        </svg>
        <select id="cel-batterie-choix" value={choisie ?? ''} onChange={choisir}
          disabled={lectureSeule || enCours || (candidats.length === 0 && choisie == null)}>
          <option value="">Aucune</option>
          {candidats.map((c) => {
            const incompatible = c.compatibilite?.statut === 'incompatible'
            return (
              <option key={c.id} value={c.id} disabled={incompatible}>
                {incompatible
                  ? `${c.libelle} — incompatible : ${(c.compatibilite.raisons ?? []).join(' ; ')}`
                  : `${c.libelle}${c.marque ? ` (${c.marque})` : ''}${c.en_stock ? ' · En stock' : ''}`}
              </option>
            )
          })}
        </select>
      </div>
      {choisie == null && duDevis && (
        <p className="cel-choix-ligne" data-testid="cal-elec-batterie-du-devis">
          {`Aucune batterie désignée ici : le schéma montre la batterie du devis (« ${duDevis.designation || `produit n° ${duDevis.produit_id}`} »${duDevis.packs > 1 ? `, ${duDevis.packs} unités` : ''}).`}
        </p>
      )}
      {choisie != null && (
        <div className="cel-choix-ligne" role="group" aria-label="Nombre de batteries">
          <button type="button" className="cel-lien" aria-label="Une batterie de moins" disabled={lectureSeule || enCours || packs <= 1}
            onClick={() => regler(packs - 1)}>−</button>
          <span data-testid="cal-elec-batterie-packs">{`${packs} ${packs > 1 ? 'batteries' : 'batterie'}`}</span>
          <button type="button" className="cel-lien" aria-label="Une batterie de plus" disabled={lectureSeule || enCours}
            onClick={() => regler(packs + 1)}>+</button>
        </div>
      )}
      {candidats.length === 0 && choisie == null && (
        <p className="cel-choix-ligne">Aucune batterie dans le catalogue de la société.</p>
      )}
      {refus && <p role="alert" className="cel-refus">{refus}</p>}
    </section>
  )
}
