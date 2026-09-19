"""NTI18N36 — granularité RTL par module (transition progressive).

Basculer tout l'ERP en RTL d'un seul interrupteur casse mécaniquement les
écrans qui n'ont pas encore été migrés : colonnes inversées, icônes
directionnelles à l'envers, tableaux illisibles. Ce module résout la question
MODULE PAR MODULE, en lisant le drapeau ``ModuleToggle.rtl_pret`` (NTI18N36) :

  * utilisateur en langue de gauche à droite  → tout en LTR, comme avant ;
  * utilisateur en langue de droite à gauche  → RTL sur les modules déclarés
    prêts, LTR FORCÉ ailleurs, avec une mention discrète expliquant pourquoi.

``core`` reste une couche de FONDATION : ``module`` est une CLÉ LIBRE (aucun
import d'app métier, contrat import-linter
``core-foundation-is-a-base-layer``). Le rendu du layout lui-même est l'affaire
de NTI18N2 côté interface ; ici on ne décide QUE la direction et la mention.

Politique par défaut, strictement non régressive : aucune ligne
``ModuleToggle`` ⇒ ``rtl_pret`` faux ⇒ LTR.
"""
from __future__ import annotations

#: Langues écrites de DROITE À GAUCHE. Le code de langue est comparé sur sa
#: racine (``ar-ma`` compte comme ``ar``), pour ne pas dépendre de la façon
#: dont un appelant écrit la variante régionale.
LOCALES_RTL = frozenset({'ar', 'he', 'fa', 'ur'})

DIRECTION_LTR = 'ltr'
DIRECTION_RTL = 'rtl'

#: Mention discrète affichée sur un module encore non migré, pour que
#: l'utilisateur comprenne pourquoi cet écran-là reste en LTR.
NOTE_MIGRATION_EN_COURS = (
    "Ce module s'affiche en LTR le temps de sa migration."
)

__all__ = [
    'LOCALES_RTL',
    'DIRECTION_LTR',
    'DIRECTION_RTL',
    'NOTE_MIGRATION_EN_COURS',
    'locale_est_rtl',
    'module_rtl_pret',
    'modules_rtl_prets',
    'direction_module',
]


def locale_est_rtl(locale):
    """Vrai si ``locale`` s'écrit de droite à gauche (``'ar'``, ``'ar-MA'``…).

    Fonction PURE : aucun accès base, aucun réglage société."""
    racine = (locale or '').strip().lower().replace('_', '-').split('-')[0]
    return racine in LOCALES_RTL


def module_rtl_pret(company, module):
    """Vrai si ``module`` est déclaré prêt pour le RTL chez ``company``.

    Aucune ligne ``ModuleToggle`` ⇒ faux (le module n'est pas encore migré).
    ``company`` ``None`` ⇒ faux (pas de scope, donc pas de promesse)."""
    if company is None or not module:
        return False
    from .models import ModuleToggle
    return bool(
        ModuleToggle.objects
        .filter(company=company, module=module)
        .values_list('rtl_pret', flat=True)
        .first()
    )


def modules_rtl_prets(company):
    """Les clés de modules déclarés prêts pour le RTL chez ``company``.

    Une SEULE requête : le shell de l'interface interroge des dizaines de
    modules au chargement, pas un par un."""
    if company is None:
        return set()
    from .models import ModuleToggle
    return set(
        ModuleToggle.objects
        .filter(company=company, rtl_pret=True)
        .values_list('module', flat=True)
    )


def direction_module(company, module, locale):
    """Direction d'écriture à appliquer à ``module``, et pourquoi.

    Retourne ``{'direction': 'ltr'|'rtl', 'force_ltr': bool, 'note': str}`` :

      * langue LTR                      → ``ltr``, sans mention ;
      * langue RTL + module prêt        → ``rtl``, sans mention ;
      * langue RTL + module non migré   → ``ltr`` avec ``force_ltr=True`` et la
        mention discrète (c'est CE cas que NTI18N36 existe pour rendre
        explicite au lieu de livrer un écran cassé).
    """
    if not locale_est_rtl(locale):
        return {'direction': DIRECTION_LTR, 'force_ltr': False, 'note': ''}
    if module_rtl_pret(company, module):
        return {'direction': DIRECTION_RTL, 'force_ltr': False, 'note': ''}
    return {
        'direction': DIRECTION_LTR,
        'force_ltr': True,
        'note': NOTE_MIGRATION_EN_COURS,
    }
