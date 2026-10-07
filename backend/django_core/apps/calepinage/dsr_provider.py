"""ACAL300 (C-ACAL-016, D-ACAL-14) — fournisseur DSR (loi 09-08) du calepinage.

Enregistré auprès du registre générique ``core.dsr`` (``core`` orchestre sans
importer le calepinage). Le CRM porte l'IDENTITÉ de la personne ; le
calepinage porte des DONNÉES qui la désignent encore : un titre qui recopiait
son nom, ses photos de site, l'épingle GPS de sa maison — et la géométrie
absolue de son toit, qui la LOCALISE à elle seule.

* **export** — les calepinages des leads / clients de la personne (résolus
  par ``crm.selectors``) : ``{id, reference, titre, lead, client, pin,
  nb_photos}``, jamais un prix.
* **effacement** — UNE fonction de scrub, :func:`anonymiser_calepinage`
  (réutilisée par la rétention, ACAL301) : titre vidé (le nom affiché
  retombe sur « Calepinage #N »), photos de site supprimées (fiche, pièce
  jointe ET objet stocké), épingle retirée et géométrie TRANSLATÉE en repère
  LOCAL (mètres relatifs à l'ancienne épingle, D-ACAL-14) — dans le document,
  ses versions et ses variantes ; la ligne de chatter de création perd
  l'ancien titre et une note « Calepinage anonymisé (loi 09-08) » est posée.
  Idempotente : un second passage ne change rien. Le devis lié n'est JAMAIS
  réécrit (règle #4) — son empreinte imprimée divergera, c'est assumé.

``erase_order = 0`` : le calepinage résout la personne PAR l'identité du CRM
(``erase_order = 100``) — il doit passer AVANT que la clé ne disparaisse.
"""
from __future__ import annotations

import copy
import logging

PROVIDER_NAME = 'calepinage'

#: Le repère d'un document anonymisé (schéma ``roof_layout_v2`` › ``repere``).
REPERE_LOCAL = {'type': 'local', 'unite': 'm',
                'motif': 'anonymisation loi 09-08'}

NOTE_ANONYMISATION = 'Calepinage anonymisé (loi 09-08)'
#: Le corps anonymisé de la ligne de chatter de création.
CREATION_ANONYMISEE = 'Calepinage créé'

logger = logging.getLogger(__name__)

__all__ = ['PROVIDER_NAME', 'REPERE_LOCAL', 'anonymiser_calepinage',
           'calepinages_du_sujet', 'export_calepinage', 'erase_calepinage',
           'on_lead_erased', 'register']


def _epingle(document):
    pin = document.get('pin') if isinstance(document, dict) else None
    if not isinstance(pin, dict):
        return None
    from .services.valeurs import nombre

    lat, lng = nombre(pin.get('lat')), nombre(pin.get('lng'))
    if lat is None or lng is None:
        return None
    return {'lat': lat, 'lng': lng}


def _origine_de_repli(document):
    """Sans épingle : le PREMIER sommet de pan (``[lng, lat]``) sert
    d'origine — aucune coordonnée absolue ne doit survivre à l'effacement."""
    from .services.valeurs import nombre

    for zone in document.get('zones') or ():
        sommets = zone.get('vertices') if isinstance(zone, dict) else None
        for sommet in sommets or ():
            if isinstance(sommet, (list, tuple)) and len(sommet) >= 2:
                lng, lat = nombre(sommet[0]), nombre(sommet[1])
                if lng is not None and lat is not None:
                    return {'lat': lat, 'lng': lng}
    return None


def document_anonymise(document, epingle=None):
    """Copie de ``document`` en repère LOCAL, sans épingle — PURE.

    Chaque coordonnée ``[lng, lat]`` des chemins géographiques du document
    (``repere.CHEMINS_TRANSLATES``) devient ``[x_m, y_m]`` relatif à
    l'épingle (la projection SURVIVANTE ``core.calepinage.geo``, C-ACAL-144).
    Un document déjà local, ou sans épingle ni ``epingle`` fournie, n'est pas
    reprojeté (rien d'absolu à quoi le rapporter) : seule l'épingle part.
    """
    if not isinstance(document, dict) or not document:
        return document
    copie = copy.deepcopy(document)
    origine = _epingle(copie) or epingle or _origine_de_repli(copie)
    deja_local = (isinstance(copie.get('repere'), dict)
                  and copie['repere'].get('type') == 'local')
    if origine is not None and not deja_local:
        from core.calepinage.geo import projeteur_local

        from .services.repere import CHEMINS_TRANSLATES, _translater_en_place

        projeter = projeteur_local((origine['lng'], origine['lat']))

        def vers_local(lng, lat):
            return tuple(round(v, 3) for v in projeter((lng, lat)))

        for chemin, (forme, ordre) in CHEMINS_TRANSLATES.items():
            if chemin == 'pin':
                continue
            _translater_en_place(copie, chemin, forme, ordre, vers_local)
        copie['repere'] = dict(REPERE_LOCAL)
    copie.pop('pin', None)
    return copie


def anonymiser_calepinage(calepinage, *, user=None):
    """LE scrub d'un calepinage — idempotent. Rend ``True`` si quelque chose
    a changé, ``False`` sinon."""
    from django.db import transaction

    from apps.records.services import anonymiser_corps_activite

    from .models import CalepinageVariante, CalepinageVersion, PhotoSite
    from .services.journal import noter
    from .services.photos import supprimer_photo_site

    change = False
    epingle = _epingle(getattr(calepinage, 'roof_layout', None))
    with transaction.atomic():
        for photo in (PhotoSite.objects.filter(calepinage=calepinage)
                      .select_related('attachment', 'calepinage')):
            supprimer_photo_site(photo)
            change = True

        champs = []
        if calepinage.titre:
            calepinage.titre = ''
            champs.append('titre')
        document = calepinage.roof_layout
        nouveau = document_anonymise(document)
        if nouveau != document:
            from apps.ventes.services import layout_hash

            calepinage.roof_layout = nouveau
            calepinage.layout_hash = layout_hash(nouveau) or ''
            champs += ['roof_layout', 'layout_hash']
        if champs:
            calepinage.save(update_fields=champs)
            change = True

        for modele in (CalepinageVersion, CalepinageVariante):
            for ligne in modele.objects.filter(calepinage=calepinage):
                apres = document_anonymise(ligne.roof_layout, epingle)
                if apres != ligne.roof_layout:
                    ligne.roof_layout = apres
                    ligne.save(update_fields=['roof_layout'])
                    change = True

        if anonymiser_corps_activite(calepinage, field='calepinage',
                                     kind='creation',
                                     valeur=CREATION_ANONYMISEE):
            change = True
        if change:
            noter(calepinage, NOTE_ANONYMISATION, user=user)
    return change


def calepinages_du_sujet(company, subject_identifier):
    """Les calepinages des leads ET des clients de la personne, bornés
    société — résolus par ``crm.selectors`` (jamais ``apps.crm.models``)."""
    from django.db.models import Q

    from apps.crm.selectors import (
        client_ids_par_identifiant, lead_ids_par_identifiant,
    )

    from .models import Calepinage

    if company is None:
        return Calepinage.objects.none()
    leads = list(lead_ids_par_identifiant(company, subject_identifier))
    clients = list(client_ids_par_identifiant(company, subject_identifier))
    if not leads and not clients:
        return Calepinage.objects.none()
    return (Calepinage.objects.filter(company=company)
            .filter(Q(lead_id__in=leads) | Q(client_id__in=clients))
            .order_by('pk'))


def export_calepinage(company, subject_identifier):
    """L'export des calepinages de la personne (jamais un prix)."""
    from .services.presentation import reference_calepinage

    return {'calepinages': [{
        'id': calepinage.pk,
        'reference': reference_calepinage(calepinage),
        'titre': calepinage.titre,
        'lead': calepinage.lead_id,
        'client': calepinage.client_id,
        'pin': _epingle(calepinage.roof_layout),
        'nb_photos': calepinage.photos_site.count(),
    } for calepinage in calepinages_du_sujet(company, subject_identifier)]}


def erase_calepinage(company, subject_identifier):
    """L'effacement : :func:`anonymiser_calepinage` sur chaque calepinage de
    la personne. Rend ``{'anonymises': n}``."""
    total = 0
    for calepinage in calepinages_du_sujet(company, subject_identifier):
        if anonymiser_calepinage(calepinage):
            total += 1
    return {'anonymises': total}


def on_lead_erased(sender, **kwargs):
    """ACAL301 — un lead CRM est effacé (DSR ou RÉTENTION) : chaque
    calepinage de ce lead reçoit LE scrub (:func:`anonymiser_calepinage`).
    Best-effort journalisé, jamais propagé : l'effacement CRM ne casse
    jamais à cause d'un abonné."""
    from .models import Calepinage

    company = kwargs.get('company')
    lead_id = kwargs.get('crm_lead_id')
    if company is None or not lead_id:
        return
    for calepinage in (Calepinage.objects
                       .filter(company=company, lead_id=lead_id)
                       .order_by('pk')):
        try:
            anonymiser_calepinage(calepinage)
        except Exception:  # noqa: BLE001 — journalisé, jamais propagé
            logger.exception('ACAL301 : calepinage %s non anonymisé '
                             '(lead %s effacé)', calepinage.pk, lead_id)


def register():
    """Enregistre le fournisseur DSR du calepinage (idempotent). ``ready()``."""
    from core import dsr

    dsr.register_dsr_provider(PROVIDER_NAME, export=export_calepinage,
                              erase=erase_calepinage, erase_order=0)

    # ACAL301 — l'abonnement à l'effacement d'un lead (rétention comprise).
    from core.events import lead_erased

    lead_erased.connect(on_lead_erased, dispatch_uid='calepinage_lead_erased')
