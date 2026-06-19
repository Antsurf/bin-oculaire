import sqlite3
import os

db_name = "database.db"

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
       contraste         DECIMAL(5,2),
       saturation        DECIMAL(5,2),
       FOREIGN KEY(image_id) REFERENCES images(id) ON DELETE CASCADE
    );""")


    conn.commit()

    conn.close()

    print(f"Base de donnée initialisée, chemin: {os.path.abspath(db_name)}")


if __name__ == "__main__":
    init_db()