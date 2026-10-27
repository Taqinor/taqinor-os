"""CCAT13 — « Prêt pour le devis agricole » : chaque poste du kit de pompage
avec son statut, l'article en cause, la raison et le lien où corriger.

Contrat partagé : ``contract_samples/pret_devis_agricole.json``. Même forme et
mêmes helpers que le jumeau C&I (``pret_devis_ci``). Les règles sont celles du
noyau ``core.pompage`` (``selection.choisir_pompe``, ``champ.choisir_variateur``,
``kit.composer_kit``) lues côté Stock via ``selectors.produits_pompage`` :

* pompe : l'ALIMENTATION se lit comme le moteur (``alimentation_produit``) et il
  faut une courbe constructeur, une puissance (kW ou CV) et un prix de vente ;
* variateur : kW de la fiche (``pompe_kw`` > 0) et prix ;
* structure au sol : prix de vente (le barème n'est pas lu pour ce rôle) ;
* installation : le produit RETENU par le moteur (``kit._par_role``) doit porter
  un barème (``kit.bareme_saisi``) ; sinon le moteur retombe sur le barème
  toiture avec une alerte interne ;
* transport : ligne composée seulement si un article de rôle ``transport`` est
  chiffré, sinon simplement omise — poste NON obligatoire ;
* options : ``core.pompage.kit.OPTIONS`` (lues, jamais recopiées).

Lecture seule, bornée à la société (+ produits globaux), produits archivés
exclus ; AUCUN prix, prix d'achat ni marge dans la réponse.
"""
from core.pompage.kit import OPTIONS, _par_role, bareme_saisi
from core.pompage.selection import _a_courbe, alimentation_produit, kw_pompe
from core.product_roles import LIBELLES_ROLES_POMPAGE

from .pret_devis_ci import MOTIF_SANS_PRIX, _candidat, _poste

MOTIF_SANS_COURBE = 'courbe constructeur absente'
MOTIF_SANS_KW = 'puissance (kW ou CV) non saisie'
MOTIF_SANS_KW_VARIATEUR = 'puissance (kW) non saisie'
MOTIF_SANS_BAREME = 'barème fixe / par panneau non saisi'
MOTIF_NON_RETENU = "un autre article du rôle est retenu en premier par le moteur"


def _positif(valeur):
    try:
        return float(valeur) > 0
    except (TypeError, ValueError):
        return False


def _lecture_catalogue(company):
    """Une requête : panneaux, transports et barèmes lus sur les produits
    (``produits_pompage`` ne sert pas le barème)."""
    from django.db.models import Q

    from .etat_ci import _role_effectif, etat_panneau
    from .models import Produit

    qs = (Produit.objects
          .filter(Q(company=company) | Q(company__isnull=True),
                  is_archived=False)
          .select_related('categorie', 'fiche_technique'))
    panneaux, transports, baremes = [], [], {}
    for p in qs.order_by('nom', 'id'):
        baremes[p.id] = {'prix_fixe_ht': p.prix_fixe_ht,
                         'prix_par_panneau_ht': p.prix_par_panneau_ht}
        etat = etat_panneau(p)
        if etat is not None:
            panneaux.append(_candidat(
                p.id, p.nom, 'panneau', etat['eligible_ci'],
                etat['prix_connu'], etat['motif_exclusion']))
        elif _role_effectif(p)[0] == 'transport':
            transports.append(_candidat(
                p.id, p.nom, 'transport', True,
                bool(p.prix_vente and p.prix_vente > 0), None))
    return panneaux, transports, baremes


def _pompes(produits, alimentation):
    """Les pompes de l'alimentation voulue, avec la raison pour laquelle le
    moteur ne peut pas les choisir (courbe, puissance, prix)."""
    candidats = []
    for e in produits:
        if e.get('role_pompage') != 'pompe' or (
                alimentation_produit(e) != alimentation):
            continue
        raisons = []
        if not _a_courbe(e):
            raisons.append(MOTIF_SANS_COURBE)
        if not kw_pompe(e)[0]:
            raisons.append(MOTIF_SANS_KW)
        if not e['prix_connu']:
            raisons.append(MOTIF_SANS_PRIX)
        candidats.append(_candidat(
            e['id'], e['nom'], 'pompe', not raisons, e['prix_connu'],
            ' ; '.join(raisons) or None))
    return candidats


def _du_role(produits, role, exiger=None):
    """Les éléments ``produits_pompage`` d'un rôle en candidats ; ``exiger``
    (prédicat, motif) rend inéligible ce qui ne le satisfait pas."""
    candidats = []
    for e in produits:
        if e.get('role_pompage') != role:
            continue
        ok = exiger is None or exiger[0](e)
        candidats.append(_candidat(
            e['id'], e['nom'], role, ok, e['prix_connu'],
            None if ok else exiger[1]))
    return candidats


def _installations(produits, baremes):
    """Le moteur retient ``_par_role`` (le premier PRICÉ, sinon le premier) et
    n'applique le barème INST-PMP que si CE produit le porte."""
    elements = [dict(e, **baremes.get(e['id'], {})) for e in produits
                if e.get('role_pompage') == 'installation_pompage']
    retenu = _par_role(elements, 'installation_pompage')
    candidats = []
    for e in elements:
        a_bareme = bareme_saisi(e)
        if retenu is not None and e['id'] == retenu['id']:
            motif = None if a_bareme else MOTIF_SANS_BAREME
        else:
            motif = MOTIF_SANS_BAREME if not a_bareme else MOTIF_NON_RETENU
        candidats.append(_candidat(e['id'], e['nom'],
                                   'installation_pompage', motif is None,
                                   True, motif))
    return candidats


def pret_devis_agricole(company):
    """``{pret, nb_obligatoires_manquants, postes[]}`` — voir le contrat."""
    from .selectors import produits_pompage

    produits = produits_pompage(company)
    panneaux, transports, baremes = _lecture_catalogue(company)
    libelle = LIBELLES_ROLES_POMPAGE

    postes = [
        _poste('pompe:tri', 'Pompe à courbe constructeur, triphasée',
               'materiel', True, _pompes(produits, 'tri')),
        _poste('pompe:mono', 'Pompe à courbe constructeur, monophasée',
               'materiel', True, _pompes(produits, 'mono')),
        _poste('variateur_pompage', libelle['variateur_pompage'], 'materiel',
               True, _du_role(produits, 'variateur_pompage', (
                   lambda e: _positif(e.get('pompe_kw')),
                   MOTIF_SANS_KW_VARIATEUR))),
        _poste('panneau', 'Panneau solaire (puissance Pmax et prix)',
               'materiel', True, panneaux),
        _poste('structure_sol', libelle['structure_sol'], 'materiel', True,
               _du_role(produits, 'structure_sol')),
        _poste('installation_pompage',
               'Installation pompage (barème fixe / par panneau)',
               'prestation', True, _installations(produits, baremes)),
        _poste('transport', 'Transport', 'prestation', False, transports),
    ]
    postes += [
        _poste('option:' + cle, lib, 'option', False,
               _du_role(produits, role))
        for cle, role, lib in OPTIONS]
    manquants = sum(1 for p in postes
                    if p['obligatoire'] and p['statut'] != 'ok')
    return {'pret': manquants == 0, 'nb_obligatoires_manquants': manquants,
            'postes': postes}
