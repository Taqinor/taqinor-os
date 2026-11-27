"""CIQ118 — Aperçu serveur C&I : POST /ventes/etude-ci/preview/.

D-CIQ-0 : UN moteur serveur C&I sert l'écran, le devis automatique, le PDF et
/proposition. Cette vue n'est qu'une porte HTTP sur
:func:`apps.ventes.domain.etude_ci.etudier_ci` ; elle rend EXACTEMENT la forme
``exemple`` du contrat ``contract_samples/etude_ci_preview.json``.

AUCUNE ÉCRITURE (patron ``etude_horaire_view.py`` / ``etude_pompage_view.py``
: fonction ``@api_view``, jamais une action de ViewSet). Company-scopé : la
société vient TOUJOURS de ``request.user`` ; ``devis`` / ``lead`` du corps sont
résolus DANS la société de l'appelant, un identifiant étranger est ignoré.
"""
from __future__ import annotations

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from apps.roles.permissions import DroitDeLaGrille
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin

from .domain.suppositions_ci import alertes_pour_la_commerciale

#: Identifiants de contexte retirés du corps avant le calcul. ``lignes`` (T4-X6-008) : les
#: lignes de l'écran d'édition — l'étude décrit alors le système que CES lignes vendent.
CLES_CONTEXTE = ('devis', 'lead', 'lignes')

#: Forme de réponse = clés de ``exemple`` du contrat
#: ``contract_samples/etude_ci_preview.json`` (PACT7 : jamais un objet vide).
EtudeCiPreviewResponse = inline_serializer('EtudeCiPreviewResponse', {
    'entrees_resolues': serializers.JSONField(),
    'niveau_donnees': serializers.CharField(allow_null=True),
    'sous_reserve_visite': serializers.JSONField(),
    'profil_charge': serializers.JSONField(),
    'production': serializers.JSONField(),
    'taille': serializers.JSONField(),
    'bilan': serializers.JSONField(),
    'economie_ci': serializers.JSONField(),
    'composition': serializers.JSONField(),
    'regime_8221_suggere': serializers.JSONField(),
    'alertes': serializers.ListField(child=serializers.JSONField()),
    'hypotheses': serializers.ListField(child=serializers.JSONField()),
    'methode': serializers.CharField(),
    'version_moteur': serializers.CharField(),
    # AMOT104 — la feuille de consommation que le moteur a RETENUE (null sans conso).
    'feuille_consommation_retenue': serializers.CharField(allow_null=True),
    # CORC1 (27/10/2026) — l'écran vendeur sait AVANT le clic si le devis
    # automatique passera, et pourquoi (même refus que le bouton).
    'devis_auto': serializers.JSONField(),
    # Fondateur 26/10/2026 — ``null`` quand l'option « avec batterie » n'est
    # pas composée (forme ``option_avec`` du contrat).
    'option_avec': serializers.JSONField(allow_null=True),
})


def _devis_de_la_societe(company, devis_id, user=None):
    """Le devis ``devis_id`` de la société, borné à la portée équipe de
    ``user`` (ADEV21 — mêmes ``owner_fields`` que ``DevisViewSet``)."""
    if not devis_id or company is None:
        return None
    from .models import Devis
    qs = Devis.objects.filter(company=company)
    if user is not None:
        from core.scoping import scope_queryset
        qs = scope_queryset(qs, user, ['created_by'])
    try:
        return qs.filter(pk=int(devis_id)).first()
    except (TypeError, ValueError):
        return None


class _DevisALaSaisie:
    """T4-X6-009 — le devis que lit l'aperçu quand l'écran ENVOIE sa consommation : le bloc
    ``consommation`` du corps remplace celui rangé (c'est lui que l'enregistrement rangera à
    sa place) ; un champ vidé à l'écran ne laisse plus passer les kWh rangés avant devant
    les factures tapées. Tout le reste est le devis."""

    def __init__(self, devis, consommation):
        self.__dict__['_devis'] = devis
        self.__dict__['etude_params'] = dict(devis.etude_params or {}, consommation=consommation)

    def __getattr__(self, nom):
        return getattr(self.__dict__['_devis'], nom)

    def __setattr__(self, nom, valeur):
        setattr(self.__dict__['_devis'], nom, valeur)  # mémos de lecture du devis (toit, plafond)


def _devis_a_la_saisie(devis, corps):
    """``devis`` lu avec la consommation de l'écran (:class:`_DevisALaSaisie`), ou tel quel."""
    consommation = corps.get('consommation')
    if devis is None or not isinstance(consommation, dict):
        return devis
    return _DevisALaSaisie(devis, consommation)


def _lead_de_la_societe(company, lead_id):
    if not lead_id or company is None:
        return None
    from apps.crm.selectors import get_company_lead
    try:
        return get_company_lead(company, int(lead_id))
    except (TypeError, ValueError):
        return None


@extend_schema(
    summary="Aperçu serveur de l'étude commercial / industriel (CIQ118, aucune écriture)",
    description=("Profil déclaré heure par heure, production PVGIS, taille par la "
                 "règle marginale, bilan, économie, composition — forme du contrat "
                 "etude_ci_preview.json. Société = celle de l'appelant."),
    request=OpenApiTypes.OBJECT, responses={200: EtudeCiPreviewResponse},
)
@api_view(['POST'])
@permission_classes([IsAnyRole])
def etude_ci_preview(request):
    """POST /ventes/etude-ci/preview/ — calcule, n'écrit rien."""
    from .domain.etude_ci import CLE_TAILLE_CREATION, devis_auto_possible, etudier_ci
    from .domain.etude_ci_batterie import CLE as CLE_OPTION_AVEC

    # CI #997 — corps non objet (``[null, null]``) : 400, plus un calcul
    # « omis » rendu 200 sur un corps hors schéma.
    if not isinstance(request.data, dict):
        from rest_framework.exceptions import ParseError
        raise ParseError('Corps JSON objet attendu.')
    corps = request.data
    company = getattr(request.user, 'company', None)
    devis = _devis_de_la_societe(company, corps.get('devis'), request.user)
    if corps.get('devis') not in (None, '') and devis is None:
        # ADEV21 — un devis désigné mais hors société ou hors portée : 404,
        # jamais un calcul silencieux sur ses données.
        # (exception, pas un dict : la forme 200 du contrat reste seule.)
        from rest_framework.exceptions import NotFound
        raise NotFound('Devis introuvable.')
    lead = _lead_de_la_societe(company, corps.get('lead'))
    entrees = {k: v for k, v in corps.items() if k not in CLES_CONTEXTE}
    vu = _devis_a_la_saisie(devis, corps)
    etude = None
    if devis is not None and isinstance(corps.get('lignes'), list):
        # T4-X6-008 — le calcul RANGÉ du devis (celui que le PDF lit) sur les lignes de l'écran.
        from .conception.etudes_lignes import etude_ci_de_l_ecran
        etude = etude_ci_de_l_ecran(devis, corps['lignes'], entrees, vu=vu)
    if etude is None:
        # ACAL1226 (revue-7) — un brouillon né du balayage garde son verdict de
        # création (taille « calculée à la création », pas « saisie ») ; un devis
        # à naître n'en a pas (None).
        etude = etudier_ci(company, entrees, devis=vu, lead=lead, verdict_creation=(
            getattr(vu or devis, 'etude_params', None) or {}).get(CLE_TAILLE_CREATION))
    return Response({
        'entrees_resolues': etude['entrees_resolues'],
        'niveau_donnees': etude['niveau_donnees'],
        'sous_reserve_visite': etude['sous_reserve_visite'],
        'profil_charge': etude['profil_charge'],
        'production': etude['production'],
        'taille': etude['taille'],
        'bilan': etude['bilan'],
        'economie_ci': etude['economie_ci'],
        'composition': etude['composition'],
        'regime_8221_suggere': etude['regime_8221_suggere'],
        'alertes': alertes_pour_la_commerciale(etude),
        'hypotheses': etude['hypotheses'],
        'methode': etude['methode'],
        'version_moteur': etude['version_moteur'],
        'feuille_consommation_retenue': etude.get('feuille_consommation_retenue'),
        'devis_auto': devis_auto_possible(etude),
        'option_avec': etude.get(CLE_OPTION_AVEC) or None,
    })


#: CORC2 — réponse de ``etude-ci/reviser-apres-visite/`` (contrat
#: ``contract_samples/devis_revise_visite.json``).
DevisReviseVisiteResponse = inline_serializer('DevisReviseVisiteResponse', {
    'devis_id': serializers.IntegerField(),
    'reference': serializers.CharField(),
    'version': serializers.IntegerField(),
    'cree': serializers.BooleanField(),
    'lignes_changees': serializers.ListField(child=serializers.JSONField()),
    'mesures_utilisees': serializers.ListField(child=serializers.JSONField()),
    'alertes': serializers.ListField(child=serializers.JSONField()),
})


@extend_schema(
    summary="Devis C&I révisé après la visite technique (CORC2)",
    description=("Recompose les lignes du devis C&I avec les mesures de la visite "
                 "C&I validée : brouillon recomposé sur place, sinon V+1 (révision) "
                 "recomposée. Aucun statut écrit. Contrat devis_revise_visite.json."),
    request=inline_serializer('DevisReviseVisiteRequest', {
        'devis': serializers.IntegerField()}),
    responses={200: DevisReviseVisiteResponse,
               404: inline_serializer('DevisReviseVisiteIntrouvable', {
                   'detail': serializers.CharField()}),
               409: inline_serializer('DevisReviseVisiteRefus', {
                   'detail': serializers.CharField(),
                   'field': serializers.CharField()})},
)
@api_view(['POST'])
@permission_classes([IsResponsableOrAdmin])
def devis_reviser_apres_visite(request):
    """POST /ventes/etude-ci/reviser-apres-visite/ — {devis} → devis révisé."""
    from rest_framework.exceptions import NotFound, ParseError

    from core.conflit_etat import ConflitEtat

    from .domain.revision import RevisionError
    from .domain.revision_visite_ci import (RevisionVisiteError,
                                            reviser_devis_apres_visite)

    if not isinstance(request.data, dict):
        raise ParseError('Corps JSON objet attendu.')
    company = getattr(request.user, 'company', None)
    devis = _devis_de_la_societe(company, request.data.get('devis'), request.user)
    if devis is None:
        raise NotFound('Devis introuvable.')
    try:
        resultat = reviser_devis_apres_visite(devis, user=request.user)
    except RevisionVisiteError as exc:
        raise ConflitEtat({'detail': exc.message, 'field': exc.champ})
    except RevisionError as exc:
        raise ConflitEtat({'detail': exc.message, 'field': 'devis'})
    cible = resultat['devis']
    return Response({
        'devis_id': cible.id, 'reference': cible.reference,
        'version': cible.version, 'cree': resultat['cree'],
        'lignes_changees': resultat['lignes_changees'],
        'mesures_utilisees': resultat['mesures_utilisees'],
        'alertes': resultat['alertes'],
    })


#: D-HYB-4 — réponse de ``etude-ci/recomposer-batteries/`` (contrat
#: ``contract_samples/devis_recomposer_batteries.json``).
DevisRecomposerBatteriesResponse = inline_serializer('DevisRecomposerBatteriesResponse', {
    'devis_id': serializers.IntegerField(),
    'nb_batteries': serializers.IntegerField(),
    'quantite_recommandee': serializers.IntegerField(),
    'nb_panneaux_avec': serializers.IntegerField(allow_null=True),
    'kwc_avec': serializers.FloatField(allow_null=True),
    'lignes_changees': serializers.BooleanField(),
    'onduleur_extension': serializers.JSONField(allow_null=True),
    'alertes': serializers.ListField(child=serializers.JSONField()),
})


@extend_schema(
    summary="Devis C&I brouillon : nombre de batteries choisi (D-HYB-4)",
    description=("1 ≤ N ≤ banque calculée : panneaux redimensionnés pour N, onduleur "
                 "hybride gardé pour la banque maximale ; lignes de l'option « avec » "
                 "recomposées, option « sans » inchangée. Brouillon seulement, aucun "
                 "statut écrit. Contrat devis_recomposer_batteries.json."),
    request=inline_serializer('DevisRecomposerBatteriesRequest', {
        'devis': serializers.IntegerField(), 'nb_batteries': serializers.IntegerField()}),
    responses={200: DevisRecomposerBatteriesResponse,
               400: inline_serializer('DevisRecomposerBatteriesSaisie', {
                   'detail': serializers.CharField(), 'field': serializers.CharField()}),
               404: inline_serializer('DevisRecomposerBatteriesIntrouvable', {
                   'detail': serializers.CharField()}),
               409: inline_serializer('DevisRecomposerBatteriesRefus', {
                   'detail': serializers.CharField(), 'field': serializers.CharField()})},
)
@api_view(['POST'])
@permission_classes([IsResponsableOrAdmin, DroitDeLaGrille('ventes_modifier')])
def devis_recomposer_batteries(request):
    """POST /ventes/etude-ci/recomposer-batteries/ — {devis, nb_batteries}."""
    from rest_framework.exceptions import NotFound, ParseError

    from core.conflit_etat import ConflitEtat

    from .domain.recomposition_batteries_ci import (RecompositionBatteriesError,
                                                    recomposer_batteries)

    if not isinstance(request.data, dict):
        raise ParseError('Corps JSON objet attendu.')
    company = getattr(request.user, 'company', None)
    devis = _devis_de_la_societe(company, request.data.get('devis'), request.user)
    if devis is None:
        raise NotFound('Devis introuvable.')
    try:
        resultat = recomposer_batteries(devis, request.data.get('nb_batteries'),
                                        user=request.user)
    except RecompositionBatteriesError as exc:
        if exc.statut_http == 400:
            raise SaisieBatteriesRefusee({'detail': exc.message, 'field': exc.champ})
        raise ConflitEtat({'detail': exc.message, 'field': exc.champ})
    return Response(resultat)


class SaisieBatteriesRefusee(APIException):
    """400 ``{detail, field}`` — ``nb_batteries`` absent, non entier, < 1 ou
    au-delà de la banque calculée (le corps, pas l'état du devis : 409)."""

    status_code = 400
    default_detail = 'Nombre de batteries invalide.'
    default_code = 'nb_batteries_invalide'
