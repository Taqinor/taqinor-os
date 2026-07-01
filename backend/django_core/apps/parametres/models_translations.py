"""N94 — Surcharges de traduction de l'interface (``TranslationOverride``).

Couche de GESTION DES TRADUCTIONS : elle permet de relire/ajuster les chaînes
de l'interface par langue (fr/en/ar) SANS changement de code. Elle s'appuie sur
le cadre i18n N93 côté frontend : chaque ligne surcharge la valeur d'UNE clé
i18n (ex. ``nav.stock``) pour UNE langue, par société.

Additif et company-scopé : la table est vide par défaut ; tant qu'aucune ligne
n'est enregistrée, l'interface affiche EXACTEMENT les catalogues statiques N93
(aucune régression). On ne crée jamais de clé i18n ici — on surcharge la valeur
d'une clé existante — mais le serveur n'impose pas de liste blanche de clés (le
catalogue vit côté frontend) : une clé inconnue est simplement ignorée à
l'affichage.
"""
from django.db import models


class TranslationOverride(models.Model):
    """Surcharge company-scopée de la valeur d'UNE clé i18n pour UNE langue.

    ``locale`` ∈ {fr, en, ar} (les 3 locales du cadre N93). ``key`` est la
    clé i18n en notation pointée (ex. ``common.save``). ``value`` est le texte
    affiché à la place du catalogue statique.
    """

    class Locale(models.TextChoices):
        FR = 'fr', 'Français'
        EN = 'en', 'English'
        AR = 'ar', 'العربية'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='translation_overrides',
    )
    # Langue d'interface visée (fr / en / ar) — les 3 locales du cadre N93.
    locale = models.CharField(max_length=5, choices=Locale.choices)
    # Clé i18n en notation pointée (ex. 'nav.stock'). Identifiant stable côté
    # frontend ; jamais interprété comme chemin ici (simple chaîne opaque).
    key = models.CharField(max_length=120)
    # Texte affiché à la place du catalogue statique pour (company, locale, key).
    value = models.TextField(blank=True, default='')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        # app_label explicite : ce module n'est pas importé par ``models.py``
        # (indépendance des lanes) ; il est chargé via ``apps.py`` ready().
        app_label = 'parametres'
        ordering = ['locale', 'key']
        unique_together = [('company', 'locale', 'key')]
        verbose_name = 'Surcharge de traduction'
        verbose_name_plural = 'Surcharges de traduction'

    def __str__(self):
        return f'{self.company_id}:{self.locale}:{self.key}'

    @classmethod
    def overrides_for_company(cls, company):
        """Dict ``{locale: {key: value}}`` des surcharges d'une société.

        Renvoie ``{}`` (repli byte-identique au catalogue statique N93) si la
        société est absente ou n'a aucune surcharge.
        """
        out = {}
        if company is None:
            return out
        for row in cls.objects.filter(company=company):
            out.setdefault(row.locale, {})[row.key] = row.value
        return out
