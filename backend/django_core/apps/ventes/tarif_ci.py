"""CIQ203 — le tarif d'électricité du CLIENT C&I, résolu (module PUR).

Ordre de résolution (contrat partagé ``contract_samples/tarifs_ci.json``,
conventions de l'orchestrateur « facture du client d'abord ») :

1. les prix de la FACTURE déclarés et datés (``etude_params.tarif_declare``) :
   MT = 3 postes + prime + puissance souscrite ; BT = tranches lues ;
2. sinon la grille OFFICIELLE (``apps/parametres/tarifs_officiels.py``) du
   contrat déclaré, origine ``grille_officielle``, ÉTIQUETÉE « Grille ONEE,
   repli » ;
3. sinon ``omis`` + motif : JAMAIS un prix plat (ni 1,75, ni 1,20, ni 0,95, ni
   un taux d'autoconsommation par défaut).

Le kWh solaire évité se valorise au prix du POSTE de l'heure (MT), jamais à une
moyenne pondérée incluant la pointe ; en BT, au prix de la tranche MARGINALE du
mois, lecture PROGRESSIVE (la plus prudente). HT/TTC : un prix déclaré garde sa
base ; un prix publié TTC donne HT = TTC ÷ (1 + TVA énergie du millésime,
``quote_engine/bareme.TVA_PAR_MILLESIME``) marqué ``derive_ht_estimation``.

Aucun accès base, aucun import de modèle. Ne change aucun statut (règle #4).
"""
from __future__ import annotations

from apps.parametres import tarifs_officiels as officiels
from apps.ventes.quote_engine.bareme import TVA_PAR_MILLESIME

CONTRATS = officiels.CONTRATS
ORIGINE_FACTURE = 'declare_facture'
ORIGINE_GRILLE = 'grille_officielle'
ORIGINE_OMIS = 'omis'

MENTION_GRILLE = (
    "Grille ONEE, repli : prix TTC tels que publiés sur one.org.ma (la page "
    "indique TVA 18 %, taux légal 2026 : 20 %) ; HT dérivé = TTC ÷ 1,20, "
    "estimation jusqu'à lecture d'une facture du client.")
MENTION_OMIS = (
    "Tarif non déclaré et contrat d'électricité inconnu : économies non "
    "chiffrées (aucun prix plat supposé).")
MENTION_DOMESTIQUE = (
    "Contrat domestique : aucune grille professionnelle de repli — économies "
    "non chiffrées sans les prix de la facture (aucun prix plat supposé).")
ETIQUETTE_TRANCHE = "règle de tranche à confirmer sur facture"

_LIBELLES_CONTRAT = {
    'bt_patente': 'BT patenté',
    'bt_force_motrice': 'BT force motrice',
    'mt_general': 'Tarif Général (MT)',
}
_POSTES_MT = ('pointe', 'pleines', 'creuses')


# ── TVA du millésime ────────────────────────────────────────────────────────
def tva_energie(millesime):
    """(taux, millésime retenu) de la TVA énergie.

    Le taux légal reste en vigueur tant qu'aucun millésime plus récent n'est
    saisi : un millésime absent prend le plus récent ANTÉRIEUR connu (jamais
    un taux futur deviné). Aucun millésime connu ⇒ ``(None, None)``.
    """
    try:
        m = int(millesime)
    except (TypeError, ValueError):
        m = max(TVA_PAR_MILLESIME)
    connus = sorted(a for a in TVA_PAR_MILLESIME if a <= m)
    if not connus:
        return None, None
    retenu = connus[-1]
    return TVA_PAR_MILLESIME[retenu]['energie'], retenu


def _r4(x):
    return round(float(x), 4)


def _num(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _date_fr(iso):
    if not iso or not isinstance(iso, str) or len(iso) < 10:
        return iso or ''
    return f'{iso[8:10]}/{iso[5:7]}/{iso[0:4]}'


def _pourcent(taux):
    pct = taux * 100
    return int(pct) if float(pct).is_integer() else round(pct, 2)


def _virgule(x):
    return f'{x:.2f}'.replace('.', ',')


# ── Résolution du tarif ─────────────────────────────────────────────────────
def _omis(mention=MENTION_OMIS, contrat=None):
    return {
        'origine': ORIGINE_OMIS,
        'contrat': contrat,
        'tarifs_par_poste': [],
        'prime_fixe_annuelle_mad': None,
        'tva_energie_pct': None,
        'tva_millesime': None,
        'mention': mention,
    }


def _entree_declaree(poste, valeur, base, taux, source, releve_le):
    if base == 'ht':
        ht, ttc, derive = _r4(valeur), _r4(valeur * (1 + taux)), False
    else:
        ttc, ht, derive = _r4(valeur), _r4(valeur / (1 + taux)), True
    return {'poste': poste, 'tarif_kwh_ht': ht, 'tarif_kwh_ttc': ttc,
            'base_publiee': base, 'derive_ht_estimation': derive,
            'source': source, 'releve_le': releve_le}


def _entree_grille(poste, ligne, taux, libelle_plage):
    ttc = ligne['valeur']
    return {
        'poste': poste,
        'tarif_kwh_ht': _r4(ttc / (1 + taux)),
        'tarif_kwh_ttc': ttc,
        'base_publiee': 'ttc',
        'derive_ht_estimation': True,
        'source': (f"grille ONEE {libelle_plage} — {ligne['source_url']} "
                   f"(libellé de page « TVA {ligne['tva_libelle_page']} % »)"),
        'releve_le': ligne['releve_le'],
    }


def _plage(ligne, contrat):
    lo, hi = ligne.get('seuil_min_kwh'), ligne.get('seuil_max_kwh')
    lib = _LIBELLES_CONTRAT[contrat]
    if hi is None:
        return f'{lib} > {lo} kWh'
    if not lo:
        return f'{lib} 0-{hi} kWh'
    return f'{lib} {lo + 1}-{hi} kWh'


def _prix_mt_declares(mt):
    if not isinstance(mt, dict):
        return None
    prix = {p: _num(mt.get(f'tarif_{p}')) for p in _POSTES_MT}
    if all(v is not None for v in prix.values()):
        return prix
    return None


def _tranches_bt_declarees(bt):
    if not isinstance(bt, dict):
        return []
    out = []
    for t in bt.get('tranches') or []:
        if isinstance(t, dict) and _num(t.get('tarif_kwh')) is not None:
            out.append(t)
    return out


def _prime(mt, prime_kva_an):
    if not isinstance(mt, dict):
        return None
    kva = _num(mt.get('puissance_souscrite_kva'))
    if prime_kva_an is None or kva is None:
        return None
    return round(prime_kva_an * kva, 2)


def tarif_applicable(tarif_declare, *, tension=None, millesime=2026):
    """La forme ``tarif`` du contrat ``tarifs_ci.json`` pour ce client.

    ``tension`` ('bt' | 'mt' | None) ne sert qu'à reconnaître un contrat MT non
    nommé (la MT n'a qu'un « Tarif Général ») ; un BT au contrat inconnu reste
    ``omis`` (patenté ou force motrice : on ne choisit pas pour le client).
    """
    td = tarif_declare if isinstance(tarif_declare, dict) else {}
    contrat = td.get('contrat')
    if contrat not in CONTRATS:
        contrat = 'mt_general' if (tension or '').lower() == 'mt' else None
    if contrat is None:
        return _omis()
    taux, annee = tva_energie(millesime)
    if taux is None:
        return _omis()
    base = td.get('base_tarifs') if td.get('base_tarifs') in ('ht', 'ttc') \
        else 'ttc'
    date_facture = td.get('date_facture')
    releve_le = td.get('saisi_le') or date_facture
    oral = td.get('provenance') == 'oral'
    if oral:
        source = 'prix déclarés oralement par le client (non relevés sur facture)'
    else:
        source = f'facture du client du {_date_fr(date_facture)}' \
            if date_facture else 'facture du client'
    pct = _pourcent(taux)

    def _mention_declaree():
        quoi = ('Tarifs déclarés oralement par le client (non relevés sur '
                'facture)' if oral else
                f"Tarifs relevés sur la facture d'électricité du client"
                f"{' du ' + _date_fr(date_facture) if date_facture else ''}")
        if base == 'ht':
            calc = (f"HT tels qu'imprimés ; TTC = HT × {_virgule(1 + taux)}, "
                    f"TVA électricité {annee}")
        else:
            calc = (f"TTC tels qu'imprimés ; HT = TTC ÷ {_virgule(1 + taux)}, "
                    f"TVA électricité {annee}")
        return f'{quoi} ({calc}).'

    sortie = {'contrat': contrat, 'tva_energie_pct': pct,
              'tva_millesime': annee}

    if contrat == 'mt_general':
        mt = td.get('mt')
        prix = _prix_mt_declares(mt)
        if prix is not None:
            prime_kva = _num(mt.get('prime_fixe_kva_an'))
            if prime_kva is not None and base == 'ttc':
                prime_kva = prime_kva / (1 + taux)
            sortie.update({
                'origine': ORIGINE_FACTURE,
                'tarifs_par_poste': [
                    _entree_declaree(p, prix[p], base, taux, source, releve_le)
                    for p in _POSTES_MT],
                'prime_fixe_annuelle_mad': _prime(mt, prime_kva),
                'mention': _mention_declaree(),
            })
            return _ordonne(sortie)
        grille = officiels.MT_GENERAL
        sortie.update({
            'origine': ORIGINE_GRILLE,
            'tarifs_par_poste': [
                _entree_grille(p, grille[p], taux,
                               f'{_LIBELLES_CONTRAT[contrat]} {p}')
                for p in _POSTES_MT],
            # Prime publiée TTC → HT dérivé, comme les prix (estimation).
            'prime_fixe_annuelle_mad': _prime(
                mt, grille['prime_fixe_kva_an']['valeur'] / (1 + taux)),
            'mention': MENTION_GRILLE,
        })
        return _ordonne(sortie)

    if contrat == 'bt_domestique':
        tranches = _tranches_bt_declarees(td.get('bt'))
        if not tranches:
            return _omis(MENTION_DOMESTIQUE, contrat)
    else:
        tranches = _tranches_bt_declarees(td.get('bt'))

    if tranches:
        sortie.update({
            'origine': ORIGINE_FACTURE,
            'tarifs_par_poste': [
                _entree_declaree(f'tranche_{i}', _num(t['tarif_kwh']), base,
                                 taux, source, releve_le)
                for i, t in enumerate(tranches, start=1)],
            'prime_fixe_annuelle_mad': None,
            'mention': _mention_declaree(),
        })
        return _ordonne(sortie)

    bi = bool(td.get('option_bi_horaire'))
    lignes = officiels.grille_bt(contrat, option_bi_horaire=bi)
    if bi:
        postes = [_entree_grille('pointe', lignes[0], taux,
                                 f'{_LIBELLES_CONTRAT[contrat]} bi-horaire HP'),
                  _entree_grille('normales', lignes[1], taux,
                                 f'{_LIBELLES_CONTRAT[contrat]} bi-horaire HN')]
    else:
        postes = [_entree_grille(f'tranche_{i}', ligne, taux,
                                 _plage(ligne, contrat))
                  for i, ligne in enumerate(lignes, start=1)]
    sortie.update({
        'origine': ORIGINE_GRILLE,
        'tarifs_par_poste': postes,
        'prime_fixe_annuelle_mad': None,
        'mention': MENTION_GRILLE,
    })
    return _ordonne(sortie)


def _ordonne(sortie):
    cles = ('origine', 'contrat', 'tarifs_par_poste', 'prime_fixe_annuelle_mad',
            'tva_energie_pct', 'tva_millesime', 'mention')
    return {k: sortie.get(k) for k in cles}


# ── Prix d'une heure ────────────────────────────────────────────────────────
def tarif_du_poste(tarif, mois, heure_gmt, *, kwh_mois=None,
                   tarif_declare=None):
    """Le prix (entrée de ``tarifs_par_poste``, copie) d'une heure donnée.

    * MT : le prix du POSTE de cette heure (``poste_horaire``), jamais une
      moyenne pondérée ;
    * BT à tranches : la tranche MARGINALE de ``kwh_mois`` (lecture
      PROGRESSIVE) ; une grille dont la règle n'est pas publiée porte
      ``etiquette`` = « règle de tranche à confirmer sur facture » ;
    * bi-horaire : les plages HP/HN ne sont pas saisies ⇒ ``None`` (omis,
      jamais deviné) ;
    * ``omis`` ou données insuffisantes ⇒ ``None``.
    """
    if not isinstance(tarif, dict) or tarif.get('origine') == ORIGINE_OMIS:
        return None
    postes = tarif.get('tarifs_par_poste') or []
    if not postes:
        return None
    if tarif.get('contrat') == 'mt_general':
        nom = officiels.poste_horaire(mois, heure_gmt)
        for p in postes:
            if p['poste'] == nom:
                return dict(p)
        return None
    if any(p['poste'] in ('pointe', 'normales') for p in postes):
        return None  # bi-horaire : plages HP/HN non saisies
    kwh = _num(kwh_mois)
    if kwh is None:
        return None
    seuils = _seuils_bt(tarif, tarif_declare)
    if seuils is None or len(seuils) != len(postes):
        return None
    # Tranches ascendantes : la MARGINALE est la première dont le plafond
    # couvre la conso du mois (lecture progressive, jamais un bloc).
    choisi = None
    for (_lo, hi), p in zip(seuils, postes):
        if hi is None or kwh <= hi:
            choisi = p
            break
    if choisi is None:
        return None
    out = dict(choisi)
    if tarif.get('origine') == ORIGINE_GRILLE:
        out['etiquette'] = ETIQUETTE_TRANCHE
    return out


def _seuils_bt(tarif, tarif_declare):
    contrat = tarif.get('contrat')
    if tarif.get('origine') == ORIGINE_GRILLE:
        try:
            lignes = officiels.grille_bt(contrat)
        except ValueError:
            return None
        return [(x['seuil_min_kwh'], x['seuil_max_kwh']) for x in lignes]
    td = tarif_declare if isinstance(tarif_declare, dict) else {}
    tranches = _tranches_bt_declarees(td.get('bt'))
    if not tranches:
        return None
    return [(_num(t.get('seuil_min_kwh')), _num(t.get('seuil_max_kwh')))
            for t in tranches]


# ── Validation de l'entrée ``tarif_declare`` (à l'écriture) ────────────────
def reproches_tarif_declare(td):
    """Reproches FR nommant ``etude_params.tarif_declare.<champ>`` (``[]`` = ok).

    Prix négatif, ``option_bi_horaire`` hors force motrice / ménages, MT dont
    un poste est saisi sans les deux autres, vocabulaire inconnu.
    """
    if td is None:
        return []
    if not isinstance(td, dict):
        return ['« etude_params.tarif_declare » doit être un objet.']
    pre = 'etude_params.tarif_declare.'
    out = []
    contrat = td.get('contrat')
    if contrat is not None and contrat not in CONTRATS:
        out.append(f'« {pre}contrat » : valeur inconnue « {contrat} » '
                   f'(attendu : {", ".join(CONTRATS)}).')
    if td.get('base_tarifs') not in (None, 'ht', 'ttc'):
        out.append(f'« {pre}base_tarifs » : ht ou ttc.')
    if td.get('provenance') not in (None, 'facture', 'oral'):
        out.append(f'« {pre}provenance » : facture ou oral.')
    if td.get('option_bi_horaire') and contrat not in (
            'bt_force_motrice', 'bt_domestique'):
        out.append(f'« {pre}option_bi_horaire » : réservé à la force motrice '
                   f'(et aux ménages), jamais à « {contrat} ».')
    mt = td.get('mt')
    if mt is not None and not isinstance(mt, dict):
        out.append(f'« {pre}mt » doit être un objet.')
    elif isinstance(mt, dict):
        for champ in ('tarif_pointe', 'tarif_pleines', 'tarif_creuses',
                      'prime_fixe_kva_an', 'puissance_souscrite_kva'):
            v = mt.get(champ)
            if v is None:
                continue
            n = _num(v)
            if n is None:
                out.append(f'« {pre}mt.{champ} » : nombre attendu.')
            elif n < 0:
                out.append(f'« {pre}mt.{champ} » : valeur négative refusée.')
        saisis = [p for p in _POSTES_MT if mt.get(f'tarif_{p}') is not None]
        if saisis and len(saisis) != len(_POSTES_MT):
            for p in _POSTES_MT:
                if p not in saisis:
                    out.append(f'« {pre}mt.tarif_{p} » : un tarif MT exige '
                               f'ses trois postes (pointe, pleines, creuses).')
    bt = td.get('bt')
    if bt is not None and not isinstance(bt, dict):
        out.append(f'« {pre}bt » doit être un objet.')
    elif isinstance(bt, dict):
        for i, t in enumerate(bt.get('tranches') or [], start=1):
            if not isinstance(t, dict):
                out.append(f'« {pre}bt.tranches[{i}] » doit être un objet.')
                continue
            for champ in ('tarif_kwh', 'seuil_min_kwh', 'seuil_max_kwh'):
                v = t.get(champ)
                if v is None:
                    continue
                n = _num(v)
                if n is None or n < 0:
                    out.append(f'« {pre}bt.tranches[{i}].{champ} » : nombre '
                               f'positif attendu.')
    return out
