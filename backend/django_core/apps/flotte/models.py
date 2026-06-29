"""Modèles du module Gestion de flotte (`apps.flotte`).

Squelette multi-société (FLOTTE1) enrichi des premiers actifs roulants :

* ``Vehicule`` (FLOTTE2) — véhicules immatriculés du parc (immatriculation,
  marque, modèle, énergie, kilométrage, valeur, statut).
* ``EnginRoulant`` (FLOTTE4) — engins non immatriculés suivis au compteur
  d'heures (nacelle, groupe électrogène, chariot…).
* ``ActifFlotte`` (FLOTTE5) — référence d'actif unifiée (véhicule OU engin)
  permettant à entretien, sinistre et document de se rattacher à l'un ou
  l'autre via un FK unique (deux FKs nullable, exactement un renseigné).
* ``Conducteur`` (FLOTTE7) — conducteur/chauffeur rattaché à un utilisateur
  ERP (``authentication.User``), avec informations de permis de conduire.

Tout est multi-société : chaque modèle porte un FK ``company`` posé côté serveur
(jamais lu du corps de requête). Module entièrement additif — aucun comportement
existant n'est modifié.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


# ── FLOTTE2 — Véhicules immatriculés ───────────────────────────────────────

class Vehicule(models.Model):
    """Un véhicule immatriculé du parc de la société."""

    class Energie(models.TextChoices):
        DIESEL = 'diesel', 'Diesel'
        ESSENCE = 'essence', 'Essence'
        ELECTRIQUE = 'electrique', 'Électrique'
        HYBRIDE = 'hybride', 'Hybride'

    class Statut(models.TextChoices):
        ACTIF = 'actif', 'Actif'
        MAINTENANCE = 'maintenance', 'En maintenance'
        REFORME = 'reforme', 'Réformé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='vehicules',
        verbose_name='Société',
    )
    immatriculation = models.CharField(
        max_length=30, verbose_name='Immatriculation')
    marque = models.CharField(max_length=80, blank=True, verbose_name='Marque')
    modele = models.CharField(max_length=80, blank=True, verbose_name='Modèle')
    energie = models.CharField(
        max_length=20, choices=Energie.choices, default=Energie.DIESEL,
        verbose_name='Énergie')
    kilometrage = models.PositiveIntegerField(
        default=0, verbose_name='Kilométrage')
    valeur = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Valeur (MAD)')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.ACTIF,
        verbose_name='Statut')
    # FLOTTE9 — catégorie de permis exigée pour conduire ce véhicule (B, C, CE,
    # D…). Vide = aucune exigence (le contrôle de catégorie à l'affectation est
    # alors neutralisé). Le contrôle « permis valide / catégorie » à
    # l'affectation s'appuie sur ce champ (voir `services.controle_permis`).
    categorie_permis_requise = models.CharField(
        max_length=30, blank=True,
        verbose_name='Catégorie de permis requise',
        help_text='Ex. : B, C, CE, D… Vide = aucune exigence de catégorie.',
    )
    # FLOTTE3 — référence VERS un emplacement de stock (`stock.EmplacementStock`)
    # par id NUMÉRIQUE, jamais un FK cross-app dur (modularité, voir CLAUDE.md).
    # null = véhicule non rattaché à un emplacement. La validation « même
    # société » se fait côté serveur via le sélecteur de `apps.stock`.
    emplacement_stock_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Emplacement de stock (id)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Véhicule'
        verbose_name_plural = 'Véhicules'
        unique_together = [('company', 'immatriculation')]
        ordering = ['immatriculation']

    def __str__(self):
        return f'{self.immatriculation} — {self.marque} {self.modele}'.strip()


# ── FLOTTE4 — Engins roulants suivis au compteur d'heures ──────────────────

class EnginRoulant(models.Model):
    """Un engin non immatriculé suivi au compteur d'heures.

    Distinct du ``Vehicule`` immatriculé : nacelles, groupes électrogènes et
    chariots se suivent au compteur d'heures (et non au kilométrage).
    """

    class Type(models.TextChoices):
        NACELLE = 'nacelle', 'Nacelle'
        GROUPE = 'groupe_electrogene', 'Groupe électrogène'
        CHARIOT = 'chariot', 'Chariot'

    class Statut(models.TextChoices):
        ACTIF = 'actif', 'Actif'
        MAINTENANCE = 'maintenance', 'En maintenance'
        REFORME = 'reforme', 'Réformé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='engins_roulants',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=120, verbose_name='Désignation')
    type_engin = models.CharField(
        max_length=30, choices=Type.choices, default=Type.NACELLE,
        verbose_name='Type d\'engin')
    marque = models.CharField(max_length=80, blank=True, verbose_name='Marque')
    modele = models.CharField(max_length=80, blank=True, verbose_name='Modèle')
    compteur_heures = models.DecimalField(
        max_digits=10, decimal_places=1, default=0,
        verbose_name='Compteur d\'heures')
    valeur = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Valeur (MAD)')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.ACTIF,
        verbose_name='Statut')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Engin roulant'
        verbose_name_plural = 'Engins roulants'
        ordering = ['nom']

    def __str__(self):
        return f'{self.nom} ({self.get_type_engin_display()})'


# ── FLOTTE6 — Référentiels (listes éditables par société) ──────────────────

class ReferentielFlotte(models.Model):
    """Entrée d'une liste de référence éditable du parc (lookup générique).

    Référentiel ADDITIF : il fournit des listes éditables par société (type de
    véhicule, type d'engin, énergie, catégorie de permis…) en PARALLÈLE des
    ``TextChoices`` figés portés par ``Vehicule``/``EnginRoulant`` — il ne les
    remplace ni ne les modifie. Chaque entrée est rattachée à une société (FK
    ``company`` posée côté serveur) et identifiée de façon stable par
    ``(company, domaine, code)``.
    """

    class Domaine(models.TextChoices):
        TYPE_VEHICULE = 'type_vehicule', 'Type de véhicule'
        TYPE_ENGIN = 'type_engin', "Type d'engin"
        ENERGIE = 'energie', 'Énergie'
        CATEGORIE_PERMIS = 'categorie_permis', 'Catégorie de permis'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='referentiels_flotte',
        verbose_name='Société',
    )
    domaine = models.CharField(
        max_length=30, choices=Domaine.choices, verbose_name='Domaine')
    code = models.CharField(max_length=40, verbose_name='Code')
    libelle = models.CharField(max_length=120, verbose_name='Libellé')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Référentiel de flotte'
        verbose_name_plural = 'Référentiels de flotte'
        unique_together = [('company', 'domaine', 'code')]
        ordering = ['domaine', 'ordre', 'libelle']

    def __str__(self):
        return f'{self.get_domaine_display()} — {self.libelle}'


# ── FLOTTE5 — Référence d'actif unifiée (Vehicule | EnginRoulant) ──────────

class ActifFlotte(models.Model):
    """Référence d'actif commune pour rattacher entretien/sinistre/document.

    Un ``ActifFlotte`` pointe vers SOIT un ``Vehicule`` SOIT un ``EnginRoulant``
    de la même société — jamais les deux, jamais aucun. La contrainte est
    vérifiée en Python (``clean``) et protégée en base par la règle métier.

    **Usage** : les futurs modèles ``Entretien``, ``Sinistre``, ``Document``
    portent un FK vers ``ActifFlotte`` plutôt que deux FKs nullable séparés —
    ce qui garde les requêtes simples (un seul JOIN) et permet de lister tous
    les événements d'un actif quel qu'en soit le type.

    **Multi-tenant** : ``company`` est posée côté serveur, jamais lue du corps
    de requête. Un ``ActifFlotte`` ne peut pointer que vers un actif de SA
    propre société (validé dans ``clean``).

    **Lecture seule** : ``type_actif`` et ``label`` sont des propriétés Python
    calculées — elles ne sont pas des colonnes DB.
    """

    TYPE_VEHICULE = 'vehicule'
    TYPE_ENGIN = 'engin'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='actifs_flotte',
        verbose_name='Société',
    )
    vehicule = models.OneToOneField(
        Vehicule,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='actif_flotte',
        verbose_name='Véhicule',
    )
    engin = models.OneToOneField(
        EnginRoulant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='actif_flotte',
        verbose_name='Engin roulant',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Référence d'actif"
        verbose_name_plural = "Références d'actif"
        ordering = ['date_creation']

    # ── contrainte : exactement un des deux FKs doit être renseigné ─────────

    def clean(self):
        """Valide qu'exactement un actif est renseigné et appartient à la même
        société."""
        has_vehicule = self.vehicule_id is not None
        has_engin = self.engin_id is not None

        if has_vehicule and has_engin:
            raise ValidationError(
                "Un actif ne peut pas pointer à la fois vers un véhicule "
                "et un engin roulant.")
        if not has_vehicule and not has_engin:
            raise ValidationError(
                "Un actif doit pointer vers un véhicule ou un engin roulant.")

        # Vérification de société : le FK doit appartenir à la même company.
        if has_vehicule and self.vehicule.company_id != self.company_id:
            raise ValidationError(
                "Le véhicule n'appartient pas à la même société.")
        if has_engin and self.engin.company_id != self.company_id:
            raise ValidationError(
                "L'engin roulant n'appartient pas à la même société.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    # ── propriétés calculées ─────────────────────────────────────────────────

    @property
    def type_actif(self):
        """'vehicule' | 'engin' selon la cible."""
        if self.vehicule_id is not None:
            return self.TYPE_VEHICULE
        return self.TYPE_ENGIN

    @property
    def label(self):
        """Désignation lisible de l'actif cible."""
        if self.vehicule_id is not None:
            return str(self.vehicule)
        if self.engin_id is not None:
            return str(self.engin)
        return ''

    def __str__(self):
        return f'ActifFlotte({self.type_actif}) — {self.label}'


# ── FLOTTE8 — Affectation conducteur ↔ véhicule (datée) ───────────────────────

class AffectationConducteur(models.Model):
    """Affectation datée d'un conducteur à un véhicule du parc.

    Relie un ``Conducteur`` à un ``Vehicule`` de la même société sur une
    période (``date_debut`` … ``date_fin`` nullable). Un seul enregistrement
    peut être marqué ``actif`` à la fois pour un véhicule donné — la règle
    métier est vérifiée au niveau sérialiseur lors de l'API (pas une contrainte
    DB car les périodes passées peuvent se superposer légitimement).

    Multi-tenant : ``company`` est posée côté serveur, jamais lue du corps de
    requête.
    """

    company = models.ForeignKey(
        "authentication.Company",
        on_delete=models.CASCADE,
        related_name="affectations_flotte",
        verbose_name="Société",
    )
    conducteur = models.ForeignKey(
        "Conducteur",
        on_delete=models.CASCADE,
        related_name="affectations_flotte",
        verbose_name="Conducteur",
    )
    vehicule = models.ForeignKey(
        "Vehicule",
        on_delete=models.CASCADE,
        related_name="affectations_flotte",
        verbose_name="Véhicule",
    )
    date_debut = models.DateField(verbose_name="Date de début")
    date_fin = models.DateField(null=True, blank=True, verbose_name="Date de fin")
    notes = models.TextField(blank=True, verbose_name="Notes")
    actif = models.BooleanField(default=True, verbose_name="Actif")
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name="Créé le")

    class Meta:
        verbose_name = "Affectation conducteur"
        verbose_name_plural = "Affectations conducteurs"
        ordering = ["-date_debut"]
        indexes = [
            models.Index(
                fields=["company", "vehicule"],
                name="flotte_aff_co_veh_idx",
            ),
            models.Index(
                fields=["company", "conducteur"],
                name="flotte_aff_co_cond_idx",
            ),
        ]

    def __str__(self):
        fin = self.date_fin.isoformat() if self.date_fin else "…"
        return f"{self.conducteur} → {self.vehicule} ({self.date_debut}/{fin})"


# ── FLOTTE10 — Réservation de véhicule + détection de conflit ────────────────

class ReservationVehicule(models.Model):
    """Réservation datée d'un véhicule du parc sur une plage horaire.

    Réserve un ``Vehicule`` de la même société entre ``debut`` et ``fin`` pour
    un usage donné (mission, déplacement chantier…). Le conducteur prévu est
    facultatif (``conducteur`` nullable). La **détection de conflit** garantit
    qu'aucune réservation active (statut ``demandee`` ou ``confirmee``) ne se
    chevauche pour le même véhicule : deux plages [a1,a2) et [b1,b2) se
    chevauchent si ``a1 < b2`` ET ``b1 < a2``. La règle est vérifiée côté
    serveur (service ``reservations_en_conflit`` + sérialiseur), pas par une
    contrainte DB — les réservations annulées peuvent légitimement se superposer
    à de nouvelles.

    Multi-tenant : ``company`` est posée côté serveur, jamais lue du corps de
    requête.
    """

    class Statut(models.TextChoices):
        DEMANDEE = 'demandee', 'Demandée'
        CONFIRMEE = 'confirmee', 'Confirmée'
        ANNULEE = 'annulee', 'Annulée'

    # Statuts qui « occupent » le véhicule (entrent dans la détection de conflit).
    STATUTS_ACTIFS = (Statut.DEMANDEE, Statut.CONFIRMEE)

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='reservations_flotte',
        verbose_name='Société',
    )
    vehicule = models.ForeignKey(
        'Vehicule',
        on_delete=models.CASCADE,
        related_name='reservations_flotte',
        verbose_name='Véhicule',
    )
    conducteur = models.ForeignKey(
        'Conducteur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reservations_flotte',
        verbose_name='Conducteur prévu',
    )
    debut = models.DateTimeField(verbose_name='Début')
    fin = models.DateTimeField(verbose_name='Fin')
    motif = models.CharField(
        max_length=200, blank=True, verbose_name='Motif')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.DEMANDEE,
        verbose_name='Statut')
    notes = models.TextField(blank=True, verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Réservation de véhicule'
        verbose_name_plural = 'Réservations de véhicule'
        ordering = ['-debut']
        indexes = [
            models.Index(
                fields=['company', 'vehicule'],
                name='flotte_resa_co_veh_idx',
            ),
        ]

    def clean(self):
        """Valide que ``fin > debut``."""
        if self.debut is not None and self.fin is not None \
                and self.fin <= self.debut:
            raise ValidationError(
                "La date de fin doit être postérieure à la date de début.")

    def __str__(self):
        return (
            f'{self.vehicule} — '
            f'{self.debut:%Y-%m-%d %H:%M} → {self.fin:%Y-%m-%d %H:%M}'
        )


# ── FLOTTE7 — Conducteurs / chauffeurs ────────────────────────────────────────

class Conducteur(models.Model):
    """Conducteur/chauffeur rattaché à un utilisateur ERP et à une société.

    Porte les informations de permis de conduire (numéro, catégorie, dates
    d'obtention et d'expiration). Le champ ``user`` relie le conducteur à un
    compte ``authentication.User`` existant de la même société — liaison
    facultative (null/blank) pour permettre l'enregistrement d'un chauffeur
    externe sans compte ERP. ``related_name='conducteurs_flotte'`` évite tout
    conflit avec d'autres apps qui pourraient définir un reverse accessor sur
    ``User``.

    Multi-tenant : ``company`` est posée côté serveur, jamais lue du corps de
    requête.
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='conducteurs_flotte',
        verbose_name='Société',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conducteurs_flotte',
        verbose_name='Utilisateur ERP',
    )
    nom = models.CharField(max_length=120, verbose_name='Nom complet')
    telephone = models.CharField(
        max_length=30, blank=True, verbose_name='Téléphone')
    numero_permis = models.CharField(
        max_length=50, blank=True, verbose_name='Numéro de permis')
    categorie_permis = models.CharField(
        max_length=30, blank=True,
        verbose_name='Catégorie de permis',
        help_text='Ex. : B, C, CE, D…',
    )
    date_obtention = models.DateField(
        null=True, blank=True, verbose_name="Date d'obtention du permis")
    date_expiration = models.DateField(
        null=True, blank=True, verbose_name="Date d'expiration du permis")
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Conducteur'
        verbose_name_plural = 'Conducteurs'
        ordering = ['nom']

    def __str__(self):
        return self.nom
