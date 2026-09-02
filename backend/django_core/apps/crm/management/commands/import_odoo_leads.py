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
# Source UNIQUE des règles d'assainissement Odoo (chemin JSON-2) — jamais une
# seconde règle écrite ici (CRX9/CRX10).
from apps.crm.odoo_sync import (
    _clean_phone, email_reel, est_reponse_formulaire, societe_reelle)
from apps.dataimport.services import parse_rows, _norm

EXTERNAL_SYSTEM = 'odoo'

# Plafonds d'affichage des rapports détaillés (les totaux restent complets).
_MAX_CORBEILLE_AFFICHEE = 20
_MAX_AMBIGUS_AFFICHES = 20

# Mapping en-tête Odoo (normalisé via dataimport._norm) → champ du modèle Lead.
# On accepte les noms techniques Odoo et leurs étiquettes françaises courantes.
ODOO_FIELD_MAP = {
    # identité / contact
    'name': 'nom', 'contact_name': 'nom', 'nom': 'nom',
    # CRX35 — `prenom` était LU à la création et dans `_FILL_FIELDS` alors
    # qu'AUCUNE en-tête ne le produisait : la lecture était morte et le prénom
    # d'un fichier d'export restait systématiquement vide. Odoo `crm.lead`
    # n'a pas de champ prénom (il n'a que `contact_name`, le nom complet) —
    # ces alias servent donc le chemin FICHIER, où l'en-tête existe vraiment.
    'prenom': 'prenom', 'first_name': 'prenom', 'firstname': 'prenom',
    'partner_name': 'societe', 'societe': 'societe', 'company_name': 'societe',
    'email_from': 'email', 'email': 'email',
    'phone': 'telephone', 'telephone': 'telephone', 'tel': 'telephone',
    # CRX35 — PIÈGE : `mobile` est un NUMÉRO DE TÉLÉPHONE côté Odoo, pas un
    # identifiant WhatsApp. Le garder ici est correct (c'est le numéro que
    # wa.me utilise), mais un lead Odoo qui ne portait QUE `mobile` arrivait
    # avec `telephone` VIDE : `phone_normalise` restait vide et toute la dédup
    # indexée (QW10) était aveugle sur lui. Le repli est posé à la création.
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
    # Étapes RÉELLES du pipeline Odoo du fondateur (relevées le
    # 2026-09-01 ; mapping 18→6 validé par le fondateur le même jour).
    # Clés sous forme _norm() puis underscores→espaces, comme _map_stage.
    '2eme appel+ message whatsapp': 'CONTACTED',
    'dernier appel+note odoo': 'CONTACTED',
    'lead qualified': 'CONTACTED',
    'waiting for consumption bills': 'CONTACTED',
    'prilimanary quote sent': 'QUOTE_SENT',
    'final quote sent': 'QUOTE_SENT',
    'quote discussed': 'FOLLOW_UP',
    'site visite scheduled': 'FOLLOW_UP',
    'negotiation / objection': 'FOLLOW_UP',
    'verbal agreement': 'FOLLOW_UP',
    'derniere chance': 'FOLLOW_UP',
    'no answer to post quote call': 'FOLLOW_UP',
    'contract signed + deposit': 'SIGNED',
    'cold lead': 'COLD',
    'not convinced no quote': 'COLD',
    'devis cold': 'COLD',
}

# Champs du Lead recopiés depuis l'export quand la fiche existante les a vides
# (jamais d'écrasement d'une saisie déjà présente).
_FILL_FIELDS = ('prenom', 'societe', 'email', 'telephone', 'whatsapp',
                'adresse', 'ville', 'note')

# Colonnes DÉRIVÉES recalculées par ``Lead.save()`` et qui doivent donc
# accompagner leur source dans ``update_fields`` (QW10 — colonnes indexées de
# dédup ; sans elles la valeur recalculée en mémoire n'est jamais persistée).
_COLONNES_DERIVEES = {
    'telephone': 'phone_normalise',
    'email': 'email_normalise',
}


def _map_stage_connu(raw):
    """Étape Odoo (chaîne libre) → clé canonique STAGES.py, ou ``None`` quand
    l'intitulé est vide ou absent de la table.

    CRX8/D-CRX3 — le repli sur ``stages.NEW`` (``_map_stage``) ne vaut QUE
    pour la CRÉATION d'un lead. ALIGNER une fiche existante sur un intitulé
    Odoo non reconnu la ramènerait à « Nouveau » : une étape Odoo inconnue
    laisse le lead INTOUCHÉ.
    """
    key = _norm(raw).replace('_', ' ').strip()
    if not key:
        return None
    return _ODOO_STAGE_TO_KEY.get(key)


def _map_stage(raw):
    """Étape Odoo (chaîne libre) → clé canonique STAGES.py, défaut NEW.

    Le défaut NEW est réservé à la CRÉATION — pour l'alignement d'une fiche
    existante, utiliser ``_map_stage_connu`` (qui renvoie ``None``).
    """
    return _map_stage_connu(raw) or stages.NEW


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

    # CRX9 — parité avec le chemin JSON-2 (``odoo_sync._clean_phone``) : un
    # téléphone aberrant (aucun chiffre, plus de 20 chiffres, ou plus de 50
    # caractères) ne peut PAS entrer en base — ``Lead.telephone`` est
    # varchar(50) et sa colonne dérivée ``phone_normalise`` varchar(20) :
    # l'insert CASSE, et le dry-run ne le voit pas. Il part en NOTE, comme le
    # fait déjà l'export JSON-2 (« Téléphone Odoo invalide: … »).
    traces = []
    for champ, libelle in (('telephone', 'Téléphone'), ('whatsapp', 'WhatsApp')):
        if champ not in fields:
            continue
        valeur, invalide = _clean_phone(fields[champ])
        if invalide is not None:
            traces.append(f'{libelle} Odoo invalide: {invalide}')
        if valeur is None:
            fields.pop(champ)
        else:
            fields[champ] = valeur

    # CRX10 — les MÊMES règles d'assainissement que le chemin JSON-2
    # (``odoo_sync``), appliquées ici : un export FICHIER des mêmes leads
    # Odoo entrait sale — email bouche-trou Meta (qui fusionne 243 leads sur
    # une fiche au rapprochement), « Facebook Lead » en raison sociale, et
    # les réponses du formulaire Meta rangées dans l'adresse postale.
    if 'email' in fields:
        email = email_reel(fields['email'])
        if email is None:
            fields.pop('email')
        else:
            fields['email'] = email
    if 'societe' in fields:
        societe = societe_reelle(fields['societe'])
        if societe is None:
            fields.pop('societe')
        else:
            fields['societe'] = societe
    if 'adresse' in fields and est_reponse_formulaire(fields['adresse']):
        traces.append('Formulaire Meta: ' + fields.pop('adresse'))

    if traces:
        fields['note'] = '\n'.join(
            ([fields['note']] if fields.get('note') else []) + traces)

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

    Renvoie ``(lead, ambigu)`` : ``lead`` est le meilleur candidat (ou
    ``None``), ``ambigu`` dit que le rapprochement par email/téléphone a
    trouvé PLUSIEURS fiches — l'appelant complète alors les champs vides mais
    n'ESTAMPILLE PAS la clé externe Odoo, qui lierait durablement la ligne
    Odoo à une fiche choisie au hasard (CRX10).

    Ordre : clé technique Odoo, puis email normalisé, puis téléphone normalisé.
    Tout est borné à la société.

    CRX7 — le rapprochement porte sur ``Lead.all_objects``, donc sur les leads
    SOFT-SUPPRIMÉS aussi. Un lead mis à la corbeille garde sa clé externe et
    reste soumis à la contrainte d'unicité ``uniq_lead_external_ref`` : en ne
    le voyant pas, l'import tentait une CRÉATION en doublon dont
    l'``IntegrityError`` tuait l'atomique de TOUT l'import (une seule
    suppression suffisait à bricker la sync). L'appelant décide quoi faire du
    lead supprimé — il n'est JAMAIS restauré silencieusement ici.

    Quand plusieurs candidats existent sur email/téléphone, le lead VIVANT
    gagne (``order_by('is_deleted', 'pk')``) : la corbeille ne sert que de
    filet contre le doublon, jamais de cible d'écriture prioritaire.

    CRX10 — le rapprochement par téléphone interroge la colonne INDEXÉE
    ``phone_normalise`` (QW10), maintenue par ``Lead.save()``. Il itérait
    auparavant TOUS les leads de la société en Python, pour CHAQUE ligne
    d'export, et deux fois par sync (import + alignement) : 930 leads × 930
    lignes × 2.
    """
    if external_id:
        match = Lead.all_objects.filter(
            company=company, external_system=EXTERNAL_SYSTEM,
            external_id=external_id).order_by('is_deleted', 'pk').first()
        if match:
            return match, False
    email = services.normalize_email(fields.get('email'))
    if email:
        candidats = list(Lead.all_objects.filter(
            company=company, email__iexact=email).order_by(
                'is_deleted', 'pk')[:2])
        if candidats:
            return candidats[0], len(candidats) > 1
    phone = services.normalize_phone(fields.get('telephone'))
    if phone:
        candidats = list(Lead.all_objects.filter(
            company=company, phone_normalise=phone).order_by(
                'is_deleted', 'pk')[:2])
        if candidats:
            return candidats[0], len(candidats) > 1
    return None, False


def _borne(champ, valeur):
    """Borne une valeur à la longueur RÉELLE de sa colonne, lue sur le modèle.

    LA SEULE source de la longueur : ``Lead._meta`` — jamais un nombre deviné
    ni recopié. ``max_length`` absent (``TextField``) ⇒ valeur inchangée.

    CRX9 avait borné le chemin RÉCONCILIATION ; le chemin CRÉATION ne bornait
    en fait que ``ville``/``telephone``/``whatsapp``, avec des nombres écrits
    en dur. Un ``partner_name`` Odoo de 300 caractères faisait donc tomber
    l'INSERT (``DataError: value too long for type character varying(255)``)
    et, la transaction étant unique, TOUT l'import avec lui.
    """
    if not valeur:
        return valeur
    maxi = Lead._meta.get_field(champ).max_length
    return valeur[:maxi] if maxi else valeur


def _fill_empty(lead, fields):
    """Complète les champs VIDES du lead existant. Renvoie True si modifié.

    CRX9 — deux corrections du chemin RÉCONCILIATION (le chemin création les
    avait déjà, celui-ci non) :

      * chaque valeur est BORNÉE à la longueur réelle de sa colonne, lue sur
        le modèle (jamais un nombre deviné) : un `ville` de 200 caractères ou
        un `telephone` de 60 faisait casser l'UPDATE, donc TOUT l'import
        (transaction unique) ;
      * les colonnes DÉRIVÉES ``phone_normalise``/``email_normalise`` entrent
        dans ``update_fields`` quand ``telephone``/``email`` sont remplis.
        ``Lead.save()`` les recalcule EN MÉMOIRE, mais
        ``save(update_fields=[...])`` ne PERSISTE que les colonnes listées :
        sans elles, les colonnes INDEXÉES de dédup (QW10) restaient vides en
        base et ``find_duplicates_by_contact`` ne retrouvait jamais le lead —
        exactement le bug réel déjà corrigé dans ``services.py`` sur le
        chemin WhatsApp.
    """
    changed = []
    for field in _FILL_FIELDS:
        if field not in fields:
            continue
        current = getattr(lead, field, None)
        if current not in (None, '', False):
            continue
        setattr(lead, field, _borne(field, fields[field]))
        changed.append(field)
    derivees = [_COLONNES_DERIVEES[f]
                for f in changed if f in _COLONNES_DERIVEES]
    if changed:
        lead.save(update_fields=changed + derivees)
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
        # CRX7 — lignes dont le lead rapproché est dans la CORBEILLE : ignorées
        # (ni écriture, ni restauration silencieuse), comptées au rapport.
        corbeille = 0
        corbeille_details = []
        # CRX10 — rapprochements AMBIGUS (2+ fiches sur le même email/tel) :
        # champs vides complétés, mais AUCUNE clé externe estampillée.
        ambigus = []
        # CRX10 — comptes honnêtes en dry-run : sans écriture, deux lignes
        # visant la même fiche (ou créant le même lead) étaient comptées deux
        # fois « créé » / « mis à jour », alors qu'un vrai run n'en compte
        # qu'une. On mémorise donc ce qui a DÉJÀ été traité dans la passe.
        vus_pk = set()
        vus_cles = set()

        # Atomique : un export ne s'applique qu'en entier (rollback en dry-run).
        with transaction.atomic():
            for row in rows:
                fields, external_id, stage_key = _row_to_fields(row)
                if not (fields.get('nom') or fields.get('email')
                        or fields.get('telephone')):
                    skipped += 1
                    continue

                existing, ambigu = _find_existing(company, external_id, fields)
                if existing is not None and existing.is_deleted:
                    # Lead dans la corbeille : on NE crée pas de doublon (la
                    # contrainte d'unicité le refuserait et l'IntegrityError
                    # tuerait tout l'import) et on ne le restaure PAS — la
                    # restauration reste une décision humaine (/core/corbeille/).
                    corbeille += 1
                    if len(corbeille_details) < _MAX_CORBEILLE_AFFICHEE:
                        corbeille_details.append(
                            f"lead #{existing.pk} « {existing.nom} »"
                            + (f" (Odoo {external_id})" if external_id else ''))
                    continue
                if existing is not None:
                    if dry_run and existing.pk in vus_pk:
                        # Une ligne précédente de CE MÊME export a déjà traité
                        # cette fiche ; un VRAI run n'y trouverait plus rien à
                        # compléter (il vient de le faire) et compterait
                        # « inchangé ». Le dry-run, qui n'écrit pas, comptait
                        # « mis à jour » autant de fois qu'il y avait de lignes.
                        unchanged += 1
                        continue
                    vus_pk.add(existing.pk)
                    if ambigu:
                        # Plusieurs fiches partagent cet email/téléphone : lier
                        # la ligne Odoo à l'une d'elles serait un choix
                        # arbitraire et DURABLE. On signale, on ne lie pas.
                        ambigus.append(
                            f"Odoo {external_id or '?'} → lead #{existing.pk} "
                            f"« {existing.nom} » et au moins un autre")
                    # Pose la clé technique si absente (rapproché par email/tel)
                    # ET si le rapprochement est certain.
                    tech_changed = False
                    if external_id and not existing.external_id and not ambigu:
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

                if dry_run:
                    # Pas de fiche en base : un VRAI run en CRÉERAIT une, que
                    # les lignes suivantes rapprocheraient. Le dry-run, qui
                    # n'écrit pas, annonçait donc N créations là où il n'y en
                    # aurait qu'une. On rejoue la chaîne en mémoire.
                    cles = set()
                    if external_id:
                        cles.add(('ext', external_id))
                    email_cle = services.normalize_email(fields.get('email'))
                    if email_cle:
                        cles.add(('email', email_cle))
                    tel_cle = services.normalize_phone(fields.get('telephone'))
                    if tel_cle:
                        cles.add(('tel', tel_cle))
                    if cles & vus_cles:
                        unchanged += 1
                        continue
                    vus_cles |= cles

                # Création — société FORCÉE, marquée import test Odoo.
                if not dry_run:
                    # Chaque colonne texte est BORNÉE à sa longueur réelle
                    # (`_borne`, lue sur le modèle) : une seule ligne trop
                    # longue faisait tomber l'INSERT et, la transaction étant
                    # unique, tout l'import avec elle.
                    Lead.objects.create(
                        company=company,
                        nom=_borne('nom',
                                   fields.get('nom') or fields.get('societe')
                                   or fields.get('email') or 'Lead Odoo'),
                        prenom=_borne('prenom', fields.get('prenom')),
                        societe=_borne('societe', fields.get('societe')),
                        email=_borne('email', fields.get('email')),
                        # CRX35 — repli sur le mobile quand Odoo n'a pas de
                        # `phone` : sans lui, `phone_normalise` reste vide et
                        # le lead devient introuvable par la dédup indexée.
                        telephone=_borne('telephone',
                                         fields.get('telephone')
                                         or fields.get('whatsapp')) or None,
                        whatsapp=_borne('whatsapp',
                                        fields.get('whatsapp')) or None,
                        adresse=_borne('adresse', fields.get('adresse')),
                        ville=_borne('ville', fields.get('ville')) or None,
                        note=fields.get('note'),
                        stage=stage_key,
                        source=Lead.Source.ODOO_IMPORT_TEST,
                        external_system=EXTERNAL_SYSTEM if external_id else None,
                        external_id=_borne('external_id', external_id),
                    )
                created += 1

            if dry_run:
                transaction.set_rollback(True)

        prefix = "[dry-run] " if dry_run else ""
        for detail in corbeille_details:
            self.stdout.write(self.style.WARNING(
                f"{prefix}Corbeille — ignoré (jamais restauré) : {detail}"))
        if corbeille > len(corbeille_details):
            self.stdout.write(self.style.WARNING(
                f"{prefix}… et {corbeille - len(corbeille_details)} autre(s) "
                "ligne(s) rapprochée(s) sur un lead en corbeille."))
        for detail in ambigus[:_MAX_AMBIGUS_AFFICHES]:
            self.stdout.write(self.style.WARNING(
                f"{prefix}Rapprochement ambigu — clé externe NON posée : "
                f"{detail}"))
        reste_ambigus = len(ambigus) - _MAX_AMBIGUS_AFFICHES
        if reste_ambigus > 0:
            self.stdout.write(self.style.WARNING(
                f"{prefix}… et {reste_ambigus} autre(s) rapprochement(s) "
                "ambigu(s)."))
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}Import Odoo terminé pour « {company.nom} » : "
            f"{created} créé(s), {updated} mis à jour, "
            f"{unchanged} inchangé(s), {skipped} ignoré(s), "
            f"{corbeille} en corbeille, {len(ambigus)} ambigu(s) sur "
            f"{len(rows)} ligne(s)."))
