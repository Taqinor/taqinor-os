import { formatDate } from '../../../../lib/format'
import { BoutonLien, Geste, Titre, montant } from './partsGestion'

/* Copilote vague 2 (CRT-B) — cartes du domaine « reporting ». */

// `chiffres_ca` — les TROIS chiffres d'affaires (action `reporting.ca.lire`) : signé, facturé,
// encaissé, tous hors taxes. Chacun garde son libellé ET sa définition venus du serveur ; la carte
// ne les additionne pas, ne les rapporte pas l'un à l'autre et n'en montre aucun sans sa définition.
function CarteChiffresCa({ carte }) {
  const d = carte.donnees ?? {}
  return (
    <div className="min-w-0">
      <Titre>Chiffres d’affaires du {formatDate(d.du)} au {formatDate(d.au)}</Titre>
      <ul className="space-y-2">
        {(d.chiffres ?? []).map((c) => (
          <li key={c.cle} className="min-w-0 rounded-md border border-border bg-background/60 p-2">
            <p className="text-xs font-semibold text-muted-foreground">{c.libelle}</p>
            <p className="text-base font-semibold">{montant(c.montant_ht)}</p>
            <p className="break-words text-xs text-muted-foreground">{c.definition}</p>
          </li>
        ))}
      </ul>
      {d.note && <p className="mt-2 break-words text-xs font-medium">{d.note}</p>}
      <Geste cle={d.a_faire} />
      <BoutonLien lien={d.lien} texte="Ouvrir le rapport commercial" />
    </div>
  )
}

const CARTES_REPORTING = Object.freeze({
  chiffres_ca: CarteChiffresCa,
})
export default CARTES_REPORTING
