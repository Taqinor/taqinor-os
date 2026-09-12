"""Modèles des affaires juridiques (module ``apps.juridique``, groupe NTJUR).

``DossierJuridique`` (NTJUR1) est le dossier de contentieux/précontentieux
d'une société : sa référence anti-collision (``JUR-{annee}-{seq}``) est
produite par ``core.numbering`` (jamais ``count() + 1`` — collision déjà vécue
en production sur les documents supprimés, cf. ``apps/ventes/utils/references``).

Multi-société : tout modèle hérite de ``core.models.TenantModel`` (FK
``company`` + horodatage, ARC1) ; la société est TOUJOURS posée côté serveur.
Les objets d'autres apps (réclamation ``litiges``, contrat, provision
``compta``) sont référencés par un simple identifiant (string-ref), jamais par
une FK réelle ni un import de leur ``models`` — la frontière inter-apps passe
par ``selectors.py`` / ``services.py``.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models

from core.models import TenantModel


class DossierJuridique(TenantModel):
    """Un dossier juridique (contentieux, précontentieux, consultatif…).

    NTJUR1 — socle du module. Le ``statut`` procédural porte ses PROPRES clés
    (ouvert → … → clos_*), explicitement SÉPARÉES du funnel commercial
    ``STAGES.py`` (règle #2 : ce n'est pas une étape de vente) et du cycle des
    documents Devis/Facture (règle #4). Les transitions légales et les actions
    qui les appliquent vivent dans ``services.changer_statut`` (NTJUR2) : le
    champ est en lecture seule au sérialiseur, jamais posable par un PATCH brut
    (garde ``scripts/check_machine_etats_statut_readonly.py``).
    """

    class Nature(models.TextChoices):
        CONTENTIEUX = 'contentieux', 'Contentieux'
        PRECONTENTIEUX = 'precontentieux', 'Précontentieux'
        CONSULTATIF = 'consultatif', 'Consultatif'
        RECOUVREMENT = 'recouvrement', 'Recouvrement'

    class TypeProcedure(models.TextChoices):
        CIVIL = 'civil', 'Civil'
        COMMERCIAL = 'commercial', 'Commercial'
        SOCIAL = 'social', 'Social'
        PENAL = 'penal', 'Pénal'
        ADMINISTRATIF = 'administratif', 'Administratif'
        ARBITRAGE = 'arbitrage', 'Arbitrage'

    class DegreJuridiction(models.TextChoices):
        PREMIERE_INSTANCE = 'premiere_instance', 'Première instance'
        APPEL = 'appel', 'Appel'
        CASSATION = 'cassation', 'Cassation'

    class Position(models.TextChoices):
        DEMANDEUR = 'demandeur', 'Demandeur'
        DEFENDEUR = 'defendeur', 'Défendeur'

    class NiveauConfidentialite(models.TextChoices):
        PUBLIC = 'public', 'Public'
        INTERNE = 'interne', 'Interne'
        CONFIDENTIEL = 'confidentiel', 'Confidentiel'

    class Statut(models.TextChoices):
        """Machine à états PROCÉDURALE — clés propres au module juridique.

        JAMAIS les clés de ``STAGES.py`` (funnel commercial, règle #2) ni
        celles du cycle Devis/Facture (règle #4) : un dossier juridique n'est
        ni une opportunité ni un document de vente.
        """
        OUVERT = 'ouvert', 'Ouvert'
        INSTRUCTION = 'instruction', 'En instruction'
        AUDIENCE_PROGRAMMEE = 'audience_programmee', 'Audience programmée'
        EN_DELIBERE = 'en_delibere', 'En délibéré'
        JUGEMENT_RENDU = 'jugement_rendu', 'Jugement rendu'
        APPEL = 'appel', 'En appel'
        EXECUTION = 'execution', 'En exécution'
        CLOS_GAGNE = 'clos_gagne', 'Clos — gagné'
        CLOS_PERDU = 'clos_perdu', 'Clos — perdu'
        CLOS_TRANSACTION = 'clos_transaction', 'Clos — transaction'
        CLOS_DESISTEMENT = 'clos_desistement', 'Clos — désistement'

    #: Statuts TERMINAUX (un dossier clos ne repart pas).
    STATUTS_CLOS = (
        Statut.CLOS_GAGNE, Statut.CLOS_PERDU,
        Statut.CLOS_TRANSACTION, Statut.CLOS_DESISTEMENT,
    )

    reference = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Référence')
    titre = models.CharField(max_length=255, verbose_name='Titre')
    nature = models.CharField(
        max_length=20, choices=Nature.choices,
        default=Nature.CONTENTIEUX, verbose_name='Nature')
    type_procedure = models.CharField(
        max_length=20, choices=TypeProcedure.choices,
        default=TypeProcedure.CIVIL, verbose_name='Type de procédure')
    juridiction_nom = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Juridiction')
    juridiction_ville = models.CharField(
        max_length=120, blank=True, default='',
        verbose_name='Ville de la juridiction')
    juridiction_degre = models.CharField(
        max_length=20, choices=DegreJuridiction.choices,
        default=DegreJuridiction.PREMIERE_INSTANCE,
        verbose_name='Degré de juridiction')
    montant_en_jeu = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant en jeu')
    partie_adverse_nom = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Partie adverse')
    notre_position = models.CharField(
        max_length=15, choices=Position.choices,
        default=Position.DEFENDEUR, verbose_name='Notre position')
    resume_faits = models.TextField(
        blank=True, default='', verbose_name='Résumé des faits')
    date_ouverture = models.DateField(verbose_name="Date d'ouverture")
    responsable_interne = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        # on_delete: un dossier juridique SURVIT au départ de son responsable
        # (pièce à valeur légale) — jamais de cascade.
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='dossiers_juridiques',
        verbose_name='Responsable interne',
    )
    # Même patron que ``contrats.Contrat.confidentialite`` : le palier faisant
    # autorité est ``CustomUser.menu_tier`` (dérivé du Role FK), jamais le
    # ``role_legacy`` peu fiable. Le filtrage vit dans le ``get_queryset`` du
    # ViewSet (NTJUR1) — un dossier confidentiel est INVISIBLE, pas 403.
    confidentialite = models.CharField(
        max_length=20, choices=NiveauConfidentialite.choices,
        default=NiveauConfidentialite.INTERNE,
        verbose_name='Confidentialité')
    statut = models.CharField(
        max_length=25, choices=Statut.choices,
        default=Statut.OUVERT, verbose_name='Statut')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        # on_delete: trace d'auteur, jamais une raison de perdre le dossier.
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='dossiers_juridiques_crees',
        verbose_name='Créé par',
    )

    class Meta:
        verbose_name = 'Dossier juridique'
        verbose_name_plural = 'Dossiers juridiques'
        ordering = ['-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                name='juridique_dossier_co_ref_uniq'),
        ]

    def __str__(self):
        return f'{self.reference} {self.titre}'.strip()

    @property
    def est_clos(self):
        """Vrai si le dossier a atteint un statut terminal ``clos_*``."""
        return self.statut in {s.value for s in self.STATUTS_CLOS}
