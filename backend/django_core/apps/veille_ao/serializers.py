"""Sérialiseurs du module « Veille appels d'offres » (``apps.veille_ao``).

Règle multi-tenant (ARC2) : ``company`` n'est JAMAIS lue du corps de la
requête — elle est forcée côté serveur par
``core.viewsets.CompanyScopedModelViewSet.perform_create``. Elle est donc
absente des champs ici, jamais simplement « en lecture seule ».

Le statut d'un avis n'est pas modifiable par écriture directe : il ne bouge
que par le service unique de transition (VAO14).
"""
from rest_framework import serializers

from .models import (
    AcheteurCible, AvisMarche, ExecutionCollecte, MotCleVeille,
    RegleExclusion, SourceVeille,
)


class SourceVeilleSerializer(serializers.ModelSerializer):
    type_source_libelle = serializers.CharField(
        source='get_type_source_display', read_only=True)
    est_collectable_automatiquement = serializers.BooleanField(read_only=True)

    class Meta:
        model = SourceVeille
        fields = [
            'id', 'code', 'libelle', 'type_source', 'type_source_libelle',
            'url_base', 'actif', 'cadence_heures',
            'derniere_collecte_reussie', 'est_collectable_automatiquement',
            'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['derniere_collecte_reussie', 'created_at',
                            'updated_at']


class MotCleVeilleSerializer(serializers.ModelSerializer):
    niveau_libelle = serializers.CharField(
        source='get_niveau_display', read_only=True)

    class Meta:
        model = MotCleVeille
        fields = ['id', 'libelle', 'niveau', 'niveau_libelle', 'poids',
                  'actif', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class RegleExclusionSerializer(serializers.ModelSerializer):
    portee_libelle = serializers.CharField(
        source='get_portee_display', read_only=True)

    class Meta:
        model = RegleExclusion
        fields = ['id', 'portee', 'portee_libelle', 'valeur', 'motif',
                  'actif', 'compteur_application', 'created_at',
                  'updated_at']
        # Le compteur est tenu par le service, jamais posé par le client.
        read_only_fields = ['compteur_application', 'created_at',
                            'updated_at']


class AvisMarcheSerializer(serializers.ModelSerializer):
    """Le SAS vu par l'API — et la porte MANUELLE de VAO27.

    Trois choix de contrat, chacun pour une raison mesurée :

    * ``source`` accepte un identifiant technique **ou** un code de TYPE
      (``tuyau_partenaire``…). Une saisie faite debout sur un chantier ne
      connaît pas la clé primaire d'une source ; elle sait seulement « c'est
      un partenaire qui me l'a dit ». Le service résout, et crée la porte
      humaine correspondante si besoin (idempotent).
    * ``date_limite`` est l'ALIAS d'écriture et de lecture de
      ``date_limite_remise`` : c'est le nom que porte l'écran (et le même que
      côté ``apps.ao``). Les deux noms restent servis — retirer l'ancien
      casserait ce qui existe.
    * ``cree_le`` est l'alias de ``created_at`` — convention déjà en vigueur
      dans le reste du dépôt côté client.
    """

    source_libelle = serializers.CharField(
        source='source.libelle', read_only=True)
    type_source = serializers.CharField(
        source='source.type_source', read_only=True)
    statut_libelle = serializers.CharField(
        source='get_statut_display', read_only=True)
    categorie_libelle = serializers.CharField(
        source='get_categorie_display', read_only=True)
    est_depasse = serializers.BooleanField(read_only=True)
    # VAO10 — jamais un filtrage muet : l'écran doit pouvoir dire POURQUOI
    # un avis a été écarté.
    regle_exclusion_motif = serializers.CharField(
        source='regle_exclusion.motif', read_only=True, default='')
    # VAO27 — la source peut être désignée par son TYPE, pas seulement par sa
    # clé. ``CharField`` (et non ``PrimaryKeyRelatedField``) parce que le
    # schéma doit dire honnêtement qu'une chaîne est acceptée.
    source = serializers.CharField(
        required=False, allow_blank=True,
        help_text="Identifiant de la source OU code de type "
                  "(« tuyau_partenaire », « saisie_manuelle »…).")
    date_limite = serializers.DateTimeField(
        source='date_limite_remise', required=False, allow_null=True)
    cree_le = serializers.DateTimeField(source='created_at', read_only=True)
    informateur_libelle = serializers.CharField(
        source='get_informateur_display', read_only=True)

    class Meta:
        model = AvisMarche
        fields = [
            'id', 'source', 'source_libelle', 'type_source',
            'ref_consultation', 'org_acronyme', 'reference_avis',
            'objet', 'acheteur', 'lieu', 'region', 'procedure',
            'categorie', 'categorie_libelle', 'lot',
            'date_publication', 'date_limite_remise', 'date_limite',
            'date_ouverture',
            'montant_estime', 'caution_provisoire', 'url_detail',
            'informateur', 'informateur_libelle',
            'mots_cles_declenches', 'score',
            'statut', 'statut_libelle', 'est_depasse',
            'appel_offre_id', 'donnees_brutes',
            'regle_exclusion', 'regle_exclusion_motif',
            'empreinte', 'created_at', 'cree_le', 'updated_at',
        ]
        read_only_fields = [
            # Le statut ne bouge QUE par le service de transition (VAO14) ;
            # le score et les mots-clés déclenchés sont calculés (VAO9) ;
            # l'identifiant d'appel d'offres est posé par la conversion ;
            # l'empreinte et la règle d'exclusion sont calculées côté serveur.
            'statut', 'score', 'mots_cles_declenches', 'appel_offre_id',
            'donnees_brutes', 'regle_exclusion', 'empreinte',
            'created_at', 'updated_at',
        ]
        extra_kwargs = {
            # Le minimum vital, et rien de plus : une validation de plus est
            # une saisie de chantier perdue (VAO27).
            'objet': {'required': False, 'allow_blank': True},
        }

    def to_representation(self, instance):
        """``source`` se LIT comme un identifiant, malgré son ``CharField``.

        L'écran affiche ``source_libelle`` ; ce champ-ci reste la clé, pour
        que la liste déroulante des sources continue de s'y accrocher.
        """
        donnees = super().to_representation(instance)
        donnees['source'] = instance.source_id
        return donnees

    def create(self, validated_data):
        """La création via l'API est TOUJOURS une saisie manuelle (VAO27).

        Elle passe donc par ``services.creer_avis_manuel`` : informateur
        obligatoire, source résolue par type, dédoublonnage de niveau 2. Les
        avis COLLECTÉS, eux, n'empruntent jamais cette route — ils sont écrits
        par le service de collecte.
        """
        from .services import creer_avis_manuel

        requete = self.context.get('request')
        donnees = dict(validated_data)
        # ``company`` est FORCÉE côté serveur par ``TenantMixin`` : on la
        # reprend de là, jamais du corps de la requête.
        company = (donnees.pop('company', None)
                   or getattr(getattr(requete, 'user', None), 'company', None))
        avis, _cree = creer_avis_manuel(
            company, donnees, user=getattr(requete, 'user', None))
        return avis

    def update(self, instance, validated_data):
        """``source`` reste résoluble par TYPE en modification, elle aussi.

        Sans cela, un PATCH portant ``source`` écrirait une CHAÎNE dans une
        clé étrangère — le genre de 500 qui ne se voit qu'en production.
        """
        from .services import resoudre_source

        donnees = dict(validated_data)
        donnees.pop('company', None)
        if 'source' in donnees:
            donnees['source'] = resoudre_source(
                instance.company, donnees.pop('source'))
        return super().update(instance, donnees)


class AcheteurCibleSerializer(serializers.ModelSerializer):
    """VAO29 — le carnet à démarcher.

    ``lead_id`` est un entier OPAQUE vers le CRM : l'écran ouvre le lead
    EXISTANT, il n'en crée jamais un second en douce. Aucune FK, donc aucun
    import de ``apps.crm.models`` — le contrat import-linter reste vert.
    """

    type_libelle = serializers.CharField(
        source='get_type_display', read_only=True)
    statut_relation_display = serializers.CharField(
        source='get_statut_relation_display', read_only=True)
    relance_due = serializers.BooleanField(read_only=True)

    class Meta:
        model = AcheteurCible
        fields = [
            'id', 'nom', 'type', 'type_libelle', 'contact',
            'dernier_contact', 'prochaine_relance', 'relance_due',
            'statut_relation', 'statut_relation_display', 'lead_id',
            'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class ExecutionCollecteSerializer(serializers.ModelSerializer):
    """VAO24 — une ligne du journal d'exécution (LECTURE seule côté API).

    Le journal est écrit par le service de collecte, jamais par un client :
    un journal qu'on peut réécrire depuis l'extérieur ne prouve plus rien.
    """

    source_libelle = serializers.CharField(
        source='source.libelle', read_only=True, default='')
    verdict_libelle = serializers.CharField(
        source='get_verdict_display', read_only=True)
    declencheur_libelle = serializers.CharField(
        source='get_declencheur_display', read_only=True)

    class Meta:
        model = ExecutionCollecte
        fields = [
            'id', 'source', 'source_libelle', 'debut', 'fin',
            'mots_cles_interroges', 'examines', 'nouveaux', 'mis_a_jour',
            'auto_ignores', 'erreurs', 'verdict', 'verdict_libelle',
            'message', 'declencheur', 'declencheur_libelle',
            'alarme_notifiee', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class SanteVeilleSerializer(serializers.Serializer):
    """VAO24/VAO35/VAO37 — l'état de la veille, en UN appel agrégé.

    Un sérialiseur RÉEL, jamais ``response=dict`` : un endpoint agrégé sans
    schéma déclaré est un contrat que le frontend doit deviner — la faute
    exacte que ``scripts/check_api_contract.py`` existe pour empêcher.

    Le bandeau de santé (VAO37) ET l'écran de paramètres (VAO35) consomment
    CE calcul, jamais un agrégat dérivé côté client à partir de la liste des
    exécutions : deux calculs finiraient par diverger, et un désaccord entre
    écrans fait douter de l'ensemble.
    """

    derniere_collecte_reussie = serializers.DateTimeField(
        read_only=True, allow_null=True,
        help_text='Null = la veille n\'a jamais rien collecté avec succès.')
    age_heures = serializers.FloatField(
        read_only=True, allow_null=True,
        help_text="L'ÂGE de cette collecte — visible sans clic (VAO37).")
    avis_examines_hier = serializers.IntegerField(read_only=True)
    alarme_active = serializers.BooleanField(
        read_only=True,
        help_text='Alarme de collecte silencieuse (VAO24) : la veille ne '
                  'ramène plus rien.')
    alarme_message = serializers.CharField(read_only=True, allow_blank=True)
    collecte_active = serializers.BooleanField(
        read_only=True,
        help_text="Armement de la collecte automatique (règle #5, VAO4).")
    dernier_verdict = serializers.CharField(read_only=True, allow_blank=True)
    dernier_message = serializers.CharField(read_only=True, allow_blank=True)
    sources_collectables = serializers.IntegerField(read_only=True)
    avis_nouveaux = serializers.IntegerField(read_only=True)


class LancementCollecteSerializer(serializers.Serializer):
    """VAO23 — la réponse du bouton « Rafraîchir maintenant ».

    Un sérialiseur RÉEL, jamais ``response=dict`` dans ``@extend_schema`` : un
    endpoint agrégé sans schéma est un contrat que le frontend doit deviner —
    exactement le défaut que ``scripts/check_api_contract.py`` existe pour
    empêcher.

    ``id`` ET ``job_id`` portent la même valeur : l'écran suit le job par le
    sondage GÉNÉRIQUE des jobs de fond (qui cherche ``id``), et ``job_id`` est
    le nom explicite du contrat.
    """

    id = serializers.IntegerField(read_only=True, help_text='Job de fond créé.')
    job_id = serializers.IntegerField(read_only=True)
    kind = serializers.CharField(read_only=True)
    statut = serializers.CharField(read_only=True)
    progress_pct = serializers.IntegerField(read_only=True)
    deja_en_cours = serializers.BooleanField(
        read_only=True,
        help_text="Vrai si une collecte tournait déjà : aucun second job "
                  "n'a été lancé (double clic sans effet).")
    collecte_active = serializers.BooleanField(
        read_only=True,
        help_text="Armement de la collecte automatique (règle #5). Faux = le "
                  "job sortira sans aucun appel réseau.")
    motif = serializers.CharField(
        read_only=True, allow_blank=True,
        help_text="Message français quand rien ne sera collecté.")
