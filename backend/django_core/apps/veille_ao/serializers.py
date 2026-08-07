"""Sérialiseurs du module « Veille appels d'offres » (``apps.veille_ao``).

Règle multi-tenant (ARC2) : ``company`` n'est JAMAIS lue du corps de la
requête — elle est forcée côté serveur par
``core.viewsets.CompanyScopedModelViewSet.perform_create``. Elle est donc
absente des champs ici, jamais simplement « en lecture seule ».

Le statut d'un avis n'est pas modifiable par écriture directe : il ne bouge
que par le service unique de transition (VAO14).
"""
from rest_framework import serializers

from .models import AvisMarche, MotCleVeille, RegleExclusion, SourceVeille


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

    class Meta:
        model = AvisMarche
        fields = [
            'id', 'source', 'source_libelle', 'type_source',
            'ref_consultation', 'org_acronyme', 'reference_avis',
            'objet', 'acheteur', 'lieu', 'region', 'procedure',
            'categorie', 'categorie_libelle', 'lot',
            'date_publication', 'date_limite_remise', 'date_ouverture',
            'montant_estime', 'caution_provisoire', 'url_detail',
            'mots_cles_declenches', 'score',
            'statut', 'statut_libelle', 'est_depasse',
            'appel_offre_id', 'donnees_brutes',
            'regle_exclusion', 'regle_exclusion_motif',
            'empreinte', 'created_at', 'updated_at',
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
