"""Modèles de la Gestion de projet (module `apps.gestion_projet`).

Socle multi-chantier : un ``Projet`` regroupe un ou plusieurs chantiers
(``ProjetChantier``) et porte le suivi de réalisation (statut, dates, budget
INTERNE). Les références transverses (client CRM, chantier installations) sont
des liens LÂCHES par identifiant — jamais d'import des modèles d'une autre app.

Tout est multi-société : chaque modèle porte un FK ``company`` posé côté serveur
(jamais lu du corps de requête). Aucun comportement existant n'est modifié — ce
module est entièrement additif.
"""
import secrets
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def _generer_token_portail():
    """Jeton URL-safe (256 bits) pour un lien de portail client."""
    return secrets.token_urlsafe(32)


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

    class PolitiqueFacturation(models.TextChoices):
        """Politique de facturation DÉCLARATIVE d'un projet (ZPRJ10).

        Purement informative : elle n'altère AUCUN statut devis/BC/facture
        (couche séparée, règle #4 CLAUDE.md). Elle sert seulement à faire
        ressortir une incohérence (avertissement non bloquant, jamais un
        blocage dur) quand une action de facturation d'un autre chemin
        (régie XPRJ3, situations BTP XPRJ4) est appelée sur un projet déclaré
        sous une autre politique.
        """
        FORFAIT = 'forfait', 'Forfait'
        JALONS = 'jalons', 'Jalons (facturation à l\'avancement)'
        REGIE = 'regie', 'Régie (temps & matériel)'
        SITUATIONS = 'situations', 'Situations de travaux (BTP)'

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
    # ── Volet marchés publics (XPRJ27) — FACULTATIF, sans impact sur les
    # projets privés (aucun champ obligatoire, tous par défaut vide/0/None).
    # Les cautions provisoire/définitive vivent déjà dans FG145/contrats —
    # référence LÂCHE ``contrat_id`` (aucun FK dur, frontière cross-app).
    numero_marche = models.CharField(
        max_length=100, blank=True, default='', verbose_name='N° de marché')
    maitre_ouvrage = models.CharField(
        max_length=200, blank=True, default='', verbose_name="Maître d'ouvrage")
    delai_execution_jours = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Délai d'exécution (jours)")
    # Taux de pénalité de retard en ‰ (pour mille) par jour de dépassement.
    taux_penalite_retard = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True,
        verbose_name='Taux de pénalité de retard (‰/jour)')
    # Plafond de pénalité en % du montant du marché (souvent 10 % au Maroc).
    plafond_penalite_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='Plafond de pénalité (%)')
    # Montant du marché — distinct du ``budget_total`` INTERNE de pilotage :
    # sert d'assiette au calcul de l'exposition aux pénalités.
    montant_marche = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Montant du marché')
    # Référence LÂCHE vers un ``contrats.Contrat`` (cautions) — jamais de FK dur.
    contrat_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du contrat (cautions)')
    # Politique de facturation DÉCLARATIVE (ZPRJ10) — n'altère aucun statut
    # devis/BC/facture (couche séparée, règle #4). Sert à détecter une
    # incohérence (avertissement non bloquant) entre le chemin de
    # facturation appelé (régie XPRJ3, situations XPRJ4) et la politique
    # déclarée.
    politique_facturation = models.CharField(
        max_length=12, choices=PolitiqueFacturation.choices,
        default=PolitiqueFacturation.FORFAIT,
        verbose_name='Politique de facturation')
    # Alias e-mail du projet (ZPRJ12) — optionnel, unique par société quand
    # renseigné (pattern ``chat.Conversation.alias_email`` ZCTR12). Sans
    # ingestion e-mail configurée, ce champ reste un simple libellé sans effet.
    alias_email = models.CharField(
        max_length=254, blank=True, default='', null=True,
        verbose_name='Alias e-mail (création de tâches)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Projet'
        verbose_name_plural = 'Projets'
        unique_together = [('company', 'code')]
        ordering = ['-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'alias_email'],
                condition=~models.Q(alias_email__in=['', None]),
                name='gp_projet_alias_email_uniq'),
        ]

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

    class Priorite(models.TextChoices):
        BASSE = 'basse', 'Basse'
        NORMALE = 'normale', 'Normale'
        HAUTE = 'haute', 'Haute'
        URGENTE = 'urgente', 'Urgente'

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
    # Assigné (XPRJ10) : une ressource UNIQUE porteuse de la tâche — distinct
    # de ``AffectationRessource`` qui gère l'affectation fine multi-ressources
    # (charge, période). ``assigne`` est le raccourci "qui fait cette tâche".
    assigne = models.ForeignKey(
        'RessourceProfil',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='taches_assignees',
        verbose_name='Assigné',
    )
    priorite = models.CharField(
        max_length=10, choices=Priorite.choices,
        default=Priorite.NORMALE, verbose_name='Priorité')
    # Tags légers en CSV (ex. "toiture,urgent") — filtrables via ?etiquette=.
    etiquettes = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Étiquettes')
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
    # Date de complétion RÉELLE (XPRJ17) — posée côté serveur quand ``statut``
    # passe à TERMINE (jamais lue du corps de requête), réinitialisée si le
    # statut repasse à un état non-terminé. Base du burndown (charge restante
    # reconstituée à chaque date).
    date_fin_reelle = models.DateField(
        null=True, blank=True, verbose_name='Date de fin réelle')
    # Référence LÂCHE (ZPRJ11) vers le ``sav.Ticket`` créé par conversion
    # (aucun FK dur, frontière cross-app) — posée côté serveur uniquement par
    # l'action ``vers-ticket-sav``. Une tâche déjà convertie (non nul) refuse
    # une seconde conversion (400).
    ticket_sav_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du ticket SAV (conversion)')
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

    # ── Cycle de publication (ZPRJ2) — enum PROPRE, JAMAIS STAGES.py ─────────
    class StatutPublication(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        PUBLIE = 'publie', 'Publié'

    statut_publication = models.CharField(
        max_length=10, choices=StatutPublication.choices,
        default=StatutPublication.BROUILLON,
        verbose_name='Statut de publication')
    # Posés CÔTÉ SERVEUR uniquement par l'action ``affectations/publier/``
    # (jamais lus du corps de requête).
    publie_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Publié le')
    publie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
        verbose_name='Publié par',
    )
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
    """Journal des transitions/modifications de champs sensibles d'un ``Projet``.

    Historiquement, tracait UNIQUEMENT le changement de statut du ``Projet``
    lui-même (``cible_type='projet'``, ``champ=''``). XPRJ26 étend ce journal,
    SANS changer le comportement des entrées existantes, aux changements de
    champs sensibles des ``Tache`` (statut, dates prévues, charge, assigné) et
    ``Jalon`` (date, statut, facturation_pct) — conformité audit/loi 09-08 sur
    qui a déplacé le planning. ``cible_type`` + ``cible_id`` identifient la
    cible RÉELLE de l'entrée : ``'projet'`` (défaut rétro-compatible —
    ``cible_id`` vaut alors ``projet_id``), ``'tache'`` ou ``'jalon'`` ;
    ``champ`` porte le nom du champ modifié (vide pour les entrées historiques
    de statut projet). Chaque changement est tracé côté serveur : ancien →
    nouveau, auteur, horodatage. La société et l'auteur sont TOUJOURS posés
    côté serveur, jamais lus du corps de requête. Modèle entièrement additif.
    """
    class CibleType(models.TextChoices):
        PROJET = 'projet', 'Projet'
        TACHE = 'tache', 'Tâche'
        JALON = 'jalon', 'Jalon'

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
    # Cible RÉELLE de l'entrée (XPRJ26) — défaut 'projet' pour rester
    # rétro-compatible avec les entrées historiques (transitions de statut du
    # projet lui-même, où cible_id == projet_id).
    cible_type = models.CharField(
        max_length=10, choices=CibleType.choices,
        default=CibleType.PROJET, verbose_name='Type de cible')
    cible_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID de la cible')
    # Nom du champ modifié (XPRJ26) — vide pour les entrées historiques de
    # statut projet (comportement inchangé).
    champ = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Champ modifié')
    old_value = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Ancien statut')
    new_value = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Nouveau statut')
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


class BudgetProjet(models.Model):
    """Budget INTERNE prévisionnel d'un ``Projet``, ventilé en lignes.

    Un projet peut porter plusieurs budgets (versions successives) ; chaque
    budget regroupe des lignes (``LigneBudgetProjet``) ventilées par catégorie
    de coût (matériel, main-d'œuvre, sous-traitance, divers). Le total prévu est
    la somme des ``montant_prevu`` des lignes (calculé par le sélecteur
    ``budget_total``). C'est une donnée de PILOTAGE interne — jamais exposée au
    client final, totalement DISTINCTE des montants des devis/factures.

    Tout est multi-société : ``company`` est posée côté serveur, jamais lue du
    corps de requête. Modèle entièrement additif.

    NB — PROJ22 (« engagé vs réel ») est une couche SÉPARÉE et ultérieure : ce
    modèle ne porte QUE le prévisionnel.
    """
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        VALIDE = 'valide', 'Validé'
        ARCHIVE = 'archive', 'Archivé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='gestion_projet_budgets',
        verbose_name='Société',
    )
    projet = models.ForeignKey(
        Projet,
        on_delete=models.CASCADE,
        related_name='budgets',
        verbose_name='Projet',
    )
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    version = models.PositiveIntegerField(default=1, verbose_name='Version')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    devise = models.CharField(
        max_length=3, default='MAD', verbose_name='Devise')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Budget projet'
        verbose_name_plural = 'Budgets projet'
        ordering = ['projet', '-version', '-id']
        indexes = [models.Index(
            fields=['projet', 'version'],
            name='gp_budget_proj_ver_idx')]

    def __str__(self):
        return f'{self.projet_id} budget v{self.version}'


class LigneBudgetProjet(models.Model):
    """Une ligne d'un ``BudgetProjet``, ventilée par catégorie de coût.

    ``categorie`` classe la dépense prévue (matériel / main-d'œuvre /
    sous-traitance / divers) ; ``montant_prevu`` est le montant prévisionnel de
    la ligne. ``quantite`` et ``pu`` (prix unitaire) sont OPTIONNELS et
    purement INDICATIFS : ils n'écrasent jamais ``montant_prevu`` (le total du
    budget agrège les ``montant_prevu``, voir ``selectors.budget_total``).

    Tout est multi-société : ``company`` est posée côté serveur, jamais lue du
    corps de requête. Modèle entièrement additif.
    """
    class Categorie(models.TextChoices):
        MATERIEL = 'materiel', 'Matériel'
        MAIN_OEUVRE = 'main_oeuvre', "Main-d'œuvre"
        SOUS_TRAITANCE = 'sous_traitance', 'Sous-traitance'
        DIVERS = 'divers', 'Divers'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='gestion_projet_lignes_budget',
        verbose_name='Société',
    )
    budget = models.ForeignKey(
        BudgetProjet,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='Budget',
    )
    categorie = models.CharField(
        max_length=14, choices=Categorie.choices,
        default=Categorie.MATERIEL, verbose_name='Catégorie')
    libelle = models.CharField(max_length=200, verbose_name='Libellé')
    quantite = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Quantité')
    pu = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Prix unitaire')
    montant_prevu = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant prévu')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Ligne de budget projet'
        verbose_name_plural = 'Lignes de budget projet'
        ordering = ['budget', 'categorie', 'id']
        indexes = [models.Index(
            fields=['budget', 'categorie'],
            name='gp_ligne_bud_cat_idx')]

    def __str__(self):
        return f'{self.get_categorie_display()} — {self.libelle}'


class Timesheet(models.Model):
    """Une feuille de temps INTERNE imputée à un ``Projet`` (PROJ24).

    Saisie d'un nombre d'``heures`` passées par une ``RessourceProfil`` un jour
    donné (``date``), imputées à un ``Projet`` et OPTIONNELLEMENT à une ``Tache``
    et/ou une ``PhaseProjet`` du même projet. C'est une donnée 100 % INTERNE de
    pilotage (comme le ``cout_horaire`` du profil) : elle alimente le suivi des
    temps et le coût de main-d'œuvre RÉEL — jamais exposée au client final.

    ``cout`` est un cache calculé côté serveur (``heures`` × ``cout_horaire``
    interne de la ressource au moment de la saisie) : on le fige pour que le
    coût historique survive à un changement de tarif de la ressource. Mis à 0
    quand la ressource n'a pas de coût horaire.

    Tout est multi-société : ``company`` est posée côté serveur, jamais lue du
    corps de requête. La ressource / la tâche / la phase doivent appartenir au
    MÊME projet et à la MÊME société (validé au sérialiseur). Modèle entièrement
    additif.

    Cycle de vie ``statut`` (XPRJ1) — machine à états PROPRE à la feuille de
    temps, JAMAIS ``STAGES.py`` (règle #2) :

        brouillon ─soumettre→ soumise ─approuver→ approuvee
                                  │
                                  └────rejeter────→ rejetee

    Le ``statut`` n'est jamais posé depuis le corps de requête (comme
    ``Projet.statut``) : seules les actions ``soumettre``/``approuver``/
    ``rejeter`` (voir ``views.py``) le déplacent. ``saisi_par`` est posé côté
    serveur à la création ; ``approuve_par``/``date_approbation`` sont posés
    par l'action ``approuver`` (palier Responsable/Admin — vérifié en vue).
    """
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        SOUMISE = 'soumise', 'Soumise'
        APPROUVEE = 'approuvee', 'Approuvée'
        REJETEE = 'rejetee', 'Rejetée'

    class TypeActivite(models.TextChoices):
        ETUDE = 'etude', 'Étude'
        POSE = 'pose', 'Pose'
        RACCORDEMENT = 'raccordement', 'Raccordement'
        MES = 'mes', 'Mise en service'
        DEPLACEMENT = 'deplacement', 'Déplacement'
        SAV = 'sav', 'SAV'
        ADMIN = 'admin', 'Administratif'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='gestion_projet_timesheets',
        verbose_name='Société',
    )
    projet = models.ForeignKey(
        Projet,
        on_delete=models.CASCADE,
        related_name='timesheets',
        verbose_name='Projet',
    )
    # Rattachement OPTIONNEL à une tâche du projet.
    tache = models.ForeignKey(
        Tache,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='timesheets',
        verbose_name='Tâche',
    )
    # Rattachement OPTIONNEL à une phase du projet.
    phase = models.ForeignKey(
        PhaseProjet,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='timesheets',
        verbose_name='Phase',
    )
    ressource = models.ForeignKey(
        RessourceProfil,
        on_delete=models.CASCADE,
        related_name='timesheets',
        verbose_name='Ressource (profil)',
    )
    date = models.DateField(verbose_name='Date')
    heures = models.DecimalField(
        max_digits=6, decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name='Heures')
    # Coût INTERNE figé (heures × coût horaire) — jamais exposé au client.
    cout = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Coût interne (figé)')
    commentaire = models.TextField(
        blank=True, default='', verbose_name='Commentaire')
    # ── Classification facturable + activité (XPRJ2) ─────────────────────────
    # Défaut True : la majorité des temps projet sont facturables en régie ;
    # peut être ajusté par saisie (ex. temps admin interne → False).
    facturable = models.BooleanField(
        default=True, verbose_name='Facturable')
    type_activite = models.CharField(
        max_length=15, choices=TypeActivite.choices,
        default=TypeActivite.POSE, verbose_name="Type d'activité")
    # Taux de facturation MAD/h CLIENT (distinct du cout_horaire INTERNE de la
    # ressource) — nullable : absent tant qu'aucun taux n'est saisi.
    taux_facturation = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Taux de facturation (MAD/h)')
    # Référence LÂCHE vers la ventes.Facture de régie qui a facturé cette
    # ligne (XPRJ3) — posée côté serveur par ``services.facturer_temps_projet``
    # UNIQUEMENT ; jamais lue du corps de requête. Empêche le double-facturation
    # (une ligne déjà facturée est exclue de la sélection du prochain run).
    facture_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID de la facture de régie')
    # ── Cycle de vie (XPRJ1) ──────────────────────────────────────────────────
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    saisi_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='gestion_projet_timesheets_saisies',
        verbose_name='Saisi par',
    )
    approuve_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='gestion_projet_timesheets_approuvees',
        verbose_name='Approuvé par',
    )
    date_approbation = models.DateTimeField(
        null=True, blank=True, verbose_name="Date d'approbation")
    motif_rejet = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Motif de rejet')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Feuille de temps'
        verbose_name_plural = 'Feuilles de temps'
        ordering = ['-date', '-id']
        indexes = [
            models.Index(
                fields=['projet', 'date'], name='gp_ts_proj_date_idx'),
            models.Index(
                fields=['ressource', 'date'], name='gp_ts_res_date_idx'),
            models.Index(
                fields=['company', 'statut'], name='gp_ts_co_statut_idx'),
        ]

    def __str__(self):
        return f'{self.ressource_id} {self.date} {self.heures} h'


class PeriodeVerrouilleeTemps(models.Model):
    """Verrou de PÉRIODE (mois) sur les feuilles de temps d'une société (XPRJ1).

    Une période verrouillée (``mois`` = 1er jour du mois, ex. 2026-01-01)
    interdit toute création/édition/suppression de ``Timesheet`` dont la
    ``date`` tombe dans ce mois — sauf pour un utilisateur ADMIN qui la
    déverrouille explicitement (suppression de la ligne, tracée dans
    ``ProjetActivity`` n'étant pas pertinent ici : le verrou n'est pas propre à
    un projet — la trace se fait au niveau applicatif, voir ``views.py``).

    Tout est multi-société : ``company`` est posée côté serveur, jamais lue du
    corps de requête. Modèle entièrement additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='gestion_projet_periodes_verrouillees',
        verbose_name='Société',
    )
    mois = models.DateField(
        verbose_name='Mois verrouillé (1er jour du mois)')
    verrouille_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='gestion_projet_periodes_verrouillees',
        verbose_name='Verrouillé par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Période verrouillée (temps)'
        verbose_name_plural = 'Périodes verrouillées (temps)'
        ordering = ['-mois']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'mois'],
                name='gp_periode_verr_co_mois_uniq'),
        ]

    def __str__(self):
        return f'{self.company_id} verrouillé {self.mois:%Y-%m}'


class Risque(models.Model):
    """Une entrée du REGISTRE DES RISQUES d'un ``Projet`` (PROJ30).

    Modélise un risque identifié sur un projet, évalué par sa ``probabilite`` et
    son ``impact`` (échelle 1–5 chacun) ; la ``criticite`` (1–25) est le PRODUIT
    des deux, calculé côté serveur — jamais lu du corps de requête. Le
    ``statut`` suit le cycle de vie PROPRE au registre
    (ouvert/surveille/maitrise/clos) — il ne réutilise NI n'importe AUCUNE
    clé/étiquette de ``STAGES.py`` (règle #2), et est DISTINCT de tous les autres
    statuts du module. ``mitigation`` porte le plan de réduction, ``proprietaire``
    (optionnel) le responsable côté ERP.

    Tout est multi-société : ``company`` est posée côté serveur, jamais lue du
    corps de requête. Modèle entièrement additif.
    """
    class Statut(models.TextChoices):
        OUVERT = 'ouvert', 'Ouvert'
        SURVEILLE = 'surveille', 'Surveillé'
        MAITRISE = 'maitrise', 'Maîtrisé'
        CLOS = 'clos', 'Clos'

    class Categorie(models.TextChoices):
        TECHNIQUE = 'technique', 'Technique'
        DELAI = 'delai', 'Délai'
        COUT = 'cout', 'Coût'
        FOURNISSEUR = 'fournisseur', 'Fournisseur'
        REGLEMENTAIRE = 'reglementaire', 'Réglementaire'
        SECURITE = 'securite', 'Sécurité'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='gestion_projet_risques',
        verbose_name='Société',
    )
    projet = models.ForeignKey(
        Projet,
        on_delete=models.CASCADE,
        related_name='risques',
        verbose_name='Projet',
    )
    libelle = models.CharField(max_length=200, verbose_name='Libellé')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    categorie = models.CharField(
        max_length=14, choices=Categorie.choices,
        default=Categorie.AUTRE, verbose_name='Catégorie')
    # Échelles 1–5 ; criticité = probabilité × impact (1–25), figée au serveur.
    probabilite = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='Probabilité (1–5)')
    impact = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='Impact (1–5)')
    criticite = models.PositiveSmallIntegerField(
        default=1, verbose_name='Criticité (1–25)')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.OUVERT, verbose_name='Statut')
    mitigation = models.TextField(
        blank=True, default='', verbose_name='Plan de mitigation')
    proprietaire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='gestion_projet_risques',
        verbose_name='Propriétaire',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Risque'
        verbose_name_plural = 'Risques'
        ordering = ['-criticite', '-id']
        indexes = [
            models.Index(
                fields=['projet', '-criticite'],
                name='gp_risque_proj_crit_idx'),
        ]

    def __str__(self):
        return f'{self.libelle} (criticité {self.criticite})'

    def save(self, *args, **kwargs):
        # Criticité TOUJOURS recalculée côté serveur (jamais du corps de requête).
        self.criticite = (self.probabilite or 0) * (self.impact or 0)
        super().save(*args, **kwargs)


class ActionProjet(models.Model):
    """Une entrée du REGISTRE D'ACTIONS d'un ``Projet`` (PROJ31).

    Action de suivi (to-do de pilotage) rattachée à un projet, éventuellement à
    un ``Risque`` (action de mitigation). ``statut`` suit un cycle PROPRE au
    registre (a_faire/en_cours/fait/annule) — il ne réutilise NI n'importe AUCUNE
    clé/étiquette de ``STAGES.py`` (règle #2). ``priorite`` (basse/moyenne/haute)
    ordonne le registre ; ``responsable`` (optionnel) et ``echeance`` cadrent le
    suivi.

    Tout est multi-société : ``company`` est posée côté serveur, jamais lue du
    corps de requête. Le risque lié (optionnel) doit appartenir au MÊME projet
    (validé au sérialiseur). Modèle entièrement additif.
    """
    class Statut(models.TextChoices):
        A_FAIRE = 'a_faire', 'À faire'
        EN_COURS = 'en_cours', 'En cours'
        FAIT = 'fait', 'Fait'
        ANNULE = 'annule', 'Annulé'

    class Priorite(models.TextChoices):
        BASSE = 'basse', 'Basse'
        MOYENNE = 'moyenne', 'Moyenne'
        HAUTE = 'haute', 'Haute'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='gestion_projet_actions',
        verbose_name='Société',
    )
    projet = models.ForeignKey(
        Projet,
        on_delete=models.CASCADE,
        related_name='actions',
        verbose_name='Projet',
    )
    # Rattachement OPTIONNEL à un risque (action de mitigation).
    risque = models.ForeignKey(
        Risque,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='actions',
        verbose_name='Risque lié',
    )
    libelle = models.CharField(max_length=200, verbose_name='Libellé')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.A_FAIRE, verbose_name='Statut')
    priorite = models.CharField(
        max_length=10, choices=Priorite.choices,
        default=Priorite.MOYENNE, verbose_name='Priorité')
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='gestion_projet_actions',
        verbose_name='Responsable',
    )
    echeance = models.DateField(
        null=True, blank=True, verbose_name='Échéance')
    date_cloture = models.DateField(
        null=True, blank=True, verbose_name='Date de clôture')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Action projet'
        verbose_name_plural = 'Actions projet'
        ordering = ['statut', 'echeance', '-id']
        indexes = [
            models.Index(
                fields=['projet', 'statut'], name='gp_action_proj_stat_idx'),
        ]

    def __str__(self):
        return f'{self.libelle} ({self.get_statut_display()})'


class CompteRenduReunion(models.Model):
    """Un COMPTE-RENDU de réunion de chantier d'un ``Projet`` (PROJ32).

    Trace une réunion de chantier : ``date_reunion``, ``lieu``, liste libre des
    ``participants`` (texte), ``ordre_du_jour``, ``decisions`` prises et
    ``points_bloquants``, plus une ``date_prochaine_reunion`` optionnelle.
    Le ``redacteur`` (optionnel) est posé côté serveur. Une réunion peut, en
    option, être rattachée à un chantier (référence LÂCHE par identifiant —
    jamais d'import de ``installations``).

    Tout est multi-société : ``company`` est posée côté serveur, jamais lue du
    corps de requête. Modèle entièrement additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='gestion_projet_comptes_rendus',
        verbose_name='Société',
    )
    projet = models.ForeignKey(
        Projet,
        on_delete=models.CASCADE,
        related_name='comptes_rendus',
        verbose_name='Projet',
    )
    # Référence LÂCHE optionnelle vers installations.Chantier (aucun FK dur).
    chantier_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du chantier')
    titre = models.CharField(max_length=200, verbose_name='Titre')
    date_reunion = models.DateField(verbose_name='Date de la réunion')
    lieu = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Lieu')
    participants = models.TextField(
        blank=True, default='', verbose_name='Participants')
    ordre_du_jour = models.TextField(
        blank=True, default='', verbose_name='Ordre du jour')
    decisions = models.TextField(
        blank=True, default='', verbose_name='Décisions')
    points_bloquants = models.TextField(
        blank=True, default='', verbose_name='Points bloquants')
    date_prochaine_reunion = models.DateField(
        null=True, blank=True, verbose_name='Date de la prochaine réunion')
    redacteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='gestion_projet_comptes_rendus',
        verbose_name='Rédacteur',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Compte-rendu de réunion'
        verbose_name_plural = 'Comptes-rendus de réunion'
        ordering = ['-date_reunion', '-id']
        indexes = [
            models.Index(
                fields=['projet', '-date_reunion'],
                name='gp_cr_proj_date_idx'),
        ]

    def __str__(self):
        return f'{self.titre} ({self.date_reunion})'


class DocumentProjet(models.Model):
    """Un DOCUMENT logique (plan, note, PV…) d'un ``Projet`` (PROJ33).

    Tête de série d'un document VERSIONNÉ : il porte le ``nom`` et le ``type_doc``
    (plan/note/photo/contrat/autre) ; chaque révision est une ``VersionDocument``
    (fichier + numéro de version). La ``derniere_version`` est mise en cache côté
    serveur à chaque dépôt (jamais lue du corps de requête) pour afficher l'état
    courant sans recompter.

    Tout est multi-société : ``company`` est posée côté serveur, jamais lue du
    corps de requête. Modèle entièrement additif.
    """
    class TypeDoc(models.TextChoices):
        PLAN = 'plan', 'Plan'
        NOTE = 'note', 'Note de calcul'
        PHOTO = 'photo', 'Photo'
        CONTRAT = 'contrat', 'Contrat'
        PV = 'pv', 'Procès-verbal'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='gestion_projet_documents',
        verbose_name='Société',
    )
    projet = models.ForeignKey(
        Projet,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name='Projet',
    )
    nom = models.CharField(max_length=200, verbose_name='Nom')
    type_doc = models.CharField(
        max_length=10, choices=TypeDoc.choices,
        default=TypeDoc.AUTRE, verbose_name='Type de document')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    # Cache du dernier numéro de version déposé (posé côté serveur).
    derniere_version = models.PositiveIntegerField(
        default=0, verbose_name='Dernière version')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Document projet'
        verbose_name_plural = 'Documents projet'
        ordering = ['projet', 'nom', 'id']
        indexes = [
            models.Index(
                fields=['projet', 'type_doc'], name='gp_doc_proj_type_idx'),
        ]

    def __str__(self):
        return f'{self.nom} (v{self.derniere_version})'


class VersionDocument(models.Model):
    """Une VERSION (révision) d'un ``DocumentProjet`` (PROJ33).

    Porte le fichier déposé (``fichier``), son ``version`` (entier croissant,
    posé côté serveur = ``document.derniere_version`` + 1 — jamais lu du corps),
    un ``commentaire`` de révision et l'``auteur`` (posé côté serveur). Les
    versions ne s'écrasent jamais : chaque dépôt crée une nouvelle ligne, l'unique
    ``(document, version)`` garantit l'absence de collision.

    Tout est multi-société : ``company`` est posée côté serveur, jamais lue du
    corps de requête. Modèle entièrement additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='gestion_projet_versions_doc',
        verbose_name='Société',
    )
    document = models.ForeignKey(
        DocumentProjet,
        on_delete=models.CASCADE,
        related_name='versions',
        verbose_name='Document',
    )
    version = models.PositiveIntegerField(verbose_name='Version')
    fichier = models.FileField(
        upload_to='gestion_projet/documents/', verbose_name='Fichier')
    commentaire = models.TextField(
        blank=True, default='', verbose_name='Commentaire de révision')
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='gestion_projet_versions_doc',
        verbose_name='Auteur',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Version de document'
        verbose_name_plural = 'Versions de document'
        ordering = ['document', '-version', '-id']
        unique_together = [('document', 'version')]
        indexes = [
            models.Index(
                fields=['document', '-version'], name='gp_docver_doc_idx'),
        ]

    def __str__(self):
        return f'{self.document_id} v{self.version}'


class CommentaireProjet(models.Model):
    """Un COMMENTAIRE avec @mentions sur un objet d'un ``Projet`` (PROJ34).

    Fil de discussion interne rattaché à un ``Projet`` et, OPTIONNELLEMENT, à un
    objet précis du projet désigné par un couple typé ``(cible_type, cible_id)``
    — tâche / risque / action / jalon / document — référence LÂCHE par
    identifiant (jamais d'import inter-modèles). Le ``texte`` porte le message ;
    les utilisateurs @mentionnés sont une M2M ``mentions`` — résolus côté serveur
    et restreints à la MÊME société. ``auteur`` est posé côté serveur.

    Tout est multi-société : ``company`` est posée côté serveur, jamais lue du
    corps de requête. Modèle entièrement additif.
    """
    class CibleType(models.TextChoices):
        PROJET = 'projet', 'Projet'
        TACHE = 'tache', 'Tâche'
        RISQUE = 'risque', 'Risque'
        ACTION = 'action', 'Action'
        JALON = 'jalon', 'Jalon'
        DOCUMENT = 'document', 'Document'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='gestion_projet_commentaires',
        verbose_name='Société',
    )
    projet = models.ForeignKey(
        Projet,
        on_delete=models.CASCADE,
        related_name='commentaires',
        verbose_name='Projet',
    )
    # Cible OPTIONNELLE précise dans le projet (référence lâche typée).
    cible_type = models.CharField(
        max_length=10, choices=CibleType.choices,
        default=CibleType.PROJET, verbose_name='Type de cible')
    cible_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID de la cible')
    texte = models.TextField(verbose_name='Texte')
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='gestion_projet_commentaires',
        verbose_name='Auteur',
    )
    mentions = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='gestion_projet_mentions',
        verbose_name='Personnes mentionnées',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Commentaire projet'
        verbose_name_plural = 'Commentaires projet'
        ordering = ['-date_creation', '-id']
        indexes = [
            models.Index(
                fields=['projet', 'cible_type', 'cible_id'],
                name='gp_comm_proj_cible_idx'),
        ]

    def __str__(self):
        return f'commentaire {self.id} ({self.cible_type})'


class ModeleProjet(models.Model):
    """Un MODÈLE (template) de projet par type d'installation (PROJ35).

    Décrit une trame réutilisable de phases + tâches pour un ``type_installation``
    (résidentiel / industriel / agricole / autre) : appliqué à un ``Projet`` via
    le service ``instancier_modele``, il y crée les phases standard nécessaires et
    les tâches du modèle (``ModeleTache``). Le ``type_installation`` est un enum
    PROPRE à ce module ; il ne réutilise NI n'importe AUCUNE clé/étiquette de
    ``STAGES.py`` (règle #2).

    Tout est multi-société : ``company`` est posée côté serveur, jamais lue du
    corps de requête. Modèle entièrement additif.
    """
    class TypeInstallation(models.TextChoices):
        RESIDENTIEL = 'residentiel', 'Résidentiel'
        INDUSTRIEL = 'industriel', 'Industriel / Commercial'
        AGRICOLE = 'agricole', 'Agricole (pompage)'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='gestion_projet_modeles',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=200, verbose_name='Nom du modèle')
    type_installation = models.CharField(
        max_length=12, choices=TypeInstallation.choices,
        default=TypeInstallation.RESIDENTIEL,
        verbose_name="Type d'installation")
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Modèle de projet'
        verbose_name_plural = 'Modèles de projet'
        ordering = ['nom', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'nom'],
                name='gp_modele_company_nom_uniq'),
        ]

    def __str__(self):
        return f'{self.nom} ({self.get_type_installation_display()})'


class ModeleTache(models.Model):
    """Une tâche-type d'un ``ModeleProjet`` (PROJ35).

    Décrit une tâche à créer lors de l'instanciation du modèle, rattachée à un
    ``type_phase`` standard (étude/appro/pose/MES/réception). ``libelle``,
    ``ordre``, ``charge_estimee`` (jours-homme prévus, optionnelle) et
    ``code_wbs`` (optionnel) sont copiés tels quels sur la ``Tache`` créée. Le
    ``type_phase`` réutilise l'enum de ``PhaseProjet.TypePhase`` (même module).

    Tout est multi-société : ``company`` est posée côté serveur, jamais lue du
    corps de requête. Modèle entièrement additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='gestion_projet_modele_taches',
        verbose_name='Société',
    )
    modele = models.ForeignKey(
        ModeleProjet,
        on_delete=models.CASCADE,
        related_name='taches',
        verbose_name='Modèle',
    )
    type_phase = models.CharField(
        max_length=12, choices=PhaseProjet.TypePhase.choices,
        default=PhaseProjet.TypePhase.ETUDE,
        verbose_name='Type de phase')
    code_wbs = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Code WBS')
    libelle = models.CharField(max_length=200, verbose_name='Libellé')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    charge_estimee = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Charge estimée (j-h)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Tâche-type de modèle'
        verbose_name_plural = 'Tâches-types de modèle'
        ordering = ['modele', 'ordre', 'id']
        indexes = [
            models.Index(
                fields=['modele', 'ordre'], name='gp_modtache_mod_idx'),
        ]

    def __str__(self):
        return f'{self.modele_id} — {self.libelle}'


class PortailProjetToken(models.Model):
    """Jeton d'accès au PORTAIL D'AVANCEMENT CLIENT d'un ``Projet`` (PROJ37).

    Donne au client un lien PUBLIC tokenisé (non authentifié) vers une vue
    d'avancement SANS AUCUN coût, budget ni marge — données strictement internes
    qui ne traversent jamais ce portail (voir ``selectors.portail_avancement_
    client``). Le ``token`` (256 bits URL-safe) est généré côté serveur ;
    ``actif`` permet de révoquer l'accès sans supprimer la ligne.

    Tout est multi-société : ``company`` est posée côté serveur, jamais lue du
    corps de requête. Relation 1–1 souple avec le projet. Modèle entièrement
    additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='gestion_projet_portail_tokens',
        verbose_name='Société',
    )
    projet = models.OneToOneField(
        Projet,
        on_delete=models.CASCADE,
        related_name='portail_token',
        verbose_name='Projet',
    )
    token = models.CharField(
        max_length=64, unique=True, default=_generer_token_portail,
        verbose_name='Jeton')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Jeton de portail client'
        verbose_name_plural = 'Jetons de portail client'
        ordering = ['-id']
        indexes = [
            models.Index(fields=['token'], name='gp_portail_token_idx'),
        ]

    def __str__(self):
        return f'portail {self.projet_id} ({"actif" if self.actif else "off"})'


class SousTraitant(models.Model):
    """Un SOUS-TRAITANT du carnet d'adresses de la société (PROJ38).

    Annuaire léger de prestataires externes mobilisables sur les projets
    (terrassement, électricité, levage…). ``specialite`` qualifie l'activité ;
    ``contact`` / ``telephone`` / ``email`` sont les coordonnées. Données INTERNES
    de pilotage — jamais exposées au client final.

    Tout est multi-société : ``company`` est posée côté serveur, jamais lue du
    corps de requête. Modèle entièrement additif.

    ARC22 — RÉGRESSION DC34 constatée : ce carnet est un 3e référentiel
    sous-traitant parallèle, alors que DC34 a unifié le sous-traitant sur
    ``stock.Fournisseur`` (``type=SERVICE``) + son satellite
    ``stock.SousTraitantProfile`` (voir ``apps/installations/views/
    soustraitant.py``, qui orchestre déjà EXCLUSIVEMENT via ce master).
    ``fournisseur`` ci-dessous est le lien ADDITIF (nullable) vers ce master :
    le carnet ``gestion_projet`` local N'EST PAS supprimé/fusionné par ARC22
    (ça reste la propriété de DC34, cf. son annotation) — seul un NOUVEAU
    sous-traitant projet créé via ``services.creer_sous_traitant_via_master``
    pose ce lien ; le backfill (``manage.py backfill_sous_traitant_fournisseur``)
    rattache les lignes EXISTANTES par correspondance nom/téléphone, sans
    jamais fusionner ni geler les colonnes dupliquées (hors scope ARC22).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='gestion_projet_sous_traitants',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=200, verbose_name='Nom / raison sociale')
    specialite = models.CharField(
        max_length=150, blank=True, default='', verbose_name='Spécialité')
    contact = models.CharField(
        max_length=150, blank=True, default='', verbose_name='Contact')
    telephone = models.CharField(
        max_length=40, blank=True, default='', verbose_name='Téléphone')
    email = models.EmailField(blank=True, default='', verbose_name='E-mail')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    # ARC22 — lien ADDITIF (nullable) vers le master sous-traitant unifié DC34
    # (``stock.Fournisseur`` type=SERVICE). String-FK : ``gestion_projet``
    # n'importe jamais ``apps.stock.models`` (frontière cross-app, CLAUDE.md).
    # SET_NULL : la suppression du Fournisseur master ne casse pas le carnet
    # projet local (comportement actuel préservé pour les lignes non liées).
    fournisseur = models.ForeignKey(
        'stock.Fournisseur',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='gestion_projet_sous_traitants_lies',
        verbose_name='Fournisseur (master DC34)',
        help_text=(
            'Lien optionnel vers le référentiel sous-traitant unifié DC34 '
            '(stock.Fournisseur type=service). Posé automatiquement pour '
            'tout nouveau sous-traitant créé via le master, ou par le '
            'backfill pour les lignes existantes correspondantes.'),
    )

    class Meta:
        verbose_name = 'Sous-traitant'
        verbose_name_plural = 'Sous-traitants'
        ordering = ['nom', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'nom'],
                name='gp_soustraitant_co_nom_uniq'),
        ]

    def __str__(self):
        return self.nom


class LotSousTraitance(models.Model):
    """Un LOT confié à un ``SousTraitant`` sur un ``Projet`` (PROJ38).

    Représente une partie des travaux sous-traitée : ``libelle`` du lot,
    ``montant`` (coût INTERNE de sous-traitance — jamais exposé au client),
    période, et ``statut`` PROPRE au lot (prévu/en_cours/réceptionné/annulé) — il
    ne réutilise NI n'importe AUCUNE clé/étiquette de ``STAGES.py`` (règle #2).

    Tout est multi-société : ``company`` est posée côté serveur, jamais lue du
    corps de requête. Le sous-traitant doit appartenir à la MÊME société (validé
    au sérialiseur). Modèle entièrement additif.
    """
    class Statut(models.TextChoices):
        PREVU = 'prevu', 'Prévu'
        EN_COURS = 'en_cours', 'En cours'
        RECEPTIONNE = 'receptionne', 'Réceptionné'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='gestion_projet_lots_st',
        verbose_name='Société',
    )
    projet = models.ForeignKey(
        Projet,
        on_delete=models.CASCADE,
        related_name='lots_sous_traitance',
        verbose_name='Projet',
    )
    sous_traitant = models.ForeignKey(
        SousTraitant,
        on_delete=models.PROTECT,
        related_name='lots',
        verbose_name='Sous-traitant',
    )
    libelle = models.CharField(max_length=200, verbose_name='Libellé du lot')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    # Coût INTERNE de sous-traitance — jamais exposé au client.
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant (interne)')
    statut = models.CharField(
        max_length=12, choices=Statut.choices,
        default=Statut.PREVU, verbose_name='Statut')
    date_debut = models.DateField(
        null=True, blank=True, verbose_name='Date de début')
    date_fin = models.DateField(
        null=True, blank=True, verbose_name='Date de fin')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Lot de sous-traitance'
        verbose_name_plural = 'Lots de sous-traitance'
        ordering = ['projet', 'id']
        indexes = [
            models.Index(
                fields=['projet', 'statut'], name='gp_lotst_proj_stat_idx'),
        ]

    def __str__(self):
        return f'{self.libelle} ({self.sous_traitant_id})'


class ClotureProjet(models.Model):
    """Clôture d'un ``Projet`` + RETOUR D'EXPÉRIENCE (REX) (PROJ38).

    Enregistre la réception/clôture d'un projet (``date_cloture``,
    ``date_reception``) et capitalise le retour d'expérience : ``points_positifs``,
    ``points_amelioration`` et ``recommandations`` pour les projets futurs.
    ``cloture_par`` est posé côté serveur. Relation 1–1 avec le projet (une seule
    clôture). Données INTERNES — jamais exposées au client.

    Tout est multi-société : ``company`` est posée côté serveur, jamais lue du
    corps de requête. Modèle entièrement additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='gestion_projet_clotures',
        verbose_name='Société',
    )
    projet = models.OneToOneField(
        Projet,
        on_delete=models.CASCADE,
        related_name='cloture',
        verbose_name='Projet',
    )
    date_cloture = models.DateField(verbose_name='Date de clôture')
    date_reception = models.DateField(
        null=True, blank=True, verbose_name='Date de réception')
    points_positifs = models.TextField(
        blank=True, default='', verbose_name='Points positifs')
    points_amelioration = models.TextField(
        blank=True, default='', verbose_name="Points d'amélioration")
    recommandations = models.TextField(
        blank=True, default='', verbose_name='Recommandations')
    cloture_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='gestion_projet_clotures',
        verbose_name='Clôturé par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Clôture de projet'
        verbose_name_plural = 'Clôtures de projet'
        ordering = ['-date_cloture', '-id']

    def __str__(self):
        return f'clôture {self.projet_id} ({self.date_cloture})'


class SituationTravaux(models.Model):
    """Un DÉCOMPTE PROGRESSIF (situation de travaux) d'un ``Projet`` (XPRJ4).

    Pratique BTP marocaine : une situation facture l'avancement RÉEL des
    travaux depuis la dernière situation (cumul antérieur → cumul période),
    plutôt qu'un jalon fixe (complète PROJ27, facturation au %, qui ne porte
    pas de cumul antérieur/période). Le ``numero`` est INCRÉMENTAL PAR PROJET
    (jamais ``count()+1`` — voir ``services.prochain_numero_situation``, verrou
    de ligne + retry sur le ``Projet``) ; ``periode`` est le mois/la période
    couverte par le décompte.

    Le ``statut`` est une machine d'état PROPRE à la situation
    (brouillon/validee/facturee) — il ne réutilise NI n'importe AUCUNE
    clé/étiquette de ``STAGES.py`` (règle #2), et n'altère JAMAIS le statut du
    devis/BC/facture (couche séparée, règle #4). ``retenue_garantie_pct`` est
    optionnelle : le POURCENTAGE déduit de la facture d'acompte générée (le
    SUIVI de sa LIBÉRATION vit déjà dans ``contrats`` CONTRAT28 — référence
    LÂCHE ``contrat_id``, aucun import de ``contrats``).

    ``facture_id`` référence LÂCHEMENT la ``ventes.Facture`` d'acompte générée
    à la validation (posé côté serveur, jamais lu du corps de requête) —
    empêche une double-génération (une situation VALIDÉE/FACTURÉE ne régénère
    jamais).

    Tout est multi-société : ``company`` est posée côté serveur, jamais lue du
    corps de requête. Modèle entièrement additif.
    """
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        VALIDEE = 'validee', 'Validée'
        FACTUREE = 'facturee', 'Facturée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='gestion_projet_situations',
        verbose_name='Société',
    )
    projet = models.ForeignKey(
        Projet,
        on_delete=models.CASCADE,
        related_name='situations',
        verbose_name='Projet',
    )
    # Incrémental PAR PROJET (jamais count()+1) — posé côté serveur.
    numero = models.PositiveIntegerField(verbose_name='N° de situation')
    periode = models.DateField(
        verbose_name='Période (1er jour du mois couvert)')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    # % de retenue de garantie DÉDUIT de la facture générée (optionnel).
    retenue_garantie_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0')),
                    MaxValueValidator(Decimal('100'))],
        verbose_name='Retenue de garantie (%)')
    # Référence LÂCHE optionnelle vers contrats.Contrat (CONTRAT28 — libération
    # de la RG) — aucun FK dur, aucun import de ``contrats``.
    contrat_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du contrat (RG)')
    # Référence LÂCHE vers la ventes.Facture d'acompte générée à la validation.
    facture_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="ID de la facture d'acompte")
    date_validation = models.DateTimeField(
        null=True, blank=True, verbose_name='Date de validation')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Situation de travaux'
        verbose_name_plural = 'Situations de travaux'
        ordering = ['projet', 'numero']
        constraints = [
            models.UniqueConstraint(
                fields=['projet', 'numero'],
                name='gp_situation_projet_numero_uniq'),
        ]
        indexes = [
            models.Index(
                fields=['projet', 'numero'],
                name='gp_situation_proj_num_idx'),
        ]

    def __str__(self):
        return f'{self.projet.code} — situation n°{self.numero}'


class LigneSituation(models.Model):
    """Une ligne (lot / ligne de budget) d'une ``SituationTravaux`` (XPRJ4).

    ``montant_marche_ht`` est le montant HT total du marché pour ce lot ;
    ``avancement_cumule_pct`` est le % d'avancement CUMULÉ (0–100) déclaré à
    cette situation. Les montants sont CALCULÉS côté serveur (jamais lus du
    corps de requête) par ``services.calculer_montants_situation`` :

        montant_cumule       = montant_marche_ht × avancement_cumule_pct / 100
        montant_cumule_anterieur = montant_cumule de la MÊME ligne (même
                                    libellé) à la situation n°N-1 du projet
                                    (0 si n°1 ou ligne absente avant)
        montant_periode       = montant_cumule − montant_cumule_anterieur

    Tout est multi-société : ``company`` est posée côté serveur, jamais lue du
    corps de requête. La ``situation`` doit appartenir à la MÊME société.
    Modèle entièrement additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='gestion_projet_lignes_situation',
        verbose_name='Société',
    )
    situation = models.ForeignKey(
        SituationTravaux,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='Situation',
    )
    libelle = models.CharField(
        max_length=200, verbose_name='Libellé (lot / ligne de budget)')
    montant_marche_ht = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant marché HT')
    avancement_cumule_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0')),
                    MaxValueValidator(Decimal('100'))],
        verbose_name='Avancement cumulé (%)')
    # ── Calculés côté serveur (jamais lus du corps de requête) ───────────────
    montant_cumule_anterieur = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant cumulé antérieur')
    montant_periode = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant de la période')
    montant_cumule = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant cumulé')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Ligne de situation'
        verbose_name_plural = 'Lignes de situation'
        ordering = ['situation', 'id']
        indexes = [
            models.Index(
                fields=['situation'], name='gp_lignesit_situation_idx'),
        ]

    def __str__(self):
        return f'{self.situation_id} — {self.libelle}'


class ChronoEnCours(models.Model):
    """Chrono ACTIF (start/stop) d'un utilisateur sur une ``Tache`` (XPRJ5).

    Modèle LÉGER : un seul enregistrement PAR UTILISATEUR peut exister à la
    fois (``OneToOneField`` sur ``user`` — démarrer un nouveau chrono ARRÊTE
    implicitement l'ancien, voir ``services.demarrer_chrono``). ``demarre_a``
    est posé côté serveur (jamais lu du corps de requête). À l'arrêt
    (``services.arreter_chrono``), l'enregistrement est SUPPRIMÉ après avoir
    créé la ``Timesheet`` brouillon correspondante.

    Tout est multi-société : ``company`` est posée côté serveur, jamais lue du
    corps de requête. Modèle entièrement additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='gestion_projet_chronos',
        verbose_name='Société',
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='gestion_projet_chrono_actif',
        verbose_name='Utilisateur',
    )
    tache = models.ForeignKey(
        Tache,
        on_delete=models.CASCADE,
        related_name='chronos',
        verbose_name='Tâche',
    )
    demarre_a = models.DateTimeField(verbose_name='Démarré à')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Chrono en cours'
        verbose_name_plural = 'Chronos en cours'
        ordering = ['-demarre_a']

    def __str__(self):
        return f'{self.user_id} — tâche {self.tache_id} ({self.demarre_a})'


class RecurrenceTache(models.Model):
    """Gabarit de tâche RÉCURRENTE d'un projet (XPRJ13).

    Génère la PROCHAINE ``Tache`` à échéance via
    ``manage.py generer_taches_recurrentes`` (branchable Celery beat, pattern
    FG1/XPRJ7). ``prochaine_echeance`` avance à chaque génération ; la
    récurrence s'arrête à ``date_fin`` OU après ``nb_occurrences`` (l'un des
    deux, optionnels ; aucun des deux = récurrence sans fin).

    Le gabarit porte les champs minimaux d'une ``Tache`` à créer : libellé,
    phase (optionnelle), charge estimée, assigné (XPRJ10). Tout est
    multi-société : ``company`` est posée côté serveur, jamais lue du corps de
    requête. Modèle entièrement additif.
    """
    class Regle(models.TextChoices):
        HEBDOMADAIRE = 'hebdomadaire', 'Hebdomadaire'
        MENSUELLE = 'mensuelle', 'Mensuelle'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='gp_recurrences_tache',
        verbose_name='Société',
    )
    projet = models.ForeignKey(
        Projet,
        on_delete=models.CASCADE,
        related_name='recurrences_tache',
        verbose_name='Projet',
    )
    # ── Gabarit de la tâche à générer ────────────────────────────────────────
    libelle = models.CharField(max_length=200, verbose_name='Libellé')
    phase = models.ForeignKey(
        PhaseProjet,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='recurrences_tache',
        verbose_name='Phase',
    )
    charge_estimee = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Charge estimée (j-h)')
    assigne = models.ForeignKey(
        'RessourceProfil',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='recurrences_tache',
        verbose_name='Assigné',
    )
    # ── Règle de récurrence ──────────────────────────────────────────────────
    regle = models.CharField(
        max_length=15, choices=Regle.choices, verbose_name='Règle')
    intervalle = models.PositiveSmallIntegerField(
        default=1, verbose_name='Intervalle')
    prochaine_echeance = models.DateField(verbose_name='Prochaine échéance')
    date_fin = models.DateField(
        null=True, blank=True, verbose_name='Fin de récurrence')
    nb_occurrences = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Nombre d'occurrences")
    nb_generees = models.PositiveIntegerField(
        default=0, verbose_name='Occurrences générées')
    actif = models.BooleanField(default=True, verbose_name='Active')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Récurrence de tâche'
        verbose_name_plural = 'Récurrences de tâches'
        ordering = ['prochaine_echeance', 'id']
        indexes = [
            models.Index(
                fields=['actif', 'prochaine_echeance'],
                name='gp_recur_actif_echeance_idx'),
        ]

    def __str__(self):
        return f'{self.libelle} ({self.get_regle_display()})'


class ItemChecklistTache(models.Model):
    """Item de checklist d'une ``Tache`` (XPRJ14).

    ``fait`` bascule côté serveur via l'action ``toggle`` du viewset : quand il
    passe à ``True``, ``fait_par``/``fait_le`` sont posés côté serveur (jamais
    lus du corps de requête) ; quand il repasse à ``False``, ils sont
    réinitialisés. Le % d'items cochés d'une tâche est une SUGGESTION affichée
    à l'``avancement_pct`` — jamais un écrasement silencieux d'un avancement
    saisi manuellement (voir sérialiseur ``Tache``).

    Tout est multi-société : ``company`` est posée côté serveur, jamais lue du
    corps de requête. Modèle entièrement additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='gp_items_checklist',
        verbose_name='Société',
    )
    tache = models.ForeignKey(
        Tache,
        on_delete=models.CASCADE,
        related_name='items_checklist',
        verbose_name='Tâche',
    )
    libelle = models.CharField(max_length=200, verbose_name='Libellé')
    fait = models.BooleanField(default=False, verbose_name='Fait')
    fait_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
        verbose_name='Fait par',
    )
    fait_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Fait le')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Item de checklist'
        verbose_name_plural = 'Items de checklist'
        ordering = ['tache', 'ordre', 'id']
        indexes = [
            models.Index(
                fields=['tache'], name='gp_item_checklist_tache_idx'),
        ]

    def __str__(self):
        return f'{self.tache_id} — {self.libelle}'


class PointAvancement(models.Model):
    """Point d'avancement PÉRIODIQUE d'un projet — statut RAG (XPRJ15).

    Historisé (une ligne par point, jamais mise à jour) : ``sante`` capture un
    statut RAG (Rouge/Orange/Vert) PROPRE à ce module (jamais une clé de
    ``STAGES.py``, règle #2), ``avancement_pct`` est FIGÉ au moment du point
    (photo, distincte du roll-up temps réel PROJ9). Le DERNIER point d'un
    projet alimente la colonne « santé » du portefeuille (``portefeuille``,
    PROJ36) et du dashboard.

    Tout est multi-société : ``company`` est posée côté serveur, jamais lue du
    corps de requête ; ``auteur`` est posé côté serveur. Modèle entièrement
    additif.
    """
    class Sante(models.TextChoices):
        VERT = 'vert', 'Vert'
        ORANGE = 'orange', 'Orange'
        ROUGE = 'rouge', 'Rouge'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='gp_points_avancement',
        verbose_name='Société',
    )
    projet = models.ForeignKey(
        Projet,
        on_delete=models.CASCADE,
        related_name='points_avancement',
        verbose_name='Projet',
    )
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
        verbose_name='Auteur',
    )
    sante = models.CharField(
        max_length=10, choices=Sante.choices, verbose_name='Santé')
    # Avancement FIGÉ au moment du point (photo) — distinct du roll-up temps
    # réel (PROJ9).
    avancement_pct = models.PositiveSmallIntegerField(
        default=0, validators=[MaxValueValidator(100)],
        verbose_name='Avancement (%)')
    realisations = models.TextField(
        blank=True, default='', verbose_name='Réalisations')
    risques = models.TextField(
        blank=True, default='', verbose_name='Risques')
    prochaines_etapes = models.TextField(
        blank=True, default='', verbose_name='Prochaines étapes')
    date_point = models.DateField(verbose_name='Date du point')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Point d'avancement"
        verbose_name_plural = "Points d'avancement"
        ordering = ['-date_point', '-id']
        indexes = [
            models.Index(
                fields=['projet', '-date_point'],
                name='gp_point_av_projet_date_idx'),
        ]

    def __str__(self):
        return f'{self.projet_id} — {self.date_point} ({self.sante})'


class ReglageTemps(models.Model):
    """Réglages SINGLETON par société pour l'encodage des temps (ZPRJ1).

    Odoo Timesheets a des « rounding rules » + « time-encoding unit » ;
    jusqu'ici XPRJ5 (chrono) codait en dur l'arrondi au quart d'heure et rien
    n'était paramétrable. ``arrondi_minutes`` + ``mode_arrondi`` pilotent le
    helper ``services.arrondir_duree`` (consommé par le chrono XPRJ5 et — le
    jour où elle existera — la grille hebdomadaire XPRJ6), ``heures_par_jour``
    est lu par les sélecteurs ``plan_de_charge``/``nivellement_charge`` à la
    place de la constante ``_HEURES_PAR_JOUR_DEFAUT``.

    Relation 1–1 avec la société : ``get_or_create`` scopé société (jamais
    créé plusieurs fois pour une même société). Tout est multi-société :
    ``company`` est posée côté serveur, jamais lue du corps de requête.
    Modèle entièrement additif.
    """
    class ModeArrondi(models.TextChoices):
        INFERIEUR = 'inferieur', 'Arrondi au pas inférieur'
        SUPERIEUR = 'superieur', 'Arrondi au pas supérieur'
        PROCHE = 'proche', 'Arrondi au pas le plus proche'

    class UniteSaisie(models.TextChoices):
        HEURES = 'heures', 'Heures'
        JOURS = 'jours', 'Jours'

    company = models.OneToOneField(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='gp_reglage_temps',
        verbose_name='Société',
    )
    arrondi_minutes = models.PositiveSmallIntegerField(
        default=15, verbose_name="Pas d'arrondi (minutes)")
    mode_arrondi = models.CharField(
        max_length=10, choices=ModeArrondi.choices,
        default=ModeArrondi.SUPERIEUR, verbose_name="Mode d'arrondi")
    unite_saisie = models.CharField(
        max_length=10, choices=UniteSaisie.choices,
        default=UniteSaisie.HEURES, verbose_name='Unité de saisie')
    heures_par_jour = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal('8'),
        verbose_name='Heures par jour')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Réglage temps'
        verbose_name_plural = 'Réglages temps'
        ordering = ['id']

    def __str__(self):
        return f'Réglages temps — {self.company_id}'


class EvaluationProjet(models.Model):
    """Enquête de satisfaction client (CSAT) par ``Projet`` (ZPRJ7).

    Odoo Project agrège une note de satisfaction client par tâche/projet ;
    rien d'équivalent ne existait côté ``gestion_projet`` (le SAV a son CSAT
    séparé). Relation 1–1 avec le projet : un seul dépôt possible (le
    ``token`` est régénéré/récupéré via ``projets/<id>/lien-evaluation/`` mais
    la NOTE ne peut être soumise qu'UNE FOIS — un second POST public est
    refusé, voir ``public_views.evaluation_projet``).

    Le ``token`` (256 bits URL-safe, généré côté serveur — même génération que
    ``PortailProjetToken``) donne accès à une vue PUBLIQUE non authentifiée
    (``portail/evaluation/<token>/``) : AUCUN coût/budget/marge n'y est jamais
    exposé (formulaire de notation pur). Tout est multi-société : ``company``
    est posée côté serveur, jamais lue du corps de requête. Modèle entièrement
    additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='gestion_projet_evaluations',
        verbose_name='Société',
    )
    projet = models.OneToOneField(
        Projet,
        on_delete=models.CASCADE,
        related_name='evaluation',
        verbose_name='Projet',
    )
    token = models.CharField(
        max_length=64, unique=True, default=_generer_token_portail,
        verbose_name='Jeton')
    # Note posée par le CLIENT via le portail public — nullable tant qu'aucun
    # dépôt n'a eu lieu (le lien peut être créé/envoyé avant la clôture).
    note = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='Note (1-5)')
    commentaire = models.TextField(
        blank=True, default='', verbose_name='Commentaire')
    soumis_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Soumis le')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Évaluation projet (CSAT)'
        verbose_name_plural = 'Évaluations projet (CSAT)'
        ordering = ['-id']
        indexes = [
            models.Index(fields=['token'], name='gp_eval_token_idx'),
        ]

    def __str__(self):
        return f'Évaluation {self.projet_id} — {self.note or "en attente"}'
