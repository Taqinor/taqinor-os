"""NTWMS34 — Contrôle qualité à réception avec échantillonnage.

Un plan d'échantillonnage dit QUELLE PART d'une catégorie de produits doit
être contrôlée à l'arrivée. Quand un plan s'applique à une réception, celle-ci
ne peut PAS être confirmée tant que le résultat du contrôle n'a pas été saisi :
conforme → put-away normal (NTWMS2) ; non conforme → quarantaine (NTWMS31).

ADAPTATION DE PÉRIMÈTRE (assumée, testée). La tâche demandait un champ additif
``ReceptionFournisseur.echantillon_requis``. Ce modèle vit dans ``apps.achats``
(ODX19) — app que cette lane ne possède pas et où elle n'écrit jamais. Le
drapeau est donc DÉRIVÉ (``echantillon_requis_pour_reception``) et le résultat
du contrôle porté par ``ControleReception``, un satellite de ``stock`` qui
référence la réception en STRING-FK. Même motif que ``AffectationCrossDock``
(NTWMS15) : la donnée vit chez qui la produit, jamais une colonne posée de
force dans l'app d'un autre.
"""
from django.conf import settings
from django.db import models

from core.models import TenantModel


class PlanEchantillonnage(TenantModel):
    """Part (en %) d'une catégorie de produits à contrôler à la réception.

    ``categorie`` nulle = plan par DÉFAUT de la société (s'applique à tout
    produit dont la catégorie n'a pas son propre plan). ``taux_echantillon_pct``
    à 0 = aucun contrôle exigé — donc comportement historique strictement
    inchangé pour toute société qui ne crée aucun plan.
    """

    categorie = models.ForeignKey(
        'stock.Categorie', on_delete=models.CASCADE,  # on_delete: CASCADE — un plan n'a de sens QUE pour sa catégorie ; sans elle il ne s'appliquerait à rien (composition stricte)
        null=True, blank=True, related_name='plans_echantillonnage',
        help_text='Catégorie visée. Vide = plan par défaut de la société.')
    taux_echantillon_pct = models.PositiveIntegerField(
        default=0,
        help_text='Part des unités reçues à contrôler (0 = aucun contrôle '
                  'exigé, comportement historique).')
    actif = models.BooleanField(default=True)
    note = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = "Plan d'échantillonnage à réception"
        verbose_name_plural = "Plans d'échantillonnage à réception"
        ordering = ['categorie_id', 'id']
        constraints = [
            # Un seul plan par (société, catégorie) — y compris le plan par
            # défaut (catégorie NULL), d'où la contrainte partielle jumelle :
            # PostgreSQL ne considère jamais deux NULL comme égaux.
            models.UniqueConstraint(
                fields=['company', 'categorie'],
                condition=models.Q(categorie__isnull=False),
                name='stock_planechant_company_categorie_uniq'),
            models.UniqueConstraint(
                fields=['company'],
                condition=models.Q(categorie__isnull=True),
                name='stock_planechant_company_defaut_uniq'),
        ]

    def __str__(self):
        cible = self.categorie_id or 'défaut'
        return f'Échantillonnage {cible} — {self.taux_echantillon_pct} %'

    def unites_a_controler(self, quantite_recue):
        """Nombre d'unités à contrôler pour ``quantite_recue`` reçues
        (arrondi SUPÉRIEUR : 1 % de 10 unités contrôle quand même 1 unité)."""
        try:
            quantite = int(quantite_recue or 0)
        except (TypeError, ValueError):
            return 0
        if quantite <= 0 or not self.taux_echantillon_pct:
            return 0
        brut = quantite * int(self.taux_echantillon_pct)
        return -(-brut // 100)  # plafond entier sans importer math


class ControleReception(TenantModel):
    """Résultat du contrôle qualité d'UNE réception fournisseur.

    Satellite de ``achats.ReceptionFournisseur`` (string-FK) : c'est lui qui
    porte le verdict que la confirmation exige quand un plan s'applique.
    ``resultat`` NON_CONFORME route la marchandise vers la quarantaine
    (``BlocageQualite``, NTWMS31) au lieu du put-away normal.
    """

    class Resultat(models.TextChoices):
        CONFORME = 'conforme', 'Conforme'
        NON_CONFORME = 'non_conforme', 'Non conforme'

    reception = models.OneToOneField(
        'achats.ReceptionFournisseur', on_delete=models.CASCADE,  # on_delete: CASCADE — le verdict n'existe QUE pour sa réception ; sans elle il n'a plus d'objet (composition stricte)
        related_name='controle_reception_stock')
    resultat = models.CharField(max_length=20, choices=Resultat.choices)
    unites_controlees = models.PositiveIntegerField(default=0)
    unites_attendues = models.PositiveIntegerField(
        default=0,
        help_text="Échantillon exigé par le plan au moment de la saisie.")
    observation = models.TextField(blank=True, default='')
    controle_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='controles_reception_stock')

    class Meta:
        verbose_name = 'Contrôle qualité de réception'
        verbose_name_plural = 'Contrôles qualité de réception'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'resultat'],
                         name='idx_ctrlrecep_co_resultat'),
        ]

    def __str__(self):
        return f'Contrôle {self.reception_id} — {self.resultat}'

    @property
    def est_conforme(self):
        return self.resultat == self.Resultat.CONFORME
