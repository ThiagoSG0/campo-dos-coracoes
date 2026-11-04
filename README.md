# Campo dos Corações

Minigame 2D top-down survivors-like para a atividade de Computação Gráfica.
O protagonista é um quadrado azul em um campo aberto com fundo liso. Os inimigos são o
**Senhor Coração do exemplo `06_senhor_coracao.py`**, com a mesma curva e olhos
que acompanham o jogador. Não há texto dentro da cena: menus, melhorias,
indicadores são feitos com geometria. A barra de título mostra FPS
e estado do vsync, conforme o enunciado.

## Executar no cgcourse

No terminal, abra a pasta do repositório. Crie o ambiente `cgcourse` com
Conda ou Miniforge e execute o jogo.

```bat
conda env create -f environment.yml
conda activate cgcourse
python jogo.py
```

Se o ambiente já existir, comece por `conda activate cgcourse`. No Windows,
`iniciar.bat` ativa o ambiente pela instalação padrão do Miniforge.

O jogo requer OpenGL 4.0 Core ou superior.

## Controles

| Entrada | Ação |
| --- | --- |
| Enter ou clique | Iniciar; retomar a pausa; reiniciar após derrota |
| WASD ou setas | Movimento contínuo, incluindo diagonais normalizadas |
| Z | Swing de espada na última direção de movimento |
| X | Disparar magia no inimigo mais próximo; sem alvo, na última direção de movimento |
| P ou Tab | Pausar e retomar |
| 1 / 2 / 3 | Escolher vida / dano / mana ao subir de nível |
| A/D ou esquerda/direita + Enter | Selecionar e confirmar uma melhoria |
| Clique sobre um cartão | Escolher a melhoria correspondente |
| R | Reiniciar toda a partida sem fechar a janela |
| V | Ligar/desligar vsync com `glfw.swap_interval` |
| Esc | Fechar |

Cada ataque exige um pressionamento de **Z** ou **X**. A repetição automática
do teclado é ignorada. O swing de Z atinge a frente do personagem num arco de
120 graus e tem um intervalo de 0,42 segundo entre golpes. A lâmina e o arco
aparecem por 0,18 segundo. O clique continua disponível nos menus.

O campo tem fundo liso e os personagens clareiam ao receber dano. Os cartões
de melhoria mostram um ícone central com borda colorida na opção selecionada.
A pulsação dos corações e o movimento das gemas são animações autônomas.

## Regras e progressão

- **Vida:** começa em 100. Contato causa 12 de dano, ou 24 no chefe; um ponto
  roxo causa 18. Após sofrer dano há 0,7 segundo de imunidade. A barra vermelha
  encolhe pela esquerda fixa, proporcionalmente à vida restante.
- **Mana:** começa em 80. Cada magia custa 16 e causa 1,9 vez o dano base.
  Recupera 9 unidades por segundo; não há disparo sem mana suficiente.
- **XP:** corações derrotados deixam um quadrado dourado, que gira e pulsa.
  Aproximar-se atrai e coleta o fragmento. Comuns/rápidos valem 2, resistentes
  valem 3 e chefes valem 20. O primeiro nível pede 6 XP; cada próximo limiar
  pede mais 4. O excedente permanece guardado.
- **Melhorias:** coração vermelho aumenta a vida máxima em 25 e cura até 40;
  estrela de sete pontas acrescenta 7 ao dano de espada e magia; orbe azul aumenta
  a mana máxima em 24, recupera a barra e acrescenta 2,5 à regeneração.
  A escolha congela a partida e concede exatamente uma melhoria por nível.
- **Inimigos:** vermelho comum; laranja menor e rápido; verde maior e
  resistente. As variantes aparecem após 12 segundos. Todas seguem o jogador,
  inclusive com o olhar, e têm vida multiplicada por `1 + tempo / 95`.
- **Hordas:** o intervalo de spawn diminui com o tempo até 0,20 segundo.
  O spawn comum aguarda quando há 180 inimigos ativos para conter o custo
  gráfico; a vida continua crescendo. Nascem nas bordas, longe do protagonista.
- **Chefe:** aparece a cada 60 segundos efetivamente jogados. Usa as cores
  por vértice interpoladas do `04_quadrado.py`. Um anel roxo anuncia o disparo
  em leque de sete pontos roxos. É derrotável e também deixa XP.
- **Fim:** a partida é de sobrevivência contínua e termina quando a vida chega
  a zero. Enter, clique ou R permitem outra tentativa.
