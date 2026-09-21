"""Seed standard solar ITP (Inspection & Test Plan) templates per company.

Creates a sensible set of ``PlanInspectionModele`` gabarits — one per
installation type — together with their ``PointControleModele`` control points,
for every company (or a single ``--company`` slug). The data is vendored here as
plain Python: realistic but deliberately scoped to a handful of points per plan,
covering the usual solar project phases (étude → réception matériel → pose →
raccordement → mise en service → réception) with mandatory hold-points at
``Raccordement`` and ``Mise en service``.

Idempotent and strictly additive — modelled on ``seed_catalogue``:
  * each plan is matched by the stable key ``(company, code)`` via
    ``get_or_create`` — re-running creates nothing new;
  * each control point is matched by ``(company, plan, ordre)`` — re-running
    creates nothing new and NEVER overwrites a row the user has since edited
    (the seeder only fills missing rows, it never updates an existing one);
  * a plan/point already present (even with edited fields) is left untouched.

Run (inside the django_core container or with DB env vars set):
  python manage.py seed_itp_solaire            # all companies
  python manage.py seed_itp_solaire --company taqinor-demo   # one company
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


# Type-de-relevé codes (mirror PointControleModele.TypeReleve.choices) — kept as
# literals so a typo surfaces in the test rather than silently importing a label.
MESURE = 'mesure'
VISUEL = 'visuel'
DOCUMENT = 'document'
ESSAI = 'essai'


# ── ITP templates : (code, nom, description, [points]) ───────────────────────
# A point is (ordre, phase, intitulé, type_releve, hold_point, description).
# Hold-points (point d'arrêt) sit at Raccordement and Mise en service: the work
# cannot proceed until they are signed off.
ITP_PLANS = [
    {
        'code': 'ITP-RES-RES',
        'nom': 'ITP — Résidentiel raccordé réseau',
        'description': (
            "Plan d'inspection et d'essais pour une installation "
            "photovoltaïque résidentielle raccordée au réseau "
            "(autoconsommation avec/sans injection)."
        ),
        'points': [
            (10, 'Étude', "Validation de l'étude et du dimensionnement",
             DOCUMENT, False,
             "Note de calcul, plan de calepinage et schéma unifilaire validés."),
            (20, 'Réception matériel',
             "Conformité du matériel livré (modules, onduleur, structure)",
             VISUEL, False,
             "Marques, références et quantités conformes au bon de commande ; "
             "absence de chocs/casse."),
            (30, 'Pose', "Serrage au couple de la structure et des modules",
             MESURE, False,
             "Couples de serrage relevés et conformes aux préconisations "
             "constructeur."),
            (40, 'Pose', "Continuité de la mise à la terre et liaisons "
             "équipotentielles",
             MESURE, False,
             "Résistance de terre mesurée et conforme."),
            (50, 'Raccordement', "Contrôle du câblage DC/AC avant mise sous "
             "tension",
             VISUEL, True,
             "Polarités, sections, calibres de protection et parafoudres "
             "vérifiés — POINT D'ARRÊT avant mise sous tension."),
            (60, 'Mise en service', "Essai de fonctionnement et mesures à la "
             "mise en service",
             ESSAI, True,
             "Tension/courant chaîne, démarrage onduleur et production "
             "constatés — POINT D'ARRÊT."),
            (70, 'Réception', "Réception des travaux et remise du dossier",
             DOCUMENT, False,
             "PV de réception signé, fiches de garantie et notice de suivi "
             "remis au client."),
        ],
    },
    {
        'code': 'ITP-AC-INDCOM',
        'nom': 'ITP — Autoconsommation industriel / commercial',
        'description': (
            "Plan d'inspection et d'essais pour une centrale "
            "photovoltaïque d'autoconsommation en site industriel ou "
            "commercial (toiture/sol, puissance élevée)."
        ),
        'points': [
            (10, 'Étude', "Validation de l'étude, du dimensionnement et de "
             "l'étude d'autoconsommation",
             DOCUMENT, False,
             "Note de calcul, taux d'autoconsommation/couverture et schéma "
             "unifilaire validés."),
            (20, 'Réception matériel',
             "Conformité du matériel et des certificats constructeur",
             DOCUMENT, False,
             "Fiches techniques, certificats et bons de livraison contrôlés."),
            (30, 'Pose', "Conformité de la structure porteuse et de "
             "l'ancrage",
             VISUEL, False,
             "Implantation, lestage/ancrage et calepinage conformes au plan."),
            (40, 'Pose', "Serrage au couple et continuité des masses",
             MESURE, False,
             "Couples de serrage et continuité des masses relevés et "
             "conformes."),
            (50, 'Raccordement', "Contrôle DC/AC, protections et compteur "
             "avant mise sous tension",
             MESURE, True,
             "Isolement DC, calibres de protection, parafoudres et compteur "
             "de production vérifiés — POINT D'ARRÊT."),
            (60, 'Mise en service', "Essais de mise en service et zéro "
             "injection",
             ESSAI, True,
             "Démarrage onduleurs, supervision et bridage/zéro injection "
             "validés — POINT D'ARRÊT."),
            (70, 'Réception', "Réception des travaux et dossier d'ouvrage "
             "exécuté",
             DOCUMENT, False,
             "PV de réception, DOE et procédure de maintenance remis."),
        ],
    },
    {
        'code': 'ITP-POMP-AGRI',
        'nom': 'ITP — Pompage solaire agricole',
        'description': (
            "Plan d'inspection et d'essais pour une station de pompage "
            "solaire agricole (pompe immergée/surface pilotée par variateur, "
            "sans batterie)."
        ),
        'points': [
            (10, 'Étude', "Validation de l'étude de pompage (HMT, débit, "
             "dimensionnement champ PV)",
             DOCUMENT, False,
             "HMT, débit souhaité, choix pompe/variateur et puissance champ "
             "PV validés."),
            (20, 'Réception matériel',
             "Conformité de la pompe, du variateur et des accessoires",
             VISUEL, False,
             "Pompe, variateur, câble immergé et afficheur conformes au bon "
             "de commande."),
            (30, 'Pose', "Installation du champ PV et de la pompe",
             VISUEL, False,
             "Structure, modules et descente de pompe au forage réalisés "
             "conformément au plan."),
            (40, 'Pose', "Continuité de la mise à la terre",
             MESURE, False,
             "Mise à la terre du champ PV et du coffret variateur mesurée et "
             "conforme."),
            (50, 'Raccordement', "Contrôle du câblage et des protections "
             "avant mise sous tension",
             VISUEL, True,
             "Câblage PV→variateur→pompe, sections du câble immergé et "
             "protections vérifiés — POINT D'ARRÊT."),
            (60, 'Mise en service', "Essai de pompage et protection marche à "
             "sec",
             ESSAI, True,
             "Débit constaté à la HMT, démarrage automatique au soleil et "
             "protection manque d'eau testés — POINT D'ARRÊT."),
            (70, 'Réception', "Réception et remise du dossier d'exploitation",
             DOCUMENT, False,
             "PV de réception, paramètres variateur consignés et notice "
             "d'exploitation remis."),
        ],
    },
]


class Command(BaseCommand):
    help = (
        "Seed standard solar ITP templates (plans + control points) per "
        "installation type, for every company or a single --company "
        "(idempotent, additive only)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', default=None,
            help="Slug of a single company to seed (default: all companies).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from authentication.models import Company
        from apps.qhse.models import PlanInspectionModele, PointControleModele

        slug = options.get('company')
        if slug:
            try:
                companies = [Company.objects.get(slug=slug)]
            except Company.DoesNotExist:
                raise CommandError(f"Company with slug '{slug}' not found.")
        else:
            companies = list(Company.objects.all())

        if not companies:
            self.stdout.write(self.style.WARNING(
                "No company to seed — nothing done."))
            return

        plans_created = points_created = 0

        for company in companies:
            for spec in ITP_PLANS:
                plan, plan_is_new = PlanInspectionModele.objects.get_or_create(
                    company=company,
                    code=spec['code'],
                    defaults={
                        'nom': spec['nom'],
                        'description': spec['description'],
                        'actif': True,
                    },
                )
                if plan_is_new:
                    plans_created += 1

                for ordre, phase, intitule, type_releve, hold, desc in \
                        spec['points']:
                    # Stable key (company, plan, ordre): re-running never
                    # duplicates and never overwrites an edited point.
                    _, pt_is_new = PointControleModele.objects.get_or_create(
                        company=company,
                        plan=plan,
                        ordre=ordre,
                        defaults={
                            'intitule': intitule,
                            'phase': phase,
                            'type_releve': type_releve,
                            'hold_point': hold,
                            'description': desc,
                        },
                    )
                    if pt_is_new:
                        points_created += 1

        self.stdout.write(self.style.SUCCESS(
            f"ITP solaire seeded for {len(companies)} société(s): "
            f"{plans_created} plan(s) and {points_created} point(s) created "
            f"(existing rows left untouched)."))
