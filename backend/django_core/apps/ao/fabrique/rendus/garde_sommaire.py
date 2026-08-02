"""AOF139 — page de garde, sommaire et bordereau des pièces.

Le sommaire est DÉRIVÉ, jamais rédigé
=====================================
Dans le dossier réel du 27/07, le sommaire était une liste tapée à la main :
ajouter une planche obligeait à se souvenir de la renuméroter, et un
« LISEZ-MOI » figé décrivait un pack qui avait déjà changé. Ici le sommaire
est une PROJECTION du manifeste du pack : une pièce ajoutée au manifeste
apparaît au sommaire sans qu'on touche à quoi que ce soit, et la numérotation
est recalculée à chaque rendu.

Ce qui n'entre PAS dans le sommaire remis
-----------------------------------------
Le filtre est structurel, pas une vigilance : seules les pièces de visibilité
``client`` sont listées. Une pièce ``interne`` ou ``directeur`` (le classeur de
rentabilité, par exemple) ne peut pas apparaître même si l'appelant la fournit
explicitement dans le manifeste — c'est la même discipline que l'exclusion du
ZIP de dépôt (AOF151). Demander à un opérateur de « penser à retirer » la
pièce directeur avant impression est exactement le mécanisme qui échoue.

Marque blanche
--------------
Quand ``identite.marque_blanche`` est vrai, la page de garde porte le
SOUMISSIONNAIRE (le partenaire qui dépose) et le bureau d'exécution n'apparaît
nulle part — ni en raison sociale, ni en ICE/IF/RC, ni en mention de pied.
Le cas réel : un dossier déposé par ACCORDIA TECH.

Contrat d'entrée
----------------
``contexte``   dict de dossier (AOF111) : ``identite``, ``marche``, ``dates``.
``manifeste``  liste de pièces ``{'code', 'libelle', 'ordre', 'visibilite',
               'format', 'obligatoire', 'presente', 'empreinte', 'pages'}`` —
               la forme du manifeste de pack (AOF116/AOF150), consommée telle
               quelle. Ce module ne décide d'aucun contenu, il met en ordre.
"""
from __future__ import annotations

__all__ = [
    'VISIBILITE_CLIENT',
    'VISIBILITES_EXCLUES',
    'MOTS_INTERDITS',
    'identite_de_garde',
    'construire_sommaire',
    'construire_bordereau_pieces',
    'rendre_page_garde_html',
    'rendre_page_garde',
]

GABARIT = 'ao/page_garde.html'

VISIBILITE_CLIENT = 'client'
VISIBILITES_EXCLUES = ('interne', 'directeur')

#: Nombre d'exemplaires papier prévus au dépôt (règle de la consultation, pas
#: une donnée de dossier) et format des planches.
EXEMPLAIRES = 2
FORMAT_PLANCHE = 'A3'
FORMAT_CORPS = 'A4'

MOTS_INTERDITS = (
    "prix d'achat", 'coût de revient', 'cout de revient', 'marge',
    'bénéfice', 'benefice', 'maximum posable',
)


def identite_de_garde(contexte):
    """Identité à imprimer en garde — JAMAIS le bureau en marque blanche.

    Lève si la marque blanche est active et qu'aucun soumissionnaire n'est
    renseigné : imprimer le bureau « par défaut » serait précisément la fuite
    que la marque blanche existe pour empêcher.
    """
    identite = (contexte or {}).get('identite') or {}
    soumissionnaire = identite.get('soumissionnaire') or {}
    if not identite.get('marque_blanche'):
        return dict(soumissionnaire or identite.get('bureau_execution') or {})
    if not soumissionnaire.get('raison_sociale'):
        raise ValueError(
            "Marque blanche active mais aucun soumissionnaire renseigné : la "
            "page de garde ne peut pas se rabattre sur le bureau d'exécution.")
    return dict(soumissionnaire)


def _verifier_etancheite_garde(identite, contexte):
    """En marque blanche, le bureau ne doit apparaître NULLE PART."""
    racine = (contexte or {}).get('identite') or {}
    if not racine.get('marque_blanche'):
        return
    bureau = (racine.get('bureau_execution') or {}).get('raison_sociale')
    if bureau and bureau in ' '.join(str(v) for v in identite.values()):
        raise ValueError(
            "Marque blanche : le bureau d'exécution « {} » apparaît dans "
            "l'identité de garde.".format(bureau))


def construire_sommaire(manifeste):
    """Sommaire NUMÉROTÉ dérivé du manifeste — client uniquement.

    Renvoie ``(entrees, exclues)`` : ``exclues`` nomme les pièces écartées et
    leur visibilité, pour que l'exclusion soit VISIBLE au contrôle interne et
    non silencieuse.
    """
    entrees = []
    exclues = []
    pieces = sorted(
        list(manifeste or []),
        key=lambda p: (p.get('ordre') if p.get('ordre') is not None else 0,
                       str(p.get('code') or '')),
    )
    numero = 0
    for piece in pieces:
        visibilite = str(piece.get('visibilite') or VISIBILITE_CLIENT)
        if visibilite != VISIBILITE_CLIENT:
            exclues.append({'code': piece.get('code'),
                            'libelle': piece.get('libelle'),
                            'visibilite': visibilite})
            continue
        numero += 1
        entrees.append({
            'numero': numero,
            'code': piece.get('code'),
            'libelle': piece.get('libelle'),
            'format': piece.get('format') or '',
            'obligatoire': bool(piece.get('obligatoire')),
            'presente': bool(piece.get('presente')),
            'pages': piece.get('pages'),
        })
    return entrees, exclues


def construire_bordereau_pieces(manifeste):
    """Bordereau des pièces : état + empreinte de chaque pièce remise.

    L'empreinte est ce qui rend le bordereau opposable : sans elle, deux
    versions d'une même pièce sont indiscernables sur le papier — c'est
    exactement le défaut « deux bordereaux homonymes divergents » de la
    session réelle.
    """
    entrees, _ = construire_sommaire(manifeste)
    par_code = {str(p.get('code')): p for p in (manifeste or [])}
    lignes = []
    for entree in entrees:
        piece = par_code.get(str(entree['code']), {})
        empreinte = piece.get('empreinte') or ''
        lignes.append({
            'numero': entree['numero'],
            'code': entree['code'],
            'libelle': entree['libelle'],
            'format': entree['format'],
            'etat': ('présente' if entree['presente']
                     else ('MANQUANTE' if entree['obligatoire']
                           else 'non fournie')),
            'obligatoire': entree['obligatoire'],
            'empreinte': empreinte,
            'empreinte_courte': empreinte[:8],
        })
    return lignes


def rendre_page_garde_html(contexte, manifeste):
    """Rend page de garde + sommaire + bordereau des pièces en un seul HTML."""
    from django.template.loader import render_to_string

    identite = identite_de_garde(contexte)
    _verifier_etancheite_garde(identite, contexte)
    sommaire, _exclues = construire_sommaire(manifeste)
    # `_exclues` n'entre JAMAIS dans le contexte de rendu : nommer au dos du
    # dossier les pièces internes et directeur qu'on a retirées reviendrait à
    # les divulguer par la porte de service.
    lignes = construire_bordereau_pieces(manifeste)
    texte = ' '.join(
        str(ligne.get('libelle') or '') for ligne in lignes).lower()
    fautes = [mot for mot in MOTS_INTERDITS if mot in texte]
    if fautes:
        raise ValueError(
            "Sommaire remis au maître d'ouvrage : libellés réservés au "
            "directeur — {}.".format(', '.join(fautes)))
    return render_to_string(GABARIT, {
        'identite': identite,
        'marche': (contexte or {}).get('marche') or {},
        'dates': (contexte or {}).get('dates') or {},
        'sommaire': sommaire,
        'pieces': lignes,
        'exemplaires': EXEMPLAIRES,
        'format_planche': FORMAT_PLANCHE,
        'format_corps': FORMAT_CORPS,
        'empreinte': (contexte or {}).get('empreinte') or '',
    })


def rendre_page_garde(contexte, manifeste, *, company=None):
    """PDF de la page de garde via ``core.pdf.render_pdf`` (ARC11)."""
    from core.pdf import render_pdf

    return render_pdf(html=rendre_page_garde_html(contexte, manifeste),
                      company=company)
