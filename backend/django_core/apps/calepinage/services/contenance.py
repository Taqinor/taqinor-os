"""Copilote vague 2 (CALA10) — « combien de panneaux tiennent ? » AVANT dessin.

Décision fondateur D-W2-Q3 (OUI_AUSSI_DICTEE) : une ESTIMATION est permise
depuis une visite VALIDÉE (zone utile mesurée), depuis les pans DÉJÀ tracés du
calepinage ouvert, ET depuis des dimensions DICTÉES par l'utilisateur — chaque
fois étiquetée par son ``origine``. Contrat :
``contract_samples/calepinage_assistant_contenance.json``.

CE QUE CE MODULE NE FAIT JAMAIS : écrire (aucune version, aucun journal,
aucun job), toucher la conception ou le devis, donner une production ou un
prix, poser une géométrie sur la carte (D-ACAL-1, ``USE_MOTEUR_CALEPINAGE``
reste éteint : ce compte n'est pas autoritaire, le calepinage dessiné fait foi).

LE CALCUL : le MÊME moteur que la villa et l'atelier
(``villa_service.calepiner_surface``) AVEC la politique de pas de l'atelier
(``traduction.politique_de_pose`` : toit plat → espacement anti-ombrage à la
latitude du lead, pente → pose affleurante) — jamais ``moteur/pose``, dont la
chaîne HTTP ignore l'espacement des rangées et surcompterait un toit-terrasse.
Retrait de rive et allée = réglages société (``degagements``), avec leur
phrase. Le panneau vient de ``produit``, sinon du module désigné ou de la ligne
du devis lié (``electrique.resoudre_materiel``) — jamais d'un kit par défaut ;
ses cotes et sa puissance sont lues sur la FICHE (fiche incomplète → 409).
Tout ce qui est supposé est DIT (règle fondateur du 17/11/2026).
"""
from __future__ import annotations

from dataclasses import replace

from .assistant import RefusAssistant

ORIGINES = ('visite', 'trace', 'dicte')
#: Bornes des dimensions dictées (contrat).
BORNES_COTE_M = (0.5, 200.0)
BORNES_PENTE_DEG = (0.0, 60.0)
#: Inclinaison des tables sur toit plat : la valeur de l'atelier
#: (``traduction.entree_depuis_layout``, ``inclinaison_deg=10.0``).
INCLINAISON_TABLES_PLAT_DEG = 10.0
POLITIQUES = {'AFFLEURANT': 'affleurante', 'ANTI_OMBRAGE': 'anti_ombrage'}
FIN_LIBELLE = "rien n'est enregistré ; le calepinage dessiné fait foi"

SUPPOSE_RECTANGLE = 'Zone utile rectangulaire, obstacles non relevés en géométrie'
SUPPOSE_SENS = 'Sens de pose inconnu : les deux sens sont calculés'
SUPPOSE_PLAN = 'Cotes relevées dans le plan du toit, modules posés à plat sur le pan'
SUPPOSE_TABLES = 'Tables inclinées à 10° sur toit plat (valeur de l\'atelier)'
SUPPOSE_LATITUDE = ('Position du site inconnue : espacement anti-ombrage à la '
                    'constante nationale du moteur')


def _refus_fiche():
    return RefusAssistant(
        'Fiche du panneau incomplète : renseignez la longueur, la largeur et la '
        'puissance dans le stock (fiche technique) avant d\'estimer.',
        'produit', 'fiche_incomplete')


SUPPOSE_PANNEAU = 'Panneau non précisé : celui du devis automatique (%s)'


def _panneau(company, produit_id, ouvert):
    """``(produit, kit, supposition)`` — le panneau demandé, sinon celui du
    calepinage ouvert (désigné, ou ligne du devis lié), sinon celui que le
    devis automatique retient par défaut (DIT dans les suppositions) ; refus
    nommé quand aucun n'est désigné."""
    from apps.stock.selectors import get_produit_scoped

    from ..villa_service import kit_panneau_du_produit
    from .electrique import entree_stockee, resoudre_materiel

    if produit_id is None and ouvert is not None:
        materiel = resoudre_materiel(company, entree_stockee(ouvert), calepinage=ouvert)
        produit_id = (materiel.get('produits') or {}).get('module')
    par_defaut = False
    if produit_id is None:
        from apps.ventes.selectors_assistant import panneau_par_defaut_id

        produit_id = panneau_par_defaut_id(company)
        par_defaut = produit_id is not None
    if produit_id is None:
        raise RefusAssistant(
            'Choisissez le panneau : cherchez-le dans le catalogue '
            '(ventes.catalogue.chercher, genre panneau) et donnez son '
            'identifiant (produit).', 'produit', 'panneau_non_designe')
    produit = get_produit_scoped(company, produit_id)
    if produit is None:
        raise RefusAssistant('Panneau introuvable dans le catalogue de la société.',
                             'produit', 'produit_introuvable', 404)
    kit = kit_panneau_du_produit(produit, company=company)
    if kit is None:
        raise _refus_fiche()
    return produit, kit, (SUPPOSE_PANNEAU % produit.nom if par_defaut else None)


def _nombre(valeur):
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    return nombre if nombre == nombre else None


def _mesures(liste):
    return {m.get('code'): m.get('valeur') for m in (liste or ()) if isinstance(m, dict)}


def _zones_de_la_visite(releve):
    """``[(nom, longueur, largeur, pente, plat)]`` de la visite VALIDÉE
    (résidentiel : la zone utile ; C&I : ses zones), suppositions dites."""
    if releve.get('visite_id') is None:
        raise RefusAssistant(
            'Aucune visite validée pour ce lead : faites valider la visite, ou '
            'donnez les dimensions du toit (origine « dicte »).',
            'visite_id', 'visite_non_validee')
    brutes = releve.get('zones_toiture') or [
        dict(_mesures(releve.get('mesures')), libelle='Zone utile')]
    zones, ecartees = [], []
    for brute in brutes:
        nom = str(brute.get('libelle') or 'Zone utile')[:80]
        longueur, largeur = _nombre(brute.get('longueur_m')), _nombre(brute.get('largeur_m'))
        plat = brute.get('toit_plat') is True
        pente = 0.0 if plat else _nombre(brute.get('pente_deg'))
        if not longueur or not largeur or pente is None:
            ecartees.append(nom)
            continue
        zones.append((nom, longueur, largeur, pente, plat or pente < 5.0))
    if not zones:
        raise RefusAssistant(
            'La visite validée ne porte pas la longueur, la largeur et la pente '
            '(ou « toit plat ») de la zone utile : complétez le relevé.',
            'visite_id', 'mesure_absente')
    return zones, [f'Zone « {nom} » sans cotes ou pente relevées : non comptée'
                   for nom in ecartees]


def _compter(longueur, largeur, pente, plat, kit, contexte):
    """``(min, max, politique, optimal)`` d'un rectangle, les deux sens."""
    from core.calepinage.surfaces.rectangle import SurfaceRectangle
    from core.calepinage.types import Parametres

    from ..villa_service import calepiner_surface
    from .traduction import politique_de_pose

    politique = politique_de_pose(plat, pente, contexte['latitude'])
    code = POLITIQUES.get(getattr(politique, 'code', ''), 'affleurante')
    kit_pose = replace(kit, inclinaison_deg=(INCLINAISON_TABLES_PLAT_DEG
                                             if code == 'anti_ombrage' else 0.0))
    extra = {} if contexte['allee'] is None else {'allee_m': contexte['allee']}
    parametres = Parametres(kits=(kit_pose,), rives=contexte['rives'], **extra)
    comptes = []
    for cote_a, cote_b in ((longueur, largeur), (largeur, longueur)):
        surface = SurfaceRectangle(repere='ZONE', longueur_m=cote_a,
                                   largeur_m=cote_b, rives=contexte['rives'])
        resultat = calepiner_surface(surface=surface, kits=(kit_pose,),
                                     parametres=parametres, politique=politique)['resultat']
        comptes.append((int(resultat.modules), bool(resultat.optimal)))
    nombres = [c[0] for c in comptes]
    return min(nombres), max(nombres), code, all(c[1] for c in comptes)


def _ligne(nom, longueur, largeur, pente, plat, comptes, wc):
    modules_min, modules_max, politique, optimal = comptes
    return {'zone': nom, 'longueur_m': longueur, 'largeur_m': largeur,
            'pente_deg': pente, 'plat': plat,
            'modules_min': modules_min, 'modules_max': modules_max,
            'kwc_min': round(modules_min * wc / 1000.0, 2),
            'kwc_max': round(modules_max * wc / 1000.0, 2),
            'politique': politique, 'optimal': optimal}


def _zones_du_trace(ouvert, produit, parametres, wc):
    """Les pans DÉJÀ tracés du calepinage ouvert, par le traducteur UNIQUE
    (``villa_service.calepiner_pan_traduit``) — le document n'est jamais
    modifié. Un pan a son azimut : un seul sens (min = max)."""
    from ..villa_service import calepiner_pan_traduit
    from .traduction import TraductionRefusee

    document = ouvert.roof_layout if ouvert is not None and isinstance(
        ouvert.roof_layout, dict) else {}
    pans = [p for p in (document.get('zones') or ())
            if isinstance(p, dict) and len(p.get('vertices') or ()) >= 3]
    if not pans:
        raise RefusAssistant(
            "Ce lead n'a pas de toit tracé : donnez les dimensions (origine "
            '« dicte ») ou faites valider la visite (origine « visite »).',
            'origine', 'aucun_trace')
    lignes, regles = [], []
    for rang, pan in enumerate(pans):
        try:
            sortie = calepiner_pan_traduit(document, pan, produit_panneau=produit,
                                           parametres=parametres)
        except TraductionRefusee as refus:
            raise RefusAssistant(str(refus), refus.champ or 'origine', 'trace_illisible') from None
        traduction, modules = sortie['traduction'], int(sortie['resultat'].modules)
        code = POLITIQUES.get(getattr(traduction.politique, 'code', ''), 'affleurante')
        pente = _nombre(pan.get('pitchDeg')) or 0.0
        lignes.append(_ligne(str(pan.get('label') or pan.get('id') or f'Pan {rang + 1}')[:80],
                             None, None, pente, code == 'anti_ombrage',
                             (modules, modules, code, bool(sortie['resultat'].optimal)), wc))
        regles = [traduction.regle_retrait, traduction.regle_allee]
    return lignes, regles


def _contexte(company, lead):
    """Rives, allée et latitude : réglages société (avec leurs phrases) et
    repère du lead (``crm.selectors.repere_toit``, jamais deviné)."""
    from core.calepinage.types import Rives

    from apps.crm.selectors import repere_toit

    from ..selectors import parametres_de_societe
    from .degagements import SECTION, allee_technique, retrait_effectif

    parametres = parametres_de_societe(company)
    degagements = parametres.get(SECTION) or {}
    retrait, regle_retrait = retrait_effectif(degagements)
    allee, regle_allee = allee_technique(degagements)
    pin = repere_toit(lead)[0]
    return {'parametres': parametres, 'rives': Rives(laterale_m=retrait, extremite_m=retrait),
            'allee': allee, 'regles': [regle_retrait, regle_allee],
            'latitude': pin.get('lat') if isinstance(pin, dict) else None}


def _zones_rectangles(origine, lead, cotes, kit, contexte):
    """``(lignes, suppositions, releve)`` pour ``visite`` et ``dicte``."""
    from apps.visites.selectors import releve_pour_calepinage

    releve, notes = {}, []
    if origine == 'visite':
        releve = releve_pour_calepinage(lead) or {}
        zones, notes = _zones_de_la_visite(releve)
        notes = [SUPPOSE_RECTANGLE, SUPPOSE_SENS] + notes
    else:
        plat = cotes.get('toit_plat') is True
        pente = 0.0 if plat else cotes['pente_deg']
        zones = [('Dimensions dictées', cotes['longueur_m'], cotes['largeur_m'],
                  pente, plat or pente < 5.0)]
        notes = ['Dimensions dictées, non mesurées', SUPPOSE_SENS]
    lignes = []
    for nom, longueur, largeur, pente, plat in zones:
        comptes = _compter(longueur, largeur, pente, plat, kit, contexte)
        lignes.append(_ligne(nom, longueur, largeur, pente, plat, comptes,
                             kit.puissance_module_wc))
        notes.append(SUPPOSE_TABLES if comptes[2] == 'anti_ombrage' else SUPPOSE_PLAN)
    return lignes, notes, releve


def _libelle(origine, releve):
    if origine == 'dicte':
        return f'Estimation sur dimensions dictées — {FIN_LIBELLE}'
    if origine == 'trace':
        return f'Estimation sur le tracé du calepinage — {FIN_LIBELLE}'
    from core.formats_fr import formater_date
    from django.utils.dateparse import parse_datetime

    moment = parse_datetime(str(releve.get('validee_le') or ''))
    date = f' du {formater_date(moment.date())}' if moment is not None else ''
    return f'Estimation (visite validée{date}) — {FIN_LIBELLE}'


def estimer(user, *, lead_id, origine, cotes=None, produit_id=None):
    """CALA10 — l'estimation de contenance (forme EXACTE du contrat).

    Raises:
        LeadIntrouvable: lead hors de la portée CRM (404).
        RefusAssistant: visite non validée, mesure absente, aucun tracé,
            panneau non désigné, fiche incomplète (409) ; produit inconnu (404).
    """
    from apps.agent.ecrans import chemin

    from .assistant import calepinage_ouvert_visible, lead_de_l_appelant

    lead = lead_de_l_appelant(user, lead_id)
    ouvert, _hors_vue = calepinage_ouvert_visible(user, lead.pk)
    produit, kit, note_panneau = _panneau(user.company, produit_id, ouvert)
    contexte = _contexte(user.company, lead)
    if origine == 'trace':
        lignes, regles = _zones_du_trace(ouvert, produit, contexte['parametres'],
                                         kit.puissance_module_wc)
        notes, releve = ['Pans tracés du calepinage, document non modifié'], {}
    else:
        lignes, notes, releve = _zones_rectangles(origine, lead, cotes or {}, kit, contexte)
        regles = list(contexte['regles'])
    if any(ligne['politique'] == 'anti_ombrage' for ligne in lignes):
        regles.append('Espacement anti-ombrage des rangées (toit plat, latitude du lead)')
        if contexte['latitude'] is None:
            notes.append(SUPPOSE_LATITUDE)
    return {
        'lead': lead.pk,
        'origine': origine,
        'libelle': _libelle(origine, releve),
        'visite_id': releve.get('visite_id'),
        'validee_le': releve.get('validee_le'),
        'produit': {'id': produit.pk, 'nom': produit.nom, 'wc': kit.puissance_module_wc,
                    'longueur_m': kit.module_long_m, 'largeur_m': kit.module_court_m},
        'zones': lignes,
        'total': {cle: (round(sum(ligne[cle] for ligne in lignes), 2) if cle.startswith('kwc')
                        else sum(ligne[cle] for ligne in lignes))
                  for cle in ('modules_min', 'modules_max', 'kwc_min', 'kwc_max')},
        'regles': [r for r in dict.fromkeys(regles) if r],
        'suppositions': list(dict.fromkeys(notes + ([note_panneau] if note_panneau else []))),
        'a_faire': 'dessiner' if ouvert is not None else 'preparer_calepinage',
        'lien': (chemin('calepinage', ouvert.pk, 'reprise-visite' if origine == 'visite' else None)
                 if ouvert is not None else chemin('lead', lead.pk)),
    }
