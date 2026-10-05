"""VEIL18 — Mesures automatiques d'une découverte (contrat ``veille_mesures.json``).

``calculer(decouverte)`` produit toutes les clés du contrat VEIL4 depuis les
pubs vues et les requêtes. RÈGLE : une valeur non calculable vaut ``None``
accompagnée d'un ``motif_fr`` — JAMAIS 0 (« calculé et nul » ≠ « non
calculable »). Les parts sont des fractions 0..1 (4 décimales).

Le rappel sur les concurrents nommés lit la liste ``CompetitorPage`` de la
société (même app) : rapprochement par ``page_id``, sinon nom normalisé, sinon
domaine du site.
"""
from __future__ import annotations

import datetime
import re
import statistics
import unicodedata
from collections import defaultdict

from django.utils import timezone

JOURS_ACTIVITE = 5


def _part(numerateur, denominateur):
    if not denominateur:
        return None
    return round(numerateur / denominateur, 4)


def normaliser_nom(texte):
    """Nom comparable : sans accents, minuscules, alphanumérique seulement."""
    ascii_ = unicodedata.normalize('NFKD', str(texte or '')).encode(
        'ascii', 'ignore').decode('ascii')
    return re.sub(r'[^a-z0-9]+', '', ascii_.lower())


def _pubs(dec):
    from .models import VeillePubVue
    return list(VeillePubVue.objects.filter(
        company_id=dec.company_id, requete__decouverte_id=dec.pk)
        .select_related('requete', 'annonceur'))


def _annonceurs_distincts(dec, pubs, requetes):
    par_mot, par_pays = defaultdict(set), defaultdict(set)
    tous = set()
    for pv in pubs:
        page_id = pv.annonceur.page_id
        par_mot[pv.requete.mot_cle].add(page_id)
        par_pays[pv.requete.pays].add(page_id)
        tous.add(page_id)
    mots = []
    for r in requetes:
        if r.mot_cle not in mots:
            mots.append(r.mot_cle)
    pays = []
    for r in requetes:
        if r.pays not in pays:
            pays.append(r.pays)
    return {
        'par_mot_cle': [{'mot_cle': m, 'valeur': len(par_mot[m])}
                        for m in mots],
        'par_pays': [{'pays': p, 'valeur': len(par_pays[p])} for p in pays],
        'total': len(tous),
    }


def _pubs_par_appel(requetes):
    valeurs = [int(e.get('pubs', 0)) for r in requetes
               for e in (r.journal_pages or [])]
    if not valeurs:
        return {'moyenne': None, 'mediane': None, 'min': None, 'max': None,
                'motif_fr': "Aucun appel réussi : le nombre de pubs par "
                            "appel n'est pas calculable."}
    return {
        'moyenne': round(sum(valeurs) / len(valeurs), 2),
        'mediane': statistics.median(valeurs),
        'min': min(valeurs), 'max': max(valeurs), 'motif_fr': None,
    }


def _appels_par_mot_cle(requetes):
    cumul = {}
    for r in requetes:
        cumul[r.mot_cle] = cumul.get(r.mot_cle, 0) + r.appels
    return [{'mot_cle': m, 'appels': n} for m, n in cumul.items()]


def _courbe(paires):
    """``paires`` = [(numero_page, page_id)] → courbe cumulée par page."""
    if not paires:
        return []
    derniere = max(n for n, _p in paires)
    vus, courbe = set(), []
    for page in range(1, derniere + 1):
        vus |= {p for n, p in paires if n == page}
        courbe.append({'page': page, 'nouveaux_page_id_cumules': len(vus)})
    return courbe


def _saturation(pubs, requetes):
    par_requete = defaultdict(list)
    tout = []
    for pv in pubs:
        paire = (pv.numero_page, pv.annonceur.page_id)
        par_requete[pv.requete_id].append(paire)
        tout.append(paire)
    return {
        'global': _courbe(tout),
        'par_requete': [{'mot_cle': r.mot_cle, 'pays': r.pays,
                         'courbe': _courbe(par_requete.get(r.pk, []))}
                        for r in requetes],
    }


def _rappel(dec, annonceurs):
    from .models import CompetitorPage
    from .veille_decouverte import legende_vers_domaine

    concurrents = list(CompetitorPage.objects.filter(company_id=dec.company_id)
                       .order_by('name'))
    if not concurrents:
        return {'trouves': None, 'total': 0, 'absents': [],
                'motif_fr': 'Aucun concurrent nommé saisi : le rappel '
                            "n'est pas calculable."}
    page_ids = {a.page_id for a in annonceurs}
    noms = {normaliser_nom(a.page_name) for a in annonceurs if a.page_name}
    domaines = {d.get('domaine') for a in annonceurs
                for d in (a.domaines or []) if d.get('domaine')}
    trouves, absents = 0, []
    for c in concurrents:
        domaine = legende_vers_domaine(c.website) if c.website else ''
        if ((c.page_id and c.page_id in page_ids)
                or (normaliser_nom(c.name) and normaliser_nom(c.name) in noms)
                or (domaine and domaine in domaines)):
            trouves += 1
        else:
            absents.append(c.name)
    return {'trouves': trouves, 'total': len(concurrents),
            'absents': absents, 'motif_fr': None}


def _doublons(pubs, annonceurs):
    if not annonceurs:
        return {'recouvrement_entre_requetes': None,
                'annonceurs_multi_pays': None, 'domaines_partages': None,
                'motif_fr': 'Aucun annonceur trouvé : les doublons ne sont '
                            'pas calculables.'}
    requetes_par_page, pays_par_page = defaultdict(set), defaultdict(set)
    pages_par_domaine = defaultdict(set)
    for pv in pubs:
        page_id = pv.annonceur.page_id
        requetes_par_page[page_id].add(pv.requete_id)
        pays_par_page[page_id].add(pv.requete.pays)
        if pv.domaine:
            pages_par_domaine[pv.domaine].add(page_id)
    total = len(requetes_par_page)
    return {
        'recouvrement_entre_requetes': _part(
            sum(1 for s in requetes_par_page.values() if len(s) >= 2), total),
        'annonceurs_multi_pays': sum(
            1 for s in pays_par_page.values() if len(s) >= 2),
        'domaines_partages': sum(
            1 for s in pages_par_domaine.values() if len(s) >= 2),
        'motif_fr': None,
    }


def _taux_domaine(pubs):
    if not pubs:
        return {'valeur': None,
                'motif_fr': "Aucune pub n'a encore été analysée : le domaine "
                            "affiché n'est pas calculable."}
    return {'valeur': _part(sum(1 for pv in pubs if pv.domaine), len(pubs)),
            'motif_fr': None}


def _part_actives(pubs, reference):
    datees = [pv for pv in pubs if pv.debut_diffusion]
    if not datees:
        return None
    seuil = datetime.timedelta(days=JOURS_ACTIVITE)
    longues = sum(1 for pv in datees
                  if (pv.fin_diffusion or reference) - pv.debut_diffusion
                  >= seuil)
    return _part(longues, len(datees))


def _part_par_classe(annonceurs):
    from .models import VEILLE_CLASSES
    if not annonceurs:
        return []
    total = len(annonceurs)
    return [{'classe': cle,
             'part': _part(sum(1 for a in annonceurs if a.classe == cle),
                           total)}
            for cle, _l, _b in VEILLE_CLASSES]


def _part_dropshipper(annonceurs):
    juges = [a for a in annonceurs if a.dropshipper_decide_par]
    if not juges:
        return {'valeur': None,
                'motif_fr': 'Aucun verdict de dropshipper rendu : la part '
                            "n'est pas calculable."}
    return {'valeur': _part(
        sum(1 for a in juges if a.dropshipper_probable == 'oui'), len(juges)),
        'motif_fr': None}


def calculer(dec, *, maintenant=None):
    """Toutes les mesures du contrat VEIL4 pour la découverte ``dec``."""
    reference = maintenant or dec.termine_le or timezone.now()
    requetes = list(dec.requetes.all().order_by('ordre', 'id'))
    pubs = _pubs(dec)
    annonceurs = list({pv.annonceur_id: pv.annonceur for pv in pubs}.values())
    return {
        'decouverte_id': dec.pk,
        'annonceurs_distincts': _annonceurs_distincts(dec, pubs, requetes),
        'pubs_par_appel': _pubs_par_appel(requetes),
        'appels_par_mot_cle': _appels_par_mot_cle(requetes),
        'saturation': _saturation(pubs, requetes),
        'rappel_concurrents_nommes': _rappel(dec, annonceurs),
        'doublons': _doublons(pubs, annonceurs),
        'taux_remplissage_domaine': _taux_domaine(pubs),
        'part_pubs_actives_5_jours': _part_actives(pubs, reference),
        'part_par_classe': _part_par_classe(annonceurs),
        'part_dropshipper': _part_dropshipper(annonceurs),
    }


# ═════════════════════════════════════════════════════════════════════════════
# VEIL23 — Précision et rappel sur l'échantillon étiqueté (D-VEIL-4, D-VEIL-9)
# ═════════════════════════════════════════════════════════════════════════════
Z_95 = 1.959963984540054
MIN_ETIQUETTES_TEST = 200
MIN_ETIQUETTES_ETALONNAGE = 50


class MesureRefusee(Exception):
    def __init__(self, message_fr):
        self.message_fr = message_fr
        super().__init__(message_fr)


def wilson(succes, total, z=Z_95):
    """Intervalle de Wilson (95 %) d'une proportion ; ``None`` si total 0."""
    if not total:
        return None
    p = succes / total
    z2 = z * z
    denominateur = 1 + z2 / total
    centre = (p + z2 / (2 * total)) / denominateur
    demi = z * ((p * (1 - p) / total + z2 / (4 * total * total)) ** 0.5) \
        / denominateur
    return [round(max(0.0, centre - demi), 4), round(min(1.0, centre + demi), 4)]


def matrice_confusion(paires, classes):
    """``{vrai: {predit: n}}`` sur toutes les classes (zéros compris)."""
    matrice = {v: {p: 0 for p in classes} for v in classes}
    for vrai, predit in paires:
        matrice.setdefault(vrai, {p: 0 for p in classes})
        matrice[vrai][predit] = matrice[vrai].get(predit, 0) + 1
    return matrice


def precision_rappel(paires, positif):
    """P/R/F1 binaires de la classe ``positif`` (+ Wilson). ``None`` quand
    non calculable (division par zéro), jamais 0."""
    vp = sum(1 for v, p in paires if v == positif and p == positif)
    fp = sum(1 for v, p in paires if v != positif and p == positif)
    fn = sum(1 for v, p in paires if v == positif and p != positif)
    precision = round(vp / (vp + fp), 4) if vp + fp else None
    rappel = round(vp / (vp + fn), 4) if vp + fn else None
    f1 = (round(2 * precision * rappel / (precision + rappel), 4)
          if precision is not None and rappel is not None
          and precision + rappel else None)
    return {'vp': vp, 'fp': fp, 'fn': fn, 'precision': precision,
            'rappel': rappel, 'f1': f1,
            'ic_precision': wilson(vp, vp + fp),
            'ic_rappel': wilson(vp, vp + fn)}


def seuils():
    from django.conf import settings
    return {
        'liste_precision': float(getattr(
            settings, 'VEILLE_SEUIL_LISTE_PRECISION', 0.90)),
        'liste_rappel': float(getattr(
            settings, 'VEILLE_SEUIL_LISTE_RAPPEL', 0.90)),
        'dropshipper_precision': float(getattr(
            settings, 'VEILLE_SEUIL_DROPSHIPPER_PRECISION', 0.80)),
    }


def evaluer(paires_classe, paires_dropshipper, *, passage_second=None,
            passage_humain=None, seuils_=None):
    """Rapport de mesure depuis des paires ``(vrai, prédit)``."""
    from .models import VEILLE_CLASSES

    seuils_ = seuils_ or seuils()
    classes = [c for c, _l, _b in VEILLE_CLASSES]
    par_classe = {c: precision_rappel(paires_classe, c) for c in classes}
    drop = precision_rappel(paires_dropshipper, 'oui')
    liste = par_classe['vendeur']
    liste_atteint = (liste['precision'] is not None
                     and liste['rappel'] is not None
                     and liste['precision'] >= seuils_['liste_precision']
                     and liste['rappel'] >= seuils_['liste_rappel'])
    drop_atteint = (drop['precision'] is not None
                    and drop['precision'] >= seuils_['dropshipper_precision'])
    return {
        'n': len(paires_classe),
        'matrice': matrice_confusion(paires_classe, classes),
        'par_classe': par_classe,
        'dropshipper': drop,
        'passage_second_modele': passage_second,
        'passage_humain': passage_humain,
        'seuils': seuils_,
        'verdict': {
            'liste_vendeurs': 'atteint' if liste_atteint else 'non atteint',
            'dropshipper': 'atteint' if drop_atteint else 'non atteint',
            'dropshipper_interne': not drop_atteint,
        },
    }


def _derniere(verdicts, condition):
    for verdict in verdicts:  # triés du plus récent au plus ancien
        if condition(verdict):
            return verdict
    return None


def mesurer_decouverte(dec, *, modele_ambigu=None, maintenant=None):
    """Mesure P/R/F1 sur le jeu ``test`` GELÉ de la découverte. Refus (FR) si
    moins de 200 étiquettes de test, si une étiquette n'est pas humaine, ou si
    une étiquette de test a servi à l'étalonnage."""
    from .models import VeilleAnnonceur, VeilleVerdict

    tires = list(VeilleAnnonceur.objects.filter(
        company_id=dec.company_id, jeu_decouverte_id=dec.pk))
    ids = [a.pk for a in tires]
    etiquettes = VeilleVerdict.objects.filter(
        company_id=dec.company_id, annonceur_id__in=ids,
        est_etiquette_mesure=True)
    non_humaines = etiquettes.exclude(decide_par='humain').count()
    if non_humaines:
        raise MesureRefusee(
            f'{non_humaines} étiquette(s) de mesure non posée(s) par un '
            'humain : mesure refusée.')
    par_jeu = {a.pk: a.jeu for a in tires}
    croisees = sum(1 for e in etiquettes if e.jeu != par_jeu.get(
        e.annonceur_id))
    if croisees:
        raise MesureRefusee(
            f'{croisees} étiquette(s) posée(s) dans un autre jeu que celui de '
            "leur annonceur : le jeu de test a servi à l'étalonnage, mesure "
            'refusée.')
    verdicts_par_ann = {}
    for v in (VeilleVerdict.objects.filter(
            company_id=dec.company_id, annonceur_id__in=ids)
            .order_by('-created_at', '-id')):
        verdicts_par_ann.setdefault(v.annonceur_id, []).append(v)
    test = [a for a in tires if a.jeu == 'test']
    paires_classe, paires_drop = [], []
    second, humain = 0, 0
    for ann in test:
        verdicts = verdicts_par_ann.get(ann.pk, [])
        etiquette = _derniere(verdicts, lambda v: v.est_etiquette_mesure)
        if etiquette is None:
            continue
        machine = _derniere(verdicts, lambda v: not v.est_etiquette_mesure
                            and v.decide_par in ('regle', 'ia'))
        predit = machine.classe if machine else 'incertain'
        paires_classe.append((etiquette.classe, predit))
        paires_drop.append((etiquette.dropshipper,
                            machine.dropshipper if machine else 'incertain'))
        if machine and modele_ambigu and machine.modele == modele_ambigu:
            second += 1
        if predit == 'incertain':
            humain += 1
    if len(paires_classe) < MIN_ETIQUETTES_TEST:
        raise MesureRefusee(
            f'{len(paires_classe)} étiquette(s) de test : il en faut au '
            f'moins {MIN_ETIQUETTES_TEST} (seuils fixés avant la mesure).')
    n = len(paires_classe)
    rapport = evaluer(
        paires_classe, paires_drop,
        passage_second=(round(second / n, 4) if modele_ambigu else None),
        passage_humain=round(humain / n, 4))
    rapport['decouverte_id'] = dec.pk
    rapport['etiquettes_etalonnage'] = sum(
        1 for e in etiquettes if e.jeu == 'etalonnage')
    rapport['rappel_decouverte'] = calculer(
        dec, maintenant=maintenant)['rappel_concurrents_nommes']
    return rapport
