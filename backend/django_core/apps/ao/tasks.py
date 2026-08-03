"""Tâches à la demande du module Appels d'offres (``apps.ao``) — AOF15.

Enveloppes FINES autour de ``apps.ao.services`` : toute la logique métier reste
testable sans Celery. Les tâches prennent des CLÉS PRIMAIRES, jamais des
instances de modèle (une instance sérialisée puis rejouée après un retry est un
risque de correction ET d'idempotence).

Autodécouvert par ``erp_agentique.celery`` (``autodiscover_tasks()``).
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='ao.generer_echeancier')
def generer_echeancier(appel_offre_id):
    """AOF15 — (re)génère l'échéancier d'un AO. IDEMPOTENT.

    Rejouer la tâche sur un dossier inchangé ne crée rien ; après une
    prorogation, elle DÉCALE l'échéance existante au lieu d'en ajouter une.
    Aucun envoi réseau : la tâche calcule et écrit, rien d'autre.
    """
    from .models import AppelOffre
    from .services import generer_echeancier_ao

    appel_offre = AppelOffre.objects.filter(pk=appel_offre_id).first()
    if appel_offre is None:
        logger.info('ao.generer_echeancier : AO #%s introuvable',
                    appel_offre_id)
        return {'creees': 0, 'mises_a_jour': 0, 'inchangees': 0}
    return generer_echeancier_ao(appel_offre)


# ── AOF153 — production ASYNCHRONE et IDEMPOTENTE du pack ────────────────────
#
# Le pack complet (9 pièces + planches + fusion + ZIP) dépasse largement une
# requête HTTP : il part en tâche de fond via ``core.jobs.submit`` et
# ``BackgroundJob``, jamais dans une file maison.
#
# Deux exigences que l'asynchrone rend NON négociables :
#
# * **Idempotence par empreinte du contexte.** Un double-clic, un rejeu réseau
#   ou un retry Celery ne doivent JAMAIS produire deux packs. La clé
#   d'idempotence est l'empreinte du contexte (AOF111) : une pièce déjà
#   produite POUR CETTE EMPREINTE est reprise telle quelle, pas refabriquée.
#   Le contexte change → l'empreinte change → tout se refait.
# * **Échec PROPRE par pièce.** Une pièce en erreur ne casse pas le dossier :
#   les autres restent intactes, le dossier demeure en constitution et le motif
#   est nommé. L'alternative (tout ou rien) transforme une coquille dans une
#   annexe en régénération complète du pack.
#
# L'orchestrateur ci-dessous est PUR : il reçoit des producteurs et n'en
# connaît aucun. C'est ce qui le rend testable sans base ni Celery.

ETAT_PRODUITE = 'produite'
ETAT_REPRISE = 'reprise'
ETAT_ECHOUEE = 'echouee'


def produire_pack(pieces, *, empreinte_contexte, deja_produites=None,
                  progression=None, journal=None):
    """Produit les pièces d'un pack, une par une, de façon IDEMPOTENTE.

    Args:
        pieces: ``[{'code', 'libelle', 'producteur'}]`` où ``producteur`` est
            un callable sans argument renvoyant l'artefact (octets, clé MinIO,
            ce que l'appelant veut). Ce module ne fabrique rien lui-même.
        empreinte_contexte: clé d'idempotence — l'empreinte du contexte de
            dossier (AOF111).
        deja_produites: ``{code: {'empreinte': …, 'artefact': …}}``, l'état
            déjà en base. Une pièce dont l'empreinte CORRESPOND est reprise
            sans être refabriquée.
        progression: callable ``(faites, total, code)`` — suivi PIÈCE PAR
            PIÈCE (un pourcentage global sans nom de pièce ne dit pas où ça
            coince).
        journal: callable ``(code, etat, detail)`` — trace métier.

    Returns:
        ``{'empreinte', 'total', 'produites', 'reprises', 'echecs',
        'resultats', 'complet'}``. ``complet`` est faux dès qu'une pièce a
        échoué : c'est lui qui interdit de passer le dossier en « prêt ».
    """
    pieces = list(pieces or [])
    deja = dict(deja_produites or {})
    total = len(pieces)
    resultats = []
    produites = reprises = 0
    echecs = []

    for index, piece in enumerate(pieces, start=1):
        code = piece.get('code')
        anterieure = deja.get(code) or {}
        if anterieure.get('empreinte') == empreinte_contexte:
            # Rejeu : l'artefact existant décrit EXACTEMENT ce contexte.
            reprises += 1
            resultats.append({'code': code, 'etat': ETAT_REPRISE,
                              'artefact': anterieure.get('artefact'),
                              'empreinte': empreinte_contexte})
            if journal:
                journal(code, ETAT_REPRISE,
                        'déjà produite pour cette empreinte')
        else:
            producteur = piece.get('producteur')
            if not callable(producteur):
                motif = 'aucun producteur fourni'
                echecs.append({'code': code, 'motif': motif})
                resultats.append({'code': code, 'etat': ETAT_ECHOUEE,
                                  'motif': motif})
                if journal:
                    journal(code, ETAT_ECHOUEE, motif)
            else:
                try:
                    artefact = producteur()
                except Exception as exc:  # une pièce, pas le dossier
                    motif = '{} : {}'.format(type(exc).__name__, exc)
                    echecs.append({'code': code, 'motif': motif})
                    resultats.append({'code': code, 'etat': ETAT_ECHOUEE,
                                      'motif': motif})
                    logger.warning('ao.produire_pack : pièce %s en échec — %s',
                                   code, motif)
                    if journal:
                        journal(code, ETAT_ECHOUEE, motif)
                else:
                    produites += 1
                    resultats.append({'code': code, 'etat': ETAT_PRODUITE,
                                      'artefact': artefact,
                                      'empreinte': empreinte_contexte})
                    if journal:
                        journal(code, ETAT_PRODUITE, '')
        if progression:
            progression(index, total, code)

    return {
        'empreinte': empreinte_contexte,
        'total': total,
        'produites': produites,
        'reprises': reprises,
        'echecs': echecs,
        'resultats': resultats,
        'complet': not echecs and total > 0,
    }


@shared_task(name='ao.produire_pack')
def produire_pack_task(job_id=None, company_id=None, dossier_id=None,
                       **_ignores):
    """Enveloppe Celery : avance le ``BackgroundJob`` pièce par pièce.

    Volontairement FINE — elle ne fabrique rien, elle branche l'orchestrateur
    ci-dessus sur le job de suivi. Le montage des producteurs appartient au
    service de dossier (il connaît les gabarits et les modèles) ; tant que ce
    monteur n'existe pas, la tâche se termine PROPREMENT en le signalant
    plutôt qu'en cassant sur un ImportError dans un worker.
    """
    from core.models import BackgroundJob

    job = BackgroundJob.objects.filter(pk=job_id).first() if job_id else None
    try:
        from .services import producteurs_de_pack
    except ImportError:
        producteurs_de_pack = None
    if producteurs_de_pack is None:
        message = ('ao.produire_pack : aucun monteur de producteurs '
                   '(services.producteurs_de_pack) — rien à produire.')
        logger.info(message)
        if job is not None:
            job.marquer_termine()
        return {'total': 0, 'produites': 0, 'reprises': 0, 'echecs': [],
                'complet': False, 'motif': message}

    pieces, empreinte, deja = producteurs_de_pack(dossier_id)

    def _progression(faites, total, code):
        if job is not None and total:
            job.marquer_progression(int(faites * 100 / total))
        logger.info('ao.produire_pack : %s/%s — %s', faites, total, code)

    rapport = produire_pack(pieces, empreinte_contexte=empreinte,
                            deja_produites=deja, progression=_progression)
    if job is not None:
        if rapport['echecs']:
            job.marquer_echec('; '.join(
                '{} : {}'.format(echec['code'], echec['motif'])
                for echec in rapport['echecs']))
        else:
            job.marquer_termine()
    return {cle: rapport[cle] for cle in
            ('total', 'produites', 'reprises', 'echecs', 'complet')}


@shared_task(name='ao.produire_rentabilite_xlsx')
def produire_rentabilite_xlsx_task(job_id=None, company_id=None,
                                   projet_id=None, **_ignores):
    """AOF160 — produit le classeur DIRECTEUR de rentabilité en tâche de fond.

    Passe en job dès que le classeur dépasse le seuil de confort d'une requête
    HTTP (patron des exports lourds : ``core.jobs.submit`` + ``BackgroundJob``,
    jamais une file maison). La tâche ne calcule RIEN elle-même : elle demande
    au service directeur l'économie du projet, puis délègue l'écriture à
    ``fabrique.rendus.rentabilite_xlsx``.

    Le classeur porte ``visibilite='directeur'`` : il est exclu de tout
    manifeste de dépôt PAR CONSTRUCTION (sommaire AOF139, ZIP AOF151 et bon à
    tirer AOF152 filtrent sur la visibilité). Sa distribution se fait par URL
    signée à durée courte — une clé d'objet devinée ou partagée contournerait
    sinon toute la permission.

    L'ARTEFACT EST DÉPOSÉ, pas jeté (AOF161). La tâche écrivait le classeur
    dans un tampon mémoire puis retournait sa TAILLE : rien n'était conservé,
    donc rien n'était téléchargeable. Les octets partent désormais dans le
    stockage objet par ``apps.records.storage.store_export_result`` (livrable
    de job, clé préfixée par société) et la clé est posée sur le
    ``BackgroundJob`` — c'est elle que l'endpoint directeur relaie.

    Il est DÉLIBÉRÉ que ce livrable ne soit pas une ``records.Attachment`` : la
    liste générique des pièces jointes (``/api/django/records/attachments/``)
    est ouverte à TOUT rôle (``IsAnyRole``) et sert le fichier par son action
    ``download`` — y déposer le coût de revient l'offrirait à un
    non-directeur, c'est-à-dire exactement la fuite que ``ao_rentabilite_voir``
    existe pour fermer.
    """
    import io

    from core.models import BackgroundJob

    from .fabrique.rendus.rentabilite_xlsx import MIME_XLSX, ecrire_classeur

    job = BackgroundJob.objects.filter(pk=job_id).first() if job_id else None
    try:
        from .services_directeur import donnees_du_classeur, economie_du_projet
    except ImportError:
        economie_du_projet = None
    if economie_du_projet is None:
        message = ('ao.produire_rentabilite_xlsx : aucun fournisseur '
                   "d'économie (services_directeur.economie_du_projet) — "
                   'rien à produire.')
        logger.info(message)
        if job is not None:
            job.marquer_termine()
        return {'produit': False, 'motif': message}

    economie, reference = economie_du_projet(projet_id)
    if economie is None:
        message = ("Cet appel d'offres n'a pas d'économie directeur : il n'y "
                   'a aucun coût de revient à mettre en classeur.')
        logger.info('ao.produire_rentabilite_xlsx : %s', message)
        if job is not None:
            job.marquer_echec(message)
        return {'produit': False, 'motif': message}

    try:
        donnees = donnees_du_classeur(economie)
        tampon = io.BytesIO()
        ecrire_classeur(donnees, tampon, reference_dossier=reference)
        octets = tampon.getvalue()
    except Exception as erreur:  # noqa: BLE001 — le job porte le motif.
        message = str(erreur) or erreur.__class__.__name__
        logger.warning('ao.produire_rentabilite_xlsx : %s', message)
        if job is not None:
            job.marquer_echec(message)
        return {'produit': False, 'motif': message}

    cle = ''
    if job is not None:
        from apps.records.storage import store_export_result

        # La clé PORTE le dossier produit (``<job>-ao<id>.xlsx``) : l'endpoint
        # directeur refuse ainsi de servir, sous le nom d'un AO, le classeur
        # d'un AUTRE — un fichier étiqueté faux ne se voit pas à l'usage.
        cle = store_export_result(
            octets, company_id=(company_id or job.company_id),
            job_id=f'{job.pk}-ao{economie.appel_offre_id}',
            ext='xlsx', content_type=MIME_XLSX)
        job.marquer_termine(cle)
    return {'produit': True, 'octets': len(octets), 'visibilite': 'directeur',
            'cle': cle}


# AOF61 — le calepinage lourd vit dans son propre module (``calepinage_tasks``)
# pour ne pas grossir ce fichier partagé par trois lanes. L'autodécouverte
# Celery n'importe QUE ``<app>.tasks`` : ce ré-export est ce qui enregistre la
# tâche ``ao.calculer_calepinage`` auprès du worker.
from .calepinage_tasks import calculer_calepinage  # noqa: E402,F401

# AOF71 — même raison pour l'ingestion d'un support de plan (rastérisation PDF
# / normalisation d'image) : le corps vit dans ``ingestion_tasks``, ce
# ré-export enregistre ``ao.ingerer_plan`` auprès du worker.
from .ingestion_tasks import ingerer_plan  # noqa: E402,F401
