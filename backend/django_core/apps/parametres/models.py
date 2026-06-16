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
    # Seuil de remise (%) au-delà duquel l'envoi d'un devis exige une
    # approbation admin/responsable. NULL = garde DÉSACTIVÉE (défaut) → rien
    # ne change tant que le founder ne l'active pas.
    seuil_remise_approbation = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Remise (%) au-delà de laquelle l\'envoi d\'un devis '
                  'requiert une approbation. Vide ou 0 = désactivé.')
    # Heures de pompage effectives/jour par défaut (mode agricole). Défaut 7.
    agricole_pump_hours = models.DecimalField(
        max_digits=4, decimal_places=1, default=7)
    # Préfixes de numérotation des pièces : {devis,facture,avoir,bon_commande}.
    # NULL = repli sur les préfixes historiques (DEV/FAC/AVO/BC).
    doc_prefixes = models.JSONField(null=True, blank=True)
    # Taux de TVA (réforme marocaine) — éditables, défauts historiques.
    tva_standard = models.DecimalField(
        max_digits=5, decimal_places=2, default=20)
    tva_panneaux = models.DecimalField(
        max_digits=5, decimal_places=2, default=10)

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
