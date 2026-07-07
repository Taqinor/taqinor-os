"""Modèles du module Appels d'offres (``apps.ao``).

Marchés publics/privés (RFP) — différenciateur sans équivalent Odoo direct.
Ces modèles ont d'abord vécu dans ``apps.compta`` (FG222–227) ; ODX11 les a
SORTIS de compta en préservant à l'IDENTIQUE les tables physiques existantes
(``db_table = 'compta_<model>'``) via des migrations
``SeparateDatabaseAndState`` (state-only, aucun SQL, aucune donnée déplacée).
Un shim de ré-export subsiste dans ``apps/compta/models.py`` pour le
code/migrations historiques.

Frontière cross-app (CLAUDE.md) : ``ao`` ne lit crm/ventes QUE via leurs
``selectors.py``/``services.py`` ou par référence opaque (id/texte) — jamais
d'import de leurs ``models`` (le lead est référencé par ``lead_id``). Tout est
multi-société : chaque modèle porte un FK ``company`` posé côté serveur (jamais
lu du corps de requête).
"""
from decimal import Decimal

from django.db import models


# ── FG222 — Gestion des appels d'offres (public/privé) ─────────────────────

class AppelOffre(models.Model):
    """Objet appel d'offres (AO) public/privé (FG222).

    Acheteur, deadline, lot, caution… L'industriel/agricole passe par des
    marchés. Lié au lead par id (jamais un FK cross-app vers crm). Sert de
    racine au BOQ (FG223), aux cautions (FG224), au dossier (FG225), à
    l'échéancier (FG226) et à l'analyse résultat (FG227).
    """
    class TypeMarche(models.TextChoices):
        PUBLIC = 'public', 'Public'
        PRIVE = 'prive', 'Privé'

    class Statut(models.TextChoices):
        IDENTIFIE = 'identifie', 'Identifié'
        EN_PREPARATION = 'en_preparation', 'En préparation'
        DEPOSE = 'depose', 'Déposé'
        GAGNE = 'gagne', 'Gagné'
        PERDU = 'perdu', 'Perdu'
        ABANDONNE = 'abandonne', 'Abandonné'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='appels_offres',
        verbose_name='Société',
    )
    reference = models.CharField(
        max_length=120, verbose_name="Référence de l'AO")
    objet = models.CharField(max_length=255, verbose_name='Objet')
    acheteur = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Acheteur')
    type_marche = models.CharField(
        max_length=8, choices=TypeMarche.choices, default=TypeMarche.PUBLIC,
        verbose_name='Type de marché')
    lot = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Lot')
    date_limite = models.DateField(
        null=True, blank=True, verbose_name='Date limite de remise des plis')
    montant_estime = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Montant estimé (MAD)')
    caution_provisoire = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Caution provisoire (MAD)')
    statut = models.CharField(
        max_length=16, choices=Statut.choices, default=Statut.IDENTIFIE,
        verbose_name='Statut')
    lead_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Id du lead lié')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Appel d'offres"
        verbose_name_plural = "Appels d'offres"
        db_table = 'compta_appeloffre'
        ordering = ['-date_creation']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                name='uniq_appel_offre_reference',
            ),
        ]

    def __str__(self):
        return f'{self.reference} — {self.objet}'


# ── FG223 — Bordereau des prix (BOQ) d'appel d'offres ──────────────────────

class BordereauPrix(models.Model):
    """Bordereau des prix (BOQ) d'un AO (FG223), séparé du devis client.

    Chiffrage interne ligne à ligne de l'AO. Distinct du devis : sert au
    montage de l'offre de prix. ``total_ht`` agrège les lignes.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='bordereaux_prix',
        verbose_name='Société',
    )
    appel_offre = models.ForeignKey(
        AppelOffre,
        on_delete=models.CASCADE,
        related_name='bordereaux',
        verbose_name="Appel d'offres",
    )
    intitule = models.CharField(
        max_length=200, default='Bordereau des prix', verbose_name='Intitulé')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Bordereau des prix (BOQ)'
        verbose_name_plural = 'Bordereaux des prix (BOQ)'
        db_table = 'compta_bordereauprix'
        ordering = ['-date_creation']

    def __str__(self):
        return f'BOQ {self.intitule} ({self.appel_offre.reference})'

    @property
    def total_ht(self):
        total = Decimal('0.00')
        for ligne in self.lignes.all():
            total += ligne.montant_ht
        return total


class LigneBordereau(models.Model):
    """Une ligne chiffrée d'un BOQ (FG223)."""
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='lignes_bordereau',
        verbose_name='Société',
    )
    bordereau = models.ForeignKey(
        BordereauPrix,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='Bordereau',
    )
    numero = models.PositiveIntegerField(default=1, verbose_name='N° ligne')
    designation = models.CharField(max_length=255, verbose_name='Désignation')
    unite = models.CharField(
        max_length=20, blank=True, default='U', verbose_name='Unité')
    quantite = models.DecimalField(
        max_digits=12, decimal_places=3, default=Decimal('0.000'),
        verbose_name='Quantité')
    prix_unitaire = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Prix unitaire HT (MAD)')

    class Meta:
        verbose_name = 'Ligne de bordereau'
        verbose_name_plural = 'Lignes de bordereau'
        db_table = 'compta_lignebordereau'
        ordering = ['bordereau', 'numero']

    def __str__(self):
        return f'{self.numero}. {self.designation}'

    @property
    def montant_ht(self):
        return (self.quantite or Decimal('0')) * (
            self.prix_unitaire or Decimal('0'))


# ── FG224 — Suivi des cautions & garanties de soumission ───────────────────

class CautionSoumission(models.Model):
    """Caution/garantie de soumission d'un AO (FG224).

    Provisoire ou définitive : montant, banque, échéance, restitution. Distincte
    de ``CautionBancaire`` (cautions sur marché en cours) — celle-ci suit le
    cycle soumission AO.
    """
    class TypeCaution(models.TextChoices):
        PROVISOIRE = 'provisoire', 'Provisoire'
        DEFINITIVE = 'definitive', 'Définitive'
        RETENUE_GARANTIE = 'retenue_garantie', 'Retenue de garantie'

    class Statut(models.TextChoices):
        CONSTITUEE = 'constituee', 'Constituée'
        RESTITUEE = 'restituee', 'Restituée'
        APPELEE = 'appelee', 'Appelée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='cautions_soumission',
        verbose_name='Société',
    )
    appel_offre = models.ForeignKey(
        AppelOffre,
        on_delete=models.CASCADE,
        related_name='cautions',
        verbose_name="Appel d'offres",
    )
    type_caution = models.CharField(
        max_length=16, choices=TypeCaution.choices,
        default=TypeCaution.PROVISOIRE, verbose_name='Type de caution')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Montant (MAD)')
    banque = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Banque')
    date_emission = models.DateField(
        null=True, blank=True, verbose_name="Date d'émission")
    date_echeance = models.DateField(
        null=True, blank=True, verbose_name="Date d'échéance")
    date_restitution = models.DateField(
        null=True, blank=True, verbose_name='Date de restitution')
    statut = models.CharField(
        max_length=16, choices=Statut.choices, default=Statut.CONSTITUEE,
        verbose_name='Statut')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Caution de soumission'
        verbose_name_plural = 'Cautions de soumission'
        db_table = 'compta_cautionsoumission'
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.type_caution} {self.montant} MAD ({self.banque})'


# ── FG225 — Dossier de soumission (pièces administratives) ─────────────────

class DossierSoumission(models.Model):
    """Dossier de soumission d'un AO (FG225) : checklist + dépôt des pièces.

    Attestations fiscale/CNSS, RC, déclaration sur l'honneur… Le dossier
    regroupe les pièces (``PieceSoumission``) ; ``complet`` est dérivé du
    pointage des pièces obligatoires.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='dossiers_soumission',
        verbose_name='Société',
    )
    appel_offre = models.OneToOneField(
        AppelOffre,
        on_delete=models.CASCADE,
        related_name='dossier',
        verbose_name="Appel d'offres",
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Dossier de soumission'
        verbose_name_plural = 'Dossiers de soumission'
        db_table = 'compta_dossiersoumission'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Dossier {self.appel_offre.reference}'

    @property
    def complet(self):
        """Vrai si toutes les pièces obligatoires sont fournies."""
        obligatoires = self.pieces.filter(obligatoire=True)
        if not obligatoires.exists():
            return False
        return not obligatoires.filter(fournie=False).exists()


class PieceSoumission(models.Model):
    """Une pièce administrative d'un dossier de soumission (FG225)."""
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='pieces_soumission',
        verbose_name='Société',
    )
    dossier = models.ForeignKey(
        DossierSoumission,
        on_delete=models.CASCADE,
        related_name='pieces',
        verbose_name='Dossier',
    )
    libelle = models.CharField(max_length=200, verbose_name='Libellé')
    obligatoire = models.BooleanField(
        default=True, verbose_name='Obligatoire')
    fournie = models.BooleanField(default=False, verbose_name='Fournie')
    fichier = models.FileField(
        upload_to='compta/soumissions/', null=True, blank=True,
        verbose_name='Document')
    date_depot = models.DateField(
        null=True, blank=True, verbose_name='Date de dépôt')

    class Meta:
        verbose_name = 'Pièce de soumission'
        verbose_name_plural = 'Pièces de soumission'
        db_table = 'compta_piecesoumission'
        ordering = ['dossier', 'libelle']

    def __str__(self):
        etat = 'OK' if self.fournie else 'manquante'
        return f'{self.libelle} ({etat})'


# ── FG226 — Échéancier & alertes de deadline d'AO ──────────────────────────

class EcheanceAO(models.Model):
    """Date clé d'un AO avec rappel (FG226).

    Remise des plis, ouverture, validité de l'offre… ``rappel_jours`` avant
    l'échéance déclenche une alerte (calcul des échéances dues dans le service ;
    aucun envoi réseau ici).
    """
    class TypeEcheance(models.TextChoices):
        REMISE_PLIS = 'remise_plis', 'Remise des plis'
        OUVERTURE = 'ouverture', 'Ouverture des plis'
        VALIDITE = 'validite', 'Fin de validité de l\'offre'
        AUTRE = 'autre', 'Autre date clé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='echeances_ao',
        verbose_name='Société',
    )
    appel_offre = models.ForeignKey(
        AppelOffre,
        on_delete=models.CASCADE,
        related_name='echeances',
        verbose_name="Appel d'offres",
    )
    type_echeance = models.CharField(
        max_length=12, choices=TypeEcheance.choices,
        default=TypeEcheance.AUTRE, verbose_name="Type d'échéance")
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    date_echeance = models.DateField(verbose_name="Date d'échéance")
    rappel_jours = models.PositiveIntegerField(
        default=3, verbose_name='Rappel (jours avant)')
    traitee = models.BooleanField(default=False, verbose_name='Traitée')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Échéance d'AO"
        verbose_name_plural = "Échéances d'AO"
        db_table = 'compta_echeanceao'
        ordering = ['date_echeance']

    def __str__(self):
        return f'{self.type_echeance} {self.date_echeance}'


# ── FG227 — Analyse gagné/perdu des appels d'offres ────────────────────────

class ResultatAO(models.Model):
    """Résultat d'un AO pour l'analyse gagné/perdu (FG227).

    Attributaire, prix gagnant, écart vs notre offre. Agrégé pour le taux de
    réussite (calcul dans le service/viewset). Un seul résultat par AO.
    """
    class Issue(models.TextChoices):
        GAGNE = 'gagne', 'Gagné'
        PERDU = 'perdu', 'Perdu'
        INFRUCTUEUX = 'infructueux', 'Infructueux'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='resultats_ao',
        verbose_name='Société',
    )
    appel_offre = models.OneToOneField(
        AppelOffre,
        on_delete=models.CASCADE,
        related_name='resultat',
        verbose_name="Appel d'offres",
    )
    issue = models.CharField(
        max_length=12, choices=Issue.choices, default=Issue.PERDU,
        verbose_name='Issue')
    attributaire = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Attributaire')
    notre_prix = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Notre prix (MAD)')
    prix_gagnant = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Prix gagnant (MAD)')
    motif = models.TextField(
        blank=True, default='', verbose_name='Motif / commentaire')
    date_resultat = models.DateField(
        null=True, blank=True, verbose_name='Date du résultat')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Résultat d'AO"
        verbose_name_plural = "Résultats d'AO"
        db_table = 'compta_resultatao'
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.appel_offre.reference} — {self.issue}'

    @property
    def ecart_prix(self):
        """Écart entre notre prix et le prix gagnant (MAD)."""
        if not self.prix_gagnant:
            return None
        return (self.notre_prix or Decimal('0.00')) - self.prix_gagnant
