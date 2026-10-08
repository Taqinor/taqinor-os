"""NTGRC1 — fournisseur DSR (loi 09-08 / RGPD) des Ventes.

Enregistré auprès du registre générique ``core.dsr`` (``core`` orchestre sans
importer les Ventes ; les Ventes lisent leurs PROPRES modèles). Le CRM porte
l'identité de la personne ; les Ventes portent ses DOCUMENTS et la
CORRESPONDANCE qui s'y rattache — c'est cela que ce fournisseur expose et
pseudonymise.

* **export** — les documents commerciaux de la personne (devis : référence,
  statut, dates, option retenue) et le décompte de la correspondance email
  rattachée. Jamais de prix d'achat ni de marge (règle du dépôt).
* **effacement** — PSEUDONYMISE ce que les Ventes détiennent EN PROPRE :
  ``Devis.accepte_par_nom`` (nom de la personne qui a accepté) et les adresses
  + le corps des ``EmailLog`` échangés avec elle. Les AGRÉGATS COMPTABLES sont
  intégralement CONSERVÉS : aucune ligne n'est supprimée, aucun montant,
  aucune référence ni aucun statut n'est touché — le dossier reste cohérent.
  ``DevisSignature`` (QJ10) n'est JAMAIS modifiée : c'est une preuve de
  signature électronique immuable au titre de la loi 53-05, conservée au même
  titre que les pièces comptables ; le motif est renvoyé dans le compte-rendu.

``subject_identifier`` = un email ou un téléphone. Tout est borné par
``company`` (multi-tenant). Le CRM reste résolu par FK déclarée en CHAÎNE
(``'crm.Client'``) : aucun import de ``apps.crm.models``.
"""
from __future__ import annotations

PROVIDER_NAME = 'ventes'

ANONYME = 'Anonymisé'

MOTIF_SIGNATURE = (
    "Les enregistrements de signature électronique (loi 53-05) et les pièces "
    "comptables sont conservés : ils font foi et relèvent d'une obligation "
    "légale de conservation. Seules les données de contact et de "
    "correspondance détenues par les Ventes ont été pseudonymisées."
)


def _clients_ids(company, subject_identifier):
    """Ids des ``crm.Client`` de la société correspondant à la personne.

    Résolution par le SELECTOR du CRM (frontière cross-app respectée) — aucun
    import de ``apps.crm.models``.
    """
    from apps.crm.selectors import client_ids_par_identifiant

    return list(client_ids_par_identifiant(company, subject_identifier))


def _documents(company, subject_identifier):
    """(devis_qs, emails_qs) rattachés à la personne, bornés à la société."""
    from django.db.models import Q

    from .models import Devis, EmailLog

    client_ids = _clients_ids(company, subject_identifier)
    ident = (subject_identifier or '').strip()

    devis = Devis.objects.filter(company=company, client_id__in=client_ids)

    email_q = Q(client_id__in=client_ids)
    if ident and '@' in ident:
        email_q |= Q(to_email__iexact=ident) | Q(from_email__iexact=ident)
    emails = EmailLog.objects.filter(company=company).filter(email_q)
    return devis, emails


def export_ventes(company, subject_identifier):
    """Export des documents commerciaux de la personne (jamais de marge)."""
    devis, emails = _documents(company, subject_identifier)
    return {
        'devis': [
            {
                'id': d.pk,
                'reference': d.reference,
                'statut': d.statut,
                'date_creation': d.date_creation.isoformat()
                if getattr(d, 'date_creation', None) else None,
                'date_acceptation': d.date_acceptation.isoformat()
                if d.date_acceptation else None,
                'accepte_par_nom': d.accepte_par_nom,
            }
            for d in devis
        ],
        'emails': [
            {
                'id': e.pk,
                'direction': e.direction,
                'sujet': e.sujet,
                'to_email': e.to_email,
                'from_email': e.from_email,
                'envoye_le': e.created_at.isoformat()
                if getattr(e, 'created_at', None) else None,
            }
            for e in emails
        ],
    }


#: ADEV59 — clés qui portent une POSITION absolue dans ``etude_params.toiture``
#: (et ses pans) : retirées à l'effacement, la géométrie relative reste.
CLES_POSITION = frozenset({
    'pin', 'lat', 'lng', 'lon', 'latitude', 'longitude', 'gps',
    'coordonnees', 'coordinates', 'centerLat', 'centerLng', 'repereAcquitte',
})


def _sans_position(valeur):
    """Copie de ``valeur`` sans aucune clé de :data:`CLES_POSITION` — PURE."""
    if isinstance(valeur, dict):
        return {k: _sans_position(v) for k, v in valeur.items()
                if k not in CLES_POSITION}
    if isinstance(valeur, list):
        return [_sans_position(v) for v in valeur]
    return valeur


def _layout_sans_position(layout):
    """ADEV59 — la copie du toit portée par le devis, sans position absolue.

    MÊME règle que l'effacement du calepinage (``document_anonymise`` : épingle
    retirée, chaque coordonnée ``[lng, lat]`` translatée en mètres LOCAUX
    relatifs à l'ancienne épingle) — réutilisée, jamais recopiée (fonction
    pure, aucun modèle du calepinage importé). Le repère du lead acquitté
    (``repereAcquitte``) part aussi : c'est une position de la maison. Les
    panneaux, comptes et résultats restent (cohérence des totaux).
    """
    if not isinstance(layout, dict) or not layout:
        return layout
    from apps.calepinage.dsr_provider import document_anonymise

    nouveau = document_anonymise(layout)
    if isinstance(nouveau, dict):
        nouveau.pop('pin', None)
        nouveau.pop('repereAcquitte', None)
    return nouveau


def _effacer_copie_toit(devis):
    """ADEV59 (C-ADEV-042) — efface la copie du toit portée par les devis du
    sujet : ``roof_layout`` sans épingle ni coordonnée absolue,
    ``etude_params.toiture`` sans coordonnées, ``roof_image`` détachée (objet
    stocké supprimé quand aucun autre devis ne le référence). Rend le nombre de
    devis modifiés. Aucun statut, montant ni référence n'est touché."""
    from .models import Devis
    from .services import supprimer_fichier_toiture

    count = 0
    ids = list(devis.values_list('pk', flat=True))
    for d in Devis.objects.filter(pk__in=ids):
        champs = []
        layout = _layout_sans_position(d.roof_layout)
        if layout != d.roof_layout:
            d.roof_layout = layout
            champs.append('roof_layout')
        etude = d.etude_params
        if isinstance(etude, dict) and isinstance(etude.get('toiture'), dict):
            toiture = _sans_position(etude['toiture'])
            if toiture != etude['toiture']:
                d.etude_params = {**etude, 'toiture': toiture}
                champs.append('etude_params')
        cle = d.roof_image
        if cle:
            d.roof_image = None
            champs.append('roof_image')
        if not champs:
            continue
        d.save(update_fields=champs)
        count += 1
        if cle and not Devis.objects.filter(roof_image=cle).exists():
            try:
                supprimer_fichier_toiture(cle)
            except Exception:  # noqa: BLE001 — l'objet stocké est best-effort
                pass
    return count


def erase_ventes(company, subject_identifier):
    """Pseudonymise les données personnelles détenues par les Ventes.

    Renvoie un compte-rendu ``{'pseudonymises', 'motif_conservation'}``.
    Aucune ligne n'est supprimée : les agrégats comptables (montants,
    références, statuts) restent strictement inchangés.
    """
    devis, emails = _documents(company, subject_identifier)
    count = 0

    for d in devis.exclude(accepte_par_nom=''):
        d.accepte_par_nom = ANONYME
        d.save(update_fields=['accepte_par_nom'])
        count += 1

    for e in emails:
        e.to_email = ''
        e.from_email = ''
        e.corps = ''
        e.save(update_fields=['to_email', 'from_email', 'corps'])
        count += 1

    count += _effacer_copie_toit(devis)

    return {
        'pseudonymises': count,
        'motif_conservation': MOTIF_SIGNATURE,
    }


def register():
    """Enregistre le fournisseur DSR Ventes (idempotent). Appelé en ready()."""
    from core import dsr
    dsr.register_dsr_provider(
        PROVIDER_NAME, export=export_ventes, erase=erase_ventes)
