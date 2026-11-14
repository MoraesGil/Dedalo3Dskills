# Dedalo3Dskills

[![Licença: MIT](https://img.shields.io/badge/License-MIT-64e3a6.svg)](LICENSE) · [English](README.md) · [As seis skills](#catálogo-de-skills) · [Instalar](#instalar)

Estas skills nasceram de problemas que encontramos na impressora: uma torre de purga que quebra no meio de uma peça alta, um cabo que balança na mesa, um suporte que trava a articulação. **Quando você pede a preparação da peça, recebe o projeto `.3mf` configurado.** Você pode abri-lo e fatiá-lo de novo. O fatiador gera o G-code; as skills leem uma cópia temporária para conferir o resultado.

## Torre Burj: da mesa de impressão para a estante

Torre de purga quebrando no meio de uma impressão alta? Foi para evitar isso que criamos a **Burj**. Inspirada na **Burj Khalifa**, ela começa com uma base larga de três alas e afina conforme a peça perde largura. A base dá mais contato com a mesa. Depois da última troca de ferramenta, a peça pode continuar subindo sozinha. Ao tirar a torre da chapa, você pode guardá-la como um pequeno edifício decorativo.

[![Ilustração técnica de uma peça alta ao lado da torre Burj. A torre tem base larga de três alas e termina mais estreita, abaixo do topo da peça.](assets/previews/burj-tall-print.svg)](assets/previews/burj-tall-print.svg)

*Neste exemplo, o vaso de 184,8 mm fica ao lado da Burj. A torre verde tem 48 mm de largura na base e 24 mm no topo. Ela termina na última troca, em Z = 144 mm.*

Já usamos **PETG na peça e PLA na interface do suporte na mesma impressão**, em cabeçotes separados. A cada troca real, o novo cabeçote faz uma passagem completa na Burj antes de voltar à peça ou ao suporte. A prime tower nativa fica desligada: só há uma torre na mesa.

[Veja o formato da torre, o uso de PETG com PLA e o que foi testado →](skills/printing/torre-burj/README.pt-BR.md)

## Prender3D: como firmar um cabo alto

Um cabo alto pode balançar mesmo com uma boa primeira camada. Um brim mais largo ajuda junto à mesa, mas não apoia a parede acima dela. Criamos a **Prender3D** para encostar suportes baixos e removíveis do fatiador nas laterais *fixas* da peça. Você escolhe onde aceita marcas de contato e quais encaixes, roscas ou articulações precisam ficar livres. A forma da peça permanece igual.

[Veja onde os apoios encostam e como conferir o contato →](skills/printing/prender-3d/README.pt-BR.md)

## Catálogo de skills

Abra o nome da skill para ver por que ela existe, um exemplo de pedido e o resultado esperado. Clique na miniatura para ampliar a ilustração ou ver a animação.

| Prévia | Guia da skill | Quando usar |
| --- | --- | --- |
| [<img src="assets/previews/burj-tall-print.svg" width="156" alt="Torre Burj ao lado de uma peça alta">](assets/previews/burj-tall-print.svg) | [Torre Burj](skills/printing/torre-burj/README.pt-BR.md) | Incluir uma torre de purga e preparação dimensionada pela peça e pelas trocas reais. |
| [<img src="assets/previews/prender-3d.gif" width="156" alt="Apoios baixos em um cabo">](assets/previews/prender-3d.gif) | [Prender3D](skills/printing/prender-3d/README.pt-BR.md) | Firmar paredes fixas sem fechar o encaixe nem acrescentar uma base sólida. |
| [<img src="assets/previews/analyze-3d-geometry.gif" width="156" alt="Seção transversal de uma peça">](assets/previews/analyze-3d-geometry.gif) | [Análise de geometria 3D](skills/analysis/analyze-3d-geometry/README.pt-BR.md) | Medir a seção da primeira camada e identificar áreas que devem ficar livres. Gera um relatório. |
| [<img src="assets/previews/custom-footprint.gif" width="156" alt="Zonas de contato no contorno da base">](assets/previews/custom-footprint.gif) | [Área de contato sob medida](skills/printing/custom-footprint/README.pt-BR.md) | Escolher onde o suporte pode encostar. O planejador devolve um plano em JSON. |
| [<img src="assets/previews/prender-polvo-3d.gif" width="156" alt="Articulações protegidas no polvo">](assets/previews/prender-polvo-3d.gif) | [PrenderPolvo3D](skills/printing/prender-polvo-3d/README.pt-BR.md) | Firmar o corpo fixo de um polvo compatível e deixar os oito braços livres. |
| [<img src="assets/previews/destacar-relevo-3d.gif" width="156" alt="Contorno em relevo sobre a peça">](assets/previews/destacar-relevo-3d.gif) | [Destaque em relevo 3D](skills/printing/destacar-relevo-3d/README.pt-BR.md) | Transformar o contorno de uma imagem em relevo no projeto. O script para superfícies planas gera um STL intermediário. |

As ilustrações mostram a geometria prevista. A [galeria de animações](assets/previews/README.md) inclui versões estáticas. Não são fotos de impressão nem gravações do fatiador.

## Fatiar sem abrir a interface gráfica

Nosso [Snapmaker Orca MCP e seu launcher Bash](https://github.com/MoraesGil/snapmaker-orca-mcp) usam o **motor nativo do Snapmaker Orca instalado no Mac**. Indique o `.3mf` salvo e a mesa de produção. O agente pode chamar `slice_3mf`; pelo terminal, basta executar o launcher. Isso poupa o tempo de abrir a interface, escolher a mesa e exportar a cada ajuste. [Veja o comando e o exemplo para MCP](docs/slicing.md).

Confira as trajetórias do fatiamento nativo. Se algo sair errado, corrija o **projeto** e volte a fatiar. Entregue o `.3mf` salvo que reproduz as trajetórias esperadas. O G-code de validação fica na pasta de trabalho.

## Instalar

Use o [skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills@latest add MoraesGil/Dedalo3Dskills --skill analyze-3d-geometry custom-footprint prender-3d prender-polvo-3d torre-burj destacar-relevo-3d
```

Selecione seu agente. A instalação padrão fica no projeto atual. As skills de análise, área de contato e polvo usam `prender-3d`. Para planejar a área de contato, instale também `analyze-3d-geometry`. A Burj é independente. Instale as dependências indicadas em cada skill; o instalador pode não resolvê-las automaticamente.

Para usar o código do repositório, crie um ambiente virtual Python e instale as dependências:

```bash
git clone https://github.com/MoraesGil/Dedalo3Dskills.git
cd Dedalo3Dskills
python -m pip install -r skills/printing/prender-3d/requirements.txt
```

A skill de relevo tem [dependências Python próprias](skills/printing/destacar-relevo-3d/requirements.txt). Python 3.12 é a versão testada. Leia o `SKILL.md` antes de executar os scripts. O pacote não inclui fatiador, preset de impressora ou conexão com impressora.

## Organização

```text
skills/analysis/<nome>/       Inspeção em modo somente leitura
skills/printing/<nome>/       Preparação da impressão
  README*.md                 Guia da skill em inglês e português brasileiro
  SKILL.md                   Instruções para o agente
  scripts/                   Implementação incluída na instalação da skill
  references/ ou examples/   Contratos e entradas quando necessários
tools/dedalo3d/               Comandos curtos para uso no checkout
assets/previews/             GIFs conceituais, posters e catálogo
tests/                       Casos sintéticos e verificações
```

Cada implementação fica na skill responsável. Os comandos em `tools/` apenas a chamam, sem duplicar algoritmos. Veja [ferramentas e comandos](tools/README.md).

## Compatibilidade e verificações

Os leitores trabalham com **3MF completo da família Orca/Bambu, com metadados**. STL e 3MF só de malha precisam de preparação prévia. O motor nativo de referência é o **Snapmaker Orca**. Outros motores exigem validação própria.

Os testes verificam geometria sintética, preservação de metadados e regras de cálculo e auditoria. No piloto nativo U1 da Burj, os comandos explícitos passaram. A auditoria completa continua pendente, pois o parser não conhece o interior das macros de firmware. Isso não comprova adesão física, movimento livre ou limpeza em todos os materiais. Confira as trajetórias finais e faça um teste físico pequeno.

Leia [compatibilidade](docs/compatibility.md), [retenção](docs/retention-workflow.md) e [fatiamento nativo](docs/slicing.md). Nenhuma ferramenta inicia ou controla a impressora.

```bash
python -m pip install -r requirements-dev.txt
python scripts/validate_repository.py
python -m unittest discover -s tests -v
```

Os testes criam projetos temporários. A [receita de GitHub Actions](docs/ci/README.md) fica em `docs/ci`; ela não está ativa. O renderer usa Pillow como dependência opcional separada.

## Próximas candidatas

Nosso jardim 3D também tem skills de pontes com interface PETG, peso extra, fragilidade, auditoria de pintura em múltiplas vistas e preparação geral de impressão. Cada uma precisa de revisão de escopo, exportação pública e licença antes de entrar no catálogo. Este pacote não inclui skills vazias nem modelos privados de clientes.

Para contribuir, apresente um problema concreto, uma skill com limites claros e uma verificação reproduzível. Veja [CONTRIBUTING.md](CONTRIBUTING.md).

## Licença e inspiração

Skills, código, ilustrações e textos originais usam **[MIT](LICENSE)**. Uso comercial, alteração e redistribuição são permitidos nos termos da licença. Modelos, dependências e software de impressora mantêm suas licenças. [Burj NOTICE](skills/printing/torre-burj/NOTICE.md) registra a origem limitada dos módulos Burj exportados.

A organização se inspira no [repositório de skills de Matt Pocock](https://github.com/mattpocock/skills): skills focadas, catálogo claro e instalação direta. A forma Burj se inspira na Burj Khalifa. Nossas ferramentas de preparação e ilustrações sintéticas são trabalho original.
