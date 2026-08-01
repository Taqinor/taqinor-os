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
