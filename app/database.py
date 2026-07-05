import sqlite3
import os
import datetime

directory_db = os.path.dirname(os.path.abspath(__file__))
db_name = os.path.join(directory_db, "database.db")

def get_connection() -> dict:
    """
    Créer une connexion à la base SQLite 

    On doit obligatoirement activer les clés étrangères (foreign key constraints) en Python pour que cela fonctionne, d'où la ligne conn.execute("PRAGMA...")
    Si on ne l'active pas, on peut supprimer des éléments liés à des clés étrangers + ON DELETE CASCADE fonctionne pas
    Plus d'infos ici:
    https://sqlite.org/foreignkeys.html
    https://www.youtube.com/watch?v=FrTQSPSbVC0

    :return: un dico avec les colonnes comme clés 
    """
    conn = sqlite3.connect(db_name)
    conn.execute("PRAGMA foreign_keys = ON")

    # permet de convertir la conn en dictionnaire avec comme clé le nom de la colonne. 
    # ça évite d'avoir un tuple de l'enfer où il faut mémoriser l'index des colonnes 
    conn.row_factory = sqlite3.Row 
    return conn



def init_db():
    """
    Créer les tables sql si elles n'existent pas déjà 

    Important: avec sqlite, on doit obligatoire utiliser un curseur (cursor) pour faire des querys 
    On doit aussi faire conn.commit() et conn.close() pour appliquer les changements

    On pourrait activer l'autocommit mais pour l'instant si y'a un bug pendant la transaction, au moins rien n'est inséré

    Doc cursor: 
    https://docs.python.org/3/library/sqlite3.html

    execute() -> n'execute qu'une seule query 
    executescript() -> on peut executer plusieurs query (;)

    Important, executescript() ne prends pas les paramètres ? (ex: "INSERT INTO data VALUES(?)",rows)
    
    Ici on fait un gros execute script mais on aurait pu faire 4 execute
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript(""" 
    CREATE TABLE IF NOT EXISTS localisation(
       id_localisation   INTEGER PRIMARY KEY AUTOINCREMENT,
       latitude          REAL NOT NULL,
       longitude         REAL NOT NULL,
       localisation_nom  VARCHAR(100)
    );

    CREATE TABLE IF NOT EXISTS images(
       id                INTEGER PRIMARY KEY AUTOINCREMENT,
       file_path         VARCHAR(255) NOT NULL,
       file_name         VARCHAR(255) NOT NULL,
       upload_date       TEXT NOT NULL,
       id_localisation   INTEGER,
       FOREIGN KEY(id_localisation) REFERENCES localisation(id_localisation) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS images_classification(
       image_id          INTEGER PRIMARY KEY,
       annotation        VARCHAR(50),
       auto_label        VARCHAR(50),
       confidence        VARCHAR(50),
       FOREIGN KEY(image_id) REFERENCES images(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS images_features(
       image_id          INTEGER PRIMARY KEY,
       file_size         DECIMAL(10,2),
       width             INT,
       height            INT,
       mean_r            DECIMAL(5,2),
       mean_g            DECIMAL(5,2),
       mean_b            DECIMAL(5,2),
       luminosite        DECIMAL(5,2),
       contraste_maximal         DECIMAL(5,2),
       contraste_global          DECIMAL(5,2),
       saturation        DECIMAL(5,2),
       edge_density      DECIMAL(5,4),
       edge_density_opencv DECIMAL(5,4),
       FOREIGN KEY(image_id) REFERENCES images(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS classifier_rules(
       id                INTEGER PRIMARY KEY AUTOINCREMENT,
       feature_name      VARCHAR(50) NOT NULL UNIQUE,
       sign              VARCHAR(2) NOT NULL,
       threshold         DECIMAL(12,8) NOT NULL,
       score             DECIMAL(12,8) NOT NULL
    );

    CREATE TABLE IF NOT EXISTS classifier_weights(
       id                INTEGER PRIMARY KEY AUTOINCREMENT,
       feature_name      VARCHAR(50) NOT NULL UNIQUE,
       weight            DECIMAL(12,8) NOT NULL
    );

    CREATE TABLE IF NOT EXISTS classifier_thresholds(
       id                INTEGER PRIMARY KEY AUTOINCREMENT,
       model_type        VARCHAR(10) NOT NULL,
       threshold_order   INTEGER NOT NULL,
       threshold_value   DECIMAL(12,8) NOT NULL,
       UNIQUE(model_type, threshold_order)
    );""")


    conn.commit()

    conn.close()

    print(f"Base de donnée initialisée, chemin: {os.path.abspath(db_name)}")

    # on initialise les règles / poids / seuils par défaut si les tables sont vides
    seed_classifier_defaults()


def insert_image(file_path: str, file_name: str ,id_localisation: int = None) -> int:
    """
    Ajoute une image à la base de donnée (table images) et renvoie son ID 

    On renvoie l'id grâce à cursor.lastrowid qui récupère les ID générés par auto_increment
    https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlcursor-lastrowid.html

    :file_path: chemin du fichier en local
    :id_localisation: id de l'emplacement 

    :return: l'id de l'image qu'on vient d'insérer

    Pour un code plus clean, l'insertion des features etc... se fait dans les fonctions plus bas 
    on récupère l'id uniquement pour ça pour pouvoir insérer dans les autres tables
    """
    conn = get_connection()
    cursor = conn.cursor()

    # récupération de l'upload date (on considère qu'une fois que la photo est prise c'est directement upload)
    upload_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""INSERT INTO images (file_path, file_name, upload_date, id_localisation) VALUES (?,?,?,?)""", (file_path,file_name,upload_date,id_localisation))

    image_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return image_id

def add_localisation(latitude: float, longitude: float, loc_name: str) -> int:
    """
    Cette fonction ajoute dans la table localisation une nouvelle localisation quand une image
    ajoutée a un emplacement qui n'existe pas déjà. 

    :latitude: coordonnée en float de la latitude récupéré grâce à l'api du gouvernement 
    :longitude: coordonnée en float de la longitude récupéré grâce à l'api du gouvernement 
    :loc_name: nom de la localisation avec laquelle on extrait l'adresse 

    :return: renvoie l'id de la localisation dans la table pour ensuite pouvoir update
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""INSERT INTO localisation (latitude, longitude, localisation_nom) VALUES (?,?,?)""", (latitude, longitude, loc_name))

    localisation_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return localisation_id 

def get_localisation(latitude: float, longitude: float, tolerance = 0.0002) -> int:
    """
    Fonction pour récupérer une localisation dans la base de données 
    :latitude: coordonnée en float de la latitude
    :longitude: coordonnée en float de la longitude
    :tolerance: paramètre le plus important c'est pour éviter les doublons de base, on met 
    une tolérance de 0.0002 ça correspond à peu près à 20 mètres de différence 

    :return: l'id de la localisation 
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""SELECT id_localisation FROM localisation 
                   WHERE latitude BETWEEN ? AND ? 
                   AND longitude BETWEEN ? AND ?""",(latitude-tolerance,latitude+tolerance,longitude-tolerance,longitude+tolerance))

    row = cursor.fetchone()
    conn.close()

    return row["id_localisation"] if row else None


def add_features(image_id : int, features: dict) -> None: 
    """
    Insère le dictionnaire de features pour une image donnée (grâce à features.py) dans la tables images_features
    :image_id: id de l'image pour laquelle on ajoute les features extraites
    :features: dico contenant les features en question 
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""INSERT INTO images_features 
                   (image_id, file_size, width, height, mean_r, mean_g, mean_b, luminosite, contraste_maximal, contraste_global, saturation, edge_density, edge_density_opencv)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                   """, (
                       image_id,
                       features["file_size"],
                       features["image_width"],
                       features["image_height"],
                       features["mean_r"],
                       features["mean_g"],
                       features["mean_b"],
                       features["brightness"],
                       features["contraste_maximal"],
                       features["contraste_global"],
                       features["saturation"],
                       features["edge_density"],
                       features["edge_density_opencv"]
                   ))

    conn.commit()
    conn.close()

def update_annotation(image_id: int, annotation: str)->None:
    """
    Définit l’annotation d’une image (‘pleine’ ou ‘vide’),
    ou l’annule en passant annotation=None.
    """
    conn = get_connection()
    cursor = conn.cursor()

    if annotation not in ("pleine", "sale", "vide", "propre", "debordante", None):
        print("annotation doit être 'pleine', 'sale', 'vide', 'propre', 'debordante' ou None")
        conn.close()
        return

    # INSERT OR REPLACE au cas où l'image n'aurait pas encore de ligne dans images_classification
    # (par exemple si elle n'a pas encore été auto-labelisée)
    cursor.execute("""
        INSERT INTO images_classification (image_id, annotation)
        VALUES (?, ?)
        ON CONFLICT(image_id) DO UPDATE SET annotation = excluded.annotation
    """, (image_id, annotation))
    conn.commit()
    conn.close()

def update_autolabel(image_id:int, autolabel: str, confidence: str) -> None:
    """
    Insère ou met à jour le label du classifier dans la BDD (INSERT OR REPLACE)
    """
    conn = get_connection()
    conn.execute("""
        INSERT INTO images_classification (image_id, auto_label, confidence)
        VALUES (?, ?, ?)
        ON CONFLICT(image_id) DO UPDATE SET auto_label = excluded.auto_label, confidence = excluded.confidence
    """, (image_id, autolabel, confidence))  
    conn.commit()
    conn.close()

def get_all_images() -> list:
    """
    Ramène toutes les images de la BDD
    Renvoie un dictionnaire avec les différentes infos extraites en clé
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            i.id, 
            i.file_path, 
            i.file_name,
            i.upload_date,
            f.luminosite,
            f.contraste_maximal,
            f.contraste_global,
            f.edge_density,
            f.edge_density_opencv,
            c.auto_label,
            c.confidence
        FROM images i
        LEFT JOIN images_features f ON i.id = f.image_id
        LEFT JOIN images_classification c ON i.id = c.image_id
        ORDER BY i.upload_date DESC
    """)

    images = cursor.fetchall()
    conn.close()

    return images

def get_classified_count() -> tuple:
    """
    Fonction qui renvoie le nombre d'image classifiées en propre et en sale 
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            SUM(CASE WHEN auto_label = 'sale' THEN 1 ELSE 0 END) as count_sales,
            SUM(CASE WHEN auto_label = 'propre' THEN 1 ELSE 0 END) as count_propres,
            SUM(CASE WHEN auto_label = 'debordante' THEN 1 ELSE 0 END) as count_debordantes
        FROM images_classification
    """)
    row = cursor.fetchone()
    conn.close()
    
    return row["count_sales"], row["count_propres"], row["count_debordantes"]

def get_image_details(image_id):
    """Récupère les informations nécessaires pour la page de résultat."""
    conn = get_connection()
    query = """
        SELECT i.id, i.file_path, i.file_name, i.upload_date, f.file_size, f.width, f.height, 
               c.auto_label, c.confidence, c.annotation, f.luminosite, f.contraste_maximal, f.saturation, f.edge_density,
               l.latitude, l.longitude, l.localisation_nom
        FROM images i
        LEFT JOIN localisation l ON i.id_localisation = l.id_localisation
        LEFT JOIN images_features f ON i.id = f.image_id
        LEFT JOIN images_classification c ON i.id = c.image_id
        WHERE i.id = ?
    """
    row = conn.execute(query, (image_id,)).fetchone()
    conn.close()
    
    return dict(row) if row else None

def get_images_paginated(limit, offset):
    """
    Fonction pour récupérer les images avec pagination (donc limit et offset)
    comme la fonction get_all_images mais avec limit et offset pour la pagination
    :return: une liste de dictionnaires avec les infos des images
    """
    conn = get_connection()
    cursor = conn.cursor()
    query = """SELECT 
            i.id, 
            i.file_path, 
            i.file_name,
            i.upload_date,
            f.luminosite,
            f.contraste_maximal,
            f.contraste_global,
            f.edge_density,
            f.edge_density_opencv,
            c.auto_label,
            c.confidence,
            l.localisation_nom,
            l.latitude,
            l.longitude
        FROM images i
        LEFT JOIN images_features f ON i.id = f.image_id
        LEFT JOIN images_classification c ON i.id = c.image_id
        LEFT JOIN localisation l ON i.id_localisation = l.id_localisation
        ORDER BY i.upload_date ASC
        LIMIT ? OFFSET ?"""
    cursor.execute(query, (limit, offset))
    images = cursor.fetchall()
    conn.close()
    return images

def get_total_images_count():
    """
    Fonction pour récupérer le nombre total d'images dans la base de données
    :return: le nombre total d'images
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM images")
    count = cursor.fetchone()[0] # Récupère le nombre total
    conn.close()
    return count

def get_total_file_size() -> float:
    """
    Fonction qui renvoie la somme des tailles (en Ko) de toutes les images
    stockées localement, calculée directement en SQL (plus léger que de
    tout charger en mémoire avec get_stats()).
    :return: la taille totale en Ko (0 si aucune image)
    """
    conn = get_connection()
    cursor = conn.cursor()
    row = cursor.execute("SELECT SUM(file_size) AS total FROM images_features").fetchone()
    conn.close()
    return row["total"] or 0


def get_luminosite()->list:
    """
    Renvoie des infos sur la luminosité pour toutes les images
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT luminosite 
        FROM images_features 
        WHERE luminosite IS NOT NULL
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    return [row["luminosite"] for row in rows]

def get_stats()->dict:
    """Statistiques pour le dashboard.
    Renvoie un dictionnaire avec différents paramètres
    Nombre total d'images
    Nombre d'image auto labelisé
    Nombre d'image annotée 
    Taille totale de toutes les images (en Ko)
    """
    conn = get_connection()
    
    total = conn.execute("SELECT COUNT(*) AS n FROM images").fetchone()["n"]

    auto_counts = conn.execute(
        "SELECT auto_label, COUNT(*) AS n FROM images_classification GROUP BY auto_label"
    ).fetchall()

    manual_counts = conn.execute(
        """
        SELECT annotation AS label, COUNT(*) AS n
        FROM images_classification
        WHERE annotation IS NOT NULL
        GROUP BY annotation
        """
    ).fetchall()

    file_sizes = [
        row["file_size"]
        for row in conn.execute("SELECT file_size FROM images_features").fetchall()
    ]

    conn.close() 

    return {
        "total_images": total,
        "automatic_labels": {r["auto_label"]: r["n"] for r in auto_counts if r["auto_label"] is not None}, # Corrigé
        "manual_annotations": {r["label"]: r["n"] for r in manual_counts},
        "file_sizes": file_sizes,
    }



#=================================
# A PARTIR DE LA NE RIEN TOUCHER, C'EST LE CODE DU CLASSIFIER
# UNE MODIFICATION DE CES VALEURS DOIT SE FAIRE DANS LA BDD, PAS DANS LE CODE
# SINON LE CLASSIFIER NE SERA PAS A JOUR ET LES MODIFICATIONS SERONT PERDUES AU PROCHAIN DEPLOIEMENT ET L'ALGORITHME NE SERA PAS A JOUR
# Gestion des règles / poids / seuils du classifier (table modifiable par
# l'utilisateur, plutôt que des dictionnaires codés en dur dans classifier.py)
#================================

# Valeurs par défaut (reprises de l'ancien classifier.py) utilisées uniquement
# pour peupler la base la toute première fois
_DEFAULT_RULES = {
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
_DEFAULT_RULES_THRESHOLD = 22  # seuil du modèle 2-classes (propre / sale)

_DEFAULT_WEIGHTS = {
    'mean_r': 0.01376422371403685,
    'mean_g': 0.0,
    'brightness': 0.0,
    'contraste_global': 0.7199924014556374,
    'edge_density_opencv': 0.4704017524096923,
    'max_r': 0.0,
    'max_g': 0.30272728971973906,
    'max_b': 0.0,
    'min_r': 1.0,
    'min_g': 0.41345849348853436,
    'min_b': 0.870891282988038,
    'index_max_r': 0.0,
    'index_max_g': 0.01748784218304835,
    'max_lum': 0.0,
    'min_lum': 1.0,
    'index_max_lum': 0.0,
    'index_min_lum': 0.047498647545156876,
    'sum_avg': 0.0,
    'quantity_of_whites': 0.13373255391552297
}
_DEFAULT_WEIGHTS_THRESHOLDS = [50, 84]  # seuils du modèle 3-classes (propre / sale / débordante)


def seed_classifier_defaults():
    """
    Peuple les tables classifier_rules / classifier_weights / classifier_thresholds
    avec les valeurs par défaut si elles sont vides. Ne touche à rien si l'utilisateur
    a déjà modifié / rempli ces tables.
    """
    conn = get_connection()

    already_seeded = conn.execute("SELECT COUNT(*) AS n FROM classifier_rules").fetchone()["n"]
    if already_seeded == 0:
        for feature_name, params in _DEFAULT_RULES.items():
            conn.execute(
                "INSERT INTO classifier_rules (feature_name, sign, threshold, score) VALUES (?,?,?,?)",
                (feature_name, params["sign"], params["threshold"], params["score"])
            )
        conn.execute(
            "INSERT INTO classifier_thresholds (model_type, threshold_order, threshold_value) VALUES ('rules', 0, ?)",
            (_DEFAULT_RULES_THRESHOLD,)
        )

    already_seeded_w = conn.execute("SELECT COUNT(*) AS n FROM classifier_weights").fetchone()["n"]
    if already_seeded_w == 0:
        for feature_name, weight in _DEFAULT_WEIGHTS.items():
            conn.execute(
                "INSERT INTO classifier_weights (feature_name, weight) VALUES (?,?)",
                (feature_name, weight)
            )
        for i, val in enumerate(_DEFAULT_WEIGHTS_THRESHOLDS):
            conn.execute(
                "INSERT INTO classifier_thresholds (model_type, threshold_order, threshold_value) VALUES ('weights', ?, ?)",
                (i, val)
            )

    conn.commit()
    conn.close()


def get_default_rules() -> dict:
    """Renvoie les règles par défaut / recommandées (modèle 2-classes), pour affichage dans l'UI"""
    return {name: dict(params) for name, params in _DEFAULT_RULES.items()}


def get_default_weights() -> dict:
    """Renvoie les poids par défaut / recommandés (modèle 3-classes), pour affichage dans l'UI"""
    return dict(_DEFAULT_WEIGHTS)


def get_default_thresholds(model_type: str):
    """Renvoie le(s) seuil(s) par défaut / recommandé(s) pour 'rules' ou 'weights'"""
    if model_type == "rules":
        return _DEFAULT_RULES_THRESHOLD
    return list(_DEFAULT_WEIGHTS_THRESHOLDS)


def get_classifier_rules() -> dict:
    """Renvoie le dictionnaire de règles pour le modèle 2-classes, tel qu'attendu par classifier.py"""
    conn = get_connection()
    rows = conn.execute("SELECT feature_name, sign, threshold, score FROM classifier_rules").fetchall()
    conn.close()
    return {
        row["feature_name"]: {"sign": row["sign"], "threshold": row["threshold"], "score": row["score"]}
        for row in rows
    }


def get_classifier_weights() -> dict:
    """Renvoie le dictionnaire de poids pour le modèle 3-classes"""
    conn = get_connection()
    rows = conn.execute("SELECT feature_name, weight FROM classifier_weights").fetchall()
    conn.close()
    return {row["feature_name"]: row["weight"] for row in rows}


def get_classifier_thresholds(model_type: str):
    """
    :model_type: 'rules' (modèle 2-classes) ou 'weights' (modèle 3-classes)
    :return: un int pour 'rules' (un seul seuil), une liste pour 'weights' (deux seuils)
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT threshold_value FROM classifier_thresholds WHERE model_type = ? ORDER BY threshold_order",
        (model_type,)
    ).fetchall()
    conn.close()
    values = [row["threshold_value"] for row in rows]
    if model_type == "rules":
        return values[0] if values else _DEFAULT_RULES_THRESHOLD
    return values if values else _DEFAULT_WEIGHTS_THRESHOLDS


def update_classifier_rule(feature_name: str, sign: str, threshold: float, score: float) -> None:
    """Permet à l'utilisateur de modifier une règle du modèle 2-classes"""
    conn = get_connection()
    conn.execute("""
        INSERT INTO classifier_rules (feature_name, sign, threshold, score)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(feature_name) DO UPDATE SET sign = excluded.sign, threshold = excluded.threshold, score = excluded.score
    """, (feature_name, sign, threshold, score))
    conn.commit()
    conn.close()


def update_classifier_weight(feature_name: str, weight: float) -> None:
    """Permet à l'utilisateur de modifier un poids du modèle 3-classes"""
    conn = get_connection()
    conn.execute("""
        INSERT INTO classifier_weights (feature_name, weight)
        VALUES (?, ?)
        ON CONFLICT(feature_name) DO UPDATE SET weight = excluded.weight
    """, (feature_name, weight))
    conn.commit()
    conn.close()


def update_classifier_threshold(model_type: str, threshold_order: int, threshold_value: float) -> None:
    """Permet à l'utilisateur de modifier un seuil ('rules' ou 'weights')"""
    conn = get_connection()
    conn.execute("""
        INSERT INTO classifier_thresholds (model_type, threshold_order, threshold_value)
        VALUES (?, ?, ?)
        ON CONFLICT(model_type, threshold_order) DO UPDATE SET threshold_value = excluded.threshold_value
    """, (model_type, threshold_order, threshold_value))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()