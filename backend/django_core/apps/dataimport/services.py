"""T9 — import réutilisable CSV/XLSX (leads, clients, produits).

Flux en deux temps, multi-tenant :
  1. dry-run : on lit les 10 premières lignes, on mappe colonne → champ (par
     en-tête, insensible à la casse/accents), et on liste ce qui n'a PAS été
     mappé — pour validation AVANT le batch complet.
  2. commit : création UNIQUEMENT (jamais d'écrasement silencieux). Les doublons
     (email/téléphone pour leads/clients, SKU pour produits) sont signalés et
     ignorés. Les enregistrements créés sont marqués d'origine (import).

Séparé de la migration ponctuelle des 619 leads Odoo (gardée à part).
"""
from django.db import transaction

from .parsing import iter_rows, normalize_header

# Mapping en-tête (normalisé) → champ modèle, par cible.
FIELD_MAPS = {
    'leads': {
        'nom': 'nom', 'prenom': 'prenom', 'societe': 'societe',
        'email': 'email', 'telephone': 'telephone', 'tel': 'telephone',
        'ville': 'ville', 'whatsapp': 'whatsapp', 'adresse': 'adresse',
        # XPLT1 — identifiant externe optionnel (rapprochement upsert/maj).
        'external_id': 'external_id', 'id_externe': 'external_id',
    },
    'clients': {
        'nom': 'nom', 'prenom': 'prenom', 'email': 'email',
        'telephone': 'telephone', 'tel': 'telephone', 'adresse': 'adresse',
        'ice': 'ice',
        'external_id': 'external_id', 'id_externe': 'external_id',
    },
    'products': {
        'nom': 'nom', 'sku': 'sku', 'reference': 'sku', 'marque': 'marque',
        'prix_vente': 'prix_vente', 'prix': 'prix_vente',
        'prix_achat': 'prix_achat', 'quantite': 'quantite_stock',
        'quantite_stock': 'quantite_stock', 'stock': 'quantite_stock',
        'description': 'description',
    },
    # FG14 — Fournisseurs : import texte simple, pas de relation.
    'fournisseurs': {
        'nom': 'nom', 'contact': 'contact_personne',
        'contact_personne': 'contact_personne', 'email': 'email',
        'telephone': 'telephone', 'tel': 'telephone',
        'adresse': 'adresse',
    },
    # FG14 — Équipements : import avec résolution produit (par SKU) et
    # installation (par référence). Seuls les champs libres sont importables
    # directement ; produit/installation sont résolus côté commit().
    'equipements': {
        'numero_serie': 'numero_serie', 'serie': 'numero_serie',
        'sn': 'numero_serie', 'statut': 'statut', 'note': 'note',
        'produit_sku': 'produit_sku', 'sku': 'produit_sku',
        'installation_ref': 'installation_ref',
        'chantier': 'installation_ref', 'installation': 'installation_ref',
        'date_pose': 'date_pose',
    },
    # XFLT22 — Import initial du parc flotte. Écriture DÉLÉGUÉE à
    # ``apps.flotte.services.creer_vehicule_import`` (jamais les models
    # flotte directement, contrairement aux autres cibles ci-dessus —
    # règle explicite du plan flotte).
    'vehicules': {
        'immatriculation': 'immatriculation', 'immat': 'immatriculation',
        'marque': 'marque', 'modele': 'modele', 'modèle': 'modele',
        'energie': 'energie', 'énergie': 'energie',
        'kilometrage': 'kilometrage', 'km': 'kilometrage',
        'cv': 'cv', 'puissance_fiscale': 'cv',
    },
    # ARC13 — Contrats : import initial du registre contractuel. Écriture
    # DÉLÉGUÉE à ``apps.contrats.services.creer_contrat_import`` (jamais le
    # modèle ``Contrat`` directement, même motif XFLT22 que ``vehicules``).
    'contrats': {
        'reference': 'reference', 'ref': 'reference',
        'objet': 'objet', 'type_contrat': 'type_contrat',
        'type': 'type_contrat', 'statut': 'statut',
        'date_debut': 'date_debut', 'date_fin': 'date_fin',
        'montant': 'montant', 'devise': 'devise',
    },
    # ARC13 — Dossiers RH : import initial des fiches employé. Écriture
    # DÉLÉGUÉE à ``apps.rh.services.creer_dossier_employe_import`` (jamais le
    # modèle ``DossierEmploye`` directement, même motif XFLT22).
    'dossiers_rh': {
        'matricule': 'matricule', 'nom': 'nom', 'prenom': 'prenom',
        'prénom': 'prenom', 'email': 'email', 'telephone': 'telephone',
        'tel': 'telephone', 'cin': 'cin', 'poste': 'poste',
        'date_embauche': 'date_embauche', 'type_contrat': 'type_contrat',
    },
}


# ARC32 — l'ensemble des cibles importables lit désormais le REGISTRE plateforme
# (``core.platform.import_specs``) : chaque app propriétaire déclare ses cibles
# dans son ``apps/<x>/platform.py`` (surface ``import_specs``), exactement comme
# ``records.ALLOWED_TARGETS`` (ARC30). ``TARGETS`` est un OBJET PARESSEUX qui se
# comporte comme un ``set`` immuable en lecture (``in``, itération, ``len``) mais
# calcule son contenu à la PREMIÈRE UTILISATION en unionnant les clés
# ``FIELD_MAPS`` (le MAPPING d'en-têtes → champ reste ici, local à dataimport)
# avec les ``import_specs`` déclarés par tous les manifestes installés.
#
# Résolution PARESSEUSE À DESSEIN : au moment où ce module est importé
# (chargement des apps Django), le registre applicatif n'est pas garanti prêt —
# le calcul n'a lieu qu'au premier ``in``/itération, bien après le démarrage.
# Non-régression garantie par test (le set résolu == les 8 clés FIELD_MAPS
# historiques, chaque cible étant déclarée par son app propriétaire).
class _LazyTargets:
    """Vue ``set``-like sur ``FIELD_MAPS`` ∪ ``core.platform.import_specs()``,
    calculée au premier accès (jamais à l'import de ce module — ``core`` /
    ``django.apps`` peuvent ne pas être prêts à ce moment).

    DROP-IN replacement de l'ancien ``set(FIELD_MAPS)`` littéral pour tous les
    usages du dépôt (``target in TARGETS``, itération, ``len``, ``sorted``)."""

    def _resolve(self):
        cibles = set(FIELD_MAPS)
        try:
            from core import platform
            cibles |= set(platform.import_specs(company=None))
        except Exception:  # pragma: no cover - registre indisponible ⇒ FIELD_MAPS seul
            pass
        return cibles

    def __contains__(self, item):
        return item in self._resolve()

    def __iter__(self):
        return iter(self._resolve())

    def __len__(self):
        return len(self._resolve())

    def __repr__(self):
        return f'_LazyTargets({sorted(self._resolve())!r})'

    def __eq__(self, other):
        if isinstance(other, _LazyTargets):
            return self._resolve() == other._resolve()
        return self._resolve() == other


TARGETS = _LazyTargets()

# ERR53 — Plafond de lignes : au-delà, on refuse proprement (ValueError → 400
# clair côté vue) plutôt que de charger un fichier géant en mémoire et risquer
# un OOM. Doit rester aligné avec `views.MAX_ROWS`.
MAX_ROWS = 10000


class ImportTooLarge(ValueError):
    """Le fichier dépasse le plafond de lignes autorisé (ERR53)."""


def _norm(s):
    """Normalise un en-tête : minuscules, sans accents, espaces → underscore.

    ARC13 — délègue à ``apps.dataimport.parsing.normalize_header`` (logique
    partagée) ; comportement inchangé."""
    return normalize_header(s)


def parse_rows(file_bytes, filename):
    """Renvoie (headers, rows[list[dict]]) depuis un CSV ou XLSX.

    ARC13 — délègue à ``apps.dataimport.parsing.iter_rows`` (parseur générique
    partagé) ; comportement inchangé pour les 6 cibles historiques."""
    return iter_rows(file_bytes, filename)


def _map_headers(headers, target, saved_mapping=None):
    """``saved_mapping`` (XPLT2, ``ImportMapping.mapping``) est un dict
    colonne→champ appliqué EN PRIORITÉ (mêmes clés que le mapping automatique) ;
    toute colonne non couverte retombe sur le mapping par en-tête habituel."""
    fmap = FIELD_MAPS[target]
    mapped, unmapped = {}, []
    for h in headers:
        field = None
        if saved_mapping:
            field = saved_mapping.get(h) or saved_mapping.get(_norm(h))
        if not field:
            field = fmap.get(_norm(h))
        if field:
            mapped[h] = field
        else:
            unmapped.append(h)
    return mapped, unmapped


def dry_run(file_bytes, filename, target, company=None, mapping_name=None):
    """Aperçu : mapping colonne→champ + 10 premières lignes mappées + non-mappés.

    XPLT2 — si ``mapping_name`` désigne un ``ImportMapping`` sauvegardé (pour
    ``company``+``target``), son mapping colonne→champ est réappliqué en
    priorité sur le mapping automatique habituel.
    """
    if target not in TARGETS:
        raise ValueError("Cible d'import inconnue.")
    headers, rows = parse_rows(file_bytes, filename)
    if len(rows) > MAX_ROWS:
        raise ImportTooLarge(
            f'Trop de lignes : {len(rows)} (max {MAX_ROWS}).')
    saved_mapping = None
    if mapping_name and company is not None:
        from .models import ImportMapping
        m = ImportMapping.objects.filter(
            company=company, entity=target, nom=mapping_name).first()
        if m is not None:
            saved_mapping = m.mapping
    mapped, unmapped = _map_headers(headers, target, saved_mapping)
    preview = []
    for row in rows[:10]:
        preview.append({field: row.get(col) for col, field in mapped.items()})
    return {
        'target': target,
        'colonnes': headers,
        'mapping': mapped,
        'non_mappees': unmapped,
        'apercu': preview,
        'total_lignes': len(rows),
    }


def save_mapping(company, target, nom, mapping):
    """XPLT2 — sauvegarde (ou remplace) un mapping colonne→champ nommé pour
    une cible, réutilisable au prochain dry-run."""
    from .models import ImportMapping
    obj, _created = ImportMapping.objects.update_or_create(
        company=company, entity=target, nom=nom, defaults={'mapping': mapping})
    return obj


def list_mappings(company, target=None):
    """XPLT2 — mappings sauvegardés d'une société (sélecteur frontend), triés
    par usage le plus récent. ``target`` optionnel restreint à une cible."""
    from .models import ImportMapping
    qs = ImportMapping.objects.filter(company=company)
    if target:
        qs = qs.filter(entity=target)
    return list(qs)


def _row_to_fields(row, mapped):
    return {field: row.get(col) for col, field in mapped.items()
            if row.get(col) not in (None, '')}


# XPLT1 — modes de commit. ``creer`` (défaut) reproduit exactement le
# comportement historique (création seule, doublons ignorés). ``maj``/
# ``upsert`` rapprochent d'abord par identifiant externe (ExternalRef) puis par
# contact normalisé (réutilise ``find_duplicates_by_contact``) : en cas de
# correspondance, seuls les champs FOURNIS par la ligne sont mis à jour
# (jamais d'écrasement silencieux par une valeur absente) ; ``maj`` n'importe
# JAMAIS de nouvelle fiche (une ligne sans correspondance est ignorée),
# ``upsert`` crée si aucune correspondance n'est trouvée.
MODES = {'creer', 'maj', 'upsert'}

DEFAULT_EXTERNAL_SYSTEM = 'import'


def _get_or_create_ref(company, external_system, external_id, obj):
    from .models import ExternalRef
    from django.contrib.contenttypes.models import ContentType
    ct = ContentType.objects.get_for_model(obj)
    ExternalRef.objects.get_or_create(
        company=company, external_system=external_system,
        external_id=external_id,
        defaults={'content_type': ct, 'object_id': obj.pk})


def _find_by_external_id(company, external_system, external_id, model):
    from .models import ExternalRef
    if not external_id:
        return None
    ref = ExternalRef.objects.filter(
        company=company, external_system=external_system,
        external_id=str(external_id)).first()
    if ref is None:
        return None
    return model.objects.filter(company=company, pk=ref.object_id).first()


def _apply_updates(instance, fields, skip_keys=()):
    """Met à jour uniquement les champs FOURNIS (non vides) — jamais d'écrasement
    par une valeur absente de la ligne importée."""
    changed = []
    for key, value in fields.items():
        if key in skip_keys:
            continue
        if not hasattr(instance, key):
            continue
        if value in (None, ''):
            continue
        if getattr(instance, key, None) != value:
            setattr(instance, key, value)
            changed.append(key)
    if changed:
        instance.save(update_fields=changed)
    return changed


def _commit_raw(file_bytes, filename, target, company, user, mode='creer',
                external_system=None, mapping_name=None):
    """Crée (mode=creer, défaut inchangé) ou rapproche+met à jour (maj/upsert)
    les enregistrements. Renvoie un récapitulatif (dont ``lignes`` : le détail
    ligne par ligne utilisé par XPLT2 pour le journal ``ImportJob``)."""
    if target not in TARGETS:
        raise ValueError("Cible d'import inconnue.")
    if mode not in MODES:
        raise ValueError("Mode d'import inconnu (creer, maj ou upsert).")
    # XPLT1 — le rapprochement maj/upsert n'est câblé que pour les cibles où un
    # contact (email/téléphone) permet un rapprochement fiable (leads, clients).
    # Les autres cibles gardent le comportement historique (création seule) et
    # refusent explicitement un mode qu'elles ne supportent pas encore, plutôt
    # que de l'ignorer silencieusement.
    if mode != 'creer' and target not in ('leads', 'clients'):
        raise ValueError(
            f"Le mode « {mode} » n'est pas supporté pour la cible « {target} » "
            "(seuls leads et clients supportent maj/upsert).")
    external_system = external_system or DEFAULT_EXTERNAL_SYSTEM
    headers, rows = parse_rows(file_bytes, filename)
    if len(rows) > MAX_ROWS:
        raise ImportTooLarge(
            f'Trop de lignes : {len(rows)} (max {MAX_ROWS}).')
    saved_mapping = None
    if mapping_name:
        from .models import ImportMapping
        m = ImportMapping.objects.filter(
            company=company, entity=target, nom=mapping_name).first()
        if m is not None:
            saved_mapping = m.mapping
    mapped, _ = _map_headers(headers, target, saved_mapping)
    created, updated, skipped = 0, 0, []

    # ERR51 — Tout l'import est atomique : une erreur en cours de boucle annule
    # l'intégralité du lot (jamais de demi-import laissant le compteur perdu et
    # une partie des lignes déjà créées).
    with transaction.atomic():
        if target == 'leads':
            from apps.crm.models import Lead
            from apps.crm.services import find_duplicates_by_contact
            for i, row in enumerate(rows, 1):
                f = _row_to_fields(row, mapped)
                if not f.get('nom') and not f.get('email') and not f.get('telephone'):
                    skipped.append({'ligne': i, 'raison': 'ligne vide'})
                    continue
                ext_id = f.pop('external_id', None)

                existing = None
                if mode in ('maj', 'upsert'):
                    existing = _find_by_external_id(
                        company, external_system, ext_id, Lead)
                    if existing is None:
                        dupes = find_duplicates_by_contact(
                            company, phone=f.get('telephone'),
                            email=f.get('email'))
                        existing = dupes[0] if dupes else None

                if existing is not None:
                    _apply_updates(existing, f)
                    if ext_id:
                        _get_or_create_ref(
                            company, external_system, ext_id, existing)
                    updated += 1
                    continue

                if mode == 'maj':
                    skipped.append(
                        {'ligne': i, 'raison': 'aucune correspondance (maj seule)'})
                    continue

                # Création (mode=creer, ou mode=upsert sans correspondance).
                if mode == 'creer':
                    dup = Lead.objects.filter(company=company)
                    if f.get('email'):
                        dup = dup.filter(email__iexact=f['email'])
                    elif f.get('telephone'):
                        dup = dup.filter(telephone=f['telephone'])
                    else:
                        dup = Lead.objects.none()
                    if dup.exists():
                        skipped.append({'ligne': i, 'raison': 'doublon (existe déjà)'})
                        continue
                tags = (f.pop('tags', '') or '')
                f['tags'] = (tags + (', ' if tags else '') + 'Import').strip(', ')[:500]
                lead = Lead.objects.create(company=company, **f)
                if ext_id:
                    _get_or_create_ref(company, external_system, ext_id, lead)
                created += 1

        elif target == 'clients':
            from apps.crm.models import Client
            for i, row in enumerate(rows, 1):
                f = _row_to_fields(row, mapped)
                if not f.get('nom'):
                    skipped.append({'ligne': i, 'raison': 'nom manquant'})
                    continue
                ext_id = f.pop('external_id', None)

                existing = None
                if mode in ('maj', 'upsert'):
                    existing = _find_by_external_id(
                        company, external_system, ext_id, Client)
                    if existing is None and f.get('email'):
                        existing = Client.objects.filter(
                            company=company, email__iexact=f['email']).first()

                if existing is not None:
                    _apply_updates(existing, f)
                    if ext_id:
                        _get_or_create_ref(
                            company, external_system, ext_id, existing)
                    updated += 1
                    continue

                if mode == 'maj':
                    skipped.append(
                        {'ligne': i, 'raison': 'aucune correspondance (maj seule)'})
                    continue

                if mode == 'creer' and f.get('email') and Client.objects.filter(
                        company=company, email__iexact=f['email']).exists():
                    skipped.append({'ligne': i, 'raison': 'doublon (email existe)'})
                    continue
                client = Client.objects.create(company=company, **f)
                if ext_id:
                    _get_or_create_ref(company, external_system, ext_id, client)
                created += 1

        elif target == 'products':
            from decimal import Decimal, InvalidOperation
            from apps.stock.models import MouvementStock, Produit
            for i, row in enumerate(rows, 1):
                f = _row_to_fields(row, mapped)
                if not f.get('nom'):
                    skipped.append({'ligne': i, 'raison': 'nom manquant'})
                    continue
                if f.get('sku') and Produit.objects.filter(
                        company=company, sku=f['sku']).exists():
                    skipped.append({'ligne': i, 'raison': 'doublon (SKU existe)'})
                    continue
                for k in ('prix_vente', 'prix_achat'):
                    if k in f:
                        raw = (str(f[k]).replace('\xa0', '').replace(' ', '')
                               .replace(',', '.'))
                        try:
                            f[k] = Decimal(raw)
                        except (InvalidOperation, ValueError):
                            f.pop(k)
                # ERR52 — Le stock d'ouverture ne peut jamais être négatif et
                # passe par le registre des mouvements (audit) comme partout
                # ailleurs : on crée le produit à 0 puis on enregistre un
                # MouvementStock ENTREE pour la quantité importée.
                opening = 0
                if 'quantite_stock' in f:
                    try:
                        opening = int(float(f.pop('quantite_stock')))
                    except (ValueError, TypeError):
                        opening = 0
                    if opening < 0:
                        skipped.append(
                            {'ligne': i, 'raison': 'stock négatif refusé'})
                        continue
                f.setdefault('prix_vente', Decimal('0'))
                produit = Produit.objects.create(
                    company=company, quantite_stock=0, **f)
                if opening > 0:
                    produit.quantite_stock = opening
                    produit.save(update_fields=['quantite_stock'])
                    MouvementStock.objects.create(
                        company=company, produit=produit,
                        type_mouvement=MouvementStock.TypeMouvement.ENTREE,
                        quantite=opening, quantite_avant=0,
                        quantite_apres=opening, created_by=user,
                        note='Stock initial (import)')
                created += 1

        # FG14 — Fournisseurs.
        elif target == 'fournisseurs':
            from apps.stock.models import Fournisseur
            for i, row in enumerate(rows, 1):
                f = _row_to_fields(row, mapped)
                if not f.get('nom'):
                    skipped.append({'ligne': i, 'raison': 'nom manquant'})
                    continue
                if Fournisseur.objects.filter(
                        company=company, nom__iexact=f['nom']).exists():
                    skipped.append({'ligne': i, 'raison': 'doublon (nom existe)'})
                    continue
                Fournisseur.objects.create(company=company, **f)
                created += 1

        # FG14 — Équipements : résolution produit par SKU, installation par réf.
        elif target == 'equipements':
            import datetime
            from apps.sav.models import Equipement
            from apps.stock.models import Produit
            from apps.installations.models import Installation
            for i, row in enumerate(rows, 1):
                f = _row_to_fields(row, mapped)
                # Résolution produit (SKU obligatoire).
                produit_sku = f.pop('produit_sku', None)
                if not produit_sku:
                    skipped.append({'ligne': i, 'raison': 'produit_sku manquant'})
                    continue
                try:
                    produit = Produit.objects.get(company=company, sku=produit_sku)
                except Produit.DoesNotExist:
                    skipped.append({'ligne': i, 'raison': f'produit SKU inconnu : {produit_sku}'})
                    continue
                # Résolution installation (référence obligatoire).
                install_ref = f.pop('installation_ref', None)
                if not install_ref:
                    skipped.append({'ligne': i, 'raison': 'installation_ref manquant'})
                    continue
                try:
                    installation = Installation.objects.get(
                        company=company, reference=install_ref)
                except Installation.DoesNotExist:
                    skipped.append({'ligne': i, 'raison': f'installation inconnue : {install_ref}'})
                    continue
                # Numéro de série : doublon par (produit, installation, numero_serie).
                numero_serie = f.get('numero_serie')
                if numero_serie and Equipement.objects.filter(
                        company=company, produit=produit,
                        installation=installation,
                        numero_serie=numero_serie).exists():
                    skipped.append({'ligne': i, 'raison': 'doublon (série existe)'})
                    continue
                # Normalisation date_pose.
                if 'date_pose' in f:
                    raw_date = f['date_pose']
                    if isinstance(raw_date, datetime.datetime):
                        f['date_pose'] = raw_date.date()
                    elif isinstance(raw_date, str):
                        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
                            try:
                                f['date_pose'] = datetime.datetime.strptime(
                                    raw_date.strip(), fmt).date()
                                break
                            except (ValueError, AttributeError):
                                pass
                        else:
                            f.pop('date_pose')
                Equipement.objects.create(
                    company=company, produit=produit,
                    installation=installation, created_by=user, **f)
                created += 1

        # XFLT22 — Véhicules du parc flotte : écriture déléguée à
        # ``apps.flotte.services`` (jamais les models flotte directement).
        elif target == 'vehicules':
            from apps.flotte.services import creer_vehicule_import
            for i, row in enumerate(rows, 1):
                f = _row_to_fields(row, mapped)
                statut, message = creer_vehicule_import(company, f)
                if statut == 'cree':
                    created += 1
                elif statut == 'doublon':
                    skipped.append(
                        {'ligne': i, 'raison': 'doublon (immatriculation existe)'})
                else:
                    skipped.append({'ligne': i, 'raison': message or 'erreur'})

        # ARC13 — Contrats : écriture déléguée à ``apps.contrats.services``
        # (jamais le modèle ``Contrat`` directement, motif XFLT22).
        elif target == 'contrats':
            from apps.contrats.services import creer_contrat_import
            for i, row in enumerate(rows, 1):
                f = _row_to_fields(row, mapped)
                statut, message = creer_contrat_import(company, f, user=user)
                if statut == 'cree':
                    created += 1
                elif statut == 'doublon':
                    skipped.append(
                        {'ligne': i, 'raison': 'doublon (référence existe)'})
                else:
                    skipped.append({'ligne': i, 'raison': message or 'erreur'})

        # ARC13 — Dossiers RH : écriture déléguée à ``apps.rh.services``
        # (jamais le modèle ``DossierEmploye`` directement, motif XFLT22).
        elif target == 'dossiers_rh':
            from apps.rh.services import creer_dossier_employe_import
            for i, row in enumerate(rows, 1):
                f = _row_to_fields(row, mapped)
                statut, message = creer_dossier_employe_import(company, f)
                if statut == 'cree':
                    created += 1
                elif statut == 'doublon':
                    skipped.append(
                        {'ligne': i, 'raison': 'doublon (matricule existe)'})
                else:
                    skipped.append({'ligne': i, 'raison': message or 'erreur'})

    return {'ok': True, 'target': target, 'mode': mode, 'created': created,
            'updated': updated, 'skipped': skipped, 'total': len(rows),
            'headers': headers, 'rows': rows}


def commit(file_bytes, filename, target, company, user, mode='creer',
           external_system=None, mapping_name=None, rollback_on_error=False):
    """XPLT2 — enveloppe publique de ``_commit_raw`` : journalise l'import dans
    un ``ImportJob``/``ImportJobRow`` (statut par ligne, motif d'échec,
    contenu brut ré-importable) et applique le choix commit partiel (défaut,
    comportement historique inchangé) vs rollback atomique total.

    ``rollback_on_error=True`` : si NE SERAIT-CE QU'UNE ligne échoue, tout le
    lot est annulé (aucune création/mise à jour ne subsiste) — le job est
    journalisé statut ECHEC et la réponse renvoie l'erreur sans avoir rien
    persisté. ``rollback_on_error=False`` (défaut) : comportement historique —
    les lignes en échec sont signalées, les autres restent commitées.
    """
    from .models import ImportJob, ImportJobRow

    def _run():
        return _commit_raw(
            file_bytes, filename, target, company, user, mode=mode,
            external_system=external_system, mapping_name=mapping_name)

    if rollback_on_error:
        # Rejoue tout dans UNE transaction externe : si des lignes ont échoué,
        # on annule le lot entier plutôt que de garder les créations partielles.
        with transaction.atomic():
            result = _run()
            if result['skipped']:
                transaction.set_rollback(True)
    else:
        result = _run()

    rows = result.pop('rows', [])
    headers = result.pop('headers', [])
    skipped_by_line = {s['ligne']: s['raison'] for s in result['skipped']}
    error_count = len(skipped_by_line)
    rolled_back = rollback_on_error and error_count > 0

    if rolled_back:
        statut = ImportJob.Statut.ECHEC
    elif error_count:
        statut = ImportJob.Statut.PARTIEL
    else:
        statut = ImportJob.Statut.OK

    job = ImportJob.objects.create(
        company=company, target=target, fichier_nom=filename, mode=mode,
        statut=statut, total_lignes=result['total'],
        created_count=0 if rolled_back else result['created'],
        updated_count=0 if rolled_back else result['updated'],
        error_count=error_count,
        created_by=user if getattr(user, 'pk', None) else None)

    job_rows = []
    for i, row in enumerate(rows, 1):
        raison = skipped_by_line.get(i)
        job_rows.append(ImportJobRow(
            job=job, ligne=i,
            statut=ImportJobRow.Statut.ERREUR if raison else ImportJobRow.Statut.OK,
            motif=raison,
            donnees={h: row.get(h) for h in headers} if raison else {}))
    if job_rows:
        ImportJobRow.objects.bulk_create(job_rows)

    result['job_id'] = job.pk
    result['statut'] = statut
    if rolled_back:
        result['created'] = 0
        result['updated'] = 0
    return result


def erreurs_csv_rows(job):
    """XPLT2 — lignes en ÉCHEC d'un ``ImportJob``, prêtes à être ré-écrites en
    CSV (mêmes en-têtes que le fichier d'origine + une colonne ``_motif``)."""
    from .models import ImportJobRow
    error_rows = job.rows.filter(statut=ImportJobRow.Statut.ERREUR).order_by('ligne')
    fieldnames = []
    seen = set()
    for r in error_rows:
        for k in r.donnees.keys():
            if k not in seen:
                seen.add(k)
                fieldnames.append(k)
    fieldnames.append('_motif')
    out_rows = []
    for r in error_rows:
        row = dict(r.donnees)
        row['_motif'] = r.motif or ''
        out_rows.append(row)
    return fieldnames, out_rows
