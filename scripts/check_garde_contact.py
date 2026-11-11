#!/usr/bin/env python3
"""ACRM50 - garde de la classe « opposition recomposee a la main dans chaque
point d'entree » (C-ACRM-010, critere C7).

Dans TOUTES les apps de ``apps/`` (ACVI107 ; hors migrations/tests), TOUTE fonction
qui :
  * cree une touche : ``RelanceEtape.objects.create(...)`` / ``bulk_create(...)``,
  * fabrique un lien ``wa.me`` (litteral de chaine contenant ``wa.me/``, ou
    ``build_wa_url(numero, message)`` a message non vide -- ACVI90),
  * envoie un e-mail : ``send_mail(...)`` / ``EmailMessage(...)``,
doit consulter la garde de contact (``GARDES_RECONNUES`` : ``peut_contacter``,
``garde_contact_du_lead``, ``_refuser_si_oppose``...) dans son corps, OU figurer dans ``LISTE_BLANCHE`` avec une
raison motivee (une ligne par site, cle de CONTENU ``fichier::fonction::genre``,
jamais un numero de ligne). Analyse AST, DB-free, lecture seule.

Sortie non nulle : fichier:ligne, fonction et genre du site non garde.

Usage : python scripts/check_garde_contact.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = ROOT / "backend" / "django_core" / "apps"
#: ACVI107 — toutes les apps de ``apps/`` (memes exclusions : migrations, tests).
APPS_VISEES = None

#: Noms dont la simple presence dans le corps de la fonction vaut « garde ».
GARDES_RECONNUES = {"peut_contacter", "_lead_relancable", "motif_de_refus",
                    "_motif_de_refus", "refus_rendu_whatsapp", "garde_rendu_whatsapp",
                    # ACVI107 — les gardes reelles qui levent le 409 / SKIPPED nomme.
                    "garde_contact_du_lead", "_refuser_si_oppose", "_refus_opposition",
                    "exiger_contact_permis"}

_LOT_FILTRE = "lot : _file_whatsapp_en_masse sort les leads ne_plus_contacter avant tout lien (C-ACVI-061)"
_INTERNE = "interne : destinataire = utilisateur ou equipe de la societe (ou numero d'alerte), jamais un prospect"
_FOURNISSEUR = "fournisseur : destinataire = un fournisseur, pas un lead"
_PLOMBERIE = "plomberie : constructeur/transport generique ; la garde de contact est chez l'appelant"
_TRANSACTIONNEL = ("transactionnel (D-ACVI-10) : message contractuel a un client (facture, chantier, SAV, portail, "
                   "O&M, signature, OTP, acceptation), permis meme a un oppose")
_AMONT_DEVIS = "garde en amont (ACVI102) : build_single_devis_whatsapp appelle exiger_contact_permis"
_AMONT_NUDGE = "garde en amont : _nudge_suppressed (CADV8, peut_contacter) avant toute relance de devis"

#: ``fichier::fonction::genre`` -> raison. Site non garde TOLERE, motive.
#: Les raisons « A CORRIGER » sont de la dette reelle a traiter dans la session
#: qui possede le fichier (jamais corrigee depuis cette garde). Surface
#: append-only (docs/ownership.yml) : une tache ne retire que les lignes de SES
#: fichiers.
LISTE_BLANCHE: dict[str, str] = {
    "backend/django_core/apps/automation/actions.py::preparer_whatsapp::wa.me":
        "garde en amont : le handler appelle _refus_opposition avant preparer_whatsapp (partage avec la simulation)",
    "backend/django_core/apps/crm/fiche_bulk.py::_lien_reactivation::wa.me": _LOT_FILTRE,
    "backend/django_core/apps/crm/receivers_clients.py::_proposer_lien_parrainage_on_devis_accepted::wa.me":
        "lien de parrainage propose au COMMERCIAL du devis (destinataire interne, pas le prospect) ; aucun envoi au "
        "lead",
    "backend/django_core/apps/crm/leads_notifications.py::_build_lead_wa_reply_url::wa.me":
        "A CORRIGER (ACRM, session crm) : lien wa.me vers le prospect construit sans consulter peut_contacter ; "
        "brouillon que le vendeur clique, mais l'opposition n'est pas visible",
    "backend/django_core/apps/crm/cadence_filet.py::_poser_etape_de_filet::touche":
        "A CORRIGER (LSVC5-5) : pose de filet sans garde propre ; liste blanche « appelants gardes » OU garde a "
        "ajouter, decision du proprietaire crm",
    "backend/django_core/apps/crm/cadence_plan.py::initialiser_plan_relance::touche":
        "A CORRIGER (session crm) : creation en masse du plan de relance, tache interne du vendeur ; garde de contact "
        "a la pose non verifiee",
    "backend/django_core/apps/crm/cadence_filet.py::assurer_prochaine_etape_apres_succes::touche":
        "A CORRIGER (session crm) : touche de suite posee sans garde de contact a la pose",
    "backend/django_core/apps/crm/cadence_signaux.py::poser_touche_signal::touche":
        "A CORRIGER (session crm) : touche de signal posee sans garde de contact a la pose",
    "backend/django_core/apps/crm/cadence_filet.py::_poser_etape_visite::touche":
        "A CORRIGER (session crm) : touche de visite posee sans garde de contact a la pose",
    "backend/django_core/apps/crm/cadence_signaux.py::_poser_touche_rappel_demande::touche":
        "A CORRIGER (session crm) : touche de rappel demande posee sans garde de contact a la pose",
    "backend/django_core/apps/crm/cadence_reponses.py::_poser_etape_passation::touche":
        "A CORRIGER (session crm) : touche de passation posee sans garde de contact a la pose",
    # ── ACVI107 — sites des autres apps, vus pour la premiere fois ──
    "backend/django_core/apps/adminops/impersonation_service.py::_notifier_demande::email": _INTERNE,
    "backend/django_core/apps/adsengine/alerts.py::wa_link::wa.me": _INTERNE,
    "backend/django_core/apps/contact/views.py::contact::email": _INTERNE,
    "backend/django_core/apps/ged/services.py::_envoyer_lien_signature::email": _TRANSACTIONNEL,
    "backend/django_core/apps/ged/services.py::envoyer_code_otp_signataire::email": _TRANSACTIONNEL,
    "backend/django_core/apps/ged/services.py::_notifier_alteration_archives::email": _INTERNE,
    "backend/django_core/apps/installations/livraison_client_notify.py::notify_livraison_transition::wa.me":
        _TRANSACTIONNEL,
    "backend/django_core/apps/installations/livraison_client_notify.py::notify_livraison_transition::email":
        _TRANSACTIONNEL,
    "backend/django_core/apps/installations/tasks.py::_wa_draft_for_intervention::wa.me": _TRANSACTIONNEL,
    "backend/django_core/apps/installations/tasks.py::_envoyer_email_client::email": _TRANSACTIONNEL,
    "backend/django_core/apps/monitoring/report.py::email_om_report::email": _TRANSACTIONNEL,
    "backend/django_core/apps/notifications/services.py::_dispatch_email::email": _INTERNE,
    "backend/django_core/apps/notifications/services.py::_whatsapp_link::wa.me": _INTERNE,
    "backend/django_core/apps/notifications/whatsapp_bsp.py::ManualWaMeProvider.get_wa_url::wa.me": _PLOMBERIE,
    "backend/django_core/apps/notifications/whatsapp_bsp.py::ManualWaMeProvider._fallback_url::wa.me": _PLOMBERIE,
    "backend/django_core/apps/portail/services.py::_envoyer_identifiants_portail::email": _TRANSACTIONNEL,
    "backend/django_core/apps/portail/services.py::_envoyer_invitation_portail::email": _TRANSACTIONNEL,
    "backend/django_core/apps/reporting/rapport_abonnements.py::_envoyer::email": _INTERNE,
    "backend/django_core/apps/reporting/scheduled_reports.py::_send_report_email::email": _INTERNE,
    "backend/django_core/apps/sav/notifications_client.py::notify_ticket_transition::email": _TRANSACTIONNEL,
    "backend/django_core/apps/sav/services.py::repondre_par_email::email": _TRANSACTIONNEL,
    "backend/django_core/apps/statuspage/receivers.py::_envoyer_notification_abonnes::email":
        "abonnes opt-in de la page de statut (inscription volontaire), pas un lead",
    "backend/django_core/apps/statuspage/views.py::_envoyer_email_confirmation::email":
        "double opt-in de la page de statut (confirmation demandee par l'abonne), pas un lead",
    "backend/django_core/apps/stock/services.py::_envoyer_identifiants_portail_fournisseur::email": _FOURNISSEUR,
    "backend/django_core/apps/stock/views/bon_commande_fournisseur.py::BonCommandeFournisseurViewSet.whatsapp::wa.me":
        _FOURNISSEUR,
    "backend/django_core/apps/ventes/domain/cycle_vie.py::_send_otp_email::email": _TRANSACTIONNEL,
    "backend/django_core/apps/ventes/domain/notifications_acceptation.py::_build_acceptance_wa_url::wa.me":
        _TRANSACTIONNEL,
    "backend/django_core/apps/ventes/domain/recouvrement.py::_build_wa_draft_url::wa.me": _AMONT_NUDGE,
    "backend/django_core/apps/ventes/domain/recouvrement.py::_send_nudge_email::email": _AMONT_NUDGE,
    "backend/django_core/apps/ventes/email_service.py::_send::email": _PLOMBERIE,
    "backend/django_core/apps/ventes/utils/whatsapp.py::build_wa_url::wa.me": _PLOMBERIE,
    "backend/django_core/apps/ventes/views/devis_envoi.py::DevisEnvoiActionsMixin.whatsapp_preview::wa.me":
        _AMONT_DEVIS,
    "backend/django_core/apps/ventes/views/devis_envoi.py::DevisEnvoiActionsMixin.whatsapp::wa.me": _AMONT_DEVIS,
    "backend/django_core/apps/facturation/views/facture_documents.py::FactureDocumentsActionsMixin.whatsapp::wa.me":
        _TRANSACTIONNEL,
}

GENRE_TOUCHE, GENRE_WAME, GENRE_MAIL = "touche", "wa.me", "email"


def _fichiers(apps_dir: Path = APPS_DIR):
    apps = APPS_VISEES or sorted(p.name for p in apps_dir.iterdir() if p.is_dir())
    for app in apps:
        base = apps_dir / app
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.py")):
            parts = p.relative_to(base).parts
            n = p.name
            if "migrations" in parts or "tests" in parts:
                continue
            if n.startswith(("test_", "tests_")) or n in ("tests.py", "conftest.py") \
                    or n.endswith("_test.py"):
                continue
            yield p


def _rel(p: Path) -> str:
    return str(p.relative_to(ROOT)).replace("\\", "/")


def _nom_appel(func: ast.AST) -> str:
    return func.attr if isinstance(func, ast.Attribute) else (
        func.id if isinstance(func, ast.Name) else "")


def _a_un_message(appel: ast.Call) -> bool:
    """``build_wa_url(n, '')`` valide un numero ; avec un message, c'est un lien
    pret a envoyer."""
    message = appel.args[1] if len(appel.args) > 1 else None
    return message is not None and not (
        isinstance(message, ast.Constant) and not message.value)


class _Visiteur(ast.NodeVisitor):
    def __init__(self):
        self.pile: list[str] = []
        # fonction qualifiee -> {"garde": bool, "sites": [(genre, ligne)]}
        self.fonctions: dict[str, dict] = {}

    def _etat(self):
        cle = ".".join(self.pile) or "<module>"
        return self.fonctions.setdefault(cle, {"garde": False, "sites": []})

    def _porte(self, node):
        self.pile.append(node.name)
        self.generic_visit(node)
        self.pile.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _porte

    def _noter(self, nom):
        if nom in GARDES_RECONNUES:
            self._etat()["garde"] = True

    def visit_Name(self, node):
        self._noter(node.id)

    def visit_Attribute(self, node):
        self._noter(node.attr)
        self.generic_visit(node)

    def visit_Call(self, node):
        nom = _nom_appel(node.func)
        if isinstance(node.func, ast.Attribute) and nom in ("create", "bulk_create"):
            recv = ast.unparse(node.func.value)
            if recv == "RelanceEtape.objects" or recv.endswith(".RelanceEtape.objects"):
                self._etat()["sites"].append((GENRE_TOUCHE, node.lineno))
        elif nom in ("send_mail", "EmailMessage", "EmailMultiAlternatives"):
            self._etat()["sites"].append((GENRE_MAIL, node.lineno))
        elif nom == "build_wa_url" and _a_un_message(node):
            self._etat()["sites"].append((GENRE_WAME, node.lineno))
        self.generic_visit(node)

    def visit_Import(self, node):
        for a in node.names:
            self._noter(a.name.split(".")[-1])

    def visit_ImportFrom(self, node):
        for a in node.names:
            self._noter(a.name)

    def visit_Constant(self, node):
        if isinstance(node.value, str) and "wa.me/" in node.value:
            self._etat()["sites"].append((GENRE_WAME, node.lineno))


def _retirer_docstrings(tree: ast.AST) -> None:
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            corps = n.body
            if corps and isinstance(corps[0], ast.Expr) \
                    and isinstance(corps[0].value, ast.Constant) \
                    and isinstance(corps[0].value.value, str):
                corps[0].value.value = ""


def analyser_source(source: str, rel: str):
    """-> liste de (cle, ligne, fonction, genre) pour les sites NON gardes."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    _retirer_docstrings(tree)
    v = _Visiteur()
    v.visit(tree)
    out = []
    for fonction, etat in v.fonctions.items():
        if etat["garde"]:
            continue
        vus = set()
        for genre, ligne in etat["sites"]:
            if genre in vus:
                continue
            vus.add(genre)
            out.append((f"{rel}::{fonction}::{genre}", ligne, fonction, genre))
    return out


def main(argv=None, sources_en_plus=()) -> int:
    """``sources_en_plus`` : ``(rel, source)`` analyses en plus du depot (tests)."""
    violations = []
    utilises = set()
    sources = [(_rel(p), p.read_text(encoding="utf-8")) for p in _fichiers()]
    for rel, source in [*sources, *sources_en_plus]:
        for cle, ligne, fonction, genre in analyser_source(source, rel):
            if cle in LISTE_BLANCHE:
                utilises.add(cle)
                continue
            violations.append((rel, ligne, fonction, genre))
    perimees = sorted(set(LISTE_BLANCHE) - utilises)
    if violations or perimees:
        for f, l, fn, g in violations:
            print(f"{f}:{l}: {fn}() - {g} sans garde de contact "
                  f"(peut_contacter/_lead_relancable/motif_de_refus) ni liste blanche")
        for c in perimees:
            print(f"liste blanche perimee (plus aucun site) : {c}")
        return 1
    print("check_garde_contact : OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
