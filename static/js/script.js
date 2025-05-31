document.addEventListener('DOMContentLoaded', function() {
    // Elementos da página
    const connectionStatus = document.getElementById('connection-status');
    const waitingScreen = document.getElementById('waiting-screen');
    const drawingScreen = document.getElementById('drawing-screen');
    const winnerScreen = document.getElementById('winner-screen');
    const countdownDisplay = document.getElementById('countdown-display');
    const waitingMessage = document.getElementById('waiting-message');
    const countdownElement = document.getElementById('countdown');
    const currentBallElement = document.getElementById('current-ball');
    const drawnBallsElement = document.getElementById('drawn-balls');
    const winnerNameElement = document.getElementById('winner-name');
    const drawnCountElement = document.getElementById('drawn-count');
    const progressFillElement = document.getElementById('progress-fill');
    const winnerCardElement = document.getElementById('winner-card');
    
    // Elementos de áudio
    const countdownSound = document.getElementById('countdown-sound');
    const ballSound = document.getElementById('ball-sound');
    const winnerSound = document.getElementById('winner-sound');
    const backgroundMusic = document.getElementById('background-music');
    const muteBtn = document.getElementById('mute-btn');
    const volumeSlider = document.getElementById('volume-slider');
    
    // Configuração inicial
    backgroundMusic.volume = 0.5;
    let isMuted = false;
    let countdownInterval = null;
    
    // Configuração do Socket.IO
    const socket = io();
    
    // Status da conexão
    socket.on('connect', function() {
        connectionStatus.textContent = 'Conectado';
        connectionStatus.classList.add('connected');
        connectionStatus.classList.remove('disconnected');
    });
    
    socket.on('disconnect', function() {
        connectionStatus.textContent = 'Desconectado';
        connectionStatus.classList.add('disconnected');
        connectionStatus.classList.remove('connected');
    });
    
    // Atualizações do jogo
    socket.on('game_update', function(data) {
        updateGameDisplay(data);
    });
    
    // Controles de volume
    volumeSlider.addEventListener('input', function() {
        backgroundMusic.volume = this.value;
        if (this.value == 0) {
            muteBtn.textContent = '🔇';
            isMuted = true;
        } else {
            muteBtn.textContent = '🔊';
            isMuted = false;
        }
    });
    
    muteBtn.addEventListener('click', function() {
        isMuted = !isMuted;
        if (isMuted) {
            backgroundMusic.volume = 0;
            volumeSlider.value = 0;
            this.textContent = '🔇';
        } else {
            backgroundMusic.volume = volumeSlider.value || 0.5;
            volumeSlider.value = backgroundMusic.volume;
            this.textContent = '🔊';
        }
    });
    
    // Botão Completar Adição
    document.getElementById('complete-add')?.addEventListener('click', function() {
        document.querySelector('.player-form').reset();
        alert('Adição de cartelas concluída com sucesso!');
    });
    
    // Atualiza a exibição do jogo
    function updateGameDisplay(data) {
        switch(data.status) {
            case 'waiting':
                showScreen(waitingScreen);
                hideCountdown();
                stopBackgroundMusic();
                break;
            case 'counting_down':
                showScreen(waitingScreen);
                showCountdown(data.countdown_end);
                stopBackgroundMusic();
                break;
            case 'drawing':
                showScreen(drawingScreen);
                startBackgroundMusic();
                updateDrawingScreen(data);
                break;
            case 'finished':
                stopBackgroundMusic();
                if (data.winner) {
                    showWinnerScreen(data);
                } else {
                    showScreen(drawingScreen);
                    updateDrawingScreen(data);
                }
                break;
        }
    }
    
    // Mostra apenas a tela especificada
    function showScreen(screenToShow) {
        [waitingScreen, drawingScreen, winnerScreen].forEach(screen => {
            screen.classList.add('hidden');
        });
        screenToShow.classList.remove('hidden');
    }
    
    // Mostrar/ocultar contagem regressiva
    function showCountdown(endTime) {
        countdownDisplay.classList.remove('hidden');
        waitingMessage.textContent = 'Prepare-se! O sorteio está começando...';
        startCountdown(endTime);
    }
    
    function hideCountdown() {
        countdownDisplay.classList.add('hidden');
        waitingMessage.textContent = 'Aguardando início do sorteio...';
        stopCountdown();
    }
    
    // Inicia a contagem regressiva
    function startCountdown(endTime) {
        stopCountdown();
        countdownSound.play();
        
        function update() {
            const now = new Date();
            const end = new Date(endTime);
            const diff = Math.floor((end - now) / 1000);
            
            if (diff <= 0) {
                countdownElement.textContent = '0';
                stopCountdown();
                return;
            }
            
            countdownElement.textContent = diff;
            gsap.to(countdownElement, {
                scale: 1.2,
                duration: 0.5,
                yoyo: true,
                repeat: 1,
                ease: "power1.inOut"
            });
        }
        
        update();
        countdownInterval = setInterval(update, 1000);
    }
    
    // Para a contagem regressiva
    function stopCountdown() {
        if (countdownInterval) {
            clearInterval(countdownInterval);
            countdownInterval = null;
        }
    }
    
    // Atualiza a tela de sorteio
    function updateDrawingScreen(data) {
        if (data.current_ball) {
            currentBallElement.textContent = data.current_ball;
            ballSound.play();
            
            gsap.fromTo(currentBallElement, 
                {scale: 0, rotation: -180, opacity: 0},
                {scale: 1, rotation: 0, opacity: 1, duration: 0.8, ease: "elastic.out(1, 0.5)"}
            );
        }
        
        // Atualiza contagem de bolas sorteadas
        if (drawnCountElement) {
            drawnCountElement.textContent = data.drawn_balls.length;
        }
        
        // Atualiza barra de progresso
        if (progressFillElement) {
            const progress = (data.drawn_balls.length / 75) * 100;
            gsap.to(progressFillElement, {
                width: `${progress}%`,
                duration: 0.8,
                ease: "power2.out"
            });
        }
        
        // Atualiza os números sorteados
        if (drawnBallsElement) {
            drawnBallsElement.innerHTML = '';
            data.drawn_balls.forEach(ball => {
                const ballElement = document.createElement('span');
                ballElement.textContent = ball;
                drawnBallsElement.appendChild(ballElement);
                
                gsap.from(ballElement, {
                    y: 20,
                    opacity: 0,
                    duration: 0.5,
                    ease: "back.out"
                });
            });
        }
    }
    
    // Mostra a tela do vencedor
    function showWinnerScreen(data) {
        winnerNameElement.textContent = data.winner;
        winnerSound.play();
        
        gsap.from(winnerNameElement, {
            scale: 0,
            duration: 1,
            ease: "elastic.out(1, 0.5)"
        });
        
        gsap.to(".confetti", {
            y: "random(500, 1000)",
            x: "random(-200, 200)",
            rotation: "random(0, 360)",
            opacity: 1,
            duration: 3,
            stagger: 0.1,
            ease: "power1.out"
        });
    }
    
    // Controle da música de fundo
    function startBackgroundMusic() {
        if (backgroundMusic.paused) {
            backgroundMusic.play().catch(e => console.log('Autoplay prevented:', e));
        }
    }
    
    function stopBackgroundMusic() {
        backgroundMusic.pause();
    }
});