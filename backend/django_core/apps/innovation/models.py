"""Modèles du module Innovation & boucle de feedback produit (`apps.innovation`).

Trois étages (voir docs/new_tasks_plan.md, Groupe NTIDE) :

1. Boîte à idées interne — ``Idee`` (NTIDE1), suivi de ``VoteIdee`` (NTIDE2).
2. Campagnes d'innovation ciblées — ``CampagneInnovation`` (NTIDE25+).
3. Canal feedback produit in-app — hors périmètre de ce lot (NTIDE36+).

Multi-société : tous les modèles héritent de ``core.models.TenantModel``
(FK ``company`` + ``created_at``/``updated_at``), jamais une FK ``company``
à la main (SCA4).
"""
from django.conf import settings
from django.db import models

from core.models import TenantModel

# NTIDE25/26 — rôles proposables comme cible de campagne QUAND le référentiel
# Departement (NTFPA1, ``apps.fpa``) n'est PAS réutilisé : même liste que le
# dropdown de repli du singleton ``InnovationSettings.segment_defaut``
# (NTIDE7). Jamais un import cross-app d'``apps.fpa``/``apps.rh`` — un nom de
# département reste une chaîne opaque, au même titre qu'un nom de rôle
# (cf. ``CampagneInnovation.cible_departement``/``segment``).
ROLES_CIBLABLES = ['Technicien', 'Commercial', 'Directeur']


class Idee(TenantModel):
    """Une idée proposée par un collaborateur (NTIDE1).

    ``linked_type``/``linked_id`` forment une référence OPAQUE (string-FK)
    vers un devis/ticket SAV/chantier — jamais un import cross-app des
    modèles ``ventes``/``sav``/``installations``.
    """

    class Statut(models.TextChoices):
        OUVERT = 'ouvert', 'Ouvert'
        EXAMINEE = 'examinee', 'Examinée'
        RETENUE = 'retenue', 'Retenue'
        REALISEE = 'realisee', 'Réalisée'
        FERMEE = 'fermee', 'Fermée'

    # Statuts qui ne sont plus modifiables (terminal du point de vue de la
    # machine à états des actions NTIDE5 — cf. ``apps.innovation.views``).
    STATUTS_ACTIFS = (Statut.OUVERT, Statut.EXAMINEE, Statut.RETENUE)

    class LinkedType(models.TextChoices):
        DEVIS = 'devis', 'Devis'
        TICKET = 'ticket', 'Ticket SAV'
        CHANTIER = 'chantier', 'Chantier'

    # Redéclaré à l'identique (ARC1) : related_name explicite dédié.
    company = models.ForeignKey(
        'authentication.Company',
        # on_delete: idées scopées société — disparaissent avec elle (nettoyage tenant standard).
        on_delete=models.CASCADE,
        related_name='innovation_idees', verbose_name='Société')
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='idees_proposees',
        verbose_name='Auteur')
    titre = models.CharField(max_length=255, verbose_name='Titre')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    # Libre (ex. « SAV », « Devis », « Stock »…) — PAS une liste fermée :
    # NTIDE10 propose les 5 valeurs les plus fréquentes en autocomplétion.
    contexte = models.CharField(
        max_length=80, blank=True, default='', verbose_name='Contexte')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.OUVERT,
        verbose_name='Statut')
    # Dénormalisé : maintenu par VoteIdee.save()/delete() (NTIDE2), jamais
    # recalculé à la lecture — évite un COUNT() sur chaque ligne de liste.
    votes_count = models.PositiveIntegerField(
        default=0, verbose_name='Votes (dénormalisé)')
    linked_type = models.CharField(
        max_length=10, choices=LinkedType.choices, blank=True, default='',
        verbose_name='Type lié (devis/ticket/chantier)')
    linked_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID lié (opaque)')
    # NTIDE18 — « Enregistrer en brouillon » : tant que True, l'idée reste
    # interne à son auteur (invisible des autres dans les listes/le tableau
    # de bord, cf. ``IdeeViewSet.get_queryset``/``selectors``) ; passe à
    # False quand l'auteur clique « Publier ».
    draft = models.BooleanField(default=False, verbose_name='Brouillon')
    # NTIDE19 — modération de contenu : le palier Directeur/Responsable peut
    # « masquer » une idée SANS la supprimer (action ``masquer``). Une idée
    # masquée disparaît des listes normales mais reste consultable en admin
    # (``?include_archived=1``, réservé au même palier).
    archived = models.BooleanField(
        default=False, verbose_name='Masquée (modération)')

    class Meta:
        verbose_name = 'Idée'
        verbose_name_plural = 'Idées'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='innovation_idee_co_statut'),
            models.Index(fields=['company', 'contexte'],
                         name='innovation_idee_co_ctx'),
        ]

    def __str__(self):
        return self.titre


class VoteIdee(TenantModel):
    """Un vote d'un utilisateur pour une idée (NTIDE2) — unique par (idee,
    votant). L'auteur de l'idée ne peut pas voter pour sa propre idée (règle
    appliquée côté vue, cf. ``apps.innovation.views.VoteIdeeViewSet``)."""

    company = models.ForeignKey(
        'authentication.Company',
        # on_delete: votes scopés société — disparaissent avec elle (nettoyage tenant standard).
        on_delete=models.CASCADE,
        related_name='innovation_votes', verbose_name='Société')
    idee = models.ForeignKey(
        Idee,
        # on_delete: un vote n'existe que rattaché à son idée (composition).
        on_delete=models.CASCADE,
        related_name='votes', verbose_name='Idée')
    votant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        # on_delete: vote sans valeur historique isolée — disparaît avec le compte votant.
        on_delete=models.CASCADE,
        related_name='votes_idees', verbose_name='Votant')

    class Meta:
        verbose_name = 'Vote idée'
        verbose_name_plural = 'Votes idée'
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['idee', 'votant'],
                name='innovation_vote_unique_idee_votant'),
        ]

    def __str__(self):
        return f'{self.votant_id} → idée {self.idee_id}'


class InnovationSettings(TenantModel):
    """Paramètres du tab Paramètres → Avancé « Campagnes innovation »
    (NTIDE7). Une ligne par société (singleton, ``OneToOneField``, pattern
    ``parametres.CompanyProfile``)."""

    class ThemeCouleur(models.TextChoices):
        PRIMARY = 'primary', 'Primaire'
        SUCCESS = 'success', 'Succès'
        WARNING = 'warning', 'Avertissement'
        INFO = 'info', 'Info'
        DESTRUCTIVE = 'destructive', 'Destructive'

    # Redéclaré en OneToOne (ARC1 autorise la redéclaration du champ hérité) :
    # une seule ligne de paramètres par société.
    company = models.OneToOneField(
        'authentication.Company',
        # on_delete: paramètres scopés société — disparaissent avec elle (nettoyage tenant standard).
        on_delete=models.CASCADE,
        related_name='innovation_settings', verbose_name='Société')
    campagnes_activees = models.BooleanField(
        default=False, verbose_name='Campagnes activées')
    # Segment par défaut — nom de Departement (NTFPA1) si bâti, sinon un des
    # rôles ['Technicien', 'Commercial', 'Directeur'] (texte libre, dropdown
    # côté frontend). Vide = pas de segment par défaut.
    segment_defaut = models.CharField(
        max_length=80, blank=True, default='', verbose_name='Segment par défaut')
    theme_couleur_cta = models.CharField(
        max_length=12, choices=ThemeCouleur.choices,
        default=ThemeCouleur.PRIMARY, verbose_name='Thème couleur du CTA')
    message_relance = models.TextField(
        blank=True, default='', verbose_name='Message de relance')
    # NTIDE16 — nombre de votes qui déclenche UNE notification (in-app +
    # email via ``notify()``) à l'auteur de l'idée (``services._maybe_
    # notify_seuil_votes``, déclenchée une seule fois, exactement au moment
    # où le seuil est atteint — jamais répétée à chaque vote suivant).
    seuil_votes_notification = models.PositiveIntegerField(
        default=3, verbose_name="Seuil de votes pour notifier l'auteur")

    class Meta:
        verbose_name = 'Paramètres innovation'
        verbose_name_plural = 'Paramètres innovation'

    def __str__(self):
        return f'Paramètres innovation — {self.company_id}'


class CampagneInnovation(TenantModel):
    """Campagne d'innovation ciblée (NTIDE25) : incite un SEGMENT précis
    (rôles, ou département quand NTFPA1 est réutilisé) à proposer des idées
    sur un sujet donné, avec un tag auto-appliqué (NTIDE28).

    ``cible_departement``/``segment`` sont des références OPAQUES (chaînes) —
    jamais un ``ForeignKey`` vers ``apps.fpa.Departement`` (cross-app
    interdit, cf. règle de frontière) : le nom de département SI le
    référentiel NTFPA1 est bâti pour cette société, sinon un nom de rôle
    (``ROLES_CIBLABLES``, repli NTIDE26)."""

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        ACTIVE = 'active', 'Active'
        FERMEE = 'fermee', 'Fermée'

    # Redéclaré à l'identique (ARC1) : related_name explicite dédié.
    company = models.ForeignKey(
        'authentication.Company',
        # on_delete: campagnes scopées société — disparaissent avec elle (nettoyage tenant standard).
        on_delete=models.CASCADE,
        related_name='innovation_campagnes', verbose_name='Société')
    nom = models.CharField(max_length=255, verbose_name='Nom')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.BROUILLON,
        verbose_name='Statut')
    # Cible MONO-valeur (raccourci d'affichage — « Nous ciblons le
    # Technicien » / « … le département Pompage ») : nom de Departement
    # (NTFPA1) si bâti, sinon un des ``ROLES_CIBLABLES``. Vide = pas de
    # cible unique affichée (seul ``segment`` compte alors).
    cible_departement = models.CharField(
        max_length=80, blank=True, default='',
        verbose_name='Cible (département ou rôle)')
    # Segment MULTI-valeur (NTIDE26/NTIDE35) : toujours un tableau de
    # chaînes (rôles ou départements), jamais un objet. Repli utilisé par
    # ``selectors.users_for_campaign`` quand ``cible_departement`` seul ne
    # suffit pas (bulk multi-rôles).
    segment = models.JSONField(default=list, blank=True, verbose_name='Segment')
    date_debut = models.DateField(
        null=True, blank=True, verbose_name='Date de début')
    date_fin = models.DateField(
        null=True, blank=True, verbose_name='Date de fin')

    class Meta:
        verbose_name = 'Campagne innovation'
        verbose_name_plural = 'Campagnes innovation'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='innovation_camp_co_statut'),
        ]

    def __str__(self):
        return self.nom
