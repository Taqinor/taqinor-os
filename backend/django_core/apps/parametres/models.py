from decimal import Decimal

from django.conf import settings
from django.db import models


class CompanyProfile(models.Model):
    """
    Un profil par entreprise (utilisé dans les PDFs et paramètres).
    Pour la rétro-compatibilité, pk=1 reste l'instance par défaut
    lorsqu'aucune company n'est fournie.
    """
    company = models.OneToOneField(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='profile',
    )
    nom = models.CharField(max_length=255, default='Mon Entreprise')
    adresse = models.TextField(blank=True, default='')
    email = models.EmailField(blank=True, default='')
    telephone = models.CharField(max_length=30, blank=True, default='')
    siret = models.CharField(max_length=20, blank=True, default='')
    tva_intra = models.CharField(max_length=20, blank=True, default='')
    # ── Identifiants légaux marocains (2026-06) — additif, tout optionnel ──
    # L'ICE du vendeur est légalement obligatoire sur une facture marocaine.
    # siret/tva_intra (style français) restent en place mais inutilisés ici.
    ice = models.CharField(
        max_length=30, blank=True, default='',
        help_text='Identifiant Commun de l\'Entreprise (obligatoire sur facture).')
    identifiant_fiscal = models.CharField(
        max_length=30, blank=True, default='',
        help_text='IF — Identifiant Fiscal.')
    rc = models.CharField(
        max_length=30, blank=True, default='',
        help_text='RC — Registre de Commerce.')
    patente = models.CharField(
        max_length=30, blank=True, default='',
        help_text='Patente / Taxe Professionnelle.')
    cnss = models.CharField(
        max_length=30, blank=True, default='',
        help_text='Numéro d\'affiliation CNSS.')
    rib = models.CharField(max_length=50, blank=True, default='')
    banque = models.CharField(max_length=100, blank=True, default='')
    couleur_principale = models.CharField(
        max_length=7, default='#2563EB'
    )
    logo_key = models.CharField(max_length=500, blank=True, default='')
    signature_key = models.CharField(
        max_length=500, blank=True, default=''
    )
    # Responsable assigné par défaut aux NOUVEAUX leads (site + manuel) quand
    # aucun responsable n'est choisi à la création. Initialisé sur le compte
    # « Meryem » par migration de données ; modifiable dans Paramètres.
    responsable_defaut_leads = models.ForeignKey(
        'authentication.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )

    # ── Paramètres métier éditables (2026-06) — ADDITIFS ──
    # Chacun a pour défaut la valeur codée en dur aujourd'hui : tant que le
    # founder n'édite rien, le comportement est strictement identique.
    # Échéancier par mode : {mode: {acompte, materiel, solde}} en %. NULL =
    # repli sur PAYMENT_TERMS_BY_MODE (défaut historique 30/60/10 · 30/60/10 ·
    # 50/40/10).
    payment_terms = models.JSONField(null=True, blank=True)
    # Durée de validité du devis (jours). Défaut historique 30.
    quote_validity_days = models.PositiveIntegerField(default=30)
    # Heures de pompage effectives/jour par défaut (mode agricole). Défaut 7.
    agricole_pump_hours = models.DecimalField(
        max_digits=4, decimal_places=1, default=7)
    # Préfixes de numérotation des pièces : {devis,facture,avoir,bon_commande}.
    # NULL = repli sur les préfixes historiques (DEV/FAC/AVO/BC).
    doc_prefixes = models.JSONField(null=True, blank=True)
    # Numérotation par type de pièce (D3) : largeur de remplissage + période de
    # réinitialisation. Forme {key: {padding:int, reset:'monthly'|'yearly'|'none'}}.
    # NULL/clé absente = défaut historique (padding 4, reset mensuel) → la
    # numérotation reste strictement identique tant que rien n'est édité. Le
    # préfixe lui-même reste dans doc_prefixes (inchangé).
    doc_numbering = models.JSONField(null=True, blank=True)
    # Taux de TVA (réforme marocaine) — éditables, défauts historiques.
    tva_standard = models.DecimalField(
        max_digits=5, decimal_places=2, default=20)
    tva_panneaux = models.DecimalField(
        max_digits=5, decimal_places=2, default=10)
    # ── Constantes ROI éditables (T6) — défauts = valeurs historiques codées
    # en dur dans le simulateur (solar.js). Tant qu'elles ne sont pas éditées,
    # le comportement reste identique ; le simulateur garde son repli interne.
    # Tarif ONEE moyen (MAD/kWh) — défaut 1.75 (solar.js KWH_PRICE).
    onee_tarif_kwh = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('1.75'))
    # Productible annuel moyen (kWh par kWc installé) — repère ROI éditable.
    productible_kwh_kwc = models.DecimalField(
        max_digits=7, decimal_places=1, default=Decimal('1600.0'))
    # ── Logique de devis éditable (D5) — défauts = constantes codées en dur du
    # simulateur (solar.js EFFICIENCY/estimerPanneaux). Tant qu'elles ne sont
    # pas éditées, le devis reste STRICTEMENT identique ; le simulateur garde
    # son repli interne (constantes par défaut).
    # Rendement global (productible appliqué à la production) — défaut 0.8.
    rendement_global = models.DecimalField(
        max_digits=4, decimal_places=3, default=Decimal('0.8'))
    # Auto-remplir : nombre de panneaux par tranche de 900 MAD (facture hiver).
    panneaux_par_900mad = models.PositiveSmallIntegerField(default=8)
    # Prix cible /kWc par défaut (pré-remplit le générateur). NULL/vide = aucun
    # (comportement actuel : pas de prix cible pré-réglé).
    prix_cible_kwc_defaut = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    # Limite de remise (%) indicative dans le générateur. NULL/vide = aucune
    # limite (comportement actuel). Distinct du seuil d'APPROBATION (T17).
    remise_max_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True)
    # Seuil d'approbation de remise (%) (T17). NULL/vide = désactivé (défaut) :
    # tant qu'il n'est pas renseigné, aucun devis n'exige d'approbation.
    discount_approval_threshold = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True)
    # ── Seuils de régime loi 82-21 (N43) — kWc, éditables. Défauts = cadre
    # marocain standard : déclaration < 11 kWc, autorisation ANRE > 1 MW.
    seuil_regime_declaration_kwc = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('11'))
    seuil_regime_anre_kwc = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('1000'))
    # ── Commission commerciale (N99) — additif, désactivé par défaut. Mode
    # 'off' (aucune commission, comportement inchangé), 'pct_devis' (% du HT
    # des devis signés) ou 'par_kwc' (MAD par kWc installé des chantiers issus
    # des devis signés). `commission_valeur` porte le % ou le montant/kWc selon
    # le mode. Donnée sensible : exposée aux seuls rôles autorisés (admin).
    commission_mode = models.CharField(max_length=10, default='off')
    commission_valeur = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = 'Profil entreprise'

    def __str__(self):
        return self.nom

    @classmethod
    def get(cls, company=None):
        """
        Retourne (ou crée) le profil pour une company donnée.
        Sans company, retourne/crée l'instance pk=1 (rétro-compat).
        """
        if company is not None:
            obj, _ = cls.objects.get_or_create(
                company=company,
                defaults={'nom': company.nom},
            )
            return obj
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# Modèles de message WhatsApp éditables (Paramètres → Messages). Placeholders
# supportés : {civilite} {nom} {reference} {lien} {n}. Le défaut s'applique tant
# que l'entreprise n'a pas enregistré sa propre version (rien ne change sinon).
MESSAGE_TEMPLATE_DEFAULTS = {
    'devis_unique':
        'Bonjour {civilite} {nom}, voici votre devis Taqinor '
        '({reference}) : {lien}',
    'devis_multi_entete':
        'Bonjour {civilite} {nom}, voici vos {n} devis Taqinor :',
    'devis_multi_ligne':
        '{reference} : {lien}',
    'facture':
        'Bonjour {civilite} {nom}, voici votre facture Taqinor '
        '({reference}) : {lien}',
    'relance':
        'Bonjour {civilite} {nom}, petit rappel concernant votre facture '
        'Taqinor ({reference}) : {lien}',
}


class MessageTemplate(models.Model):
    """Un modèle de message WhatsApp éditable, par entreprise et par clé.

    Deux variantes de langue : Français (`corps_fr`) et Darija (`corps_darija`).
    La Darija retombe sur le FR tant qu'elle est vide.
    """
    class Cle(models.TextChoices):
        DEVIS_UNIQUE = 'devis_unique', 'Devis (un seul)'
        DEVIS_MULTI_ENTETE = 'devis_multi_entete', 'Devis (plusieurs) — en-tête'
        DEVIS_MULTI_LIGNE = 'devis_multi_ligne', 'Devis (plusieurs) — ligne'
        FACTURE = 'facture', 'Facture'
        RELANCE = 'relance', 'Rappel de paiement'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='message_templates',
    )
    cle = models.CharField(max_length=40, choices=Cle.choices)
    corps_fr = models.TextField(blank=True, default='')
    corps_darija = models.TextField(blank=True, default='')

    class Meta:
        unique_together = [('company', 'cle')]
        ordering = ['cle']

    def __str__(self):
        return f'{self.company_id}:{self.cle}'

    @classmethod
    def get_corps(cls, company, cle, langue='fr'):
        """Corps du message pour (company, cle, langue), défaut si absent.

        La Darija vide retombe sur le FR ; le FR vide retombe sur le défaut.
        """
        row = cls.objects.filter(company=company, cle=cle).first()
        default = MESSAGE_TEMPLATE_DEFAULTS.get(cle, '')
        if row is None:
            return default
        if langue == 'darija' and row.corps_darija.strip():
            return row.corps_darija
        return row.corps_fr.strip() or default


class SettingsAuditLog(models.Model):
    """Une ligne par changement de paramètre (company-scopée) — N55.

    `section` regroupe les changements (ex. 'profil', 'messages') et `field`
    nomme le champ modifié. `old_value`/`new_value` sont stockés en texte
    (str() de la valeur). Aucune donnée de prix d'achat / marge n'est concernée
    par les paramètres."""

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='settings_audit_logs',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='settings_audit_logs',
    )
    section = models.CharField(max_length=50, default='profil')
    field = models.CharField(max_length=100, blank=True, default='')
    field_label = models.CharField(max_length=150, blank=True, default='')
    old_value = models.TextField(blank=True, default='')
    new_value = models.TextField(blank=True, default='')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Journal d'audit des paramètres"
        verbose_name_plural = "Journaux d'audit des paramètres"

    def __str__(self):
        return f'{self.section}.{self.field} @ {self.timestamp:%Y-%m-%d %H:%M}'

    @classmethod
    def log_change(cls, company, user, section, field, field_label, old, new):
        """Écrit une ligne d'audit (ancien→nouveau) en texte."""
        return cls.objects.create(
            company=company,
            user=user if (user and getattr(
                user, 'is_authenticated', False)) else None,
            section=section,
            field=field or '',
            field_label=field_label or '',
            old_value='' if old is None else str(old),
            new_value='' if new is None else str(new),
        )
