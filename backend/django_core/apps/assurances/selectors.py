"""Selectors du registre des assurances & sinistres d'entreprise (NTASS).

Point d'entrée des LECTURES cross-app entrantes (aucune autre app n'a besoin
de lire ``assurances`` pour l'instant, ce module reste donc côté LECTEUR :
il importe PARESSEUSEMENT les selectors des autres apps — jamais leurs
``models`` — pour résoudre des libellés d'actifs transverses (NTASS7/20)."""
from .models import ActifCouvert


def resoudre_libelle_actif(company, type_actif, actif_ref):
    """Résout le libellé lisible d'un actif transverse couvert (NTASS7).

    ``actif_ref`` est une string-FK (jamais une vraie FK) : la résolution
    passe TOUJOURS par le ``selectors`` de l'app propriétaire, import
    paresseux + ``try/except`` défensif — une app absente (futur NTPRO pour
    SITE/EQUIPEMENT) ou une lecture qui échoue renvoie simplement ``None``
    (l'appelant retombe alors sur le snapshot ``actif_libelle`` stocké)."""
    if actif_ref is None:
        return None
    if type_actif == ActifCouvert.TypeActif.VEHICULE:
        try:
            from apps.flotte import selectors as flotte_selectors
            assurance = flotte_selectors.assurances_vehicule_de_la_societe(
                company, actif_flotte_id=actif_ref).select_related(
                    'actif_flotte').first()
            if assurance and assurance.actif_flotte_id:
                return assurance.actif_flotte.label
        except Exception:  # noqa: BLE001 - dégradation gracieuse défensive
            return None
        return None
    # SITE/EQUIPEMENT/AUTRE : pas encore de selector propriétaire (futur
    # NTPRO) — snapshot uniquement, résolu par l'appelant.
    return None


def actifs_couverts_de_la_police(police):
    """Liste des ``ActifCouvert`` d'une police, avec libellé résolu à la volée
    (NTASS7). Renvoie une liste de dicts (pas un queryset — le libellé résolu
    n'est pas une colonne DB)."""
    resultats = []
    for actif in police.actifs_couverts.all():
        libelle_resolu = resoudre_libelle_actif(
            police.company, actif.type_actif, actif.actif_ref)
        resultats.append({
            'id': actif.id,
            'type_actif': actif.type_actif,
            'actif_ref': actif.actif_ref,
            'actif_libelle': libelle_resolu or actif.actif_libelle,
            'date_ajout': actif.date_ajout,
        })
    return resultats
