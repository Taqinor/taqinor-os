"""Modèles de la Gestion de projet (module `apps.gestion_projet`).

Socle multi-chantier : un ``Projet`` regroupe un ou plusieurs chantiers
(``ProjetChantier``) et porte le suivi de réalisation (statut, dates, budget
INTERNE). Les références transverses (client CRM, chantier installations) sont
des liens LÂCHES par identifiant — jamais d'import des modèles d'une autre app.

Tout est multi-société : chaque modèle porte un FK ``company`` posé côté serveur
(jamais lu du corps de requête). Aucun comportement existant n'est modifié — ce
module est entièrement additif.
"""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Projet(models.Model):
    """Un projet multi-chantier d'une société (suivi de réalisation).

    Le ``client_id`` référence LÂCHEMENT un ``crm.Client`` (aucun FK dur) ; le
    ``budget_total`` est une donnée INTERNE de pilotage, jamais exposée au
    client final.

    Le cycle de vie ``statut`` est une machine à états PROPRE au projet
    d'installation solaire — totalement DISTINCTE des étapes du tunnel CRM de
    ``STAGES.py`` (règle #2) : il ne réutilise NI n'importe AUCUNE clé/étiquette
    de ``STAGES.py``. Le ``statut`` n'est jamais posé depuis le corps de
    requête : seules les actions de transition (voir ``views.py``) le déplacent.
    """
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        PLANIFIE = 'planifie', 'Planifié'
        EN_COURS = 'en_cours', 'En cours'
        EN_PAUSE = 'en_pause', 'En pause'
        TERMINE = 'termine', 'Terminé'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='projets',
        verbose_name='Société',
    )
    code = models.CharField(max_length=30, verbose_name='Code')
    nom = models.CharField(max_length=200, verbose_name='Nom')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    statut = models.CharField(
        max_length=15, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    # Référence lâche vers crm.Client (aucun FK dur).
    client_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du client')
    date_debut = models.DateField(
        null=True, blank=True, verbose_name='Date de début')
    date_fin_prevue = models.DateField(
        null=True, blank=True, verbose_name='Date de fin prévue')
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='projets_responsable',
        verbose_name='Responsable',
    )
    # Budget INTERNE de pilotage — jamais exposé au client final.
    budget_total = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Budget total')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Projet'
        verbose_name_plural = 'Projets'
        unique_together = [('company', 'code')]
        ordering = ['-id']

    def __str__(self):
        return f'{self.code} — {self.nom}'


class ProjetChantier(models.Model):
    """Rattachement LÂCHE d'un chantier (installations.Chantier) à un projet.

    Le ``chantier_id`` référence LÂCHEMENT un ``installations.Chantier`` (aucun
    FK dur) ; un même projet peut agréger plusieurs chantiers.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='projet_chantiers',
        verbose_name='Société',
    )
    projet = models.ForeignKey(
        Projet,
        on_delete=models.CASCADE,
        related_name='chantiers',
        verbose_name='Projet',
    )
    # Référence lâche vers installations.Chantier (aucun FK dur).
    chantier_id = models.PositiveIntegerField(verbose_name='ID du chantier')
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Chantier du projet'
        verbose_name_plural = 'Chantiers du projet'
        ordering = ['id']

    def __str__(self):
        return f'{self.projet.code} ← chantier {self.chantier_id}'


class ProjetLien(models.Model):
    """Lien LÂCHE d'un projet vers un document métier d'une AUTRE app.

    Permet de rattacher un projet à un devis (``ventes``), une facture
    (``ventes``), un ticket SAV (``sav``) ou un achat (``stock``) SANS aucun FK
    dur : la cible est désignée par un couple typé ``(type_cible, cible_id)`` —
    jamais un import du modèle d'une autre app. Le ``libelle`` met en cache un
    libellé d'affichage ; les sélecteurs (``selectors.py``) l'enrichissent au
    vol quand l'app cible expose un sélecteur de lecture, et dégradent
    proprement (libellé stocké seul) sinon.
    """
    class TypeCible(models.TextChoices):
        DEVIS = 'devis', 'Devis'
        FACTURE = 'facture', 'Facture'
        TICKET = 'ticket', 'Ticket SAV'
        ACHAT = 'achat', 'Achat'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='projet_liens',
        verbose_name='Société',
    )
    projet = models.ForeignKey(
        Projet,
        on_delete=models.CASCADE,
        related_name='liens',
        verbose_name='Projet',
    )
    type_cible = models.CharField(
        max_length=10, choices=TypeCible.choices, verbose_name='Type de cible')
    # PK de l'objet cible dans son app (référence lâche, aucun FK dur).
    cible_id = models.PositiveIntegerField(verbose_name='ID de la cible')
    # Libellé d'affichage mis en cache (fallback quand l'app cible n'a pas de
    # sélecteur d'enrichissement).
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Lien du projet'
        verbose_name_plural = 'Liens du projet'
        ordering = ['id']
        unique_together = [('projet', 'type_cible', 'cible_id')]

    def __str__(self):
        return f'{self.projet.code} → {self.type_cible} #{self.cible_id}'


class PhaseProjet(models.Model):
    """Une phase de la décomposition (WBS) d'un ``Projet``.

    Découpe un projet en étapes de réalisation standard — étude, appro, pose,
    mise en service, réception — pour suivre l'avancement par phase (statut,
    dates prévues/réelles, pourcentage). C'est le WBS PROPRE à la gestion de
    projet : totalement DISTINCT des jalons ``installations.JalonProjet`` — ce
    module n'importe JAMAIS ``installations`` (référence d'aucune sorte).

    Le ``type_phase`` est un enum PROPRE à ce module : il ne réutilise NI
    n'importe AUCUNE clé/étiquette de ``STAGES.py`` (règle #2). Tout est
    multi-société : ``company`` est posée côté serveur, jamais lue du corps de
    requête. Modèle entièrement additif.
    """
    class TypePhase(models.TextChoices):
        ETUDE = 'etude', 'Étude'
        APPRO = 'appro', 'Approvisionnement'
        POSE = 'pose', 'Pose'
        MES = 'mes', 'Mise en service'
        RECEPTION = 'reception', 'Réception'

    class Statut(models.TextChoices):
        A_VENIR = 'a_venir', 'À venir'
        EN_COURS = 'en_cours', 'En cours'
        TERMINEE = 'terminee', 'Terminée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='projet_phases',
        verbose_name='Société',
    )
    projet = models.ForeignKey(
        Projet,
        on_delete=models.CASCADE,
        related_name='phases',
        verbose_name='Projet',
    )
    type_phase = models.CharField(
        max_length=12, choices=TypePhase.choices,
        verbose_name='Type de phase')
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    date_debut_prevue = models.DateField(
        null=True, blank=True, verbose_name='Date de début prévue')
    date_fin_prevue = models.DateField(
        null=True, blank=True, verbose_name='Date de fin prévue')
    date_debut_reelle = models.DateField(
        null=True, blank=True, verbose_name='Date de début réelle')
    date_fin_reelle = models.DateField(
        null=True, blank=True, verbose_name='Date de fin réelle')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.A_VENIR, verbose_name='Statut')
    avancement_pct = models.PositiveSmallIntegerField(
        default=0, validators=[MaxValueValidator(100)],
        verbose_name='Avancement (%)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Phase de projet'
        verbose_name_plural = 'Phases de projet'
        ordering = ['projet', 'ordre', 'id']
        unique_together = [('projet', 'type_phase')]

    def __str__(self):
        return f'{self.projet.code} — {self.get_type_phase_display()}'


class Tache(models.Model):
    """Une tâche de la décomposition de travail (WBS) d'un ``Projet``.

    Brique de planning la plus fine du module : une tâche appartient à un
    ``Projet`` et, optionnellement, à une ``PhaseProjet``. Les SOUS-TÂCHES sont
    portées par un FK auto-référent ``parent`` (related_name ``sous_taches``) →
    arborescence WBS de profondeur ARBITRAIRE. Le ``code_wbs`` (ex. « 1.2.3 »)
    et ``ordre`` donnent un classement stable au sein d'une fratrie.

    Le ``statut`` est une machine d'état PROPRE à la tâche
    (a_faire/en_cours/termine/bloque) : il ne réutilise NI n'importe AUCUNE
    clé/étiquette de ``STAGES.py`` (règle #2), et il est DISTINCT du statut du
    ``Projet`` (PROJ3) comme de celui de la ``PhaseProjet`` (PROJ4).

    Les champs ``charge_estimee`` (jours-homme prévus, nullable) et
    ``avancement_pct`` sont posés MINIMAUX mais EXTENSIBLES : PROJ6
    (dépendances), PROJ8 (CPM) et PROJ9 (roll-up d'avancement pondéré par la
    charge) construiront dessus. Tout est multi-société : ``company`` est posée
    côté serveur, jamais lue du corps de requête. Modèle entièrement additif.
    """
    class Statut(models.TextChoices):
        A_FAIRE = 'a_faire', 'À faire'
        EN_COURS = 'en_cours', 'En cours'
        TERMINE = 'termine', 'Terminée'
        BLOQUE = 'bloque', 'Bloquée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='projet_taches',
        verbose_name='Société',
    )
    projet = models.ForeignKey(
        Projet,
        on_delete=models.CASCADE,
        related_name='taches',
        verbose_name='Projet',
    )
    # Phase optionnelle : une tâche peut être rattachée à une phase du projet.
    phase = models.ForeignKey(
        PhaseProjet,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='taches',
        verbose_name='Phase',
    )
    # FK auto-référent : porte les SOUS-TÂCHES (arborescence WBS, profondeur
    # arbitraire). Supprimer une tâche supprime ses descendants (CASCADE).
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='sous_taches',
        verbose_name='Tâche parente',
    )
    code_wbs = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Code WBS')
    libelle = models.CharField(max_length=200, verbose_name='Libellé')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.A_FAIRE, verbose_name='Statut')
    avancement_pct = models.PositiveSmallIntegerField(
        default=0, validators=[MaxValueValidator(100)],
        verbose_name='Avancement (%)')
    # Charge prévue en jours-homme (nullable) — base de PROJ8/PROJ9.
    charge_estimee = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Charge estimée (j-h)')
    date_debut_prevue = models.DateField(
        null=True, blank=True, verbose_name='Date de début prévue')
    date_fin_prevue = models.DateField(
        null=True, blank=True, verbose_name='Date de fin prévue')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Tâche de projet'
        verbose_name_plural = 'Tâches de projet'
        ordering = ['projet', 'ordre', 'id']
        indexes = [
            models.Index(
                fields=['projet', 'parent'], name='gp_tache_proj_parent_idx'),
        ]

    def __str__(self):
        prefix = f'{self.code_wbs} ' if self.code_wbs else ''
        return f'{prefix}{self.libelle}'


class DependanceTache(models.Model):
    """Une dépendance de planning entre deux ``Tache`` d'un MÊME projet.

    Relie une tâche PRÉDÉCESSEUR (``predecesseur``) à une tâche SUCCESSEUR
    (``successeur``) selon un ``type_dependance`` de planification classique :

        FS (finish-to-start)  — le successeur démarre après la fin du prédécesseur
        SS (start-to-start)   — les deux démarrent ensemble
        FF (finish-to-finish) — les deux finissent ensemble
        SF (start-to-finish)  — le successeur finit après le début du prédécesseur

    Le ``lag`` est un décalage en JOURS (lead/lag) appliqué à la contrainte : il
    peut être NÉGATIF (lead, chevauchement) comme positif (lag, temporisation).
    Le ``type_dependance`` est un enum PROPRE à ce module — il ne réutilise NI
    n'importe AUCUNE clé/étiquette de ``STAGES.py`` (règle #2).

    Garde-fous (posés au ``clean`` du modèle ET au sérialiseur) : prédécesseur et
    successeur doivent appartenir au MÊME projet et à la MÊME société ; une tâche
    ne peut dépendre d'elle-même ; et un cycle DIRECT (A→B alors que B→A existe
    déjà) est refusé. C'est la brique de données de PROJ8 (chemin critique / CPM).
    Tout est multi-société : ``company`` est posée côté serveur, jamais lue du
    corps de requête. Modèle entièrement additif.
    """
    class TypeDependance(models.TextChoices):
        FS = 'fs', 'Fin → Début (FS)'
        SS = 'ss', 'Début → Début (SS)'
        FF = 'ff', 'Fin → Fin (FF)'
        SF = 'sf', 'Début → Fin (SF)'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='projet_dependances',
        verbose_name='Société',
    )
    # La tâche dont l'achèvement/le démarrage CONTRAINT l'autre.
    predecesseur = models.ForeignKey(
        Tache,
        on_delete=models.CASCADE,
        related_name='dependances_sortantes',
        verbose_name='Tâche prédécesseur',
    )
    # La tâche contrainte par le prédécesseur.
    successeur = models.ForeignKey(
        Tache,
        on_delete=models.CASCADE,
        related_name='dependances_entrantes',
        verbose_name='Tâche successeur',
    )
    type_dependance = models.CharField(
        max_length=2, choices=TypeDependance.choices,
        default=TypeDependance.FS, verbose_name='Type de dépendance')
    # Décalage en jours (lead/lag) — peut être négatif.
    lag = models.IntegerField(default=0, verbose_name='Décalage (jours)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Dépendance de tâche'
        verbose_name_plural = 'Dépendances de tâches'
        ordering = ['id']
        # Une seule arête par couple (prédécesseur, successeur) : le type/lag se
        # modifie par PATCH, jamais en dupliquant l'arête.
        unique_together = [('predecesseur', 'successeur')]
        indexes = [
            models.Index(
                fields=['successeur'], name='gp_dep_successeur_idx'),
            models.Index(
                fields=['predecesseur'], name='gp_dep_predecesseur_idx'),
        ]

    def __str__(self):
        return (f'{self.predecesseur_id} →[{self.type_dependance}] '
                f'{self.successeur_id}')

    def clean(self):
        from django.core.exceptions import ValidationError
        pred = self.predecesseur
        succ = self.successeur
        if pred is None or succ is None:
            return
        # Pas d'auto-dépendance.
        if pred.id is not None and pred.id == succ.id:
            raise ValidationError(
                'Une tâche ne peut pas dépendre d’elle-même.')
        # Même projet (et donc même société).
        if pred.projet_id != succ.projet_id:
            raise ValidationError(
                'Le prédécesseur et le successeur doivent appartenir au même '
                'projet.')
        # Cycle DIRECT : l'arête inverse existe déjà (B→A alors qu'on crée A→B).
        inverse = DependanceTache.objects.filter(
            predecesseur_id=succ.id, successeur_id=pred.id)
        if self.pk is not None:
            inverse = inverse.exclude(pk=self.pk)
        if inverse.exists():
            raise ValidationError(
                'Dépendance cyclique : l’arête inverse existe déjà.')


class Jalon(models.Model):
    """Un jalon (milestone) d'un ``Projet`` — éventuellement de FACTURATION.

    Un jalon marque une étape clé du projet à une ``date_prevue`` ; sa
    ``date_reelle`` (nullable) est posée quand il est ATTEINT. Il peut, en
    option, être rattaché à une ``PhaseProjet`` ou à une ``Tache`` du même
    projet (jalons d'événement de planning) — les deux FK sont nullables.

    Le ``facturation_pct`` (Decimal 0–100) porte le % de la VALEUR du projet à
    facturer lorsque le jalon est atteint : c'est la brique des JALONS DE
    FACTURATION (échéancier de paiement adossé à l'avancement). À 0 le jalon est
    un simple repère de planning sans incidence de facturation.

    Le ``statut`` est une machine d'état PROPRE au jalon
    (a_venir/atteint/manque) : il ne réutilise NI n'importe AUCUNE clé/étiquette
    de ``STAGES.py`` (règle #2), et il est DISTINCT des statuts du ``Projet``,
    de la ``PhaseProjet`` et de la ``Tache``. Tout est multi-société :
    ``company`` est posée côté serveur, jamais lue du corps de requête. Modèle
    entièrement additif.
    """
    class Statut(models.TextChoices):
        A_VENIR = 'a_venir', 'À venir'
        ATTEINT = 'atteint', 'Atteint'
        MANQUE = 'manque', 'Manqué'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='projet_jalons',
        verbose_name='Société',
    )
    projet = models.ForeignKey(
        Projet,
        on_delete=models.CASCADE,
        related_name='jalons',
        verbose_name='Projet',
    )
    # Rattachement OPTIONNEL à une phase du projet.
    phase = models.ForeignKey(
        PhaseProjet,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='jalons',
        verbose_name='Phase',
    )
    # Rattachement OPTIONNEL à une tâche du projet.
    tache = models.ForeignKey(
        Tache,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='jalons',
        verbose_name='Tâche',
    )
    libelle = models.CharField(max_length=200, verbose_name='Libellé')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    date_prevue = models.DateField(verbose_name='Date prévue')
    date_reelle = models.DateField(
        null=True, blank=True, verbose_name='Date réelle')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.A_VENIR, verbose_name='Statut')
    # % de la valeur du projet à facturer à l'atteinte du jalon (0–100).
    facturation_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0')),
                    MaxValueValidator(Decimal('100'))],
        verbose_name='Facturation (%)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Jalon de projet'
        verbose_name_plural = 'Jalons de projet'
        ordering = ['projet', 'date_prevue', 'id']
        indexes = [
            models.Index(
                fields=['projet', 'date_prevue'],
                name='gp_jalon_proj_date_idx'),
        ]

    def __str__(self):
        return f'{self.projet.code} — {self.libelle} ({self.date_prevue})'


class ProjetActivity(models.Model):
    """Journal minimal des transitions de statut d'un ``Projet``.

    Chaque changement de statut appliqué par une action de transition
    (``views.py``) y est tracé côté serveur : ancien → nouveau statut, auteur,
    horodatage. La société et l'auteur sont TOUJOURS posés côté serveur, jamais
    lus du corps de requête. Modèle entièrement additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='projet_activites',
        verbose_name='Société',
    )
    projet = models.ForeignKey(
        Projet,
        on_delete=models.CASCADE,
        related_name='activites',
        verbose_name='Projet',
    )
    old_value = models.CharField(
        max_length=15, blank=True, default='', verbose_name='Ancien statut')
    new_value = models.CharField(
        max_length=15, blank=True, default='', verbose_name='Nouveau statut')
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='projet_activites',
        verbose_name='Auteur',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Activité projet'
        verbose_name_plural = 'Activités projet'
        ordering = ['-date_creation', '-id']
        indexes = [models.Index(
            fields=['projet', '-date_creation'],
            name='gp_proj_activity_idx')]

    def __str__(self):
        return f'{self.projet_id} {self.old_value}→{self.new_value}'.strip()
