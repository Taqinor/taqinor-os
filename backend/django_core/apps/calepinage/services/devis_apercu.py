"""Lane E9 (constat T4-X5-010) — AVANT « Générer le devis » : ce que le devis PORTERA.

La composition que « Générer le devis » écrirait (``generer_devis`` →
``build_devis_from_layout``) est rejouée À BLANC par le MÊME chemin
(``build_devis_from_layout(a_blanc=True)`` : étapes 1-4 du pipeline, aucune écriture,
aucune seconde composition), et l'étape Documents lit, par option, le module et
l'onduleur que le devis portera. Quand un produit DÉSIGNÉ à l'étape Électrique n'est
pas celui-là, une phrase le dit et dit pourquoi : la raison rangée par la conception
(``designations_ecartees``) quand elle existe, sinon le fait — le devis de l'atelier
compose son module depuis la pose. Lecture seule ; aucun prix servi.

D-ACAL-148 (fondateur, 26/11/2026) — l'ONDULEUR désigné est chiffré par le devis quand il est
au catalogue avec un prix et que la forme du devis le porte (décision de ``ventes``,
``creation_calepinage.decision_onduleur_designe``, rendue par la composition à blanc) : la
phrase devient l'EXCEPTION — le repli, avec sa raison. Devis « les deux » : seule l'option qui
le porte (réseau ⇒ sans, hybride ⇒ avec) est jugée.

Lot 8 (26/11) — la génération ne compose PAS toujours : quand le lead a un brouillon libre
antérieur, elle pose la question R2-22 et, rattaché, ce brouillon garde son onduleur ; l'aperçu
le dit (``ecarts`` champ ``rattacher_devis``) au lieu d'annoncer la composition comme LE devis.
"""
from __future__ import annotations

#: Les deux rôles désignables à l'étape Électrique (clés de l'entrée stockée).
ROLES_DESIGNES = (('module_produit', 'module', 'Le module'), ('onduleur_produit', 'onduleur', "L'onduleur"))
#: Les codes de supposition de la conception qui écartent une désignation (relecture E6 B2).
CODES_ECARTEES = ('designation_hors_catalogue', 'designation_ecartee')
RAISON_PAR_DEFAUT = ('le devis généré depuis l’atelier compose son matériel d’après la pose du toit : '
                     'la désignation de l’étape Électrique n’y entre pas')
#: D-ACAL-148 — le brouillon que « Générer » rendrait garde les produits qu'il porte (PV18) : son
#: onduleur n'est pas re-choisi d'après la désignation.
#: Round 4, point 6 a — vraie selon le cas : brouillon NÉ sous la règle (marqueur) ⇒ « Resynchroniser »
#: lui appliquera la désignation ; créé avant ⇒ il ne la suivra pas.
RAISON_BROUILLON_SOUS_LA_REGLE = ('ce devis existe déjà : « Générer le devis » l’ouvre tel quel, et « Resynchroniser '
                                  'le devis » lui appliquera la désignation')
RAISON_BROUILLON_AVANT_LA_REGLE = ('ce devis, créé avant que le devis suive la désignation, garde les produits qu’il '
                                   'porte ; un nouveau devis généré depuis le calepinage la suivra')
#: Relecture D-ACAL-148, point 4 — l'onduleur imposé que la composition n'a pourtant pas posé sur
#: l'option qui doit le porter (aucun cas connu ; jamais la raison par défaut, fausse depuis D-ACAL-148).
RAISON_IMPOSE_NON_POSE = 'la composition du devis ne l’a pas posé sur cette option'
MESSAGE_ECART = '%s désigné à l’étape Électrique (« %s ») n’est pas celui que le devis portera (« %s ») : %s'
LIBELLE_OPTION = {'': 'Devis', 'sans': 'Sans batterie', 'avec': 'Avec batterie'}


def _materiel_par_option(specs):
    """``[{option, libelle, module, onduleur, module_produit, onduleur_produit}]`` lus sur
    les lignes composées : une ligne sans variante vaut pour chaque option."""
    variantes = sorted({s.get('variante') or '' for s in specs} - {''}) or ['']
    options = []
    for variante in variantes:
        lignes = [s for s in specs if (s.get('variante') or '') in ('', variante)]
        module = next((s for s in lignes if s.get('role_devis') == 'panneau'), {})
        onduleur = next((s for s in lignes if str(s.get('role_devis') or '').startswith('onduleur_')), {})
        options.append({'option': variante or None, 'libelle': LIBELLE_OPTION.get(variante, variante),
                        'module': module.get('designation') or None, 'onduleur': onduleur.get('designation') or None,
                        'module_produit': module.get('produit'), 'onduleur_produit': onduleur.get('produit')})
    return options


def _ecarts(calepinage, options, decision_onduleur=None, *, brouillon=False, sous_la_regle=False):
    """Une phrase par produit désigné à l'étape Électrique qu'une option ne portera pas.
    ``decision_onduleur`` (D-ACAL-148) : la décision de la composition pour l'onduleur désigné
    (``journal['onduleur_designe']``) — chiffré, seule l'option qui le porte est jugée ; en
    repli, sa raison remplace la raison par défaut. ``brouillon`` : les options sont les lignes
    d'un brouillon existant (son onduleur n'est jamais re-choisi).

    Relecture, point 4 — pour l'onduleur, chaque issue dit SA vérité, la même phrase que la
    génération : la phrase de la décision (repli, ou passage « avec batterie » D-ACAL-159) telle
    quelle ; imposé et posé, rien ; imposé mais pas posé, :data:`RAISON_IMPOSE_NON_POSE`."""
    from apps.stock.selectors import get_produit_scoped

    from .devis_retenu import conception_du_calepinage
    from .electrique import entree_stockee

    from .variantes import onduleur_designe_a_la_main

    entree = entree_stockee(calepinage)
    if not onduleur_designe_a_la_main(calepinage):  # Lot 8 — « repris de l'original » : aucune désignation à juger
        entree.pop('onduleur_produit', None)
    rangees = [s for s in ((conception_du_calepinage(calepinage) or {}).get('suppositions') or ())
               if s.get('code') in CODES_ECARTEES]
    phrases = []
    for champ, cle, sujet in ROLES_DESIGNES:
        designe = entree.get(champ)
        if designe in (None, ''):
            continue
        if champ == 'onduleur_produit' and decision_onduleur and decision_onduleur.get('message'):
            phrases.append({'champ': champ, 'message': decision_onduleur['message']})
            continue
        jugees = options
        if champ == 'onduleur_produit' and decision_onduleur and decision_onduleur.get('impose'):
            option = decision_onduleur.get('option') or None
            jugees = [o for o in options if option is None or o['option'] in (None, option)]
        portes = [o for o in jugees if str(o[f'{cle}_produit']) != str(designe)]
        if not portes:
            continue
        try:
            produit = get_produit_scoped(calepinage.company, int(designe))
        except (TypeError, ValueError):
            produit = None
        raison = next((s.get('message') for s in rangees if s.get('champ') == champ), None)
        if champ == 'onduleur_produit' and decision_onduleur:
            raison = RAISON_IMPOSE_NON_POSE
        elif champ == 'onduleur_produit' and brouillon:
            raison = RAISON_BROUILLON_SOUS_LA_REGLE if sous_la_regle else RAISON_BROUILLON_AVANT_LA_REGLE
        porte = ' / '.join(sorted({o[cle] or 'aucun' for o in portes}))
        nom = getattr(produit, 'nom', None) or 'produit inconnu'
        motif = (raison or RAISON_PAR_DEFAUT).rstrip('. ') + '.'
        phrases.append({'champ': champ, 'message': MESSAGE_ECART % (sujet, nom, porte, motif)})
    return phrases


def _suit_les_designations(devis):
    """Le brouillon rendu est-il né sous la règle des désignations (lecture ``ventes``) ?"""
    from .devis import devis_suit_les_designations

    return devis_suit_les_designations(devis)


def _ecart_batterie(decision):
    """D-ACAL-164 — la phrase de la décision sur la batterie désignée (repli, ou « sans batterie »),
    LA MÊME que la génération met dans ``avertissements`` ; ``[]`` quand elle est chiffrée."""
    return ([{'champ': 'batterie.produit', 'message': decision['message']}]
            if decision and decision.get('message') else [])


def _role_de_ligne(ligne):
    """Lot 8 (B2) — le rôle d'une ligne déjà au devis, résolu comme le reste du code pour une ligne
    sans rôle figé (``ventes.domain.bordereau._boq_role_de_ligne``) : le rôle FIGÉ de la ligne, sinon
    le rôle déclaré de son produit, sinon les mots-clés de la désignation — le classifieur unique
    ``core.product_roles.role_effectif``, celui de ventes injecté (``ventes.selectors``)."""
    from core.product_roles import role_effectif

    from .equipements import classer_produit_nom

    declare = ligne.role_devis or getattr(getattr(ligne, 'produit', None), 'role_devis', None)
    return role_effectif(declare, None, ligne.designation or '', classer_nom=classer_produit_nom)[0]


def _specs_du_brouillon(devis):
    """Lane E9b — les lignes RÉELLES du brouillon que le bouton ouvrirait, à la forme des specs de
    composition que lit :func:`_materiel_par_option` (rôle, variante, désignation, produit) : on lit
    ce que le devis porte, rien n'est recomposé. Lot 8 (B2) — rôle résolu par :func:`_role_de_ligne`."""
    return [{'role_devis': _role_de_ligne(ligne), 'variante': ligne.variante or '',
             'designation': ligne.designation, 'produit': ligne.produit_id}
            for ligne in devis.lignes.select_related('produit').order_by('ordre', 'pk')]


#: Lot 8 (aperçu ≠ devis, 26/11) — le lead a un brouillon LIBRE né avant ce calepinage : « Générer »
#: ne compose pas, il pose la question R2-22 (``devis._brouillon_libre_choisi``) ; rattaché, ce brouillon
#: est resynchronisé (``reconcilier``, PV18 : les produits des lignes ne sont jamais re-choisis).
MESSAGE_BROUILLON_LIBRE = ('Ce lead a déjà le devis %s (brouillon), créé avant ce calepinage : rattaché à ce '
                           'calepinage, il garde les produits qu’il porte%s et ne prend que le compte de '
                           'panneaux et le scénario de la pose ; le matériel ci-dessus est celui d’un autre devis.')


def _phrase_brouillon_libre(reference, onduleurs):
    """Lot 8 (B2) — la phrase R2-22 ; l'onduleur n'est nommé que s'il est ÉTABLI sur les lignes
    (pompage, micro-onduleurs non reconnus, rôle introuvable : la phrase s'en tait)."""
    noms = ' / '.join(sorted({o for o in onduleurs if o}))
    return MESSAGE_BROUILLON_LIBRE % (reference, f' (onduleur « {noms} »)' if noms else '')


def _ecart_brouillon_libre(libre):
    """L'entrée ``ecarts`` R2-22 pour le brouillon libre que « Générer » proposera de rattacher (le
    plus récent, comme le 409 ``devis_existant``). Ce qu'il porte est lu sur SES lignes."""
    onduleurs = [o['onduleur'] for o in _materiel_par_option(_specs_du_brouillon(libre))]
    return {'champ': 'rattacher_devis',
            'message': _phrase_brouillon_libre(libre.reference or f'#{libre.pk}', onduleurs)}


#: Lot 8 (D-ACAL-106 « toujours aucun devis ni aucun prix ») — ce que dit l'aperçu à qui ne peut pas
#: LIRE un devis (``ventes.selectors_assistant.lit_les_devis``) : qu'un devis existe, jamais lequel
#: (ni référence, ni statut, ni montant, ni matériel lu sur ses lignes). Le motif est celui de la garde
#: de lecture des devis (``LectureVentes.message``).
MOTIF_LECTURE_VENTES = 'accès réservé aux rôles du module Ventes'
MESSAGE_DEVIS_EXISTANT_CAVIARDE = f'Un devis brouillon existe déjà pour ce calepinage ({MOTIF_LECTURE_VENTES}).'
MESSAGE_DEJA_RATTACHE_CAVIARDE = f'Ce calepinage est déjà rattaché à un devis ({MOTIF_LECTURE_VENTES}).'
MESSAGE_BROUILLON_LIBRE_CAVIARDE = ('Ce lead a déjà un devis brouillon, créé avant ce calepinage : '
                                    '« Générer le devis » proposera de lui rattacher ce calepinage '
                                    f'({MOTIF_LECTURE_VENTES}).')


def _caviarder(reponse, issue):
    """Lot 8 (D-ACAL-106) — la réponse pour un utilisateur SANS droit de lecture des devis. Pure.
    Mêmes clés ; ce qui décrit le calepinage (composition du catalogue, désignations) reste ; ce qui
    NOMME un devis part : brouillon rendu (ses lignes et sa référence), devis lié du refus « déjà
    rattaché », brouillon libre de la phrase R2-22."""
    from .devis import ISSUE_BROUILLON_LIBRE, ISSUE_DEJA_RATTACHE, ISSUE_RENDU

    if issue == ISSUE_RENDU:
        return {'options': [], 'ecarts': [], 'refus': MESSAGE_DEVIS_EXISTANT_CAVIARDE,
                'source': reponse['source'], 'reference': None}
    if issue == ISSUE_DEJA_RATTACHE:
        return dict(reponse, refus=MESSAGE_DEJA_RATTACHE_CAVIARDE, reference=None)
    if issue == ISSUE_BROUILLON_LIBRE:
        ecarts = [dict(e, message=MESSAGE_BROUILLON_LIBRE_CAVIARDE) if e.get('champ') == 'rattacher_devis' else e
                  for e in reponse['ecarts']]
        return dict(reponse, ecarts=ecarts, reference=None)
    return reponse


def apercu_materiel_du_devis(calepinage, surfaces=None, *, lit_les_devis=True):
    """``{options, ecarts, refus, source, reference}`` — voir :func:`_apercu_complet`. Lot 8
    (D-ACAL-106) — ``lit_les_devis`` (la vue passe ``ventes.selectors_assistant.lit_les_devis`` de
    l'utilisateur) : faux ⇒ :func:`_caviarder` ; vrai ⇒ la réponse complète, inchangée."""
    reponse, issue = _apercu_complet(calepinage, surfaces)
    return reponse if lit_les_devis else _caviarder(reponse, issue)


def _apercu_complet(calepinage, surfaces):
    """``({options, ecarts, refus, source, reference}, issue)`` : par option, le module et l'onduleur que
    « Générer le devis » porterait, les désignations électriques qu'il ne portera pas (phrase et
    raison) ; ``refus`` = la phrase de la composition (ou de l'absence de toit, ou de la sélection
    de surfaces) quand rien ne se compose. Lane E9b — LES décisions de la génération :
    ``surfaces`` (les clés cochées, ``None`` = tout) passent par ``devis._layout_des_surfaces`` ;
    le brouillon que le bouton RENDRAIT (``devis._brouillon_rendu``) est lu sur ses lignes
    (``source: brouillon_existant`` + sa référence), sinon la composition à blanc
    (``source: composition``), sous des réglages lus sans être créés. Lot 8 (B1) — l'ORDRE est
    celui de la génération (``devis._ordre_de_generation``) : lié à un devis non réutilisable ⇒
    ``refus`` = le 409 que la génération rendrait ; brouillon libre ⇒ la phrase R2-22. N'écrit rien."""
    from .devis import (
        ISSUE_BROUILLON_LIBRE, ISSUE_DEJA_RATTACHE, ISSUE_RENDU, DevisRefuse, _brouillon_rendu,
        _brouillons_libres_anterieurs, _devis_lie_actif, _empreinte_generee, _exiger_layout,
        _layout_des_surfaces, _lead_et_client, _ordre_de_generation, _refus_deja_rattache,
    )
    from .equipements import composition_a_blanc

    from .devis import _batterie_designee, _onduleur_designe

    composer, AutoDevisError = composition_a_blanc()
    source, reference, libre, issue = 'composition', None, None, None
    journal = {}
    company = calepinage.company
    try:
        layout = _layout_des_surfaces(_exiger_layout(calepinage), surfaces)
        lead, _client = _lead_et_client(calepinage)
        lie = _devis_lie_actif(calepinage)
        rendu = _brouillon_rendu(calepinage, company, lead, _empreinte_generee(calepinage, layout), lie=lie)
        issue, retenu = _ordre_de_generation(lie, rendu, lambda: (
            _brouillons_libres_anterieurs(calepinage, company, lead) if lead is not None else []))
        if issue == ISSUE_DEJA_RATTACHE:
            raise _refus_deja_rattache(retenu)
        if issue == ISSUE_RENDU:
            source, reference = 'brouillon_existant', retenu.reference
            specs = _specs_du_brouillon(retenu)
        else:
            specs = composer(layout=layout, company=company, lead=lead,
                             onduleur_designe=_onduleur_designe(calepinage), journal=journal,
                             batterie_designee=_batterie_designee(calepinage))
            if issue == ISSUE_BROUILLON_LIBRE:
                libre = _ecart_brouillon_libre(retenu[0])
    except (AutoDevisError, DevisRefuse) as refus:
        return {'options': [], 'ecarts': [], 'refus': getattr(refus, 'message', None) or str(refus),
                'source': None, 'reference': None}, issue
    options = _materiel_par_option(specs)
    sous_la_regle = source == 'brouillon_existant' and _suit_les_designations(retenu)
    ecarts = (_ecarts(calepinage, options, journal.get('onduleur_designe'), brouillon=source == 'brouillon_existant',
                      sous_la_regle=sous_la_regle)
              + ([libre] if libre else []) + _ecart_batterie(journal.get('batterie_designee'))
              + [{'champ': 'geometry.tiltDeg', 'message': m} for m in journal.get('suppositions_toit') or ()])
    for option in options:
        option.pop('module_produit')
        option.pop('onduleur_produit')
    return {'options': options, 'ecarts': ecarts, 'refus': None, 'source': source, 'reference': reference}, issue
