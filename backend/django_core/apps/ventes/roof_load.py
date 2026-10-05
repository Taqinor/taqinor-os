"""FG253 / CIQ114 — vérification INTERNE de la charge de toiture.

CIQ114 (audit L3 C&I du 03/10/2026) : la capacité admissible du toit est
DÉCLARÉE — document du propriétaire ou du bureau de contrôle, avec sa source
et sa date (entrée ``toit.charge_admissible_kg_m2`` + source du contrat
``etude_ci_preview.json`` ; l'orchestrateur CIQ118 la résout depuis le relevé
de visite validé, sinon depuis la saisie). Les anciennes capacités «
indicatives » par type de toit, la masse forfaitaire du système et le
coefficient de sécurité, tous non sourcés, ont DISPARU : FM Global DS 1-15
(avril 2026, §2.1.5.2) demande de vérifier la capacité EXISTANTE du toit, pas
de la supposer.

* Sans capacité déclarée : aucune comparaison, aucun nombre de capacité ;
  verdict « charge admissible non déclarée — vérification structure requise
  avant le devis final ».
* Masse ajoutée = ``struct_masse_kg_m2`` de la fiche structure retenue +
  masse du module (fiche ``poids_kg`` ÷ aire), OU la masse de lestage du
  calepinage quand elle existe, REÇUE en paramètre (``masse_layout_kg_m2``,
  lue par l'orchestrateur via ``apps.calepinage.services``) — ce module
  n'importe ni le calepinage ni les visites.
* Un coefficient de sécurité ne s'applique que SAISI avec sa source.
* Couverture ``fibrociment`` déclarée ⇒ alerte BLOQUANTE pour le devis
  final : « amiante possible — diagnostic requis avant tout travail ».

Le résultat est INTERNE : jamais imprimé au client, jamais de conclusion
« suffisant » ; le moteur C&I en tire une alerte. Module PUR : aucune
écriture, aucun prix.
"""
from __future__ import annotations

import math

VERDICT_NON_DECLAREE = 'non_declaree'
VERDICT_MASSE_INCONNUE = 'masse_inconnue'
VERDICT_MARGE = 'marge_calculee'
VERDICT_DEPASSEMENT = 'depassement'

MESSAGE_NON_DECLAREE = ('charge admissible non déclarée — vérification '
                        'structure requise avant le devis final')
MESSAGE_AMIANTE = 'amiante possible — diagnostic requis avant tout travail'


class ChargeNonSourcee(ValueError):
    """Une valeur saisie SANS sa source (refus FR nommant le champ)."""

    def __init__(self, champ, message):
        super().__init__(message)
        self.champ = champ
        self.message = message


def _nombre(valeur):
    if valeur is None or valeur == '':
        return None
    try:
        x = float(valeur)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) and x >= 0 else None


def _texte(valeur):
    return valeur.strip() if isinstance(valeur, str) else ''


def verifier_charge_toiture(*, charge_admissible_kg_m2=None,
                            charge_admissible_source=None,
                            struct_masse_kg_m2=None, poids_module_kg=None,
                            aire_module_m2=None, masse_layout_kg_m2=None,
                            couverture=None, coefficient_securite=None,
                            coefficient_source=None):
    """Compare la masse AJOUTÉE à la capacité DÉCLARÉE du toit (interne).

    Raises:
        ChargeNonSourcee: une capacité ou un coefficient saisi sans source.
    """
    alertes = []
    if _texte(couverture).lower() == 'fibrociment':
        alertes.append({'code': 'TOIT_AMIANTE', 'champ': 'toit.couverture',
                        'message': MESSAGE_AMIANTE, 'niveau': 'bloquant',
                        'interne': True})

    capacite = _nombre(charge_admissible_kg_m2)
    source = _texte(charge_admissible_source)
    if capacite is not None and not source:
        raise ChargeNonSourcee(
            'charge_admissible_source',
            'La charge admissible du toit exige sa source (document du '
            'propriétaire ou du bureau de contrôle, date).')
    coefficient = _nombre(coefficient_securite)
    source_coefficient = _texte(coefficient_source)
    if coefficient is not None and not source_coefficient:
        raise ChargeNonSourcee(
            'coefficient_source',
            "Un coefficient de sécurité ne s'applique qu'avec sa source.")

    # Masse ajoutée : le lestage du calepinage d'abord, sinon fiches.
    detail = {'struct_masse_kg_m2': _nombre(struct_masse_kg_m2),
              'module_kg_m2': None, 'masse_layout_kg_m2':
              _nombre(masse_layout_kg_m2)}
    poids = _nombre(poids_module_kg)
    aire = _nombre(aire_module_m2)
    if poids is not None and aire:
        detail['module_kg_m2'] = round(poids / aire, 3)
    if detail['masse_layout_kg_m2'] is not None:
        masse = detail['masse_layout_kg_m2']
        provenance = 'lestage du calepinage'
    elif detail['struct_masse_kg_m2'] is not None and \
            detail['module_kg_m2'] is not None:
        masse = detail['struct_masse_kg_m2'] + detail['module_kg_m2']
        provenance = 'fiche structure + fiche module'
    else:
        masse = None
        provenance = None
    if masse is not None and coefficient is not None:
        masse = masse * coefficient

    resultat = {
        'capacite_kg_m2': capacite,
        'capacite_source': source or None,
        'masse_ajoutee_kg_m2': round(masse, 3) if masse is not None else None,
        'masse_provenance': provenance,
        'detail_masse': detail,
        'coefficient': ({'valeur': coefficient, 'source': source_coefficient}
                        if coefficient is not None else None),
        'marge_kg_m2': None,
        'verdict': None,
        'message': None,
        'alertes': alertes,
        'interne': True,
    }
    if capacite is None:
        resultat['verdict'] = VERDICT_NON_DECLAREE
        resultat['message'] = MESSAGE_NON_DECLAREE
        alertes.append({'code': 'TOIT_CHARGE_NON_DECLAREE',
                        'champ': 'toit.charge_admissible_kg_m2',
                        'message': MESSAGE_NON_DECLAREE, 'niveau': 'alerte',
                        'interne': True})
        return resultat
    if masse is None:
        resultat['verdict'] = VERDICT_MASSE_INCONNUE
        resultat['message'] = (
            'masse du système posé non publiée (fiche structure ou module '
            'incomplète) : comparaison impossible')
        alertes.append({'code': 'TOIT_MASSE_INCONNUE',
                        'champ': 'struct_masse_kg_m2',
                        'message': resultat['message'], 'niveau': 'alerte',
                        'interne': True})
        return resultat
    marge = round(capacite - masse, 3)
    resultat['marge_kg_m2'] = marge
    if marge < 0:
        resultat['verdict'] = VERDICT_DEPASSEMENT
        resultat['message'] = (
            'masse ajoutée %.2f kg/m² au-delà de la charge admissible '
            'déclarée %.2f kg/m² (%s) — renforcement ou étude structure '
            'requis' % (masse, capacite, source))
        alertes.append({'code': 'TOIT_CHARGE_DEPASSEE',
                        'champ': 'toit.charge_admissible_kg_m2',
                        'message': resultat['message'], 'niveau': 'bloquant',
                        'interne': True})
    else:
        resultat['verdict'] = VERDICT_MARGE
        resultat['message'] = (
            'marge calculée %.2f kg/m² sur la charge admissible déclarée '
            '(%s) — à valider par la vérification structure' % (marge, source))
    return resultat
