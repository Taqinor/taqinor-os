"""AOF142 — rapport de bascule : ce qui a changé ET ce qui aurait dû changer.

Le défaut réel qu'il faut attraper
==================================
Dans le dossier du 27/07, la bascule de batterie a bien fait descendre le
montant du bordereau (4 166 600 HT / 4 999 920 TTC), mais le Word « À REMPLIR
PAR ACCORDIA » disait toujours, dans une parenthèse de justification,
« batteries 2 800 DH HT/kWh » alors que le bordereau final était à 2 600.
**Le montant a été cascadé, sa JUSTIFICATION non.**

Un rapport qui ne liste que les emplacements MODIFIÉS ne voit pas ce défaut :
la parenthèse n'a pas changé, c'est précisément le problème. Ce module produit
donc deux listes :

* ``modifies``  — les emplacements que la bascule a effectivement touchés ;
* ``suspects``  — les textes libres qui portent ENCORE l'ancienne référence ou
  l'ancien prix. Un suspect n'est pas une certitude : c'est un endroit à
  regarder, cité avec son extrait, sa position et ce qui l'a déclenché.

Ce module est PUR : il travaille sur des chaînes et des dicts, jamais sur
l'ORM. Il ne modifie rien — il constate. L'application atomique de la bascule
est le rôle de ``services.basculer_equipement`` (AOF141).

Contrat d'entrée
----------------
``ancien`` / ``nouveau`` : ``{'designation', 'reference', 'marque',
'prix_unitaire', 'unite', 'caracteristiques': {...}}``.
``textes`` : ``[{'emplacement': 'memoire §4.2', 'texte': '…'}]`` — n'importe
quelle source de texte libre du dossier (mémoire, note, annexe, commentaire).
"""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

__all__ = [
    'normaliser',
    'nombres_du_texte',
    'plan_bascule',
    'emplacements_suspects',
    'rapport_bascule',
]

#: Espaces utilisés comme séparateurs de milliers en typographie française :
#: espace fine insécable (U+202F — celle de `core/formats_fr.py`),
#: insécable (U+00A0), fine (U+2009) et espace simple. Écrites en
#: ÉCHAPPEMENTS : un caractère invisible recopié dans le source est
#: indébogable — et c'est exactement ce genre de détail qui fait rater
#: un « 2 800 » écrit avec une espace fine.
ESPACES = '\u202f\u00a0\u2009 '

_MOTIF_NOMBRE = re.compile(
    r'\d{1,3}(?:[' + ESPACES + r'.]\d{3})+(?:,\d+)?'
    r'|\d+(?:,\d+)?'
)


def normaliser(texte):
    """Minuscules, sans accent, ponctuation réduite — pour comparer des refs.

    Une référence produit s'écrit « BOS-G », « BOS G » ou « bos-g » selon la
    pièce ; comparer les chaînes brutes raterait deux occurrences sur trois.
    """
    if texte is None:
        return ''
    sans_accent = unicodedata.normalize('NFKD', str(texte))
    sans_accent = ''.join(c for c in sans_accent
                          if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', sans_accent.lower()).strip()


def nombres_du_texte(texte):
    """Renvoie ``[(valeur Decimal, extrait brut, position)]``.

    Le séparateur de milliers français (espace fine, insécable ou point) est
    absorbé, la virgule décimale est convertie. Sans cette normalisation,
    « 2 800 » et « 2800 » seraient deux nombres différents et le contrôle
    passerait à côté du défaut qu'il existe pour trouver.
    """
    trouves = []
    for occurrence in _MOTIF_NOMBRE.finditer(str(texte or '')):
        brut = occurrence.group(0)
        nettoye = brut
        for espace in ESPACES:
            nettoye = nettoye.replace(espace, '')
        nettoye = nettoye.replace('.', '').replace(',', '.')
        try:
            valeur = Decimal(nettoye)
        except (InvalidOperation, ValueError):
            continue
        trouves.append((valeur, brut, occurrence.start()))
    return trouves


def plan_bascule(ancien, nouveau, *, emplacements=()):
    """PLAN de la bascule : ce qui DOIT changer, poste par poste.

    Livré ici (module pur) plutôt que dans le service ORM parce que c'est la
    partie vérifiable : le service se contente ensuite de l'appliquer en UNE
    transaction. Le plan couvre les six familles de la bascule réelle —
    désignation, prix, caractéristiques, grandeurs dérivées, lignes de
    bordereau, fiches annexées.
    """
    changements = []
    for champ in ('designation', 'reference', 'marque', 'prix_unitaire',
                  'unite'):
        avant = (ancien or {}).get(champ)
        apres = (nouveau or {}).get(champ)
        if avant != apres:
            changements.append({'nature': 'champ', 'champ': champ,
                                'avant': avant, 'apres': apres})
    caracteristiques_avant = (ancien or {}).get('caracteristiques') or {}
    caracteristiques_apres = (nouveau or {}).get('caracteristiques') or {}
    for cle in sorted(set(caracteristiques_avant) | set(caracteristiques_apres)):
        avant = caracteristiques_avant.get(cle)
        apres = caracteristiques_apres.get(cle)
        if avant != apres:
            changements.append({'nature': 'caracteristique', 'champ': cle,
                                'avant': avant, 'apres': apres})
    for emplacement in emplacements or ():
        changements.append({'nature': 'emplacement',
                            'emplacement': emplacement})
    changements.append({'nature': 'annexe', 'retirer': (ancien or {}).get(
        'reference'), 'ajouter': (nouveau or {}).get('reference')})
    return changements


def emplacements_suspects(textes, ancien, nouveau, *, extrait=70):
    """Textes libres portant ENCORE l'ancienne référence ou l'ancien prix.

    Un emplacement est suspect si :
      * la référence ou la désignation de l'ANCIEN équipement y apparaît,
        alors qu'elle ne devrait plus exister dans un objet actif ;
      * l'ANCIEN prix unitaire y apparaît alors que le nouveau ne s'y trouve
        pas — c'est la signature exacte du défaut « 2 800 vs 2 600 » : une
        justification restée en arrière de son propre montant.
    """
    suspects = []
    ancien_prix = (ancien or {}).get('prix_unitaire')
    nouveau_prix = (nouveau or {}).get('prix_unitaire')
    # Un jeton PARTAGÉ avec le nouvel équipement (typiquement la marque, qui
    # ne change pas dans une bascule de gamme) ne prouve rien : le retenir
    # rendrait suspect tout texte parlant du MATÉRIEL RETENU. Un détecteur
    # bruyant est désactivé en trois dossiers.
    empreinte_nouveau = ' '.join(
        normaliser((nouveau or {}).get(champ))
        for champ in ('reference', 'designation', 'marque')
    )
    jetons = []
    for champ in ('reference', 'designation', 'marque'):
        jeton = normaliser((ancien or {}).get(champ))
        if jeton and jeton not in empreinte_nouveau:
            jetons.append((champ, jeton))
    for entree in textes or ():
        texte = str(entree.get('texte') or '')
        emplacement = entree.get('emplacement') or ''
        normalise = normaliser(texte)
        for champ, jeton in jetons:
            position = normalise.find(jeton)
            if position >= 0:
                suspects.append({
                    'emplacement': emplacement,
                    'motif': 'ancienne_reference',
                    'champ': champ,
                    'valeur': (ancien or {}).get(champ),
                    'extrait': texte[:extrait].strip(),
                })
                break
        if ancien_prix is None:
            continue
        valeurs = [valeur for valeur, _brut, _pos in nombres_du_texte(texte)]
        if Decimal(str(ancien_prix)) in valeurs:
            if nouveau_prix is None or \
                    Decimal(str(nouveau_prix)) not in valeurs:
                suspects.append({
                    'emplacement': emplacement,
                    'motif': 'ancien_prix',
                    'champ': 'prix_unitaire',
                    'valeur': ancien_prix,
                    'attendu': nouveau_prix,
                    'extrait': texte[:extrait].strip(),
                })
    return suspects


def rapport_bascule(ancien, nouveau, *, emplacements_modifies=(), textes=()):
    """Rapport complet : modifiés + suspects + verdict.

    ``bloquant`` est vrai dès qu'un suspect subsiste : une bascule qui laisse
    une justification en arrière n'est pas terminée, même si tous les montants
    sont justes.
    """
    suspects = emplacements_suspects(textes, ancien, nouveau)
    return {
        'ancien': dict(ancien or {}),
        'nouveau': dict(nouveau or {}),
        'plan': plan_bascule(ancien, nouveau,
                             emplacements=emplacements_modifies),
        'modifies': list(emplacements_modifies or ()),
        'suspects': suspects,
        'bloquant': bool(suspects),
    }
