"""Publie les documents internes de Meryem dans la GED, versionnés.

FOUNDER REQUEST (07/09/2026) : le Guide de Meryem, le Protocole de rappel
(FR + darija) et la carte one-page doivent vivre DANS la GED (jamais un
fichier à part), versionnés, visibles de Meryem, avec une notification ERP
envoyée à Meryem ET au fondateur à chaque nouvelle version — automatiquement,
au déploiement, sans jamais un geste manuel du fondateur.

Source des fichiers : ``docs/meryem/manifest.json`` (une LISTE d'entrées
``{fichier, titre, version, description}``) + les PDF eux-mêmes, tous à côté
du manifeste (``MERYEM_DOCS_DIR``, voir plus bas). ``version``/``description``
viennent du manifeste ; c'est le SHA-256 du contenu du fichier qui décide si
une NOUVELLE VERSION doit être créée — jamais l'étiquette de version, qui
n'est qu'informative.

Idempotent :
  * Cabinet « Documents internes » -> Dossier « Commercial » -> Dossier
    « Guides de Meryem », créés une seule fois (réutilise
    ``services.ensure_cabinet``/``ensure_root_folder`` pour les deux premiers
    niveaux — mêmes helpers que ``migrate_attachments_to_ged`` — puis un
    troisième niveau posé avec le même patron filter+create, jamais
    ``get_or_create`` : ``Folder`` ne porte aucune contrainte unique sur
    (company, cabinet, parent, nom)) ;
  * le fichier est stocké via ``apps.records.storage.store_attachment``
    (EXACTEMENT le même pipeline MinIO que ``televerser``/
    ``deposer_photos_assemblees`` — jamais un second chemin de stockage),
    avec ``company=`` posé (SCA42 : clé préfixée par société) ;
  * ACL de lecture (``AclGed``, ``herite=True``) posée une fois sur le dossier
    « Guides de Meryem » pour chaque rôle de la société dont le palier hérité
    n'est PAS admin (Commercial, Commercial responsable, Technicien…) — les
    rôles admin (Directeur/Administrateur) n'ont besoin d'aucune entrée : ils
    ont déjà l'accès implicite ``is_admin_role`` dans
    ``selectors.acl_effective`` (garde de gestion totale AVANT toute ACL) ;
  * un ``Document`` par entrée de manifeste, retrouvé par ``titre`` dans le
    dossier (créé si absent, avec sa description) ;
  * une nouvelle ``DocumentVersion`` seulement si le SHA-256 du fichier
    diffère de la dernière version connue du document (ou ``--force``) —
    sinon rien n'est écrit pour cette entrée.

Notifie (une fois par destinataire ET par NOUVELLE version, jamais en
répétition sur un contenu inchangé sauf ``--force``) :
  * le responsable par défaut des leads de la société
    (``CompanyProfile.responsable_defaut_leads``, actif) ;
  * tout utilisateur actif « admin ou directeur » de la société — réutilise
    ``CustomUser.admins_actifs_qs`` (couvre le Role fin portant
    ``roles_gerer`` — Directeur ET Administrateur —, le legacy
    ``role_legacy='admin'``, et le superuser), dédupliqué avec le
    responsable des leads.

Aucun type d'événement dédié « document publié » n'existe dans
``apps.notifications.models.EventType`` (registre fermé — CLAUDE.md : on
n'invente jamais un événement à la volée). Le plus proche est
``EventType.ANNONCE_PUBLISHED`` (« Nouvelle annonce interne »), déjà utilisé
pour EXACTEMENT ce type de diffusion (contenu interne publié à l'équipe,
titre/corps/lien entièrement libres côté appelant — voir
``apps.notifications.services.publish_annonce``) ; c'est celui-ci qui est
réutilisé ici plutôt qu'inventer une nouvelle clé.

``link`` pointe vers ``/ged`` : la page GED (``GedNavigator``, montée sur
l'unique route ``/ged``) ne lit AUCUN paramètre d'URL pour pré-ouvrir un
document ou même un dossier précis (sélection 100% en état React interne) —
il n'existe donc PAS de lien profond réel vers ce document aujourd'hui.

Usage :
    python manage.py publier_documents_meryem [--company <slug-ou-id>]
        [--dry-run] [--force]

``--company`` est optionnel UNIQUEMENT si une seule société existe en base
(sinon obligatoire — ``CommandError``). ``--dry-run`` n'écrit RIEN et imprime
ce qui serait fait. ``--force`` republie même si le contenu est inchangé (et
renotifie). Best-effort PAR ENTRÉE de manifeste : une erreur sur un fichier
n'empêche jamais le traitement des autres ; le code de sortie du PROCESSUS
est 1 si au moins une entrée a échoué (``SystemExit(1)`` après le résumé —
même patron que ``update_pdf_baselines``/``meta_webhook_status``). Une
erreur STRUCTURELLE (société ambiguë, manifeste absent/invalide) lève
``CommandError`` avant tout traitement — jamais du best-effort sur du vide.
"""
import json
import os
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError

from authentication.models import Company, CustomUser
from authentication.role_tiers import ROLE_ADMIN, tier_for_role_fields

from apps.ged import services
from apps.ged.models import ACL_LECTURE, AclGed, Document, Folder
from apps.notifications.models import EventType
from apps.notifications.services import notify_many
from apps.parametres.models_company import CompanyProfile
from apps.records.storage import store_attachment
from apps.roles.models import Role

CABINET_NOM = 'Documents internes'
DOSSIER_RACINE_NOM = 'Commercial'
DOSSIER_MERYEM_NOM = 'Guides de Meryem'
MANIFEST_NOM = 'manifest.json'


def _default_docs_dir():
    """Racine du dépôt (``docs/meryem/``) déduite de ``settings.BASE_DIR``.

    ``BASE_DIR`` = ``backend/django_core`` (voir ``erp_agentique/settings/
    base.py``) ; deux niveaux plus haut = la racine du dépôt, qui porte
    ``docs/``. Même idiome que les tests qui remontent au dépôt depuis
    ``backend/django_core/...`` (ex. ``apps/ventes/tests/
    test_qx50_injection_82_21.py``)."""
    return Path(settings.BASE_DIR).resolve().parents[1] / 'docs' / 'meryem'


# Surchageable via l'environnement : en conteneur Docker, ``docs/`` n'est PAS
# monté dans ``/app`` (seuls ``backend/django_core`` et ``STAGES.py`` le sont,
# voir docker-compose.yml) — ``MERYEM_DOCS_DIR`` pointe alors vers le bind
# mount dédié en lecture seule ajouté pour cette fonctionnalité. Hors Docker
# (dépôt complet en clair), le repli calculé ci-dessus suffit.
MERYEM_DOCS_DIR = (
    Path(os.environ['MERYEM_DOCS_DIR']) if os.environ.get('MERYEM_DOCS_DIR')
    else _default_docs_dir())


def _resolve_company(value):
    """Résout une société par slug ou id ; lève CommandError si introuvable.

    Même patron que ``migrate_attachments_to_ged._resolve_company``."""
    company = Company.objects.filter(slug=value).first()
    if company is None and str(value).isdigit():
        company = Company.objects.filter(pk=value).first()
    if company is None:
        raise CommandError(f'Société introuvable : {value!r}.')
    return company


def _resolve_default_company():
    """La société UNIQUE de la base, sinon lève CommandError (0 ou 2+)."""
    total = Company.objects.count()
    if total == 1:
        return Company.objects.first()
    if total == 0:
        raise CommandError('Aucune société en base : --company est requis.')
    raise CommandError(
        f'{total} sociétés en base : --company <slug-ou-id> est requis.')


def _find_dossier_meryem(company):
    """Dossier « Guides de Meryem » de la société, ou None s'il n'existe pas
    encore (lecture seule — sert au dry-run comme au run réel)."""
    return Folder.objects.filter(
        company=company, cabinet__nom=CABINET_NOM, nom=DOSSIER_MERYEM_NOM,
        parent__nom=DOSSIER_RACINE_NOM, parent__parent__isnull=True,
    ).first()


def _ensure_dossier_meryem(company):
    """Cabinet « Documents internes » -> Commercial -> Guides de Meryem.

    Réutilise les helpers idempotents existants pour le cabinet et le premier
    niveau (``services.ensure_cabinet``/``ensure_root_folder``) ; le second
    niveau (non-racine) suit le même patron filter+create que
    ``migrate_attachments_to_ged._ensure_landing_folder``."""
    cabinet = services.ensure_cabinet(company, CABINET_NOM)
    racine = services.ensure_root_folder(
        company, cabinet=cabinet, nom=DOSSIER_RACINE_NOM)
    dossier = Folder.objects.filter(
        company=company, cabinet=cabinet, parent=racine,
        nom=DOSSIER_MERYEM_NOM).first()
    if dossier is None:
        dossier = Folder.objects.create(
            company=company, cabinet=cabinet, parent=racine,
            nom=DOSSIER_MERYEM_NOM)
    return dossier


def _non_admin_roles(company):
    """Rôles de la société dont le palier hérité N'EST PAS admin.

    Les rôles admin (Directeur/Administrateur — ``roles_gerer``) n'ont besoin
    d'AUCUNE entrée ACL : ``selectors.acl_effective`` leur accorde déjà
    « gestion » de façon inconditionnelle via ``is_admin_role``, avant même
    de consulter l'ACL. Le reste (Commercial, Commercial responsable,
    Technicien, rôles personnalisés…) est le public visé par « les rôles
    qu'un commercial peut porter »."""
    roles = []
    for role in Role.objects.filter(company=company):
        tier = tier_for_role_fields(
            role.nom, role.est_systeme, role.permissions or [])
        if tier != ROLE_ADMIN:
            roles.append(role)
    return roles


def _ensure_acl_lecture(dossier, company):
    """Pose (idempotent) une ACL de lecture héritée sur ``dossier`` pour
    chaque rôle non-admin de la société. Filter+create (jamais
    ``get_or_create`` : ``AclGed`` ne porte aucune contrainte unique sur
    (folder, role)). Renvoie le nombre d'entrées CRÉÉES par cet appel."""
    created = 0
    for role in _non_admin_roles(company):
        exists = AclGed.objects.filter(
            folder=dossier, document__isnull=True, role=role).exists()
        if not exists:
            AclGed.objects.create(
                company=company, folder=dossier, role=role,
                niveau=ACL_LECTURE, herite=True)
            created += 1
    return created


def _load_manifest():
    """Charge ``MERYEM_DOCS_DIR/manifest.json`` (liste d'entrées). Lève
    ``CommandError`` si absent/illisible/mal formé — une erreur STRUCTURELLE,
    jamais du best-effort par entrée (il n'y a alors rien à itérer)."""
    manifest_path = MERYEM_DOCS_DIR / MANIFEST_NOM
    if not manifest_path.is_file():
        raise CommandError(f'Manifeste introuvable : {manifest_path}.')
    try:
        data = json.loads(manifest_path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise CommandError(
            f'Manifeste illisible ({manifest_path}) : {exc}') from exc
    if not isinstance(data, list):
        raise CommandError(
            f'Manifeste invalide (liste attendue) : {manifest_path}.')
    return data


def _notification_recipients(company):
    """Responsable des leads (actif) + admins/directeurs actifs, dédupliqués
    dans cet ordre (le responsable en tête)."""
    recipients = []
    profile = (CompanyProfile.objects
               .filter(company=company)
               .select_related('responsable_defaut_leads')
               .first())
    responsable = profile.responsable_defaut_leads if profile else None
    if responsable is not None and responsable.is_active:
        recipients.append(responsable)
    recipients += list(CustomUser.admins_actifs_qs(company))
    vus, dedup = set(), []
    for user in recipients:
        if user.pk not in vus:
            vus.add(user.pk)
            dedup.append(user)
    return dedup


def publier_documents(company, *, dry_run=False, force=False, stdout=None):
    """Publie chaque entrée du manifeste dans la GED pour ``company``.

    Renvoie ``(counters, erreurs)`` : ``counters`` est un dict
    ``{'documents_crees', 'nouvelles_versions', 'inchanges', 'echecs'}`` ;
    ``erreurs`` la liste des messages d'échec PAR ENTRÉE (best-effort — une
    entrée en échec n'empêche jamais les autres)."""
    def _log(msg):
        if stdout is not None:
            stdout.write(msg)

    counters = {
        'documents_crees': 0, 'nouvelles_versions': 0,
        'inchanges': 0, 'echecs': 0,
    }
    erreurs = []

    manifest = _load_manifest()
    if not manifest:
        _log('Manifeste vide — rien à publier.')
        return counters, erreurs

    dossier = None
    recipients = []
    if dry_run:
        dossier = _find_dossier_meryem(company)
    else:
        dossier = _ensure_dossier_meryem(company)
        acl_crees = _ensure_acl_lecture(dossier, company)
        if acl_crees:
            _log(f'ACL de lecture posée sur {acl_crees} rôle(s).')
        recipients = _notification_recipients(company)

    for entry in manifest:
        fichier = (entry or {}).get('fichier') or ''
        titre = ((entry or {}).get('titre') or '').strip()
        version_label = (entry or {}).get('version') or ''
        description = (entry or {}).get('description') or ''
        try:
            if not fichier or not titre:
                raise ValueError(
                    'entrée de manifeste incomplète (fichier/titre requis).')
            chemin = MERYEM_DOCS_DIR / fichier
            if not chemin.is_file():
                raise ValueError(f'fichier introuvable : {chemin}.')
            contenu = chemin.read_bytes()
            checksum = services.compute_checksum(contenu)

            document = (Document.objects.filter(
                company=company, folder=dossier, nom=titre).first()
                if dossier else None)
            derniere = document.versions.first() if document else None

            if dry_run:
                if document is None:
                    _log(f'[dry-run] {titre} : nouveau document + version 1.')
                elif force or derniere is None or derniere.checksum != checksum:
                    _log(f'[dry-run] {titre} : nouvelle version.')
                else:
                    _log(f'[dry-run] {titre} : déjà à jour, rien à faire.')
                continue

            if document is None:
                document = Document.objects.create(
                    company=company, folder=dossier, nom=titre,
                    description=description)
                counters['documents_crees'] += 1
                derniere = None

            if derniere is not None and derniere.checksum == checksum \
                    and not force:
                counters['inchanges'] += 1
                continue

            upload = SimpleUploadedFile(
                fichier, contenu, content_type='application/pdf')
            meta, err = store_attachment(upload, company=company)
            if err:
                raise ValueError(err)
            services.add_version(
                document, file_key=meta['file_key'], company=company,
                filename=meta['filename'], size=meta['size'],
                mime=meta['mime'], checksum=checksum)
            counters['nouvelles_versions'] += 1
            _log(f'{titre} : nouvelle version publiée (v{version_label}).')

            if recipients:
                titre_notif = f'Nouveau document : {titre} v{version_label}'
                corps = (
                    f'{description}\n\nOuvrir dans la GED.' if description
                    else 'Ouvrir dans la GED.')
                notify_many(
                    recipients, EventType.ANNONCE_PUBLISHED, titre_notif,
                    body=corps, link='/ged', company=company)
        except Exception as exc:  # noqa: BLE001 — best-effort par entrée
            counters['echecs'] += 1
            message = f'{fichier or titre or "?"} : {exc}'
            erreurs.append(message)
            _log(f'ÉCHEC — {message}')

    return counters, erreurs


class Command(BaseCommand):
    help = ('Publie le Guide de Meryem, le Protocole de rappel et la carte '
            'one-page dans la GED (versionné, ACL de lecture, notification '
            'à chaque nouvelle version).')

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', dest='company', default=None,
            help='Société cible (slug ou id). Requis sauf société unique.')
        parser.add_argument(
            '--dry-run', action='store_true', dest='dry_run',
            help="N'écrit rien ; imprime ce qui serait fait.")
        parser.add_argument(
            '--force', action='store_true', dest='force',
            help='Republie (nouvelle version + notification) même si le '
                 'contenu est inchangé.')

    def handle(self, *args, **options):
        if options.get('company'):
            company = _resolve_company(options['company'])
        else:
            company = _resolve_default_company()

        counters, erreurs = publier_documents(
            company, dry_run=options['dry_run'], force=options['force'],
            stdout=self.stdout)

        prefix = '[dry-run] ' if options['dry_run'] else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Documents créés : {counters["documents_crees"]} ; '
            f'nouvelles versions : {counters["nouvelles_versions"]} ; '
            f'déjà à jour : {counters["inchanges"]} ; '
            f'échecs : {counters["echecs"]}.'))
        if erreurs:
            for msg in erreurs:
                self.stderr.write(self.style.WARNING(msg))
            raise SystemExit(1)
