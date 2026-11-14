# PrenderPolvo3D

[Catálogo de skills](../../../README.pt-BR.md) · [English](README.md) · [Instruções e comandos da skill](SKILL.md)

O centro de um polvo articulado precisa de apoio, e os vãos entre os segmentos dos braços precisam ficar livres. O PrenderPolvo3D adapta o Prender3D a uma família de polvos de oito braços. Ele posiciona **oito contatos baixos entre os braços e um dentro do corpo fixo**, fora do encaixe.

## Prepare um polvo compatível

> Confira se a geometria deste polvo é compatível. Se for, apoie só os primeiros 3 mm da base fixa. Deixe as articulações dos tentáculos e o encaixe livres. Não use brim no polvo nem na árvore de suporte.

1. Instale PrenderPolvo3D junto com Prender3D. Execute o detector no projeto 3MF completo da família Orca/Bambu, já salvo. O comando de aplicação altera **todos os conjuntos compatíveis** no arquivo. Se o pedido abranger apenas um entre vários conjuntos compatíveis, use a API Python com o ID da raiz desse conjunto. [Detector](scripts/detect_octopus.py) · [Guia do Prender3D](../prender-3d/README.pt-BR.md)
2. Feche o projeto salvo antes de preparar as máscaras nativas de suporte. Oito bloqueadores protegem os braços. Um bloqueador superior acompanha o corpo fixo. Meça o limite de referência de 3 mm a partir da mesa, na **base comum**. A altura da cabeça decorativa pode variar.
3. Em um fatiamento nativo novo, siga os nove apoios da mesa até o corpo fixo. Confira o contato acima da primeira camada, a camada mais alta de suporte, a abertura do encaixe e cada articulação de cada cópia. Na primeira camada, confirme que o fatiador deixou o polvo e a árvore de suporte sem brim.

Salve os ajustes aprovados no projeto atual e fatie de novo. **Entregue o 3MF preparado**, com a geometria articulada, a pintura e a posição das peças preservadas. Inspecione o G-code temporário do fatiador sem editá-lo. Uma pequena impressão física verifica se o suporte se solta sem danificar a peça e se os braços se movem livremente.

[Ilustração conceitual dos nove contatos](../../../assets/previews/prender-polvo-3d.gif)
