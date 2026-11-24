"""ADEV139 — ventes RELANCE la conception quand une entrée change (D-ACAL-97).

Abonnés de ``core.events`` (câblés par ``VentesConfig.ready``) :

* ``lead_entrees_modifiees`` (crm, ALEA68) — une colonne d'entrée du lead a
  changé ;
* ``pose_enregistree`` (calepinage, ACAL2011) — une pose d'empreinte nouvelle
  est enregistrée.

Aucun calcul dans la requête : l'abonné met UNE tâche ``ventes.
relancer_conception`` en file (``tasks.task_relancer_conception``) et rend la
main ; la tâche appelle l'écrivain unique ``conception/service.py::relancer``
(empreinte égale ⇒ rien n'est écrit).

DÉDUPLICATION par ``(porteur, empreinte)`` — patron de
``calepinage/services/simulation_auto.py`` (marqueur de cache posé au
lancement) :

* une tâche EN FILE (pas encore partie) pour le porteur ⇒ aucune seconde : elle
  relit le lead à son départ, donc calcule le dernier état ; les champs changés
  s'ajoutent à son déclencheur (premier « avant », dernier « après ») — dix
  modifications rapprochées, un calcul ;
* une tâche EN COURS pour la même empreinte d'événement ⇒ rien ; pour une autre,
  une tâche suivante est mise en file (elle verra la nouvelle valeur) ;
* un import de dix leads ⇒ dix porteurs, dix tâches : une par lead.

``core.jobs.submit`` n'est PAS utilisé : son ``BackgroundJob`` exige un
utilisateur, et un événement de fiche n'en porte aucun (la tâche du moteur
écrit avec ``calcule_par = None``) — la file est la file Celery existante, la
même que celle de ``submit``. Un échec (courtier, calcul) n'empêche jamais
l'enregistrement de la fiche : journalisé, jamais levé ; le filet d'empreinte
de la lecture (ADEV140) rattrape un événement perdu.
"""
import hashlib
import json
import logging
import uuid

from core.events import lead_entrees_modifiees, pose_enregistree

logger = logging.getLogger(__name__)

#: Durée de vie du marqueur (s) : au-delà, un marqueur orphelin (tâche
#: perdue) n'empêche plus une nouvelle relance.
DUREE_MARQUEUR_S = 600
#: Délai avant départ (s) : les enregistrements rapprochés s'y regroupent.
DELAI_REGROUPEMENT_S = 5
EN_FILE, EN_COURS = 'en_file', 'en_cours'
#: Origines nées d'un geste sur la fiche ou la pose (dites au chatter).
ORIGINES_GESTE = ('lead_entrees_modifiees', 'pose_enregistree')


def cle_marqueur(lead_id=None, calepinage_id=None):
    """La clé du porteur : le lead, sinon le calepinage sans lead."""
    if lead_id:
        return 'ventes:conception:relance:lead:%s' % lead_id
    return 'ventes:conception:relance:calepinage:%s' % calepinage_id


def _cle(company_id, nom):
    from core.cache import tenant_key
    return tenant_key(company_id, nom)


def _empreinte_evenement(champs, empreinte_pose):
    canonique = json.dumps({'champs': [(c.get('champ'), c.get('apres')) for c in champs or []],
                            'pose': empreinte_pose}, sort_keys=True, default=str)
    return hashlib.sha256(canonique.encode('utf-8')).hexdigest()


def _fusionner(anciens, nouveaux):
    """Premier « avant », dernier « après » par champ, dans l'ordre d'arrivée."""
    par_champ = {c['champ']: dict(c) for c in anciens or []}
    for champ in nouveaux or []:
        if champ['champ'] in par_champ:
            par_champ[champ['champ']]['apres'] = champ.get('apres')
        else:
            par_champ[champ['champ']] = dict(champ)
    return list(par_champ.values())


def mettre_en_file(company_id, *, lead_id=None, calepinage_id=None, origine, champs=None,
                   empreinte_pose=None):
    """UNE tâche de relance par ``(porteur, empreinte)`` ; rend ``'lancee'``,
    ``'deja_en_file'`` ou ``'echec'``. Ne lève jamais."""
    from django.core.cache import cache

    if not company_id or not (lead_id or calepinage_id):
        return 'echec'
    try:
        cle = _cle(company_id, cle_marqueur(lead_id, calepinage_id))
        empreinte = _empreinte_evenement(champs, empreinte_pose)
        jeton = uuid.uuid4().hex
        marqueur = {'etat': EN_FILE, 'jeton': jeton, 'empreinte': empreinte, 'origine': origine,
                    'champs': list(champs or []), 'empreinte_pose': empreinte_pose}
        if not cache.add(cle, marqueur, DUREE_MARQUEUR_S):
            present = cache.get(cle) or {}
            if present.get('etat') == EN_FILE:
                # Relecture E3 M3 — un geste (fiche, pose) regroupé dans une
                # relance muette (filet…) la rend parlante au chatter.
                origine_fusionnee = origine if origine in ORIGINES_GESTE else present.get('origine')
                present.update(champs=_fusionner(present.get('champs'), champs), empreinte=empreinte,
                               origine=origine_fusionnee,
                               empreinte_pose=(empreinte_pose if empreinte_pose is not None
                                               else present.get('empreinte_pose')))
                cache.set(cle, present, DUREE_MARQUEUR_S)
                return 'deja_en_file'
            if present.get('etat') == EN_COURS and present.get('empreinte') == empreinte:
                return 'deja_en_file'
            cache.set(cle, marqueur, DUREE_MARQUEUR_S)
        from apps.ventes.tasks import task_relancer_conception
        try:
            task_relancer_conception.apply_async(kwargs={
                'company_id': company_id, 'lead_id': lead_id, 'calepinage_id': calepinage_id,
                'origine': origine, 'champs': list(champs or []), 'empreinte_pose': empreinte_pose,
                'jeton': jeton}, countdown=DELAI_REGROUPEMENT_S, retry=False)
        except Exception:
            cache.delete(cle)  # une prochaine modification retentera
            raise
        return 'lancee'
    except Exception:  # noqa: BLE001 — la fiche est enregistrée, le filet rattrape (D-ENF22-BLE001)
        logger.warning('ADEV139 : relance de la conception non mise en file (lead #%s, calepinage #%s)',
                       lead_id, calepinage_id, exc_info=True)
        return 'echec'


def relance_en_file(company_id, *, lead_id=None, calepinage_id=None):
    """Une relance est-elle en file ou en cours pour ce porteur ? (lecture)."""
    from django.core.cache import cache
    try:
        return bool(cache.get(_cle(company_id, cle_marqueur(lead_id, calepinage_id))))
    except Exception:  # noqa: BLE001 — cache indisponible : rien en file (D-ENF22-BLE001)
        return False


def oublier_relance(company_id, *, lead_id=None, calepinage_id=None):
    """Relecture E3 B1 — le marqueur du porteur retiré (lead effacé) : une
    tâche déjà en file ne le retrouve plus, ses champs regroupés (valeurs
    effacées) partent avec lui. Ne lève jamais."""
    from django.core.cache import cache
    try:
        cache.delete(_cle(company_id, cle_marqueur(lead_id, calepinage_id)))
    except Exception:  # noqa: BLE001 — cache indisponible : le marqueur expire seul (D-ENF22-BLE001)
        logger.warning('ADEV139 : marqueur du lead #%s non retiré', lead_id, exc_info=True)


def _prendre(cle, jeton):
    """La tâche part : son marqueur passe « en cours » ; rend les champs et la
    pose regroupés (``None`` si le marqueur a disparu ou est celui d'une autre)."""
    from django.core.cache import cache

    marqueur = cache.get(cle)
    if not isinstance(marqueur, dict) or marqueur.get('jeton') != jeton:
        return None
    marqueur['etat'] = EN_COURS
    cache.set(cle, marqueur, DUREE_MARQUEUR_S)
    return marqueur


def _liberer(cle, jeton):
    """Fin de la tâche : son marqueur part, sauf si une suivante l'a remplacé."""
    from django.core.cache import cache

    marqueur = cache.get(cle)
    if isinstance(marqueur, dict) and marqueur.get('jeton') == jeton and marqueur.get('etat') == EN_COURS:
        cache.delete(cle)


def _pose_servie(company, lead_id, calepinage_id, empreinte_pose):
    """``(toit, calepinage_id)`` : la pose de l'événement, sinon celle que la
    version courante a utilisée (une fiche modifiée ne fait pas oublier le toit)."""
    from types import SimpleNamespace

    from apps.ventes.models import ConceptionLead

    if empreinte_pose is None:
        filtre = {'lead_id': lead_id} if lead_id else {'lead__isnull': True, 'calepinage_id': calepinage_id}
        courante = ConceptionLead.objects.filter(company=company, courante=True, **filtre).first()
        empreinte_pose = courante.empreinte_pose if courante is not None else ''
        calepinage_id = calepinage_id or (courante.calepinage_id if courante is not None else None)
    toit = SimpleNamespace(empreinte=empreinte_pose, plafond_panneaux=None) if empreinte_pose else None
    return toit, calepinage_id


def executer_relance(company_id, *, lead_id=None, calepinage_id=None, origine, champs=None,
                     empreinte_pose=None, jeton=None):
    """Corps de ``tasks.task_relancer_conception`` : relit le porteur (de la
    société de l'événement seulement) et appelle ``relancer``. Rend ``{version,
    ecrite}`` ou ``None`` (porteur disparu, échec). Ne lève jamais."""
    from authentication.models import Company

    from apps.crm.selectors import get_company_lead, lead_efface
    from apps.ventes.conception.service import relancer

    cle = _cle(company_id, cle_marqueur(lead_id, calepinage_id))
    try:
        marqueur = _prendre(cle, jeton) if jeton else None
        if marqueur is not None:
            origine, champs = marqueur.get('origine') or origine, marqueur.get('champs') or []
            empreinte_pose = marqueur.get('empreinte_pose', empreinte_pose)
        company = Company.objects.filter(pk=company_id).first()
        lead = get_company_lead(company, lead_id) if company is not None and lead_id else None
        if company is None or (lead_id and lead is None) or lead_efface(lead):
            return None  # porteur disparu ou effacé (loi 09-08, relecture E3 B1) : rien
        toit, calepinage_id = _pose_servie(company, lead_id, calepinage_id, empreinte_pose)
        relance = relancer(lead, company=company, declencheur={'origine': origine, 'champs': champs or []},
                           toit=toit, calepinage_id=calepinage_id)
        return {'version': getattr(relance.conception, 'version', None), 'ecrite': relance.ecrite}
    except Exception:  # noqa: BLE001 — une relance ratée n'écrit rien ; le filet la rejoue (D-ENF22-BLE001)
        logger.exception('ADEV139 : relance de la conception en échec (lead #%s, calepinage #%s)',
                         lead_id, calepinage_id)
        return None
    finally:
        if jeton:
            try:
                _liberer(cle, jeton)
            except Exception:  # noqa: BLE001 — cache indisponible : le marqueur expire seul (D-ENF22-BLE001)
                logger.debug('ADEV139 : marqueur non libéré', exc_info=True)


def _sur_entrees_modifiees(sender, company_id=None, lead_id=None, champs=None, **kwargs):
    mettre_en_file(company_id, lead_id=lead_id, origine='lead_entrees_modifiees', champs=champs or [])


def _sur_pose_enregistree(sender, company_id=None, calepinage_id=None, lead_id=None,
                          empreinte_pose=None, **kwargs):
    mettre_en_file(company_id, lead_id=lead_id, calepinage_id=calepinage_id, origine='pose_enregistree',
                   empreinte_pose=empreinte_pose or '')


lead_entrees_modifiees.connect(_sur_entrees_modifiees, dispatch_uid='ventes_relancer_conception_lead')
pose_enregistree.connect(_sur_pose_enregistree, dispatch_uid='ventes_relancer_conception_pose')
