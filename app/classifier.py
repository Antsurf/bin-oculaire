from features import *
import pandas as pd
import os

def get_dataframe() -> dict:
    dict_dataframe = {}

    path_clean = "../Data/train/with_label/clean"
    for e in os.scandir(path_clean):
        if e.is_file():
            dict_dataframe[e.name] = {}
            dict_dataframe[e.name]['name'] = e.name
            path = e.path
            features_img = extract_features(path)
            for key in features_img.keys():
                dict_dataframe[e.name][key] = features_img[key]
            dict_dataframe[e.name]['class'] = 'clean'

    path_dirty = "../Data/train/with_label/dirty"
    for e in os.scandir(path_dirty):
        if e.is_file():
            dict_dataframe[e.name] = {}
            dict_dataframe[e.name]['name'] = e.name
            path = e.path
            features_img = extract_features(path)
            for key in features_img.keys():
                dict_dataframe[e.name][key] = features_img[key]
            dict_dataframe[e.name]['class'] = 'dirty'

    return dict_dataframe

if __name__ == "__main__":
    dict_df = get_dataframe()
    print(dict_df)
