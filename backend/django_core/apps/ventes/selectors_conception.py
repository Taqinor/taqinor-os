"""ADEV137 — les LECTEURS de la conception rangée (D-ACAL-97), bornés société.

Lecture seule : rien n'est calculé, rien n'est écrit (le seul écrivain est
``conception/service.py::relancer``). Forme servie : contrat
``contract_samples/conception_lead.json`` (sortie du moteur + clés de la
version rangée). Ré-exportés par ``selectors.py``.

* ``conception_courante(company, lead_id=None, *, calepinage_id=None)`` — la
  version courante du porteur à la forme du contrat, ou ``None`` ;
* ``historique_conception(...)`` — les versions, la plus récente d'abord ;
* ``manques_du_moteur(lead)`` — ``[{champ, label}]`` des champs sans lesquels
  le moteur refuse (lieu, puis les groupes requis du devis automatique) ;
* ``ecart_devis(devis)`` — ce qui diffère entre un devis (FIGÉ, lu sans être
  touché) et la conception courante de son lead ;
* ``champs_entrees(marche)`` — les colonnes du lead entrées du moteur
  (``conception/champs.py::CHAMPS_ENTREES``), lues par l'émetteur du CRM.

``perimee`` (ADEV140, le FILET d'empreinte) : l'empreinte des ENTRÉES
actuelles du porteur (jamais le calcul) comparée à celle de la version ; un
écart (écriture hors du chemin normal, événement perdu) sert la version telle
quelle avec ``perimee: true`` et met UNE relance en file (origine ``filet``) —
la lecture n'écrit rien. ``brouillons_a_mettre_a_jour`` (ADEV148) : les
brouillons RETOUCHÉS nés d'une version plus ancienne (un brouillon intact suit
seul, ADEV147 ; ``conception/brouillons.py``).
"""

#: Les valeurs comparées entre un devis et la conception (clés de ``valeurs``).
VALEURS_COMPAREES = ('nb_panneaux', 'module', 'nombre_onduleurs', 'production_annuelle')


def _porteur(lead_id, calepinage_id):
    if lead_id:
        return {'lead_id': lead_id}
    if calepinage_id:
        return {'lead__isnull': True, 'calepinage_id': calepinage_id}
    raise ValueError('Une conception se lit par son lead ou son calepinage.')


def _versions(company, lead_id, calepinage_id):
    from .models import ConceptionLead
    if company is None:
        return ConceptionLead.objects.none()
    return ConceptionLead.objects.filter(company=company, **_porteur(lead_id, calepinage_id))


def conception_courante(company, lead_id=None, *, calepinage_id=None, suivi_des_devis=True):
    """La version COURANTE du porteur (de ``company``), forme du contrat.
    ``suivi_des_devis=False`` (relecture E5, coût des requêtes) : ``ecart_devis`` et
    ``brouillons_a_mettre_a_jour`` servis vides — pour un lecteur qui sert lui-même
    l'écart du devis qu'il montre (le calepinage, ``devis_retenu.bloc_conception``)."""
    version = _versions(company, lead_id, calepinage_id).filter(courante=True).select_related('company').first()
    return None if version is None else _forme(version, suivi_des_devis=suivi_des_devis)


def historique_conception(company, lead_id=None, *, calepinage_id=None):
    """``[{version, courante, etat, calcule_le, empreinte, declencheur,
    entrees_utilisees}]``, la plus récente d'abord (le journal par version)."""
    return [{'version': v.version, 'courante': v.courante, 'etat': v.etat,
             'calcule_le': v.calcule_le.isoformat(), 'empreinte': v.empreinte,
             'declencheur': v.declencheur, 'entrees_utilisees': v.entrees_utilisees}
            for v in _versions(company, lead_id, calepinage_id).order_by('-version')]


def _forme(version, suivi_des_devis=True):
    from .conception.moteur import CLES_SORTIE
    forme = {cle: getattr(version, cle) for cle in CLES_SORTIE}
    suivi = suivi_des_devis and version.lead_id
    forme.update(
        option_retenue=version.option_retenue or None, lead=version.lead_id, calepinage=version.calepinage_id,
        empreinte_pose=version.empreinte_pose, declencheur=version.declencheur, version=version.version,
        calcule_le=version.calcule_le.isoformat(), perimee=_perimee(version),
        brouillons_a_mettre_a_jour=_brouillons_a_mettre_a_jour(version) if suivi else [],
        ecart_devis=ecart_devis(_devis_envoye_du_lead(version)) if suivi else [])
    return forme


def _brouillons_a_mettre_a_jour(version):
    """ADEV148 — les brouillons RETOUCHÉS du lead nés d'une version plus
    ancienne (``conception/brouillons.py``) ; ``[]`` sans lead."""
    from .conception.brouillons import brouillons_a_mettre_a_jour
    if not version.lead_id:
        return []
    return brouillons_a_mettre_a_jour(version.company_id, version.lead_id, version.version)


def _empreinte_des_entrees(version):
    """L'empreinte des entrées ACTUELLES du porteur de ``version`` (la pose
    qu'elle a utilisée comprise), par les mêmes fonctions que l'écrivain —
    aucune seconde comparaison, aucun calcul, aucune écriture."""
    from types import SimpleNamespace

    from .conception.entrees import entrees_pour
    from .conception.moteur import empreinte_conception, reglages_lus_sans_creer
    from .conception.service import _porteur

    company = version.company
    lead, _filtre, refus = _porteur(version.lead, company, None if version.lead_id else version.calepinage_id)
    if refus is not None or lead is None:
        return None
    pose = version.empreinte_pose
    toit = SimpleNamespace(empreinte=pose, plafond_panneaux=None) if pose else None
    # Relecture E6 B1 — les désignations à la main du calepinage de la version entrent
    # dans l'empreinte rangée (``service.relancer``) : la lecture les relit par la MÊME porte.
    imposes = None
    if version.calepinage_id:
        from .conception.porte_calepinage import designations_du_calepinage
        imposes = designations_du_calepinage(company, version.calepinage_id) or None
    with reglages_lus_sans_creer(company):
        return empreinte_conception(entrees_pour(lead, company, toit=toit), imposes)


def _perimee(version):
    """ADEV140 — ``True`` quand les entrées du porteur ne sont plus celles de
    la version ; la relance (``conception/receivers.py::mettre_en_file``,
    dédupliquée) part alors une fois. Une lecture illisible ne dit rien."""
    import logging

    from .conception.receivers import mettre_en_file

    try:
        actuelle = _empreinte_des_entrees(version)
    except Exception:  # noqa: BLE001 — une lecture ne tombe jamais pour le filet (D-ENF22-BLE001)
        logging.getLogger(__name__).warning('ADEV140 : empreinte des entrées illisible (conception #%s)',
                                            version.pk, exc_info=True)
        return False
    if actuelle is None or actuelle == version.empreinte:
        return False
    mettre_en_file(version.company_id, lead_id=version.lead_id,
                   calepinage_id=None if version.lead_id else version.calepinage_id, origine='filet', champs=[])
    return True


#: Relecture E6 m3 — une version rangée AVANT les verdicts (ACAL2016) : rien n'est jugé.
MOTIF_A_RECALCULER = 'conception à recalculer'


def verdicts_pour_le_calepinage(company, conception, pose):
    """Relecture E6 M4 + m3 — ``(verdicts | None, note, a_recalculer)`` que « Prêt à
    envoyer ? » montre pour la POSE ``pose`` (``{nb_panneaux, kwc, ratio, onduleur_produit,
    chaines}``, lue par le calepinage) face à la conception servie ``conception`` (forme du
    contrat) :

    * même nombre de panneaux : le verdict RANGÉ, tel quel ;
    * nombre différent (au niveau 14 la pose n'est pas une entrée du moteur) : LA MÊME
      règle, par la porte du moteur (``porte_calepinage.verdicts_electriques``, celle qui a
      produit le verdict rangé — aucune seconde règle, aucun seuil copié), pour le compte
      et le matériel de la pose ; ``note`` dit pour quoi il est jugé ;
    * version rangée sans ``verdicts`` (d'avant leur calcul) : ``a_recalculer`` et UNE
      relance part en file (le filet ADEV140) — jamais « Compléter la fiche technique »."""
    from .conception.porte_calepinage import verdicts_electriques
    from .conception.receivers import mettre_en_file

    valeurs = (conception.get('valeurs') or {}).get(conception.get('option_retenue')) or {}
    if 'verdicts' not in valeurs:
        if conception.get('lead'):
            mettre_en_file(company.pk, lead_id=conception['lead'], origine='filet', champs=[])
        return None, '', True
    verdicts = (valeurs.get('verdicts') or {}).get('valeur') or {}
    nombre, posees = (valeurs.get('nb_panneaux') or {}).get('valeur'), (pose or {}).get('nb_panneaux')
    if not posees or nombre is None or posees == nombre or (pose or {}).get('ratio') is None:
        return verdicts, '', False
    onduleurs = (valeurs.get('onduleurs') or {}).get('valeur') or []
    produit = pose.get('onduleur_produit')
    lignes = ([o for o in onduleurs if o.get('produit') == produit]
              or ([{'produit': produit, 'designation': None, 'quantite': 1}] if produit else onduleurs))
    design = {'ratio_dc_ac': pose['ratio'], 'chaines': pose.get('chaines') or [],
              'materiel': {'onduleur': {'designation': lignes[0].get('designation') if lignes else None}}}
    jugees = verdicts_electriques(company, design, lignes, pose.get('kwc'))
    if jugees is None:
        return verdicts, '', False
    return (dict(jugees, non_calcule=None),
            'jugé pour la pose : %d panneaux — la conception du lead en compte %d' % (posees, nombre), False)


def _devis_envoye_du_lead(version):
    """Le devis ENVOYÉ (ou accepté), actif, le plus récent du lead."""
    from .models import Devis
    return (Devis.objects.filter(company_id=version.company_id, lead_id=version.lead_id, is_active=True,
                                 statut__in=(Devis.Statut.ENVOYE, Devis.Statut.ACCEPTE))
            .order_by('-pk').first())


def manques_du_moteur(lead):
    """``[{champ, label}]`` : le lieu (refus ``localisation_inconnue``), puis
    les groupes requis du devis automatique (``crm.selectors.
    champs_devis_auto_manquants``, la garde que le moteur applique). Liste vide
    = le moteur peut calculer ; rien n'est calculé ici."""
    from apps.crm.selectors import champs_devis_auto_manquants

    from .conception.moteur import refus_localisation
    from .conception.service import libelle_champ

    if lead is None:
        return []
    manques = []
    refus = refus_localisation(lead)
    if refus is not None:
        manques.append({'champ': refus['champ'], 'label': libelle_champ(lead, refus['champ'])})
    vus = {m['champ'] for m in manques}
    return manques + [{'champ': m['champ'], 'label': m['label']} for m in champs_devis_auto_manquants(lead)
                      if m['champ'] not in vus]


def ecart_devis(devis, *, retenue=None):
    """``[{valeur, devis, conception, devis_ref, reviser_possible,
    mise_a_jour_proposee, courante_refusee}]`` — chaque valeur de
    :data:`VALEURS_COMPAREES` qui diffère entre ``devis`` (lu tel qu'il est
    FIGÉ : ``selectors_calepinage.conception_retenue_du_devis``, rien n'est
    recalculé ni écrit) et la DERNIÈRE version COMPLÈTE de son lead, pour
    l'option que le devis a retenue. ADEV146 (relecture m5) : une version
    courante en REFUS ne fait pas disparaître l'écart — il reste comparé à la
    dernière version complète et ``courante_refusee`` le dit. ``reviser_possible`` : la révision existe
    pour ce devis (actif, pas un brouillon — ``domain/revision.py``) ;
    ``mise_a_jour_proposee`` (ADEV148) : un brouillon actif RETOUCHÉ, né d'une
    version plus ancienne, propose « Mettre à jour » (rien n'est écrit ici).
    Vide sans devis, sans lead, sans conception. ``retenue`` : la conception retenue du
    devis déjà lue par l'appelant (relecture E5, coût des requêtes : jamais relue)."""
    from django.db.models import Q

    from .models import ConceptionLead, Devis
    from .selectors_calepinage import conception_retenue_du_devis

    if devis is None or not devis.lead_id:
        return []
    # UNE lecture : la dernière version complète et la courante (relecture E5, coût des requêtes).
    lues = list(ConceptionLead.objects.filter(company_id=devis.company_id, lead_id=devis.lead_id)
                .filter(Q(etat=ConceptionLead.Etat.COMPLET) | Q(courante=True))
                .only('pk', 'etat', 'courante', 'version', 'valeurs', 'option_retenue').order_by('-version'))
    version = next((v for v in lues if v.etat == ConceptionLead.Etat.COMPLET), None)
    courante_refusee = any(v.courante and v.etat == ConceptionLead.Etat.REFUS for v in lues)
    if version is not None and retenue is None:
        retenue = conception_retenue_du_devis(devis)
    elif version is None:
        retenue = None
    if not retenue:
        return []
    module = retenue.get('module') or {}
    du_devis = {'nb_panneaux': module.get('quantite'), 'module': module.get('designation'),
                'nombre_onduleurs': sum(o.get('quantite') or 0 for o in retenue.get('onduleurs') or []) or None,
                'production_annuelle': retenue.get('production_annuelle_kwh')}
    valeurs = version.valeurs.get(retenue.get('option')) or version.valeurs.get(version.option_retenue) or {}
    revisable = bool(devis.is_active) and devis.statut != Devis.Statut.BROUILLON
    proposee = _mise_a_jour_proposee(devis, version)
    ecarts = []
    for cle in VALEURS_COMPAREES:
        a, b = du_devis.get(cle), (valeurs.get(cle) or {}).get('valeur')
        if a is None or b is None or _egales(a, b):
            continue
        ecarts.append({'valeur': cle, 'devis': _lisible(a), 'conception': _lisible(b), 'devis_ref': devis.reference,
                       'reviser_possible': revisable, 'mise_a_jour_proposee': proposee,
                       'courante_refusee': courante_refusee})
    return ecarts


def _mise_a_jour_proposee(devis, version):
    from .conception.brouillons import est_retouche
    from .models import Devis
    nee_de = (devis.conception_source or {}).get('version')
    return bool(devis.statut == Devis.Statut.BROUILLON and devis.is_active and nee_de is not None
                and nee_de < version.version and est_retouche(devis))


def _nombre(valeur):
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _egales(a, b):
    """Deux nombres au kWh / à l'unité près ; sinon égalité stricte."""
    x, y = _nombre(a), _nombre(b)
    if x is not None and y is not None:
        return round(x) == round(y)
    return a == b


def _lisible(valeur):
    nombre = _nombre(valeur)
    if nombre is None:
        return valeur
    return int(round(nombre)) if not isinstance(valeur, bool) else valeur


def champs_entrees(marche):
    """Les colonnes du lead entrées du moteur pour ``marche`` (``KeyError``
    pour un marché inconnu) : ce que l'émetteur ``lead_entrees_modifiees``
    surveille (ALEA68)."""
    from .conception.champs import champs_pour
    return champs_pour(marche)
