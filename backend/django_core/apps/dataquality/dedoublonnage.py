"""NTDATA17/19 — DÉTECTION de doublons : proposer, jamais fusionner.

CE QUE CE MODULE FAIT. Il regroupe des fiches qui désignent PROBABLEMENT la
même entité du monde réel (le même client saisi deux fois, le même fournisseur
sous deux orthographes) et rend des GROUPES CANDIDATS avec, pour chacun, les
CRITÈRES concordants et un score de confiance.

CE QU'IL NE FAIT JAMAIS. Il ne fusionne rien, ne modifie rien, ne supprime
rien. La fusion est une décision humaine (NTDATA18/19) : deux clients au même
numéro peuvent être un père et son fils.

LE SCORE N'EST PAS UNE MESURE MÉTIER. C'est la CONFIANCE DU DÉTECTEUR, et
elle vaut exactement le poids du critère le plus fort qui a rapproché les
fiches (:data:`POIDS_CRITERES`) — aucune arithmétique inventée par-dessus. Les
critères concordants sont TOUS rendus (``motifs``) : c'est eux, pas le score,
qui permettent de trancher.

LES CLÉS DE RAPPROCHEMENT VIENNENT DU CRM. Téléphone, email et nom sont
normalisés par ``apps.crm.selectors`` (``normalize_phone_key`` /
``normalize_email_key`` / ``normalize_name_key``) — les points d'entrée
cross-app sanctionnés. Aucune normalisation n'est réécrite ici : si le CRM
change sa règle de téléphone, la détection suit automatiquement.
"""
from __future__ import annotations

from difflib import SequenceMatcher

#: Poids = confiance du critère. Un identifiant légal (ICE) est plus sûr qu'un
#: téléphone (partagé en famille), lui-même plus sûr qu'un nom (homonymes).
POIDS_CRITERES = {
    'ice': 0.95,
    'telephone': 0.90,
    'email': 0.85,
    'nom': 0.60,
}

#: Similarité minimale entre deux noms NORMALISÉS pour les rapprocher.
SEUIL_NOM = 0.92

#: Longueur du préfixe de blocage pour la comparaison de noms. Sans blocage,
#: comparer tous les noms deux à deux serait quadratique (5 000 fiches = 12,5
#: millions de comparaisons) : on ne compare que des noms partageant leurs
#: premiers caractères, ce qui borne le coût sans manquer les variantes
#: d'orthographe en fin de mot (« belkacem » / « belkacim »).
PREFIXE_BLOC = 4


class _Unions:
    """Union-find minimal : relie les fiches en groupes transitifs.

    Deux fiches liées par le TÉLÉPHONE et deux autres liées par l'EMAIL
    forment UN seul groupe si elles partagent une fiche — c'est le
    comportement attendu d'une file de dédoublonnage (sinon la même fiche
    apparaîtrait dans deux propositions concurrentes).
    """

    def __init__(self):
        self.parent = {}

    def _racine(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def unir(self, a, b):
        ra, rb = self._racine(a), self._racine(b)
        if ra != rb:
            self.parent[rb] = ra

    def groupes(self):
        out = {}
        for element in self.parent:
            out.setdefault(self._racine(element), []).append(element)
        return [sorted(membres) for membres in out.values()
                if len(membres) > 1]


def _cles_exactes(lignes, champ, normaliseur):
    """``{clé normalisée: [ids]}`` — les clés vides sont ignorées."""
    index = {}
    for ligne in lignes:
        cle = normaliseur(ligne.get(champ))
        if not cle:
            continue
        index.setdefault(cle, []).append(ligne['id'])
    return {cle: ids for cle, ids in index.items() if len(ids) > 1}


def _paires_de_noms(lignes, normaliseur):
    """Paires d'ids dont les NOMS normalisés se ressemblent (blocage préfixe)."""
    blocs = {}
    for ligne in lignes:
        cle = normaliseur(ligne.get('nom'))
        if not cle:
            continue
        blocs.setdefault(cle[:PREFIXE_BLOC], []).append((ligne['id'], cle))
    paires = []
    for membres in blocs.values():
        for i in range(len(membres)):
            for j in range(i + 1, len(membres)):
                id_a, cle_a = membres[i]
                id_b, cle_b = membres[j]
                if cle_a == cle_b or SequenceMatcher(
                        None, cle_a, cle_b).ratio() >= SEUIL_NOM:
                    paires.append((id_a, id_b))
    return paires


def grouper_doublons(lignes, *, criteres, normaliseurs, libelle_champ='nom'):
    """Les GROUPES candidats d'un jeu de lignes.

    ``lignes`` — dicts portant au moins ``id`` et les champs des critères.
    ``criteres`` — sous-ensemble ordonné de :data:`POIDS_CRITERES` à appliquer
    (``'nom'`` déclenche la comparaison approchée, les autres une égalité de
    clé normalisée). ``normaliseurs`` — ``{critere: fonction}``.

    Renvoie une liste de dicts ``{ids, score, motifs, libelles}`` triée par
    score décroissant puis par premier id (rendu déterministe).
    """
    lignes = [ligne for ligne in lignes if ligne.get('id') is not None]
    unions = _Unions()
    motifs_par_paire = {}

    def _noter(ids, motif):
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                paire = tuple(sorted((ids[i], ids[j])))
                motifs_par_paire.setdefault(paire, set()).add(motif)
                unions.unir(*paire)

    for critere in criteres:
        normaliseur = normaliseurs.get(critere)
        if normaliseur is None:
            continue
        if critere == 'nom':
            for paire in _paires_de_noms(lignes, normaliseur):
                _noter(list(paire), 'nom')
            continue
        for _cle, ids in _cles_exactes(lignes, critere, normaliseur).items():
            _noter(ids, critere)

    par_id = {ligne['id']: ligne for ligne in lignes}
    groupes = []
    for membres in unions.groupes():
        motifs = set()
        for i in range(len(membres)):
            for j in range(i + 1, len(membres)):
                motifs |= motifs_par_paire.get(
                    tuple(sorted((membres[i], membres[j]))), set())
        if not motifs:
            continue
        score = max(POIDS_CRITERES[m] for m in motifs)
        groupes.append({
            'ids': membres,
            'score': round(score, 2),
            'motifs': sorted(motifs),
            'libelles': [str(par_id[i].get(libelle_champ) or '')
                         for i in membres],
        })
    groupes.sort(key=lambda g: (-g['score'], g['ids'][0]))
    return groupes
