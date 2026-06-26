from flask import Flask, request, render_template, flash, redirect, url_for
from werkzeug.utils import secure_filename
import os
from markupsafe import escape
import database as db

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app = Flask(__name__)
db.init_db()

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def base():
    return render_template('index.html')
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')
@app.route('/gallery')
def gallery():
    images = db.get_all_images()
    return render_template('gallery.html', images=images)
@app.route('/index', methods=['GET', 'POST'])
def index():

    if request.method == 'POST':

        if 'mon_image' not in request.files:
            return redirect(request.url)
        file = request.files['mon_image']
        if file.filename == '':
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            chemin_final = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            file.save(chemin_final)
            db.insert_image(chemin_final)
            return render_template('index.html')
    return render_template('index.html')
@app.route('/result')
def result():
    return render_template('result.html')
