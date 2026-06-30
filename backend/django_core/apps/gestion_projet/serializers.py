"""Sérialiseurs de la Gestion de projet.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). Tous les FK reçus sont validés comme
appartenant à la société de l'utilisateur.
"""
from rest_framework import serializers

from .models import (
    ActionProjet,
    AffectationRessource,
    BaselinePlanning,
    ClotureProjet,
    CommentaireProjet,
    CompteRenduReunion,
    DocumentProjet,
    BaselineTache,
    BudgetProjet,
    CalendrierProjet,
    DependanceTache,
    Equipe,
    Indisponibilite,
    Jalon,
    JourFerie,
    LigneBudgetProjet,
    ModeleProjet,
    ModeleTache,
    PhaseProjet,
    PortailProjetToken,
    Projet,
    ProjetActivity,
    ProjetChantier,
    ProjetLien,
    RessourceProfil,
    Risque,
    SousTraitant,
    LotSousTraitance,
    Tache,
    Timesheet,
    VersionDocument,
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


class JalonSerializer(serializers.ModelSerializer):
    """Jalon (milestone) d'un projet, éventuellement de FACTURATION.

    ``company`` n'est jamais exposée : elle est posée côté serveur. Les FK reçus
    (``projet``, ``phase``, ``tache``) sont validés comme appartenant à la
    société de l'utilisateur ; une phase/tâche reçue doit en outre cibler le
    MÊME projet. Le ``facturation_pct`` est borné à [0, 100] (en plus du
    validateur du modèle).
    """
    projet_code = serializers.CharField(source='projet.code', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = Jalon
        fields = [
            'id', 'projet', 'projet_code', 'phase', 'tache', 'libelle',
            'description', 'date_prevue', 'date_reelle', 'statut',
            'statut_display', 'facturation_pct', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_projet(self, value):
        return _meme_societe(self, value, 'Projet')

    def validate_phase(self, value):
        return _meme_societe(self, value, 'Phase')

    def validate_tache(self, value):
        return _meme_societe(self, value, 'Tâche')

    def validate_facturation_pct(self, value):
        if value is not None and not (0 <= value <= 100):
            raise serializers.ValidationError(
                'Le pourcentage de facturation doit être compris entre 0 et '
                '100.')
        return value

    def validate(self, attrs):
        # ``projet`` peut manquer d'un PATCH partiel : on retombe sur l'instance
        # courante pour les contrôles de cohérence FK.
        projet = attrs.get('projet') or getattr(self.instance, 'projet', None)
        phase = attrs.get('phase', getattr(self.instance, 'phase', None))
        tache = attrs.get('tache', getattr(self.instance, 'tache', None))
        if phase is not None and projet is not None \
                and phase.projet_id != projet.id:
            raise serializers.ValidationError(
                {'phase': 'La phase doit appartenir au même projet.'})
        if tache is not None and projet is not None \
                and tache.projet_id != projet.id:
            raise serializers.ValidationError(
                {'tache': 'La tâche doit appartenir au même projet.'})
        return attrs


class JourFerieSerializer(serializers.ModelSerializer):
    """Jour férié (chômé) d'un calendrier de projet.

    ``company`` n'est jamais exposée : elle est posée côté serveur. Le
    ``calendrier`` reçu est validé comme appartenant à la société de
    l'utilisateur.
    """
    class Meta:
        model = JourFerie
        fields = [
            'id', 'calendrier', 'date', 'libelle', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_calendrier(self, value):
        return _meme_societe(self, value, 'Calendrier')


class CalendrierProjetSerializer(serializers.ModelSerializer):
    """Calendrier ouvré d'un projet (jours travaillés + fériés imbriqués).

    ``company`` n'est jamais exposée : elle est posée côté serveur. Le ``projet``
    reçu est validé comme appartenant à la société de l'utilisateur ; un seul
    calendrier par projet (OneToOne). Les jours fériés sont exposés en LECTURE
    seule (créés via leur propre endpoint).
    """
    projet_code = serializers.CharField(source='projet.code', read_only=True)
    jours_feries = JourFerieSerializer(many=True, read_only=True)

    class Meta:
        model = CalendrierProjet
        fields = [
            'id', 'projet', 'projet_code', 'lundi', 'mardi', 'mercredi',
            'jeudi', 'vendredi', 'samedi', 'dimanche', 'jours_feries',
            'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_projet(self, value):
        return _meme_societe(self, value, 'Projet')


class RessourceProfilSerializer(serializers.ModelSerializer):
    """Profil de ressource interne pour le planning de projet (PROJ15).

    ``company`` n'est jamais exposée : elle est posée côté serveur. Le ``user``
    reçu (optionnel) est validé comme appartenant à la société de l'utilisateur.
    ``cout_horaire`` est un champ INTERNE de pilotage : il reste lisible sur cet
    écran de gestion de projet mais ne doit jamais apparaître dans un PDF client.
    """
    class Meta:
        model = RessourceProfil
        fields = [
            'id', 'user', 'nom', 'role', 'competences', 'cout_horaire',
            'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']


class EquipeSerializer(serializers.ModelSerializer):
    """Équipe de ressources pour le planning de projet (PROJ15).

    ``company`` n'est jamais exposée : elle est posée côté serveur. Les
    ``membres`` reçus sont validés comme appartenant à la société de
    l'utilisateur. Les détails de chaque membre sont exposés en lecture seule
    via ``membres_detail``.
    """
    membres_detail = RessourceProfilSerializer(
        source='membres', many=True, read_only=True)

    class Meta:
        model = Equipe
        fields = [
            'id', 'nom', 'description', 'membres', 'membres_detail',
            'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_membres(self, value):
        request = self.context.get('request')
        if request is not None:
            for membre in value:
                if membre.company_id != request.user.company_id:
                    raise serializers.ValidationError(
                        f'Ressource #{membre.id} inconnue.')
        return value


class BaselineTacheSerializer(serializers.ModelSerializer):
    """Ligne figée d'une baseline (lecture seule — créée par le service)."""
    class Meta:
        model = BaselineTache
        fields = [
            'id', 'baseline', 'tache', 'tache_libelle', 'tache_code_wbs',
            'date_debut_prevue', 'date_fin_prevue', 'charge_estimee',
            'date_creation',
        ]
        read_only_fields = fields


class BaselinePlanningSerializer(serializers.ModelSerializer):
    """Baseline de planning d'un projet (snapshot figé).

    ``company`` et ``auteur`` ne sont jamais exposés en écriture (posés côté
    serveur). Le ``projet`` reçu est validé même-société ; les lignes figées sont
    exposées en lecture seule (le snapshot est pris par l'action ``baseline``).
    """
    projet_code = serializers.CharField(source='projet.code', read_only=True)
    auteur_nom = serializers.CharField(
        source='auteur.username', read_only=True, default='')
    nb_lignes = serializers.IntegerField(
        source='lignes.count', read_only=True)

    class Meta:
        model = BaselinePlanning
        fields = [
            'id', 'projet', 'projet_code', 'libelle', 'auteur', 'auteur_nom',
            'nb_lignes', 'date_creation',
        ]
        read_only_fields = ['auteur', 'date_creation']

    def validate_projet(self, value):
        return _meme_societe(self, value, 'Projet')


class AffectationRessourceSerializer(serializers.ModelSerializer):
    """Affectation d'une ressource (personne, equipe ou actif) a une tache.

    ``company`` n'est jamais exposee en ecriture : elle est posee cote serveur
    par le ``TenantMixin``. Les FK recus (``tache``, ``ressource``, ``equipe``)
    sont valides comme appartenant a la societe de l'utilisateur.

    EXACTEMENT UN des trois vecteurs doit etre fourni :
        - ``ressource``                 : FK RessourceProfil
        - ``equipe``                    : FK Equipe
        - ``actif_type`` + ``actif_id`` : reference lache flotte
    """
    tache_libelle = serializers.CharField(
        source='tache.libelle', read_only=True)
    ressource_nom = serializers.CharField(
        source='ressource.nom', read_only=True, default=None)
    equipe_nom = serializers.CharField(
        source='equipe.nom', read_only=True, default=None)

    class Meta:
        model = AffectationRessource
        fields = [
            'id', 'tache', 'tache_libelle',
            'ressource', 'ressource_nom',
            'equipe', 'equipe_nom',
            'actif_type', 'actif_id',
            'date_debut', 'date_fin',
            'charge_jours', 'quantite', 'note',
            'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_tache(self, value):
        return _meme_societe(self, value, 'Tache')

    def validate_ressource(self, value):
        return _meme_societe(self, value, 'Ressource')

    def validate_equipe(self, value):
        return _meme_societe(self, value, 'Equipe')

    def validate(self, attrs):
        # Recupere les valeurs depuis attrs ou l'instance courante (PATCH partiel).
        ressource = attrs.get(
            'ressource', getattr(self.instance, 'ressource', None))
        equipe = attrs.get(
            'equipe', getattr(self.instance, 'equipe', None))
        actif_type = attrs.get(
            'actif_type', getattr(self.instance, 'actif_type', ''))
        actif_id = attrs.get(
            'actif_id', getattr(self.instance, 'actif_id', None))

        has_ressource = ressource is not None
        has_equipe = equipe is not None
        has_actif = bool(actif_type) and actif_id is not None
        vecteurs = sum([has_ressource, has_equipe, has_actif])

        if vecteurs == 0:
            raise serializers.ValidationError(
                "Exactement un vecteur de ressource doit etre renseigne "
                "(ressource, equipe ou actif materiel).")
        if vecteurs > 1:
            raise serializers.ValidationError(
                "Un seul vecteur de ressource a la fois : ressource, equipe "
                "ou actif materiel.")

        # Validation date_fin >= date_debut.
        date_debut = attrs.get(
            'date_debut', getattr(self.instance, 'date_debut', None))
        date_fin = attrs.get(
            'date_fin', getattr(self.instance, 'date_fin', None))
        if date_debut and date_fin and date_fin < date_debut:
            raise serializers.ValidationError(
                {'date_fin': "La date de fin ne peut pas etre anterieure "
                             "a la date de debut."})
        return attrs


class IndisponibiliteSerializer(serializers.ModelSerializer):
    """Indisponibilite d'une ressource (conge / formation / arret) -- PROJ17.

    ``company`` n'est jamais exposee en ecriture : elle est posee cote serveur
    par le ``TenantMixin``. La ``ressource`` recue est validee comme appartenant
    a la societe de l'utilisateur. La periode est inclusive des deux bornes ;
    ``date_fin`` ne peut pas etre anterieure a ``date_debut``.
    """
    ressource_nom = serializers.CharField(
        source='ressource.nom', read_only=True)

    class Meta:
        model = Indisponibilite
        fields = [
            'id', 'ressource', 'ressource_nom',
            'type_indispo',
            'date_debut', 'date_fin', 'motif',
            'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_ressource(self, value):
        return _meme_societe(self, value, 'Ressource')

    def validate(self, attrs):
        date_debut = attrs.get(
            'date_debut', getattr(self.instance, 'date_debut', None))
        date_fin = attrs.get(
            'date_fin', getattr(self.instance, 'date_fin', None))
        if date_debut and date_fin and date_fin < date_debut:
            raise serializers.ValidationError(
                {'date_fin': "La date de fin ne peut pas etre anterieure "
                             "a la date de debut."})
        return attrs


class BudgetProjetSerializer(serializers.ModelSerializer):
    """Budget prévisionnel d'un projet (en-tête).

    ``company`` n'est jamais exposée ; le ``projet`` reçu est validé
    même-société. Le total ventilé par catégorie est lecture seule, calculé
    par le sélecteur ``budget_total``.
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    projet_code = serializers.CharField(source='projet.code', read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = BudgetProjet
        fields = [
            'id', 'projet', 'projet_code', 'libelle', 'version', 'statut',
            'statut_display', 'devise', 'total', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_projet(self, value):
        return _meme_societe(self, value, 'Projet')

    def get_total(self, obj):
        from . import selectors
        agg = selectors.budget_total(obj)
        return {
            'total': str(agg['total']),
            'par_categorie': {
                cat: str(montant)
                for cat, montant in agg['par_categorie'].items()
            },
            'nb_lignes': agg['nb_lignes'],
        }


class LigneBudgetProjetSerializer(serializers.ModelSerializer):
    """Ligne d'un budget projet (catégorie + montant prévu).

    ``company`` n'est jamais exposée ; le ``budget`` reçu est validé
    même-société. ``quantite`` et ``pu`` sont optionnels et indicatifs.
    """
    categorie_display = serializers.CharField(
        source='get_categorie_display', read_only=True)

    class Meta:
        model = LigneBudgetProjet
        fields = [
            'id', 'budget', 'categorie', 'categorie_display', 'libelle',
            'quantite', 'pu', 'montant_prevu', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_budget(self, value):
        return _meme_societe(self, value, 'Budget')


class TimesheetSerializer(serializers.ModelSerializer):
    """Feuille de temps interne imputée à un projet (PROJ24).

    ``company`` n'est jamais exposée : elle est posée côté serveur. Les FK reçus
    (``projet``, ``tache``, ``phase``, ``ressource``) sont validés même-société ;
    une tâche / phase reçue doit en outre cibler le MÊME projet. ``cout`` est
    calculé côté serveur (``heures`` × ``cout_horaire`` interne de la ressource)
    et exposé en LECTURE seule — jamais lu du corps de requête.
    """
    projet_code = serializers.CharField(source='projet.code', read_only=True)
    ressource_nom = serializers.CharField(
        source='ressource.nom', read_only=True)

    class Meta:
        model = Timesheet
        fields = [
            'id', 'projet', 'projet_code', 'tache', 'phase', 'ressource',
            'ressource_nom', 'date', 'heures', 'cout', 'commentaire',
            'date_creation',
        ]
        read_only_fields = ['cout', 'date_creation']

    def validate_projet(self, value):
        return _meme_societe(self, value, 'Projet')

    def validate_tache(self, value):
        return _meme_societe(self, value, 'Tâche')

    def validate_phase(self, value):
        return _meme_societe(self, value, 'Phase')

    def validate_ressource(self, value):
        return _meme_societe(self, value, 'Ressource')

    def validate_heures(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                'Les heures ne peuvent pas être négatives.')
        return value

    def validate(self, attrs):
        # ``projet`` peut manquer d'un PATCH partiel : on retombe sur l'instance.
        projet = attrs.get('projet') or getattr(self.instance, 'projet', None)
        tache = attrs.get('tache', getattr(self.instance, 'tache', None))
        phase = attrs.get('phase', getattr(self.instance, 'phase', None))
        if tache is not None and projet is not None \
                and tache.projet_id != projet.id:
            raise serializers.ValidationError(
                {'tache': 'La tâche doit appartenir au même projet.'})
        if phase is not None and projet is not None \
                and phase.projet_id != projet.id:
            raise serializers.ValidationError(
                {'phase': 'La phase doit appartenir au même projet.'})
        return attrs


class RisqueSerializer(serializers.ModelSerializer):
    """Entrée du registre des risques d'un projet (PROJ30).

    ``company`` n'est jamais exposée : elle est posée côté serveur. Le ``projet``
    et le ``proprietaire`` (optionnel) reçus sont validés même-société. La
    ``criticite`` est CALCULÉE côté serveur (probabilité × impact) et exposée en
    LECTURE seule — jamais lue du corps de requête. Probabilité et impact sont
    bornés à [1, 5].
    """
    projet_code = serializers.CharField(source='projet.code', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    categorie_display = serializers.CharField(
        source='get_categorie_display', read_only=True)

    class Meta:
        model = Risque
        fields = [
            'id', 'projet', 'projet_code', 'libelle', 'description',
            'categorie', 'categorie_display', 'probabilite', 'impact',
            'criticite', 'statut', 'statut_display', 'mitigation',
            'proprietaire', 'date_creation',
        ]
        read_only_fields = ['criticite', 'date_creation']

    def validate_projet(self, value):
        return _meme_societe(self, value, 'Projet')

    def _borne_1_5(self, value, champ):
        if value is not None and not (1 <= value <= 5):
            raise serializers.ValidationError(
                f'{champ} doit être compris entre 1 et 5.')
        return value

    def validate_probabilite(self, value):
        return self._borne_1_5(value, 'La probabilité')

    def validate_impact(self, value):
        return self._borne_1_5(value, "L'impact")

    def validate_proprietaire(self, value):
        return _meme_societe(self, value, 'Propriétaire')


class ActionProjetSerializer(serializers.ModelSerializer):
    """Entrée du registre d'actions d'un projet (PROJ31).

    ``company`` n'est jamais exposée : elle est posée côté serveur. Le ``projet``,
    le ``risque`` (optionnel) et le ``responsable`` (optionnel) reçus sont
    validés même-société ; un risque lié doit en outre cibler le MÊME projet.
    """
    projet_code = serializers.CharField(source='projet.code', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    priorite_display = serializers.CharField(
        source='get_priorite_display', read_only=True)

    class Meta:
        model = ActionProjet
        fields = [
            'id', 'projet', 'projet_code', 'risque', 'libelle', 'description',
            'statut', 'statut_display', 'priorite', 'priorite_display',
            'responsable', 'echeance', 'date_cloture', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_projet(self, value):
        return _meme_societe(self, value, 'Projet')

    def validate_risque(self, value):
        return _meme_societe(self, value, 'Risque')

    def validate_responsable(self, value):
        return _meme_societe(self, value, 'Responsable')

    def validate(self, attrs):
        projet = attrs.get('projet') or getattr(self.instance, 'projet', None)
        risque = attrs.get('risque', getattr(self.instance, 'risque', None))
        if risque is not None and projet is not None \
                and risque.projet_id != projet.id:
            raise serializers.ValidationError(
                {'risque': 'Le risque lié doit appartenir au même projet.'})
        return attrs


class CompteRenduReunionSerializer(serializers.ModelSerializer):
    """Compte-rendu de réunion de chantier d'un projet (PROJ32).

    ``company`` n'est jamais exposée : elle est posée côté serveur ; le
    ``redacteur`` aussi (lecture seule). Le ``projet`` reçu est validé
    même-société. Le ``chantier_id`` est une référence LÂCHE (aucun FK dur).
    """
    projet_code = serializers.CharField(source='projet.code', read_only=True)
    redacteur_nom = serializers.CharField(
        source='redacteur.username', read_only=True, default='')

    class Meta:
        model = CompteRenduReunion
        fields = [
            'id', 'projet', 'projet_code', 'chantier_id', 'titre',
            'date_reunion', 'lieu', 'participants', 'ordre_du_jour',
            'decisions', 'points_bloquants', 'date_prochaine_reunion',
            'redacteur', 'redacteur_nom', 'date_creation',
        ]
        read_only_fields = ['redacteur', 'date_creation']

    def validate_projet(self, value):
        return _meme_societe(self, value, 'Projet')


class VersionDocumentSerializer(serializers.ModelSerializer):
    """Version (révision) d'un document projet (PROJ33) — lecture seule.

    Le ``version`` et l'``auteur`` sont posés côté serveur par le service de
    dépôt ; ce sérialiseur n'expose donc que la lecture des révisions (le dépôt
    se fait via l'action ``documents/<id>/deposer/``).
    """
    auteur_nom = serializers.CharField(
        source='auteur.username', read_only=True, default='')

    class Meta:
        model = VersionDocument
        fields = [
            'id', 'document', 'version', 'fichier', 'commentaire', 'auteur',
            'auteur_nom', 'date_creation',
        ]
        read_only_fields = fields


class DocumentProjetSerializer(serializers.ModelSerializer):
    """Document logique VERSIONNÉ d'un projet (PROJ33).

    ``company`` n'est jamais exposée : elle est posée côté serveur. Le ``projet``
    reçu est validé même-société. ``derniere_version`` est posée côté serveur
    (cache du dernier dépôt) — lecture seule. Les versions sont exposées en
    lecture seule (le dépôt se fait via ``documents/<id>/deposer/``).
    """
    projet_code = serializers.CharField(source='projet.code', read_only=True)
    type_doc_display = serializers.CharField(
        source='get_type_doc_display', read_only=True)
    versions = VersionDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = DocumentProjet
        fields = [
            'id', 'projet', 'projet_code', 'nom', 'type_doc',
            'type_doc_display', 'description', 'derniere_version', 'versions',
            'date_creation',
        ]
        read_only_fields = ['derniere_version', 'date_creation']

    def validate_projet(self, value):
        return _meme_societe(self, value, 'Projet')


class CommentaireProjetSerializer(serializers.ModelSerializer):
    """Commentaire avec @mentions sur un objet d'un projet (PROJ34).

    ``company`` et ``auteur`` sont posés côté serveur (lecture seule). Le
    ``projet`` reçu est validé même-société ; les utilisateurs ``mentions``
    reçus sont restreints à la MÊME société. La cible précise est une référence
    LÂCHE typée ``(cible_type, cible_id)``.
    """
    projet_code = serializers.CharField(source='projet.code', read_only=True)
    auteur_nom = serializers.CharField(
        source='auteur.username', read_only=True, default='')
    cible_type_display = serializers.CharField(
        source='get_cible_type_display', read_only=True)

    class Meta:
        model = CommentaireProjet
        fields = [
            'id', 'projet', 'projet_code', 'cible_type', 'cible_type_display',
            'cible_id', 'texte', 'auteur', 'auteur_nom', 'mentions',
            'date_creation',
        ]
        read_only_fields = ['auteur', 'date_creation']

    def validate_projet(self, value):
        return _meme_societe(self, value, 'Projet')

    def validate_mentions(self, value):
        request = self.context.get('request')
        if request is not None:
            for membre in value:
                if membre.company_id != request.user.company_id:
                    raise serializers.ValidationError(
                        f'Utilisateur #{membre.id} inconnu.')
        return value


class ModeleTacheSerializer(serializers.ModelSerializer):
    """Tâche-type d'un modèle de projet (PROJ35).

    ``company`` n'est jamais exposée : elle est posée côté serveur. Le ``modele``
    reçu est validé même-société.
    """
    type_phase_display = serializers.CharField(
        source='get_type_phase_display', read_only=True)

    class Meta:
        model = ModeleTache
        fields = [
            'id', 'modele', 'type_phase', 'type_phase_display', 'code_wbs',
            'libelle', 'ordre', 'charge_estimee', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_modele(self, value):
        return _meme_societe(self, value, 'Modèle')


class ModeleProjetSerializer(serializers.ModelSerializer):
    """Modèle (template) de projet par type d'installation (PROJ35).

    ``company`` n'est jamais exposée : elle est posée côté serveur. Les
    tâches-types sont exposées en lecture seule (créées via leur propre endpoint
    ``modele-taches/``). L'instanciation sur un projet se fait via
    ``modeles/<id>/instancier/``.
    """
    type_installation_display = serializers.CharField(
        source='get_type_installation_display', read_only=True)
    taches = ModeleTacheSerializer(many=True, read_only=True)
    nb_taches = serializers.IntegerField(
        source='taches.count', read_only=True)

    class Meta:
        model = ModeleProjet
        fields = [
            'id', 'nom', 'type_installation', 'type_installation_display',
            'description', 'actif', 'taches', 'nb_taches', 'date_creation',
        ]
        read_only_fields = ['date_creation']


class PortailProjetTokenSerializer(serializers.ModelSerializer):
    """Jeton d'accès au portail d'avancement client (PROJ37).

    ``company`` n'est jamais exposée : elle est posée côté serveur. Le ``token``
    est GÉNÉRÉ côté serveur (lecture seule). Le ``projet`` reçu est validé
    même-société (un seul jeton par projet — OneToOne).
    """
    projet_code = serializers.CharField(source='projet.code', read_only=True)

    class Meta:
        model = PortailProjetToken
        fields = [
            'id', 'projet', 'projet_code', 'token', 'actif', 'date_creation',
        ]
        read_only_fields = ['token', 'date_creation']

    def validate_projet(self, value):
        return _meme_societe(self, value, 'Projet')


class SousTraitantSerializer(serializers.ModelSerializer):
    """Sous-traitant du carnet d'adresses (PROJ38).

    ``company`` n'est jamais exposée : elle est posée côté serveur.
    """
    class Meta:
        model = SousTraitant
        fields = [
            'id', 'nom', 'specialite', 'contact', 'telephone', 'email',
            'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']


class LotSousTraitanceSerializer(serializers.ModelSerializer):
    """Lot confié à un sous-traitant sur un projet (PROJ38).

    ``company`` n'est jamais exposée : elle est posée côté serveur. Le ``projet``
    et le ``sous_traitant`` reçus sont validés même-société. Le ``montant`` est
    un coût INTERNE — jamais exposé au client.
    """
    projet_code = serializers.CharField(source='projet.code', read_only=True)
    sous_traitant_nom = serializers.CharField(
        source='sous_traitant.nom', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = LotSousTraitance
        fields = [
            'id', 'projet', 'projet_code', 'sous_traitant',
            'sous_traitant_nom', 'libelle', 'description', 'montant', 'statut',
            'statut_display', 'date_debut', 'date_fin', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_projet(self, value):
        return _meme_societe(self, value, 'Projet')

    def validate_sous_traitant(self, value):
        return _meme_societe(self, value, 'Sous-traitant')


class ClotureProjetSerializer(serializers.ModelSerializer):
    """Clôture de projet + retour d'expérience (PROJ38).

    ``company`` et ``cloture_par`` sont posés côté serveur (lecture seule). Le
    ``projet`` reçu est validé même-société. La clôture se prend de préférence
    via l'action ``projets/<id>/cloturer/`` (transition serveur + REX) ; ce
    sérialiseur sert l'affichage et l'édition du REX.
    """
    projet_code = serializers.CharField(source='projet.code', read_only=True)
    cloture_par_nom = serializers.CharField(
        source='cloture_par.username', read_only=True, default='')

    class Meta:
        model = ClotureProjet
        fields = [
            'id', 'projet', 'projet_code', 'date_cloture', 'date_reception',
            'points_positifs', 'points_amelioration', 'recommandations',
            'cloture_par', 'cloture_par_nom', 'date_creation',
        ]
        read_only_fields = ['cloture_par', 'date_creation']

    def validate_projet(self, value):
        return _meme_societe(self, value, 'Projet')
