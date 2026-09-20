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

__all__ = ['MoteurCalculerView', 'MoteurResultatView',
           'document_de_la_demande']


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
            return Response(
                accuse_de_travail_long(
                    cout, _lancer_en_tache_de_fond(request, company,
                                                   document)),
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


def _lancer_en_tache_de_fond(request, company, document):
    """CAL23 — dispatch par ``core.jobs.submit`` : jamais une file maison.

    Une soumission de PLUSIEURS documents emprunte le MÊME kind
    (``calepinage``) : l'appelant passe une liste, la tâche traite chaque
    élément séparément. Société et utilisateur sont posés côté serveur par la
    primitive elle-même.
    """
    from core.jobs import submit

    from ..tasks import KIND_CALEPINAGE, calculer_calepinage

    documents = document.get('entrees') if isinstance(
        document.get('entrees'), list) else None
    return submit(KIND_CALEPINAGE, calculer_calepinage, company=company,
                  user=request.user,
                  entree=None if documents else document,
                  entrees=documents)


def accuse_de_travail_long(cout, job):
    """Le 202 : le job à suivre, et ce que le calcul coûte.

    Forme ``exemple_vide`` du contrat CAL2 : l'identifiant est nommé
    ``job_id`` (et pas ``id``) pour qu'aucun écran ne le confonde avec l'id
    d'un calepinage.
    """
    return {
        'job_id': job.pk,
        'kind': job.kind,
        'statut': job.statut,
        'progress_pct': job.progress_pct,
        'message_erreur': job.message_erreur or '',
        'resultat': None,
        'variante': None,
        'detail': ("Ce calepinage dépasse le budget de calcul synchrone : "
                   "suivez-le sur /api/django/calepinage/moteur/resultat/"
                   f"{job.pk}/."),
        'cout_estime': {
            'positions': cout.positions,
            'kits': cout.kits,
            'appels': cout.appels,
            'millisecondes': round(cout.millisecondes, 1),
            'motif': cout.motif,
        },
    }


class MoteurResultatView(APIView):
    """``GET /api/django/calepinage/moteur/resultat/<job_id>/`` — l'état + le
    résultat d'un calcul lancé en tâche de fond.

    Le job d'une AUTRE société est INTROUVABLE (404), jamais « interdit » : un
    403 confirmerait son existence. Mêmes clés que l'accusé 202, plus le
    résultat quand il est là — ``resultat: null`` veut dire « pas encore », et
    la liste ``elements`` dit l'issue de CHAQUE document d'un lot.
    """

    permission_classes = [ScopedPermission]
    read_permission = CAL_VOIR
    write_permission = CAL_GERER

    def get(self, request, job_id=None, *args, **kwargs):
        from core.models import BackgroundJob

        from ..tasks import KIND_CALEPINAGE, resultat_du_job

        company = getattr(request.user, 'company', None)
        job = BackgroundJob.objects.filter(
            pk=job_id, company=company, kind=KIND_CALEPINAGE).first()
        if job is None:
            return Response({'detail': 'Calcul de calepinage introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        charge = resultat_du_job(job) or {}
        return Response({
            'job_id': job.pk,
            'kind': job.kind,
            'statut': job.statut,
            'progress_pct': job.progress_pct,
            'message_erreur': job.message_erreur or '',
            'resultat': charge.get('resultat'),
            'elements': charge.get('elements') or [],
            'variante': None,
        })
