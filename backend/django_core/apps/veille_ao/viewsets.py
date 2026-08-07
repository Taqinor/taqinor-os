"""ViewSets du module « Veille appels d'offres » (VAO12).

Tous héritent de ``core.viewsets.CompanyScopedModelViewSet`` (ARC2) : queryset
filtré sur ``request.user.company`` et ``company`` FORCÉE côté serveur dans
``perform_create``, jamais lue du corps de la requête.
``scripts/check_platform.py`` refuse tout NOUVEAU ``ModelViewSet`` hors de ce
socle.

Le contrôle d'accès est exprimé d'UNE seule façon, jamais un mélange ad hoc :
``read_permission`` / ``write_permission`` (lus par ``ScopedPermission``).

  * ``veille_ao_voir``  — LIRE les avis. Distribué largement : un commercial
    doit voir passer les avis, sinon la veille ne sert à personne.
  * ``veille_ao_gerer`` — ÉCRIRE : sources, mots-clés, règles d'exclusion et
    arbitrages. Palier Responsable/Directeur — ces réglages décident de ce que
    TOUTE la société voit.
"""
from core.viewsets import CompanyScopedModelViewSet

from .models import (
    AcheteurCible, AvisMarche, ExecutionCollecte, MotCleVeille,
    RegleExclusion, SourceVeille,
)
from .serializers import (
    AcheteurCibleSerializer, AvisMarcheSerializer, ExecutionCollecteSerializer,
    MotCleVeilleSerializer, RegleExclusionSerializer, SourceVeilleSerializer,
)

VEILLE_AO_VOIR = 'veille_ao_voir'
VEILLE_AO_GERER = 'veille_ao_gerer'


class SourceVeilleViewSet(CompanyScopedModelViewSet):
    """Le catalogue des sources (VAO7) — réglage, donc palier gestion."""

    queryset = SourceVeille.objects.all()
    serializer_class = SourceVeilleSerializer
    read_permission = VEILLE_AO_VOIR
    write_permission = VEILLE_AO_GERER
    search_fields = ['code', 'libelle', 'notes']
    ordering_fields = ['libelle', 'type_source', 'actif',
                       'derniere_collecte_reussie', 'id']


class AvisMarcheViewSet(CompanyScopedModelViewSet):
    """Le SAS (VAO8) — la liste des avis à trier."""

    queryset = AvisMarche.objects.select_related('source', 'regle_exclusion')
    serializer_class = AvisMarcheSerializer
    read_permission = VEILLE_AO_VOIR
    write_permission = VEILLE_AO_GERER
    search_fields = ['objet', 'acheteur', 'reference_avis',
                     'ref_consultation', 'lieu', 'region']
    ordering_fields = ['date_publication', 'date_limite_remise', 'score',
                       'acheteur', 'statut', 'id']


class MotCleVeilleViewSet(CompanyScopedModelViewSet):
    """Les mots-clés (VAO9) — de la DONNÉE, réglable sans redéploiement."""

    queryset = MotCleVeille.objects.all()
    serializer_class = MotCleVeilleSerializer
    read_permission = VEILLE_AO_VOIR
    write_permission = VEILLE_AO_GERER
    search_fields = ['libelle']
    ordering_fields = ['libelle', 'niveau', 'poids', 'actif', 'id']


class RegleExclusionViewSet(CompanyScopedModelViewSet):
    """Les règles d'exclusion (VAO10) — « Ignorer » qui apprend."""

    queryset = RegleExclusion.objects.all()
    serializer_class = RegleExclusionSerializer
    read_permission = VEILLE_AO_VOIR
    write_permission = VEILLE_AO_GERER
    search_fields = ['valeur', 'motif']
    ordering_fields = ['portee', 'valeur', 'compteur_application', 'actif',
                       'id']


class AcheteurCibleViewSet(CompanyScopedModelViewSet):
    """Le carnet à démarcher (VAO29) — la vraie contre-mesure FRDISI.

    Écriture au palier ``veille_ao_gerer`` comme le reste du module ; lecture
    largement distribuée, parce qu'un commercial doit voir qui il faut aller
    voir.
    """

    queryset = AcheteurCible.objects.all()
    serializer_class = AcheteurCibleSerializer
    read_permission = VEILLE_AO_VOIR
    write_permission = VEILLE_AO_GERER
    search_fields = ['nom', 'contact', 'notes']
    ordering_fields = ['nom', 'type', 'prochaine_relance', 'dernier_contact',
                       'statut_relation', 'id']


class ExecutionCollecteViewSet(CompanyScopedModelViewSet):
    """Le journal d'exécution (VAO24) — LECTURE SEULE.

    ``http_method_names`` retire les verbes d'écriture : le journal est écrit
    par le service de collecte et par lui seul. Un journal qu'un client peut
    réécrire ou effacer ne prouve plus rien le jour où il faut comprendre
    pourquoi la veille n'a rien ramené.

    Le socle reste ``CompanyScopedModelViewSet`` (et non un
    ``ReadOnlyModelViewSet``) pour que le balayage générique d'isolation
    multi-tenant le découvre automatiquement.
    """

    queryset = ExecutionCollecte.objects.select_related('source')
    serializer_class = ExecutionCollecteSerializer
    read_permission = VEILLE_AO_VOIR
    write_permission = VEILLE_AO_GERER
    http_method_names = ['get', 'head', 'options']
    search_fields = ['message']
    ordering_fields = ['debut', 'fin', 'verdict', 'examines', 'nouveaux',
                       'id']
