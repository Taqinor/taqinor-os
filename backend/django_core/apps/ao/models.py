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

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.documents import DocumentMetier
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
    #: AOF144 — marque blanche de PREMIER RANG : quand elle est active, aucun
    #: artefact remis au maître d'ouvrage ne nomme le bureau d'exécution.
    marque_blanche = models.BooleanField(
        default=False, verbose_name='Marque blanche active')
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


# ── AOF21 — Le DCE REÇU de l'acheteur devient une pièce du dossier ─────────

class PieceConsultation(TenantModel):
    """Une pièce du dossier de consultation REÇUE de l'acheteur (AOF21).

    Constat : ``ExigenceCPS.source_page`` référençait « la page du CPS » alors
    qu'AUCUN modèle ne stockait le CPS lui-même, et un plan importé perdait
    l'origine documentaire dont il provenait. Le dossier ne connaissait que NOS
    pièces (``PieceSoumission``), jamais celles de l'acheteur.

    Le cas qui coûte cher est l'ADDITIF (erratum) reçu APRÈS le téléchargement
    du dossier : il change des clauses déjà relevées. Ici, enregistrer un
    additif marque « à revérifier » les exigences qui en dérivent — au lieu de
    les laisser silencieusement périmées.
    """

    class TypePiece(models.TextChoices):
        CPS = 'cps', 'CPS (cahier des prescriptions spéciales)'
        REGLEMENT = 'reglement', 'Règlement de consultation'
        PLAN_ARCHITECTE = 'plan_architecte', "Plan d'architecte"
        MODELE_ACTE = 'modele_acte', "Modèle d'acte d'engagement"
        BORDEREAU_VIERGE = 'bordereau_vierge', 'Bordereau des prix vierge'
        ADDITIF = 'additif', 'Additif / erratum'
        AUTRE = 'autre', 'Autre pièce du DCE'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: purge multi-tenant — les pieces du DCE suivent la societe
        related_name='pieces_consultation',
        verbose_name='Société',
    )
    appel_offre = models.ForeignKey(
        AppelOffre,
        on_delete=models.CASCADE,  # on_delete: piece du DCE : aucune existence hors de son appel d'offres
        related_name='pieces_consultation',
        verbose_name="Appel d'offres",
    )
    type_piece = models.CharField(
        max_length=20, choices=TypePiece.choices, default=TypePiece.AUTRE,
        verbose_name='Type de pièce')
    reference = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Référence')
    version = models.CharField(
        max_length=40, blank=True, default='', verbose_name='Version reçue')
    date_reception = models.DateField(
        null=True, blank=True, verbose_name='Date de réception')
    attachment = models.ForeignKey(
        'records.Attachment',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pieces_consultation_ao', verbose_name='Fichier (MinIO)')
    #: Sommaire indexé : ``[{"page": 33, "titre": "Ratio DC/AC"}, …]``.
    pages_indexees = models.JSONField(
        default=list, blank=True, verbose_name='Pages indexées')
    #: Empreinte du fichier reçu — reconnaît un même document reçu deux fois
    #: et évite un doublon en stockage.
    empreinte_sha256 = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='Empreinte SHA-256')
    #: Un ADDITIF pointe la pièce qu'il modifie.
    modifie = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='additifs', verbose_name='Pièce modifiée')

    class Meta:
        verbose_name = 'Pièce du dossier de consultation'
        verbose_name_plural = 'Pièces du dossier de consultation'
        db_table = 'ao_piece_consultation'
        ordering = ['appel_offre', 'type_piece', 'id']
        indexes = [
            models.Index(fields=['company', 'appel_offre']),
            models.Index(fields=['company', 'empreinte_sha256']),
        ]

    def __str__(self):
        etiquette = self.reference or self.get_type_piece_display()
        return f'{etiquette} ({self.version})' if self.version else etiquette

    @property
    def est_additif(self):
        return self.type_piece == self.TypePiece.ADDITIF


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
    #: AOF21 — la pièce RÉELLEMENT reçue dont cette clause est extraite.
    #: Sans elle, « page 33 du CPS » ne désigne aucun document existant.
    piece_consultation = models.ForeignKey(
        PieceConsultation,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='exigences', verbose_name='Pièce du DCE (document)')
    #: AOF21 — un ADDITIF reçu après coup lève ce drapeau sur les clauses qui
    #: dérivent de la pièce modifiée : elles sont à RELIRE, pas silencieusement
    #: périmées.
    a_reverifier = models.BooleanField(
        default=False, verbose_name='À revérifier (additif reçu)')
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
#: saisie ; ce n'est PAS réglementaire (aucun texte normatif marocain n'est
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
    #: AOF27 — le preset APPLIQUÉ et l'instantané de ses paramètres. On garde
    #: les DEUX : le lien dit d'où viennent les réglages, l'instantané
    #: garantit qu'un preset modifié plus tard ne réécrit pas l'histoire d'un
    #: calepinage déjà publié.
    preset_applique = models.ForeignKey(
        'PresetCalepinage', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='toitures', verbose_name='Preset appliqué')
    parametres_calepinage = models.JSONField(
        default=dict, blank=True, verbose_name='Paramètres de calepinage')

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


# ── AOF24 — La visite contradictoire comme OBJET ───────────────────────────

class ReleveAO(TenantModel):
    """Une visite de relevé, contradictoire ou non (AOF24).

    Pourquoi en faire un objet : sans lui, une cote ou un obstacle ne peut pas
    dire D'OÙ il vient. Le cartouche d'une planche doit pouvoir écrire « base :
    relevé contradictoire du 27/07/2026 » — c'est ce qui rend le plan opposable.

    Les « points restant à lever » ne sont PAS une saisie libre : ils DÉRIVENT
    des cotes ``A_CONFIRMER`` et des obstacles non engageables. Une cote orange
    absente de la liste est un défaut, pas une omission acceptable — et un test
    le détecte.
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: purge multi-tenant — les releves suivent la societe
        related_name='releves_ao',
        verbose_name='Société',
    )
    appel_offre = models.ForeignKey(
        AppelOffre,
        on_delete=models.CASCADE,  # on_delete: releve fille d'un AO : aucune existence hors de son appel d'offres
        related_name='releves',
        verbose_name="Appel d'offres",
    )
    date_visite = models.DateField(verbose_name='Date de la visite')
    participants = models.TextField(
        blank=True, default='', verbose_name='Participants (un par ligne)')
    contradictoire = models.BooleanField(
        default=False, verbose_name='Visite contradictoire')
    toitures = models.ManyToManyField(
        ToitureAO, blank=True, related_name='releves',
        verbose_name='Toitures couvertes')
    conditions = models.TextField(
        blank=True, default='',
        verbose_name='Conditions (météo, accès, sécurité)')
    photos = models.ManyToManyField(
        'records.Attachment', blank=True, related_name='releves_ao',
        verbose_name='Photos')
    notes = models.TextField(blank=True, default='', verbose_name='Notes')

    class Meta:
        verbose_name = 'Relevé de toiture (AO)'
        verbose_name_plural = 'Relevés de toiture (AO)'
        db_table = 'ao_releve'
        ordering = ['-date_visite', 'id']
        indexes = [models.Index(fields=['company', 'appel_offre'])]

    def __str__(self):
        nature = 'contradictoire' if self.contradictoire else 'simple'
        return f'Relevé {nature} du {self.date_visite:%d/%m/%Y}'

    @property
    def mention_cartouche(self):
        """Mention prête à imprimer dans le cartouche d'une planche."""
        nature = 'contradictoire' if self.contradictoire else 'simple'
        return f'base : relevé {nature} du {self.date_visite:%d/%m/%Y}'


# ── AOF23 — Chaînes de cotes : le STATUT est porté par la DONNÉE ───────────

class StatutCote(models.TextChoices):
    """Fiabilité d'une cote — portée par la DONNÉE, jamais par un style.

    Ce statut alimentera le dessin, la légende, la section « À CONFIRMER À
    L'EXÉCUTION » et la liste des points à lever : le coder comme une couleur
    dans un gabarit le rendrait impossible à interroger.
    """
    MESURE = 'MESURE', 'Mesurée sur site'
    A_CONFIRMER = 'A_CONFIRMER', 'À confirmer à l\'exécution'
    PLAN_OU_DEDUIT = 'PLAN_OU_DEDUIT', 'Lue sur plan ou déduite'


class ChaineCotes(TenantModel):
    """Une chaîne de cotes et sa FERMETURE (AOF23).

    Une chaîne additionne des segments et se compare à une mesure totale. Le
    RÉSIDU (en mètres ET en pourcentage) est la seule façon honnête de dire si
    un relevé tient debout.

    **Règle métier gravée :** une cote DÉDUITE d'une fermeture exacte PRIME sur
    une valeur annoncée arrondie, et bascule automatiquement en
    ``A_CONFIRMER``. Cas réel : 51,10 − (19,36 + 7,92 + 4,50 + 10,50) = 8,82 m
    déduits, contre « ≈ 8,5 » annoncé — l'écart de 0,32 m se publie, il ne se
    gomme pas.

    La tolérance est PAR CHAÎNE (0,02 à 0,30 m constatés selon l'instrument et
    la longueur) : une tolérance globale serait tantôt laxiste, tantôt absurde.
    """

    class Axe(models.TextChoices):
        X = 'x', 'Axe X (longueur)'
        Y = 'y', 'Axe Y (largeur)'
        OBLIQUE = 'oblique', 'Oblique / diagonale'

    class Verdict(models.TextChoices):
        OK = 'ok', 'Fermeture OK'
        ECART = 'ecart', 'Écart de fermeture'
        INCOMPLETE = 'incomplete', 'Chaîne incomplète'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: purge multi-tenant — les cotes suivent la societe
        related_name='chaines_cotes_ao',
        verbose_name='Société',
    )
    toiture = models.ForeignKey(
        ToitureAO,
        on_delete=models.CASCADE,  # on_delete: chaine fille d'une toiture : aucune existence hors d'elle
        related_name='chaines_cotes',
        verbose_name='Toiture',
    )
    #: AOF24 — la visite qui a produit cette chaîne. Sans elle, une cote ne
    #: peut pas dire d'où elle vient et le cartouche ne peut rien opposer.
    releve = models.ForeignKey(
        ReleveAO, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='chaines_cotes', verbose_name='Relevé')
    libelle = models.CharField(max_length=255, verbose_name='Libellé')
    axe = models.CharField(
        max_length=8, choices=Axe.choices, default=Axe.X, verbose_name='Axe')
    #: ``[{"libelle": "A→B", "valeur_m": 19.36, "statut": "MESURE",
    #:    "valeur_annoncee_m": 8.5, "deduit": true}, …]``
    segments = models.JSONField(
        default=list, blank=True, verbose_name='Segments')
    #: Mesure d'ensemble de la chaîne, en MÈTRES au millimètre.
    #: NE PAS renommer en ``mesure_totale_m`` : le garde YDATA7
    #: (``check_money_fields --decimal-places``) traite tout champ contenant
    #: « total » comme un MONTANT et exigerait ``decimal_places=2`` — on
    #: perdrait le millimètre sur une LONGUEUR.
    mesure_globale_m = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        verbose_name="Mesure d'ensemble (m)")
    #: Tolérance PROPRE à cette chaîne (0,02 à 0,30 m constatés).
    tolerance_m = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('0.050'),
        verbose_name='Tolérance (m)')
    #: Résidus CALCULÉS et PERSISTÉS (le rapport doit pouvoir les citer).
    residu_m = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        verbose_name='Résidu (m)')
    residu_pct = models.DecimalField(
        max_digits=8, decimal_places=3, null=True, blank=True,
        verbose_name='Résidu (%)')
    verdict = models.CharField(
        max_length=12, choices=Verdict.choices, default=Verdict.INCOMPLETE,
        verbose_name='Verdict')

    class Meta:
        verbose_name = 'Chaîne de cotes (AO)'
        verbose_name_plural = 'Chaînes de cotes (AO)'
        db_table = 'ao_chaine_cotes'
        ordering = ['toiture', 'axe', 'id']
        indexes = [models.Index(fields=['company', 'toiture'])]

    def __str__(self):
        return f'{self.libelle} ({self.get_axe_display()})'

    @property
    def somme_segments_m(self):
        total = Decimal('0.000')
        for segment in self.segments or []:
            valeur = segment.get('valeur_m')
            if valeur in (None, ''):
                continue
            total += Decimal(str(valeur))
        return total

    @property
    def cotes_a_confirmer(self):
        """Les segments ORANGE — la liste des points à lever en dérive."""
        return [
            segment for segment in (self.segments or [])
            if segment.get('statut') == StatutCote.A_CONFIRMER
        ]

    def recalculer_fermeture(self):
        """Recalcule résidu (m et %) + verdict. Valeurs PERSISTÉES à l'appel."""
        if self.mesure_globale_m is None:
            self.residu_m = None
            self.residu_pct = None
            self.verdict = self.Verdict.INCOMPLETE
            return self.verdict
        residu = Decimal(self.mesure_globale_m) - self.somme_segments_m
        self.residu_m = residu.quantize(Decimal('0.001'))
        total = Decimal(self.mesure_globale_m)
        self.residu_pct = (
            (residu / total * Decimal('100')).quantize(Decimal('0.001'))
            if total else None)
        self.verdict = (
            self.Verdict.OK if abs(self.residu_m) <= Decimal(self.tolerance_m)
            else self.Verdict.ECART)
        return self.verdict


# ── AOF22 — L'obstacle est une ENTITÉ DE PREMIER RANG ──────────────────────

class ObstacleAO(TenantModel):
    """Un obstacle de toiture, avec sa PROVENANCE et son dégagement (AOF22).

    Constat mesuré sur un relevé réel : deux emprises venues du PLAN et jamais
    relevées coûtaient 12 modules sur la seule aile en L, et quatre « souches »
    avaient été purement INVENTÉES faute de photo lisible. D'où la règle
    centrale de ce modèle : **la provenance d'un obstacle est une donnée de
    premier rang**, elle pilote son dégagement ET son caractère engageable.

    **Un obstacle mesuré n'est JAMAIS supprimé.** Il passe ``ECARTE`` avec sa
    décision, et sa GÉOMÉTRIE reste en base : le retour arrière devient un
    one-liner, et l'échelle de décomposition peut CHIFFRER ce que la décision
    rapporte. ``ECARTE`` reste filtrable et sérialisé de premier rang — sans
    requête sur les écartés, la marche correspondante de l'échelle est
    irreproductible.
    """

    class Nature(models.TextChoices):
        CAISSON_TECHNIQUE = 'caisson_technique', 'Caisson technique'
        CAGE_ESCALIER = 'cage_escalier', "Cage d'escalier"
        EDICULE = 'edicule', 'Édicule'
        SOUCHE = 'souche', 'Souche'
        GROUPE_CLIM = 'groupe_clim', 'Groupe de climatisation'
        ACROTERE = 'acrotere', 'Acrotère'
        JOINT_DILATATION = 'joint_dilatation', 'Joint de dilatation'
        MURET = 'muret', 'Muret'
        DECROCHEMENT_NIVEAU = 'decrochement_niveau', 'Décrochement de niveau'
        PAN_COUPE = 'pan_coupe', 'Pan coupé'
        LANTERNEAU = 'lanterneau', 'Lanterneau'
        EXUTOIRE_FUMEE = 'exutoire_fumee', 'Exutoire de fumée'
        CHEMIN_CABLES = 'chemin_cables', 'Chemin de câbles'

    class Provenance(models.TextChoices):
        MESURE = 'MESURE', 'Mesuré sur site'
        MESURE_DOUTEUX = 'MESURE_DOUTEUX', 'Mesuré, valeur douteuse'
        PLAN = 'PLAN', 'Lu sur plan (non relevé)'
        DEVINE = 'DEVINE', 'Deviné (photo illisible)'
        DECLARE_CLIENT = 'DECLARE_CLIENT', 'Déclaré par le client'
        ECARTE = 'ECARTE', 'Écarté (hors compte)'

    #: Dégagement DÉRIVÉ de la provenance (m). Une donnée dont on n'est pas
    #: sûr coûte plus de marge — c'est le prix de l'incertitude, pas une
    #: punition.
    DEGAGEMENT_PAR_PROVENANCE = {
        Provenance.MESURE: Decimal('0.30'),
        Provenance.MESURE_DOUTEUX: Decimal('0.50'),
        Provenance.PLAN: Decimal('0.50'),
        Provenance.DEVINE: Decimal('0.50'),
        Provenance.DECLARE_CLIENT: Decimal('0.30'),
        Provenance.ECARTE: Decimal('0.00'),
    }

    #: Une offre ne s'ENGAGE que sur ce qui a été RELEVÉ. Tout le reste est
    #: informatif : il entre dans le calcul, jamais dans l'engagement.
    PROVENANCES_ENGAGEABLES = frozenset({
        Provenance.MESURE, Provenance.MESURE_DOUTEUX,
    })

    #: Dégagement MINIMAL par nature d'obstacle (m) — un exutoire de fumée
    #: n'accepte pas le même voisinage qu'un simple chemin de câbles.
    DEGAGEMENT_PAR_NATURE = {
        Nature.CAISSON_TECHNIQUE: Decimal('0.50'),
        Nature.CAGE_ESCALIER: Decimal('0.60'),
        Nature.EDICULE: Decimal('0.60'),
        Nature.SOUCHE: Decimal('0.50'),
        Nature.GROUPE_CLIM: Decimal('0.60'),
        Nature.ACROTERE: Decimal('0.30'),
        Nature.JOINT_DILATATION: Decimal('0.30'),
        Nature.MURET: Decimal('0.30'),
        Nature.DECROCHEMENT_NIVEAU: Decimal('0.30'),
        Nature.PAN_COUPE: Decimal('0.30'),
        Nature.LANTERNEAU: Decimal('0.60'),
        Nature.EXUTOIRE_FUMEE: Decimal('1.00'),
        Nature.CHEMIN_CABLES: Decimal('0.30'),
    }

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: purge multi-tenant — les obstacles suivent la societe
        related_name='obstacles_ao',
        verbose_name='Société',
    )
    toiture = models.ForeignKey(
        ToitureAO,
        on_delete=models.CASCADE,  # on_delete: obstacle fille d'une toiture : aucune existence hors d'elle
        related_name='obstacles',
        verbose_name='Toiture',
    )
    #: AOF24 — la visite qui a produit cet obstacle (ou ``None`` s'il vient du
    #: plan). C'est ce lien qui distingue « relevé le 27/07 » de « supposé ».
    releve = models.ForeignKey(
        ReleveAO, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='obstacles', verbose_name='Relevé')
    repere = models.CharField(
        max_length=8, blank=True, default='', verbose_name='Repère (A, B, C…)')
    designation = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Désignation')
    nature = models.CharField(
        max_length=22, choices=Nature.choices,
        default=Nature.CAISSON_TECHNIQUE, verbose_name='Nature')

    # ── Emprise : rectangle (le cas courant) OU polygone ───────────────────
    #: Les noms portent l'unité : ``_m`` = mètres, repère LOCAL de la toiture.
    rect_x0_m = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        verbose_name='x0 (m)')
    rect_x1_m = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        verbose_name='x1 (m)')
    rect_y0_m = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        verbose_name='y0 (m)')
    rect_y1_m = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        verbose_name='y1 (m)')
    polygone_local_m = models.JSONField(
        default=list, blank=True,
        verbose_name='Polygone local [x, y] en mètres')
    hauteur_m = models.DecimalField(
        max_digits=8, decimal_places=3, null=True, blank=True,
        verbose_name='Hauteur (m)')

    provenance = models.CharField(
        max_length=16, choices=Provenance.choices, default=Provenance.MESURE,
        verbose_name='Provenance')
    degagement_m = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0.30'),
        verbose_name='Dégagement (m)')
    #: Une surcharge est LÉGITIME mais doit être JUSTIFIÉE : sans motif, une
    #: valeur retouchée devient indéfendable devant le maître d'ouvrage.
    degagement_surcharge = models.BooleanField(
        default=False, verbose_name='Dégagement surchargé')
    motif_surcharge = models.TextField(
        blank=True, default='', verbose_name='Motif de la surcharge')
    #: La RÈGLE effectivement appliquée, en clair — pas un commentaire de code.
    regle_degagement = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Règle de dégagement appliquée')

    hors_zone_pv = models.BooleanField(
        default=False, verbose_name='Hors zone photovoltaïque')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    decision = models.TextField(
        blank=True, default='', verbose_name='Décision (écart / confirmation)')
    # AOF25 — le lien vers la QUESTION qui porte cet obstacle existe, mais dans
    # l'autre sens : ``QuestionAO.obstacle`` (accesseur inverse
    # ``obstacle.questions``). Une seconde FK ici créerait deux vérités pour le
    # même lien — et un jour elles divergeraient.

    class Meta:
        verbose_name = 'Obstacle de toiture (AO)'
        verbose_name_plural = 'Obstacles de toiture (AO)'
        db_table = 'ao_obstacle'
        ordering = ['toiture', 'repere', 'id']
        indexes = [
            models.Index(fields=['company', 'toiture']),
            models.Index(fields=['company', 'provenance']),
        ]

    def __str__(self):
        etiquette = self.repere or self.get_nature_display()
        return f'{etiquette} — {self.get_provenance_display()}'

    @property
    def engageable(self):
        """Peut-on S'ENGAGER sur cet obstacle devant le maître d'ouvrage ?

        Seules les provenances RELEVÉES (mesurées, même douteuses) engagent.
        Un obstacle lu sur plan, deviné ou déclaré par le client entre dans le
        calcul mais JAMAIS dans l'engagement — c'est exactement la confusion
        qui a coûté 12 modules sur un relevé réel. Un obstacle ÉCARTÉ ou
        inactif n'engage rien non plus.
        """
        if not self.actif:
            return False
        return self.provenance in self.PROVENANCES_ENGAGEABLES

    @property
    def est_ecarte(self):
        return self.provenance == self.Provenance.ECARTE

    def degagement_derive(self):
        """Dégagement RÉGLÉ = max(défaut de la nature, défaut de la provenance).

        Renvoie ``(valeur, règle_en_clair)``. La règle est renvoyée pour être
        ÉCRITE dans la donnée : « on a pris 0,60 m » sans dire pourquoi n'est
        pas défendable trois mois plus tard.
        """
        par_nature = self.DEGAGEMENT_PAR_NATURE.get(
            self.nature, Decimal('0.30'))
        par_provenance = self.DEGAGEMENT_PAR_PROVENANCE.get(
            self.provenance, Decimal('0.30'))
        if self.provenance == self.Provenance.ECARTE:
            return Decimal('0.00'), (
                'écarté — hors compte (géométrie conservée)')
        valeur = max(par_nature, par_provenance)
        gagnant = 'nature' if par_nature >= par_provenance else 'provenance'
        regle = (
            f'max(nature {self.get_nature_display()} = {par_nature} m ; '
            f'provenance {self.get_provenance_display()} = {par_provenance} m)'
            f' → {valeur} m [{gagnant}]'
        )
        return valeur, regle

    def appliquer_degagement(self):
        """Recalcule ``degagement_m`` SAUF si une surcharge motivée l'a figé."""
        if self.degagement_surcharge:
            self.regle_degagement = (
                f'surcharge manuelle ({self.degagement_m} m) — '
                f'{self.motif_surcharge or "motif manquant"}')
            return self.degagement_m
        valeur, regle = self.degagement_derive()
        self.degagement_m = valeur
        self.regle_degagement = regle
        return valeur

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.degagement_surcharge and not (self.motif_surcharge or '').strip():
            raise ValidationError({'motif_surcharge': (
                'Une surcharge de dégagement exige un motif : une valeur '
                "retouchée sans justification n'est pas défendable devant le "
                'maître d\'ouvrage.'
            )})


# ── AOF25 — Le workflow Q/R sur documents annotés ──────────────────────────

class SerieQuestions(TenantModel):
    """Une série de questions envoyée au client/à l'acheteur (AOF25).

    Constat MESURÉ : trois séries de questions chiffrées sur images annotées
    ont fait passer un site de 512 → 522 → 562 → 618 modules posables. La
    série 2 a supprimé quatre souches inventées et rouvert les allées ; la
    série 3 a récupéré un grand rectangle « NÉANT », un angle SE droit et une
    structure de rive hors zone PV. Poser les bonnes questions est donc une
    opération PRODUCTIVE, pas de la paperasse — d'où sa modélisation.
    """

    class Canal(models.TextChoices):
        EMAIL = 'email', 'Courriel'
        WHATSAPP = 'whatsapp', 'WhatsApp'
        COURRIER = 'courrier', 'Courrier'
        REUNION = 'reunion', 'Réunion'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: purge multi-tenant — les series suivent la societe
        related_name='series_questions_ao',
        verbose_name='Société',
    )
    appel_offre = models.ForeignKey(
        AppelOffre,
        on_delete=models.CASCADE,  # on_delete: serie fille d'un AO : aucune existence hors de son appel d'offres
        related_name='series_questions',
        verbose_name="Appel d'offres",
    )
    numero = models.PositiveIntegerField(default=1, verbose_name='Numéro')
    date_envoi = models.DateField(
        null=True, blank=True, verbose_name="Date d'envoi")
    canal = models.CharField(
        max_length=10, choices=Canal.choices, default=Canal.EMAIL,
        verbose_name='Canal')
    destinataire = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Destinataire')

    class Meta:
        verbose_name = 'Série de questions (AO)'
        verbose_name_plural = 'Séries de questions (AO)'
        db_table = 'ao_serie_questions'
        ordering = ['appel_offre', 'numero']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'appel_offre', 'numero'],
                name='uniq_serie_questions_numero',
            ),
        ]
        indexes = [models.Index(fields=['company', 'appel_offre'])]

    def __str__(self):
        return f'Série {self.numero} — {self.get_canal_display()}'

    @property
    def impact_total_modules(self):
        """Fourchette d'impact CUMULÉE de la série, en modules."""
        mini = maxi = 0
        for question in self.questions.all():
            mini += question.impact_min_modules or 0
            maxi += question.impact_max_modules or 0
        return {'min': mini, 'max': maxi}


class QuestionAO(TenantModel):
    """Une question chiffrée sur un document annoté (AOF25).

    **Règle produit gravée : une question ne se pose QUE si sa réponse change
    le compte.** Une question sans impact chiffré prévisionnel est REFUSÉE —
    sinon la série devient un questionnaire administratif que personne ne
    remplit, et les vraies questions s'y noient.
    """

    class Statut(models.TextChoices):
        POSEE = 'posee', 'Posée'
        REPONDUE = 'repondue', 'Répondue'
        TRANCHEE = 'tranchee', 'Tranchée'
        SANS_SUITE = 'sans_suite', 'Sans suite'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: purge multi-tenant — les questions suivent la societe
        related_name='questions_ao',
        verbose_name='Société',
    )
    serie = models.ForeignKey(
        SerieQuestions,
        on_delete=models.CASCADE,  # on_delete: question fille d'une serie : aucune existence hors d'elle
        related_name='questions',
        verbose_name='Série',
    )
    repere = models.CharField(
        max_length=4, blank=True, default='',
        verbose_name='Repère sur l\'image (A–K)')
    image = models.ForeignKey(
        'records.Attachment',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='questions_ao', verbose_name='Image annotée')
    texte = models.CharField(max_length=500, verbose_name='Question')
    #: Impact PRÉVISIONNEL en modules — la raison d'être de la question.
    impact_min_modules = models.IntegerField(
        null=True, blank=True, verbose_name='Impact minimal (modules)')
    impact_max_modules = models.IntegerField(
        null=True, blank=True, verbose_name='Impact maximal (modules)')
    reponse = models.TextField(blank=True, default='', verbose_name='Réponse')
    decision = models.TextField(
        blank=True, default='', verbose_name='Décision retenue')
    date_decision = models.DateField(
        null=True, blank=True, verbose_name='Date de la décision')
    statut = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.POSEE,
        verbose_name='Statut')
    #: Objets CONCERNÉS — c'est ce qui rend la décision applicable.
    obstacle = models.ForeignKey(
        ObstacleAO, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='questions', verbose_name='Obstacle concerné')
    chaine = models.ForeignKey(
        ChaineCotes, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='questions', verbose_name='Chaîne de cotes concernée')

    class Meta:
        verbose_name = 'Question (AO)'
        verbose_name_plural = 'Questions (AO)'
        db_table = 'ao_question'
        ordering = ['serie', 'repere', 'id']
        indexes = [
            models.Index(fields=['company', 'serie']),
            models.Index(fields=['company', 'statut']),
        ]

    def __str__(self):
        return f'{self.repere or "?"} — {self.texte[:60]}'

    @property
    def a_un_impact_chiffre(self):
        return not (self.impact_min_modules is None
                    and self.impact_max_modules is None)

    def clean(self):
        from django.core.exceptions import ValidationError

        if not self.a_un_impact_chiffre:
            raise ValidationError({'impact_min_modules': (
                "Une question ne se pose QUE si sa réponse change le compte : "
                "chiffrez son impact prévisionnel en modules (minimum et/ou "
                "maximum), sinon la série devient un questionnaire "
                "administratif où les vraies questions se noient."
            )})


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
    #: AOF21 — la pièce du DCE dont ce plan provient. Un plan importé par la
    #: porte n°1 doit pouvoir CITER son origine documentaire, sinon la
    #: provenance est perdue dès la deuxième version reçue.
    piece_consultation = models.ForeignKey(
        PieceConsultation,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='plans_source', verbose_name='Pièce du DCE')
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


# ── AOF26 — Catalogue des KITS de pose ─────────────────────────────────────

class KitCalepinage(TenantModel):
    """Un kit de pose : la brique élémentaire du calepinage (AOF26).

    Le moteur est PARTAGÉ avec les villas : une villa est simplement un kit à
    ``modules_par_kit = 1``, l'AO un kit table dos-à-dos à 2 modules. Modéliser
    le kit — plutôt que de coder deux moteurs — est ce qui rend cette parité
    possible.

    **AUCUN PRIX ICI.** Le prix vient du ``Produit`` lié (string-FK
    ``stock.Produit``, jamais un import cross-app) : figer un prix dans le kit
    créerait une seconde vérité qui divergerait du catalogue au premier
    réapprovisionnement.

    Les emprises transversales se DÉRIVENT de la géométrie
    (``2 × longueur_pente × cos(inclinaison) + faîtage``) mais une valeur
    MESURÉE sur un kit réellement approvisionné peut être FIGÉE : elle prime
    alors, et l'écart avec la dérivation reste tracé (``ecart_emprise_m``) —
    c'est l'écart qui révèle une hypothèse fausse, pas la valeur seule.
    """

    class Mode(models.TextChoices):
        TABLE_DOS_A_DOS = 'table_dos_a_dos', 'Table dos-à-dos'
        PANNEAU_SIMPLE = 'panneau_simple', 'Panneau simple'

    class Orientation(models.TextChoices):
        PORTRAIT = 'portrait', 'Portrait'
        PAYSAGE = 'paysage', 'Paysage'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: purge multi-tenant — le catalogue de kits suit la societe
        related_name='kits_calepinage',
        verbose_name='Société',
    )
    code = models.CharField(max_length=40, verbose_name='Code du kit')
    libelle = models.CharField(max_length=255, verbose_name='Libellé')
    mode = models.CharField(
        max_length=16, choices=Mode.choices, default=Mode.TABLE_DOS_A_DOS,
        verbose_name='Mode de pose')
    modules_par_kit = models.PositiveIntegerField(
        default=2, verbose_name='Modules par kit')
    #: Pas LE LONG de la rangée (m) — la dimension qui se répète.
    pas_rangee_m = models.DecimalField(
        max_digits=8, decimal_places=3, verbose_name='Pas le long de la rangée (m)')
    #: Dimension du module DANS LA PENTE (m) — sert à dériver l'emprise.
    longueur_pente_m = models.DecimalField(
        max_digits=8, decimal_places=3,
        verbose_name='Longueur du module dans la pente (m)')
    faitage_m = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('0.000'),
        verbose_name='Jeu de faîtage (m)')
    #: Emprise transversale RETENUE (dérivée, ou mesurée si figée).
    emprise_transversale_m = models.DecimalField(
        max_digits=8, decimal_places=3, default=Decimal('0.000'),
        verbose_name='Emprise transversale (m)')
    emprise_mesuree_m = models.DecimalField(
        max_digits=8, decimal_places=3, null=True, blank=True,
        verbose_name='Emprise MESURÉE (m)')
    emprise_figee = models.BooleanField(
        default=False, verbose_name='Emprise mesurée figée (prime)')
    ecart_emprise_m = models.DecimalField(
        max_digits=8, decimal_places=3, null=True, blank=True,
        verbose_name='Écart mesuré − dérivé (m)')
    puissance_module_w = models.PositiveIntegerField(
        default=625, verbose_name='Puissance unitaire du module (W)')
    inclinaison_deg = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('15.00'),
        verbose_name='Inclinaison (°)')
    orientation_modules = models.CharField(
        max_length=10, choices=Orientation.choices,
        default=Orientation.PORTRAIT, verbose_name='Orientation des modules')
    #: string-FK ``'stock.Produit'`` — ``apps.ao.models`` n'importe JAMAIS
    #: ``apps.stock.models`` (contrat import-linter ``ao-models-decoupled``).
    #: C'est LUI qui porte le prix ; le kit n'en fige aucun.
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='kits_calepinage_ao', verbose_name='Produit (prix)')
    actif = models.BooleanField(default=True, verbose_name='Actif')

    class Meta:
        verbose_name = 'Kit de calepinage (AO)'
        verbose_name_plural = 'Kits de calepinage (AO)'
        db_table = 'ao_kit_calepinage'
        ordering = ['code']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'], name='uniq_kit_calepinage_code'),
        ]
        indexes = [models.Index(fields=['company', 'actif'])]

    def __str__(self):
        return f'{self.code} — {self.libelle}'

    @property
    def puissance_kwc(self):
        """kWc d'UN kit = modules × puissance unitaire (jamais recopié)."""
        return (Decimal(self.modules_par_kit)
                * Decimal(self.puissance_module_w) / Decimal('1000'))

    def emprise_derivee_m(self):
        """``2 × longueur_pente × cos(inclinaison) + faîtage`` pour une table.

        Un panneau simple n'a qu'un versant : la dérivation n'a alors qu'un
        facteur 1. Renvoie un ``Decimal`` arrondi au millimètre.
        """
        facteur = 2 if self.mode == self.Mode.TABLE_DOS_A_DOS else 1
        cosinus = math.cos(math.radians(float(self.inclinaison_deg)))
        valeur = (facteur * float(self.longueur_pente_m) * cosinus
                  + float(self.faitage_m))
        return Decimal(f'{valeur:.3f}')

    def appliquer_emprise(self):
        """Fixe ``emprise_transversale_m`` et TRACE l'écart éventuel."""
        derivee = self.emprise_derivee_m()
        if self.emprise_figee and self.emprise_mesuree_m is not None:
            self.emprise_transversale_m = self.emprise_mesuree_m
            self.ecart_emprise_m = Decimal(self.emprise_mesuree_m) - derivee
        else:
            self.emprise_transversale_m = derivee
            self.ecart_emprise_m = (
                Decimal(self.emprise_mesuree_m) - derivee
                if self.emprise_mesuree_m is not None else None)
        return self.emprise_transversale_m


# ── AOF27 — Jeux de paramètres NOMMÉS, réutilisables, réappliquables ───────

class PresetCalepinage(TenantModel):
    """Un jeu de paramètres de calepinage nommé (AOF27).

    **Le jeu de référence s'appelle « FRDISI 2026-07 », JAMAIS autrement.**
    Aucun texte réglementaire marocain (dégagement pompier, distance acrotère,
    exutoire) n'est présent dans ce dépôt : présenter ces valeurs comme
    réglementaires produirait un jour un plan non conforme, opposable à
    l'entreprise. Ce sont des paramètres MAISON, issus d'un chantier réel — et
    le nom du preset doit le dire.

    Les anciens défauts conservateurs (1,50 / 0,50 / 0,50) restent disponibles
    comme « variante conservatrice », à titre d'information.
    """

    class Portee(models.TextChoices):
        VILLA = 'villa', 'Villa'
        AO = 'ao', "Appel d'offres"
        SOCIETE = 'societe', 'Société (tous usages)'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: purge multi-tenant — les presets suivent la societe
        related_name='presets_calepinage',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=120, verbose_name='Nom du preset')
    portee = models.CharField(
        max_length=10, choices=Portee.choices, default=Portee.AO,
        verbose_name='Portée')
    #: Paramètres : rives, allée minimale, dégagements par provenance, kits
    #: autorisés, orientation imposée, recherche d'allée gratuite, pas de
    #: recherche. Un dict — jamais une colonne par réglage, sinon chaque
    #: nouveau paramètre coûterait une migration.
    parametres = models.JSONField(default=dict, blank=True,
                                  verbose_name='Paramètres')
    par_defaut = models.BooleanField(
        default=False, verbose_name='Preset par défaut')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')

    class Meta:
        verbose_name = 'Preset de calepinage (AO)'
        verbose_name_plural = 'Presets de calepinage (AO)'
        db_table = 'ao_preset_calepinage'
        ordering = ['portee', 'nom']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'nom'], name='uniq_preset_calepinage_nom'),
        ]
        indexes = [models.Index(fields=['company', 'portee'])]

    def __str__(self):
        return f'{self.nom} ({self.get_portee_display()})'


#: AOF27 — le jeu de RÉFÉRENCE, relevé sur un chantier réel (07/2026).
#: Rives 0,35 m · allée minimale 0,60 m · dégagements 0,30 / 0,50 m.
PRESET_REFERENCE_NOM = 'FRDISI 2026-07'
PRESET_REFERENCE_PARAMETRES = {
    'rive_laterale_m': 0.35,
    'rive_extremite_m': 0.35,
    'allee_min_m': 0.60,
    'degagements_par_provenance_m': {
        'MESURE': 0.30,
        'MESURE_DOUTEUX': 0.50,
        'PLAN': 0.50,
        'DEVINE': 0.50,
        'DECLARE_CLIENT': 0.30,
    },
    'kits_autorises': ['AO-TABLE-PORTRAIT', 'AO-TABLE-PAYSAGE'],
    'orientation_imposee': None,
    'recherche_allee_gratuite': True,
    'pas_recherche_m': 0.01,
}

#: Les anciens défauts, conservés à titre d'INFORMATION (jamais le défaut).
PRESET_CONSERVATEUR_NOM = 'Variante conservatrice'
PRESET_CONSERVATEUR_PARAMETRES = {
    'rive_laterale_m': 1.50,
    'rive_extremite_m': 0.50,
    'allee_min_m': 0.50,
    'degagements_par_provenance_m': {
        'MESURE': 0.50,
        'MESURE_DOUTEUX': 0.50,
        'PLAN': 0.50,
        'DEVINE': 0.50,
        'DECLARE_CLIENT': 0.50,
    },
    'kits_autorises': ['AO-TABLE-PORTRAIT'],
    'orientation_imposee': None,
    'recherche_allee_gratuite': False,
    'pas_recherche_m': 0.05,
}


# ── AOF28 — Le modèle PIVOT des variantes (role + parent + preuve) ─────────

class VarianteCalepinage(TenantModel):
    """Un calepinage calculé, vu sous QUATRE angles (AOF28).

    Variante retenue, alternative comparée, sensibilité défavorable et marche
    de l'échelle de décomposition sont le MÊME objet : ``role`` + ``parent``
    suffisent. Trois tables jumelles auraient triplé chaque évolution du moteur
    et rendu l'écran de comparaison impossible à écrire en une requête.

    **La PREUVE est un CHAMP, pas un commentaire.** On ne peut écrire
    « capacité prouvée optimale » à un maître d'ouvrage que si la donnée le
    démontre : la transition vers ``publiable`` est REFUSÉE quand le total
    retenu est inférieur au total optimal, quand une marge de tronçon ou de
    bande passe sous son seuil, ou quand un obstacle NON MESURÉ est encore
    actif sur la toiture.
    """

    class Role(models.TextChoices):
        RETENUE = 'RETENUE', 'Variante retenue'
        ALTERNATIVE = 'ALTERNATIVE', 'Alternative comparée'
        SENSIBILITE = 'SENSIBILITE', 'Sensibilité défavorable'
        MARCHE = 'MARCHE', "Marche de l'échelle de décomposition"

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        CALCULEE = 'calculee', 'Calculée'
        PUBLIABLE = 'publiable', 'Publiable'
        PERIME = 'perime', 'Périmée'

    #: Seuils de PREUVE — sous ces marges, un plan n'est pas publiable.
    MARGE_TRONCON_MIN_M = Decimal('0.02')
    MARGE_BANDE_MIN_M = Decimal('0.04')

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: purge multi-tenant — les variantes suivent la societe
        related_name='variantes_calepinage',
        verbose_name='Société',
    )
    toiture = models.ForeignKey(
        ToitureAO,
        on_delete=models.CASCADE,  # on_delete: variante fille d'une toiture : aucune existence hors d'elle
        related_name='variantes',
        verbose_name='Toiture',
    )
    #: Dénormalisé pour que l'écran projet soit UNE requête (jamais deux
    #: sources de vérité : il est posé à la création depuis la toiture).
    appel_offre = models.ForeignKey(
        AppelOffre,
        on_delete=models.CASCADE,  # on_delete: variante fille d'un AO : aucune existence hors de son appel d'offres
        related_name='variantes_calepinage',
        verbose_name="Appel d'offres",
    )
    role = models.CharField(
        max_length=12, choices=Role.choices, default=Role.RETENUE,
        verbose_name='Rôle')
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='enfants', verbose_name='Variante parente')
    nom = models.CharField(max_length=255, verbose_name='Nom')
    params = models.JSONField(
        default=dict, blank=True, verbose_name="Paramètres d'entrée")
    #: Empreinte canonique de l'ENTRÉE (AOF29) — pilote la péremption.
    entree_hash = models.CharField(
        max_length=64, blank=True, default='', verbose_name="Empreinte d'entrée")
    #: Rangées EXPLICITES : ``[{"x0": .., "kit": "..", "modules": n}, …]``.
    resultat = models.JSONField(
        default=dict, blank=True, verbose_name='Résultat')
    #: Preuve : total_retenu, total_optimal, methode, pas_cm, nb_optima,
    #: marge_troncon_min, marge_bande_min, controles.
    preuve = models.JSONField(
        default=dict, blank=True, verbose_name='Preuve du calcul')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.BROUILLON,
        verbose_name='Statut')
    est_retenue = models.BooleanField(
        default=False, verbose_name='Variante retenue de la toiture')
    est_recommandee = models.BooleanField(
        default=False, verbose_name='Recommandée')
    score = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        verbose_name='Score')
    justification = models.TextField(
        blank=True, default='', verbose_name='Justification')
    version_moteur = models.CharField(
        max_length=40, blank=True, default='', verbose_name='Version du moteur')
    job = models.ForeignKey(
        'core.BackgroundJob', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='variantes_calepinage_ao', verbose_name='Job de calcul')

    class Meta:
        verbose_name = 'Variante de calepinage (AO)'
        verbose_name_plural = 'Variantes de calepinage (AO)'
        db_table = 'ao_variante_calepinage'
        ordering = ['toiture', 'role', '-score', 'id']
        constraints = [
            # UNE seule variante retenue par toiture — la contrainte est en
            # base, pas dans une vue : deux « retenues » rendraient le dossier
            # indéfendable.
            models.UniqueConstraint(
                fields=['toiture'], condition=models.Q(est_retenue=True),
                name='uniq_variante_retenue_par_toiture'),
        ]
        indexes = [
            models.Index(fields=['company', 'appel_offre']),
            models.Index(fields=['company', 'toiture', 'role']),
            models.Index(fields=['company', 'entree_hash']),
        ]

    def __str__(self):
        return f'{self.nom} [{self.get_role_display()}]'

    @property
    def total_modules(self):
        return (self.resultat or {}).get('total_modules', 0)

    @property
    def puissance_kwc(self):
        return (self.resultat or {}).get('kwc', 0)

    def raisons_de_non_publiabilite(self):
        """Les motifs, en clair, qui INTERDISENT de publier (AOF28).

        Liste vide = publiable. Chaque motif est une phrase française : c'est
        ce que l'utilisateur doit lire, pas un code d'erreur.
        """
        preuve = self.preuve or {}
        raisons = []
        retenu = preuve.get('total_retenu')
        optimal = preuve.get('total_optimal')
        if retenu is None or optimal is None:
            raisons.append(
                "La preuve est incomplète : sans total retenu ET total "
                "optimal, la capacité ne peut pas être qualifiée d'optimale."
            )
        elif Decimal(str(retenu)) < Decimal(str(optimal)):
            raisons.append(
                f'Le calepinage retenu ({retenu} modules) est inférieur à '
                f"l'optimum trouvé ({optimal} modules)."
            )
        marge_troncon = preuve.get('marge_troncon_min')
        if marge_troncon is not None and \
                Decimal(str(marge_troncon)) < self.MARGE_TRONCON_MIN_M:
            raisons.append(
                f'La marge minimale de tronçon ({marge_troncon} m) est sous '
                f'le seuil de {self.MARGE_TRONCON_MIN_M} m.'
            )
        marge_bande = preuve.get('marge_bande_min')
        if marge_bande is not None and \
                Decimal(str(marge_bande)) < self.MARGE_BANDE_MIN_M:
            raisons.append(
                f'La marge minimale de bande ({marge_bande} m) est sous le '
                f'seuil de {self.MARGE_BANDE_MIN_M} m.'
            )
        if self.pk and self.toiture_id:
            non_mesures = self.toiture.obstacles.filter(actif=True).exclude(
                provenance__in=list(ObstacleAO.PROVENANCES_ENGAGEABLES))
            if non_mesures.exists():
                reperes = ', '.join(
                    o.repere or f'#{o.pk}' for o in non_mesures[:5])
                raisons.append(
                    "Des obstacles NON MESURÉS sont encore actifs sur la "
                    f'toiture ({reperes}) : le plan ne peut pas être publié '
                    'comme engageant.'
                )
        return raisons


# ── FG223 — Bordereau des prix (BOQ) d'appel d'offres ──────────────────────

class BordereauPrix(TenantModel):
    """Bordereau des prix (BOQ) d'un AO (FG223), séparé du devis client.

    Chiffrage ligne à ligne de l'AO. Distinct du devis : sert au montage de
    l'offre de prix.

    AOF120 — bordereau v2. Le bordereau réel compte QUATRE sections
    (une par bâtiment + les prestations communes) et une trentaine d'items ;
    ses totaux sont RECALCULÉS côté serveur à chaque lecture — jamais des
    colonnes recopiées qui divergeraient à la première remise. La **clause de
    réserve** est OBLIGATOIRE sur un marché à prix unitaires : c'est elle qui
    encadre l'écart entre les quantités engagées et les quantités constatées à
    l'exécution.

    **NTMAR22 est SUPERSEDED** : aucun modèle ``LigneBordereauPrix`` n'est créé
    — ``LigneBordereau`` est ÉTENDU, sinon l'app porterait deux modèles de
    ligne de bordereau (test d'introspection dans ``test_bordereau_v2``).
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

    # ── AOF120 — révision, remise globale, TVA, clause de réserve ─────────
    #: Indice de révision du bordereau (A, B, C…) — deux bordereaux d'indices
    #: différents ne sont JAMAIS le même document.
    indice_revision = models.CharField(
        max_length=4, blank=True, default='A',
        verbose_name='Indice de révision')
    remise_globale_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Remise globale (%)')
    taux_tva_defaut = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('20.00'),
        verbose_name='Taux de TVA par défaut (%)')
    #: Un marché à prix unitaires engage des PRIX, pas des quantités fermes.
    marche_prix_unitaires = models.BooleanField(
        default=True, verbose_name='Marché à prix unitaires')
    clause_reserve = models.TextField(
        blank=True, default='',
        verbose_name='Clause de réserve (obligatoire en prix unitaires)')

    class Meta:
        verbose_name = 'Bordereau des prix (BOQ)'
        verbose_name_plural = 'Bordereaux des prix (BOQ)'
        db_table = 'compta_bordereauprix'
        ordering = ['-date_creation']

    def __str__(self):
        return f'BOQ {self.intitule} ({self.appel_offre.reference})'

    # ── Totaux RECALCULÉS côté serveur (jamais des colonnes recopiées) ────

    @property
    def sous_total_ht(self):
        """Somme des lignes, remises de LIGNE déduites, avant remise globale."""
        total = Decimal('0.00')
        for ligne in self.lignes.all():
            total += ligne.montant_ht
        return total.quantize(Decimal('0.01'))

    @property
    def montant_remise_globale(self):
        """Montant de la remise globale, DÉRIVÉ du sous-total."""
        taux = self.remise_globale_pct or Decimal('0')
        return (self.sous_total_ht * taux / Decimal('100')).quantize(
            Decimal('0.01'))

    @property
    def total_ht(self):
        """Sous-total HT moins la remise globale."""
        return (self.sous_total_ht - self.montant_remise_globale).quantize(
            Decimal('0.01'))

    @property
    def tva_par_taux(self):
        """Panier de TVA ``{taux: montant}`` — la remise globale est répartie
        au PRORATA de chaque ligne, sinon un bordereau à deux taux serait faux.
        """
        sous_total = self.sous_total_ht
        if not sous_total:
            return {}
        facteur = Decimal('1') - (
            self.remise_globale_pct or Decimal('0')) / Decimal('100')
        panier = {}
        for ligne in self.lignes.all():
            taux = ligne.taux_tva_effectif
            base = (ligne.montant_ht * facteur)
            panier[taux] = panier.get(taux, Decimal('0.00')) + (
                base * taux / Decimal('100'))
        return {taux: montant.quantize(Decimal('0.01'))
                for taux, montant in panier.items()}

    @property
    def total_tva(self):
        return sum(self.tva_par_taux.values(), Decimal('0.00')).quantize(
            Decimal('0.01'))

    @property
    def total_ttc(self):
        return (self.total_ht + self.total_tva).quantize(Decimal('0.01'))

    def raisons_de_non_conformite(self):
        """Motifs, en français, qui rendent le bordereau non remettable."""
        raisons = []
        if self.marche_prix_unitaires and not (self.clause_reserve or '').strip():
            raisons.append(
                "Marché à prix unitaires : la clause de réserve est "
                "obligatoire — sans elle, les quantités du bordereau sont "
                "lues comme un engagement ferme."
            )
        return raisons

    def clean(self):
        from django.core.exceptions import ValidationError

        raisons = self.raisons_de_non_conformite()
        if raisons:
            raise ValidationError({'clause_reserve': raisons})


class SectionBordereau(TenantModel):
    """Une SECTION du bordereau des prix (AOF120).

    Le bordereau réel se lit par section (une par bâtiment, plus les
    prestations communes) : sans sections, un total par bâtiment n'est pas
    vérifiable et la correspondance « quantités du bordereau = engagements des
    planches » devient une lecture à l'œil.
    """

    bordereau = models.ForeignKey(
        BordereauPrix,
        on_delete=models.CASCADE,  # on_delete: section fille d'un bordereau : aucune existence hors de lui
        related_name='sections',
        verbose_name='Bordereau',
    )
    numero = models.CharField(max_length=8, verbose_name='Numéro (A, B, C…)')
    libelle = models.CharField(max_length=200, verbose_name='Libellé')
    batiment = models.ForeignKey(
        BatimentAO,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sections_bordereau', verbose_name='Bâtiment',
    )
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')

    class Meta:
        verbose_name = 'Section de bordereau (AO)'
        verbose_name_plural = 'Sections de bordereau (AO)'
        db_table = 'ao_section_bordereau'
        ordering = ['bordereau', 'ordre', 'numero']
        constraints = [
            models.UniqueConstraint(
                fields=['bordereau', 'numero'],
                name='uniq_section_bordereau_numero'),
        ]

    def __str__(self):
        return f'{self.numero} — {self.libelle}'

    @property
    def total_ht(self):
        """Total HT de la section (lignes de la section uniquement)."""
        total = Decimal('0.00')
        for ligne in self.lignes.all():
            total += ligne.montant_ht
        return total.quantize(Decimal('0.01'))


class LigneBordereau(TenantModel):
    """Une ligne chiffrée d'un BOQ (FG223), étendue par AOF120.

    ``quantite_source`` + ``variante`` rendent VÉRIFIABLE EN MACHINE
    l'invariant « quantités du bordereau = engagements portés sur les
    planches » : une quantité issue du calepinage CITE la variante qui l'a
    produite. ``quantite_verrouillee`` protège une quantité arbitrée à la main
    d'un ré-alignement automatique.
    """

    class QuantiteSource(models.TextChoices):
        CALEPINAGE = 'calepinage', 'Calepinage (variante)'
        MANUELLE = 'manuelle', 'Saisie manuelle'
        CATALOGUE = 'catalogue', 'Catalogue'
        ACHETEUR = 'acheteur', "Imposée par l'acheteur"

    class TauxTVA(models.TextChoices):
        DIX = '10.00', '10 %'
        VINGT = '20.00', '20 %'

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
    section = models.ForeignKey(
        SectionBordereau,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lignes', verbose_name='Section',
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

    # ── AOF120 — TVA, remise, traçabilité de la quantité ─────────────────
    taux_tva = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        choices=TauxTVA.choices,
        verbose_name='Taux de TVA (%) — vide = taux du bordereau')
    remise_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Remise de ligne (%)')
    batiment = models.ForeignKey(
        BatimentAO,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lignes_bordereau', verbose_name='Bâtiment',
    )
    #: String-FK catalogue (même raison qu'AOF118 : le contrat interdit les
    #: IMPORTS de ``apps.stock.models``, pas les FK par chaîne).
    produit = models.ForeignKey(
        'stock.Produit',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lignes_bordereau_ao', verbose_name='Produit',
    )
    quantite_source = models.CharField(
        max_length=12, choices=QuantiteSource.choices,
        default=QuantiteSource.MANUELLE,
        verbose_name='Origine de la quantité')
    #: La variante qui a PRODUIT cette quantité (obligatoire quand
    #: ``quantite_source == calepinage`` — vérifié par le service).
    variante = models.ForeignKey(
        VarianteCalepinage,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lignes_bordereau', verbose_name='Variante source',
    )
    quantite_verrouillee = models.BooleanField(
        default=False, verbose_name='Quantité verrouillée')
    #: AOF135 — le CAPEX « hors stockage » de la simulation client se DÉRIVE
    #: du bordereau : il faut donc savoir quelle ligne EST du stockage. Un
    #: booléen porté par la ligne évite de deviner sur la désignation (le
    #: chercher-remplacer que tout ce groupe combat).
    est_stockage = models.BooleanField(
        default=False, verbose_name='Ligne de stockage (batteries)')

    class Meta:
        verbose_name = 'Ligne de bordereau'
        verbose_name_plural = 'Lignes de bordereau'
        db_table = 'compta_lignebordereau'
        ordering = ['bordereau', 'numero']

    def __str__(self):
        return f'{self.numero}. {self.designation}'

    @property
    def taux_tva_effectif(self):
        """Taux de la ligne, ou celui du bordereau en repli."""
        if self.taux_tva is not None:
            return Decimal(self.taux_tva)
        return Decimal(self.bordereau.taux_tva_defaut or Decimal('20.00'))

    @property
    def montant_ht(self):
        """``quantité × PU × (1 − remise/100)`` — remise de LIGNE incluse."""
        brut = (self.quantite or Decimal('0')) * (
            self.prix_unitaire or Decimal('0'))
        remise = self.remise_pct or Decimal('0')
        return brut * (Decimal('1') - remise / Decimal('100'))

    @property
    def montant_tva(self):
        return (self.montant_ht * self.taux_tva_effectif
                / Decimal('100')).quantize(Decimal('0.01'))

    def raisons_de_non_tracabilite(self):
        """Motifs, en français, qui rendent la quantité non traçable."""
        raisons = []
        if self.quantite_source == self.QuantiteSource.CALEPINAGE \
                and not self.variante_id:
            raisons.append(
                f'Ligne {self.numero} « {self.designation} » : quantité '
                "annoncée issue du calepinage mais AUCUNE variante n'est "
                'citée — la correspondance « bordereau = planches » ne peut '
                'pas être vérifiée.'
            )
        return raisons


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

    # ── AOF32 — L'ouverture des plis, enfin exploitée ──────────────────────
    #
    # Ce modèle existait et n'était JAMAIS écrit : l'app s'arrêtait au dépôt,
    # alors que la valeur récurrente est en AVAL — classement, attributaire,
    # prix du moins-disant, motif de perte. C'est cette donnée qui alimentera
    # la bibliothèque de prix et le KPI de taux de réussite.
    date_ouverture = models.DateField(
        null=True, blank=True, verbose_name="Date d'ouverture des plis")
    nombre_plis = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Nombre de plis reçus')
    #: Classement complet : ``[{"rang": 1, "soumissionnaire": "…",
    #: "montant": 4200000.00}, …]``. Un tableau, pas des colonnes : le nombre
    #: de concurrents n'est pas connu à l'avance.
    classement = models.JSONField(
        default=list, blank=True, verbose_name='Classement des plis')
    notre_rang = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Notre rang')

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

    @property
    def ecart_prix_pct(self):
        """AOF32 — écart en POURCENTAGE du prix retenu.

        C'est la forme comparable d'un dossier à l'autre : « 180 000 MAD de
        trop » ne veut rien dire sans le montant du marché.
        """
        if not self.prix_gagnant:
            return None
        ecart = self.ecart_prix
        if ecart is None:
            return None
        return (ecart / Decimal(self.prix_gagnant) * Decimal('100')).quantize(
            Decimal('0.01'))


# ══════════════════════════════════════════════════════════════════════════
# W6 — FABRIQUE DOCUMENTAIRE : le dossier de dépôt et ses pièces
# ══════════════════════════════════════════════════════════════════════════

# ── AOF115 — ``DossierAO`` sur le kit ``core/documents.py`` ────────────────

class DossierAO(DocumentMetier):
    """Le DOSSIER DE DÉPÔT d'un appel d'offres, sur le kit document (AOF115).

    Le kit ``core/documents.py`` est explicitement « réservé aux NOUVEAUX
    types de documents » : c'est le socle LÉGITIME ici. Aucun rétrofit
    Devis/Facture/BonCommande/Avoir n'est fait ni permis (règle #4) — ceux-là
    gardent leurs chemins propres. ``core/documents.py`` reste un MODULE (un
    seul fichier), il n'est pas transformé en paquet.

    Ce que le kit apporte SANS une ligne recopiée :

    * ``statut`` propre à cette classe (injecté par ``DocumentMetierMeta``
      depuis l'énumération ``Statut`` ci-dessous) ;
    * ``TRANSITIONS`` DÉCLARATIVE — la seule description du cycle ; une
      transition absente de la table est refusée par
      ``core.documents.changer_statut`` ;
    * le socle multi-société ``TenantModel`` (FK ``company`` + horodatage) ;
    * la référence ``AODOS-YYYYMM-0001`` via ``core.numbering`` (jamais
      ``count()+1``) ;
    * le chatter générique ``records`` par le viewset (jamais une classe
      ``*Activity`` maison) et le hook PDF
      ``core.documents.render_document_pdf``.

    À distinguer de ``DossierSoumission`` (FG225), la checklist administrative
    HISTORIQUE : celle-ci porte les pièces déjà en base et n'est pas remplacée.
    Une ``PieceDossierAO`` peut POINTER une ``PieceSoumission`` legacy plutôt
    que d'en recréer un jumeau (cf. la contrainte d'exclusivité ci-dessous).
    """

    class Statut(models.TextChoices):
        MONTAGE = 'montage', 'Montage'
        EN_CONSTITUTION = 'en_constitution', 'En constitution'
        CONTROLE = 'controle', 'Contrôle'
        PRET_A_DEPOSER = 'pret_a_deposer', 'Prêt à déposer'
        DEPOSE = 'depose', 'Déposé'
        CLOS = 'clos', 'Clos'

    STATUT_INITIAL = 'montage'

    #: Le graphe d'états, DÉCLARATIF. Un retour en arrière reste possible tant
    #: que le pli n'est pas déposé — un dossier réel repasse en constitution
    #: dès qu'une pièce change. Après ``depose``, seul ``clos`` subsiste :
    #: l'histoire d'un pli remis ne se réécrit pas.
    TRANSITIONS = {
        Statut.MONTAGE: {Statut.EN_CONSTITUTION, Statut.CLOS},
        Statut.EN_CONSTITUTION: {
            Statut.CONTROLE, Statut.MONTAGE, Statut.CLOS},
        Statut.CONTROLE: {
            Statut.PRET_A_DEPOSER, Statut.EN_CONSTITUTION, Statut.CLOS},
        Statut.PRET_A_DEPOSER: {
            Statut.DEPOSE, Statut.EN_CONSTITUTION, Statut.CLOS},
        Statut.DEPOSE: {Statut.CLOS},
        Statut.CLOS: set(),
    }

    #: Préfixe de numérotation ``core.numbering`` — ``AODOS-YYYYMM-0001``.
    PREFIXE_REFERENCE = 'AODOS'

    appel_offre = models.OneToOneField(
        AppelOffre,
        on_delete=models.CASCADE,  # on_delete: dossier fils d'un AO : aucune existence hors de son appel d'offres
        related_name='dossier_ao',
        verbose_name="Appel d'offres",
    )
    reference = models.CharField(
        max_length=40, blank=True, default='', verbose_name='Référence')
    intitule = models.CharField(
        max_length=200, default='Dossier de dépôt', verbose_name='Intitulé')
    date_depot = models.DateField(
        null=True, blank=True, verbose_name='Date de dépôt effectif')

    class Meta:
        verbose_name = 'Dossier de dépôt (AO)'
        verbose_name_plural = 'Dossiers de dépôt (AO)'
        db_table = 'ao_dossier'
        ordering = ['-created_at', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                condition=~models.Q(reference=''),
                name='uniq_dossier_ao_reference'),
        ]
        indexes = [
            models.Index(fields=['company', 'statut']),
        ]

    def __str__(self):
        return (f'{self.reference or self.intitule} — '
                f'{self.appel_offre.reference}')

    # ── Complétude DÉRIVÉE des pièces obligatoires ────────────────────────

    def pieces_obligatoires_manquantes(self):
        """Les pièces obligatoires encore ABSENTES (queryset, jamais un drapeau).

        La complétude d'un dossier ne se stocke pas : une colonne ``complet``
        deviendrait fausse à la première pièce ajoutée, et c'est précisément
        l'information la plus consultée avant un dépôt.
        """
        return self.pieces.filter(obligatoire=True, presente=False)

    @property
    def complet(self):
        """Vrai si AUCUNE pièce obligatoire ne manque.

        Un dossier SANS aucune pièce obligatoire n'est pas « complet » : il
        n'est pas encore constitué (même sémantique que
        ``DossierSoumission.complet``, FG225).
        """
        if not self.pieces.filter(obligatoire=True).exists():
            return False
        return not self.pieces_obligatoires_manquantes().exists()

    @property
    def taux_completude(self):
        """Part des pièces obligatoires présentes, en % (0 si aucune)."""
        obligatoires = self.pieces.filter(obligatoire=True).count()
        if not obligatoires:
            return Decimal('0.00')
        presentes = self.pieces.filter(
            obligatoire=True, presente=True).count()
        return (Decimal(presentes) / Decimal(obligatoires)
                * Decimal('100')).quantize(Decimal('0.01'))

    def raisons_de_non_depot(self):
        """Motifs, en français, qui INTERDISENT de passer « prêt à déposer ».

        Liste vide = la porte s'ouvre. Chaque motif est une phrase lisible :
        c'est ce que l'utilisateur doit lire, pas un code d'erreur.
        """
        raisons = []
        manquantes = list(self.pieces_obligatoires_manquantes())
        if manquantes:
            libelles = ', '.join(
                f'{p.code} {p.libelle}'.strip() for p in manquantes[:8])
            raisons.append(
                f'{len(manquantes)} pièce(s) obligatoire(s) manquante(s) : '
                f'{libelles}.'
            )
        elif not self.pieces.filter(obligatoire=True).exists():
            raisons.append(
                "Le dossier ne porte aucune pièce obligatoire : il n'est pas "
                'constitué.'
            )
        # AOF136 — une case obligatoire OUVERTE de la checklist partenaire
        # bloque le dépôt : la checklist est un OBJET SUIVI, pas un document
        # mort qu'on relit en diagonale la veille de la remise.
        ouvertes = list(self.lignes_checklist.filter(
            obligatoire=True, faite=False))
        if ouvertes:
            libelles = ', '.join(
                f'{ligne.get_bloc_display()} — {ligne.libelle}'
                for ligne in ouvertes[:8])
            raisons.append(
                f'{len(ouvertes)} point(s) obligatoire(s) de la checklist '
                f'partenaire encore ouvert(s) : {libelles}.'
            )
        # AOF137 — une pièce administrative EXPIRÉE À LA DATE DE REMISE DES
        # PLIS (jamais « à la date du jour ») est bloquante, et le motif CITE
        # sa date : c'est ce que l'utilisateur doit pouvoir vérifier.
        raisons.extend(self.raisons_pieces_administratives())
        return raisons

    @property
    def date_reference_controle(self):
        """La SEULE date qui compte : celle de la remise/ouverture des plis.

        Ouverture des plis si connue, sinon date limite de remise. ``None``
        quand aucune n'est saisie — on ne contrôle pas contre une date
        inventée (une date fausse est pire qu'une absence de date).
        """
        ao = self.appel_offre
        return ao.date_ouverture_plis or ao.date_limite

    def raisons_pieces_administratives(self):
        """Pièces administratives expirées à la date de remise (AOF137)."""
        reference = self.date_reference_controle
        if reference is None:
            return []
        raisons = []
        for piece in self.pieces_administratives.filter(actif=True):
            if piece.est_expiree_a(reference):
                raisons.append(
                    f'{piece.get_type_piece_display()} « {piece.libelle} » : '
                    f'émise le {piece.date_emission}, expirée le '
                    f'{piece.date_expiration} — donc EXPIRÉE à la date de '
                    f'remise des plis ({reference}).'
                )
        return raisons


class PieceDossierAO(TenantModel):
    """Une pièce du dossier de dépôt (AOF115).

    Une pièce pointe SOIT un artefact GÉNÉRÉ par la fabrique (stocké via
    ``records.Attachment`` — aucun nouveau ``FileField``, le garde
    ``apps/records/platform_guards.py`` gèle ``apps/ao/models.py`` à
    ``{"fichier": 1}``), SOIT une ``PieceSoumission`` administrative LEGACY —
    jamais les deux : un doublon ferait exister deux versions de la même pièce
    dans le même dossier, exactement la classe de défaut « fichier frère
    périmé » que ce groupe combat. La contrainte est en BASE, pas dans une vue.
    """

    class TypePiece(models.TextChoices):
        GENEREE = 'generee', 'Générée par la fabrique'
        FOURNIE = 'fournie', 'Fournie (partenaire / acheteur)'

    class Visibilite(models.TextChoices):
        CLIENT = 'client', "Client (remise au maître d'ouvrage)"
        INTERNE = 'interne', 'Interne'
        DIRECTEUR = 'directeur', 'Directeur'

    dossier = models.ForeignKey(
        DossierAO,
        on_delete=models.CASCADE,  # on_delete: piece fille d'un dossier : aucune existence hors de lui
        related_name='pieces',
        verbose_name='Dossier',
    )
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    code = models.CharField(max_length=20, verbose_name='Code de la pièce')
    libelle = models.CharField(max_length=200, verbose_name='Libellé')
    type_piece = models.CharField(
        max_length=8, choices=TypePiece.choices, default=TypePiece.GENEREE,
        verbose_name='Type de pièce')
    obligatoire = models.BooleanField(default=True, verbose_name='Obligatoire')
    presente = models.BooleanField(default=False, verbose_name='Présente')
    visibilite = models.CharField(
        max_length=10, choices=Visibilite.choices, default=Visibilite.CLIENT,
        verbose_name='Visibilité')
    #: Artefact GÉNÉRÉ (MinIO via ``records.Attachment``).
    attachment = models.ForeignKey(
        'records.Attachment',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pieces_dossier_ao', verbose_name='Artefact (MinIO)')
    #: Pièce administrative HISTORIQUE (FG225) réutilisée telle quelle.
    piece_soumission = models.ForeignKey(
        PieceSoumission,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pieces_dossier_ao',
        verbose_name='Pièce administrative (legacy)')
    signee = models.BooleanField(
        default=False,
        verbose_name='Signée / paraphée (pointage humain)',
        help_text=(
            "NON-OBJECTIF v1 ACTÉ : PAS de signature électronique. Le dépôt "
            "marocain visé est PAPIER, en 2 exemplaires, avec paraphe "
            "manuscrit — ce booléen est donc un POINTAGE HUMAIN, jamais un "
            "état cryptographique. Le jour où la signature devient un besoin, "
            "elle se branchera sur ged.ChampSignature (déjà en production) et "
            "sur AUCUN mécanisme local."
        ),
    )
    motif = models.TextField(
        blank=True, default='', verbose_name='Motif / commentaire')
    #: AOF149 — ce qui n'est pas FABRIQUÉ par la fabrique n'est jamais présumé
    #: vert. Les invariants d'AOF146 ne s'appliquent qu'aux pièces produites
    #: ici : dès qu'une pièce est fournie à la main (acte d'engagement au
    #: modèle de l'acheteur, attestations, caution bancaire, checklist remplie
    #: par le partenaire), elle échappe aux contrôles. Un dossier « tout vert »
    #: dont un tiers n'a jamais été vérifié est plus dangereux qu'un dossier
    #: orange : elle est donc marquée HORS CONTRÔLE, avec un motif OBLIGATOIRE.
    controlee = models.CharField(
        max_length=14, default='fabriquee',
        choices=[
            ('fabriquee', 'Fabriquée (contrôlée)'),
            ('hors_controle', 'Fournie — HORS CONTRÔLE'),
        ],
        verbose_name='Régime de contrôle')
    #: AOF146 — empreinte du CONTEXTE au moment où l'artefact a été produit.
    #: Une pièce dont l'empreinte diverge de l'empreinte courante du dossier
    #: est PÉRIMÉE : c'est le défaut réel du « LISEZ-MOI figé » resté dans le
    #: dépôt alors que le pack avait été régénéré.
    empreinte_source = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='Empreinte du contexte à la production')

    class Meta:
        verbose_name = 'Pièce du dossier de dépôt (AO)'
        verbose_name_plural = 'Pièces du dossier de dépôt (AO)'
        db_table = 'ao_piece_dossier'
        ordering = ['dossier', 'ordre', 'code']
        constraints = [
            models.UniqueConstraint(
                fields=['dossier', 'code'],
                name='uniq_piece_dossier_ao_code'),
            # JAMAIS un doublon : une pièce est générée OU legacy, pas les deux.
            models.CheckConstraint(
                condition=(
                    models.Q(attachment__isnull=True)
                    | models.Q(piece_soumission__isnull=True)
                ),
                name='piece_dossier_ao_source_unique'),
        ]
        indexes = [
            models.Index(fields=['company', 'dossier', 'visibilite']),
        ]

    def __str__(self):
        etat = 'présente' if self.presente else 'manquante'
        return f'{self.code} {self.libelle} ({etat})'

    #: AOF149 — les deux régimes de contrôle, nommés une seule fois.
    FABRIQUEE = 'fabriquee'
    HORS_CONTROLE = 'hors_controle'

    @property
    def source(self):
        """« generee » / « legacy » / « aucune » — d'où vient le fichier."""
        if self.attachment_id:
            return 'generee'
        if self.piece_soumission_id:
            return 'legacy'
        return 'aucune'

    @property
    def etat_controle(self):
        """« manquante » / « hors_controle » / « verte » (AOF149).

        Une pièce FOURNIE n'apparaît JAMAIS « verte » : le vert veut dire
        « vérifié par la fabrique », et une pièce qu'elle n'a pas produite n'a
        pas été vérifiée. Elle est « hors contrôle », avec son motif.
        """
        if not self.presente:
            return 'manquante'
        if self.controlee == self.HORS_CONTROLE:
            return 'hors_controle'
        return 'verte'

    def raisons_hors_controle(self):
        """Motif manquant sur une pièce hors contrôle (liste, jamais None)."""
        if self.controlee != self.HORS_CONTROLE:
            return []
        if (self.motif or '').strip():
            return []
        return [(
            f'Pièce {self.code} « {self.libelle} » déclarée HORS CONTRÔLE '
            f"sans motif : une pièce que la fabrique n'a pas produite doit "
            f'dire POURQUOI elle échappe aux contrôles.'
        )]

    def clean(self):
        from django.core.exceptions import ValidationError

        raisons = self.raisons_hors_controle()
        if raisons:
            raise ValidationError({'motif': raisons})


# ── AOF116 — Gabarits de pack + bibliothèque de sections ───────────────────

class ModelePack(TenantModel):
    """Gabarit de PACK : la liste ORDONNÉE des pièces d'un dossier (AOF116).

    Le pack réel d'un dépôt solaire marocain compte neuf pièces (00 checklist
    partenaire … 08 dossier administratif). Les décrire en DONNÉES plutôt qu'en
    code fait qu'ajouter une pièce est une ligne de seed, pas une release :
    c'est aussi la seule façon de rendre le sommaire (AOF139) cohérent avec le
    manifeste RÉEL sans intervention.
    """

    code = models.CharField(max_length=40, verbose_name='Code du modèle')
    libelle = models.CharField(max_length=200, verbose_name='Libellé')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    actif = models.BooleanField(default=True, verbose_name='Actif')

    class Meta:
        verbose_name = 'Modèle de pack (AO)'
        verbose_name_plural = 'Modèles de pack (AO)'
        db_table = 'ao_modele_pack'
        ordering = ['code']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'], name='uniq_modele_pack_code'),
        ]

    def __str__(self):
        return f'{self.code} — {self.libelle}'


class PieceModele(TenantModel):
    """Une pièce DÉCLARÉE d'un gabarit de pack (AOF116).

    ``generateur`` nomme la fabrique qui produit la pièce (jamais un chemin de
    fichier ni un import) ; ``gabarit`` porte le corps à placeholders
    ``{{ … }}`` rendu par ``core.templating.rendre`` — fondation SANS ``eval``,
    déjà en production. **Aucun littéral chiffré n'est permis dans un
    gabarit** : un nombre écrit à la main est un vestige qui survit à la
    prochaine cascade de prix (le défaut « justification 2 800 contre bordereau
    à 2 600 » de la session réelle). Le contrôle vit dans
    ``apps.ao.fabrique.gabarits``.
    """

    class Format(models.TextChoices):
        PDF = 'pdf', 'PDF'
        PDF_A3 = 'pdf_a3', 'PDF A3 (planches)'
        XLSX = 'xlsx', 'Classeur XLSX'
        DOCX = 'docx', 'Document DOCX éditable'
        ZIP = 'zip', 'Archive ZIP'

    modele = models.ForeignKey(
        ModelePack,
        on_delete=models.CASCADE,  # on_delete: piece de gabarit : aucune existence hors de son modele
        related_name='pieces',
        verbose_name='Modèle de pack',
    )
    code = models.CharField(max_length=20, verbose_name='Code de la pièce')
    libelle = models.CharField(max_length=200, verbose_name='Libellé')
    generateur = models.CharField(
        max_length=60, blank=True, default='',
        verbose_name='Générateur (nom logique)')
    format = models.CharField(
        max_length=8, choices=Format.choices, default=Format.PDF,
        verbose_name='Format')
    obligatoire = models.BooleanField(default=True, verbose_name='Obligatoire')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    visibilite = models.CharField(
        max_length=10, choices=PieceDossierAO.Visibilite.choices,
        default=PieceDossierAO.Visibilite.CLIENT, verbose_name='Visibilité')
    gabarit = models.TextField(
        blank=True, default='',
        verbose_name='Gabarit (placeholders {{ … }}, aucun chiffre littéral)')

    class Meta:
        verbose_name = 'Pièce de gabarit (AO)'
        verbose_name_plural = 'Pièces de gabarit (AO)'
        db_table = 'ao_piece_modele'
        ordering = ['modele', 'ordre', 'code']
        constraints = [
            models.UniqueConstraint(
                fields=['modele', 'code'], name='uniq_piece_modele_code'),
        ]

    def __str__(self):
        return f'{self.code} {self.libelle}'


class SectionMemoire(TenantModel):
    """Une section COMPOSABLE de mémoire technique (AOF116, rendue en AOF133).

    Le mémoire n'est pas un texte libre : c'est une suite de sections dont le
    corps porte des placeholders. Sans cela, une bascule d'équipement redevient
    un chercher-remplacer sur ~90 paragraphes — les 12 remplacements de
    désignation de la bascule batterie ne sont fiables que si la désignation
    n'existe qu'à UN endroit.
    """

    code = models.CharField(max_length=40, verbose_name='Code')
    titre = models.CharField(max_length=200, verbose_name='Titre')
    corps = models.TextField(
        blank=True, default='',
        verbose_name='Corps (placeholders {{ … }})')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    #: Conditions d'inclusion DÉCLARATIVES : ``{"variable": valeur_attendue}``
    #: évaluées contre le contexte du dossier (jamais du code exécuté).
    conditions_inclusion = models.JSONField(
        default=dict, blank=True, verbose_name="Conditions d'inclusion")
    actif = models.BooleanField(default=True, verbose_name='Active')

    class Meta:
        verbose_name = 'Section de mémoire (AO)'
        verbose_name_plural = 'Sections de mémoire (AO)'
        db_table = 'ao_section_memoire'
        ordering = ['ordre', 'code']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'], name='uniq_section_memoire_code'),
        ]

    def __str__(self):
        return f'{self.code} — {self.titre}'


# ── AOF118 — ``EquipementAO`` : string-FK catalogue + SNAPSHOT figé ────────

class EquipementAO(TenantModel):
    """Un équipement engagé par le dossier, avec son SNAPSHOT figé (AOF118).

    Pourquoi un snapshot. Le catalogue produit est re-seedé régulièrement
    (prix, archivage de placeholders, fiches). **Sans snapshot, un re-seed
    ferait bouger la désignation d'un matériel dans un dossier DÉJÀ DÉPOSÉ** —
    la version numérique du « fichier frère périmé », le défaut n°1 de la
    session réelle. La désignation, la marque, la référence constructeur et les
    caractéristiques sont donc COPIÉES au moment de l'engagement et ne bougent
    plus jamais toutes seules ; seule une bascule d'équipement NOMMÉE (AOF141)
    les change, en une transaction.

    Pourquoi une string-FK. ``produit`` pointe ``'stock.Produit'`` par CHAÎNE :
    le contrat import-linter ``ao-models-decoupled`` interdit les IMPORTS de
    ``apps.stock.models``, pas les FK par chaîne — et une FK vaut mieux qu'un
    entier opaque (intégrité référentielle, ``PROTECT`` contre la suppression
    d'un produit encore engagé). Toute lecture d'ATTRIBUT du produit passe par
    ``apps.stock.selectors``, jamais par un import de ses modèles.

    Aucun champ de COÛT ici : ni ``prix_achat``, ni marge, ni bénéfice.
    L'économie vit dans une table SÉPARÉE derrière ``ao_rentabilite_voir``.
    """

    class Role(models.TextChoices):
        MODULE = 'module', 'Module photovoltaïque'
        ONDULEUR = 'onduleur', 'Onduleur'
        BATTERIE = 'batterie', 'Batterie / stockage'
        COFFRET_DC = 'coffret_dc', 'Coffret DC'
        COFFRET_AC = 'coffret_ac', 'Coffret AC'
        TGPV = 'tgpv', 'TGPV'
        CABLE = 'cable', 'Câble'
        STRUCTURE = 'structure', 'Structure de pose'
        EMS = 'ems', 'EMS / supervision'
        STATION_METEO = 'station_meteo', 'Station météo'
        AFFICHEUR = 'afficheur', 'Afficheur'
        VARIATEUR = 'variateur', 'Variateur'

    appel_offre = models.ForeignKey(
        AppelOffre,
        on_delete=models.CASCADE,  # on_delete: equipement fils d'un AO : aucune existence hors de son appel d'offres
        related_name='equipements',
        verbose_name="Appel d'offres",
    )
    batiment = models.ForeignKey(
        BatimentAO,
        on_delete=models.CASCADE,  # on_delete: equipement affecte a un batiment : suit sa suppression
        null=True, blank=True,
        related_name='equipements', verbose_name='Bâtiment',
    )
    role = models.CharField(
        max_length=14, choices=Role.choices, verbose_name='Rôle')
    #: String-FK vers le catalogue — AUTORISÉE (le contrat interdit les
    #: IMPORTS de ``apps.stock.models``, pas les FK par chaîne). ``PROTECT`` :
    #: un produit engagé dans un dossier ne se supprime pas en silence.
    produit = models.ForeignKey(
        'stock.Produit',
        on_delete=models.PROTECT,  # on_delete: un produit engage dans un dossier depose ne se supprime jamais
        null=True, blank=True,
        related_name='equipements_ao', verbose_name='Produit du catalogue',
    )

    # ── SNAPSHOT FIGÉ (copié à l'engagement, jamais recalculé) ────────────
    designation = models.CharField(
        max_length=255, verbose_name='Désignation (figée)')
    marque = models.CharField(
        max_length=100, blank=True, default='', verbose_name='Marque (figée)')
    reference_constructeur = models.CharField(
        max_length=120, blank=True, default='',
        verbose_name='Référence constructeur (figée)')
    caracteristiques = models.JSONField(
        default=dict, blank=True,
        verbose_name='Caractéristiques (figées)')
    quantite = models.DecimalField(
        max_digits=12, decimal_places=3, default=Decimal('0.000'),
        verbose_name='Quantité')
    unite = models.CharField(
        max_length=20, blank=True, default='U', verbose_name='Unité')
    #: Fiche technique constructeur — via ``records.Attachment`` (aucun
    #: nouveau ``FileField`` : le garde plateforme gèle ce fichier).
    fiche_technique = models.ForeignKey(
        'records.Attachment',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='equipements_ao', verbose_name='Fiche technique')
    #: Traçabilité d'une bascule : le NOUVEL équipement pointe l'ANCIEN.
    remplace = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='remplace_par', verbose_name='Remplace')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    #: Horodatage du gel du snapshot — ce que le dossier a VU du catalogue.
    snapshot_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Snapshot figé le')

    class Meta:
        verbose_name = 'Équipement engagé (AO)'
        verbose_name_plural = 'Équipements engagés (AO)'
        db_table = 'ao_equipement'
        ordering = ['appel_offre', 'role', 'id']
        indexes = [
            models.Index(fields=['company', 'appel_offre', 'role']),
            models.Index(fields=['company', 'actif']),
        ]

    def __str__(self):
        return f'{self.get_role_display()} — {self.designation}'

    @property
    def puissance_totale_w(self):
        """Puissance cumulée, DÉRIVÉE du snapshot (None si non renseignée).

        Lit ``caracteristiques['puissance_w']`` — une caractéristique FIGÉE :
        un re-seed du catalogue ne peut donc pas déplacer la puissance d'un
        dossier déjà déposé.
        """
        puissance = (self.caracteristiques or {}).get('puissance_w')
        if puissance in (None, ''):
            return None
        return Decimal(str(puissance)) * (self.quantite or Decimal('0'))


# ── AOF135 — Simulation de rentabilité : PIÈCE CLIENT, sans AUCUN coût ─────

class SimulationRentabilite(TenantModel):
    """Simulation de rentabilité remise au maître d'ouvrage (AOF135).

    **Objet DISTINCT de l'économie directeur (AOF157).** Les fusionner « parce
    que ça parle de rentabilité » est le chemin le plus court vers la fuite de
    marge : cette pièce est CLIENT, elle ne porte donc AUCUN coût de revient,
    AUCUNE marge, AUCUN bénéfice. Un test d'introspection le vérifie.

    Rien n'est saisi deux fois : la puissance vient du CALEPINAGE (variantes
    retenues), le CAPEX vient du BORDEREAU (total TTC, et total TTC hors
    lignes de stockage). Ne restent en paramètres que ce qui ne se dérive pas :
    le productible spécifique du site (avec sa provenance CITÉE), le tarif,
    l'inflation, la dégradation annuelle et le taux d'actualisation.

    ``source_hash`` fige l'empreinte des entrées : une simulation dont
    l'empreinte ne correspond plus au dossier est PÉRIMÉE, jamais « à peu près
    juste ».
    """

    appel_offre = models.OneToOneField(
        AppelOffre,
        on_delete=models.CASCADE,  # on_delete: simulation fille d'un AO : aucune existence hors de lui
        related_name='simulation_rentabilite',
        verbose_name="Appel d'offres",
    )
    bordereau = models.ForeignKey(
        BordereauPrix,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='simulations', verbose_name='Bordereau source du CAPEX',
    )
    duree_annees = models.PositiveSmallIntegerField(
        default=25, verbose_name='Durée de la simulation (ans)')
    #: Productible SPÉCIFIQUE du site, en kWh par kWc et par an. Sa provenance
    #: est CITÉE (``productible_source``) : un productible sans source n'est
    #: pas défendable devant un maître d'ouvrage.
    productible_kwh_par_kwc_an = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Productible spécifique (kWh/kWc/an)')
    productible_source = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Source du productible')
    tarif_kwh = models.DecimalField(
        max_digits=8, decimal_places=4, default=Decimal('0.0000'),
        verbose_name='Tarif du kWh évité (MAD)')
    inflation_tarif_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Inflation annuelle du tarif (%)')
    degradation_annuelle_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.50'),
        verbose_name='Dégradation annuelle des modules (%)')
    taux_actualisation_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        verbose_name="Taux d'actualisation (%)")
    part_autoconsommee_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('100.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Part autoconsommée (%)')
    source_hash = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='Empreinte des entrées')

    class Meta:
        verbose_name = 'Simulation de rentabilité (AO)'
        verbose_name_plural = 'Simulations de rentabilité (AO)'
        db_table = 'ao_simulation_rentabilite'
        ordering = ['appel_offre']

    def __str__(self):
        return f'Simulation {self.duree_annees} ans — {self.appel_offre.reference}'

    # ── Grandeurs DÉRIVÉES (jamais saisies deux fois) ────────────────────

    @property
    def puissance_kwc(self):
        """Puissance retenue, somme des variantes RETENUES (calepinage)."""
        total = Decimal('0.000')
        for variante in self.appel_offre.variantes_calepinage.filter(
                est_retenue=True):
            total += Decimal(str(variante.puissance_kwc or 0))
        return total

    @property
    def productible_kwh_an(self):
        """Productible de la première année — puissance × productible spécifique."""
        return (self.puissance_kwc
                * (self.productible_kwh_par_kwc_an or Decimal('0')))

    @property
    def economie_annuelle_initiale(self):
        """Économie de la première année (MAD), part autoconsommée incluse."""
        part = (self.part_autoconsommee_pct or Decimal('0')) / Decimal('100')
        return (self.productible_kwh_an * (self.tarif_kwh or Decimal('0'))
                * part).quantize(Decimal('0.01'))

    @property
    def capex_total(self):
        """CAPEX TOTAL = montant TTC du bordereau (aucun coût de revient)."""
        if self.bordereau_id is None:
            return Decimal('0.00')
        return self.bordereau.total_ttc

    @property
    def capex_hors_stockage(self):
        """CAPEX hors stockage = TTC du bordereau moins les lignes stockage."""
        if self.bordereau_id is None:
            return Decimal('0.00')
        facteur = Decimal('1') - (
            self.bordereau.remise_globale_pct or Decimal('0')) / Decimal('100')
        stockage_ttc = Decimal('0.00')
        for ligne in self.bordereau.lignes.filter(est_stockage=True):
            ht = ligne.montant_ht * facteur
            stockage_ttc += ht * (
                Decimal('1') + ligne.taux_tva_effectif / Decimal('100'))
        return (self.capex_total - stockage_ttc).quantize(Decimal('0.01'))

    def _annee(self, rang):
        """Grandeurs de l'année ``rang`` (1-indexée), sans effet de bord."""
        degradation = (Decimal('1') - (
            self.degradation_annuelle_pct or Decimal('0')) / Decimal('100')
        ) ** (rang - 1)
        inflation = (Decimal('1') + (
            self.inflation_tarif_pct or Decimal('0')) / Decimal('100')
        ) ** (rang - 1)
        economie = self.economie_annuelle_initiale * degradation * inflation
        actualisation = (Decimal('1') + (
            self.taux_actualisation_pct or Decimal('0')) / Decimal('100')
        ) ** rang
        return {
            'annee': rang,
            'productible_kwh': (self.productible_kwh_an * degradation
                                ).quantize(Decimal('0.01')),
            'economie': economie.quantize(Decimal('0.01')),
            'economie_actualisee': (economie / actualisation).quantize(
                Decimal('0.01')),
        }

    @property
    def tableau_annuel(self):
        """Le tableau année par année — la donnée du classeur et du PDF."""
        lignes = []
        cumul = Decimal('0.00')
        cumul_actualise = Decimal('0.00')
        for rang in range(1, int(self.duree_annees or 0) + 1):
            annee = self._annee(rang)
            cumul += annee['economie']
            cumul_actualise += annee['economie_actualisee']
            annee['economie_cumulee'] = cumul
            annee['economie_cumulee_actualisee'] = cumul_actualise
            lignes.append(annee)
        return lignes

    @property
    def economies_cumulees(self):
        """Économies cumulées sur toute la durée (MAD)."""
        lignes = self.tableau_annuel
        return lignes[-1]['economie_cumulee'] if lignes else Decimal('0.00')

    def _annees_pour_atteindre(self, cible, cle):
        """Années (interpolées) pour que le cumul ``cle`` atteigne ``cible``."""
        if cible <= 0:
            return None
        precedent = Decimal('0.00')
        for ligne in self.tableau_annuel:
            cumul = ligne[cle]
            if cumul >= cible:
                flux = cumul - precedent
                if flux <= 0:
                    return Decimal(ligne['annee'])
                reste = (cible - precedent) / flux
                return (Decimal(ligne['annee'] - 1) + reste).quantize(
                    Decimal('0.01'))
            precedent = cumul
        return None

    @property
    def payback_simple_ans(self):
        """Retour SIMPLE sur le CAPEX hors stockage (années, None si jamais)."""
        return self._annees_pour_atteindre(
            self.capex_hors_stockage, 'economie_cumulee')

    @property
    def roi_sur_ttc_ans(self):
        """Retour sur le montant TTC REMIS (années) — le ROI de l'offre."""
        return self._annees_pour_atteindre(
            self.capex_total, 'economie_cumulee')

    @property
    def payback_actualise_ans(self):
        """Retour ACTUALISÉ sur le CAPEX hors stockage (années)."""
        return self._annees_pour_atteindre(
            self.capex_hors_stockage, 'economie_cumulee_actualisee')


# ── AOF136 — Checklist partenaire : un OBJET SUIVI, pas un document mort ──

class LigneChecklistPartenaire(TenantModel):
    """Un point de la checklist de remise, en BASE et non sur un papier.

    Les sept blocs de la checklist réelle deviennent des lignes d'état :
    chaque point porte sa case, son RESPONSABLE et son commentaire, et un
    point obligatoire encore ouvert BLOQUE la transition « prêt à déposer »
    (``DossierAO.raisons_de_non_depot``). Un document mort se relit en
    diagonale la veille de la remise ; un objet suivi ferme la porte.
    """

    class Bloc(models.TextChoices):
        CPS = 'cps', 'CPS'
        ACTE_ENGAGEMENT = 'acte_engagement', "Acte d'engagement"
        BORDEREAU = 'bordereau', 'Bordereau des prix'
        LETTRE_SOUMISSION = 'lettre_soumission', 'Lettre de soumission'
        MEMOIRE = 'memoire', 'Mémoire technique'
        ADMINISTRATIF = 'administratif', 'Dossier administratif'
        VERIFICATIONS = 'verifications', 'Vérifications avant dépôt'

    dossier = models.ForeignKey(
        DossierAO,
        on_delete=models.CASCADE,  # on_delete: ligne de checklist : aucune existence hors de son dossier
        related_name='lignes_checklist',
        verbose_name='Dossier',
    )
    bloc = models.CharField(
        max_length=20, choices=Bloc.choices, verbose_name='Bloc')
    code = models.CharField(max_length=40, verbose_name='Code du point')
    libelle = models.CharField(max_length=255, verbose_name='Point à traiter')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    obligatoire = models.BooleanField(default=True, verbose_name='Obligatoire')
    faite = models.BooleanField(default=False, verbose_name='Fait')
    #: Nommé ``responsable_utilisateur`` et non ``responsable`` : le garde
    #: YDATA3 (``scripts/check_on_delete.py``) traite un champ littéralement
    #: nommé ``responsable`` comme un champ de PORTÉE (tenant/owner), où un
    #: ``SET_NULL`` dé-scoperait silencieusement la ligne. Ici, c'est un
    #: ASSIGNÉ : perdre l'assignation à la suppression d'un compte est le
    #: comportement voulu (le point reste attaché à son dossier). Le libellé
    #: métier reste « Responsable », et l'API expose bien ``responsable``.
    responsable_utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lignes_checklist_ao', verbose_name='Responsable')
    commentaire = models.TextField(
        blank=True, default='', verbose_name='Commentaire')
    date_faite = models.DateTimeField(
        null=True, blank=True, verbose_name='Fait le')

    class Meta:
        verbose_name = 'Point de checklist partenaire (AO)'
        verbose_name_plural = 'Points de checklist partenaire (AO)'
        db_table = 'ao_ligne_checklist'
        ordering = ['dossier', 'ordre', 'code']
        constraints = [
            models.UniqueConstraint(
                fields=['dossier', 'code'],
                name='uniq_ligne_checklist_code'),
        ]
        indexes = [
            models.Index(fields=['company', 'dossier', 'bloc']),
        ]

    def __str__(self):
        etat = 'fait' if self.faite else 'ouvert'
        return f'[{self.get_bloc_display()}] {self.libelle} ({etat})'


# ── AOF137 — ``PieceAdministrative`` : une attestation est une donnée DATÉE ─

class PieceAdministrative(TenantModel):
    """Une pièce administrative DATÉE, réutilisable d'un AO à l'autre (AOF137).

    Constat. La checklist (AOF136) énumère déclaration sur l'honneur, pouvoirs,
    attestation fiscale de moins d'un an, CNSS de moins de trois mois, registre
    de commerce modèle J, RIB, assurances RC et décennale, caution provisoire —
    en CASES cochées à la main. Or leur péremption est strictement
    mécanisable, et les mêmes pièces se réutilisent d'un dossier à l'autre.

    **La date qui compte est celle de la REMISE DES PLIS, pas celle du jour.**
    Une attestation valable aujourd'hui mais expirée le jour de l'ouverture
    fait rejeter le pli : contrôler « à la date du jour » donnerait un dossier
    vert qui sera rouge à l'ouverture.

    Aucun nouveau ``FileField`` : le fichier vit dans ``records.Attachment``
    (ou ``ged.Document``), ce qui permet à la MÊME pièce d'être rattachée à
    deux appels d'offres sans dupliquer un octet.
    """

    class TypePiece(models.TextChoices):
        DECLARATION_HONNEUR = 'declaration_honneur', "Déclaration sur l'honneur"
        POUVOIRS = 'pouvoirs', 'Pouvoirs du signataire'
        ATTESTATION_FISCALE = 'attestation_fiscale', 'Attestation fiscale'
        ATTESTATION_CNSS = 'attestation_cnss', 'Attestation CNSS'
        REGISTRE_COMMERCE = 'registre_commerce', 'Registre de commerce (modèle J)'
        RIB = 'rib', 'RIB'
        ASSURANCE_RC = 'assurance_rc', 'Assurance responsabilité civile'
        ASSURANCE_DECENNALE = 'assurance_decennale', 'Assurance décennale étanchéité'
        CAUTION_PROVISOIRE = 'caution_provisoire', 'Caution provisoire'
        AUTRE = 'autre', 'Autre pièce administrative'

    #: Durées de validité RÉGLEMENTAIRES, en jours, par type de pièce.
    #: Attestation fiscale : moins d'un an. CNSS : moins de trois mois.
    #: Une pièce hors de cette table n'a pas de durée par défaut — on ne
    #: présume jamais d'une péremption qu'aucun texte n'impose.
    DUREES_PAR_DEFAUT = {
        TypePiece.ATTESTATION_FISCALE: 365,
        TypePiece.ATTESTATION_CNSS: 90,
    }

    type_piece = models.CharField(
        max_length=24, choices=TypePiece.choices, verbose_name='Type de pièce')
    libelle = models.CharField(max_length=200, verbose_name='Libellé')
    #: L'ORGANISME qui délivre (DGI, CNSS, tribunal de commerce, banque…).
    emetteur = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Émetteur')
    #: La société AU NOM DE laquelle la pièce est établie — en marque blanche,
    #: c'est le soumissionnaire, pas forcément la société de l'ERP.
    societe_emettrice = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Société titulaire de la pièce')
    date_emission = models.DateField(
        null=True, blank=True, verbose_name="Date d'émission")
    duree_validite_jours = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Durée de validité (jours)')
    #: Fichier — via ``records.Attachment`` ou ``ged.Document``, JAMAIS un
    #: nouveau ``FileField`` (le garde plateforme gèle ce module).
    attachment = models.ForeignKey(
        'records.Attachment',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pieces_administratives_ao', verbose_name='Fichier')
    ged_document = models.ForeignKey(
        'ged.Document',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pieces_administratives_ao', verbose_name='Document GED')
    #: Rattachement MULTIPLE : la même pièce sert plusieurs dossiers sans
    #: qu'un seul octet ne soit dupliqué.
    dossiers = models.ManyToManyField(
        DossierAO, blank=True, related_name='pieces_administratives',
        verbose_name='Dossiers rattachés')
    rappel_jours = models.PositiveIntegerField(
        default=30, verbose_name='Rappel avant expiration (jours)')
    actif = models.BooleanField(default=True, verbose_name='Active')

    class Meta:
        verbose_name = 'Pièce administrative (AO)'
        verbose_name_plural = 'Pièces administratives (AO)'
        db_table = 'ao_piece_administrative'
        ordering = ['type_piece', '-date_emission', 'id']
        indexes = [
            models.Index(fields=['company', 'type_piece']),
            models.Index(fields=['company', 'actif']),
        ]

    def __str__(self):
        return f'{self.get_type_piece_display()} — {self.libelle}'

    def save(self, *args, **kwargs):
        """Pose la durée RÉGLEMENTAIRE quand elle n'est pas renseignée."""
        if self.duree_validite_jours is None:
            defaut = self.DUREES_PAR_DEFAUT.get(self.type_piece)
            if defaut is not None:
                self.duree_validite_jours = defaut
        super().save(*args, **kwargs)

    @property
    def date_expiration(self):
        """Date d'expiration DÉRIVÉE (None = pièce sans péremption connue)."""
        if not self.date_emission or not self.duree_validite_jours:
            return None
        return self.date_emission + timedelta(days=self.duree_validite_jours)

    def est_expiree_a(self, date_reference):
        """Vrai si la pièce est expirée À CETTE DATE (pas à la date du jour)."""
        expiration = self.date_expiration
        if expiration is None or date_reference is None:
            return False
        return expiration < date_reference

    def jours_restants_a(self, date_reference):
        """Jours de validité restants à ``date_reference`` (None si sans date)."""
        expiration = self.date_expiration
        if expiration is None or date_reference is None:
            return None
        return (expiration - date_reference).days


# ── AOF140 — ``PlancheAO`` : indices AUTOMATIQUES + référence croisée ─────

class PlancheAO(TenantModel):
    """Une planche d'implantation, à indice AUTOMATIQUE (AOF140).

    Constat : les codes ``05H`` / ``06H`` / ``06I`` du dossier réel SONT déjà
    une numérotation d'indice faite à la main. L'automatiser supprime toute
    une classe de défaut : « planche citée dans le mémoire à un indice qui
    n'existe plus ».

    Règle : **l'indice n'est jamais saisi**. Il s'incrémente SUR CHANGEMENT
    D'EMPREINTE de la source (calepinage + paramètres de rendu) ; générer un
    indice supérieur ARCHIVE le précédent, et la base interdit deux planches
    ACTIVES de même code.

    Le cartouche et le bandeau d'engagement sont portés ici comme DONNÉES —
    le rendu de planche les consomme, il ne les rédige pas.
    """

    class Statut(models.TextChoices):
        ACTIVE = 'active', 'Active'
        ARCHIVEE = 'archivee', 'Archivée'

    appel_offre = models.ForeignKey(
        AppelOffre,
        on_delete=models.CASCADE,  # on_delete: planche fille d'un AO : aucune existence hors de son appel d'offres
        related_name='planches',
        verbose_name="Appel d'offres",
    )
    toiture = models.ForeignKey(
        ToitureAO,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='planches', verbose_name='Toiture',
    )
    variante = models.ForeignKey(
        VarianteCalepinage,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='planches', verbose_name='Variante représentée',
    )
    code_document = models.CharField(
        max_length=20, verbose_name='Code document')
    #: JAMAIS saisi : posé par ``services.generer_indice_planche``.
    indice = models.CharField(
        max_length=4, default='A', verbose_name='Indice')
    empreinte = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='Empreinte de la source')
    motif_revision = models.TextField(
        blank=True, default='', verbose_name='Motif de révision')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.ACTIVE,
        verbose_name='Statut')
    #: Données du cartouche et du bandeau d'engagement — CONSOMMÉES par le
    #: rendu de planche, jamais écrites à la main sur le dessin.
    cartouche = models.JSONField(
        default=dict, blank=True, verbose_name='Données du cartouche')
    bandeau_engagement = models.JSONField(
        default=dict, blank=True, verbose_name="Bandeau d'engagement")
    attachment = models.ForeignKey(
        'records.Attachment',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='planches_ao', verbose_name='Planche rendue (MinIO)')

    class Meta:
        verbose_name = 'Planche (AO)'
        verbose_name_plural = 'Planches (AO)'
        db_table = 'ao_planche'
        ordering = ['appel_offre', 'code_document', 'indice']
        constraints = [
            models.UniqueConstraint(
                fields=['appel_offre', 'code_document', 'indice'],
                name='uniq_planche_code_indice'),
            # Impossible d'avoir DEUX planches actives de même code : c'est la
            # règle qui empêche le « fichier frère périmé » de coexister.
            models.UniqueConstraint(
                fields=['appel_offre', 'code_document'],
                condition=models.Q(statut='active'),
                name='uniq_planche_active_par_code'),
        ]
        indexes = [
            models.Index(fields=['company', 'appel_offre', 'statut']),
        ]

    def __str__(self):
        return f'{self.code_document}{self.indice} [{self.get_statut_display()}]'

    @property
    def reference_complete(self):
        """``05H`` + indice — la référence telle que citée par le mémoire."""
        return f'{self.code_document}{self.indice}'


class CitationPlanche(TenantModel):
    """Une CITATION de planche dans une section du mémoire (AOF140).

    La référence croisée est une donnée, pas une relecture : c'est elle qui
    permet de détecter qu'une planche est citée à un indice qui n'existe plus.
    """

    appel_offre = models.ForeignKey(
        AppelOffre,
        on_delete=models.CASCADE,  # on_delete: citation fille d'un AO : aucune existence hors de lui
        related_name='citations_planches',
        verbose_name="Appel d'offres",
    )
    section = models.ForeignKey(
        SectionMemoire,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='citations_planches', verbose_name='Section du mémoire',
    )
    code_document = models.CharField(
        max_length=20, verbose_name='Code de la planche citée')
    indice_cite = models.CharField(
        max_length=4, blank=True, default='', verbose_name='Indice cité')
    emplacement = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Emplacement de la citation')

    class Meta:
        verbose_name = 'Citation de planche (AO)'
        verbose_name_plural = 'Citations de planche (AO)'
        db_table = 'ao_citation_planche'
        ordering = ['appel_offre', 'code_document', 'indice_cite']
        indexes = [
            models.Index(fields=['company', 'appel_offre', 'code_document']),
        ]

    def __str__(self):
        return f'{self.code_document}{self.indice_cite} ({self.emplacement})'


# ── AOF144 — Marque blanche : soumissionnaire ≠ bureau d'exécution ────────

class IdentiteAO(TenantModel):
    """L'identité d'un RÔLE du dossier : soumissionnaire ou bureau (AOF144).

    Cas réel : le dossier est DÉPOSÉ par une entité partenaire, alors que
    l'étude et l'exécution sont faites par le bureau. Ce sont deux rôles, deux
    identités légales, et **les rendus client n'utilisent QUE le
    soumissionnaire** : quand la marque blanche est active, la société
    propriétaire de l'ERP n'apparaît NULLE PART dans un artefact remis.

    **Aucun champ d'identité n'est dupliqué avec ``authentication.Company``**
    (qui ne porte que ``nom``/``slug``) ni avec ``parametres.CompanyProfile``
    (l'identité de NOTRE société) : ce modèle porte l'identité du PARTENAIRE,
    qui n'existe nulle part ailleurs. Le rôle ``bureau_execution`` sans
    enregistrement retombe sur ``parametres.selectors.company_identity`` — une
    lecture cross-app par selector, jamais un import de modèles.
    """

    class Role(models.TextChoices):
        SOUMISSIONNAIRE = 'soumissionnaire', 'Soumissionnaire (déposant)'
        BUREAU_EXECUTION = 'bureau_execution', "Bureau d'exécution"

    appel_offre = models.ForeignKey(
        AppelOffre,
        on_delete=models.CASCADE,  # on_delete: identite fille d'un AO : aucune existence hors de lui
        related_name='identites',
        verbose_name="Appel d'offres",
    )
    role = models.CharField(
        max_length=20, choices=Role.choices, verbose_name='Rôle')
    raison_sociale = models.CharField(
        max_length=255, verbose_name='Raison sociale')
    ice = models.CharField(
        max_length=40, blank=True, default='', verbose_name='ICE')
    identifiant_fiscal = models.CharField(
        max_length=40, blank=True, default='',
        verbose_name='Identifiant fiscal')
    registre_commerce = models.CharField(
        max_length=40, blank=True, default='',
        verbose_name='Registre de commerce')
    adresse = models.TextField(blank=True, default='', verbose_name='Adresse')
    #: Logo — via ``records.Attachment`` (aucun nouveau ``FileField``).
    logo = models.ForeignKey(
        'records.Attachment',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='identites_ao', verbose_name='Logo')
    signataire_nom = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Signataire')
    signataire_qualite = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Qualité du signataire')
    rib = models.CharField(
        max_length=60, blank=True, default='', verbose_name='RIB')
    mentions_legales = models.TextField(
        blank=True, default='', verbose_name='Mentions légales')

    class Meta:
        verbose_name = "Identité d'appel d'offres (AO)"
        verbose_name_plural = "Identités d'appel d'offres (AO)"
        db_table = 'ao_identite'
        ordering = ['appel_offre', 'role']
        constraints = [
            models.UniqueConstraint(
                fields=['appel_offre', 'role'], name='uniq_identite_ao_role'),
        ]

    def __str__(self):
        return f'{self.get_role_display()} — {self.raison_sociale}'


# ── AOF146 — Contrôleur de cohérence croisée : une PORTE, pas un rapport ──

class ControleCoherence(TenantModel):
    """Le RÉSULTAT d'une passe de contrôle de cohérence (AOF146).

    Chaque anomalie est une LIGNE : code de règle, sévérité, message français,
    objet visé, date. Une passe REMPLACE les lignes de la passe précédente —
    un contrôle est une photographie d'un état, jamais un journal qui
    s'allonge.

    Le point capital : ce n'est pas un rapport à lire, c'est une PORTE. La
    transition ``pret_a_deposer`` est REFUSÉE tant qu'un contrôle bloquant est
    rouge, et le refus CITE le code de règle fautif.
    """

    class Severite(models.TextChoices):
        BLOQUANT = 'bloquant', 'Bloquant'
        AVERTISSEMENT = 'avertissement', 'Avertissement'
        INFO = 'info', 'Information'

    dossier = models.ForeignKey(
        DossierAO,
        on_delete=models.CASCADE,  # on_delete: controle fils d'un dossier : aucune existence hors de lui
        related_name='controles',
        verbose_name='Dossier',
    )
    code_regle = models.CharField(max_length=60, verbose_name='Code de règle')
    severite = models.CharField(
        max_length=14, choices=Severite.choices,
        default=Severite.BLOQUANT, verbose_name='Sévérité')
    message = models.TextField(verbose_name='Message (français)')
    objet = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Objet visé')
    #: Empreinte du contexte contrôlé : un contrôle vert ne prouve rien s'il
    #: décrit un autre état du dossier.
    empreinte = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='Empreinte du contexte contrôlé')
    date_controle = models.DateTimeField(
        auto_now_add=True, verbose_name='Contrôlé le')

    class Meta:
        verbose_name = 'Contrôle de cohérence (AO)'
        verbose_name_plural = 'Contrôles de cohérence (AO)'
        db_table = 'ao_controle_coherence'
        ordering = ['dossier', 'severite', 'code_regle', 'id']
        indexes = [
            models.Index(fields=['company', 'dossier', 'severite']),
        ]

    def __str__(self):
        return f'[{self.severite}] {self.code_regle} — {self.objet}'


# ── AOF150 — Archivage IMMUABLE + manifeste de pack ───────────────────────

class ArtefactAO(TenantModel):
    """Un artefact ARCHIVÉ, immuable, adressé par son empreinte (AOF150).

    La clé est ``ao/<company>/<dossier>/<code>/<indice>-<empreinte8>.<ext>`` :
    l'indice ET l'empreinte y figurent, donc **deux versions ne peuvent pas se
    disputer la même clé** et rien ne s'écrase jamais. Le dépôt réel contient
    encore aujourd'hui deux bordereaux homonymes divergents — même classe de
    risque qu'un devis obsolète envoyé au client.

    Les octets vivent dans MinIO via ``records.Attachment`` : **aucun nouveau
    ``FileField``** (le garde plateforme gèle ce module).
    """

    dossier = models.ForeignKey(
        DossierAO,
        on_delete=models.CASCADE,  # on_delete: artefact fils d'un dossier : aucune existence hors de lui
        related_name='artefacts',
        verbose_name='Dossier',
    )
    code = models.CharField(max_length=20, verbose_name='Code de la pièce')
    indice = models.CharField(max_length=4, default='A', verbose_name='Indice')
    empreinte = models.CharField(
        max_length=64, verbose_name='Empreinte du contexte produit')
    cle = models.CharField(max_length=500, verbose_name='Clé objet (MinIO)')
    taille = models.PositiveBigIntegerField(
        default=0, verbose_name='Taille (octets)')
    mime = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Type MIME')
    attachment = models.ForeignKey(
        'records.Attachment',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='artefacts_ao', verbose_name='Pièce jointe')

    class Meta:
        verbose_name = 'Artefact archivé (AO)'
        verbose_name_plural = 'Artefacts archivés (AO)'
        db_table = 'ao_artefact'
        ordering = ['dossier', 'code', 'indice']
        constraints = [
            # La clé est UNIQUE : un artefact ne s'écrase jamais.
            models.UniqueConstraint(
                fields=['company', 'cle'], name='uniq_artefact_ao_cle'),
            models.UniqueConstraint(
                fields=['dossier', 'code', 'indice'],
                name='uniq_artefact_ao_code_indice'),
        ]
        indexes = [
            models.Index(fields=['company', 'dossier', 'empreinte']),
        ]

    def __str__(self):
        return f'{self.code}{self.indice} — {self.cle}'


class ManifestePack(TenantModel):
    """Le « pack courant » : un MANIFESTE DE CLÉS, pas un répertoire (AOF150).

    Un répertoire accumule les versions et laisse le dépôt choisir ; un
    manifeste NOMME exactement ce qui part. Les indices antérieurs restent
    consultables en historique mais **ne peuvent STRUCTURELLEMENT pas entrer
    dans un pack de dépôt** : le manifeste porte une empreinte, et il n'accepte
    que des artefacts produits sous CETTE empreinte (garde en service +
    ``verifier``).
    """

    dossier = models.ForeignKey(
        DossierAO,
        on_delete=models.CASCADE,  # on_delete: manifeste fils d'un dossier : aucune existence hors de lui
        related_name='manifestes',
        verbose_name='Dossier',
    )
    empreinte = models.CharField(
        max_length=64, verbose_name='Empreinte du contexte')
    artefacts = models.ManyToManyField(
        ArtefactAO, blank=True, related_name='manifestes',
        verbose_name='Artefacts du pack')
    courant = models.BooleanField(
        default=True, verbose_name='Manifeste courant')

    class Meta:
        verbose_name = 'Manifeste de pack (AO)'
        verbose_name_plural = 'Manifestes de pack (AO)'
        db_table = 'ao_manifeste_pack'
        ordering = ['-created_at', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['dossier'], condition=models.Q(courant=True),
                name='uniq_manifeste_courant_par_dossier'),
        ]

    def __str__(self):
        return f'Manifeste {self.empreinte[:8]} — {self.dossier_id}'

    def artefacts_perimes(self):
        """Artefacts du manifeste produits sous une AUTRE empreinte.

        Doit toujours être VIDE : le service refuse de les y mettre. La
        méthode existe pour que l'invariant soit vérifiable, pas seulement
        déclaré.
        """
        return [a for a in self.artefacts.all()
                if a.empreinte != self.empreinte]


# ══════════════════════════════════════════════════════════════════════════
# W7 — ÉCONOMIE DIRECTEUR : TABLES SÉPARÉES, PERMISSION ÉLEVÉE (AOF157)
# ══════════════════════════════════════════════════════════════════════════
#
# RÈGLE GRAVÉE. L'économie d'un appel d'offres vit dans des tables À PART,
# derrière ``ao_rentabilite_voir`` (permission ÉLEVÉE, non octroyable par un
# non-administrateur, mappée sur AUCUN rôle Responsable/Commercial/Technicien/
# Utilisateur). **Aucun champ de coût ni de marge ne touche ``AppelOffre``, le
# bordereau ou une variante** — un test d'introspection le vérifie.
#
# À NE PAS CONFONDRE avec la « simulation de rentabilité 25 ans » (AOF135) :
# celle-là est une pièce CLIENT qui ne porte aucun coût. Les fusionner « parce
# que ça parle de rentabilité » est le chemin le plus court vers la fuite de
# marge.

class EconomieAO(TenantModel):
    """L'économie DIRECTEUR d'un appel d'offres (AOF157) — table séparée.

    Porte les régimes de TVA et le verrou ; les COÛTS sont dans
    ``LigneCoutRevient``, la CIBLE de bénéfice dans ``CibleFinanciere``
    (versionnée). Tous les agrégats sont DÉRIVÉS : rien n'est recopié.

    TVA sur ACHATS différenciée : 10 % sur les panneaux, 20 % sur le reste.
    C'est ce qui rend la TVA nette à reverser calculable — et le contrôle de
    trésorerie (encaissement TTC − décaissements TTC − TVA nette == bénéfice
    HT) vérifiable au dirham. Un écart non nul, et le classeur est rouge.
    """

    appel_offre = models.OneToOneField(
        AppelOffre,
        on_delete=models.CASCADE,  # on_delete: economie fille d'un AO : aucune existence hors de lui
        related_name='economie',
        verbose_name="Appel d'offres",
    )
    taux_tva_vente = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('20.00'),
        verbose_name='Taux de TVA de vente (%)')
    taux_tva_achat_reduit = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('10.00'),
        verbose_name='TVA sur achats — régime réduit panneaux (%)')
    taux_tva_achat_standard = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('20.00'),
        verbose_name='TVA sur achats — régime standard (%)')
    verrouillee = models.BooleanField(
        default=False, verbose_name='Économie verrouillée')
    note_comptable = models.TextField(
        blank=True, default='', verbose_name='Point ouvert signalé au comptable')

    class Meta:
        verbose_name = "Économie d'appel d'offres (directeur)"
        verbose_name_plural = "Économies d'appel d'offres (directeur)"
        db_table = 'ao_economie'
        ordering = ['appel_offre']

    def __str__(self):
        return f'Économie {self.appel_offre.reference}'

    # ── Coûts (dérivés des lignes) ───────────────────────────────────────

    @property
    def cout_revient_ht(self):
        total = Decimal('0.00')
        for ligne in self.lignes.all():
            total += ligne.montant_ht
        return total.quantize(Decimal('0.01'))

    @property
    def cout_regime_reduit_ht(self):
        """Part du coût de revient soumise au régime réduit (panneaux)."""
        total = Decimal('0.00')
        for ligne in self.lignes.filter(
                regime_tva=LigneCoutRevient.RegimeTVA.REDUIT):
            total += ligne.montant_ht
        return total.quantize(Decimal('0.01'))

    @property
    def cout_regime_standard_ht(self):
        return (self.cout_revient_ht - self.cout_regime_reduit_ht).quantize(
            Decimal('0.01'))

    @property
    def tva_deductible(self):
        """TVA sur achats DIFFÉRENCIÉE : 10 % panneaux, 20 % le reste."""
        reduite = (self.cout_regime_reduit_ht
                   * self.taux_tva_achat_reduit / Decimal('100'))
        standard = (self.cout_regime_standard_ht
                    * self.taux_tva_achat_standard / Decimal('100'))
        return (reduite + standard).quantize(Decimal('0.01'))

    # ── Cible et totaux (dérivés) ────────────────────────────────────────

    @property
    def cible(self):
        """La cible financière ACTIVE (dernière version), ou None."""
        return self.cibles.filter(active=True).first()

    @property
    def benefice_net_cible_ht(self):
        cible = self.cible
        return cible.benefice_net_cible_ht if cible else Decimal('0.00')

    @property
    def total_ht(self):
        """Coût de revient + bénéfice net visé — la cascade part de LÀ."""
        return (self.cout_revient_ht
                + self.benefice_net_cible_ht).quantize(Decimal('0.01'))

    @property
    def tva_collectee(self):
        return (self.total_ht * self.taux_tva_vente
                / Decimal('100')).quantize(Decimal('0.01'))

    @property
    def total_ttc(self):
        return (self.total_ht + self.tva_collectee).quantize(Decimal('0.01'))

    @property
    def tva_nette_a_reverser(self):
        """TVA collectée − TVA déductible : ce qui sort réellement."""
        return (self.tva_collectee - self.tva_deductible).quantize(
            Decimal('0.01'))

    @property
    def marge_pct(self):
        """Bénéfice net visé rapporté au total HT (%)."""
        total = self.total_ht
        if not total:
            return Decimal('0.00')
        return (self.benefice_net_cible_ht / total
                * Decimal('100')).quantize(Decimal('0.01'))

    @property
    def controle_tresorerie(self):
        """Encaissement TTC − décaissements TTC − TVA nette (doit == bénéfice).

        C'est LE contrôle du classeur : un écart non nul et le classeur est
        rouge. Il n'y a pas de « presque juste » en trésorerie.
        """
        decaissements = self.cout_revient_ht + self.tva_deductible
        return (self.total_ttc - decaissements
                - self.tva_nette_a_reverser).quantize(Decimal('0.01'))

    @property
    def ecart_tresorerie(self):
        """Écart entre le contrôle de trésorerie et le bénéfice visé."""
        return (self.controle_tresorerie
                - self.benefice_net_cible_ht).quantize(Decimal('0.01'))

    @property
    def sous_seuil_psychologique(self):
        """Vrai si le TTC reste sous le seuil visé (ex. la barre des 5 M)."""
        cible = self.cible
        if cible is None or not cible.seuil_psychologique:
            return True
        return self.total_ttc < cible.seuil_psychologique


class LigneCoutRevient(TenantModel):
    """Un POSTE du coût de revient (AOF157) — directeur seulement.

    ``regime_tva`` porte la différenciation 10 % panneaux / 20 % reste : sans
    elle, la TVA nette à reverser serait fausse de plusieurs dizaines de
    milliers de dirhams sur un dossier de cette taille.
    """

    class RegimeTVA(models.TextChoices):
        REDUIT = 'reduit', 'Réduit (panneaux, 10 %)'
        STANDARD = 'standard', 'Standard (20 %)'

    class Poste(models.TextChoices):
        PANNEAUX = 'panneaux', 'Panneaux'
        STRUCTURE = 'structure', 'Structure'
        ONDULEURS = 'onduleurs', 'Onduleurs et équipements'
        GARANTIE_ONDULEURS = 'garantie_onduleurs', 'Extension de garantie onduleurs'
        CABLE_SOLAIRE = 'cable_solaire', 'Câble solaire'
        CABLE_AC = 'cable_ac', 'Câble AC'
        MAIN_OEUVRE = 'main_oeuvre', "Main d'œuvre"
        ALEAS = 'aleas', 'Aléas'
        AUTRE = 'autre', 'Autre poste'

    economie = models.ForeignKey(
        EconomieAO,
        on_delete=models.CASCADE,  # on_delete: ligne de cout : aucune existence hors de son economie
        related_name='lignes',
        verbose_name='Économie',
    )
    poste = models.CharField(
        max_length=20, choices=Poste.choices, default=Poste.AUTRE,
        verbose_name='Poste')
    designation = models.CharField(max_length=255, verbose_name='Désignation')
    quantite = models.DecimalField(
        max_digits=12, decimal_places=3, default=Decimal('1.000'),
        verbose_name='Quantité')
    unite = models.CharField(
        max_length=20, blank=True, default='U', verbose_name='Unité')
    prix_unitaire_ht = models.DecimalField(
        max_digits=14, decimal_places=4, default=Decimal('0.0000'),
        verbose_name='Coût unitaire HT (MAD)')
    regime_tva = models.CharField(
        max_length=10, choices=RegimeTVA.choices, default=RegimeTVA.STANDARD,
        verbose_name='Régime de TVA sur achat')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')

    class Meta:
        verbose_name = 'Ligne de coût de revient (directeur)'
        verbose_name_plural = 'Lignes de coût de revient (directeur)'
        db_table = 'ao_ligne_cout_revient'
        ordering = ['economie', 'ordre', 'id']

    def __str__(self):
        return f'{self.get_poste_display()} — {self.designation}'

    @property
    def montant_ht(self):
        return ((self.quantite or Decimal('0'))
                * (self.prix_unitaire_ht or Decimal('0')))


class CibleFinanciere(TenantModel):
    """La CIBLE de bénéfice, VERSIONNÉE (AOF157) — directeur seulement.

    Un mouvement de prix se justifie : chaque version porte son auteur, sa
    date et son motif. La ligne d'AJUSTEMENT désignée reçoit le résidu de la
    répartition (AOF158) — la désigner ici évite qu'un solveur choisisse tout
    seul quelle ligne encaisse l'arrondi.
    """

    economie = models.ForeignKey(
        EconomieAO,
        on_delete=models.CASCADE,  # on_delete: cible fille d'une economie : aucune existence hors d'elle
        related_name='cibles',
        verbose_name='Économie',
    )
    version = models.PositiveIntegerField(default=1, verbose_name='Version')
    benefice_net_cible_ht = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Bénéfice net visé HT (MAD)')
    #: Pas d'arrondi métier appliqué aux prix unitaires (50/100/500/1 000 DH).
    arrondi_psychologique = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Pas d\'arrondi des prix unitaires (MAD)')
    #: Barre à ne pas franchir en TTC (cas réel : les 5 000 000 MAD).
    seuil_psychologique = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True,
        verbose_name='Seuil psychologique TTC (MAD)')
    ligne_ajustement = models.ForeignKey(
        LigneBordereau,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cibles_financieres',
        verbose_name="Ligne d'ajustement du résidu")
    active = models.BooleanField(default=True, verbose_name='Version active')
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cibles_financieres_ao', verbose_name='Auteur')
    motif = models.TextField(
        blank=True, default='', verbose_name='Motif de la version')

    class Meta:
        verbose_name = 'Cible financière (directeur)'
        verbose_name_plural = 'Cibles financières (directeur)'
        db_table = 'ao_cible_financiere'
        ordering = ['economie', '-version']
        constraints = [
            models.UniqueConstraint(
                fields=['economie', 'version'],
                name='uniq_cible_financiere_version'),
            models.UniqueConstraint(
                fields=['economie'], condition=models.Q(active=True),
                name='uniq_cible_financiere_active'),
        ]

    def __str__(self):
        return f'v{self.version} — {self.benefice_net_cible_ht} MAD HT'
