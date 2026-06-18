"""Profil entreprise (``CompanyProfile``).

Domaine « Société & identité / Devis & logique métier ». Extrait de l'ancien
``models.py`` monolithique sans le moindre changement de champ, de ``Meta`` ou
de nom de table — l'``app_label`` reste ``parametres`` et la table reste
``parametres_companyprofile`` (split sans migration)."""
from decimal import Decimal

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
    # ── Bloc paiement & conditions sur la FACTURE (Feature B, 2026-06) ──
    # Trois réglages texte libre, additifs et VIDES par défaut : tant qu'ils ne
    # sont pas renseignés, le PDF facture est strictement identique (les blocs ne
    # s'affichent que si non-vides). Le RIB ci-dessus complète ce bloc. Ces
    # valeurs ne touchent JAMAIS le moteur premium des devis (pas de slot dédié).
    instructions_paiement = models.TextField(blank=True, default='')
    conditions_generales = models.TextField(blank=True, default='')
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
    # N66 — installateur (technicien) assigné par défaut aux NOUVEAUX chantiers
    # quand aucun n'est choisi. NULL = comportement actuel (le créateur du
    # chantier en est le technicien responsable). Additif.
    default_installer = models.ForeignKey(
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
    # N98 — programme de parrainage : activation + récompense par défaut (pré-
    # remplit un nouveau parrainage). Désactivé par défaut → rien ne change.
    referral_enabled = models.BooleanField(default=False)
    referral_reward = models.DecimalField(
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
