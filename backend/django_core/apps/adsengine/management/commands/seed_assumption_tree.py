"""PUB127 — Commande de SEMIS de l'arbre d'hypothèses (point de contact IA §4).

``seeding.py`` savait valider et importer un semis YAML (idempotent, testé,
ASG5) mais N'AVAIT AUCUNE COMMANDE : ``AssumptionNode`` restait à 0 pour
toujours, et la porte préflight d'autonomie (« arbre semé ») ne pouvait jamais
passer au vert. Cette commande est le chaînon manquant du jour 0 :

    manage.py seed_assumption_tree --file docs/engine/solar-tree-seed.yml \
        [--company <slug|id>] [--dry-run]

  * ``--file`` est OBLIGATOIRE : on ne sème jamais un arbre « par défaut »
    implicite — le fichier semé est un choix explicite, lisible et versionné ;
  * ``--dry-run`` VALIDE et IMPRIME le plan de semis (nœuds, classes, priors,
    liens) **sans écrire une seule ligne en base** ;
  * un YAML invalide est REFUSÉ avec TOUTES ses raisons en français
    (``seeding.SeedValidationError`` les collecte d'un coup) — jamais un import
    à moitié fait ;
  * l'import est IDEMPOTENT (``seeding.import_seed``) : deux passages laissent
    exactement le même état, et le posterior déjà APPRIS n'est jamais écrasé.

Sans ``--company``, toutes les sociétés actives sont semées (le même arbre de
départ) — chacune apprendra ensuite le sien.
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = ("Sème l'arbre d'hypothèses depuis un YAML validé "
            "(idempotent ; --dry-run n'écrit rien).")

    def add_arguments(self, parser):
        parser.add_argument(
            '--file', dest='file', required=True,
            help="Chemin du YAML de semis (ex. docs/engine/solar-tree-seed.yml).")
        parser.add_argument(
            '--company', dest='company', default=None,
            help="Slug ou id de la société (défaut : toutes les actives).")
        parser.add_argument(
            '--dry-run', dest='dry_run', action='store_true',
            help="Valide et imprime le plan de semis SANS rien écrire.")

    # ── Résolution des cibles ────────────────────────────────────────────────
    def _companies(self, raw):
        from authentication.models import Company
        from authentication.selectors import active_companies

        if raw is None:
            return list(active_companies())
        company = Company.objects.filter(slug=raw).first()
        if company is None and str(raw).isdigit():
            company = Company.objects.filter(pk=int(raw)).first()
        if company is None:
            raise CommandError(f"Société « {raw} » introuvable.")
        return [company]

    def _read(self, path):
        try:
            with open(path, encoding='utf-8') as handle:
                return handle.read()
        except OSError as exc:
            raise CommandError(
                f"Fichier de semis illisible : {path} ({exc}).") from exc

    # ── Plan de semis (dry-run) ──────────────────────────────────────────────
    def _print_plan(self, data):
        from apps.adsengine.models import AssumptionNode

        nodes = data['nodes']
        self.stdout.write(f"Plan de semis — {len(nodes)} nœud(s) :")
        for spec in nodes:
            prior = spec.get('prior') or {}
            alpha0 = prior.get('alpha0', 1)
            beta0 = prior.get('beta0', 1)
            demi_vie = spec.get('demi_vie_semaines')
            if demi_vie is None:
                demi_vie = AssumptionNode.HALF_LIFE_WEEKS.get(
                    spec['classe'], '?')
            liens = spec.get('invalidation_links') or []
            self.stdout.write(
                f"  · [{spec['classe']}] {spec['key']} — "
                f"S={spec['enjeux_s']} R={spec['pertinence_r']} "
                f"prior Beta({alpha0}, {beta0}) demi-vie {demi_vie} sem. "
                f"statut « {spec.get('statut', 'assumed')} »")
            self.stdout.write(f"      « {spec['enonce_fr']} »")
            if spec.get('parent'):
                self.stdout.write(f"      parent : {spec['parent']}")
            if liens:
                self.stdout.write(
                    f"      invalide aussi : {', '.join(liens)}")
        self.stdout.write(self.style.WARNING(
            "--dry-run : AUCUNE écriture en base."))

    # ── Exécution ────────────────────────────────────────────────────────────
    def handle(self, *args, **options):
        from apps.adsengine import seeding

        raw = self._read(options['file'])
        try:
            data = seeding.validate(raw)
        except seeding.SeedValidationError as exc:
            self.stdout.write(self.style.ERROR(
                "Semis REFUSÉ — le fichier n'est pas importable :"))
            for reason in exc.reasons_fr:
                self.stdout.write(self.style.ERROR(f"  · {reason}"))
            raise CommandError(
                f"{len(exc.reasons_fr)} problème(s) dans {options['file']} — "
                f"rien n'a été semé.")

        if options['dry_run']:
            self._print_plan(data)
            return None

        companies = self._companies(options.get('company'))
        if not companies:
            self.stdout.write(self.style.WARNING(
                "Aucune société active — no-op propre."))
            return None

        total_created = total_updated = 0
        for company in companies:
            # ``validate_first=False`` : le semis vient d'être validé ci-dessus
            # (une seule validation pour toutes les sociétés).
            result = seeding.import_seed(company, data, validate_first=False)
            total_created += result['created']
            total_updated += result['updated']
            self.stdout.write(
                f"  · {getattr(company, 'nom', company.pk)} : "
                f"{result['created']} créé(s), {result['updated']} mis à jour.")

        self.stdout.write(self.style.SUCCESS(
            f"seed_assumption_tree : {len(companies)} société(s), "
            f"{total_created} nœud(s) créé(s), "
            f"{total_updated} mis à jour (idempotent)."))
        return None
