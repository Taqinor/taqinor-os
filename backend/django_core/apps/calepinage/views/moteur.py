"""CAL22 — la porte HTTP NEUTRE du moteur de calepinage.

LE CONSTAT
----------
Le moteur (``core/calepinage``) est un NOYAU PUR ouvert à tout consommateur —
``apps.ventes`` le consomme déjà pour la villa (``domain/geometrie.py`` via
``apps.ao.selectors.calepinage_villa``). Mais son SEUL accès HTTP était gardé
AO (``apps/ao/calepinage_urls.py``, permissions ``ao_voir``/``ao_gerer``) : un
module autonome devait donc emprunter la porte d'un autre domaine, avec les
permissions de cet autre domaine. Cette vue est la porte propre du module.

CE QU'ELLE NE FAIT PAS
----------------------
* elle ne REFAIT pas la sérialisation du moteur : elle appelle
  ``apps.ao.selectors.calepinage_json`` (fonction mince ajoutée côté AO), donc
  la forme publiée reste CELLE DU DÉPÔT — une seconde sérialisation dériverait
  de la première au premier champ ajouté ;
* elle n'invente AUCUNE valeur par défaut de perte ni de tarif (décision D5) :
  ce que le document ne dit pas, le moteur ne le suppose pas ;
* elle n'écrit RIEN : aucune ligne AO, aucun calepinage, aucun statut.

LA BORNE DE COÛT
----------------
Le travail est CHIFFRÉ avant d'être lancé. Au-delà du budget synchrone, la
route rend **202** avec la consigne de suivi (CAL23 branche la tâche de fond)
plutôt que de tenir un utilisateur devant un écran gelé.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import ScopedPermission

from ..permissions import CAL_GERER, CAL_VOIR

__all__ = ['MoteurCalculerView', 'document_de_la_demande']


def document_de_la_demande(donnees):
    """Le document d'entrée d'un corps de requête, ou ``None``.

    Accepte l'enveloppe ``{"entree": {…}}`` (la forme d'AO) et le document
    NU. Rien d'autre : un corps qui n'est pas un objet ne décrit aucune
    toiture.
    """
    if isinstance(donnees, dict):
        if set(donnees.keys()) == {'entree'}:
            donnees = donnees['entree']
        elif 'entree' in donnees and isinstance(donnees['entree'], dict):
            donnees = donnees['entree']
    if not isinstance(donnees, dict) or not donnees:
        return None
    return donnees


class MoteurCalculerView(APIView):
    """``POST /api/django/calepinage/moteur/calculer/`` — calcul BORNÉ.

    * **200** — le résultat, à la forme figée par CAL2 ;
    * **202** — le travail dépasse le budget synchrone (corps : le coût
      estimé et où suivre le calcul) ;
    * **400** — document invalide ou plan incohérent, avec le motif FRANÇAIS
      du serveur et le champ fautif nommé.
    """

    permission_classes = [ScopedPermission]
    read_permission = CAL_VOIR
    #: Le calcul est une ÉCRITURE au sens des permissions (il consomme du
    #: temps serveur et produit un document de travail) : ``calepinage_gerer``.
    write_permission = CAL_GERER

    def post(self, request, *args, **kwargs):
        from apps.ao.selectors import (
            calepinage_json, cout_calepinage, erreurs_moteur_calepinage,
        )

        entree_invalide, incoherent = erreurs_moteur_calepinage()
        document = document_de_la_demande(request.data)
        if document is None:
            return Response(
                {'entree': "Document de calepinage manquant ou invalide : le "
                           "corps attendu est l'entrée du moteur."},
                status=status.HTTP_400_BAD_REQUEST)

        company = getattr(request.user, 'company', None)
        if company is None:
            return Response(
                {'entree': 'Un calepinage se calcule toujours dans une '
                           'société.'},
                status=status.HTTP_400_BAD_REQUEST)

        try:
            cout = cout_calepinage(document)
        except entree_invalide as erreur:
            return Response({'entree': [str(erreur)]},
                            status=status.HTTP_400_BAD_REQUEST)
        if not cout.synchrone:
            return Response(accuse_de_travail_long(cout),
                            status=status.HTTP_202_ACCEPTED)

        try:
            resultat = calepinage_json(document, company=company,
                                       user=request.user)
        except entree_invalide as erreur:
            return Response({'entree': [str(erreur)]},
                            status=status.HTTP_400_BAD_REQUEST)
        except incoherent as erreur:
            return Response({'calepinage': [str(erreur)],
                             'controle': erreur.controle,
                             'repere': erreur.repere},
                            status=status.HTTP_400_BAD_REQUEST)
        resultat['depuis_cache'] = False
        return Response(resultat)


def accuse_de_travail_long(cout):
    """Le 202 : ce que coûte le calcul, et OÙ le suivre.

    Forme ``exemple_vide`` du contrat CAL2. CAL23 y branche la tâche de fond ;
    tant qu'elle n'est pas là, la route DIT que le travail est trop lourd au
    lieu de le lancer quand même.
    """
    return {
        'detail': ("Ce calepinage dépasse le budget de calcul synchrone : "
                   "lancez-le en tâche de fond."),
        'cout_estime': {
            'positions': cout.positions,
            'kits': cout.kits,
            'appels': cout.appels,
            'millisecondes': round(cout.millisecondes, 1),
            'motif': cout.motif,
        },
    }
