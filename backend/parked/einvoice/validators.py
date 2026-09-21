"""NTMAR8 — Validateur pré-transmission (contrôles DGI durs).

``controler_avant_transmission(fe) -> list[str]`` : liste d'anomalies
BLOQUANTES (liste vide = conforme). RÉUTILISE le validateur art. 145 CGI
existant de ``ventes`` (N105, ``apps.ventes.dgi.dgi_validator``) via import de
module (jamais un import de ``apps.ventes.models``) — n'introduit AUCUNE
nouvelle règle de conformité dupliquée : ICE/IF/RC vendeur, ICE client B2B,
TVA par ligne, cohérence HT+TVA=TTC y sont déjà couverts.

Ajoute par-dessus les contrôles SPÉCIFIQUES à la transmission e-invoice :
présence de la facture source, hash calculé (XML effectivement généré).

NOTE — le contrôle ICE vendeur via ``NTMAR1`` (checksum modulo dédié) n'est
PAS branché ici : NTMAR1 vit dans ``apps.parametres`` et reste hors périmètre
de ce lot (revient au run plateforme) ; ``validate_dgi_conformity`` couvre déjà
la présence de l'ICE (format non vérifié par checksum tant que NTMAR1
n'existe pas).
"""


def controler_avant_transmission(fe):
    """Renvoie la liste des anomalies bloquantes avant transmission Simpl.

    ``fe`` : une ``FactureElectronique``. Liste vide = conforme."""
    anomalies = []

    if not fe.hash_contenu or not fe.xml_key:
        anomalies.append(
            "Aucun XML généré pour cette e-facture (statut incomplet).")

    from apps.ventes.dgi import validate_dgi_conformity
    from apps.ventes.selectors import get_facture_scoped

    facture = get_facture_scoped(fe.company, fe.facture_id)
    if facture is None:
        anomalies.append(
            "Facture source introuvable — impossible de vérifier la conformité.")
        return anomalies

    anomalies.extend(validate_dgi_conformity(facture))
    return anomalies
