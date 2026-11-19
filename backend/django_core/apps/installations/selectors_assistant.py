"""Copilote vague 2 (CHTA2, CHTA3, CHTA7) — lectures COMPACTES des chantiers
pour l'assistant (action ``installations.chantier.etat``, carte
``fiche_chantier``).

Contrat : ``contract_samples/assistant_chantier_etat.json`` (une fiche, aussi
rendue par ``POST chantiers/{id}/planifier-pose/``). Chaque fonction publique
rend un dictionnaire LITTÉRAL dont les clés sont celles de l'échantillon.

Règles :
* lecture seule ; la portée est celle de l'APPELANT (chantier lu par
  ``InstallationViewSet.get_queryset``) ;
* le statut est la couche PROPRE du chantier (statut canonique), jamais
  STAGES.py ; rien ici ne le change ;
* aucun prix, coût, prix d'achat ni montant de commande fournisseur ; aucun
  téléphone de client ; aucune position de personne ;
* le besoin matériel (``compute_besoin_materiel``, une requête par produit)
  n'est calculé que pour UNE fiche (``etat_chantier``), jamais par ligne de
  liste.
"""
import datetime

#: Ensemble FERMÉ des « à faire » (fiche ET lignes ; une ligne de liste ne
#: rend jamais ``commander_materiel`` : le matériel n'y est pas calculé).
A_FAIRE = ('commander_materiel', 'encaisser_acompte', 'planifier_pose',
           'assigner_technicien', 'poser', 'rien')
#: Ensemble FERMÉ des blocages d'une ligne (sans le besoin matériel).
BLOCAGES = ('sans_date', 'sans_technicien', 'pose_sans_intervention',
            'pose_depassee', 'acompte_non_encaisse')
MANQUES_MAX = 8
DESIGNATION_MAX = 80
LIEN_APPRO = '/chantiers/approvisionnement'
#: Statut d'un BCF brouillon (``BonCommandeFournisseur.Statut.BROUILLON``,
#: lu dans la ligne servie par ``achats.selectors.bcf_du_chantier``).
_BCF_BROUILLON = 'brouillon'


def _statuts():
    """(statuts canoniques après la pose, statuts stockés AVANT la pose)."""
    from .models import Installation
    s = Installation.Statut
    fin = (s.INSTALLE, s.RECEPTIONNE, s.CLOTURE)
    avant = [v for v in s.values if Installation.canonical_statut(v) not in fin]
    return fin, avant


def lien_chantier(pk):
    return f'/chantiers?id={pk}'


def _iso(jour):
    return jour.isoformat() if jour else None


def _nom(user):
    if user is None:
        return ''
    return (user.get_full_name() or '').strip() or user.username


def _client_nom(inst):
    client = inst.client if inst.client_id else None
    return f"{client.nom} {client.prenom or ''}".strip() if client else ''


def poses_par_chantier(company_id, ids):
    """``{chantier_id: intervention de pose la plus proche}`` en UNE requête :
    pose non annulée ; d'abord la non terminée la plus tôt datée (une non
    datée en dernier), sinon la dernière terminée."""
    from .models import Intervention
    finies = (Intervention.Statut.TERMINEE, Intervention.Statut.VALIDEE)
    groupes = {}
    for pose in (Intervention.objects
                 .filter(company_id=company_id, installation_id__in=list(ids),
                         type_intervention=Intervention.Type.POSE, annulee=False)
                 .select_related('technicien')):
        groupes.setdefault(pose.installation_id, []).append(pose)
    choix = {}
    for chantier_id, poses in groupes.items():
        ouvertes = [p for p in poses if p.statut not in finies]
        if ouvertes:
            choix[chantier_id] = min(ouvertes, key=lambda p: (
                p.date_prevue is None, p.date_prevue or datetime.date.max, p.pk))
        else:
            choix[chantier_id] = max(poses, key=lambda p: (
                p.date_prevue or datetime.date.min, p.pk))
    return choix


def acompte_exige_par_societe(company):
    """Le réglage société « acompte avant planification » est-il allumé ?"""
    if company is None:
        return False
    from apps.parametres.models import CompanyProfile
    return bool(getattr(CompanyProfile.get(company),
                        'exiger_acompte_avant_planification', False))


def _acompte_paye(inst, company):
    from apps.ventes.selectors import acompte_paye_pour_devis
    return bool(inst.devis_id and acompte_paye_pour_devis(inst.devis_id, company))


def blocages_du_chantier(inst, pose, aujourdhui, acompte_bloque):
    """Blocages GRATUITS d'un chantier pas encore posé (ensemble fermé
    :data:`BLOCAGES`, dans cet ordre) ; un chantier installé ou au-delà n'en a
    aucun."""
    from .models import Installation
    fin, _avant = _statuts()
    if Installation.canonical_statut(inst.statut) in fin:
        return []
    date_pose = inst.date_pose_prevue
    blocages = []
    if date_pose is None:
        blocages.append('sans_date')
    if not inst.technicien_responsable_id:
        blocages.append('sans_technicien')
    if date_pose is not None and (pose is None or pose.date_prevue is None):
        blocages.append('pose_sans_intervention')
    if date_pose is not None and (inst.date_pose_fin_prevue or date_pose) < aujourdhui:
        blocages.append('pose_depassee')
    if acompte_bloque:
        blocages.append('acompte_non_encaisse')
    return blocages


def a_faire(inst, blocages, nb_manques=0):
    """L'action suivante (ensemble fermé :data:`A_FAIRE`)."""
    from .models import Installation
    fin, _avant = _statuts()
    if inst.annule or Installation.canonical_statut(inst.statut) in fin:
        return 'rien'
    if nb_manques:
        return 'commander_materiel'
    if 'acompte_non_encaisse' in blocages:
        return 'encaisser_acompte'
    if {'sans_date', 'pose_sans_intervention', 'pose_depassee'} & set(blocages):
        return 'planifier_pose'
    if 'sans_technicien' in blocages:
        return 'assigner_technicien'
    return 'poser'


def _materiel(appro):
    """Quantités seulement (jamais un prix) : compteurs du résumé, BCF
    brouillons, et au plus :data:`MANQUES_MAX` lignes en manque."""
    resume = appro['resume']
    manques = [{'produit_id': li['produit_id'],
                'designation': (li['designation'] or '')[:DESIGNATION_MAX],
                'manque': li['manque']}
               for li in appro['lignes'] if li['manque'] > 0][:MANQUES_MAX]
    return {
        'nb_lignes': resume['nb_lignes'],
        'nb_manques': resume['nb_manques'],
        'nb_en_commande': resume['nb_en_commande'],
        'nb_recues': resume['nb_recues'],
        'bcf_brouillons': sum(1 for bon in appro['bons_commande']
                              if bon['statut'] == _BCF_BROUILLON),
        'manques': manques,
    }


def _planning(inst, pose):
    tech = inst.technicien_responsable if inst.technicien_responsable_id else None
    return {
        'date_pose_prevue': _iso(inst.date_pose_prevue),
        'date_pose_fin_prevue': _iso(inst.date_pose_fin_prevue),
        'technicien': {'id': tech.pk, 'nom': _nom(tech)} if tech else None,
        'intervention_pose': None if pose is None else {
            'id': pose.pk,
            'date_prevue': _iso(pose.date_prevue),
            'technicien_nom': _nom(pose.technicien if pose.technicien_id else None),
            'statut': pose.statut,
        },
    }


def _etapes(inst):
    """(étape courante, étape suivante et son gate) — ``(None, None)`` tant
    que la société n'a pas amorcé ses étapes (CH2)."""
    from .services import etape_courante, stage_gate_status, stages_actifs
    stages = stages_actifs(inst.company)
    if not stages:
        return None, None
    courante = etape_courante(inst)
    ids = [s.pk for s in stages]
    rang = ids.index(courante.pk) + 1 if courante is not None and courante.pk in ids else 0
    suivante = stages[rang] if rang < len(stages) else None
    prochaine = None
    if suivante is not None:
        gate = stage_gate_status(inst, suivante)
        prochaine = {'cle': gate['cle'],
                     'bloquante': bool(suivante.bloquant and not gate['satisfait']),
                     'raisons': list(gate['raisons'])}
    etape = {'cle': courante.cle, 'libelle': courante.libelle} if courante else None
    return etape, prochaine


def etat_acompte(inst):
    """``{exige, encaisse}`` : exigé = réglage société allumé ET devis lié."""
    exige = bool(inst.devis_id) and acompte_exige_par_societe(inst.company)
    return {'exige': exige, 'encaisse': _acompte_paye(inst, inst.company)}


def etat_chantier(inst, aujourdhui=None):
    """La fiche compacte d'UN chantier (``assistant_chantier_etat.json``) :
    prêt à poser et pourquoi (UN calcul du besoin matériel, via
    ``approvisionnement_chantier``), matériel en quantités, acompte, pose,
    étape suivante, ``a_faire`` et liens."""
    from .models import Installation
    from .selectors import approvisionnement_chantier
    aujourdhui = aujourdhui or datetime.date.today()
    appro = approvisionnement_chantier(inst)
    materiel = _materiel(appro)
    pose = poses_par_chantier(inst.company_id, [inst.pk]).get(inst.pk)
    acompte = etat_acompte(inst)
    blocages = blocages_du_chantier(
        inst, pose, aujourdhui, acompte['exige'] and not acompte['encaisse'])
    etape, prochaine = _etapes(inst)
    canon = Installation.canonical_statut(inst.statut)
    return {
        'id': inst.pk,
        'reference': inst.reference,
        'client_nom': _client_nom(inst),
        'statut': canon,
        'statut_libelle': dict(Installation.Statut.choices).get(canon, canon),
        'annule': bool(inst.annule),
        'etape_courante': etape,
        'planning': _planning(inst, pose),
        'pret_a_poser': bool(appro['resume']['pret_a_poser']),
        'raisons': list(appro['resume']['raisons']),
        'materiel': materiel,
        'acompte': acompte,
        'prochaine_etape': prochaine,
        'a_faire': a_faire(inst, blocages, materiel['nb_manques']),
        'lien': lien_chantier(inst.pk),
        'liens': {
            'chantier': lien_chantier(inst.pk),
            'approvisionnement': LIEN_APPRO,
            'intervention_pose': f'/interventions?id={pose.pk}' if pose else None,
        },
    }
