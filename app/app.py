from flask import Flask, request, render_template, flash, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
import os
from markupsafe import escape
import uuid
from datetime import datetime
import requests as http_requests

import database as db
import features as ft
import classifier as cl

UPLOAD_FOLDER = "app/static/uploads/"

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app = Flask(__name__)

# création de la base de donnée en local ou vérification de son existence
db.init_db()

# création du fichier upload dans lequel toutes les images uploadés via le form sont stockées localement
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """
    Fonction pour vérifier que le fichier donné respecte les extensions mentionnées au dessus
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ROUTE VERS L'INDEX (page d'accueil avec le form)
@app.route('/')
def base():
    return render_template('index.html')

# ROUTE VERS LA CARTE
@app.route('/carte')
def carte():
    return render_template('carte.html')

# ROUTE VERS LE DASHBOARD
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

# ROUTE VERS LA GALERIE avec différentes pages (pagination)
@app.route('/gallery')
def gallery():
    page = int(request.args.get('page', 1))

    # nombre d'images par page et offset pour la pagination
    per_page = 10

    # id de l'image de départ pour la page actuelle (page 1 = 0, page 2 = 50, page 3 = 100, etc.)
    offset = (page - 1) * per_page
    
    images = db.get_images_paginated(limit=per_page, offset=offset)
    
    total_images = db.get_total_images_count()
    total_pages = (total_images + per_page - 1) // per_page
    
    return render_template('gallery.html', images=images, page=page, total_pages=total_pages)

# ROUTE VERS RESULT 
@app.route('/result/<int:image_id>')
def result(image_id):
    image = db.get_image_details(image_id)
    file_path = image['file_path']
    histo_dic = ft.get_histograms(file_path)
    return render_template('result.html', image=image, hist_data=histo_dic['hist_rgb'])


# Route d'upload d'une image
@app.route('/index', methods=['GET', 'POST'])
def upload_file():

    if request.method == 'POST':

        if 'mon_image' not in request.files:
            return redirect(request.url)
        
        file = request.files['mon_image']
        
        if file.filename == '':
            return redirect(request.url)

        if file and allowed_file(file.filename):

            # sauvegarde du fichier
            extension  = file.filename.rsplit('.', 1)[1].lower()
            filename   = f"{uuid.uuid4().hex}.{extension}"
            chemin_final = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(chemin_final)

            id_localisation = None
            try:
                images_features = ft.extract_features(chemin_final)

                adresse = request.form.get('mon_adresse', '').strip() #pour éviter les faux espaces
                # on regarde si on a des coordonnées 
                """
                Petite remarque, quand on vérifie que la personne rentre une adresse via 
                l'api dans index, ça enregistre dans des input cachés la latitude et la longitude
                cependant, si l'utilisateur écrit simplement une adresse sans en sélectionner une
                ces valeurs sont vides. Donc on doit utiliser l'appel d'api qu'on a codé 
                dans features.py 
                """
                lat_str = request.form.get('lat')
                lon_str = request.form.get('lon')

                if lat_str and lon_str:
                    lat, lon = float(lat_str), float(lon_str)
                else:
                    lat, lon = ft.get_coords_from_address(adresse)
                id_localisation = db.get_localisation(lat, lon)

                # Sinon on la crée
                if id_localisation is None:
                    id_localisation = db.add_localisation(lat, lon, adresse)

            except (ValueError, TypeError):
                # pas de localisation
                id_localisation = None

            # On insert l'image dans la BDD ainsi que les features et la classification 
            img_id = db.insert_image(chemin_final, id_localisation)
            db.add_features(img_id, images_features)
            classification, confidence = cl.classify(images_features)
            db.update_autolabel(img_id, classification, confidence)

            return redirect(url_for('result', image_id=img_id))

    return render_template('index.html')
        

@app.route('/api/agglomeration/geojson', methods=['GET'])
def get_zones_risque():
    """
    API appelée quand on visualise la carte. Elle renvoie les localisations des images avec le dernier label associé en format geojson
    """
    conn = db.get_connection()

    # Requête qui récupère les localisations et le dernier label associé
    rows = conn.execute("""
        SELECT l.latitude, l.longitude, l.localisation_nom
        FROM localisation l
        JOIN images i ON l.id_localisation = i.id_localisation
    """).fetchall()
    conn.close()
#         WHERE ic.auto_label = 'dirty' OR ic.auto_label = 'very_dirty'

    print(rows)

    # transformation en format geojson
    geojson = {
        "type": "FeatureCollection",
        "features": []
    }
    
    for row in rows:
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [row['longitude'], row['latitude']]
            },
            "properties": {
                "adresse": row['localisation_nom'],
            }
        }
        geojson["features"].append(feature)
        
    return jsonify(geojson)


@app.route('/api/context')
def api_context():
    lat = request.args.get('lat')
    lon = request.args.get('lon')

    if not lat or not lon:
        return jsonify({"error": "Coordonnées manquantes"}), 400

    meteo = "Indisponible"
    jour_marche = "Non"
    chantiers_btp = 0

    # open-météo pas de clé API
    try:
        r = http_requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current_weather": True
            },
            timeout=5
        )
        data = r.json()
        code = data["current_weather"]["weathercode"]
        temp = data["current_weather"]["temperature"]

        # Traduction basique des weather codes WMO
        if code == 0:
            desc = "Ciel dégagé"
        elif code in [1, 2, 3]:
            desc = "Nuageux"
        elif code in range(51, 68):
            desc = "Pluie"
        elif code in range(71, 78):
            desc = "Neige"
        elif code in range(80, 83):
            desc = "Averses"
        elif code in range(95, 100):
            desc = "Orage"
        else:
            desc = f"Code {code}"

        meteo = f"{desc}, {temp}°C"
    except Exception as e:
        print(f"Erreur météo: {e}")

    # marché
    try:
        # Recherche des marchés dans un rayon de 500m
        overpass_query = f"""
        [out:json][timeout:10];
        node["amenity"="marketplace"](around:500,{lat},{lon});
        out body;
        """
        r = http_requests.post(
            "https://overpass-api.de/api/interpreter",
            data=overpass_query,
            timeout=10
        )
        data = r.json()
        if data.get("elements"):
            # Un marché existe à proximité
            # Tu peux affiner avec les horaires OSM si disponibles
            jour_marche = f"Oui ({len(data['elements'])} marché(s) à proximité)"
        else:
            jour_marche = "Aucun marché à proximité"
    except Exception as e:
        print(f"Erreur marchés: {e}")
        jour_marche = "Indisponible"

    # chantier
    try:
        overpass_query = f"""
        [out:json][timeout:10];
        (
          node["landuse"="construction"](around:300,{lat},{lon});
          way["landuse"="construction"](around:300,{lat},{lon});
        );
        out count;
        """
        r = http_requests.post(
            "https://overpass-api.de/api/interpreter",
            data=overpass_query,
            timeout=10
        )
        data = r.json()
        chantiers_btp = data.get("elements", [{}])[0].get("tags", {}).get("total", 0)
    except Exception as e:
        print(f"Erreur chantiers: {e}")

    return jsonify({
        "meteo": meteo,
        "jour_marche": jour_marche,
        "chantiers_btp": chantiers_btp
    })

if __name__ == '__main__':
    print("--- Lancement du serveur sur http://127.0.0.1:5000 ---")
    app.run(debug=True, port=5000)