"""Modèles de l'app santé (``apps.sante``) — cabinets/cliniques.

Vertical NTSAN : gestion administrative d'un cabinet/clinique (agenda
multi-praticiens, admission, nomenclature d'actes, facturation patient/tiers
payant). Multi-société : chaque modèle hérite de ``core.models.TenantModel``
(FK ``company`` posée côté serveur, jamais lue du corps de requête).

DONNÉES SENSIBLES (CNDP/(DECISION), note founder du groupe NTSAN) : ce module
ne stocke QUE des données ADMINISTRATIVES (identité, RDV, facturation) —
explicitement AUCUNE donnée médicale clinique. Toute donnée personnelle de
santé future devra suivre le pattern YHARD (chiffrement au repos) + une
(DECISION) explicite du founder avant d'être ajoutée.
"""
from django.conf import settings
from django.db import models

from core.models import TenantModel


class Praticien(TenantModel):
    """NTSAN1 — praticien exerçant dans le cabinet/clinique."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sante_praticiens',
        verbose_name='Utilisateur lié',
    )
    nom = models.CharField(max_length=255, verbose_name='Nom')
    specialite = models.CharField(
        max_length=150, blank=True, default='', verbose_name='Spécialité')
    numero_ordre = models.CharField(
        max_length=50, blank=True, default='', verbose_name="Numéro d'ordre")
    couleur_agenda = models.CharField(
        max_length=20, blank=True, default='#2563eb',
        verbose_name='Couleur agenda')
    actif = models.BooleanField(default=True, verbose_name='Actif')

    class Meta:
        verbose_name = 'Praticien'
        verbose_name_plural = 'Praticiens'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class Salle(TenantModel):
    """NTSAN2 — salle/ressource (consultation, bloc, imagerie, labo).

    Réservation croisée praticien+salle dans l'agenda : une salle ne peut pas
    être double-réservée sur le même créneau. La contrainte applicative vit
    dans ``services.py`` (``verifier_disponibilite_salle``) et n'est
    exerçable qu'une fois le modèle ``RendezVous`` posé (NTSAN4) — c'est
    l'unique consommateur d'un créneau de salle ; elle est implémentée et
    testée dans la même passe que NTSAN4.
    """

    class Type(models.TextChoices):
        CONSULTATION = 'consultation', 'Consultation'
        BLOC = 'bloc', 'Bloc opératoire'
        IMAGERIE = 'imagerie', 'Imagerie'
        LABO = 'labo', 'Laboratoire'

    nom = models.CharField(max_length=150, verbose_name='Nom')
    type = models.CharField(
        max_length=15, choices=Type.choices, default=Type.CONSULTATION,
        verbose_name='Type')
    capacite = models.PositiveIntegerField(default=1, verbose_name='Capacité')
    equipements = models.TextField(
        blank=True, default='', verbose_name='Équipements')

    class Meta:
        verbose_name = 'Salle'
        verbose_name_plural = 'Salles'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class Patient(TenantModel):
    """NTSAN3 — dossier ADMINISTRATIF patient (aucune donnée médicale
    clinique). ``client`` référence ``crm.Client`` par FK À CHAÎNE (jamais
    d'import direct de ``apps.crm.models``) ; la résolution/rattachement se
    fait via ``services.resoudre_client_pour_patient`` (import local par
    l'appelant). ``convention``/``numero_affiliation`` (NTSAN9) permettent un
    tarif par mutuelle/CNOPS/CNSS via ``GrilleTarifaire`` (NTSAN8)."""

    class Sexe(models.TextChoices):
        M = 'M', 'Masculin'
        F = 'F', 'Féminin'

    nom = models.CharField(max_length=255, verbose_name='Nom')
    prenom = models.CharField(max_length=255, blank=True, default='', verbose_name='Prénom')
    cin = models.CharField(max_length=30, blank=True, default='', verbose_name='CIN')
    date_naissance = models.DateField(
        null=True, blank=True, verbose_name='Date de naissance')
    sexe = models.CharField(
        max_length=1, choices=Sexe.choices, blank=True, default='',
        verbose_name='Sexe')
    telephone = models.CharField(max_length=20, blank=True, default='', verbose_name='Téléphone')
    whatsapp = models.CharField(max_length=20, blank=True, default='', verbose_name='WhatsApp')
    email = models.EmailField(blank=True, default='', verbose_name='Email')
    adresse = models.TextField(blank=True, default='', verbose_name='Adresse')
    numero_dossier = models.CharField(
        max_length=30, blank=True, default='', db_index=True,
        verbose_name='Numéro de dossier')
    contact_urgence = models.CharField(
        max_length=255, blank=True, default='', verbose_name="Contact d'urgence")
    # NTSAN3 — jamais d'import direct de crm.models : FK par chaîne.
    client = models.ForeignKey(
        'crm.Client', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='patients_sante', verbose_name='Client CRM lié')
    # NTSAN9 — mutuelle/CNOPS/CNSS/cash par défaut du patient.
    convention = models.ForeignKey(
        'Convention', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='patients', verbose_name='Convention')
    numero_affiliation = models.CharField(
        max_length=50, blank=True, default='', verbose_name="Numéro d'affiliation")

    class Meta:
        verbose_name = 'Patient'
        verbose_name_plural = 'Patients'
        ordering = ['nom', 'prenom']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'numero_dossier'],
                condition=~models.Q(numero_dossier=''),
                name='sante_patient_unique_dossier_par_societe'),
        ]

    def __str__(self):
        return f"{self.nom} {self.prenom}".strip()


class RendezVous(TenantModel):
    """NTSAN4 — agenda multi-praticiens. La détection de chevauchement
    (praticien OU salle) est appliquée côté serveur dans
    ``services.verifier_chevauchement_rdv`` (appelée par le viewset), pas ici
    (garde de service, pas de contrainte DB — les créneaux se chevauchent sur
    des intervalles calculés, pas une simple égalité de colonnes)."""

    class Statut(models.TextChoices):
        PLANIFIE = 'planifie', 'Planifié'
        CONFIRME = 'confirme', 'Confirmé'
        ARRIVE = 'arrive', 'Arrivé'
        EN_COURS = 'en_cours', 'En cours'
        TERMINE = 'termine', 'Terminé'
        ANNULE = 'annule', 'Annulé'
        ABSENT = 'absent', 'Absent'

    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name='rendez_vous',
        verbose_name='Patient')
    praticien = models.ForeignKey(
        Praticien, on_delete=models.CASCADE, related_name='rendez_vous',
        verbose_name='Praticien')
    salle = models.ForeignKey(
        Salle, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='rendez_vous', verbose_name='Salle')
    date_heure_debut = models.DateTimeField(verbose_name='Date et heure de début')
    duree_min = models.PositiveIntegerField(default=30, verbose_name='Durée (min)')
    type_acte = models.CharField(
        max_length=255, blank=True, default='', verbose_name="Type d'acte")
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.PLANIFIE,
        verbose_name='Statut')
    motif_court = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Motif')
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='sante_rdv_crees',
        verbose_name='Créé par')

    class Meta:
        verbose_name = 'Rendez-vous'
        verbose_name_plural = 'Rendez-vous'
        ordering = ['date_heure_debut']
        indexes = [
            models.Index(
                fields=['praticien', 'date_heure_debut'],
                name='sante_rdv_praticien_debut_idx'),
            models.Index(
                fields=['salle', 'date_heure_debut'],
                name='sante_rdv_salle_debut_idx'),
        ]

    def __str__(self):
        return f'{self.patient_id} @ {self.date_heure_debut}'


class Admission(TenantModel):
    """NTSAN6 — parcours administratif patient (admission → actes → sortie).

    La clôture n'est autorisée que si tous les ``ActeRealise`` rattachés sont
    facturés ou explicitement marqués non-facturables — la garde vit dans
    ``services.cloturer_admission`` et n'est COMPLÈTE qu'une fois
    ``ActeRealise`` posé (NTSAN10) ; avant cela, une admission sans acte se
    clôture toujours (garde vacuously vraie)."""

    class Type(models.TextChoices):
        CONSULTATION = 'consultation', 'Consultation'
        HOSPITALISATION = 'hospitalisation', 'Hospitalisation'
        ACTE_TECHNIQUE = 'acte_technique', 'Acte technique'

    class Statut(models.TextChoices):
        EN_COURS = 'en_cours', 'En cours'
        CLOTUREE = 'cloturee', 'Clôturée'

    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name='admissions',
        verbose_name='Patient')
    rdv = models.ForeignKey(
        RendezVous, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='admissions', verbose_name='Rendez-vous')
    praticien = models.ForeignKey(
        Praticien, on_delete=models.CASCADE, related_name='admissions',
        verbose_name='Praticien')
    date_admission = models.DateTimeField(verbose_name="Date d'admission")
    date_sortie = models.DateTimeField(
        null=True, blank=True, verbose_name='Date de sortie')
    type = models.CharField(
        max_length=20, choices=Type.choices, default=Type.CONSULTATION,
        verbose_name='Type')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.EN_COURS,
        verbose_name='Statut')

    class Meta:
        verbose_name = 'Admission'
        verbose_name_plural = 'Admissions'
        ordering = ['-date_admission']

    def __str__(self):
        return f'Admission {self.patient_id} ({self.date_admission:%Y-%m-%d})'


class ActeMedical(TenantModel):
    """NTSAN7 — nomenclature des actes (paramétrage clinique).

    Pas de table NGAP officielle importée en v1 : ``code_ngap``/
    ``cotation_lettre_cle`` sont du texte libre paramétrable par la clinique.
    Soft-disable uniquement (``actif``) : un acte déjà référencé par
    ``GrilleTarifaire``/``ActeRealise`` ne doit JAMAIS être supprimé
    physiquement — la garde de suppression est complétée dans la même passe
    que NTSAN10 (une fois ``ActeRealise`` posé, seul vrai « acte déjà
    facturé »)."""

    code_ngap = models.CharField(
        max_length=30, blank=True, default='', verbose_name='Code NGAP')
    libelle = models.CharField(max_length=255, verbose_name='Libellé')
    categorie = models.CharField(
        max_length=100, blank=True, default='', verbose_name='Catégorie')
    tarif_base_ttc = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Tarif de base TTC')
    cotation_lettre_cle = models.CharField(
        max_length=20, blank=True, default='',
        verbose_name='Cotation (lettre clé)')
    actif = models.BooleanField(default=True, verbose_name='Actif')

    class Meta:
        verbose_name = 'Acte médical'
        verbose_name_plural = 'Actes médicaux'
        ordering = ['libelle']

    def __str__(self):
        return self.libelle


class Convention(TenantModel):
    """NTSAN9 — mutuelle/CNOPS/CNSS/cash, paramétrable par clinique (jamais
    codée en dur)."""

    class Type(models.TextChoices):
        CNOPS = 'cnops', 'CNOPS'
        CNSS = 'cnss', 'CNSS'
        MUTUELLE_PRIVEE = 'mutuelle_privee', 'Mutuelle privée'
        CASH = 'cash', 'Cash'
        AUTRE = 'autre', 'Autre'

    nom = models.CharField(max_length=150, verbose_name='Nom')
    type = models.CharField(
        max_length=20, choices=Type.choices, default=Type.AUTRE,
        verbose_name='Type')
    taux_tiers_payant_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name='Taux tiers payant par défaut (%)')
    contact = models.CharField(max_length=255, blank=True, default='', verbose_name='Contact')
    actif = models.BooleanField(default=True, verbose_name='Actif')

    class Meta:
        verbose_name = 'Convention'
        verbose_name_plural = 'Conventions'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class GrilleTarifaire(TenantModel):
    """NTSAN8 — tarif par convention (mutuelle/CNOPS/CNSS), différent du
    ``tarif_base_ttc`` de l'acte. La facturation (NTSAN13) lit cette grille
    pour la convention du patient si une ligne existe, sinon retombe sur
    ``ActeMedical.tarif_base_ttc`` (voir ``selectors.tarif_applicable``)."""

    convention = models.ForeignKey(
        Convention, on_delete=models.CASCADE,
        related_name='grilles_tarifaires', verbose_name='Convention')
    acte = models.ForeignKey(
        ActeMedical, on_delete=models.CASCADE,
        related_name='grilles_tarifaires', verbose_name='Acte')
    tarif_convention_ttc = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Tarif convention TTC')
    taux_prise_charge_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name='Taux de prise en charge (%)')

    class Meta:
        verbose_name = 'Grille tarifaire'
        verbose_name_plural = 'Grilles tarifaires'
        ordering = ['convention', 'acte']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'convention', 'acte'],
                name='sante_grille_unique_convention_acte'),
        ]

    def __str__(self):
        return f'{self.convention_id} / {self.acte_id}'


class ActeRealise(TenantModel):
    """NTSAN10 — acte réalisé. ``tarif_applique_ttc`` est SNAPSHOTTÉ à la
    réalisation (jamais recalculé rétroactivement si ``GrilleTarifaire``
    change ensuite — test de non-régression dédié).

    ``facturable=False`` (NTSAN6) marque explicitement un acte comme non
    facturable, permettant la clôture de l'admission sans facturation.
    ``facture_sante`` (posé par NTSAN13, pas encore ici) référencera la
    facture qui a réglé cet acte."""

    admission = models.ForeignKey(
        Admission, on_delete=models.CASCADE, related_name='actes_realises',
        verbose_name='Admission')
    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name='actes_realises',
        verbose_name='Patient')
    praticien = models.ForeignKey(
        Praticien, on_delete=models.CASCADE, related_name='actes_realises',
        verbose_name='Praticien')
    acte = models.ForeignKey(
        ActeMedical, on_delete=models.PROTECT, related_name='realisations',
        verbose_name='Acte')
    date_realisation = models.DateTimeField(verbose_name='Date de réalisation')
    quantite = models.PositiveIntegerField(default=1, verbose_name='Quantité')
    tarif_applique_ttc = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='Tarif appliqué TTC')
    facturable = models.BooleanField(
        default=True, verbose_name='Facturable',
        help_text="Décoché : l'acte est explicitement marqué non-facturable "
                  "(n'empêche pas la clôture de l'admission).")
    # NTSAN12 — si posée, une prise en charge refusée/expirée fait basculer
    # cet acte en reste-à-charge patient total (services.verifier_prise_en_charge).
    prise_en_charge = models.ForeignKey(
        'PriseEnCharge', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='actes_realises', verbose_name='Prise en charge')
    # NTSAN13 — facture qui a réglé cet acte (lignes = actes réalisés). Une
    # fois posée, l'admission considère cet acte comme facturé (garde de
    # clôture NTSAN6).
    facture_sante = models.ForeignKey(
        'FactureSante', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lignes_actes', verbose_name='Facture santé')

    class Meta:
        verbose_name = 'Acte réalisé'
        verbose_name_plural = 'Actes réalisés'
        ordering = ['-date_realisation']

    def __str__(self):
        return f'{self.acte_id} @ {self.date_realisation}'


class PriseEnCharge(TenantModel):
    """NTSAN12 — prise en charge / entente préalable auprès d'une convention.

    Une ``ActeRealise`` liée à une prise en charge refusée ou expirée
    bascule automatiquement en reste-à-charge patient total — appliqué par
    ``services.verifier_prise_en_charge`` (appelé à la transition de statut),
    tracé dans l'historique via ``records.Activity``."""

    class Statut(models.TextChoices):
        DEMANDEE = 'demandee', 'Demandée'
        ACCORDEE = 'accordee', 'Accordée'
        REFUSEE = 'refusee', 'Refusée'
        EXPIREE = 'expiree', 'Expirée'

    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name='prises_en_charge',
        verbose_name='Patient')
    convention = models.ForeignKey(
        Convention, on_delete=models.CASCADE, related_name='prises_en_charge',
        verbose_name='Convention')
    admission = models.ForeignKey(
        Admission, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='prises_en_charge', verbose_name='Admission')
    numero_dossier_convention = models.CharField(
        max_length=50, blank=True, default='',
        verbose_name='Numéro de dossier (convention)')
    date_demande = models.DateField(verbose_name='Date de demande')
    date_reponse = models.DateField(
        null=True, blank=True, verbose_name='Date de réponse')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.DEMANDEE,
        verbose_name='Statut')
    montant_accorde = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Montant accordé')
    motif_refus = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Motif de refus')
    date_expiration = models.DateField(
        null=True, blank=True, verbose_name="Date d'expiration")

    class Meta:
        verbose_name = 'Prise en charge'
        verbose_name_plural = 'Prises en charge'
        ordering = ['-date_demande']

    def __str__(self):
        return f'PEC {self.patient_id} / {self.convention_id}'


class FactureSante(TenantModel):
    """NTSAN13 — facturation patient/tiers payant.

    Lignes = ``ActeRealise`` rattachés (via ``ActeRealise.facture_sante``).
    Split tiers payant/patient calculé par
    ``services.calculer_split_facture_sante`` depuis
    ``GrilleTarifaire.taux_prise_charge_pct`` ou
    ``PriseEnCharge.montant_accorde``. Même chaîne Sous-total → Remise →
    Total HT → TVA → Total TTC que les factures ventes existantes — la TVA
    reste à 0 par défaut (actes médicaux généralement exonérés), le champ
    existe pour permettre une TVA le cas échéant, jamais un moteur de calcul
    différent. PDF via le moteur légataire ventes (règle #4 — factures
    gardent leur PDF séparé, jamais ``/proposal``), pas construit dans ce lot
    (NTSAN14)."""

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        EMISE = 'emise', 'Émise'
        PAYEE_PARTIEL = 'payee_partiel', 'Payée partiellement'
        PAYEE = 'payee', 'Payée'
        IMPAYEE = 'impayee', 'Impayée'

    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name='factures_sante',
        verbose_name='Patient')
    admission = models.ForeignKey(
        Admission, on_delete=models.CASCADE, related_name='factures_sante',
        verbose_name='Admission')
    convention = models.ForeignKey(
        Convention, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='factures_sante', verbose_name='Convention')
    sous_total_ttc = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name='Sous-total TTC')
    remise_ttc = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name='Remise TTC')
    taux_tva = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, verbose_name='Taux TVA (%)')
    montant_tva = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name='Montant TVA')
    total_ttc = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name='Total TTC')
    part_tiers_payant_ttc = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Part tiers payant TTC')
    part_patient_ttc = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Part patient TTC (reste à charge)')
    statut = models.CharField(
        max_length=15, choices=Statut.choices, default=Statut.BROUILLON,
        verbose_name='Statut')
    date_emission = models.DateTimeField(
        null=True, blank=True, verbose_name="Date d'émission")

    class Meta:
        verbose_name = 'Facture santé'
        verbose_name_plural = 'Factures santé'
        ordering = ['-id']

    def __str__(self):
        return f'Facture santé {self.patient_id} ({self.total_ttc})'
