"""Services d'orchestration du groupe NTMIG.

Toute écriture de données métier est DÉLÉGUÉE à ``apps.dataimport`` (dry-run /
commit / ExternalRef / ImportJob) ou aux ``services.py`` des apps cibles —
jamais un import direct de leurs modèles, jamais un second importateur, jamais
un second journal.

NTMIG5 — la garde « pas de succès sans reconcile » : un lot ne devient
``reconcilie`` (et un projet ``termine``) que si son dernier rapport est
``conforme`` OU s'il porte une dérogation explicite, motivée et attribuée.
"""
from decimal import Decimal

from django.utils import timezone

from .models import LotMigration, ProjetMigration, RapportReconciliation


class LotFige(ValueError):
    """Le lot est déjà réconcilié : on n'y rejoue plus ni analyse ni
    chargement sans lever d'abord la réconciliation.

    Sans cette garde, recharger un lot déjà réconcilié écraserait ses
    compteurs miroir et rendrait MENSONGER le rapport déjà remis au client
    (le PV dirait « conforme » sur des chiffres qui ne sont plus ceux du
    chargement réel).
    """


class ReconcileBloque(ValueError):
    """Clôture refusée : réconciliation non conforme et non dérogée.

    Porte la liste des ``ecarts`` bloquants pour que l'appelant (endpoint,
    écran) puisse les afficher au lieu d'un simple « échec » (NTMIG5).
    """

    def __init__(self, message, ecarts=None):
        super().__init__(message)
        self.ecarts = ecarts or []


def _refuser_si_fige(lot):
    if lot.statut == LotMigration.Statut.RECONCILIE:
        raise LotFige(
            'Lot déjà réconcilié : rejouer une analyse ou un chargement '
            'invaliderait son rapport. Levez la réconciliation d\'abord.')


# ─────────────────────────────────────────────────────────────────────────
# NTMIG15 — étalonnage tenant : un système externe STABLE par projet
# ─────────────────────────────────────────────────────────────────────────
def external_system_pour(projet):
    """Système externe stable d'un projet : ``migration:<source>:<projet_id>``.

    C'est la clé d'idempotence de tout le groupe : les ``ExternalRef`` posés
    par le premier chargement sont retrouvés par les suivants, donc un
    ré-import du même fichier sur CE projet ne duplique JAMAIS (2ᵉ passe = 0
    création, N mises à jour).

    L'identifiant de PROJET fait partie de la clé, et ce n'est pas décoratif :
    sans lui, deux projets d'une même société ayant la même source
    partageraient un seul espace de noms — le second projet mettrait à jour
    les enregistrements créés par le premier, et surtout un rollback de lot
    (NTMIG6, qui cible précisément ce système externe) SUPPRIMERAIT des lignes
    créées par l'autre projet. La clé est donc par projet, comme le nom de la
    tâche l'exige, pas seulement par source.
    """
    return f'migration:{projet.source}:{projet.pk}'


def _mode_pour(entite, demande=None):
    """Mode de commit valide pour cette cible.

    ``upsert`` (rapprochement par identifiant externe, donc idempotent) n'est
    supporté par le moteur que pour certaines cibles ; ailleurs il lève. On
    choisit donc le meilleur mode disponible plutôt que de faire échouer
    l'étape. Un mode fourni par l'appelant est FILTRÉ : ``creer`` ne rapproche
    rien et re-crée à chaque passe — accepter ce mode depuis une requête HTTP
    supprimerait la garantie d'idempotence de tout le groupe.
    """
    from apps.dataimport import services as dataimport_services

    supporte_upsert = entite in dataimport_services.UPSERT_TARGETS
    if not supporte_upsert:
        return 'creer'
    if demande in ('upsert', 'maj'):
        return demande
    return 'upsert'


# ─────────────────────────────────────────────────────────────────────────
# NTMIG35 — fichiers source TEMPORAIRES : mémorisation puis purge
# ─────────────────────────────────────────────────────────────────────────
#: Délai de conservation des fichiers source après la clôture d'un projet.
RETENTION_FICHIERS_JOURS = 30


def memoriser_fichier_source(lot, file_bytes, filename):
    """Range le fichier source du lot dans le stockage objet (MinIO/S3).

    Pourquoi le garder : sans lui, une reprise après incident (NTMIG38) ou une
    migration à blanc (NTMIG33) exigerait de re-téléverser exactement le même
    fichier — introuvable des semaines plus tard chez un grand compte.

    Pourquoi ne PAS le garder longtemps : il contient des données personnelles
    (clients, leads). Il est donc TEMPORAIRE par contrat — purgé
    automatiquement `RETENTION_FICHIERS_JOURS` jours après la clôture
    (:func:`purger_fichiers_expires`) — et n'est JAMAIS commité au dépôt.

    Le fichier précédent est supprimé du stockage : garder les versions
    intermédiaires multiplierait les copies de données personnelles sans que
    personne ne les demande.
    """
    from . import stockage

    ancien = lot.fichier_source_cle
    lot.fichier_source_cle = stockage.enregistrer(
        lot.company_id, lot.pk, file_bytes, filename)
    lot.fichier_source_nom = filename or ''
    if ancien and ancien != lot.fichier_source_cle:
        stockage.supprimer(ancien)


def fichier_source_de(lot):
    """(octets, nom d'origine) du fichier source mémorisé — ``None`` si purgé.

    ``None`` n'est pas une anomalie : c'est l'état NORMAL d'un projet clôturé
    depuis plus de :data:`RETENTION_FICHIERS_JOURS` jours (ou d'un stockage
    objet momentanément indisponible — l'appelant propose alors de
    re-téléverser le fichier plutôt que de travailler sur du vide).
    """
    from . import stockage

    contenu = stockage.lire(lot.fichier_source_cle)
    if contenu is None:
        return None
    return contenu, (lot.fichier_source_nom or 'source.csv')


def purger_fichiers_source(projet):
    """Supprime du stockage les fichiers source des lots d'un projet.

    Les RAPPORTS de réconciliation (agrégats non-PII) et les compteurs sont
    conservés intacts : après la purge, le PV de migration reste produisible —
    seules les données personnelles brutes disparaissent.
    """
    from . import stockage

    purges = 0
    for lot in lots_du_projet(projet):
        if not lot.fichier_source_cle:
            continue
        stockage.supprimer(lot.fichier_source_cle)
        lot.fichier_source_cle = ''
        lot.fichier_source_nom = ''
        lot.save(update_fields=[
            'fichier_source_cle', 'fichier_source_nom', 'updated_at'])
        purges += 1
    if not projet.fichiers_purges:
        projet.fichiers_purges = True
        projet.save(update_fields=['fichiers_purges', 'updated_at'])
    return purges


def projets_a_purger(maintenant=None):
    """Projets clôturés depuis plus de :data:`RETENTION_FICHIERS_JOURS` jours
    et pas encore purgés — toutes sociétés confondues (c'est un job de
    plateforme, la rétention ne dépend pas du tenant)."""
    maintenant = maintenant or timezone.now()
    limite = maintenant - timezone.timedelta(days=RETENTION_FICHIERS_JOURS)
    return ProjetMigration.objects.filter(
        statut=ProjetMigration.Statut.TERMINE,
        date_fin__isnull=False, date_fin__lte=limite,
        fichiers_purges=False)


def purger_fichiers_expires(maintenant=None):
    """NTMIG35 — purge planifiée (job Beat ``migration.purger_fichiers_migration``).

    Best-effort par projet : un stockage indisponible sur UN projet ne doit pas
    empêcher la purge des autres (une purge de données personnelles qui
    s'arrête à la première erreur laisserait des fichiers en trop, ce qui est
    exactement ce que la tâche doit éviter).
    """
    import logging

    logger = logging.getLogger(__name__)
    total_projets = 0
    total_fichiers = 0
    for projet in projets_a_purger(maintenant):
        try:
            total_fichiers += purger_fichiers_source(projet)
        except Exception:
            logger.exception(
                'Purge des fichiers source impossible pour le projet %s',
                projet.pk)
            continue
        total_projets += 1
    return {'projets': total_projets, 'fichiers': total_fichiers}


def analyser_lot(lot, file_bytes, filename, *, mapping_name=None):
    """Aperçu DRY-RUN STRICT : rien n'est écrit dans les tables cibles.

    Pose les comptages source sur le lot (base du reconcile) et REMET À ZÉRO
    les compteurs cible du chargement précédent. Ce dernier point est vital :
    sans lui, analyser un nouveau fichier puis réconcilier comparerait le
    comptage du NOUVEAU fichier aux résultats de l'ANCIEN chargement, et
    pourrait certifier « conforme » un fichier jamais importé.

    Le dry-run rejoue le rapprochement réel et renvoie les ``conflits`` /
    ``ecrasements_*`` : l'intégrateur voit, AVANT d'importer, quelles valeurs
    déjà saisies le fichier toucherait.
    """
    from apps.dataimport import services as dataimport_services

    _refuser_si_fige(lot)
    apercu = dataimport_services.dry_run(
        file_bytes, filename, lot.entite, company=lot.company,
        mapping_name=mapping_name, mode=_mode_pour(lot.entite),
        external_system=external_system_pour(lot.projet))
    lot.source_lignes = apercu.get('total_lignes', 0)
    lot.crees = 0
    lot.maj = 0
    lot.erreurs = 0
    lot.import_job = None
    lot.statut = LotMigration.Statut.ANALYSE
    # NTMIG35 — le fichier analysé est mémorisé (temporairement) pour que le
    # chargement, la reprise (NTMIG38) et la migration à blanc (NTMIG33)
    # rejouent EXACTEMENT le fichier validé, pas un autre.
    memoriser_fichier_source(lot, file_bytes, filename)
    lot.save(update_fields=[
        'source_lignes', 'crees', 'maj', 'erreurs', 'import_job', 'statut',
        'fichier_source_cle', 'fichier_source_nom', 'updated_at'])
    return apercu


# ─────────────────────────────────────────────────────────────────────────
# NTMIG32 — qualité de la SOURCE avant chargement
# ─────────────────────────────────────────────────────────────────────────
def _reconstruire_csv(headers, rows, filename):
    """Réécrit des lignes déjà parsées en CSV utf-8 (mêmes en-têtes, même ordre).

    Sert à REJOUER un SOUS-ENSEMBLE du fichier source dans le moteur d'import
    sans lui ajouter d'API : le moteur relit un fichier, on lui en donne un.
    Le CSV est le format pivot (un XLSX d'origine ressort en CSV) — le mapping
    par en-tête est identique, seules les lignes changent.
    """
    import csv
    import io
    import os

    tampon = io.StringIO()
    writer = csv.DictWriter(tampon, fieldnames=list(headers),
                            extrasaction='ignore')
    writer.writeheader()
    for row in rows:
        writer.writerow({h: ('' if row.get(h) is None else row.get(h))
                         for h in headers})
    base = os.path.splitext(os.path.basename(filename or 'source'))[0]
    return tampon.getvalue().encode('utf-8'), f'{base}.csv'


def fichier_sans_lignes(file_bytes, filename, lignes_exclues):
    """Fichier source PRIVÉ des lignes citées (numéros 1-based, en-tête exclu).

    C'est le « continuer sans les lignes invalides » proposé par
    :func:`valider_source` : rien n'est corrigé automatiquement, les lignes
    fautives sont simplement laissées de côté — et l'appelant sait lesquelles.
    """
    from apps.dataimport import services as dataimport_services

    exclues = set(lignes_exclues or ())
    headers, rows = dataimport_services.parse_rows(file_bytes, filename)
    gardees = [row for numero, row in enumerate(rows, 1)
               if numero not in exclues]
    return _reconstruire_csv(headers, gardees, filename)


def valider_source(lot, file_bytes, filename, *, kit_cle=None,
                   mapping_name=None):
    """NTMIG32 — rapport de qualité de la SOURCE, AVANT tout chargement.

    Applique les règles de format (ICE/e-mail/téléphone/montant) issues du kit
    quand il existe, sinon de ``dataquality`` (NTDATA14) s'il est présent,
    sinon des règles locales minimales — voir :mod:`apps.migration.validation`.
    Aucune écriture : ni en base cible, ni sur le lot (un contrôle de qualité
    ne doit pas déplacer le lot dans le flux ; seul l'analyse dry-run le fait).

    Le rapport porte les numéros des lignes invalides pour que l'écran puisse
    proposer de continuer SANS elles (:func:`fichier_sans_lignes`) plutôt que
    d'imposer un choix binaire « tout ou rien ».
    """
    from apps.dataimport import services as dataimport_services

    from . import validation

    # La société est passée pour que le mapping SAUVEGARDÉ (XPLT2) s'applique
    # comme il s'appliquera au chargement : valider un fichier avec un mapping
    # différent de celui qui sera utilisé donnerait un rapport hors sujet.
    apercu = dataimport_services.dry_run(
        file_bytes, filename, lot.entite, company=lot.company,
        mapping_name=mapping_name,
        external_system=external_system_pour(lot.projet))
    mapped = apercu.get('mapping') or {}
    _, rows = dataimport_services.parse_rows(file_bytes, filename)
    regles = validation.regles_effectives(
        mapped, kit_cle=kit_cle, company=lot.company, entite=lot.entite)
    rapport = validation.valider_lignes(rows, mapped, regles)
    rapport['entite'] = lot.entite
    rapport['kit'] = kit_cle or ''
    rapport['colonnes_non_mappees'] = apercu.get('non_mappees') or []
    return rapport


def charger_lot(lot, file_bytes, filename, *, mode=None,
                mapping_name=None, user=None):
    """Charge un lot via le moteur ``dataimport`` — jamais un 2ᵉ importateur.

    Garanties non négociables :

    * ``external_system`` vaut TOUJOURS ``migration:<source>:<projet_id>``
      (NTMIG15) : un second passage du même fichier retrouve les
      enregistrements par ``ExternalRef`` et met à jour au lieu de dupliquer ;
    * le mode est FILTRÉ par :func:`_mode_pour` — ``creer``, qui ne rapproche
      rien, n'est jamais accepté depuis une requête sur une cible qui sait
      faire mieux ;
    * ``ecraser`` n'est JAMAIS activé — le chargement est en REMPLISSAGE SEUL.
      Une cellule vide ou absente ne remplace pas une valeur déjà saisie, et
      une valeur déjà saisie n'est pas remplacée par la source (le moteur la
      remonte dans ``refuses``). Une migration ne doit jamais effacer ce qu'un
      humain a corrigé à la main dans l'ERP ; c'est volontairement NON
      paramétrable depuis l'API ;
    * une DÉROGATION antérieure est levée : elle portait sur les chiffres du
      chargement précédent. La laisser en place ferait clôturer le nouveau
      chargement sur un motif périmé, et imprimerait ce motif sur le PV.

    Le lot est verrouillé (``select_for_update``) le temps de la transition :
    deux chargements simultanés ne peuvent pas se marcher dessus et laisser
    des compteurs qui ne décrivent aucun des deux.
    """
    from django.db import transaction

    from apps.dataimport import services as dataimport_services

    with transaction.atomic():
        verrou = (LotMigration.objects.select_for_update()
                  .get(pk=lot.pk))
        _refuser_si_fige(verrou)

        result = dataimport_services.commit(
            file_bytes, filename, verrou.entite, verrou.company, user,
            mode=_mode_pour(verrou.entite, mode),
            external_system=external_system_pour(verrou.projet),
            mapping_name=mapping_name, ecraser=False)

        verrou.source_lignes = result.get('total', 0)
        verrou.crees = result.get('created', 0)
        verrou.maj = result.get('updated', 0)
        verrou.erreurs = len(result.get('skipped', []))
        job_id = result.get('job_id')
        verrou.import_job_id = job_id or None
        verrou.statut = LotMigration.Statut.CHARGE
        # La dérogation portait sur le chargement PRÉCÉDENT : elle ne couvre
        # pas celui-ci.
        verrou.derogation_reconcile = False
        verrou.derogation_motif = ''
        verrou.derogation_par = None
        verrou.derogation_at = None
        # NTMIG38 — un chargement COMPLET repart de la ligne 1 : le décalage
        # de reprise éventuel d'un chargement précédent ne vaut plus.
        verrou.fichier_offset_lignes = 0
        # NTMIG35 — fichier réellement chargé, gardé temporairement (reprise
        # NTMIG38 / migration à blanc NTMIG33), purgé après clôture.
        memoriser_fichier_source(verrou, file_bytes, filename)
        verrou.save(update_fields=[
            'source_lignes', 'crees', 'maj', 'erreurs', 'import_job',
            'statut', 'derogation_reconcile', 'derogation_motif',
            'derogation_par', 'derogation_at', 'fichier_source_cle',
            'fichier_source_nom', 'fichier_offset_lignes', 'updated_at'])

    lot.refresh_from_db()
    return result


# ─────────────────────────────────────────────────────────────────────────
# NTMIG38 — reprise sur incident (idempotence d'un lot partiellement chargé)
# ─────────────────────────────────────────────────────────────────────────
class RepriseImpossible(ValueError):
    """Rien à reprendre — ou pas de quoi reprendre sans risque de doublon."""


def derniere_ligne_commitee(lot):
    """Numéro, DANS LE FICHIER D'ORIGINE, de la dernière ligne commitée.

    ``0`` s'il n'y a jamais eu de chargement : la « reprise » est alors un
    chargement complet. Le décalage ``fichier_offset_lignes`` traduit les
    numéros du dernier journal (qui portent sur le RESTE du fichier après une
    reprise précédente) en numéros de la source d'origine.
    """
    from django.db.models import Max

    job = lot.import_job
    if job is None:
        return 0
    statut_ok = job.rows.model.Statut.OK
    dernier = job.rows.filter(statut=statut_ok).aggregate(
        m=Max('ligne'))['m'] or 0
    return lot.fichier_offset_lignes + dernier


def reprendre_lot(lot, file_bytes=None, filename=None, *, user=None,
                  mapping_name=None):
    """NTMIG38 — reprend un lot interrompu APRÈS sa dernière ligne commitée.

    Un chargement de 1 000 lignes coupé à la 600ᵉ reprend à la 601ᵉ : les 600
    premières ne sont ni rejouées ni dupliquées, parce qu'elles ne sont même
    pas envoyées au moteur — le fichier est REJOUÉ TRONQUÉ (les lignes déjà
    commitées sont retirées) plutôt que re-soumis en entier en espérant que le
    rapprochement les reconnaisse. C'est la seule façon d'être idempotent y
    compris sur les cibles qui ne savent pas encore faire d'``upsert``
    (produits, fournisseurs…) : sur celles-là, un simple ré-envoi
    RE-CRÉERAIT les 600 premières.

    Ceinture ET bretelles : le mode ``upsert`` est en plus demandé quand la
    cible le supporte, de sorte qu'une ligne à cheval (commitée mais non
    journalisée à cause de l'incident) soit rapprochée par ``ExternalRef``
    au lieu d'être dupliquée.

    Sans fichier fourni, on reprend celui MÉMORISÉ au chargement (NTMIG35) :
    quelques semaines après, plus personne ne retrouve le fichier d'origine —
    et reprendre avec un AUTRE fichier décalerait toute la numérotation.

    Les compteurs du lot restent CUMULÉS (source = fichier d'origine entier,
    créés/màj = toutes passes confondues) : la réconciliation NTMIG4/5 compare
    bien la source complète à ce qui a réellement été chargé, sinon un lot
    repris paraîtrait « conforme » sur les seules 400 dernières lignes.
    """
    from apps.dataimport import services as dataimport_services

    _refuser_si_fige(lot)

    if file_bytes is None:
        memorise = fichier_source_de(lot)
        if memorise is None:
            raise RepriseImpossible(
                'Aucun fichier source mémorisé pour ce lot (purgé ou jamais '
                'chargé) : re-téléversez le fichier d\'origine pour reprendre.')
        file_bytes, filename = memorise
    filename = filename or lot.fichier_source_nom or 'source.csv'

    coupe = derniere_ligne_commitee(lot)
    headers, rows = dataimport_services.parse_rows(file_bytes, filename)
    total_source = len(rows)
    restantes = rows[coupe:]
    prior_crees, prior_maj = lot.crees, lot.maj
    prior_erreurs = _erreurs_avant_coupe(lot)

    if not restantes:
        raise RepriseImpossible(
            f'Rien à reprendre : les {total_source} ligne(s) du fichier ont '
            'déjà été traitées.')

    octets, nom = _reconstruire_csv(headers, restantes, filename)
    resultat = charger_lot(
        lot, octets, nom, mode='upsert', mapping_name=mapping_name, user=user)

    lot.refresh_from_db()
    lot.source_lignes = total_source
    lot.crees = prior_crees + resultat.get('created', 0)
    lot.maj = prior_maj + resultat.get('updated', 0)
    lot.erreurs = prior_erreurs + len(resultat.get('skipped', []))
    lot.fichier_offset_lignes = coupe
    # Le fichier mémorisé par ``charger_lot`` est le TRONÇON rejoué : on
    # remet l'ORIGINAL, faute de quoi une seconde reprise repartirait d'un
    # fichier amputé de ses 600 premières lignes.
    memoriser_fichier_source(lot, file_bytes, filename)
    lot.save(update_fields=[
        'source_lignes', 'crees', 'maj', 'erreurs', 'fichier_offset_lignes',
        'fichier_source_cle', 'fichier_source_nom', 'updated_at'])

    return {
        'reprise_depuis_ligne': coupe + 1,
        'lignes_deja_commitees': coupe,
        'lignes_rejouees': len(restantes),
        'total_source': total_source,
        'resultat': resultat,
    }


def _erreurs_avant_coupe(lot):
    """Erreurs cumulées à CONSERVER, hors lignes sur le point d'être rejouées.

    Une ligne refusée AVANT le point de coupe ne redevient pas valide parce
    qu'on reprend : elle reste un écart à traiter (fichier corrigé ou
    dérogation motivée), et l'oublier ferait passer le lot « conforme » alors
    que des lignes source n'ont jamais été importées. En revanche, les lignes
    en erreur SITUÉES APRÈS la coupe repartent dans la passe de reprise : les
    compter deux fois gonflerait artificiellement les écarts.
    """
    from django.db.models import Max

    job = lot.import_job
    if job is None:
        return lot.erreurs
    statuts = job.rows.model.Statut
    dernier_ok = job.rows.filter(statut=statuts.OK).aggregate(
        m=Max('ligne'))['m'] or 0
    rejouees = job.rows.filter(
        statut=statuts.ERREUR, ligne__gt=dernier_ok).count()
    return max(lot.erreurs - rejouees, 0)


# ─────────────────────────────────────────────────────────────────────────
# NTMIG9 — chargement via le connecteur Odoo JSON-2 (gated ; jamais de SQL)
# ─────────────────────────────────────────────────────────────────────────
#: Module du connecteur Odoo JSON-2 (FG378, propriété du groupe NTAPI). Il
#: n'existe pas encore : la constante est le SEUL point de couplage, et son
#: absence rend simplement le chemin API indisponible.
CONNECTEUR_ODOO_MODULE = 'apps.publicapi.connectors.odoo'


class ConnecteurNonConfigure(ValueError):
    """Le connecteur Odoo JSON-2 (FG378) n'est pas présent/configuré.

    Le chargement par API est alors un no-op propre : l'import fichier reste
    la voie disponible et l'endpoint le dit explicitement (NTMIG9).
    """


def _odoo_connector_client(company):
    """Import PARESSEUX du client connecteur Odoo JSON-2 (FG378, NTAPI).

    Renvoie ``None`` tant que le connecteur n'est pas présent ou configuré
    pour cette société. RÈGLE #1 : quand il existe, il est utilisé en LECTURE
    SEULE via l'API JSON-2 — jamais une écriture, et JAMAIS du SQL vers la
    base Odoo, sous aucun prétexte.
    """
    import importlib

    try:
        module = importlib.import_module(CONNECTEUR_ODOO_MODULE)
    except ImportError:
        return None
    fabrique = getattr(module, 'client_pour_societe', None)
    if fabrique is None:
        return None
    try:
        return fabrique(company)
    except Exception:
        # Une société sans clé/URL configurée n'est pas une erreur : c'est le
        # cas nominal « pas encore branché ».
        return None


def charger_depuis_odoo_api(lot, params=None, user=None):
    """Récupère les enregistrements via l'API JSON-2 d'Odoo, puis les passe au
    MÊME pipeline dry-run/commit que l'import fichier.

    Sans connecteur configuré : ``ConnecteurNonConfigure`` (no-op propre → 400
    explicite proposant l'import fichier). Le connecteur n'est appelé QUE pour
    EXPORTER (lecture) ; rien n'est jamais écrit côté Odoo, ni par API ni —
    à plus forte raison — par SQL (règle #1).
    """
    _refuser_si_fige(lot)
    client = _odoo_connector_client(lot.company)
    if client is None:
        raise ConnecteurNonConfigure(
            'Connecteur Odoo non configuré — utilisez l\'import fichier.')
    exporter = getattr(client, 'exporter_entite', None)
    if exporter is None:
        raise ConnecteurNonConfigure(
            'Connecteur Odoo présent mais incomplet (pas d\'export lecture '
            'seule) — utilisez l\'import fichier.')
    file_bytes, filename = exporter(lot.entite, params or {})
    # `user` est propagé pour que l'ImportJob et l'AuditLog du chemin API
    # portent un auteur, comme ceux du chemin fichier.
    return charger_lot(lot, file_bytes, filename, user=user)


def reconcilier_lot(lot, *, total_financier_cible=None):
    """Produit un :class:`RapportReconciliation` — comptages source vs cible.

    ``conforme`` seulement si TOUT est vrai : zéro ligne en erreur, comptage
    cible == comptage source, et — quand les DEUX totaux financiers sont
    renseignés — écart financier nul.

    DEUX LIMITES CONNUES, écrites ici pour que personne ne croie le contrôle
    plus fort qu'il n'est :

    1. ``lot.source_montant`` et ``total_financier_cible`` sont alimentés par
       les KITS (qui déclarent les colonnes montant par entité) ; ces kits ne
       sont pas construits. Tant que l'un des deux manque, la comparaison
       financière ne s'applique pas — et le rapport ne prétend PAS l'avoir
       faite : ses deux colonnes restent vides sur le PV.
    2. Le moteur d'import compte une mise à jour PAR LIGNE SOURCE. Si deux
       lignes source se rapprochent d'un même enregistrement cible (même
       e-mail), il compte 2 alors qu'un seul enregistrement existe, et le
       comptage paraît juste. Détecter cette fusion demande le nombre
       d'enregistrements DISTINCTS touchés, que ``dataimport.commit`` ne
       renvoie pas aujourd'hui ; l'ajouter est du ressort de cette app-là. On
       ne devine pas ici : une heuristique locale (compter les lignes de
       journal portant une cible) se déclenche à tort sur un ré-import
       identique — où aucune ligne n'est journalisée faute de modification —
       et un faux écart pousserait l'intégrateur à déroger par réflexe, ce qui
       affaiblirait la garde au lieu de la renforcer.

    Chaque appel crée un NOUVEAU rapport : l'historique des constats n'est
    jamais réécrit.
    """
    total_cible = lot.crees + lot.maj
    ecarts = []
    if lot.erreurs:
        ecarts.append({
            'type': 'erreurs', 'nb': lot.erreurs,
            'detail': f'{lot.erreurs} ligne(s) en erreur, non importée(s).'})
    if lot.source_lignes and total_cible != lot.source_lignes:
        ecarts.append({
            'type': 'comptage', 'source': lot.source_lignes,
            'cible': total_cible,
            'detail': (f'Comptage cible ({total_cible}) différent de la '
                       f'source ({lot.source_lignes}).')})
    if not lot.source_lignes and not lot.crees and not lot.maj:
        ecarts.append({
            'type': 'jamais_charge',
            'detail': 'Aucun chargement enregistré pour ce lot.'})

    src = lot.source_montant
    cib = total_financier_cible
    if src is not None and cib is not None and Decimal(src) != Decimal(cib):
        ecarts.append({
            'type': 'financier', 'source': str(src), 'cible': str(cib),
            'detail': (f'Total financier cible ({cib}) différent de la '
                       f'source ({src}).')})

    return RapportReconciliation.objects.create(
        company=lot.company, lot=lot,
        nb_source=lot.source_lignes, nb_cible_crees=lot.crees,
        nb_cible_existants=lot.maj, nb_erreurs=lot.erreurs,
        total_financier_source=src, total_financier_cible=cib,
        ecarts=ecarts, conforme=not ecarts)


# ─────────────────────────────────────────────────────────────────────────
# NTMIG34 — estimation d'effort (indicative, jamais bloquante)
# ─────────────────────────────────────────────────────────────────────────
#: Jours-homme fixes d'un projet (cadrage, réglages, recette finale).
EFFORT_SOCLE_JOURS = Decimal('1.0')
#: Jours-homme fixes par lot (préparation de l'export, contrôle, reconcile).
EFFORT_PAR_LOT_JOURS = Decimal('0.5')
#: Jours-homme par tranche de 1 000 lignes (nettoyage + contrôles).
EFFORT_PAR_MILLE_LIGNES = Decimal('0.1')
#: Surcoût d'une entité MAÎTRE-DÉTAIL (en-têtes + lignes à rattacher).
EFFORT_MAITRE_DETAIL_JOURS = Decimal('1.0')
#: Surcoût quand aucun kit ne couvre (source, entité) : mapping à la main.
EFFORT_SANS_KIT_JOURS = Decimal('0.5')
#: Entités à documents maître-détail (NTMIG10/11).
ENTITES_MAITRE_DETAIL = ('devis', 'factures', 'commandes', 'avoirs')


def _kit_disponible(source, entite):
    """Un kit couvre-t-il ce couple ? ``False`` tant que les kits n'existent
    pas (import paresseux — aucun registre de substitution n'est fabriqué)."""
    import importlib

    from .validation import KITS_MODULE

    try:
        module = importlib.import_module(KITS_MODULE)
    except ImportError:
        return False
    registre = getattr(module, 'KIT_REGISTRY', None)
    if not registre:
        return False
    return (source, entite) in registre


def estimer_effort(projet):
    """NTMIG34 — estimation en jours-homme + points d'attention.

    PUREMENT INDICATIF : cette fonction ne bloque rien, ne change aucun statut
    et n'écrit rien. Elle sert à répondre « combien de temps ? » avant de
    s'engager, à partir de ce qui est déjà mesuré : les comptages source posés
    par l'analyse (NTMIG7) et la complexité du couple (source, entité).

    Déterministe par construction (que des comptages et des constantes, aucun
    hasard ni horodatage) : deux appels sur un projet inchangé renvoient le
    même chiffre — une estimation qui bouge toute seule ne serait pas
    opposable au client.
    """
    lots = list(lots_du_projet(projet))
    total = EFFORT_SOCLE_JOURS
    detail = []
    sans_kit = []
    non_analyses = []
    volumineux = []
    maitre_detail = []
    for lot in lots:
        effort = EFFORT_PAR_LOT_JOURS
        effort += (Decimal(lot.source_lignes) / Decimal(1000)
                   * EFFORT_PAR_MILLE_LIGNES)
        if lot.entite in ENTITES_MAITRE_DETAIL:
            effort += EFFORT_MAITRE_DETAIL_JOURS
            maitre_detail.append(lot.entite)
        if not _kit_disponible(projet.source, lot.entite):
            effort += EFFORT_SANS_KIT_JOURS
            sans_kit.append(lot.entite)
        if not lot.source_lignes:
            non_analyses.append(lot.entite)
        if lot.source_lignes >= 10000:
            volumineux.append(lot.entite)
        effort = _arrondi_demi_journee(effort)
        detail.append({
            'lot': lot.pk, 'entite': lot.entite,
            'lignes_source': lot.source_lignes,
            'jours_homme': str(effort)})
        total += effort

    points = []
    if non_analyses:
        points.append(
            'Lots pas encore analysés (estimation au socle, sans volume) : '
            + ', '.join(non_analyses))
    if sans_kit:
        points.append(
            'Aucun kit de mapping pour ces entités : mapping manuel à prévoir '
            '— ' + ', '.join(sans_kit))
    if maitre_detail:
        points.append(
            'Documents maître-détail (en-têtes + lignes à rattacher) : '
            + ', '.join(maitre_detail))
    if volumineux:
        points.append(
            'Volumes supérieurs à 10 000 lignes (prévoir un chargement par '
            'lots et une fenêtre dédiée) : ' + ', '.join(volumineux))
    if not lots:
        points.append('Aucun lot déclaré : estimation limitée au socle projet.')
    points.append(
        'Estimation INDICATIVE : elle ne conditionne aucun chargement ni '
        'aucune clôture.')

    return {
        'projet': projet.pk,
        'source': projet.source,
        'nb_lots': len(lots),
        'lignes_source_total': sum(lot.source_lignes for lot in lots),
        'jours_homme': str(_arrondi_demi_journee(total)),
        'detail_par_lot': detail,
        'points_attention': points,
    }


def _arrondi_demi_journee(valeur):
    """Arrondit au demi-jour SUPÉRIEUR — une estimation de migration
    s'annonce en demi-journées, jamais en centièmes de jour."""
    from decimal import ROUND_CEILING

    return (Decimal(valeur) * 2).quantize(
        Decimal('1'), rounding=ROUND_CEILING) / 2


def deroger_reconcile(lot, motif, user):
    """Enregistre une dérogation explicite — bool + motif + qui + quand.

    C'est la SEULE porte de sortie d'un lot non conforme : elle exige un motif
    non vide et laisse une trace attribuée (jamais une dérogation anonyme ni
    silencieuse). Écrit uniquement les champs de dérogation (``update_fields``)
    pour ne rien écraser d'autre sur le lot.
    """
    if not motif or not motif.strip():
        raise ValueError('Une dérogation exige un motif explicite.')
    lot.derogation_reconcile = True
    lot.derogation_motif = motif.strip()
    lot.derogation_par = user if getattr(user, 'pk', None) else None
    lot.derogation_at = timezone.now()
    lot.save(update_fields=[
        'derogation_reconcile', 'derogation_motif', 'derogation_par',
        'derogation_at', 'updated_at'])
    return lot


def ecarts_bloquants(lot):
    """Écarts qui EMPÊCHENT de clôturer ``lot`` — ``[]`` s'il est clôturable.

    Ordre de décision : un rapport conforme libère ; sinon une dérogation
    libère ; sinon on renvoie les écarts (ou l'absence même de rapport, qui
    est l'écart le plus grave : « migration réussie » jamais affirmée sans
    preuve).
    """
    rapport = lot.rapports.order_by('-created_at').first()
    if rapport is not None and rapport.conforme:
        return []
    if lot.derogation_reconcile:
        return []
    if rapport is None:
        return [{'type': 'sans_rapport',
                 'detail': 'Aucun rapport de réconciliation pour ce lot.'}]
    return list(rapport.ecarts) or [{
        'type': 'non_conforme',
        'detail': 'Rapport de réconciliation non conforme.'}]


def marquer_lot_termine(lot, user=None):
    """Passe un lot en ``reconcilie`` — refuse sinon (``ReconcileBloque``).

    Un lot dont le rapport n'est pas conforme et qui n'est pas dérogé RESTE
    ``charge`` : jamais ``reconcilie``, jamais ``termine``.
    """
    bloquants = ecarts_bloquants(lot)
    if bloquants:
        raise ReconcileBloque(
            "Le lot n'est pas réconcilié : rapport non conforme et aucune "
            "dérogation motivée.", ecarts=bloquants)
    if lot.statut != LotMigration.Statut.RECONCILIE:
        lot.statut = LotMigration.Statut.RECONCILIE
        lot.save(update_fields=['statut', 'updated_at'])
    return lot


# ─────────────────────────────────────────────────────────────────────────
# NTMIG33 — migration à blanc sur le sandbox (NTADM10) — jamais la production
# ─────────────────────────────────────────────────────────────────────────
#: Selectors de l'app sandbox (NTADM10) — SEUL point de couplage (lecture).
ADMINOPS_SELECTORS_MODULE = 'apps.adminops.selectors'


class SandboxIndisponible(ValueError):
    """Aucun environnement sandbox prêt — no-op propre (NTMIG33).

    Ce n'est pas une panne : un tenant qui n'a jamais provisionné de sandbox
    est le cas nominal. L'endpoint le dit et propose de le créer.
    """


def _societe_sandbox(company):
    """Société SANDBOX d'un tenant via les selectors d'``adminops``.

    Import PARESSEUX + lecture par selector : jamais un import des modèles
    d'``adminops``, jamais une redéfinition locale de « sandbox utilisable ».
    """
    import importlib

    try:
        module = importlib.import_module(ADMINOPS_SELECTORS_MODULE)
    except ImportError:
        return None
    lecteur = getattr(module, 'sandbox_pret', None)
    if lecteur is None:
        return None
    try:
        env = lecteur(company)
    except Exception:
        return None
    return getattr(env, 'sandbox_company', None) if env is not None else None


def migrer_a_blanc(projet, user=None):
    """NTMIG33 — rejoue TOUT le projet sur le tenant sandbox, jamais en prod.

    Objectif : valider mappings + réconciliation sur des données réelles sans
    risque. Le projet d'origine n'est pas touché du tout (ni statut, ni
    compteurs, ni fichiers) : un PROJET MIROIR est créé dans la société
    sandbox, ses lots y sont chargés depuis les fichiers mémorisés (NTMIG35),
    et chacun produit son rapport de réconciliation.

    GARDE-FOU CENTRAL — la société cible est vérifiée DIFFÉRENTE de celle du
    projet avant la moindre écriture. Un sandbox mal provisionné qui pointerait
    sur le tenant de production ferait de cette fonction un import réel non
    demandé : on refuse plutôt que d'écrire.

    Sans sandbox prêt : :class:`SandboxIndisponible` (no-op propre, rien créé).
    Un lot dont le fichier source a été purgé (NTMIG35) est SAUTÉ avec son
    motif — jamais rejoué « à vide », ce qui produirait un rapport de
    réconciliation trompeur.
    """
    from django.db import transaction

    societe_sandbox = _societe_sandbox(projet.company)
    if societe_sandbox is None:
        raise SandboxIndisponible(
            'Aucun environnement sandbox prêt pour cette société : créez-en '
            'un (Administration → Sandbox) avant de tester une migration à '
            'blanc.')
    if societe_sandbox.pk == projet.company_id:
        raise SandboxIndisponible(
            'Le sandbox déclaré désigne la société de production : migration '
            'à blanc refusée.')

    with transaction.atomic():
        projet_blanc = ProjetMigration.objects.create(
            company=societe_sandbox,
            nom=f'[À blanc] {projet.nom}'[:200],
            source=projet.source,
            statut=ProjetMigration.Statut.CHARGEMENT,
            cree_par=user if getattr(user, 'pk', None) else None,
            date_debut=timezone.now(),
            notes=(f'Migration à blanc du projet {projet.pk} '
                   f'({projet.company_id}) — données de test uniquement.'))
        lots_blancs = []
        for lot in lots_du_projet(projet).order_by('ordre', 'pk'):
            lots_blancs.append((lot, LotMigration.objects.create(
                company=societe_sandbox, projet=projet_blanc,
                entite=lot.entite, ordre=lot.ordre)))

    resultats = []
    for lot, lot_blanc in lots_blancs:
        memorise = fichier_source_de(lot)
        if memorise is None:
            resultats.append({
                'entite': lot.entite, 'lot_blanc': lot_blanc.pk,
                'saute': True,
                'motif': ('Fichier source indisponible (purgé ou jamais '
                          'chargé) : lot non rejoué.')})
            continue
        file_bytes, filename = memorise
        try:
            charger_lot(lot_blanc, file_bytes, filename, user=user)
        except Exception as exc:  # un lot en échec n'arrête pas l'essai
            resultats.append({
                'entite': lot.entite, 'lot_blanc': lot_blanc.pk,
                'saute': True, 'motif': f'Chargement à blanc échoué : {exc}'})
            continue
        lot_blanc.refresh_from_db()
        rapport = reconcilier_lot(lot_blanc)
        resultats.append({
            'entite': lot.entite, 'lot_blanc': lot_blanc.pk, 'saute': False,
            'conforme': rapport.conforme, 'ecarts': rapport.ecarts,
            'nb_source': rapport.nb_source,
            'nb_cible': rapport.nb_cible_crees + rapport.nb_cible_existants})

    # Les copies de fichiers source posées dans le sandbox sont supprimées TOUT
    # DE SUITE : un essai à blanc n'a aucune raison de laisser une seconde
    # copie de données personnelles derrière lui, et le projet miroir n'étant
    # jamais clôturé, la purge planifiée (NTMIG35) ne le ramasserait jamais.
    purger_fichiers_source(projet_blanc)

    return {
        'projet_blanc': projet_blanc.pk,
        'societe_sandbox': societe_sandbox.pk,
        'lots': resultats,
        'conforme': all(r.get('conforme') for r in resultats
                        if not r.get('saute')) and bool(resultats),
    }


def lots_du_projet(projet):
    """Lots d'un projet, RE-FILTRÉS sur la société du projet.

    Ceinture et bretelles : la relation inverse suffit tant que rien n'a pu
    rattacher un lot d'une autre société au projet, mais tout ce qui parle au
    client (clôture, PV) doit être borné société de façon explicite plutôt que
    par confiance dans l'intégrité amont.
    """
    return projet.lots.filter(company_id=projet.company_id)


def terminer_projet(projet, user=None):
    """Clôture un projet — refuse tant qu'un lot n'est pas conforme/dérogé.

    Vérifie TOUS les lots AVANT d'en marquer un seul, et applique le tout dans
    UNE transaction : une clôture refusée — ou interrompue — ne laisse jamais
    un projet à moitié clôturé (des lots figés en ``reconcilie`` sous un projet
    resté ouvert seraient ingérables : ``_refuser_si_fige`` interdirait de les
    recharger). L'erreur porte, par lot, la liste des écarts bloquants (rendue
    telle quelle en 400 par l'endpoint).
    """
    from django.db import transaction

    lots = list(lots_du_projet(projet))
    bloquants = []
    for lot in lots:
        ecarts = ecarts_bloquants(lot)
        if ecarts:
            bloquants.append({
                'lot': lot.pk, 'entite': lot.entite, 'ecarts': ecarts})
    if bloquants:
        raise ReconcileBloque(
            'Des lots ne sont pas réconciliés ni dérogés : clôture refusée.',
            ecarts=bloquants)

    with transaction.atomic():
        for lot in lots:
            marquer_lot_termine(lot, user=user)
        projet.statut = ProjetMigration.Statut.TERMINE
        projet.date_fin = timezone.now()
        projet.save(update_fields=['statut', 'date_fin', 'updated_at'])
    return projet


# ─────────────────────────────────────────────────────────────────────────
# NTMIG22 — checklist de déploiement : instancier un playbook kb et cocher
# ses étapes. La lecture du playbook passe par ``kb.selectors`` (frontière
# cross-app) ; ``apps.kb.models`` n'est JAMAIS importé ici.
# ─────────────────────────────────────────────────────────────────────────


class EtapeInconnue(ValueError):
    """La clé d'étape cochée n'appartient pas à cette instance.

    Accepter une clé inconnue ferait grossir ``avancement`` de cases
    fantômes que rien n'afficherait jamais — et un jour, si le playbook
    modèle réintroduisait cette clé, elle réapparaîtrait cochée sans que
    personne ne l'ait fait.
    """


def _etapes_instantanees(article):
    """Aplatit les phases d'un playbook kb en étapes plates instantanées."""
    from apps.kb import selectors as kb_selectors

    etapes, vues = [], set()
    for phase in kb_selectors.phases_playbook(article):
        for etape in phase['etapes']:
            if etape['cle'] in vues:
                continue
            vues.add(etape['cle'])
            etapes.append({
                'cle': etape['cle'],
                'libelle': etape['libelle'],
                'phase': phase['cle'],
                'phase_titre': phase['titre'],
            })
    return etapes


def instancier_playbook(article, *, company, projet_migration=None,
                        responsable=None, client_final=''):
    """Crée l'instance d'un playbook kb pour un déploiement donné.

    ``article`` est un playbook DÉJÀ résolu scopé société par l'appelant
    (``kb.selectors.playbook_par_id``). Les étapes sont figées ici : voir la
    docstring du modèle pour la raison (une checklist en cours ne se réécrit
    pas sous les pieds de l'intégrateur).
    """
    from .models import PlaybookInstance

    if projet_migration is not None \
            and projet_migration.company_id != company.pk:
        raise ValueError('Projet de migration introuvable.')
    etapes = _etapes_instantanees(article)
    if not etapes:
        raise ValueError(
            "Ce playbook n'a aucune étape : rien à cocher. Complétez sa "
            'structure (phases → étapes) avant de l\'instancier.')
    return PlaybookInstance.objects.create(
        company=company,
        playbook_article=article,
        playbook_titre=article.titre,
        projet_migration=projet_migration,
        client_final=client_final or '',
        responsable=responsable,
        etapes=etapes,
        avancement={},
    )


def cocher_etape(instance, cle, fait=True):
    """Coche (ou décoche) UNE étape d'une instance de playbook.

    Écrit uniquement ``avancement`` : le statut reste une décision explicite
    (``terminer_playbook``), jamais un effet de bord d'une case cochée.
    """
    cle = str(cle or '')
    if cle not in instance.cles_etapes:
        raise EtapeInconnue(
            f'Étape « {cle} » inconnue de ce playbook.')
    avancement = dict(instance.avancement or {})
    if fait:
        avancement[cle] = True
    else:
        avancement.pop(cle, None)
    instance.avancement = avancement
    instance.save(update_fields=['avancement', 'updated_at'])
    return instance


def terminer_playbook(instance):
    """Passe l'instance en ``termine`` — refuse tant qu'il reste des étapes.

    Même esprit que NTMIG5 : pas de « déploiement terminé » déclaré au-dessus
    d'une checklist incomplète. L'erreur porte les étapes restantes.
    """
    restantes = [
        etape for etape in (instance.etapes or [])
        if isinstance(etape, dict)
        and not (instance.avancement or {}).get(str(etape.get('cle') or ''))
    ]
    if restantes:
        raise ReconcileBloque(
            'Des étapes du playbook ne sont pas faites : clôture refusée.',
            ecarts=[{'cle': e.get('cle'), 'libelle': e.get('libelle')}
                    for e in restantes])
    instance.statut = instance.Statut.TERMINE
    instance.save(update_fields=['statut', 'updated_at'])
    return instance


# ─────────────────────────────────────────────────────────────────────────
# NTMIG28 — traçabilité des déploiements partenaire. La table vit ici ; la
# FICHE partenaire vit dans ``crm``, donc son compteur miroir est écrit par
# ``crm.services`` (frontière cross-app : jamais ``crm.models`` ici).
# ─────────────────────────────────────────────────────────────────────────


def compter_deploiements_reussis(partenaire_id, company):
    """Nombre de déploiements RÉUSSIS d'un partenaire, scopé société."""
    from .models import DeploiementPartenaire

    return DeploiementPartenaire.objects.filter(
        company=company, partenaire_id=partenaire_id,
        statut=DeploiementPartenaire.Statut.REUSSI).count()


def resynchroniser_compteur_partenaire(deploiement):
    """Réaligne le compteur miroir de la fiche partenaire.

    Recompté à chaque fois plutôt qu'incrémenté : un déploiement repassé de
    ``reussi`` à ``abandonne`` (ou supprimé) doit FAIRE BAISSER le compteur —
    un simple ``+1`` laisserait un historique gonflé que rien ne corrigerait.
    """
    from apps.crm import services as crm_services

    if deploiement.partenaire_id is None:
        return None
    return crm_services.poser_compteur_deploiements(
        deploiement.partenaire_id, deploiement.company,
        compter_deploiements_reussis(
            deploiement.partenaire_id, deploiement.company))
