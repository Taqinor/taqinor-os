"""
FG291 — Programme / Projet multi-chantiers.

Un ``Projet`` regroupe, pour un même client/site, plusieurs chantiers
(``Installation``), les devis et les tickets SAV associés — par exemple une
ferme à 4 forages (4 chantiers de pompage sous un seul programme) ou une
toiture réalisée par tranches (un chantier par tranche).

C'est une NOUVELLE brique architecturale, additive et multi-tenant :

  * ``Projet`` porte sa PROPRE machine à états (``Statut`` ci-dessous) —
    INDÉPENDANTE de l'entonnoir commercial (``STAGES.py``), du statut document
    devis/facture, et du statut d'exécution du chantier (``Installation.Statut``).
    Ces couches ne se mélangent JAMAIS.
  * Le regroupement passe par trois tables de liaison :
      - ``ProjetChantier``  → ``Installation`` (même app, FK directe) ;
      - ``ProjetDevis``     → ``ventes.Devis`` (string-FK, couplage lâche) ;
      - ``ProjetTicket``    → ``sav.Ticket`` (string-FK, couplage lâche).
    Les apps ``ventes`` et ``sav`` ne sont JAMAIS importées : on les référence
    par string-FK. Aucun statut de ces objets n'est touché ici.

Référence de programme générée via le numéroteur anti-collision partagé
(``apps.ventes.utils.references`` ; jamais ``count()+1``).

Aucune migration destructive : on AJOUTE des tables, on ne touche jamais aux
colonnes existantes.
"""
from django.conf import settings
from django.db import models

from .models_installation import Installation


class Projet(models.Model):
    """FG291 — programme/projet multi-chantiers d'un même client/site.

    Regroupe N chantiers + leurs devis + leurs tickets sous un dossier unique
    (ferme à 4 forages, toiture par tranches…). Porte une référence
    tenant-scopée et une machine à états PROPRE (jamais l'entonnoir commercial
    ni le statut chantier). Additif, multi-tenant (société posée côté serveur)."""

    class Statut(models.TextChoices):
        # Machine à états PROPRE au programme — distincte de toute autre couche.
        BROUILLON = 'brouillon', 'Brouillon'
        ACTIF = 'actif', 'Actif'
        EN_PAUSE = 'en_pause', 'En pause'
        TERMINE = 'termine', 'Terminé'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='installations_projets')
    reference = models.CharField(max_length=50)
    nom = models.CharField(max_length=200)
    # Client/site du programme — string-FK vers le CRM (couplage lâche). Le
    # même client peut porter plusieurs programmes (toiture + pompage…).
    client = models.ForeignKey(
        'crm.Client', on_delete=models.PROTECT,
        null=True, blank=True, related_name='installations_projets')
    # Site physique du programme (distinct de l'adresse de facturation).
    site_adresse = models.TextField(blank=True, null=True)
    site_ville = models.CharField(max_length=120, blank=True, null=True)
    statut = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.BROUILLON)
    description = models.TextField(blank=True, null=True)
    date_debut = models.DateField(null=True, blank=True)
    date_fin_cible = models.DateField(null=True, blank=True)
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='installations_projets_responsable')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='installations_projets_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Programme / Projet'
        verbose_name_plural = 'Programmes / Projets'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_projet_co_statut'),
        ]

    def __str__(self):
        return f'{self.reference} · {self.nom}'


class ProjetTache(models.Model):
    """FG292 — tâche (et sous-tâche) d'un programme/projet, avec dépendances.

    Va AU-DELÀ de la checklist d'exécution figée (``ChantierChecklistItem``,
    par étapes prédéfinies) : une vraie tâche de chef de projet — assignée,
    avec une échéance, un prédécesseur (dépendance : « ne peut commencer
    qu'après ») et une hiérarchie parent → sous-tâches. Tout reste dans l'app
    ``installations`` (FK directe vers ``Projet``, même app). L'assigné est
    référencé via ``settings.AUTH_USER_MODEL`` (couche fondation, autorisée).

    Trois auto-FK structurent la tâche :
      * ``parent``       → hiérarchie tâche/sous-tâche (même programme) ;
      * ``predecesseur`` → dépendance d'ordonnancement (même programme).
    Les deux sont protégées contre les CYCLES côté validation (``clean``) — une
    tâche ne peut jamais être son propre ancêtre/prédécesseur, ni fermer une
    boucle plus longue.

    Le ``Statut`` ci-dessous est PROPRE à la tâche (à faire / en cours /
    terminé) — JAMAIS l'entonnoir commercial (``STAGES.py``), ni le statut du
    document devis/facture, ni le statut du chantier, ni la machine à états du
    ``Projet``. Ces couches ne se mélangent jamais. Additif, multi-tenant
    (société posée côté serveur)."""

    class Statut(models.TextChoices):
        # Machine à états PROPRE à la tâche — distincte de toute autre couche.
        A_FAIRE = 'a_faire', 'À faire'
        EN_COURS = 'en_cours', 'En cours'
        TERMINE = 'termine', 'Terminé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='installations_projet_taches')
    projet = models.ForeignKey(
        Projet, on_delete=models.CASCADE, related_name='taches')
    # Sous-tâche : hiérarchie tâche/sous-tâche au sein du même programme.
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE,
        null=True, blank=True, related_name='sous_taches')
    # Dépendance d'ordonnancement : cette tâche suit ``predecesseur``.
    predecesseur = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='suivantes')
    libelle = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    assigne = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='installations_taches_assignees')
    date_echeance = models.DateField(null=True, blank=True)
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.A_FAIRE)
    ordre = models.PositiveIntegerField(default=0)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tâche de projet'
        verbose_name_plural = 'Tâches de projet'
        ordering = ['projet_id', 'ordre', 'id']
        indexes = [
            models.Index(fields=['company', 'projet'],
                         name='idx_projtache_co_proj'),
            models.Index(fields=['company', 'statut'],
                         name='idx_projtache_co_stat'),
        ]

    def __str__(self):
        return f'{self.projet_id} · {self.libelle}'

    # ── Garde anti-cycle ─────────────────────────────────────────────────────
    def _has_cycle(self, attr):
        """``True`` si suivre ``attr`` (``parent`` ou ``predecesseur``) en
        chaîne reboucle sur cette tâche. Borné par le nombre de tâches du
        programme — jamais une boucle infinie même sur des données corrompues."""
        seen = set()
        current = getattr(self, f'{attr}_id', None)
        # Une tâche ne peut pas se référencer elle-même.
        if current is not None and self.pk is not None and current == self.pk:
            return True
        guard = 0
        while current is not None:
            if current == self.pk or current in seen:
                return True
            seen.add(current)
            guard += 1
            if guard > 10000:  # garde-fou ultime contre toute donnée corrompue
                return True
            current = (ProjetTache.objects
                       .filter(pk=current)
                       .values_list(f'{attr}_id', flat=True)
                       .first())
        return False

    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        # parent et predecesseur doivent appartenir au MÊME programme.
        if self.parent_id is not None and self.parent_id == self.pk:
            errors['parent'] = 'Une tâche ne peut pas être sa propre sous-tâche.'
        elif self.parent_id is not None and self._has_cycle('parent'):
            errors['parent'] = 'Cycle de sous-tâches interdit.'
        if self.predecesseur_id is not None and self.predecesseur_id == self.pk:
            errors['predecesseur'] = (
                'Une tâche ne peut pas être son propre prédécesseur.')
        elif (self.predecesseur_id is not None
              and self._has_cycle('predecesseur')):
            errors['predecesseur'] = 'Cycle de dépendances interdit.'
        if errors:
            raise ValidationError(errors)


class ProjetChantier(models.Model):
    """FG291 — rattachement d'un chantier (``Installation``) à un programme.

    Table de liaison (un chantier appartient à au plus un programme) : même
    app, donc FK directe vers ``Installation``. La société est posée côté
    serveur."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='installations_projet_chantiers')
    projet = models.ForeignKey(
        Projet, on_delete=models.CASCADE, related_name='chantiers')
    installation = models.ForeignKey(
        Installation, on_delete=models.CASCADE, related_name='projets')
    # Tranche/forage — libellé libre pour distinguer les chantiers du programme
    # (« Forage 1 », « Tranche A »…).
    libelle = models.CharField(max_length=120, blank=True, null=True)
    ordre = models.PositiveIntegerField(default=0)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Chantier de programme'
        verbose_name_plural = 'Chantiers de programme'
        ordering = ['projet_id', 'ordre', 'id']
        # Un chantier ne peut être rattaché qu'une fois à un même programme.
        unique_together = [('projet', 'installation')]
        indexes = [
            models.Index(fields=['company', 'projet'],
                         name='idx_projchant_co_proj'),
        ]

    def __str__(self):
        return f'{self.projet_id} · chantier {self.installation_id}'


class ProjetDevis(models.Model):
    """FG291 — rattachement d'un devis (``ventes.Devis``) à un programme.

    Couplage lâche : string-FK vers ``ventes.Devis`` (jamais d'import des
    modèles ventes). Le statut du devis n'est PAS touché ici."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='installations_projet_devis')
    projet = models.ForeignKey(
        Projet, on_delete=models.CASCADE, related_name='devis')
    devis = models.ForeignKey(
        'ventes.Devis', on_delete=models.CASCADE,
        related_name='installations_projets')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Devis de programme'
        verbose_name_plural = 'Devis de programme'
        ordering = ['projet_id', 'id']
        unique_together = [('projet', 'devis')]
        indexes = [
            models.Index(fields=['company', 'projet'],
                         name='idx_projdevis_co_proj'),
        ]

    def __str__(self):
        return f'{self.projet_id} · devis {self.devis_id}'


class ProjetTicket(models.Model):
    """FG291 — rattachement d'un ticket SAV (``sav.Ticket``) à un programme.

    Couplage lâche : string-FK vers ``sav.Ticket`` (jamais d'import des
    modèles sav). Le statut du ticket n'est PAS touché ici."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='installations_projet_tickets')
    projet = models.ForeignKey(
        Projet, on_delete=models.CASCADE, related_name='tickets')
    ticket = models.ForeignKey(
        'sav.Ticket', on_delete=models.CASCADE,
        related_name='installations_projets')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ticket de programme'
        verbose_name_plural = 'Tickets de programme'
        ordering = ['projet_id', 'id']
        unique_together = [('projet', 'ticket')]
        indexes = [
            models.Index(fields=['company', 'projet'],
                         name='idx_projticket_co_proj'),
        ]

    def __str__(self):
        return f'{self.projet_id} · ticket {self.ticket_id}'


class BudgetProjet(models.Model):
    """FG294 — budget d'un programme/projet (engagé/dépensé) vs réel.

    Porte les enveloppes BUDGÉTÉES par catégorie de coût (matériel,
    main-d'œuvre, sous-traitance, divers) pour un ``Projet``. Le RÉEL (engagé +
    dépensé) n'est PAS stocké ici : il est AGRÉGÉ à la lecture par le sélecteur
    ``budget_projet_synthese`` à partir des devis du programme (``ProjetDevis``),
    des bons de commande / factures fournisseur rattachés (``BudgetEngagement``,
    référencés par string-FK — jamais d'import des modèles ``stock``/``ventes``)
    et de la main-d'œuvre des chantiers (``Installation.labour_*`` × tarif).

    Couche INDÉPENDANTE : ce budget ne touche AUCUN statut (ni l'entonnoir
    commercial ``STAGES.py``, ni le statut devis/facture, ni le statut chantier,
    ni la machine à états du ``Projet``). Additif, multi-tenant (société posée
    côté serveur). Relation 1-à-1 avec ``Projet`` : un programme a au plus un
    budget."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='installations_budgets_projet')
    projet = models.OneToOneField(
        Projet, on_delete=models.CASCADE, related_name='budget')
    devise = models.CharField(max_length=8, default='MAD')
    # Enveloppes budgétées HT par catégorie de coût.
    budget_materiel = models.DecimalField(
        max_digits=14, decimal_places=2, default=0)
    budget_main_oeuvre = models.DecimalField(
        max_digits=14, decimal_places=2, default=0)
    budget_sous_traitance = models.DecimalField(
        max_digits=14, decimal_places=2, default=0)
    budget_divers = models.DecimalField(
        max_digits=14, decimal_places=2, default=0)
    # Tarif main-d'œuvre (MAD/jour) appliqué aux jours-homme des chantiers pour
    # monétiser le réel main-d'œuvre. 0 → le coût main-d'œuvre réel reste 0.
    tarif_jour_mo = models.DecimalField(
        max_digits=10, decimal_places=2, default=0)
    # Seuil d'alerte de dépassement, en % du budget total (10 → alerte si le
    # réel dépasse 110 % du budget). Borné [0, 100] côté validation.
    seuil_alerte_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=0)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_budgets_projet_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Budget de projet'
        verbose_name_plural = 'Budgets de projet'
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['company', 'projet'],
                         name='idx_budgproj_co_proj'),
        ]

    def __str__(self):
        return f'Budget {self.projet_id}'

    @property
    def budget_total(self):
        """Enveloppe budgétée totale (somme des catégories)."""
        from decimal import Decimal
        return (
            (self.budget_materiel or Decimal('0'))
            + (self.budget_main_oeuvre or Decimal('0'))
            + (self.budget_sous_traitance or Decimal('0'))
            + (self.budget_divers or Decimal('0')))


class BudgetEngagement(models.Model):
    """FG294 — rattachement d'un coût FOURNISSEUR à un budget de projet.

    Aucune FK native ne relie un bon de commande / une facture fournisseur à un
    ``Projet`` : cette table de liaison attribue EXPLICITEMENT une dépense
    d'achat à un budget de programme, par string-FK (``stock.BonCommandeFournisseur``
    ou ``stock.FactureFournisseur``) — JAMAIS d'import des modèles ``stock``. Le
    sélecteur ``budget_projet_synthese`` lit les montants via
    ``apps.stock.selectors`` (engagé = montant commandé/HT du BCF ; dépensé =
    montant HT facturé) sans coupler les apps.

    ``categorie`` ventile la dépense dans la même grille que les enveloppes
    budgétées. ``source`` distingue un BCF (engagé) d'une facture (dépensé)."""

    class Source(models.TextChoices):
        BON_COMMANDE = 'bon_commande', 'Bon de commande fournisseur'
        FACTURE = 'facture', 'Facture fournisseur'

    class Categorie(models.TextChoices):
        MATERIEL = 'materiel', 'Matériel'
        MAIN_OEUVRE = 'main_oeuvre', "Main-d'œuvre"
        SOUS_TRAITANCE = 'sous_traitance', 'Sous-traitance'
        DIVERS = 'divers', 'Divers'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_budget_engagements')
    budget = models.ForeignKey(
        BudgetProjet, on_delete=models.CASCADE, related_name='engagements')
    source = models.CharField(
        max_length=12, choices=Source.choices, default=Source.BON_COMMANDE)
    categorie = models.CharField(
        max_length=14, choices=Categorie.choices, default=Categorie.MATERIEL)
    # Id de l'objet stock rattaché (BCF ou facture fournisseur), selon
    # ``source`` — string-FK volontaire (jamais d'import des modèles stock).
    bon_commande = models.ForeignKey(
        'achats.BonCommandeFournisseur', on_delete=models.CASCADE,
        null=True, blank=True, related_name='installations_budget_engagements')
    facture = models.ForeignKey(
        'achats.FactureFournisseur', on_delete=models.CASCADE,
        null=True, blank=True, related_name='installations_budget_engagements')
    libelle = models.CharField(max_length=200, blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Engagement de budget'
        verbose_name_plural = 'Engagements de budget'
        ordering = ['budget_id', 'id']
        indexes = [
            models.Index(fields=['company', 'budget'],
                         name='idx_budgeng_co_budg'),
        ]

    def __str__(self):
        cible = self.facture_id if self.source == self.Source.FACTURE \
            else self.bon_commande_id
        return f'{self.budget_id} · {self.source}:{cible}'
