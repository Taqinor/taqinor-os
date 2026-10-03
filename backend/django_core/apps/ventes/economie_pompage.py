"""AGR201-AGR205 — l'économie DÉCLARÉE d'un devis de pompage agricole.

LE CONSTAT. Un devis de pompage n'avait qu'une économie résidentielle
détournée : la dépense saisie « par mois » était multipliée par 12 sur des
mois inconnus, et aucun calcul serveur ne partait des chiffres que le client
DÉCLARE (bouteilles ou litres, prix PAYÉ, mois d'irrigation, facture réseau,
entretien payé). Ce module est le moteur PUR de ce calcul ; il sert le bloc
``economie_pompage`` du contrat partagé
``contract_samples/economie_pompage.json`` (AGR3).

LA RÈGLE : SAISI, SOURCÉ, OU OMIS (patron d'``economie.py``)
-----------------------------------------------------------
* chaque entrée DÉCLARÉE est publiée dans ``entrees_declarees`` avec sa
  provenance ``{origine, detail, date}`` (forme UNIQUE du contrat AGR2) ;
* toute saisie manquante ⇒ ``statut = omis`` et un motif qui NOMME la saisie ;
* aucun prix du carburant n'est pré-enregistré (Q17, D-AGR-5) ; aucune grille
  tarifaire réseau n'est lue ; l'ancienne clé ``fuel_spend_current`` n'est
  jamais lue (D-AGR-13 : aucune branche « ancien devis ») ;
* jamais × 12 : la dépense est celle de CHAQUE mois coché.

Module PUR : aucune requête, aucun réseau. L'appelant (AGR206) lit le devis,
les lignes, les réglages et la sortie du moteur de pompage, puis appelle
:func:`economie_pompage`.
"""
from __future__ import annotations

import calendar

from .economie import EconomieInvalide, _nombre, flux_de_tresorerie

__all__ = [
    'ANNEE_REMPLACEMENT_POMPE', 'CAS_CARBURANT', 'CAS_NOUVEAU_FORAGE',
    'CAS_RESEAU', 'ENERGIES', 'HORIZON_ANS', 'depense_actuelle',
    'economie_pompage', 'investissement_ttc', 'mention_declaration',
]

#: Vocabulaire de ``crm.Lead.PompeAlimActuelle`` (contrat AGR3).
ENERGIES = ('aucune', 'butane', 'diesel', 'electrique')
UNITES = ('bouteille_12kg', 'litre')
PERIODES = ('jour_irrigation', 'semaine', 'mois')
PERIODICITES = ('mensuelle', 'bimestrielle')

CAS_CARBURANT = 'carburant'
CAS_RESEAU = 'reseau'
CAS_NOUVEAU_FORAGE = 'nouveau_forage'

#: Jours de chaque mois — calendrier grégorien d'une année NON bissextile
#: (une dépense annuelle récurrente ne porte pas le 29 février une année sur
#: quatre). Source : ``calendar.monthrange`` de la bibliothèque standard.
JOURS_DU_MOIS = tuple(calendar.monthrange(2026, mois)[1]
                      for mois in range(1, 13))

_LIBELLE_UNITE = {'bouteille_12kg': 'bouteille_12kg', 'litre': 'litre'}
_LIBELLE_PERIODE = {
    'jour_irrigation': "par jour d'irrigation",
    'semaine': 'par semaine',
    'mois': 'par mois',
}
_PAR_UNITE = {'bouteille_12kg': 'MAD par bouteille', 'litre': 'MAD par litre'}


# ── Lecture des saisies ─────────────────────────────────────────────────────

def _bloc(saisies, cle):
    valeur = (saisies or {}).get(cle)
    return valeur if isinstance(valeur, dict) else None


def _positif(champ, brute, *, strict=False):
    """Un nombre >= 0 (> 0 si ``strict``), ou un refus qui NOMME ``champ``."""
    nombre = _nombre(champ, brute)
    if nombre < 0 or (strict and nombre == 0):
        borne = 'strictement positif' if strict else 'positif ou nul'
        raise EconomieInvalide(
            f"{champ} : {nombre:g} refusé — un nombre {borne} est attendu.",
            champ=champ)
    return nombre


def _provenance_saisie(date):
    return {'origine': 'saisie', 'detail': None, 'date': date}


def _provenance(bloc, date=None):
    prov = bloc.get('provenance') if isinstance(bloc, dict) else None
    if isinstance(prov, dict):
        return {'origine': prov.get('origine'), 'detail': prov.get('detail'),
                'date': prov.get('date')}
    return _provenance_saisie(date)


def _entree(cle, valeur, unite, provenance, saisi_le):
    return {'cle': cle, 'valeur': valeur, 'unite': unite,
            'provenance': provenance, 'saisi_le': saisi_le}


def mention_declaration(entree):
    """La mention imprimée d'une entrée : « déclaré par le client le JJ/MM ».

    Des mois pré-cochés par le calendrier de culture sont publiés COMME TELS
    (« pré-cochés selon le calendrier de culture »), jamais comme une
    déclaration du client.
    """
    prov = entree.get('provenance') or {}
    if prov.get('origine') == 'calculee' and \
            prov.get('detail') == 'calendrier_culture':
        return 'pré-cochés selon le calendrier de culture'
    date = entree.get('saisi_le') or prov.get('date')
    if isinstance(date, str) and len(date) >= 10:
        return 'déclaré par le client le %s/%s' % (date[8:10], date[5:7])
    return 'déclaré par le client'


def _mois_coches(saisies):
    """``(mois triés, bloc)`` ou ``(None, bloc)`` si non déclarés."""
    bloc = _bloc(saisies, 'mois_irrigation')
    if not bloc or not bloc.get('mois'):
        return None, bloc
    mois = bloc['mois']
    if not isinstance(mois, (list, tuple)):
        raise EconomieInvalide(
            'mois_irrigation.mois : une liste de mois (1 à 12) est attendue.',
            champ='mois_irrigation.mois')
    propres = set()
    for brut in mois:
        if isinstance(brut, bool) or not isinstance(brut, int) \
                or not 1 <= brut <= 12:
            raise EconomieInvalide(
                f'mois_irrigation.mois : « {brut} » n\'est pas un mois '
                f'(1 à 12).', champ='mois_irrigation.mois')
        propres.add(brut)
    return sorted(propres), bloc


def jours_irrigation_par_semaine(saisies):
    """Les jours d'irrigation par semaine DÉCLARÉS, ou ``None``."""
    conso = _bloc(saisies, 'consommation') or {}
    brute = conso.get('jours_irrigation_par_semaine')
    if brute is None:
        return None
    jours = _positif('consommation.jours_irrigation_par_semaine', brute,
                     strict=True)
    if jours > 7:
        raise EconomieInvalide(
            'consommation.jours_irrigation_par_semaine : au plus 7 jours.',
            champ='consommation.jours_irrigation_par_semaine')
    return jours


def jours_irrigues_du_mois(mois, jours_par_semaine):
    """Jours irrigués d'un mois : jours par semaine × jours du mois ÷ 7."""
    return jours_par_semaine * JOURS_DU_MOIS[mois - 1] / 7.0


# ── AGR201 — la dépense ACTUELLE ────────────────────────────────────────────

def _quantite_du_mois(quantite, periode, mois, jours_par_semaine):
    """La quantité ramenée au mois — jamais × 12."""
    if periode == 'jour_irrigation':
        return quantite * jours_irrigues_du_mois(mois, jours_par_semaine)
    if periode == 'semaine':
        return quantite * JOURS_DU_MOIS[mois - 1] / 7.0
    return quantite


def depense_actuelle(saisies):
    """AGR201 — la dépense ACTUELLE déclarée, mois par mois.

    Rend ``{statut, cas, motifs, entrees_declarees, depense_actuelle,
    quantite_par_mois, depense_carburant_par_mois, omissions}`` :

    * ``cas`` : ``carburant`` | ``reseau`` | ``nouveau_forage`` | ``None`` ;
    * ``depense_actuelle`` : ``{par_mois[12], entretien_mad_an, annuelle_mad,
      formule}`` (forme du contrat) ou ``None`` si une saisie manque ;
    * ``quantite_par_mois`` : unités consommées chaque mois (carburant), ou le
      montant mensuel de la facture hors part fixe (réseau) — la base des
      grilles de sensibilité (AGR203) ;
    * ``motifs`` : une phrase par saisie manquante, qui la NOMME.
    """
    saisies = saisies or {}
    resultat = {
        'statut': 'omis', 'cas': None, 'motifs': [], 'entrees_declarees': [],
        'depense_actuelle': None, 'quantite_par_mois': None,
        'valeur_unitaire': None, 'unite': None, 'omissions': [],
    }
    motifs, omissions = resultat['motifs'], resultat['omissions']
    entrees = resultat['entrees_declarees']

    def manque(cle, motif):
        motifs.append(motif)
        omissions.append({'cle': f'saisies_economie_pompage.{cle}',
                          'motif': motif})

    energie_bloc = _bloc(saisies, 'energie_actuelle')
    energie = (energie_bloc or {}).get('valeur')
    if energie is None:
        manque('energie_actuelle', 'énergie actuelle non déclarée')
    elif energie not in ENERGIES:
        raise EconomieInvalide(
            f"energie_actuelle.valeur : « {energie} » inconnue — choisir "
            f"parmi {', '.join(ENERGIES)}.", champ='energie_actuelle.valeur')
    else:
        prov = _provenance(energie_bloc)
        entrees.append(_entree('energie_actuelle', energie, None, prov,
                               prov.get('date')))

    if energie == 'aucune':
        # QJR150 : un forage neuf n'a ni dépense ni économie — le seul repère
        # publiable est le coût du m³ solaire (AGR203).
        resultat['cas'] = CAS_NOUVEAU_FORAGE
        resultat['statut'] = 'calcule'
        return resultat

    if energie == 'electrique':
        resultat['cas'] = CAS_RESEAU
    elif energie in ('butane', 'diesel'):
        resultat['cas'] = CAS_CARBURANT

    mois, mois_bloc = _mois_coches(saisies)
    jours_semaine = jours_irrigation_par_semaine(saisies)
    conso = _bloc(saisies, 'consommation')
    prix_bloc = _bloc(saisies, 'depense_unitaire_payee')
    facture = _bloc(saisies, 'facture_reseau')

    quantite = unite = periode = prix = None
    montant_mensuel = None
    if resultat['cas'] == CAS_RESEAU:
        if not facture or facture.get('montant_mad') is None:
            manque('facture_reseau', 'facture réseau non déclarée')
        else:
            montant = _positif('facture_reseau.montant_mad',
                               facture['montant_mad'])
            periodicite = facture.get('periodicite')
            if periodicite not in PERIODICITES:
                raise EconomieInvalide(
                    'facture_reseau.periodicite : choisir parmi '
                    f"{', '.join(PERIODICITES)}.",
                    champ='facture_reseau.periodicite')
            if facture.get('part_fixe_mad_mois') is None:
                manque('facture_reseau.part_fixe_mad_mois',
                       'part fixe de la facture non déclarée (0 si aucune)')
            else:
                part_fixe = _positif('facture_reseau.part_fixe_mad_mois',
                                     facture['part_fixe_mad_mois'])
                # Règle Q24 : une facture bimestrielle couvre deux mois.
                mensuel = montant / 2.0 if periodicite == 'bimestrielle' \
                    else montant
                montant_mensuel = mensuel - part_fixe
                if montant_mensuel < 0:
                    raise EconomieInvalide(
                        'facture_reseau.part_fixe_mad_mois : la part fixe '
                        'dépasse la facture mensuelle déclarée.',
                        champ='facture_reseau.part_fixe_mad_mois')
                saisi_le = facture.get('saisi_le')
                entrees.append(_entree(
                    'facture_reseau', montant,
                    f'MAD par facture {periodicite}',
                    _provenance_saisie(saisi_le), saisi_le))
                entrees.append(_entree(
                    'part_fixe_mad_mois', part_fixe, 'MAD par mois',
                    _provenance_saisie(saisi_le), saisi_le))
                resultat['valeur_unitaire'] = montant
                resultat['unite'] = f'MAD par facture {periodicite}'
    elif resultat['cas'] == CAS_CARBURANT or energie is None:
        if not conso or conso.get('quantite') is None:
            manque('consommation', 'consommation non déclarée')
        else:
            quantite = _positif('consommation.quantite', conso['quantite'])
            unite, periode = conso.get('unite'), conso.get('periode')
            if unite not in UNITES:
                raise EconomieInvalide(
                    f"consommation.unite : choisir parmi {', '.join(UNITES)}.",
                    champ='consommation.unite')
            if periode not in PERIODES:
                raise EconomieInvalide(
                    'consommation.periode : choisir parmi '
                    f"{', '.join(PERIODES)}.", champ='consommation.periode')
            saisi_le = conso.get('saisi_le')
            entrees.append(_entree(
                'consommation', quantite,
                f'{_LIBELLE_UNITE[unite]} {_LIBELLE_PERIODE[periode]}',
                _provenance_saisie(saisi_le), saisi_le))
            if periode == 'jour_irrigation':
                if jours_semaine is None:
                    manque('consommation.jours_irrigation_par_semaine',
                           "jours d'irrigation par semaine non déclarés")
                else:
                    entrees.append(_entree(
                        'jours_irrigation_par_semaine', jours_semaine,
                        'jours', _provenance_saisie(saisi_le), saisi_le))
        if not prix_bloc or prix_bloc.get('valeur') is None:
            manque('depense_unitaire_payee', 'prix payé non déclaré')
        else:
            prix = _positif('depense_unitaire_payee.valeur',
                            prix_bloc['valeur'])
            saisi_le = prix_bloc.get('saisi_le')
            entrees.append(_entree(
                'depense_unitaire_payee', prix,
                _PAR_UNITE.get(unite, 'MAD par unité'),
                _provenance_saisie(saisi_le), saisi_le))
            resultat['valeur_unitaire'] = prix
            resultat['unite'] = _PAR_UNITE.get(unite)

    if mois is None:
        manque('mois_irrigation', "mois d'irrigation non déclarés")
    else:
        prov = _provenance(mois_bloc)
        entrees.append(_entree('mois_irrigation', list(mois), 'mois', prov,
                               prov.get('date')))

    entretien = None
    entretien_bloc = _bloc(saisies, 'entretien_paye_mad_an')
    if entretien_bloc and entretien_bloc.get('valeur') is not None:
        entretien = _positif('entretien_paye_mad_an.valeur',
                             entretien_bloc['valeur'])
        saisi_le = entretien_bloc.get('saisi_le')
        entrees.append(_entree('entretien_paye_mad_an', entretien,
                               'MAD par an', _provenance_saisie(saisi_le),
                               saisi_le))
    else:
        omissions.append({
            'cle': 'saisies_economie_pompage.entretien_paye_mad_an',
            'motif': "entretien payé non déclaré : aucun entretien évité "
                     "n'est compté"})

    if motifs:
        return resultat

    par_mois = [0.0] * 12
    quantites = [0.0] * 12
    for m in mois:
        if resultat['cas'] == CAS_RESEAU:
            quantites[m - 1] = montant_mensuel
            par_mois[m - 1] = montant_mensuel
        else:
            q = _quantite_du_mois(quantite, periode, m, jours_semaine)
            quantites[m - 1] = q
            par_mois[m - 1] = q * prix
    if resultat['cas'] == CAS_RESEAU:
        formule = ('par mois coché : facture déclarée ramenée au mois '
                   '(bimestrielle ÷ 2) − part fixe déclarée ; + entretien '
                   'payé déclaré')
    else:
        formule = {
            'jour_irrigation': "par mois coché : quantité × jours "
                               "d'irrigation par semaine × jours du mois ÷ 7 "
                               "× prix payé déclaré",
            'semaine': 'par mois coché : quantité par semaine × jours du '
                       'mois ÷ 7 × prix payé déclaré',
            'mois': 'par mois coché : quantité par mois × prix payé déclaré',
        }[periode]
        formule += ' ; + entretien payé déclaré'
    annuelle = sum(par_mois) + (entretien or 0.0)
    resultat['statut'] = 'calcule'
    resultat['quantite_par_mois'] = quantites
    resultat['depense_actuelle'] = {
        'par_mois': [round(v, 2) for v in par_mois],
        'entretien_mad_an': entretien,
        'annuelle_mad': round(annuelle, 2),
        'formule': formule,
    }
    # Valeurs NON arrondies, pour l'arithmétique aval (jamais publiées).
    resultat['_par_mois'] = par_mois
    resultat['_entretien'] = entretien or 0.0
    resultat['_mois'] = list(mois)
    return resultat


# ── AGR202 — lignes, couverture, charges, remplacements ─────────────────────

#: Horizon d'analyse — décision fondateur D-AGR-5 du 02/10/2026.
HORIZON_ANS = 10
SOURCE_HORIZON = 'décision fondateur D-AGR-5 du 02/10/2026'
#: Indexation du prix du carburant — décision fondateur D-AGR-5 : 0 % ÉCRIT.
INDEXATION_PCT = 0.0
SOURCE_INDEXATION = ('décision fondateur D-AGR-5 du 02/10/2026 — prix du '
                     'carburant constant : il peut monter ou baisser')
#: Dégradation : sans objet (une dépense évitée n'est pas une production).
DEGRADATION_PCT = 0.0
SOURCE_DEGRADATION = ("sans objet : l'économie est une dépense déclarée "
                      "évitée, pas une production valorisée")
#: Année de remplacement de la pompe — Banque mondiale 2018, « Solar Pumping:
#: The Basics » (pompe à remplacer après 7-10 ans) : la borne BASSE, au TTC
#: réel de la ligne pompe du devis (D-AGR-5).
ANNEE_REMPLACEMENT_POMPE = 7
SOURCE_POMPE = ('Banque mondiale 2018, « Solar Pumping: The Basics » (pompe '
                'à remplacer après 7-10 ans) — TTC réel de la ligne pompe du '
                'devis')
SOURCE_VARIATEUR = ('fin de garantie constructeur (Produit.garantie_mois) — '
                    'TTC réel de la ligne variateur du devis')
SOURCE_INVESTISSEMENT = ("total TTC client des lignes du devis (jamais le "
                         "prix d'achat)")
SOURCE_CHARGES = ('barème société — Paramètres › Tarification & ROI › '
                  'Pompage agricole')

#: Reconnaissance des lignes : ``categorie.type_equipement`` (STKCAT3) puis
#: le rôle pompage (contrat ``stock/contract_samples/produit_pompage.json``).
TYPES_POMPE = ('pompe',)
TYPES_VARIATEUR = ('variateur',)
ROLES_POMPE = ('pompe',)
ROLES_VARIATEUR = ('variateur_pompage',)


def _ligne_comptee(ligne):
    return (ligne.get('type_ligne') in (None, '', 'produit')
            and not ligne.get('optionnelle'))


def _montants_ligne(rang, ligne):
    """``(HT, TTC)`` d'une ligne : quantité × P.U. HT × (1 − remise %) ×
    (1 + TVA %). ``total_ttc_mad`` transmis par l'appelant prime (remise
    globale déjà répartie) — jamais un prix d'achat."""
    prefixe = f'lignes[{rang}]'
    if ligne.get('total_ttc_mad') is not None:
        ttc = _positif(f'{prefixe}.total_ttc_mad', ligne['total_ttc_mad'])
        ht = ligne.get('total_ht_mad')
        ht = None if ht is None else _positif(f'{prefixe}.total_ht_mad', ht)
        return ht, ttc
    quantite = _positif(f'{prefixe}.quantite', ligne.get('quantite'))
    pu = _positif(f'{prefixe}.prix_unitaire', ligne.get('prix_unitaire'))
    remise = _positif(f'{prefixe}.remise', ligne.get('remise') or 0)
    if ligne.get('taux_tva') is None:
        raise EconomieInvalide(
            f'{prefixe}.taux_tva : le taux de TVA de la ligne doit être '
            f'transmis (aucun taux de repli).', champ=f'{prefixe}.taux_tva')
    tva = _positif(f'{prefixe}.taux_tva', ligne['taux_tva'])
    ht = quantite * pu * (1.0 - remise / 100.0)
    return ht, ht * (1.0 + tva / 100.0)


def _lignes_lues(lignes):
    lues = []
    for rang, ligne in enumerate(lignes or []):
        if not isinstance(ligne, dict) or not _ligne_comptee(ligne):
            continue
        ht, ttc = _montants_ligne(rang, ligne)
        lues.append({'ligne': ligne, 'ht': ht, 'ttc': ttc})
    return lues


def _est(ligne, types, roles):
    return (ligne.get('type_equipement') in types
            or ligne.get('role_pompage') in roles)


def investissement_ttc(lignes):
    """Le total TTC client des lignes comptées (jamais le prix d'achat)."""
    return sum(lg['ttc'] for lg in _lignes_lues(lignes))


def _couverture(sortie_etude, mois):
    """``{verifiee, part_evitee_par_mois[12], motif}``.

    Part évitée d'un mois coché = min(1, couverture du mois ÷ 100) servie par
    le moteur de pompage (AGR2) ; mois non coché = 0. Sans couverture
    calculable (pompe sans courbe, QXG3) : part 1, ``verifiee`` false.
    """
    couverture = (sortie_etude or {}).get('couverture_pct_mois')
    if isinstance(couverture, (list, tuple)) and len(couverture) == 12 \
            and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                    for v in couverture):
        parts = [min(1.0, max(0.0, couverture[m - 1] / 100.0))
                 if m in mois else 0 for m in range(1, 13)]
        return {'verifiee': True, 'part_evitee_par_mois': parts,
                'motif': None}
    return {'verifiee': False,
            'part_evitee_par_mois': [1 if m in mois else 0
                                     for m in range(1, 13)],
            'motif': 'couverture non vérifiable : pompe sans courbe'}


def _charges(reglages):
    """``(bloc charges_solaires | None, total | None, motifs)``."""
    lignes = (reglages or {}).get('charges_pompage_solaire') or []
    if not lignes:
        return None, None, ['barème des charges solaires non saisi']
    publiees, motifs = [], []
    for rang, ligne in enumerate(lignes):
        libelle = str((ligne or {}).get('libelle') or '').strip()
        source = str((ligne or {}).get('source') or '').strip()
        montant = (ligne or {}).get('montant_mad_an')
        if montant is None or not source:
            motifs.append('ligne du barème des charges solaires sans montant '
                          'ou sans source : « %s »' % (libelle or rang))
            continue
        publiees.append({
            'libelle': libelle,
            'montant_mad_an': _positif(
                f'charges_pompage_solaire[{rang}].montant_mad_an', montant),
            'source': source})
    if motifs:
        return None, None, motifs
    total = sum(lg['montant_mad_an'] for lg in publiees)
    return {'total_mad_an': round(total, 2), 'lignes': publiees}, total, []


def mode_pompe(sortie_etude):
    """``neuve`` | ``existante`` | ``None`` — servi par le moteur (D-AGR-7)."""
    pompe = (sortie_etude or {}).get('pompe') or {}
    return pompe.get('mode')


def _remplacements(lignes, mode):
    """``(publiés, entrées du flux, omissions)`` — pompe année 7, variateur
    à ceil(garantie_mois / 12), au TTC RÉEL de leurs lignes."""
    lues = _lignes_lues(lignes)
    publies, flux, omissions = [], [], []

    def omettre(composant, motif):
        publies.append({'composant': composant, 'annee': None,
                        'montant_ttc_mad': None, 'source': None,
                        'motif': motif})
        omissions.append({'cle': f'remplacement_{composant}',
                          'motif': motif})

    def porter(composant, annee, montant, source, libelle):
        publies.append({'composant': composant, 'annee': annee,
                        'montant_ttc_mad': round(montant, 2),
                        'source': source, 'motif': None})
        flux.append({'equipement': libelle, 'annee': annee,
                     'mode': 'remplacer', 'montant_mad': round(montant, 2),
                     'source': source})

    pompes = [lg for lg in lues
              if _est(lg['ligne'], TYPES_POMPE, ROLES_POMPE)]
    if mode == 'existante':
        omettre('pompe', 'pompe conservée dans les deux scénarios : aucune '
                         'provision de remplacement')
    elif not pompes:
        omettre('pompe', 'aucune ligne pompe au devis : remplacement omis')
    elif not sum(lg['ttc'] for lg in pompes):
        omettre('pompe', 'prix de la pompe à renseigner : remplacement omis')
    else:
        porter('pompe', ANNEE_REMPLACEMENT_POMPE,
               sum(lg['ttc'] for lg in pompes), SOURCE_POMPE, 'pompe')

    variateurs = [lg for lg in lues
                  if _est(lg['ligne'], TYPES_VARIATEUR, ROLES_VARIATEUR)]
    if not variateurs:
        omettre('variateur', 'aucune ligne variateur au devis : '
                             'remplacement omis')
    else:
        garanties = [lg['ligne'].get('garantie_mois') for lg in variateurs]
        if any(g in (None, '', 0) for g in garanties):
            omettre('variateur', 'garantie constructeur du variateur non '
                                 'renseignée sur la fiche produit : '
                                 'remplacement omis')
        else:
            mois_garantie = max(_positif('variateur.garantie_mois', g,
                                         strict=True) for g in garanties)
            annee = -(-int(mois_garantie) // 12)
            if annee > HORIZON_ANS:
                omettre('variateur', 'garantie constructeur au-delà de '
                                     f'{HORIZON_ANS} ans : aucun '
                                     'remplacement dans le flux')
            elif not sum(lg['ttc'] for lg in variateurs):
                omettre('variateur', 'prix du variateur à renseigner : '
                                     'remplacement omis')
            else:
                porter('variateur', annee,
                       sum(lg['ttc'] for lg in variateurs), SOURCE_VARIATEUR,
                       'variateur — fin de garantie constructeur')
    return publies, flux, omissions


#: Les omissions du flux générique remplacées par le motif propre au pompage.
_OMISSIONS_REMPLACEES = ('production_annee1_kwh', 'lcoe_mad_kwh',
                         'taux_actualisation_pct', 'van_mad',
                         'retour_actualise_ans')


def _flux(investissement, economie1, charges, remplacements, *,
          taux_actualisation=None):
    """Appelle ``economie.flux_de_tresorerie`` — AUCUNE seconde arithmétique.

    Retour SANS aide : aucune aide FDA n'entre jamais ici (D-AGR-5/6).
    """
    bloc = flux_de_tresorerie(
        investissement_mad={'valeur': investissement,
                            'source': SOURCE_INVESTISSEMENT},
        economie_annee1_mad={
            'valeur': economie1,
            'source': 'dépense actuelle déclarée × part évitée des mois '
                      'cochés + entretien payé déclaré'},
        horizon_ans={'valeur': HORIZON_ANS, 'source': SOURCE_HORIZON},
        indexation_pct={'valeur': INDEXATION_PCT,
                        'source': SOURCE_INDEXATION},
        degradation_pct={'valeur': DEGRADATION_PCT,
                         'source': SOURCE_DEGRADATION},
        charges_annuelles_mad=(None if charges is None else {
            'valeur': charges, 'source': SOURCE_CHARGES}),
        remplacements=remplacements,
        taux_actualisation_pct=taux_actualisation,
    )
    if taux_actualisation is None:
        bloc['omissions'] = [
            o for o in bloc['omissions']
            if o['cle'] not in _OMISSIONS_REMPLACEES]
        bloc['omissions'].append({
            'cle': 'taux_actualisation_pct',
            'motif': "taux d'actualisation : vue interne uniquement "
                     "(D-AGR-5) — VAN, retour actualisé et flux actualisés "
                     "non publiés"})
    else:
        bloc['omissions'] = [
            o for o in bloc['omissions']
            if o['cle'] not in ('production_annee1_kwh', 'lcoe_mad_kwh')]
    bloc['omissions'].append({
        'cle': 'lcoe_mad_kwh',
        'motif': 'sans objet pour le pompage : aucune énergie vendue ni '
                 'valorisée en kWh'})
    return bloc


def _economie_vide(motif):
    return {'horizon_ans': HORIZON_ANS, 'flux': [], 'van_mad': None,
            'tri_pct': None, 'lcoe_mad_kwh': None, 'retour_ans': None,
            'retour_actualise_ans': None, 'hypotheses': [],
            'omissions': [{'cle': 'economie', 'motif': motif}]}


def _economie_annee1(par_mois, parts, entretien):
    return sum(par_mois[m] * parts[m] for m in range(12)) + entretien


# ── Le bloc ─────────────────────────────────────────────────────────────────

def _bloc_vide():
    return {
        'statut': 'omis', 'publiable_client': False,
        'motifs_non_publiable': [], 'cas': None, 'entrees_declarees': [],
        'depense_actuelle': None, 'charges_solaires': None,
        'remplacements': [], 'economie': None, 'couverture': None,
        'mad_par_m3': {'actuel': None, 'solaire': None, 'formule': None},
        'sensibilite_carburant': [], 'seuil_rentabilite_carburant': None,
        'financement': None, 'coherence': [], 'reperes_affiches': [],
        'omissions': [],
        'vue_interne': {
            'van_mad': None, 'retour_actualise_ans': None,
            'scenario_butane_non_subventionne': None,
            'aide_fda_indicative': None,
            'rendement_global_implicite_pct': None, 'omissions': [],
        },
    }


def economie_pompage(saisies, *, sortie_etude=None, lignes=None,
                     reglages=None):
    """Le bloc ``economie_pompage`` (contrat ``economie_pompage.json``).

    Args:
        saisies: ``etude_params.saisies_economie_pompage`` (propriétaire
            écran, contrat AGR3).
        sortie_etude: la sortie du moteur serveur de pompage (contrat
            ``etude_pompage_preview.json``, AGR2) — couverture, besoin,
            production, HMT, champ, mode de la pompe.
        lignes: les lignes du devis ``[{designation, quantite, prix_unitaire,
            remise, taux_tva, optionnelle, type_ligne, type_equipement,
            role_pompage, garantie_mois}]`` (ou ``total_ttc_mad`` déjà
            résolu par l'appelant) — JAMAIS le prix d'achat.
        reglages: ``{charges_pompage_solaire, regle_fda_pompage}``
            (``TariffSettings``, AGR207).
    """
    dep = depense_actuelle(saisies)
    bloc = _bloc_vide()
    bloc['cas'] = dep['cas']
    bloc['entrees_declarees'] = dep['entrees_declarees']
    bloc['depense_actuelle'] = dep['depense_actuelle']
    bloc['omissions'] = list(dep['omissions'])
    motifs = bloc['motifs_non_publiable'] = list(dep['motifs'])
    bloc['statut'] = dep['statut']

    investissement = investissement_ttc(lignes)
    publies, remplacements, omis_rempl = _remplacements(
        lignes, mode_pompe(sortie_etude))
    bloc['remplacements'] = publies
    charges_bloc, charges, motifs_charges = _charges(reglages)
    bloc['charges_solaires'] = charges_bloc

    if dep['cas'] == CAS_NOUVEAU_FORAGE:
        bloc['economie'] = _economie_vide(
            'nouveau forage : aucune énergie remplacée, aucune économie '
            'calculée')
        bloc['couverture'] = {'verifiee': False,
                              'part_evitee_par_mois': None,
                              'motif': 'aucune dépense déclarée'}
        bloc['publiable_client'] = not motifs
        return bloc

    if dep['statut'] != 'calcule':
        premier = motifs[0] if motifs else 'saisie manquante'
        bloc['economie'] = _economie_vide(
            f'{premier} : aucune économie calculée')
        bloc['couverture'] = {'verifiee': False,
                              'part_evitee_par_mois': None,
                              'motif': 'aucune dépense déclarée'}
        bloc['remplacements'] = []
        return bloc

    motifs.extend(motifs_charges)
    couverture = _couverture(sortie_etude, dep['_mois'])
    bloc['couverture'] = couverture
    economie1 = _economie_annee1(dep['_par_mois'],
                                 couverture['part_evitee_par_mois'],
                                 dep['_entretien'])
    economie = _flux(investissement, economie1, charges, remplacements)
    economie['omissions'].extend(omis_rempl)
    bloc['economie'] = economie
    bloc['publiable_client'] = not motifs
    return bloc
