#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
rename_courbes.py

Ce script parcourt tous les sous-dossiers de "data/taxan/" nommés au format
   taxan_YYYY-MM-DD-HH-MM-SS
pour extraire leur timestamp, puis les associe à un utilisateur dont la
plage [Date d'enregistrement, Dernière mise à jour] (dans le fichier Excel
"data/visiteurs-aresia.xlsx") englobe ce timestamp. Ensuite, il renomme
tous les fichiers .png contenus dans chacun de ces sous-dossiers en
<ID>_courbe1.png, <ID>_courbe2.png, …, où <ID> est l'identifiant
de l'utilisateur trouvé.

Usage (depuis la racine du projet) :
    python3 scripts/rename_courbes.py [--excel <chemin_vers_excel>] [--taxan-dir <chemin_vers_taxan_dir>]

Si vous ne spécifiez pas d'arguments, il cherchera par défaut :
    Excel  =>  data/visiteurs-aresia.xlsx
    Taxan  =>  data/taxan/
"""

import os
import sys
import argparse
from datetime import datetime

import pandas as pd


def parse_datetime_from_foldername(foldername: str) -> datetime:
    """
    Extrait la date & l'heure depuis un nom de dossier du format :
        taxan_YYYY-MM-DD-HH-MM-SS
    et retourne un objet datetime correspondant.

    Exemple : "taxan_2025-06-03-14-14-57" → datetime(2025, 6, 3, 14, 14, 57)
    """
    prefix = "taxan_"
    if not foldername.startswith(prefix):
        raise ValueError(f"Le dossier '{foldername}' ne commence pas par '{prefix}'")
    ts_str = foldername[len(prefix):]  # ex. "2025-06-03-14-14-57"
    return datetime.strptime(ts_str, "%Y-%m-%d-%H-%M-%S")


def main():
    # -------------------------
    # 1) Analyse des arguments
    # -------------------------
    parser = argparse.ArgumentParser(
        description="Renomme automatiquement les fichiers .png de chaque sous-dossier 'taxan_YYYY-MM-DD-HH-MM-SS' "
                    "en <ID>_courbe1.png, <ID>_courbe2.png, … selon l'utilisateur trouvé dans l'Excel."
    )
    parser.add_argument(
        "--excel",
        "-e",
        type=str,
        default="visiteurs-aresia.xlsx",
        help="Chemin vers le fichier Excel (par défaut : visiteursaresia.xlsx)."
    )
    parser.add_argument(
        "--taxan-dir",
        "-t",
        type=str,
        default="taxan",
        help="Chemin vers le dossier contenant les sous-dossiers 'taxan_YYYY-MM-DD-HH-MM-SS' "
             "(par défaut : taxan/)."
    )
    args = parser.parse_args()

    excel_path = args.excel
    taxan_root = args.taxan_dir  # CORRECTION : erreur dans le script original

    # Vérifications rapides :
    if not os.path.isfile(excel_path):
        print(f"✖ ERREUR : Le fichier Excel '{excel_path}' n'existe pas.", file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(taxan_root):
        print(f"✖ ERREUR : Le dossier '{taxan_root}' n'existe pas ou n'est pas un dossier.", file=sys.stderr)
        sys.exit(1)

    print(f"> Chargement du fichier Excel : '{excel_path}'")
    # -------------------------------------------------
    # 2) Lecture de l'Excel et parsing des dates
    # -------------------------------------------------
    try:
        # On suppose que le fichier Excel contient au moins les colonnes :
        #   "ID", "Date d'enregistrement", "Dernière mise à jour"
        df = pd.read_excel(excel_path, sheet_name="Visiteurs ARESIA", dtype={"ID": str})
    except Exception as exc:
        print(f"✖ ERREUR : Impossible de lire l'Excel : {exc}", file=sys.stderr)
        sys.exit(1)

    # Vérification des colonnes attendues
    required_cols = {"ID", "Date d'enregistrement", "Dernière mise à jour"}
    missing = required_cols - set(df.columns)
    if missing:
        print(f"✖ ERREUR : Colonnes manquantes dans l'Excel : {missing}", file=sys.stderr)
        print(f"Colonnes disponibles : {list(df.columns)}", file=sys.stderr)
        sys.exit(1)

    # Conversion des colonnes en datetime avec gestion des formats multiples
    try:
        # Format principal attendu : 2025-05-28T14:14:21.712Z
        df["Date d'enregistrement"] = pd.to_datetime(
            df["Date d'enregistrement"], 
            format="%Y-%m-%dT%H:%M:%S.%fZ",
            errors='coerce'  # Les erreurs deviennent NaT
        )
        
        # Si certaines dates n'ont pas pu être parsées, essayer sans les millisecondes
        mask_nan = df["Date d'enregistrement"].isna()
        if mask_nan.any():
            df.loc[mask_nan, "Date d'enregistrement"] = pd.to_datetime(
                df.loc[mask_nan, "Date d'enregistrement"], 
                format="%Y-%m-%dT%H:%M:%SZ",
                errors='coerce'
            )
        
        # Même traitement pour "Dernière mise à jour"
        df["Dernière mise à jour"] = pd.to_datetime(
            df["Dernière mise à jour"], 
            format="%Y-%m-%dT%H:%M:%S.%fZ",
            errors='coerce'
        )
        
        mask_nan = df["Dernière mise à jour"].isna()
        if mask_nan.any():
            df.loc[mask_nan, "Dernière mise à jour"] = pd.to_datetime(
                df.loc[mask_nan, "Dernière mise à jour"], 
                format="%Y-%m-%dT%H:%M:%SZ",
                errors='coerce'
            )
            
    except Exception as exc:
        print(f"✖ ERREUR : Impossible de parser les dates dans l'Excel : {exc}", file=sys.stderr)
        sys.exit(1)

    # Supprimer les lignes avec des dates invalides
    df = df.dropna(subset=["Date d'enregistrement", "Dernière mise à jour"])
    
    # On s'assure que l'ID est une chaîne de caractères (str)
    df["ID"] = df["ID"].astype(str)

    print(f"> {len(df)} enregistrements d'utilisateurs chargés depuis l'Excel.\n")

    # Afficher quelques exemples pour debug
    print("Exemples d'enregistrements :")
    for i in range(min(3, len(df))):
        row = df.iloc[i]
        print(f"  ID: {row['ID']}")
        print(f"  Enregistrement: {row['Date d\'enregistrement']}")
        print(f"  Dernière MAJ: {row['Dernière mise à jour']}")
        print()

    # -------------------------------------------------
    # 3) Parcours des dossiers "taxan_*" et renommage
    # -------------------------------------------------
    if not os.path.exists(taxan_root):
        print(f"✖ ERREUR : Le dossier '{taxan_root}' n'existe pas.", file=sys.stderr)
        sys.exit(1)
        
    dossiers = os.listdir(taxan_root)
    dossiers.sort()
    total_dossiers = 0
    total_png_renommes = 0
    total_non_trouves = 0
    total_conflits = 0

    for entry in dossiers:
        full_path = os.path.join(taxan_root, entry)
        if not os.path.isdir(full_path):
            continue
        if not entry.startswith("taxan_"):
            continue

        total_dossiers += 1

        # a) Extraction de la date/heure depuis le nom du dossier
        try:
            dossier_dt = parse_datetime_from_foldername(entry)
        except ValueError as e:
            print(f"[!] Ignore '{entry}' : {e}", file=sys.stderr)
            total_non_trouves += 1
            continue

        print(f"\n> Traitement du dossier '{entry}' (timestamp: {dossier_dt})")

        # b) Filtrer le(s) utilisateur(s) correspondants
        # La condition est : Date d'enregistrement <= timestamp du dossier <= Dernière mise à jour
        mask = (
            (df["Date d'enregistrement"] <= dossier_dt)
            & (dossier_dt <= df["Dernière mise à jour"])
        )
        candidats = df[mask]

        if len(candidats) == 0:
            # Aucun utilisateur trouvé
            print(f"[!] Aucun utilisateur pour '{entry}' (timestamp = {dossier_dt})", file=sys.stderr)
            print("    Plages disponibles :")
            for _, row in df.iterrows():
                print(f"    - {row['ID']}: {row['Date d\'enregistrement']} → {row['Dernière mise à jour']}")
            total_non_trouves += 1
            continue

        if len(candidats) > 1:
            # Plusieurs utilisateurs trouvés (intervalles qui se chevauchent)
            print(f"[!] Conflit (plusieurs IDs) pour '{entry}' → {candidats['ID'].tolist()}", file=sys.stderr)
            total_conflits += 1
            # On choisit de prendre le premier ID (on peut changer la logique si besoin)
        
        user_id = candidats.iloc[0]["ID"]
        print(f"→ Utilisateur trouvé : ID={user_id}")

        # c) Lister tous les fichiers .png dans ce dossier
        png_files = [
            f for f in os.listdir(full_path)
            if os.path.isfile(os.path.join(full_path, f)) and f.lower().endswith(".png")
        ]
        if not png_files:
            print(f"   (aucun .png trouvé dans '{entry}')")
            continue

        # On trie pour garantir un ordre stable de numérotation
        png_files.sort()
        print(f"   Fichiers PNG trouvés : {png_files}")

        # d) Renommer chacun en "<ID>_courbe<i>.png"
        for idx, old_fname in enumerate(png_files, start=1):
            old_fpath = os.path.join(full_path, old_fname)
            new_fname = f"{user_id}_courbe{idx}.png"
            new_fpath = os.path.join(full_path, new_fname)

            if os.path.exists(new_fpath) and old_fpath != new_fpath:
                # Ne pas écraser un fichier déjà présent (sauf si c'est le même)
                print(f"   [!] Le fichier existe déjà : '{new_fpath}' → non renommé")
                continue

            if old_fpath == new_fpath:
                print(f"   - '{old_fname}' → déjà au bon nom")
                continue

            try:
                os.rename(old_fpath, new_fpath)
                print(f"   ✓ '{old_fname}' → '{new_fname}'")
                total_png_renommes += 1
            except Exception as exc:
                print(f"   [!] Erreur en renommant '{old_fname}' : {exc}")

    # -------------------------------------------------
    # 4) Récapitulatif
    # -------------------------------------------------
    print("\n" + "="*50)
    print("RÉCAPITULATIF")
    print("="*50)
    print(f"Nombre de dossiers 'taxan_*' traités : {total_dossiers}")
    print(f"  • Fichiers .png renommés            : {total_png_renommes}")
    print(f"  • Dossiers sans correspondance      : {total_non_trouves}")
    print(f"  • Dossiers avec conflit d'IDs       : {total_conflits}")
    print("="*50)

    if total_non_trouves > 0:
        print(f"\n⚠️  {total_non_trouves} dossier(s) n'ont pas pu être associés à un utilisateur.")
        print("   Vérifiez que les plages temporelles dans l'Excel couvrent bien les timestamps des dossiers.")
    
    if total_conflits > 0:
        print(f"\n⚠️  {total_conflits} dossier(s) correspondent à plusieurs utilisateurs.")
        print("   Le script a choisi le premier utilisateur trouvé. Vérifiez les plages temporelles.")


if __name__ == "__main__":
    main()