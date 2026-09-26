# Alice: seis versões e todas as fichas de camadas

Objetivo integral: construir cada versão em `F:/Alice/prototipo`, desde a base corporal até o vestido finalizado, seguindo todas as fichas. O objetivo permanece incompleto enquanto qualquer versão, camada, detalhe visível ou comparação em 3D estiver pendente. Salvar checkpoints não comprova fidelidade.

Fluxo determinado pelo usuário: preservar o GLB existente da Alice Base com vestido; para cada outra versão, gerar somente um GLB completo no Tripo e trabalhar nele localmente. Refinar personagem, vestido e todas as camadas contra suas próprias fotos. Finalizar as camadas e o rig da versão atual antes de iniciar a próxima. O Chapeleiro é a versão em trabalho. O modelo Base aprovado visualmente não comprova rig, tecido ou colisões aprovados.

## Referências observadas

O índice local contém seis pastas e sessenta fichas numeradas. As fichas não têm a mesma ordem entre versões; algumas são panoramas, bibliotecas de material ou montagem final.

| Versão | Fichas e construção observada | Detalhes próprios ainda exigidos |
|---|---|---|
| Base | 1 panorama; 2 camisa/fundação; 3 corsete/cintos; 4 anáguas; 5 saia/avental; 6 mangas/colar; 7 costas/laço; 8 meias/botas; 9 acessórios; 10 materiais | Damasco creme, jacquard marinho, bordados, ferragens, braceletes, rosas; distinguir as referências violeta e Faca de Cozinha |
| Chapeleiro | 1 fundação; 2 corpete/mangas; 3 avental; 4 saia; 5 anáguas/rendas; 6 costas; 7 cartola/joias; 8 punhos/meias/botas; 9 biblioteca; 10 montagem | Cartola inclinada, cartas e naipes, relógios, xícaras, correntes, tecido verde, laço posterior |
| Cheshire | 1 panorama; 2 base interna; 3 corpete; 4 mangas; 5 anáguas; 6 saia externa; 7 avental; 8 costas; 9 acessórios; 10 calçados/materiais | Orelhas felinas, roxo/preto, emblemas de gato/sorriso, franjas, pedras violetas e ornamentos específicos |
| Coelho | 1 panorama; 2 fundação; 3 corsete; 4 corpete/mangas; 5 avental; 6 anáguas; 7 saia; 8 costas; 9 acessórios; 10 materiais | Orelhas decorativas, relógios, mostradores, damasco com motivos de relógio, correntes e pingentes |
| Lagarta | 1 vistas; 2 base; 3 corpete; 4 estrutura; 5 drapeados; 6 mangas; 7 costas; 8 acessórios; 9 tecidos; 10 montagem | Mangas longas franzidas, cascatas de tecido azul, lanternas, gemas azuis, acabamento assimétrico e drapeados próprios |
| Rainha | 1 panorama; 2 base; 3 corpete; 4 mangas/decote; 5 estrutura; 6 painéis externos; 7 painéis frontais; 8 costas; 9 acessórios; 10 materiais | Coroa, corações, tecido vermelho/preto, painéis pontudos e creme estampado, gemas rubras e ferragens específicas |

Coelho não contém um turnaround final isolado nessa pasta. A referência de conjunto está na ficha 1; `alice.jpg` é corporal. O índice usa a ficha 1 para o conjunto e preserva a imagem corporal separadamente.

## Fotos por etapa e origem da geometria

`scripts/index_alice_variants.py` indexa imagens, verifica os números 1 a 10 e registra hashes. As pranchas de contato são instrumentos de inspeção, não modelos.

`scripts/plan_alice_stage_comparisons.py` vincula as sessenta fichas e seis fotos corporais às respectivas etapas, com caminhos e hashes. A camisa deve ser comparada à sua ficha, o corsete à ficha do corsete, e assim por diante. Fotos de montagem final não substituem a referência de uma camada interna. Fichas de materiais e acessórios exigem conferir cada detalhe representado, não gerar uma malha da colagem inteira.

Os rascunhos `foundations_v*` e `skirt_layers_v*` que utilizavam corpo e roupas antigos foram rejeitados pelo usuário. Eles são preservados somente para inspeção histórica e recebem `REJECTED.json`; não entram no progresso da reconstrução nova. Os geradores que adaptavam essa geometria foram retirados.

O usuário identificou o resultado detalhado que aprovou como gerado pelo **Tripo AI**. Tripo AI e TripoSR não são o mesmo gerador. A imagem aprovada serve de referência para a definição do rosto, cabelo, mangas, rendas, bordados e botas; cada camada continua sendo comparada à sua própria ficha. Por instrução posterior, preservar o GLB da Alice Base aprovado; gerar somente os conjuntos das outras versões. O ensaio anterior do corsete Chapeleiro foi rejeitado pelo nível de detalhe e permanece disponível somente para inspeção das diferenças.

O fluxo solicitado usa o **Tripo Studio na aba do Edge**: enviar as vistas da foto do conjunto, conferir a configuração e o custo, gerar uma vez, baixar somente o GLB na pasta Downloads e importar o arquivo novo no Blender. Usar a maior fidelidade disponível sem recursos premium. Recursos exclusivos de assinantes, geração em partes e textura 8K ficam desligados; não contratar upgrade nem comprar créditos. A configuração observada para o Chapeleiro usa H3.1, malha Ultra, textura 4K, PBR e limite de dois milhões de polígonos. Frente, lateral e costas são recortes documentados da foto original, enviados no modo de várias vistas do mesmo modelo. A geração única do Chapeleiro consumiu 55 créditos, com saldo passando de 675 para 620. O custo deve ser conferido antes de cada geração, pois depende das opções e do serviço. Não gerar em lote, nem riggar, animar ou refazer texturas no serviço pago.

Registrar a foto original e seu hash, coordenadas de recorte, configurações observadas, identificação do modelo novo no Studio, custo e hash do arquivo baixado. O GLB novo completo é o ponto de partida para o refinamento local das camadas dessa versão. A reutilização do GLB Base é a exceção explicitamente autorizada pelo usuário; os rascunhos antigos rejeitados das demais versões continuam excluídos. Na comparação de uma camada, usar sua própria ficha. Fichas com várias peças exigem conferir cada componente; uma colagem inteira não representa uma peça única. Um resultado bem-sucedido continua aguardando revisão visual. Renders de quatro vistas, revisão de todos os componentes, rig, tecido e colisões permanecem necessários. A instalação local do CLI não comprova autenticação nem geração concluída.

`scripts/reconstruct_alice_cpu.py` executa inferência real TripoSR usando exclusivamente a foto, registra seu recorte e a segmentação e extrai uma superfície 3D. Não importa nenhum GLB/FBX/BLEND anterior e não produz geometria substituta quando a inferência falha. O primeiro ensaio corporal produziu uma malha, mas perdeu rosto, dedos e cachos; foi rejeitado por comparação visual. Não é uma Alice fiel nem um corpo aprovado.

`scripts/reconstruct_alice_trellis2.py` utiliza o cliente oficial do demonstrador Microsoft TRELLIS.2, mantendo a sessão entre geração e extração. O serviço depende da disponibilidade e cota do provedor. A tentativa inicial retornou erro do aplicativo remoto, sem malha. Não há resultado TRELLIS.2 aprovado. A API NVIDIA TRELLIS preview configurada recusou a imagem própria com HTTP 422 (`Expected: example_id, got: asset_id`); a existência de uma credencial válida não comprova suporte a fotos próprias.

`blender/model_chapeleiro_corset_from_photo.py` modela superfícies novas para um componente da ficha 2 do Chapeleiro: corsete aberto com espessura, painéis pontudos, vivos, canais, ilhoses e amarrações em geometria. Frente e costas recebem UVs da própria ficha. Profundidade e medidas são estimativas modeladas; textura projetada conserva a iluminação da foto. Mangas, rendas e joias dessa ficha permanecem pendentes.

`blender/rig_fresh_corset_motion_study.py` liga esse componente e seus acabamentos ao esqueleto dos FBXs de movimento fornecidos, sem usar a geometria de personagem desses arquivos. Confere compatibilidade das posições de repouso, pesos normalizados e deslocamento da malha avaliada. Exporta caminhada, corrida e ataque dos FBXs e um salto novo de teste. A malha exportada contém skin e quatro clipes; isso é um ensaio inicial de um corsete, não valida todas as camadas, aparência em movimento, colisões ou física de tecido. O salto precisa de refinamento visual e de gameplay.

`blender/audit_fresh_layer_rig.py` verifica todos os componentes da camada, seus pesos, rig compartilhado e os quatro movimentos. Amostra sete poses e dezesseis vértices por componente, descontando a transformação do osso raiz para distinguir deformação de deslocamento do personagem. Registra configurações de cloth e os colliders existentes. Exige os hashes da foto, GLB e arquivo editável; um arquivo antigo não pode substituir o editável registrado. O relatório mantém movimento visual, tecido, colisões e prontidão para gameplay pendentes. Peças ajustadas podem acompanhar o torso rigidamente; camadas soltas precisam de resposta secundária própria e ensaios de colisão.

`blender/render_fresh_alice_stage.py` exige uma geração nova e a mesma foto original registrada para a etapa. Renderiza frente, perfil, costas e ¾ da geometria real, salva um `.blend` e um GLB de inspeção com orientação corrigida. `scripts/compose_alice_stage_comparison.py` coloca a foto original da etapa e seu recorte ao lado desses renders. `scripts/register_alice_stage_review.py` registra as diferenças visíveis e uma rejeição ou necessidade de refinamento. Arquivos ou fotos que mudaram de hash invalidam a comparação.

`blender/import_tripo_studio_full_model.py` importa o GLB novo baixado, confere hashes das vistas e do modelo, registra o custo observado e preserva geometria, materiais e UVs no arquivo editável. `blender/polish_tripo_chapeleiro_skin.py` faz um estudo de material para a pele em uma cópia; a máscara e os defeitos restantes precisam de revisão. `blender/extract_tripo_chapeleiro_bodice.py` separa o corpete e as mangas do novo conjunto para trabalho local. A ficha 2 continua sendo sua referência de comparação; a foto de geração do conjunto permanece registrada separadamente. Recortes, superfícies ocultas, forro, rendas e rig ainda exigem construção e revisão. Essas operações locais não gastam créditos do Tripo.

Arquivos locais: `F:/Alice/Deliverables/Alice_Variants/<versão>/`. O índice `stage_comparisons.json` mantém etapas pendentes e resultados rejeitados explicitamente; não existe aprovação automática por número de polígonos, textura, render ou presença de arquivo.

## Executar

```powershell
python scripts/index_alice_variants.py
python scripts/plan_alice_stage_comparisons.py
$env:ALICE_STAGE_ROOT='F:/Alice/Deliverables/Alice_Variants'
node server.js
```


Abrir `/alice/layers` para selecionar uma versão e uma foto de etapa. A foto original muda com a seleção; uma etapa sem malha permanece vazia, sem recorrer ao modelo final. Resultados rejeitados mostram as diferenças observadas e continuam disponíveis para comparação em 3D. O repositório inclui o ensaio anterior rejeitado da ficha 2 e o GLB completo novo do Chapeleiro, com 1.890.825 triângulos, sua foto original e comparação de quatro vistas. O conjunto é identificado separadamente, por `kind:full-model` e número nulo; sua existência não conclui nenhuma ficha numerada. A prévia do conjunto contém o primeiro polimento local de material, sem rig, e permanece `needs_refinement`. Não representa as seis versões concluídas. A origem e o custo estão em `data/alice-stages/alice_chapeleiro_full/provenance.json`.

`scripts/package_alice_stage_preview.py` copia etapas explicitamente selecionadas, confere hashes e grava caminhos relativos para uma prévia portátil. A API resolve esses caminhos a partir da pasta do índice. O arquivo `stage_comparisons.json` mantém `completed:false` e registra o escopo parcial.

## Atualizações da galeria por commit

A galeria em `https://project-alice.gamefy.games/galeria` lê `Content/Assets/3D/<categoria>/<slug>.glb` do ramo `main` de **programador-powershell/project-alice-game**. O item do vestido Chapeleiro usa `Content/Assets/3D/personagens/alice-vestido-chapeleiro.glb`. O commit inicial com o novo modelo é `88b525c`; o conjunto fica disponível no mesmo item e os próximos refinamentos atualizam esse caminho por novos commits, preservando o histórico. A página informa atualização automática a cada 60 segundos, sem deploy do portal.

`scripts/package_alice_gallery_update.js --generation <generation.json> --comparison <comparison.json> --game-root <checkout-do-jogo>` prepara esse checkpoint no repositório do jogo. Confere a origem Tripo, custo, configuração sem premium, GLB volumétrico e hashes da foto e dos quatro renders revisados antes de copiar. Rejeita uma extração de camada como substituta do conjunto. Copia o modelo, a referência e a comparação, e registra `allLayersFinished:false`, movimento/colisões pendentes e `nextVariantMayStart:false`. A preparação não faz commit nem push; estes são executados diretamente no ramo solicitado, sem PR e sem reescrever commits anteriores. Os arquivos de proveniência protegidos do jogo ficam preservados.

Para o ensaio CPU, instalar as dependências em um ambiente separado: PyTorch CPU, TripoSR oficial, OmegaConf, Transformers, Pillow, NumPy, rembg/ONNX Runtime, Trimesh e PyMCubes. O script recebe `--engine`, `--weights`, `--source`, `--output` e, para uma peça de ficha, `--crop LEFT TOP RIGHT BOTTOM`. Usar um diretório novo por tentativa, preservando seus registros. O recorte deve isolar a peça observada; ele não representa todas as peças de uma ficha como concluídas.

O teste de identidade das etapas é executado com `node --test tests/alice_stages.test.js`. Ele verifica que a foto de outra camada, geometria reutilizada e arquivos alterados não podem passar como evidência da etapa atual; não mede semelhança artística.

## Auditoria exigida antes da conclusão

Todas as camadas reais devem compartilhar um rig compatível com Alice. Caminhada, corrida, salto e ataque precisam deformar a malha, e o vestido precisa acompanhar os movimentos de um jogo Soulslike. Nas camadas soltas, conferir resposta secundária do tecido, colisão com corpo/pernas e colisões entre forro, anáguas, saia, avental, mangas e acessórios. Pesos rígidos nos quadris ou ossos extras sem comportamento testado não satisfazem esse requisito. Materiais e fotos de biblioteca não são camadas riggadas; suas peças correspondentes precisam cumprir os testes.

Para cada versão: corpo/rosto/cabelo coerentes com a referência; todas as camadas internas e externas; mangas, costas, laços, rendas e acabamentos; meias/botas; todos os ornamentos e acessórios de sua ficha; UVs, estampas, materiais e detalhes; conferência de frente/perfil/costas e cortes entre camadas; geometria tridimensional verificável e arquivos editáveis. Fichas de panorama/material/montagem exigem conferir o conjunto, não criar uma cópia com outro nome.

Rig e colisões adaptados ainda exigem inspeção e ensaios. Ausência de erros no Python, existência de arquivos, contagem de polígonos e renders isolados não aprovam fidelidade integral nem prontidão para Unreal.
