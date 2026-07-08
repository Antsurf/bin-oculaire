from PIL import Image, ImageStat, ImageFilter
import matplotlib.pyplot as plt
import os
import json
import numpy as np
import cv2
import requests

def get_histograms(file_path:str) -> dict:
    """
    Renvoie les histogrammes pour la visualisation dans la page result.html
    """
    histo_dic = {}
    img = Image.open(file_path).convert("RGB")
    r, g, b = img.split()
    r_histo = r.histogram()
    g_histo = g.histogram()
    b_histo = b.histogram()
    histo_dic["hist_rgb"] = json.dumps({
        "red":   r_histo,
        "green": g_histo,
        "blue":  b_histo,
    }) 

    gray = img.convert("L")
    histo_dic["luminance"] = json.dumps(gray.histogram())

    return histo_dic


def get_coords_from_address(address: str) -> tuple[float, float] | None:
    """
    Géocodage direct (adresse -> lat/lon). 
    Appelle l'API de géocodage de la Géoplateforme (IGN) et renvoie (lat, lon) ou None si erreur.

    NB: l'ancienne API api-adresse.data.gouv.fr est dépréciée (décommissionnement
    prévu fin janvier 2026) au profit de cette nouvelle API, qui reprend le même
    format de réponse GeoJSON.
    """
    try:
        response = requests.get(
            "https://data.geopf.fr/geocodage/search",
            params={"q": address, "limit": 1},
            timeout=5,
        )
        data = response.json()
        if data['features']:
            coords = data['features'][0]['geometry']['coordinates']
            return coords[1], coords[0]  # (lat, lon)
    except Exception as e:
        print(f"Erreur API géocodage (direct): {e}")
    return None


def get_address_from_coords(lat: float, lon: float) -> str | None:
    """
    Géocodage inverse (lat/lon -> adresse).
    Appelle l'API de géocodage de la Géoplateforme (IGN) et renvoie le libellé
    de l'adresse la plus proche des coordonnées données, ou None si aucune
    adresse n'est trouvée / en cas d'erreur.

    C'est ce qui manquait pour le cas des caméras (test_cas_reel.py) : elles
    fournissent seulement lat/lon (pas de texte d'adresse), donc il faut
    "remonter" jusqu'à une adresse à partir des coordonnées, plutôt que
    l'inverse.
    """
    try:
        response = requests.get(
            "https://data.geopf.fr/geocodage/reverse",
            params={"lon": lon, "lat": lat, "index": "address", "limit": 1},
            timeout=5,
        )
        data = response.json()
        if data['features']:
            return data['features'][0]['properties']['label']
    except Exception as e:
        print(f"Erreur API géocodage (reverse): {e}")
    return None

def extract_features(file_path: str) -> dict:
    """
    Taille de l'image : en ko
    Dimension de l'image: width x height en pixels
    Moyenne RGB : 3 canaux
    Luminosité RGB: basé sur le calcul REC601 (voir discord)
    Contraste de couleur: max(pixel) - min(pixel)
    Contraste global : écart type des pixels (0–255)
    Saturation : saturation moyenne HSV (0–255)
    Histogramme niveaux de gris : 256 valeurs (JSON)
    Histogramme RGB       : r/g/b × 256 valeurs (JSON)
    Histogramme luminance : 256 valeurs (JSON)
    Densité de contours   : % de pixels avec un bord détecté (0–1)
    Densité de contours (OpenCV) : nombre de pixels avec un bord détecté (0–N)
    
    :param file_path: uploads/...
    :return: dictionary with features of a specific image
    """
    features = dict()

    # File size
    features["file_size"] = round(os.path.getsize(file_path) / 1024, 2)

    # Image dimension
    img = Image.open(file_path).convert("RGB")
    features["image_width"], features["image_height"] = img.size

    # RGB, Couleur moyenne
    stat = ImageStat.Stat(img)
    features["mean_r"] = round(stat.mean[0],2)
    features["mean_g"] = round(stat.mean[1],2)
    features["mean_b"] = round(stat.mean[2],2)


    # Luminosité, valeur entre 0 et 255
    features["brightness"] = features["mean_r"] * 0.299 + features["mean_g"] * 0.587 + features["mean_b"] * 0.114

    # gray image 
    gray = img.convert("L")
    extrema = gray.getextrema()
    # Niveau de contraste 
    features["contraste_maximal"] = extrema[1] - extrema[0]
    features['contraste_global'] = float(np.std(gray))

    # Saturation moyenne
    img_hsv = img.convert("HSV")
    stat_hsv = ImageStat.Stat(img_hsv)
    features["saturation"] = round(stat_hsv.mean[1], 2)

    # Histogrammes RGB
    r, g, b = img.split()
    r_histo = r.histogram()
    g_histo = g.histogram()
    b_histo = b.histogram()
    features["hist_rgb"] = json.dumps({
        "red":   r_histo,
        "green": g_histo,
        "blue":  b_histo,
    })

    # Histogramme luminance
    features["hist_luminance"] = json.dumps(gray.histogram())


    # Contours de l'image
    # % en fonction des pixels actifs (bords détectés)
    # Valeur élevée = image complexe/chargée (poubelle pleine)
    edge_img = gray.filter(ImageFilter.FIND_EDGES)
    stat_edge = ImageStat.Stat(edge_img)
    features["edge_density"] = round(stat_edge.mean[0] / 255.0, 4)
    # on force le passage en int pour éviter les problèmes de JSON avec numpy.int64 et stockage dans la base de données
    features['edge_density_opencv'] = int(np.sum(cv2.Canny(np.array(gray), 50, 150)>0))

    return features


def show_histo(features: dict) -> None:
    """
    Montre le graphiques des histogrammes RGB
    :param features: dict retourné par extract_features() 
    """
    hist = json.loads(features["hist_rgb"])
    plt.figure(figsize=(8, 4))
    plt.plot(hist["red"],   label="Rouge", color="red",   alpha=0.7)
    plt.plot(hist["green"], label="Vert",  color="green", alpha=0.7)
    plt.plot(hist["blue"],  label="Bleu",  color="blue",  alpha=0.7)
    plt.xlabel("Intensité (0–255)")
    plt.ylabel("Nombre de pixels")
    plt.title("Histogrammes RGB")
    plt.legend()
    plt.tight_layout()
    plt.show()


def features_summary(features: dict) -> str:
    """Résume des features dans la console (pas en .json)"""
    return (
        f"Taille        : {features['file_size']} Ko\n"
        f"Dimensions    : {features['image_width']} x {features['image_height']} px\n"
        f"Moyenne RGB   : R={features['mean_r']}  G={features['mean_g']}  B={features['mean_b']}\n"
        f"Luminosité    : {features['brightness']}\n"
        f"Contraste     : {features['contraste_maximal']} / 255\n"
        f"Contraste global : {features['contraste_global']}\n"
        f"Saturation    : {features['saturation']}\n"
        f"Densité bords : {features['edge_density']}\n"
        f"Densité bords (OpenCV) : {features['edge_density_opencv']}"
    )


def enregistrement_json(features: dict, output_path: str):
    """
    Sauvegarde les features dans un fichier JSON (uniquement pour faire des tests !)
    :param features: dict retourné par extract_features()
    :param output_path: chemin complet du fichier .json à créer
    """
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(features, f, indent=4, ensure_ascii=False)
    print(f"Features sauvegardées dans : {output_path}")




if __name__ == "__main__":
    path = input("Chemin de l'image : ").replace("\\", "/")
    features = extract_features(path)
    print(features_summary(features))

    # Sauvegarde JSON dans le même dossier que l'image
    json_out = path.rsplit(".", 1)[0] + "_features.json"
    #enregistrement_json(features, json_out)

    # Affiche les histogrammes
    show_histo(features)