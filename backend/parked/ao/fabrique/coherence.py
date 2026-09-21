"""AOF146 — la PASSE de contrôle de cohérence croisée d'un dossier d'AO.

Le moteur assemble le CONTEXTE une fois, exécute le registre
``apps.ao.controles`` en UNE passe, puis REMPLACE les lignes
``ControleCoherence`` du dossier. Une passe est une photographie d'un état :
elle porte l'empreinte du contexte contrôlé, sans quoi un résultat vert ne
prouverait rien (il pourrait décrire un autre dossier).

Le résultat est une PORTE : ``services.changer_statut_dossier`` refuse
``pret_a_deposer`` tant qu'un contrôle bloquant est rouge, en citant le code de
règle fautif.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal

from .. import controles

__all__ = [
    'bordereau_de_reference',
    'contexte_controle',
    'controles_bloquants',
    'empreinte_dossier',
    'passe_en_lecture',
    'passer_controle',
    'pieces_hors_controle',
]


def _empreinte_de_texte(*morceaux):
    """SHA-256 court d'un contenu textuel — pour ne pas gonfler le canonique."""
    charge = '\x1f'.join(str(m or '') for m in morceaux)
    return hashlib.sha256(charge.encode('utf-8')).hexdigest()[:16]


def empreinte_dossier(dossier):
    """SHA-256 du contexte du dossier — ce que le pack REFLÈTE aujourd'hui.

    Entrent : les totaux des bordereaux, les empreintes d'entrée des variantes
    retenues, les désignations et quantités des équipements actifs, les indices
    des planches actives, **le CONTENU des textes normalisés du mémoire et
    l'état de la checklist** (AUD604). N'entrent pas : les identifiants
    techniques, les horodatages, les libellés d'affichage (un simple renommage
    ne périme pas un pack — sinon le bandeau « périmé » se dévalue).

    AUD604 — pourquoi le mémoire et la checklist ENTRENT. Le mémoire technique
    est assemblé en LIVE depuis ``SectionMemoire`` (``sections_a_inclure`` /
    ``assembler_memoire``) et la checklist partenaire est produite depuis
    ``LigneChecklistPartenaire`` : leur contenu ne laissait AUCUNE trace dans
    l'empreinte. Corriger une phrase du mémoire laissait donc l'empreinte
    identique, la branche REPRISE de ``producteurs_de_pack`` reprenait la pièce
    ARCHIVÉE, et c'est l'ancien texte qui partait à l'acheteur.

    Le hachage est VOLONTAIREMENT plus large que le rendu : il couvre toutes
    les sections actives de la société, pas seulement celles que les conditions
    d'inclusion retiendront. Sur-périmer coûte une régénération ; sous-périmer
    dépose une pièce fausse. Conséquence assumée : les artefacts produits AVANT
    ce correctif sont vus une fois comme périmés et se refabriquent.
    """
    from ..models import SectionMemoire

    ao = dossier.appel_offre
    canonique = {
        'bordereaux': sorted(
            f'{b.indice_revision}:{b.total_ttc}'
            for b in ao.bordereaux.all()),
        'variantes': sorted(
            f'{v.toiture_id}:{v.entree_hash}:{v.total_modules}'
            for v in ao.variantes_calepinage.filter(est_retenue=True)),
        'equipements': sorted(
            f'{e.role}:{e.designation}:{e.quantite}'
            for e in ao.equipements.filter(actif=True)),
        'planches': sorted(
            f'{p.code_document}{p.indice}'
            for p in ao.planches.filter(statut='active')),
        'memoire': sorted(
            '{}:{}'.format(
                s.code,
                _empreinte_de_texte(
                    s.titre, s.corps, s.ordre,
                    # JSONField : `str(dict)` dépend de l'ordre des clés rendu
                    # par PostgreSQL — l'empreinte bougerait sans que rien ne
                    # change. `sort_keys` la rend stable.
                    json.dumps(s.conditions_inclusion, sort_keys=True,
                               ensure_ascii=False)))
            for s in SectionMemoire.objects.filter(
                company_id=dossier.company_id, actif=True)),
        'checklist': sorted(
            '{}:{}:{}'.format(
                ligne.code, int(bool(ligne.faite)),
                _empreinte_de_texte(ligne.commentaire))
            for ligne in dossier.lignes_checklist.all()),
    }
    charge = json.dumps(canonique, sort_keys=True, ensure_ascii=False,
                        separators=(',', ':'))
    return hashlib.sha256(charge.encode('utf-8')).hexdigest()


def bordereau_de_reference(bordereaux):
    """Le bordereau qui fait foi : le plus haut indice de révision.

    PUBLIC depuis AUD603 : le producteur du bordereau des prix et celui de
    l'acte d'engagement doivent choisir EXACTEMENT le même bordereau que la
    passe de contrôle, sinon le pli déposé pourrait porter un montant que les
    contrôles n'ont jamais vu.
    """
    if not bordereaux:
        return None
    return sorted(bordereaux, key=lambda b: (b.indice_revision, b.pk))[-1]


def contexte_controle(dossier):
    """Assemble UNE fois tout ce dont les règles ont besoin."""
    ao = dossier.appel_offre
    bordereaux = list(ao.bordereaux.all())
    variantes = list(ao.variantes_calepinage.filter(est_retenue=True))
    modules_engages = sum(int(v.total_modules or 0) for v in variantes) \
        if variantes else None
    puissance = Decimal('0.000')
    for variante in variantes:
        puissance += Decimal(str(variante.puissance_kwc or 0))
    toitures = []
    for batiment in ao.batiments.all():
        toitures.extend(batiment.toitures.all())
    return {
        'dossier': dossier,
        'appel_offre': ao,
        'bordereaux': bordereaux,
        'bordereau': bordereau_de_reference(bordereaux),
        'variantes': variantes,
        'modules_engages': modules_engages,
        'puissance_kwc': puissance,
        'equipements': list(ao.equipements.filter(actif=True)),
        'toitures': toitures,
        'pieces': list(dossier.pieces.all()),
        'empreinte': empreinte_dossier(dossier),
        'textes_client': (),
    }


def passer_controle(dossier, *, codes=None):
    """Exécute la passe et REMPLACE les lignes de contrôle du dossier.

    Renvoie ``{'empreinte', 'bloquants', 'avertissements', 'resultats'}``.
    """
    from django.db import transaction

    from ..models import ControleCoherence

    contexte = contexte_controle(dossier)
    resultats = controles.executer_regles(contexte, codes=codes)
    empreinte = contexte['empreinte']
    with transaction.atomic():
        ControleCoherence.objects.filter(dossier=dossier).delete()
        ControleCoherence.objects.bulk_create([
            ControleCoherence(
                company=dossier.company, dossier=dossier,
                code_regle=item['code_regle'], severite=item['severite'],
                message=item['message'], objet=item['objet'],
                empreinte=empreinte)
            for item in resultats
        ])
    bloquants = [r for r in resultats
                 if r['severite'] == controles.BLOQUANT]
    avertissements = [r for r in resultats
                      if r['severite'] == controles.AVERTISSEMENT]
    hors = pieces_hors_controle(dossier)
    return {
        'empreinte': empreinte,
        'bloquants': bloquants,
        'avertissements': avertissements,
        'resultats': resultats,
        # AOF149 — le rapport COMPTE et NOMME les pièces hors contrôle : un
        # dossier « tout vert » dont un tiers n'a jamais été vérifié est plus
        # dangereux qu'un dossier orange.
        'hors_controle': [
            {'code': piece.code, 'libelle': piece.libelle,
             'motif': piece.motif, 'etat': piece.etat_controle}
            for piece in hors
        ],
        'nombre_hors_controle': len(hors),
    }


def pieces_hors_controle(dossier):
    """Les pièces PRÉSENTES que la fabrique n'a pas produites (AOF149)."""
    from ..models import PieceDossierAO

    return [piece for piece in dossier.pieces.all()
            if piece.controlee == PieceDossierAO.HORS_CONTROLE
            and piece.presente]


def controles_bloquants(dossier):
    """Les anomalies BLOQUANTES d'une passe fraîche (sans persistance)."""
    contexte = contexte_controle(dossier)
    return [item for item in controles.executer_regles(contexte)
            if item['severite'] == controles.BLOQUANT]


def _libelle_de_regle(code):
    """Le libellé du REGISTRE — l'écran n'invente jamais un titre de règle."""
    regle = controles.REGLES.get(code)
    return regle.libelle if regle is not None else code


def passe_en_lecture(dossier):
    """La MÊME passe que ``passer_controle``, sans écrire une seule ligne.

    Un GET ne persiste rien : l'écran « Contrôles avant dépôt » (AOF176) LIT
    l'état du dossier, il ne le fige pas. ``passer_controle`` reste le seul
    chemin qui REMPLACE les ``ControleCoherence`` — c'est lui la photographie
    opposable, et il se déclenche explicitement.

    Le rapport porte les mêmes pièces HORS CONTRÔLE (AOF149) que la passe
    persistante : un dossier « tout vert » dont un tiers n'a jamais été
    vérifié est plus dangereux qu'un dossier orange, et l'omettre ici aurait
    reconstruit exactement ce piège côté écran.
    """
    contexte = contexte_controle(dossier)
    resultats = controles.executer_regles(contexte)
    hors = pieces_hors_controle(dossier)
    return {
        'empreinte': contexte['empreinte'],
        'bloquant': any(item['severite'] == controles.BLOQUANT
                        for item in resultats),
        'controles': [
            {'code': item['code_regle'],
             'code_regle': item['code_regle'],
             'libelle': _libelle_de_regle(item['code_regle']),
             'severite': item['severite'],
             'message': item['message'],
             'objet': item['objet']}
            for item in resultats
        ],
        'pieces_hors_controle': [
            {'code': piece.code, 'libelle': piece.libelle,
             'motif': piece.motif, 'etat': piece.etat_controle}
            for piece in hors
        ],
        'nombre_hors_controle': len(hors),
    }
