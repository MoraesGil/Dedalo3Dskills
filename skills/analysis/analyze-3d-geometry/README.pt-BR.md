# Analisar a geometria 3D

[Catálogo de skills](../../../README.pt-BR.md) · [English](README.md) · [Instruções e comandos da skill](SKILL.md)

Um cabo visto de cima pode parecer largo e tocar a mesa só por um anel estreito. A largura total inclui o espaço vazio no centro desse anel. Esta skill mede uma seção horizontal na primeira camada para você escolher os pontos de apoio a partir da geometria do conjunto.

## Peça uma medição

> Meu cabo tem um encaixe aberto. Use a altura da primeira camada definida no projeto. Mostre a área de material nessa seção de cada cópia e indique os cortes incompletos. Preserve o arquivo.

1. Forneça o 3MF salvo da família Orca/Bambu com os metadados do projeto. Instale a skill junto com Prender3D para usar o leitor de geometria compartilhado. [Instalação](../../../README.pt-BR.md#instalar)
2. Informe a altura da primeira camada desse projeto. Com uma camada de 0,20 mm e mesa em Z = 0, o leitor corta em Z = 0,10 mm. Ele considera a posição e a orientação de cada cópia e desconta os volumes negativos que conseguiu resolver nessa altura.
3. No relatório JSON, localize o conjunto e a mesa solicitados. Confira `on_bed`, `section_complete` e `warnings` antes de usar a área em `net_geometric_area_mm2`. O hash identifica o 3MF medido.

**O resultado é um relatório de geometria em modo somente leitura.** O projeto permanece intacto. O corte descreve o material em uma única altura. O fatiamento nativo mostra as linhas de extrusão previstas. Um teste físico verifica a adesão à mesa.

[Ilustração conceitual da medição](../../../assets/previews/analyze-3d-geometry.gif)
