#imports
import numpy as np
import pandas as pd
import ast

def get_whites_from_hist(hist):
    red = np.array(hist['red'])
    green = np.array(hist['green'])
    blue = np.array(hist['blue'])
    diff = abs(red -green) + abs(red - blue) + abs(green-blue)
    mean = (red + green + blue)/3
    whites = sum(((mean - diff)>0))
    return whites

def get_features(features_dict):

    features_dict['max_r'] = max(ast.literal_eval(features_dict['hist_rgb'])['red'])
    features_dict['max_g'] = max(ast.literal_eval(features_dict['hist_rgb'])['green'])
    features_dict['max_b'] = max(ast.literal_eval(features_dict['hist_rgb'])['blue'])

    features_dict['min_r'] = min(ast.literal_eval(features_dict['hist_rgb'])['red'])
    features_dict['min_g'] = min(ast.literal_eval(features_dict['hist_rgb'])['green'])
    features_dict['min_b'] = min(ast.literal_eval(features_dict['hist_rgb'])['blue'])

    features_dict['index_max_r'] = ast.literal_eval(features_dict['hist_rgb'])['red'].index(features_dict['max_r'])
    features_dict['index_max_g'] = ast.literal_eval(features_dict['hist_rgb'])['green'].index(features_dict['max_g'])
    features_dict['index_max_b'] = ast.literal_eval(features_dict['hist_rgb'])['blue'].index(features_dict['max_b'])

    features_dict['index_min_r'] = ast.literal_eval(features_dict['hist_rgb'])['red'].index(features_dict['min_r'])
    features_dict['index_min_g'] = ast.literal_eval(features_dict['hist_rgb'])['green'].index(features_dict['min_g'])
    features_dict['index_min_b'] = ast.literal_eval(features_dict['hist_rgb'])['blue'].index(features_dict['min_b'])

    features_dict['max_lum'] = max(ast.literal_eval(features_dict['hist_luminance']))
    features_dict['min_lum'] = min(ast.literal_eval(features_dict['hist_luminance']))

    features_dict['index_max_lum'] = ast.literal_eval(features_dict['hist_luminance']).index(features_dict['max_lum'])
    features_dict['index_min_lum'] = ast.literal_eval(features_dict['hist_luminance']).index(features_dict['min_lum'])

    features_dict['sum_avg'] = features_dict['mean_r'] + features_dict['mean_g'] + features_dict['mean_b']
    features_dict['sum_diff_avg'] = abs(features_dict['mean_r'] - features_dict['mean_g']) + abs(features_dict['mean_r'] - features_dict['mean_b']) + abs(features_dict['mean_b'] - features_dict['mean_g'])

    features_dict['quantity_of_whites'] = get_whites_from_hist(ast.literal_eval(features_dict['hist_rgb']))

    return features_dict

# Définition des fonctions pour les poids

def score_to_three_class(score, thresholds):
    if score < thresholds[0]:
        clean_class = "propre"
    elif thresholds[0] <= score <= thresholds[1]:
        clean_class = "sale"
    else:
        clean_class = "debordante"
    return clean_class

def compute_score(img_features, weights):
    cleaness_score = sum([img_features[k]*v for k,v in weights.items()])
    return cleaness_score*100

def predict_with_weight(row, weights, thresholds):
    y_pred = score_to_three_class(compute_score(row, weights), thresholds)
    return y_pred

# Définition des fonctions pour les règles

def score_to_two_class(score, threshold):
    if score < threshold:
        clean_class = "propre"
    else:
        clean_class = "sale"
    return clean_class

def apply_rule(row,rule):
    score = 0
    for elem, value in rule.items():
        if value['sign'] == ">":
            if row[elem] > value['threshold']:
                score += value['score']
        else:
            if row[elem] < value['threshold']:
                score += value['score']
    return score

def predict_with_rules(row, rule, thresholds):
    y_pred = score_to_two_class(apply_rule(row, rule), thresholds)
    return y_pred

def classify(features, nb_of_classes = 2, weights = None, rules = None, thresholds = None):
    """
    Fonction pour classifier une image de poubelle.

    :param features:
        éléments de l'image extrait au préalable
    :param nb_of_classes:
        2: propre, sale
        3: propre, sale, debordante
    :param weights:
        Les possibles poids que l'utilisateur peut indiquer
    :param rules:
        Les possibles règles que l'utilisateur peut indiquer
    :return:
        La classe de l'image: propre, sale ou debordante
    """

    # Ajout de différent élément supplémentaire à nos features
    features = get_features(features)

    # Règle de base si non définies
    if rules is None and nb_of_classes == 2:
        rules = {
            'mean_r': {'threshold': 0.4150344801743592, 'sign': '>', 'score': 0.0},
            'mean_g': {'threshold': 0.37576611164675755, 'sign': '<', 'score': 5.0},
            'brightness': {'threshold': 0.3081680996813572, 'sign': '>', 'score': 0.0},
            'contraste_global': {'threshold': 0.8825309043036617, 'sign': '>', 'score': 4.006880156485172},
            'edge_density_opencv': {'threshold': 0.07458731202114097, 'sign': '>', 'score': 3.016836491962818},
            'max_r': {'threshold': 0.35701858263043873, 'sign': '>', 'score': 5.0},
            'max_g': {'threshold': 0.5711799355230485, 'sign': '<', 'score': 1.3194733615860947},
            'max_b': {'threshold': 0.2906460917001866, 'sign': '<', 'score': 5.0},
            'min_r': {'threshold': 0.8325647870174255, 'sign': '>', 'score': 5.0},
            'min_g': {'threshold': 0.4132767987860906, 'sign': '<', 'score': 1.4018698389974804},
            'min_b': {'threshold': 0.8781258552989745, 'sign': '<', 'score': 0.4617996469677823},
            'index_max_r': {'threshold': 0.2169395594693997, 'sign': '<', 'score': 5.0},
            'index_max_g': {'threshold': 0.5592029408562174, 'sign': '<', 'score': 2.9971308149598004},
            'max_lum': {'threshold': 0.05198941915700317, 'sign': '<', 'score': 0.0},
            'min_lum': {'threshold': 0.4698152878443205, 'sign': '<', 'score': 0.8497127013463754},
            'index_max_lum': {'threshold': 0.9333318980617655, 'sign': '<', 'score': 2.897761468964595},
            'index_min_lum': {'threshold': 0.6180389106981365, 'sign': '<', 'score': 5.0},
            'sum_avg': {'threshold': 0.7096892789474282, 'sign': '<', 'score': 1.3021515119621079},
            'quantity_of_whites': {'threshold': 0.13134950971169676, 'sign': '>', 'score': 3.050209399787727}
        }
        thresholds = 22

    # Poids de base si non définis
    if weights is None and nb_of_classes == 3:
        weights = {
            'mean_r': np.float64(0.01376422371403685),
            'mean_g': 0.0,
            'brightness': 0.0,
            'contraste_global': np.float64(0.7199924014556374),
            'edge_density_opencv': np.float64(0.4704017524096923),
            'max_r': 0.0,
            'max_g': np.float64(0.30272728971973906),
            'max_b': 0.0,
            'min_r': 1.0,
            'min_g': np.float64(0.41345849348853436),
            'min_b': 0.870891282988038,
            'index_max_r': 0.0,
            'index_max_g': np.float64(0.01748784218304835),
            'max_lum': 0.0,
            'min_lum': 1.0,
            'index_max_lum': 0.0,
            'index_min_lum': np.float64(0.047498647545156876),
            'sum_avg': 0.0,
            'quantity_of_whites': np.float64(0.13373255391552297)
        }
        thresholds = [50, 84]


    if nb_of_classes == 2:
        prediction = predict_with_rules(features, rules, thresholds)
        return prediction

    elif nb_of_classes == 3:
        prediction = predict_with_weight(features, weights, thresholds)
        return prediction

    else:
        print("Le nombre de class indiqué n'est pas supporté")
        return "Erreur"