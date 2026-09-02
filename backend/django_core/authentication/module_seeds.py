"""SOL8 — Semis des modules OFF PAR DÉFAUT, à la CRÉATION d'un tenant.

Deux niveaux de spécialisation solaire, jamais de suppression de code :
l'ÉDITION retire du build les verticaux non adaptables (SOL1-SOL6) ; ce
module-ci gère l'autre niveau — les modules parfaitement ADAPTABLES mais RARES
chez un installateur solaire. Ils restent LIVRÉS et réactivables en un clic
(Paramètres → Applications) ; ils démarrent simplement éteints.

RÈGLE ABSOLUE — JAMAIS DE BACKFILL
----------------------------------
Le semis n'est appelé QUE depuis les chemins de CRÉATION d'une société
(`RegisterCompanyView`, la console `views_console_create`). Il n'est
DÉLIBÉRÉMENT PAS enregistré dans `core.signup_hooks` : ce registre est aussi
rejoué par la commande `seed_company` sur une société EXISTANTE, ce qui
éteindrait des modules qu'un tenant utilise pour de vrai (TAQINOR utilise
`douane` et `scm`). Une société préexistante ne doit recevoir AUCUNE ligne —
c'est ce que prouve `tests_sol8_modules_off_defaut.py`.

Idempotent et non destructif : `get_or_create` uniquement — une ligne
`ModuleToggle` déjà présente (module réactivé par l'admin) n'est JAMAIS écrasée.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: Modules livrés mais RARES chez un installateur solaire : off au départ.
#: `magasin` n'a pas de manifeste backend — c'est une surface FRONT (logistique
#: d'entrepôt, `frontend/src/features/magasin`) dont la section de nav est
#: masquée par la même liste `modules_desactives` servie par `/auth/me`. Le
#: catalogue de modules l'expose quand même (voir `core.feature_flags`), donc
#: elle reste réactivable en un clic comme les autres.
MODULES_OFF_PAR_DEFAUT = (
    'pos',
    'promotions',   # appairé à pos, qui l'appelle
    'douane',
    'transport',
    'scm',
    'magasin',
)

#: « Pack pays » : n'a de sens qu'au Maroc (DGI/Simpl, calendrier fiscal
#: marocain, CNSS/AMO/IR). Éteint pour un tenant NON marocain uniquement.
PACK_PAYS_MAROC = ('einvoice', 'fiscal', 'paie')

PAYS_MAROC = 'MA'


def modules_a_eteindre(company):
    """Clés de module à éteindre pour ce tenant NEUF (liste ordonnée, stable)."""
    cles = list(MODULES_OFF_PAR_DEFAUT)
    pays = (getattr(company, 'pays', PAYS_MAROC) or PAYS_MAROC).upper()
    if pays != PAYS_MAROC:
        cles.extend(PACK_PAYS_MAROC)
    return cles


def semer_modules_off_par_defaut(company, *, user=None):
    """Pose les lignes `ModuleToggle(actif=False)` d'un tenant NEUF.

    À N'APPELER QUE depuis un chemin de création de société. Renvoie la liste
    des clés effectivement écrites (vide si tout existait déjà). Best-effort :
    un échec n'interrompt jamais la création du tenant.
    """
    from core.models import ModuleToggle

    ecrites = []
    for cle in modules_a_eteindre(company):
        try:
            _toggle, cree = ModuleToggle.objects.get_or_create(
                company=company, module=cle,
                defaults={
                    'actif': False,
                    'raison': "Éteint par défaut à la création du tenant "
                              "(SOL8) — réactivable dans Paramètres → "
                              "Applications.",
                },
            )
        except Exception as exc:  # noqa: BLE001 — ne casse jamais le signup
            logger.warning(
                'SOL8 : semis du module %s impossible pour %s : %s',
                cle, getattr(company, 'pk', None), exc)
            continue
        if cree:
            ecrites.append(cle)
    return ecrites
