import requests
import random

class camera:
    def __init__(self):
        self.lat = random.uniform(48.789356, 48.812311)
        self.long = random.uniform(2.346613, 2.367125)

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
        'nb_classes': 2
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



cameras = []
for i in range(20):
    cameras.append(camera())

for i in range(len(cameras)):
    if i < 10:
        class_ = "clean"
    else:
        class_ = "dirty"
    cameras[i].take_picture(f"Data/train/with_label/{class_}/train_{class_}_img_0{"0" if i<9 else ""}{i+1}.jpeg")
for camera in cameras:
    upload_image_to_website(
        url_server="http://localhost:5000/index",
        image_path=camera.img_path,
        lat=camera.lat,
        lon=camera.long,
    )