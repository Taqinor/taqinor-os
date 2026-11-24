// Une carte d'acte dans le parcours « Contrats » : titre, référence, statut EN
// MOTS, avertissements du serveur et les gestes que le serveur autorise.
import { Badge, Button } from '../../../ui'
import {
  actionPrincipale, LIBELLE_ACTION, libelleStatut, tonStatut,
} from './outils'

export default function ActeEtape({
  acte, peutEcrire, occupe, erreur, onAction, enVariante = false,
}) {
  const annule = acte.statut === 'annule'
  const gestes = [
    ['apercu', true, 'outline'],
    ['modifier', peutEcrire && acte.peut_modifier, 'outline'],
    ['emettre', peutEcrire && acte.peut_emettre, actionPrincipale(acte, peutEcrire) === 'emettre' ? 'default' : 'outline'],
    ['signer', peutEcrire && acte.peut_signer, actionPrincipale(acte, peutEcrire) === 'signer' ? 'default' : 'outline'],
    ['papier', peutEcrire && acte.peut_signer, 'outline'],
    ['rouvrir', peutEcrire && acte.peut_rouvrir, 'outline'],
    ['telecharger', true, 'ghost'],
  ].filter(([, visible]) => visible)

  return (
    <div
      className="contrats-acte"
      data-statut={acte.statut}
      data-ecarte={acte.ecarte ? 'oui' : 'non'}
      data-variante={enVariante ? 'oui' : 'non'}
    >
      <div className="contrats-acte__tete">
        <h4 className="contrats-acte__titre">{acte.titre}</h4>
        <span className="contrats-acte__ref">{acte.reference}</span>
      </div>

      <div className="contrats-acte__etat">
        <Badge tone={tonStatut(acte)}>{libelleStatut(acte)}</Badge>
        {acte.personnalise && <Badge tone="outline">Texte personnalisé</Badge>}
        {acte.ecarte && <Badge tone="outline">Écartée : l’autre version est retenue</Badge>}
        {acte.version > 1 && <span className="contrats-acte__version">Version {acte.version}</span>}
      </div>

      {acte.avertissements?.length > 0 && (
        <ul className="contrats-acte__avertissements">
          {acte.avertissements.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ul>
      )}

      {erreur && (
        <p className="contrats-acte__erreur" role="alert">{erreur}</p>
      )}

      {!annule && (
        <div className="contrats-acte__gestes">
          {gestes.map(([nom, , variante]) => (
            <Button
              key={nom}
              size="sm"
              variant={variante}
              className="contrats-acte__bouton"
              disabled={occupe}
              onClick={() => onAction(nom, acte)}
            >
              {LIBELLE_ACTION[nom]}
            </Button>
          ))}
        </div>
      )}
    </div>
  )
}
