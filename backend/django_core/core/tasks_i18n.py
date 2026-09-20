"""NTI18N39 — recalcul HEBDOMADAIRE de la couverture i18n en tâche de fond.

Avant : `scripts/extract_i18n_strings.py` (NTI18N1) était lancé À LA MAIN et
son rapport JSON committé dans le dépôt ; l'écran NTI18N28 lisait ce fichier
figé. Ici, un job Beat hebdomadaire rejoue la MÊME logique et en persiste le
résultat dans ``core.I18nCoverageSnapshot`` — donc un historique, donc un delta
semaine à semaine.

LA LOGIQUE N'EST PAS DUPLIQUÉE. Ce module IMPORTE `build_report()` du script et
l'appelle tel quel : aucun comptage n'est réécrit ici (deux implémentations du
même comptage dériveraient, et le chiffre affiché ne voudrait plus rien dire).
Le script vit à la RACINE du dépôt, hors du paquet Django : il est donc chargé
par chemin (`importlib`), exactement comme `apps/crm/stages.py` charge le
`STAGES.py` canonique.

CONTRAINTE RÉELLE, ASSUMÉE ET JOURNALISÉE — le worker de production ne voit PAS
le dépôt. Les conteneurs Django/Celery montent `backend/django_core` sur `/app`
(plus `STAGES.py` sur `/opt/STAGES.py`), donc ni `scripts/` ni `frontend/src/`
n'y sont présents. Quand le script ou l'arborescence `frontend/src` est
introuvable, la tâche NE STOCKE RIEN et journalise POURQUOI : écrire un
instantané à 0 % afficherait sur l'écran NTI18N28 un effondrement de couverture
totalement faux (règle fondateur « aucun chiffre inventé » — mieux vaut « pas
de mesure » que le chiffre d'un répertoire vide). Rendre le job opérant en
production demande une moitié d'INFRASTRUCTURE hors périmètre de ce module :
monter `scripts/` + `frontend/src` (lecture seule) dans le service
`celery_worker`, comme `STAGES.py` l'est déjà.
"""
import importlib.util
import logging
from decimal import Decimal
from pathlib import Path

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

# Nom du script canonique de NTI18N1, à la racine du dépôt.
NOM_SCRIPT = 'extract_i18n_strings.py'
_HERE = Path(__file__).resolve()


def _chemins_candidats():
    """Emplacements possibles de `scripts/extract_i18n_strings.py`.

    Même stratégie que ``apps/crm/stages.py`` pour `STAGES.py` : on essaie le
    point de montage conventionnel des conteneurs puis on remonte l'arbre
    jusqu'à la racine du dépôt (hôte / CI).
    """
    candidats = [Path('/opt') / 'scripts' / NOM_SCRIPT]
    candidats += [parent / 'scripts' / NOM_SCRIPT for parent in _HERE.parents]
    candidats += [Path('/app') / 'scripts' / NOM_SCRIPT,
                  Path.cwd() / 'scripts' / NOM_SCRIPT]
    return candidats


def charger_extracteur():
    """Charge le module du script, ou ``None`` s'il est introuvable/illisible.

    ``None`` n'est PAS une erreur : c'est l'état normal du worker de production
    (voir le docstring du module). L'appelant journalise et s'arrête.
    """
    for candidat in _chemins_candidats():
        try:
            if not candidat.exists():
                continue
        except OSError:
            continue
        try:
            spec = importlib.util.spec_from_file_location(
                'taqinor_extract_i18n_strings', candidat)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception:  # noqa: BLE001 — un script illisible ne casse pas le beat
            logger.warning(
                'core.recalculer_couverture_i18n : %s trouvé à %s mais '
                'non chargeable.', NOM_SCRIPT, candidat)
            continue
        if hasattr(module, 'build_report'):
            return module
    return None


def rapport_utilisable(rapport):
    """Vrai si le rapport porte une mesure RÉELLE.

    Un rapport à 0 composant signifie que l'arborescence `frontend/src`
    n'était pas là (worker de production) — pas qu'il n'y a aucun écran. On
    refuse de le persister : 0/0 → 0 %, et l'écran lirait un effondrement
    inventé.
    """
    return bool(rapport) and int(rapport.get('total_components') or 0) > 0


def _chiffres(rapport):
    """Extrait du rapport les seuls chiffres persistés, sans en recalculer un."""
    domaines = rapport.get('domains') or {}
    chaines = sum(
        int((d or {}).get('hardcoded_strings') or 0)
        for d in domaines.values())
    return {
        'couverture_pct': Decimal(str(rapport.get('coverage_pct') or 0)),
        'composants_total': int(rapport.get('total_components') or 0),
        'composants_migres': int(rapport.get('migrated_components') or 0),
        'chaines_en_dur': chaines,
        'par_domaine': domaines,
    }


def recalculer_couverture_i18n(semaine=None, rapport=None):
    """Recalcule la couverture i18n et la persiste pour chaque société active.

    Renvoie la liste des instantanés écrits — VIDE quand aucune mesure réelle
    n'est disponible (le motif est journalisé, rien n'est écrit).

    ``semaine`` : lundi de la semaine ISO visée (défaut : la semaine courante,
    en heure marocaine). ``rapport`` : rapport déjà construit (les tests
    l'injectent pour ne pas dépendre de l'arborescence frontend).
    """
    from authentication.selectors import active_companies

    from .dates import aujourd_hui_local
    from .models import I18nCoverageSnapshot

    if rapport is None:
        module = charger_extracteur()
        if module is None:
            logger.info(
                'core.recalculer_couverture_i18n : %s introuvable depuis ce '
                'conteneur (le worker ne monte que backend/django_core) — '
                'aucun instantané écrit, aucun chiffre inventé.', NOM_SCRIPT)
            return []
        try:
            rapport = module.build_report()
        except Exception:  # noqa: BLE001 — jamais casser le beat sur un script
            logger.exception(
                'core.recalculer_couverture_i18n : build_report() a échoué — '
                'aucun instantané écrit.')
            return []

    if not rapport_utilisable(rapport):
        logger.info(
            'core.recalculer_couverture_i18n : rapport sans composant '
            '(frontend/src absent de ce conteneur) — aucun instantané écrit, '
            'plutôt qu\'une couverture de 0 %% qui serait fausse.')
        return []

    semaine = semaine or I18nCoverageSnapshot.lundi_de(aujourd_hui_local())
    valeurs = _chiffres(rapport)
    valeurs['calcule_le'] = timezone.now()

    ecrits = []
    for company in active_companies():
        snapshot, _cree = I18nCoverageSnapshot.objects.update_or_create(
            company=company, semaine=semaine, defaults=valeurs)
        ecrits.append(snapshot)
    logger.info(
        'core.recalculer_couverture_i18n : %d instantané(s) écrit(s) pour la '
        'semaine du %s (couverture %s%%).',
        len(ecrits), semaine, valeurs['couverture_pct'])
    return ecrits


@shared_task(name='core.recalculer_couverture_i18n')
def recalculer_couverture_i18n_task():
    """Job Beat hebdomadaire (voir BEAT_SCHEDULE dans erp_agentique/celery.py)."""
    return len(recalculer_couverture_i18n())
