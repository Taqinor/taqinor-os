"""YHARD10 — export anonymisé du parc de données (clone UAT/staging).

Produit un dump de fixtures Django (JSON, rechargeable via ``loaddata``) où
TOUTES les colonnes PII connues (``core.anonymize_export``) sont remplacées
par des valeurs factices déterministes, en préservant l'intégrité relationnelle
(les FK/PK ne sont jamais modifiées — seules les VALEURS des champs PII
changent). LECTURE SEULE vis-à-vis de la base source : ce n'est PAS un
``core.dsr`` (droits RGPD/personne — logique légale différente, ex. RH refuse
l'effacement) ; ici on fabrique un clone de test, jamais un effacement légal
et jamais une écriture sur la base source.

Garde de sécurité : refuse de tourner sans ``--confirm`` explicite (aucune
sortie accidentelle d'un jeu de données PII réel).

Exemple :
    python manage.py export_anonymise --confirm --output uat_dump.json
"""
import json

from django.apps import apps as django_apps
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError

from core import anonymize_export


class Command(BaseCommand):
    help = (
        'Exporte un clone anonymisé du parc de données (fixtures JSON) pour '
        'un environnement UAT/staging. Lecture seule vis-à-vis de la source ; '
        'refuse de tourner sans --confirm.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm', action='store_true', default=False,
            help='Obligatoire — confirme explicitement vouloir exporter un dump.')
        parser.add_argument(
            '--output', default='anonymized_export.json',
            help='Chemin du fichier de sortie (JSON, fixtures Django).')
        parser.add_argument(
            '--models', nargs='*', default=None,
            help=(
                'Sous-ensemble de modèles à exporter (ex. crm.Client rh.DossierEmploye). '
                'Par défaut : tous les modèles ayant un masque PII enregistré, '
                'PLUS toute app fournie explicitement pour préserver l\'intégrité FK.'
            ))

    def handle(self, *args, **options):
        if not options['confirm']:
            raise CommandError(
                "export_anonymise refuse de tourner sans --confirm "
                "(garde de sécurité — évite une sortie accidentelle de PII réelles).")

        anonymize_export.reset_counter()

        model_labels = options['models'] or anonymize_export.registered_models()
        if not model_labels:
            raise CommandError(
                'Aucun modèle à exporter (ni --models fourni, ni masque enregistré).')

        objects_out = []
        summary = {}

        for label in model_labels:
            try:
                model = django_apps.get_model(label)
            except (LookupError, ValueError) as exc:
                raise CommandError(f'Modèle introuvable: {label} ({exc})')

            mask = anonymize_export.mask_for(label)
            count = 0
            for instance in model.objects.all().iterator():
                for field_name, scrubber in mask.items():
                    if not hasattr(instance, field_name):
                        continue
                    original = getattr(instance, field_name)
                    setattr(instance, field_name, scrubber(original))
                # Sérialise l'instance MODIFIÉE EN MÉMOIRE (jamais sauvegardée —
                # aucune écriture sur la base source, cf. docstring).
                objects_out.append(instance)
                count += 1
            summary[label] = count

        payload = serializers.serialize('json', objects_out, indent=2)
        with open(options['output'], 'w', encoding='utf-8') as fh:
            fh.write(payload)

        total = sum(summary.values())
        self.stdout.write(self.style.SUCCESS(
            f'export_anonymise: OK — {total} objet(s) exporté(s) vers '
            f'{options["output"]}.'))
        for label, count in sorted(summary.items()):
            self.stdout.write(f'  - {label}: {count}')
        # Sortie machine-lisible optionnelle (script CI/staging).
        self.stdout.write(json.dumps({'output': options['output'], 'summary': summary}))
