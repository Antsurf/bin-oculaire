"""
features.py — Extraction de caractéristiques visuelles sans ML.

Toutes les features sont calculées avec Pillow + la bibliothèque standard.
Aucun modèle de machine learning n'est utilisé.
"""

import os
import math
from PIL import Image, ImageFilter, ImageStat


# ─── Paramètres globaux ────────────────────────────────────────────────────────

# Taille max pour le calcul des features (accélère le traitement sans perte significative)
ANALYSIS_SIZE = (512, 512)


# ─── Fonction principale ───────────────────────────────────────────────────────

def extract_features(filepath: str) -> dict:
    """
    Extrait toutes les caractéristiques visuelles d'une image.

    Retourne un dict avec :
      - file_size_kb  : taille du fichier en Ko
      - width, height : dimensions originales en pixels
      - mean_r/g/b    : moyenne des canaux Rouge, Vert, Bleu (0–255)
      - brightness    : luminosité perçue (formule ITU-R BT.601)
      - contrast      : écart-type des niveaux de gris (dispersion des pixels)
      - saturation    : saturation moyenne HSV (0–255)
      - edge_density  : densité de contours (% de pixels avec contour fort)
    """
    features = {}

    # ── 1. Taille du fichier ────────────────────────────────────────────────
    features["file_size_kb"] = round(os.path.getsize(filepath) / 1024, 2)

    # ── 2. Dimensions originales ────────────────────────────────────────────
    img = Image.open(filepath).convert("RGB")
    features["width"], features["height"] = img.size

    # Redimensionne pour l'analyse (plus rapide, résultats cohérents)
    img_small = img.copy()
    img_small.thumbnail(ANALYSIS_SIZE, Image.LANCZOS)

    # ── 3. Couleur moyenne (canaux R, G, B) ─────────────────────────────────
    stat = ImageStat.Stat(img_small)
    features["mean_r"] = round(stat.mean[0], 2)
    features["mean_g"] = round(stat.mean[1], 2)
    features["mean_b"] = round(stat.mean[2], 2)

    # ── 4. Luminosité perçue ─────────────────────────────────────────────────
    # Formule ITU-R BT.601 : l'œil est plus sensible au vert qu'au rouge ou bleu
    # Valeur entre 0 (noir pur) et 255 (blanc pur)
    features["brightness"] = round(
        0.299 * features["mean_r"] +
        0.587 * features["mean_g"] +
        0.114 * features["mean_b"],
        2
    )

    # ── 5. Contraste : écart-type sur le canal de luminosité ─────────────────
    # Un contraste élevé = image avec beaucoup de zones claires ET sombres
    # (typique d'une poubelle pleine avec déchets débordants et ombres)
    gray = img_small.convert("L")
    stat_gray = ImageStat.Stat(gray)
    features["contrast"] = round(stat_gray.stddev[0], 2)

    # ── 6. Saturation moyenne ─────────────────────────────────────────────────
    # Convertit en HSV et récupère le canal S (saturation)
    # Une saturation faible = image terne/grisâtre (poubelle vide souvent plus neutre)
    img_hsv = img_small.convert("HSV")
    stat_hsv = ImageStat.Stat(img_hsv)
    features["saturation"] = round(stat_hsv.mean[1], 2)

    # ── 7. Densité de contours ────────────────────────────────────────────────
    # Applique un filtre de détection de bords (Pillow FIND_EDGES)
    # puis calcule le % de pixels "actifs" (contour détecté)
    # Une densité élevée = beaucoup de bords = image complexe/chargée
    edge_img = gray.filter(ImageFilter.FIND_EDGES)
    stat_edge = ImageStat.Stat(edge_img)
    # Normalise par 255 pour obtenir une valeur entre 0 et 1
    features["edge_density"] = round(stat_edge.mean[0] / 255.0, 4)

    return features


# ─── Utilitaire de diagnostic ──────────────────────────────────────────────────

def features_summary(features: dict) -> str:
    """Retourne un résumé lisible des features extraites (pour debug/affichage)."""
    return (
        f"Taille: {features['file_size_kb']} Ko | "
        f"Dimensions: {features['width']}×{features['height']}px | "
        f"Luminosité: {features['brightness']:.1f} | "
        f"Contraste: {features['contrast']:.1f} | "
        f"Saturation: {features['saturation']:.1f} | "
        f"Contours: {features['edge_density']:.3f}"
    )