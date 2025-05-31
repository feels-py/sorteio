import json
import os
import random
import time
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'quinbingo_super_secret_key_123')
app.config['UPLOAD_FOLDER'] = 'static/sounds'
app.config['IMAGE_UPLOAD_FOLDER'] = 'static/images'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
socketio = SocketIO(app, cors_allowed_origins="*")

# Configurações
DATA_FILE = 'quinbingo_data.json'
BALLS_RANGE = list(range(1, 76))
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'quinbingo123')
SPONSORS = [
    {'name': 'Patrocinador 1', 'image': 'sponsor1.png'},
    {'name': 'Patrocinador 2', 'image': 'sponsor2.png'},
    {'name': 'Patrocinador 3', 'image': 'sponsor3.png'}
]
PRIZE_IMAGE = 'premio.jpg'

class QuinBingoGame:
    def __init__(self):
        self.data = self.load_data()
    
    def load_data(self):
        if not os.path.exists(DATA_FILE):
            return self.reset_game()
        
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                defaults = {
                    'balls': BALLS_RANGE.copy(),
                    'drawn_balls': [],
                    'players': {},
                    'winner': None,
                    'status': 'waiting',
                    'countdown_end': None,
                    'current_ball': None,
                    'background_music': 'background.mp3',
                    'winner_sound': 'winner.mp3',
                    'ball_sound': 'ball.mp3',
                    'countdown_sound': 'countdown.mp3'
                }
                for key, value in defaults.items():
                    if key not in data:
                        data[key] = value
                return data
        except Exception:
            return self.reset_game()
    
    def save_data(self):
        try:
            with open(DATA_FILE, 'w') as f:
                json.dump(self.data, f, indent=4)
            socketio.emit('game_update', self.data)
            return True
        except Exception as e:
            print(f"Erro ao salvar dados: {e}")
            return False
    
    def reset_game(self):
        self.data = {
            'balls': BALLS_RANGE.copy(),
            'drawn_balls': [],
            'players': {},
            'winner': None,
            'status': 'waiting',
            'countdown_end': None,
            'current_ball': None,
            'background_music': 'background.mp3',
            'winner_sound': 'winner.mp3',
            'ball_sound': 'ball.mp3',
            'countdown_sound': 'countdown.mp3'
        }
        self.save_data()
        return self.data
    
    def add_player_card(self, player_name, card_id, card_numbers):
        if not all([player_name, card_id, card_numbers]):
            raise ValueError("Todos os campos devem ser preenchidos")
        
        try:
            numbers = []
            seen = set()
            for num in card_numbers.split(','):
                num = num.strip()
                if not num:
                    continue
                n = int(num)
                if n < 1 or n > 75:
                    raise ValueError("Números devem estar entre 1 e 75")
                if n in seen:
                    raise ValueError("Não podem haver números repetidos")
                seen.add(n)
                numbers.append(n)
                
            if len(numbers) != 24:
                raise ValueError("A cartela deve ter exatamente 24 números")
            
            if player_name not in self.data['players']:
                self.data['players'][player_name] = {}
            
            self.data['players'][player_name][card_id] = numbers
            
            if not self.save_data():
                raise ValueError("Erro ao salvar no servidor")
            
            return True
            
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise ValueError(f"Erro ao processar cartela: {str(e)}")
    
    def change_prize_image(self, image_file):
        if image_file and allowed_file(image_file.filename, {'jpg', 'jpeg', 'png'}):
            filename = secure_filename(PRIZE_IMAGE)
            image_path = os.path.join(app.config['IMAGE_UPLOAD_FOLDER'], filename)
            image_file.save(image_path)
            return True
        return False
    
    def start_countdown(self):
        if self.data['status'] == 'counting_down':
            return False
            
        self.data['status'] = 'counting_down'
        self.data['countdown_end'] = (datetime.now() + timedelta(seconds=60)).isoformat()
        
        if self.save_data():
            Thread(target=self.start_drawing_after_countdown).start()
            return True
        return False
    
    def start_drawing_after_countdown(self):
        try:
            countdown_end = datetime.fromisoformat(self.data['countdown_end'])
            while datetime.now() < countdown_end and self.data['status'] == 'counting_down':
                time.sleep(1)
            
            if self.data['status'] == 'counting_down':
                self.data['status'] = 'drawing'
                self.save_data()
                self.start_drawing()
        except Exception as e:
            print(f"Erro no countdown: {e}")
            self.data['status'] = 'waiting'
            self.save_data()
    
    def start_drawing(self):
        try:
            while self.data['balls'] and self.data['status'] == 'drawing':
                time.sleep(3)
                ball = random.choice(self.data['balls'])
                self.data['balls'].remove(ball)
                self.data['drawn_balls'].append(ball)
                self.data['current_ball'] = ball
                self.save_data()
                self.check_winner()
            
            if self.data['status'] == 'drawing':
                self.data['status'] = 'finished'
                self.save_data()
        except Exception as e:
            print(f"Erro no sorteio: {e}")
            self.data['status'] = 'waiting'
            self.save_data()
    
    def check_winner(self):
        try:
            drawn_balls = set(self.data['drawn_balls'])
            for player, cards in self.data['players'].items():
                for card_id, numbers in cards.items():
                    if set(numbers).issubset(drawn_balls):
                        self.data['winner'] = f"{player} (Cartela: {card_id})"
                        self.data['status'] = 'finished'
                        self.save_data()
                        return True
            return False
        except Exception as e:
            print(f"Erro ao verificar vencedor: {e}")
            return False

quinbingo_game = QuinBingoGame()

def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

@app.route('/')
def bingo():
    return render_template('bingo.html', 
                         data=quinbingo_game.data, 
                         sponsors=SPONSORS,
                         prize_image=PRIZE_IMAGE)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static/images'), 'favicon.ico')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST' and 'login' in request.form:
        if request.form['password'] == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
        else:
            return render_template('admin_login.html', error="Senha incorreta!")
    
    if not session.get('admin_logged_in'):
        return render_template('admin_login.html')
    
    error = None
    success = None
    
    if request.method == 'POST':
        try:
            if 'add_player_card' in request.form:
                player_name = request.form.get('player_name', '').strip()
                card_id = request.form.get('card_id', '').strip()
                card_numbers = request.form.get('card_numbers', '').strip()
                
                quinbingo_game.add_player_card(player_name, card_id, card_numbers)
                success = f"Cartela {card_id} de {player_name} adicionada com sucesso!"
            
            elif 'start_countdown' in request.form:
                if quinbingo_game.start_countdown():
                    success = "Contagem regressiva iniciada!"
                else:
                    error = "Erro ao iniciar contagem regressiva"
            
            elif 'reset' in request.form:
                quinbingo_game.reset_game()
                success = "Jogo reiniciado com sucesso!"
            
            elif 'change_music' in request.form:
                music_file = request.files.get('background_music')
                if music_file and allowed_file(music_file.filename, {'mp3', 'wav'}):
                    filename = secure_filename(music_file.filename)
                    music_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    quinbingo_game.data['background_music'] = filename
                    quinbingo_game.save_data()
                    success = "Música alterada com sucesso!"
                else:
                    error = "Arquivo inválido. Use apenas MP3 ou WAV."
            
            elif 'change_prize' in request.form:
                prize_file = request.files.get('prize_image')
                if prize_file:
                    if quinbingo_game.change_prize_image(prize_file):
                        success = "Imagem do prêmio atualizada com sucesso!"
                    else:
                        error = "Formato de imagem inválido. Use JPG ou PNG."
                else:
                    error = "Nenhuma imagem foi enviada"
            
        except ValueError as e:
            error = str(e)
        except Exception as e:
            error = f"Erro inesperado: {str(e)}"
    
    return render_template('admin.html', 
                         data=quinbingo_game.data,
                         error=error,
                         success=success,
                         prize_image=PRIZE_IMAGE)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@socketio.on('connect')
def handle_connect():
    emit('game_update', quinbingo_game.data)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)