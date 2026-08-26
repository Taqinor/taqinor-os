"""RELANCE FOUNDATION — cadence de relance par défaut, par société.

Référentiel founder-editable (Paramètres → CRM) consommé par
``apps.crm.services.initialiser_plan_relance`` pour matérialiser un plan de
relance structuré (``apps.crm.models.RelanceEtape``) sur un lead donné. Chaque
« barreau » de la cadence est un délai en jours après le point de départ du
plan, un canal SUGGÉRÉ (appel/whatsapp/email/visite) et un libellé.

Zéro chiffre affiché au client : ce sont des DÉFAUTS DE PLANIFICATION interne
(ordonnancement de rappels), jamais une statistique de conversion ni une
preuve chiffrée présentée à qui que ce soit (règle fondateur « zéro chiffre
inventé/affiché »). Même patron que ``UniteMesure``
(``apps/parametres/models_units.py``) : ``TenantModel``, seed idempotent
additif, seedé au signup ET à la volée pour les sociétés déjà existantes.
"""
from django.db import models

from core.models import TenantModel


class CanalRelance(models.TextChoices):
    APPEL = 'appel', 'Appel'
    WHATSAPP = 'whatsapp', 'WhatsApp'
    EMAIL = 'email', 'E-mail'
    VISITE = 'visite', 'Visite'


# Échelle NEUTRE par défaut (J+2/J+5/J+10/J+20/J+35) — un ordonnancement de
# rappels internes modifiable par société, jamais une statistique de
# conversion affichée (« modifiable » dans Paramètres → CRM).
CADENCE_RELANCE_DEFAUT = [
    {'ordre': 1, 'delai_jours': 2, 'canal': CanalRelance.APPEL,
     'libelle': 'Premier rappel'},
    {'ordre': 2, 'delai_jours': 5, 'canal': CanalRelance.WHATSAPP,
     'libelle': 'Relance WhatsApp'},
    {'ordre': 3, 'delai_jours': 10, 'canal': CanalRelance.EMAIL,
     'libelle': 'Relance e-mail'},
    {'ordre': 4, 'delai_jours': 20, 'canal': CanalRelance.APPEL,
     'libelle': "Point d'étape"},
    {'ordre': 5, 'delai_jours': 35, 'canal': CanalRelance.VISITE,
     'libelle': 'Dernière relance'},
]


class CadenceRelanceEtape(TenantModel):
    """Un barreau (délai + canal + libellé) de la cadence de relance par
    défaut d'une société — modifiable via l'API Paramètres. Purement un
    GABARIT : ``crm.RelanceEtape`` matérialise une COPIE indépendante par
    lead au moment de l'initialisation (modifier le gabarit après coup
    n'altère jamais un plan déjà initialisé sur un lead)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='cadence_relance_etapes')
    ordre = models.PositiveIntegerField(default=0)
    delai_jours = models.PositiveIntegerField(
        help_text="Nombre de jours après le point de départ du plan.")
    canal = models.CharField(max_length=20, choices=CanalRelance.choices)
    libelle = models.CharField(max_length=150)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Étape de cadence de relance'
        verbose_name_plural = 'Étapes de cadence de relance'
        ordering = ['ordre', 'delai_jours']
        # Un seul barreau par société + ordre (idempotence seed/backfill,
        # même convention que UniteMesure (company, code)).
        unique_together = [('company', 'ordre')]

    def __str__(self):
        return f'{self.company_id}: J+{self.delai_jours} {self.libelle}'

    @classmethod
    def seed_defaults(cls, company):
        """Seede la cadence neutre par défaut pour ``company`` (idempotent,
        additif). ``get_or_create`` par (company, ordre) : rejouable sans
        doublon, ne retouche jamais un barreau déjà personnalisé."""
        crees = 0
        for entry in CADENCE_RELANCE_DEFAUT:
            _, created = cls.objects.get_or_create(
                company=company, ordre=entry['ordre'],
                defaults={
                    'delai_jours': entry['delai_jours'],
                    'canal': entry['canal'],
                    'libelle': entry['libelle'],
                    'actif': True,
                })
            if created:
                crees += 1
        return crees

    @classmethod
    def cadence_pour(cls, company):
        """Cadence active de ``company``, triée par ordre — seedée à la volée
        si absente (sociétés créées avant ce référentiel, même filet que les
        autres hooks signup : jamais un défaut codé en dur côté appelant)."""
        qs = cls.objects.filter(
            company=company, actif=True).order_by('ordre', 'delai_jours')
        if not qs.exists():
            cls.seed_defaults(company)
            qs = cls.objects.filter(
                company=company, actif=True).order_by('ordre', 'delai_jours')
        return list(qs)
