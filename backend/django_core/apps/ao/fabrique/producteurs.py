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
from decimal import ROUND_HALF_UP, Decimal

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


# ── AUD603 — le pont DossierAO -> contexte gelé AOF111 ───────────────────────
#
# Le contexte gelé (``fabrique.contexte.construire_contexte``) attend un mapping
# préparé par la couche Django. Ce mapping n'était assemblé NULLE PART hors des
# tests : c'est l'unique raison pour laquelle les deux pièces BLOQUANTES d'un
# pli marocain — le bordereau des prix et l'acte d'engagement — restaient
# déclarées sans monteur, et donc pourquoi la fabrique ne pouvait produire aucun
# pli déposable. Le pont est ICI, une seule fois, pour les deux.

def _bordereau_du_dossier(dossier):
    """Le bordereau qui FAIT FOI — le même que la passe de contrôle."""
    from .coherence import bordereau_de_reference

    return bordereau_de_reference(list(dossier.appel_offre.bordereaux.all()))


def _remise_de_ligne(ligne):
    """La remise de LIGNE en MONTANT (le modèle la porte en pourcentage)."""
    brut = (ligne.quantite or Decimal('0')) * (
        ligne.prix_unitaire or Decimal('0'))
    pct = ligne.remise_pct or Decimal('0')
    if not pct:
        return Decimal('0')
    return (brut * pct / Decimal('100')).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)


def _lignes_du_bordereau(bordereau):
    """Les lignes du BOQ au format attendu par ``fabrique.ordonnancement``.

    ``cle`` est la clé primaire de la ligne : c'est elle que la comparaison
    PDF ↔ classeur (``bordereau_pdf.comparer``) apparie, et une clé stable est
    ce qui permet de nommer la ligne fautive plutôt que « un écart quelque
    part ».
    """
    lignes = []
    for ligne in (bordereau.lignes
                  .select_related('section', 'batiment')
                  .order_by('numero', 'id')):
        section = ligne.section
        lignes.append({
            'cle': str(ligne.pk),
            'numero': ligne.numero,
            'section': ('%s — %s' % (section.numero, section.libelle)
                        if section is not None else ''),
            'designation': ligne.designation,
            'unite': ligne.unite,
            'quantite': ligne.quantite,
            'prix_unitaire': ligne.prix_unitaire,
            'remise': _remise_de_ligne(ligne),
            'taux_tva': ligne.taux_tva_effectif,
            'batiment': getattr(ligne.batiment, 'code', '') or '',
            'quantite_source': ligne.quantite_source,
        })
    return lignes


def _identite_pour_contexte(ao):
    """Traduit l'identité AOF144 vers les clés du contexte gelé AOF111.

    Les deux vocabulaires diffèrent (``identifiant_fiscal`` ↔ ``if_fiscal``,
    ``signataire_nom`` ↔ ``signataire``…) : la traduction est ici, explicite,
    plutôt que dupliquée dans chaque monteur.
    """
    source = appeler('apps.ao.fabrique.identite:identite_soumissionnaire', ao)
    return {
        'raison_sociale': source.get('raison_sociale', ''),
        'forme_juridique': '',
        'adresse': source.get('adresse', ''),
        'ville': '',
        'ice': source.get('ice', ''),
        'rc': source.get('registre_commerce', ''),
        'if_fiscal': source.get('identifiant_fiscal', ''),
        'cnss': '',
        'patente': '',
        'rib': source.get('rib', ''),
        'banque': '',
        'signataire': source.get('signataire_nom', ''),
        'qualite_signataire': source.get('signataire_qualite', ''),
        'telephone': '',
        'email': '',
    }


def _dossier_pour_contexte(dossier, bordereau, lignes):
    """Le mapping que ``contexte.construire_contexte`` attend, depuis la base.

    ``calepinage`` est DÉLIBÉRÉMENT vide : la section du contexte oppose le
    contrat AOF112 (``valider_lot``) aux résultats de calepinage, et ni le
    bordereau ni l'acte n'en impriment quoi que ce soit. Y verser des variantes
    non validées aurait fait échouer les deux pièces sur une donnée qu'elles ne
    lisent pas.
    """
    ao = dossier.appel_offre
    calcules = appeler('apps.ao.fabrique.ordonnancement:totaux', lignes,
                       taux_defaut=bordereau.taux_tva_defaut,
                       remise_globale=bordereau.montant_remise_globale)
    return {
        'identite': _identite_pour_contexte(ao),
        'acheteur': {
            'nom': ao.maitre_ouvrage or ao.acheteur or '',
            'adresse': ao.site_adresse or '',
            'ville': '',
            'representant': '',
        },
        'marche': {
            'objet': ao.objet or '',
            'reference_acheteur': ao.reference_acheteur or '',
            'reference': ao.reference or '',
            'type_prix': ('unitaires' if bordereau.marche_prix_unitaires
                          else 'forfaitaires'),
            'lot': ao.lot or '',
            'mode_passation': ao.mode_passation or '',
            'lieu_execution': ao.site_adresse or '',
            'delai_execution_jours': ao.delai_execution_jours,
            'validite_offre_jours': ao.validite_offre_jours,
        },
        'batiments': [
            {'code': batiment.code, 'libelle': batiment.designation,
             'engagement_modules': batiment.engagement_modules}
            for batiment in ao.batiments.all().order_by('ordre', 'code')
        ],
        'calepinage': [],
        'equipements': [
            {'role': equipement.role,
             'designation': equipement.designation,
             'marque': equipement.marque,
             'reference': equipement.reference_constructeur,
             'quantite': equipement.quantite,
             'unite': equipement.unite,
             'batiment': getattr(equipement.batiment, 'code', '') or ''}
            for equipement in ao.equipements.filter(actif=True)
            .select_related('batiment').order_by('role', 'id')
        ],
        'montants': {
            'sous_total_ht': calcules.sous_total_ht,
            'remise': calcules.remise,
            'total_ht': calcules.total_ht,
            'taux_tva': Decimal(str(bordereau.taux_tva_defaut or 20)),
            'tva': calcules.tva,
            'total_ttc': calcules.total_ttc,
            'devise': 'DH',
        },
        'clauses': {'reserve': bordereau.clause_reserve or ''},
        'dates': {
            'offre': dossier.date_depot or dossier.created_at,
            'remise_offre': ao.date_limite,
            'ouverture_plis': ao.date_ouverture_plis,
        },
        'engagements': [
            {'batiment': batiment.code,
             'modules': batiment.engagement_modules}
            for batiment in ao.batiments.all().order_by('ordre', 'code')
            if batiment.engagement_modules
        ],
    }


def _entrees_de_bordereau(dossier):
    """``(bordereau, lignes, contexte_gele)`` — ou un échec NOMMÉ."""
    bordereau = _bordereau_du_dossier(dossier)
    if bordereau is None:
        raise ProducteurIndisponible(
            'Aucun bordereau des prix n\'est rattaché à cet appel d\'offres : '
            'un pli sans bordereau des prix est déclaré irrecevable à '
            'l\'ouverture. Créer le bordereau avant de produire le pack.')
    lignes = _lignes_du_bordereau(bordereau)
    if not lignes:
        raise ProducteurIndisponible(
            'Le bordereau des prix ne porte aucune ligne : la pièce serait '
            'un tableau vide, refusée à l\'ouverture.')
    contexte = appeler(
        'apps.ao.fabrique.contexte:construire_contexte',
        _dossier_pour_contexte(dossier, bordereau, lignes))
    return bordereau, lignes, contexte


def _monter_bordereau(dossier, piece, contexte=None):
    """03 — Bordereau des prix (PDF) : PIÈCE BLOQUANTE d'un pli marocain."""
    from core.pdf import render_pdf

    from .rendus import bordereau_pdf

    bordereau, lignes, gele = _entrees_de_bordereau(dossier)
    donnees = appeler(
        'apps.ao.fabrique.rendus.bordereau_pdf:contexte_gabarit',
        lignes, gele,
        texte_clause=(bordereau.clause_reserve or None),
        taux_tva=bordereau.taux_tva_defaut,
        remise_globale=bordereau.montant_remise_globale)
    return render_pdf(template=bordereau_pdf.NOM_GABARIT, context=donnees,
                      company=_company_de(dossier))


def _modele_acte_de_l_acheteur(ao):
    """La ``PieceConsultation`` portant l'acte FOURNI par l'acheteur, si elle
    existe : sa seule présence bascule l'acte en fiche de REPORT (AOF132) —
    refabriquer le document de l'acheteur est un motif d'écartement."""
    from ..models import PieceConsultation

    piece = (PieceConsultation.objects
             .filter(company=ao.company, appel_offre=ao,
                     type_piece=PieceConsultation.TypePiece.MODELE_ACTE)
             .order_by('-id').first())
    if piece is None:
        return None
    return {'reference': piece.reference or '',
            'libelle': piece.get_type_piece_display()}


def _monter_acte_engagement(dossier, piece, contexte=None):
    """09 — Acte d'engagement : PIÈCE BLOQUANTE d'un pli marocain.

    Un acte dont un blanc OBLIGATOIRE est vide fait écarter le pli : il échoue
    ici en NOMMANT les blancs manquants, plutôt que de partir dans le ZIP.
    """
    from core.pdf import render_pdf

    from .rendus import acte_engagement

    bordereau, lignes, gele = _entrees_de_bordereau(dossier)
    donnees = appeler(
        'apps.ao.fabrique.rendus.acte_engagement:contexte_gabarit',
        lignes, gele,
        modele_acheteur=_modele_acte_de_l_acheteur(dossier.appel_offre),
        taux_tva=bordereau.taux_tva_defaut,
        remise_globale=bordereau.montant_remise_globale)
    manquants = appeler(
        'apps.ao.fabrique.rendus.acte_engagement:blancs_non_remplis', donnees)
    if manquants:
        raise ProducteurIndisponible(
            'Acte d\'engagement INCOMPLET — blancs obligatoires vides : %s. '
            'Un acte incomplet fait écarter le pli : renseigner l\'identité '
            'du soumissionnaire (IdentiteAO) et les données du marché avant '
            'de produire le pack.' % ', '.join(manquants))
    return render_pdf(template=acte_engagement.NOM_GABARIT, context=donnees,
                      company=_company_de(dossier))


def _pieces_administratives_a_fusionner(dossier):
    """Les pièces administratives ACTIVES et non périmées à la date de remise.

    La péremption N'EST PAS re-contrôlée ici : elle a déjà sa porte (AOF137 /
    ``AO_PIECE_ADMIN_EXPIREE``, BLOQUANTE), et le ZIP de dépôt refuse tant
    qu'un contrôle est rouge. Ce producteur se borne donc à ne PAS coller dans
    le dossier administratif une attestation que la commission rejetterait.
    """
    reference = dossier.date_reference_controle
    pieces = list(dossier.pieces_administratives.filter(actif=True)
                  .select_related('attachment')
                  .order_by('type_piece', 'id'))
    if reference is None:
        return pieces
    return [piece for piece in pieces if not piece.est_expiree_a(reference)]


def _monter_administratif(dossier, piece, contexte=None):
    """08 — Dossier administratif : FUSION des scans des pièces valides.

    3e pièce bloquante d'un pli marocain. La fusion se fait en octets, sans
    créer de document GED : un pack de dépôt ne doit rien laisser derrière lui
    dans la gestion documentaire.
    """
    from apps.records.storage import fetch_attachment

    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover — dépendance déclarée
        raise ProducteurIndisponible(
            'PyMuPDF est absent : le dossier administratif ne peut pas être '
            'fusionné. Une pièce vide ne part jamais à sa place.') from exc

    pieces = _pieces_administratives_a_fusionner(dossier)
    if not pieces:
        raise ProducteurIndisponible(
            'Aucune pièce administrative valide n\'est rattachée à ce '
            'dossier à la date de remise des plis : un pli sans dossier '
            'administratif est écarté. Rattacher les attestations avant de '
            'produire le pack.')
    sans_scan = [p.libelle for p in pieces if p.attachment_id is None]
    if sans_scan:
        raise ProducteurIndisponible(
            'Pièces administratives SANS scan joint : %s. Le dossier '
            'administratif serait amputé de ces pièces sans que rien ne le '
            'dise.' % ', '.join(sans_scan))

    sortie = fitz.open()
    try:
        for administrative in pieces:
            octets, erreur = fetch_attachment(administrative.attachment.file_key)
            if erreur or not octets:
                raise ProducteurIndisponible(
                    'Scan illisible pour la pièce administrative '
                    '« %s » : %s.' % (administrative.libelle,
                                      erreur or 'contenu vide'))
            try:
                source = fitz.open(stream=octets, filetype='pdf')
            except Exception as exc:
                raise ProducteurIndisponible(
                    'Le scan de « %s » n\'est pas un PDF exploitable : %s.'
                    % (administrative.libelle, exc)) from exc
            try:
                sortie.insert_pdf(source)
            finally:
                source.close()
        return sortie.tobytes()
    finally:
        sortie.close()


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
            'apps.ao.fabrique.contexte:construire_contexte',
            'apps.ao.fabrique.identite:identite_soumissionnaire',
        ),
        monteur=_monter_bordereau,
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
        # AUD604/AUD603 — ce producteur assemble des SCANS déjà rattachés au
        # dossier (records/MinIO), il ne rend rien : citer ici
        # `pack_pdf:fusionner_pack` (comme le faisait l'entrée non montée)
        # aurait été faux, cette fonction crée un document GED, or un pack de
        # dépôt ne doit rien laisser derrière lui. La fabrique RÉELLEMENT
        # appelée par `_monter_administratif` est le sélecteur ci-dessous
        # (le stockage MinIO est le socle transverse, hors `apps.ao.fabrique`
        # — voir PACT180 `HORS_REGISTRE_JUSTIFIE`) : la nommer ici est ce qui
        # évite que ce producteur reste orphelin.
        fabriques=(
            'apps.ao.fabrique.producteurs:_pieces_administratives_a_fusionner',
        ),
        monteur=_monter_administratif,
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
            'apps.ao.fabrique.contexte:construire_contexte',
            'apps.ao.fabrique.identite:identite_soumissionnaire',
        ),
        monteur=_monter_acte_engagement,
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
