#imports
import numpy as np
import pandas as pd
import ast
import joblib

import database as db


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

def scale_features(features):
    column_to_normalize = ['file_size', 'image_width', 'image_height', 'mean_r', 'mean_g', 'mean_b', 'brightness', 'contraste_maximal',
     'contraste_global', 'saturation', 'edge_density', 'edge_density_opencv', 'max_r', 'max_g', 'max_b', 'min_r',
     'min_g', 'min_b', 'index_max_r', 'index_max_g', 'index_max_b', 'index_min_r', 'index_min_g', 'index_min_b',
     'max_lum', 'min_lum', 'index_max_lum', 'index_min_lum', 'sum_avg', 'sum_diff_avg', 'quantity_of_whites']
    values = []
    for col in column_to_normalize:
        values.append(features[col])
    values = np.array(values)
    values = values.reshape(1, -1)
    min_max_scaler = joblib.load('app/scaler_for_data.save')
    scaled_values = min_max_scaler.transform(values)
    scaled_values = scaled_values.reshape(-1)

    for i in range(len(column_to_normalize)):
        features[column_to_normalize[i]] = scaled_values[i]
    return features

# Définition des fonctions pour les poids

def score_to_three_class(score, thresholds):
    if score < thresholds[0]:
        clean_class = "propre"
        confidence = thresholds[0] - score
    elif thresholds[0] <= score <= thresholds[1]:
        clean_class = "sale"
        confidence = min(score - thresholds[0], thresholds[1] - score)
    else:
        clean_class = "debordante"
        confidence = score - thresholds[1]
    return clean_class, confidence

def compute_score(img_features, weights):
    cleaness_score = sum([img_features[k]*v for k,v in weights.items()])
    return cleaness_score*100

def predict_with_weight(row, weights, thresholds):
    y_pred, confidence = score_to_three_class(compute_score(row, weights), thresholds)
    return y_pred, confidence

# Définition des fonctions pour les règles

def score_to_two_class(score, threshold):
    if score < threshold:
        clean_class = "propre"
    else:
        clean_class = "sale"
    confidence = abs(score - threshold)
    return clean_class, confidence

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
    y_pred, confidence = score_to_two_class(apply_rule(row, rule), thresholds)
    return y_pred, confidence

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
    features = scale_features(features)

    # Règle de base si non définie : on va chercher les règles modifiables par
    # l'utilisateur dans la BDD (table classifier_rules / classifier_thresholds)
    if rules is None and nb_of_classes == 2:
        rules = db.get_classifier_rules()
        thresholds = db.get_classifier_thresholds("rules")

    # Poids de base si non définie : idem, on va chercher dans la BDD pour que
    # l'utilisateur puisse les modifier sans toucher au code
    if weights is None and nb_of_classes == 3:
        weights = db.get_classifier_weights()
        thresholds = db.get_classifier_thresholds("weights")


    if nb_of_classes == 2:
        prediction, confidence = predict_with_rules(features, rules, thresholds)
        return prediction, confidence

    elif nb_of_classes == 3:
        prediction, confidence = predict_with_weight(features, weights, thresholds)
        return prediction, confidence

    else:
        print("Le nombre de class indiqué n'est pas supporté")
        return "Erreur"