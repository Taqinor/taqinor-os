"""Modèles de l'app Paramètres — surface d'import publique.

Le monolithe d'origine a été éclaté par domaine (un fichier par domaine) pour
que plusieurs réglages puissent évoluer en parallèle sans se gêner. Ce module
ré-exporte les classes pour que ``from apps.parametres.models import …`` (et la
découverte des modèles par Django) continue de fonctionner à l'identique.

Split SANS migration : ``app_label`` et noms de table inchangés
(``parametres_companyprofile`` / ``parametres_messagetemplate`` /
``parametres_settingsauditlog``).

NTEXT18 — ``GabaritDocumentCustom`` est défini ICI (et non dans un fichier
``models_*`` dédié) parce qu'il déclare des noms d'index/contrainte EXPLICITES :
la garde CI ``scripts/check_migration_safety.py`` exige que ces noms figurent
verbatim dans un ``models.py`` pour empêcher la dérive « changes not
reflected »."""
from django.core.exceptions import ValidationError
from django.db import models

from core.models import TenantModel

from .models_company import CompanyProfile
from .models_messages import MESSAGE_TEMPLATE_DEFAULTS, MessageTemplate
from .models_audit import SettingsAuditLog
from .models_tariff import DEFAULT_RESIDENTIAL_TIERS, TariffSettings
from .models_translations import TranslationOverride
from .models_taxes import TAUX_TVA_MAROCAINS, TauxTVA
from .models_payment_terms import ConditionPaiement
from .models_units import UNITES_MESURE_DEFAUT, UniteMesure

__all__ = [
    'CompanyProfile',
    'MessageTemplate',
    'MESSAGE_TEMPLATE_DEFAULTS',
    'SettingsAuditLog',
    'TariffSettings',
    'DEFAULT_RESIDENTIAL_TIERS',
    'TranslationOverride',
    'TauxTVA',
    'TAUX_TVA_MAROCAINS',
    'ConditionPaiement',
    'UniteMesure',
    'UNITES_MESURE_DEFAUT',
    'GabaritDocumentCustom',
    'CIBLE_INTERDITE',
]


# ---------------------------------------------------------------------------
# NTEXT18 — Gabarits de DOCUMENT custom (hors devis, règle #4).
#
# Un ``GabaritDocumentCustom`` est un document éditable par société : un corps
# HTML avec des placeholders ``{{ variable }}``, rendu par ``core.templating``
# (substitution PUREMENT littérale, jamais d'exécution de code) puis en PDF par
# ``core.pdf.render_pdf`` (WeasyPrint mutualisé, ARC11). Voir
# ``apps/parametres/gabarits.py`` pour le rendu.
#
# ⚠ RÈGLE #4 — la cible ``devis`` est STRICTEMENT INTERDITE. Le devis client
# passe UNIQUEMENT par ``/proposal`` (moteur premium vendorisé) : ce modèle ne
# doit jamais devenir un chemin PDF de devis alternatif. La cible n'est pas dans
# les choix ET une garde ``save()``/``clean()`` la refuse quoi qu'il arrive.
#
# ⚠ NE PAS CONFONDRE avec ``parametres.models_documents.DocumentTemplates`` :
# celui-là est un SINGLETON PRÉEXISTANT par société qui porte les portions de
# TEXTE du devis premium (validité, CGV, garanties…). Les deux sont distincts et
# le restent — ce modèle n'étend, ne remplace ni ne fusionne rien.
# ---------------------------------------------------------------------------

# Cible INTERDITE (règle #4). Chaîne littérale, jamais un import du domaine
# ventes : le devis client n'a qu'UN chemin PDF, ``/proposal``.
CIBLE_INTERDITE = 'devis'


class GabaritDocumentCustom(TenantModel):
    """Gabarit de document éditable, par société (hors devis — règle #4)."""

    class Cible(models.TextChoices):
        CHANTIER = 'chantier', 'Chantier'
        CLIENT = 'client', 'Client'
        TICKET = 'ticket', 'Ticket SAV'
        OBJET_CUSTOM = 'objet_custom', 'Objet personnalisé'

    code = models.SlugField(
        'Code', max_length=60,
        help_text="Identifiant stable, ex. « fiche_visite_chantier ».")
    nom = models.CharField('Nom', max_length=160)
    cible = models.CharField(
        'Cible', max_length=20, choices=Cible.choices,
        help_text="Type d'objet documenté. La cible « devis » est interdite "
                  "(règle #4 : le devis client passe par /proposal).")
    corps = models.TextField(
        'Corps HTML', blank=True, default='',
        help_text='HTML avec placeholders ``{{ variable }}``.')
    actif = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = 'Gabarit de document'
        verbose_name_plural = 'Gabarits de document'
        ordering = ['cible', 'code', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'],
                name='parametres_gabaritdoc_co_code'),
        ]
        indexes = [
            models.Index(fields=['company', 'cible', 'actif'],
                         name='param_gabaritdoc_idx'),
        ]

    def __str__(self):
        return f'{self.code} ({self.cible})'

    # ── Garde règle #4 ─────────────────────────────────────────────────────

    def _verifier_cible(self):
        """Refuse la cible ``devis`` — sur TOUS les chemins d'écriture."""
        if (self.cible or '').strip().lower() == CIBLE_INTERDITE:
            raise ValidationError({
                'cible': "La cible « devis » est interdite : le devis client "
                         "est généré uniquement par /proposal.",
            })

    def clean(self):
        super().clean()
        self._verifier_cible()

    def save(self, *args, **kwargs):
        # La garde vit dans ``save()`` (et pas seulement dans ``clean()``) :
        # un ``objects.create(cible='devis')`` en ORM brut n'appelle jamais
        # ``full_clean()`` et contournerait sinon la règle #4.
        self._verifier_cible()
        return super().save(*args, **kwargs)
