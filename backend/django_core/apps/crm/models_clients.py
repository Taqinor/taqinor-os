"""Modèles crm « clients & partenaires » sortis de ``models.py`` (SPL91).

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
from django.db import models

from core.models import TenantModel

from .models import (
    _default_deal_expiry, _default_salle_vente_expiry,
    _default_salle_vente_token)

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
