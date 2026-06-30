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
import datetime

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
    # FLOTTE20 — puissance fiscale (chevaux fiscaux, CV) inscrite sur la carte
    # grise. Sert de clé, avec l'``energie``, au calcul de la vignette / TSAV
    # (taxe spéciale annuelle sur les véhicules) via le barème éditable
    # ``BaremeVignette``. null = puissance inconnue → la TSAV n'est pas calculée.
    puissance_fiscale = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Puissance fiscale (CV)',
        help_text='Chevaux fiscaux (carte grise). Sert au calcul de la TSAV.')
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


# ── FLOTTE11 — Check-list état des lieux départ / retour (photos) ────────────

class EtatDesLieux(models.Model):
    """Check-list d'état des lieux d'un véhicule au départ ou au retour.

    Constate l'état d'un ``Vehicule`` à un moment clé (départ d'une mission /
    retour), avec relevé du kilométrage, du niveau de carburant, l'état général,
    une check-list de points contrôlés (JSON, ex.
    ``[{"point": "Pneus", "ok": true}]``) et une liste de **photos** stockées
    par clé d'objet (clés MinIO — jamais le binaire en base). Optionnellement
    rattachable à une ``ReservationVehicule``.

    Multi-tenant : ``company`` est posée côté serveur, jamais lue du corps de
    requête.
    """

    class Moment(models.TextChoices):
        DEPART = 'depart', 'Départ'
        RETOUR = 'retour', 'Retour'

    class Etat(models.TextChoices):
        BON = 'bon', 'Bon'
        MOYEN = 'moyen', 'Moyen'
        MAUVAIS = 'mauvais', 'Mauvais'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='etats_des_lieux_flotte',
        verbose_name='Société',
    )
    vehicule = models.ForeignKey(
        'Vehicule',
        on_delete=models.CASCADE,
        related_name='etats_des_lieux_flotte',
        verbose_name='Véhicule',
    )
    reservation = models.ForeignKey(
        'ReservationVehicule',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='etats_des_lieux_flotte',
        verbose_name='Réservation liée',
    )
    conducteur = models.ForeignKey(
        'Conducteur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='etats_des_lieux_flotte',
        verbose_name='Conducteur',
    )
    moment = models.CharField(
        max_length=10, choices=Moment.choices, default=Moment.DEPART,
        verbose_name='Moment')
    date_constat = models.DateTimeField(verbose_name='Date du constat')
    kilometrage = models.PositiveIntegerField(
        default=0, verbose_name='Kilométrage relevé')
    niveau_carburant = models.PositiveSmallIntegerField(
        default=0, verbose_name='Niveau de carburant (%)')
    etat_general = models.CharField(
        max_length=10, choices=Etat.choices, default=Etat.BON,
        verbose_name='État général')
    # Check-list de points contrôlés (additive, non figée) :
    # [{"point": "Pneus", "ok": true, "commentaire": "…"}, …].
    points = models.JSONField(
        default=list, blank=True, verbose_name='Points contrôlés')
    # Photos par clé d'objet (clés MinIO) — jamais le binaire en base.
    photos = models.JSONField(
        default=list, blank=True, verbose_name='Photos (clés)')
    commentaire = models.TextField(blank=True, verbose_name='Commentaire')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'État des lieux'
        verbose_name_plural = 'États des lieux'
        ordering = ['-date_constat']
        indexes = [
            models.Index(
                fields=['company', 'vehicule'],
                name='flotte_edl_co_veh_idx',
            ),
        ]

    def clean(self):
        if self.niveau_carburant is not None and \
                not (0 <= self.niveau_carburant <= 100):
            raise ValidationError(
                "Le niveau de carburant doit être compris entre 0 et 100 %.")

    @property
    def nb_photos(self):
        return len(self.photos or [])

    def __str__(self):
        return f'{self.vehicule} — {self.get_moment_display()} ' \
               f'({self.date_constat:%Y-%m-%d})'


# ── FLOTTE12 — Carnet de carburant (`PleinCarburant`) ────────────────────────

class PleinCarburant(models.Model):
    """Un plein de carburant (ou charge électrique) au carnet d'un véhicule.

    Enregistre une prise de carburant : kilométrage au compteur, quantité
    (litres ou kWh), prix total, plein complet ou non, station. La cohérence du
    kilométrage (relevé strictement croissant par véhicule) est vérifiée côté
    serveur (sérialiseur) — la détection fine d'anomalie/fraude relève de
    FLOTTE14 ; ici on pose le carnet et le coût unitaire calculé.

    Multi-tenant : ``company`` est posée côté serveur, jamais lue du corps de
    requête.
    """

    class Unite(models.TextChoices):
        LITRE = 'litre', 'Litre'
        KWH = 'kwh', 'kWh'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='pleins_carburant_flotte',
        verbose_name='Société',
    )
    vehicule = models.ForeignKey(
        'Vehicule',
        on_delete=models.CASCADE,
        related_name='pleins_carburant_flotte',
        verbose_name='Véhicule',
    )
    conducteur = models.ForeignKey(
        'Conducteur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pleins_carburant_flotte',
        verbose_name='Conducteur',
    )
    date_plein = models.DateField(verbose_name='Date du plein')
    kilometrage = models.PositiveIntegerField(
        verbose_name='Kilométrage au compteur')
    quantite = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Quantité')
    unite = models.CharField(
        max_length=10, choices=Unite.choices, default=Unite.LITRE,
        verbose_name='Unité')
    prix_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Prix total (MAD)')
    plein_complet = models.BooleanField(
        default=True, verbose_name='Plein complet')
    station = models.CharField(
        max_length=120, blank=True, verbose_name='Station')
    notes = models.TextField(blank=True, verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Plein de carburant'
        verbose_name_plural = 'Pleins de carburant'
        ordering = ['-date_plein', '-kilometrage']
        indexes = [
            models.Index(
                fields=['company', 'vehicule'],
                name='flotte_plein_co_veh_idx',
            ),
        ]

    def clean(self):
        if self.quantite is not None and self.quantite < 0:
            raise ValidationError(
                "La quantité ne peut pas être négative.")
        if self.prix_total is not None and self.prix_total < 0:
            raise ValidationError(
                "Le prix total ne peut pas être négatif.")

    @property
    def prix_unitaire(self):
        """Prix par litre / kWh (MAD), ou ``None`` si quantité nulle."""
        if not self.quantite:
            return None
        return round(float(self.prix_total) / float(self.quantite), 3)

    def __str__(self):
        return f'{self.vehicule} — {self.date_plein} ' \
               f'({self.quantite} {self.get_unite_display()})'


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


# ── FLOTTE14 — Cartes carburant ───────────────────────────────────────────────

class CarteCarburant(models.Model):
    """Carte carburant rattachée à la société (et, en option, à un véhicule /
    conducteur précis).

    Une carte porte un ``numero`` (identifiant du fournisseur), un ``plafond``
    facultatif (montant maximum d'un plein avant alerte « dépassement de
    plafond »), et un drapeau ``actif``. Le rattachement à un ``vehicule`` ou un
    ``conducteur`` est facultatif : une carte « parc » non rattachée reste
    valide.

    La détection d'anomalie/fraude au carnet de carburant (kilométrage
    incohérent, consommation aberrante, dépassement de plafond) est un calcul
    LECTURE SEULE exposé via ``selectors.anomalies_pleins`` — elle ne stocke
    rien sur la carte.

    Multi-tenant : ``company`` est posée côté serveur, jamais lue du corps de
    requête.
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='cartes_carburant_flotte',
        verbose_name='Société',
    )
    vehicule = models.ForeignKey(
        'Vehicule',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cartes_carburant_flotte',
        verbose_name='Véhicule attribué',
    )
    conducteur = models.ForeignKey(
        'Conducteur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cartes_carburant_flotte',
        verbose_name='Conducteur attribué',
    )
    numero = models.CharField(
        max_length=60, verbose_name='Numéro de carte')
    plafond = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Plafond par plein (MAD)',
        help_text='Montant maximum toléré sur un plein avant alerte ; '
                  'laisser vide pour aucun plafond.',
    )
    actif = models.BooleanField(default=True, verbose_name='Active')
    notes = models.TextField(blank=True, verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Carte carburant'
        verbose_name_plural = 'Cartes carburant'
        ordering = ['numero']
        indexes = [
            models.Index(
                fields=['company', 'actif'],
                name='flotte_carte_co_act_idx',
            ),
        ]

    def clean(self):
        if self.plafond is not None and self.plafond < 0:
            raise ValidationError(
                "Le plafond ne peut pas être négatif.")

    def __str__(self):
        return f'Carte {self.numero}'


# ── FLOTTE15 — Plans d'entretien préventif (km / date / heures) ────────────────

class PlanEntretien(models.Model):
    """Plan d'entretien préventif d'un actif du parc (FLOTTE15).

    Un plan déclenche un rappel d'entretien (vidange, révision, contrôle
    technique, graissage…) selon un OU plusieurs critères additifs :

    * ``intervalle_km``     — tous les N kilomètres (véhicules immatriculés) ;
    * ``intervalle_jours``  — tous les N jours (date calendaire) ;
    * ``intervalle_heures`` — toutes les N heures de compteur (engins roulants).

    Chaque critère est associé à une référence « dernier réalisé » (``dernier_km``,
    ``derniere_date``, ``dernier_heures``) à partir de laquelle l'échéance suivante
    est calculée : ``prochaine = dernier_réalisé + intervalle``. La comparaison à
    l'état COURANT de l'actif (kilométrage du véhicule, compteur d'heures de
    l'engin, date du jour) classe le plan en ``due`` (échéance dépassée) ou
    ``upcoming`` (à venir). Tout le calcul est LECTURE SEULE et vit dans
    ``selectors.plans_entretien_status`` — le modèle ne stocke aucun état dérivé.

    L'actif ciblé est référencé via ``ActifFlotte`` (FLOTTE5), qui pointe vers SOIT
    un ``Vehicule`` SOIT un ``EnginRoulant`` de la même société : un seul FK, des
    requêtes simples, et l'accès uniforme au kilométrage / compteur d'heures
    courant quel que soit le type d'actif.

    Multi-tenant : ``company`` est posée côté serveur, jamais lue du corps de
    requête. L'actif ciblé doit appartenir à la MÊME société (validé dans
    ``clean`` et au sérialiseur).
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='plans_entretien_flotte',
        verbose_name='Société',
    )
    actif_flotte = models.ForeignKey(
        'ActifFlotte',
        on_delete=models.CASCADE,
        related_name='plans_entretien_flotte',
        verbose_name="Actif (véhicule ou engin)",
    )
    # Code court du type d'entretien (vidange, révision, contrôle technique…).
    # CharField borné : la valeur DOIT tenir dans max_length (leçon FG136).
    type_entretien = models.CharField(
        max_length=60, verbose_name="Type d'entretien")

    # ── Critères de déclenchement (au moins un renseigné, validé dans clean) ──
    intervalle_km = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Intervalle (km)')
    intervalle_jours = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Intervalle (jours)')
    intervalle_heures = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Intervalle (heures)")

    # ── Références « dernier entretien réalisé » ──────────────────────────────
    dernier_km = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Dernier entretien (km)')
    derniere_date = models.DateField(
        null=True, blank=True, verbose_name='Dernier entretien (date)')
    dernier_heures = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Dernier entretien (heures)')

    # Seuil d'anticipation : un plan est « à venir » (upcoming) quand l'échéance
    # tombe dans cette marge (en % de l'intervalle restant) — purement indicatif,
    # le calcul concret vit dans le sélecteur.
    seuil_alerte_km = models.PositiveIntegerField(
        default=500, verbose_name="Marge d'alerte (km)")
    seuil_alerte_jours = models.PositiveIntegerField(
        default=14, verbose_name="Marge d'alerte (jours)")
    seuil_alerte_heures = models.PositiveIntegerField(
        default=25, verbose_name="Marge d'alerte (heures)")

    notes = models.TextField(blank=True, verbose_name='Notes')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Plan d'entretien préventif"
        verbose_name_plural = "Plans d'entretien préventif"
        ordering = ['type_entretien']
        indexes = [
            models.Index(
                fields=['company', 'actif'],
                name='flotte_plan_co_act_idx',
            ),
        ]

    def clean(self):
        """Au moins un intervalle renseigné ; l'actif appartient à la société."""
        if not any((self.intervalle_km, self.intervalle_jours,
                    self.intervalle_heures)):
            raise ValidationError(
                "Renseignez au moins un intervalle (km, jours ou heures).")
        if self.actif_flotte_id is not None \
                and self.actif_flotte.company_id != self.company_id:
            raise ValidationError(
                "L'actif ciblé n'appartient pas à la même société.")

    def __str__(self):
        return f'{self.type_entretien} — {self.actif_flotte}'


# ── FLOTTE16 — Échéances d'entretien dues (générées depuis les plans) ──────────

class EcheanceEntretien(models.Model):
    """Échéance d'entretien DUE matérialisée depuis un ``PlanEntretien`` (FLOTTE16).

    Alors que ``PlanEntretien`` (FLOTTE15) décrit la RÈGLE (vidange tous les
    10 000 km…) et que ``selectors.plans_entretien_status`` calcule en LECTURE
    SEULE l'état courant, FLOTTE16 GÉNÈRE l'enregistrement concret de l'échéance
    qui tombe : une ``EcheanceEntretien`` est un travail d'entretien à planifier,
    suivi de son ``statut`` (``a_faire`` → ``planifie`` → ``fait``) et tracé par
    sa date de génération.

    La génération (``services.generer_echeances_entretien``) est IDEMPOTENTE :
    pour un plan donné on ne crée pas une nouvelle échéance OUVERTE
    (``a_faire`` / ``planifie``) tant qu'une échéance ouverte existe déjà — le
    « cycle » courant reste matérialisé une seule fois. Cela évite de dupliquer
    une échéance à chaque passage du générateur.

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête) et toujours égale à celle du plan source.
    """

    class Statut(models.TextChoices):
        A_FAIRE = 'a_faire', 'À faire'
        PLANIFIE = 'planifie', 'Planifié'
        FAIT = 'fait', 'Fait'

    # Statuts qui « occupent » le cycle courant (bloquent une re-génération).
    STATUTS_OUVERTS = (Statut.A_FAIRE, Statut.PLANIFIE)

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='echeances_entretien_flotte',
        verbose_name='Société',
    )
    plan = models.ForeignKey(
        'PlanEntretien',
        on_delete=models.CASCADE,
        related_name='echeances_entretien_flotte',
        verbose_name="Plan d'entretien",
    )
    actif_flotte = models.ForeignKey(
        'ActifFlotte',
        on_delete=models.CASCADE,
        related_name='echeances_entretien_flotte',
        verbose_name="Actif (véhicule ou engin)",
    )
    # Copie figée du type d'entretien du plan au moment de la génération (un plan
    # peut être renommé / supprimé ensuite). CharField borné : la valeur tient
    # dans max_length (leçon FG136 — alignée sur PlanEntretien.type_entretien).
    type_entretien = models.CharField(
        max_length=60, verbose_name="Type d'entretien")

    # ── Cible de l'échéance (au moins une dimension renseignée) ───────────────
    due_le = models.DateField(
        null=True, blank=True, verbose_name="Échéance (date)")
    due_km = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Échéance (km)")
    due_heures = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Échéance (heures)")

    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.A_FAIRE,
        verbose_name='Statut')
    notes = models.TextField(blank=True, verbose_name='Notes')
    genere_le = models.DateTimeField(
        auto_now_add=True, verbose_name='Généré le')

    class Meta:
        verbose_name = "Échéance d'entretien"
        verbose_name_plural = "Échéances d'entretien"
        ordering = ['statut', 'due_le', 'due_km', 'due_heures', 'id']
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='flotte_ech_co_stat_idx',
            ),
            models.Index(
                fields=['plan', 'statut'],
                name='flotte_ech_plan_stat_idx',
            ),
        ]

    def __str__(self):
        return f'{self.type_entretien} — {self.actif_flotte} ' \
               f'[{self.get_statut_display()}]'


# ── FLOTTE17 — Garage / atelier de réparation ─────────────────────────────────

class Garage(models.Model):
    """Garage / atelier de réparation référencé par la société (FLOTTE17).

    Un ``Garage`` est un prestataire (atelier externe ou atelier interne) auprès
    duquel un ``OrdreReparation`` est ouvert. Modèle additif, multi-société :
    ``company`` est posée côté serveur, jamais lue du corps de requête.
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_garages',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=120, verbose_name='Nom du garage')
    adresse = models.CharField(
        max_length=255, blank=True, verbose_name='Adresse')
    telephone = models.CharField(
        max_length=30, blank=True, verbose_name='Téléphone')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Garage / atelier'
        verbose_name_plural = 'Garages / ateliers'
        ordering = ['nom']
        indexes = [
            models.Index(
                fields=['company', 'actif'],
                name='flotte_garage_co_act_idx',
            ),
        ]

    def __str__(self):
        return self.nom


# ── FLOTTE17 — Ordres de réparation (atelier/garage + coûts) ──────────────────

class OrdreReparation(models.Model):
    """Ordre de réparation d'un actif du parc auprès d'un garage (FLOTTE17).

    Un ``OrdreReparation`` (OR) trace une intervention curative sur un actif
    unifié (``ActifFlotte`` — véhicule OU engin) : le garage qui la réalise (FK
    nullable, un OR peut être ouvert sans garage encore choisi), une description,
    les dates d'ouverture / clôture, le statut (``ouvert`` → ``en_cours`` →
    ``cloture``) et les coûts. ``cout_total`` est CALCULÉ
    (``cout_main_oeuvre + cout_pieces``) et figé en base à chaque enregistrement
    afin de rester triable / filtrable côté DB.

    L'OR peut optionnellement référencer une ``EcheanceEntretien`` (FLOTTE16) :
    quand l'OR est clôturé, le service peut clôturer (``fait``) l'échéance liée.

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête). L'actif, le garage et l'échéance liés doivent appartenir à la MÊME
    société (validé dans ``clean`` et au sérialiseur).
    """

    class Statut(models.TextChoices):
        OUVERT = 'ouvert', 'Ouvert'
        EN_COURS = 'en_cours', 'En cours'
        CLOTURE = 'cloture', 'Clôturé'

    # Statuts considérés comme « terminés » (l'OR ne bloque plus l'actif).
    STATUTS_CLOS = (Statut.CLOTURE,)

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_ordres_reparation',
        verbose_name='Société',
    )
    actif_flotte = models.ForeignKey(
        'ActifFlotte',
        on_delete=models.CASCADE,
        related_name='flotte_ordres_reparation',
        verbose_name='Actif (véhicule ou engin)',
    )
    garage = models.ForeignKey(
        'Garage',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='flotte_ordres_reparation',
        verbose_name='Garage / atelier',
    )
    # Lien optionnel vers l'échéance d'entretien à l'origine de l'OR (FLOTTE16) :
    # la clôture de l'OR peut clôturer (``fait``) cette échéance.
    echeance = models.ForeignKey(
        'EcheanceEntretien',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='flotte_ordres_reparation',
        verbose_name="Échéance d'entretien liée",
    )
    description = models.TextField(
        blank=True, verbose_name='Description des travaux')
    date_ouverture = models.DateField(verbose_name="Date d'ouverture")
    date_cloture = models.DateField(
        null=True, blank=True, verbose_name='Date de clôture')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.OUVERT,
        verbose_name='Statut')
    cout_main_oeuvre = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name="Coût main d'œuvre (MAD)")
    cout_pieces = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Coût pièces (MAD)')
    # Coût total figé en base (main d'œuvre + pièces) — recalculé à chaque save
    # pour rester triable / filtrable côté DB sans annotation.
    cout_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Coût total (MAD)')
    notes = models.TextField(blank=True, verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Ordre de réparation'
        verbose_name_plural = 'Ordres de réparation'
        ordering = ['-date_ouverture', '-id']
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='flotte_or_co_stat_idx',
            ),
            models.Index(
                fields=['company', 'actif_flotte'],
                name='flotte_or_co_act_idx',
            ),
        ]

    def clean(self):
        """Valide l'appartenance société des FKs, la cohérence des dates et des
        coûts."""
        if self.actif_flotte_id is not None \
                and self.actif_flotte.company_id != self.company_id:
            raise ValidationError(
                "L'actif ciblé n'appartient pas à la même société.")
        if self.garage_id is not None \
                and self.garage.company_id != self.company_id:
            raise ValidationError(
                "Le garage n'appartient pas à la même société.")
        if self.echeance_id is not None \
                and self.echeance.company_id != self.company_id:
            raise ValidationError(
                "L'échéance d'entretien n'appartient pas à la même société.")
        if self.date_ouverture is not None and self.date_cloture is not None \
                and self.date_cloture < self.date_ouverture:
            raise ValidationError(
                "La date de clôture ne peut pas précéder l'ouverture.")
        if self.cout_main_oeuvre is not None and self.cout_main_oeuvre < 0:
            raise ValidationError(
                "Le coût de main d'œuvre ne peut pas être négatif.")
        if self.cout_pieces is not None and self.cout_pieces < 0:
            raise ValidationError(
                "Le coût des pièces ne peut pas être négatif.")

    def save(self, *args, **kwargs):
        # Coût total toujours dérivé des deux postes (jamais saisi à la main).
        self.cout_total = (self.cout_main_oeuvre or 0) + (self.cout_pieces or 0)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'OR #{self.pk} — {self.actif_flotte} ' \
               f'[{self.get_statut_display()}]'


# ── FLOTTE18 — Pneumatiques montés sur un véhicule (suivi d'usure) ────────────

class Pneumatique(models.Model):
    """Un pneumatique suivi à une position d'un véhicule du parc (FLOTTE18).

    Trace la vie d'un pneu monté à une ``position`` du véhicule (avant/arrière
    gauche/droite ou roue de secours) : marque, dimension, date et kilométrage
    de montage, et — une fois déposé — date de dépose. Le ``statut`` suit le
    cycle ``monte`` (en service) → ``depose`` (retiré, encore exploitable) →
    ``use`` (hors service). Le coût d'achat est conservé pour le suivi de
    dépense.

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête). Le véhicule lié doit appartenir à la MÊME société (validé dans
    ``clean`` et au sérialiseur).
    """

    class Position(models.TextChoices):
        AV_G = 'av_g', 'Avant gauche'
        AV_D = 'av_d', 'Avant droite'
        AR_G = 'ar_g', 'Arrière gauche'
        AR_D = 'ar_d', 'Arrière droite'
        SECOURS = 'secours', 'Roue de secours'

    class Statut(models.TextChoices):
        MONTE = 'monte', 'Monté'
        DEPOSE = 'depose', 'Déposé'
        USE = 'use', 'Usé'

    # Statuts considérés « en service » (le pneu occupe sa position).
    STATUTS_MONTES = (Statut.MONTE,)

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_pneumatiques',
        verbose_name='Société',
    )
    vehicule = models.ForeignKey(
        'Vehicule',
        on_delete=models.CASCADE,
        related_name='flotte_pneumatiques',
        verbose_name='Véhicule',
    )
    # Code court de position — CharField borné : la valeur tient dans
    # max_length (leçon FG136). 'secours' (7) est le plus long code.
    position = models.CharField(
        max_length=10, choices=Position.choices, default=Position.AV_G,
        verbose_name='Position')
    marque = models.CharField(max_length=80, blank=True, verbose_name='Marque')
    dimension = models.CharField(
        max_length=40, blank=True, verbose_name='Dimension',
        help_text='Ex. : 205/55 R16')
    date_montage = models.DateField(
        null=True, blank=True, verbose_name='Date de montage')
    km_montage = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Kilométrage au montage')
    date_depose = models.DateField(
        null=True, blank=True, verbose_name='Date de dépose')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.MONTE,
        verbose_name='Statut')
    cout = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name="Coût d'achat (MAD)")
    notes = models.TextField(blank=True, verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Pneumatique'
        verbose_name_plural = 'Pneumatiques'
        ordering = ['vehicule', 'position', '-date_montage', '-id']
        indexes = [
            models.Index(
                fields=['company', 'vehicule'],
                name='flotte_pneu_co_veh_idx',
            ),
            models.Index(
                fields=['company', 'statut'],
                name='flotte_pneu_co_stat_idx',
            ),
        ]

    def clean(self):
        """Valide l'appartenance société du véhicule, la cohérence des dates et
        le coût."""
        if self.vehicule_id is not None \
                and self.vehicule.company_id != self.company_id:
            raise ValidationError(
                "Le véhicule n'appartient pas à la même société.")
        if self.date_montage is not None and self.date_depose is not None \
                and self.date_depose < self.date_montage:
            raise ValidationError(
                "La date de dépose ne peut pas précéder le montage.")
        if self.cout is not None and self.cout < 0:
            raise ValidationError(
                "Le coût ne peut pas être négatif.")

    def __str__(self):
        return f'{self.get_position_display()} — {self.vehicule} ' \
               f'[{self.get_statut_display()}]'


# ── FLOTTE18 — Pièces détachées posées sur un véhicule du parc ────────────────

class PieceFlotte(models.Model):
    """Une pièce détachée posée sur un véhicule du parc (FLOTTE18).

    Trace une pièce (filtre, plaquette, batterie, courroie…) montée sur un
    ``Vehicule`` : désignation, référence fournisseur, quantité, coût unitaire et
    date de pose. La pièce peut optionnellement être rattachée à un
    ``OrdreReparation`` (FLOTTE17) qui en a déclenché la pose. Le coût total de
    la ligne est CALCULÉ (``quantite × cout_unitaire``) — propriété lecture
    seule, jamais une colonne saisie.

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête). Le véhicule et l'ordre de réparation liés doivent appartenir à la
    MÊME société (validé dans ``clean`` et au sérialiseur).
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_pieces',
        verbose_name='Société',
    )
    vehicule = models.ForeignKey(
        'Vehicule',
        on_delete=models.CASCADE,
        related_name='flotte_pieces',
        verbose_name='Véhicule',
    )
    # Lien optionnel vers l'OR (FLOTTE17) qui a déclenché la pose de la pièce.
    ordre_reparation = models.ForeignKey(
        'OrdreReparation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='flotte_pieces',
        verbose_name='Ordre de réparation lié',
    )
    designation = models.CharField(
        max_length=160, verbose_name='Désignation')
    reference = models.CharField(
        max_length=80, blank=True, verbose_name='Référence')
    quantite = models.PositiveIntegerField(
        default=1, verbose_name='Quantité')
    cout_unitaire = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Coût unitaire (MAD)')
    date_pose = models.DateField(
        null=True, blank=True, verbose_name='Date de pose')
    notes = models.TextField(blank=True, verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Pièce de flotte'
        verbose_name_plural = 'Pièces de flotte'
        ordering = ['vehicule', '-date_pose', '-id']
        indexes = [
            models.Index(
                fields=['company', 'vehicule'],
                name='flotte_piece_co_veh_idx',
            ),
        ]

    def clean(self):
        """Valide l'appartenance société du véhicule et de l'OR, et le coût."""
        if self.vehicule_id is not None \
                and self.vehicule.company_id != self.company_id:
            raise ValidationError(
                "Le véhicule n'appartient pas à la même société.")
        if self.ordre_reparation_id is not None \
                and self.ordre_reparation.company_id != self.company_id:
            raise ValidationError(
                "L'ordre de réparation n'appartient pas à la même société.")
        if self.cout_unitaire is not None and self.cout_unitaire < 0:
            raise ValidationError(
                "Le coût unitaire ne peut pas être négatif.")

    @property
    def cout_total(self):
        """Coût total de la ligne (quantité × coût unitaire), en ``float``."""
        return round(float(self.cout_unitaire or 0) * (self.quantite or 0), 2)

    def __str__(self):
        return f'{self.designation} ×{self.quantite} — {self.vehicule}'


# ── FLOTTE19 — Échéances réglementaires (visite technique, assurance…) ─────────

class EcheanceReglementaire(models.Model):
    """Échéance réglementaire / administrative DATÉE d'un actif de flotte (FLOTTE19).

    Modèle GÉNÉRIQUE des obligations légales et administratives d'un actif :
    visite technique, assurance, vignette / TSAV, carte grise, taxe à l'essieu,
    etc. Chaque enregistrement porte une ``date_echeance`` (la date limite de
    validité / renouvellement) et, optionnellement, la ``date_dernier_renouvellement``,
    l'``organisme`` émetteur, le ``cout`` et une marge d'alerte ``alerte_jours``.

    **Famille DISTINCTE de l'entretien** : ``EcheanceEntretien`` (FLOTTE16)
    matérialise les échéances de MAINTENANCE (vidange, courroie…) générées depuis
    un ``PlanEntretien``. ``EcheanceReglementaire`` couvre les obligations
    LÉGALES/ADMINISTRATIVES, indépendantes du kilométrage — les deux familles ne
    se confondent jamais.

    **Statut** : ``statut`` est STOCKÉ (``a_jour`` par défaut) et peut être posé à
    la main, mais ``statut_calcule(today)`` recalcule l'état réel vs une date
    (``expire`` si la date est passée, ``a_renouveler`` si elle tombe dans la
    fenêtre ``alerte_jours``, sinon ``a_jour``). Le sélecteur
    ``echeances_reglementaires_status`` s'appuie sur ce calcul (date injectable).

    **Multi-tenant** : ``company`` est posée côté serveur (jamais lue du corps de
    requête). L'actif lié (``actif_flotte``, qui pointe vers un ``Vehicule`` OU un
    ``EnginRoulant``) doit appartenir à la MÊME société (validé dans ``clean`` et
    au sérialiseur).
    """

    class TypeEcheance(models.TextChoices):
        VISITE_TECHNIQUE = 'visite_technique', 'Visite technique'
        ASSURANCE = 'assurance', 'Assurance'
        VIGNETTE = 'vignette', 'Vignette / TSAV'
        CARTE_GRISE = 'carte_grise', 'Carte grise'
        TAXE_ESSIEU = 'taxe_essieu', "Taxe à l'essieu"
        AUTRE = 'autre', 'Autre'

    class Statut(models.TextChoices):
        A_JOUR = 'a_jour', 'À jour'
        A_RENOUVELER = 'a_renouveler', 'À renouveler'
        EXPIRE = 'expire', 'Expiré'

    # Marge d'alerte par défaut (jours avant l'échéance → « à renouveler »).
    ALERTE_JOURS_DEFAUT = 30

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_echeances_reglementaires',
        verbose_name='Société',
    )
    actif_flotte = models.ForeignKey(
        'ActifFlotte',
        on_delete=models.CASCADE,
        related_name='flotte_echeances_reglementaires',
        verbose_name='Actif (véhicule ou engin)',
    )
    # Code court du type d'échéance — CharField borné : la valeur tient dans
    # max_length (leçon FG136). 'visite_technique' (16) est le plus long code.
    type_echeance = models.CharField(
        max_length=20, choices=TypeEcheance.choices,
        default=TypeEcheance.VISITE_TECHNIQUE, verbose_name="Type d'échéance")
    date_echeance = models.DateField(verbose_name="Date d'échéance")
    date_dernier_renouvellement = models.DateField(
        null=True, blank=True, verbose_name='Dernier renouvellement')
    organisme = models.CharField(
        max_length=120, blank=True, verbose_name='Organisme')
    cout = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Coût (MAD)')
    # Marge d'alerte (jours) : si l'échéance tombe dans cette fenêtre, l'actif
    # passe « à renouveler ». 'a_jour' (6) est le plus long code de statut.
    alerte_jours = models.PositiveIntegerField(
        default=ALERTE_JOURS_DEFAUT, verbose_name="Marge d'alerte (jours)")
    statut = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.A_JOUR,
        verbose_name='Statut')
    notes = models.TextField(blank=True, verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Échéance réglementaire'
        verbose_name_plural = 'Échéances réglementaires'
        ordering = ['date_echeance', 'id']
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='flotte_echreg_co_stat_idx',
            ),
            models.Index(
                fields=['company', 'actif_flotte'],
                name='flotte_echreg_co_actif_idx',
            ),
            models.Index(
                fields=['company', 'date_echeance'],
                name='flotte_echreg_co_date_idx',
            ),
        ]

    def clean(self):
        """Valide l'appartenance société de l'actif, la cohérence des dates et
        le coût."""
        if self.actif_flotte_id is not None \
                and self.actif_flotte.company_id != self.company_id:
            raise ValidationError(
                "L'actif n'appartient pas à la même société.")
        if self.date_echeance is not None \
                and self.date_dernier_renouvellement is not None \
                and self.date_echeance < self.date_dernier_renouvellement:
            raise ValidationError(
                "La date d'échéance ne peut pas précéder le dernier "
                "renouvellement.")
        if self.cout is not None and self.cout < 0:
            raise ValidationError(
                "Le coût ne peut pas être négatif.")

    def statut_calcule(self, today=None):
        """État RÉEL de l'échéance vs ``today`` (lecture seule, date injectable).

        Retourne ``'expire'`` si la date d'échéance est déjà passée,
        ``'a_renouveler'`` si elle tombe dans les ``alerte_jours`` prochains
        jours (inclusif), sinon ``'a_jour'``. ``today`` défaut = date du jour.
        """
        if today is None:
            today = datetime.date.today()
        if self.date_echeance is None:
            return self.Statut.A_JOUR
        if self.date_echeance < today:
            return self.Statut.EXPIRE
        marge = self.alerte_jours \
            if self.alerte_jours is not None else self.ALERTE_JOURS_DEFAUT
        horizon = today + datetime.timedelta(days=marge)
        if self.date_echeance <= horizon:
            return self.Statut.A_RENOUVELER
        return self.Statut.A_JOUR

    def __str__(self):
        return f'{self.get_type_echeance_display()} — {self.actif_flotte} ' \
               f'({self.date_echeance})'


# ── FLOTTE20 — Barème de la vignette / TSAV (CV × énergie, éditable) ────────────

class BaremeVignette(models.Model):
    """Barème ÉDITABLE de la vignette / TSAV (FLOTTE20).

    La vignette (Taxe Spéciale Annuelle sur les Véhicules, TSAV) est due chaque
    année et dépend de DEUX critères : l'``energie`` du véhicule (essence, diesel,
    électrique, hybride) et sa ``puissance_fiscale`` en chevaux fiscaux (CV). Ce
    modèle matérialise UNE ligne de barème : « pour cette énergie et cette
    tranche de CV [``cv_min`` .. ``cv_max``], le montant TSAV est ``montant`` ».

    **Référentiel par société, éditable** : chaque société porte SON propre
    barème (les montants officiels peuvent évoluer d'une loi de finances à
    l'autre). La clé stable est ``(company, energie, cv_min, cv_max, annee)`` —
    deux lignes ne peuvent pas définir la même tranche pour la même énergie et la
    même année. ``annee`` permet de garder l'historique des grilles ; ``actif``
    permet de désactiver une ligne sans la supprimer.

    **Calcul** : ``selectors.calcul_tsav(vehicule, annee=…)`` choisit la ligne
    ACTIVE dont ``energie`` correspond et dont la tranche
    ``cv_min ≤ puissance_fiscale ≤ cv_max`` contient la puissance du véhicule, et
    renvoie son ``montant``. L'électrique est typiquement EXONÉRÉ : il suffit de
    seeder une ligne ``electrique`` à ``montant = 0``.

    **Famille DISTINCTE de l'échéance** : ``EcheanceReglementaire`` (FLOTTE19)
    suit la DATE limite de la vignette ; ``BaremeVignette`` (FLOTTE20) calcule le
    MONTANT dû — les deux ne se confondent jamais.

    **Multi-tenant** : ``company`` est posée côté serveur (jamais lue du corps de
    requête).
    """

    class Energie(models.TextChoices):
        DIESEL = 'diesel', 'Diesel'
        ESSENCE = 'essence', 'Essence'
        ELECTRIQUE = 'electrique', 'Électrique'
        HYBRIDE = 'hybride', 'Hybride'

    # CV maximal « sans plafond » : une tranche supérieure ouverte (« ≥ 15 CV »)
    # se saisit avec un ``cv_max`` très grand (PositiveSmallIntegerField ≤ 32767).
    CV_MAX_OUVERT = 9999

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_baremes_vignette',
        verbose_name='Société',
    )
    # Code court de l'énergie — CharField borné : 'electrique' (10) est le plus
    # long code, tient dans max_length (leçon FG136).
    energie = models.CharField(
        max_length=20, choices=Energie.choices, default=Energie.ESSENCE,
        verbose_name='Énergie')
    cv_min = models.PositiveSmallIntegerField(
        default=0, verbose_name='CV min (inclus)')
    cv_max = models.PositiveSmallIntegerField(
        default=CV_MAX_OUVERT, verbose_name='CV max (inclus)')
    montant = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Montant TSAV (MAD)')
    annee = models.PositiveIntegerField(
        default=0,
        verbose_name='Année',
        help_text='Année du barème (0 = barème générique, toutes années).')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    notes = models.CharField(
        max_length=200, blank=True, verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Barème vignette / TSAV'
        verbose_name_plural = 'Barèmes vignette / TSAV'
        unique_together = [
            ('company', 'energie', 'cv_min', 'cv_max', 'annee')]
        ordering = ['annee', 'energie', 'cv_min']
        indexes = [
            models.Index(
                fields=['company', 'energie', 'annee'],
                name='flotte_barvig_co_en_an_idx',
            ),
            models.Index(
                fields=['company', 'actif'],
                name='flotte_barvig_co_act_idx',
            ),
        ]

    def clean(self):
        """Valide la cohérence de la tranche et la positivité du montant."""
        if self.cv_min is not None and self.cv_max is not None \
                and self.cv_min > self.cv_max:
            raise ValidationError(
                "Le CV min ne peut pas dépasser le CV max.")
        if self.montant is not None and self.montant < 0:
            raise ValidationError(
                "Le montant ne peut pas être négatif.")

    def couvre_cv(self, cv):
        """``True`` si ``cv`` tombe dans la tranche [cv_min .. cv_max] (inclus)."""
        if cv is None:
            return False
        return self.cv_min <= cv <= self.cv_max

    def __str__(self):
        return (f'TSAV {self.get_energie_display()} '
                f'{self.cv_min}-{self.cv_max} CV : {self.montant} MAD '
                f'({self.annee or "générique"})')


# ── FLOTTE21 — Police d'assurance auto (police/échéance/attestation/franchise) ─

class AssuranceVehicule(models.Model):
    """Police d'assurance d'un actif de flotte (FLOTTE21).

    Modèle DÉDIÉ au CONTRAT d'assurance auto : il porte les détails propres à
    la police que l'``EcheanceReglementaire`` GÉNÉRIQUE (FLOTTE19) ne capture
    pas — ``numero_police``, ``assureur``, période de couverture
    (``date_debut`` → ``date_echeance``), ``franchise`` (montant à charge de
    l'assuré en cas de sinistre) et l'``attestation`` (document scanné).

    **Complémentaire, jamais doublon de FLOTTE19** :
    ``EcheanceReglementaire`` (type ``assurance``) suit UNE date limite
    administrative de façon générique (visite technique, vignette, assurance…),
    sans numéro de police, assureur, franchise ni attestation. Ce modèle stocke
    le CONTRAT lui-même. Les deux familles ne se confondent jamais : l'échéance
    réglementaire reste le suivi calendaire transverse, l'assurance porte le
    détail du contrat.

    **Statut** : ``statut_calcule(today)`` recalcule l'état réel de la couverture
    vs une date (``expiree`` si ``date_echeance`` est passée, ``a_renouveler`` si
    elle tombe dans la fenêtre ``alerte_jours``, sinon ``valide``). La date est
    injectable (lecture seule, ne change rien en base).

    **Multi-tenant** : ``company`` est posée côté serveur (jamais lue du corps de
    requête). L'actif lié (``actif_flotte``, véhicule OU engin) doit appartenir à
    la MÊME société (validé dans ``clean`` et au sérialiseur).
    """

    class Statut(models.TextChoices):
        VALIDE = 'valide', 'Valide'
        A_RENOUVELER = 'a_renouveler', 'À renouveler'
        EXPIREE = 'expiree', 'Expirée'

    # Marge d'alerte par défaut (jours avant l'échéance → « à renouveler »).
    ALERTE_JOURS_DEFAUT = 30

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_assurances_vehicule',
        verbose_name='Société',
    )
    actif_flotte = models.ForeignKey(
        'ActifFlotte',
        on_delete=models.CASCADE,
        related_name='flotte_assurances_vehicule',
        verbose_name='Actif (véhicule ou engin)',
    )
    assureur = models.CharField(
        max_length=120, verbose_name='Assureur / Compagnie')
    numero_police = models.CharField(
        max_length=80, verbose_name='Numéro de police')
    date_debut = models.DateField(
        null=True, blank=True, verbose_name='Début de couverture')
    date_echeance = models.DateField(verbose_name="Date d'échéance")
    franchise = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Franchise (MAD)')
    # Attestation d'assurance scannée — stockée via le storage projet (même
    # convention que ``compta.NoteFrais.justificatif``).
    attestation = models.FileField(
        upload_to='flotte/assurances/attestations/%Y/%m/',
        blank=True, null=True, verbose_name="Attestation d'assurance")
    # Marge d'alerte (jours) : si l'échéance tombe dans cette fenêtre, la police
    # passe « à renouveler ». 'a_renouveler' (12) est le plus long code de statut.
    alerte_jours = models.PositiveIntegerField(
        default=ALERTE_JOURS_DEFAUT, verbose_name="Marge d'alerte (jours)")
    statut = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.VALIDE,
        verbose_name='Statut')
    notes = models.TextField(blank=True, verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Police d'assurance"
        verbose_name_plural = "Polices d'assurance"
        ordering = ['date_echeance', 'id']
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='flotte_assur_co_stat_idx',
            ),
            models.Index(
                fields=['company', 'actif_flotte'],
                name='flotte_assur_co_actif_idx',
            ),
            models.Index(
                fields=['company', 'date_echeance'],
                name='flotte_assur_co_date_idx',
            ),
        ]

    def clean(self):
        """Valide l'appartenance société de l'actif, la cohérence des dates et
        la franchise."""
        if self.actif_flotte_id is not None \
                and self.actif_flotte.company_id != self.company_id:
            raise ValidationError(
                "L'actif n'appartient pas à la même société.")
        if self.date_echeance is not None \
                and self.date_debut is not None \
                and self.date_echeance < self.date_debut:
            raise ValidationError(
                "La date d'échéance ne peut pas précéder le début de "
                "couverture.")
        if self.franchise is not None and self.franchise < 0:
            raise ValidationError(
                "La franchise ne peut pas être négative.")

    def statut_calcule(self, today=None):
        """État RÉEL de la couverture vs ``today`` (lecture seule, date injectable).

        Retourne ``'expiree'`` si la date d'échéance est déjà passée,
        ``'a_renouveler'`` si elle tombe dans les ``alerte_jours`` prochains
        jours (inclusif), sinon ``'valide'``. ``today`` défaut = date du jour.
        """
        if today is None:
            today = datetime.date.today()
        if self.date_echeance is None:
            return self.Statut.VALIDE
        if self.date_echeance < today:
            return self.Statut.EXPIREE
        marge = self.alerte_jours \
            if self.alerte_jours is not None else self.ALERTE_JOURS_DEFAUT
        horizon = today + datetime.timedelta(days=marge)
        if self.date_echeance <= horizon:
            return self.Statut.A_RENOUVELER
        return self.Statut.VALIDE

    def __str__(self):
        return (f'Assurance {self.assureur} n°{self.numero_police} — '
                f'{self.actif_flotte} ({self.date_echeance})')


# ── FLOTTE22 — Visite technique (validité paramétrable) ────────────────────────

class VisiteTechnique(models.Model):
    """Visite technique périodique d'un actif de flotte (FLOTTE22).

    Modèle DÉDIÉ au contrôle technique : il porte les détails propres au passage
    en centre que l'``EcheanceReglementaire`` GÉNÉRIQUE (FLOTTE19) ne capture
    pas — le ``centre`` de visite, la ``date_visite`` (date du passage), le
    ``resultat`` (favorable / défavorable / contre-visite), une période de
    validité PARAMÉTRABLE ``validite_mois`` (12 ou 24 mois selon le véhicule) et
    la ``date_prochaine`` calculée depuis ``date_visite`` + ``validite_mois``.

    **Complémentaire, jamais doublon de FLOTTE19** : ``EcheanceReglementaire``
    (type ``visite_technique``) ne suit qu'UNE date limite administrative de
    façon générique — sans centre, résultat ni validité paramétrable. Ce modèle
    stocke le PASSAGE lui-même et sa validité. Les deux familles ne se confondent
    jamais : l'échéance réglementaire reste le suivi calendaire transverse, la
    visite technique porte le détail du contrôle. (Même rapport que FLOTTE21
    ``AssuranceVehicule`` entretient avec FLOTTE19.)

    **Validité paramétrable** : ``date_prochaine`` est STOCKÉE ; si elle n'est
    pas fournie, ``clean`` la calcule depuis ``date_visite`` + ``validite_mois``.
    Le défaut de ``validite_mois`` est 12 mois (cas du contrôle annuel), mais il
    est éditable (24 mois pour un véhicule neuf, etc.).

    **Statut** : ``statut_calcule(today)`` recalcule l'état réel vs une date
    (``expiree`` si ``date_prochaine`` est passée, ``a_renouveler`` si elle tombe
    dans la fenêtre ``alerte_jours``, sinon ``valide``). La date est injectable
    (lecture seule, ne change rien en base).

    **Multi-tenant** : ``company`` est posée côté serveur (jamais lue du corps de
    requête). L'actif lié (``actif_flotte``, véhicule OU engin) doit appartenir à
    la MÊME société (validé dans ``clean`` et au sérialiseur).
    """

    class Resultat(models.TextChoices):
        FAVORABLE = 'favorable', 'Favorable'
        DEFAVORABLE = 'defavorable', 'Défavorable'
        CONTRE_VISITE = 'contre_visite', 'Contre-visite'

    class Statut(models.TextChoices):
        VALIDE = 'valide', 'Valide'
        A_RENOUVELER = 'a_renouveler', 'À renouveler'
        EXPIREE = 'expiree', 'Expirée'

    # Validité par défaut (mois) — contrôle technique annuel.
    VALIDITE_MOIS_DEFAUT = 12
    # Marge d'alerte par défaut (jours avant l'échéance → « à renouveler »).
    ALERTE_JOURS_DEFAUT = 30

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_visites_techniques',
        verbose_name='Société',
    )
    actif_flotte = models.ForeignKey(
        'ActifFlotte',
        on_delete=models.CASCADE,
        related_name='flotte_visites_techniques',
        verbose_name='Actif (véhicule ou engin)',
    )
    centre = models.CharField(
        max_length=120, verbose_name='Centre de visite')
    date_visite = models.DateField(verbose_name='Date de la visite')
    # Code court du résultat — CharField borné : 'contre_visite' (13) est le plus
    # long code (leçon FG136).
    resultat = models.CharField(
        max_length=16, choices=Resultat.choices, default=Resultat.FAVORABLE,
        verbose_name='Résultat')
    # Période de validité PARAMÉTRABLE (mois) — 12 (annuel) par défaut, éditable.
    validite_mois = models.PositiveIntegerField(
        default=VALIDITE_MOIS_DEFAUT, verbose_name='Validité (mois)')
    # Prochaine visite due — calculée depuis date_visite + validite_mois si non
    # fournie (voir ``clean``).
    date_prochaine = models.DateField(
        null=True, blank=True, verbose_name='Prochaine visite')
    cout = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Coût (MAD)')
    # Marge d'alerte (jours) : si la prochaine visite tombe dans cette fenêtre,
    # la visite passe « à renouveler ».
    alerte_jours = models.PositiveIntegerField(
        default=ALERTE_JOURS_DEFAUT, verbose_name="Marge d'alerte (jours)")
    statut = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.VALIDE,
        verbose_name='Statut')
    notes = models.TextField(blank=True, verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Visite technique'
        verbose_name_plural = 'Visites techniques'
        ordering = ['date_prochaine', 'id']
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='flotte_vistec_co_stat_idx',
            ),
            models.Index(
                fields=['company', 'actif_flotte'],
                name='flotte_vistec_co_actif_idx',
            ),
            models.Index(
                fields=['company', 'date_prochaine'],
                name='flotte_vistec_co_proch_idx',
            ),
        ]

    @staticmethod
    def calculer_date_prochaine(date_visite, validite_mois):
        """Calcule la prochaine visite = ``date_visite`` + ``validite_mois`` mois.

        Gère proprement le débordement de fin de mois (ex. 31 janv. + 1 mois →
        28/29 févr.) sans dépendance externe. Retourne ``None`` si les entrées
        sont incomplètes.
        """
        if date_visite is None or not validite_mois:
            return None
        total = date_visite.month - 1 + int(validite_mois)
        year = date_visite.year + total // 12
        month = total % 12 + 1
        # Dernier jour du mois cible (jour 0 du mois suivant).
        if month == 12:
            last_day = 31
        else:
            last_day = (datetime.date(year, month + 1, 1)
                        - datetime.timedelta(days=1)).day
        day = min(date_visite.day, last_day)
        return datetime.date(year, month, day)

    def clean(self):
        """Valide l'appartenance société de l'actif, le coût, et calcule la
        prochaine visite si elle n'est pas fournie."""
        if self.actif_flotte_id is not None \
                and self.actif_flotte.company_id != self.company_id:
            raise ValidationError(
                "L'actif n'appartient pas à la même société.")
        if self.cout is not None and self.cout < 0:
            raise ValidationError(
                "Le coût ne peut pas être négatif.")
        if self.date_prochaine is None:
            self.date_prochaine = self.calculer_date_prochaine(
                self.date_visite, self.validite_mois)
        if self.date_visite is not None and self.date_prochaine is not None \
                and self.date_prochaine < self.date_visite:
            raise ValidationError(
                "La prochaine visite ne peut pas précéder la visite.")

    def save(self, *args, **kwargs):
        # ``date_prochaine`` est calculée à l'enregistrement : le ``save()`` de
        # DRF n'appelle pas ``clean()``, donc on garantit ici le calcul de la
        # prochaine visite (validité paramétrable) sur tous les chemins de
        # création/mise à jour, pas seulement les ModelForm/full_clean.
        if self.date_prochaine is None and self.date_visite is not None \
                and self.validite_mois:
            self.date_prochaine = self.calculer_date_prochaine(
                self.date_visite, self.validite_mois)
        super().save(*args, **kwargs)

    def statut_calcule(self, today=None):
        """État RÉEL de la visite vs ``today`` (lecture seule, date injectable).

        Retourne ``'expiree'`` si la prochaine visite est déjà passée,
        ``'a_renouveler'`` si elle tombe dans les ``alerte_jours`` prochains
        jours (inclusif), sinon ``'valide'``. ``today`` défaut = date du jour.
        """
        if today is None:
            today = datetime.date.today()
        echeance = self.date_prochaine
        if echeance is None:
            echeance = self.calculer_date_prochaine(
                self.date_visite, self.validite_mois)
        if echeance is None:
            return self.Statut.VALIDE
        if echeance < today:
            return self.Statut.EXPIREE
        marge = self.alerte_jours \
            if self.alerte_jours is not None else self.ALERTE_JOURS_DEFAUT
        horizon = today + datetime.timedelta(days=marge)
        if echeance <= horizon:
            return self.Statut.A_RENOUVELER
        return self.Statut.VALIDE

    def __str__(self):
        return (f'Visite technique {self.actif_flotte} — '
                f'{self.date_visite} ({self.get_resultat_display()})')


# ── FLOTTE23 — Carte grise & autorisation de circulation ───────────────────────

class CarteGriseVehicule(models.Model):
    """Carte grise et autorisation de circulation d'un actif de flotte (FLOTTE23).

    Modèle DÉDIÉ aux DOCUMENTS d'immatriculation de l'actif : il porte le numéro
    de carte grise, la date d'immatriculation et la date de mise en circulation,
    plus, le cas échéant, une autorisation de circulation (numéro + date de
    validité). Les deux documents scannés (carte grise, autorisation) sont
    stockés directement sur ce modèle via des ``FileField`` flotte — la note du
    plan mentionne la GED, mais on reste 100 % flotte (aucun couplage à
    ``apps.ged``) pour rester autonome.

    **Complémentaire, jamais doublon de FLOTTE19/21/22** : ce modèle stocke les
    PIÈCES d'immatriculation elles-mêmes (carte grise + autorisation), distinctes
    de la police d'assurance (FLOTTE21), de la visite technique (FLOTTE22) et de
    l'échéance réglementaire générique (FLOTTE19).

    **Statut** : ``statut_calcule(today)`` recalcule l'état RÉEL de
    l'autorisation de circulation vs une date — ``expiree`` si
    ``autorisation_date_validite`` est passée, ``a_renouveler`` si elle tombe
    dans la fenêtre ``alerte_jours``, sinon ``valide``. Quand aucune date de
    validité n'est fournie (autorisation facultative), l'état reste ``valide``.
    La date est injectable (lecture seule, ne change rien en base).

    **Multi-tenant** : ``company`` est posée côté serveur (jamais lue du corps de
    requête). L'actif lié (``actif_flotte``, véhicule OU engin) doit appartenir à
    la MÊME société (validé dans ``clean`` et au sérialiseur).
    """

    class Statut(models.TextChoices):
        VALIDE = 'valide', 'Valide'
        A_RENOUVELER = 'a_renouveler', 'À renouveler'
        EXPIREE = 'expiree', 'Expirée'

    # Marge d'alerte par défaut (jours avant l'échéance → « à renouveler »).
    ALERTE_JOURS_DEFAUT = 30

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_cartes_grises',
        verbose_name='Société',
    )
    actif_flotte = models.ForeignKey(
        'ActifFlotte',
        on_delete=models.CASCADE,
        related_name='flotte_cartes_grises',
        verbose_name='Actif (véhicule ou engin)',
    )
    numero_carte_grise = models.CharField(
        max_length=80, verbose_name='Numéro de carte grise')
    date_immatriculation = models.DateField(
        null=True, blank=True, verbose_name="Date d'immatriculation")
    date_mise_circulation = models.DateField(
        null=True, blank=True, verbose_name='Date de mise en circulation')
    autorisation_circulation_numero = models.CharField(
        max_length=80, blank=True,
        verbose_name="Numéro d'autorisation de circulation")
    autorisation_date_validite = models.DateField(
        null=True, blank=True,
        verbose_name="Validité de l'autorisation de circulation")
    # Documents scannés — stockés via le storage projet (même convention que
    # ``AssuranceVehicule.attestation``).
    carte_grise_fichier = models.FileField(
        upload_to='flotte/cartes_grises/%Y/%m/',
        blank=True, null=True, verbose_name='Carte grise (scan)')
    autorisation_fichier = models.FileField(
        upload_to='flotte/autorisations_circulation/%Y/%m/',
        blank=True, null=True,
        verbose_name="Autorisation de circulation (scan)")
    # Marge d'alerte (jours) : si la validité de l'autorisation tombe dans cette
    # fenêtre, le document passe « à renouveler ». 'a_renouveler' (12) est le
    # plus long code de statut.
    alerte_jours = models.PositiveIntegerField(
        default=ALERTE_JOURS_DEFAUT, verbose_name="Marge d'alerte (jours)")
    statut = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.VALIDE,
        verbose_name='Statut')
    notes = models.TextField(blank=True, verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Carte grise / autorisation de circulation'
        verbose_name_plural = 'Cartes grises / autorisations de circulation'
        ordering = ['actif_flotte', 'id']
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='flotte_cg_co_stat_idx',
            ),
            models.Index(
                fields=['company', 'actif_flotte'],
                name='flotte_cg_co_actif_idx',
            ),
            models.Index(
                fields=['company', 'autorisation_date_validite'],
                name='flotte_cg_co_autval_idx',
            ),
        ]

    def clean(self):
        """Valide l'appartenance société de l'actif."""
        if self.actif_flotte_id is not None \
                and self.actif_flotte.company_id != self.company_id:
            raise ValidationError(
                "L'actif n'appartient pas à la même société.")

    def statut_calcule(self, today=None):
        """État RÉEL de l'autorisation de circulation vs ``today``.

        Lecture seule, date injectable. Retourne ``'expiree'`` si
        ``autorisation_date_validite`` est déjà passée, ``'a_renouveler'`` si
        elle tombe dans les ``alerte_jours`` prochains jours (inclusif), sinon
        ``'valide'``. Sans date de validité (autorisation facultative), reste
        ``'valide'``. ``today`` défaut = date du jour.
        """
        if today is None:
            today = datetime.date.today()
        if self.autorisation_date_validite is None:
            return self.Statut.VALIDE
        if self.autorisation_date_validite < today:
            return self.Statut.EXPIREE
        marge = self.alerte_jours \
            if self.alerte_jours is not None else self.ALERTE_JOURS_DEFAUT
        horizon = today + datetime.timedelta(days=marge)
        if self.autorisation_date_validite <= horizon:
            return self.Statut.A_RENOUVELER
        return self.Statut.VALIDE

    def __str__(self):
        return (f'Carte grise n°{self.numero_carte_grise} — '
                f'{self.actif_flotte}')
