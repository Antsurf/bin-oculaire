from PIL import Image, ImageStat, ImageFilter
import matplotlib.pyplot as plt
import os
import json

path = input("Enter a path:")
path_test = path.replace("\\", "/")


def extract_features(file_path: str) -> dict:
    """
    Taille de l'image : en ko
    Dimension de l'image: width x height en pixels
    Moyenne RGB : 3 canaux
    Luminosité RGB: basé sur le calcul REC601 (voir discord)
    Contraste de couleur: max(pixel) - min(pixel)
    Saturation : saturation moyenne HSV (0–255)

    :param file_path: uploads/...
    :return: dictionary with features of a specific image
    """
    features = dict()

    # File size
    features["file_size"] = round(os.path.getsize(file_path) / 1024, 2)

    # Image dimension
    img = Image.open(file_path).convert("RGB")
    features["image_size"] = dict()
    features["image_size"]["image_width"], features["image_size"]["image_height"] = img.size

    # RGB, Couleur moyenne
    stat = ImageStat.Stat(img)
    features["moyennes_canaux"] = dict()
    features["moyennes_canaux"]["red"] = round(stat.mean[0], 2)
    features["moyennes_canaux"]["green"] = round(stat.mean[1], 2)
    features["moyennes_canaux"]["blue"] = round(stat.mean[2], 2)

    # Luminosité, valeur entre 0 et 255
    features["luminosity"] = features["moyennes_canaux"]["red"] * 0.299 + features["moyennes_canaux"]["green"] * 0.587 + features["moyennes_canaux"]["blue"] * 0.114

    # gray image 
    gray = img.convert("L")
    extrema = gray.getextrema()
    # Niveau de contraste 
    features["contraste"] = extrema[1] - extrema[0]

    # Saturation moyenne
    img_hsv = img.convert("HSV")
    stat_hsv = ImageStat.Stat(img_hsv)
    features["saturation"] = round(stat_hsv.mean[1], 2)

    # Histogrammes
    r, g, b = img.split()
    r_histo = r.histogram()
    g_histo = g.histogram()
    b_histo = b.histogram()
    features["histograms"] = dict()
    features["histograms"]["red"] = r_histo
    features["histograms"]["green"] = g_histo
    features["histograms"]["blue"] = b_histo
    #show_histo(r_histo, g_histo, b_histo)

    return features


def show_histo(r_histo,g_histo, b_histo):
    """
    Montre le graphiques des histogrammes RGB
    :param r_histo: liste (nb pixels VS intensité)
    :param g_histo: liste (nb pixels VS intensité)
    :param b_histo: liste (nb pixels VS intensité)

    """
    plt.plot(r_histo, label="Rouge", color="red")
    plt.plot(g_histo, label="Vert", color="green")
    plt.plot(b_histo, label="Bleu", color="blue")

    plt.xlabel("Intensité")
    plt.ylabel("Nombre de pixels")
    plt.title("Histogrammes RGB")
    plt.legend()
    plt.show()



dico = extract_features(path_test)

def features_summary(features: dict) -> str:
    return (f"Taille:{features["file_size"]}"
            f"Dimensions: width {features["image_size"]["image_width"]}, height {features["image_size"]["image_height"]}"
            f"Moyenne RGB: rouge {features["moyennes_canaux"]["red"]}; vert {features["moyennes_canaux"]["green"]}; bleu {features["moyennes_canaux"]["blue"]}"
            f"Luminosité: {features["luminosity"]}"
            f"Contraste: {features["contraste"]}"
            f"Saturation: {features["saturation"]}"
        )


def enregistrement_json(features: dict):
    json_path = path_test.split("Data")[0] + "Data_json/test.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(features, f, indent=4, ensure_ascii=False)

enregistrement_json(dico)


