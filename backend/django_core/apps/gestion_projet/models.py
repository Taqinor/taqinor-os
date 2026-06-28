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


class CalendrierProjet(models.Model):
    """Calendrier ouvré d'un ``Projet`` : jours travaillés + fériés (PROJ12).

    Définit, pour UN projet, quels jours de la semaine sont OUVRÉS (drapeaux
    ``lundi``…``dimanche``, par défaut lundi→vendredi) afin que les calculs de
    planning (PROJ8/PROJ10/PROJ11) puissent sauter les jours non travaillés.
    Les jours fériés ponctuels sont portés par ``JourFerie`` (FK enfant). Relation
    1–1 souple avec le projet (un calendrier par projet, garanti
    ``unique_together``). Aucun comportement existant n'est modifié — modèle
    entièrement additif. Tout est multi-société : ``company`` est posée côté
    serveur, jamais lue du corps de requête.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='projet_calendriers',
        verbose_name='Société',
    )
    projet = models.OneToOneField(
        Projet,
        on_delete=models.CASCADE,
        related_name='calendrier',
        verbose_name='Projet',
    )
    lundi = models.BooleanField(default=True, verbose_name='Lundi ouvré')
    mardi = models.BooleanField(default=True, verbose_name='Mardi ouvré')
    mercredi = models.BooleanField(default=True, verbose_name='Mercredi ouvré')
    jeudi = models.BooleanField(default=True, verbose_name='Jeudi ouvré')
    vendredi = models.BooleanField(default=True, verbose_name='Vendredi ouvré')
    samedi = models.BooleanField(default=False, verbose_name='Samedi ouvré')
    dimanche = models.BooleanField(default=False, verbose_name='Dimanche ouvré')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Calendrier de projet'
        verbose_name_plural = 'Calendriers de projet'
        ordering = ['id']

    def __str__(self):
        return f'Calendrier {self.projet.code}'

    def jours_ouvres(self):
        """Liste des indices de jours OUVRÉS (0=lundi … 6=dimanche)."""
        drapeaux = [
            self.lundi, self.mardi, self.mercredi, self.jeudi,
            self.vendredi, self.samedi, self.dimanche,
        ]
        return [i for i, ouvre in enumerate(drapeaux) if ouvre]


class JourFerie(models.Model):
    """Un jour FÉRIÉ (chômé) du calendrier d'un projet (PROJ12).

    Une date ponctuelle exclue des jours ouvrés (en plus des week-ends définis
    par ``CalendrierProjet``). Unique par ``(calendrier, date)``. Modèle
    entièrement additif ; ``company`` est posée côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='projet_jours_feries',
        verbose_name='Société',
    )
    calendrier = models.ForeignKey(
        CalendrierProjet,
        on_delete=models.CASCADE,
        related_name='jours_feries',
        verbose_name='Calendrier',
    )
    date = models.DateField(verbose_name='Date')
    libelle = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Libellé')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Jour férié'
        verbose_name_plural = 'Jours fériés'
        ordering = ['date', 'id']
        unique_together = [('calendrier', 'date')]
        indexes = [
            models.Index(
                fields=['calendrier', 'date'], name='gp_ferie_cal_date_idx'),
        ]

    def __str__(self):
        return f'{self.date} {self.libelle}'.strip()


class BaselinePlanning(models.Model):
    """Un INSTANTANÉ figé du planning d'un ``Projet`` (PROJ13 — plan vs réel).

    Une baseline mémorise, à un instant donné, le créneau PRÉVU
    (``date_debut_prevue`` / ``date_fin_prevue``) et la charge estimée de CHAQUE
    tâche du projet (lignes ``BaselineTache``). Comparée plus tard au planning
    courant, elle donne l'écart PLAN vs RÉEL (glissement de dates, dérive de
    charge). Plusieurs baselines peuvent coexister (référence initiale,
    re-baseline après avenant) ; chaque ligne est figée à la prise de snapshot.

    Tout est multi-société : ``company`` est posée côté serveur, jamais lue du
    corps de requête. ``auteur`` est posé côté serveur. Modèle entièrement
    additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='projet_baselines',
        verbose_name='Société',
    )
    projet = models.ForeignKey(
        Projet,
        on_delete=models.CASCADE,
        related_name='baselines',
        verbose_name='Projet',
    )
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='projet_baselines',
        verbose_name='Auteur',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Baseline de planning'
        verbose_name_plural = 'Baselines de planning'
        ordering = ['-date_creation', '-id']
        indexes = [
            models.Index(
                fields=['projet', '-date_creation'],
                name='gp_baseline_proj_idx'),
        ]

    def __str__(self):
        return f'{self.projet.code} — baseline {self.libelle or self.id}'


class BaselineTache(models.Model):
    """Ligne figée d'une ``BaselinePlanning`` : créneau prévu d'UNE tâche.

    Mémorise, au moment du snapshot, le ``date_debut_prevue`` /
    ``date_fin_prevue`` et la ``charge_estimee`` d'une tâche. Le FK ``tache`` est
    en ``SET_NULL`` : si la tâche est supprimée plus tard, la ligne de baseline
    survit (on garde ``tache_libelle`` / ``tache_code_wbs`` figés pour
    l'affichage). Modèle entièrement additif ; ``company`` posée côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='projet_baseline_taches',
        verbose_name='Société',
    )
    baseline = models.ForeignKey(
        BaselinePlanning,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='Baseline',
    )
    tache = models.ForeignKey(
        Tache,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='baseline_lignes',
        verbose_name='Tâche',
    )
    # Libellé/code figés au snapshot (survivent à une suppression de la tâche).
    tache_libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé figé')
    tache_code_wbs = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Code WBS figé')
    date_debut_prevue = models.DateField(
        null=True, blank=True, verbose_name='Date de début prévue (figée)')
    date_fin_prevue = models.DateField(
        null=True, blank=True, verbose_name='Date de fin prévue (figée)')
    charge_estimee = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Charge estimée (figée)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Ligne de baseline'
        verbose_name_plural = 'Lignes de baseline'
        ordering = ['id']
        indexes = [
            models.Index(
                fields=['baseline'], name='gp_baseline_tache_idx'),
        ]

    def __str__(self):
        return f'baseline {self.baseline_id} ← {self.tache_libelle}'


class RessourceProfil(models.Model):
    """Profil de ressource interne pour le planning de projet (PROJ15).

    Représente une personne (ou un rôle) mobilisable sur un projet. Le lien
    vers un compte utilisateur (``user``) est OPTIONNEL : une ressource peut
    exister sans compte ERP (sous-traitant, poste budgétaire, futur embauche).

    Le ``cout_horaire`` est un coût INTERNE de pilotage (comme ``budget_total``
    du Projet) — il ne doit jamais apparaître dans un PDF ou un lien client.
    Tout est multi-société : ``company`` est posée côté serveur, jamais lue du
    corps de requête. Modèle entièrement additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='projet_ressources',
        verbose_name='Société',
    )
    # Lien OPTIONNEL vers un compte utilisateur de la fondation (import autorisé
    # car authentication est une app fondation, non un domaine-cœur).
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='gestion_projet_ressources',
        verbose_name='Utilisateur lié',
    )
    nom = models.CharField(max_length=150, verbose_name='Nom / identifiant')
    role = models.CharField(
        max_length=100, blank=True, default='', verbose_name='Rôle')
    competences = models.TextField(
        blank=True, default='', verbose_name='Compétences')
    # Coût horaire INTERNE — jamais exposé dans un PDF ou un lien client.
    cout_horaire = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0'),
        verbose_name='Coût horaire interne')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Profil ressource'
        verbose_name_plural = 'Profils ressources'
        ordering = ['nom', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'nom'],
                name='gp_ressource_company_nom_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.nom} ({self.role})' if self.role else self.nom


class Equipe(models.Model):
    """Équipe de ressources pour le planning de projet (PROJ15).

    Regroupe plusieurs ``RessourceProfil`` d'une même société sous un nom
    d'équipe (ex. « Équipe pose Casablanca »). La relation membres est une M2M
    directe (pas de through explicite : aucune donnée propre à l'appartenance
    n'est requise ici). Tout est multi-société : ``company`` est posée côté
    serveur, jamais lue du corps de requête. Modèle entièrement additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='projet_equipes',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=150, verbose_name="Nom de l'équipe")
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    membres = models.ManyToManyField(
        RessourceProfil,
        blank=True,
        related_name='equipes',
        verbose_name='Membres',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Équipe'
        verbose_name_plural = 'Équipes'
        ordering = ['nom', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'nom'],
                name='gp_equipe_company_nom_uniq',
            ),
        ]

    def __str__(self):
        return self.nom


class AffectationRessource(models.Model):
    """Affectation d'une ressource (personne, équipe ou matériel) à une tâche.

    Brique PROJ16 : alloue une RESSOURCE — ``RessourceProfil`` (personne/rôle),
    ``Equipe``, ou un actif matériel (véhicule/machine, référence LÂCHE vers
    ``flotte.ActifFlotte``) — à une ``Tache`` du projet, sur une période
    définie (``date_debut`` / ``date_fin``). La charge (``charge_jours``) et
    la quantité (``quantite``) sont optionnelles : données de pilotage interne.

    EXACTEMENT UN des trois vecteurs de ressource doit être renseigné (validé
    dans ``clean`` et dans le sérialiseur) :
        • ``ressource``     — FK vers ``RessourceProfil`` (personne ou rôle)
        • ``equipe``        — FK vers ``Equipe``
        • ``actif_type`` + ``actif_id`` — référence LÂCHE vers ``flotte.ActifFlotte``
          (type = 'actif_flotte') ; l'identifiant est stocké séparément pour ne
          JAMAIS importer les modèles flotte (règle cross-app).

    Tout est multi-société : ``company`` est posée côté serveur, jamais lue du
    corps de requête. Modèle entièrement additif.
    """

    class TypeActif(models.TextChoices):
        ACTIF_FLOTTE = 'actif_flotte', 'Actif flotte'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='gp_affectations',
        verbose_name='Société',
    )
    tache = models.ForeignKey(
        Tache,
        on_delete=models.CASCADE,
        related_name='affectations',
        verbose_name='Tâche',
    )
    # ── Vecteur 1 : personne / rôle ──────────────────────────────────────────
    ressource = models.ForeignKey(
        RessourceProfil,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='gp_affectations',
        verbose_name='Ressource (profil)',
    )
    # ── Vecteur 2 : équipe ────────────────────────────────────────────────────
    equipe = models.ForeignKey(
        Equipe,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='gp_affectations',
        verbose_name='Équipe',
    )
    # ── Vecteur 3 : actif matériel (référence LÂCHE vers flotte) ─────────────
    actif_type = models.CharField(
        max_length=30,
        choices=TypeActif.choices,
        blank=True, default='',
        verbose_name='Type actif',
    )
    actif_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="ID de l'actif")
    # ── Période ───────────────────────────────────────────────────────────────
    date_debut = models.DateField(verbose_name='Date de début')
    date_fin = models.DateField(verbose_name='Date de fin')
    # ── Charge / quantité (pilotage interne) ─────────────────────────────────
    charge_jours = models.DecimalField(
        max_digits=8, decimal_places=2,
        null=True, blank=True,
        verbose_name='Charge (j-h)',
    )
    quantite = models.DecimalField(
        max_digits=10, decimal_places=3,
        null=True, blank=True,
        verbose_name='Quantité',
    )
    note = models.TextField(blank=True, default='', verbose_name='Note')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Affectation de ressource"
        verbose_name_plural = "Affectations de ressources"
        ordering = ['tache', 'date_debut', 'id']
        indexes = [
            models.Index(
                fields=['tache', 'date_debut'],
                name='gp_affect_tache_debut_idx'),
            models.Index(
                fields=['ressource'],
                name='gp_affect_ressource_idx'),
            models.Index(
                fields=['equipe'],
                name='gp_affect_equipe_idx'),
        ]

    def __str__(self):
        if self.ressource_id:
            label = str(self.ressource)
        elif self.equipe_id:
            label = str(self.equipe)
        else:
            label = f"{self.actif_type}#{self.actif_id}"
        return f"Tâche {self.tache_id} ← {label} ({self.date_debut}/{self.date_fin})"

    def clean(self):
        self._validate_un_seul_vecteur()

    def _validate_un_seul_vecteur(self):
        from django.core.exceptions import ValidationError
        has_ressource = self.ressource_id is not None
        has_equipe = self.equipe_id is not None
        has_actif = bool(self.actif_type) and self.actif_id is not None
        vecteurs = sum([has_ressource, has_equipe, has_actif])
        if vecteurs == 0:
            raise ValidationError(
                "Exactement un vecteur de ressource doit être renseigné "
                "(ressource, équipe ou actif matériel).")
        if vecteurs > 1:
            raise ValidationError(
                "Un seul vecteur de ressource à la fois : ressource, équipe "
                "ou actif matériel — pas plusieurs simultanément.")


class Indisponibilite(models.Model):
    """Fenêtre d'indisponibilité d'une ressource de projet (PROJ17).

    Modélise une période pendant laquelle une ``RessourceProfil`` n'est PAS
    mobilisable — congé, formation ou arrêt (maladie/panne/autre). La planification
    et l'affectation (PROJ16/18/19) peuvent ainsi exclure une ressource indisponible
    sur une fenêtre donnée (voir ``selectors.ressource_disponible_sur_periode``).

    La période ``date_debut`` / ``date_fin`` est INCLUSIVE des deux bornes : une
    indisponibilité du 1er au 5 couvre les cinq jours. ``motif`` est un commentaire
    libre optionnel (réf. dossier RH, n° de formation…).

    Tout est multi-société : ``company`` est posée côté serveur, jamais lue du
    corps de requête. La ressource est une ``RessourceProfil`` de la MÊME société
    (validé dans le sérialiseur). Modèle entièrement additif.
    """

    class TypeIndispo(models.TextChoices):
        CONGE = 'conge', 'Congé'
        FORMATION = 'formation', 'Formation'
        ARRET = 'arret', 'Arrêt'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='gp_indisponibilites',
        verbose_name='Société',
    )
    ressource = models.ForeignKey(
        RessourceProfil,
        on_delete=models.CASCADE,
        related_name='gp_indisponibilites',
        verbose_name='Ressource (profil)',
    )
    type_indispo = models.CharField(
        max_length=20,
        choices=TypeIndispo.choices,
        default=TypeIndispo.CONGE,
        verbose_name="Type d'indisponibilité",
    )
    date_debut = models.DateField(verbose_name='Date de début')
    date_fin = models.DateField(verbose_name='Date de fin')
    motif = models.TextField(blank=True, default='', verbose_name='Motif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Indisponibilité ressource'
        verbose_name_plural = 'Indisponibilités ressources'
        ordering = ['ressource', 'date_debut', 'id']
        indexes = [
            models.Index(
                fields=['ressource', 'date_debut'],
                name='gp_indispo_res_debut_idx'),
            models.Index(
                fields=['company', 'date_debut'],
                name='gp_indispo_co_debut_idx'),
        ]

    def __str__(self):
        return (
            f"{self.ressource_id} {self.type_indispo} "
            f"({self.date_debut}→{self.date_fin})")

    def clean(self):
        from django.core.exceptions import ValidationError
        if (self.date_debut and self.date_fin
                and self.date_fin < self.date_debut):
            raise ValidationError(
                "La date de fin ne peut pas être antérieure à la date de début.")

    def chevauche(self, debut, fin):
        """True si cette indisponibilité chevauche la fenêtre [debut, fin].

        Bornes INCLUSIVES des deux côtés (comme la période stockée) : deux
        intervalles se chevauchent dès que ``date_debut <= fin`` ET
        ``date_fin >= debut``.
        """
        return self.date_debut <= fin and self.date_fin >= debut


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
