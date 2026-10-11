"""Fusion de leads (SPL22, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
import logging

from apps.records.provenance import ecrire_si_libre

from .cadence_filet import assurer_prochaine_etape_apres_succes
from .leads_doublons import _MERGE_FILL_FIELDS, _est_vide
from .leads_score import recompute_lead_score
from .models import Lead, LeadActivity, RelanceEtape

logger = logging.getLogger(__name__)


#: Le motif porté par une touche que la FUSION retire du plan. Statut
#: ANNULEE (CKP1 : annulation MOTEUR, jamais un saut humain) — sans quoi la
#: fusion compterait autant de manquements d'adhérence que de touches.
FUSION_TOUCHE_NOTE = 'annulée — fusion de fiches'


def relances_ouvertes_de(lead):
    """Les touches encore À FAIRE d'un lead (l'aperçu et la fusion comptent
    la même chose — jamais deux définitions)."""
    return lead.relance_etapes.filter(statut=RelanceEtape.Statut.A_FAIRE)


def reprendre_relances_apres_fusion(absorbed, survivor, user):
    """CAD106 — les relances SUIVENT le dossier quand deux fiches fusionnent.

    `merge_leads` déplaçait devis, chantiers, activités, pièces jointes et
    historique — et pas une seule relance. Les touches ouvertes restaient
    accrochées à une fiche ARCHIVÉE, donc invisibles dans la file (qui exclut
    les archivés), jamais passées en « annulée », et rien ne reposait de
    prochaine étape sur la survivante. Le cas est garanti d'arriver : le
    nouveau lead venait justement d'être privé de cadence par la garde
    « doublon ».

    Ce qu'on fait, et POURQUOI pas un simple déplacement : la survivante a
    souvent DÉJÀ une cadence active, et CADX interdit deux cadences en
    parallèle sur un lead. Les touches ouvertes de l'absorbée sont donc
    CLOSES en ANNULÉE avec le motif « fusion » — elles ne comptent alors
    comme un manquement nulle part (CKP1) — puis le FILET garantit à la
    survivante une prochaine étape, exactement comme à la reprise d'un lead
    dé-perdu (`unset_perdu`).

    Rend le nombre de touches retirées du plan de l'absorbée.
    """
    from django.utils import timezone

    ouvertes = list(relances_ouvertes_de(absorbed))
    if ouvertes:
        RelanceEtape.objects.filter(
            pk__in=[e.pk for e in ouvertes],
        ).update(statut=RelanceEtape.Statut.ANNULEE,
                 note=FUSION_TOUCHE_NOTE, traite_par=None,
                 traite_le=timezone.now())
        absorbed.relance_date = None
        absorbed.save(update_fields=['relance_date'])
    # QJ-INVARIANT — la survivante ne reste jamais sans prochaine étape.
    # Best-effort : une fusion n'échoue pas sur un filet.
    try:
        assurer_prochaine_etape_apres_succes(survivor, user)
    except Exception:  # noqa: BLE001
        logger.warning(
            'CAD106: filet non posé après fusion (lead #%s)',
            getattr(survivor, 'pk', '?'), exc_info=True)
    return len(ouvertes)


def _transferer_calepinages_apres_fusion(absorbed, survivor, user):
    """ACAL177 — fait suivre les calepinages de l'absorbé au survivant.

    Appel DIRECT du service ``apps.calepinage.services.liens.transferer_lead``
    (même patron que ``update_installation_lead`` : transactionnel, pas
    d'événement), import FONCTION-LOCAL (frontière inter-apps : jamais un
    modèle de calepinage). Sous-bloc ``atomic`` (savepoint) : un échec annule
    le seul transfert, la fusion continue, et le chatter du survivant le dit.
    """
    from django.db import transaction

    try:
        from apps.calepinage.services.liens import transferer_lead

        with transaction.atomic():
            transferer_lead(survivor.company, de_lead_id=absorbed.pk,
                            vers_lead_id=survivor.pk, user=user)
    except Exception:  # noqa: BLE001 — la fusion ne casse jamais ici
        logger.exception(
            'ACAL177 : calepinages du lead #%s non transférés vers #%s',
            absorbed.pk, survivor.pk)
        LeadActivity.objects.create(
            company=survivor.company, lead=survivor, user=user,
            kind=LeadActivity.Kind.NOTE,
            body=(f'Fusion : les calepinages du lead #{absorbed.pk} n\'ont '
                  'pas pu être rattachés à cette fiche — rattachez-les depuis '
                  'le module Calepinage.'))


def raison_refus_suppression(lead):
    """ACAL177 — LA garde de corbeille d'un lead, écrite UNE fois.

    Sert les DEUX chemins de suppression (``LeadViewSet.destroy`` et
    l'opération en masse ``delete``). Rend ``None`` si le lead peut partir en
    corbeille, sinon un dict ``{detail, [calepinages]}`` (corps du 409) :

    * des devis liés : on n'orpheline jamais de pièces financières ;
    * un calepinage OUVERT (non archivé) : refus qui le NOMME. Un calepinage
      archivé ne bloque pas.
    """
    if lead.devis.exists():
        return {'detail': "Ce lead a des devis liés. Supprimer le lead "
                          "détacherait ces pièces — archivez-le plutôt."}
    from apps.calepinage.selectors import calepinages_ouverts_du_lead

    ouverts = calepinages_ouverts_du_lead(lead.company, lead.pk)
    if ouverts:
        premier = ouverts[0]
        titre = (getattr(premier, 'titre', '') or '').strip() or 'sans titre'
        return {
            'detail': (f'Ce lead porte le calepinage « {titre} » '
                       f'(#{premier.pk}) : archivez-le d\'abord ou ouvrez-le '
                       'depuis le module Calepinage'),
            'calepinages': [c.pk for c in ouverts],
        }
    return None


def _nom_fiche_client(client):
    """ACRM40 — « Nom Prénom (#id) » d'une fiche client, pour la note."""
    nom = f"{client.nom or ''} {client.prenom or ''}".strip() or 'Client'
    return f'{nom} (#{client.pk})'


def merge_leads(survivor, others, user):
    """Fusionne `others` dans `survivor` SANS perte de données. Déplace devis,
    activités, pièces jointes, historique et chantiers ; complète les champs
    vides du survivant ; archive les leads absorbés avec une note. Ne laisse
    JAMAIS un devis/chantier orphelin. Tout est transactionnel.
    """
    from django.contrib.contenttypes.models import ContentType
    from django.db import transaction
    from django.utils import timezone

    others = [o for o in others if o.pk != survivor.pk
              and o.company_id == survivor.company_id]
    if not others:
        return survivor

    ct = ContentType.objects.get_for_model(Lead)
    relances_reprises = 0
    # ACRM40 (C-ACRM-035) — les fiches client DISTINCTES rencontrées : le
    # survivant garde la sienne, les devis de l'autre restent sur l'autre.
    deux_clients = []
    with transaction.atomic():
        for absorbed in others:
            if (survivor.client_id and absorbed.client_id
                    and survivor.client_id != absorbed.client_id):
                deux_clients.append((
                    absorbed.client,
                    list(absorbed.devis.filter(client_id=absorbed.client_id)
                         .order_by('pk').values_list('reference', flat=True))))
            # 1) Devis → survivant (related_name='devis').
            absorbed.devis.update(lead=survivor)
            # 2) Chantiers liés au lead → survivant (FK SET_NULL, on réassigne).
            try:
                from apps.installations.selectors import (
                    update_installation_lead,
                )
                update_installation_lead(absorbed, survivor)
            except Exception:
                pass
            # 2 bis) ACAL177 — les CALEPINAGES suivent le dossier (D06-T04).
            # Savepoint : un transfert qui échoue ne casse jamais la fusion,
            # mais il est tracé (journal + note au chatter du survivant).
            _transferer_calepinages_apres_fusion(absorbed, survivor, user)
            # 3) Activités + pièces jointes génériques → survivant.
            try:
                from apps.records.models import Activity, Attachment
                Activity.objects.filter(
                    content_type=ct, object_id=absorbed.id).update(
                    object_id=survivor.id)
                Attachment.objects.filter(
                    content_type=ct, object_id=absorbed.id).update(
                    object_id=survivor.id)
            except Exception:
                pass
            # 4) Historique chatter → survivant.
            LeadActivity.objects.filter(lead=absorbed).update(lead=survivor)
            # 4 bis) CAD106 — les RELANCES suivent le dossier : les touches
            # ouvertes de l'absorbée sortent de son plan (annulées « fusion »,
            # donc jamais comptées comme des manquements) et le filet garantit
            # une prochaine étape à la survivante.
            relances_reprises += reprendre_relances_apres_fusion(
                absorbed, survivor, user)
            # 5) Client : adopter celui de l'absorbé si le survivant n'en a pas.
            if not survivor.client_id and absorbed.client_id:
                survivor.client = absorbed.client
            # 6) Compléter les champs VIDES du survivant — ACRM13 : vide au
            # sens de ``_est_vide`` (un 0 saisi du survivant SURVIT).
            for field in _MERGE_FILL_FIELDS:
                cur = getattr(survivor, field, None)
                if _est_vide(survivor, field, cur):
                    val = getattr(absorbed, field, None)
                    if not _est_vide(absorbed, field, val):
                        # AMET21 — une clé SAISIE du survivant n'est jamais remplacée.
                        ecrire_si_libre(survivor, field, val, user=user)
            # 7) Fusionner les tags (union).
            tags = set()
            for src in (survivor, absorbed):
                for t in (src.tags or '').split(','):
                    t = t.strip()
                    if t:
                        tags.add(t)
            if tags:
                survivor.tags = ', '.join(sorted(tags))[:500]
            # 8) Archiver l'absorbé (jamais supprimé).
            absorbed.is_archived = True
            absorbed.archived_by = user
            absorbed.archived_at = timezone.now()
            absorbed.note = ((absorbed.note or '') +
                             f'\n[Fusionné dans le lead #{survivor.id} '
                             f'par {getattr(user, "username", "?")}]').strip()
            absorbed.save()
            LeadActivity.objects.create(
                company=survivor.company, lead=survivor, user=user,
                kind=LeadActivity.Kind.NOTE,
                body=(f"Fusion : lead « {absorbed.nom} {absorbed.prenom or ''} »"
                      f" (#{absorbed.id}) absorbé dans cette fiche."))
        # ACRM40 — DEUX fiches client pour une même personne : la fusion le
        # DIT (chatter du survivant + ``survivor._clients_distincts`` que la
        # vue rend) ; la fusion des clients reste un geste humain (outil de
        # fusion de clients, NTDATA18) — jamais automatique.
        survivor._clients_distincts = []
        if deux_clients:
            gardee = survivor.client
            survivor._clients_distincts = [gardee.pk] + [
                client.pk for client, _refs in deux_clients]
            for client, refs in deux_clients:
                devis_txt = (f"devis {', '.join(refs)} rattachés" if refs
                             else 'aucun devis rattaché')
                LeadActivity.objects.create(
                    company=survivor.company, lead=survivor, user=user,
                    kind=LeadActivity.Kind.NOTE,
                    body=(f'Deux fiches client pour ce lead : '
                          f'{_nom_fiche_client(gardee)} (gardée) et '
                          f'{_nom_fiche_client(client)} ({devis_txt}) — à '
                          'fusionner (outil de fusion des clients).'))
        survivor.save()
    if relances_reprises:
        # CAD106 — la fusion DIT ce qu'elle a fait des relances : sans cette
        # ligne, des touches disparaissaient du plan sans un mot.
        LeadActivity.objects.create(
            company=survivor.company, lead=survivor, user=user,
            kind=LeadActivity.Kind.NOTE,
            body=(f'Fusion : {relances_reprises} relance(s) reprise(s) — '
                  'les touches des fiches absorbées sont retirées de leur '
                  'plan et le suivi continue sur cette fiche.'))
    # CRX33 — l'étape 6 complète les champs VIDES du survivant depuis les
    # absorbés (téléphone, e-mail, ville, facture, orientation…) : autant de
    # composantes du score. Sans ce recalcul, le survivant gardait le score
    # d'AVANT la fusion — une fiche enrichie restait « froide », et le badge
    # comme le tri mentaient jusqu'à la prochaine édition manuelle.
    recompute_lead_score(survivor)
    return survivor
