"""GED7 — Import idempotent des `records.Attachment` existants dans la GED.

Amène les pièces jointes éparses de `records.Attachment` dans le référentiel
gouverné de la GED en tant que `Document` (avec une `DocumentVersion` v1), SANS
recopier ni re-téléverser le fichier : on RÉUTILISE la même clé objet MinIO
(`file_key`). Là où la pièce jointe cible un objet métier autorisé
(`records.ALLOWED_TARGETS`), on crée le `DocumentLien` (GED6) correspondant pour
que le document apparaisse rattaché à cet objet.

Usage :

    python manage.py migrate_attachments_to_ged [--company <slug-ou-id>] [--dry-run]

Conception :

  * STRICTEMENT idempotent. La clé d'idempotence est ``(company, file_key)`` :
    une pièce jointe déjà importée (il existe déjà une `DocumentVersion` portant
    ce `file_key` dans cette société) est SAUTÉE — re-lancer la commande ne crée
    jamais de doublon. Le `DocumentLien` est lui aussi posé via `get_or_create`.

  * Multi-tenant. Chaque pièce jointe est importée dans SA société (jamais
    cross-société). Le cabinet/dossier d'accueil, le document, la version et le
    lien portent tous la société de la pièce jointe. ``--company`` borne le
    traitement à une seule société.

  * Additif. On NE supprime ni ne modifie JAMAIS la `Attachment` d'origine :
    l'objet MinIO et la ligne restent intacts ; la GED ne fait que pointer
    dessus.

  * DÉCISION — cabinet/dossier par défaut : un cabinet « Importé » et un dossier
    « Pièces jointes importées » sont auto-créés (idempotents) par société et
    servent de point d'atterrissage à toutes les pièces importées. Le mapping
    Attachment→Document est conservateur : nom = nom de fichier, description
    rappelant l'origine + la cible, auteur = `uploaded_by`.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from authentication.models import Company
# `records` est une app de fondation : import autorisé. On réutilise son registre
# de cibles autorisées pour décider quels rattachements donnent un DocumentLien.
from apps.records.models import ALLOWED_TARGETS, Attachment

from apps.ged.models import Cabinet, Document, DocumentLien, DocumentVersion, Folder

# DÉCISION — noms du cabinet/dossier d'atterrissage par défaut (par société).
DEFAULT_CABINET_NOM = 'Importé'
DEFAULT_FOLDER_NOM = 'Pièces jointes importées'


def _ensure_landing_folder(company):
    """Cabinet « Importé » + dossier « Pièces jointes importées » de la société.

    Idempotent : réutilise le cabinet/dossier s'ils existent déjà (clé = nom +
    société), sinon les crée. Le dossier est à la racine du cabinet.
    """
    cabinet, _ = Cabinet.objects.get_or_create(
        company=company, nom=DEFAULT_CABINET_NOM,
        defaults={'description': 'Documents importés depuis les pièces jointes.'})
    folder = (Folder.objects
              .filter(company=company, cabinet=cabinet,
                      parent__isnull=True, nom=DEFAULT_FOLDER_NOM)
              .first())
    if folder is None:
        folder = Folder.objects.create(
            company=company, cabinet=cabinet, parent=None, nom=DEFAULT_FOLDER_NOM)
    return folder


def import_attachments(company=None, dry_run=False):
    """Importe les pièces jointes (d'une société ou de toutes) dans la GED.

    Retourne un dict de compteurs : ``{'documents', 'liens', 'skipped'}``.
    Idempotent — une pièce jointe déjà importée (même `file_key` dans la même
    société) est comptée dans ``skipped`` et ne crée rien.
    """
    counters = {'documents': 0, 'liens': 0, 'skipped': 0}

    qs = Attachment.objects.select_related('content_type').all()
    if company is not None:
        qs = qs.filter(company=company)

    # Cache des dossiers d'atterrissage par société (évite de re-résoudre).
    landing_cache = {}

    for att in qs.iterator():
        att_company = att.company
        if att_company is None:
            # Pièce jointe sans société : pas de référentiel GED cible — on saute.
            counters['skipped'] += 1
            continue

        # Idempotence : déjà importée si une version porte ce file_key dans la
        # société. On ne recopie jamais le fichier — on réutilise la même clé.
        existing = (DocumentVersion.objects
                    .filter(company=att_company, file_key=att.file_key)
                    .first())
        if existing:
            # Le document existe déjà ; on s'assure tout de même que le lien vers
            # la cible est présent (idempotent), au cas où un import précédent
            # aurait été interrompu avant la pose du lien.
            if not dry_run and _ensure_lien(existing.document, att):
                counters['liens'] += 1
            counters['skipped'] += 1
            continue

        if dry_run:
            counters['documents'] += 1
            if _target_is_allowed(att):
                counters['liens'] += 1
            continue

        with transaction.atomic():
            cid = att_company.id
            if cid not in landing_cache:
                landing_cache[cid] = _ensure_landing_folder(att_company)
            folder = landing_cache[cid]

            document = Document.objects.create(
                company=att_company,
                folder=folder,
                nom=att.filename or att.file_key or f'Pièce jointe #{att.pk}',
                description=_origin_description(att),
                created_by=att.uploaded_by,
            )
            DocumentVersion.objects.create(
                company=att_company,
                document=document,
                version=1,
                # RÉUTILISE la clé MinIO d'origine — aucun fichier recopié.
                file_key=att.file_key,
                filename=att.filename or '',
                size=att.size or 0,
                mime=att.mime or '',
                uploaded_by=att.uploaded_by,
            )
            counters['documents'] += 1
            if _ensure_lien(document, att):
                counters['liens'] += 1

    return counters


def _target_is_allowed(att):
    """La cible de la pièce jointe est-elle dans `records.ALLOWED_TARGETS` ?"""
    ct = att.content_type
    return (ct.app_label, ct.model) in ALLOWED_TARGETS


def _ensure_lien(document, att):
    """Crée (idempotent) le DocumentLien vers la cible de la pièce jointe.

    Ne crée un lien que si la cible est un type autorisé ET existe encore. La
    société du lien est celle du document (jamais cross-société). Retourne True
    si un lien a été créé, False sinon (déjà présent / cible non autorisée).
    """
    if not _target_is_allowed(att):
        return False
    ct = att.content_type
    # La cible doit exister encore (une pièce jointe peut survivre à son objet).
    if not ct.model_class().objects.filter(pk=att.object_id).exists():
        return False
    _lien, created = DocumentLien.objects.get_or_create(
        document=document,
        content_type=ct,
        object_id=att.object_id,
        defaults={'company': document.company, 'created_by': att.uploaded_by},
    )
    return created


def _origin_description(att):
    """Description conservatrice rappelant l'origine + la cible de la pièce."""
    ct = att.content_type
    return (f'Importé depuis une pièce jointe (records.Attachment #{att.pk}, '
            f'cible {ct.app_label}.{ct.model}:{att.object_id}).')


def _resolve_company(value):
    """Résout une société par slug ou id ; lève CommandError si introuvable."""
    company = Company.objects.filter(slug=value).first()
    if company is None and str(value).isdigit():
        company = Company.objects.filter(pk=value).first()
    if company is None:
        raise CommandError(f'Société introuvable : {value!r}.')
    return company


class Command(BaseCommand):
    help = ('GED7 — Importe les records.Attachment existants dans la GED en '
            'réutilisant leur file_key MinIO (idempotent, additif).')

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', dest='company', default=None,
            help='Limite l\'import à une société (slug ou id).')
        parser.add_argument(
            '--dry-run', action='store_true', dest='dry_run',
            help='Compte ce qui serait importé sans rien écrire.')

    def handle(self, *args, **options):
        company = None
        if options.get('company'):
            company = _resolve_company(options['company'])

        counters = import_attachments(company=company, dry_run=options['dry_run'])

        prefix = '[dry-run] ' if options['dry_run'] else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Documents importés : {counters["documents"]} ; '
            f'liens créés : {counters["liens"]} ; '
            f'ignorés (déjà importés / sans société) : {counters["skipped"]}.'))
