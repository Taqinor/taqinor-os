"""Contre-visite AERR de clôture (VER2-201, facturation, S2, résidu d'AERR133, jumeau oublié du survivant PaiementDialog) :
pages/ventes/NoteDebitDialog.jsx::NoteDebitDialog. AERR133 remet à zéro la liste et l'échec de lecture à chaque ouverture
et à chaque changement de facture, mais PAS la clé d'envoi `cleEnvoi` (ACNC2, remise à null au seul succès), ni `motif`,
`montant` et `erreur`. La boîte est montée en permanence par FactureList.jsx (sans `key`). Côté serveur, la clé est rangée
sous l'endpoint de la VUE + « .note_debit » (`core/idempotency.py::IdempotentCreateMixin._idempotency_endpoint`, sans l'id
de la facture) et l'empreinte ne porte que le corps. Chemin : « Créer » sur la facture A échoue sans réponse (délai ; la
note a pu être créée), on ferme, on ouvre B : motif et montant de A sont encore là ; « Créer » renvoie la même clé et le
même corps, le serveur REJOUE la réponse de A : « Note de débit ND-… créée » sous B, la note de A listée sous B, B ne
reçoit rien. Le jumeau `PaiementDialog.jsx` remet bien sa clé à null au changement de facture. Le détecteur vérifie ces
conditions dans le source (front et serveur)."""
SONDE = {"constat": "C-AERR-VER2-201", "sha": "d986bb9bc",
         "attendu": "bloc de remise à zéro sans cleEnvoi/motif/montant + clé remise à null au seul succès + endpoint serveur sans id de facture + survivant PaiementDialog"}
import pathlib, re
RACINE = pathlib.Path(__file__).resolve().parents[4]
SRC = RACINE / "frontend/src"
BACK = RACINE / "backend/django_core"


def nettoyer(s):
    """Retire les commentaires // et /* */ ; les chaînes sont respectées."""
    out, i, n, q = [], 0, len(s), None
    while i < n:
        c = s[i]
        if q:
            out.append(c)
            if c == "\\" and i + 1 < n:
                i += 1; out.append(s[i])
            elif c == q or (c == "\n" and q != "`"):
                q = None
        elif c in "'\"`":
            q = c; out.append(c)
        elif s.startswith("//", i):
            while i < n and s[i] != "\n":
                i += 1
            continue
        elif s.startswith("/*", i):
            j = s.find("*/", i + 2); i = n if j < 0 else j + 2; out.append(" "); continue
        else:
            out.append(c)
        i += 1
    return "".join(out)


def lire(rel):
    p = SRC / rel
    return nettoyer(p.read_text(encoding="utf-8")) if p.is_file() else None


def apparier(s, i, o="{", f="}"):
    d, q, j = 0, None, i
    while j < len(s):
        c = s[j]
        if q:
            if c == "\\":
                j += 1
            elif c == q or (c == "\n" and q != "`"):
                q = None
        elif c in "'\"`":
            q = c
        elif c == o:
            d += 1
        elif c == f:
            d -= 1
            if d == 0:
                return s[i + 1:j]
        j += 1
    return None


def corps_de(s, motif):
    m = re.search(motif, s)
    return (apparier(s, m.end() - 1) or "") if m else ""


def sonde(ctx=None):
    rel, rel_pay = "pages/ventes/NoteDebitDialog.jsx", "pages/ventes/PaiementDialog.jsx"
    s, pay = lire(rel), lire(rel_pay)
    vue_p = BACK / "apps/facturation/views/facture_rectificatifs.py"
    idem_p = BACK / "core/idempotency.py"
    introuvable = [r for r, t in ((rel, s), (rel_pay, pay)) if t is None]
    introuvable += [str(p.relative_to(RACINE)) for p in (vue_p, idem_p) if not p.is_file()]
    if introuvable:
        return {"repro": False, "observe": {"introuvable": introuvable}, "methode": "lecture écran + serveur"}
    m = re.search(r"if\s*\(\s*open\s*!==\s*wasOpen\s*\|\|\s*factureId\s*!==\s*vuFactureId\s*\)\s*\{", s)
    bloc = apparier(s, m.end() - 1) if m else None
    remet = {k: bool(bloc and re.search(p, bloc)) for k, p in (
        ("cleEnvoi", r"cleEnvoi\.current\s*=\s*null"), ("motif", r"setMotif\("),
        ("montant", r"setMontant\("), ("erreur", r"setErreur\("))}
    remises_cle = len(re.findall(r"cleEnvoi\.current\s*=\s*null", s))
    vue = vue_p.read_text(encoding="utf-8")
    idem = idem_p.read_text(encoding="utf-8")
    cle_vue = bool(re.search(r"rejeu_par_cle\(self,\s*request,\s*'note_debit'", vue))
    me = re.search(r"def _idempotency_endpoint\(self\):\s*\n\s*return ([^\n]+)", idem)
    endpoint_sans_pk = bool(me and "pk" not in me.group(1) and "kwargs" not in me.group(1))
    survivant = bool(re.search(r"cleEnvoi\.current\s*=\s*null[\s\S]{0,600}?\}, \[facture\?\.id\]\)", pay))
    repro = (bloc is not None and not any(remet.values()) and remises_cle == 1 and cle_vue
             and endpoint_sans_pk and survivant)
    return {"repro": repro,
            "observe": {"bloc_remise_a_zero_trouve": bloc is not None, "bloc_remet": remet,
                        "remises_de_la_cle_dans_le_fichier": remises_cle,
                        "serveur_cle_note_debit_par_vue": cle_vue,
                        "endpoint_idempotence": me.group(1).strip() if me else None,
                        "endpoint_sans_id_facture": endpoint_sans_pk,
                        "PaiementDialog_remet_sa_cle_au_changement_de_facture": survivant},
            "methode": "lecture écran + serveur"}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
