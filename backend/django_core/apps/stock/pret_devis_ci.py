"""CCAT8 — « Prêt pour le devis C&I » : chaque poste du devis commercial /
industriel avec son statut, l'article en cause, la raison et le lien où corriger.

Contrat partagé : ``contract_samples/pret_devis_ci.json`` (CCAT7). Les règles
sont celles du moteur (``apps.ventes.moteur_ci.composition``) lues côté Stock
via ``selectors.produits_ci``, ``etat_ci`` (panneaux, hybrides, batteries) et le
profil société (``CompanyProfile.forfaits_ci``, app de fondation). Lecture
seule, bornée à la société (+ produits globaux), produits archivés exclus ;
AUCUN prix, prix d'achat ni marge dans la réponse : seulement « chiffré ou
non ».
"""
from decimal import Decimal, InvalidOperation

from core.product_roles import (
    LIBELLES_ROLES_CI, LIBELLES_TYPES_POSE, TYPES_POSE)

#: Les 8 prestations C&I réglables (miroir de
#: ``parametres.serializers_company.FORFAITS_CI_PRESTATIONS`` — ordre du
#: moteur ``composition.PRESTATIONS_CI``).
PRESTATIONS = (
    'etudes_ingenierie', 'pose_structure', 'pose_modules', 'raccordement_ac',
    'mise_en_service', 'dossier_raccordement', 'levage_acces', 'transport_ci',
)
#: Défaut du moteur quand le type de pose n'est pas déclaré (décision
#: fondateur du 26/10/2026) : le seul type de structure OBLIGATOIRE.
TYPE_POSE_DEFAUT = 'toit_plat_leste'

MOTIF_SANS_PRIX = 'prix de vente non saisi'
LIEN_STOCK = '/stock'
LIEN_A_COMPLETER = '/stock?ci=a_completer'
LIEN_FORFAITS = '/parametres?onglet=devis#prestations-ci'


def _montant(valeur):
    if valeur is None or valeur == '':
        return None
    try:
        x = Decimal(str(valeur))
    except (InvalidOperation, ValueError):
        return None
    return x if x.is_finite() else None


def _forfait_regle(forfait):
    """Même règle que ``moteur_ci.composition._prestation`` : une source ET au
    moins un montant."""
    forfait = forfait or {}
    return bool((forfait.get('source') or '').strip()) and any(
        _montant(forfait.get(k)) is not None
        for k in ('fixe_ht', 'par_kwc_ht', 'par_panneau_ht'))


def _forfaits_societe(company):
    from apps.parametres.models import CompanyProfile
    profil = CompanyProfile.objects.filter(company=company).first()
    return getattr(profil, 'forfaits_ci', None) or {}


def _est_parafoudre(candidat):
    return (candidat['fiche'].get('prot_type') == 'parafoudre'
            or 'parafoudre' in (candidat['nom'] or '').lower())


def _candidat(id_, nom, role, eligible, prix_connu, motif, fiche=None,
              type_pose=''):
    return {'id': id_, 'nom': nom, 'role': role, 'eligible': eligible,
            'prix_connu': prix_connu, 'motif': motif, 'fiche': fiche or {},
            'type_pose': type_pose}


def _candidats_catalogue(company):
    """Les articles de rôle C&I (``produits_ci``) en candidats neutres."""
    from .selectors import produits_ci
    return [_candidat(e['id'], e['nom'], e['role_ci'],
                      e.get('eligible_ci') is not False, e['prix_connu'],
                      e.get('motif_exclusion'), e.get('fiche'),
                      e.get('type_pose'))
            for e in produits_ci(company)]


def _candidats_options(company):
    """Panneaux, hybrides BT et batteries (aucun rôle C&I : ``etat_ci_complet``
    — CCAT2, CCAT11). Une requête, catégorie et fiche préchargées."""
    from django.db.models import Q

    from .etat_ci import etat_ci_complet
    from .models import Produit
    from .selectors import plage_batterie_onduleur, specs_for_produit

    qs = (Produit.objects
          .filter(Q(company=company) | Q(company__isnull=True),
                  is_archived=False)
          .select_related('categorie', 'fiche_technique'))
    sortie = {'panneau': [], 'onduleur_hybride': [], 'batterie': []}
    for p in qs.order_by('nom', 'id'):
        etat = etat_ci_complet(p)
        if etat is None:
            continue
        role = {'batterie_ci': 'batterie'}.get(etat['role_ci'], etat['role_ci'])
        if role not in sortie:
            continue
        c = _candidat(p.id, p.nom, role, etat['eligible_ci'],
                      etat['prix_connu'], etat['motif_exclusion'])
        if role == 'onduleur_hybride' and c['eligible']:
            c['plage'] = plage_batterie_onduleur(p)
        elif role == 'batterie' and c['eligible']:
            specs = specs_for_produit(p) or {}
            v = specs.get('v_nominal')
            c['v_nominal'] = float(v) if v is not None else None
        sortie[role].append(c)
    return sortie


def _exiger(candidats, champ, motif):
    """Revue R3 (CCAT8) — le moteur n'apparie un disjoncteur que par son
    calibre (``prot_calibre_a``) et un câble AC que par sa section
    (``cable_section_mm2``) : un article sans cette grandeur n'est JAMAIS
    composé, il ne peut donc pas rendre le poste « ok »."""
    return [c if c['fiche'].get(champ) not in (None, '')
            else dict(c, eligible=False, motif=motif) for c in candidats]


def _ok(c):
    return bool(c['eligible'] and c['prix_connu'])


def _motif(c):
    return c['motif'] or ('' if _ok(c) else MOTIF_SANS_PRIX)


def _poste(cle, libelle, groupe, obligatoire, candidats):
    """Un poste matière : ok si un candidat est chiffré ET éligible,
    a_completer si des candidats existent sans qu'aucun ne le soit, sinon
    absent."""
    if any(_ok(c) for c in candidats):
        statut, action = 'ok', ('Ouvrir le catalogue Stock', LIEN_STOCK)
        articles = []
    elif candidats:
        statut, action = 'a_completer', (
            'Compléter la fiche en Stock', LIEN_A_COMPLETER)
        articles = [{'id': c['id'], 'nom': c['nom'], 'motif': _motif(c)}
                    for c in candidats]
    else:
        statut, action = 'absent', ("Créer l'article en Stock", LIEN_STOCK)
        articles = []
    return {'cle': cle, 'libelle': libelle, 'groupe': groupe,
            'obligatoire': obligatoire, 'statut': statut, 'articles': articles,
            'action': {'texte': action[0], 'lien': action[1]}}


def _poste_forfait(cle, forfait, candidats):
    libelle = LIBELLES_ROLES_CI[cle]
    poste = {'cle': 'forfait:' + cle,
             'libelle': 'Prestation « %s »' % libelle,
             'groupe': 'prestation', 'obligatoire': True, 'articles': []}
    regle = ('Régler le forfait', LIEN_FORFAITS)
    if not _forfait_regle(forfait):
        poste['statut'], action = 'absent', regle
    elif not candidats:
        # Le forfait compte dans l'étude mais, sans article du même rôle,
        # n'apparaîtrait pas sur le devis (``composition._prestation``).
        poste['statut'], action = 'a_completer', (
            "Créer l'article « %s » en Stock (sinon le forfait n'apparaît pas "
            "sur le devis)" % libelle, LIEN_STOCK)
    else:
        poste['statut'], action = 'ok', regle
    poste['action'] = {'texte': action[0], 'lien': action[1]}
    return poste


def _batteries_compatibles(batteries, hybrides):
    """Une batterie éligible dont la tension nominale n'entre dans la plage
    d'aucun hybride éligible (règle PVOND) devient « à compléter » (motif
    dédié) ; sans hybride éligible la compatibilité ne peut pas se juger : les
    batteries restent telles quelles."""
    plages = [h['plage'] for h in hybrides if h['eligible'] and h.get('plage')]
    if not plages:
        return batteries
    out = []
    for b in batteries:
        v = b.get('v_nominal')
        if b['eligible'] and not (v is not None and any(
                bas <= v <= haut for bas, haut in plages)):
            b = dict(b, eligible=False,
                     motif="tension nominale hors plage des hybrides")
        out.append(b)
    return out


def pret_devis_ci(company):
    """``{pret, nb_obligatoires_manquants, postes[]}`` — voir le contrat."""
    catalogue = _candidats_catalogue(company)
    options = _candidats_options(company)
    forfaits = _forfaits_societe(company)

    def roles(*noms, filtre=None):
        return [c for c in catalogue if c['role'] in noms
                and (filtre is None or filtre(c))]

    def structures(type_pose):
        return roles('structure_ci', filtre=lambda c: (
            (c['type_pose'] or c['fiche'].get('struct_type_pose'))
            == type_pose))

    def libelle(role):
        return LIBELLES_ROLES_CI[role]

    postes = [
        _poste('panneau', 'Panneau solaire (puissance Pmax et prix)',
               'materiel', True, options['panneau']),
        _poste('onduleur_string', 'Onduleur string (réseau)', 'materiel', True,
               roles('onduleur_string_tri', 'onduleur_string_mono')),
        _poste('coffret_dc', libelle('coffret_dc'), 'materiel', True,
               roles('coffret_dc')),
        _poste('coffret_ac', libelle('coffret_ac'), 'materiel', True,
               roles('coffret_ac')),
        _poste('protection_ac', 'Disjoncteur AC (un article par calibre)',
               'materiel', True, _exiger(roles('protection_ac', filtre=lambda c: (
                   c['fiche'].get('prot_type') == 'disjoncteur')),
                   'prot_calibre_a', 'fiche incomplète : calibre (A)')),
        _poste('cable_ac', 'Câble AC (un article par section)', 'materiel', True,
               _exiger(roles('cable_ac'), 'cable_section_mm2',
                       'fiche incomplète : section (mm²)')),
        _poste('cable_dc', libelle('cable_dc'), 'materiel', True,
               roles('cable_dc')),
        _poste('comptage', "Comptage ou contrôleur d'injection", 'materiel',
               True, roles('compteur_injection', 'controleur_injection')),
        _poste('structure_ci:' + TYPE_POSE_DEFAUT,
               'Structure — %s' % LIBELLES_TYPES_POSE[TYPE_POSE_DEFAUT],
               'materiel', True, structures(TYPE_POSE_DEFAUT)),
    ]
    postes += [
        _poste('structure_ci:' + t, 'Structure — %s' % LIBELLES_TYPES_POSE[t],
               'materiel', False, structures(t))
        for t in TYPES_POSE if t != TYPE_POSE_DEFAUT]
    postes += [
        _poste('logger_supervision', libelle('logger_supervision'), 'materiel',
               False, roles('logger_supervision')),
        _poste('protection_dc', libelle('protection_dc'), 'materiel', False,
               roles('protection_dc', filtre=lambda c: not _est_parafoudre(c))),
        _poste('parafoudre_dc', 'Parafoudre DC', 'materiel', False,
               roles('protection_dc', filtre=_est_parafoudre)),
        _poste('parafoudre_ac', 'Parafoudre AC', 'materiel', False,
               roles('protection_ac', filtre=_est_parafoudre)),
        _poste('mise_a_la_terre', libelle('mise_a_la_terre'), 'materiel',
               False, roles('mise_a_la_terre')),
        _poste('cellule_mt', libelle('cellule_mt'), 'materiel', False,
               roles('cellule_mt')),
    ]
    postes += [_poste_forfait(cle, forfaits.get(cle), roles(cle))
               for cle in PRESTATIONS]
    postes += [
        _poste('om_ci', libelle('om_ci'), 'option', False, roles('om_ci')),
        _poste('option_batterie:hybride',
               'Onduleur hybride basse tension (option « avec batterie »)',
               'option_batterie', False, options['onduleur_hybride']),
        _poste('option_batterie:batterie',
               'Batterie compatible (option « avec batterie »)',
               'option_batterie', False,
               _batteries_compatibles(options['batterie'],
                                      options['onduleur_hybride'])),
    ]
    manquants = sum(1 for p in postes
                    if p['obligatoire'] and p['statut'] != 'ok')
    return {'pret': manquants == 0, 'nb_obligatoires_manquants': manquants,
            'postes': postes}
