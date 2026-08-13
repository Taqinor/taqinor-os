"""PACT25 — LE REGISTRE qui associe chaque type de pièce à son producteur réel.

LE TROU QUE CE MODULE BOUCHE
----------------------------
Toute la machinerie basse du pack de soumission existait — écriture en flux
(``stockage.ecrire_artefact``), refus si un contrôle est rouge
(``coherence.passer_controle`` / ``pack_zip.ecrire_pack_zip``), orchestration
idempotente par empreinte (``tasks.produire_pack``), suivi de tâche
(``core.jobs`` / ``BackgroundJob``) — mais **rien ne lui fournissait les
pièces**. ``tasks.produire_pack_task`` importait ``services.producteurs_de_pack``
dans un ``try/except ImportError`` et, faute de monteur, **marquait le job
TERMINÉ** : un pack à zéro pièce se serait affiché « prêt » sur une archive
vide. C'est pour ça que les trois chemins (``generer-piece``, ``zip``,
``statut-de-job``) avaient été délibérément laissés fermés : *un faux succès est
pire qu'un 404, parce qu'il se dépose.*

CE QUE CE MODULE GARANTIT
-------------------------
1. **Chaque générateur déclaré est NOMMÉ ici** — code, libellé, format, et la
   liste des fonctions de ``fabrique/`` qu'il appelle réellement, sous forme de
   noms pointés ``module:fonction``. PACT180 en fait un test paramétré : aucun
   producteur nommé ne peut être orphelin (chaque nom doit se résoudre en un
   appelable), et aucune pièce du gabarit de pack ne peut rester sans entrée.
2. **Un générateur inconnu, ou dont les entrées manquent, ÉCHOUE en le
   NOMMANT.** Il ne renvoie jamais un artefact vide et ne se tait jamais :
   ``tasks.produire_pack`` transforme cet échec en ``complet=False``, ce qui
   interdit de marquer le pack prêt. Une pièce absente est un rouge, jamais un
   vert silencieux.
3. **Aucun coût, aucune marge.** Les pièces produites ici sont CLIENT ou
   INTERNE ; le classeur de rentabilité DIRECTEUR
   (``rendus/rentabilite_xlsx``) n'est volontairement PAS dans ce registre —
   il a son propre chemin gardé par ``ao_rentabilite_voir``, et l'entrer ici
   l'aurait fait tomber dans un pack de dépôt.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field

__all__ = [
    'MIME_PAR_FORMAT',
    'ProducteurIndisponible',
    'Producteur',
    'REGISTRE',
    'appeler',
    'generateurs_declares',
    'noms_de_fabrique',
    'producteur_pour',
    'resoudre',
]


class ProducteurIndisponible(Exception):
    """Le producteur existe mais ses entrées manquent — échec NOMMÉ.

    Levée par un monteur, elle remonte à ``tasks.produire_pack`` qui marque la
    pièce ``echouee`` avec ce motif : le pack devient INCOMPLET. C'est le
    comportement voulu — jamais une pièce vide déposée en silence.
    """


#: Extension + MIME par format déclaré sur ``PieceModele.Format``.
MIME_PAR_FORMAT = {
    'pdf': ('pdf', 'application/pdf'),
    'pdf_a3': ('pdf', 'application/pdf'),
    'xlsx': ('xlsx', 'application/vnd.openxmlformats-officedocument'
                     '.spreadsheetml.sheet'),
    'docx': ('docx', 'application/vnd.openxmlformats-officedocument'
                     '.wordprocessingml.document'),
    'zip': ('zip', 'application/zip'),
}


def resoudre(nom):
    """``'apps.ao.fabrique.rendus.memoire:rendre_memoire_html'`` -> l'appelable.

    Lève ``AttributeError``/``ImportError`` si le nom ne désigne plus rien :
    c'est exactement ce que le test paramétré de PACT180 exploite pour prouver
    qu'aucun producteur nommé n'est orphelin après un fold.
    """
    module_nom, _, attribut = str(nom).partition(':')
    module = importlib.import_module(module_nom)
    fonction = getattr(module, attribut)
    if not callable(fonction):
        raise TypeError(f'{nom} n\'est pas appelable.')
    return fonction


def appeler(nom, *args, **kwargs):
    """Appelle une fabrique NOMMÉE — l'indirection rend le registre auditable."""
    return resoudre(nom)(*args, **kwargs)


@dataclass(frozen=True)
class Producteur:
    """Une entrée du registre : qui produit quoi, avec quelles fabriques."""

    generateur: str
    libelle: str
    #: Fonctions de ``apps.ao.fabrique`` réellement appelées, nommées (PACT180).
    fabriques: tuple
    #: Monteur ``(dossier, piece, contexte) -> callable() -> bytes``.
    #: ``None`` = producteur DÉCLARÉ mais pas encore monté : la pièce échoue en
    #: le disant, elle n'est jamais produite vide.
    monteur: object = None
    #: Motif français quand le monteur manque — nomme l'entrée qui manque.
    motif_indisponible: str = ''
    formats: tuple = field(default_factory=lambda: ('pdf',))

    @property
    def monte(self):
        return callable(self.monteur)

    def octets(self, dossier, piece, contexte=None):
        """Produit les octets de la pièce, ou lève ``ProducteurIndisponible``."""
        if not self.monte:
            raise ProducteurIndisponible(
                self.motif_indisponible
                or f'Le producteur « {self.generateur} » n\'est pas monté.')
        return self.monteur(dossier, piece, contexte)


# ── Monteurs RÉELS ───────────────────────────────────────────────────────────

def _company_de(dossier):
    return getattr(dossier, 'company', None)


def _blocs_de_checklist(dossier):
    """Les points de checklist du dossier, groupés par bloc, dans l'ordre.

    Source unique : ``LigneChecklistPartenaire`` (AOF136) — la checklist est un
    OBJET SUIVI en base, jamais un document mort recomposé à la main.
    """
    blocs = {}
    ordre_blocs = []
    for ligne in dossier.lignes_checklist.all().order_by('ordre', 'code'):
        cle = ligne.bloc
        if cle not in blocs:
            blocs[cle] = {
                'code': cle,
                'titre': ligne.get_bloc_display(),
                'lignes': [],
            }
            ordre_blocs.append(cle)
        responsable = ligne.responsable_utilisateur
        blocs[cle]['lignes'].append({
            'libelle': ligne.libelle,
            'obligatoire': bool(ligne.obligatoire),
            'cochee': bool(ligne.faite),
            'responsable': (
                getattr(responsable, 'username', '') if responsable else ''),
            'commentaire': ligne.commentaire or '',
        })
    return [blocs[cle] for cle in ordre_blocs]


def _monter_checklist(dossier, piece, contexte=None):
    """00 — Checklist partenaire (DOCX, ou PDF dégradé si python-docx manque).

    ``rendre_checklist`` renvoie ``(contenu, format, a_fournir)`` :
    ``a_fournir=True`` signale un rendu DÉGRADÉ qui doit être imprimé et
    rempli à la main — donc une pièce qui n'est PAS produite par la fabrique.
    On lève alors plutôt que de la compter verte.
    """
    blocs = _blocs_de_checklist(dossier)
    if not blocs:
        raise ProducteurIndisponible(
            'Checklist partenaire vide : initialiser la checklist du dossier '
            '(action « initialiser-checklist ») avant de produire le pack.')
    ao = dossier.appel_offre
    identite = appeler('apps.ao.fabrique.identite:identite_soumissionnaire', ao)
    contenu, _format, a_fournir = appeler(
        'apps.ao.fabrique.rendus.checklist_docx:rendre_checklist',
        blocs, identite=identite,
        marche={'reference': ao.reference, 'objet': ao.objet},
        company=_company_de(dossier))
    if a_fournir:
        raise ProducteurIndisponible(
            'Checklist rendue en mode DÉGRADÉ (python-docx absent) : elle doit '
            'être fournie remplie, elle ne peut pas compter comme produite.')
    return contenu


def _monter_memoire(dossier, piece, contexte=None):
    """02 — Mémoire technique : sections composables -> HTML -> PDF."""
    from core.pdf import render_pdf

    html = appeler('apps.ao.fabrique.rendus.memoire:rendre_memoire_html',
                   dossier.appel_offre)
    if not (html or '').strip():
        raise ProducteurIndisponible(
            'Aucune section de mémoire applicable à ce dossier : le mémoire '
            'serait vide (voir SectionMemoire et ses conditions d\'inclusion).')
    return render_pdf(html=html, company=_company_de(dossier))


def _monter_simulation(dossier, piece, contexte=None):
    """05 — Simulation de rentabilité CLIENT (aucun coût, aucune marge)."""
    simulation = getattr(dossier.appel_offre, 'simulation_rentabilite', None)
    if simulation is None:
        raise ProducteurIndisponible(
            'Aucune simulation de rentabilité rattachée à cet appel d\'offres : '
            'la créer avant de produire le pack.')
    return appeler(
        'apps.ao.fabrique.rendus.simulation:rendre_simulation_pdf', simulation)


# ── Producteurs DÉCLARÉS mais pas encore montés ──────────────────────────────
#
# Ils sont nommés ICI, avec la fabrique qui les rendra et l'entrée qui leur
# manque, plutôt que d'être absents du registre : une pièce déclarée par le
# gabarit de pack et sans entrée de registre serait un TROU MUET. Nommée, elle
# échoue en disant pourquoi, et le pack refuse de passer prêt.

_MOTIF_CONTEXTE = (
    'Le rendu « {code} » attend le contexte gelé AOF111 '
    '(fabrique.contexte.construire_contexte) : aucun monteur ne l\'assemble '
    'encore depuis un DossierAO. La pièce est déclarée, pas produite — le pack '
    'reste donc INCOMPLET au lieu de se terminer vert sur une archive vide.'
)


def _indisponible(code):
    return _MOTIF_CONTEXTE.format(code=code)


#: Le registre. La clé est ``PieceModele.generateur`` (seed ``seed_pack_ao``).
REGISTRE = {
    'checklist': Producteur(
        generateur='checklist',
        libelle='Checklist partenaire',
        fabriques=(
            'apps.ao.fabrique.rendus.checklist_docx:rendre_checklist',
            'apps.ao.fabrique.rendus.checklist_docx:docx_disponible',
            'apps.ao.fabrique.rendus.checklist_docx:html_degrade',
            'apps.ao.fabrique.identite:identite_soumissionnaire',
        ),
        monteur=_monter_checklist,
        formats=('docx', 'pdf'),
    ),
    'lettre_soumission': Producteur(
        generateur='lettre_soumission',
        libelle='Lettre de soumission',
        fabriques=(
            'apps.ao.fabrique.rendus.lettre:contexte_gabarit',
            'apps.ao.fabrique.rendus.lettre:valeurs_de_controle',
            'apps.ao.fabrique.rendus.lettre:controler_vs_bordereau',
            'apps.ao.fabrique.rendus.lettre:controler_clause',
            'apps.ao.fabrique.rendus.lettre:controler_montants_rendus',
            'apps.ao.fabrique.montants:arrete',
            'apps.ao.fabrique.clauses:texte_clause',
        ),
        motif_indisponible=_indisponible('lettre_soumission'),
    ),
    'memoire': Producteur(
        generateur='memoire',
        libelle='Mémoire technique',
        fabriques=(
            'apps.ao.fabrique.rendus.memoire:rendre_memoire_html',
            'apps.ao.fabrique.rendus.memoire:assembler_memoire',
            'apps.ao.fabrique.rendus.memoire:contexte_memoire',
            'apps.ao.fabrique.rendus.memoire:sections_a_inclure',
        ),
        monteur=_monter_memoire,
    ),
    'note_calcul': Producteur(
        generateur='note_calcul',
        libelle='Note de calcul',
        fabriques=(
            'apps.ao.fabrique.rendus.note_calcul:rendre_note_calcul',
            'apps.ao.fabrique.rendus.note_calcul:rendre_note_calcul_html',
            'apps.ao.fabrique.rendus.note_calcul:construire_note_calcul',
            'apps.ao.fabrique.productible:resoudre',
            'apps.ao.fabrique.derivations:deriver',
        ),
        motif_indisponible=_indisponible('note_calcul'),
    ),
    'bordereau': Producteur(
        generateur='bordereau',
        libelle='Bordereau des prix',
        fabriques=(
            'apps.ao.fabrique.rendus.bordereau_pdf:contexte_gabarit',
            'apps.ao.fabrique.rendus.bordereau_pdf:valeurs_de_controle',
            'apps.ao.fabrique.rendus.bordereau_pdf:exiger_concordance',
            'apps.ao.fabrique.rendus.bordereau_xlsx:rendre',
            'apps.ao.fabrique.rendus.bordereau_xlsx:construire_classeur',
            'apps.ao.fabrique.rendus.bordereau_xlsx:vers_octets',
            'apps.ao.fabrique.ordonnancement:totaux',
        ),
        motif_indisponible=_indisponible('bordereau'),
        formats=('pdf', 'xlsx'),
    ),
    'simulation': Producteur(
        generateur='simulation',
        libelle='Simulation de rentabilité',
        fabriques=(
            'apps.ao.fabrique.rendus.simulation:rendre_simulation_pdf',
            'apps.ao.fabrique.rendus.simulation:classeur_xlsx',
            'apps.ao.fabrique.rendus.simulation:contexte_simulation',
            'apps.ao.fabrique.rendus.simulation:controler_absence_de_cout',
        ),
        monteur=_monter_simulation,
        formats=('pdf', 'xlsx'),
    ),
    'planches': Producteur(
        generateur='planches',
        libelle='Planches A3',
        fabriques=(
            'apps.ao.fabrique.pack_pdf:fusionner_pack',
            'apps.ao.fabrique.pack_pdf:sequence_impression',
            'apps.ao.fabrique.pack_pdf:plan_pagination',
        ),
        motif_indisponible=(
            'Les planches sont FUSIONNÉES depuis les documents GED des planches '
            'actives (fabrique.pack_pdf.fusionner_pack) : aucun monteur ne les '
            'sélectionne encore. Pièce déclarée, pas produite.'),
        formats=('pdf_a3',),
    ),
    'annexes': Producteur(
        generateur='annexes',
        libelle='Annexe — fiches techniques',
        fabriques=(
            'apps.ao.fabrique.annexes:index_annexes',
            'apps.ao.fabrique.annexes:controler_annexes',
            'apps.ao.fabrique.annexes:fiches_manquantes',
        ),
        motif_indisponible=(
            'L\'annexe agrège les fiches techniques des équipements actifs '
            '(fabrique.annexes.index_annexes) : aucun monteur ne fournit encore '
            'les fiches. Pièce déclarée, pas produite.'),
    ),
    'administratif': Producteur(
        generateur='administratif',
        libelle='Dossier administratif',
        fabriques=(
            'apps.ao.fabrique.pack_pdf:fusionner_pack',
            'apps.ao.fabrique.identite:identite_soumissionnaire',
        ),
        motif_indisponible=(
            'Le dossier administratif fusionne les PieceAdministrative valides '
            'à la date de remise : aucun monteur ne les assemble encore. Pièce '
            'déclarée, pas produite.'),
    ),
    'acte_engagement': Producteur(
        generateur='acte_engagement',
        libelle="Acte d'engagement",
        fabriques=(
            'apps.ao.fabrique.rendus.acte_engagement:contexte_gabarit',
            'apps.ao.fabrique.rendus.acte_engagement:blancs',
            'apps.ao.fabrique.rendus.acte_engagement:blancs_non_remplis',
            'apps.ao.fabrique.rendus.acte_engagement:valeurs_de_controle',
            'apps.ao.fabrique.rendus.acte_engagement:controler_vs',
        ),
        motif_indisponible=_indisponible('acte_engagement'),
    ),
}


def generateurs_declares():
    """Les clés du registre, triées — l'inventaire lisible d'un pack."""
    return tuple(sorted(REGISTRE))


def producteur_pour(generateur):
    """Le ``Producteur`` d'un générateur, ou ``None`` s'il n'est pas déclaré."""
    return REGISTRE.get((generateur or '').strip())


def noms_de_fabrique():
    """TOUS les noms de fabrique cités par le registre, dédupliqués et triés.

    PACT180 : c'est cette liste que le test paramétré résout une par une pour
    prouver qu'aucun producteur nommé n'est devenu orphelin.
    """
    noms = set()
    for producteur in REGISTRE.values():
        noms.update(producteur.fabriques)
    return tuple(sorted(noms))
