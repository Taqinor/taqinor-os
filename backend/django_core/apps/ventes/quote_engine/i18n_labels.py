"""NTI18N5 — libellés STRUCTURELS du document client rendu par le moteur
``/proposal`` (règle #4 : ce moteur est le seul chemin PDF devis client, et il
ne fait que RENDRE).

CE QUE CE MODULE CONTIENT — et seulement ça : les mots que le GABARIT écrit
lui-même (en-têtes de colonnes, chaîne des totaux, libellés des conditions de
paiement, « Réf. »). Trois langues : fr / en / ar.

CE QU'IL NE CONTIENT PAS, ET NE CONTIENDRA JAMAIS :
  * les DONNÉES du devis — désignations produit, marques, notes de TVA, textes
    de validité éditables par la société, ligne légale de l'entreprise. Ce sont
    des données réelles saisies par un humain : un moteur de rendu ne les
    traduit pas, il les imprime telles quelles (la traduction du contenu saisi
    est le périmètre de YHARD4). Une « mention légale » appartient donc à
    l'entreprise, pas à ce dictionnaire ;
  * le moindre CHIFFRE, ni le moindre format de montant. Les libellés reçoivent
    les nombres déjà formatés par les utilitaires du moteur ; ce module n'en
    fabrique, n'en arrondit et n'en reformate aucun.

REPLI : toujours le FRANÇAIS, jamais une clé brute (un client ne doit jamais
lire ``total_ttc`` dans son devis). Une langue inconnue, vide ou ``None`` rend
le document français d'aujourd'hui, au caractère près. Une clé ABSENTE du
catalogue lève ``KeyError`` : c'est une faute de frappe du gabarit, qui doit
échouer bruyamment au test plutôt qu'imprimer une chaîne vide ou un nom de
variable sur un document client.

VALEURS PRÊTES POUR LE HTML. Le gabarit les interpole directement dans le HTML
envoyé à WeasyPrint, donc les valeurs FRANÇAISES gardent EXACTEMENT l'écriture
qu'elles avaient dans le gabarit, entités numériques comprises
(``D&#233;signation``) : un devis français reste ainsi octet pour octet celui
d'hier. L'anglais est en ASCII pur et l'arabe en UTF-8 (le gabarit déclare
``<meta charset="UTF-8">`` et le HTML est écrit en UTF-8).
"""
from __future__ import annotations

#: Langues de sortie possibles d'un document — mêmes trois langues que le cadre
#: i18n du produit (``apps.parametres.i18n_resolver.LANGUES_SUPPORTEES``).
LANGUES = ('fr', 'en', 'ar')

#: Repli de tout dernier recours : le comportement historique du moteur.
LANGUE_DE_REPLI = 'fr'

#: Langues écrites de droite à gauche.
LANGUES_RTL = ('ar',)

#: Catalogue par CLÉ (et non par langue) : impossible d'ajouter un libellé
#: arabe sans son équivalent français, donc impossible de construire un repli
#: qui n'existe pas. Un test vérifie que chaque clé porte les trois langues.
LIBELLES = {
    # ── Bloc client ─────────────────────────────────────────────────────────
    'client': {
        'fr': 'Client',
        'en': 'Client',
        'ar': 'العميل',
    },
    # ── En-têtes de colonnes du tableau d'équipements ───────────────────────
    'designation': {
        'fr': 'D&#233;signation',
        'en': 'Description',
        'ar': 'البيان',
    },
    'marque': {
        'fr': 'Marque',
        'en': 'Brand',
        'ar': 'العلامة',
    },
    'qte': {
        'fr': 'Qt&#233;',
        'en': 'Qty',
        'ar': 'الكمية',
    },
    'pu_ht': {
        'fr': 'P.U. HT',
        'en': 'Unit price excl. VAT',
        'ar': 'سعر الوحدة (خ.ض)',
    },
    # Colonne étroite ET lignes de totaux : l'abréviation est la forme lisible
    # dans les deux (« ض.ق.م » = الضريبة على القيمة المضافة).
    'tva': {
        'fr': 'TVA',
        'en': 'VAT',
        'ar': 'ض.ق.م',
    },
    'total_ht': {
        'fr': 'Total HT',
        'en': 'Total excl. VAT',
        'ar': 'المجموع (خ.ض)',
    },
    # ── Chaîne des totaux ───────────────────────────────────────────────────
    'sous_total_ht': {
        'fr': 'Sous-total HT',
        'en': 'Subtotal excl. VAT',
        'ar': 'المجموع الفرعي (خ.ض)',
    },
    'remise': {
        'fr': 'Remise',
        'en': 'Discount',
        'ar': 'الخصم',
    },
    'total_ttc': {
        'fr': 'Total TTC',
        'en': 'Total incl. VAT',
        'ar': 'المجموع شامل الضريبة',
    },
    # ── Conditions de paiement ──────────────────────────────────────────────
    'conditions_paiement': {
        'fr': 'Conditions de paiement',
        'en': 'Payment terms',
        'ar': 'شروط الدفع',
    },
    'acompte': {
        'fr': 'Acompte',
        'en': 'Down payment',
        'ar': 'الدفعة المقدمة',
    },
    'a_la_reception_materiel': {
        'fr': '&#224; la r&#233;ception du mat&#233;riel',
        'en': 'on delivery of the equipment',
        'ar': 'عند استلام المعدات',
    },
    'apres_mise_en_marche': {
        'fr': 'apr&#232;s mise en marche',
        'en': 'after commissioning',
        'ar': 'بعد التشغيل',
    },
    # ── Pied de page ────────────────────────────────────────────────────────
    'reference': {
        'fr': 'R&#233;f.',
        'en': 'Ref.',
        'ar': 'المرجع',
    },
}


def normaliser(langue) -> str:
    """Langue de sortie utilisable : une des trois du cadre, sinon le FR.

    Défense en profondeur : une valeur inconnue venue d'un appelant (ou d'une
    charge utile bricolée) ne traverse jamais ce module autrement qu'en repli
    français.
    """
    return langue if langue in LANGUES else LANGUE_DE_REPLI


def libelle(cle: str, langue=None) -> str:
    """Libellé structurel ``cle`` dans ``langue`` (repli FR).

    Lève ``KeyError`` sur une clé absente du catalogue : le gabarit s'est
    trompé de nom, et cela doit casser au test — jamais imprimer un nom de
    variable ou un blanc sur un document client.
    """
    try:
        traductions = LIBELLES[cle]
    except KeyError:
        raise KeyError(
            f"i18n_labels: libellé inconnu {cle!r} — ajouter la clé au "
            f"catalogue (les trois langues) avant de l'appeler dans un gabarit"
        ) from None
    return traductions.get(normaliser(langue)) or traductions[LANGUE_DE_REPLI]


def libelles(langue=None) -> dict:
    """Toute la table résolue pour ``langue`` (chaque clé, repli FR appliqué).

    C'est la forme que le builder publie dans sa charge utile : le gabarit lit
    un dictionnaire plat, sans jamais refaire de résolution de langue.
    """
    active = normaliser(langue)
    return {cle: libelle(cle, active) for cle in LIBELLES}


def est_rtl(langue=None) -> bool:
    """Vrai si ``langue`` s'écrit de droite à gauche."""
    return normaliser(langue) in LANGUES_RTL


def direction(langue=None) -> str:
    """``'rtl'`` ou ``'ltr'`` — la valeur CSS/HTML ``dir`` du document."""
    return 'rtl' if est_rtl(langue) else 'ltr'
