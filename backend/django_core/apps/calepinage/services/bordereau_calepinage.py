"""ACAL632 — le bordereau (nomenclature) du calepinage.

Extrait de ``services/electrique.py`` : ``electrique`` ré-importe
``bordereau_du_calepinage`` sous son ancien nom ``_bordereau_du_calepinage``.
"""


def bordereau_du_calepinage(calepinage, conception, noyau, *,
                            equipements=(), branches=(), troncons=(),
                            checklist=None):
    """CALX246/230/232/247/227 — ``{lignes, alertes}``, ou l'omission motivée.

    ``noyau`` est le ``{entree, protections, cables}`` que
    ``cables_du_calepinage`` vient de produire : le bordereau descend du MÊME
    calcul que les câbles publiés. ``None`` (norme absente, aucune chaîne) ⇒
    aucun bordereau, et le motif est déjà publié par les omissions de câbles.

    ``troncons`` (CALX227) — les tronçons mesurés du cheminement. Dès qu'il
    y en a un dont la section est calculable, le MÉTRÉ (une ligne par couple
    côté/section) remplace les deux lignes de câblage forfaitaires : c'est ce
    que le magasinier coupe. Aucun tronçon tracé ⇒ sortie d'aujourd'hui.
    """
    from core.electrique.nomenclature import nomenclature

    from .capacites_coffrets import capacites_des_coffrets
    from .coffrets import coffret_ac, coffrets_dc
    from .electrique import (
        CLE_CORRESPONDANCES, CLE_REGLE_STRUCTURE, _avec_resultat,
        _ligne_bordereau, _references_nomenclature, _regle_structure,
        _reglages_electrique_societe, _valeur_reglee,
        resultat_electrique_complet,
    )
    from .protections import resultat_protections_retenues
    from .troncons import metre_de_cable

    if not noyau:
        return {'lignes': [], 'alertes': []}
    # ACAL159 — le bordereau chiffre la check-list DÉCIDÉE (``checklist``) :
    # un organe écarté n'y figure plus, un organe société y figure — jamais
    # la liste brute de ``concevoir_protections``.
    noyau = dict(noyau, protections=resultat_protections_retenues(
        noyau['protections'], checklist))

    company = getattr(calepinage, 'company', None)
    reglages = _reglages_electrique_societe(calepinage)
    alertes = []

    capacites, alertes_capacite = capacites_des_coffrets(
        company, equipements)
    alertes.extend(alertes_capacite)
    resultat_coffrets = coffrets_dc(conception.chaines, equipements,
                                    capacites=capacites)

    # ``coffret_ac`` lit ``conception.resultat.protections`` (forme du
    # ``ResultatElectrique`` du noyau). ACAL55 — l'adaptateur UNIQUE
    # ``resultat_electrique_complet`` la fournit, bâti sur les organes que
    # ``concevoir_protections`` vient de retenir (les MÊMES objets).
    porteur = _avec_resultat(conception, resultat_electrique_complet(
        conception, noyau=noyau))
    resultat_coffret_ac = coffret_ac(porteur, branches)

    valeur_structure, source_structure = _valeur_reglee(reglages,
                                                        CLE_REGLE_STRUCTURE)
    correspondances, source_correspondances = _valeur_reglee(
        reglages, CLE_CORRESPONDANCES)
    references, alertes_references = _references_nomenclature(
        company, correspondances, source_correspondances)
    alertes.extend(alertes_references)

    resultat = nomenclature(
        noyau['entree'], conception.resultat, noyau['protections'],
        noyau['cables'], resultat_coffrets, resultat_coffret_ac,
        _regle_structure(valeur_structure, source_structure), references,
        metre_de_cable(troncons))
    return {'lignes': [_ligne_bordereau(ligne) for ligne in resultat.lignes],
            'alertes': alertes + list(resultat.alertes)}
