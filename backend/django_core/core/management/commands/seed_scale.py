"""NTPLT47 — Générateur de données à L'ÉCHELLE pour les mesures de charge.

    python manage.py seed_scale --companies 5 --users 200 --leads 100000 \
        --devis 30000 --lignes 1000000 --mouvements 500000

Prérequis de toute mesure de charge honnête et des démos « gros volume ».
``bulk_create`` par lots de 5 000, données Faker fr_FR. REFUSE de tourner hors
DEBUG sans ``--force-je-sais`` (garde-fou anti-prod). IDEMPOTENT par tag : les
sociétés portent le tag dans leur nom ; relancer ne double pas.

``core`` reste FONDATION : aucun import statique d'app métier — les modèles sont
résolus dynamiquement (``apps.get_model``) et les champs synthétisés
GÉNÉRIQUEMENT par introspection ``_meta`` (bulk_create court-circuite la
validation : seules les contraintes DB not-null / unique / FK comptent).
"""
from __future__ import annotations

import random
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.text import slugify

BATCH = 5000


def _concrete_required_fields(model):
    """Champs concrets à VALORISER : not-null, sans défaut, non auto, non pk."""
    out = []
    for f in model._meta.get_fields():
        if not getattr(f, 'concrete', False):
            continue
        if getattr(f, 'primary_key', False):
            continue
        if getattr(f, 'auto_created', False):
            continue
        if getattr(f, 'has_default', lambda: False)():
            continue
        if getattr(f, 'auto_now', False) or getattr(f, 'auto_now_add', False):
            continue
        if getattr(f, 'null', False):
            continue
        out.append(f)
    return out


def _fake_scalar(field, faker, seq):
    """Valeur synthétique par type interne, unicité assurée via ``seq``."""
    it = field.get_internal_type()
    unique = getattr(field, 'unique', False)
    choices = getattr(field, 'choices', None)
    if choices:
        return list(choices)[0][0]
    if it in ('CharField', 'TextField', 'SlugField'):
        maxlen = getattr(field, 'max_length', None) or 200
        base = f'{field.name}-{seq}' if unique else faker.word()
        if 'email' in field.name.lower():
            base = f'{field.name}{seq}@example.test'
        return base[:maxlen]
    if it in ('EmailField',):
        return f'{field.name}{seq}@example.test'
    if it in ('IntegerField', 'PositiveIntegerField', 'BigIntegerField',
              'PositiveBigIntegerField', 'SmallIntegerField',
              'PositiveSmallIntegerField'):
        return seq if unique else random.randint(0, 1000)
    if it in ('DecimalField', 'FloatField'):
        return round(random.uniform(0, 10000), 2)
    if it in ('BooleanField',):
        return bool(random.getrandbits(1))
    if it in ('DateField',):
        return timezone.now().date() - timedelta(days=random.randint(0, 900))
    if it in ('DateTimeField',):
        return timezone.now() - timedelta(days=random.randint(0, 900))
    if it in ('JSONField',):
        return {}
    if it in ('UUIDField',):
        import uuid
        return uuid.uuid4()
    # Repli sûr.
    return f'{field.name}-{seq}'


class Command(BaseCommand):
    help = "Génère des données à l'échelle (charge/démo). DEBUG only sauf --force."

    def add_arguments(self, parser):
        parser.add_argument('--companies', type=int, default=2)
        parser.add_argument('--users', type=int, default=50)
        parser.add_argument('--leads', type=int, default=1000)
        parser.add_argument('--devis', type=int, default=200)
        parser.add_argument('--lignes', type=int, default=1000)
        parser.add_argument('--mouvements', type=int, default=1000)
        parser.add_argument('--tag', default='SEED_SCALE')
        parser.add_argument(
            '--force-je-sais', action='store_true',
            help='Autorise l\'exécution hors DEBUG (dangereux).')

    def handle(self, *args, **options):
        from django.apps import apps as django_apps
        from django.conf import settings
        try:
            from faker import Faker
        except ImportError:
            raise CommandError(
                'Faker requis (pip install Faker ; cf. requirements-dev.txt).')

        if not settings.DEBUG and not options['force_je_sais']:
            raise CommandError(
                'seed_scale refuse de tourner hors DEBUG sans --force-je-sais.')

        faker = Faker('fr_FR')
        tag = options['tag']

        Company = django_apps.get_model('authentication', 'Company')
        # Idempotence par tag : sociétés déjà taguées → on ne recrée pas.
        existing = list(Company.objects.filter(nom__startswith=f'[{tag}]'))
        companies = existing
        want_co = options['companies']
        if len(companies) < want_co:
            new = []
            for i in range(len(companies), want_co):
                # ``bulk_create`` court-circuite ``Company.save()`` qui génère
                # d'ordinaire le ``slug`` (unique). Sans slug explicite, toutes
                # les sociétés porteraient slug='' → violation d'unicité dès la
                # 2e. On sème donc un slug déterministe et unique par index.
                c = Company(nom=f'[{tag}] {faker.company()} {i}',
                            slug=slugify(f'{tag}-{i}'))
                new.append(c)
            Company.objects.bulk_create(new, batch_size=BATCH)
            companies = list(Company.objects.filter(nom__startswith=f'[{tag}]'))
        if not companies:
            raise CommandError('Aucune société cible.')
        company_ids = [c.pk for c in companies]
        self.stdout.write(f'Sociétés: {len(company_ids)}')

        pools: dict[str, list] = {'authentication.company': company_ids}

        def seed(label, count, *, extra=None, seeding=None):
            """Crée ``count`` lignes du modèle ``label`` en lots, FK résolues
            depuis ``pools`` (parents pré-remplis à la demande). Renvoie les pk
            créés (ajoutés au pool)."""
            seeding = seeding or set()
            if count <= 0:
                return pools.get(label, [])
            model = django_apps.get_model(label)
            fields = _concrete_required_fields(model)
            # Assure les pools des FK requises (récursif, borné).
            for f in fields:
                if not (getattr(f, 'many_to_one', False)
                        or getattr(f, 'one_to_one', False)):
                    continue
                tgt = f.related_model
                tlabel = f'{tgt._meta.app_label}.{tgt._meta.model_name}'
                if f.name == 'company' or tlabel == 'authentication.company':
                    continue
                if pools.get(tlabel):
                    continue
                if tlabel in seeding:
                    continue  # cycle : on laissera le repli
                seed(tlabel, min(count, 200),
                     seeding=seeding | {label})

            created_pks = []
            buf = []
            base_seq = len(pools.get(label, []))
            for i in range(count):
                seq = base_seq + i
                inst = model()
                for f in fields:
                    if getattr(f, 'many_to_one', False) or \
                            getattr(f, 'one_to_one', False):
                        tgt = f.related_model
                        tlabel = (f'{tgt._meta.app_label}.'
                                  f'{tgt._meta.model_name}')
                        if f.name == 'company' or \
                                tlabel == 'authentication.company':
                            setattr(inst, f.attname,
                                    random.choice(company_ids))
                            continue
                        pool = pools.get(tlabel)
                        if pool:
                            setattr(inst, f.attname, random.choice(pool))
                        else:
                            setattr(inst, f.attname, None)
                        continue
                    setattr(inst, f.attname, _fake_scalar(f, faker, seq))
                if extra:
                    extra(inst, seq)
                buf.append(inst)
                if len(buf) >= BATCH:
                    objs = model.objects.bulk_create(buf, batch_size=BATCH)
                    created_pks.extend(o.pk for o in objs if o.pk)
                    buf = []
            if buf:
                objs = model.objects.bulk_create(buf, batch_size=BATCH)
                created_pks.extend(o.pk for o in objs if o.pk)
            pools.setdefault(label, []).extend(created_pks)
            self.stdout.write(f'{label}: +{len(created_pks)}')
            return pools[label]

        # Utilisateurs : mot de passe partagé (hash unique calculé une fois).
        from django.contrib.auth.hashers import make_password
        shared_pw = make_password('seed-scale-not-secret')

        def user_extra(inst, seq):
            if hasattr(inst, 'username'):
                inst.username = f'{tag.lower()}_u{seq}'
            if hasattr(inst, 'password') and not getattr(inst, 'password', ''):
                inst.password = shared_pw
            if hasattr(inst, 'email'):
                inst.email = f'{tag.lower()}_u{seq}@example.test'

        User = django_apps.get_model(settings.AUTH_USER_MODEL)
        ulabel = f'{User._meta.app_label}.{User._meta.model_name}'
        seed(ulabel, options['users'], extra=user_extra)

        seed('crm.lead', options['leads'])
        seed('ventes.devis', options['devis'])
        # Lignes de devis : trouve le modèle enfant portant une FK vers Devis.
        ligne_label = self._find_child('ventes', 'devis', django_apps)
        if ligne_label:
            seed(ligne_label, options['lignes'])
        else:
            self.stdout.write(self.style.WARNING(
                'Modèle ligne de devis introuvable — lignes ignorées.'))
        seed('stock.mouvement', options['mouvements'])

        self.stdout.write(self.style.SUCCESS('seed_scale terminé.'))

    @staticmethod
    def _find_child(app_label, parent_model, django_apps):
        """Cherche un modèle de ``app_label`` avec une FK requise vers
        ``parent_model`` (ex. la ligne de devis)."""
        parent = f'{app_label}.{parent_model}'
        for model in django_apps.get_app_config(app_label).get_models():
            for f in model._meta.get_fields():
                if not (getattr(f, 'many_to_one', False)):
                    continue
                tgt = f.related_model
                tl = f'{tgt._meta.app_label}.{tgt._meta.model_name}'
                if tl == parent and not getattr(f, 'null', False):
                    return f'{model._meta.app_label}.{model._meta.model_name}'
        return None
