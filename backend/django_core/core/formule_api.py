"""NTEXT37 — test unitaire d'une EXPRESSION sur des données réelles.

``POST core/formule/tester/`` évalue une expression (``core.formula``, jamais
``eval``) sur les premières lignes RÉELLES d'un dataset enregistré
(``core.data_explorer``) et renvoie ligne par ligne la valeur calculée — de
quoi vérifier une formule AVANT de la sauver comme champ calculé ou comme
mesure de rapport.

Garanties
---------
* **Aucun effet de bord** — 100 % lecture : ``run_query`` projette en
  ``values()`` et l'évaluateur de formule n'a ni écriture, ni accès système.
  Rien n'est enregistré (ni la formule, ni le résultat).
* **Scopé société** — la société vient TOUJOURS de ``request.user`` ; le
  ``queryset_provider`` du dataset est déjà borné au tenant.
* **Borné** — au plus 20 lignes (défaut 5) : c'est un banc d'essai, pas un
  export.
* **Erreurs en français** — dataset inconnu, champ hors liste blanche,
  expression illégale : chacun renvoie un message clair, jamais une 500.

Corps attendu::

    {"expression": "ca / nb_devis", "dataset": "ventes",
     "filtres": {"statut": "accepte"}, "limite": 5,
     "group_by": ["commercial"],
     "agregats": [{"alias": "ca", "fn": "sum", "field": "total_ht"},
                  {"alias": "nb_devis", "fn": "count", "field": "id"}]}

``group_by``/``agregats`` sont OPTIONNELS : sans eux, l'expression est évaluée
sur les CHAMPS BRUTS de chaque ligne ; avec eux, sur les alias d'agrégats
(exactement le contexte d'une mesure formule de rapport, XPLT11).
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsAnyRole

__all__ = ['FormuleTestView', 'LIMITE_MAX_LIGNES']

#: Borne dure du banc d'essai (jamais un export déguisé).
LIMITE_MAX_LIGNES = 20
#: Nombre de lignes testées par défaut.
LIMITE_DEFAUT = 5


def _limite(brut):
    try:
        valeur = int(brut) if brut not in (None, '') else LIMITE_DEFAUT
    except (TypeError, ValueError):
        valeur = LIMITE_DEFAUT
    return max(1, min(valeur, LIMITE_MAX_LIGNES))


class FormuleTestView(APIView):
    """Banc d'essai d'une expression sur des données réelles (lecture seule)."""

    permission_classes = [IsAnyRole]

    @extend_schema(
        request=inline_serializer('FormuleTestRequete', {
            'expression': drf_serializers.CharField(),
            'dataset': drf_serializers.CharField(),
            'filtres': drf_serializers.JSONField(required=False),
            'limite': drf_serializers.IntegerField(required=False),
            'group_by': drf_serializers.JSONField(required=False),
            'agregats': drf_serializers.JSONField(required=False),
        }),
        responses=inline_serializer('FormuleTestReponse', {
            'dataset': drf_serializers.CharField(),
            'expression': drf_serializers.CharField(),
            'lignes': drf_serializers.JSONField(),
        }))
    def post(self, request):
        from core import data_explorer
        from core.formula import (
            FormulaError, evaluer_formule, valider_formule,
        )

        donnees = request.data if isinstance(request.data, dict) else {}
        expression = (donnees.get('expression') or '').strip()
        nom_dataset = (donnees.get('dataset') or '').strip()

        if not expression:
            return Response(
                {'detail': "L'expression à tester est requise."},
                status=status.HTTP_400_BAD_REQUEST)
        if not nom_dataset:
            return Response(
                {'detail': 'Le dataset à interroger est requis.'},
                status=status.HTTP_400_BAD_REQUEST)

        filtres = donnees.get('filtres') or {}
        if not isinstance(filtres, dict):
            return Response(
                {'detail': 'Les filtres doivent être un objet '
                           '{champ: valeur}.'},
                status=status.HTTP_400_BAD_REQUEST)

        spec = {
            'filters': filtres,
            'limit': _limite(donnees.get('limite')),
            'group_by': donnees.get('group_by') or [],
            'aggregates': donnees.get('agregats') or [],
        }

        try:
            lignes = data_explorer.run_query(
                nom_dataset, request.user.company, request.user, spec)
        except data_explorer.DatasetInconnu:
            return Response(
                {'detail': f'Dataset « {nom_dataset} » inconnu.'},
                status=status.HTTP_404_NOT_FOUND)
        except data_explorer.ChampNonAutorise as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        except FormulaError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {'detail': 'Impossible de lire ce dataset avec ces filtres.'},
                status=status.HTTP_400_BAD_REQUEST)

        if not lignes:
            return Response({
                'dataset': nom_dataset, 'expression': expression,
                'lignes': [],
                'detail': 'Aucune donnée réelle ne correspond : la formule '
                          "n'a pas pu être testée.",
            })

        # Une expression ILLÉGALE (nœud interdit, fonction non autorisée) est
        # rejetée UNE fois pour toutes, pas ligne par ligne : c'est une erreur
        # de saisie, pas un résultat.
        colonnes = sorted({cle for ligne in lignes for cle in ligne})
        ok, erreur = valider_formule(expression, colonnes)
        if not ok:
            return Response(
                {'detail': f'Expression invalide : {erreur} '
                           f'Colonnes disponibles : '
                           f'{", ".join(colonnes) or "aucune"}.'},
                status=status.HTTP_400_BAD_REQUEST)

        resultats = []
        for ligne in lignes:
            entree = {'contexte': ligne}
            try:
                entree['valeur'] = evaluer_formule(expression, ligne)
            except FormulaError as exc:
                # Cas ligne-par-ligne (typiquement une division par zéro sur
                # CETTE ligne) : la ligne porte son erreur, les autres restent
                # calculées.
                entree['valeur'] = None
                entree['erreur'] = str(exc)
            resultats.append(entree)

        return Response({
            'dataset': nom_dataset,
            'expression': expression,
            'colonnes': colonnes,
            'lignes': resultats,
        })
