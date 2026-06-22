"""Sérialiseurs de la Gestion de projet.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). Tous les FK reçus sont validés comme
appartenant à la société de l'utilisateur.
"""
from rest_framework import serializers

from .models import (
    DependanceTache,
    PhaseProjet,
    Projet,
    ProjetActivity,
    ProjetChantier,
    ProjetLien,
    Tache,
)


def _meme_societe(serializer, value, label):
    """Garde-fou : un FK doit appartenir à la société de l'utilisateur."""
    request = serializer.context.get('request')
    if value is not None and request is not None:
        if value.company_id != request.user.company_id:
            raise serializers.ValidationError(f'{label} inconnu.')
    return value


class ProjetSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = Projet
        fields = [
            'id', 'code', 'nom', 'description', 'statut', 'statut_display',
            'client_id', 'date_debut', 'date_fin_prevue', 'responsable',
            'budget_total', 'date_creation',
        ]
        # ``statut`` est piloté UNIQUEMENT par les actions de transition
        # (machine à états côté serveur) — jamais écrit depuis le corps de
        # requête (création ou PATCH).
        read_only_fields = ['statut', 'date_creation']

    def validate_responsable(self, value):
        return _meme_societe(self, value, 'Responsable')


class ProjetActivitySerializer(serializers.ModelSerializer):
    """Entrée du journal des transitions de statut d'un projet (lecture seule).

    ``company`` et ``auteur`` sont posés côté serveur ; jamais exposés en
    écriture.
    """
    auteur_nom = serializers.CharField(
        source='auteur.username', read_only=True, default='')

    class Meta:
        model = ProjetActivity
        fields = [
            'id', 'projet', 'old_value', 'new_value', 'auteur', 'auteur_nom',
            'date_creation',
        ]
        read_only_fields = fields


class ProjetChantierSerializer(serializers.ModelSerializer):
    projet_code = serializers.CharField(source='projet.code', read_only=True)

    class Meta:
        model = ProjetChantier
        fields = [
            'id', 'projet', 'projet_code', 'chantier_id', 'libelle',
            'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_projet(self, value):
        return _meme_societe(self, value, 'Projet')


class PhaseProjetSerializer(serializers.ModelSerializer):
    """Phase (WBS) d'un projet.

    ``company`` n'est jamais exposée : elle est posée côté serveur. Le ``projet``
    reçu est validé comme appartenant à la société de l'utilisateur.
    """
    projet_code = serializers.CharField(source='projet.code', read_only=True)
    type_phase_display = serializers.CharField(
        source='get_type_phase_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = PhaseProjet
        fields = [
            'id', 'projet', 'projet_code', 'type_phase', 'type_phase_display',
            'libelle', 'ordre', 'date_debut_prevue', 'date_fin_prevue',
            'date_debut_reelle', 'date_fin_reelle', 'statut', 'statut_display',
            'avancement_pct', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_projet(self, value):
        return _meme_societe(self, value, 'Projet')

    def validate_avancement_pct(self, value):
        if value is not None and not (0 <= value <= 100):
            raise serializers.ValidationError(
                'L’avancement doit être compris entre 0 et 100.')
        return value


class TacheSerializer(serializers.ModelSerializer):
    """Tâche (WBS) d'un projet, avec sous-tâches auto-référentes.

    ``company`` n'est jamais exposée : elle est posée côté serveur. Les FK reçus
    (``projet``, ``phase``, ``parent``) sont validés comme appartenant à la
    société de l'utilisateur ; un parent doit en outre cibler le MÊME projet (et
    une tâche ne peut être son propre parent).
    """
    projet_code = serializers.CharField(source='projet.code', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    # Nombre de sous-tâches directes (lecture seule, pratique pour l'UI).
    nb_sous_taches = serializers.IntegerField(
        source='sous_taches.count', read_only=True)

    class Meta:
        model = Tache
        fields = [
            'id', 'projet', 'projet_code', 'phase', 'parent', 'code_wbs',
            'libelle', 'description', 'ordre', 'statut', 'statut_display',
            'avancement_pct', 'charge_estimee', 'date_debut_prevue',
            'date_fin_prevue', 'nb_sous_taches', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_projet(self, value):
        return _meme_societe(self, value, 'Projet')

    def validate_phase(self, value):
        return _meme_societe(self, value, 'Phase')

    def validate_parent(self, value):
        return _meme_societe(self, value, 'Tâche parente')

    def validate_avancement_pct(self, value):
        if value is not None and not (0 <= value <= 100):
            raise serializers.ValidationError(
                'L’avancement doit être compris entre 0 et 100.')
        return value

    def validate(self, attrs):
        # ``projet`` peut être absent d'un PATCH partiel : on retombe sur
        # l'instance courante pour les contrôles de cohérence.
        projet = attrs.get('projet') or getattr(self.instance, 'projet', None)
        parent = attrs.get('parent', getattr(self.instance, 'parent', None))
        phase = attrs.get('phase', getattr(self.instance, 'phase', None))
        if parent is not None:
            if self.instance is not None and parent.id == self.instance.id:
                raise serializers.ValidationError(
                    {'parent': 'Une tâche ne peut pas être sa propre parente.'})
            if projet is not None and parent.projet_id != projet.id:
                raise serializers.ValidationError(
                    {'parent': 'La tâche parente doit appartenir au même '
                               'projet.'})
        if phase is not None and projet is not None \
                and phase.projet_id != projet.id:
            raise serializers.ValidationError(
                {'phase': 'La phase doit appartenir au même projet.'})
        return attrs


class ProjetLienSerializer(serializers.ModelSerializer):
    """Lien projet → document métier d'une autre app (référence lâche typée).

    ``company`` n'est jamais exposée : elle est posée côté serveur. Le ``projet``
    reçu est validé comme appartenant à la société de l'utilisateur.
    """
    projet_code = serializers.CharField(source='projet.code', read_only=True)
    type_cible_display = serializers.CharField(
        source='get_type_cible_display', read_only=True)

    class Meta:
        model = ProjetLien
        fields = [
            'id', 'projet', 'projet_code', 'type_cible', 'type_cible_display',
            'cible_id', 'libelle', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_projet(self, value):
        return _meme_societe(self, value, 'Projet')


class DependanceTacheSerializer(serializers.ModelSerializer):
    """Dépendance de planning entre deux tâches (FS/SS/FF/SF + lag).

    ``company`` n'est jamais exposée : elle est posée côté serveur. Les deux FK
    reçus (``predecesseur``, ``successeur``) sont validés même-société ; le
    ``validate`` global refuse en plus l'auto-dépendance, une dépendance entre
    tâches de projets DIFFÉRENTS, et un cycle DIRECT (l'arête inverse existe
    déjà). Mêmes garde-fous que ``DependanceTache.clean`` — exposés ici en 400.
    """
    type_dependance_display = serializers.CharField(
        source='get_type_dependance_display', read_only=True)
    projet = serializers.IntegerField(
        source='predecesseur.projet_id', read_only=True)

    class Meta:
        model = DependanceTache
        fields = [
            'id', 'predecesseur', 'successeur', 'type_dependance',
            'type_dependance_display', 'lag', 'projet', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_predecesseur(self, value):
        return _meme_societe(self, value, 'Tâche prédécesseur')

    def validate_successeur(self, value):
        return _meme_societe(self, value, 'Tâche successeur')

    def validate(self, attrs):
        # ``predecesseur``/``successeur`` peuvent manquer d'un PATCH partiel : on
        # retombe sur l'instance courante pour les contrôles de cohérence.
        pred = attrs.get(
            'predecesseur', getattr(self.instance, 'predecesseur', None))
        succ = attrs.get(
            'successeur', getattr(self.instance, 'successeur', None))
        if pred is None or succ is None:
            return attrs
        if pred.id == succ.id:
            raise serializers.ValidationError(
                {'successeur': 'Une tâche ne peut pas dépendre d’elle-même.'})
        if pred.projet_id != succ.projet_id:
            raise serializers.ValidationError(
                {'successeur': 'Le prédécesseur et le successeur doivent '
                               'appartenir au même projet.'})
        inverse = DependanceTache.objects.filter(
            predecesseur_id=succ.id, successeur_id=pred.id)
        if self.instance is not None:
            inverse = inverse.exclude(pk=self.instance.pk)
        if inverse.exists():
            raise serializers.ValidationError(
                {'successeur': 'Dépendance cyclique : l’arête inverse existe '
                               'déjà.'})
        return attrs
