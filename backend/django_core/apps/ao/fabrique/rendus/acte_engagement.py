"""AOF132 — acte d'engagement : la pièce HYBRIDE du dossier.

**Ce qui la rend particulière.** L'acte d'engagement est le plus souvent
FOURNI par l'acheteur, avec sa mise en page, ses articles et ses blancs. Il est
alors joint au DCE et doit être rempli — à la main, sur SON exemplaire — sans
jamais être « régénéré » : refabriquer le document de l'acheteur, c'est
remettre une pièce qui n'est pas la sienne, et c'est un motif d'écartement.
Mais certaines consultations n'en fournissent aucun, et il faut alors le
produire.

D'où deux modes, et un seul jeu de valeurs :

* `MODE_AUTONOME` — aucun modèle acheteur : on rend l'acte complet.
* `MODE_REPORT` — un modèle acheteur est rattaché : on ne rend PAS l'acte, on
  rend une **fiche de report** qui liste chaque blanc, la valeur à y écrire, et
  la référence de la pièce du DCE concernée. La personne qui remplit à la main
  n'a plus à chercher les valeurs dans trois documents — c'est là que se
  fabriquent les fautes de recopie.

Dans les deux cas, les valeurs sont LES MÊMES que celles du bordereau et de la
lettre (mêmes lignes, mêmes fonctions de total), et `controler_vs()` le prouve.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Tuple

from core.formats_fr import formater_date

from ..montants import duree_en_lettres, en_chiffres, en_lettres
from ..ordonnancement import totaux
from ..styles import contexte_style

NOM_GABARIT = 'ao/acte_engagement.html'
TITRE_AUTONOME = "Acte d'engagement"
TITRE_REPORT = "Acte d'engagement — fiche de report des valeurs"

MODE_AUTONOME = 'autonome'
MODE_REPORT = 'report'

VALIDITE_DEFAUT_JOURS = 75


@dataclass(frozen=True)
class Blanc:
    """UN blanc de l'acte : ce qu'il demande et ce qu'il faut y écrire."""

    code: str
    libelle: str
    valeur: str
    lettres: str = ''
    reference_dce: str = ''
    obligatoire: bool = True

    @property
    def rempli(self):
        return bool(str(self.valeur).strip())

    def vers_dict(self):
        return {'code': self.code, 'libelle': self.libelle,
                'valeur': self.valeur, 'lettres': self.lettres,
                'reference_dce': self.reference_dce,
                'obligatoire': self.obligatoire, 'rempli': self.rempli}


def _identite(contexte):
    return contexte.get('identite') or {}


def _marche(contexte):
    return contexte.get('marche') or {}


def blancs(lignes, contexte, *, taux_tva=Decimal('20'), devise='DH',
           reference_dce=''):
    """Les blancs de l'acte, dans l'ordre où un acte marocain les demande."""
    calcules = totaux(lignes, taux_defaut=taux_tva)
    identite = _identite(contexte)
    marche = _marche(contexte)
    validite = marche.get('validite_offre_jours') or VALIDITE_DEFAUT_JOURS
    delai = marche.get('delai_execution_jours')

    definition = [
        ('raison_sociale', 'Dénomination du soumissionnaire',
         identite.get('raison_sociale', ''), ''),
        ('forme_juridique', 'Forme juridique',
         identite.get('forme_juridique', ''), ''),
        ('adresse', 'Siège social',
         ', '.join(p for p in (identite.get('adresse'), identite.get('ville'))
                   if p), ''),
        ('ice', 'Identifiant commun de l\'entreprise (ICE)',
         identite.get('ice', ''), ''),
        ('rc', 'Registre du commerce', identite.get('rc', ''), ''),
        ('if_fiscal', 'Identifiant fiscal', identite.get('if_fiscal', ''), ''),
        ('cnss', 'Affiliation CNSS', identite.get('cnss', ''), ''),
        ('patente', 'Taxe professionnelle', identite.get('patente', ''), ''),
        ('rib', 'Relevé d\'identité bancaire', identite.get('rib', ''), ''),
        ('banque', 'Établissement bancaire', identite.get('banque', ''), ''),
        ('objet', 'Objet du marché', marche.get('objet', ''), ''),
        ('reference_acheteur', 'Référence de la consultation',
         marche.get('reference_acheteur', ''), ''),
        ('total_ht', 'Montant hors taxes',
         en_chiffres(calcules.total_ht, devise=devise),
         en_lettres(calcules.total_ht)),
        ('tva', 'Montant de la TVA',
         en_chiffres(calcules.tva, devise=devise),
         en_lettres(calcules.tva)),
        ('total_ttc', 'Montant toutes taxes comprises',
         en_chiffres(calcules.total_ttc, devise=devise),
         en_lettres(calcules.total_ttc)),
        ('validite', 'Durée de validité de l\'offre',
         '%s jours' % validite, duree_en_lettres(validite)),
        ('signataire', 'Nom et qualité du signataire',
         ' — '.join(p for p in (identite.get('signataire'),
                                identite.get('qualite_signataire')) if p), ''),
        ('lieu_date', 'Lieu et date',
         ', '.join(p for p in (identite.get('ville'),
                               formater_date((contexte.get('dates') or {})
                                             .get('offre'))) if p), ''),
    ]
    if delai:
        definition.insert(-3, ('delai', 'Délai d\'exécution',
                               '%s jours' % delai, duree_en_lettres(delai)))

    return tuple(Blanc(code=code, libelle=libelle, valeur=valeur,
                       lettres=lettres, reference_dce=reference_dce,
                       obligatoire=code not in ('cnss', 'patente',
                                                'forme_juridique', 'banque'))
                 for code, libelle, valeur, lettres in definition)


def contexte_gabarit(lignes, contexte, *, modele_acheteur=None,
                     taux_tva=Decimal('20'), devise='DH'):
    """Contexte du gabarit, dans le mode imposé par le DCE.

    :param modele_acheteur: mapping `{'reference': …, 'libelle': …}` de la
        `PieceConsultation` portant l'acte fourni par l'acheteur. Sa seule
        présence bascule en mode report.
    """
    mode = MODE_REPORT if modele_acheteur else MODE_AUTONOME
    reference_dce = str((modele_acheteur or {}).get('reference') or '')
    calcules = totaux(lignes, taux_defaut=taux_tva)

    donnees = {
        'piece_titre': TITRE_REPORT if mode == MODE_REPORT else TITRE_AUTONOME,
        'contexte': contexte,
        'mode': mode,
        'mode_report': mode == MODE_REPORT,
        'modele_acheteur': modele_acheteur or None,
        'reference_dce': reference_dce,
        'blancs': blancs(lignes, contexte, taux_tva=taux_tva, devise=devise,
                         reference_dce=reference_dce),
        'totaux': calcules,
        'total_ttc_lettres': en_lettres(calcules.total_ttc),
        'taux_tva': taux_tva,
    }
    donnees.update(contexte_style())
    return donnees


def fiche_de_report(donnees):
    """La fiche : chaque blanc, sa valeur, sa pièce du DCE. Rien à inventer."""
    return tuple(blanc.vers_dict() for blanc in donnees['blancs'])


def blancs_non_remplis(donnees):
    """Les blancs OBLIGATOIRES sans valeur — un acte incomplet est écarté."""
    return tuple(blanc.code for blanc in donnees['blancs']
                 if blanc.obligatoire and not blanc.rempli)


def valeurs_de_controle(donnees):
    return {'total_ht': donnees['totaux'].total_ht,
            'tva': donnees['totaux'].tva,
            'total_ttc': donnees['totaux'].total_ttc}


def controler_vs(donnees, *autres_valeurs) -> Tuple[str, ...]:
    """L'acte dit-il la même chose que le bordereau ET la lettre ?"""
    portes = valeurs_de_controle(donnees)
    ecarts = []
    for index, valeurs in enumerate(autres_valeurs, start=1):
        for cle in ('total_ht', 'tva', 'total_ttc'):
            if portes.get(cle) != valeurs.get(cle):
                ecarts.append('%s : acte %s, pièce %d %s'
                              % (cle, portes.get(cle), index,
                                 valeurs.get(cle)))
    return tuple(ecarts)


def valeur_du_blanc(donnees, code) -> Optional[str]:
    for blanc in donnees['blancs']:
        if blanc.code == code:
            return blanc.valeur
    return None
