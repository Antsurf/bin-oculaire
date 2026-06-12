from PIL import Image, ImageStat, ImageFilter
import os


def extract_features(file_path: str) -> dict:
    """
    Taille de l'image : en ko
    Dimension de l'image: width x height en pixels
    Moyenne RGB : 3 canaux
    :param path: uploads/...
    :return: dictionary with features of a specific image
    """
    features = dict()

    # File size
    features["file_size"] = round(os.path.getsize(file_path) / 1024, 2)

    # Image dimension
    img = Image.open(file_path).convert("RGB")
    features["image_width"], features["image_height"] = img.size

    # RGB
    stat = ImageStat.Stat(img)
    features["moyenne_r"] = round(stat.mean[0], 2)
    features["moyenne_g"] = round(stat.mean[1], 2)
    features["moyenne_b"] = round(stat.mean[2], 2)

    return features


print(extract_features("C:/Users/Mathilde/Devs/Mastercamp/Binoculaire/Data/train/no_label/00007_00.jpg"))

def features_summary(features: dict) -> str:
    return (f"Taille:{features["file_size"]}"
            f"Dimensions: width {features["image_width"]}, height {features["image_height"]}"
            f"Moyenne RGB: rouge {features["moyenne_r"]}; vert {features["moyenne_g"]}; bleu {features["moyenne_b"]}"
        )