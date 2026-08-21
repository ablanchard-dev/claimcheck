"""Preuve par MUTATION : le chemin de réfutation existe-t-il vraiment ?

Sur le transcript réel, claimcheck rend 0 réfutation — parce qu'il n'y a aucun
compte-rendu faux à y attraper. Un détecteur qui ne détecte rien sur son unique
corpus n'est pas un détecteur prouvé, c'est un détecteur non testé.

On prend donc des affirmations VRAIES du corpus, on les falsifie une par une, et on
exige que l'outil bascule. Si une mutation ne fait pas rougir, la garantie
correspondante est nommée mais pas prouvée.

    python test_mutation.py
"""
import sys

from claimcheck import INCONNU, REFUTE, VERIFIE, extract, judge

BILAN = "==== BILAN : 235 PASS / 0 FAIL ===="
PYTEST = "162 passed in 7.40s"
PUSH = ("To https://github.com/x/a.git\n   6a60fb5..b443640  main -> main\n"
        "To https://github.com/x/b.git\n   2ffc439..b2f1b12  main -> main")


def check(nom, texte, evidence, attendu):
    claims = judge(extract(texte), evidence)
    if not claims:
        print(f"  [RATE] {nom} -- aucune affirmation extraite")
        return False
    got = claims[0].state
    ok = got == attendu
    print(f"  [{'OK  ' if ok else 'RATE'}] {nom} -> {got}"
          f"{'' if ok else f' (attendu {attendu})'}")
    if not ok:
        print(f"         motif : {claims[0].evidence}")
    return ok


def main():
    print("Temoins -- doivent PASSER (l'outil ne doit pas accuser le vrai)")
    r = [
        check("235 PASS, sortie qui le porte", "235 PASS", [BILAN], VERIFIE),
        check("162 tests verts, sortie qui le porte", "162 tests verts", [PYTEST], VERIFIE),
        check("2 depots pousses, 2 pushes reels", "2 depots pousses", [PUSH], VERIFIE),
        check("intention au futur", "je vais pousser les 9 depots", [PUSH], INCONNU),
    ]

    print("\nMutations -- doivent REFUTER (sinon la garantie est nommee, pas prouvee)")
    r += [
        check("le compte de tests est fausse", "999 tests verts", [PYTEST], REFUTE),
        check("le BILAN est fausse", "500 PASS", [BILAN], REFUTE),
        check("plus de depots annonces que pousses", "9 depots pousses", [PUSH], REFUTE),
        check("moins de depots annonces que pousses", "1 depot pousse", [PUSH], REFUTE),
        check("zero echec alors que le lanceur echoue",
              "0 fail", ["3 failed, 10 passed"], REFUTE),
    ]

    print("\nBords -- l'absence de preuve n'est jamais une refutation")
    r += [
        check("aucune sortie du tout", "162 tests verts", [], INCONNU),
        check("commit jamais vu", "162 tests verts", ["ls -la"], INCONNU),
        check("referent indetermine : commits, pas depots",
              "8 commits pousses", [PUSH], INCONNU),
    ]

    r += test_citation()

    ko = r.count(False)
    print(f"\n{len(r) - ko}/{len(r)} — {'TOUT PASSE' if not ko else str(ko) + ' RATE(S)'}")
    sys.exit(1 if ko else 0)



def test_citation():
    """CITER n'est pas AFFIRMER. Trouve en installant le hook pour de vrai : un message
    qui expliquait l'outil citait « 235 PASS » en exemple, et l'outil a refute sa propre
    documentation."""
    print("\nCitations -- l'outil ne doit jamais accuser un exemple")
    G, D = chr(171), chr(187)
    r = [
        check("exemple entre guillemets francais",
              "il reconnait " + G + "300 tests verts" + D + " comme forme",
              [PYTEST], INCONNU),
        # La typographie francaise met une ESPACE dans les guillemets. La v1 du
        # correctif exigeait l'adjacence stricte et ratait donc le cas reel.
        check("guillemets francais AVEC espaces",
              "il reconnait " + G + " 300 tests verts " + D + " comme forme",
              [PYTEST], INCONNU),
        check("exemple entre guillemets droits",
              'il reconnait "300 tests verts" comme forme', [PYTEST], INCONNU),
        check("exemple entre backticks",
              "il reconnait `300 tests verts` comme forme", [PYTEST], INCONNU),
        check("mais une VRAIE affirmation reste jugee",
              "J'ai lance : 300 tests verts.", [PYTEST], REFUTE),
    ]
    return r

if __name__ == "__main__":
    main()
