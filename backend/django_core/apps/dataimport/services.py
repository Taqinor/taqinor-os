"""T9 — import réutilisable CSV/XLSX (leads, clients, produits).

Flux en deux temps, multi-tenant :
  1. dry-run : on lit les 10 premières lignes, on mappe colonne → champ (par
     en-tête, insensible à la casse/accents), et on liste ce qui n'a PAS été
     mappé — pour validation AVANT le batch complet.
  2. commit : création UNIQUEMENT (jamais d'écrasement silencieux). Les doublons
     (email/téléphone pour leads/clients, SKU pour produits) sont signalés et
     ignorés. Les enregistrements créés sont marqués d'origine (import).

Séparé de la migration ponctuelle des 619 leads Odoo (gardée à part).

SÉCURITÉ DES DONNÉES RÉELLES (garde-fou « écrasement »)
-------------------------------------------------------
Les modes ``maj``/``upsert`` écrivent sur des fiches EXISTANTES — donc sur les
deux seuls jeux de données réels du parc (le catalogue ``stock.Produit`` et le
pipeline ``crm.Lead``). Trois protections, toutes actives par défaut :

1. **Remplissage seul par défaut** (``ecraser=False``) — une ligne importée ne
   peut que RENSEIGNER un champ vide. Un champ déjà rempli n'est JAMAIS remplacé
   sans que l'appelant demande explicitement ``ecraser=True`` : c'est le même
   contrat que les webhooks entrants (fill-only), après l'incident où une source
   externe avait écrasé des noms de leads réels. Les valeurs refusées sont
   renvoyées ligne par ligne (rien n'est avalé en silence).
2. **Aperçu AVANT écriture** — ``dry_run(..., mode=..., ecraser=...)`` rejoue le
   MÊME rapprochement que le commit (mêmes helpers ``_match_*``) sans rien
   écrire, et liste champ par champ ce qui serait écrasé (ancienne → nouvelle).
3. **Journal réversible** — chaque fiche modifiée laisse (a) le détail des
   champs et de leurs valeurs PRÉCÉDENTES sur ``ImportJobRow`` et (b) une ligne
   d'audit via la primitive plateforme ``apps.audit.recorder`` (jamais un
   journal maison).

Une cellule VIDE n'écrase jamais rien, quel que soit le mode : ``_row_to_fields``
écarte les valeurs vides avant tout traitement.
"""
import logging

from django.db import transaction

from .parsing import iter_rows, normalize_header

logger = logging.getLogger(__name__)

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


def dry_run(file_bytes, filename, target, company=None, mapping_name=None,
            mode='creer', ecraser=False, external_system=None):
    """Aperçu : mapping colonne→champ + 10 premières lignes mappées + non-mappés.

    XPLT2 — si ``mapping_name`` désigne un ``ImportMapping`` sauvegardé (pour
    ``company``+``target``), son mapping colonne→champ est réappliqué en
    priorité sur le mapping automatique habituel.

    APERÇU DES ÉCRASEMENTS — l'aperçu rejoue en plus, SANS RIEN ÉCRIRE, le
    rapprochement exact du commit (``mode``/``external_system`` identiques) et
    répond à la seule question qui compte avant d'importer sur des données
    réelles : *quelles valeurs déjà saisies ce fichier remplacerait-il, et par
    quoi ?* (clés ``conflits``/``ecrasements_total``/``ecrasements_appliques``).
    Sans ``company`` le rapprochement est impossible (multi-tenant) : l'aperçu
    se limite alors au mapping, comme avant.
    """
    if target not in TARGETS:
        raise ValueError("Cible d'import inconnue.")
    _check_mode(target, mode)
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
    result = {
        'target': target,
        'colonnes': headers,
        'mapping': mapped,
        'non_mappees': unmapped,
        'apercu': preview,
        'total_lignes': len(rows),
        'mode': mode,
        'ecraser': bool(ecraser),
    }
    if company is not None and mapped:
        result.update(_analyser_conflits(
            target, rows, mapped, company, mode, external_system,
            ecraser=ecraser))
    return result


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

# Cibles où un rapprochement fiable existe : les seules qui acceptent maj/upsert
# (donc les seules où un écrasement est seulement POSSIBLE).
UPSERT_TARGETS = ('leads', 'clients')

DEFAULT_EXTERNAL_SYSTEM = 'import'

# Aperçu : nombre maximum de lignes DÉTAILLÉES renvoyées (les compteurs, eux,
# portent sur la totalité du fichier). Borne la réponse d'un fichier de 10 000
# lignes sans jamais masquer l'existence d'un écrasement.
MAX_CONFLITS_DETAILLES = 200


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


def _txt(valeur):
    """Forme texte stable d'une valeur (comparaison + journalisation)."""
    return '' if valeur is None else str(valeur)


def _identique(ancienne, nouvelle):
    """Vrai si les deux valeurs sont la MÊME donnée.

    La comparaison se fait sur la forme texte : une cellule CSV/XLSX arrive
    toujours en texte alors que la valeur stockée peut être typée — comparer
    brut ferait passer une réécriture inutile pour un vrai changement (et la
    ferait apparaître à tort comme un écrasement dans l'aperçu)."""
    return _txt(ancienne).strip() == _txt(nouvelle).strip()


def _est_vide(valeur, valeurs_vides=()):
    """Vrai si la valeur STOCKÉE compte comme « non renseignée ».

    ``None``/``''`` toujours ; plus les sentinelles de vide propres à la cible
    (``valeurs_vides``). Un ``DecimalField(default=0)`` par exemple — un tarif
    fournisseur à 0 n'est PAS un prix négocié, c'est un « prix à renseigner » :
    le remplir doit rester un remplissage, jamais un écrasement à autoriser."""
    if valeur is None or valeur == '':
        return True
    for vide in valeurs_vides:
        try:
            if valeur == vide:
                return True
        except (TypeError, ValueError):  # pragma: no cover - types exotiques
            continue
    return False


def _diff_fields(instance, fields, skip_keys=(), valeurs_vides=()):
    """Diff LECTURE SEULE entre une fiche existante et une ligne importée.

    Renvoie ``(ecrasements, remplissages)`` :

    * ``ecrasements`` — champs DÉJÀ REMPLIS dont la valeur diffère. Ce sont les
      SEULS changements destructeurs : une donnée réelle y serait remplacée.
      Format ``{'champ', 'ancienne', 'nouvelle'}``.
    * ``remplissages`` — champs vides que la ligne renseignerait (jamais
      destructeur). Format ``{'champ', 'nouvelle'}``.

    Une cellule vide n'apparaît dans aucune des deux listes : ``_row_to_fields``
    les a déjà écartées, donc un import ne peut jamais VIDER un champ rempli.

    Partagé par l'aperçu (``dry_run``) et l'écriture (``_apply_updates``) pour
    qu'ils ne puissent pas diverger.
    """
    ecrasements, remplissages = [], []
    for key, value in fields.items():
        if key in skip_keys or not hasattr(instance, key):
            continue
        if value in (None, ''):
            continue
        ancienne = getattr(instance, key, None)
        if _identique(ancienne, value):
            continue
        if _est_vide(ancienne, valeurs_vides):
            remplissages.append({'champ': key, 'nouvelle': _txt(value)})
        else:
            ecrasements.append({'champ': key, 'ancienne': _txt(ancienne),
                                'nouvelle': _txt(value)})
    return ecrasements, remplissages


def _apply_updates(instance, fields, skip_keys=(), ecraser=False,
                   valeurs_vides=()):
    """Met à jour une fiche existante à partir d'une ligne importée.

    Ne considère QUE les champs fournis non vides (une valeur absente n'efface
    jamais rien). Par défaut (``ecraser=False``) le comportement est
    REMPLISSAGE SEUL : un champ déjà rempli est laissé intact et la valeur
    entrante est renvoyée dans ``refuses`` au lieu d'être appliquée en silence.
    ``ecraser=True`` (opt-in explicite de l'appelant) applique aussi ces
    remplacements — et les journalise comme tels.

    Renvoie ``(changed, modifications, refuses)`` :

    * ``changed`` — noms des champs réellement écrits (``update_fields``) ;
    * ``modifications`` — pour CHAQUE champ écrit, sa valeur PRÉCÉDENTE et la
      nouvelle + ``ecrasement`` (vrai si la précédente n'était pas vide). C'est
      la trace qui rend l'import réversible ;
    * ``refuses`` — écrasements bloqués par le garde-fou (mode remplissage seul).
    """
    ecrasements, remplissages = _diff_fields(
        instance, fields, skip_keys, valeurs_vides)
    changed, modifications, refuses = [], [], []

    for item in remplissages:
        setattr(instance, item['champ'], fields[item['champ']])
        changed.append(item['champ'])
        modifications.append({'champ': item['champ'], 'ancienne': '',
                              'nouvelle': item['nouvelle'], 'ecrasement': False})

    for item in ecrasements:
        if not ecraser:
            refuses.append(dict(item))
            continue
        setattr(instance, item['champ'], fields[item['champ']])
        changed.append(item['champ'])
        modifications.append(dict(item, ecrasement=True))

    if changed:
        instance.save(update_fields=changed)
    return changed, modifications, refuses


def _journaliser_maj(instance, company, user, modifications, filename):
    """Trace d'audit d'une fiche modifiée par un import.

    Réutilise la primitive plateforme ``apps.audit.recorder`` (entonnoir ARC16 :
    ``AuditLog`` + diff structuré ``changes``) plutôt qu'un journal maison. UNE
    ligne d'audit par FICHE, portant le diff de tous ses champs modifiés — et
    non une ligne par champ : un import de 10 000 lignes en produirait des
    dizaines de milliers, avec autant de requêtes de chaînage.

    Best-effort de bout en bout (même contrat que ``recorder.record``) : une
    trace d'audit qui échoue ne casse jamais l'import.
    """
    if not modifications:
        return
    try:
        from apps.audit.models import AuditLog
        from apps.audit.recorder import record
        resume = ', '.join(
            f"{m['champ']} « {m['ancienne']} » → « {m['nouvelle']} »"
            for m in modifications)
        prefixe = 'Import (écrasement)' if any(
            m['ecrasement'] for m in modifications) else 'Import'
        record(
            AuditLog.Action.UPDATE, instance=instance, company=company,
            user=user if getattr(user, 'pk', None) else None,
            detail=f'{prefixe} « {filename} » : {resume}'[:2000],
            changes=[{'field': m['champ'], 'old': m['ancienne'],
                      'new': m['nouvelle']} for m in modifications])
    except Exception:  # noqa: BLE001 — best-effort, ne jamais casser l'import
        logger.debug('audit import échoué', exc_info=True)


# --- Primitive PARTAGÉE : le même garde-fou pour les importeurs MÉTIER --------
# Cinq importeurs spécialisés vivent hors de cette app (prix fournisseur,
# limites de crédit, entités, compteurs de contrat, tâches de projet) mais font
# exactement la même chose de dangereux : écrire sur des fiches EXISTANTES.
# Ils réutilisent DONC ces trois fonctions publiques — jamais une copie locale
# du diff, du remplissage-seul ou du journal (un second journal maison est la
# dette #1 mesurée du dépôt). L'app propriétaire garde son rapprochement
# métier ; seul le garde-fou est mutualisé.

def diff_import(instance, fields, skip_keys=(), valeurs_vides=()):
    """Aperçu LECTURE SEULE d'une ligne importée sur une fiche existante.

    Renvoie ``(ecrasements, remplissages)`` — voir ``_diff_fields``. C'est la
    fonction qu'un dry-run métier appelle pour répondre, AVANT toute écriture,
    à « quelles valeurs déjà saisies ce fichier remplacerait-il, et par quoi ? ».

    ``valeurs_vides`` : sentinelles de « non renseigné » propres à la cible
    (ex. ``(0,)`` pour un montant dont le défaut modèle est 0) — voir
    ``_est_vide``. À passer À L'IDENTIQUE à ``appliquer_maj_import``, sinon
    l'aperçu et l'écriture divergent.
    """
    return _diff_fields(instance, fields, skip_keys, valeurs_vides)


def appliquer_maj_import(instance, fields, company, user=None, filename='',
                         skip_keys=(), ecraser=False, valeurs_vides=()):
    """Écrit une ligne importée sur une fiche existante, avec le garde-fou.

    ``ecraser=False`` (défaut) = REMPLISSAGE SEUL : un champ déjà rempli n'est
    pas remplacé, la valeur entrante repart dans ``refuses``. ``ecraser=True``
    applique aussi les remplacements. Dans les deux cas, chaque champ écrit
    laisse sa valeur PRÉCÉDENTE (retour ``modifications``) et une ligne d'audit
    via la primitive plateforme ``apps.audit.recorder``.

    Renvoie ``(changed, modifications, refuses)`` — voir ``_apply_updates``.
    """
    changed, modifications, refuses = _apply_updates(
        instance, fields, skip_keys=skip_keys, ecraser=ecraser,
        valeurs_vides=valeurs_vides)
    _journaliser_maj(instance, company, user, modifications, filename)
    return changed, modifications, refuses


def enregistrer_job(company, target, filename, user=None, mode='maj',
                    ecraser=False, statut=None, total_lignes=0, created=0,
                    updated=0, lignes=None):
    """Journalise un lot d'import dans ``ImportJob``/``ImportJobRow``.

    Le MÊME journal que celui de ``commit()`` (qui passe désormais par ici),
    ouvert aux importeurs métier des autres apps : un import de prix d'achat ou
    de limites de crédit apparaît dans le même historique, avec la valeur
    précédente de chaque champ écrit — donc réversible.

    ``lignes`` : liste de dicts ``{ligne, statut, motif, donnees, cible,
    cible_id, modifications, refuses}``. Les compteurs d'écrasements, de refus
    et d'erreurs en sont DÉDUITS (jamais recomptés à la main par l'appelant).
    """
    from .models import ImportJob, ImportJobRow
    lignes = list(lignes or [])
    error_count = sum(1 for ligne in lignes
                      if ligne.get('statut') == ImportJobRow.Statut.ERREUR)
    ecrasement_count = sum(
        1 for ligne in lignes for m in (ligne.get('modifications') or [])
        if m.get('ecrasement'))
    refus_count = sum(len(ligne.get('refuses') or []) for ligne in lignes)
    if statut is None:
        statut = (ImportJob.Statut.PARTIEL if error_count
                  else ImportJob.Statut.OK)

    job = ImportJob.objects.create(
        company=company, target=target, fichier_nom=filename, mode=mode,
        statut=statut, total_lignes=total_lignes,
        created_count=created, updated_count=updated,
        error_count=error_count, ecraser=bool(ecraser),
        ecrasement_count=ecrasement_count, refus_count=refus_count,
        created_by=user if getattr(user, 'pk', None) else None)

    job_rows = [
        ImportJobRow(
            job=job, ligne=ligne['ligne'],
            statut=ligne.get('statut') or ImportJobRow.Statut.OK,
            motif=ligne.get('motif'),
            donnees=ligne.get('donnees') or {},
            cible_type=ligne.get('cible') or '',
            cible_id=ligne.get('cible_id'),
            modifications=ligne.get('modifications') or [],
            refuses=ligne.get('refuses') or [])
        for ligne in lignes]
    if job_rows:
        ImportJobRow.objects.bulk_create(job_rows)
    return job


def _check_mode(target, mode):
    """Valide le couple cible/mode — MÊME règle pour l'aperçu et le commit (un
    mode refusé à l'écriture doit l'être aussi à l'aperçu)."""
    if mode not in MODES:
        raise ValueError("Mode d'import inconnu (creer, maj ou upsert).")
    if mode != 'creer' and target not in UPSERT_TARGETS:
        raise ValueError(
            f"Le mode « {mode} » n'est pas supporté pour la cible « {target} » "
            "(seuls leads et clients supportent maj/upsert).")


# --- Rapprochement : helpers PARTAGÉS par l'aperçu et le commit ---------------
# L'aperçu doit désigner EXACTEMENT la fiche que le commit modifierait, sinon il
# ment. Les deux passent donc par ces mêmes fonctions (aucune duplication de la
# logique de rapprochement).

def _match_lead(company, f, ext_id, external_system):
    """Lead rapproché en mode maj/upsert : identifiant externe d'abord, sinon
    contact normalisé (email/téléphone)."""
    from apps.crm.models import Lead
    from apps.crm.services import find_duplicates_by_contact
    existing = _find_by_external_id(company, external_system, ext_id, Lead)
    if existing is None:
        dupes = find_duplicates_by_contact(
            company, phone=f.get('telephone'), email=f.get('email'))
        existing = dupes[0] if dupes else None
    return existing


def _match_client(company, f, ext_id, external_system):
    from apps.crm.models import Client
    existing = _find_by_external_id(company, external_system, ext_id, Client)
    if existing is None and f.get('email'):
        existing = Client.objects.filter(
            company=company, email__iexact=f['email']).first()
    return existing


def _doublon_lead(company, f):
    """Fiche existante qui fait IGNORER la ligne en mode ``creer``."""
    from apps.crm.models import Lead
    if f.get('email'):
        return Lead.objects.filter(
            company=company, email__iexact=f['email']).first()
    if f.get('telephone'):
        return Lead.objects.filter(
            company=company, telephone=f['telephone']).first()
    return None


def _doublon_client(company, f):
    from apps.crm.models import Client
    if f.get('email'):
        return Client.objects.filter(
            company=company, email__iexact=f['email']).first()
    return None


def _doublon_produit(company, f):
    from apps.stock.models import Produit
    if f.get('sku'):
        return Produit.objects.filter(company=company, sku=f['sku']).first()
    return None


def _analyser_conflits(target, rows, mapped, company, mode, external_system,
                       ecraser=False):
    """Rejoue le rapprochement du commit SANS RIEN ÉCRIRE (cœur de l'aperçu).

    Pour chaque ligne : quelle fiche existante elle vise, ce qu'elle
    ÉCRASERAIT (valeur actuelle → valeur du fichier, champ par champ) et ce
    qu'elle se contenterait de remplir. Les cibles créées uniquement et sans
    rapprochement (véhicules, contrats, dossiers RH… — écriture déléguée à
    l'app propriétaire) n'ont rien à prévisualiser : aucune fiche existante
    n'y est jamais touchée.
    """
    external_system = external_system or DEFAULT_EXTERNAL_SYSTEM
    conflits = []
    resume = {'creation': 0, 'mise_a_jour': 0, 'ignoree': 0}
    ecrasements_total = 0
    lignes_ecrasees = 0
    tronque = False

    for i, row in enumerate(rows, 1):
        f = _row_to_fields(row, mapped)
        if not f:
            continue
        ext_id = f.pop('external_id', None)
        existing, action, raison = None, 'creation', None

        # Mêmes lignes écartées d'emblée que par le commit, sinon les compteurs
        # de l'aperçu annonceraient des créations qui n'auront pas lieu.
        if target == 'leads' and not (
                f.get('nom') or f.get('email') or f.get('telephone')):
            continue
        if target in ('clients', 'products') and not f.get('nom'):
            continue

        if target == 'leads':
            if mode in ('maj', 'upsert'):
                existing = _match_lead(company, f, ext_id, external_system)
                if existing is None and mode == 'maj':
                    action = 'ignoree'
                    raison = 'aucune correspondance (maj seule)'
            else:
                existing = _doublon_lead(company, f)
                if existing is not None:
                    action, raison = 'ignoree', 'doublon (existe déjà)'
        elif target == 'clients':
            if mode in ('maj', 'upsert'):
                existing = _match_client(company, f, ext_id, external_system)
                if existing is None and mode == 'maj':
                    action = 'ignoree'
                    raison = 'aucune correspondance (maj seule)'
            else:
                existing = _doublon_client(company, f)
                if existing is not None:
                    action, raison = 'ignoree', 'doublon (email existe)'
        elif target == 'products':
            existing = _doublon_produit(company, f)
            if existing is not None:
                action, raison = 'ignoree', 'doublon (SKU existe)'
        else:
            continue

        if existing is not None and action != 'ignoree':
            action = 'mise_a_jour'
        resume[action] += 1

        if existing is None:
            continue

        ecrasements, remplissages = _diff_fields(existing, f)
        if action == 'mise_a_jour' and ecrasements:
            lignes_ecrasees += 1
            ecrasements_total += len(ecrasements)
        if not ecrasements and not remplissages and action == 'mise_a_jour':
            continue  # rien à signaler : la ligne est identique à la fiche
        if len(conflits) >= MAX_CONFLITS_DETAILLES:
            tronque = True
            continue
        conflits.append({
            'ligne': i,
            'action': action,
            'raison': raison,
            'cible': existing._meta.label_lower,
            'cible_id': existing.pk,
            'cible_libelle': str(existing)[:150],
            'ecrasements': ecrasements,
            'remplissages': [r['champ'] for r in remplissages],
        })

    return {
        'conflits': conflits,
        'conflits_tronques': tronque,
        'resume': resume,
        # Champs déjà remplis dont la valeur DIFFÈRE, sur les lignes qui seraient
        # effectivement mises à jour : le risque, indépendamment du garde-fou.
        'ecrasements_total': ecrasements_total,
        'lignes_ecrasees': lignes_ecrasees,
        # Ce qui serait RÉELLEMENT écrit compte tenu du garde-fou : 0 en mode
        # remplissage seul (défaut), sinon tous les écrasements ci-dessus.
        'ecrasements_appliques': ecrasements_total if ecraser else 0,
    }


def _commit_raw(file_bytes, filename, target, company, user, mode='creer',
                external_system=None, mapping_name=None, ecraser=False):
    """Crée (mode=creer, défaut inchangé) ou rapproche+met à jour (maj/upsert)
    les enregistrements. Renvoie un récapitulatif (dont ``lignes`` : le détail
    ligne par ligne utilisé par XPLT2 pour le journal ``ImportJob``, et
    ``maj_par_ligne`` : pour chaque fiche modifiée, ses valeurs PRÉCÉDENTES).

    ``ecraser=False`` (défaut) = remplissage seul : les champs déjà remplis ne
    sont pas remplacés, les valeurs entrantes correspondantes sont remontées
    dans ``refuses``. ``ecraser=True`` = l'appelant assume les remplacements,
    qui sont alors tous journalisés (``ImportJobRow`` + ``AuditLog``).
    """
    if target not in TARGETS:
        raise ValueError("Cible d'import inconnue.")
    # XPLT1 — le rapprochement maj/upsert n'est câblé que pour les cibles où un
    # contact (email/téléphone) permet un rapprochement fiable (leads, clients).
    # Les autres cibles gardent le comportement historique (création seule) et
    # refusent explicitement un mode qu'elles ne supportent pas encore, plutôt
    # que de l'ignorer silencieusement.
    _check_mode(target, mode)
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
    # Ligne → fiche touchée + valeurs PRÉCÉDENTES de chaque champ modifié (+ les
    # écrasements refusés par le garde-fou). Persisté par ``commit()`` sur
    # ``ImportJobRow`` : c'est ce qui rend l'import auditable et réversible.
    maj_par_ligne = {}

    def _noter_maj(ligne, instance, modifications, refuses):
        if not modifications and not refuses:
            return
        maj_par_ligne[ligne] = {
            'cible': instance._meta.label_lower,
            'cible_id': instance.pk,
            'modifications': modifications,
            'refuses': refuses,
        }
        _journaliser_maj(instance, company, user, modifications, filename)

    # ERR51 — Tout l'import est atomique : une erreur en cours de boucle annule
    # l'intégralité du lot (jamais de demi-import laissant le compteur perdu et
    # une partie des lignes déjà créées).
    with transaction.atomic():
        if target == 'leads':
            from apps.crm.models import Lead
            for i, row in enumerate(rows, 1):
                f = _row_to_fields(row, mapped)
                if not f.get('nom') and not f.get('email') and not f.get('telephone'):
                    skipped.append({'ligne': i, 'raison': 'ligne vide'})
                    continue
                ext_id = f.pop('external_id', None)

                existing = None
                if mode in ('maj', 'upsert'):
                    existing = _match_lead(company, f, ext_id, external_system)

                if existing is not None:
                    _, modifications, refuses = _apply_updates(
                        existing, f, ecraser=ecraser)
                    _noter_maj(i, existing, modifications, refuses)
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
                    if _doublon_lead(company, f) is not None:
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
                    existing = _match_client(company, f, ext_id, external_system)

                if existing is not None:
                    _, modifications, refuses = _apply_updates(
                        existing, f, ecraser=ecraser)
                    _noter_maj(i, existing, modifications, refuses)
                    if ext_id:
                        _get_or_create_ref(
                            company, external_system, ext_id, existing)
                    updated += 1
                    continue

                if mode == 'maj':
                    skipped.append(
                        {'ligne': i, 'raison': 'aucune correspondance (maj seule)'})
                    continue

                if mode == 'creer' and _doublon_client(company, f) is not None:
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
                # Le catalogue réel n'est JAMAIS écrasé par un import : un SKU
                # déjà présent fait ignorer la ligne (l'aperçu le dit, champ par
                # champ, via le même ``_doublon_produit``).
                if _doublon_produit(company, f) is not None:
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

    return {'ok': True, 'target': target, 'mode': mode, 'ecraser': bool(ecraser),
            'created': created, 'updated': updated, 'skipped': skipped,
            'total': len(rows), 'headers': headers, 'rows': rows,
            'maj_par_ligne': maj_par_ligne}


def commit(file_bytes, filename, target, company, user, mode='creer',
           external_system=None, mapping_name=None, rollback_on_error=False,
           ecraser=False):
    """XPLT2 — enveloppe publique de ``_commit_raw`` : journalise l'import dans
    un ``ImportJob``/``ImportJobRow`` (statut par ligne, motif d'échec,
    contenu brut ré-importable) et applique le choix commit partiel (défaut,
    comportement historique inchangé) vs rollback atomique total.

    ``rollback_on_error=True`` : si NE SERAIT-CE QU'UNE ligne échoue, tout le
    lot est annulé (aucune création/mise à jour ne subsiste) — le job est
    journalisé statut ECHEC et la réponse renvoie l'erreur sans avoir rien
    persisté. ``rollback_on_error=False`` (défaut) : comportement historique —
    les lignes en échec sont signalées, les autres restent commitées.

    ``ecraser`` (défaut ``False`` = remplissage seul) : voir ``_apply_updates``.
    Chaque fiche modifiée laisse sur son ``ImportJobRow`` la valeur PRÉCÉDENTE
    de chaque champ écrit (``modifications``) et les écrasements bloqués par le
    garde-fou (``refuses``) — de quoi auditer et revenir en arrière.
    """
    from .models import ImportJob, ImportJobRow

    def _run():
        return _commit_raw(
            file_bytes, filename, target, company, user, mode=mode,
            external_system=external_system, mapping_name=mapping_name,
            ecraser=ecraser)

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
    maj_par_ligne = result.pop('maj_par_ligne', {})
    skipped_by_line = {s['ligne']: s['raison'] for s in result['skipped']}
    error_count = len(skipped_by_line)
    rolled_back = rollback_on_error and error_count > 0
    ecrasements = [m for detail in maj_par_ligne.values()
                   for m in detail['modifications'] if m['ecrasement']]
    refuses = [r for detail in maj_par_ligne.values() for r in detail['refuses']]

    if rolled_back:
        statut = ImportJob.Statut.ECHEC
    elif error_count:
        statut = ImportJob.Statut.PARTIEL
    else:
        statut = ImportJob.Statut.OK

    lignes = []
    for i, row in enumerate(rows, 1):
        raison = skipped_by_line.get(i)
        detail = {} if rolled_back else maj_par_ligne.get(i, {})
        lignes.append({
            'ligne': i,
            'statut': (ImportJobRow.Statut.ERREUR if raison
                       else ImportJobRow.Statut.OK),
            'motif': raison,
            'donnees': {h: row.get(h) for h in headers} if raison else {},
            'cible': detail.get('cible') or '',
            'cible_id': detail.get('cible_id'),
            'modifications': detail.get('modifications') or [],
            'refuses': detail.get('refuses') or [],
        })
    # Même journal que les importeurs métier des autres apps (primitive
    # partagée ``enregistrer_job``) : un seul historique, un seul format.
    job = enregistrer_job(
        company, target, filename, user=user, mode=mode, ecraser=ecraser,
        statut=statut, total_lignes=result['total'],
        created=0 if rolled_back else result['created'],
        updated=0 if rolled_back else result['updated'], lignes=lignes)

    result['job_id'] = job.pk
    result['statut'] = statut
    # Ce que l'import a réellement remplacé (et ce que le garde-fou a bloqué) :
    # remonté dans la réponse pour que l'écran le montre sans re-requêter.
    result['ecrasements'] = len(ecrasements)
    result['refuses'] = refuses
    if rolled_back:
        result['created'] = 0
        result['updated'] = 0
        result['ecrasements'] = 0
        result['refuses'] = []
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
