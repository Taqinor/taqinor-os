"""CIQ202 — Grille OFFICIELLE ONEE sourcée : UN module PUR de fondation.

Lisible par ``ventes`` (``quote_engine/constants_82_21.py``, ``tarif_ci.py``)
ET par ``parametres/tariff.py`` (qui ne peut pas lire ventes). Aucun import
d'app, aucun accès base : de la DONNÉE de référence, chaque valeur portant
{source_url, page_audience, releve_le, inchange_depuis} (contrat partagé
``apps/ventes/contract_samples/tarifs_ci.json`` → ``grille_officielle``).

Règles (zéro chiffre inventé, D-CIQ-4) :

* les prix sont stockés TELS QUE PUBLIÉS (« TTC publié ») ; la page ONEE porte
  un libellé de TVA PÉRIMÉ (18 %) alors que le taux légal de l'électricité est
  20 % depuis le 01/01/2026 (loi de finances 2024). ``tva_libelle_page`` est
  conservé pour la mention, JAMAIS utilisé pour dériver. Aucun TTC n'est
  re-multiplié ici : le HT se DÉRIVE ailleurs (TTC ÷ 1,20, ``tarif_ci``) et
  porte « estimation » jusqu'à la lecture d'une facture 2026 réelle ;
* EXCLUS : la grille « Grands Comptes » (494,09 DH/kVA ; 1,3645 / 0,9736 /
  0,7131) n'est PAS une grille MT (branche THT/HT ; ANRE 02/26 « tarif général
  THT-HT ») ; la pondération TGM de l'ANRE (10/21/17) n'est JAMAIS un profil
  ni un tarif moyen ; le TURD (tarif d'accès) n'est jamais un tarif de vente ;
* aucune durée de poste inventée : les plages sont celles PUBLIÉES (schéma
  one.org.ma/images/horr.jpg, page bi-horaire ; décision ANRE 04/26 art. 7),
  en heure GMT. Le Maroc est à GMT toute l'année depuis le 20/09/2026 (décret
  2.26.530) : aucun décalage ici (libellés civils via ``decalage_maroc_h``).
"""
from __future__ import annotations

RELEVE_LE = '2026-10-03'

_URL_MT = ("https://www.one.org.ma/ (Professionnels — « Tarif vert », "
           "id1=2&id2=35 ; page « Tarif Général (MT) » id1=14&id2=114)")
_AUDIENCE_MT = 'Professionnels — Tarif Général (MT)'
_URL_BT_PATENTE = "capture Wayback one.org.ma 20250216142859"
_URL_BT_FM = ("captures Wayback one.org.ma 20250216142859 et "
              "20250216144818")


def _ligne(cle, valeur, unite, *, source_url, page_audience,
           inchange_depuis=None, regle_tranches='non_publiee',
           tva_libelle_page=18):
    return {
        'cle': cle,
        'valeur': valeur,
        'unite': unite,
        'base': 'TTC publié',
        'tva_libelle_page': tva_libelle_page,
        'source_url': source_url,
        'page_audience': page_audience,
        'releve_le': RELEVE_LE,
        'inchange_depuis': inchange_depuis,
        'regle_tranches': regle_tranches,
    }


# ── MT « Tarif Général » (inchangé sur les captures Wayback des 30/11/2023,
#    09/10/2024 et 26/06/2025 sous des libellés 14 %, 16 %, 18 %) ───────────
_MT = dict(source_url=_URL_MT, page_audience=_AUDIENCE_MT,
           inchange_depuis='2023-11-30')
MT_GENERAL = {
    'pointe': _ligne('mt_pointe', 1.4157, 'MAD/kWh', **_MT),
    'pleines': _ligne('mt_pleines', 1.0101, 'MAD/kWh', **_MT),
    'creuses': _ligne('mt_creuses', 0.7398, 'MAD/kWh', **_MT),
    'prime_fixe_kva_an': _ligne('mt_prime_fixe_kva_an', 512.62,
                                'MAD/kVA/an', **_MT),
}

# ── BT professionnel (libellé de page « TVA 18 % » ; règle de tranche NON
#    publiée par la page → ``regle_tranches: non_publiee``) ───────────────
_PAT = dict(source_url=_URL_BT_PATENTE,
            page_audience='Professionnels — BT patenté')
_FM = dict(source_url=_URL_BT_FM,
           page_audience='Professionnels — BT force motrice')
BT_PATENTE = [
    dict(_ligne('bt_patente_tranche_1', 1.5146, 'MAD/kWh', **_PAT),
         seuil_min_kwh=0, seuil_max_kwh=150),
    dict(_ligne('bt_patente_tranche_2', 1.7090, 'MAD/kWh', **_PAT),
         seuil_min_kwh=150, seuil_max_kwh=None),
]
BT_FORCE_MOTRICE = [
    dict(_ligne('bt_force_motrice_tranche_1', 1.3639, 'MAD/kWh', **_FM),
         seuil_min_kwh=0, seuil_max_kwh=100),
    dict(_ligne('bt_force_motrice_tranche_2', 1.4663, 'MAD/kWh', **_FM),
         seuil_min_kwh=100, seuil_max_kwh=500),
    dict(_ligne('bt_force_motrice_tranche_3', 1.6758, 'MAD/kWh', **_FM),
         seuil_min_kwh=500, seuil_max_kwh=None),
]
# Bi-horaire : OPTIONNEL, réservé aux ménages et à la force motrice
# > 500 kWh/mois — JAMAIS aux patentés.
BT_BI_HORAIRE = {
    'hp': _ligne('bt_bi_horaire_hp', 2.4250, 'MAD/kWh', **_FM),
    'hn': _ligne('bt_bi_horaire_hn', 1.3472, 'MAD/kWh', **_FM),
}
BI_HORAIRE_SEUIL_FM_KWH_MOIS = 500

CONTRATS = ('bt_domestique', 'bt_patente', 'bt_force_motrice', 'mt_general')

# ── Postes horaires MT, heure GMT, intervalles [de_h, a_h) ────────────────
POSTES_SOURCE = ("page officielle ONEE MT (schéma one.org.ma/images/horr.jpg, "
                 "page bi-horaire) ; décision ANRE 04/26 art. 7")
POSTES_MT = [
    {'saison': 'hiver', 'du': '10-01', 'au': '03-31', 'postes': [
        {'poste': 'pointe', 'de_h': 17, 'a_h': 22},
        {'poste': 'pleines', 'de_h': 7, 'a_h': 17},
        {'poste': 'creuses', 'de_h': 22, 'a_h': 7},
    ]},
    {'saison': 'ete', 'du': '04-01', 'au': '09-30', 'postes': [
        {'poste': 'pointe', 'de_h': 18, 'a_h': 23},
        {'poste': 'pleines', 'de_h': 7, 'a_h': 18},
        {'poste': 'creuses', 'de_h': 23, 'a_h': 7},
    ]},
]


def saison(mois):
    """'hiver' (01/10-31/03) ou 'ete' (01/04-30/09) pour un mois 1..12."""
    m = int(mois)
    if not 1 <= m <= 12:
        raise ValueError(f'mois invalide : {mois!r}')
    return 'ete' if 4 <= m <= 9 else 'hiver'


def _dans(h, de_h, a_h):
    if de_h <= a_h:
        return de_h <= h < a_h
    return h >= de_h or h < a_h  # enjambe minuit


def poste_horaire(mois, heure_gmt):
    """Poste MT ('pointe' | 'pleines' | 'creuses') d'une heure GMT d'un mois."""
    h = int(heure_gmt)
    if not 0 <= h <= 23:
        raise ValueError(f'heure invalide : {heure_gmt!r}')
    s = saison(mois)
    for bloc in POSTES_MT:
        if bloc['saison'] != s:
            continue
        for p in bloc['postes']:
            if _dans(h, p['de_h'], p['a_h']):
                return p['poste']
    raise ValueError(f'heure non couverte : {heure_gmt!r}')  # pragma: no cover


def grille_bt(contrat, option_bi_horaire=False):
    """Lignes publiées d'un contrat BT pro (copies, jamais les originaux).

    ``option_bi_horaire`` n'est ouvert qu'à la force motrice (et aux ménages,
    hors de ce module pro) : demandé pour un patenté ⇒ ``ValueError`` nommant
    ``option_bi_horaire``. Contrat inconnu / domestique ⇒ ``ValueError``.
    """
    if contrat == 'bt_patente':
        if option_bi_horaire:
            raise ValueError(
                "option_bi_horaire : réservé aux ménages et à la force "
                "motrice > 500 kWh/mois, jamais à un patenté")
        return [dict(x) for x in BT_PATENTE]
    if contrat == 'bt_force_motrice':
        if option_bi_horaire:
            return [dict(BT_BI_HORAIRE['hp'], poste='hp'),
                    dict(BT_BI_HORAIRE['hn'], poste='hn')]
        return [dict(x) for x in BT_FORCE_MOTRICE]
    raise ValueError(f'contrat BT pro inconnu : {contrat!r}')


def grille_mt():
    """Lignes publiées du MT « Tarif Général » (copies)."""
    return {k: dict(v) for k, v in MT_GENERAL.items()}
