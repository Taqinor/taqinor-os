"""YTEST11 — régénère les baselines PNG des golden PDF (YTEST10).

    python manage.py update_pdf_baselines

Régénère chaque baseline sous ``apps/ventes/tests/baselines/`` en rendant les
MÊMES formats, avec les MÊMES données fixes (``BASELINE_CASES``), que
``apps/ventes/tests/test_quote_engine_snapshot.py`` — le test et cette
commande appellent le MÊME code de rendu (``_render_pdf_bytes``) et de
rasterisation/écriture (``check_or_write_baseline``), pour qu'il n'existe
jamais deux logiques de génération divergentes.

Pensée pour tourner DANS l'image docker prod (WeasyPrint + PyMuPDF réels) —
la CI ne régénère JAMAIS automatiquement les baselines (revue humaine
obligatoire avant de committer un nouveau PNG, voir docs/TESTING.md). Les
lignes/société/client créés pour le rendu vivent dans une transaction
annulée à la fin (aucune trace en base) ; seuls les PNG sous
``apps/ventes/tests/baselines/`` sont des effets persistants.

Après exécution, ``git diff --stat apps/ventes/tests/baselines/`` montre
exactement les pages dont le rendu a changé — à revoir avant de committer.
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = ('YTEST11 — régénère les baselines PNG des golden PDF du moteur '
            'de devis premium (apps/ventes/tests/baselines/). À lancer dans '
            "l'image docker prod ; jamais en CI.")

    def handle(self, *args, **options):
        from apps.ventes.tests.test_quote_engine_snapshot import (
            BASELINE_CASES,
            _build_snapshot_devis,
            _render_pdf_bytes,
            check_or_write_baseline,
            make_client,
            make_company,
            make_user,
        )

        self.stdout.write(
            'Régénération des baselines PDF (UPDATE_PDF_SNAPSHOTS=1)…')

        written_total = []
        failures = []
        # Toute donnée créée pour le rendu (société/client/devis/produits de
        # démonstration) est annulée à la fin — seuls les PNG persistent.
        with transaction.atomic():
            company = make_company('qe-snap-baseline-cmd')
            user = make_user(company)
            client_obj = make_client(company)

            for case in BASELINE_CASES:
                devis = _build_snapshot_devis(company, user, client_obj, case)
                try:
                    pdf_bytes = _render_pdf_bytes(devis, case.get('pdf_options'))
                    written = check_or_write_baseline(
                        case['name'], pdf_bytes,
                        page_count=case['page_count'], update=True)
                except Exception as exc:  # noqa: BLE001 — on veut TOUT tenter
                    failures.append((case['name'], exc))
                    continue
                written_total.extend(written)
                self.stdout.write(f"  {case['name']} : "
                                  f'{len(written)} page(s) écrite(s)')

            transaction.set_rollback(True)

        if failures:
            self.stderr.write(self.style.ERROR(
                f'{len(failures)} cas en échec :'))
            for name, exc in failures:
                self.stderr.write(f'  {name} : {exc}')
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS(
            f'{len(written_total)} fichier(s) PNG écrit(s) sous '
            'apps/ventes/tests/baselines/. Relisez '
            '`git diff --stat apps/ventes/tests/baselines/` puis committez '
            'si le changement visuel est attendu.'))
