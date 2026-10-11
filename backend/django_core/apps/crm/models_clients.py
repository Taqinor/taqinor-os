"""Modèles crm « clients & partenaires » sortis de ``models.py`` (SPL91).

SPL91 : partenaires, apporteurs, deals, salle de vente, T-TRACE. SPL92 : Client
et les modèles de pilotage (parrainage, objectifs, concurrents, plans
d'activité, équipes, forecast, plans de compte, playbooks, défis).

Move only : corps de classes inchangés, même ``app_label`` (``crm``), mêmes
``db_table`` — aucune migration. ``apps.crm.models`` les ré-exporte dans son
UNIQUE bloc de ré-export, TOUT EN BAS du fichier : Django n'enregistre que les
modèles importés par ``apps.crm.models``, et les migrations comme tous les
``from apps.crm.models import …`` du dépôt continuent de résoudre.

Règle d'architecture : ce module n'importe depuis ``.models`` que des noms
définis AU-DESSUS du bloc de ré-export, et n'est JAMAIS importé avant
``apps.crm.models``. Les callables de migration (``_default_salle_vente_*``,
``_default_deal_expiry``) RESTENT dans ``models.py`` : les migrations les
référencent par ``apps.crm.models._default_*`` (chemin de deconstruct).
"""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Lower

from core.models import TenantModel

from .models import (
    Lead, _default_deal_expiry, _default_salle_vente_expiry,
    _default_salle_vente_token)
from .stages import STAGE_CHOICES

# ── FG234–237 — Partenaires & territoires commerciaux (ODX13, rapatriés de
# compta : leur foyer Odoo naturel CRM/resellers) ──────────────────────────
# ``db_table`` figé sur le nom historique (``compta_<model>``) — SORTIE
# state-only de compta (migration ``crm.0059_odx13_partenaires_split`` +
# ``compta.0109_odx13_partenaires_split``), aucune donnée déplacée. Les
# anciennes routes ``/api/django/compta/…`` restent servies à l'identique
# (les ViewSets/serializers restent physiquement dans l'app compta — voir
# ``apps/crm/views.py``/``apps/crm/serializers.py`` pour le ré-export
# transitoire des nouvelles routes ``/api/django/crm/…``).

# NTMIG26 — spécialités (modules maîtrisés) qu'un partenaire intégrateur peut
# déclarer. Liste FERMÉE et validée côté serializer : une spécialité libre
# rendrait l'annuaire des certifiés infiltrable ("Compta", "compta ", "COMPTA"
# seraient trois spécialités distinctes et aucun filtre ne les retrouverait).
SPECIALITES_PARTENAIRE = (
    ('crm', 'CRM & prospection'),
    ('ventes', 'Ventes & devis'),
    ('compta', 'Comptabilité'),
    ('stock', 'Stock & achats'),
    ('installations', 'Chantiers & installations'),
    ('sav', 'SAV & maintenance'),
    ('rh', 'RH & paie'),
    ('migration', 'Migration de données'),
)


SPECIALITES_PARTENAIRE_CLES = tuple(cle for cle, _ in SPECIALITES_PARTENAIRE)


class Partenaire(models.Model):
    """Partenaire commercial : apporteur d'affaires ou sous-revendeur (FG234).

    Fiche minimale ici (compte + accès tokenisé + taux de commission). FG237
    enrichit la fiche (statut d'agrément, zone, onboarding). NTMIG26 ajoute
    PAR-DESSUS la couche CERTIFICATION/compétence (niveau, spécialités,
    échéance, compteur de déploiements) — jamais les mêmes champs que
    l'agrément de base. Un partenaire soumet des leads via le portail
    (``SoumissionLeadPartenaire``) et suit leur statut. Scopé société ; le
    token d'accès est posé côté serveur.
    """
    class Type(models.TextChoices):
        APPORTEUR = 'apporteur', "Apporteur d'affaires"
        SOUS_REVENDEUR = 'sous_revendeur', 'Sous-revendeur'
        INSTALLATEUR = 'installateur', 'Installateur'

    class NiveauCertification(models.TextChoices):
        """NTMIG26 — niveau de certification intégrateur.

        Distinct de ``statut_onboarding`` (FG237), qui dit si le partenaire est
        AGRÉÉ (droit de travailler) : le niveau dit à quel point il est
        COMPÉTENT. Un partenaire agréé peut rester ``aucun`` ; un partenaire
        ``platine`` suspendu reste suspendu. Défaut ``aucun`` = comportement
        historique inchangé pour toutes les fiches existantes.
        """
        AUCUN = 'aucun', 'Aucun'
        ENREGISTRE = 'enregistre', 'Enregistré'
        CERTIFIE = 'certifie', 'Certifié'
        OR = 'or', 'Or'
        PLATINE = 'platine', 'Platine'

    # Référentiel des spécialités, porté PAR LA CLASSE : les consommateurs
    # (serializers compta, scoring NTMIG27) le lisent sur ``Partenaire``, sans
    # importer un module d'une autre app pour une simple liste de clés.
    SPECIALITES = SPECIALITES_PARTENAIRE
    SPECIALITES_CLES = SPECIALITES_PARTENAIRE_CLES

    # Ordre CROISSANT des niveaux — le seul endroit où « ≥ certifié » est
    # défini (l'annuaire NTMIG29 et le scoring NTMIG27 s'y adossent, jamais
    # une seconde échelle recopiée ailleurs).
    NIVEAUX_ORDONNES = (
        NiveauCertification.AUCUN,
        NiveauCertification.ENREGISTRE,
        NiveauCertification.CERTIFIE,
        NiveauCertification.OR,
        NiveauCertification.PLATINE,
    )

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        related_name='partenaires',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=200, verbose_name='Nom / raison sociale')
    type_partenaire = models.CharField(
        max_length=16, choices=Type.choices, default=Type.APPORTEUR,
        verbose_name='Type de partenaire')
    email = models.EmailField(blank=True, default='', verbose_name='Email')
    telephone = models.CharField(
        max_length=30, blank=True, default='', verbose_name='Téléphone')
    taux_commission = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name='Taux de commission (%)')
    token_acces = models.CharField(
        max_length=64, unique=True, db_index=True,
        verbose_name="Token d'accès")
    actif = models.BooleanField(default=True, verbose_name='Actif')
    # FG237 — Annuaire & onboarding installateurs partenaires.
    statut_onboarding = models.CharField(
        max_length=12,
        choices=[
            ('prospect', 'Prospect'),
            ('en_cours', "En cours d'agrément"),
            ('agree', 'Agréé (activé)'),
            ('suspendu', 'Suspendu'),
        ],
        default='prospect',
        verbose_name="Statut d'onboarding")
    numero_agrement = models.CharField(
        max_length=60, blank=True, default='',
        verbose_name="Numéro d'agrément")
    zone = models.CharField(
        max_length=120, blank=True, default='',
        verbose_name='Zone géographique')
    date_activation = models.DateField(
        null=True, blank=True, verbose_name="Date d'activation")

    # ── NTMIG26 — Couche CERTIFICATION (par-dessus l'agrément FG237) ──
    # Additive et rétro-compatible : toute fiche existante reste ``aucun``,
    # sans spécialité ni échéance — aucune n'est modifiée.
    niveau_certification = models.CharField(
        max_length=12, choices=NiveauCertification.choices,
        default=NiveauCertification.AUCUN,
        verbose_name='Niveau de certification')
    date_certification = models.DateField(
        null=True, blank=True, verbose_name='Date de certification')
    date_expiration_certification = models.DateField(
        null=True, blank=True,
        verbose_name="Date d'expiration de la certification")
    # Liste de clés de ``SPECIALITES_PARTENAIRE`` (validée au serializer).
    specialites = models.JSONField(
        default=list, blank=True, verbose_name='Spécialités (modules)')
    # Compteur d'historique alimenté par les déploiements NTMIG28 ; il ne se
    # recalcule jamais par un count() à la volée (le nombre de déploiements
    # RECONNUS est une décision, pas une jointure).
    nb_deploiements_reussis = models.PositiveIntegerField(
        default=0, verbose_name='Déploiements réussis')

    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    # ── ARC19 — Pont additif vers le répertoire unifié Tiers ──
    # FK nullable (string-FK ``'tiers.Tiers'`` — jamais d'import de
    # apps.tiers.models ici). L'identité reste MAÎTRE côté Partenaire ; ``tiers``
    # n'en est qu'un MIROIR one-way réversible, posé par le hook de sauvegarde
    # (apps/compta/tiers_bridge.py, sender re-pointé sur ``crm.Partenaire`` par
    # ODX13) et backfillé par ``backfill_tiers`` (source re-pointée pareil).
    tiers = models.ForeignKey(
        'tiers.Tiers',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='partenaires',
        verbose_name='Tiers (répertoire unifié)',
        help_text="Fiche du répertoire unifié des parties prenantes reflétant "
                  "ce partenaire. Renseignée automatiquement (miroir).")

    class Meta:
        verbose_name = 'Partenaire commercial'
        verbose_name_plural = 'Partenaires commerciaux'
        db_table = 'compta_partenaire'
        ordering = ['nom']

    # ── NTMIG26 — lectures dérivées de la couche certification ──

    @property
    def rang_certification(self):
        """Position du niveau dans l'échelle (0 = aucun). Sert aux filtres
        « niveau ≥ certifié » — jamais une comparaison alphabétique, qui
        classerait « or » avant « platine » mais aussi avant « certifie »."""
        try:
            return list(self.NIVEAUX_ORDONNES).index(
                self.niveau_certification)
        except ValueError:
            return 0

    @property
    def certification_expiree(self):
        """La certification est-elle échue ? (Faux si aucune échéance posée.)"""
        from core.dates import aujourd_hui_local

        if not self.date_expiration_certification:
            return False
        return self.date_expiration_certification < aujourd_hui_local()

    def __str__(self):
        return f'{self.nom} ({self.get_type_partenaire_display()})'


class SoumissionLeadPartenaire(models.Model):
    """Lead soumis par un partenaire via le portail (FG234).

    Le partenaire renseigne les coordonnées d'un prospect ; on enregistre la
    soumission scopée société. Après qualification, le lead réel est créé dans
    ``crm`` (via son service, jamais importé ici) et référencé par ``lead_id``.
    Le partenaire suit le statut de sa soumission.
    """
    class Statut(models.TextChoices):
        SOUMIS = 'soumis', 'Soumis'
        QUALIFIE = 'qualifie', 'Qualifié'
        CONVERTI = 'converti', 'Converti'
        REJETE = 'rejete', 'Rejeté'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        related_name='soumissions_lead_partenaire',
        verbose_name='Société',
    )
    partenaire = models.ForeignKey(
        Partenaire,
        on_delete=models.CASCADE,  # on_delete: SoumissionLeadPartenaire est le détail de Partenaire — n'existe pas sans lui
        related_name='soumissions',
        verbose_name='Partenaire',
    )
    nom_prospect = models.CharField(
        max_length=200, verbose_name='Nom du prospect')
    telephone_prospect = models.CharField(
        max_length=30, blank=True, default='',
        verbose_name='Téléphone du prospect')
    email_prospect = models.EmailField(
        blank=True, default='', verbose_name='Email du prospect')
    ville = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Ville')
    note = models.TextField(blank=True, default='', verbose_name='Note')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.SOUMIS,
        verbose_name='Statut')
    lead_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Id du lead créé')
    date_soumission = models.DateTimeField(
        auto_now_add=True, verbose_name='Soumis le')

    class Meta:
        verbose_name = 'Soumission de lead (partenaire)'
        verbose_name_plural = 'Soumissions de lead (partenaire)'
        db_table = 'compta_soumissionleadpartenaire'
        ordering = ['-date_soumission']

    def __str__(self):
        return f'{self.nom_prospect} — {self.partenaire.nom}'


class CommissionPartenaire(models.Model):
    """Commission due à un partenaire sur un devis signé/lead converti (FG235).

    Calculée sur une base HT × taux (%). Le devis est référencé par id
    (cross-app — jamais d'import ventes). Statut de règlement (due → payée). Le
    relevé par partenaire s'obtient en agrégeant ces lignes (action ``releve``).
    Scopée société.
    """
    class Statut(models.TextChoices):
        DUE = 'due', 'Due'
        PAYEE = 'payee', 'Payée'
        ANNULEE = 'annulee', 'Annulée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        related_name='commissions_partenaire',
        verbose_name='Société',
    )
    partenaire = models.ForeignKey(
        Partenaire,
        on_delete=models.PROTECT,
        related_name='commissions',
        verbose_name='Partenaire',
    )
    devis_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Id du devis signé')
    lead_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Id du lead')
    base_ht = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Base HT (MAD)')
    taux = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name='Taux de commission (%)')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Montant de commission (MAD)')
    statut = models.CharField(
        max_length=8, choices=Statut.choices, default=Statut.DUE,
        verbose_name='Statut')
    paye_le = models.DateField(
        null=True, blank=True, verbose_name='Payée le')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Commission partenaire'
        verbose_name_plural = 'Commissions partenaire'
        db_table = 'compta_commissionpartenaire'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Commission {self.montant} — {self.partenaire.nom}'


class SalleVente(TenantModel):
    """NTCRM17 — Salle de vente : page publique regroupant plusieurs
    devis/documents/liens pour UN lead OU UN client (jamais les deux, jamais
    ni l'un ni l'autre — voir `clean()`). Sécurité calquée sur
    `ged.PartageGed` : `token` imprévisible = unique clé d'accès public,
    `expires_at` par défaut 30 j, `password_hash` optionnel (jamais en
    clair), `actif` = kill-switch de révocation immédiate.

    ARC1 — hérite de ``core.models.TenantModel`` ; ``company`` redéclaré à
    l'identique (related_name + nullabilité historiques)."""
    company = models.ForeignKey(  # on_delete: salle de vente 100 % fille du tenant — la purge d'une société doit emporter ses salles (et leurs jetons d'accès publics).
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='salles_vente')
    lead = models.ForeignKey(  # on_delete: la salle n'existe que pour présenter CE lead ; sans lui elle n'a plus d'objet.
        'crm.Lead', on_delete=models.CASCADE,
        null=True, blank=True, related_name='salles_vente')
    client = models.ForeignKey(  # on_delete: idem lead — espace de vente rattaché à ce client, sans existence propre.
        'crm.Client', on_delete=models.CASCADE,
        null=True, blank=True, related_name='salles_vente')
    titre = models.CharField(max_length=200, verbose_name='Titre')
    token = models.CharField(
        max_length=64, unique=True, default=_default_salle_vente_token,
        editable=False)
    expires_at = models.DateTimeField(
        default=_default_salle_vente_expiry, verbose_name='Expire le')
    # Hash du mot de passe optionnel (make_password). Vide = pas de mot de
    # passe. JAMAIS stocké en clair — voir set_password()/check_password().
    password_hash = models.TextField(blank=True, default='')
    actif = models.BooleanField(
        default=True, verbose_name='Actif',
        help_text='Décoché = révocation immédiate du lien public.')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='salles_vente_creees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Salle de vente'
        verbose_name_plural = 'Salles de vente'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['token'], name='crm_salle_vente_token_idx'),
        ]

    def __str__(self):
        return f'Salle de vente « {self.titre} » ({self.token[:8]}…)'

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        if bool(self.lead_id) == bool(self.client_id):
            raise ValidationError(
                'Une salle de vente doit référencer EXACTEMENT un lead OU '
                'un client (jamais les deux, jamais ni l\'un ni l\'autre).')

    @property
    def has_password(self):
        return bool(self.password_hash)

    @property
    def is_expired(self):
        from django.utils import timezone as _timezone
        return self.expires_at is not None and self.expires_at <= _timezone.now()

    @property
    def is_accessible(self):
        """Servable publiquement : actif ET non expiré (mot de passe validé
        séparément par l'endpoint — 403 distinct de 404/410)."""
        return self.actif and not self.is_expired

    def set_password(self, raw_password):
        from django.contrib.auth.hashers import make_password
        self.password_hash = make_password(raw_password) if raw_password else ''

    def check_password(self, raw_password):
        from django.contrib.auth.hashers import check_password
        if not self.password_hash:
            return True
        if not raw_password:
            return False
        return check_password(raw_password, self.password_hash)


class SalleVenteItem(models.Model):
    """NTCRM17 — UN élément affiché dans une salle de vente : un devis
    (rendu via le canal `/proposal` existant, JAMAIS un nouveau renderer —
    règle #4), un document GED (string-FK — jamais `ged.models`), un lien
    vidéo libre, ou une note libre. `reference` porte l'id cible (devis/GED)
    ou l'URL/texte selon `type`."""
    class TypeItem(models.TextChoices):
        DEVIS = 'devis', 'Devis'
        DOCUMENT = 'document', 'Document'
        VIDEO_LIEN = 'video_lien', 'Lien vidéo'
        NOTE = 'note', 'Note'

    salle = models.ForeignKey(  # on_delete: ligne fille d'une salle de vente, aucune existence hors de sa salle.
        SalleVente, on_delete=models.CASCADE, related_name='items')
    type = models.CharField(max_length=12, choices=TypeItem.choices)
    reference = models.CharField(
        max_length=500, blank=True, default='',
        help_text="Id du devis/document GED cible, ou URL/texte libre "
                  "(video_lien/note).")
    titre = models.CharField(max_length=200, blank=True, default='')
    ordre = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Élément de salle de vente'
        verbose_name_plural = 'Éléments de salle de vente'
        ordering = ['ordre', 'id']

    def __str__(self):
        return f'{self.get_type_display()} #{self.pk} (salle {self.salle_id})'


class SalleVenteVue(models.Model):
    """NTCRM18 — Journal de consultation d'une salle de vente publique.

    Une entrée par visite (timestamp + IP HACHÉE — jamais l'IP en clair,
    aucune autre PII). Alimente le compteur/dernière-vue de NTCRM19."""
    salle = models.ForeignKey(  # on_delete: trace de visite d'une salle ; la salle supprimée, la trace n'est plus rattachable (et ne doit pas survivre).
        SalleVente, on_delete=models.CASCADE, related_name='vues')
    ip_hash = models.CharField(max_length=64, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Vue de salle de vente'
        verbose_name_plural = 'Vues de salle de vente'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['salle', '-created_at'],
                         name='crm_salle_vue_salle_idx'),
        ]

    def __str__(self):
        return f'Vue salle {self.salle_id} @ {self.created_at:%Y-%m-%d %H:%M}'


# ── NTCRM20 — Registre des apporteurs d'affaires (Deal Registration) ───────
# NOTE DE COUVERTURE : `Partenaire`/`SoumissionLeadPartenaire`/
# `CommissionPartenaire` (FG234/235 — modèles relocalisés ici par ODX13, mais
# dont les ViewSets/serializers vivent encore sous `apps/compta/`) couvrent
# déjà un portail partenaire→lead→commission proche. `Apporteur`/
# `DealEnregistre` restent des modèles SÉPARÉS (comme demandé explicitement
# par NTCRM20) : la fenêtre de PROTECTION (refus d'un second enregistrement
# concurrent) n'existe nulle part dans FG234/235, et les étendre exigerait
# d'écrire dans l'app comptable — un futur run compta/crm conjoint pourra
# fusionner les deux registres.
class Apporteur(TenantModel):
    """NTCRM20 — Apporteur d'affaires B2B (partenaire/courtier/installateur
    indépendant) qui enregistre des deals plutôt que de soumettre des leads
    (contrairement à `Partenaire`/FG234, orienté soumission de prospects).

    ARC1 — hérite de ``core.models.TenantModel`` ; ``company`` redéclaré à
    l'identique (related_name + nullabilité historiques)."""
    class Type(models.TextChoices):
        PARTENAIRE_INSTALLATEUR = 'partenaire_installateur', 'Partenaire installateur'
        COURTIER = 'courtier', 'Courtier'
        APPORTEUR_INDEPENDANT = 'apporteur_independant', "Apporteur indépendant"
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(  # on_delete: référentiel d'apporteurs propre au tenant — purgé avec sa société.
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='apporteurs')
    nom = models.CharField(max_length=200, verbose_name='Nom')
    type_apporteur = models.CharField(
        max_length=24, choices=Type.choices, default=Type.AUTRE)
    contact_email = models.EmailField(blank=True, default='')
    contact_telephone = models.CharField(max_length=30, blank=True, default='')
    taux_commission_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='Taux de commission (%)')
    actif = models.BooleanField(default=True)
    # RIB optionnel pour versement de la commission — jamais un numéro de
    # carte/compte tiers, seulement l'identifiant bancaire du versement.
    rib = models.CharField(max_length=34, blank=True, default='', verbose_name='RIB')
    created_at = models.DateTimeField(auto_now_add=True)
    # NTCRM21 — token d'accès dédié au portail apporteur (lecture seule),
    # DISTINCT des comptes CustomUser — jamais de mot de passe/session, même
    # modèle de confiance que `ShareLink`/`PartageGed.token_acces`
    # (`Partenaire.token_acces`, FG234) : un jeton long/imprévisible = SEUL
    # secret d'accès à `GET /apporteur-portail/<token>/mes-deals/`.
    token_acces = models.CharField(
        max_length=64, unique=True, null=True, blank=True, editable=False,
        verbose_name="Token d'accès portail")

    class Meta:
        verbose_name = "Apporteur d'affaires"
        verbose_name_plural = "Apporteurs d'affaires"
        ordering = ['nom']

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        if not self.token_acces:
            import secrets
            self.token_acces = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)


def _lead_identity_keys(lead):
    """Clés d'identité d'un lead (email/téléphone normalisés) pour détecter
    le MÊME prospect enregistré par deux apporteurs différents."""
    keys = set()
    if lead.email:
        keys.add(('email', lead.email.strip().lower()))
    if lead.telephone:
        digits = ''.join(ch for ch in lead.telephone if ch.isdigit())
        if digits:
            keys.add(('tel', digits[-9:]))
    if lead.client_id:
        keys.add(('client', lead.client_id))
    return keys


class DealEnregistre(TenantModel):
    """NTCRM20 — Enregistrement d'un deal par un `Apporteur` sur UN lead.

    Protège l'apporteur contre une réassignation du MÊME prospect par un
    autre apporteur pendant `expire_le` (`clean()`). `montant_commission_
    estime` est calculé à l'acceptation du devis lié (NTCRM22).

    ARC1 — hérite de ``core.models.TenantModel`` ; ``company`` redéclaré à
    l'identique. ``date_enregistrement`` (métier) reste distinct des
    ``created_at``/``updated_at`` hérités."""
    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        APPROUVE = 'approuve', 'Approuvé'
        REJETE = 'rejete', 'Rejeté'
        EXPIRE = 'expire', 'Expiré'
        # NTCRM22 — commission calculée automatiquement à l'acceptation du
        # devis lié, en attente de règlement comptable.
        A_PAYER = 'a_payer', 'À payer'

    company = models.ForeignKey(  # on_delete: enregistrement de deal 100 % fille du tenant — purgé avec sa société.
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='deals_enregistres')
    apporteur = models.ForeignKey(  # on_delete: l'enregistrement matérialise l'antériorité DE CET apporteur ; sans lui il n'a plus de titulaire.
        Apporteur, on_delete=models.CASCADE, related_name='deals')
    lead = models.OneToOneField(  # on_delete: 1-1 avec le lead enregistré ; le lead disparu, la réservation d'antériorité n'a plus d'objet.
        'crm.Lead', on_delete=models.CASCADE, related_name='deal_enregistre')
    date_enregistrement = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.EN_ATTENTE)
    expire_le = models.DateTimeField(default=_default_deal_expiry)
    montant_commission_estime = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True)
    montant_commission_du = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Commission due (MAD)',
        help_text='Posé à `À_PAYER` par NTCRM22 (acceptation du devis lié).')

    class Meta:
        verbose_name = 'Deal enregistré'
        verbose_name_plural = 'Deals enregistrés'
        ordering = ['-date_enregistrement']

    def __str__(self):
        return f'Deal {self.apporteur.nom} — lead {self.lead_id}'

    @property
    def protection_active(self):
        from django.utils import timezone as _timezone
        if self.statut in (self.Statut.REJETE, self.Statut.EXPIRE):
            return False
        return self.expire_le is None or self.expire_le > _timezone.now()

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        if self.lead_id is None or self.company_id is None:
            return
        mes_cles = _lead_identity_keys(self.lead)
        if not mes_cles:
            return
        concurrents = (DealEnregistre.objects
                       .filter(company_id=self.company_id)
                       .exclude(pk=self.pk)
                       .exclude(apporteur_id=self.apporteur_id)
                       .select_related('lead'))
        for autre in concurrents:
            if not autre.protection_active:
                continue
            if _lead_identity_keys(autre.lead) & mes_cles:
                raise ValidationError(
                    'Ce client est déjà enregistré par un autre apporteur '
                    f'({autre.apporteur.nom}), protégé jusqu\'au '
                    f'{autre.expire_le:%d/%m/%Y} — enregistrement refusé.')


# ─────────────────────────────────────────────────────────────────────────────
# T-TRACE (ordres fondateur 25/08/2026) — traçage des visiteurs EXTERNES.
#
# « store IP … keep them stored » / « notify when two clients have any similar
# data that can show it is a competitor » / « and this at all the points … ».
#
# VÉRITÉ TECHNIQUE ACTÉE : l'adresse MAC n'est PAS collectable depuis le web
# (elle ne franchit jamais le routeur). L'identifiant PRIMAIRE d'un visiteur
# est donc ``appareil_id`` — un uuid que le SITE pose lui-même dans le
# localStorage du navigateur. L'IP reste stockée comme signal SECONDAIRE :
# le fondateur l'a explicitement jugée trompeuse (les IP sont massivement
# partagées au Maroc), elle ne suffit donc JAMAIS à affirmer une identité,
# seulement à étayer un soupçon libellé comme tel.
# ─────────────────────────────────────────────────────────────────────────────


class VisiteExterne(TenantModel):
    """T-TRACE — UN passage d'un visiteur EXTERNE sur une surface publique.

    FINALITÉ ANTI-FRAUDE (mention CNDP). Ces traces existent pour UNE seule
    raison : reconnaître une demande frauduleuse — un même appareil qui
    redemande un devis sous une autre identité, ou qui ouvre les propositions
    de plusieurs prospects différents (concurrent en reconnaissance). Elles ne
    servent ni au profilage publicitaire, ni à la revente, ni à la mesure
    d'audience, et ne portent aucune donnée déduite : uniquement ce que le
    visiteur a réellement fait, là où il l'a fait.

    Le jeton de la page visitée n'est JAMAIS stocké : seul son suffixe
    (6 derniers caractères) l'est, assez pour rapprocher deux traces d'un même
    lien dans une enquête, jamais assez pour rouvrir le lien.

    Rétention : AUCUNE purge automatique (ordre fondateur « keep them
    stored ») — la valeur anti-fraude d'une trace tient justement à sa
    longévité.

    Socle multi-tenant ARC1 : ``company`` + ``created_at``/``updated_at``
    viennent de ``TenantModel`` (jamais reposés à la main).
    """

    class Point(models.TextChoices):
        """Les cinq points de contact publics tracés (aucun autre)."""
        VISITE_SITE = 'visite_site', 'Visite du site'
        TUNNEL_LEAD = 'tunnel_lead', 'Demande de devis (tunnel)'
        PROPOSITION = 'proposition', 'Ouverture de proposition'
        QUESTIONNAIRE = 'questionnaire', 'Réponse au questionnaire'
        BOOKING = 'booking', 'Réservation de visite'

    #: Fenêtre pendant laquelle un battement supplémentaire du MÊME appareil
    #: sur la MÊME page met à jour la MÊME visite au lieu d'en ouvrir une
    #: nouvelle. Un beacon bat toutes les ~20 s : sans cette fenêtre, une
    #: lecture de 10 min produirait 30 lignes au lieu d'une.
    FENETRE_BATTEMENT_MINUTES = 30

    lead = models.ForeignKey(
        'crm.Lead',
        # on_delete: une trace anti-fraude SURVIT au lead qu'elle éclairait —
        # c'est précisément quand une fiche disparaît (fusion, suppression)
        # que l'historique de l'appareil garde sa valeur. Jamais une cascade.
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='visites_externes',
        verbose_name='Lead rattaché',
    )
    point = models.CharField(
        max_length=20, choices=Point.choices,
        default=Point.VISITE_SITE, verbose_name='Point de contact')
    # Page ou contexte COURT (« /tarifs », « section prix ») — jamais une URL
    # complète avec ses paramètres, jamais un contenu de formulaire.
    contexte = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Page / contexte')
    # 6 DERNIERS caractères du jeton de la page publique — jamais le jeton.
    token_suffixe = models.CharField(
        max_length=6, blank=True, default='', verbose_name='Suffixe du jeton')
    # Signal SECONDAIRE (voir l'en-tête de section) : lue côté serveur
    # (X-Forwarded-For / REMOTE_ADDR), JAMAIS acceptée d'un corps de requête.
    ip = models.CharField(
        max_length=64, blank=True, default='', verbose_name='Adresse IP')
    user_agent = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Navigateur (tronqué)')
    langue = models.CharField(
        max_length=10, blank=True, default='', verbose_name='Langue affichée')
    # Identifiant PRIMAIRE du visiteur (uuid localStorage posé par le site).
    appareil_id = models.CharField(
        max_length=64, blank=True, default='', db_index=True,
        verbose_name='Identifiant d’appareil')
    duree_s = models.PositiveIntegerField(
        default=0, verbose_name='Durée sur la page (s)')
    # Posé par le battement final (`fin: true`) : le battement suivant du même
    # appareil sur la même page ouvre alors une NOUVELLE visite.
    terminee = models.BooleanField(
        default=False, verbose_name='Visite terminée')

    class Meta:
        verbose_name = 'Visite externe (anti-fraude)'
        verbose_name_plural = 'Visites externes (anti-fraude)'
        ordering = ['-created_at']
        indexes = [
            # Les deux seules recherches faites sur cette table, toutes deux
            # company-scopées : « l'historique de CET appareil » et « qui
            # d'autre est passé par CETTE IP ».
            models.Index(fields=['company', 'appareil_id'],
                         name='crm_visite_comp_app_idx'),
            models.Index(fields=['company', 'ip'],
                         name='crm_visite_comp_ip_idx'),
        ]

    def __str__(self):
        return f'{self.get_point_display()} — {self.appareil_id[:8] or "?"}'


class AppareilEquipe(TenantModel):
    """QJ-EQUIPE-2 (14/09/2026) — registre SERVEUR des appareils de l'ÉQUIPE.

    ORDRE FONDATEUR (14/09/2026) : les appareils du fondateur (et de l'équipe)
    déclenchaient les alertes T-TRACE anti-fraude — le seul mécanisme
    d'exclusion existant était le cookie CLIENT ``tq_equipe`` vérifié par
    ``apps/ventes/public_views.py::_lecture_equipe`` (via
    ``crm.services.requete_marquee_equipe``) : fragile, posé par
    NAVIGATEUR, absent du navigateur intégré WhatsApp et de la navigation
    privée. Ce registre est le complément SERVEUR : un ``appareil_id`` marqué
    ici est exclu du comptage/des alertes anti-fraude PARTOUT, pour TOUJOURS,
    quel que soit le navigateur ou le cookie posé.

    RÉTROACTIF, ordre fondateur « keep them stored ». Les traces
    ``VisiteExterne`` déjà écrites pour cet appareil ne sont JAMAIS
    supprimées — elles restent dans la base pour l'historique — mais elles
    cessent d'être LUES par les alertes/corrélations dès l'instant du
    marquage, y compris celles créées AVANT ce marquage.

    Couche PERMANENTE et SÉPARÉE du cookie ``tq_equipe`` (QJ-EQUIPE
    09/09/2026) : celui-ci ne couvre qu'un navigateur à la fois et reste
    utile en repli ; celui-ci couvre l'appareil, partout, définitivement.
    """
    appareil_id = models.CharField(
        max_length=64, db_index=True, verbose_name='Identifiant d’appareil')
    libelle = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Libellé (ex. « Téléphone Reda »)')
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Enregistré par')

    class Meta:
        verbose_name = 'Appareil équipe (exclu du traçage)'
        verbose_name_plural = 'Appareils équipe (exclus du traçage)'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'appareil_id'],
                name='crm_appareil_equipe_company_uniq'),
        ]

    def __str__(self):
        return self.libelle or self.appareil_id[:8]


class Client(models.Model):
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        null=True,
        blank=True,
        related_name='clients',
    )

    class TypeClient(models.TextChoices):
        PARTICULIER = 'particulier', 'Particulier'
        ENTREPRISE = 'entreprise', 'Entreprise'

    nom = models.CharField(max_length=255)
    prenom = models.CharField(max_length=255, blank=True, null=True)
    # Optionnel depuis 2026-06 : un client peut être créé depuis un lead sans
    # email (l'unicité (company, email) reste garantie quand l'email existe).
    email = models.EmailField(blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    adresse = models.TextField(blank=True, null=True)
    # ── Type + identifiants légaux marocains (2026-06) — additif ──
    # Particulier → CIN ; Entreprise → ICE / IF / RC. Le formulaire montre le
    # bon jeu de champs selon le type. Migration de données : un client qui
    # porte déjà un ICE devient « Entreprise », sinon « Particulier ».
    type_client = models.CharField(
        max_length=12, choices=TypeClient.choices,
        default=TypeClient.PARTICULIER)
    cin = models.CharField(max_length=30, blank=True, null=True)
    # Identifiant Commun de l'Entreprise (clients professionnels marocains).
    # Optionnel : affiché sur les PDF uniquement quand renseigné.
    ice = models.CharField(max_length=30, blank=True, null=True)
    if_fiscal = models.CharField(max_length=30, blank=True, null=True)
    rc = models.CharField(max_length=30, blank=True, null=True)
    # ── CIQ402 (contrat CIQ8 ``client_entreprise.json``, D-CIQ-11) — le
    # client ENTREPRISE : siège, personne « à l'attention de », TVA
    # récupérable. Additifs, vides par défaut : aucun ancien client modifié.
    adresse_siege = models.TextField(
        blank=True, null=True, verbose_name='Adresse du siège',
        help_text="Sert au document et à la facture quand elle existe ; "
                  "sinon l'adresse (du site).")
    contact_nom = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name="À l'attention de",
        help_text="La personne qui représente l'entreprise.")
    contact_fonction = models.CharField(
        max_length=120, blank=True, null=True,
        verbose_name='Fonction du contact')
    tva_recuperable = models.CharField(
        max_length=12, blank=True, null=True,
        choices=[('oui', 'Oui'), ('non', 'Non'),
                 ('ne_sait_pas', 'Ne sait pas')],
        verbose_name='TVA récupérable',
        help_text='D-CIQ-3 : économies en HT si oui, en TTC sinon.')
    raison_sociale_a_confirmer = models.BooleanField(
        default=False, verbose_name='Raison sociale à confirmer',
        help_text="Commerçant en nom propre créé depuis un lead sans raison "
                  "sociale : le nom est celui de la personne — jamais "
                  'bloquant.')
    date_creation = models.DateTimeField(auto_now_add=True)
    # Traçabilité (additif) : qui a créé le client (forcé côté serveur) et
    # date de dernière modification. created_by est nullable (clients importés /
    # créés depuis un lead sans utilisateur courant) et SET_NULL pour ne jamais
    # perdre un client si l'utilisateur est supprimé.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clients_crees',
    )
    date_modification = models.DateTimeField(auto_now=True)
    # Champs personnalisés (T11) — valeurs indexées par CustomFieldDef.code.
    custom_data = models.JSONField(null=True, blank=True)
    # FG41 — plafond d'encours client (soft warning, jamais un blocage dur).
    # NULL = pas de limite définie (comportement actuel inchangé).
    # Quand défini, un devis/facture ajouté qui pousse l'encours TTC total
    # des factures ouvertes au-delà déclenche un avertissement API + UI.
    plafond_credit = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        verbose_name='Plafond de crédit (MAD TTC)',
        help_text='Seuil d\'encours client. Vide = pas de limite.',
    )
    # FG26 — RGPD : un client anonymisé (droit à l'effacement) a ses PII
    # scrubées tout en préservant l'intégrité comptable (devis/factures gardés).
    # Le drapeau bloque toute ré-identification accidentelle et marque la ligne.
    is_anonymized = models.BooleanField(default=False)
    anonymized_at = models.DateTimeField(null=True, blank=True)

    # N93 — langue des documents client-facing (facture / devis). Sert à marquer,
    # par client, la langue dans laquelle ses PDF doivent être produits. Le RENDU
    # Arabe du PDF (RTL + police arabe dans le moteur premium) est un chantier de
    # suivi distinct ; ce champ ne fait que porter la préférence. FR par défaut.
    class LangueDocument(models.TextChoices):
        FR = 'fr', 'Français'
        AR = 'ar', 'العربية'

    langue_document = models.CharField(
        max_length=2,
        choices=LangueDocument.choices,
        default=LangueDocument.FR,
        verbose_name='Langue des documents',
        help_text='Langue des factures / devis générés pour ce client.',
    )

    # XSAL1 — Liste de prix négociée (string-FK additive vers
    # ventes.ListePrix — jamais d'import direct de apps.ventes.models ici).
    # Vide = comportement historique inchangé (le client reste au
    # `Produit.prix_vente` standard, résolu par
    # `apps.ventes.services.prix_applicable`).
    liste_prix = models.ForeignKey(
        'ventes.ListePrix',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clients',
        verbose_name='Liste de prix',
        help_text="Tarif négocié pour ce client. Vide = prix de vente standard.",
    )

    # XFAC25 — envoi programmé (mensuel) du relevé de compte. Défaut OFF :
    # le relevé reste disponible uniquement à la demande (comportement actuel
    # inchangé). ON + email renseigné + encours non nul → un relevé PDF est
    # envoyé automatiquement le 1er du mois (job beat idempotent, voir
    # apps.ventes.scheduled.releve_mensuel_reminders).
    releve_mensuel_auto = models.BooleanField(
        default=False,
        verbose_name='Envoi mensuel automatique du relevé',
        help_text="Envoie automatiquement le relevé de compte PDF le 1er du "
                  "mois si l'encours n'est pas nul. Désactivé par défaut.",
    )
    # XFAC23 — conditions de paiement négociées par client (délai en jours,
    # ex. 30/60/90 — omniprésent en B2B marocain) + report facultatif en fin
    # de mois. NULL = pas de réglage → comportement actuel inchangé (fallback
    # +30 j dans apps.ventes.scheduled._echeance_effective).
    delai_paiement_jours = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name='Délai de paiement (jours)',
        help_text='Vide = comportement par défaut (+30 j depuis émission).',
    )
    fin_de_mois = models.BooleanField(
        default=False,
        verbose_name='Échéance reportée en fin de mois',
        help_text=(
            "Si coché, l'échéance calculée depuis le délai est reportée au "
            "dernier jour de son mois (ex. « 60 jours fin de mois »)."
        ),
    )

    # ── XSAL9 — Hiérarchie de comptes (société mère / filiales) ──
    # Self-FK nullable, additif : un groupe (ex. holding agricole à 3 fermes)
    # peut lier ses fiches Client sans fusionner leurs données. `clean()`
    # garde contre un cycle ; la même société uniquement (jamais cross-tenant).
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='filiales',
        verbose_name='Société mère',
        help_text="Rattache ce client à une société mère (consolidation "
                  "CA groupe). Même société uniquement ; jamais de cycle.")

    # ── QX35 — Code de parrainage DÉTERMINISTE (additif) ──
    # Dérivé du pk (ex. « TQ-1042 ») dès la première sauvegarde — jamais un
    # UUID aléatoire : un code stable, lisible, copiable dans un lien
    # `?utm_source=parrainage&utm_campaign=<code>` (parrainage.astro). Unique
    # par construction (dérivé du pk) ; nullable pour les lignes existantes
    # tant qu'elles ne sont pas resauvegardées (comportement inchangé).
    code_parrainage = models.CharField(
        max_length=20, blank=True, null=True, unique=True,
        verbose_name='Code de parrainage',
        help_text="Code stable partagé par ce client pour parrainer un "
                  "prospect (lien /devis/mon-toit?utm_source=parrainage&"
                  "utm_campaign=<code>).",
    )
    # ── ARC18 — Pont additif vers le répertoire unifié Tiers ──
    # FK nullable (string-FK — jamais d'import de apps.tiers.models ici, crm
    # reste découplé de la couche fondation par référence string). L'identité
    # reste MAÎTRE ici ; ``tiers`` n'en est qu'un MIROIR one-way, réversible,
    # posé par le hook de sauvegarde (voir apps/crm/tiers_bridge.py) et
    # backfillé par la commande ``backfill_tiers``. Vide = pas encore relié
    # (comportement API historique strictement inchangé).
    tiers = models.ForeignKey(
        'tiers.Tiers',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='clients',
        verbose_name='Tiers (répertoire unifié)',
        help_text="Fiche du répertoire unifié des parties prenantes reflétant "
                  "ce client. Renseignée automatiquement (miroir).")
    # ── ZSAL9 — Avertissement de vente (« sale warnings » façon Odoo) ──
    # Message optionnel affiché quand ce client est sélectionné dans le
    # générateur de devis (ex. « client à traiter au comptant »). Si
    # ``avertissement_bloquant`` est True, une garde serveur refuse
    # l'acceptation / la génération de facture d'un devis pour ce client SAUF
    # override responsable/admin journalisé (patron XFAC28). Vide (défaut) =
    # comportement historique strictement inchangé. Jamais de prix d'achat ici.
    avertissement_vente = models.TextField(
        blank=True, default='',
        verbose_name='Avertissement de vente',
        help_text="Message affiché au devis quand ce client est sélectionné.")
    avertissement_bloquant = models.BooleanField(
        default=False,
        verbose_name='Avertissement bloquant',
        help_text="Si activé, empêche l'acceptation/facturation sans override "
                  "responsable/admin.")

    # NTCRM14 — anti-spam : horodatage de la dernière notification "compte
    # dormant" envoyée au commercial propriétaire pour ce client. NULL = pas
    # encore alerté. Posé par la commande `detecter_comptes_dormants` (une
    # seule alerte par franchissement de seuil, jamais répétée en boucle).
    derniere_alerte_dormance = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Dernière alerte de dormance',
        help_text="Date de la dernière notification 'compte dormant' envoyée "
                  "pour ce client. Vide = jamais alerté.")

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        unique_together = [('company', 'email')]
        constraints = [
            # CRX24 — unicité de l'e-mail INSENSIBLE À LA CASSE. Le
            # ``unique_together`` ci-dessus est sensible à la casse, alors que
            # toutes les recherches de client se font en ``email__iexact``
            # (``services.resolve_client_for_lead``) : « A@x.ma » et « a@x.ma »
            # étaient donc DEUX lignes que le code traitait comme une seule —
            # le doublon naissait à la création, la lecture n'en voyait qu'un,
            # et les devis se répartissaient entre les deux fiches.
            # Index fonctionnel partiel : les e-mails vides/NULL restent
            # multiples (un client sans e-mail est légitime et fréquent).
            models.UniqueConstraint(
                'company', Lower('email'),
                name='crx24_client_email_unique_ci',
                condition=models.Q(email__isnull=False) & ~models.Q(email=''),
                violation_error_message=(
                    "Un client de cette société porte déjà cet e-mail "
                    "(la casse ne compte pas)."),
            ),
        ]

    def __str__(self):
        return f"{self.nom} {self.prenom if self.prenom else ''}"

    def save(self, *args, **kwargs):
        # QX35 — génère le code de parrainage APRÈS la première sauvegarde
        # (a besoin du pk pour rester déterministe et unique sans collision) —
        # patron standard Django « dérivé du pk », deuxième save() ciblé sur
        # le seul champ concerné (jamais de boucle : ne s'exécute qu'une
        # fois, quand code_parrainage est encore vide).
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and not self.code_parrainage:
            self.code_parrainage = f'TQ-{self.pk}'
            # QX35 — écrire via QuerySet.update() plutôt qu'un 2ᵉ save() : un
            # second save() re-déclenche le post_save (le miroir tiers ARC18
            # créerait alors un DOUBLON pour un client sans clé). .update() pose
            # le champ en base sans signal ; l'instance le porte déjà.
            type(self).objects.filter(pk=self.pk).update(
                code_parrainage=self.code_parrainage)

    def clean(self):
        super().clean()
        # XSAL9 — anti-cycle : `parent` ne peut jamais créer une boucle
        # (A→B→A) ni se référencer lui-même, et doit rester dans la MÊME
        # société (jamais de hiérarchie cross-tenant).
        if self.parent_id is None:
            return
        if self.parent_id == self.pk:
            from django.core.exceptions import ValidationError
            raise ValidationError(
                {'parent': "Un client ne peut pas être sa propre société mère."})
        if self.company_id and self.parent.company_id != self.company_id:
            from django.core.exceptions import ValidationError
            raise ValidationError(
                {'parent': 'La société mère doit appartenir à la même société.'})
        seen = {self.pk} if self.pk else set()
        current = self.parent
        depth = 0
        while current is not None:
            if current.pk in seen or depth > 100:
                from django.core.exceptions import ValidationError
                raise ValidationError(
                    {'parent': 'Cette hiérarchie créerait un cycle.'})
            seen.add(current.pk)
            current = current.parent
            depth += 1


class Parrainage(models.Model):
    """N98 — parrainage : un client (parrain) recommande un prospect (filleul).

    Le filleul peut être un lead non encore converti et/ou un client. La
    récompense (configurable, défaut en Paramètres) est versée une fois le
    parrainage « converti ». Additif, borné société.
    """
    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        CONVERTI = 'converti', 'Converti'
        RECOMPENSE_VERSEE = 'recompense_versee', 'Récompense versée'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        null=True, blank=True, related_name='parrainages')
    parrain = models.ForeignKey(
        'crm.Client', on_delete=models.PROTECT,
        related_name='parrainages_donnes')
    filleul_lead = models.ForeignKey(
        'crm.Lead', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='parrainages')
    filleul_client = models.ForeignKey(
        'crm.Client', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='parrainages_recus')
    filleul_nom = models.CharField(max_length=200, blank=True, default='')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE)
    recompense = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_creation']
        verbose_name = 'Parrainage'

    def __str__(self):
        return f'Parrainage #{self.pk} (parrain {self.parrain_id})'

    @property
    def filleul_display_nom(self) -> str:
        """DC14 — nom du filleul affiché, le FK étant la source prioritaire.

        ``filleul_nom`` (texte libre) peut diverger du FK lié. Quand un
        ``filleul_client`` ou ``filleul_lead`` est présent, on affiche SON nom
        (source de vérité) ; sinon on retombe sur le texte libre saisi.
        """
        if self.filleul_client_id and self.filleul_client:
            return self.filleul_client.nom
        if self.filleul_lead_id and self.filleul_lead:
            return self.filleul_lead.nom
        return self.filleul_nom or ''


class ObjectifCommercial(models.Model):
    """FG39 — Objectif commercial / KPI target (objectif vs réalisé).

    Chaque objectif porte une métrique, une période et une cible (Decimal).
    Le « réalisé » est calculé à la demande (endpoint attainment) depuis les
    données du domaine CRM — pas stocké, pour rester toujours à jour.

    Métriques CRM-only (pas d'import ventes) :
      - nb_leads    : leads créés dans la période
      - nb_contacts : leads passés en CONTACTED+ dans la période
      - nb_devis    : placeholder (réalisé = 0 sans données ventes)
      - ca_signe    : placeholder (réalisé = 0 sans données ventes)
      - nb_rdv      : rendez-vous effectués dans la période

    Les métriques ``nb_devis`` et ``ca_signe`` sont exposées pour permettre
    au fondateur de saisir des cibles maintenant ; le réalisé sera branché
    quand la couche service ventes sera exposée via un sélecteur cross-app.
    (Aucun import de ``apps.ventes.models`` ici — règle import-linter.)
    """

    class PeriodType(models.TextChoices):
        MONTH = 'month', 'Mensuel'
        QUARTER = 'quarter', 'Trimestriel'
        YEAR = 'year', 'Annuel'

    class Metric(models.TextChoices):
        NB_LEADS = 'nb_leads', 'Nombre de leads'
        NB_CONTACTS = 'nb_contacts', 'Leads contactés'
        NB_DEVIS = 'nb_devis', 'Nombre de devis'
        CA_SIGNE = 'ca_signe', 'CA signé (MAD TTC)'
        NB_RDV = 'nb_rdv', 'Rendez-vous effectués'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        null=True,
        blank=True,
        related_name='objectifs_commerciaux',
    )
    # Responsable optionnel — NULL = objectif d'équipe global.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,  # on_delete: objectif attribué à un commercial — l'objectif reste si l'utilisateur est supprimé
        null=True,
        blank=True,
        related_name='crm_objectifs',
        verbose_name='Responsable',
    )
    metric = models.CharField(
        max_length=20,
        choices=Metric.choices,
        verbose_name='Métrique',
    )
    period_type = models.CharField(
        max_length=10,
        choices=PeriodType.choices,
        default=PeriodType.MONTH,
        verbose_name='Périodicité',
    )
    # Année du début de la période (ex. 2026). Pour un trimestre : trimestre
    # 1 = mois 1–3 de cette année. Pour un mois : period_month (1–12).
    period_year = models.PositiveSmallIntegerField(verbose_name='Année')
    # Pour les objectifs mensuels (1–12) ; ignoré pour les trimestriels/annuels.
    period_month = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name='Mois (1–12)',
        help_text='Uniquement pour les objectifs mensuels.',
    )
    # Pour les objectifs trimestriels (1–4) ; ignoré sinon.
    period_quarter = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name='Trimestre (1–4)',
        help_text='Uniquement pour les objectifs trimestriels.',
    )
    cible = models.DecimalField(
        max_digits=14, decimal_places=2,
        verbose_name='Cible',
    )
    notes = models.TextField(blank=True, null=True, verbose_name='Notes')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='crm_objectifs_crees',
        verbose_name='Créé par',
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Objectif commercial'
        verbose_name_plural = 'Objectifs commerciaux'
        ordering = ['-period_year', '-period_month', 'metric']
        # Contraintes nommées (pas d'Index sans nom — règle CI-enforced).
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'owner', 'metric',
                        'period_type', 'period_year', 'period_month'],
                name='crm_obj_uniq_month',
                condition=models.Q(period_type='month'),
            ),
            models.UniqueConstraint(
                fields=['company', 'owner', 'metric',
                        'period_type', 'period_year', 'period_quarter'],
                name='crm_obj_uniq_quarter',
                condition=models.Q(period_type='quarter'),
            ),
            models.UniqueConstraint(
                fields=['company', 'owner', 'metric',
                        'period_type', 'period_year'],
                name='crm_obj_uniq_year',
                condition=models.Q(period_type='year'),
            ),
        ]

    def __str__(self):
        return (
            f'{self.get_metric_display()} — {self.period_type} '
            f'{self.period_year} (cible {self.cible})'
        )


class ConcurrentPerte(models.Model):
    """FG242 — Suivi des concurrents sur deals perdus.

    Sur un lead PERDU (drapeau ``Lead.perdu`` — voir STAGES.py : « Perdu » est un
    lost-flag, pas une étape), on saisit le concurrent qui a remporté l'affaire
    et son prix. Cette intelligence concurrentielle alimente l'analyse des
    pertes (qui nous bat, à quel prix, sur quel motif).

    Additif et borné société : un enregistrement appartient à la société du lead
    (posée côté serveur, jamais lue du corps de requête — multi-tenant). Le motif
    réutilise le vocabulaire ``Lead.motif_perte`` (texte libre alimenté par la
    liste gérée ``MotifPerte``), donc aucun nouveau jeu de valeurs n'est inventé.
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        null=True,
        blank=True,
        related_name='concurrents_perte',
    )
    lead = models.ForeignKey(
        'crm.Lead',
        on_delete=models.CASCADE,  # on_delete: ConcurrentPerte est le détail de Lead — n'existe pas sans lui
        related_name='concurrents_perte',
        verbose_name='Lead perdu',
    )
    # Nom du concurrent gagnant (obligatoire — c'est le cœur de l'intel).
    concurrent_nom = models.CharField(
        max_length=200,
        verbose_name='Concurrent gagnant',
    )
    # Prix proposé par le concurrent (optionnel : pas toujours connu).
    concurrent_prix = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(0)],
        verbose_name='Prix du concurrent',
        help_text='Prix proposé par le concurrent. Vide si inconnu.',
    )
    # Devise du prix (défaut MAD) ; courte par convention ISO-ish.
    devise = models.CharField(
        max_length=8,
        default='MAD',
        blank=True,
        verbose_name='Devise',
    )
    # Motif de la perte — réutilise le vocabulaire de Lead.motif_perte (texte
    # libre alimenté par la liste gérée MotifPerte). Optionnel.
    motif = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name='Motif de la perte',
    )
    notes = models.TextField(blank=True, null=True, verbose_name='Notes')
    # Traçabilité : qui a saisi l'info (forcé côté serveur) + quand.
    saisi_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='concurrents_perte_saisis',
        verbose_name='Saisi par',
    )
    saisi_le = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Concurrent (deal perdu)'
        verbose_name_plural = 'Concurrents (deals perdus)'
        ordering = ['-saisi_le']
        indexes = [
            # Nom d'index ≤ 30 chars (règle CI-enforced).
            models.Index(fields=['company', 'lead'],
                         name='crm_concperte_co_lead_idx'),
        ]

    def __str__(self):
        return (
            f'Concurrent {self.concurrent_nom} '
            f'(lead {self.lead_id})'
        )


class PlanActivite(models.Model):
    """ZSAL2 — Plan d'activité (Odoo « Activity Plans ») : séquence de tâches
    pré-définies applicable à un lead d'un clic (ex. « Nouveau lead solaire »
    = J0 appeler, J1 email étude, J3 visite technique, J7 relance devis).

    Distinct des séquences marketing XMKT (email/SMS automatisés côté
    marketing) : ceci est une CHECKLIST d'activités internes du commercial,
    matérialisée en ``records.Activity`` sur le lead cible.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        related_name='plans_activite')
    nom = models.CharField(max_length=120)
    actif = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Plan d'activité"
        verbose_name_plural = "Plans d'activité"
        ordering = ['nom']

    def __str__(self):
        return self.nom


class EtapePlanActivite(models.Model):
    """ZSAL2 — Une étape d'un :class:`PlanActivite` : un type d'activité à
    créer, ``delai_jours`` après la date d'application du plan (0 = le jour
    même), avec un résumé par défaut et un assigné par défaut optionnel
    (owner du lead si vide, sinon un utilisateur fixe)."""
    plan = models.ForeignKey(
        PlanActivite, on_delete=models.CASCADE, related_name='etapes')  # on_delete: historique/chatter de PlanActivite — suit son objet
    ordre = models.PositiveIntegerField(default=0)
    activity_type = models.ForeignKey(
        'records.ActivityType', on_delete=models.PROTECT,
        related_name='etapes_plan_activite')
    delai_jours = models.PositiveIntegerField(
        default=0,
        help_text="Nombre de jours après l'application du plan (0 = le jour même).")
    resume_defaut = models.CharField(max_length=255, blank=True, default='')
    # NULL = assigné par défaut = owner du lead ciblé (résolu à l'application).
    assigne_par_defaut = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='etapes_plan_activite_assignees')

    class Meta:
        verbose_name = "Étape de plan d'activité"
        verbose_name_plural = "Étapes de plan d'activité"
        ordering = ['plan', 'ordre', 'delai_jours']

    def __str__(self):
        return f'{self.plan.nom} — J{self.delai_jours} {self.resume_defaut}'.strip()


class EquipeCommerciale(models.Model):
    """ZSAL3 — Équipe commerciale (Odoo « Sales Teams / My Teams »).

    PAS un pipeline/étapes propre à l'équipe (règle #2 — STAGES.py reste
    l'unique source des étapes) : juste un regroupement de commerciaux pour
    agréger un tableau de bord d'équipe (pipeline ouvert, valeur pondérée,
    activités en retard, avancement vs objectif). ``responsable`` est le
    manager d'équipe (peut ne pas être membre lui-même) ; ``membres`` est un
    M2M additif — n'importe quel utilisateur peut appartenir à 0 ou 1+ équipe
    (comportement historique inchangé : un commercial sans équipe reste visible
    partout ailleurs, seul le dashboard « Mes équipes » l'ignore).
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        related_name='equipes_commerciales')
    nom = models.CharField(max_length=120)
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,  # on_delete: chef d'équipe informatif — l'équipe survit à son départ
        null=True, blank=True, related_name='equipes_dirigees')
    membres = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='equipes_commerciales')
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Équipe commerciale'
        verbose_name_plural = 'Équipes commerciales'
        ordering = ['nom']

    def __str__(self):
        return self.nom


# ── NTCRM4 — Catégories de forecast (commit/best-case/pipeline/omis) ─────────
class ForecastEntry(TenantModel):
    """Catégorisation forecast d'UN lead, liée 1-1 pour ne pas alourdir
    ``Lead``. Un lead SANS ``ForecastEntry`` explicite est classé PIPELINE par
    défaut (voir ``montant_effectif``/le sélecteur ``forecast_rollup`` — aucune
    migration de données requise).

    ARC1 — hérite de ``core.models.TenantModel``; ``company`` redéclaré à
    l'identique (related_name historique)."""

    class Categorie(models.TextChoices):
        COMMIT = 'commit', 'Commit'
        BEST_CASE = 'best_case', 'Best case'
        PIPELINE = 'pipeline', 'Pipeline'
        OMIS = 'omis', 'Omis'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='forecast_entries')
    lead = models.OneToOneField(
        Lead, on_delete=models.CASCADE,  # on_delete: entrée sans objet si lead supprimé
        related_name='forecast_entry')
    categorie = models.CharField(
        max_length=12, choices=Categorie.choices, default=Categorie.PIPELINE)
    # Vide = repli sur le devis actif le plus récent du lead, sinon
    # `Lead.montant_estime` (voir la propriété `montant_effectif`).
    montant_prevu = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Montant prévu (MAD)')
    commentaire = models.TextField(blank=True, default='')
    mis_a_jour_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='forecast_entries_maj')
    mis_a_jour_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Entrée de forecast'
        verbose_name_plural = 'Entrées de forecast'
        ordering = ['-mis_a_jour_le']

    def __str__(self):
        return f'{self.lead_id} — {self.categorie}'

    @property
    def montant_effectif(self):
        """Montant retenu pour l'agrégation forecast : ``montant_prevu`` posé
        explicitement, sinon le devis ACTIF le plus récent du lead, sinon
        ``Lead.montant_estime`` (XSAL7), sinon zéro."""
        from decimal import Decimal
        if self.montant_prevu is not None:
            return self.montant_prevu
        try:
            devis = self.lead.devis.filter(is_active=True).order_by(
                '-date_creation').first()
            if devis is not None:
                return devis.total_ttc
        except Exception:
            pass
        return self.lead.montant_estime or Decimal('0')


# ── NTCRM6 — Snapshots hebdomadaires du forecast ──────────────────────────────
class ForecastSnapshot(TenantModel):
    """Photo hebdomadaire agrégée du forecast (glissement visible dans le
    temps) — créée par ``manage.py snapshot_forecast_hebdo`` (idempotente : un
    seul snapshot par semaine ISO + owner, upsert). ``owner`` nul = snapshot
    SOCIÉTÉ (tous commerciaux confondus) ; renseigné = snapshot individuel.

    ARC1 — hérite de ``core.models.TenantModel``; ``company`` redéclaré à
    l'identique (related_name historique). ``created_at`` hérité de
    TenantModel (à l'identique)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='forecast_snapshots')
    semaine_iso = models.CharField(
        max_length=8, verbose_name='Semaine ISO (ex. 2026-W29)')
    categorie = models.CharField(
        max_length=12, choices=ForecastEntry.Categorie.choices)
    montant_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    nb_leads = models.PositiveIntegerField(default=0)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        # on_delete: snapshot individuel lié à l'utilisateur (CASCADE conservé
        # plutôt que SET_NULL pour ne pas risquer une collision avec le
        # snapshot société existant sous la même contrainte unique)
        null=True, blank=True, related_name='forecast_snapshots')

    class Meta:
        verbose_name = 'Snapshot de forecast'
        verbose_name_plural = 'Snapshots de forecast'
        ordering = ['-semaine_iso']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'semaine_iso', 'categorie', 'owner'],
                name='crm_forecast_snapshot_uniq_semaine_owner',
            ),
        ]

    def __str__(self):
        return f'{self.semaine_iso} {self.categorie} = {self.montant_total}'


# ── NTCRM10 — Plan de compte (Account Planning) formel ────────────────────────
class PlanCompte(TenantModel):
    """Plan de compte stratégique pour un client (création MANUELLE only —
    réservé aux comptes stratégiques, pas tous les clients).

    ARC1 — hérite de ``core.models.TenantModel``; ``company`` redéclaré à
    l'identique (related_name historique). Les timestamps propres
    (``date_creation``/``date_modification``) restent distincts des
    ``created_at``/``updated_at`` hérités (noms différents, conservés)."""

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        ACTIF = 'actif', 'Actif'
        ARCHIVE = 'archive', 'Archivé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='plans_compte')
    client = models.OneToOneField(
        Client, on_delete=models.CASCADE,  # on_delete: plan sans objet si client supprimé
        related_name='plan_compte')
    objectifs_strategiques = models.TextField(blank=True, default='')
    potentiel_estime = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Potentiel estimé (MAD)')
    # Distinct de ConcurrentPerte/FG242 (qui ne couvre que les deals PERDUS) —
    # ici, un texte libre sur les concurrents présents chez ce compte.
    concurrents_presents = models.TextField(blank=True, default='')
    swot_forces = models.JSONField(null=True, blank=True)
    swot_faiblesses = models.JSONField(null=True, blank=True)
    swot_opportunites = models.JSONField(null=True, blank=True)
    swot_menaces = models.JSONField(null=True, blank=True)
    prochaine_revue = models.DateField(null=True, blank=True)
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.BROUILLON)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='plans_compte_crees')
    mis_a_jour_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='plans_compte_maj')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Plan de compte'
        verbose_name_plural = 'Plans de compte'
        ordering = ['-date_modification']

    def __str__(self):
        return f'Plan de compte — {self.client_id}'


# ARC8 — l'historique (chatter) d'un ``PlanCompte`` NE passe PLUS par un modèle
# ``*Activity`` maison : il converge sur ``records.Activity`` via
# ``records.services.log_activity`` / ``chatter_qs`` (voir ``PlanCompteViewSet``).


# ── NTCRM30 (préparé par NTCRM10/11) — Revue de compte ────────────────────────
class RevueCompte(models.Model):
    """Note de réunion structurée liée à un ``PlanCompte`` (même esprit que
    ``ReunionChantier``/FG296 côté commercial), affichée en timeline."""
    plan = models.ForeignKey(
        PlanCompte, on_delete=models.CASCADE,  # on_delete: composant du parent
        related_name='revues')
    date_revue = models.DateField()
    participants = models.TextField(blank=True, default='')
    decisions = models.TextField(blank=True, default='')
    prochaine_action = models.CharField(max_length=255, blank=True, default='')
    prochaine_action_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='revues_compte_creees')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Revue de compte'
        verbose_name_plural = 'Revues de compte'
        ordering = ['-date_revue']

    def __str__(self):
        return f'Revue {self.plan_id} — {self.date_revue}'


# ── NTCRM12 — Playbooks de vente par étape (STAGES.py — jamais codé en dur) ──
class Playbook(TenantModel):
    """ARC1 — hérite de ``core.models.TenantModel``; ``company`` redéclaré à
    l'identique (related_name historique)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='playbooks')
    nom = models.CharField(max_length=150)
    actif = models.BooleanField(default=True)
    # CRX35 — le drapeau ``bloquant`` a été RETIRÉ (migration 0088) : aucun
    # code ne le lisait, donc un playbook « bloquant » ne bloquait rien. Un
    # changement d'étape reste TOUJOURS possible même avec des tâches
    # obligatoires non cochées (avertissement seulement) — « never auto-move »,
    # jamais un blocage dur. Le rétablir supposerait d'écrire la garde, pas
    # seulement la colonne.
    # NTCRM26 — critère de sélection optionnel (arbre core.rules FG367, évalué
    # contre {type_installation, canal} du lead). ``None`` = playbook
    # universel (comportement historique, s'applique à tout lead) ; renseigné
    # = ce playbook n'entre en jeu QUE pour les leads qui matchent, permettant
    # plusieurs playbooks actifs sur le même stage (un par profil de lead)
    # sans dupliquer les tâches sur un profil non concerné.
    condition = models.JSONField(
        null=True, blank=True, verbose_name='Critère de sélection',
        help_text="Arbre de conditions (core.rules) évalué contre "
                  "{type_installation, canal} du lead. Vide = s'applique à tout lead.")
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Playbook'
        verbose_name_plural = 'Playbooks'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class PlaybookEtape(models.Model):
    """Étape d'un playbook — la clé ``stage`` vient TOUJOURS de STAGES.py
    (``STAGE_CHOICES``), jamais codée en dur (règle #2)."""
    playbook = models.ForeignKey(
        Playbook, on_delete=models.CASCADE,  # on_delete: composant du parent
        related_name='etapes')
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES)
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Étape de playbook'
        verbose_name_plural = 'Étapes de playbook'
        ordering = ['ordre', 'id']
        unique_together = [('playbook', 'stage')]

    def __str__(self):
        return f'{self.playbook.nom} — {self.stage}'


class PlaybookTache(models.Model):
    etape = models.ForeignKey(
        PlaybookEtape, on_delete=models.CASCADE,  # on_delete: composant du parent
        related_name='taches')
    libelle = models.CharField(max_length=255)
    obligatoire = models.BooleanField(default=False)
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Tâche de playbook'
        verbose_name_plural = 'Tâches de playbook'
        ordering = ['ordre', 'id']

    def __str__(self):
        return self.libelle


class LeadPlaybookProgress(models.Model):
    """Progression d'UN lead sur UNE tâche de playbook — créée automatiquement
    (signal ``core.events.lead_stage_changed``, voir ``receivers.py``) quand le
    lead entre dans une étape portant un playbook actif. Cocher une tâche pose
    l'acteur + la date, jamais silencieux."""
    lead = models.ForeignKey(
        Lead, on_delete=models.CASCADE,  # on_delete: progression sans objet si lead supprimé
        related_name='playbook_progress')
    tache = models.ForeignKey(
        PlaybookTache, on_delete=models.CASCADE,  # on_delete: composant du parent
        related_name='progressions')
    fait = models.BooleanField(default=False)
    fait_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='playbook_taches_faites')
    fait_le = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Progression playbook du lead'
        verbose_name_plural = 'Progressions playbook des leads'
        ordering = ['tache__ordre', 'id']
        unique_together = [('lead', 'tache')]

    def __str__(self):
        return f'{self.lead_id} — {self.tache_id} ({"fait" if self.fait else "à faire"})'


class Defi(TenantModel):
    """NTCRM23 — Défi d'équipe temporaire (gamification), distinct de
    `ObjectifCommercial` (FG39, cible individuelle PERMANENTE privée) : un
    défi est PUBLIC (visible de toute l'équipe, cf. NTCRM24), sur une fenêtre
    de dates explicite (pas un système année/mois/trimestre), avec un
    classement plutôt qu'un simple taux d'atteinte. Réutilise STRICTEMENT
    `ObjectifCommercial.Metric` (jamais une seconde taxonomie de métriques).

    ARC1 — hérite de ``core.models.TenantModel`` ; ``company`` redéclaré à
    l'identique (related_name + nullabilité historiques)."""
    company = models.ForeignKey(  # on_delete: défi commercial interne au tenant — purgé avec sa société.
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='defis')
    nom = models.CharField(max_length=200, verbose_name='Nom du défi')
    periode_debut = models.DateField(verbose_name='Début')
    periode_fin = models.DateField(verbose_name='Fin')
    metrique = models.CharField(
        max_length=12, choices=ObjectifCommercial.Metric.choices,
        verbose_name='Métrique')
    cible_equipe = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name="Cible d'équipe (optionnelle)")
    recompense = models.CharField(
        max_length=300, blank=True, default='', verbose_name='Récompense')
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Défi d'équipe"
        verbose_name_plural = "Défis d'équipe"
        ordering = ['-periode_debut', '-id']

    def __str__(self):
        return self.nom
