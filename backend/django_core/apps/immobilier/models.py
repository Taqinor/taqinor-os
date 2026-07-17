"""Modèles du module Immobilier (Groupe NTPRO).

Patrimoine hiérarchique (Site → Bâtiment → Niveau → Local), baux, révisions de
loyer, échéancier de loyers et relances impayés. Toute écriture/lecture vers un
autre domaine (``crm``/``ventes``/``installations``) passe exclusivement par
leurs ``selectors.py``/``services.py`` (jamais un import de leurs ``models``),
conformément à la frontière cross-app de CLAUDE.md. ``client_ventes_id`` est
une référence LÂCHE (id entier, pas de FK dure) vers ``crm.Client`` — même
convention que ``chantier_id``/``ged_document_id`` ailleurs dans le repo.
"""
from django.db import models

from core.models import TenantModel


class Site(TenantModel):
    """NTPRO1 — Racine du patrimoine (un ensemble immobilier / adresse)."""

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='immobilier_sites',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=255, verbose_name='Nom')
    adresse = models.TextField(blank=True, default='', verbose_name='Adresse')
    ville = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Ville')
    gps_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        verbose_name='Latitude GPS')
    gps_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        verbose_name='Longitude GPS')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Site'
        verbose_name_plural = 'Sites'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class Batiment(TenantModel):
    """NTPRO1 — Bâtiment d'un site."""

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='immobilier_batiments',
        verbose_name='Société',
    )
    site = models.ForeignKey(
        Site, on_delete=models.CASCADE,  # on_delete: cascade parent→enfant (composant du parent)
        related_name='batiments',
        verbose_name='Site')
    nom = models.CharField(max_length=255, verbose_name='Nom')
    nb_niveaux = models.PositiveIntegerField(
        default=1, verbose_name='Nombre de niveaux')
    annee_construction = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Année de construction')
    # NTPRO29 (hors périmètre de ce lot) posera le dossier GED du bâtiment ;
    # le champ existe déjà pour éviter une migration supplémentaire plus tard.
    plan_ged_document_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='ID document GED (plan)')

    class Meta:
        verbose_name = 'Bâtiment'
        verbose_name_plural = 'Bâtiments'
        ordering = ['site__nom', 'nom']

    def __str__(self):
        return f'{self.site.nom} / {self.nom}'


class Niveau(TenantModel):
    """NTPRO1 — Niveau (étage) d'un bâtiment."""

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='immobilier_niveaux',
        verbose_name='Société',
    )
    batiment = models.ForeignKey(
        Batiment, on_delete=models.CASCADE,  # on_delete: cascade parent→enfant (composant du parent)
        related_name='niveaux',
        verbose_name='Bâtiment')
    numero = models.CharField(
        max_length=50, verbose_name='Numéro / libellé')
    ordre = models.IntegerField(default=0, verbose_name='Ordre d\'affichage')

    class Meta:
        verbose_name = 'Niveau'
        verbose_name_plural = 'Niveaux'
        ordering = ['batiment_id', 'ordre', 'numero']

    def __str__(self):
        return f'{self.batiment.nom} / {self.numero}'


class Local(TenantModel):
    """NTPRO1 — Local (unité louable) d'un niveau."""

    class TypeLocal(models.TextChoices):
        HABITATION = 'habitation', 'Habitation'
        COMMERCE = 'commerce', 'Commerce'
        BUREAU = 'bureau', 'Bureau'
        PARKING = 'parking', 'Parking'
        ENTREPOT = 'entrepot', 'Entrepôt'

    class Statut(models.TextChoices):
        LIBRE = 'libre', 'Libre'
        LOUE = 'loue', 'Loué'
        EN_TRAVAUX = 'en_travaux', 'En travaux'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='immobilier_locaux',
        verbose_name='Société',
    )
    niveau = models.ForeignKey(
        Niveau, on_delete=models.CASCADE,  # on_delete: cascade parent→enfant (composant du parent)
        related_name='locaux',
        verbose_name='Niveau')
    reference = models.CharField(max_length=50, verbose_name='Référence')
    type_local = models.CharField(
        max_length=15, choices=TypeLocal.choices,
        default=TypeLocal.HABITATION, verbose_name='Type')
    surface_m2 = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Surface (m²)')
    tantiemes = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Tantièmes')
    statut = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.LIBRE,
        verbose_name='Statut')

    class Meta:
        verbose_name = 'Local'
        verbose_name_plural = 'Locaux'
        ordering = ['niveau_id', 'reference']

    def __str__(self):
        return f'{self.niveau} / {self.reference}'


class Locataire(TenantModel):
    """NTPRO2 — Locataire (personne ou société), distinct du CRM."""

    class TypeLocataire(models.TextChoices):
        PARTICULIER = 'particulier', 'Particulier'
        SOCIETE = 'societe', 'Société'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='immobilier_locataires',
        verbose_name='Société',
    )
    type_locataire = models.CharField(
        max_length=12, choices=TypeLocataire.choices,
        default=TypeLocataire.PARTICULIER, verbose_name='Type')
    nom = models.CharField(
        max_length=255, verbose_name='Nom / raison sociale')
    cin = models.CharField(
        max_length=30, blank=True, default='', verbose_name='CIN')
    ice = models.CharField(
        max_length=30, blank=True, default='', verbose_name='ICE')
    telephone = models.CharField(
        max_length=30, blank=True, default='', verbose_name='Téléphone')
    email = models.EmailField(blank=True, default='', verbose_name='Email')
    adresse = models.TextField(blank=True, default='', verbose_name='Adresse')
    # NTPRO2 — référence LÂCHE (jamais un import de crm.models) vers un
    # crm.Client existant, résolue via apps.crm.selectors.find_client_by_*.
    client_ventes_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID client ventes (crm.Client)')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Locataire'
        verbose_name_plural = 'Locataires'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class Bail(TenantModel):
    """NTPRO3 — Bail (habitation loi 67-12 ou commercial loi 49-16)."""

    class TypeBail(models.TextChoices):
        HABITATION = 'habitation', 'Habitation (loi 67-12)'
        COMMERCIAL = 'commercial', 'Commercial (loi 49-16)'

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        ACTIF = 'actif', 'Actif'
        PREAVIS = 'preavis', 'Préavis'
        RESILIE = 'resilie', 'Résilié'
        EXPIRE = 'expire', 'Expiré'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='immobilier_baux',
        verbose_name='Société',
    )
    local = models.ForeignKey(
        Local, on_delete=models.PROTECT, related_name='baux',
        verbose_name='Local')
    locataire = models.ForeignKey(
        Locataire, on_delete=models.PROTECT, related_name='baux',
        verbose_name='Locataire')
    type_bail = models.CharField(
        max_length=12, choices=TypeBail.choices,
        default=TypeBail.HABITATION, verbose_name='Type de bail')
    date_debut = models.DateField(verbose_name='Date de début')
    duree_mois = models.PositiveIntegerField(verbose_name='Durée (mois)')
    loyer_mensuel_ht = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='Loyer mensuel HT')
    charges_mensuelles_provisions = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Charges mensuelles (provisions)')
    depot_garantie = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Dépôt de garantie')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.BROUILLON,
        verbose_name='Statut')
    date_preavis = models.DateField(
        null=True, blank=True, verbose_name='Date de préavis')
    date_fin_effective = models.DateField(
        null=True, blank=True, verbose_name='Date de fin effective')
    # Immuabilité contractuelle : snapshot des noms au moment de la signature
    # (jamais recalculé si le Local/Locataire change ensuite).
    bailleur_nom_snapshot = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Bailleur (snapshot)')
    locataire_nom_snapshot = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Locataire (snapshot)')
    # NTPRO5 — cycle de vie du dépôt de garantie.
    depot_garantie_recu = models.BooleanField(
        default=False, verbose_name='Dépôt reçu')
    date_reception_depot = models.DateField(
        null=True, blank=True, verbose_name='Date de réception du dépôt')
    depot_garantie_restitue = models.BooleanField(
        default=False, verbose_name='Dépôt restitué')
    date_restitution = models.DateField(
        null=True, blank=True, verbose_name='Date de restitution')
    montant_retenu = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Montant retenu (retenues justifiées)')
    motif_retenue = models.TextField(
        blank=True, default='', verbose_name='Motif de la retenue')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Bail'
        verbose_name_plural = 'Baux'
        ordering = ['-date_debut', '-id']

    def __str__(self):
        return f'Bail {self.local} / {self.locataire}'


class RevisionLoyer(TenantModel):
    """NTPRO4 — Historique IMMUABLE des révisions de loyer d'un bail."""

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='immobilier_revisions_loyer',
        verbose_name='Société',
    )
    bail = models.ForeignKey(
        Bail, on_delete=models.CASCADE,  # on_delete: cascade parent→enfant (composant du parent)
        related_name='revisions',
        verbose_name='Bail')
    date_effet = models.DateField(verbose_name="Date d'effet")
    ancien_loyer = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='Ancien loyer')
    nouveau_loyer = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='Nouveau loyer')
    indice = models.CharField(
        max_length=120, blank=True, default='',
        verbose_name='Indice de référence')
    taux_variation = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name='Taux de variation (%)')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Révision de loyer'
        verbose_name_plural = 'Révisions de loyer'
        ordering = ['-date_effet', '-id']

    def __str__(self):
        return f'{self.bail} — révision {self.date_effet}'


class EcheanceLoyer(TenantModel):
    """NTPRO6 — Échéance mensuelle de loyer (générée pour un bail actif)."""

    class Statut(models.TextChoices):
        A_EMETTRE = 'a_emettre', 'À émettre'
        EMISE = 'emise', 'Émise'
        PAYEE = 'payee', 'Payée'
        IMPAYEE = 'impayee', 'Impayée'
        RELANCEE = 'relancee', 'Relancée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='immobilier_echeances_loyer',
        verbose_name='Société',
    )
    bail = models.ForeignKey(
        Bail, on_delete=models.CASCADE,  # on_delete: cascade parent→enfant (composant du parent)
        related_name='echeances',
        verbose_name='Bail')
    periode_debut = models.DateField(verbose_name='Début de période')
    periode_fin = models.DateField(verbose_name='Fin de période')
    montant_loyer_ht = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='Montant loyer HT')
    montant_charges = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Montant charges')
    montant_total = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='Montant total')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.A_EMETTRE,
        verbose_name='Statut')
    # NTPRO7 — référence LÂCHE vers apps.facturation.Facture (exposée via
    # apps.ventes.services/selectors), jamais un import de modèle Facture ici.
    facture_ventes_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID facture ventes')
    date_emission_quittance = models.DateTimeField(
        null=True, blank=True, verbose_name='Date d\'émission de la quittance')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Échéance de loyer'
        verbose_name_plural = 'Échéances de loyer'
        ordering = ['-periode_debut', '-id']
        unique_together = [('bail', 'periode_debut')]

    def __str__(self):
        return f'{self.bail} — {self.periode_debut}'


class RelanceLoyer(TenantModel):
    """NTPRO8 — Relance d'impayé sur une échéance de loyer (distincte des
    relances devis existantes)."""

    class Niveau(models.IntegerChoices):
        NIVEAU_1 = 1, 'Niveau 1'
        NIVEAU_2 = 2, 'Niveau 2'
        NIVEAU_3 = 3, 'Niveau 3'

    class Canal(models.TextChoices):
        WHATSAPP = 'whatsapp', 'WhatsApp'
        EMAIL = 'email', 'Email'
        COURRIER = 'courrier', 'Courrier'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='immobilier_relances_loyer',
        verbose_name='Société',
    )
    echeance_loyer = models.ForeignKey(
        EcheanceLoyer, on_delete=models.CASCADE,  # on_delete: cascade parent→enfant (composant du parent)
        related_name='relances',
        verbose_name='Échéance de loyer')
    niveau = models.PositiveSmallIntegerField(
        choices=Niveau.choices, default=Niveau.NIVEAU_1, verbose_name='Niveau')
    date_envoi = models.DateTimeField(
        auto_now_add=True, verbose_name="Date d'envoi")
    canal = models.CharField(
        max_length=10, choices=Canal.choices, default=Canal.WHATSAPP,
        verbose_name='Canal')
    template_utilise = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Template utilisé')

    class Meta:
        verbose_name = 'Relance loyer'
        verbose_name_plural = 'Relances loyer'
        ordering = ['-date_envoi', '-id']

    def __str__(self):
        return f'Relance N{self.niveau} — {self.echeance_loyer}'
