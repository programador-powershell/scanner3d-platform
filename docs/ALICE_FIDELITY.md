# Alice: referência, origem e evidência

## Problemas corrigidos

- `python/eagle_vlm.py` aprovava sem modelo e atribuia notas fixas a esqueleto/músculos. Agora a ausência de inferência permanece desconhecida, com reprovação automática e nota nula.
- O juiz legado avaliava apenas referências, sem render do portão, e gerava notas aleatórias quando o VLM falhava. Agora o render real é obrigatório e seus bytes têm hash registrado.
- `build_stage.py` podia exportar cubos, planos e esferas como corpo/camadas/personagem final. Os pontos de entrada agora exportam uma malha real explicitamente importada; não há substituição por primitivas.
- O full build tinha tentativas ilimitadas e podia aceitar `character.glb` de uma execução anterior. Agora cada execução tem diretório novo, prazo, captura de erros e verificação dos artefatos.
- A interface tratava etapas sem GLB como prontas e tinha um modo de aprovação sem juiz. Agora aguarda o artefato real e pausa quando falta análise ou há divergência.
- O arquivo detalhado existente no jogo contém cinco LODs sobrepostos e um atlas ligado a emissão. A importação seleciona um LOD e recupera o mapa de cor existente, sem sintetizar texturas.

## Assets e escala

Origem: `programador-powershell/project-alice-game`, commit `f6e534865a7b3432b6c7b374e8e10921905b4e4c`.

| Arquivo | Origem e função | O que não prova |
|---|---|---|
| `data/assets/alice-detail.glb` | FBX original, LOD3, 249.975 triângulos, atlas 2048 px | Rig, camadas independentes, física e fidelidade total |
| `data/references/alice/alice-source.glb` | GLB anterior do jogo, 36.399 triângulos, 33 juntas | Material do vestido e boa deformação |
| `data/assets/alice-restored.glb` | Projeção do turnaround na malha anterior, 34.135 triângulos ativos após excluir o corpo-template | Albedo capturado, superfícies ocultas e simulação |
| `data/references/alice/turnaround.jpg` | Imagem original enviada pelo usuário | Escala absoluta e partes não observadas |

`profile.json` registra recortes, eixo frontal, escala de trabalho e detalhes observáveis. A altura de 1,704 m é calibração de apresentação, não uma medida derivada da imagem. As dimensões no parser GLB são de malha local sem pose; o visualizador calcula os limites efetivos da cena e do skinning para enquadrar.

Os relatórios `.report.json` incluem hashes e créditos. O atlas do FBX e as cores projetadas têm iluminação incorporada; conectá-los a Base Color melhora a renderização, mas não os transforma em albedo fisicamente capturado.

## Evidência por versão

`POST /api/alice/evidence` recebe três PNGs RGBA, 440×850, e a identidade/hash da malha atual. Rejeita uma versão desatualizada e salva renders + relatório. O servidor confere arquivos e associação, não consegue provar que um cliente arbitrário realmente renderizou aquela geometria. O relatório mantém `fidelityVerified:false` e `awaiting_visual_review`. Os renders gerados diretamente no Blender são uma segunda fonte local de inspeção.

Os controles de câmera, sobreposição e foco são instrumentos de inspeção. Marcar detalhes ou registrar imagens não valida automaticamente rosto, tecidos, bordados ou narrativa.

## Aprendizado com TrackEverything

O [repositório indicado](https://github.com/ayushjain1144/trackeverything) ainda anuncia código a publicar. O [artigo de 24/09/2026](https://arxiv.org/abs/2609.30222) descreve tracks persistentes de cena em coordenadas 3D e deduplicação por voxels entre janelas de vídeo. Isso é rastreamento de pontos ao longo de vídeo, não geração automática de uma personagem completa a partir de um turnaround.

Aplicação conceitual nesta correção: uma geometria persistente deve ser observada por câmeras coerentes em várias vistas, preservando sua identidade e origem. Os hashes associam a evidência à versão do asset; não implementam deduplicação espacial por voxels. Esta branch não executa TrackEverything, LocateAnything, física de roupa ou treinamento de reconstrução. Uma integração real depende do código/pesos e de sequências adequadas, além de testes próprios.

## Verificação local desta alteração

- Importação do FBX com Blender 4.5.9 LTS portátil, verificando o SHA-256 do arquivo original.
- Exportação real pelo endpoint de build: GLB, FBX com textura incorporada, .blend e três renders transparentes.
- Inspeção em navegador de frente, perfil, costas, argila, topologia e aproximação de detalhes.
- Testes Node para validar o contrato da API e impedir aprovação por falta de evidência.

Não foi executada Unreal Engine 5.7, nem testado gameplay. A semelhança melhorou com o asset detalhado existente, mas o resultado não é certificado como reprodução integral do Project Alice.
