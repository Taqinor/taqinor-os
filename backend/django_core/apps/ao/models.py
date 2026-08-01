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

AOF4 — les 8 modèles legacy héritent désormais de ``core.models.TenantModel``
(socle ARC1 : FK ``company`` + ``created_at``/``updated_at``). Chacun REDÉCLARE
``company`` DANS SON CORPS : c'est le motif documenté de préservation du
``related_name`` historique (``appels_offres``, ``lignes_bordereau``,
``cautions_soumission``…) — jamais un renommage d'accesseur. Les ``db_table =
'compta_*'`` restent STRICTEMENT inchangés (migrations
``SeparateDatabaseAndState`` d'ODX11) : la migration ``0002_tenantmodel`` est
purement ADDITIVE (deux horodatages par table) et ne contient AUCUN
``AlterModelTable`` — un renommage de table en production serait irréversible.
``date_creation`` (historique) est CONSERVÉ tel quel : il porte des données
existantes et reste le champ d'ordonnancement.
"""
import math
from datetime import timedelta
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.models import TenantModel

# AOF19 — géométrie PURE (repère local métrique, ordre des axes contractuel).
# Ré-exports : l'implémentation n'existe qu'une fois, dans ``geometrie.py``.
from .geometrie import (  # noqa: F401
    aire_polygone_m2,
    normaliser_orientation,
    perimetre_polygone_m,
    polygone_est_simple,
)


# ── FG222 — Gestion des appels d'offres (public/privé) ─────────────────────

class AppelOffre(TenantModel):
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
        """AOF13 — le cycle réel d'un dossier d'appel d'offres.

        Les SIX valeurs historiques (``identifie``, ``en_preparation``,
        ``depose``, ``gagne``, ``perdu``, ``abandonne``) sont CONSERVÉES à
        l'identique : aucune migration de données, aucune ligne existante ne
        devient invalide. ``en_preparation`` devient l'étape « fourre-tout »
        historique que les six nouvelles valeurs détaillent.
        """
        IDENTIFIE = 'identifie', 'Identifié'
        ANALYSE_CPS = 'analyse_cps', 'Analyse du CPS'
        RELEVE = 'releve', 'Relevé de la toiture'
        ETUDE = 'etude', 'Étude / calepinage'
        CHIFFRAGE = 'chiffrage', 'Chiffrage'
        DOSSIER = 'dossier', 'Montage du dossier'
        PRET_A_DEPOSER = 'pret_a_deposer', 'Prêt à déposer'
        EN_PREPARATION = 'en_preparation', 'En préparation (historique)'
        DEPOSE = 'depose', 'Déposé'
        GAGNE = 'gagne', 'Gagné'
        PERDU = 'perdu', 'Perdu'
        ABANDONNE = 'abandonne', 'Abandonné'

    class ModePassation(models.TextChoices):
        """AOF12 — mode de passation annoncé par l'avis (marchés publics)."""
        APPEL_OUVERT = 'appel_ouvert', "Appel d'offres ouvert"
        APPEL_RESTREINT = 'appel_restreint', "Appel d'offres restreint"
        CONCOURS = 'concours', 'Concours'
        NEGOCIE = 'negocie', 'Marché négocié'
        CONSULTATION = 'consultation', 'Consultation / bon de commande'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: purge multi-tenant — supprimer une societe retire ses dossiers d'AO
        related_name='appels_offres',
        verbose_name='Société',
    )
    reference = models.CharField(
        max_length=120, verbose_name="Référence de l'AO")
    # AOF5 — NOTRE référence (``reference``, générée ``AO-YYYYMM-0001`` par
    # ``core.numbering``) et la référence du marché CÔTÉ ACHETEUR sont deux
    # choses distinctes : les confondre rend impossible de retrouver un dossier
    # à partir de l'avis publié, et fait entrer dans notre séquence un numéro
    # que nous ne contrôlons pas.
    reference_acheteur = models.CharField(
        max_length=120, blank=True, default='',
        verbose_name="Référence du marché (acheteur)")
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

    # ── AOF12 — le projet d'appel d'offres au complet ──────────────────────
    #
    # AUCUN champ de coût, de marge ou de bénéfice ici : l'économie de l'AO
    # vit dans des tables SÉPARÉES derrière ``ao_rentabilite_voir`` (AOF2).
    # Un test d'introspection (``test_projet_ao``) échoue si un tel champ
    # apparaît un jour sur ce modèle — la « simulation de rentabilité » remise
    # au maître d'ouvrage est une pièce CLIENT distincte, sans aucun coût.

    #: Le maître d'ouvrage (celui POUR qui les travaux sont faits) n'est pas
    #: toujours l'acheteur qui publie l'avis (centrale d'achat, délégataire).
    maitre_ouvrage = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name="Maître d'ouvrage")
    #: Raison sociale sous laquelle le dossier est DÉPOSÉ — peut différer de la
    #: société de l'ERP (cas réel : dépôt sous une entité partenaire).
    soumissionnaire = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Soumissionnaire (raison sociale déposante)')
    groupement = models.BooleanField(
        default=False, verbose_name='Dépôt en groupement')
    groupement_membres = models.TextField(
        blank=True, default='',
        verbose_name='Membres du groupement (un par ligne)')

    #: Site des travaux — adresse + point GPS (bornes géographiques validées).
    site_adresse = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Adresse du site')
    site_gps_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        verbose_name='Latitude du site')
    site_gps_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        verbose_name='Longitude du site')

    mode_passation = models.CharField(
        max_length=20, choices=ModePassation.choices,
        default=ModePassation.APPEL_OUVERT, verbose_name='Mode de passation')
    reference_cps = models.CharField(
        max_length=120, blank=True, default='',
        verbose_name='Référence du CPS')

    date_ouverture_plis = models.DateField(
        null=True, blank=True, verbose_name="Date d'ouverture des plis")
    #: Durée de validité de l'offre annoncée par le règlement (75 j au Maroc).
    validite_offre_jours = models.PositiveIntegerField(
        default=75, verbose_name="Validité de l'offre (jours)")
    delai_execution_jours = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Délai d'exécution (jours)")
    #: Nombre d'exemplaires du dossier à remettre (2 par défaut).
    nombre_exemplaires = models.PositiveSmallIntegerField(
        default=2, verbose_name="Nombre d'exemplaires à remettre")
    #: Engagement GLOBAL du projet, en modules posés (somme des bâtiments).
    engagement_modules = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Engagement global (modules)')

    #: Montants de NOTRE offre, dérivés du bordereau (jamais un coût).
    montant_offre_ht = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        verbose_name="Montant de l'offre HT (MAD)")
    montant_offre_ttc = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        verbose_name="Montant de l'offre TTC (MAD)")

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

    #: AOF13 — drapeau d'instance posé par ``services.changer_statut_ao`` pour
    #: autoriser la mutation du statut. Jamais posé ailleurs.
    ATTR_STATUT_AUTORISE = '_statut_change_par_service'

    def save(self, *args, **kwargs):
        """AOF13 — le statut ne se mute QUE par ``services.changer_statut_ao``.

        Sans cette garde, la table de transitions déclarative serait une
        suggestion : n'importe quelle vue pourrait écrire ``ao.statut = 'gagne'``
        et court-circuiter à la fois la validation et les deux événements M6.
        La création reste libre (un dossier peut naître à n'importe quelle
        étape, y compris à l'import d'un historique) ; seule la MODIFICATION
        d'un statut existant est gardée. Un ``queryset.update()`` contourne
        ``save()`` par construction — c'est documenté, jamais un chemin
        applicatif.
        """
        update_fields = kwargs.get('update_fields')
        touche_statut = update_fields is None or 'statut' in update_fields
        autorise = getattr(self, self.ATTR_STATUT_AUTORISE, False)
        if self.pk and touche_statut and not autorise:
            ancien = type(self).objects.filter(pk=self.pk).values_list(
                'statut', flat=True).first()
            if ancien is not None and ancien != self.statut:
                from django.core.exceptions import ValidationError
                raise ValidationError({
                    'statut': (
                        "Le statut d'un appel d'offres ne se change que par le "
                        "service dédié (changer_statut_ao) : la table des "
                        "transitions et les événements de dépôt/attribution en "
                        "dépendent."
                    ),
                })
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.reference} — {self.objet}'

    @property
    def surface_toitures_m2(self):
        """AOF18 — surface totale des toitures du projet, CALCULÉE.

        Jamais recopiée dans une colonne : une valeur figée deviendrait fausse
        dès la première toiture ajoutée, et la note de synthèse la plus lue
        serait alors la plus fausse.
        """
        total = Decimal('0.000')
        for batiment in self.batiments.all():
            total += batiment.surface_toitures_m2
        return total

    @property
    def engagement_modules_batiments(self):
        """AOF18 — somme des engagements en modules DÉCLARÉS par bâtiment.

        À distinguer de ``engagement_modules``, qui porte l'engagement GLOBAL
        annoncé par l'avis : les comparer est précisément l'intérêt (un écart
        signale un bâtiment oublié).
        """
        total = 0
        for batiment in self.batiments.all():
            total += batiment.engagement_modules or 0
        return total

    @property
    def date_fin_validite_offre(self):
        """AOF12 — fin de validité de l'offre, DÉRIVÉE (jamais stockée).

        Court à partir de l'ouverture des plis quand elle est connue, sinon de
        la date limite de remise. ``None`` si aucune des deux n'est saisie —
        une date inventée serait pire qu'une absence de date.
        """
        base = self.date_ouverture_plis or self.date_limite
        if base is None or not self.validite_offre_jours:
            return None
        return base + timedelta(days=self.validite_offre_jours)


# ── AOF14 — Les clauses du CPS deviennent des DONNÉES paramétrables ────────

class ExigenceCPS(TenantModel):
    """Une clause chiffrée du CPS, sous forme de donnée (AOF14).

    Constat marché qui justifie le modèle : le cautionnement DÉFINITIF est un
    TAUX du montant initial (3 % au Maroc) tandis que le PROVISOIRE est un
    MONTANT ABSOLU fixé par le CPS (10 000 / 25 000 / 30 000 / 50 000 DH). Les
    deux sont donc des clauses PARAMÉTRABLES, jamais des constantes du code, et
    le provisoire n'est JAMAIS calculable depuis le montant de l'offre.

    **Aucune exigence d'ASSURANCE ici.** ``NTASS19`` est déjà livré :
    ``apps.assurances.ExigenceAssuranceMarche`` possède les exigences
    d'assurance d'un marché et les rattache à l'AO par sa string-FK
    ``marche_ref`` (l'``id`` de l'``AppelOffre``). On s'y RÉFÈRE, on ne les
    duplique pas — un test d'introspection échoue si un champ d'assurance
    apparaît sur ce modèle.
    """

    class TypeExigence(models.TextChoices):
        RATIO_DC_AC = 'ratio_dc_ac', 'Ratio DC/AC (min–max)'
        PUISSANCE_ONDULEUR_MAX = (
            'puissance_onduleur_max', "Puissance unitaire max d'onduleur")
        CAUTION_PROVISOIRE = (
            'caution_provisoire', 'Caution provisoire (montant absolu)')
        CAUTION_DEFINITIVE_TAUX = (
            'caution_definitive_taux', 'Caution définitive (taux)')
        VALIDITE_OFFRE = 'validite_offre', "Validité de l'offre"
        PENALITE_RETARD = 'penalite_retard', 'Pénalité de retard'
        PIECE_ADMINISTRATIVE = (
            'piece_administrative', 'Pièce administrative exigée')
        REFERENCE_NORMATIVE = 'reference_normative', 'Référence normative'
        AUTRE = 'autre', 'Autre clause'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: purge multi-tenant — les clauses suivent la societe
        related_name='exigences_cps',
        verbose_name='Société',
    )
    appel_offre = models.ForeignKey(
        AppelOffre,
        on_delete=models.CASCADE,  # on_delete: clause fille d'un AO : aucune existence hors de son appel d'offres
        related_name='exigences_cps',
        verbose_name="Appel d'offres",
    )
    code = models.CharField(
        max_length=60, verbose_name='Code de la clause')
    libelle = models.CharField(max_length=255, verbose_name='Libellé')
    type_exigence = models.CharField(
        max_length=24, choices=TypeExigence.choices,
        default=TypeExigence.AUTRE, verbose_name="Type d'exigence")
    #: Valeur principale. ``valeur_max_num`` n'est renseignée QUE pour une
    #: clause d'intervalle (ratio DC/AC 0,75 → 1).
    valeur_num = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True,
        verbose_name='Valeur (numérique)')
    valeur_max_num = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True,
        verbose_name='Valeur maximale (intervalle)')
    unite = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Unité')
    valeur_texte = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Valeur (texte)')
    #: Provenance documentaire : la PIÈCE du DCE et sa page.
    source_piece = models.CharField(
        max_length=120, blank=True, default='CPS',
        verbose_name='Pièce du DCE')
    source_page = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Page')
    bloquant = models.BooleanField(
        default=True, verbose_name='Clause bloquante')
    commentaire = models.TextField(
        blank=True, default='', verbose_name='Commentaire')

    class Meta:
        verbose_name = 'Exigence du CPS'
        verbose_name_plural = 'Exigences du CPS'
        ordering = ['appel_offre', 'code']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'appel_offre', 'code'],
                name='uniq_exigence_cps_code',
            ),
        ]
        indexes = [models.Index(fields=['company', 'appel_offre'])]

    def __str__(self):
        return f'{self.code} — {self.libelle}'

    @property
    def est_intervalle(self):
        return self.valeur_max_num is not None


#: AOF14 — jeu de clauses de RÉFÉRENCE relevé sur un CPS réel (session du
#: 27/07/2026). Sert de fixture reproductible aux tests et d'amorce à la
#: saisie ; ce n'est PAS une norme (aucun texte normatif marocain n'est présent
#: dans le dépôt — cf. la règle de nommage d'AOF27).
CLAUSES_REFERENCE_CPS = (
    {
        'code': 'RATIO_DC_AC',
        'libelle': 'Ratio DC/AC admissible',
        'type_exigence': ExigenceCPS.TypeExigence.RATIO_DC_AC,
        'valeur_num': '0.7500',
        'valeur_max_num': '1.0000',
        'unite': '',
        'source_piece': 'CPS',
        'source_page': 33,
        'bloquant': True,
    },
    {
        'code': 'ONDULEUR_KWC_MAX',
        'libelle': "Puissance unitaire maximale d'un onduleur",
        'type_exigence': ExigenceCPS.TypeExigence.PUISSANCE_ONDULEUR_MAX,
        'valeur_num': '60.0000',
        'unite': 'kWc',
        'source_piece': 'CPS',
        'source_page': 33,
        'bloquant': True,
    },
    {
        'code': 'CAUTION_PROVISOIRE',
        'libelle': 'Caution provisoire (montant absolu fixé par le CPS)',
        'type_exigence': ExigenceCPS.TypeExigence.CAUTION_PROVISOIRE,
        'valeur_num': '30000.0000',
        'unite': 'MAD',
        'source_piece': 'Règlement de consultation',
        'bloquant': True,
    },
    {
        'code': 'CAUTION_DEFINITIVE_TAUX',
        'libelle': 'Cautionnement définitif (taux du montant initial)',
        'type_exigence': ExigenceCPS.TypeExigence.CAUTION_DEFINITIVE_TAUX,
        'valeur_num': '3.0000',
        'unite': '%',
        'source_piece': 'CPS',
        'bloquant': True,
    },
    {
        'code': 'VALIDITE_OFFRE',
        'libelle': "Durée de validité de l'offre",
        'type_exigence': ExigenceCPS.TypeExigence.VALIDITE_OFFRE,
        'valeur_num': '75.0000',
        'unite': 'jours',
        'source_piece': 'Règlement de consultation',
        'bloquant': True,
    },
    {
        'code': 'PENALITE_RETARD',
        'libelle': 'Pénalité de retard journalière',
        'type_exigence': ExigenceCPS.TypeExigence.PENALITE_RETARD,
        'valeur_num': '1.0000',
        'unite': '‰/jour',
        'source_piece': 'CPS',
        'bloquant': False,
    },
    {
        'code': 'PIECE_ATTESTATION_FISCALE',
        'libelle': 'Attestation fiscale de moins d\'un an',
        'type_exigence': ExigenceCPS.TypeExigence.PIECE_ADMINISTRATIVE,
        'valeur_texte': 'Attestation fiscale (< 1 an)',
        'source_piece': 'Règlement de consultation',
        'bloquant': True,
    },
)


# ── AOF18/AOF19 — Bâtiments et toitures du projet ──────────────────────────
#
# AOF19 — les fonctions de géométrie vivent dans ``apps/ao/geometrie.py``, le
# module PUR (stdlib seule, zéro Django, zéro I/O) qui porte le contrat d'ordre
# des axes. Elles sont ré-exportées ici pour que ``from apps.ao.models import
# polygone_est_simple`` reste valide, mais l'implémentation n'est écrite QU'UNE
# fois — deux copies divergeraient au premier correctif.

class BatimentAO(TenantModel):
    """Un bâtiment du projet (AOF18).

    Un site d'appel d'offres se découpe en bâtiments (A, B, C…), chacun portant
    une ou plusieurs toitures. L'engagement en modules du PROJET n'est jamais
    recopié : il s'agrège depuis les bâtiments et les toitures.
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: purge multi-tenant — les batiments suivent la societe
        related_name='batiments_ao',
        verbose_name='Société',
    )
    appel_offre = models.ForeignKey(
        AppelOffre,
        on_delete=models.CASCADE,  # on_delete: batiment fille d'un AO : aucune existence hors de son appel d'offres
        related_name='batiments',
        verbose_name="Appel d'offres",
    )
    code = models.CharField(max_length=30, verbose_name='Code du bâtiment')
    designation = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Désignation')
    ordre = models.PositiveIntegerField(default=1, verbose_name='Ordre')
    engagement_modules = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Engagement (modules)')
    notes = models.TextField(blank=True, default='', verbose_name='Notes')

    class Meta:
        verbose_name = 'Bâtiment (AO)'
        verbose_name_plural = 'Bâtiments (AO)'
        db_table = 'ao_batiment'
        ordering = ['appel_offre', 'ordre', 'code']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'appel_offre', 'code'],
                name='uniq_batiment_ao_code',
            ),
        ]
        indexes = [models.Index(fields=['company', 'appel_offre'])]

    def __str__(self):
        return f'{self.code} — {self.designation}' if self.designation \
            else self.code

    @property
    def surface_toitures_m2(self):
        """Somme des surfaces des toitures — CALCULÉE, jamais recopiée."""
        total = Decimal('0.000')
        for toiture in self.toitures.all():
            total += toiture.surface_m2 or Decimal('0.000')
        return total


class ToitureAO(TenantModel):
    """Une toiture d'un bâtiment, en repère LOCAL MÉTRIQUE (AOF18).

    **Ordre des axes.** ``contour_local_m`` est une liste de ``[x, y]`` en
    MÈTRES dans le repère local de la toiture — jamais des degrés. Le nom du
    champ porte l'unité ET l'ordre : un champ nommé ``coordonnees`` rendrait
    indétectable l'inversion lat/lng déjà repérée entre l'outil de tracé
    (``[lng, lat]``) et le lead CRM (``[lat, lng]``). La conversion depuis/vers
    les degrés vit à la FRONTIÈRE (AOF19, ``apps/ao/geometrie.py``) ; le moteur
    de calepinage ne voit JAMAIS de degrés.
    """

    class Forme(models.TextChoices):
        RECTANGLE = 'rectangle', 'Rectangle'
        POLYGONE = 'polygone', 'Polygone'
        FORME_L = 'forme_l', 'Forme en L'
        ARC = 'arc', 'Arc / aile courbe'

    class TypeCouverture(models.TextChoices):
        BAC_ACIER = 'bac_acier', 'Bac acier'
        DALLE_BETON = 'dalle_beton', 'Dalle béton'
        TUILE = 'tuile', 'Tuile'
        MEMBRANE = 'membrane', 'Membrane / étanchéité'
        FIBROCIMENT = 'fibrociment', 'Fibrociment'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: purge multi-tenant — les toitures suivent la societe
        related_name='toitures_ao',
        verbose_name='Société',
    )
    batiment = models.ForeignKey(
        BatimentAO,
        on_delete=models.CASCADE,  # on_delete: toiture fille d'un batiment : aucune existence hors de lui
        related_name='toitures',
        verbose_name='Bâtiment',
    )
    code_document = models.CharField(
        max_length=20, blank=True, default='',
        verbose_name='Code de la planche (05H, 06H, 06I…)')
    designation = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Désignation')
    forme = models.CharField(
        max_length=12, choices=Forme.choices, default=Forme.RECTANGLE,
        verbose_name='Forme')
    #: Enveloppe : liste de ``[x, y]`` en MÈTRES, repère local (jamais degrés).
    contour_local_m = models.JSONField(
        default=list, blank=True,
        verbose_name='Contour local [x, y] en mètres')
    angle_nord_deg = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Azimut du repère local vs Nord (°)')

    # ── Paramètres d'ARC (aile courbe) ─────────────────────────────────────
    rayon_ext_m = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        verbose_name='Rayon extérieur (m)')
    largeur_m = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        verbose_name='Largeur de la bande (m)')
    arc_segments = models.JSONField(
        default=list, blank=True,
        verbose_name='Segments de l\'arc (découpage)')
    murets = models.JSONField(
        default=list, blank=True, verbose_name='Murets / refends')

    niveau = models.IntegerField(default=0, verbose_name='Niveau')
    altitude_m = models.DecimalField(
        max_digits=8, decimal_places=3, null=True, blank=True,
        verbose_name='Altitude / hauteur du plan (m)')
    type_couverture = models.CharField(
        max_length=14, choices=TypeCouverture.choices,
        default=TypeCouverture.AUTRE, verbose_name='Type de couverture')
    contraintes_structure = models.TextField(
        blank=True, default='', verbose_name='Contraintes de structure')
    #: Surface CALCULÉE depuis le contour (jamais saisie à la main).
    surface_m2 = models.DecimalField(
        max_digits=12, decimal_places=3, default=Decimal('0.000'),
        verbose_name='Surface calculée (m²)')

    class Meta:
        verbose_name = 'Toiture (AO)'
        verbose_name_plural = 'Toitures (AO)'
        db_table = 'ao_toiture'
        ordering = ['batiment', 'code_document', 'id']
        indexes = [models.Index(fields=['company', 'batiment'])]

    def __str__(self):
        etiquette = self.code_document or self.designation or f'#{self.pk}'
        return f'{self.batiment.code} · {etiquette}'

    def clean(self):
        """Refuse une enveloppe qui ne tient pas debout (AOF18).

        Deux refus, tous deux constatés sur des relevés réels : un polygone
        qui se croise (les rangées sortiraient du bâtiment) et un arc sans
        rayon NI largeur (impossible à développer).
        """
        erreurs = {}
        if self.forme == self.Forme.ARC:
            if self.rayon_ext_m is None or self.largeur_m is None:
                erreurs['rayon_ext_m'] = (
                    "Une toiture en arc exige un rayon extérieur ET une "
                    "largeur de bande : sans les deux, l'arc n'est pas "
                    "développable."
                )
        elif self.contour_local_m:
            if not polygone_est_simple(self.contour_local_m):
                erreurs['contour_local_m'] = (
                    "L'enveloppe doit être un polygone SIMPLE (au moins 3 "
                    "sommets distincts, aucune arête qui en croise une autre)."
                )
        if erreurs:
            from django.core.exceptions import ValidationError
            raise ValidationError(erreurs)

    def recalculer_surface(self):
        """Recalcule ``surface_m2`` depuis le contour (jamais une saisie)."""
        self.surface_m2 = Decimal(
            f'{aire_polygone_m2(self.contour_local_m):.3f}')
        return self.surface_m2


# ── AOF20 — Les 3 portes d'entrée sont UN CHAMP, pas 3 chemins de données ───

class PlanSource(TenantModel):
    """Un support de tracé rattaché à une toiture (AOF20).

    Les TROIS portes d'entrée du plan de toiture — plan fourni (PDF/DXF/image
    calibré à 2 points), tracé manuel, reprise depuis un lecteur de cartes —
    sont un CHAMP (``origine``), pas trois chemins de données : elles
    produisent toutes le même ``ToitureAO`` et ouvrent le même éditeur. Trois
    chemins signifieraient trois éditeurs à maintenir.

    Séparer ``PlanSource`` de ``ToitureAO`` est ce qui rend naturel le cas
    « plan fourni MAIS à compléter » : une même toiture porte un plan calibré
    ET des tracés manuels additifs, cumulables.

    La pièce elle-même passe par ``records.Attachment`` (MinIO) — JAMAIS un
    ``FileField`` : le garde ARC26 gèle ``apps/ao/models.py`` à l'unique
    ``PieceSoumission.fichier`` historique.
    """

    class Origine(models.TextChoices):
        PLAN_FOURNI = 'plan_fourni', 'Plan fourni (PDF/DXF/image)'
        TRACE_MANUEL = 'trace_manuel', 'Tracé manuel'
        CARTE = 'carte', 'Reprise depuis une carte'

    class TypeFichier(models.TextChoices):
        PDF = 'pdf', 'PDF'
        DXF = 'dxf', 'DXF'
        IMAGE = 'image', 'Image'
        AUCUN = 'aucun', 'Aucun fichier'

    class Etat(models.TextChoices):
        BRUT = 'brut', 'Brut (non calibré)'
        CALIBRE = 'calibre', 'Calibré'
        VECTORISE = 'vectorise', 'Vectorisé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: purge multi-tenant — les plans suivent la societe
        related_name='plans_source_ao',
        verbose_name='Société',
    )
    toiture = models.ForeignKey(
        ToitureAO,
        on_delete=models.CASCADE,  # on_delete: support fille d'une toiture : aucune existence hors d'elle
        related_name='plans_source', null=True, blank=True,
        verbose_name='Toiture',
    )
    batiment = models.ForeignKey(
        BatimentAO,
        on_delete=models.CASCADE,  # on_delete: support fille d'un batiment : aucune existence hors de lui
        related_name='plans_source', null=True, blank=True,
        verbose_name='Bâtiment',
    )
    origine = models.CharField(
        max_length=14, choices=Origine.choices, default=Origine.PLAN_FOURNI,
        verbose_name="Porte d'entrée")
    type_fichier = models.CharField(
        max_length=8, choices=TypeFichier.choices, default=TypeFichier.AUCUN,
        verbose_name='Type de fichier')
    attachment = models.ForeignKey(
        'records.Attachment',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='plans_source_ao', verbose_name='Fichier (MinIO)')
    page = models.PositiveIntegerField(default=1, verbose_name='Page')

    # ── Calibration à DEUX points ──────────────────────────────────────────
    #: Les noms portent l'UNITÉ : ``_px`` = pixels de l'image/planche.
    calib_point_a_px = models.JSONField(
        default=list, blank=True, verbose_name='Point A [x, y] en pixels')
    calib_point_b_px = models.JSONField(
        default=list, blank=True, verbose_name='Point B [x, y] en pixels')
    calib_distance_reelle_m = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        verbose_name='Distance réelle A→B (m)')
    #: DÉRIVÉE de la calibration — jamais saisie.
    echelle_m_par_px = models.DecimalField(
        max_digits=14, decimal_places=8, null=True, blank=True,
        verbose_name='Échelle (m/px)')

    # ── Transformation vers le repère local de la toiture ──────────────────
    origine_px = models.JSONField(
        default=list, blank=True,
        verbose_name='Origine du repère [x, y] en pixels')
    rotation_deg = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Rotation (°)')
    miroir_x = models.BooleanField(default=False, verbose_name='Miroir X')
    miroir_y = models.BooleanField(default=False, verbose_name='Miroir Y')

    empreinte_sha256 = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='Empreinte SHA-256 du fichier')
    etat = models.CharField(
        max_length=10, choices=Etat.choices, default=Etat.BRUT,
        verbose_name='État')
    fourni_par = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Fourni par')

    class Meta:
        verbose_name = 'Support de plan (AO)'
        verbose_name_plural = 'Supports de plan (AO)'
        db_table = 'ao_plan_source'
        ordering = ['toiture', 'batiment', 'id']
        indexes = [
            models.Index(fields=['company', 'toiture']),
            models.Index(fields=['company', 'empreinte_sha256']),
        ]

    def __str__(self):
        return f'{self.get_origine_display()} — {self.get_etat_display()}'

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.toiture_id is None and self.batiment_id is None:
            raise ValidationError({'toiture': (
                'Un support de plan se rattache à une toiture ou, à défaut, à '
                'un bâtiment : sans rattachement, sa provenance est perdue.'
            )})

    @property
    def distance_calibration_px(self):
        """Distance A→B en pixels, ou ``None`` si la calibration est partielle."""
        a, b = self.calib_point_a_px or [], self.calib_point_b_px or []
        if len(a) < 2 or len(b) < 2:
            return None
        return math.hypot(float(b[0]) - float(a[0]),
                          float(b[1]) - float(a[1]))

    def recalculer_echelle(self):
        """(Re)calcule ``echelle_m_par_px`` depuis les deux points (AOF20).

        Toute modification d'un point de calibration doit repasser par ici :
        une échelle figée après un déplacement de point ferait fausser TOUTES
        les cotes déduites du plan. Renvoie l'échelle (ou ``None``) et met
        l'état à jour.
        """
        distance_px = self.distance_calibration_px
        if not distance_px or self.calib_distance_reelle_m in (None, ''):
            self.echelle_m_par_px = None
            if self.etat == self.Etat.CALIBRE:
                self.etat = self.Etat.BRUT
            return None
        echelle = Decimal(self.calib_distance_reelle_m) / Decimal(
            f'{distance_px:.8f}')
        self.echelle_m_par_px = echelle.quantize(Decimal('0.00000001'))
        if self.etat == self.Etat.BRUT:
            self.etat = self.Etat.CALIBRE
        return self.echelle_m_par_px


# ── FG223 — Bordereau des prix (BOQ) d'appel d'offres ──────────────────────

class BordereauPrix(TenantModel):
    """Bordereau des prix (BOQ) d'un AO (FG223), séparé du devis client.

    Chiffrage interne ligne à ligne de l'AO. Distinct du devis : sert au
    montage de l'offre de prix. ``total_ht`` agrège les lignes.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: purge multi-tenant — supprimer une societe retire ses dossiers d'AO
        related_name='bordereaux_prix',
        verbose_name='Société',
    )
    appel_offre = models.ForeignKey(
        AppelOffre,
        on_delete=models.CASCADE,  # on_delete: piece fille d'un AO : aucune existence hors de son appel d'offres
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


class LigneBordereau(TenantModel):
    """Une ligne chiffrée d'un BOQ (FG223)."""
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: purge multi-tenant — supprimer une societe retire ses dossiers d'AO
        related_name='lignes_bordereau',
        verbose_name='Société',
    )
    bordereau = models.ForeignKey(
        BordereauPrix,
        on_delete=models.CASCADE,  # on_delete: ligne de bordereau : aucune existence hors de son bordereau
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

class CautionSoumission(TenantModel):
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
        on_delete=models.CASCADE,  # on_delete: purge multi-tenant — supprimer une societe retire ses dossiers d'AO
        related_name='cautions_soumission',
        verbose_name='Société',
    )
    appel_offre = models.ForeignKey(
        AppelOffre,
        on_delete=models.CASCADE,  # on_delete: piece fille d'un AO : aucune existence hors de son appel d'offres
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

    # ── AOF16 — acte + pièce jointe ────────────────────────────────────────
    #
    # ATTENTION : ``banque``, ``date_emission``, ``date_echeance``,
    # ``date_restitution`` et ``statut`` EXISTAIENT DÉJÀ ci-dessus — les
    # redéclarer aurait produit une migration en double champ. Seuls les deux
    # champs ci-dessous sont NOUVEAUX.
    reference_acte = models.CharField(
        max_length=120, blank=True, default='',
        verbose_name="Référence de l'acte de cautionnement")
    #: Pièce jointe via ``records.Attachment`` (MinIO) — JAMAIS un
    #: ``FileField`` : le garde ARC26 gèle ``apps/ao/models.py`` à l'unique
    #: ``PieceSoumission.fichier`` historique.
    attachment = models.ForeignKey(
        'records.Attachment',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cautions_ao', verbose_name='Acte scanné')

    class Meta:
        verbose_name = 'Caution de soumission'
        verbose_name_plural = 'Cautions de soumission'
        db_table = 'compta_cautionsoumission'
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.type_caution} {self.montant} MAD ({self.banque})'

    @property
    def expire_avant_ouverture(self):
        """AOF16 — la caution expire-t-elle AVANT l'ouverture des plis ?

        Une caution provisoire périmée le jour de l'ouverture fait rejeter le
        pli : c'est une alerte, pas une information. ``None`` quand l'une des
        deux dates manque (jamais un faux « tout va bien »).
        """
        ouverture = self.appel_offre.date_ouverture_plis
        if self.date_echeance is None or ouverture is None:
            return None
        return self.date_echeance < ouverture


# ── FG225 — Dossier de soumission (pièces administratives) ─────────────────

class DossierSoumission(TenantModel):
    """Dossier de soumission d'un AO (FG225) : checklist + dépôt des pièces.

    Attestations fiscale/CNSS, RC, déclaration sur l'honneur… Le dossier
    regroupe les pièces (``PieceSoumission``) ; ``complet`` est dérivé du
    pointage des pièces obligatoires.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: purge multi-tenant — supprimer une societe retire ses dossiers d'AO
        related_name='dossiers_soumission',
        verbose_name='Société',
    )
    appel_offre = models.OneToOneField(
        AppelOffre,
        on_delete=models.CASCADE,  # on_delete: piece fille d'un AO : aucune existence hors de son appel d'offres
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


class PieceSoumission(TenantModel):
    """Une pièce administrative d'un dossier de soumission (FG225)."""
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: purge multi-tenant — supprimer une societe retire ses dossiers d'AO
        related_name='pieces_soumission',
        verbose_name='Société',
    )
    dossier = models.ForeignKey(
        DossierSoumission,
        on_delete=models.CASCADE,  # on_delete: piece administrative : aucune existence hors de son dossier
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

class EcheanceAO(TenantModel):
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
        on_delete=models.CASCADE,  # on_delete: purge multi-tenant — supprimer une societe retire ses dossiers d'AO
        related_name='echeances_ao',
        verbose_name='Société',
    )
    appel_offre = models.ForeignKey(
        AppelOffre,
        on_delete=models.CASCADE,  # on_delete: piece fille d'un AO : aucune existence hors de son appel d'offres
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

class ResultatAO(TenantModel):
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
        on_delete=models.CASCADE,  # on_delete: purge multi-tenant — supprimer une societe retire ses dossiers d'AO
        related_name='resultats_ao',
        verbose_name='Société',
    )
    appel_offre = models.OneToOneField(
        AppelOffre,
        on_delete=models.CASCADE,  # on_delete: piece fille d'un AO : aucune existence hors de son appel d'offres
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
