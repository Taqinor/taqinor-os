"""AOF134 — Note de calcul à bilans RECALCULÉS.

Pourquoi cette pièce est particulière
=====================================
Dans le dossier réel du 27/07, la note de calcul portait des bilans SAISIS :
un changement de batterie (BOS-G → BOS-B Pro-A3) a obligé à recalculer à la
main l'énergie installée, le nombre de packs, la tension de banc et la
couverture nocturne — et la note de synthèse annonçait encore 264 modules
quand la donnée en disait 314. **La pièce la plus lue était la plus fausse.**

Ce module ne saisit RIEN. Il ne fait que LIRE le contexte de dossier (AOF111)
et composer les bilans à partir de lui. Deux conséquences directes :

* un changement d'équipement ou de calepinage change les bilans **sans
  intervention** — il n'existe aucun endroit où retaper un chiffre ;
* une grandeur absente du contexte fait ÉCHOUER le rendu (``ValueError``)
  au lieu d'être inventée ou laissée à zéro. Un blanc est un défaut visible ;
  un zéro silencieux est un mensonge.

Contrat d'entrée (``contexte``)
-------------------------------
Le contexte est un dict GELÉ produit par ``fabrique.contexte.construire_contexte``
(AOF111). Ce module en consomme les clés suivantes — et **aucune autre** :

``empreinte``            str — SHA-256 du contexte, reportée sur la pièce.
``site.productible``     {``valeur``, ``unite``, ``ville``, ``source``, ``date``}
                         source UNIQUE (AOF113) ; sa provenance est CITÉE dans
                         la pièce, sinon deux notes de deux dossiers peuvent
                         diverger sans que personne ne sache pourquoi.
``batiments``            [{``code``, ``libelle``, ``kwc``, ``modules_engages``,
                         ``puissance_module_wc``}]
``derivations``          bloc produit par le registre de dérivations (AOF114) :
                         ``chaines``, ``onduleurs``, ``stockage``,
                         ``liaison_inter_sites``.
``cotes_a_confirmer``    [{``repere``, ``libelle``, ``batiment``}] — alimente la
                         section « à confirmer à l'exécution ».

**Ce module ne dérive AUCUNE grandeur électrique lui-même** (nombre de chaînes,
calibre d'onduleur, packs, tension, couverture nocturne) : c'est le registre
AOF114 qui les produit, ici on les MET EN PAGE. La seule arithmétique faite ici
est le bilan de production annuelle (kWc × productible), qui est le propos même
de la note et n'appartient à personne d'autre.

Étanchéité (ratchet AOF129)
---------------------------
La note est une pièce CLIENT : elle ne porte ni prix d'achat, ni coût de
revient, ni marge, ni « maximum posable » agrégé du site. Les clés de coût sont
refusées à l'entrée (``_CLES_INTERDITES``) plutôt que filtrées à la sortie —
une omission de filtre est silencieuse, un refus ne l'est pas.
"""
from __future__ import annotations

from decimal import Decimal

__all__ = [
    'CLES_INTERDITES',
    'construire_note_calcul',
    'rendre_note_calcul_html',
    'rendre_note_calcul',
]

GABARIT = 'ao/note_calcul.html'

#: Clés dont la seule PRÉSENCE dans un bloc destiné à la note est un défaut
#: d'étanchéité. Volontairement en dur ICI (c'est une règle, pas une donnée).
CLES_INTERDITES = (
    'prix_achat', 'cout_revient', 'cout_de_revient', 'marge', 'benefice',
    'benefice_net', 'coefficient', 'maximum_posable', 'max_posable',
    'maximum_site',
)


def _exiger(source, chemin):
    """Lit ``chemin`` (« a.b.c ») dans ``source`` ou lève — jamais de défaut.

    Un ``.get(..., 0)`` transformerait une donnée manquante en bilan faux et
    imprimé. On préfère un rendu qui refuse de sortir.
    """
    courant = source
    parcouru = []
    for cle in chemin.split('.'):
        parcouru.append(cle)
        if not isinstance(courant, dict) or cle not in courant:
            raise ValueError(
                "Note de calcul : la grandeur « {} » est absente du contexte "
                "de dossier. Elle doit être DÉRIVÉE (AOF114/AOF113), jamais "
                "saisie dans la pièce.".format('.'.join(parcouru))
            )
        courant = courant[cle]
    if courant is None:
        raise ValueError(
            "Note de calcul : la grandeur « {} » vaut None dans le contexte ; "
            "un bilan ne se rend pas à partir d'une valeur inconnue.".format(
                chemin)
        )
    return courant


def _verifier_etancheite(contexte):
    """Refuse un contexte qui charrie une grandeur d'économie directeur."""
    trouves = []

    def _descendre(noeud, chemin):
        if isinstance(noeud, dict):
            for cle, valeur in noeud.items():
                normalisee = str(cle).lower()
                if any(interdite in normalisee
                       for interdite in CLES_INTERDITES):
                    trouves.append('.'.join(filter(None, [chemin, str(cle)])))
                _descendre(valeur, '.'.join(filter(None, [chemin, str(cle)])))
        elif isinstance(noeud, (list, tuple)):
            for index, valeur in enumerate(noeud):
                _descendre(valeur, '{}[{}]'.format(chemin, index))

    _descendre(contexte, '')
    if trouves:
        raise ValueError(
            "Note de calcul (pièce CLIENT) : le contexte porte des grandeurs "
            "réservées au directeur — {}. Elles ne franchissent jamais la "
            "fabrique documentaire.".format(', '.join(sorted(trouves)))
        )


def _decimal(valeur):
    return Decimal(str(valeur))


def construire_note_calcul(contexte):
    """Compose les BILANS de la note à partir du seul contexte de dossier.

    Renvoie un dict prêt à rendre. Aucune valeur n'y est écrite en dur : tout
    provient de ``contexte`` ou d'un produit de deux de ses grandeurs.
    """
    if not isinstance(contexte, dict):
        raise ValueError("Le contexte de dossier doit être un dict gelé.")
    _verifier_etancheite(contexte)

    productible = {
        'valeur': _decimal(_exiger(contexte, 'site.productible.valeur')),
        'unite': _exiger(contexte, 'site.productible.unite'),
        'ville': _exiger(contexte, 'site.productible.ville'),
        'source': _exiger(contexte, 'site.productible.source'),
        'date': _exiger(contexte, 'site.productible.date'),
    }

    batiments = _exiger(contexte, 'batiments')
    if not batiments:
        raise ValueError(
            "Note de calcul : aucun bâtiment dans le contexte — il n'y a "
            "aucun bilan à établir.")

    lignes = []
    total_kwc = Decimal('0')
    total_modules = 0
    total_production = Decimal('0')
    for batiment in batiments:
        kwc = _decimal(_exiger(batiment, 'kwc'))
        modules = int(_exiger(batiment, 'modules_engages'))
        puissance_module = _decimal(_exiger(batiment, 'puissance_module_wc'))
        production = kwc * productible['valeur']
        lignes.append({
            'code': _exiger(batiment, 'code'),
            'libelle': _exiger(batiment, 'libelle'),
            'kwc': kwc,
            'modules': modules,
            'puissance_module_wc': puissance_module,
            'production_annuelle_kwh': production,
        })
        total_kwc += kwc
        total_modules += modules
        total_production += production

    derivations = _exiger(contexte, 'derivations')
    note = {
        'empreinte': _exiger(contexte, 'empreinte'),
        'productible': productible,
        'batiments': lignes,
        'total': {
            'kwc': total_kwc,
            'modules': total_modules,
            'production_annuelle_kwh': total_production,
        },
        'chaines': _exiger(derivations, 'chaines'),
        'onduleurs': _exiger(derivations, 'onduleurs'),
        'stockage': _exiger(derivations, 'stockage'),
        'liaison_inter_sites': _exiger(derivations, 'liaison_inter_sites'),
        'a_confirmer': list(contexte.get('cotes_a_confirmer') or []),
    }
    # Une hypothèse « à confirmer à l'exécution » DOIT être signalée : une cote
    # au statut A_CONFIRMER qui ne remonterait pas ici serait une hypothèse
    # invisible dans une pièce contractuelle.
    note['mention_a_confirmer'] = bool(note['a_confirmer'])
    return note


def rendre_note_calcul_html(contexte, *, identite=None):
    """Rend le gabarit HTML de la note (sans WeasyPrint) — utile aux tests."""
    from django.template.loader import render_to_string

    return render_to_string(GABARIT, {
        'note': construire_note_calcul(contexte),
        'identite': identite or (contexte.get('identite') or {}),
        'marche': contexte.get('marche') or {},
    })


def rendre_note_calcul(contexte, *, company=None, identite=None):
    """Rend la note en PDF via ``core.pdf.render_pdf`` (ARC11).

    Jamais un import direct de WeasyPrint : ``check_platform.py`` refuserait le
    fichier, et surtout la plomberie PDF n'a pas à être re-codée par pièce.
    """
    from core.pdf import render_pdf

    return render_pdf(html=rendre_note_calcul_html(contexte,
                                                   identite=identite),
                      company=company)
