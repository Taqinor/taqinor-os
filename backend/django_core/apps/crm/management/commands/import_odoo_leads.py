"""Importateur de leads Odoo — commande de gestion idempotente (N107).

Importe un export de `crm.lead` Odoo (CSV ou JSON) dans le modèle `crm.Lead`
de TAQINOR, de façon STRICTEMENT idempotente : re-lancer la commande sur le même
fichier ne crée jamais de doublon et n'écrase jamais de donnée déjà saisie.

  python manage.py import_odoo_leads <chemin> --company <slug-ou-id> [--dry-run]

Conception (réutilise le cadre d'import T9 `apps.dataimport.services` et les
aides de rapprochement `apps.crm.services`) :

  * Société FORCÉE côté serveur depuis `--company` — jamais lue dans le fichier
    (règle multi-tenant CLAUDE.md). La société est obligatoire.
  * Rapprochement idempotent en trois temps, dans cet ordre :
      1. (external_system='odoo', external_id=<id Odoo>) — clé technique stable,
         garantie par la contrainte d'unicité `uniq_lead_external_ref` ;
      2. email normalisé (insensible à la casse) ;
      3. téléphone normalisé (`services.normalize_phone`).
    Si une fiche existe déjà → MISE À JOUR des seuls champs vides (« on garde la
    valeur la plus complète », jamais d'écrasement). Sinon → CRÉATION.
  * Étapes : noms canoniques chargés depuis STAGES.py (`apps.crm.stages`) ; une
    étape Odoo non reconnue retombe sur NEW. Jamais de nom d'étape codé en dur.
  * Sans fichier (ou fichier introuvable) → la commande ne fait RIEN : message
    d'usage et sortie propre, aucune ligne créée.

L'extraction réelle des 619 leads reste manuelle et gatée sur la vraie
sauvegarde Odoo (fichier PII, jamais committé). Cette commande ne fait rien tant
qu'on ne lui passe pas un fichier d'export.
"""
import json
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.crm import services, stages
from apps.crm.models import Lead
from apps.dataimport.services import parse_rows, _norm

EXTERNAL_SYSTEM = 'odoo'

# Mapping en-tête Odoo (normalisé via dataimport._norm) → champ du modèle Lead.
# On accepte les noms techniques Odoo et leurs étiquettes françaises courantes.
ODOO_FIELD_MAP = {
    # identité / contact
    'name': 'nom', 'contact_name': 'nom', 'nom': 'nom',
    'partner_name': 'societe', 'societe': 'societe', 'company_name': 'societe',
    'email_from': 'email', 'email': 'email',
    'phone': 'telephone', 'telephone': 'telephone', 'tel': 'telephone',
    'mobile': 'whatsapp', 'whatsapp': 'whatsapp',
    'street': 'adresse', 'adresse': 'adresse', 'address': 'adresse',
    'city': 'ville', 'ville': 'ville',
    # pipeline / commercial
    'description': 'note', 'note': 'note', 'notes': 'note',
}

# Identifiant Odoo de la ligne — sert de clé technique de rapprochement.
ODOO_ID_KEYS = ('id', 'lead_id', 'external_id', 'odoo_id')

# Étape (stage) Odoo → clé canonique STAGES.py. Tout intitulé non listé retombe
# sur NEW (jamais d'invention/renommage d'étape — CLAUDE.md règle #2).
_ODOO_STAGE_TO_KEY = {
    'new': 'NEW', 'nouveau': 'NEW', 'nouveau lead': 'NEW',
    'contacted': 'CONTACTED', 'contacte': 'CONTACTED', 'qualified': 'CONTACTED',
    'qualifie': 'CONTACTED',
    'proposition': 'QUOTE_SENT', 'devis envoye': 'QUOTE_SENT',
    'quote sent': 'QUOTE_SENT', 'proposition envoyee': 'QUOTE_SENT',
    'relance': 'FOLLOW_UP', 'follow up': 'FOLLOW_UP', 'negociation': 'FOLLOW_UP',
    'won': 'SIGNED', 'gagne': 'SIGNED', 'signe': 'SIGNED', 'signed': 'SIGNED',
    'cold': 'COLD', 'froid': 'COLD', 'perdu': 'COLD', 'lost': 'COLD',
}

# Champs du Lead recopiés depuis l'export quand la fiche existante les a vides
# (jamais d'écrasement d'une saisie déjà présente).
_FILL_FIELDS = ('prenom', 'societe', 'email', 'telephone', 'whatsapp',
                'adresse', 'ville', 'note')


def _map_stage(raw):
    """Étape Odoo (chaîne libre) → clé canonique STAGES.py, défaut NEW."""
    key = _norm(raw).replace('_', ' ').strip()
    return _ODOO_STAGE_TO_KEY.get(key, stages.NEW)


def _read_export(path):
    """Lit le fichier d'export et renvoie une liste de dict (lignes brutes).

    Accepte JSON (liste d'objets, ou objet enveloppant {"leads"|"records": [...]})
    et CSV/XLSX (via le parseur T9 partagé).
    """
    name = path.lower()
    if name.endswith('.json'):
        with open(path, 'rb') as fh:
            payload = json.loads(fh.read().decode('utf-8-sig'))
        if isinstance(payload, dict):
            for key in ('leads', 'records', 'data', 'rows'):
                if isinstance(payload.get(key), list):
                    return payload[key]
            return [payload]
        if isinstance(payload, list):
            return payload
        raise CommandError("JSON inattendu : liste ou objet {leads:[...]} attendu.")
    # CSV / XLSX — réutilise le parseur du cadre d'import T9.
    with open(path, 'rb') as fh:
        _headers, rows = parse_rows(fh.read(), path)
    return rows


def _row_to_fields(row):
    """Projette une ligne d'export brute vers les champs du modèle Lead.

    Renvoie (fields, external_id, stage_key). Les valeurs vides sont omises.
    """
    fields = {}
    for raw_key, value in row.items():
        field = ODOO_FIELD_MAP.get(_norm(raw_key))
        if not field:
            continue
        if value in (None, ''):
            continue
        text = str(value).strip()
        if not text:
            continue
        # Première valeur gagne (les en-têtes Odoo natifs précèdent les alias).
        fields.setdefault(field, text)

    external_id = None
    for key in ODOO_ID_KEYS:
        for raw_key, value in row.items():
            if _norm(raw_key) == key and value not in (None, ''):
                external_id = str(value).strip()
                break
        if external_id:
            break

    stage_raw = None
    for raw_key, value in row.items():
        if _norm(raw_key) in ('stage', 'stage_id', 'etape', 'stage_name'):
            stage_raw = value
            break
    stage_key = _map_stage(stage_raw)
    return fields, external_id, stage_key


def _find_existing(company, external_id, fields):
    """Trouve un lead existant pour rapprochement idempotent (jamais de doublon).

    Ordre : clé technique Odoo, puis email normalisé, puis téléphone normalisé.
    Tout est borné à la société.
    """
    if external_id:
        match = Lead.objects.filter(
            company=company, external_system=EXTERNAL_SYSTEM,
            external_id=external_id).first()
        if match:
            return match
    email = services.normalize_email(fields.get('email'))
    if email:
        match = Lead.objects.filter(
            company=company, email__iexact=email).first()
        if match:
            return match
    phone = services.normalize_phone(fields.get('telephone'))
    if phone:
        for other in Lead.objects.filter(company=company).exclude(
                telephone__isnull=True).exclude(telephone=''):
            if services.normalize_phone(other.telephone) == phone:
                return other
    return None


def _fill_empty(lead, fields):
    """Complète les champs VIDES du lead existant. Renvoie True si modifié."""
    changed = []
    for field in _FILL_FIELDS:
        if field not in fields:
            continue
        current = getattr(lead, field, None)
        if current in (None, '', False):
            setattr(lead, field, fields[field])
            changed.append(field)
    if changed:
        lead.save(update_fields=changed)
    return bool(changed)


class Command(BaseCommand):
    help = ("Importe un export de leads Odoo (crm.lead, CSV ou JSON) de façon "
            "idempotente. Société forcée côté serveur via --company.")

    def add_arguments(self, parser):
        parser.add_argument(
            'path', nargs='?', default=None,
            help="Chemin du fichier d'export Odoo (CSV ou JSON).")
        parser.add_argument(
            '--company', dest='company', default=None,
            help="Slug ou id de la société cible (obligatoire pour importer).")
        parser.add_argument(
            '--dry-run', action='store_true',
            help="N'écrit rien : compte seulement créations / mises à jour.")

    def _resolve_company(self, raw):
        from authentication.models import Company
        if raw is None:
            return None
        company = Company.objects.filter(slug=raw).first()
        if company is None and str(raw).isdigit():
            company = Company.objects.filter(pk=int(raw)).first()
        return company

    def handle(self, *args, **options):
        path = options.get('path')
        dry_run = options.get('dry_run')

        # Sans fichier → ne RIEN faire : usage + sortie propre, aucune création.
        if not path:
            self.stdout.write(self.style.WARNING(
                "Aucun fichier fourni — rien à importer.\n"
                "Usage : manage.py import_odoo_leads <chemin> "
                "--company <slug-ou-id> [--dry-run]"))
            return
        if not os.path.isfile(path):
            self.stdout.write(self.style.WARNING(
                f"Fichier introuvable : {path} — rien à importer."))
            return

        company = self._resolve_company(options.get('company'))
        if company is None:
            raise CommandError(
                "--company <slug-ou-id> est obligatoire et doit correspondre à "
                "une société existante. La société est forcée côté serveur.")

        rows = _read_export(path)
        created = updated = unchanged = skipped = 0

        # Atomique : un export ne s'applique qu'en entier (rollback en dry-run).
        with transaction.atomic():
            for row in rows:
                fields, external_id, stage_key = _row_to_fields(row)
                if not (fields.get('nom') or fields.get('email')
                        or fields.get('telephone')):
                    skipped += 1
                    continue

                existing = _find_existing(company, external_id, fields)
                if existing is not None:
                    # Pose la clé technique si absente (rapproché par email/tel).
                    tech_changed = False
                    if external_id and not existing.external_id:
                        existing.external_system = EXTERNAL_SYSTEM
                        existing.external_id = external_id
                        if not dry_run:
                            existing.save(update_fields=[
                                'external_system', 'external_id'])
                        tech_changed = True
                    filled = _fill_empty(existing, fields) if not dry_run \
                        else any(
                            f in fields and getattr(existing, f, None)
                            in (None, '', False) for f in _FILL_FIELDS)
                    if filled or tech_changed:
                        updated += 1
                    else:
                        unchanged += 1
                    continue

                # Création — société FORCÉE, marquée import test Odoo.
                if not dry_run:
                    Lead.objects.create(
                        company=company,
                        nom=fields.get('nom') or (fields.get('societe')
                                                  or fields.get('email')
                                                  or 'Lead Odoo'),
                        prenom=fields.get('prenom'),
                        societe=fields.get('societe'),
                        email=fields.get('email'),
                        telephone=(fields.get('telephone') or '')[:50] or None,
                        whatsapp=(fields.get('whatsapp') or '')[:50] or None,
                        adresse=fields.get('adresse'),
                        ville=(fields.get('ville') or '')[:120] or None,
                        note=fields.get('note'),
                        stage=stage_key,
                        source=Lead.Source.ODOO_IMPORT_TEST,
                        external_system=EXTERNAL_SYSTEM if external_id else None,
                        external_id=external_id,
                    )
                created += 1

            if dry_run:
                transaction.set_rollback(True)

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}Import Odoo terminé pour « {company.nom} » : "
            f"{created} créé(s), {updated} mis à jour, "
            f"{unchanged} inchangé(s), {skipped} ignoré(s) sur "
            f"{len(rows)} ligne(s)."))
