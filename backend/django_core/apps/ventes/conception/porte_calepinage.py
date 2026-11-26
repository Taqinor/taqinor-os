"""La SEULE porte du moteur unique vers ``apps/calepinage`` (D-ACAL-97).

Le moteur (``apps/ventes/conception/``) lit le calepinage par ses portes
``selectors`` / ``services`` seulement, et toujours depuis ce module (un seul
fichier de ``ventes`` en plus au cliquet ACAL1009) :

* ACAL2016 — les VERDICTS électriques d'une option, jugés par LA règle
  existante du ratio (``calepinage/services/ratio_devis.py::juger_ratio``,
  ACAL1954, D-ACAL-91) et la règle D-HYB-1 de la capacité publiée d'un hybride
  (``core.electrique.onduleurs.capacite_publiee_hybride``) : aucune seconde
  règle ici, le moteur RANGE le verdict et « Prêt à envoyer ? » le relit ;
* ACAL2018 — la pose du toit tracé et LA simulation de la pose, par la façade
  ``calepinage/services/pose_pour_moteur.py`` (jamais ``simulation.py``).

Rien n'est écrit, sauf LA simulation de la pose (``simuler_la_pose`` : le détail rangé
dans ``Calepinage.resultat`` comme le bouton), en tâche seulement (relecture E6).
"""
from contextlib import contextmanager
from contextvars import ContextVar
from types import SimpleNamespace

from apps.ventes.domain.taille import AutoDevisError


def _nombre(valeur):
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _onduleur_lu(company, produit_id):
    """``(fiche, produit)`` : la fiche (bloc plat) de l'onduleur ``produit_id`` de ``company``
    et le produit, UNE lecture (D-HYB-1 : son nom et son rôle servent aussi) ; ``({}, None)`` sinon."""
    from apps.stock.selectors import get_produit_scoped, specs_for_produit

    produit = get_produit_scoped(company, produit_id) if company is not None and produit_id else None
    return ((specs_for_produit(produit) or {}) if produit is not None else {}), produit


def _reglages_electriques(company):
    """La section « electrique_societe » des réglages calepinage (seuils DC/AC saisis)."""
    from apps.calepinage.selectors import parametres_de_societe
    from apps.calepinage.services.parametres_cles import SECTION_ELECTRIQUE_SOCIETE

    return parametres_de_societe(company).get(SECTION_ELECTRIQUE_SOCIETE) or {}


def _verdict_ratio(ratio, evaluation, conception, reglages):
    from apps.calepinage.services.ratio_devis import bornes_du_verdict, bornes_ratio, detail_ratio, juger_ratio
    from core.electrique.types import fr

    bornes = bornes_du_verdict(bornes_ratio(reglages=reglages), evaluation, conception)
    conforme = juger_ratio(ratio, bornes, reglages)
    return {'conforme': conforme, 'valeur': ratio, 'borne': bornes[0], 'borne_source': bornes[2],
            'detail': detail_ratio(fr(ratio, 2), conforme, bornes, valeur=ratio, reglages=reglages,
                                   conception=conception)}


def _verdict_capacite(onduleur, nombre, puissance_kwc):
    from core.electrique.onduleurs import capacite_publiee_hybride
    from core.electrique.types import fr

    capacite = capacite_publiee_hybride(onduleur, nombre)
    if capacite is None or puissance_kwc is None:
        return None
    conforme = puissance_kwc <= capacite + 1e-9
    return {'conforme': conforme, 'capacite_kwc': capacite, 'puissance_kwc': puissance_kwc,
            'detail': '%s kWc %s la capacité publiée de l\'onduleur hybride (%s kWc)' % (
                fr(puissance_kwc, 2), 'dans' if conforme else 'au-delà de', fr(capacite, 0))}


def _verdict_longueur(chaines):
    longueurs = [c.get('nb_modules') for c in chaines if c.get('nb_modules')]
    if not longueurs:
        return None
    conforme = all(c.get('conforme') is not False for c in chaines)
    return {'conforme': conforme, 'longueurs': longueurs, 'longueur': max(longueurs),
            'detail': 'chaînes de %s modules %s dans la fenêtre de tension de l\'onduleur' % (
                '/'.join(str(n) for n in sorted(set(longueurs))), 'toutes' if conforme else 'pas toutes')}


def verdicts_electriques(company, design, onduleurs, puissance_kwc):
    """ACAL2016 — ``{ratio_dc_ac, capacite_hybride, longueur_chaine}`` de l'option dont la
    conception électrique ``design`` porte l'onduleur (``onduleurs`` : ses lignes, forme
    ``valeurs.onduleurs``), ``None`` sans conception électrique. Chaque verdict =
    ``{conforme, …, detail}`` ou ``None`` quand il ne s'applique pas (onduleur réseau ou
    capacité non publiée pour la capacité ; aucune chaîne pour la longueur)."""
    if not design or not onduleurs:
        return None
    from apps.calepinage.services.ratio_devis import famille_de_l_onduleur

    fiche, produit = _onduleur_lu(company, onduleurs[0].get('produit'))
    role, famille_par_nom = famille_de_l_onduleur(produit)  # D-HYB-1 : la règle du calepinage
    materiel = (design.get('materiel') or {}).get('onduleur') or {}
    nombre = sum(int(o.get('quantite') or 0) for o in onduleurs) or 1
    # D-HYB-1 (lead 1742) — une pose jugée sur un onduleur absent des lignes de la conception
    # arrive sans désignation : le NOM du produit dit s'il est hybride, jamais « réseau » par défaut.
    # D-HYB-1 (fondateur 24/11/2026) — le RÔLE, puis le port batterie de la fiche, puis le nom.
    onduleur = SimpleNamespace(designation=(materiel.get('designation') or onduleurs[0].get('designation')
                                            or getattr(produit, 'nom', None)),
                               role=role, famille_par_nom=famille_par_nom,
                               bat_max_charge_kw=fiche.get('bat_max_charge_kw'),
                               bat_max_decharge_kw=fiche.get('bat_max_decharge_kw'),
                               dc_max_kwc=fiche.get('dc_max_kwc'))
    ac_kw = _nombre(materiel.get('ac_kw')) or _nombre(fiche.get('ac_kw')) or 0.0
    evaluation = SimpleNamespace(nombre=nombre, puissance_ac_kw=nombre * ac_kw)
    ratio = _nombre(design.get('ratio_dc_ac'))
    return {
        'ratio_dc_ac': (_verdict_ratio(ratio, evaluation, SimpleNamespace(entree=SimpleNamespace(onduleur=onduleur)),
                                       _reglages_electriques(company)) if ratio is not None else None),
        'capacite_hybride': _verdict_capacite(onduleur, nombre, _nombre(puissance_kwc)),
        'longueur_chaine': _verdict_longueur(design.get('chaines') or []),
    }


# ── ACAL2018 / ADEV149 — la pose du toit tracé, par la façade du calepinage ──

def pose_du_calepinage(company, calepinage_id):
    """``pose_servie`` de la façade (``{nb_panneaux, kwc, complete, a_la_main,
    empreinte_pose, manquants}``), ``None`` sans calepinage de la société."""
    from apps.calepinage.services.pose_pour_moteur import pose_servie

    return pose_servie(company, calepinage_id) if calepinage_id else None


class SimulationEnCours(AutoDevisError):
    """Relecture E6 (règle « jamais de simulation dans une requête ») — la pose doit être
    simulée et ne l'est pas encore : la simulation est mise en file, rien n'est rangé, le
    devis automatique répond 409 avec :data:`MESSAGE_SIMULATION_EN_COURS`."""


MESSAGE_SIMULATION_EN_COURS = 'La simulation de la pose est en cours : réessayez dans une minute.'
#: Qui peut simuler la pose dans CE contexte : une tâche, une commande (``simuler``) ;
#: l'utilisateur de la requête (``auteur``) qui met la simulation en file sinon.
_CONTEXTE_POSE = ContextVar('ventes_conception_contexte_de_pose', default=None)


@contextmanager
def contexte_de_pose(*, simuler=False, auteur=None):
    """``simuler=True`` : la tâche du moteur ou la commande — la simulation tourne ici ;
    sinon (requête web, défaut) la pose non simulée est mise en file au nom d'``auteur``."""
    jeton = _CONTEXTE_POSE.set({'simuler': simuler, 'auteur': auteur})
    try:
        yield
    finally:
        _CONTEXTE_POSE.reset(jeton)


def contexte_de_la_relance(auteur):
    """Le contexte d'une relance : celui de l'appelant s'il en a posé un (tâche, commande),
    sinon celui d'une REQUÊTE au nom d'``auteur`` (aucune simulation, mise en file)."""
    from contextlib import nullcontext
    return nullcontext() if _CONTEXTE_POSE.get() is not None else contexte_de_pose(auteur=auteur)


def productible_de_la_pose(company, calepinage_id, materiel):
    """Relecture E6 M1 — le productible posé SERVI du calepinage (contrat
    ``calepinage_productible_pose.json``, ``selectors_devis.productible_pose_du_calepinage``)
    quand son résultat rangé est celui de la pose ; une pose jamais simulée ou dont la
    simulation est périmée est simulée pour ``materiel`` dans une tâche
    (:func:`contexte_de_pose` ``simuler``), mise en file et dite
    (:class:`SimulationEnCours`) dans une requête. ``None`` sans calepinage."""
    from apps.calepinage.selectors_devis import productible_pose_du_calepinage
    from apps.ventes.coherence.registre import TOLERANCES
    from apps.ventes.selectors_calepinage import calepinage_de_societe

    calepinage = calepinage_de_societe(calepinage_id, company) if calepinage_id else None
    if calepinage is None:
        return None

    def lire():
        return productible_pose_du_calepinage(calepinage, tolerance_kwc_ratio=TOLERANCES['kwc_calepinage_ratio'])
    servi = lire()
    # Jamais simulée, ou simulation d'une AUTRE pose (``kwc_simule`` absent) ; un résultat
    # incomplet (pertes non saisies) n'est pas refait : la simulation n'y changerait rien.
    if servi is not None and not (servi.get('perime') and servi.get('kwc_simule') is None):
        return servi
    contexte = _CONTEXTE_POSE.get() or {}
    if contexte.get('simuler'):
        simuler_la_pose(company, calepinage_id, materiel)
        calepinage.refresh_from_db()
        return lire()
    if contexte.get('auteur') is not None:
        from apps.calepinage.services.simulation_auto import lancer_simulation_automatique
        lancer_simulation_automatique(calepinage, user=contexte['auteur'])
    raise SimulationEnCours(MESSAGE_SIMULATION_EN_COURS, field='calepinage')


def simuler_la_pose(company, calepinage_id, materiel):
    """La production de LA simulation de la pose pour le matériel du moteur
    (``{module, onduleur}`` : identifiants produit) ; ``None`` sans calepinage."""
    from apps.calepinage.services.pose_pour_moteur import simuler_pose
    from apps.ventes.selectors_calepinage import calepinage_de_societe

    calepinage = calepinage_de_societe(calepinage_id, company) if calepinage_id else None
    return simuler_pose(calepinage, materiel=materiel) if calepinage is not None else None


def production_du_plan_par_defaut(company, lead, kwc, produits, nb_panneaux=None):
    """ADEV154 / ACAL2026 — la production du PLAN PAR DÉFAUT d'un lead sans toit tracé
    (``calepinage/services/plan_par_defaut.py``, sans écriture) : ``kwc`` du moteur, son
    matériel (``{module, onduleur}`` : identifiants produit), le point du lead et sa pente
    déclarée (``Lead.inclinaison_deg``, sinon 30° dite) ; ``nb_panneaux`` : le compte de la
    conception, qui pose le plan à SA taille quand la fiche du module ne porte aucune
    puissance (correction d'ACAL2026). Une simulation refusée rend ``{refus: <motif
    nommé>}`` (aucun autre fichier de ventes n'importe le calepinage)."""
    from apps.calepinage.services.plan_par_defaut import simuler_plan_par_defaut
    from apps.calepinage.services.simulation import SimulationRefusee

    pente = getattr(lead, 'inclinaison_deg', None)
    try:
        return simuler_plan_par_defaut(company, None, None, kwc, lead_id=lead.pk, produits=produits,
                                       nb_panneaux=nb_panneaux,
                                       pente=float(pente) if pente is not None else None,
                                       type_installation=getattr(lead, 'type_installation', None),
                                       type_toiture=getattr(lead, 'type_toiture', None))
    except SimulationRefusee as refus:
        return {'refus': refus.motif or str(refus)}


#: ADEV155 — une fiche de module vide fait omettre des pertes : la production serait SURESTIMÉE.
CODES_FICHE_VIDE = ('fiche_module_incomplete', 'puissance_module_de_la_conception')
MESSAGE_PRODUCTION_PLAN = ('Production simulée sur un toit supposé (un seul pan, pente %s°, %s, sans ombre '
                           'proche : %s kWh/kWc) : tracer le toit au calepinage pour la production de la pose réelle.')


def productible_du_plan_par_defaut(company, lead, kwc, produits):
    """ADEV155 (D-ACAL-108, niveau 15 seulement) — ``(servi | None, suppositions, motif)`` :
    le plan par défaut de :func:`production_du_plan_par_defaut` (au kWc et au matériel du
    moteur) à la forme du productible servi d'une pose (kWh/kWc, pertes incluses,
    ``source`` = ``SOURCE_PLAN_PAR_DEFAUT``), lu par ``horaire/productible_pose.base_depuis_servi``
    comme celui d'une pose. ``kwc_simule`` absent : un rendement par kWc, le même pour les
    deux options du lead. Jamais servi (motif dit) : plan refusé, incomplet, ou fiche du
    module vide (pertes omises, production surestimée)."""
    from apps.ventes.horaire.productible_pose import SOURCE_PLAN_PAR_DEFAUT

    if not kwc:
        return None, [], 'puissance du moteur inconnue'
    plan = production_du_plan_par_defaut(company, lead, kwc, produits)
    if plan.get('refus'):
        return None, [], 'plan par défaut refusé : %s' % plan['refus']
    suppositions = list(plan.get('suppositions') or ())
    vides = [s for s in suppositions if s.get('code') in CODES_FICHE_VIDE]
    if vides:  # B1 (relecture lot 5) : toute étape omise faute de fiche, puissance portée ou non
        champs = [str(s['valeur']) for s in vides if s.get('code') == 'fiche_module_incomplete' and s.get('valeur')]
        return None, [], 'fiche technique du module incomplète : pertes non appliquées%s' % (
            ' (champ manquant : %s)' % ' ; '.join('« %s »' % c for c in champs) if champs else '')
    annuel, mensuel, kwc_plan = plan.get('production_annuelle'), plan.get('production_mensuelle'), plan.get('kwc')
    if (not plan.get('complete') or not annuel or not kwc_plan or not isinstance(mensuel, list) or len(mensuel) != 12
            or any(m is None for m in mensuel)):  # un mois absent : jamais servi comme zéro
        return None, [], 'plan par défaut incomplet'
    par_mois = [round(float(m) / float(kwc_plan), 1) for m in mensuel]
    # Le rendement annuel = la somme des 12 mois servis : celle que relit un brouillon C&I
    # (``horaire/productible_pose._base_du_plan_rangee``), une seule valeur de bout en bout.
    rendement = round(sum(par_mois), 1)
    azimut = float(plan.get('azimut_deg') or 180.0)
    suppositions.append({'code': 'production_plan_par_defaut', 'champ': 'calepinage', 'valeur': rendement,
                         'source': 'defaut', 'message': MESSAGE_PRODUCTION_PLAN % (
                             '{:g}'.format(float(plan.get('pente_deg') or 0)),
                             'plein sud' if azimut == 180.0 else 'azimut {:g}°'.format(azimut),
                             '{:g}'.format(rendement).replace('.', ','))})
    return {'perime': False, 'motif': '', 'source': SOURCE_PLAN_PAR_DEFAUT, 'kwc_simule': None,
            'kwh_kwc_annuel': rendement,
            'kwh_kwc_mensuel': par_mois,
            'complete': True, 'pertes_et_ombrage_inclus': True}, suppositions, ''


#: Reste d'ACAL2020 — l'origine du RELEVÉ collé à l'étape Consommation (``consumption.source``
#: du document, écrite par ``calepinage/services/consommation.py::proposer_consommation``).
ORIGINE_RELEVE = 'csv'


def consommation_du_calepinage(company, calepinage_id):
    """Reste d'ACAL2020 — le RELEVÉ collé au calepinage (``roof_layout.consumption`` dont la
    source est ``csv`` : la journée moyenne de 24 h du relevé) à la forme de la consommation
    imposée du moteur (``conception/consommation_imposee.py``) : ``{kwh_annuel, kwh_mensuels:
    None, source: 'releve'}`` (journée moyenne × 365, la convention de l'étape pour une courbe
    sans saisons) ; ``None`` sans calepinage de la société, sans relevé (factures, appareils,
    consommation du lead) ou sans courbe lisible de 24 valeurs."""
    from apps.ventes.selectors_calepinage import calepinage_de_societe

    calepinage = calepinage_de_societe(calepinage_id, company) if calepinage_id else None
    conso = ((getattr(calepinage, 'roof_layout', None) or {}).get('consumption') or {}) if calepinage else {}
    source = conso.get('source') if isinstance(conso, dict) and isinstance(conso.get('source'), dict) else {}
    courbe = [_nombre(v) for v in conso.get('courbe24') or []] if source.get('origine') == ORIGINE_RELEVE else []
    if len(courbe) != 24 or any(v is None or v < 0 for v in courbe) or not sum(courbe):
        return None
    return {'kwh_annuel': round(sum(courbe) * 365, 1), 'kwh_mensuels': None, 'source': 'releve'}


#: Relecture E6 B2 — une désignation que le catalogue de vente du moteur refuse.
CODE_DESIGNATION_HORS_CATALOGUE = 'designation_hors_catalogue'
MESSAGE_HORS_CATALOGUE = ('Le matériel désigné « %s » n\'est plus au catalogue de vente : la conception utilise le '
                          'matériel choisi par le moteur. Désignez un autre produit à l\'étape Électrique, ou '
                          'remettez celui-ci en vente dans Stock.')
#: Rôle de l'étape Électrique → (champ imposé du moteur, genre du vivier).
_ROLES_DESIGNES = (('module_produit', 'panneau_produit_id', 'panneau'),
                   ('onduleur_produit', 'onduleur_produit_id', 'onduleur'))


def _designations(company, calepinage_id, lu=None):
    """``(imposes, écartées)`` : les désignations que le vivier du moteur accepte (forme des
    champs imposés) et ``[{champ, nom}]`` de celles qu'il refuse (archivé, sans prix de
    vente, d'un autre genre, inconnu) — jamais imposées (relecture E6 B2)."""
    from apps.calepinage.services.electrique import entree_stockee
    from apps.calepinage.services.variantes import onduleur_designe_a_la_main
    from apps.ventes.selectors_calepinage import calepinage_de_societe

    calepinage = (lu if lu is not None and lu.pk == calepinage_id
                  else calepinage_de_societe(calepinage_id, company) if calepinage_id else None)
    entree = (entree_stockee(calepinage) or {}) if calepinage is not None else {}
    # Lot 8 — un onduleur « repris de l'original » (copie, ACAL1253) n'est pas imposé : seul ce que le
    # vendeur a désigné à la main l'est (lu par le calepinage, qui porte le marqueur).
    if entree.get('onduleur_produit') not in (None, '') and not onduleur_designe_a_la_main(calepinage):
        entree.pop('onduleur_produit')
    designes = [(role, cle, genre, entree[role]) for role, cle, genre in _ROLES_DESIGNES
                if entree.get(role) not in (None, '')]
    if not designes:
        return {}, []
    from apps.ventes.domain import resolution_catalogue as rc

    vivier = rc.vivier(company)
    imposes, ecartees = {}, []
    for role, cle, genre, produit_id in designes:
        if rc.resoudre_par_id(company, genre, produit_id, entrees=vivier).statut == rc.STATUT_UNIQUE:
            imposes[cle] = produit_id
        else:
            ecartees.append({'champ': role, 'nom': _nom_produit(company, produit_id)})
    return imposes, ecartees


def _nom_produit(company, produit_id):
    from apps.stock.selectors import get_produit_scoped
    try:
        produit = get_produit_scoped(company, int(produit_id)) if company is not None else None
    except (TypeError, ValueError):
        produit = None
    return getattr(produit, 'nom', None) or None


def calepinage_du_lead(company, lead, calepinage_id=None, toit=None):
    """``(calepinage_id, toit)`` — :func:`calepinage_et_toit_du_lead` sans l'objet lu."""
    return calepinage_et_toit_du_lead(company, lead, calepinage_id, toit)[:2]


def calepinage_et_toit_du_lead(company, lead, calepinage_id=None, toit=None):
    """Lane E6e (T4-X5-003) — ``(calepinage_id, toit)`` d'une relance du LEAD : ceux que
    l'appelant passe, sinon le calepinage OUVERT du lead (hors appel d'offres) et sa pose
    enregistrée (``layout_hash``) comme toit. LA résolution unique des entrées imposées
    d'un lead : quel que soit le déclencheur (fiche, lecture, devis, calepinage), la
    conception lit le même toit et les mêmes désignations. Sans calepinage : inchangés."""
    from types import SimpleNamespace

    if calepinage_id or lead is None or not getattr(lead, 'pk', None):
        return calepinage_id, toit, None
    from apps.calepinage.selectors import calepinage_ouvert_du_lead

    calepinage = calepinage_ouvert_du_lead(company, lead.pk)
    if calepinage is None or calepinage.appel_offre_id:
        return None, toit, None
    empreinte = (calepinage.layout_hash or '').strip()
    if toit is None and empreinte:
        toit = SimpleNamespace(empreinte=calepinage.layout_hash, plafond_panneaux=None)
    return calepinage.pk, toit, calepinage  # coût des requêtes : l'objet lu sert ses désignations


def designations_du_calepinage(company, calepinage_id, calepinage=None):
    """ACAL2013 — le module et l'onduleur DÉSIGNÉS À LA MAIN à l'étape Électrique du
    calepinage (entrée électrique stockée : ``module_produit``, ``onduleur_produit``), à la
    forme des champs imposés du moteur (``panneau_produit_id``, ``onduleur_produit_id``) ;
    ``{}`` sans désignation ou sans calepinage de la société. Relecture E6 B2 : seulement
    celles que le catalogue de vente du moteur accepte (les autres :
    :func:`designations_ecartees`)."""
    return _designations(company, calepinage_id, calepinage)[0]


def designations_ecartees(company, calepinage_id):
    """Relecture E6 B2 — les suppositions (forme du contrat) des désignations du calepinage
    que le catalogue de vente refuse : la conception garde le matériel du moteur et le DIT,
    le produit nommé (jamais son identifiant)."""
    return [{'code': CODE_DESIGNATION_HORS_CATALOGUE, 'champ': e['champ'], 'valeur': None, 'source': 'defaut',
             'message': (MESSAGE_HORS_CATALOGUE % e['nom'] if e['nom'] else
                         MESSAGE_HORS_CATALOGUE.replace('« %s »', "à l'étape Électrique"))}
            for e in _designations(company, calepinage_id)[1]]


# Cliquet ACAL1009 — portes minces pour le reste de ``ventes`` (pur ré-acheminement,
# lecture à l'appel : un ``mock.patch`` du module du calepinage reste vu).

def calepinage_lie_au_devis(devis_id, company):
    """Le calepinage du devis (``apps.calepinage.selectors.calepinage_du_devis``) —
    lu par ``domain/revision.py``."""
    from apps.calepinage.selectors import calepinage_du_devis

    return calepinage_du_devis(devis_id, company)


def relier_calepinage_au_devis_revise(ancien, nouveau, *, user=None):
    """LE service de re-liaison du calepinage à la V+1
    (``apps.calepinage.services.relier_au_devis_revise``) — appelé par
    ``domain/revision.py``."""
    from apps.calepinage import services as calepinage_services

    return calepinage_services.relier_au_devis_revise(ancien, nouveau, user=user)


def specs_module_du_calepinage(specs, nom):
    """La fiche électrique d'un module (``apps.calepinage.services.chaines.specs_module``)
    — lue par ``domain/etude_ci_module.py``."""
    from apps.calepinage.services.chaines import specs_module

    return specs_module(specs, nom)
