import requests
import random
import database as db

class camera:
    def __init__(self):
        self.lat = random.uniform(48.789356, 48.812311)
        self.long = random.uniform(2.346613, 2.367125)
        self.id = None
        self.class_ = None

    def take_picture(self, img_path):
        self.img_path = img_path





def upload_image_to_website(url_server, image_path, lat, lon):
    """
    Simule l'envoi du formulaire d'upload sans passer par l'interface web.

    :param url_server: URL de la route Flask
    :param image_path: Chemin local de l'image
    :param adresse: Adresse textuelle (optionnel)
    :param lat: Latitude (optionnel)
    :param lon: Longitude (optionnel)
    """

    donnees_formulaire = {
        'mon_adresse': 'adresse inconnu',
        'nb_classes': 3
    }
    donnees_formulaire['lat'] = str(lat)
    donnees_formulaire['lon'] = str(lon)

    try:
        with open(image_path, 'rb') as image_fichier:
            fichiers = {
                'mon_image': image_fichier
            }

            # Envoi de la requête POST
            response = requests.post(url_server, data=donnees_formulaire, files=fichiers)

            # traitement de la réponse
            if response.status_code == 200:
                print("image uploaded successfully")
                print(f"URL de destination : {response.url}")
                return response
            else:
                print(f"Upload failed. code : {response.status_code}")
                return None

    except FileNotFoundError:
        print(f"file '{image_path}' not found.")
    except requests.exceptions.RequestException as e:
        print(f"Error : {e}")



def get_routes(cameras):
    dirty_cameras = []
    for camera in cameras:
        if camera.class_ == "sale" or camera.class_ == "debordante":
            dirty_cameras.append(camera)

    sorted_cameras = sorted(dirty_cameras, key=lambda x: x.lat)
    link = "https://www.google.com/maps/dir/?api=1"

    origin = sorted_cameras[0]
    destination = sorted_cameras[-1]
    waypoints = []
    for waypoint in sorted_cameras[1:-1]:
        waypoints.append(f"{waypoint.lat}%2C+{waypoint.long}")

    params = {
        'origin': f"{origin.lat}%2C+{origin.long}",
        'destination': f"{destination.lat}%2C+{destination.long}"
    }

    if waypoints:
        params['waypoints'] = '%7C'.join(waypoints)

    for key in params.keys():
        link+= f"&{key}={params[key]}"

    return link