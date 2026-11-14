# Destacar relevo 3D

[Catálogo de skills](../../../README.pt-BR.md) · [English](README.md) · [Instruções e comandos da skill](SKILL.md)

A imagem de referência mostra o contorno de um emblema. A peça determina quanto esse contorno pode subir e até onde sua raiz colorida pode entrar sem alcançar um furo. A skill usa a referência e as medidas da peça para criar geometria imprimível acima da face e dentro dela.

## Transforme uma imagem em contorno elevado

> Faça um contorno branco em relevo no escudo desta placa. Use a largura da referência, preserve a abertura central e mostre em quais camadas o filamento branco entra abaixo da superfície.

1. Alinhe o desenho a uma borda medida na face da peça. Marque a abertura e meça a espessura da parede atrás do contorno. Escolha a altura externa e a profundidade da raiz que cabem nessa parede. [Alinhamento da imagem à superfície](references/image-and-surface.md)
2. Para uma face plana, o script opcional transforma um **polígono revisado em milímetros** em um STL fechado do relevo. O escudo do exemplo tem uma abertura central. Uma face curva exige uma projeção sobre a superfície medida. [Polígono de exemplo](examples/shield-mask.json) · [Script para faces planas](scripts/build_relief.py)
3. Adicione o relevo ao conjunto existente do 3MF como uma peça separada e atribua o slot do filamento branco. Preserve o furo, a pintura original e os outros componentes. Fatie o projeto salvo. Procure **extrusão branca abaixo e acima da face original**. Se o fatiador atribuir as camadas da raiz à cor da base, ajuste a prioridade dos volumes ou separe os sólidos no 3MF e fatie de novo.

**Na preparação da peça, entregue o 3MF configurado.** Se o pedido for apenas pela malha do relevo em uma face plana, a entrega pode terminar no STL conferido. Inspecione o G-code temporário do fatiador sem editá-lo. A impressão física verifica a união da raiz com a base, o acabamento ao toque e a aparência da cor.

[Ilustração conceitual do contorno e da raiz embutida](../../../assets/previews/destacar-relevo-3d.gif)
