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


def _fiche_onduleur(company, produit_id):
    """La fiche (bloc plat) de l'onduleur ``produit_id`` de ``company``, ``{}`` sinon."""
    from apps.stock.selectors import get_produit_scoped, specs_for_produit

    produit = get_produit_scoped(company, produit_id) if company is not None and produit_id else None
    return (specs_for_produit(produit) or {}) if produit is not None else {}


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
            'detail': detail_ratio(fr(ratio, 2), conforme, bornes, valeur=ratio, reglages=reglages)}


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
    fiche = _fiche_onduleur(company, onduleurs[0].get('produit'))
    materiel = (design.get('materiel') or {}).get('onduleur') or {}
    nombre = sum(int(o.get('quantite') or 0) for o in onduleurs) or 1
    onduleur = SimpleNamespace(designation=materiel.get('designation') or onduleurs[0].get('designation'),
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


def production_du_plan_par_defaut(company, lead, kwc, produits):
    """ADEV154 / ACAL2026 — la production du PLAN PAR DÉFAUT d'un lead sans toit tracé
    (``calepinage/services/plan_par_defaut.py``, sans écriture) : ``kwc`` du moteur, son
    matériel (``{module, onduleur}`` : identifiants produit), le point du lead et sa pente
    déclarée (``Lead.inclinaison_deg``, sinon 30° dite). Lève ``SimulationRefusee``."""
    from apps.calepinage.services.plan_par_defaut import simuler_plan_par_defaut

    pente = getattr(lead, 'inclinaison_deg', None)
    return simuler_plan_par_defaut(company, None, None, kwc, lead_id=lead.pk, produits=produits,
                                   pente=float(pente) if pente is not None else None)


#: Relecture E6 B2 — une désignation que le catalogue de vente du moteur refuse.
CODE_DESIGNATION_HORS_CATALOGUE = 'designation_hors_catalogue'
MESSAGE_HORS_CATALOGUE = ('Le matériel désigné « %s » n\'est plus au catalogue de vente : la conception utilise le '
                          'matériel choisi par le moteur. Désignez un autre produit à l\'étape Électrique, ou '
                          'remettez celui-ci en vente dans Stock.')
#: Rôle de l'étape Électrique → (champ imposé du moteur, genre du vivier).
_ROLES_DESIGNES = (('module_produit', 'panneau_produit_id', 'panneau'),
                   ('onduleur_produit', 'onduleur_produit_id', 'onduleur'))


def _designations(company, calepinage_id):
    """``(imposes, écartées)`` : les désignations que le vivier du moteur accepte (forme des
    champs imposés) et ``[{champ, nom}]`` de celles qu'il refuse (archivé, sans prix de
    vente, d'un autre genre, inconnu) — jamais imposées (relecture E6 B2)."""
    from apps.calepinage.services.electrique import entree_stockee
    from apps.ventes.selectors_calepinage import calepinage_de_societe

    calepinage = calepinage_de_societe(calepinage_id, company) if calepinage_id else None
    entree = (entree_stockee(calepinage) or {}) if calepinage is not None else {}
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
        produit = get_produit_scoped(company, int(produit_id))
    except (TypeError, ValueError):
        produit = None
    return getattr(produit, 'nom', None) or None


def designations_du_calepinage(company, calepinage_id):
    """ACAL2013 — le module et l'onduleur DÉSIGNÉS À LA MAIN à l'étape Électrique du
    calepinage (entrée électrique stockée : ``module_produit``, ``onduleur_produit``), à la
    forme des champs imposés du moteur (``panneau_produit_id``, ``onduleur_produit_id``) ;
    ``{}`` sans désignation ou sans calepinage de la société. Relecture E6 B2 : seulement
    celles que le catalogue de vente du moteur accepte (les autres :
    :func:`designations_ecartees`)."""
    return _designations(company, calepinage_id)[0]


def designations_ecartees(company, calepinage_id):
    """Relecture E6 B2 — les suppositions (forme du contrat) des désignations du calepinage
    que le catalogue de vente refuse : la conception garde le matériel du moteur et le DIT,
    le produit nommé (jamais son identifiant)."""
    return [{'code': CODE_DESIGNATION_HORS_CATALOGUE, 'champ': e['champ'], 'valeur': None, 'source': 'defaut',
             'message': (MESSAGE_HORS_CATALOGUE % e['nom'] if e['nom'] else
                         MESSAGE_HORS_CATALOGUE.replace('« %s »', "à l'étape Électrique"))}
            for e in _designations(company, calepinage_id)[1]]
