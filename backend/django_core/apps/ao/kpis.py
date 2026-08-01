"""AOF166 — KPI d'appels d'offres + tableau de bord des marchés.

**Supersede NTMAR27** (``docs/plans/PLAN_FINANCE.md``) et en REPREND
NOMINATIVEMENT le nom d'endpoint (``GET /api/django/ao/tableau-marches/``), son
selector (``apps.ao.selectors.tableau_marches(company)``) et ses deux KPI
propres (cautions immobilisées, marchés en exécution). Sans cette reprise,
l'ERP finirait avec DEUX tableaux de bord d'appels d'offres concurrents, ce qui
est pire que zéro : deux chiffres différents pour la même question.

Trois règles gravées dans ce module
-----------------------------------
1. **Le taux de réussite est CALCULÉ, jamais saisi.** Il se dérive de
   ``ResultatAO`` (gagnés / (gagnés + perdus)) via ``services.taux_reussite_ao``
   — un champ « taux de réussite » saisissable serait une opinion, pas une
   mesure.
2. **UN SEUL appel agrégé sert le tableau de bord.** Le front ne compose pas
   six requêtes : ``tableau_marches(company)`` rend le tout.
3. **Aucun coût, aucune marge, aucun ``prix_achat``.** Ce tableau est visible
   par le palier ``ao_voir`` : l'économie de l'AO vit derrière
   ``ao_rentabilite_voir``, dans des endpoints SÉPARÉS (AOF2). Les seuls
   montants publiés ici sont ceux de NOTRE OFFRE et des cautions immobilisées —
   des engagements, jamais des coûts de revient. Un test d'introspection
   échoue si une clé de coût apparaît.
"""
from __future__ import annotations

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from core.permissions import _user_has_or_legacy

from .permissions import AO_VOIR

__all__ = ['kpi_ao', 'TableauMarchesPermission', 'tableau_marches_view']

#: Préfixes de clés INTERDITS dans toute sortie de ce module (garde de fuite).
CLES_INTERDITES = (
    'cout', 'coût', 'prix_achat', 'marge', 'benefice', 'bénéfice',
    'revient', 'rentabilite', 'rentabilité',
)


def kpi_ao(company):
    """Tuiles KPI du domaine AO pour le hub fédéré (ARC40).

    Contrat de tuile : ``{id, label, valeur, unite?}``. Le hub
    (``apps/reporting/reports.py::kpi_federes``) résout ce callable par son
    chemin dotted déclaré dans ``apps/ao/platform.py`` — il n'importe AUCUN
    modèle d'``apps.ao``.
    """
    from .selectors import tableau_marches

    tableau = tableau_marches(company)
    return [
        {'id': 'ao_en_cours', 'label': "Appels d'offres en cours",
         'valeur': tableau['en_cours']['total']},
        {'id': 'ao_remise_7j', 'label': 'Remises sous 7 jours',
         'valeur': tableau['en_cours']['sous_7_jours']},
        {'id': 'ao_echeances_dues', 'label': 'Échéances AO dues',
         'valeur': tableau['echeances_dues']},
        {'id': 'ao_taux_reussite', 'label': 'Taux de réussite AO',
         'valeur': tableau['reussite']['taux_reussite_pct'], 'unite': '%'},
        {'id': 'ao_cautions_immobilisees', 'label': 'Cautions immobilisées',
         'valeur': tableau['cautions']['montant_immobilise'], 'unite': 'MAD'},
        {'id': 'ao_marches_execution', 'label': 'Marchés en exécution',
         'valeur': tableau['marches_en_execution']['total']},
        {'id': 'ao_capacite_demontree', 'label': 'Capacité démontrée',
         'valeur': tableau['capacite']['demontree_modules'],
         'unite': 'modules'},
    ]


class TableauMarchesPermission(BasePermission):
    """Lecture du tableau de bord : la permission ``ao_voir``, rien de plus.

    Le tableau ne porte AUCUN coût : il n'a donc pas besoin d'
    ``ao_rentabilite_voir``, et l'exiger fermerait à tort la vue d'ensemble aux
    commerciaux qui montent les dossiers.

    Même sémantique que la lecture des ViewSets AO (``ScopedPermission`` avec
    ``read_permission = ao_voir``) : on réutilise le MÊME helper de repli
    historique, pour qu'un compte légacy ne perde pas l'accès qu'il avait — et
    on ferme la porte aux comptes PORTAIL, comme partout sur les routes
    internes.
    """
    message = "Accès au tableau de bord des marchés non autorisé."

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return False
        if getattr(user, 'portee', 'interne') != 'interne':
            return False
        return _user_has_or_legacy(user, AO_VOIR)


@api_view(['GET'])
@permission_classes([TableauMarchesPermission])
def tableau_marches_view(request):
    """``GET /api/django/ao/tableau-marches/`` — le tableau de bord, en UN appel.

    Nom d'endpoint REPRIS DE NTMAR27 à dessein (voir le docstring du module).
    Société lue sur l'utilisateur, jamais dans la requête ; un compte sans
    société reçoit un tableau vide plutôt qu'une erreur.
    """
    from .selectors import tableau_marches, tableau_marches_vide

    company = getattr(request.user, 'company', None)
    if company is None:
        return Response(tableau_marches_vide())
    return Response(tableau_marches(company))
