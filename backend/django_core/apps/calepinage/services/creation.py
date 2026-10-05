"""CAL11 — les trois portes de création d'un calepinage.

TROIS PORTES, UN SEUL OBJET
---------------------------
* ``obtenir_ou_creer_pour_devis`` — la PARITÉ CRM. Le geste « Concevoir la
  toiture (3D) » d'un devis doit retomber sur LE MÊME calepinage à chaque
  appel : le service est IDEMPOTENT et reprend la conception déjà portée par
  le devis (``roof_layout`` / ``layout_hash``).
* ``creer_pour_lead`` et ``creer_pour_client`` — les portes du module
  AUTONOME : on choisit un lead ou un client, et on conçoit sa toiture, même
  s'il n'existe aucun devis. Un calepinage sans devis est un objet de
  première classe.

CE QUE CE MODULE NE FAIT JAMAIS
-------------------------------
* il n'importe AUCUN modèle de ``crm`` ni de ``ventes`` : le lead et le
  client sont résolus par ``apps.crm.selectors`` (``get_company_lead`` /
  ``get_company_client``), le devis par ``apps.ventes.selectors``
  (``get_devis_by_pk``, dont l'appelant vérifie la société — c'est fait ici) ;
* il n'écrit JAMAIS un statut de devis (règle #4 : le moteur de devis ne fait
  que RENDRE) ;
* il ne lit JAMAIS la société d'un corps de requête : ``company`` et l'auteur
  sont posés par l'appelant côté serveur.

ACAL182 — UNE PORTE DE CRÉATION SUR UN LEAD (D-ACAL-12)
--------------------------------------------------------
Toute porte qui crée un calepinage pour un LEAD (``POST calepinages/``,
``depuis-lead``, ``depuis-modele`` sans modèle, la reprise du tracé public)
passe par ``ouvrir_ou_creer_pour_lead`` : sous un verrou consultatif
PostgreSQL (``_verrou_creation``, pris AVANT la relecture), elle rend le
calepinage OUVERT du lead s'il existe (``selectors.calepinage_ouvert_du_lead``)
et n'en crée un — chatter CREATION, client du lead, même titre de repli —
que sinon. UN calepinage ouvert par lead : deux clics simultanés n'en créent
jamais deux. ``obtenir_ou_creer_pour_devis`` prend le MÊME verrou (le lead
du devis).
"""
from __future__ import annotations

import contextlib
import hashlib

from .journal import journaliser_creation


class CreationRefusee(ValueError):
    """Refus métier de création, message français, champ fautif nommé."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def _message_deja_ouvert(existant):
    """ACAL182 — le refus « un seul calepinage ouvert par lead » (D-ACAL-12),
    qui NOMME l'existant pour qu'on l'ouvre (contrat
    ``calepinage_creation_conflit.json``)."""
    titre = (getattr(existant, 'titre', '') or '').strip()
    etiquette = f'« {titre} », #{existant.pk}' if titre else f'#{existant.pk}'
    return (f'Ce lead a déjà un calepinage ouvert ({etiquette}) : '
            'ouvrez-le, ou créez une variante.')


#: ACAL295 — le 409 quand l'existant est HORS de la vue de l'appelant (vue
#: restreinte au responsable) : ni identifiant, ni référence, ni nom.
MESSAGE_HORS_VUE = ('Ce lead a déjà un calepinage ouvert confié à un autre '
                    'responsable : demandez-lui de vous le confier.')


def _visible(calepinage, user):
    from ..selectors import calepinages_visibles

    return calepinages_visibles(user, inclure_archives=True).filter(
        pk=calepinage.pk).exists()


def corps_conflit(existant, user=None):
    """Le corps 409 publié par les portes qui refusent un second ouvert.

    ACAL295 — ``user`` donné et l'existant hors de SA vue
    (``selectors.calepinages_visibles``) ⇒ ``{detail}`` SANS identifiant,
    référence ni nom : l'unicité reste tenue (D-ACAL-12), rien ne fuit.
    """
    if user is not None and not _visible(existant, user):
        return {'detail': MESSAGE_HORS_VUE}
    return {'lead': _message_deja_ouvert(existant),
            'calepinage_existant': existant.pk}


@contextlib.contextmanager
def _verrou_creation(company_id, lead_id):
    """ACAL182 — sérialise les créations visant le MÊME (société, lead).

    Verrou consultatif PostgreSQL porté par la transaction
    (``pg_advisory_xact_lock``, patron de ``apps.crm.services`` CRX24) : il ne
    bloque aucune ligne et se libère seul à la fin de la transaction, même en
    cas d'erreur. À prendre DANS ``transaction.atomic()`` et AVANT la
    relecture de l'existant. Sans lead, ou sur un moteur sans verrou
    consultatif, no-op.
    """
    from django.db import connection

    if not company_id or not lead_id or connection.vendor != 'postgresql':
        yield False
        return
    empreinte = hashlib.blake2b(
        f'calepinage.creation:{company_id}:{lead_id}'.encode('utf-8'),
        digest_size=8).digest()
    cle = int.from_bytes(empreinte, 'big', signed=True)
    with connection.cursor() as curseur:
        curseur.execute('SELECT pg_advisory_xact_lock(%s)', [cle])
    yield True


def ouvrir_ou_creer_pour_lead(lead_id, company, *, user=None, titre='',
                              preset_id=None, responsable=None):
    """ACAL182 — LE calepinage ouvert de ce lead, ou un neuf (D-ACAL-12).

    Returns:
        ``(calepinage, cree)`` — ``cree`` vaut ``False`` quand le lead avait
        déjà un calepinage OUVERT (non archivé) : rien n'est créé, rien n'est
        modifié, et c'est à la porte de décider (``depuis-lead`` l'ouvre,
        les autres répondent 409 avec ``corps_conflit``).

    Raises:
        CreationRefusee: lead absent ou d'une autre société (même message),
            jeu de réglages inconnu, responsable d'une autre société.
    """
    from django.db import transaction

    from ..selectors import calepinage_ouvert_du_lead

    _exiger_societe(company)
    with transaction.atomic():
        with _verrou_creation(company.pk, lead_id):
            existant = calepinage_ouvert_du_lead(company, lead_id)
            if existant is not None:
                return existant, False
            calepinage = creer_pour_lead(
                lead_id, company, user=user, titre=titre,
                preset_id=preset_id, responsable=responsable)
    return calepinage, True


def _exiger_societe(company):
    if company is None:
        raise CreationRefusee(
            "Un calepinage est toujours rattaché à une société : aucune "
            "société n'a été fournie.", champ='company')


def obtenir_ou_creer_pour_devis(devis_id, company, *, user=None, titre='',
                                preset_id=None):
    """Le calepinage de ce devis — le même à chaque appel (IDEMPOTENT).

    CALX351 — ``preset_id`` (optionnel) désigne un jeu de réglages société
    (``services/presets.py``) appliqué aux pans du document de DÉPART, à la
    création seulement : un calepinage déjà existant n'est jamais retouché.
    Absent ⇒ comportement d'aujourd'hui, strictement identique.

    Returns:
        ``(calepinage, cree)`` — ``cree`` vaut ``True`` seulement au premier
        appel.

    Raises:
        CreationRefusee: devis absent, ou appartenant à une AUTRE société
            (rien n'est créé, et l'appelant n'apprend rien de son existence) ;
            jeu de réglages inconnu (``preset_id``).
    """
    from django.db import IntegrityError, transaction

    from apps.ventes.selectors import get_devis_by_pk

    from ..models import Calepinage
    from ..selectors import calepinage_du_devis

    _exiger_societe(company)
    jeu = _jeu_de_reglages(company, preset_id)
    if not devis_id:
        raise CreationRefusee(
            "Aucun devis n'a été indiqué : impossible de retrouver ou de "
            "créer son calepinage.", champ='devis')

    devis = get_devis_by_pk(devis_id)
    if devis is None or devis.company_id != company.pk:
        raise CreationRefusee(
            f"Devis introuvable (#{devis_id}).", champ='devis')

    existant = calepinage_du_devis(devis_id, company)
    if existant is not None:
        return existant, False

    roof_layout = getattr(devis, 'roof_layout', None)
    empreinte = getattr(devis, 'layout_hash', None) or ''
    regles = 0
    if jeu is not None:
        roof_layout, regles = _layout_regle(roof_layout, jeu)
        if regles:
            from apps.ventes.services import layout_hash

            empreinte = layout_hash(roof_layout) or ''

    with transaction.atomic(), _verrou_creation(
            company.pk, getattr(devis, 'lead_id', None)):
        # Re-lecture DANS la transaction, SOUS le verrou du lead (ACAL182) :
        # deux clics simultanés sur « Concevoir la toiture » ne doivent pas
        # produire deux calepinages.
        existant = calepinage_du_devis(devis_id, company)
        if existant is not None:
            return existant, False
        try:
            with transaction.atomic():
                calepinage = Calepinage.objects.create(
                    company=company,
                    devis=devis,
                    client_id=getattr(devis, 'client_id', None),
                    lead_id=getattr(devis, 'lead_id', None),
                    titre=titre or _titre_du_devis(devis),
                    roof_layout=roof_layout,
                    layout_hash=empreinte,
                    roof_image=getattr(devis, 'roof_image', None) or '',
                    cree_par=user,
                )
        except IntegrityError:
            # ACAL33 — course perdue : la contrainte ``calepinage_un_par_devis``
            # a gardé le calepinage du clic gagnant ; on le rend tel quel.
            existant = calepinage_du_devis(devis_id, company)
            if existant is None:
                raise
            return existant, False
    # CAL26 — la première ligne du chatter, par la primitive `records`.
    journaliser_creation(calepinage, user=user)
    _noter_jeu(calepinage, jeu, regles, user=user)
    return calepinage, True


def _titre_du_devis(devis):
    """Un titre lisible, dérivé du devis — jamais un prénom codé en dur."""
    reference = (getattr(devis, 'reference', '') or '').strip()
    return f'Calepinage {reference}'.strip() if reference else ''


def creer_pour_lead(lead_id, company, *, user=None, titre='',
                    preset_id=None, responsable=None):
    """Crée un calepinage sur un LEAD (porte autonome du module).

    CALX351 — ``preset_id`` : voir ``obtenir_ou_creer_pour_devis``. Un
    calepinage neuf n'a encore aucun pan : le jeu est VALIDÉ et son choix
    noté au chatter, rien n'est inventé dans un document vide.

    ACAL182 — les portes de l'écran passent par ``ouvrir_ou_creer_pour_lead``
    (verrou + un seul ouvert par lead) ; ``responsable`` (optionnel) doit
    être un compte de la MÊME société.

    Raises:
        CreationRefusee: lead absent ou d'une autre société — rien n'est
            créé ; jeu de réglages inconnu (``preset_id``).
    """
    from apps.crm.selectors import get_company_lead

    from ..models import Calepinage

    _exiger_societe(company)
    jeu = _jeu_de_reglages(company, preset_id)
    if not lead_id:
        raise CreationRefusee(
            "Aucun lead n'a été indiqué : choisissez le lead dont vous "
            "concevez la toiture.", champ='lead')

    lead = get_company_lead(company, lead_id)
    if lead is None:
        raise CreationRefusee(
            f"Lead introuvable (#{lead_id}).", champ='lead')
    _exiger_responsable(company, responsable)

    calepinage = Calepinage.objects.create(
        company=company,
        lead_id=lead.pk,
        client_id=getattr(lead, 'client_id', None),
        titre=titre or _titre_depuis(getattr(lead, 'nom', '')),
        cree_par=user,
        responsable=responsable,
    )
    journaliser_creation(calepinage, user=user)  # CAL26
    _noter_jeu(calepinage, jeu, 0, user=user)
    return calepinage


def creer_pour_client(client_id, company, *, user=None, titre='',
                      preset_id=None, responsable=None):
    """Crée un calepinage sur un CLIENT (porte autonome du module).

    CALX351 — ``preset_id`` : voir ``creer_pour_lead``.

    Raises:
        CreationRefusee: client absent ou d'une autre société — rien n'est
            créé ; jeu de réglages inconnu (``preset_id``).
    """
    from apps.crm.selectors import get_company_client

    from ..models import Calepinage

    _exiger_societe(company)
    jeu = _jeu_de_reglages(company, preset_id)
    if not client_id:
        raise CreationRefusee(
            "Aucun client n'a été indiqué : choisissez le client dont vous "
            "concevez la toiture.", champ='client')

    client = get_company_client(company, client_id)
    if client is None:
        raise CreationRefusee(
            f"Client introuvable (#{client_id}).", champ='client')
    _exiger_responsable(company, responsable)

    calepinage = Calepinage.objects.create(
        company=company,
        client_id=client.pk,
        titre=titre or _titre_depuis(getattr(client, 'nom', '')),
        cree_par=user,
        responsable=responsable,
    )
    journaliser_creation(calepinage, user=user)  # CAL26
    _noter_jeu(calepinage, jeu, 0, user=user)
    return calepinage


def _exiger_responsable(company, responsable):
    """ACAL182 — un responsable choisi à la création est de la MÊME société
    (refus nommé ``responsable``, sans jamais nommer le compte étranger)."""
    if responsable is None:
        return
    if getattr(responsable, 'company_id', None) != company.pk:
        raise CreationRefusee(
            'Responsable introuvable dans votre société.',
            champ='responsable')


def _titre_depuis(nom):
    """« Calepinage <nom> » — dérivé de la donnée, jamais d'un nom figé."""
    nom = (nom or '').strip()
    return f'Calepinage {nom}'.strip() if nom else ''


# ── CALX351 — partir d'un MODÈLE et d'un JEU DE RÉGLAGES société ────────────
#
# Les trois portes ci-dessus acceptent un ``preset_id`` optionnel : un jeu
# MAISON de la section ``presets`` (``services/presets.py``, CAL197), appliqué
# aux pans du document de départ par ``services/gabarits.py::
# appliquer_gabarit`` — le SEUL applicateur de réglages de pose du module :
# il ne touche que les clés de pan déjà définies par le contrat v2 (type de
# toit, pente, azimut…) et JAMAIS la géométrie. ``preset_id`` absent ⇒ AUCUNE
# lecture de réglage, création strictement identique à aujourd'hui (D12).

#: Les entrées de la section ``presets`` qui ne sont PAS un jeu de réglages
#: nommé : la liste des jeux elle-même (CAL197) et le catalogue de kits
#: (SOLMVP15). Même liste que ``PRESETS_RESERVES`` de ``Bibliotheque.jsx``.
ENTREES_RESERVEES = ('jeux', 'kits')


def _jeux_disponibles(company):
    """Les jeux de réglages société qu'on peut choisir à la création.

    DEUX formes coexistent dans la section ``presets`` et les deux sont
    offertes : la liste ``jeux`` (``[{id, nom, …}]``, ``services/presets.py``)
    et les PRÉRÉGLAGES NOMMÉS édités par la bibliothèque (``{<nom>: {…,
    source}}``, CALX43) — un préréglage nommé a pour ``id`` son nom. Les
    interrupteurs (booléens : feu vert, approbation exigée) n'en sont pas.
    """
    from ..selectors import parametres_de_societe

    section = parametres_de_societe(company).get('presets') or {}
    jeux = [jeu for jeu in (section.get('jeux') or [])
            if isinstance(jeu, dict) and str(jeu.get('id') or '').strip()]
    for cle, valeur in section.items():
        if cle in ENTREES_RESERVEES or not isinstance(valeur, dict):
            continue
        jeux.append(dict(valeur, id=cle, nom=valeur.get('nom') or cle))
    return jeux


def _jeu_de_reglages(company, preset_id):
    """Le jeu ``preset_id`` de la société, ``None`` s'il n'est pas demandé —
    refus nommant ``preset_id`` s'il est inconnu."""
    if preset_id in (None, ''):
        return None
    demande = str(preset_id).strip()
    for jeu in _jeux_disponibles(company):
        if str(jeu.get('id') or '').strip() == demande:
            return jeu
    raise CreationRefusee(
        f"Jeu de réglages inconnu : « {demande} » — choisissez l'un des jeux "
        "enregistrés dans les réglages de la société.", champ='preset_id')


def _layout_regle(roof_layout, jeu):
    """``(copie du document, nombre de pans réglés)`` — l'original intact."""
    import copy

    from .gabarits import appliquer_gabarit

    if not isinstance(roof_layout, dict):
        return roof_layout, 0
    document = copy.deepcopy(roof_layout)
    zones = document.get('zones')
    if not isinstance(zones, list):
        return document, 0
    regles = 0
    for rang, zone in enumerate(zones):
        if not isinstance(zone, dict):
            continue
        reglee, _regles_moteur = appliquer_gabarit(jeu, zone)
        if reglee != zone:
            regles += 1
        zones[rang] = reglee
    return document, regles


def _noter_jeu(calepinage, jeu, regles, *, user=None):
    """Le choix du jeu au chatter — rien quand aucun jeu n'est demandé."""
    if jeu is None:
        return
    from .journal import noter

    nom = str(jeu.get('nom') or jeu.get('id') or '').strip()
    if regles:
        texte = (f"Jeu de réglages « {nom} » appliqué à {regles} pan(s) du "
                 "document de départ.")
    else:
        texte = (f"Jeu de réglages « {nom} » retenu à la création : aucun pan "
                 "du document de départ n'en a été modifié.")
    noter(calepinage, texte, user=user)


def demarrer_depuis_modele(modele, company, *, user=None, lead_id=None,
                           client_id=None, devis_id=None, titre='',
                           preset_id=None):
    """CALX351 — un calepinage NEUF depuis un MODÈLE, sur un lead, un client
    OU un devis, avec un jeu de réglages optionnel.

    La copie reste le service UNIQUE ``services.modeles.creer_depuis_modele``
    (qui appelle ``services.variantes.dupliquer``, CAL14) : aucun troisième
    chemin de copie. Un ``devis_id`` rattache la copie à ce devis (son lead et
    son client en sont repris) ; rien n'est écrit si le devis, le jeu ou le
    rattachement est refusé.

    Raises:
        CreationRefusee: jeu inconnu (``preset_id``), devis introuvable
            (``devis_id``).
        services.modeles.ModeleInvalide: modèle non marqué, rattachement
            absent ou étranger (champ nommé par le service).
    """
    from django.db import transaction

    from apps.ventes.selectors import get_devis_by_pk

    from .modeles import creer_depuis_modele

    _exiger_societe(company)
    jeu = _jeu_de_reglages(company, preset_id)
    devis = None
    if devis_id:
        devis = get_devis_by_pk(devis_id)
        if devis is None or devis.company_id != company.pk:
            raise CreationRefusee(f"Devis introuvable (#{devis_id}).",
                                  champ='devis_id')
        # ACAL33 — un devis déjà rattaché est refusé AVANT toute copie : la
        # base n'admet qu'un calepinage par devis, et le refus nomme le
        # calepinage qui le tient.
        from ..selectors import calepinage_du_devis
        from .liens import _message_deja_lie

        deja = calepinage_du_devis(devis.pk, company)
        if deja is not None:
            raise CreationRefusee(_message_deja_lie(devis, deja),
                                  champ='devis_id')
        lead_id = getattr(devis, 'lead_id', None) or lead_id
        client_id = getattr(devis, 'client_id', None) or client_id

    with transaction.atomic():
        copie = creer_depuis_modele(modele, user=user, lead_id=lead_id,
                                    client_id=client_id, titre=titre)
        if devis is not None:
            # ACAL33 — le SEUL écrivain de ``Calepinage.devis`` ; un refus
            # (course perdue) annule la copie entière.
            from .liens import LiaisonRefusee, lier_devis

            try:
                lier_devis(copie, devis.pk, user=user)
            except LiaisonRefusee as refus:
                raise CreationRefusee(str(refus), champ='devis_id') from None
    champs = []
    regles = 0
    if jeu is not None:
        document, regles = _layout_regle(copie.roof_layout, jeu)
        if regles:
            from apps.ventes.services import layout_hash

            copie.roof_layout = document
            copie.layout_hash = layout_hash(document) or ''
            champs += ['roof_layout', 'layout_hash']
    if champs:
        copie.save(update_fields=champs + ['updated_at'])
    _noter_jeu(copie, jeu, regles, user=user)
    return copie
