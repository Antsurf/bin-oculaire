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
    );""")


    conn.commit()

    conn.close()

    print(f"Base de donnée initialisée, chemin: {os.path.abspath(db_name)}")


def insert_image(file_path: str, id_localisation: int = None) -> int:
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

    cursor.execute("""INSERT INTO images (file_path, upload_date, id_localisation) VALUES (?,?,?)""", (file_path,upload_date,id_localisation))

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

def get_image_details(image_id):
    """Récupère les informations nécessaires pour la page de résultat."""
    conn = get_connection()
    query = """
        SELECT i.id, i.file_path, i.upload_date, f.file_size, f.width, f.height, 
               c.auto_label, f.luminosite, f.contraste_maximal, f.saturation, f.edge_density,
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
        ORDER BY i.upload_date DESC
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

def update_annotation(image_id: int, annotation: str)->None:
    """
    Définit l’annotation d’une image (‘pleine’ ou ‘vide’),
    ou l’annule en passant annotation=None.
    """
    conn = get_connection()
    cursor = conn.cursor()

    if annotation not in ("pleine", "vide", None):
        print("annotation doit être ‘pleine’ ou ‘vide’ ou 'None'")
    cur = conn.execute(
    f"UPDATE images_classification SET annotation = {annotation} WHERE image_id = {image_id}")
    conn.commit()
    conn.close()

def update_autolabel(image_id:int, autolabel: str) -> None:
    """
    Insère ou met à jour le label du classifier dans la BDD (INSERT OR REPLACE)
    """
    conn = get_connection()
    conn.execute("""
        INSERT INTO images_classification (image_id, auto_label)
        VALUES (?, ?)
        ON CONFLICT(image_id) DO UPDATE SET auto_label = excluded.auto_label
    """, (image_id, autolabel))  
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()