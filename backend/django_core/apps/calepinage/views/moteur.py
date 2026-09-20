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

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import ScopedPermission

from ..permissions import CAL_GERER, CAL_VOIR

__all__ = ['MoteurCalculerView', 'MoteurPoseView', 'MoteurResultatView',
           'document_de_la_demande', 'verdict_de_pose']


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


# ---------------------------------------------------------------------------
# YAPIC6/PACT7 — LES FORMES DÉCLARÉES DES TROIS PORTES DU MOTEUR
# ---------------------------------------------------------------------------
#
# Ces vues sont des ``APIView`` : drf-spectacular ne peut pas DEVINER leur
# sérialiseur, et le dépôt refuse à la fois de le laisser deviner
# (``scripts/check_openapi_shapes.py``, cliquet R2) et de déclarer une forme
# VIDE (``response=dict``, règle R1 — c'est littéralement ce que déclarait
# l'écran qui a planté le 03/08/2026).
#
# Les formes ci-dessous sont RECOPIÉES des contrats committés
# (``contract_samples/moteur_calculer.json``, ``pose.json``), déjà confrontés
# au code par ``scripts/check_api_shapes.py``. Les sous-documents du moteur
# (un plan, une preuve, des marges) gardent un ``DictField``/``ListField`` :
# leur vocabulaire est celui du noyau ``core/calepinage``, versionné là-bas —
# le figer ICI en créerait une seconde définition, la dérive que PACT10 ferme.

#: Le tronc COMMUN à ``calculer`` et à ``pose`` : ce que le moteur MESURE.
_POSE_MESUREE = {
    'schema_version': serializers.IntegerField(),
    'repere': serializers.CharField(allow_blank=True),
    'hash_entree': serializers.CharField(allow_blank=True),
    'version_moteur': serializers.CharField(allow_blank=True),
    'total_modules': serializers.IntegerField(),
    'kwc': serializers.FloatField(),
    'engageable': serializers.BooleanField(),
    'motifs_non_engageable': serializers.ListField(
        child=serializers.CharField()),
    'plans': serializers.ListField(child=serializers.DictField()),
    'preuve': serializers.DictField(),
    'marges': serializers.DictField(),
}

#: L'entrée du moteur : le document de relevé, dont le vocabulaire est celui
#: de ``core/calepinage/serialisation.py`` (contour, surfaces, kits,
#: paramètres, obstacles, zones) — décrit ici section par section.
_DOCUMENT_MOTEUR = {
    'schema_version': serializers.IntegerField(required=False),
    'repere': serializers.CharField(required=False, allow_blank=True),
    'contour': serializers.ListField(child=serializers.ListField(
        child=serializers.FloatField()), required=False),
    'surfaces': serializers.ListField(child=serializers.DictField(),
                                      required=False),
    'kits': serializers.ListField(child=serializers.DictField(),
                                  required=False),
    'parametres': serializers.DictField(required=False),
    'obstacles': serializers.ListField(child=serializers.DictField(),
                                       required=False),
    'zones': serializers.ListField(child=serializers.DictField(),
                                   required=False),
    'engagements': serializers.ListField(child=serializers.DictField(),
                                         required=False),
}

FORME_CALCULER = inline_serializer('CalepinageMoteurCalculerReponse', dict(
    _POSE_MESUREE,
    company_id=serializers.IntegerField(allow_null=True),
    engagement_modules=serializers.IntegerField(allow_null=True),
    depuis_cache=serializers.BooleanField(),
    rangees=serializers.ListField(child=serializers.DictField()),
    tiroirs=serializers.DictField(),
    suggestions=serializers.ListField(child=serializers.DictField()),
))

FORME_ACCUSE = inline_serializer('CalepinageMoteurAccuseTravailLong', {
    'job_id': serializers.IntegerField(),
    'kind': serializers.CharField(),
    'statut': serializers.CharField(),
    'progress_pct': serializers.IntegerField(),
    'message_erreur': serializers.CharField(allow_blank=True),
    'resultat': serializers.DictField(allow_null=True),
    'variante': serializers.DictField(allow_null=True),
    'detail': serializers.CharField(),
    'cout_estime': serializers.DictField(),
})

FORME_POSE = inline_serializer('CalepinageMoteurPoseReponse', dict(
    _POSE_MESUREE, verdict=serializers.CharField()))

FORME_SUIVI = inline_serializer('CalepinageMoteurResultatReponse', {
    'job_id': serializers.IntegerField(),
    'kind': serializers.CharField(),
    'statut': serializers.CharField(),
    'progress_pct': serializers.IntegerField(),
    'message_erreur': serializers.CharField(allow_blank=True),
    'resultat': serializers.DictField(allow_null=True),
    'elements': serializers.ListField(child=serializers.DictField()),
    'variante': serializers.DictField(allow_null=True),
})


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

    @extend_schema(
        request=inline_serializer('CalepinageMoteurCalculerRequete',
                                  dict(_DOCUMENT_MOTEUR)),
        responses={200: FORME_CALCULER, 202: FORME_ACCUSE})
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


def verdict_de_pose(resultat):
    """CAL78 — la phrase de verdict, GÉNÉRÉE des grandeurs MESURÉES.

    Règle du dépôt (``core/calepinage/sensibilites.py``) : une phrase de
    verdict est GÉNÉRÉE, jamais rédigée. Elle ne dit donc rien que la preuve
    ne porte déjà — compte posé, régime de preuve, borne supérieure — et
    reprend mot pour mot le libellé du moteur quand il n'y a rien à poser :
    inventer une raison que le moteur n'a pas donnée serait un chiffre de
    plus, pas une explication.
    """
    preuve = resultat.get('preuve') or {}
    modules = resultat.get('total_modules') or 0
    if not modules:
        return (preuve.get('libelle')
                or "Aucun module posable sur ce relevé.")
    if preuve.get('optimal') and preuve.get('methode_exacte'):
        return "Pose complète : %d modules posés, optimum prouvé." % modules
    borne = preuve.get('borne_superieure')
    if borne is None:
        return ("Pose retenue : %d modules posés, optimum NON prouvé."
                % modules)
    return ("Pose retenue : %d modules posés, optimum NON prouvé "
            "(borne supérieure : %d)." % (modules, borne))


class MoteurPoseView(APIView):
    """``POST /api/django/calepinage/moteur/pose/`` — LA POSE, avec sa preuve.

    Contrat committé : ``contract_samples/pose.json`` (PACT10). On soumet un
    relevé sous la clé ``demande`` et le moteur rend les panneaux POSÉS **avec
    le régime de preuve sous lequel il les a posés** — un compte sans son
    régime n'est pas opposable.

    CE QUI LA DISTINGUE DE ``calculer``. Rien dans le moteur : c'est LE MÊME
    point d'entrée neutre (``apps.ao.selectors.calepinage_json``), donc aucune
    seconde sérialisation qui dériverait de la première. La différence est la
    RÉPONSE : ``calculer`` publie la carte complète de l'atelier (tiroirs,
    suggestions, cache, engagement) ; ``pose`` publie la POSE et sa preuve, et
    rien d'autre. Les charges utiles d'atelier ne sont donc même pas calculées
    (``tiroirs=False``, ``suggestions=False``) : on ne paye pas un travail que
    la réponse ne publie pas.

    Elle n'écrit RIEN — aucun calepinage, aucune variante, aucun statut.

    * **200** — la pose, à la forme figée par le contrat ;
    * **400** — document invalide ou plan incohérent, motif FRANÇAIS du
      serveur, champ fautif nommé ;
    * **403** — sans ``calepinage_gerer`` (le calcul est une écriture au sens
      des permissions, comme pour ``calculer``).
    """

    permission_classes = [ScopedPermission]
    read_permission = CAL_VOIR
    write_permission = CAL_GERER

    @extend_schema(
        request=inline_serializer('CalepinageMoteurPoseRequete', {
            'demande': inline_serializer('CalepinageMoteurPoseDemande',
                                         dict(_DOCUMENT_MOTEUR)),
        }),
        responses={200: FORME_POSE})
    def post(self, request, *args, **kwargs):
        from apps.ao.selectors import calepinage_json, erreurs_moteur_calepinage

        entree_invalide, incoherent = erreurs_moteur_calepinage()
        donnees = request.data
        # La demande voyage sous ``demande`` (la clé que le contrat fige).
        # L'enveloppe ``entree`` et le document NU sont acceptés en plus, par
        # le MÊME lecteur que ``calculer`` : un appelant qui connaît déjà la
        # porte du moteur n'a pas à apprendre une seconde grammaire.
        if isinstance(donnees, dict) and isinstance(donnees.get('demande'),
                                                    dict):
            donnees = donnees['demande']
        document = document_de_la_demande(donnees)
        # LES REFUS SONT LEVÉS, PAS RENVOYÉS. DRF rend exactement le même 400
        # (même corps, même champ fautif nommé) et, surtout,
        # `scripts/check_api_shapes.py` lit la vue en UNION de tous ses
        # `return Response(...)` : un 400 renvoyé ferait entrer `demande`,
        # `calepinage` et `controle` dans la FORME de la réponse 200 et
        # ferait diverger le contrat committé `contract_samples/pose.json`.
        if document is None:
            raise ValidationError(
                {'demande': "Relevé de pose manquant ou invalide : le corps "
                            "attendu porte le document du moteur sous "
                            "« demande »."})

        company = getattr(request.user, 'company', None)
        if company is None:
            raise ValidationError(
                {'demande': 'Une pose se calcule toujours dans une société.'})

        try:
            resultat = calepinage_json(document, company=company,
                                       user=request.user, tiroirs=False,
                                       suggestions=False)
        except entree_invalide as erreur:
            raise ValidationError({'demande': [str(erreur)]}) from erreur
        except incoherent as erreur:
            raise ValidationError({'calepinage': [str(erreur)],
                                   'controle': erreur.controle,
                                   'repere': erreur.repere}) from erreur

        # Dictionnaire LITTÉRAL : c'est lui que `scripts/check_api_shapes.py`
        # lit statiquement pour le confronter à `contract_samples/pose.json`.
        # Le construire par compréhension rendrait la vue illisible à la garde
        # — et un contrat qu'aucune garde ne relit pourrit en silence.
        return Response({
            'schema_version': resultat['schema_version'],
            'repere': resultat['repere'],
            'hash_entree': resultat['hash_entree'],
            'version_moteur': resultat['version_moteur'],
            'total_modules': resultat['total_modules'],
            'kwc': resultat['kwc'],
            'engageable': resultat['engageable'],
            'motifs_non_engageable': resultat['motifs_non_engageable'],
            'verdict': verdict_de_pose(resultat),
            'plans': resultat['plans'],
            'preuve': resultat['preuve'],
            'marges': resultat['marges'],
        })


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

    @extend_schema(responses={200: FORME_SUIVI})
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
