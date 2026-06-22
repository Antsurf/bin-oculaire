from flask import Flask, request, render_template
from markupsafe import escape

app = Flask(__name__)

@app.route('/base')
def base():
    return render_template('base.html')
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')
@app.route('/gallery')
def gallery():
    return render_template('gallery.html')
@app.route('/index')
def index():
    return render_template('index.html')
@app.route('/result')
def result():
    return render_template('result.html')
