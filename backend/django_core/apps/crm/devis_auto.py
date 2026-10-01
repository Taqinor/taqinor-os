"""
Gating « devis automatique » — source de vérité UNIQUE côté serveur.

Selon le mode du lead (type_installation), certaines entrées sont requises
avant de pouvoir lancer le générateur de devis automatique :

  - Résidentiel (ou non renseigné) : facture hiver ; facture été UNIQUEMENT
    si le toggle « été différent » est actif (sinon la facture hiver vaut
    pour toute l'année) ;
  - Industriel / Commercial : consommation mensuelle (kWh) ;
  - Agricole (pompage) : puissance pompe (CV), HMT (m), débit souhaité (m³/h).

La même liste alimente le champ sérialisé `devis_auto` (UI) et l'endpoint
POST /crm/leads/<id>/devis-auto/ (règle serveur) — jamais deux logiques.
"""

# Modes regroupés (clés de Lead.TypeInstallation — scalaires, jamais une
# liste d'étapes du pipeline, qui vit dans STAGES.py).
_MODES_ETUDE = ('commercial', 'industriel')
_MODE_AGRICOLE = 'agricole'


def champs_requis(lead) -> list[list[str]]:
    """QJR600 (contrat ``devis_auto_pret.json``) — la règle STRUCTURÉE : une
    liste de groupes « l'un des » (noms de champs ``Lead``). Le devis
    automatique est prêt quand CHAQUE groupe a au moins un champ rempli —
    même sémantique du vide que :func:`champs_manquants` (0 = manquant)."""
    mode = lead.type_installation or 'residentiel'
    if mode == _MODE_AGRICOLE:
        return [['pompe_cv'], ['pompe_hmt_m'], ['pompe_debit_m3h']]
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
    'pompe_cv': 'pompe (CV)',
    'pompe_hmt_m': 'HMT',
    'pompe_debit_m3h': 'débit souhaité',
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
        if any(getattr(lead, champ, None) for champ in groupe):
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
