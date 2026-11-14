# Área de contato sob medida

[Catálogo de skills](../../../README.pt-BR.md) · [English](README.md) · [Instruções e comandos da skill](SKILL.md)

Em uma peça em L, uma máscara retangular de suporte pode ocupar o canto vazio e alcançar uma peça vizinha. Com Custom footprint, você escolhe um contorno que acompanha o corpo fixo, posiciona os contatos nas paredes medidas e reserva espaço para aberturas e articulações.

## Planeje a área de contato

> Planeje suporte até 3 mm de altura nesta carcaça em L. Siga o contorno medido, encoste nas paredes fixas e deixe livre o recuo da dobradiça. Mostre primeiro o plano.

1. Use um projeto 3MF completo da família Orca/Bambu, em milímetros. As cópias do conjunto devem estar em pé, apoiadas na mesa e na escala original. Consulte o relatório de geometria e o desenho para escolher as peças fixas, as direções de contato e o espaço que a dobradiça ocupa ao se mover. [Guia de geometria](../../analysis/analyze-3d-geometry/README.pt-BR.md)
2. Escolha a forma e defina a altura máxima. O exemplo usa um polígono côncavo e uma área protegida no recuo. Substitua as medidas do exemplo pelas do seu projeto. [Exemplo de polígono](examples/custom-polygon.json) · [Opções de forma e folga](references/options.md)
3. Confira o **plano em JSON** e seu relatório. Verifique os contatos propostos, os ângulos rejeitados, a cobertura do bloqueador superior e a sobreposição das máscaras com as peças vizinhas. O planejador lê o 3MF. O comando grava no arquivo de regiões uma **lista** de máscaras que pedem ou bloqueiam suporte no fatiador.

Um pedido de planejamento termina na lista de regiões. Para preparar a peça, passe a lista ao Prender3D junto com as configurações revisadas de suporte manual, em arquivo separado. Se usou a API Python, a lista está em `result["regions"]`. No fatiamento nativo novo, confira a largura das linhas de extrusão perto da dobradiça. Os pés do suporte e o brim podem avançar além da máscara. Entregue o **3MF preparado** e mantenha o G-code temporário, sem editá-lo. Um teste físico verifica o movimento da dobradiça e a remoção do suporte. [Guia do Prender3D](../prender-3d/README.pt-BR.md)

[Ilustração conceitual das máscaras de suporte](../../../assets/previews/custom-footprint.gif)
