"""Banc unique : les trois bancs, plus la défense des chiffres du README.

Un chiffre écrit à la main dans un README est une dette : il est vrai le jour où on
l'écrit et faux la semaine suivante, sans que rien ne le signale. Ce banc lit les
chiffres annoncés dans README.md et les compare à ce que le code produit MAINTENANT.
Si le README ment, ce fichier rougit.

    python check_all.py          # code de retour 0 si tout passe, 1 sinon
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import tempfile

ICI = os.path.dirname(os.path.abspath(__file__))
TRANSCRIPT = (r"C:\Users\blanc\.claude\projects\C--Users-blanc"
              r"\f3f76cf7-0caa-4aaa-b57f-6b8b13004952.jsonl")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

resultats = []


def bilan(nom, ok, detail=""):
    resultats.append(ok)
    print(("  [OK  ] " if ok else "  [RATE] ") + nom + (("  -- " + detail) if detail else ""))
    return ok


def _faux_transcript(sortie):
    """Un tour minimal portant UNE sortie d'outil. Fabriquer le faux est le seul moyen
    de tester un détecteur de faux — mesuré au tour 11 : sur des données saines il ne
    trouve rien et paraît parfait."""
    p = os.path.join(tempfile.gettempdir(), "cc_bench_%d.jsonl" % abs(hash(sortie)))
    lignes = [
        {"type": "user", "message": {"role": "user", "content": "vas-y"}},
        {"type": "assistant",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "1", "content": sortie, "is_error": False}]}},
    ]
    with io.open(p, "w", encoding="utf-8") as f:
        for l in lignes:
            f.write(json.dumps(l) + "\n")
    return p


def banc_mutation():
    print("\n1. Preuve par mutation")
    r = subprocess.run([sys.executable, "test_mutation.py"], cwd=ICI,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"(\d+)/(\d+)", r.stdout or "")
    if not m:
        return bilan("test_mutation.py", False, "sortie illisible"), 0, 0
    n, tot = int(m.group(1)), int(m.group(2))
    bilan("test_mutation.py", r.returncode == 0 and n == tot, f"{n}/{tot}")
    return None, n, tot


def banc_hook():
    print("\n2. Hook Stop, JSON sur stdin")
    vert = _faux_transcript("162 passed in 7.40s")
    rouge = _faux_transcript("3 failed, 159 passed in 8.1s")
    cas = [("compte-rendu faux", "J'ai lance la suite : 9999 tests verts.", vert, True),
           ("compte-rendu vrai", "J'ai lance la suite : 162 tests verts.", vert, False),
           ("intention", "Prochain tour : pousser les 9 depots.", vert, False),
           ("0 fail contredit", "Tout est vert, 0 fail.", rouge, True),
           ("0 fail confirme", "Tout est vert, 0 fail.", vert, False)]
    n = 0
    for nom, msg, tp, doit_bloquer in cas:
        p = json.dumps({"hook_event_name": "Stop", "last_assistant_message": msg,
                        "transcript_path": tp})
        r = subprocess.run([sys.executable, "claimcheck.py", "--hook"], cwd=ICI, input=p,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        bloque = '"block"' in (r.stdout or "")
        n += bilan(nom, bloque == doit_bloquer,
                   "bloque" if bloque else "passe")
    return n, len(cas)


def banc_corpus():
    print("\n3. Corpus réel : aucun faux positif")
    if not os.path.exists(TRANSCRIPT):
        bilan("transcript introuvable", False, TRANSCRIPT)
        return None, None, None
    r = subprocess.run([sys.executable, "claimcheck.py", TRANSCRIPT], cwd=ICI,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = r.stdout or ""
    ref = re.search(r"REFUTE\s*:\s*(\d+)", out)
    tours = re.search(r"BILAN sur (\d+) tours", out)
    couv = re.search(r"reconnues\s*:\s*(\d+)\s+\((\d+)% du vérifiable, (\d+)% du total\)", out)
    nb_ref = int(ref.group(1)) if ref else -1
    bilan("0 réfutation sur le corpus réel", nb_ref == 0, f"{nb_ref} réfuté(s)")
    if not couv:
        bilan("ligne de couverture présente", False)
        return None, None, None
    bilan("la couverture est AFFICHÉE", True,
          f"{couv.group(2)}% du vérifiable, {couv.group(3)}% du total")
    return int(tours.group(1)) if tours else 0, int(couv.group(2)), int(couv.group(3))


def banc_readme(mut, tot_mut, hook_ok, hook_tot, tours, verif, total):
    """Les chiffres du README sont-ils encore vrais ?"""
    print("\n4. Le README dit-il encore la vérité ?")
    texte = io.open(os.path.join(ICI, "README.md"), encoding="utf-8").read()

    def annonce(motif, attendu, nom):
        m = re.search(motif, texte)
        if not m:
            return bilan(nom, False, "chiffre absent du README")
        lu = int(m.group(1))
        return bilan(nom, lu == attendu, f"README dit {lu}, mesuré {attendu}")

    annonce(r"Mutation proof.*?\|\s*(\d+)/\d+", mut, "compte de mutation")
    annonce(r"Hook, real JSON on stdin\s*\|\s*(\d+)/\d+", hook_ok, "compte du hook")
    annonce(r"(\d+)% of what is checkable", verif, "couverture du vérifiable")
    annonce(r"(\d+)% of all numeric sentences", total, "couverture du total")


def banc_tells():
    print("\n5. Aucune trace d'IA dans les fichiers publiables")
    # L'aiguille est ASSEMBLÉE à l'exécution : écrite en clair, le motif se trouverait
    # lui-même et ce fichier serait signalé à chaque passage. Un détecteur qui s'accuse
    # lui-même finit par être ignoré, et c'est ainsi qu'une vraie trace passe.
    motif = re.compile("|".join(["co-" + "authored-by", "generated" + " with",
                                 "\U0001F916"]), re.I)
    sales = []
    for f in os.listdir(ICI):
        if f.endswith((".py", ".md")):
            if motif.search(io.open(os.path.join(ICI, f), encoding="utf-8",
                                    errors="replace").read()):
                sales.append(f)
    bilan("grep tells IA", not sales, ", ".join(sales) or "aucun")


def main():
    print("=== claimcheck — banc complet ===")
    _, mut, tot_mut = banc_mutation()
    hook_ok, hook_tot = banc_hook()
    tours, verif, total = banc_corpus()
    if tours is not None:
        banc_readme(mut, tot_mut, hook_ok, hook_tot, tours, verif, total)
    banc_tells()

    ko = resultats.count(False)
    print(f"\n{len(resultats) - ko}/{len(resultats)} — "
          + ("TOUT PASSE" if not ko else f"{ko} RATE(S)"))
    sys.exit(1 if ko else 0)


if __name__ == "__main__":
    main()
