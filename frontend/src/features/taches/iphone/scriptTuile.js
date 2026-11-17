/* ============================================================================
   TCH110 — Le script de la grande tuile Scriptable (≤ 90 lignes), servi par Mon iPhone (étape 4)
   avec « Copier le script ». Il lit `GET taches/tuile/` (contract_samples/tuile.json : faites,
   prevues, objectif, essentiel.prevues, top, reste, prochaine_echeance, lien, maj) avec le jeton
   `tuile` qu'il garde dans le Trousseau de l'iPhone — le script ne contient JAMAIS le jeton ;
   `__BASE__` est remplacé par l'adresse de l'ERP à la copie (`scriptPour`).
   Textes : reference/textes.md §8. Maquette : docs/taches/maquettes/tuile.html.
   Hors ligne : la dernière réponse gardée est relue et le pied dit « Hors ligne · maj HH:MM ».
   ========================================================================== */

export const SCRIPT_TUILE = String.raw`// Tâches Taqinor — tuile Scriptable. Colle ce script dans Scriptable, puis lance-le une fois (▶).
const BASE = "__BASE__";
const fm = FileManager.local();
const FICHIER = fm.joinPath(fm.documentsDirectory(), "taches-tuile.json");
const fond = Color.dynamic(new Color("#ffffff"), new Color("#0f172a"));
const texte = Color.dynamic(new Color("#0f172a"), new Color("#f8fafc"));
const doux = Color.dynamic(new Color("#64748b"), new Color("#94a3b8"));

async function jeton() {
  if (Keychain.contains("taqinor_tuile")) return Keychain.get("taqinor_tuile");
  if (!config.runsInApp) return null;
  const a = new Alert();
  a.title = "Jeton de la tuile";
  a.message = "Colle le jeton copié depuis Mon iPhone.";
  a.addTextField("tqt_…");
  a.addAction("Enregistrer");
  await a.present();
  const v = a.textFieldValue(0).trim();
  if (v) Keychain.set("taqinor_tuile", v);
  return v || null;
}

async function charger(t) {
  try {
    const r = new Request(BASE + "/api/django/taches/tuile/");
    r.headers = { Authorization: "Bearer " + t };
    r.timeoutInterval = 15;
    const d = await r.loadJSON();
    if (!d || !d.jour) throw new Error("réponse refusée");
    fm.writeString(FICHIER, JSON.stringify(d));
    return { d: d, enLigne: true };
  } catch (e) {
    if (fm.fileExists(FICHIER)) return { d: JSON.parse(fm.readString(FICHIER)), enLigne: false };
    return { d: null, enLigne: false };
  }
}

function ligne(w, s, taille, couleur, gras) {
  const x = w.addText(s);
  x.font = gras ? Font.boldSystemFont(taille) : Font.systemFont(taille);
  x.textColor = couleur;
  x.lineLimit = 1;
}

const t = await jeton();
const res = t ? await charger(t) : { d: null, enLigne: false };
const d = res.d;
const w = new ListWidget();
w.backgroundColor = fond;
w.refreshAfterDate = new Date(Date.now() + 15 * 60 * 1000);
if (!d) {
  ligne(w, t ? "Pas de données" : "Jeton absent", 16, texte, true);
  ligne(w, "Ouvre le script dans Scriptable.", 12, doux);
} else {
  if (d.lien) w.url = d.lien;
  ligne(w, d.objectif != null ? d.faites + " sur " + d.objectif : d.faites + " faites", 20, texte, true);
  if (d.essentiel && d.essentiel.prevues >= 1) {
    ligne(w, "Essentiel " + d.essentiel.faites + "/" + d.essentiel.prevues, 13, doux);
  }
  const n = config.widgetFamily === "large" ? 6 : 3;
  for (const x of d.top.slice(0, n)) {
    w.addSpacer(4);
    ligne(w, (x.heure ? x.heure + "  " : "• ") + x.titre, 14, texte);
  }
  if (!d.top.length) ligne(w, "Rien de gardé aujourd'hui.", 14, doux);
  if (d.reste > 0) ligne(w, "+ " + d.reste + " autres", 12, doux);
  if (d.prochaine_echeance) {
    const j = new Date(d.prochaine_echeance.jour + "T12:00:00");
    const jour = j.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric" });
    w.addSpacer(6);
    ligne(w, "Échéance " + jour + " : " + d.prochaine_echeance.titre, 12, doux);
  }
  w.addSpacer();
  const h = /T(\d\d:\d\d)/.exec(d.maj || "");
  ligne(w, (res.enLigne ? "maj " : "Hors ligne · maj ") + (h ? h[1] : ""), 11, doux);
}
Script.setWidget(w);
if (config.runsInApp) await w.presentLarge();
Script.complete();
`

/** Le script prêt à coller : `__BASE__` devient l'adresse de l'ERP (jamais un jeton). */
export const scriptPour = (base) => SCRIPT_TUILE.replace('__BASE__', String(base).replace(/\/+$/, ''))
