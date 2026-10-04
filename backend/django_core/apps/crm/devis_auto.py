"""
Gating « devis automatique » — source de vérité UNIQUE côté serveur.

Selon le mode du lead (type_installation), certaines entrées sont requises
avant de pouvoir lancer le générateur de devis automatique :

  - Résidentiel (ou non renseigné) : facture hiver ; facture été UNIQUEMENT
    si le toggle « été différent » est actif (sinon la facture hiver vaut
    pour toute l'année) ;
  - Industriel / Commercial : consommation mensuelle (kWh) ;
  - Agricole (pompage, AGR403) : [HMT OU niveau d'eau] ET [débit souhaité,
    besoin en eau (m³/jour) OU débit de la pompe actuelle — ce dernier ne
    comptant qu'avec ses heures, volume déclaré D-AGR-3]. Le CV ne compte
    plus : il décrit la pompe ACTUELLE (``pompe_actuelle_cv``).

La même liste alimente le champ sérialisé `devis_auto` (UI) et l'endpoint
POST /crm/leads/<id>/devis-auto/ (règle serveur) — jamais deux logiques.
"""

# Modes regroupés (clés de Lead.TypeInstallation — scalaires, jamais une
# liste d'étapes du pipeline, qui vit dans STAGES.py).
_MODES_ETUDE = ('commercial', 'industriel')
_MODE_AGRICOLE = 'agricole'

#: AGR403 — les groupes « l'un des » agricoles (groupes HYDRAULIQUES, lus
#: aussi par AGR530). ``pompe_actuelle_debit_m3h`` ne compte QUE si
#: ``pompage_heures_jour`` est renseigné (volume déclaré = débit actuel ×
#: heures actuelles, D-AGR-3 ; dérivé par AGR404).
GROUPES_HYDRAULIQUES_AGRICOLES = (
    ('pompe_hmt_m', 'niveau_statique_m'),
    ('pompe_debit_m3h', 'besoin_eau_m3j', 'pompe_actuelle_debit_m3h'),
)

#: Champ qui ne compte qu'accompagné d'un autre (sinon il vaut « vide »).
_COMPTE_SEULEMENT_AVEC = {'pompe_actuelle_debit_m3h': 'pompage_heures_jour'}


def _rempli(lead, champ):
    """Même sémantique du vide partout (0 = manquant), plus la règle AGR403 :
    un débit actuel sans ses heures ne fait pas un volume."""
    if not getattr(lead, champ, None):
        return False
    compagnon = _COMPTE_SEULEMENT_AVEC.get(champ)
    return not compagnon or bool(getattr(lead, compagnon, None))


def champs_requis(lead) -> list[list[str]]:
    """QJR600 (contrat ``devis_auto_pret.json``) — la règle STRUCTURÉE : une
    liste de groupes « l'un des » (noms de champs ``Lead``). Le devis
    automatique est prêt quand CHAQUE groupe a au moins un champ rempli —
    même sémantique du vide que :func:`champs_manquants` (0 = manquant)."""
    mode = lead.type_installation or 'residentiel'
    if mode == _MODE_AGRICOLE:
        return [list(groupe) for groupe in GROUPES_HYDRAULIQUES_AGRICOLES]
    if mode in _MODES_ETUDE:
        # CAD166 — conso éditable OU kWh du tunnel : l'un vaut l'autre.
        return [['conso_mensuelle_kwh', 'bill_kwh']]
    requis = [['facture_hiver']]
    if lead.ete_differente:
        requis.append(['facture_ete'])
    return requis


#: Libellé affiché d'un groupe manquant, indexé sur le PREMIER champ du
#: groupe (celui que la puce « manquant » vise). Libellés inchangés.
_LIBELLES = {
    # AGR403 — libellés du contrat ``devis_auto_pret.json``.
    'pompe_hmt_m': "HMT (m) ou niveau d'eau",
    'pompe_debit_m3h': ('Débit souhaité, besoin en eau (m³/jour) ou débit '
                        'de la pompe actuelle'),
    # ── CAD-M ── CAD166 — LE DOSSIER PRO ÉTAIT BLOQUÉ ALORS QUE LA DONNÉE
    # ÉTAIT LÀ. Le tunnel professionnel du site n'écrit que ``bill_kwh``
    # (archive web, lecture seule) ; ce gating, lui, n'interrogeait que
    # ``conso_mensuelle_kwh`` (le champ ÉDITABLE, saisi par la commerciale
    # ou écrit par l'OCR). Les deux ne fusionnent PAS — chacun garde son
    # rôle — mais l'un vaut l'autre pour décider si le devis automatique
    # peut partir (groupe « l'un des » de :func:`champs_requis`).
    'conso_mensuelle_kwh': 'consommation mensuelle (kWh)',
    # Résidentiel — comportement simulateur : la facture été n'est requise
    # QUE si elle diffère de l'hiver (toggle existant).
    'facture_hiver': 'facture hiver',
    'facture_ete': 'facture été',
}


def champs_manquants_detail(lead) -> list[dict]:
    """QJR600 — ``[{champ, label}]`` des groupes requis sans aucun champ
    rempli (``champ`` = premier champ du groupe, nom du champ ``Lead``)."""
    detail = []
    for groupe in champs_requis(lead):
        if any(_rempli(lead, champ) for champ in groupe):
            continue
        detail.append({'champ': groupe[0], 'label': _LIBELLES[groupe[0]]})
    return detail


def champs_manquants(lead) -> list[str]:
    """Champs requis manquants (libellés) pour un devis automatique, selon le
    mode du lead. QJR600 — dérivé de :func:`champs_manquants_detail` : UNE
    seule règle, :func:`champs_requis`."""
    return [entree['label'] for entree in champs_manquants_detail(lead)]


def message_manquants(manquants):
    return 'Manque : ' + ', '.join(manquants)


def visite_point_eau_avant_devis(lead):
    """AGR403 (D-AGR-4) — ``{requise, motifs}`` pour un lead AGRICOLE, None
    ailleurs.

    Requise quand le niveau d'eau OU le débit du forage est inconnu (D-AGR-4
    appliquée à la lettre). C'est une information : ``pret`` ne mesure que la
    complétude des données, les boutons manuels avertissent sans bloquer
    (patron CAD123) et la retenue du devis automatique serveur revient au
    moteur agricole (D1).
    """
    if (lead.type_installation or '') != _MODE_AGRICOLE:
        return None
    motifs = []
    if lead.niveau_statique_m is None:
        motifs.append("niveau d'eau du forage inconnu")
    if lead.debit_forage_m3h is None:
        motifs.append('débit du forage inconnu')
    return {'requise': bool(motifs), 'motifs': motifs}
