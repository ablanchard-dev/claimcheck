"""Conditions hostiles : l'outil doit échouer PROPREMENT, jamais rassurer.

Un hook qui plante affiche une erreur à chaque fin de tour et se fait désinstaller le
jour même. Un hook qui bloque à tort, pire. La règle unique de ce banc :

    dans TOUTES ces situations, ne jamais planter et ne jamais bloquer.

Un blocage n'est légitime que si une affirmation est réellement contredite. Toute
situation dégradée — fichier absent, JSON cassé, message vide — doit se traduire par
« je n'ai pas pu regarder », donc par un silence, jamais par une accusation.

    python test_robustesse.py
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import time

ICI = os.path.dirname(os.path.abspath(__file__))
T = tempfile.gettempdir()

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

res = []


def hook(payload_brut):
    """Renvoie (a_plante, a_bloque, duree_s, stderr)."""
    t0 = time.time()
    r = subprocess.run([sys.executable, "claimcheck.py", "--hook"], cwd=ICI,
                       input=payload_brut, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return (r.returncode != 0, '"block"' in (r.stdout or ""),
            time.time() - t0, (r.stderr or "").strip())


def cas(nom, payload_brut, max_s=3.0):
    plante, bloque, duree, err = hook(payload_brut)
    ok = (not plante) and (not bloque) and duree <= max_s
    res.append(ok)
    detail = []
    if plante:
        detail.append("PLANTE: " + err.splitlines()[-1][:70] if err else "PLANTE")
    if bloque:
        detail.append("BLOQUE A TORT")
    detail.append("%.2fs" % duree)
    print(("  [OK  ] " if ok else "  [RATE] ") + nom + "  -- " + " | ".join(detail))
    return ok


def ecrire(nom, lignes, dossier=T):
    p = os.path.join(dossier, nom)
    with io.open(p, "w", encoding="utf-8") as f:
        for l in lignes:
            f.write((l if isinstance(l, str) else json.dumps(l)) + "\n")
    return p


def tour(sortie=None):
    L = [{"type": "user", "message": {"role": "user", "content": "vas-y"}},
         {"type": "assistant",
          "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}}]
    if sortie is not None:
        L.append({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "1", "content": sortie,
             "is_error": False}]}})
    return L


def p(msg, tp):
    return json.dumps({"hook_event_name": "Stop", "last_assistant_message": msg,
                       "transcript_path": tp})


def main():
    print("=== claimcheck — conditions hostiles ===\n")
    bon = ecrire("cc_rb_ok.jsonl", tour("162 passed in 7.40s"))

    print("Fichier de transcript")
    cas("inexistant", p("J'ai lance : 162 tests verts.", os.path.join(T, "n_existe_pas.jsonl")))
    cas("vide", p("J'ai lance : 162 tests verts.", ecrire("cc_rb_vide.jsonl", [])))
    cas("JSON invalide", p("J'ai lance : 162 tests verts.",
                           ecrire("cc_rb_casse.jsonl", ["{pas du json", "}{", ""])))
    cas("lignes valides mais schema inconnu", p("J'ai lance : 162 tests verts.",
        ecrire("cc_rb_schema.jsonl", [{"autre": 1}, {"message": "pas un dict"}])))
    cas("chemin absent du payload", json.dumps(
        {"hook_event_name": "Stop", "last_assistant_message": "J'ai lance : 162 tests verts."}))

    print("\nChemins hostiles")
    acc = os.path.join(T, "dossier accentué éèç")
    os.makedirs(acc, exist_ok=True)
    cas("accents et espaces dans le chemin",
        p("J'ai lance : 162 tests verts.", ecrire("cc rb é.jsonl", tour("162 passed"), acc)))

    print("\nMessage final")
    cas("message vide", p("", bon))
    cas("message sans aucun chiffre", p("C'est fait, tout est en ordre.", bon))
    cas("message tres long sans chiffre", p("bla " * 5000, bon))
    cas("chiffres qui ne sont pas des affirmations", p("Le 21/08 a 14:30, version 3.11.", bon))

    print("\nPayload stdin")
    cas("JSON malforme", "{ceci n'est pas du json")
    cas("stdin vide", "")
    cas("JSON valide mais pas un objet", "[1, 2, 3]")
    cas("last_assistant_message absent", json.dumps(
        {"hook_event_name": "Stop", "transcript_path": bon}))
    cas("last_assistant_message = null", json.dumps(
        {"hook_event_name": "Stop", "last_assistant_message": None, "transcript_path": bon}))

    print("\nTour sans preuve")
    cas("aucune sortie d'outil dans le tour",
        p("J'ai lance : 162 tests verts.", ecrire("cc_rb_nopreuve.jsonl", tour(None))))

    print("\nPerformance — un hook lent se fait desinstaller")
    gros = tour("162 passed in 7.40s")
    for i in range(4000):
        gros.append({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": str(i), "content": "ligne " * 40,
             "is_error": False}]}})
    cas("transcript de 4000 sorties d'outil (< 3 s)",
        p("J'ai lance : 162 tests verts.", ecrire("cc_rb_gros.jsonl", gros)), max_s=3.0)

    ko = res.count(False)
    print("\n%d/%d — %s" % (len(res) - ko, len(res),
                            "TOUT PASSE" if not ko else "%d RATE(S)" % ko))
    sys.exit(1 if ko else 0)


if __name__ == "__main__":
    main()
