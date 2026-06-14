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
