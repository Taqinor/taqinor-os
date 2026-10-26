"""
Gating « devis automatique » — source de vérité UNIQUE côté serveur.

Selon le mode du lead (type_installation), certaines entrées sont requises
avant de pouvoir lancer le générateur de devis automatique :

  - Résidentiel (ou non renseigné) : facture hiver ; facture été UNIQUEMENT
    si le toggle « été différent » est actif (sinon la facture hiver vaut
    pour toute l'année) ;
  - Industriel / Commercial (CIQ404, contrat CIQ1) : l'un de
    conso_mensuelle_kwh, bill_kwh, releve_conso, ou facture_hiver (MAD) —
    pour un commercial si la tension n'est pas « mt », pour un industriel
    seulement si la basse tension est DÉCLARÉE, avec un contrat BT ; ALEA47 —
    + le contrat (sauf MT déclarée) et le rythme, par LA règle du moteur
    (``ventes.selectors.profil_charge_prerequis_ci``, jamais une copie) ;
  - Agricole (pompage, AGR403) : [HMT OU niveau d'eau] ET [débit souhaité,
    besoin en eau (m³/jour) OU débit de la pompe actuelle — ce dernier ne
    comptant qu'avec ses heures, volume déclaré D-AGR-3]. Le CV ne compte
    plus : il décrit la pompe ACTUELLE (``pompe_actuelle_cv``).

La même liste alimente le champ sérialisé `devis_auto` (UI) et l'endpoint
POST /crm/leads/<id>/devis-auto/ (règle serveur) — jamais deux logiques.
"""

import logging

from .categories_commerciales import TALON_PART_PCT_PAR_REPONSE

logger = logging.getLogger(__name__)

# Modes regroupés (clés de Lead.TypeInstallation — scalaires, jamais une
# liste d'étapes du pipeline, qui vit dans STAGES.py).
_MODES_ETUDE = ('commercial', 'industriel')
_MODE_AGRICOLE = 'agricole'

#: AGR403 — les groupes « l'un des » agricoles (groupes HYDRAULIQUES, lus
#: aussi par AGR530). ``pompe_actuelle_debit_m3h`` ne compte QUE si
#: ``pompage_heures_jour`` est renseigné (volume déclaré = débit actuel ×
#: heures actuelles, D-AGR-3 ; dérivé par AGR404).
#: AGQ9 (D-AGQ-5) — la HMT SAISIE est requise : le niveau d'eau seul ne fait
#: aucune HMT (il faut dénivelé, conduite, pertes) et ne compte que pour la
#: règle de visite D-AGR-4 (``visite_point_eau_avant_devis``).
GROUPES_HYDRAULIQUES_AGRICOLES = (
    ('pompe_hmt_m',),
    ('pompe_debit_m3h', 'besoin_eau_m3j', 'pompe_actuelle_debit_m3h'),
)

#: Champ qui ne compte qu'accompagné d'autres (sinon il vaut « vide »).
#: AGQ39 (D-AGQ-10) — la plaque de la pompe conservée ne compte que COMPLÈTE
#: (kW, tension, phases) : une seule puce, jamais une plaque à moitié lue.
_COMPTE_SEULEMENT_AVEC = {
    'pompe_actuelle_debit_m3h': ('pompage_heures_jour',),
    'pompe_actuelle_kw': ('pompe_actuelle_tension_v', 'pompe_actuelle_phases'),
}

#: AGQ39 (D-AGQ-10) — groupe requis en plus quand le lead dit « pompe
#: existante conservée » : la plaque de la pompe actuelle.
GROUPE_PLAQUE_EXISTANTE = ('pompe_actuelle_kw',)


def mode_pompe_du_lead(lead):
    """AGQ39 (D-AGQ-10) — ``{valeur, par_defaut}`` pour un lead AGRICOLE,
    ``None`` ailleurs. Vide ⇒ « neuve » comme avant, étiqueté « par défaut »
    (jamais écrit sur le lead)."""
    if (lead.type_installation or '') != _MODE_AGRICOLE:
        return None
    mode = getattr(lead, 'mode_pompe', None) or None
    return {'valeur': mode or 'neuve', 'par_defaut': mode is None}


def _releve_rempli(lead):
    releve = getattr(lead, 'releve_conso', None) or {}
    mois = releve.get('mois') if isinstance(releve, dict) else None
    return any(isinstance(m, dict) and m.get('kwh') not in (None, '')
               for m in (mois or []))


def _tension_declaree(lead):
    """La tension que le client a DÉCLARÉE (``None`` si inconnue) : une
    valeur pré-cochée par le site et jamais touchée ne compte pas."""
    tension = getattr(lead, 'tension_raccordement', None) or None
    if tension in (None, 'ne_sait_pas'):
        return None
    if getattr(lead, 'tension_source', None) == 'site_defaut_visible':
        return None
    return tension


def _facture_mad_compte(lead):
    """CIQ404 (contrat CIQ1 ``regles_devis_auto.facture_hiver``) — une
    facture MT porte une prime fixe : diviser ses MAD par un prix gonflerait
    les kWh. Commercial : compte sauf en « mt » ; industriel : seulement si
    la basse tension est DÉCLARÉE."""
    mode = lead.type_installation
    if mode == 'commercial':
        return getattr(lead, 'tension_raccordement', None) != 'mt'
    if mode == 'industriel':
        return _tension_declaree(lead) == 'bt'
    return True


def _contrat_bt_declare(lead):
    """ALEA47 — contrat BT déclaré, exigé par le gating pour une facture MAD
    (le lecteur du moteur sert la facture seule : son refus nomme le contrat)."""
    return (getattr(lead, 'contrat_electricite', None) or '').startswith('bt_')


def _rempli(lead, champ):
    """Même sémantique du vide partout (0 = manquant), plus la règle AGR403 :
    un débit actuel sans ses heures ne fait pas un volume."""
    if champ == 'releve_conso':
        return _releve_rempli(lead)
    if not getattr(lead, champ, None):
        return False
    if champ == 'contrat_electricite':
        return lead.contrat_electricite != 'ne_sait_pas'
    if champ == 'raccordement':
        return lead.raccordement != 'inconnu'
    if (champ == 'facture_hiver' and lead.type_installation in _MODES_ETUDE
            and not (_facture_mad_compte(lead) and _contrat_bt_declare(lead))):
        return False
    return all(getattr(lead, compagnon, None)
               for compagnon in _COMPTE_SEULEMENT_AVEC.get(champ, ()))


def releve_eau_manquant(lead) -> bool:
    """AGR530 (D-AGR-4 côté cadence) — lead AGRICOLE dont le niveau d'eau
    OU le débit du forage est inconnu (:func:`visite_point_eau_avant_devis`) :
    la suite est le relevé du point d'eau. Faux pour tout autre segment."""
    if (getattr(lead, 'type_installation', None) or '') != _MODE_AGRICOLE:
        return False
    # AGQ9 (D-AGQ-5) — la HMT est une DÉCLARATION, pas une mesure : son
    # absence ne demande pas un relevé. Le relevé suit la règle D-AGR-4
    # (niveau d'eau ou débit du forage inconnu), une seule définition.
    bloc = visite_point_eau_avant_devis(lead)
    return bool(bloc and bloc['requise'])


def champs_requis(lead) -> list[list[str]]:
    """QJR600 (contrat ``devis_auto_pret.json``) — la règle STRUCTURÉE : une
    liste de groupes « l'un des » (noms de champs ``Lead``). Le devis
    automatique est prêt quand CHAQUE groupe a au moins un champ rempli —
    même sémantique du vide que :func:`champs_manquants` (0 = manquant)."""
    mode = lead.type_installation or 'residentiel'
    if mode == _MODE_AGRICOLE:
        requis = [list(groupe) for groupe in GROUPES_HYDRAULIQUES_AGRICOLES]
        if getattr(lead, 'mode_pompe', None) == 'existante':
            requis.append(list(GROUPE_PLAQUE_EXISTANTE))
        return requis
    if mode in _MODES_ETUDE:
        # CAD166 — conso éditable OU kWh du tunnel : l'un vaut l'autre.
        # CIQ404 (contrat CIQ1) — + le relevé de factures et la facture en
        # MAD (selon la tension, voir :func:`_facture_mad_compte`).
        requis = [list(GROUPE_CONSO_PRO)]
        # ALEA47 (D-ACI-5=a) — + le contrat (MT déclarée : Tarif Général).
        if _tension_declaree(lead) != 'mt':
            requis.append(['contrat_electricite'])
        # ADEV89 (rejeu « humain » 23/10/2026) — + la phase du site : la
        # combinaison d'onduleurs la suit (jamais « je ne sais pas »).
        requis.append(['raccordement'])
        return requis + _groupes_rythme(lead)
    requis = [['facture_hiver']]
    if lead.ete_differente:
        requis.append(['facture_ete'])
    return requis


def _rythme_ci(lead):
    """ALEA47 — le bloc ``rythme`` tel que le moteur le lit (jumeau sans
    requête de ``devis_selectors.entrees_ci_du_lead`` §4, garde de test)."""
    rythme = {}
    if lead.jours_ouverture:
        jours = set(lead.jours_ouverture)
        rythme['jours_ouverts'] = [j in jours for j in range(1, 8)]
    if lead.heure_debut is not None and lead.heure_fin is not None:
        rythme['plages'] = {'ouvre': [[lead.heure_debut, lead.heure_fin]]}
    elif lead.heure_debut is not None and lead.regime_equipes:
        rythme['debut_equipe_h'] = lead.heure_debut
    if lead.regime_equipes:
        rythme['equipes'] = lead.regime_equipes
    pct = TALON_PART_PCT_PAR_REPONSE.get(lead.equipements_hors_horaires)
    if pct is not None:
        rythme['talon'] = {'part_pct': pct}
    if lead.type_installation == 'commercial':
        if lead.categorie_commerciale:
            rythme['categorie_commerciale'] = lead.categorie_commerciale
        if lead.reponses_categorie:
            rythme['reponses_categorie'] = dict(lead.reponses_categorie)
    return rythme


#: ALEA47 — champ du lead rendu par la règle partagée → son groupe requis.
_GROUPES_RYTHME = {'jours_ouverture': ('jours_ouverture',),
                   'heure_debut': ('heure_debut', 'regime_equipes')}


def _groupes_rythme(lead):
    """ALEA47 — les groupes de rythme MANQUANTS selon la règle du moteur ; le
    profil SAISI par la société (D-ACI-7=a) lu seulement s'il peut aider."""
    from apps.ventes.selectors import profil_charge_prerequis_ci

    mode = lead.type_installation
    rythme = _rythme_ci(lead)
    categorie = (rythme.get('categorie_commerciale') if mode == 'commercial'
                 else 'industriel')
    champs = profil_charge_prerequis_ci(rythme, categorie, en_champs_lead=True)
    cle = categorie if mode == 'commercial' else lead.secteur_industriel
    if champs and cle and getattr(lead, 'company_id', None):
        champs = profil_charge_prerequis_ci(
            rythme, categorie, company=lead.company, mode=mode,
            cle_profil=cle, en_champs_lead=True)
    return [list(_GROUPES_RYTHME[champ]) for champ in champs]


#: CIQ404 (contrat CIQ1 ``regles_devis_auto.groupe_pro``).
GROUPE_CONSO_PRO = ('conso_mensuelle_kwh', 'bill_kwh', 'releve_conso',
                    'facture_hiver')

#: CIQ404 — libellés du groupe pro, par segment (contrat
#: ``devis_auto_pret.json`` → ``exemple_industriel``).
_LIBELLES_PRO = {
    'commercial': 'Consommation (kWh) ou facture mensuelle (MAD)',
    'industriel': ('Consommation (kWh), relevé de factures, ou facture en '
                   'MAD si la basse tension est déclarée'),
}

#: Ordre de préférence de la source de consommation : le relevé prime, puis
#: le kWh mensuel, puis la facture en MAD (convertie par QJR665, jamais ici).
_ORDRE_SOURCE_CONSO = ('releve_conso', 'conso_mensuelle_kwh', 'bill_kwh',
                       'facture_hiver')

#: Libellé affiché d'un groupe manquant, indexé sur le PREMIER champ du
#: groupe (celui que la puce « manquant » vise). Libellés inchangés.
_LIBELLES = {
    # AGR403 — libellés du contrat ``devis_auto_pret.json``.
    'pompe_hmt_m': 'HMT (m)',
    'pompe_debit_m3h': ('Débit souhaité, besoin en eau (m³/jour) ou débit '
                        'de la pompe actuelle'),
    # AGQ39 (D-AGQ-10) — une seule puce pour la plaque complète.
    'pompe_actuelle_kw': 'plaque de la pompe actuelle (kW, tension, phases)',
    # ── CAD-M ── CAD166 — LE DOSSIER PRO ÉTAIT BLOQUÉ ALORS QUE LA DONNÉE
    # ÉTAIT LÀ. Le tunnel professionnel du site n'écrit que ``bill_kwh``
    # (archive web, lecture seule) ; ce gating, lui, n'interrogeait que
    # ``conso_mensuelle_kwh`` (le champ ÉDITABLE, saisi par la commerciale
    # ou écrit par l'OCR). Les deux ne fusionnent PAS — chacun garde son
    # rôle — mais l'un vaut l'autre pour décider si le devis automatique
    # peut partir (groupe « l'un des » de :func:`champs_requis`).
    'conso_mensuelle_kwh': 'consommation mensuelle (kWh)',
    # Résidentiel — comportement simulateur : la facture été n'est requise
    # QUE si elle diffère de l'hiver (toggle existant).
    'facture_hiver': 'facture hiver',
    'facture_ete': 'facture été',
    # ALEA47 (D-ACI-5=a) — un libellé par groupe ; les deux groupes de
    # rythme partagent le leur (une seule puce).
    'contrat_electricite': "Contrat d'électricité",
    # ADEV89 — la phase du site, prérequis de la combinaison d'onduleurs.
    'raccordement': 'Phase du site (monophasé ou triphasé)',
    'jours_ouverture': "Jours et heures d'ouverture (ou catégorie d'activité)",
    'heure_debut': "Jours et heures d'ouverture (ou catégorie d'activité)",
}


def champs_manquants_detail(lead, requis=None) -> list[dict]:
    """QJR600 — ``[{champ, label}]`` des groupes requis sans aucun champ
    rempli (``champ`` = premier champ du groupe, nom du champ ``Lead``) ; un
    groupe de rythme n'est requis QUE manquant (ALEA47, règle du moteur)."""
    detail = []
    mode = lead.type_installation or 'residentiel'
    for groupe in champs_requis(lead) if requis is None else requis:
        rythme = tuple(groupe) in _GROUPES_RYTHME.values()
        if not rythme and any(_rempli(lead, champ) for champ in groupe):
            continue
        label = (_LIBELLES_PRO[mode] if mode in _MODES_ETUDE
                 and groupe[0] in GROUPE_CONSO_PRO else _LIBELLES[groupe[0]])
        if all(entree['label'] != label for entree in detail):
            detail.append({'champ': groupe[0], 'label': label})
    return detail


def source_conso(lead):
    """CIQ404 — la colonne qui remplit le groupe pro (``releve_conso`` >
    ``conso_mensuelle_kwh`` > ``bill_kwh`` > ``facture_hiver``), ``None``
    si aucune — ou hors commercial/industriel. Le moteur D1 étiquette une
    facture en MAD « estimation dérivée de la facture déclarée en MAD »."""
    if (lead.type_installation or '') not in _MODES_ETUDE:
        return None
    for champ in _ORDRE_SOURCE_CONSO:
        if _rempli(lead, champ):
            return champ
    return None


def visite_avant_devis(lead):
    """CIQ404 (D-CIQ-5, contrat CIQ1) — ``{requise, motifs}`` pour un lead
    commercial/industriel, ``None`` ailleurs.

    Requise si la tension vaut « mt », ou est inconnue (vide, « ne sait
    pas », ou défaut visible du site jamais touché), si la puissance
    souscrite est vide, ou si le type de surface ou la surface sont vides.
    Une information : ``pret`` ne mesure que les données, un devis indicatif
    reste possible (« estimation sous réserve de visite »).
    """
    if (lead.type_installation or '') not in _MODES_ETUDE:
        return None
    motifs = []
    tension = getattr(lead, 'tension_raccordement', None)
    if tension == 'mt':
        motifs.append('site en moyenne tension')
    elif _tension_declaree(lead) is None:
        motifs.append('tension de raccordement inconnue')
    if getattr(lead, 'compteur_puissance_kva', None) is None:
        motifs.append('puissance souscrite inconnue')
    if not getattr(lead, 'type_surface', None):
        motifs.append('type de surface inconnu')
    if getattr(lead, 'surface_toiture_m2', None) is None:
        motifs.append('surface disponible inconnue')
    return {'requise': bool(motifs), 'motifs': motifs}


def champs_manquants(lead) -> list[str]:
    """Champs requis manquants (libellés) pour un devis automatique, selon le
    mode du lead. QJR600 — dérivé de :func:`champs_manquants_detail` : UNE
    seule règle, :func:`champs_requis`."""
    return [entree['label'] for entree in champs_manquants_detail(lead)]


def message_manquants(manquants):
    return 'Manque : ' + ', '.join(manquants)


def visite_point_eau_avant_devis(lead):
    """AGR403 (D-AGR-4) — ``{requise, motifs}`` pour un lead AGRICOLE, None
    ailleurs.

    Requise quand le niveau d'eau OU le débit du forage est inconnu (D-AGR-4
    appliquée à la lettre). C'est une information : ``pret`` ne mesure que la
    complétude des données, les boutons manuels avertissent sans bloquer
    (patron CAD123) et la retenue du devis automatique serveur revient au
    moteur agricole (D1).
    """
    if (lead.type_installation or '') != _MODE_AGRICOLE:
        return None
    # AGQ22 (C-AGQ-021) — chaque motif porte le CHAMP du lead qu'il vise
    # (``motifs_detail``) : la puce et le 409 du devis automatique nomment le
    # bon champ (débit du forage ≠ niveau). ``motifs`` (textes) inchangé.
    motifs, detail = [], []
    if lead.niveau_statique_m is None:
        motifs.append("niveau d'eau du forage inconnu")
        detail.append({'champ': 'niveau_statique_m',
                       'libelle': "niveau d'eau du forage (visite)"})
    if lead.debit_forage_m3h is None:
        motifs.append('débit du forage inconnu')
        detail.append({'champ': 'debit_forage_m3h',
                       'libelle': 'débit du forage (visite)'})
    return {'requise': bool(motifs), 'motifs': motifs,
            'motifs_detail': detail}


def catalogue_ci(lead):
    """ALEA50 (D-ACI-6=a) — ``{pret, manquants}`` : les postes FIXES du
    moteur C&I sans prix (forfaits société, coffrets, protection AC, comptage
    d'injection). Un lead commercial/industriel dont le catalogue n'est pas
    prêt ne peut pas recevoir de devis automatique (le moteur refuserait en
    409 « Prix à renseigner ») : l'écran désactive le bouton et dit pourquoi.
    ``None`` hors C&I, ou si la lecture échoue (jamais un blocage muet).
    Lu par ``ventes.selectors.catalogue_ci_pret`` (cache 5 min par société)."""
    if (lead.type_installation or '') not in _MODES_ETUDE:
        return None
    if not getattr(lead, 'company_id', None):
        return None
    try:
        from apps.ventes.selectors import catalogue_ci_pret
        return catalogue_ci_pret(lead.company_id)
    except Exception:
        logger.warning('catalogue_ci_pret : échec ignoré (dégradé)',
                       exc_info=True)
        return None
