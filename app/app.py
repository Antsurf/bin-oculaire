from flask import Flask, request, render_template, flash, redirect, url_for, jsonify, session
from werkzeug.utils import secure_filename
import os
from markupsafe import escape
import uuid
from datetime import datetime
import requests as http_requests
from flask_babel import Babel, gettext as _, ngettext

import database as db
import features as ft
import classifier as cl

# BASE_DIR pointe vers le dossier où se trouve app.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# On définit le chemin complet vers static/uploads
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app = Flask(__name__)

# évite d'utiliser alert() pour les messages flash, on utilisera plutôt des div bootstrap
app.secret_key = "poubelle-app-secret-key-dev"  # nécessaire pour flash() et la session (langue) ; à changer en prod
# On l'applique à la configuration Flask
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Configuration multilingue (français par défaut, anglais disponible)
app.config['LANGUAGES'] = {'fr': 'Français', 'en': 'English', 'es': 'Español', 'de': 'Deutsch', 'it': 'Italiano'}
app.config['BABEL_DEFAULT_LOCALE'] = 'fr'
app.config['BABEL_TRANSLATION_DIRECTORIES'] = 'translations'


def get_locale():
    """
    Détermine la langue à utiliser pour la requête en cours :
    1. la langue explicitement choisie par l'utilisateur (stockée en session),
    2. sinon la langue préférée envoyée par le navigateur (Accept-Language),
    3. sinon la langue par défaut (français).
    """
    if 'lang' in session and session['lang'] in app.config['LANGUAGES']:
        return session['lang']
    return request.accept_languages.best_match(app.config['LANGUAGES'].keys()) or app.config['BABEL_DEFAULT_LOCALE']


babel = Babel(app, locale_selector=get_locale)


@app.route('/lang/<lang_code>')
def set_language(lang_code):
    """Change la langue de l'interface et revient sur la page précédente"""
    if lang_code in app.config['LANGUAGES']:
        session['lang'] = lang_code
    return redirect(request.referrer or url_for('upload_file'))


@app.context_processor
def inject_locale():
    """Rend get_locale() disponible dans tous les templates (ex: <html lang="{{ get_locale() }}">)"""
    return dict(get_locale=get_locale)


# On s'assure qu'il existe
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
# création de la base de donnée en local ou vérification de son existence
db.init_db()

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


# Fonction pour le dashboard pour convertir la taille en Ko en une chaîne lisible
def format_taille_stockage(taille_ko: float) -> str:
    """
    Convertit une taille en Ko (comme stockée dans images_features.file_size)
    en une chaîne lisible : Ko / Mo / Go selon l'ordre de grandeur.
    """
    taille_mo = taille_ko / 1024
    if taille_mo >= 1024:
        return f"{taille_mo / 1024:.2f} Go"
    elif taille_mo >= 1:
        return f"{taille_mo:.2f} Mo"
    else:
        return f"{taille_ko:.2f} Ko"

# ROUTE VERS LE DASHBOARD
@app.route('/dashboard')
def dashboard():
    """
    Récupère données python (stats des poubelles) pour les exploiter ensuite en chartjs (graphiques)
    """
    images = db.get_all_images() #récupère toutes les images

    adresses = [] # récupérer toutes les adresses des poubelles
    total_images_annotees = 0  # compter les images qui ont une annotation
    nb_good_class = 0 # compter les images qui ont une bonne annotation

    for image in images:
        image_id = image["id"] # récupère id de chaque image
        image_info = db.get_image_details(image_id)  # récupère infos sur l'image

        annot = image_info["annotation"]
        if annot == "pleine":
            annot = "debordante" # respecter stockage bdd
        label = image_info["auto_label"]

        if annot is not None:
            total_images_annotees += 1
            if annot == label: # vérifie si classification bien effectuée
                nb_good_class += 1

        if image_info['localisation_nom'] is None: # vérifie si Adresse dispo
            adresses.append('Adresse inconnue')
        else:
            adresses.append(image_info['localisation_nom']) # ajoute la localisation

    adresses_count = dict()
    for ad in adresses:
        if ad in adresses_count.keys():
            adresses_count[ad] += 1 # ajoute 1 au compte
        else:
            adresses_count[ad] = 1 # initialise le compte

    nb_images = db.get_total_images_count()
    nb_poubelles_sales, nb_poubelles_propres, nb_poubelles_deb = db.get_classified_count()
    taille_totale = format_taille_stockage(db.get_total_file_size())
    labels1 = [_("Propre"), _("Sale"), _("Débordante")]
    labels2 = list(adresses_count.keys())
    labels3 = [_("Bien classé"), _("Mal classé")]
    values1 = [nb_poubelles_propres, nb_poubelles_sales, nb_poubelles_deb]
    values2 = list(adresses_count.values())
    values3 = [nb_good_class, total_images_annotees - nb_good_class]

    return render_template(
        "dashboard.html",
        nb_images=nb_images,
        nb_images_annot=total_images_annotees,
        taille_totale=taille_totale,
        labels1=labels1,
        labels2=labels2,
        labels3=labels3,
        values1=values1,
        values2=values2,
        values3=values3
    )


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
    return render_template('result.html', image=image, hist_rgb=histo_dic['hist_rgb'], hist_lum = histo_dic['luminance'])


# ROUTE POUR ENREGISTRER L'ANNOTATION MANUELLE DE L'UTILISATEUR (poubelle réellement sale/pleine ou non)
@app.route('/result/<int:image_id>/annotation', methods=['POST'])
def save_annotation(image_id):
    """
    On est obligé de faire ça car c'est du html css 
    et pas du javascript, 
    donc on ne peut pas faire un fetch() 
    pour envoyer l'annotation à l'API. 
    On fait donc un POST classique vers cette route,
    qui va ensuite rediriger vers la page result.html de l'image concernée.
    """
    annotation = request.form.get('annotation')
    if annotation == '':
        annotation = None
    db.update_annotation(image_id, annotation)
    return redirect(url_for('result', image_id=image_id))


# Route d'upload d'une image
@app.route('/index', methods=['GET', 'POST'])
def upload_file():

    if request.method == 'POST':

        if 'mon_image' not in request.files:
            flash(_("Aucun fichier envoyé."))
            return redirect(request.url)
        
        file = request.files['mon_image']
        
        if file.filename == '':
            flash(_("Aucune image sélectionnée."))
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

                Cas des caméras (test_cas_reel.py) : elles envoient directement lat/lon
                mais pas de vraie adresse (juste un texte de substitution). Dans ce cas
                on fait l'inverse : on résout l'adresse à partir des coordonnées via le
                géocodage inverse, plutôt que de faire confiance au texte du formulaire. 
                """
                lat_str = request.form.get('lat')
                lon_str = request.form.get('lon')

                if lat_str and lon_str:
                    lat, lon = float(lat_str), float(lon_str)
                    adresse_resolue = ft.get_address_from_coords(lat, lon)
                    if adresse_resolue:
                        adresse = adresse_resolue
                    elif not adresse:
                        adresse = _("Adresse inconnue")
                else:
                    if not adresse:
                        flash(_("L'adresse est obligatoire."))
                        return redirect(request.url)
                    lat, lon = ft.get_coords_from_address(adresse)
                id_localisation = db.get_localisation(lat, lon)

                # Sinon on la crée
                if id_localisation is None:
                    id_localisation = db.add_localisation(lat, lon, adresse)

            except (ValueError, TypeError):
                # pas de localisation
                id_localisation = None

            # On insert l'image dans la BDD ainsi que les features et la classification 
            img_id = db.insert_image(chemin_final, filename, id_localisation)
            db.add_features(img_id, images_features)

            # récupération du choix de l'utilisateur (2 ou 3 classes) sur index.html
            try:
                nb_classes = int(request.form.get('nb_classes', 2))
            except (TypeError, ValueError):
                nb_classes = 2
            if nb_classes not in (2, 3):
                nb_classes = 2

            classification, confidence = cl.classify(images_features, nb_of_classes=nb_classes)
            db.update_autolabel(img_id, classification, confidence)

            return redirect(url_for('result', image_id=img_id))

    return render_template('index.html')
        

# ROUTE VERS LES PARAMETRES DU CLASSIFIER (règles du modèle 2-classes, poids du modèle 3-classes)
@app.route('/parametres', methods=['GET'])
def parametres():
    current_rules = db.get_classifier_rules()
    default_rules = db.get_default_rules()
    current_weights = db.get_classifier_weights()
    default_weights = db.get_default_weights()

    rules_threshold = db.get_classifier_thresholds('rules')
    default_rules_threshold = db.get_default_thresholds('rules')
    weights_thresholds = db.get_classifier_thresholds('weights')
    default_weights_thresholds = db.get_default_thresholds('weights')

    rules_rows = []
    for feature in sorted(default_rules.keys()):
        current = current_rules.get(feature, default_rules[feature])
        rec = default_rules[feature]
        rules_rows.append({
            "feature": feature,
            "sign": current["sign"],
            "threshold": current["threshold"],
            "score": current["score"],
            "rec_sign": rec["sign"],
            "rec_threshold": rec["threshold"],
            "rec_score": rec["score"],
        })

    weights_rows = []
    for feature in sorted(default_weights.keys()):
        current_weight = current_weights.get(feature, default_weights[feature])
        weights_rows.append({
            "feature": feature,
            "weight": current_weight,
            "rec_weight": default_weights[feature],
        })

    return render_template(
        'parametres.html',
        rules_rows=rules_rows,
        weights_rows=weights_rows,
        rules_threshold=rules_threshold,
        default_rules_threshold=default_rules_threshold,
        weights_thresholds=weights_thresholds,
        default_weights_thresholds=default_weights_thresholds,
    )


@app.route('/parametres', methods=['POST'])
def save_parametres():
    default_rules = db.get_default_rules()
    for feature, rec in default_rules.items():
        sign = request.form.get(f'rule_sign_{feature}', rec['sign'])
        if sign not in ('>', '<'):
            sign = rec['sign']

        try:
            threshold = float(request.form.get(f'rule_threshold_{feature}'))
        except (TypeError, ValueError):
            threshold = rec['threshold']

        try:
            score = float(request.form.get(f'rule_score_{feature}'))
        except (TypeError, ValueError):
            score = rec['score']

        db.update_classifier_rule(feature, sign, threshold, score)

    default_weights = db.get_default_weights()
    for feature, rec_weight in default_weights.items():
        try:
            weight = float(request.form.get(f'weight_{feature}'))
        except (TypeError, ValueError):
            weight = rec_weight
        db.update_classifier_weight(feature, weight)

    try:
        rules_threshold = float(request.form.get('rules_threshold'))
        db.update_classifier_threshold('rules', 0, rules_threshold)
    except (TypeError, ValueError):
        pass

    for i in range(2):
        try:
            value = float(request.form.get(f'weights_threshold_{i}'))
            db.update_classifier_threshold('weights', i, value)
        except (TypeError, ValueError):
            pass

    flash("Paramètres du classifier enregistrés avec succès.")
    return redirect(url_for('parametres'))


@app.route('/api/agglomeration/geojson', methods=['GET'])
def get_zones_risque():
    """
    API appelée quand on visualise la carte. Elle renvoie les localisations des images avec le dernier label associé en format geojson
    """
    conn = db.get_connection()

    # Requête qui récupère une ligne PAR IMAGE (et pas une par adresse) : ainsi,
    # quand plusieurs poubelles existent à la même adresse, on a bien plusieurs
    # marqueurs superposés que Leaflet regroupe avec un numéro cliquable
    # (cluster), au lieu de n'afficher que la dernière image de l'adresse.
    rows = conn.execute("""
        SELECT i.id AS image_id, i.upload_date, l.latitude, l.longitude, l.localisation_nom, c.auto_label, c.annotation
        FROM localisation l
        JOIN images i ON l.id_localisation = i.id_localisation
        LEFT JOIN images_classification c ON i.id = c.image_id
        ORDER BY i.upload_date DESC
    """).fetchall()
    conn.close()

    print(rows)

    # transformation en format geojson
    geojson = {
        "type": "FeatureCollection",
        "features": []
    }
    
    for row in rows:
        label = row['auto_label']
        annotation = row['annotation']
        if annotation == "pleine":
            annotation = "debordante"  # même mapping que sur le dashboard

        # Si l'utilisateur a annoté l'image ET que son annotation diffère de la
        # classification automatique, on donne priorité à l'annotation pour la
        # couleur du point. Si elle est identique, ou si l'image n'est pas
        # annotée, on garde la classification automatique (ou "inconnu").
        if annotation is not None and annotation != label:
            etat = annotation
        else:
            etat = label if label else "inconnu"

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [row['longitude'], row['latitude']]
            },
            "properties": {
                "adresse": row['localisation_nom'],
                "etat": etat,
                "image_id": row['image_id'],
                "date": row['upload_date'],
            }
        }
        geojson["features"].append(feature)
        
    return jsonify(geojson)


@app.route('/api/context')
def api_context():
    lat = request.args.get('lat')
    lon = request.args.get('lon')

    if not lat or not lon:
        return jsonify({"error": _("Coordonnées manquantes")}), 400

    meteo = _("Indisponible")
    jour_marche = _("Non")
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
            desc = _("Ciel dégagé")
        elif code in [1, 2, 3]:
            desc = _("Nuageux")
        elif code in range(51, 68):
            desc = _("Pluie")
        elif code in range(71, 78):
            desc = _("Neige")
        elif code in range(80, 83):
            desc = _("Averses")
        elif code in range(95, 100):
            desc = _("Orage")
        else:
            desc = _("Code %(code)s", code=code)

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
            timeout=10,
            headers={"User-Agent": "bin-oculaire-app/1.0 (contact: dev@example.com)"}
        )
        # Overpass (serveur public partagé) est souvent surchargé et répond
        # alors avec un code d'erreur (429/504) et un corps vide ou non-JSON.
        # r.json() plante dans ce cas avec "Expecting value: line 1 column 1"
        # sans dire pourquoi -> on vérifie le status avant de parser.
        r.raise_for_status()
        data = r.json()
        if data.get("elements"):
            # Un marché existe à proximité (ngettext gère le singulier/pluriel de "marché(s)")
            nb_marches = len(data["elements"])
            jour_marche = ngettext(
                "Oui (%(num)d marché à proximité)",
                "Oui (%(num)d marchés à proximité)",
                nb_marches,
                num=nb_marches
            )
        else:
            jour_marche = _("Aucun marché à proximité")
    except http_requests.exceptions.RequestException as e:
        print(f"Erreur réseau/HTTP marchés (status={getattr(e.response, 'status_code', '?')}): {e}")
        jour_marche = _("Indisponible (serveur Overpass surchargé, réessayez plus tard)")
    except ValueError as e:
        # ValueError = JSONDecodeError ici : la réponse n'était pas du JSON
        print(f"Erreur JSON marchés (status={r.status_code}, début réponse={r.text[:200]!r}): {e}")
        jour_marche = _("Indisponible (serveur Overpass surchargé, réessayez plus tard)")

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
            timeout=10,
            headers={"User-Agent": "bin-oculaire-app/1.0 (contact: dev@example.com)"}
        )
        r.raise_for_status()
        data = r.json()
        chantiers_btp = data.get("elements", [{}])[0].get("tags", {}).get("total", 0)
    except http_requests.exceptions.RequestException as e:
        print(f"Erreur réseau/HTTP chantiers (status={getattr(e.response, 'status_code', '?')}): {e}")
    except ValueError as e:
        print(f"Erreur JSON chantiers (status={r.status_code}, début réponse={r.text[:200]!r}): {e}")

    return jsonify({
        "meteo": meteo,
        "jour_marche": jour_marche,
        "chantiers_btp": chantiers_btp
    })

if __name__ == '__main__':
    print("--- Lancement du serveur sur http://127.0.0.1:5000 ---")
    app.run(debug=True, port=5000)