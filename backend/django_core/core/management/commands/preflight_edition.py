"""SOL13 — Préflight de bascule d'édition. LECTURE SEULE, sortie en français.

À exécuter AVANT de poser `TAQINOR_EDITION=solar` en production, depuis
l'édition COMPLÈTE (c'est la seule où les apps parquées sont chargées, donc la
seule où l'on peut compter ce qu'on s'apprête à rendre inaccessible).

Ce que la commande imprime, et pourquoi :

  1. **Données** — lignes par société dans les tables de chaque app parquée.
     Rien n'est supprimé par la bascule (les tables restent, les migrations
     restent), mais une société qui a 400 lignes dans `sante` perdra l'ACCÈS à
     ses écrans : ça se décide en connaissance de cause, pas par surprise.
  2. **Travail asynchrone** — tâches Celery beat qui vont disparaître du
     planning, jobs de fond encore en file dont le type vise une app parquée,
     et (best-effort) tâches réservées côté broker qui ne seront plus
     enregistrées après le redéploiement.
  3. **Configuration** — `ModuleToggle`, préférences et règles de routage de
     notification, et rôles portant des permissions d'apps parquées : autant de
     réglages qui deviendront inertes.

ZÉRO ÉCRITURE : aucune création, aucune mise à jour, aucune suppression. La
commande peut être relancée autant de fois qu'on veut.

Code de retour : TOUJOURS 0 — c'est un rapport, pas une garde. Un préflight
« suspect » se lit ; il ne casse pas un déploiement tout seul.
"""
from django.core.management.base import BaseCommand

from erp_agentique.settings import editions

SEPARATEUR = '─' * 72


class Command(BaseCommand):
    help = ("Préflight LECTURE SEULE avant bascule d'édition : ce que la "
            "bascule vers l'édition solaire rendra inaccessible (données, "
            "travail asynchrone, configuration). N'écrit rien.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--edition', default=editions.EDITION_SOLAR,
            choices=list(editions.EDITIONS),
            help="Édition VISÉE (défaut : solar).")
        parser.add_argument(
            '--max-societes', type=int, default=20,
            help="Nombre maximum de sociétés détaillées par table (défaut 20).")
        parser.add_argument(
            '--inspecter-broker', action='store_true',
            help="Interroge AUSSI les workers Celery (tâches réservées / "
                 "planifiées). Opt-in : hors du serveur il n'y a aucun worker "
                 "joignable, et l'attente ne dirait rien d'utile.")

    # ── utilitaires ────────────────────────────────────────────────────────
    def _titre(self, texte):
        self.stdout.write('')
        self.stdout.write(SEPARATEUR)
        self.stdout.write(texte)
        self.stdout.write(SEPARATEUR)

    def _societes(self):
        from authentication.models import Company
        return {c.pk: c.nom for c in Company.objects.all().only('id', 'nom')}

    # ── 1. données ─────────────────────────────────────────────────────────
    def _donnees(self, parquees, max_societes):
        from django.apps import apps as django_apps
        from django.db.models import Count

        self._titre('1. DONNÉES des applications parquées')
        noms_societes = self._societes()
        total_general = 0
        for chemin, libelle in sorted(parquees.items(), key=lambda kv: kv[1]):
            label = chemin.rsplit('.', 1)[-1]
            try:
                app_config = django_apps.get_app_config(label)
            except LookupError:
                self.stdout.write(
                    f'\n{libelle} ({chemin}) : app NON CHARGÉE — relancez ce '
                    'préflight en édition complète pour compter ses données.')
                continue
            modeles = list(app_config.get_models())
            self.stdout.write(f'\n{libelle} ({chemin}) — {len(modeles)} table(s)')
            total_app = 0
            for modele in sorted(modeles, key=lambda m: m._meta.model_name):
                try:
                    total = modele.objects.count()
                except Exception as exc:  # noqa: BLE001 — table absente/illisible
                    self.stdout.write(
                        f'  {modele._meta.model_name:<38} illisible ({exc})')
                    continue
                total_app += total
                if total == 0:
                    continue
                self.stdout.write(
                    f'  {modele._meta.model_name:<38} {total:>8} ligne(s)')
                if not any(f.name == 'company'
                           for f in modele._meta.get_fields()
                           if hasattr(f, 'attname')):
                    continue
                try:
                    par_societe = (modele.objects
                                   .values('company_id')
                                   .annotate(n=Count('id'))
                                   .order_by('-n')[:max_societes])
                except Exception:  # noqa: BLE001 — pas de FK company exploitable
                    continue
                for ligne in par_societe:
                    nom = noms_societes.get(
                        ligne['company_id'], f"société #{ligne['company_id']}")
                    self.stdout.write(
                        f'      · {nom:<32} {ligne["n"]:>8}')
            total_app and self.stdout.write(
                f'  → total {libelle} : {total_app} ligne(s)')
            total_general += total_app
        self.stdout.write(
            f'\nTOTAL des données parquées : {total_general} ligne(s). '
            'AUCUNE ne sera supprimée par la bascule — les tables et les '
            "migrations restent ; seul l'ACCÈS disparaît.")
        return total_general

    # ── 2. travail asynchrone ──────────────────────────────────────────────
    def _asynchrone(self, edition, cles_parquees, inspecter_broker=False):
        self._titre('2. TRAVAIL ASYNCHRONE')
        prefixes = tuple(f'{cle}.' for cle in sorted(cles_parquees))

        # 2a. planning beat qui disparaît.
        try:
            from erp_agentique.celery import app as celery_app
            planning = dict(celery_app.conf.beat_schedule or {})
        except Exception as exc:  # noqa: BLE001
            planning = {}
            self.stdout.write(f'Planning beat illisible : {exc}')
        perdues = sorted(
            (nom, str(e.get('task', '')))
            for nom, e in planning.items()
            if prefixes and str(e.get('task', '')).startswith(prefixes))
        self.stdout.write(
            f'\nTâches planifiées (beat) retirées par la bascule : {len(perdues)}')
        for nom, tache in perdues:
            self.stdout.write(f'  · {nom} → {tache}')

        # 2b. jobs de fond encore en file.
        try:
            from core.models import BackgroundJob
            en_file = list(
                BackgroundJob.objects
                .filter(statut__in=[BackgroundJob.STATUT_QUEUED,
                                    BackgroundJob.STATUT_RUNNING])
                .values_list('id', 'kind', 'statut', 'company_id')[:200])
        except Exception as exc:  # noqa: BLE001
            en_file = []
            self.stdout.write(f'Jobs de fond illisibles : {exc}')
        vises = [j for j in en_file
                 if prefixes and str(j[1]).startswith(prefixes)]
        self.stdout.write(
            f'\nJobs de fond en file / en cours : {len(en_file)}, '
            f'dont {len(vises)} visant une app parquée')
        for job_id, kind, statut, company_id in vises:
            self.stdout.write(
                f'  · #{job_id} {kind} ({statut}, société #{company_id})')

        # 2c. broker (opt-in — nécessite un worker joignable).
        self.stdout.write('')
        if not inspecter_broker:
            self.stdout.write(
                "Inspection du broker Celery non demandée (--inspecter-broker "
                'pour la lancer depuis le serveur).')
            return len(perdues)
        try:
            from erp_agentique.celery import app as celery_app
            inspection = celery_app.control.inspect(timeout=2)
            reserves = inspection.reserved() or {}
            planifiees = inspection.scheduled() or {}
        except Exception as exc:  # noqa: BLE001 — broker injoignable = normal
            self.stdout.write(
                f'Inspection du broker Celery impossible ({exc}) — à relancer '
                'depuis le serveur si vous voulez ce détail.')
            return len(perdues)
        attente = []
        for source in (reserves, planifiees):
            for _worker, taches in (source or {}).items():
                for tache in taches or []:
                    nom = (tache.get('request') or tache).get('name') or ''
                    if prefixes and str(nom).startswith(prefixes):
                        attente.append(nom)
        self.stdout.write(
            f"Tâches en attente côté broker visant une app parquée : "
            f'{len(attente)}')
        for nom in sorted(set(attente)):
            self.stdout.write(f'  · {nom}')
        return len(perdues)

    # ── 3. configuration ───────────────────────────────────────────────────
    def _configuration(self, cles_parquees):
        self._titre('3. CONFIGURATION qui deviendra inerte')
        noms_societes = self._societes()

        # 3a. ModuleToggle.
        try:
            from core.models import ModuleToggle
            toggles = list(
                ModuleToggle.objects
                .filter(module__in=sorted(cles_parquees))
                .values_list('company_id', 'module', 'actif'))
        except Exception as exc:  # noqa: BLE001
            toggles = []
            self.stdout.write(f'ModuleToggle illisible : {exc}')
        self.stdout.write(
            f'\nLignes ModuleToggle sur un module parqué : {len(toggles)}')
        for company_id, module, actif in sorted(toggles):
            nom = noms_societes.get(company_id, f'société #{company_id}')
            etat = 'actif' if actif else 'désactivé'
            self.stdout.write(f'  · {nom} — {module} ({etat})')

        # 3b. notifications (préférences + règles de routage).
        for chemin_modele, libelle in (
                ('apps.notifications.models.NotificationPreference',
                 'Préférences de notification'),
                ('apps.notifications.models.NotificationRoutingRule',
                 'Règles de routage de notification')):
            self._compter_event_types(chemin_modele, libelle, cles_parquees)

        # 3c. rôles portant des permissions d'apps parquées.
        try:
            from apps.roles.models import PERMISSION_MODULE, Role
            codes = sorted(
                c for c, m in PERMISSION_MODULE.items() if m in cles_parquees)
            porteurs = []
            if codes:
                for role in Role.objects.all().only(
                        'id', 'nom', 'company_id', 'permissions'):
                    portes = sorted(
                        set(role.permissions or []) & set(codes))
                    if portes:
                        porteurs.append((role.company_id, role.nom, portes))
        except Exception as exc:  # noqa: BLE001
            codes, porteurs = [], []
            self.stdout.write(f'Rôles illisibles : {exc}')
        self.stdout.write(
            f'\nCodes de permission appartenant à une app parquée : '
            f'{len(codes)} ; rôles qui en portent : {len(porteurs)}')
        for company_id, nom_role, portes in sorted(porteurs):
            nom = noms_societes.get(company_id, f'société #{company_id}')
            self.stdout.write(
                f'  · {nom} — rôle « {nom_role} » : {", ".join(portes)}')
        self.stdout.write(
            "  (ces codes RESTENT sur les rôles : réactiver l'édition "
            'complète rend les droits intacts.)')

    def _compter_event_types(self, chemin_modele, libelle, cles_parquees):
        from django.utils.module_loading import import_string

        try:
            modele = import_string(chemin_modele)
            lignes = list(
                modele.objects.values_list('event_type', flat=True)[:5000])
        except Exception as exc:  # noqa: BLE001 — app absente = rien à dire
            self.stdout.write(f'\n{libelle} : illisible ({exc})')
            return
        vises = sorted({
            e for e in lignes
            if any(str(e).startswith(f'{cle}_') for cle in cles_parquees)
        })
        self.stdout.write(
            f'\n{libelle} : {len(lignes)} ligne(s), '
            f"{len(vises)} type(s) d'événement d'une app parquée")
        for event_type in vises:
            self.stdout.write(f'  · {event_type}')

    # ── point d'entrée ─────────────────────────────────────────────────────
    def handle(self, *args, **options):
        edition_visee = options['edition']
        parquees = editions.apps_parquees(edition_visee)
        cles = set(editions.modules_parques(edition_visee))

        from django.conf import settings
        edition_courante = getattr(
            settings, 'TAQINOR_EDITION', editions.DEFAULT_EDITION)

        self.stdout.write(SEPARATEUR)
        self.stdout.write(
            "PRÉFLIGHT DE BASCULE D'ÉDITION — lecture seule, aucune écriture")
        self.stdout.write(SEPARATEUR)
        self.stdout.write(f'Édition actuellement chargée : {edition_courante}')
        self.stdout.write(f'Édition visée                : {edition_visee}')
        if not parquees:
            self.stdout.write(
                "\nL'édition visée ne parque aucune application : la bascule "
                "n'a aucun impact. Rien à vérifier.")
            return
        if edition_courante != editions.EDITION_FULL:
            self.stdout.write(self.style.WARNING(
                "\nATTENTION : ce préflight tourne HORS édition complète. Les "
                'applications parquées ne sont pas chargées, leurs données ne '
                'peuvent donc pas être comptées. Relancez-le avec '
                'TAQINOR_EDITION=full pour un rapport complet.'))
        self.stdout.write(
            f'\nApplications parquées par l\'édition « {edition_visee} » : '
            f'{len(parquees)}')
        for chemin, libelle in sorted(parquees.items(), key=lambda kv: kv[1]):
            self.stdout.write(f'  · {libelle} ({chemin})')

        lignes = self._donnees(parquees, options['max_societes'])
        beat = self._asynchrone(
            edition_visee, cles,
            inspecter_broker=options['inspecter_broker'])
        self._configuration(cles)

        self._titre('RÉSUMÉ')
        self.stdout.write(
            f'{len(parquees)} application(s) parquée(s), {lignes} ligne(s) de '
            f'données concernées, {beat} tâche(s) planifiée(s) retirée(s).')
        self.stdout.write(
            'Rien n\'a été écrit. Si ce rapport ne réserve aucune surprise, la '
            'bascule peut être appliquée (TAQINOR_EDITION=solar côté serveur, '
            'puis redéploiement et vérification de santé). Au moindre doute — '
            'des données métier vivantes dans une app parquée, une tâche en '
            'file — remonter le rapport avant de basculer.')
