"""ACAL857 — « prêt à envoyer ? » : les contrôles de PORTE, sans lever.

La porte unique ``feu_vert.verifier_avant_publication`` (geste ``devis``)
LÈVE à la PREMIÈRE porte fermée : capter son erreur ne dit rien de
l'approbation quand le feu vert manque. Ce module l'APPELLE (aucune règle
recopiée) et traduit son verdict en contrôles de la forme du contrat
``contract_samples/calepinage_pret_a_envoyer.json`` — sans jamais lever,
sans rien écrire : lecture seule.

Codes produits ici (``codes_produits`` du contrat) : ``visite_validee``,
``approbation_a_jour``, ``conception_perimee``, ``simulation_fraiche``,
``kwh_declare``.
"""
from __future__ import annotations

NON_EXIGE = 'Non exigé par votre société'
SANS_LEAD = 'Sans lead : non applicable'
A_LA_CREATION = 'Vérifié à la création du devis'

CIBLE_VISITE = {'etape': 'documents', 'onglet': 'releve', 'champ': ''}
CIBLE_DOCUMENTS = {'etape': 'documents', 'onglet': 'documents', 'champ': ''}
CIBLE_PRODUCTION = {'etape': 'resultats', 'onglet': 'production',
                    'champ': ''}
CIBLE_KWH = {'etape': 'resultats', 'onglet': 'production',
             'champ': 'conso_mensuelle_kwh'}


def _controle(code, libelle, etat, valeur_texte, *, cause='', geste='',
              cible=None):
    return {'code': code, 'libelle': libelle, 'etat': etat,
            'valeur_texte': valeur_texte, 'cause': cause, 'geste': geste,
            'cible': dict(cible or CIBLE_DOCUMENTS), 'seuil_source': None}


def _visite(etat, valeur, **autres):
    return _controle('visite_validee', 'Visite technique validée', etat,
                     valeur, cible=CIBLE_VISITE, **autres)


def _approbation(etat, valeur, **autres):
    return _controle('approbation_a_jour', 'Approbation à jour', etat,
                     valeur, **autres)


def _premier(detail, cle):
    valeurs = detail.get(cle) if isinstance(detail, dict) else None
    return str(valeurs[0]) if valeurs else ''


def _portes(calepinage):
    """Feu vert de la visite + approbation : LA porte, jamais recopiée."""
    from rest_framework.exceptions import ValidationError

    from .approbation import approbation_exigee
    from .feu_vert import (
        GESTE_DEVIS, _lead_id_de_reference, _option_active,
        verifier_avant_publication,
    )

    lead_id = _lead_id_de_reference(calepinage)
    if lead_id is None and getattr(calepinage, 'devis', None) is None:
        return [_visite('info', SANS_LEAD), _approbation('info', SANS_LEAD)]
    company = getattr(calepinage, 'company', None)
    option = _option_active(company)
    try:
        verifier_avant_publication(calepinage, geste=GESTE_DEVIS)
        refus = {}
    except ValidationError as erreur:
        refus = erreur.detail if isinstance(erreur.detail, dict) else {}
    if 'feu_vert' in refus:
        return [
            _visite('bloquant', 'Non validée',
                    cause=_premier(refus, 'feu_vert'),
                    geste='Faire valider la visite'),
            _approbation('info', "Non évaluée tant que la visite n'est pas "
                                 'validée')]
    if not option:
        visite = _visite('ok', NON_EXIGE)
    elif lead_id is None:
        visite = _visite('info', SANS_LEAD)
    else:
        visite = _visite('ok', 'Validée')
    if 'approbation' in refus:
        approbation = _approbation(
            'bloquant', 'Non approuvée ou périmée',
            cause=_premier(refus, 'approbation'),
            geste='Demander l’approbation de la conception')
    elif not approbation_exigee(company):
        approbation = _approbation('ok', NON_EXIGE)
    else:
        approbation = _approbation('ok', 'À jour')
    return [visite, approbation]


def _simulation(calepinage):
    from .comparaison import (
        _hash_de_simulation, simulation_perimee_du_calepinage,
    )

    libelle = 'Simulation à jour'
    if not _hash_de_simulation(getattr(calepinage, 'resultat', None)):
        return _controle('simulation_fraiche', libelle, 'a_regler',
                         'Jamais lancée', geste='Lancer la simulation',
                         cible=CIBLE_PRODUCTION)
    if simulation_perimee_du_calepinage(calepinage):
        return _controle(
            'simulation_fraiche', libelle, 'a_regler',
            'Lancée avant la dernière modification',
            cause='La production affichée ne correspond plus à la '
                  'conception.',
            geste='Relancer la simulation', cible=CIBLE_PRODUCTION)
    return _controle('simulation_fraiche', libelle, 'ok', 'À jour',
                     cible=CIBLE_PRODUCTION)


def _devis_lie(calepinage):
    libelle_conception = 'Devis à jour de la conception'
    libelle_kwh = 'Consommation déclarée cohérente avec les factures'
    devis = getattr(calepinage, 'devis', None)
    if devis is None:
        return [_controle('conception_perimee', libelle_conception, 'info',
                          A_LA_CREATION),
                _controle('kwh_declare', libelle_kwh, 'info', A_LA_CREATION,
                          cible=CIBLE_KWH)]
    from apps.ventes.selectors_calepinage import refus_kwh_declare_du_devis

    from ..serializers import peremption_du_calepinage

    if peremption_du_calepinage(devis, calepinage).get('layout_stale'):
        conception = _controle(
            'conception_perimee', libelle_conception, 'a_regler',
            'Le devis ne suit plus la conception',
            cause='La conception a changé depuis la dernière mise à jour '
                  'du devis.',
            geste='Resynchroniser le devis')
    else:
        conception = _controle('conception_perimee', libelle_conception,
                               'ok', 'À jour')
    refus = refus_kwh_declare_du_devis(devis)
    if refus is not None:
        kwh = _controle('kwh_declare', libelle_kwh, 'bloquant',
                        'Contredite par les factures',
                        cause=refus.get('detail') or '',
                        geste='Corriger la consommation du lead',
                        cible=CIBLE_KWH)
    else:
        kwh = _controle('kwh_declare', libelle_kwh, 'ok', 'Cohérente',
                        cible=CIBLE_KWH)
    return [conception, kwh]


def controles_de_porte(calepinage):
    """Les cinq contrôles de porte, dans l'ordre du contrat. Ne lève pas."""
    return [*_portes(calepinage), _simulation(calepinage),
            *_devis_lie(calepinage)]
