"""SOL3 — vérifie que l'édition chargée est COHÉRENTE (lecture seule).

Une seule commande, utilisée par le test de boot des deux éditions ET par le
job CI « solar-boot ». Elle n'écrit rien et ne touche pas la base : elle
inspecte l'état effectivement chargé (INSTALLED_APPS, arbre d'urls, planning
beat, overrides d'énumération) et le compare au registre statique
``erp_agentique/settings/editions.py``.

Sortie en français ; code de retour non nul (``CommandError``) au premier
écart — un vertical parqué qui reste monté est exactement le genre de
recouplage silencieux que le groupe SOL existe pour empêcher.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from erp_agentique.settings import editions


def _modules_de_l_arbre_urls():
    """Noms de modules d'urls effectivement montés (récursif, best-effort)."""
    from django.urls import get_resolver

    vus = set()

    def _descendre(resolver, profondeur=0):
        if profondeur > 6:
            return
        for motif in getattr(resolver, 'url_patterns', []):
            cible = getattr(motif, 'urlconf_name', None)
            nom = getattr(cible, '__name__', None)
            if nom:
                vus.add(nom)
            if hasattr(motif, 'url_patterns'):
                _descendre(motif, profondeur + 1)

    _descendre(get_resolver())
    return vus


class Command(BaseCommand):
    help = (
        "Vérifie la cohérence de l'édition chargée (TAQINOR_EDITION) : "
        "apps parquées absentes d'INSTALLED_APPS, de l'arbre d'urls, du "
        "planning Celery beat et des overrides d'énumération. Lecture seule."
    )

    def handle(self, *args, **options):
        edition = getattr(
            settings, 'TAQINOR_EDITION', editions.DEFAULT_EDITION)
        parquees = editions.apps_parquees(edition)
        modules_parques = editions.modules_parques(edition)

        self.stdout.write(f'Édition chargée : {edition}')
        self.stdout.write(
            f'Apps installées : {len(settings.INSTALLED_APPS)}')
        if parquees:
            self.stdout.write('Verticaux parqués par cette édition :')
            for chemin, libelle in sorted(parquees.items()):
                self.stdout.write(f'  - {libelle} ({chemin})')
        else:
            self.stdout.write(
                'Aucun vertical parqué (édition complète) — tout est chargé.')

        ecarts = []

        # 1. INSTALLED_APPS
        installees = set(settings.INSTALLED_APPS)
        restantes = sorted(installees & set(parquees))
        if restantes:
            ecarts.append(
                'apps parquées encore dans INSTALLED_APPS : '
                + ', '.join(restantes))

        # 2. Arbre d'urls
        montes = _modules_de_l_arbre_urls()
        urls_parquees = sorted(
            nom for nom in montes
            if editions.est_module_parque(nom, edition))
        if urls_parquees:
            ecarts.append(
                "modules d'urls parqués encore montés (ils répondraient au "
                'lieu de renvoyer 404) : ' + ', '.join(urls_parquees))

        # 3. Planning Celery beat
        try:
            from erp_agentique.celery import app as celery_app
            planning = dict(celery_app.conf.beat_schedule or {})
        except Exception:  # pragma: no cover - celery indisponible
            planning = {}
        prefixes = tuple(f'{cle}.' for cle in sorted(modules_parques))
        beat_parquees = sorted(
            nom for nom, entree in planning.items()
            if prefixes and str(entree.get('task', '')).startswith(prefixes))
        if beat_parquees:
            ecarts.append(
                'tâches beat d\'apps parquées encore planifiées : '
                + ', '.join(beat_parquees))

        # 4. Overrides d'énumération OpenAPI
        overrides = (
            getattr(settings, 'SPECTACULAR_SETTINGS', {})
            .get('ENUM_NAME_OVERRIDES', {}) or {})
        enums_parquees = sorted(
            nom for nom, chemin in overrides.items()
            if isinstance(chemin, str)
            and editions.est_module_parque(chemin, edition))
        if enums_parquees:
            ecarts.append(
                "overrides d'énumération pointant vers une app parquée : "
                + ', '.join(enums_parquees))

        self.stdout.write(f'Routes/urls montées (modules) : {len(montes)}')
        self.stdout.write(f'Tâches planifiées (beat) : {len(planning)}')

        if ecarts:
            raise CommandError(
                'Édition INCOHÉRENTE — ' + ' ; '.join(ecarts))
        self.stdout.write(
            self.style.SUCCESS(f'Édition « {edition} » cohérente.'))
