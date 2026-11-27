"""R2-15 / R2-01 — la toiture DÉCLARÉE sur le lead, servie à l'atelier.

Bloc ``toiture_lead`` du contexte de conception (contrat
``contract_samples/calepinage_design_context.json``) : ce que la fiche du lead
dit de son toit et de son site (section « Toiture & site »), TEL QUEL. Chaque
champ vaut ``None`` quand le lead ne le dit pas — jamais une valeur devinée
(D-ACAL-7). Décision Q1 de la recette du 22/11 : l'atelier AFFICHE ces valeurs
en lecture et n'en préremplit aucune (ni pente, ni orientation).

``mode_pose`` est le seul champ qui agit : c'est le mode que le SERVEUR a posé
dans le document à la création du calepinage (CIQ112, ``modePoseDeclare``) et
que le traducteur applique déjà aux pans ; il est relu du DOCUMENT (jamais
recalculé depuis le lead, qui a pu changer depuis). L'atelier le relit lui
aussi dans le document pour son pan vierge ; ce bloc le redit à l'écran.

Lead lu par ``apps.crm.selectors`` (jamais ses modèles). LECTURE PURE.
"""
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutVoirCalepinage
from ..serializers import forme_du_contrat
from ..services.valeurs import nombre
from .calepinages import CalepinageViewSet

#: Champs à choix : servis par leur LIBELLÉ de fiche (``get_<champ>_display``).
CHAMPS_LIBELLES = ('type_surface', 'type_toiture', 'orientation', 'ombrage', 'structure_pref')
#: Champs numériques : ``float`` fini ou ``None``.
CHAMPS_NOMBRES = ('surface_toiture_m2', 'inclinaison_deg', 'nb_etages', 'roof_age')


def toiture_du_lead(company, calepinage, *, lire_lead=None):
    """Le bloc ``toiture_lead`` : toutes ses clés, toujours présentes."""
    lead = _lead(company, getattr(calepinage, 'lead_id', None), lire_lead)
    bloc = {champ: _libelle(lead, champ) for champ in CHAMPS_LIBELLES}
    bloc.update({champ: nombre(getattr(lead, champ, None)) for champ in CHAMPS_NOMBRES})
    bloc['ombrage_notes'] = str(getattr(lead, 'ombrage_notes', None) or '').strip() or None
    mode = (getattr(calepinage, 'roof_layout', None) or {}).get('modePoseDeclare')
    bloc['mode_pose'] = mode if isinstance(mode, str) and mode else None
    return bloc


#: T4-U3-012 — clé du panneau Pompage (``PompagePanel.jsx`` ``CHAMPS``, la clé
#: que ``views/pompage.py`` relit) → (champ du lead, champ de sa provenance).
#: Le débit souhaité n'a pas de provenance sur la fiche : ``None``.
POMPAGE_DU_LEAD = (
    ('niveau_statique_m', 'niveau_statique_m', 'niveau_statique_source'),
    ('hmt_saisie', 'pompe_hmt_m', 'pompe_hmt_source'),
    ('debit_exploitation_m3h', 'debit_forage_m3h', 'debit_forage_source'),
    ('debit_souhaite_m3h', 'pompe_debit_m3h', None),
)


def prefill_du_lead(company, calepinage, *, lire_lead=None):
    """T4-U3-012 — le bloc ``prefill_lead`` : ce que la fiche du lead dit du
    pompage, à PRÉREMPLIR dans le panneau Pompage (jamais écrit ici).

    ``{lead, pompage: {<clé du panneau>: {valeur, origine, origine_libelle}}}``
    — ``valeur`` ``None`` quand la question n'a pas été posée ; ``origine`` est
    la provenance telle que la fiche la garde (« déclaré », « mesuré en
    visite »…). ``None`` sans lead, ou pour un lead d'une autre société (le
    sélecteur CRM est borné société)."""
    lead = _lead(company, getattr(calepinage, 'lead_id', None), lire_lead)
    if lead is None:
        return None
    pompage = {}
    for cle, champ, provenance in POMPAGE_DU_LEAD:
        valeur = nombre(getattr(lead, champ, None))
        origine = (getattr(lead, provenance, None) or None) if provenance else None
        pompage[cle] = {
            'valeur': valeur,
            'origine': origine if valeur is not None else None,
            'origine_libelle': (_libelle(lead, provenance)
                                if origine and valeur is not None else None)}
    return {'lead': lead.pk, 'pompage': pompage}


def _lead(company, lead_id, lire_lead):
    """Le lead de la société (sélecteur CRM), ou ``None``."""
    if company is None or not lead_id:
        return None
    if lire_lead is None:
        from apps.crm.selectors import get_company_lead as lire_lead
    return lire_lead(company, lead_id)


def _libelle(lead, champ):
    """Le libellé de fiche d'un champ à choix renseigné, sinon ``None``."""
    if lead is None or not getattr(lead, champ, None):
        return None
    return str(getattr(lead, f'get_{champ}_display')()) or None


def cible_factures_et_refus(calepinage, *, lire_cible=None, lire_lead=None):
    """ACAL1500 — ``(cible_factures, refus)`` d'UNE seule lecture de la cible
    du garde R2-17 (``services.devis._cible_du_calepinage`` →
    ``apps.ventes.selectors.cible_depuis_lead``) : le dimensionnement n'est
    joué qu'une fois. ``refus`` est la phrase NOMMÉE qui dit pourquoi aucune
    taille ne se tire des factures : celle de ``cible_depuis_lead`` (C&I,
    agricole, facture absente…) ou, quand la taille souhaitée du lead est
    souveraine (R6-N4, ``source`` ``'lead'``), la phrase de
    :func:`_refus_taille_souhaitee` ; ``''`` quand la cible vient des
    factures (``cible_factures`` servi) ou qu'il n'y a ni lead ni refus."""
    if lire_cible is None:
        from ..services.devis import _cible_du_calepinage as lire_cible
    cible = lire_cible(calepinage)
    des_factures = _cible_des_factures(cible)
    if des_factures is not None:
        return des_factures, ''
    if cible and cible.get('source') == 'lead' and cible.get('panneaux'):
        lead = _lead(getattr(calepinage, 'company', None), getattr(calepinage, 'lead_id', None), lire_lead)
        return None, _refus_taille_souhaitee(cible, nombre(getattr(lead, 'taille_souhaitee_kwc', None)))
    return None, str((cible or {}).get('refus') or '')


def _cible_des_factures(cible):
    """Le bloc ``cible_factures`` quand la taille vient des factures, sinon ``None`` (aucune lecture de lead)."""
    if not (cible and cible.get('source') == 'factures' and cible.get('panneaux')):
        return None
    return {'panneaux': int(cible['panneaux']), 'kwc': nombre(cible.get('kwc')),
            'module_wc': nombre(cible.get('panel_watt')),
            # Lane E9 — la version de la conception qui fait ces chiffres et la raison de son calcul.
            'version': cible.get('version'), 'raison': cible.get('raison')}


def _kwc_fr(valeur):
    """``6.0`` → « 6 », ``6.39`` → « 6,39 », ``6.5`` → « 6,5 » : jamais de décimales forcées (« 6,00 kWc »)."""
    from core.electrique.types import fr

    return fr(valeur).rstrip('0').rstrip(',')


def _refus_taille_souhaitee(cible, souhait):
    """R6-N4 — la taille souhaitée du lead est SOUVERAINE (``cible_depuis_lead`` : ``source`` ``'lead'``) : le moteur
    n'a donc rien lu dans les factures, et ``cible_factures`` reste ``null``. Sans phrase, l'étape Panneaux retombait
    sur « Aucune taille ne se tire des factures de ce lead », fausse pour un lead qui porte une facture ET une taille.
    La phrase dit le SOUHAIT tel qu'il est sur la fiche (``souhait`` = ``taille_souhaitee_kwc``, lu par le
    sélecteur CRM) et, à côté, la pose calculée NOMMÉE comme telle (« conception ») : le calcul n'est jamais
    présenté comme le souhait."""
    n, kwc = int(cible['panneaux']), nombre(cible.get('kwc'))
    pose = '%d panneau%s' % (n, 'x' if n > 1 else '') + (' · %s kWc' % _kwc_fr(kwc) if kwc else '')
    morceaux = (['%s kWc' % _kwc_fr(souhait)] if souhait else []) + ['conception : %s' % pose]
    detail = ' ; '.join(morceaux)
    return 'La taille de ce lead vient de la taille souhaitée sur sa fiche (%s), pas de ses factures.' % detail


def cible_factures(calepinage, *, lire_cible=None):
    """Maquette Panneaux (22/11) — le bloc ``cible_factures`` : la taille que
    le devis automatique tirerait des FACTURES du lead, par LA fonction du
    garde R2-17 — jamais un second dimensionnement. ``{panneaux, kwc,
    module_wc}``, ou ``None`` quand la taille ne vient pas des factures (sans
    lead, sans facture, taille souhaitée, C&I, agricole, refus ; le motif est
    dit par ``cible_factures_et_refus``). LECTURE PURE."""
    if lire_cible is None:
        from ..services.devis import _cible_du_calepinage as lire_cible
    return _cible_des_factures(lire_cible(calepinage))


# ── H3 (22/11) — ``GET calepinages/<pk>/cible-factures/`` : le bloc ci-dessus, LU À PART.
# Le dimensionnement horaire qu'il appelle coûtait ~1,9 s et ~28 requêtes à CHAQUE ouverture de
# l'atelier quand il vivait dans le design-context (sur le chemin de démarrage) : il est servi ici,
# lu par les étapes Toit et Panneaux seules. Mêmes droits que le design-context (``PeutVoirCalepinage``),
# société bornée par ``get_object()`` (404 pour une autre société). Contrat
# ``contract_samples/calepinage_cible_factures.json``.
@extend_schema(responses=forme_du_contrat('CalepinageCibleFactures', 'calepinage_cible_factures.json'))
@action(detail=True, methods=['get'], url_path='cible-factures', permission_classes=[PeutVoirCalepinage])
def cible_factures_servie(self, request, pk=None):
    """La taille tirée des factures du lead (``cible_factures``), ou ``null`` avec le ``refus`` nommé ;
    ``calcul_en_cours`` (relecture E5 B1) : le premier calcul de la conception est en file, l'écran relit."""
    from ..services.devis_retenu import attend_son_premier_calcul

    calepinage = self.get_object()
    cible, refus = cible_factures_et_refus(calepinage)
    return Response({'cible_factures': cible, 'refus': refus, 'calcul_en_cours': attend_son_premier_calcul(calepinage)})


CalepinageViewSet.cible_factures_servie = cible_factures_servie
