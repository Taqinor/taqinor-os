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
        # XFLT4 — cycle de vie complet : les 3 statuts historiques restent
        # intacts, ces 3 nouveaux couvrent l'acquisition → cession.
        COMMANDE = 'commande', 'Commandé'
        A_VENDRE = 'a_vendre', 'À vendre'
        VENDU = 'vendu', 'Vendu'

    class TypeFiscal(models.TextChoices):
        UTILITAIRE = 'utilitaire', 'Utilitaire'
        TOURISME = 'tourisme', 'Tourisme'

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
    # FLOTTE30 — lien VERS l'immobilisation comptable (`compta.Immobilisation`)
    # du véhicule, via un FK référencé par CHAÎNE (jamais un import croisé des
    # modèles compta). null = véhicule non rattaché au registre des
    # immobilisations. L'amortissement (VNC) du véhicule est LU au travers de
    # `selectors.amortissement_vehicule`, qui passe par les sélecteurs de
    # `apps.compta` — la flotte n'écrit jamais le module comptable.
    immobilisation = models.ForeignKey(
        'compta.Immobilisation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='vehicules_flotte',
        verbose_name='Immobilisation comptable',
    )
    # XFLT4 — Fiche véhicule enrichie + cycle de vie complet. La date de mise
    # en circulation existe DÉJÀ (``CarteGriseVehicule.date_mise_circulation``,
    # FLOTTE23) : elle n'est PAS dupliquée ici, on la lit via sélecteur.
    vin = models.CharField(
        max_length=30, blank=True, verbose_name='N° châssis (VIN)')
    annee = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Année')
    date_acquisition = models.DateField(
        null=True, blank=True, verbose_name="Date d'acquisition")
    # Clé pour XFLT8 (TVA carburant) / XFLT9 (plafond CGI amortissement).
    type_fiscal = models.CharField(
        max_length=15, choices=TypeFiscal.choices, blank=True,
        verbose_name='Type fiscal',
        help_text='Utilitaire ou tourisme — sert au calcul TVA et au '
        'plafond CGI amortissement.')
    tags = models.JSONField(default=list, blank=True, verbose_name='Tags')
    # XFLT4 — checklist de mise en service (immatriculation faite, plaques,
    # assurance active, carte grise reçue) : dict {item: bool}. Distincte des
    # ``tags`` (liste libre) — bloque le passage commande→actif tant qu'un
    # item n'est pas coché (voir ``checklist_mise_en_service_ok``).
    checklist_mise_en_service = models.JSONField(
        default=dict, blank=True,
        verbose_name='Checklist de mise en service')
    # XFLT12 — Catalogue de modèles véhicule : lien optionnel vers un
    # ``ModeleVehicule`` de référence. À la sélection, pré-remplissage des
    # specs (voir ``services.prefill_depuis_modele``) SANS écraser une saisie
    # déjà présente. null = véhicule créé sans modèle de référence (saisie
    # libre historique, aucune régression).
    modele_ref = models.ForeignKey(
        'ModeleVehicule',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='vehicules',
        verbose_name='Modèle de référence',
    )
    # ZCTR11 — n° de carte carburant/mobilité (texte libre, distincte de
    # ``CarteCarburant`` FLOTTE14 qui gère les cartes en tant qu'entités
    # propres) — simple champ d'identification affiché sur la fiche véhicule.
    carte_mobilite = models.CharField(
        max_length=60, blank=True, verbose_name='Carte mobilité')
    # ZCTR11 — Enrichissement fiscal : copie véhicule des champs catalogue
    # (``ModeleVehicule.valeur_residuelle``/``pct_charges_non_deductibles``),
    # pré-remplis à la sélection du modèle (``services.prefill_depuis_modele``)
    # SANS écraser une saisie existante — un véhicule peut aussi les porter en
    # saisie libre (sans modèle de référence). Lus par le TCO/amortissement
    # (FLOTTE30/31) et la synthèse fiscale (XFLT8/XFLT9) pour signaler la part
    # non déductible.
    valeur_residuelle = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Valeur résiduelle (MAD)')
    pct_charges_non_deductibles = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='% charges non déductibles',
        help_text='0-100 — plafond CGI tourisme. Vide = non renseigné.')
    # XFLT16 — Cession / sortie de parc. Renseignés par l'action ``ceder/`` ;
    # les véhicules vendus/réformés gardent TOUT leur historique mais sont
    # exclus des KPI actifs (FLOTTE35) et des alertes d'échéances.
    date_cession = models.DateField(
        null=True, blank=True, verbose_name='Date de cession')
    prix_cession = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Prix de cession (MAD)')
    acheteur = models.CharField(
        max_length=150, blank=True, verbose_name='Acheteur')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    # ARC14 — champs personnalisés (additif, jamais destructif). Les
    # définitions viennent de apps.customfields (module='vehicule', pilote
    # enregistré via customfields.registry par apps/flotte/apps.py.ready()).
    custom_data = models.JSONField(
        null=True, blank=True, verbose_name='Champs personnalisés')

    class Meta:
        verbose_name = 'Véhicule'
        verbose_name_plural = 'Véhicules'
        unique_together = [('company', 'immatriculation')]
        ordering = ['immatriculation']

    def __str__(self):
        return f'{self.immatriculation} — {self.marque} {self.modele}'.strip()

    # ── XFLT4 — Checklist de mise en service (commande → actif) ────────────

    CHECKLIST_MISE_EN_SERVICE = (
        'immatriculation_faite', 'plaques', 'assurance_active',
        'carte_grise_recue',
    )

    def clean(self):
        """ZCTR11 — ``pct_charges_non_deductibles`` doit rester dans [0, 100]
        quand renseigné (vide = non renseigné, aucune contrainte)."""
        if self.pct_charges_non_deductibles is not None and not (
                0 <= self.pct_charges_non_deductibles <= 100):
            raise ValidationError(
                "Le % de charges non déductibles doit être compris entre "
                "0 et 100.")

    def checklist_mise_en_service_ok(self):
        """XFLT4 — Vrai si tous les items de la checklist de mise en service
        sont cochés (``self.checklist_mise_en_service``, dict {item: bool}).

        Lecture seule, aucun effet de bord.
        """
        checklist = self.checklist_mise_en_service
        if not isinstance(checklist, dict):
            return False
        return all(checklist.get(item) for item in
                   self.CHECKLIST_MISE_EN_SERVICE)


# ── XFLT4 — Journal des changements de statut véhicule ─────────────────────────

class JournalStatutVehicule(models.Model):
    """Trace un changement de statut d'un ``Vehicule`` (XFLT4).

    Une entrée par transition (ancien statut → nouveau statut), posée
    SERVEUR-SIDE (utilisateur et horodatage jamais lus du corps de requête).
    Immuable : aucune modification/suppression via l'API (lecture + création
    interne uniquement — même patron que le futur ``ActiviteFlotte`` XFLT21).

    Multi-tenant : ``company`` est posée côté serveur. Le véhicule et
    l'utilisateur doivent appartenir à la MÊME société.
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_journal_statuts_vehicule',
        verbose_name='Société',
    )
    vehicule = models.ForeignKey(
        'Vehicule',
        on_delete=models.CASCADE,
        related_name='journal_statuts',
        verbose_name='Véhicule',
    )
    ancien_statut = models.CharField(
        max_length=20, blank=True, verbose_name='Ancien statut')
    nouveau_statut = models.CharField(
        max_length=20, verbose_name='Nouveau statut')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='flotte_journal_statuts_vehicule',
        verbose_name='Utilisateur',
    )
    horodatage = models.DateTimeField(
        auto_now_add=True, verbose_name='Horodatage')

    class Meta:
        verbose_name = 'Journal de statut véhicule'
        verbose_name_plural = 'Journal des statuts véhicule'
        ordering = ['-horodatage', '-id']
        indexes = [
            models.Index(
                fields=['company', 'vehicule'],
                name='flotte_jsv_co_veh_idx',
            ),
        ]

    def __str__(self):
        return (f'{self.vehicule} : {self.ancien_statut} → '
                f'{self.nouveau_statut} ({self.horodatage})')


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
        # XFLT25 — criticité des préfixes de code défaut moteur (DTC), éditable
        # par société (P0xxx moteur, etc.). ``code`` porte le préfixe (ex.
        # ``P0``) et ``libelle`` la criticité littérale
        # (``critique``/``moyenne``/``faible`` — voir
        # ``services.criticite_dtc``, qui lit ce référentiel).
        CODE_DTC = 'code_dtc', 'Criticité des codes défaut (DTC)'
        # ZCTR10 — types de service / entretien flotte, éditable par société
        # (vidange, freins, pneus, révision, carrosserie…). Référencé par
        # ``OrdreReparation.type_service`` — jamais un domaine hardcodé.
        TYPE_SERVICE = 'type_service', "Type de service / entretien"

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
    # XFLT29 — avantage en nature véhicule -> paie. Un véhicule affecté avec
    # USAGE PRIVÉ constitue un avantage en nature imposable (règles
    # marocaines d'évaluation à valider par le fondateur/comptable —
    # DECISION) : la VALORISATION reste saisie/éditable ici (jamais calculée
    # automatiquement tant que la règle n'est pas validée). La flotte EXPOSE
    # cette donnée en LECTURE via ``selectors.avantages_en_nature`` pour que
    # la paie (FG192) l'intègre à ses éléments variables — la flotte N'ÉCRIT
    # JAMAIS dans le module paie (cross-app, voir CLAUDE.md).
    usage_prive = models.BooleanField(
        default=False, verbose_name='Usage privé (avantage en nature)')
    valeur_avantage_mensuelle = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name="Valeur de l'avantage en nature (MAD/mois)")
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
    # XFLT17 — Signatures e-signature loi 53-05 (nom saisi + horodatage
    # serveur, comme le flux devis existant — pas de signature graphique) et
    # accessoires remis (gilet, triangle, cric, roue de secours…).
    signature_conducteur = models.CharField(
        max_length=150, blank=True,
        verbose_name='Signature conducteur (nom saisi)')
    signature_conducteur_horodatage = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Horodatage signature conducteur')
    signature_responsable = models.CharField(
        max_length=150, blank=True,
        verbose_name='Signature responsable (nom saisi)')
    signature_responsable_horodatage = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Horodatage signature responsable')
    accessoires = models.JSONField(
        default=list, blank=True, verbose_name='Accessoires',
        help_text='[{"nom": "Gilet", "present": true}, …]')
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
    # XFLT8 — TVA carburant : récupérable (gasoil sur utilitaire) vs non
    # déductible (carburant sur véhicule de tourisme, règles CGI TVA).
    # ``tva_recuperable`` est CALCULÉ par défaut à la création (voir
    # ``_classifier_tva_recuperable``) mais reste ÉDITABLE (override founder).
    tva_recuperable = models.BooleanField(
        default=True, verbose_name='TVA récupérable')
    montant_tva = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Montant TVA (MAD)')
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
        if self.montant_tva is not None and self.montant_tva < 0:
            raise ValidationError(
                "Le montant de TVA ne peut pas être négatif.")

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
    # YHIRE11 — lien optionnel vers le dossier employé RH (``rh.DossierEmploye``,
    # même société). STRING-FK (PositiveInteger), jamais un FK Django cross-app
    # dur (modularité, voir CLAUDE.md) — la flotte ne lit ``rh`` que par
    # ``rh.selectors`` (``peut_conduire``/``permis_expirant_bientot``). null =
    # conducteur externe sans dossier employé (comportement historique
    # inchangé, les champs de permis locaux restent la source de vérité).
    # Quand renseigné, la validité du permis RH PRIME sur les champs locaux
    # (conservés en repli) — voir ``services.controle_permis``.
    employe_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Employé RH (id)',
        help_text="Lien optionnel vers le dossier employé RH. Quand "
        "renseigné, le permis RH (rh.PermisConduire) prime sur les champs "
        "de permis locaux.")
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
    # XFLT27 — conformité transport lourd (> 3,5 t, DECISION fondateur) :
    # carte de conducteur professionnel (n° + expiration) et formation
    # continue NARSA (date + validité). Tous optionnels — un conducteur de
    # véhicule léger n'en a simplement pas besoin (aucune régression).
    carte_conducteur_pro_numero = models.CharField(
        max_length=50, blank=True,
        verbose_name='N° carte de conducteur professionnel')
    carte_conducteur_pro_expiration = models.DateField(
        null=True, blank=True,
        verbose_name='Expiration carte de conducteur professionnel')
    formation_continue_narsa_date = models.DateField(
        null=True, blank=True,
        verbose_name='Date de formation continue NARSA')
    formation_continue_narsa_validite = models.DateField(
        null=True, blank=True,
        verbose_name='Validité de la formation continue NARSA')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Conducteur'
        verbose_name_plural = 'Conducteurs'
        ordering = ['nom']
        indexes = [
            models.Index(
                fields=['company', 'employe_id'],
                name='flotte_cond_co_emp_idx'),
        ]

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
    # XFLT26 — préparation e-facturation DGI : identité légale du garage
    # (fournisseur ponctuel non référencé dans ``stock.Fournisseur``, qui
    # porte DÉJÀ ICE/IF/RC/RIB — DC15). Champs additifs, tous optionnels
    # (compat ascendante). L'ICE marocain est un identifiant à 15 chiffres.
    ice = models.CharField(
        max_length=15, blank=True, verbose_name='ICE',
        help_text="Identifiant Commun de l'Entreprise (15 chiffres).")
    identifiant_fiscal = models.CharField(
        max_length=20, blank=True, verbose_name='Identifiant fiscal (IF)')
    # WIR90 — lien OPTIONNEL vers un `stock.Fournisseur` référencé (qui porte
    # déjà ICE/IF/RC/RIB) : un garage n'est PLUS forcément un prestataire
    # ponctuel — s'il coïncide avec un fournisseur existant, on pointe vers
    # l'identité canonique par id NUMÉRIQUE (jamais un FK cross-app dur,
    # modularité CLAUDE.md). null = garage ponctuel (repli sur la saisie libre
    # nom/ICE/IF). Validation « même société » côté serveur via le sélecteur
    # `apps.stock` (voir CoutVehicule.fournisseur_id_ref, même pattern).
    fournisseur_id_ref = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Fournisseur (référentiel stock)')
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

    def clean(self):
        """XFLT26 — Valide le format de l'ICE (15 chiffres) s'il est
        renseigné. WIR90 — et l'appartenance société du fournisseur
        référencé (repli sur la saisie libre si non renseigné)."""
        if self.ice and (len(self.ice) != 15 or not self.ice.isdigit()):
            raise ValidationError(
                "L'ICE doit comporter exactement 15 chiffres.")
        if self.fournisseur_id_ref is not None and self.company_id is not None:
            from apps.stock.selectors import get_fournisseur_by_id
            if get_fournisseur_by_id(
                    self.company, self.fournisseur_id_ref) is None:
                raise ValidationError(
                    "Le fournisseur référencé n'appartient pas à la même "
                    "société.")

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
        # XFLT19 — Approbation des devis de réparation externe : chaîne
        # enrichie DEVIS_RECU → APPROUVE → EN_COURS, la chaîne existante
        # ouvert/en_cours/clôturé reste intacte (jamais de doublon).
        DEVIS_RECU = 'devis_recu', 'Devis reçu'
        APPROUVE = 'approuve', 'Approuvé'
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
    # ZCTR10 — type de service/entretien (vidange, freins, pneus, révision,
    # carrosserie…), tiré du référentiel ÉDITABLE par société
    # (``ReferentielFlotte.Domaine.TYPE_SERVICE``) — JAMAIS un domaine
    # hardcodé. Nullable : un OR sans type reste "non catégorisé" (aucune
    # régression sur les OR existants). Validé même-société dans ``clean``.
    type_service = models.ForeignKey(
        'ReferentielFlotte',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='flotte_ordres_reparation',
        verbose_name='Type de service',
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
    # XFLT14 — Flag posé automatiquement à la création si l'actif a une
    # garantie active couvrant la date (et le km courant si connu) : sert au
    # suivi de récupération du coût auprès du fournisseur (warning non
    # bloquant, jamais recalculé après coup).
    sous_garantie = models.BooleanField(
        default=False, verbose_name='Sous garantie (possiblement)')
    # XFLT19 — Approbation des devis de réparation externe : montant du
    # devis fournisseur + fichier scanné, contrôlés à l'entrée en
    # ``en_cours`` (seuil société, voir ``ParametreApprobationOR``) et
    # écart facture (``cout_total``) vs devis signalé à la clôture.
    montant_devis = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Montant du devis (MAD)')
    devis_fichier = models.FileField(
        upload_to='flotte/ordres_reparation/devis/%Y/%m/',
        blank=True, null=True, verbose_name='Devis (scan)')
    approuve_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='flotte_ordres_reparation_approuves',
        verbose_name='Approuvé par',
    )
    date_approbation = models.DateTimeField(
        null=True, blank=True, verbose_name="Date d'approbation")
    ecart_facture_devis_pct = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name='Écart facture / devis (%)')
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
        if self.type_service_id is not None:
            if self.type_service.company_id != self.company_id:
                raise ValidationError(
                    "Le type de service n'appartient pas à la même société.")
            if self.type_service.domaine != ReferentielFlotte.Domaine.TYPE_SERVICE:
                raise ValidationError(
                    "Le type de service doit provenir du référentiel "
                    "« Type de service / entretien ».")
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
        # XFLT27 — conformité transport lourd (> 3,5 t) : calibration du
        # chronotachygraphe, périodicité 2 ans (arrêté 2399-20). Code CORT
        # (17) tient dans max_length=20 (leçon FG136 — 'visite_technique',
        # 16, restait jusqu'ici le plus long).
        CHRONOTACHYGRAPHE = 'chronotachygraphe', \
            'Calibration chronotachygraphe'
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


# ── FLOTTE25 — Sinistres (accident / constat / assurance) ──────────────────────

class Sinistre(models.Model):
    """Sinistre d'un actif de flotte — accident, vol, bris de glace… (FLOTTE25).

    Enregistre un incident impliquant un véhicule ou un engin du parc : la date,
    le type (accident matériel/corporel, vol, bris de glace, catastrophe
    naturelle, incendie, autre), une description, le lieu, le constat amiable
    scanné (facultatif), la police d'assurance liée (``AssuranceVehicule``,
    FLOTTE21, même app — facultative), le numéro de déclaration, les montants
    (estimé, franchise à charge) et le statut du dossier
    (déclaré → en cours → clos / indemnisé).

    **Multi-tenant** : ``company`` est posée côté serveur (jamais lue du corps de
    requête). L'actif lié (``actif_flotte``, véhicule OU engin) ET la police
    d'assurance liée (si renseignée) doivent appartenir à la MÊME société (validé
    dans ``clean`` et au sérialiseur).
    """

    class TypeSinistre(models.TextChoices):
        ACCIDENT_MATERIEL = 'accident_materiel', 'Accident matériel'
        ACCIDENT_CORPOREL = 'accident_corporel', 'Accident corporel'
        VOL = 'vol', 'Vol'
        BRIS_DE_GLACE = 'bris_de_glace', 'Bris de glace'
        INCENDIE = 'incendie', 'Incendie'
        CATASTROPHE = 'catastrophe', 'Catastrophe naturelle'
        AUTRE = 'autre', 'Autre'

    class Statut(models.TextChoices):
        DECLARE = 'declare', 'Déclaré'
        EN_COURS = 'en_cours', 'En cours'
        CLOS = 'clos', 'Clos'
        INDEMNISE = 'indemnise', 'Indemnisé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_sinistres',
        verbose_name='Société',
    )
    actif_flotte = models.ForeignKey(
        'ActifFlotte',
        on_delete=models.CASCADE,
        related_name='flotte_sinistres',
        verbose_name='Actif (véhicule ou engin)',
    )
    assurance = models.ForeignKey(
        'AssuranceVehicule',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='flotte_sinistres',
        verbose_name="Police d'assurance liée",
    )
    date_sinistre = models.DateField(verbose_name='Date du sinistre')
    type_sinistre = models.CharField(
        max_length=20, choices=TypeSinistre.choices,
        default=TypeSinistre.ACCIDENT_MATERIEL,
        verbose_name='Type de sinistre')
    description = models.TextField(verbose_name='Description')
    lieu = models.CharField(
        max_length=255, blank=True, verbose_name='Lieu')
    # Constat amiable scanné — même convention de storage que les autres
    # documents flotte (cf. ``AssuranceVehicule.attestation``).
    constat_fichier = models.FileField(
        upload_to='flotte/sinistres/constats/%Y/%m/',
        blank=True, null=True, verbose_name='Constat amiable')
    numero_declaration = models.CharField(
        max_length=80, blank=True, verbose_name='Numéro de déclaration')
    montant_estime = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Montant estimé des dommages (MAD)')
    franchise = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Franchise à charge (MAD)')
    # 'indemnise' (9) est le plus long code de statut.
    statut = models.CharField(
        max_length=9, choices=Statut.choices, default=Statut.DECLARE,
        verbose_name='Statut')
    date_declaration = models.DateField(
        null=True, blank=True, verbose_name='Date de déclaration')
    notes = models.TextField(blank=True, verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Sinistre'
        verbose_name_plural = 'Sinistres'
        ordering = ['-date_sinistre', '-id']
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='flotte_sin_co_stat_idx',
            ),
            models.Index(
                fields=['company', 'actif_flotte'],
                name='flotte_sin_co_actif_idx',
            ),
            models.Index(
                fields=['company', 'type_sinistre'],
                name='flotte_sin_co_type_idx',
            ),
            models.Index(
                fields=['company', 'date_sinistre'],
                name='flotte_sin_co_date_idx',
            ),
        ]

    def clean(self):
        """Valide l'appartenance société de l'actif et de la police liée, ainsi
        que la cohérence des montants."""
        if self.actif_flotte_id is not None \
                and self.actif_flotte.company_id != self.company_id:
            raise ValidationError(
                "L'actif n'appartient pas à la même société.")
        if self.assurance_id is not None \
                and self.assurance.company_id != self.company_id:
            raise ValidationError(
                "La police d'assurance n'appartient pas à la même société.")
        if self.montant_estime is not None and self.montant_estime < 0:
            raise ValidationError(
                "Le montant estimé ne peut pas être négatif.")
        if self.franchise is not None and self.franchise < 0:
            raise ValidationError(
                "La franchise ne peut pas être négative.")

    def __str__(self):
        return (f'Sinistre {self.get_type_sinistre_display()} — '
                f'{self.actif_flotte} ({self.date_sinistre})')


# ── FLOTTE26 — Infractions / PV de circulation ────────────────────────────────

class Infraction(models.Model):
    """PV de circulation / infraction routière contre un actif de flotte (FLOTTE26).

    Enregistre un procès-verbal (PV) dressé contre un véhicule ou un engin du
    parc : la date, le type (excès de vitesse, stationnement, feu rouge,
    document, autre), le lieu, la référence du PV, le montant de l'amende, le PV
    scanné (facultatif) et le statut de traitement (à payer → payée / contestée
    / classée). Le conducteur tenu pour responsable au moment des faits est
    optionnellement rattaché (FK ``Conducteur``, FLOTTE7, même app — nullable :
    un PV peut être reçu sans conducteur identifié).

    **Multi-tenant** : ``company`` est posée côté serveur (jamais lue du corps de
    requête). L'actif lié (``actif_flotte``, véhicule OU engin) ET le conducteur
    lié (si renseigné) doivent appartenir à la MÊME société (validé dans
    ``clean`` et au sérialiseur).
    """

    class TypeInfraction(models.TextChoices):
        EXCES_VITESSE = 'exces_vitesse', 'Excès de vitesse'
        STATIONNEMENT = 'stationnement', 'Stationnement'
        FEU_ROUGE = 'feu_rouge', 'Feu rouge'
        DOCUMENT = 'document', 'Défaut de document'
        AUTRE = 'autre', 'Autre'

    class Statut(models.TextChoices):
        A_PAYER = 'a_payer', 'À payer'
        PAYEE = 'payee', 'Payée'
        CONTESTEE = 'contestee', 'Contestée'
        CLASSEE = 'classee', 'Classée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_infractions',
        verbose_name='Société',
    )
    actif_flotte = models.ForeignKey(
        'ActifFlotte',
        on_delete=models.CASCADE,
        related_name='flotte_infractions',
        verbose_name='Actif (véhicule ou engin)',
    )
    conducteur = models.ForeignKey(
        'Conducteur',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='flotte_infractions',
        verbose_name='Conducteur responsable',
    )
    date_infraction = models.DateField(verbose_name="Date de l'infraction")
    # 'exces_vitesse' (13) est le plus long code de type.
    type_infraction = models.CharField(
        max_length=13, choices=TypeInfraction.choices,
        default=TypeInfraction.EXCES_VITESSE,
        verbose_name="Type d'infraction")
    lieu = models.CharField(
        max_length=255, blank=True, verbose_name='Lieu')
    reference_pv = models.CharField(
        max_length=80, blank=True, verbose_name='Référence du PV')
    montant_amende = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name="Montant de l'amende (MAD)")
    # PV scanné — même convention de storage que les autres documents flotte
    # (cf. ``Sinistre.constat_fichier``).
    pv_fichier = models.FileField(
        upload_to='flotte/infractions/pv/%Y/%m/',
        blank=True, null=True, verbose_name='PV scanné')
    # 'contestee' (9) est le plus long code de statut.
    statut = models.CharField(
        max_length=9, choices=Statut.choices, default=Statut.A_PAYER,
        verbose_name='Statut')
    date_paiement = models.DateField(
        null=True, blank=True, verbose_name='Date de paiement')
    notes = models.TextField(blank=True, verbose_name='Notes')
    # XFLT11 — Imputation automatique du conducteur : trace si ``conducteur``
    # a été résolu automatiquement (via l'historique ``AffectationConducteur``
    # à la date de l'infraction) plutôt que saisi manuellement.
    imputation_auto = models.BooleanField(
        default=False, verbose_name='Conducteur imputé automatiquement')
    date_limite_contestation = models.DateField(
        null=True, blank=True, verbose_name='Date limite de contestation')
    # La retenue de paie éventuelle reste une écriture MANUELLE côté paie —
    # ces champs ne font qu'exposer l'intention en lecture
    # (``infractions/?refacturables=1``), jamais d'écriture cross-app.
    refacture_conducteur = models.BooleanField(
        default=False, verbose_name='Refacturée au conducteur')
    montant_retenu = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Montant retenu (MAD)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Infraction / PV'
        verbose_name_plural = 'Infractions / PV'
        ordering = ['-date_infraction', '-id']
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='flotte_inf_co_stat_idx',
            ),
            models.Index(
                fields=['company', 'actif_flotte'],
                name='flotte_inf_co_actif_idx',
            ),
            models.Index(
                fields=['company', 'type_infraction'],
                name='flotte_inf_co_type_idx',
            ),
            models.Index(
                fields=['company', 'date_infraction'],
                name='flotte_inf_co_date_idx',
            ),
        ]

    def clean(self):
        """Valide l'appartenance société de l'actif et du conducteur liés, ainsi
        que la cohérence du montant."""
        if self.actif_flotte_id is not None \
                and self.actif_flotte.company_id != self.company_id:
            raise ValidationError(
                "L'actif n'appartient pas à la même société.")
        if self.conducteur_id is not None \
                and self.conducteur.company_id != self.company_id:
            raise ValidationError(
                "Le conducteur n'appartient pas à la même société.")
        if self.montant_amende is not None and self.montant_amende < 0:
            raise ValidationError(
                "Le montant de l'amende ne peut pas être négatif.")

    def __str__(self):
        return (f'PV {self.get_type_infraction_display()} — '
                f'{self.actif_flotte} ({self.date_infraction})')


# ── FLOTTE27 — Relevés télématiques (point d'intégration GPS, no-op) ───────────

class ReleveTelematique(models.Model):
    """Relevé télématique d'un actif du parc (FLOTTE27 — point d'intégration GPS).

    Stocke une LECTURE issue d'un boîtier GPS / d'un fournisseur télématique
    externe : odomètre, position GPS, niveau de carburant, heures moteur. Chaque
    relevé est rattaché à un ``ActifFlotte`` (FLOTTE5 — véhicule OU engin) de la
    MÊME société et horodaté.

    POINT D'INTÉGRATION KEY-GATED / NO-OP : ce modèle est le MAGASIN des relevés.
    La SYNCHRONISATION depuis un fournisseur externe
    (``services.synchroniser_releves``) est un NO-OP tant qu'aucun fournisseur
    n'est configuré (``settings.TELEMATIQUE_ENABLED`` faux par défaut) — aucun
    appel réseau, aucune dépendance, aucun coût. L'INGESTION MANUELLE (créer un
    ``ReleveTelematique`` directement, ``source='manuel'``) fonctionne toujours,
    fournisseur ou pas.

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête). L'actif lié doit appartenir à la MÊME société (validé dans
    ``clean`` et au sérialiseur).
    """

    class Source(models.TextChoices):
        MANUEL = 'manuel', 'Saisie manuelle'
        TELEMATIQUE = 'telematique', 'Fournisseur télématique'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_releves_telematiques',
        verbose_name='Société',
    )
    actif_flotte = models.ForeignKey(
        'ActifFlotte',
        on_delete=models.CASCADE,
        related_name='flotte_releves_telematiques',
        verbose_name='Actif (véhicule ou engin)',
    )
    horodatage = models.DateTimeField(verbose_name='Horodatage du relevé')
    odometre = models.DecimalField(
        max_digits=12, decimal_places=1, null=True, blank=True,
        verbose_name='Odomètre (km)')
    position_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        verbose_name='Latitude')
    position_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        verbose_name='Longitude')
    niveau_carburant = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True,
        verbose_name='Niveau de carburant (%)')
    heures_moteur = models.DecimalField(
        max_digits=10, decimal_places=1, null=True, blank=True,
        verbose_name='Heures moteur')
    # Origine du relevé : 'manuel' (saisi à la main, toujours possible) ou
    # 'telematique' (poussé par un fournisseur, via la synchro no-op-gated).
    # CharField borné : 'telematique' (11) est le plus long code (leçon FG136).
    source = models.CharField(
        max_length=20, choices=Source.choices, default=Source.MANUEL,
        verbose_name='Source')
    # Charge brute renvoyée par le fournisseur (additive, jamais figée) — utile
    # pour tracer ce que le boîtier a remonté sans inventer de schéma de colonnes.
    raw_payload = models.JSONField(
        default=dict, blank=True, verbose_name='Charge brute (fournisseur)')
    # XFLT25 — Codes défaut moteur (DTC, Diagnostic Trouble Codes) remontés
    # par le boîtier OU saisis manuellement (la saisie manuelle reste
    # toujours possible, comme le reste de la télématique). Liste de codes
    # bruts (ex. ``["P0301", "P0420"]``) ; la CRITICITÉ par préfixe est un
    # référentiel ÉDITABLE (``ReferentielFlotte`` domaine ``code_dtc``),
    # jamais figée dans ce modèle.
    codes_defaut = models.JSONField(
        default=list, blank=True, verbose_name='Codes défaut moteur (DTC)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Relevé télématique'
        verbose_name_plural = 'Relevés télématiques'
        ordering = ['-horodatage', '-id']
        indexes = [
            models.Index(
                fields=['company', 'actif_flotte'],
                name='flotte_tel_co_actif_idx',
            ),
            models.Index(
                fields=['company', 'horodatage'],
                name='flotte_tel_co_horo_idx',
            ),
        ]

    def clean(self):
        """Valide l'appartenance société de l'actif lié et la cohérence des
        relevés numériques (odomètre / heures non négatifs ; carburant 0–100 %).
        """
        if self.actif_flotte_id is not None \
                and self.actif_flotte.company_id != self.company_id:
            raise ValidationError(
                "L'actif n'appartient pas à la même société.")
        if self.odometre is not None and self.odometre < 0:
            raise ValidationError(
                "L'odomètre ne peut pas être négatif.")
        if self.heures_moteur is not None and self.heures_moteur < 0:
            raise ValidationError(
                "Les heures moteur ne peuvent pas être négatives.")
        if self.niveau_carburant is not None \
                and not (0 <= self.niveau_carburant <= 100):
            raise ValidationError(
                "Le niveau de carburant doit être compris entre 0 et 100 %.")

    def __str__(self):
        return (f'Relevé {self.get_source_display()} — '
                f'{self.actif_flotte} ({self.horodatage:%Y-%m-%d %H:%M})')


# ── FLOTTE28 — Suivi de position & trajets télématiques ────────────────────────

class TrajetTelematique(models.Model):
    """Trajet télématique d'un actif du parc — un déplacement daté (FLOTTE28).

    Matérialise un TRAJET (un déplacement de A à B) d'un véhicule ou d'un engin,
    construit à partir des ``ReleveTelematique`` (FLOTTE27) successifs OU saisi
    manuellement : horodatage et position de départ / d'arrivée, distance
    parcourue (km), durée (minutes), vitesse moyenne. Le trajet peut, en option,
    pointer son relevé de départ et d'arrivée (FK ``ReleveTelematique`` de la
    MÊME société, nullable — un trajet saisi à la main n'en porte pas).

    Le trajet est un MAGASIN : ``services.construire_trajets_telematiques``
    agrège les relevés consécutifs d'un actif en trajets ; la saisie manuelle
    reste toujours possible (aucun fournisseur requis).

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête). L'actif lié ET les relevés liés doivent appartenir à la MÊME
    société (validé dans ``clean`` et au sérialiseur).
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_trajets_telematiques',
        verbose_name='Société',
    )
    actif_flotte = models.ForeignKey(
        'ActifFlotte',
        on_delete=models.CASCADE,
        related_name='flotte_trajets_telematiques',
        verbose_name='Actif (véhicule ou engin)',
    )
    debut = models.DateTimeField(verbose_name='Début du trajet')
    fin = models.DateTimeField(verbose_name='Fin du trajet')
    depart_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        verbose_name='Latitude de départ')
    depart_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        verbose_name='Longitude de départ')
    arrivee_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        verbose_name="Latitude d'arrivée")
    arrivee_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        verbose_name="Longitude d'arrivée")
    distance_km = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Distance parcourue (km)')
    releve_depart = models.ForeignKey(
        'ReleveTelematique',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='trajets_depart',
        verbose_name='Relevé de départ',
    )
    releve_arrivee = models.ForeignKey(
        'ReleveTelematique',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='trajets_arrivee',
        verbose_name="Relevé d'arrivée",
    )
    notes = models.TextField(blank=True, verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Trajet télématique'
        verbose_name_plural = 'Trajets télématiques'
        ordering = ['-debut', '-id']
        indexes = [
            models.Index(
                fields=['company', 'actif_flotte'],
                name='flotte_traj_co_actif_idx',
            ),
            models.Index(
                fields=['company', 'debut'],
                name='flotte_traj_co_debut_idx',
            ),
        ]

    @property
    def duree_minutes(self):
        """Durée du trajet en minutes (float), ou ``None`` si bornes absentes."""
        if self.debut is None or self.fin is None:
            return None
        return round((self.fin - self.debut).total_seconds() / 60.0, 1)

    @property
    def vitesse_moyenne_kmh(self):
        """Vitesse moyenne (km/h), ou ``None`` si distance/durée inexploitable."""
        if self.distance_km is None:
            return None
        minutes = self.duree_minutes
        if not minutes or minutes <= 0:
            return None
        return round(float(self.distance_km) / (minutes / 60.0), 1)

    def clean(self):
        """Valide l'appartenance société de l'actif et des relevés liés, la
        cohérence temporelle (fin ≥ début) et la distance (≥ 0)."""
        if self.actif_flotte_id is not None \
                and self.actif_flotte.company_id != self.company_id:
            raise ValidationError(
                "L'actif n'appartient pas à la même société.")
        if self.debut is not None and self.fin is not None \
                and self.fin < self.debut:
            raise ValidationError(
                "La fin du trajet ne peut pas précéder son début.")
        if self.distance_km is not None and self.distance_km < 0:
            raise ValidationError(
                "La distance parcourue ne peut pas être négative.")
        for champ in ('releve_depart', 'releve_arrivee'):
            releve = getattr(self, champ, None)
            releve_id = getattr(self, f'{champ}_id', None)
            if releve_id is not None and releve is not None \
                    and releve.company_id != self.company_id:
                raise ValidationError(
                    "Un relevé lié n'appartient pas à la même société.")

    def __str__(self):
        return (f'Trajet {self.actif_flotte} '
                f'({self.debut:%Y-%m-%d %H:%M} → {self.fin:%H:%M})')


# ── FLOTTE29 — Journal kilométrique & trajets imputés chantier ─────────────────

class TrajetChantier(models.Model):
    """Trajet d'un actif imputé à un chantier — journal kilométrique (FLOTTE29).

    Tient un JOURNAL KILOMÉTRIQUE imputé chantier : un déplacement d'un véhicule
    ou d'un engin du parc rattaché à un chantier (``installations.Installation``)
    par son id NUMÉRIQUE — jamais un FK cross-app dur (modularité CLAUDE.md). La
    validation « le chantier appartient à la société » se fait côté serveur via
    ``installations.selectors.installation_scoped`` (au sérialiseur). Le trajet
    porte la date, le motif, le kilométrage de départ / d'arrivée et la distance
    parcourue (déduite ou saisie).

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête). L'actif lié doit appartenir à la MÊME société (validé dans
    ``clean`` et au sérialiseur). ``installation_id`` reste un entier libre
    (validé via le sélecteur d'``installations``) — null = trajet non imputé.
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_trajets_chantier',
        verbose_name='Société',
    )
    actif_flotte = models.ForeignKey(
        'ActifFlotte',
        on_delete=models.CASCADE,
        related_name='flotte_trajets_chantier',
        verbose_name='Actif (véhicule ou engin)',
    )
    # FLOTTE29 — référence VERS un chantier (`installations.Installation`) par id
    # NUMÉRIQUE, jamais un FK cross-app dur (modularité, voir CLAUDE.md). null =
    # trajet non imputé à un chantier. La validation « même société » se fait
    # côté serveur via `installations.selectors.installation_scoped`.
    installation_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Chantier (id)')
    date_trajet = models.DateField(verbose_name='Date du trajet')
    motif = models.CharField(
        max_length=255, blank=True, verbose_name='Motif / objet du trajet')
    km_depart = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Kilométrage de départ')
    km_arrivee = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Kilométrage d'arrivée")
    distance_km = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Distance parcourue (km)')
    notes = models.TextField(blank=True, verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Trajet imputé chantier'
        verbose_name_plural = 'Trajets imputés chantier'
        ordering = ['-date_trajet', '-id']
        indexes = [
            models.Index(
                fields=['company', 'actif_flotte'],
                name='flotte_trch_co_actif_idx',
            ),
            models.Index(
                fields=['company', 'installation_id'],
                name='flotte_trch_co_inst_idx',
            ),
            models.Index(
                fields=['company', 'date_trajet'],
                name='flotte_trch_co_date_idx',
            ),
        ]

    @property
    def distance_calculee_km(self):
        """Distance déduite du compteur (``km_arrivee - km_depart``) si possible,
        sinon la ``distance_km`` saisie, sinon ``None``. Lecture seule."""
        if self.km_depart is not None and self.km_arrivee is not None \
                and self.km_arrivee >= self.km_depart:
            return self.km_arrivee - self.km_depart
        if self.distance_km is not None:
            return float(self.distance_km)
        return None

    def clean(self):
        """Valide l'appartenance société de l'actif, la cohérence du kilométrage
        (arrivée ≥ départ) et de la distance (≥ 0). L'appartenance société du
        chantier est validée au sérialiseur (sélecteur d'``installations``)."""
        if self.actif_flotte_id is not None \
                and self.actif_flotte.company_id != self.company_id:
            raise ValidationError(
                "L'actif n'appartient pas à la même société.")
        if self.km_depart is not None and self.km_arrivee is not None \
                and self.km_arrivee < self.km_depart:
            raise ValidationError(
                "Le kilométrage d'arrivée ne peut pas être inférieur "
                "au kilométrage de départ.")
        if self.distance_km is not None and self.distance_km < 0:
            raise ValidationError(
                "La distance parcourue ne peut pas être négative.")

    def __str__(self):
        return (f'Trajet chantier {self.actif_flotte} '
                f'({self.date_trajet})')


# ── FLOTTE32 — Pool de véhicules & demandes ────────────────────────────────────

class DemandeVehicule(models.Model):
    """Demande d'un véhicule du pool partagé (FLOTTE32).

    Un collaborateur DEMANDE un véhicule du parc pour une période donnée (besoin,
    période souhaitée, motif). Le responsable APPROUVE / REFUSE et, à
    l'approbation, attribue un véhicule précis (FK ``Vehicule`` de la MÊME
    société, posé seulement à l'approbation). La demande complète le couple
    affectation/réservation (FLOTTE8/FLOTTE10) par la couche « pool » : qui a
    besoin de quoi, quand, et la décision.

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête). Le demandeur (``authentication.User``), le décideur et le véhicule
    attribué doivent appartenir à la MÊME société (validé dans ``clean`` et au
    sérialiseur).
    """

    class Statut(models.TextChoices):
        DEMANDEE = 'demandee', 'Demandée'
        APPROUVEE = 'approuvee', 'Approuvée'
        REFUSEE = 'refusee', 'Refusée'
        ANNULEE = 'annulee', 'Annulée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_demandes_vehicule',
        verbose_name='Société',
    )
    demandeur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='flotte_demandes_vehicule',
        verbose_name='Demandeur',
    )
    besoin = models.CharField(
        max_length=255, verbose_name='Besoin / objet de la demande')
    date_debut_souhaitee = models.DateField(
        verbose_name='Début souhaité')
    date_fin_souhaitee = models.DateField(
        verbose_name='Fin souhaitée')
    # 'demandee' (8) est la valeur par défaut ; 'approuvee' (9) est le plus long
    # code de statut.
    statut = models.CharField(
        max_length=9, choices=Statut.choices, default=Statut.DEMANDEE,
        verbose_name='Statut')
    # Véhicule attribué à l'approbation (du pool de la même société). null tant
    # que la demande n'est pas approuvée (ou refusée / annulée).
    vehicule_attribue = models.ForeignKey(
        'Vehicule',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='demandes_attribuees',
        verbose_name='Véhicule attribué',
    )
    decide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='flotte_demandes_vehicule_decidees',
        verbose_name='Décidée par',
    )
    date_decision = models.DateTimeField(
        null=True, blank=True, verbose_name='Date de décision')
    motif_decision = models.TextField(
        blank=True, verbose_name='Motif de la décision')
    notes = models.TextField(blank=True, verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Demande de véhicule (pool)'
        verbose_name_plural = 'Demandes de véhicule (pool)'
        ordering = ['-date_creation', '-id']
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='flotte_dem_co_stat_idx',
            ),
            models.Index(
                fields=['company', 'demandeur'],
                name='flotte_dem_co_dem_idx',
            ),
        ]

    def clean(self):
        """Valide l'appartenance société du demandeur, du décideur et du
        véhicule attribué, ainsi que la cohérence des dates (fin ≥ début)."""
        if self.demandeur_id is not None \
                and self.demandeur.company_id != self.company_id:
            raise ValidationError(
                "Le demandeur n'appartient pas à la même société.")
        if self.decide_par_id is not None \
                and self.decide_par.company_id != self.company_id:
            raise ValidationError(
                "Le décideur n'appartient pas à la même société.")
        if self.vehicule_attribue_id is not None \
                and self.vehicule_attribue.company_id != self.company_id:
            raise ValidationError(
                "Le véhicule attribué n'appartient pas à la même société.")
        if self.date_debut_souhaitee is not None \
                and self.date_fin_souhaitee is not None \
                and self.date_fin_souhaitee < self.date_debut_souhaitee:
            raise ValidationError(
                "La fin souhaitée ne peut pas précéder le début souhaité.")

    def __str__(self):
        return (f'Demande {self.get_statut_display()} — '
                f'{self.besoin} ({self.date_debut_souhaitee})')


# ── XFLT1 — Contrats véhicule (leasing/LLD/location/entretien) ────────────────

class ContratVehicule(models.Model):
    """Contrat véhicule (leasing/LLD/location/entretien) rattaché à un
    ``Vehicule`` de la société (XFLT1).

    Distinct de ``AssuranceVehicule`` (FLOTTE21, contrat d'ASSURANCE
    uniquement) : ce modèle couvre les contrats de FINANCEMENT / prestation
    (leasing, location longue durée, location courte, contrat d'entretien,
    garantie constructeur) qui portent un MONTANT RÉCURRENT (loyer mensuel/
    trimestriel/annuel) plutôt qu'une prime d'assurance. Jamais de doublon
    entre les deux familles.

    ``statut_calcule(today)`` retourne l'état RÉEL du contrat vs une date
    (``expire`` si ``date_fin`` est dépassée, ``actif`` sinon) — lecture
    seule, date injectable, ne modifie rien en base.

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête). Le véhicule et le garage (bailleur/fournisseur interne)
    rattachés doivent appartenir à la MÊME société (validé dans ``clean``).
    """

    class TypeContrat(models.TextChoices):
        LEASING = 'leasing', 'Leasing'
        LLD = 'lld', 'Location longue durée (LLD)'
        LOCATION = 'location', 'Location'
        CONTRAT_ENTRETIEN = 'contrat_entretien', "Contrat d'entretien"
        GARANTIE_CONSTRUCTEUR = 'garantie_constructeur', \
            'Garantie constructeur'

    class Periodicite(models.TextChoices):
        MENSUEL = 'mensuel', 'Mensuel'
        TRIMESTRIEL = 'trimestriel', 'Trimestriel'
        ANNUEL = 'annuel', 'Annuel'

    class Statut(models.TextChoices):
        ACTIF = 'actif', 'Actif'
        EXPIRE = 'expire', 'Expiré'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_contrats_vehicule',
        verbose_name='Société',
    )
    vehicule = models.ForeignKey(
        'Vehicule',
        on_delete=models.CASCADE,
        related_name='contrats_vehicule',
        verbose_name='Véhicule',
    )
    type_contrat = models.CharField(
        max_length=25, choices=TypeContrat.choices,
        default=TypeContrat.LOCATION, verbose_name='Type de contrat')
    fournisseur = models.CharField(
        max_length=150, blank=True,
        verbose_name='Fournisseur / bailleur')
    # WIR90 — lien OPTIONNEL du bailleur/loueur vers un `stock.Fournisseur`
    # référencé (par id NUMÉRIQUE, jamais un FK cross-app dur — modularité
    # CLAUDE.md). Le CharField `fournisseur` reste la saisie libre par défaut ;
    # renseigné, `fournisseur_id_ref` pointe vers l'identité canonique (ICE/IF/
    # RC/RIB déjà portés par le fournisseur). Validation « même société » côté
    # serveur via le sélecteur `apps.stock` (voir CoutVehicule, même pattern).
    fournisseur_id_ref = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Fournisseur (référentiel stock)')
    garage = models.ForeignKey(
        'Garage',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contrats_vehicule',
        verbose_name='Garage / atelier (si prestataire référencé)',
    )
    date_debut = models.DateField(verbose_name='Début du contrat')
    date_fin = models.DateField(
        null=True, blank=True, verbose_name='Fin du contrat')
    montant_recurrent = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Montant récurrent (MAD)')
    periodicite = models.CharField(
        max_length=12, choices=Periodicite.choices,
        default=Periodicite.MENSUEL, verbose_name='Périodicité')
    services_inclus = models.JSONField(
        default=list, blank=True, verbose_name='Services inclus')
    km_contractuel_an = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Km contractuel / an')
    statut = models.CharField(
        max_length=7, choices=Statut.choices, default=Statut.ACTIF,
        verbose_name='Statut')
    notes = models.TextField(blank=True, verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Contrat véhicule'
        verbose_name_plural = 'Contrats véhicule'
        ordering = ['date_fin', 'id']
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='flotte_ctrv_co_stat_idx',
            ),
            models.Index(
                fields=['company', 'vehicule'],
                name='flotte_ctrv_co_veh_idx',
            ),
            models.Index(
                fields=['company', 'date_fin'],
                name='flotte_ctrv_co_fin_idx',
            ),
        ]

    def clean(self):
        """Valide l'appartenance société du véhicule/garage et la cohérence
        des dates (fin ≥ début)."""
        if self.vehicule_id is not None \
                and self.vehicule.company_id != self.company_id:
            raise ValidationError(
                "Le véhicule n'appartient pas à la même société.")
        if self.garage_id is not None \
                and self.garage.company_id != self.company_id:
            raise ValidationError(
                "Le garage n'appartient pas à la même société.")
        if self.date_fin is not None and self.date_debut is not None \
                and self.date_fin < self.date_debut:
            raise ValidationError(
                "La fin du contrat ne peut pas précéder le début.")
        # WIR90 — le bailleur/loueur référencé (optionnel) doit appartenir à la
        # même société ; le CharField `fournisseur` reste le repli en saisie libre.
        if self.fournisseur_id_ref is not None and self.company_id is not None:
            from apps.stock.selectors import get_fournisseur_by_id
            if get_fournisseur_by_id(
                    self.company, self.fournisseur_id_ref) is None:
                raise ValidationError(
                    "Le fournisseur référencé n'appartient pas à la même "
                    "société.")

    def statut_calcule(self, today=None):
        """État RÉEL du contrat vs ``today`` (lecture seule, date injectable).

        Retourne ``'expire'`` si ``date_fin`` est renseignée et déjà passée,
        ``'actif'`` sinon (y compris contrat sans date de fin — durée
        indéterminée). ``today`` défaut = date du jour.
        """
        if today is None:
            today = datetime.date.today()
        if self.date_fin is not None and self.date_fin < today:
            return self.Statut.EXPIRE
        return self.Statut.ACTIF

    def __str__(self):
        return (f'{self.get_type_contrat_display()} — {self.vehicule} '
                f'({self.montant_recurrent} MAD/{self.periodicite})')


# ── XFLT2 — Génération des coûts récurrents de contrat ─────────────────────────

class EcheanceContrat(models.Model):
    """Ligne de coût datée matérialisant l'échéance d'un ``ContratVehicule``
    (XFLT2).

    Générée par ``services.generer_couts_contrat`` : une ligne PAR contrat ET
    PAR période (``unique_together`` — garantit l'IDEMPOTENCE de la
    génération, deux exécutions sur la même période ne créent qu'une seule
    ligne). ``period`` est une chaîne ``'YYYY-MM'`` (mensuel — la seule
    granularité de génération, indépendamment de la ``periodicite`` du
    contrat qui reste informative sur le montant facturé).

    Modèle transitoire : si ``CoutVehicule`` (XFLT3) existe sur cette
    branche, la génération y écrit à la place (voir docstring du service) —
    ce modèle reste le repli tant que XFLT3 n'est pas construit.

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête). Le contrat lié doit appartenir à la MÊME société.
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_echeances_contrat',
        verbose_name='Société',
    )
    contrat = models.ForeignKey(
        'ContratVehicule',
        on_delete=models.CASCADE,
        related_name='echeances',
        verbose_name='Contrat véhicule',
    )
    period = models.CharField(
        max_length=7, verbose_name='Période (YYYY-MM)')
    date_echeance = models.DateField(verbose_name="Date de l'échéance")
    montant = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Montant (MAD)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Échéance de contrat'
        verbose_name_plural = 'Échéances de contrat'
        ordering = ['-date_echeance', '-id']
        unique_together = [('contrat', 'period')]
        indexes = [
            models.Index(
                fields=['company', 'period'],
                name='flotte_ecc_co_period_idx',
            ),
        ]

    def clean(self):
        """Valide l'appartenance société du contrat lié."""
        if self.contrat_id is not None \
                and self.contrat.company_id != self.company_id:
            raise ValidationError(
                "Le contrat n'appartient pas à la même société.")

    def __str__(self):
        return f'Échéance {self.period} — {self.contrat} ({self.montant} MAD)'


# ── XFLT3 — Grand livre des coûts par véhicule ──────────────────────────────────

class CoutVehicule(models.Model):
    """Ligne de coût divers saisie manuellement pour un actif de flotte
    (XFLT3).

    Capture les coûts qu'aucun autre modèle flotte ne saisit aujourd'hui
    (péage Jawaz, parking, lavage…) mais aussi tout coût libre rattachable à
    un contrat (catégorie ``contrat``). Alimente le grand livre unifié
    ``selectors.ledger_vehicule`` aux côtés de ``PleinCarburant``,
    ``OrdreReparation.cout_total``, ``AssuranceVehicule``, la TSAV et
    ``Infraction.montant_amende`` — sans dupliquer ces sources : une dépense
    déjà saisie ailleurs (carburant, réparation…) n'a PAS à être re-saisie
    ici.

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête). L'actif et le conducteur liés doivent appartenir à la MÊME
    société (validé dans ``clean``).
    """

    class Categorie(models.TextChoices):
        CARBURANT = 'carburant', 'Carburant'
        ENTRETIEN = 'entretien', 'Entretien'
        ASSURANCE = 'assurance', 'Assurance'
        VIGNETTE = 'vignette', 'Vignette'
        AMENDE = 'amende', 'Amende'
        PEAGE = 'peage', 'Péage'
        PARKING = 'parking', 'Parking'
        LAVAGE = 'lavage', 'Lavage'
        CONTRAT = 'contrat', 'Contrat'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_couts_vehicule',
        verbose_name='Société',
    )
    actif_flotte = models.ForeignKey(
        'ActifFlotte',
        on_delete=models.CASCADE,
        related_name='flotte_couts_vehicule',
        verbose_name='Actif (véhicule ou engin)',
    )
    categorie = models.CharField(
        max_length=10, choices=Categorie.choices, default=Categorie.AUTRE,
        verbose_name='Catégorie')
    date = models.DateField(verbose_name='Date')
    montant = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Montant (MAD)')
    fournisseur = models.CharField(
        max_length=150, blank=True, verbose_name='Fournisseur',
        help_text='Repli en saisie libre pour un fournisseur ponctuel — '
                  'préférer `fournisseur_id` (référentiel stock.Fournisseur, '
                  'qui porte déjà ICE/IF/RC/RIB) quand il existe.')
    # XFLT26 — préparation e-facturation DGI : référence VERS un
    # `stock.Fournisseur` (qui porte DÉJÀ ICE/IF/RC/RIB, DC15) par id
    # NUMÉRIQUE, jamais un FK cross-app dur (modularité, voir CLAUDE.md). null
    # = coût sans fournisseur référencé (repli sur le champ `fournisseur` en
    # saisie libre). La validation « même société » se fait côté serveur via
    # le sélecteur de `apps.stock`.
    fournisseur_id_ref = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Fournisseur (référentiel stock)')
    reference_piece = models.CharField(
        max_length=80, blank=True, verbose_name='Référence pièce')
    conducteur = models.ForeignKey(
        'Conducteur',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='flotte_couts_vehicule',
        verbose_name='Conducteur',
    )
    notes = models.TextField(blank=True, verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Coût véhicule'
        verbose_name_plural = 'Coûts véhicule'
        ordering = ['-date', '-id']
        indexes = [
            models.Index(
                fields=['company', 'actif_flotte'],
                name='flotte_cv_co_actif_idx',
            ),
            models.Index(
                fields=['company', 'categorie'],
                name='flotte_cv_co_cat_idx',
            ),
            models.Index(
                fields=['company', 'date'],
                name='flotte_cv_co_date_idx',
            ),
        ]

    # XFLT26 — au-delà de ce montant (MAD), une référence de facture
    # structurée (``reference_piece``) est exigée en WARNING (non bloquant —
    # voir ``CoutVehiculeSerializer.get_reference_avertissement``).
    SEUIL_REFERENCE_MAD = 5000

    def clean(self):
        """Valide l'appartenance société de l'actif et du conducteur, et un
        montant non négatif."""
        if self.actif_flotte_id is not None \
                and self.actif_flotte.company_id != self.company_id:
            raise ValidationError(
                "L'actif n'appartient pas à la même société.")
        if self.conducteur_id is not None \
                and self.conducteur.company_id != self.company_id:
            raise ValidationError(
                "Le conducteur n'appartient pas à la même société.")
        if self.montant is not None and self.montant < 0:
            raise ValidationError(
                "Le montant ne peut pas être négatif.")
        if self.fournisseur_id_ref is not None:
            from apps.stock.selectors import get_fournisseur_by_id
            if get_fournisseur_by_id(
                    self.company, self.fournisseur_id_ref) is None:
                raise ValidationError(
                    "Le fournisseur référencé n'appartient pas à la même "
                    "société.")

    def __str__(self):
        return (f'{self.get_categorie_display()} — {self.actif_flotte} '
                f'({self.montant} MAD, {self.date})')


# ── XFLT5 — Signalement d'anomalie véhicule par le conducteur ──────────────────

class SignalementVehicule(models.Model):
    """Signalement d'anomalie sur un actif de flotte, déposé par un
    conducteur (XFLT5).

    Tout rôle peut CRÉER un signalement (comme ``DemandeVehicule``, FLOTTE32)
    — la résolution (passage à ``en_cours``/``resolu``/``clos``) reste
    réservée aux rôles écriture. L'action ``convertir-en-or`` crée un
    ``OrdreReparation`` (FLOTTE17) pré-rempli et lie les deux.

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête). L'actif et le conducteur liés (si renseigné) doivent
    appartenir à la MÊME société (validé dans ``clean``).
    """

    class Gravite(models.TextChoices):
        FAIBLE = 'faible', 'Faible'
        MOYENNE = 'moyenne', 'Moyenne'
        CRITIQUE = 'critique', 'Critique'

    class Statut(models.TextChoices):
        OUVERT = 'ouvert', 'Ouvert'
        EN_COURS = 'en_cours', 'En cours'
        RESOLU = 'resolu', 'Résolu'
        CLOS = 'clos', 'Clos'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_signalements_vehicule',
        verbose_name='Société',
    )
    actif_flotte = models.ForeignKey(
        'ActifFlotte',
        on_delete=models.CASCADE,
        related_name='flotte_signalements_vehicule',
        verbose_name='Actif (véhicule ou engin)',
    )
    conducteur = models.ForeignKey(
        'Conducteur',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='flotte_signalements_vehicule',
        verbose_name='Conducteur',
    )
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='flotte_signalements_vehicule',
        verbose_name='Auteur',
    )
    description = models.TextField(verbose_name='Description')
    photo = models.FileField(
        upload_to='flotte/signalements/photos/%Y/%m/',
        blank=True, null=True, verbose_name='Photo')
    gravite = models.CharField(
        max_length=8, choices=Gravite.choices, default=Gravite.MOYENNE,
        verbose_name='Gravité')
    statut = models.CharField(
        max_length=8, choices=Statut.choices, default=Statut.OUVERT,
        verbose_name='Statut')
    ordre_reparation = models.ForeignKey(
        'OrdreReparation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='signalements',
        verbose_name='Ordre de réparation lié',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Signalement d'anomalie véhicule"
        verbose_name_plural = "Signalements d'anomalie véhicule"
        ordering = ['-date_creation', '-id']
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='flotte_sig_co_stat_idx',
            ),
            models.Index(
                fields=['company', 'actif_flotte'],
                name='flotte_sig_co_actif_idx',
            ),
        ]

    def clean(self):
        """Valide l'appartenance société de l'actif, du conducteur et de
        l'auteur."""
        if self.actif_flotte_id is not None \
                and self.actif_flotte.company_id != self.company_id:
            raise ValidationError(
                "L'actif n'appartient pas à la même société.")
        if self.conducteur_id is not None \
                and self.conducteur.company_id != self.company_id:
            raise ValidationError(
                "Le conducteur n'appartient pas à la même société.")
        if self.auteur_id is not None \
                and self.auteur.company_id != self.company_id:
            raise ValidationError(
                "L'auteur n'appartient pas à la même société.")

    def __str__(self):
        return (f'Signalement {self.get_gravite_display()} — '
                f'{self.actif_flotte} [{self.get_statut_display()}]')


# ── XFLT9 — Plafond CGI d'amortissement des véhicules de tourisme ──────────────

class ParametreAmortissementCGI(models.Model):
    """Paramètre société du plafond CGI d'amortissement des véhicules de
    tourisme (XFLT9).

    Un seul enregistrement par société (``OneToOne``-like via
    ``unique=True``) : la valeur d'acquisition TTC des véhicules
    ``type_fiscal='tourisme'`` au-delà de ``plafond_ttc`` génère une part
    d'amortissement NON déductible fiscalement (article CGI, LF 2025 :
    plafond par défaut 400 000 DH TTC). Les véhicules utilitaires sont
    EXONÉRÉS du plafond (jamais de part non déductible).

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête).
    """

    PLAFOND_DEFAUT = 400000

    company = models.OneToOneField(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_parametre_amortissement_cgi',
        verbose_name='Société',
    )
    plafond_ttc = models.DecimalField(
        max_digits=12, decimal_places=2, default=PLAFOND_DEFAUT,
        verbose_name='Plafond CGI (DH TTC)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Paramètre d'amortissement CGI"
        verbose_name_plural = "Paramètres d'amortissement CGI"

    def __str__(self):
        return f'Plafond CGI {self.company} : {self.plafond_ttc} DH TTC'

    @classmethod
    def plafond_pour(cls, company):
        """XFLT9 — Plafond CGI (DH TTC) de la société, ou la valeur par
        défaut si non paramétré. Lecture seule."""
        param = cls.objects.filter(company=company).first()
        if param is not None:
            return float(param.plafond_ttc)
        return float(cls.PLAFOND_DEFAUT)


# ── XFLT12 — Catalogue de modèles véhicule ──────────────────────────────────────

class ModeleVehicule(models.Model):
    """Catalogue de modèles véhicule de référence (XFLT12).

    Fiche modèle réutilisable (marque + modèle + specs standard) permettant de
    pré-remplir un ``Vehicule`` à la création (``modele_ref``) sans écraser une
    saisie existante. Le ``co2_g_km`` alimente l'éco-conduite (FLOTTE33) en
    FALLBACK quand le véhicule n'a pas sa propre valeur mesurée ; la
    ``capacite_reservoir_l`` renforce le détecteur d'anomalies FLOTTE14 (plein
    > capacité réservoir = fraude probable).

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête).
    """

    class Categorie(models.TextChoices):
        VOITURE = 'voiture', 'Voiture'
        FOURGON = 'fourgon', 'Fourgon'
        CAMION = 'camion', 'Camion'
        REMORQUE = 'remorque', 'Remorque'
        CHARIOT = 'chariot', 'Chariot'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_modeles_vehicule',
        verbose_name='Société',
    )
    marque = models.CharField(max_length=80, verbose_name='Marque')
    modele = models.CharField(max_length=80, verbose_name='Modèle')
    categorie = models.CharField(
        max_length=10, choices=Categorie.choices, default=Categorie.VOITURE,
        verbose_name='Catégorie')
    energie = models.CharField(
        max_length=20, choices=Vehicule.Energie.choices,
        default=Vehicule.Energie.DIESEL, verbose_name='Énergie')
    co2_g_km = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='CO₂ (g/km)')
    places = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Places')
    puissance_fiscale = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Puissance fiscale (CV)')
    puissance_kw = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Puissance (kW)')
    valeur_catalogue = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Valeur catalogue (MAD)')
    capacite_reservoir_l = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Capacité réservoir (L)',
        help_text='Sert au détecteur de fraude FLOTTE14 : un plein '
        'dépassant cette capacité est une anomalie.')
    # ZCTR11 — Enrichissement fiscal du catalogue. ``valeur_residuelle`` sert
    # de repli au TCO/amortissement quand le véhicule n'a pas (encore) sa
    # propre estimation ; ``pct_charges_non_deductibles`` (0-100, plafond CGI
    # tourisme) est pré-rempli sur le ``Vehicule`` à la sélection du modèle et
    # lu par la synthèse fiscale (XFLT8/XFLT9) pour signaler la part non
    # déductible. Tous deux nullable/optionnels : aucune régression sur les
    # modèles déjà catalogués.
    valeur_residuelle = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Valeur résiduelle (MAD)')
    pct_charges_non_deductibles = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='% charges non déductibles',
        help_text='0-100 — plafond CGI tourisme. Vide = non renseigné '
        '(aucune part non déductible signalée).')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Modèle véhicule (catalogue)'
        verbose_name_plural = 'Modèles véhicule (catalogue)'
        ordering = ['marque', 'modele']
        indexes = [
            models.Index(
                fields=['company', 'marque', 'modele'],
                name='flotte_modveh_co_mm_idx',
            ),
        ]

    def clean(self):
        """ZCTR11 — ``pct_charges_non_deductibles`` doit rester dans [0, 100]
        quand renseigné (vide = non renseigné, aucune contrainte)."""
        if self.pct_charges_non_deductibles is not None and not (
                0 <= self.pct_charges_non_deductibles <= 100):
            raise ValidationError(
                "Le % de charges non déductibles doit être compris entre "
                "0 et 100.")

    def __str__(self):
        return f'{self.marque} {self.modele}'


# ── XFLT13 — Inspections périodiques paramétrables (check-lists DVIR) ──────────

class ModeleInspection(models.Model):
    """Modèle de check-list d'inspection périodique pré-départ (XFLT13).

    Distinct de l'état des lieux ``EtatDesLieux`` (FLOTTE11, remise/retour de
    véhicule) : ceci est l'inspection PÉRIODIQUE (type DVIR — Driver Vehicle
    Inspection Report), généralement pré-départ, paramétrable par société.
    ``items`` est une liste JSON ``[{"libelle": str, "photo_requise": bool,
    "bloquant": bool}, …]`` — la structure des items reste souple (pas de
    modèle enfant) pour rester simple à éditer côté founder.

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête).
    """

    class TypeActifCible(models.TextChoices):
        VEHICULE = 'vehicule', 'Véhicule'
        ENGIN = 'engin', 'Engin roulant'
        TOUS = 'tous', 'Tous'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_modeles_inspection',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=120, verbose_name='Nom')
    type_actif_cible = models.CharField(
        max_length=10, choices=TypeActifCible.choices,
        default=TypeActifCible.TOUS, verbose_name="Type d'actif visé")
    items = models.JSONField(
        default=list, blank=True, verbose_name='Items de la check-list',
        help_text='[{"libelle": str, "photo_requise": bool, '
        '"bloquant": bool}, …]')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Modèle d'inspection"
        verbose_name_plural = "Modèles d'inspection"
        ordering = ['nom']

    def __str__(self):
        return self.nom


class InspectionVehicule(models.Model):
    """Inspection périodique pré-départ réalisée sur un actif (XFLT13).

    Résultats par item stockés en JSON, alignés sur ``ModeleInspection.items``
    par INDEX : ``[{"libelle": str, "resultat": "pass"|"fail", "photo": url|
    None}, …]``. Tout item ``fail`` crée automatiquement un
    ``SignalementVehicule`` lié (voir ``services.traiter_items_fail``).
    ``signature_nom`` est le nom saisi par le conducteur/utilisateur au moment
    de la validation (e-signature loi 53-05, comme le flux devis existant) —
    pas de signature graphique, juste un nom + horodatage serveur.

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête). L'actif et le modèle liés doivent appartenir à la MÊME société.
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_inspections_vehicule',
        verbose_name='Société',
    )
    actif_flotte = models.ForeignKey(
        'ActifFlotte',
        on_delete=models.CASCADE,
        related_name='flotte_inspections_vehicule',
        verbose_name='Actif (véhicule ou engin)',
    )
    modele_inspection = models.ForeignKey(
        'ModeleInspection',
        on_delete=models.PROTECT,
        related_name='inspections',
        verbose_name="Modèle d'inspection",
    )
    conducteur = models.ForeignKey(
        'Conducteur',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='flotte_inspections_vehicule',
        verbose_name='Conducteur',
    )
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='flotte_inspections_vehicule',
        verbose_name='Auteur',
    )
    date_inspection = models.DateTimeField(
        auto_now_add=True, verbose_name="Date de l'inspection")
    resultats = models.JSONField(
        default=list, blank=True, verbose_name='Résultats par item',
        help_text='[{"libelle": str, "resultat": "pass"|"fail", '
        '"photo": url|None}, …]')
    signature_nom = models.CharField(
        max_length=150, blank=True,
        verbose_name='Nom du signataire (e-signature)')
    signature_horodatage = models.DateTimeField(
        null=True, blank=True, verbose_name='Horodatage de signature')

    class Meta:
        verbose_name = 'Inspection véhicule'
        verbose_name_plural = 'Inspections véhicule'
        ordering = ['-date_inspection', '-id']
        indexes = [
            models.Index(
                fields=['company', 'actif_flotte'],
                name='flotte_insp_co_actif_idx',
            ),
            models.Index(
                fields=['company', 'conducteur'],
                name='flotte_insp_co_cond_idx',
            ),
        ]

    def clean(self):
        """Valide l'appartenance société de l'actif, du modèle et du
        conducteur liés."""
        if self.actif_flotte_id is not None \
                and self.actif_flotte.company_id != self.company_id:
            raise ValidationError(
                "L'actif n'appartient pas à la même société.")
        if self.modele_inspection_id is not None \
                and self.modele_inspection.company_id != self.company_id:
            raise ValidationError(
                "Le modèle d'inspection n'appartient pas à la même société.")
        if self.conducteur_id is not None \
                and self.conducteur.company_id != self.company_id:
            raise ValidationError(
                "Le conducteur n'appartient pas à la même société.")

    def nb_items_fail(self):
        """XFLT13 — Nombre d'items en échec (``resultat='fail'``). Lecture
        seule, calculé depuis ``resultats``."""
        return sum(
            1 for item in (self.resultats or [])
            if item.get('resultat') == 'fail')

    def __str__(self):
        return (f'Inspection {self.modele_inspection.nom} — '
                f'{self.actif_flotte} ({self.date_inspection:%Y-%m-%d})')


# ── XFLT14 — Garanties véhicule & pièces ────────────────────────────────────────

class GarantieFlotte(models.Model):
    """Garantie constructeur/fournisseur sur un actif ou un composant
    (XFLT14).

    ``composant`` est du texte libre (ex. « moteur », « boîte de vitesses »)
    ou la valeur conventionnelle ``'vehicule'`` pour une garantie couvrant
    l'actif entier. La couverture est exprimée en durée (``duree_mois``
    depuis ``date_debut``) ET/OU en kilométrage (``duree_km``) — l'un des
    deux suffit, les deux peuvent coexister (garantie expire au premier
    seuil atteint). À la création d'un ``OrdreReparation``, un warning NON
    BLOQUANT est levé si l'actif a une garantie active couvrant la date (et
    le km courant si renseigné) — voir ``services.garantie_active_pour``.

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête). L'actif lié doit appartenir à la MÊME société.
    """

    VEHICULE_ENTIER = 'vehicule'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_garanties',
        verbose_name='Société',
    )
    actif_flotte = models.ForeignKey(
        'ActifFlotte',
        on_delete=models.CASCADE,
        related_name='flotte_garanties',
        verbose_name='Actif (véhicule ou engin)',
    )
    composant = models.CharField(
        max_length=120, default=VEHICULE_ENTIER, verbose_name='Composant',
        help_text="Texte libre, ou 'vehicule' pour une garantie couvrant "
        "l'actif entier.")
    duree_mois = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Durée (mois)')
    duree_km = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Durée (km)')
    date_debut = models.DateField(verbose_name='Date de début')
    fournisseur = models.CharField(
        max_length=150, blank=True, verbose_name='Fournisseur')
    notes = models.TextField(blank=True, verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Garantie flotte'
        verbose_name_plural = 'Garanties flotte'
        ordering = ['-date_debut', '-id']
        indexes = [
            models.Index(
                fields=['company', 'actif_flotte'],
                name='flotte_gar_co_actif_idx',
            ),
        ]

    def clean(self):
        """Valide l'appartenance société de l'actif lié."""
        if self.actif_flotte_id is not None \
                and self.actif_flotte.company_id != self.company_id:
            raise ValidationError(
                "L'actif n'appartient pas à la même société.")

    def date_fin(self):
        """XFLT14 — Date d'expiration par durée (mois), ou ``None`` si
        ``duree_mois`` n'est pas renseignée. Lecture seule."""
        if self.duree_mois is None or self.date_debut is None:
            return None
        total = self.date_debut.month - 1 + int(self.duree_mois)
        year = self.date_debut.year + total // 12
        month = total % 12 + 1
        if month == 12:
            last_day = 31
        else:
            last_day = (datetime.date(year, month + 1, 1)
                        - datetime.timedelta(days=1)).day
        day = min(self.date_debut.day, last_day)
        return datetime.date(year, month, day)

    def couvre(self, today=None, kilometrage=None):
        """XFLT14 — ``True`` si la garantie couvre encore ``today`` (et
        ``kilometrage`` si les deux sont renseignés — expire au PREMIER
        seuil atteint). Lecture seule, dates/km injectables."""
        if today is None:
            today = datetime.date.today()
        if today < self.date_debut:
            return False
        fin_date = self.date_fin()
        if fin_date is not None and today > fin_date:
            return False
        if self.duree_km is not None and kilometrage is not None \
                and kilometrage > self.duree_km:
            return False
        return True

    def __str__(self):
        return f'Garantie {self.composant} — {self.actif_flotte}'


# ── XFLT15 — Analyse de remplacement (fin de vie économique) ───────────────────

class ParametreRemplacementFlotte(models.Model):
    """Seuils société pour l'analyse de remplacement (XFLT15).

    Un seul enregistrement par société (comme
    ``ParametreAmortissementCGI``) — style « 50/30/20 » : un véhicule
    dépassant AU MOINS 2 des 3 règles (âge, kilométrage, ratio coût-
    réparations-12-mois / valeur vénale) est flaggé « à remplacer ».

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête).
    """

    AGE_MAX_ANS_DEFAUT = 8
    KM_MAX_DEFAUT = 200000
    RATIO_COUT_REPARATION_DEFAUT = 0.30  # 30 % de la valeur vénale / an.

    company = models.OneToOneField(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_parametre_remplacement',
        verbose_name='Société',
    )
    age_max_ans = models.PositiveSmallIntegerField(
        default=AGE_MAX_ANS_DEFAUT, verbose_name='Âge maximal (ans)')
    km_max = models.PositiveIntegerField(
        default=KM_MAX_DEFAUT, verbose_name='Kilométrage maximal')
    ratio_cout_reparation_max = models.DecimalField(
        max_digits=4, decimal_places=2, default=RATIO_COUT_REPARATION_DEFAUT,
        verbose_name='Ratio coût-réparations/valeur vénale max')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Paramètre de remplacement flotte'
        verbose_name_plural = 'Paramètres de remplacement flotte'

    def __str__(self):
        return f'Seuils remplacement {self.company}'

    @classmethod
    def pour(cls, company):
        """XFLT15 — Paramètre de la société, ou les valeurs par défaut si
        non paramétré. Lecture seule."""
        param = cls.objects.filter(company=company).first()
        if param is not None:
            return param
        return cls(
            company=company, age_max_ans=cls.AGE_MAX_ANS_DEFAUT,
            km_max=cls.KM_MAX_DEFAUT,
            ratio_cout_reparation_max=cls.RATIO_COUT_REPARATION_DEFAUT)


# ── XFLT17 — Charte véhicule + accusé de lecture ────────────────────────────────

class CharteVehicule(models.Model):
    """Charte véhicule versionnée d'une société (XFLT17).

    Document (FileField) décrivant les règles d'usage du véhicule ; VERSIONNÉ
    (``version`` entier croissant par société) — une nouvelle version
    n'écrase jamais l'ancienne (historique conservé), elle rend juste les
    accusés antérieurs obsolètes vs la version courante (voir
    ``AccuseCharte`` et ``services.charte_courante``).

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête).
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_chartes_vehicule',
        verbose_name='Société',
    )
    version = models.PositiveIntegerField(verbose_name='Version')
    document = models.FileField(
        upload_to='flotte/chartes_vehicule/%Y/%m/',
        verbose_name='Document (charte véhicule)')
    date_publication = models.DateTimeField(
        auto_now_add=True, verbose_name='Date de publication')

    class Meta:
        verbose_name = 'Charte véhicule'
        verbose_name_plural = 'Chartes véhicule'
        unique_together = [('company', 'version')]
        ordering = ['-version']

    def __str__(self):
        return f'Charte véhicule v{self.version} — {self.company}'


class AccuseCharte(models.Model):
    """Accusé de lecture de la charte véhicule par un conducteur (XFLT17).

    Un conducteur accuse réception d'une VERSION précise de la charte
    (``conducteur`` + ``version`` + horodatage serveur — nom saisi comme les
    autres e-signatures flotte). À la première affectation d'un conducteur
    (``AffectationConducteur``), un warning non bloquant liste la version
    courante si aucun accusé ne la couvre (voir
    ``services.accuse_charte_manquant``).

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête). Le conducteur lié doit appartenir à la MÊME société.
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_accuses_charte',
        verbose_name='Société',
    )
    conducteur = models.ForeignKey(
        'Conducteur',
        on_delete=models.CASCADE,
        related_name='flotte_accuses_charte',
        verbose_name='Conducteur',
    )
    version = models.PositiveIntegerField(
        verbose_name='Version de la charte accusée')
    date_accuse = models.DateTimeField(
        auto_now_add=True, verbose_name="Date de l'accusé")

    class Meta:
        verbose_name = 'Accusé de charte véhicule'
        verbose_name_plural = 'Accusés de charte véhicule'
        unique_together = [('company', 'conducteur', 'version')]
        ordering = ['-date_accuse']

    def clean(self):
        """Valide l'appartenance société du conducteur lié."""
        if self.conducteur_id is not None \
                and self.conducteur.company_id != self.company_id:
            raise ValidationError(
                "Le conducteur n'appartient pas à la même société.")

    def __str__(self):
        return f'Accusé charte v{self.version} — {self.conducteur}'


# ── XFLT18 — Budget flotte annuel vs réalisé ────────────────────────────────────

class BudgetFlotte(models.Model):
    """Budget flotte annuel par catégorie de coût (XFLT18).

    Une ligne budgétaire par ``(company, annee, categorie)`` — mêmes clés de
    catégorie que le ledger unifié (XFLT3, ``CoutVehicule.Categorie``), le
    variance vs réalisé est calculé par
    ``selectors.variance_budget_flotte`` (agrégat du ledger, jamais
    dupliqué ici).

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête).
    """

    class Categorie(models.TextChoices):
        CARBURANT = 'carburant', 'Carburant'
        ENTRETIEN = 'entretien', 'Entretien'
        ASSURANCE = 'assurance', 'Assurance'
        VIGNETTE = 'vignette', 'Vignette'
        CONTRAT = 'contrat', 'Contrat'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_budgets',
        verbose_name='Société',
    )
    annee = models.PositiveSmallIntegerField(verbose_name='Année')
    categorie = models.CharField(
        max_length=10, choices=Categorie.choices, default=Categorie.AUTRE,
        verbose_name='Catégorie')
    montant_budgete = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Montant budgété (MAD)')
    # XFLT18 — Trace qu'une alerte de dépassement (>100 %) a déjà été
    # notifiée pour CETTE ligne budgétaire (idempotence : une seule
    # notification par (société, année, catégorie), jamais renvoyée en
    # boucle par un cron/appel répété de ``services.verifier_depassements``).
    notifie_depassement = models.BooleanField(
        default=False, verbose_name='Dépassement déjà notifié')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Budget flotte'
        verbose_name_plural = 'Budgets flotte'
        unique_together = [('company', 'annee', 'categorie')]
        ordering = ['-annee', 'categorie']

    def clean(self):
        """Valide que le montant budgété n'est pas négatif."""
        if self.montant_budgete is not None and self.montant_budgete < 0:
            raise ValidationError(
                "Le montant budgété ne peut pas être négatif.")

    def __str__(self):
        return (f'Budget {self.get_categorie_display()} {self.annee} — '
                f'{self.montant_budgete} MAD')


# ── XFLT19 — Approbation des devis de réparation externe ───────────────────────

class ParametreApprobationOR(models.Model):
    """Seuil société d'approbation des devis de réparation (XFLT19).

    Un seul enregistrement par société (comme ``ParametreAmortissementCGI``) :
    un ``OrdreReparation`` dont ``montant_devis`` dépasse ``seuil_approbation``
    exige l'action ``approuver/`` (rôle gestionnaire — réutilise la mécanique
    rôles existante de ``DemandeVehicule``) avant de pouvoir passer en
    ``en_cours``.

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête).
    """

    SEUIL_APPROBATION_DEFAUT = 5000
    ECART_ALERTE_PCT_DEFAUT = 10

    company = models.OneToOneField(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_parametre_approbation_or',
        verbose_name='Société',
    )
    seuil_approbation = models.DecimalField(
        max_digits=12, decimal_places=2, default=SEUIL_APPROBATION_DEFAUT,
        verbose_name='Seuil d’approbation (MAD)')
    ecart_alerte_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=ECART_ALERTE_PCT_DEFAUT,
        verbose_name='Écart facture/devis alerte (%)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Paramètre d'approbation OR"
        verbose_name_plural = "Paramètres d'approbation OR"

    def __str__(self):
        return f'Seuil approbation OR {self.company} : {self.seuil_approbation} MAD'

    @classmethod
    def pour(cls, company):
        """XFLT19 — Paramètre de la société, ou les valeurs par défaut si
        non paramétré. Lecture seule."""
        param = cls.objects.filter(company=company).first()
        if param is not None:
            return param
        return cls(
            company=company,
            seuil_approbation=cls.SEUIL_APPROBATION_DEFAUT,
            ecart_alerte_pct=cls.ECART_ALERTE_PCT_DEFAUT)


# ── XFLT20 — Registre de remise clés / carte / badge / tag Jawaz ───────────────

class RemiseAccessoire(models.Model):
    """Journal de custody des accessoires d'un actif (XFLT20).

    Répond à « qui a les clés du L-4523 ? » : trace chaque remise d'un
    accessoire (clé, double de clé, carte carburant, tag Jawaz, badge) à un
    conducteur, avec date de remise et — une fois restitué — date de retour.
    Le détenteur COURANT d'un accessoire est celui dont la ligne la plus
    récente n'a pas de ``date_retour`` (voir ``services.detenteurs_courants``).

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête). L'actif et le conducteur liés doivent appartenir à la MÊME
    société (validé dans ``clean``).
    """

    class Type(models.TextChoices):
        CLE = 'cle', 'Clé'
        DOUBLE_CLE = 'double_cle', 'Double de clé'
        CARTE_CARBURANT = 'carte_carburant', 'Carte carburant'
        TAG_JAWAZ = 'tag_jawaz', 'Tag Jawaz'
        BADGE = 'badge', 'Badge'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_remises_accessoire',
        verbose_name='Société',
    )
    actif_flotte = models.ForeignKey(
        'ActifFlotte',
        on_delete=models.CASCADE,
        related_name='flotte_remises_accessoire',
        verbose_name='Actif (véhicule ou engin)',
    )
    # 'carte_carburant' (15) est le plus long code de type.
    type_accessoire = models.CharField(
        max_length=16, choices=Type.choices, verbose_name='Type')
    conducteur = models.ForeignKey(
        'Conducteur',
        on_delete=models.CASCADE,
        related_name='flotte_remises_accessoire',
        verbose_name='Détenteur',
    )
    date_remise = models.DateField(verbose_name='Date de remise')
    date_retour = models.DateField(
        null=True, blank=True, verbose_name='Date de retour')
    commentaire = models.TextField(blank=True, verbose_name='Commentaire')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Remise d'accessoire"
        verbose_name_plural = "Remises d'accessoire"
        ordering = ['-date_remise', '-id']
        indexes = [
            models.Index(
                fields=['company', 'actif_flotte'],
                name='flotte_rem_co_actif_idx',
            ),
            models.Index(
                fields=['company', 'conducteur'],
                name='flotte_rem_co_cond_idx',
            ),
        ]

    def clean(self):
        """Valide l'appartenance société de l'actif et du conducteur liés,
        et la cohérence des dates."""
        if self.actif_flotte_id is not None \
                and self.actif_flotte.company_id != self.company_id:
            raise ValidationError(
                "L'actif n'appartient pas à la même société.")
        if self.conducteur_id is not None \
                and self.conducteur.company_id != self.company_id:
            raise ValidationError(
                "Le conducteur n'appartient pas à la même société.")
        if self.date_remise is not None and self.date_retour is not None \
                and self.date_retour < self.date_remise:
            raise ValidationError(
                "La date de retour ne peut pas précéder la remise.")

    def __str__(self):
        return (f'{self.get_type_accessoire_display()} — '
                f'{self.actif_flotte} → {self.conducteur}')


# ── XFLT21 — Journal d'audit flotte ─────────────────────────────────────────────

class ActiviteFlotte(models.Model):
    """Historique immuable des changements sur véhicule/affectation/statut
    (XFLT21).

    Modèle maison sur le principe du chatter CRM (``crm.LeadActivity`` COMME
    RÉFÉRENCE DE CONCEPTION — jamais importé, aucun couplage cross-app) :
    une entrée par changement RÉEL (ancien→nouveau), alimentée dans
    ``perform_update`` des viewsets concernés (``VehiculeViewSet``,
    ``AffectationConducteurViewSet``) — utilisateur et société TOUJOURS
    posés côté serveur. Immuable : aucune suppression/édition possible
    (lecture + création seules, jamais d'update/delete depuis l'API).

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête).
    """

    class TypeObjet(models.TextChoices):
        VEHICULE = 'vehicule', 'Véhicule'
        AFFECTATION = 'affectation', 'Affectation conducteur'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_activites',
        verbose_name='Société',
    )
    type_objet = models.CharField(
        max_length=11, choices=TypeObjet.choices, verbose_name="Type d'objet")
    objet_id = models.PositiveIntegerField(verbose_name="ID de l'objet")
    # Rattachement direct au véhicule pour lister l'historique sur la fiche
    # véhicule même quand type_objet='affectation' (l'affectation porte un
    # véhicule) — évite un JOIN cross-modèle pour l'action ``historique/``.
    vehicule = models.ForeignKey(
        'Vehicule',
        on_delete=models.CASCADE,
        related_name='flotte_activites',
        verbose_name='Véhicule',
    )
    champ = models.CharField(max_length=60, verbose_name='Champ modifié')
    ancienne_valeur = models.CharField(
        max_length=255, blank=True, verbose_name='Ancienne valeur')
    nouvelle_valeur = models.CharField(
        max_length=255, blank=True, verbose_name='Nouvelle valeur')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='flotte_activites',
        verbose_name='Utilisateur',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Activité flotte (journal d'audit)"
        verbose_name_plural = "Activités flotte (journal d'audit)"
        ordering = ['-date_creation', '-id']
        indexes = [
            models.Index(
                fields=['company', 'vehicule'],
                name='flotte_act_co_veh_idx',
            ),
            models.Index(
                fields=['company', 'type_objet', 'objet_id'],
                name='flotte_act_co_type_obj_idx',
            ),
        ]

    def __str__(self):
        return (f'{self.get_type_objet_display()} #{self.objet_id} — '
                f'{self.champ} : {self.ancienne_valeur} → {self.nouvelle_valeur}')


# ── XFLT24 — Géofencing sur les données télématiques ────────────────────────────

class ZoneGeographique(models.Model):
    """Zone géographique circulaire de géofencing (XFLT24).

    Cercle simple (centre lat/lng + rayon en mètres — PAS de PostGIS) évalué
    a posteriori contre les ``ReleveTelematique``/``TrajetTelematique`` déjà
    ingérés (FLOTTE27/28) : détection d'entrée/sortie de zone et de mouvement
    hors plage horaire autorisée. Purement LOCAL sur des données existantes —
    aucune dépendance nouvelle, no-op si la télématique est inactive (gate
    FLOTTE27 respectée par ``services.evaluer_geofencing``).

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête).
    """

    class TypeZone(models.TextChoices):
        DEPOT = 'depot', 'Dépôt'
        CHANTIER = 'chantier', 'Chantier'
        INTERDITE = 'interdite', 'Zone interdite'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_zones_geographiques',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=120, verbose_name='Nom de la zone')
    type_zone = models.CharField(
        max_length=10, choices=TypeZone.choices, default=TypeZone.DEPOT,
        verbose_name='Type de zone')
    centre_lat = models.DecimalField(
        max_digits=9, decimal_places=6, verbose_name='Latitude du centre')
    centre_lng = models.DecimalField(
        max_digits=9, decimal_places=6, verbose_name='Longitude du centre')
    rayon_metres = models.PositiveIntegerField(
        verbose_name='Rayon (mètres)')
    # Plage horaire autorisée (optionnelle) : hors de cette plage, un
    # mouvement détecté dans la zone déclenche une alerte. Vide = aucune
    # contrainte horaire (seule l'appartenance interdite/zone compte).
    heure_debut_autorisee = models.TimeField(
        null=True, blank=True, verbose_name='Heure de début autorisée')
    heure_fin_autorisee = models.TimeField(
        null=True, blank=True, verbose_name='Heure de fin autorisée')
    actif = models.BooleanField(default=True, verbose_name='Active')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Zone géographique'
        verbose_name_plural = 'Zones géographiques'
        ordering = ['nom']
        indexes = [
            models.Index(
                fields=['company', 'type_zone'],
                name='flotte_zone_co_type_idx',
            ),
            models.Index(
                fields=['company', 'actif'],
                name='flotte_zone_co_act_idx',
            ),
        ]

    def clean(self):
        """Valide le rayon (> 0) et la cohérence de la plage horaire (fin >
        début si les deux sont renseignées)."""
        if self.rayon_metres is not None and self.rayon_metres <= 0:
            raise ValidationError(
                'Le rayon doit être strictement positif.')
        if self.heure_debut_autorisee is not None \
                and self.heure_fin_autorisee is not None \
                and self.heure_fin_autorisee <= self.heure_debut_autorisee:
            raise ValidationError(
                "L'heure de fin autorisée doit être postérieure à l'heure "
                'de début.')

    def __str__(self):
        return f'{self.nom} ({self.get_type_zone_display()})'


# ── XFLT28 — Rappels constructeur (recall) ──────────────────────────────────────

class RappelConstructeur(models.Model):
    """Rappel constructeur (recall) touchant un ou plusieurs VIN du parc
    (XFLT28).

    Saisi une fois (référence de campagne, constructeur, description, liste
    des VIN concernés) puis RAPPROCHÉ automatiquement contre
    ``Vehicule.vin`` (XFLT4) : le service ``services.rapprocher_rappel``
    crée un ``SignalementVehicule`` (XFLT5) PAR véhicule du parc touché,
    tous groupables en cette campagne pour un suivi de résolution unifié.

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête).
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='flotte_rappels_constructeur',
        verbose_name='Société',
    )
    reference_campagne = models.CharField(
        max_length=80, verbose_name='Référence de campagne')
    constructeur = models.CharField(
        max_length=120, blank=True, verbose_name='Constructeur')
    description = models.TextField(blank=True, verbose_name='Description')
    # Liste des VIN concernés par la campagne (saisie constructeur — peut
    # dépasser largement le parc de la société ; le rapprochement ne crée un
    # signalement QUE pour les VIN qui matchent un véhicule de la société).
    vin_concernes = models.JSONField(
        default=list, blank=True, verbose_name='VIN concernés')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Rappel constructeur'
        verbose_name_plural = 'Rappels constructeur'
        ordering = ['-date_creation', '-id']
        indexes = [
            models.Index(
                fields=['company', 'reference_campagne'],
                name='flotte_rappel_co_ref_idx',
            ),
        ]

    def __str__(self):
        return f'Rappel {self.reference_campagne} — {self.constructeur}'
