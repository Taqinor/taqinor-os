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
import logging

logger = logging.getLogger(__name__)

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


def conception_courante(company, lead_id=None, *, calepinage_id=None, suivi_des_devis=True,
                        peremption=True):
    """La version COURANTE du porteur (de ``company``), forme du contrat.
    ``suivi_des_devis=False`` (relecture E5, coût des requêtes) : ``ecart_devis`` et
    ``brouillons_a_mettre_a_jour`` servis vides — pour un lecteur qui sert lui-même
    l'écart du devis qu'il montre (le calepinage, ``devis_retenu.bloc_conception``).
    ``peremption=False`` (coût d'une LISTE) : ni empreinte des entrées recalculée, ni relance
    du filet ADEV140 — ``perimee`` servi ``False`` ; réservé aux listes qui n'en lisent rien."""
    version = _versions(company, lead_id, calepinage_id).filter(courante=True).select_related('company').first()
    return None if version is None else _forme(version, suivi_des_devis=suivi_des_devis, peremption=peremption)


def kwc_de_la_conception_courante(company, lead_id):
    """ACAL2021 — le kWc de l'option retenue de la conception COURANTE d'un lead, lu en UNE
    requête de trois colonnes (la pastille de la fiche du lead n'a besoin ni du payback, ni de
    l'écart des devis, ni de « périmée » : ``conception_courante`` en coûtait plusieurs à chaque
    ouverture de fiche). ``None`` sans conception, en refus ou sans valeur — jamais supposé."""
    ligne = (_versions(company, lead_id, None).filter(courante=True)
             .values('etat', 'valeurs', 'option_retenue').first())
    if not ligne or ligne['etat'] != 'complet':
        return None
    valeurs = ligne['valeurs'] or {}
    option = ligne['option_retenue'] or next(iter(valeurs), None)
    return ((valeurs.get(option) or {}).get('puissance_kwc') or {}).get('valeur')


def historique_conception(company, lead_id=None, *, calepinage_id=None):
    """``[{version, courante, etat, calcule_le, empreinte, declencheur,
    entrees_utilisees}]``, la plus récente d'abord (le journal par version)."""
    return [{'version': v.version, 'courante': v.courante, 'etat': v.etat,
             'calcule_le': v.calcule_le.isoformat(), 'empreinte': v.empreinte,
             'declencheur': v.declencheur, 'entrees_utilisees': v.entrees_utilisees}
            for v in _versions(company, lead_id, calepinage_id).order_by('-version')]


def _forme(version, suivi_des_devis=True, peremption=True):
    from .conception.moteur import CLES_SORTIE
    forme = {cle: getattr(version, cle) for cle in CLES_SORTIE}
    suivi = suivi_des_devis and version.lead_id
    forme.update(
        option_retenue=version.option_retenue or None, lead=version.lead_id, calepinage=version.calepinage_id,
        empreinte_pose=version.empreinte_pose, declencheur=version.declencheur, version=version.version,
        calcule_le=version.calcule_le.isoformat(), perimee=_perimee(version) if peremption else False,
        brouillons_a_mettre_a_jour=_brouillons_a_mettre_a_jour(version) if suivi else [],
        ecart_devis=ecart_devis(_devis_envoye_du_lead(version)) if suivi else [])
    forme['valeurs'], forme['payback_devis'] = _payback_servi(version, forme['valeurs'])
    return forme


#: Relecture E6 — sans devis de référence, le retour sur investissement n'est pas chiffrable.
MOTIF_PAYBACK_SANS_DEVIS = 'retour sur investissement : après un premier devis'


def _devis_de_reference(version):
    """Le devis de RÉFÉRENCE du lead pour le payback : le brouillon ou devis actif qui pointe
    sur CETTE version (``Devis.conception_source``), sinon le devis envoyé ou accepté le plus
    récent ; ``None`` sinon. Lu, jamais écrit."""
    from .models import Devis
    if not version.lead_id:
        return None
    actifs = Devis.objects.filter(company_id=version.company_id, lead_id=version.lead_id, is_active=True)
    return (actifs.filter(conception_source__version=version.version).order_by('-pk').first()
            or _devis_envoye_du_lead(version))


def _payback_servi(version, valeurs):
    """Relecture E6 — le payback SERVI À LA LECTURE (jamais rangé périmé) : par option, LA
    fonction du PDF (``quote_engine/pricing.payback_publiable``, appelée telle quelle) sur
    l'investissement TTC de l'option du devis de référence et l'économie de la conception,
    provision d'onduleur au prix de ses lignes ; ``source: 'devis'``. Rend ``(valeurs,
    {devis_ref, motif})`` ; sans devis : payback ``None`` et le motif dit."""
    import copy

    if version.etat != 'complet' or version.marche == 'agricole':
        return valeurs, {'devis_ref': None, 'motif': None}
    devis = _devis_de_reference(version)
    if devis is None:
        return valeurs, {'devis_ref': None, 'motif': MOTIF_PAYBACK_SANS_DEVIS}
    from . import offres_tailles
    from .domain.catalogue import classer_produit
    from .conception.valeurs import entrees_du_payback
    from .domain.classe_ligne import role_de_ligne
    from .quote_engine.pricing import payback_publiable
    from .utils.options import (AVEC_BATTERIE, SANS_BATTERIE, deux_options_declarees, filter_lines_for_option,
                                lignes_avec_produit, option_totaux)

    servies, lignes = copy.deepcopy(valeurs), list(lignes_avec_produit(devis))
    if version.marche in ('commercial', 'industriel'):
        # T4-X6-006 — C&I : LE retour que le PDF du devis imprime, lu, jamais recalculé.
        for option, table in servies.items():
            if 'payback' in table:
                table['payback'] = _payback_ci(devis, option, len(servies) > 1)
        return servies, {'devis_ref': devis.reference, 'motif': None}
    # T4-X7-001 — le DEVIS dit s'il porte deux options, pas la conception : une conception à une
    # option lue sur un devis à deux options sommait les lignes des deux (97 400 MAD pour 7 987 MAD/an).
    # Budget de requêtes : les lignes DÉJÀ lues ci-dessus, jamais relues pour ce prédicat.
    deux_au_devis = len(servies) > 1 or deux_options_declarees(devis, lignes=lignes)
    for option, table in servies.items():
        if 'payback' not in table:
            continue
        # Les lignes de l'option, découpées comme le PDF (une option seule : ses lignes).
        panier = AVEC_BATTERIE if option == 'avec' else SANS_BATTERIE
        de_l_option = filter_lines_for_option(lignes, panier, devis=devis) if deux_au_devis else lignes
        portees = [li for li in de_l_option if li.type_ligne == 'produit']
        # Lane E6d — LA provision d'onduleur des cartes (``offres_tailles._cout_onduleur_ttc``),
        # rôles du classifieur catalogue, remise du devis : un seul calcul. Lecteurs en aval
        # (constat 5) : le rôle RANGÉ d'abord, comme le PDF (``etude_chiffrage._cout_onduleur``) ;
        # devis envoyé avant ``COUPURE_CLASSE_PAR_ROLE`` : le classifieur d'hier.
        cout = offres_tailles._cout_onduleur_ttc(
            portees, [role_de_ligne(li, lambda li=li: classer_produit(
                getattr(li.produit, 'nom', '') or li.designation), devis=devis) for li in portees],
            1 - float(devis.remise_globale or 0) / 100, devis.taux_tva, getattr(devis, 'company', None), devis)
        investissement = option_totaux(devis, '', lignes=de_l_option)['ttc']
        economie = (table.get('economies_annuelles') or {}).get('valeur')
        # Modèle HORAIRE (résidentiel) : l'économie « avec » est déjà nette du rendement de la batterie,
        # le cashflow n'en re-déduit rien (part stockée 0, comme le PDF, AMOT58).
        horaire = {'part_batterie': 0} if version.marche == 'residentiel' else {}
        table['payback'] = dict({'valeur': payback_publiable(investissement, economie, stockage=option == 'avec',
                                                             cout_onduleur_ttc=cout, **horaire)['payback_years'],
                                 'unite': 'ans', 'source': 'devis'},
                                **entrees_du_payback(investissement, economie, cout,
                                                     stockage=option == 'avec' and version.marche != 'residentiel'))
    return servies, {'devis_ref': devis.reference, 'motif': None}


def _payback_ci(devis, option, deux_options):
    """T4-X6-006 — le retour C&I de ``option`` tel que le PDF du devis l'imprime : « avec »
    d'un devis à deux options (ou toute option qui sert ``option_avec``) =
    ``etude_ci.option_avec.retour_simple_ans`` et son flux ``economie_flux``
    (``ci/options_cote.lignes_avec``) ; sinon le bloc ``economie_ci_pour_devis`` au dixième
    (``ci/couverture.retour_dixieme``, CE2E3 — comme la bannière ``_resume_devis_auto``).
    À côté : montant et économie de l'année 1 de CE flux, sur SA base (HT quand la TVA est
    récupérable, D-CIQ-3). Rien de servi (flux absent, investissement non chiffré) ⇒ valeur
    ``None`` et ``calcul`` dit pourquoi — jamais un second calcul."""
    from .domain.regles_calcul import REGLES_CORRIGEES_2710, regles_au_moins
    from .quote_engine.ci.couverture import retour_dixieme

    etude = (devis.etude_params or {}).get('etude_ci') or {}
    avec = etude.get('option_avec') if isinstance(etude.get('option_avec'), dict) else None
    if option == 'avec' and (deux_options or avec):
        bloc, retour = (avec or {}).get('economie_flux'), (avec or {}).get('retour_simple_ans')
    else:
        from .economie_ci import STATUT_CALCULE, economie_ci_pour_devis
        try:
            bloc = economie_ci_pour_devis(devis, devis.company) or {}
        except Exception:  # lecture seule : la carte se passe du retour, le PDF le dira
            logger.warning('conception : retour C&I du devis %s indisponible', devis.reference, exc_info=True)
            bloc = {}
        bloc = bloc if bloc.get('statut') == STATUT_CALCULE else None
        retour = ((bloc or {}).get('indicateurs') or {}).get('retour_ans')
        if retour is not None and regles_au_moins(devis, REGLES_CORRIGEES_2710):
            retour = retour_dixieme(bloc, retour)
    return dict({'valeur': retour, 'unite': 'ans', 'source': 'devis'}, **_entrees_flux_ci(bloc, retour))


def _entrees_flux_ci(bloc, retour):
    """Montant, économie de l'année 1 et base du flux PRINCIPAL servi (hypothèses de
    ``economie.flux_de_tresorerie`` : les entrées exactes du retour imprimé)."""
    from core.money import quantize_mad

    from .economie_ci import BASE_TTC

    bloc = bloc if isinstance(bloc, dict) else {}
    base = 'TTC' if bloc.get('base') == BASE_TTC else 'HT'
    flux = bloc.get('flux_ttc' if base == 'TTC' else 'flux_ht') or {}
    lues = {h.get('cle'): h.get('valeur') for h in flux.get('hypotheses') or [] if isinstance(h, dict)}
    montant, economie = lues.get('investissement_mad'), lues.get('economie_annee1_mad')
    remplacements = ', '.join('%s la %de année' % (r.get('equipement'), r.get('annee'))
                              for r in lues.get('remplacements') or [] if isinstance(r, dict))
    if retour is None:
        calcul = 'Retour non chiffré sur ce devis : investissement ou économies non servis.'
    else:
        calcul = 'Cumul des économies %s du flux du devis sur %s ans%s jusqu’à couvrir le montant %s.' % (
            base, lues.get('horizon_ans') or 25, ' (remplacements : %s)' % remplacements if remplacements else '',
            base)
    return {'investissement': float(quantize_mad(montant)) if montant else None, 'base': base,
            'investissement_ttc': None, 'economie_annuelle': float(quantize_mad(economie)) if economie else None,
            'cout_onduleur_ttc': None, 'calcul': calcul}


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
    imposes, calepinage_id, lu = None, version.calepinage_id, None
    if version.lead_id and not calepinage_id:
        # Lane E6e — la résolution de l'écrivain (``porte_calepinage.calepinage_du_lead``) : une
        # version rangée sans le calepinage ouvert du lead est périmée, une relance la range avec.
        # Coût des requêtes : le calepinage lu sert aussi ses désignations (pas de seconde lecture).
        from .conception.porte_calepinage import calepinage_et_toit_du_lead
        calepinage_id, toit, lu = calepinage_et_toit_du_lead(company, lead, None, toit)
    if calepinage_id:
        from .conception.moteur import consommation_imposee
        from .conception.porte_calepinage import designations_du_calepinage
        imposes = designations_du_calepinage(company, calepinage_id, lu) or None
        # Reste d'ACAL2020 — le relevé collé, relu par LA MÊME porte que l'écrivain (niveau 15).
        lead, _conso = consommation_imposee(lead, company, calepinage_id)
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
    kwc_conception = (valeurs.get('puissance_kwc') or {}).get('valeur')
    # T4-X3-009 — même compte mais autre puissance de module (8 × 710 W contre 8 × 550 W) : autre pose.
    meme_pose = posees == nombre and not _autre_puissance(kwc_conception, (pose or {}).get('kwc'))
    if not posees or nombre is None or meme_pose or (pose or {}).get('ratio') is None:
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
            'jugé pour la pose : %d panneaux — la conception du lead en compte %s'
            % (posees, _compte_de_la_conception(nombre, kwc_conception)), False)


def _autre_puissance(kwc_conception, kwc_pose):
    """T4-X3-009 — vrai quand les deux puissances sont connues et diffèrent (au centième de kWc)."""
    return kwc_conception is not None and kwc_pose is not None and abs(float(kwc_conception) - float(kwc_pose)) >= 0.01


def _compte_de_la_conception(nombre, kwc):
    """T4-X3-009 — « 8 de 550 W » : le compte de la conception NOMME son panneau (jamais un « 8 » nu
    à côté de panneaux d'une autre puissance) ; sans puissance servie, le compte seul, comme avant."""
    if not kwc or not nombre:
        return '%d' % nombre
    return '%d de %s W' % (nombre, '{:g}'.format(round(float(kwc) * 1000 / nombre)))


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
