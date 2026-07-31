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
    lot.save(update_fields=[
        'source_lignes', 'crees', 'maj', 'erreurs', 'import_job', 'statut',
        'updated_at'])
    return apercu


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
        verrou.save(update_fields=[
            'source_lignes', 'crees', 'maj', 'erreurs', 'import_job',
            'statut', 'derogation_reconcile', 'derogation_motif',
            'derogation_par', 'derogation_at', 'updated_at'])

    lot.refresh_from_db()
    return result


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
