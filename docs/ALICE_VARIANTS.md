# Alice: seis versões e todas as fichas de camadas

Objetivo integral: construir cada versão em `F:/Alice/prototipo`, desde a base corporal até o vestido finalizado, seguindo todas as fichas. O objetivo permanece incompleto enquanto qualquer versão, camada, detalhe visível ou comparação em 3D estiver pendente. Salvar checkpoints não comprova fidelidade.

Fluxo determinado pelo usuário: preservar o GLB existente da Alice Base com vestido; para cada outra versão, gerar somente um GLB completo no Tripo e trabalhar nele localmente. Refinar personagem, vestido e todas as camadas contra suas próprias fotos. Finalizar as camadas e o rig da versão atual antes de iniciar a próxima. O Chapeleiro é a versão em trabalho. O modelo Base aprovado visualmente não comprova rig, tecido ou colisões aprovados.

Correção explícita do usuário: **o vestido exterior já está no GLB completo; as
fichas servem à construção das camadas inferiores que faltam.** Recortar o
vestido do scan e substituí-lo por peças projetadas das fichas foi uma
interpretação incorreta. Os ensaios de extração de corpete/mangas ficam como
histórico rejeitado desse método e não devem ser continuados. O fluxo atual
preserva o exterior inteiro e trabalha em cópias: polimento, redução inicial,
retopologia para deformação, UVs e bake de detalhes/PBR, seguidos de construção
dos interiores, rig compartilhado e tecido. Redução automática não é aprovação
de retopologia anatômica nem de aparência.

O ZIP `BystedtsClothBuilder_1_0_1.zip` fornecido pelo usuário tem SHA-256
`132440c150ce09a04d5e7b19de57485cfcf0d630914fd63201c9835abca0dab8`.
`install_bystedts_cloth_builder.py` instalou e habilitou o add-on de Daniel
Bystedt no Blender 5.2.1 e registrou a biblioteca de assets. Os grupos originais
`Post sim cloth`, `Solidify` e `UV unwrap solidified` vêm desse pacote. Os
personagens/roupas genéricos da biblioteca não entram na Alice. Código do
add-on: GPL-3.0-or-later, conforme cabeçalho do pacote; origem:
https://3dbystedt.gumroad.com/l/bystedtsClothBuilder e tutorial:
https://www.youtube.com/watch?v=EAraCGAaLoU.

`build_chapeleiro_inner_cloth.py` constrói superfícies quad novas para a anágua
creme, seu babado e três níveis pretos da ficha 1. Usa o Cloth Builder real para
grupos de pinning/cloth e o grupo original de Geometry Nodes após a simulação.
Espessura interna de 0,00055 unidades; separação de costuras em zero. No arquivo
carregado, o armazenamento UV passa de `FLOAT_VECTOR` para `FLOAT2`, necessário
para virar mapa UV no Blender atual. Entradas do modificador são configuradas
pela interface RNA 5.2. Nenhum vértice do exterior é alterado nessa construção.
O ensaio é parcial: renda, camisa, corsete, bloomers, ligas/meias, rig e ensaios
de movimento/colisão ainda precisam de trabalho. A presença do modificador
Cloth não comprova simulação aprovada nem exportação de física ao GLB.

`refine_chapeleiro_foundation_cloth.py` acrescenta ao mesmo fluxo anáguas com
franzidos de espaçamento variável, suporte preto contínuo até a cintura e
corsete creme com canais de barbatana, fechos frontais, ilhoses e cruzamentos
traseiros em geometria. A renda é traçada de dois recortes documentados da
própria ficha 1 por `trace_chapeleiro_foundation_lace.py`: os contornos viram
superfícies com aberturas reais, espessura pelo grupo original de Bystedt e UV
fotográfico preservado além do UV automático. Mapas normais de trama e renda
entram no GLB; nenhum card plano ou alpha substitui essas aberturas.

Babados seguem os respectivos suportes por Surface Deform antes de Cloth,
com raízes dinâmicas; rendas seguem os babados por outro vínculo real.
`audit_chapeleiro_foundation_carriers.py` mede aberturas pela topologia e
movimento dos vínculos em um teste de translação no frame 1, sem salvar
alterações. Esse ensaio não aprova rig, simulação durante ações ou colisões.
As sombras e dobras da foto afetam o traçado; a repetição ao redor das peças é
inferida. Camisa, bloomers, ligas, meias, acabamentos e o movimento completo
continuam pendentes. O item de fundação publicado pelo script de embalagem
fica separado do GLB completo e mantém explícito o estado em refinamento.

`refine_chapeleiro_foundation_blouse.py` continua o mestre da fundação, mantendo
as 83 peças anteriores e o exterior inteiro. Acrescenta 21 peças da própria
ficha 1: camisa com decote aberto e duas cavas reais, mangas bufantes franzidas,
punhos/babados, acabamento do decote, carcela, botões e pequeno ornamento de
latão, além de laços vazados de fio nas rendas dos punhos e do decote. As mangas
partem das bordas reais das cavas; os punhos e o decote também
partem das bordas do tecido, sem tampas ou recortes do vestido exterior.

Cada uma das três superfícies de camisa/manga tem uma única malha de simulação
antes da espessura. A superfície visível e seus acabamentos seguem essa malha;
o grupo original de Bystedt acrescenta espessura e UV após a deformação. Somente
o alvo avaliado recebe triangulação para evitar polígonos côncavos durante o
vínculo; a malha editável de tecido mantém seus quads. Isso
evita usar a saída espessa dos nós como alvo de Surface Deform. As malhas de
simulação ficam no Blender editável e não são exportadas como roupa duplicada.
Os modificadores antigos são desativados somente durante a construção e
restaurados antes de salvar e exportar; a geometria anterior é conferida por hash.

A auditoria mede os cinco encontros reais: duas cavas, dois punhos e decote.
Confere um solver por peça, UVs avaliados e todos os seguidores da hierarquia,
sem depender de uma contagem fixa de peças. São verificações de construção no
frame 1, não aprovação de fidelidade, rig ou simulação de ações.

`refine_chapeleiro_foundation_lower.py` acrescenta bloomers com uma superfície
conectada de cintura, entrepernas e duas pernas, ligas com quatro tiras e
ferragens, e meias com malha fechada nos pés. As medidas das pernas vêm apenas
dos ossos do FBX de caminhada; nenhuma roupa ou corpo desse FBX é incorporado.
O entrepernas compartilha vértices reais. A renda das barras dos bloomers usa
um terceiro recorte da própria ficha 1, registrado pelo traçador com
`--section bloomers`; não reaproveita a estampa das anáguas.

Bloomers e cintura das ligas recebem malhas de simulação únicas. Meias e tiras
recebem superfícies preparadas para skinning antes da espessura, ainda sem
pesos ou rig. A auditoria exige a topologia do entrepernas e dos pés e vínculos
reais de todas as peças, mantendo as 104 peças anteriores e o exterior intactos.
O renderizador permite comparar as peças escondidas isoladamente em quatro
vistas, sempre junto da foto original e do recorte documentado. A revisão
`--part-only` não substitui o conjunto completo no índice de etapas.
Caimento, ajuste às fotos, retopologia para jogo, rig, movimentos e colisões
continuam pendentes; essas construções não são camadas finalizadas.

`refine_chapeleiro_corset_edges.py` constrói babados nas bordas reais do
corsete, renda inferior traçada da mesma ficha com a costura inclinada
fotografada, laço e pontas de fita com largura e espessura. O traçador recebe
`--section corset`. A posição do nó acompanha a última fileira real de ilhoses;
as pontas seguem o perfil traseiro medido do corsete e da anágua para evitar
ficarem escondidas dentro da peça. Isso ainda exige validação em movimento.
O renderizador permite `--component-group corset` para incluir também o tecido,
canais, fechos e ilhoses anteriores na comparação isolada, sem perder as
peças cuja função não começa pelo mesmo prefixo.

`refine_chapeleiro_petticoat_cascades.py` acrescenta dois painéis laterais de
tecido, canais para os cordões, seis estações de franzido por lado, ilhoses
de latão e laços com pontas de fita. As raízes partem da borda real da anágua
creme; não são recortes do vestido exterior. Cada painel usa uma única malha
fina de Cloth, ligada à anágua antes da simulação. A superfície visível amostra
as posições avaliadas do suporte por índice de vértice, antes da espessura e
do UV original do Bystedt. As duas malhas têm a mesma ordem de vértices.
Os alvos avaliados usam diagonais fixas; os quads editáveis são preservados.

O auditor aplica temporariamente uma deformação somente ao suporte avaliado
e mede a resposta da superfície visível, sem salvar nem editar a malha bruta.
Confere também as raízes na cintura, os pontos de franzido, UVs e vínculos dos
acabamentos. Isso verifica a construção, não uma animação física ou rig.
`--component-group petticoats` inclui todas as anáguas e suas rendas na revisão
isolada. A primeira tentativa com pregas infladas foi rejeitada na comparação;
o refinamento reduz o volume, mas ainda exige vincos, caimento e acabamento
mais próximos da ficha 1. As costas não visíveis continuam inferidas.

`probe_chapeleiro_bloomers_cloth.py` realizou um ensaio de 24 quadros reais
contra volumes aproximados de pelve e coxas. O GLB resolvido foi comparado à
foto própria em quatro vistas. Dobras, cintura e punhos ainda diferem da
referência, então essa solução não entrou na fundação publicada. A evidência
está em `docs/alice-experiments/chapeleiro/bloomers-static-v051/`.

O tamanho dos arquivos não reduz o escopo solicitado. Continuar o trabalho
local em checkpoints completos; publicar o FBX no GitHub depois da validação
do rig compartilhado, movimentos e tecido. A fundação estática em refinamento
não substitui esse FBX final. Atualizações do site continuam por commits
diretos, preservando o histórico e sem PR.

`optimize_alice_whole_outfit.py` mantém o mestre inteiro e salva uma cópia com
modificador reversível de redução, preservando o atlas PBR 4K e dando prioridade
ao rosto, dedos e decote. O ensaio `whole_reduction_v027` tem 302.532 triângulos
(16% de 1.890.825). Mediu distância mestre→cópia em 20.075 amostras; isso não
substitui comparação de vistas e close-ups. A primeira comparação mostrou
distorção nas faixas das meias, portanto essa cópia sem bake não é publicada
como refinamento aprovado. `bake_alice_whole_outfit.py` transfere cor base,
roughness, metallic e normal tangente do mestre completo para o alvo, em 4K.
Os quatro renders e a foto original continuam exigidos antes da atualização
do mesmo item da galeria por commit direto, sem PR.

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

O código do portal está em **programador-powershell/project-alice-challenge**. O commit `48eaa21` corrigiu o erro do visualizador com Three.js direto, adicionou vistas de câmera e passou a usar a revisão real do blob na URL para recarregar novos refinamentos. O commit `04d3111` retirou a dependência legada do Supabase: modelos e feed são lidos do GitHub, e o login usa OAuth GitHub com sessão própria. O vínculo antigo do banco com a publicação na Vercel foi removido; o banco e seus dados não foram excluídos. A compilação de produção e o feed foram verificados localmente. Esses ajustes no site não aprovam o rig nem as camadas pendentes do Chapeleiro.

`scripts/package_alice_gallery_update.js --generation <generation.json> --comparison <comparison.json> --game-root <checkout-do-jogo>` prepara esse checkpoint no repositório do jogo. Confere a origem Tripo, custo, configuração sem premium, GLB volumétrico e hashes da foto e dos quatro renders revisados antes de copiar. Rejeita uma extração de camada como substituta do conjunto. Copia o modelo, a referência e a comparação, e registra `allLayersFinished:false`, movimento/colisões pendentes e `nextVariantMayStart:false`. A preparação não faz commit nem push; estes são executados diretamente no ramo solicitado, sem PR e sem reescrever commits anteriores. Os arquivos de proveniência protegidos do jogo ficam preservados.

Para o ensaio CPU, instalar as dependências em um ambiente separado: PyTorch CPU, TripoSR oficial, OmegaConf, Transformers, Pillow, NumPy, rembg/ONNX Runtime, Trimesh e PyMCubes. O script recebe `--engine`, `--weights`, `--source`, `--output` e, para uma peça de ficha, `--crop LEFT TOP RIGHT BOTTOM`. Usar um diretório novo por tentativa, preservando seus registros. O recorte deve isolar a peça observada; ele não representa todas as peças de uma ficha como concluídas.

O teste de identidade das etapas é executado com `node --test tests/alice_stages.test.js`. Ele verifica que a foto de outra camada, geometria reutilizada e arquivos alterados não podem passar como evidência da etapa atual; não mede semelhança artística.

## Histórico de extração do corpete — método rejeitado pelo usuário

`blender/refine_tripo_chapeleiro_bodice.py` trabalha exclusivamente sobre a
extração do novo Tripo Chapeleiro `32254621-cdf9-43bd-8297-54446796d892`, com a
foto original da camada 2 identificada por `3a7fb91e7a0724f3`. Não lê o corsete
antigo rejeitado nem a malha da Alice Base. Ajusta uma superfície nova às medidas
do scan, reconstrói a frente verde e as costas ocultas pelo cabelo, costura as
alças à malha e preserva aberturas separadas para pescoço e braços. O forro tem
espessura real; vivos, ilhós, cordões, canais e pequenos laços são geometria.
As duas mangas conservam as dobras do scan novo e usam sua própria ficha para
o acabamento. Profundidade traseira, material e detalhes invisíveis são inferidos.

O checkpoint histórico `bodice_native_shared_rig_v025` está em
`data/alice-stages/alice_chapeleiro_stage_02/`, com a foto própria da ficha 2,
GLB, Blender editável, quatro vistas, doze poses e auditoria do rig. O refinamento
`finish_chapeleiro_bodice_details.py` acrescentou cinco abas sobrepostas,
correntes com elos individuais, laços de fita, plissados e renda vazada. A revisão
lateral detectou uma ponta criada pelo deslocamento de espessura da manga;
o deslocamento normal limitado corrigiu esse defeito.

`rig_chapeleiro_sheet_two.py` liga os **40 componentes** deste arquivo, incluindo
forro e acabamentos, ao mesmo esqueleto com **74 ossos**. Usa somente ossos e
movimentos dos FBXs fornecidos, descartando suas malhas. Ajusta a pose de vínculo
aos braços do scan novo e transfere a orientação mundial das animações, evitando
aplicar duas vezes a mudança de braços de T-pose para A-pose. O GLB real contém
caminhada, corrida, ataque e um salto autoral de teste. Os pesos são normalizados,
sem vértices sem peso; o esquema de vínculo está em `shared_rig_bind.json`.

`render_chapeleiro_skin_motion.py` importa o GLB exportado e registra três poses
de cada clipe, com câmera fixa e medição de estiramento. A situação continua
**precisa de refinamento**: volume da ligação interna no ombro, dobras da manga
diferentes da foto 2, textura lateral esticada, reforços isolados pendentes e
deformações excessivas em partes da costura durante corrida/ataque.
Os laços e abas têm ossos secundários com chaves de ensaio;
isso não é simulação de tecido nem aprovação de colisões. Salto, transições e
movimento Soulslike permanecem pendentes. Não conta como camada finalizada.

`sew_native_chapeleiro_sleeves.py` recupera as dobras do mesmo Tripo novo sem
excluir motivos escuros da estampa. Modela a ligação interna, adapta a altura do
ombro e costura cada manga aos 66 vértices da cava e aos 192 vértices do punho.
Mantém as duas aberturas separadas e verifica a topologia. Os pesos seguem uma
solução harmônica sobre a superfície real, com as mesmas influências do corpete
na cava e do braço no punho. A ligação oculta e os ajustes continuam inferidos.

`audit_alice_exported_seams.py` importa o GLB real e confere as 249 amostras
exportadas dos quatro clipes. Os quatro encontros manga/corpete e manga/punho
mantiveram distância zero nessas amostras. No ataque, o percentil 95 de
estiramento das mangas chegou a 1,176; uma aresta interna de 0,368 mm atingiu
3,312 mm (9,00 vezes), portanto o movimento permanece sem aprovação. O relatório
grava os pontos e o instante dessa aresta para o próximo ajuste. Continuidade
da costura não comprova fidelidade, todos os quadros interpolados ou colisões.

`compose_alice_motion_review.py` reúne a foto original e os renders reais.
`package_alice_rig_checkpoint.py` confere os hashes da foto, GLB, Blender e
evidências, e atualiza somente a etapa selecionada no índice do repositório.
Para mangas reconstruídas, exige também a auditoria dos encontros de todos os
clipes, vinculada ao mesmo hash do GLB e à foto própria da etapa.
O arquivo `legacy_rejected_rig_audit.json` pertence ao ensaio antigo rejeitado;
`rig_audit.json` audita as peças novas deste checkpoint. Nenhum crédito adicional
foi gasto. O vestido completo publicado e a Alice Base aprovada foram preservados.

O portal publicou a remoção dos textos legados de armazenamento Supabase no
commit `ac1d9d9` de `project-alice-challenge`; build e tipos passaram, e a Vercel
confirmou a produção. Modelos e histórico continuam no GitHub.
O commit `dc1065a` removeu também a permissão residual de imagens do Supabase
em `next.config.ts`; build e publicação na Vercel passaram. A galeria em produção
lista os 35 modelos diretamente do GitHub, sem banco Supabase.

## Auditoria exigida antes da conclusão

`refine_chapeleiro_garter_cups.py` arredonda os dois reforços das ligas sem
deslocar suas bordas de união. As costuras centrais são reposicionadas sobre
o tecido e seus vínculos são refeitos. Costuras curvas com pontos reais,
faixas superiores e laços laterais com fitas planas seguem os suportes das
meias. O enquadramento da referência isolada inclui agora os dois reforços,
o cinto e as fitas; a foto original inteira continua ao lado das quatro vistas.
O auditador mede o UV e os vínculos das peças novas e verifica que os pontos
de costura são volumes fechados. O primeiro checkpoint teve tampas de fios
com UV colapsado e foi preservado localmente para rastrear a correção.
Essas verificações não aprovam tensão do tecido, rendas, rig ou movimento.

`refine_chapeleiro_garter_drape.py` trabalha o abaulado frontal e os vincos
diagonais nos reforços reais da mesma ficha. Refina os quadriláteros na direção
vertical e transfere os fios e laços existentes pelas faces da superfície
anterior. O campo de volume preserva as faixas superiores e as bordas de união;
seus hashes são conferidos no editável reaberto. O ensaio v066 deslocou a faixa
e não foi publicado; a construção seguinte limita o relevo abaixo dela.
O ensaio v067 mostrou tiras desaparecendo no novo volume, e o v068 manteve
penetração residual de cerca de 0,10 mm nos centros das faces. As fotos próprias,
quatro vistas e rejeições estão em `docs/alice-experiments/chapeleiro/`.
O v069 acrescenta amostras ao longo da largura das tiras, ajusta seus suportes
reais e transfere os fechos pela superfície anterior, preservando os encontros
no cinto e na ponta. Cada tira tem 57 linhas e cinco colunas de vértices.
`inspect_chapeleiro_garter_contacts.py` mede a projeção das superfícies reais
do GLB exportado, incluindo vértices e centros dos triângulos; o auditador do
Blender mede separadamente as malhas avaliadas. Ambos exigem folga positiva
de pelo menos 0,15 mm nas amostras em repouso.
O teste de topologia e dos encontros não aprova o caimento, encaixe no corpo,
pesos de skin, movimentos ou colisões.

`refine_chapeleiro_garter_belt.py` ajusta a faixa central e os franzidos do
cinto conforme a mesma ficha 1. Mantém o anel original onde começam as tiras,
liga os dois babados às bordas reais e acrescenta duas costuras contínuas.
A opção `--section garter` do traçador usa um trecho da renda deste cinto,
preservando a foto inteira como referência. A renda inferior tem contornos
vazados em geometria, UVs da própria foto e espessura do Bystedt; sombras do
tecido e repetições nas áreas não visíveis continuam sujeitos a revisão.

A troca da malha no Blender 5.2 remove os grupos de vértices do Cloth.
A construção repõe o esquema original, interpola os campos existentes e
recria os pinos da cintura na nova malha. O primeiro ensaio parou antes de
exportar; o diagnóstico e a ficha original estão preservados em
`docs/alice-experiments/chapeleiro/garter-belt-pin-v070/`.
O auditador confere os grupos, o suporte fino único, o anel das tiras,
os encontros dos babados, os fios fechados e os UVs avaliados. Essas medidas
não aprovam proporções finais, escala corporal, rig, movimentos ou colisões.

As quatro vistas rejeitaram a renda dos ensaios v072 e v073: mudar apenas o
material para algodão corrigiu a cor, mas não a aparência quebrada. A leitura
das bordas reais encontrou cinco segmentos longos na união da renda; pontos
ao longo desses segmentos chegaram a 11,77 mm do babado, apesar de seus
vértices terminais coincidirem com a borda. A ficha original, os quatro renders
e a rejeição estão em `docs/alice-experiments/chapeleiro/garter-belt-lace-v072/`
e `garter-belt-lace-v073/`; nenhum desses ensaios foi publicado como fundação.

`refine_chapeleiro_garter_lace_surface.py` subdivide adaptativamente a superfície
plana traçada antes de envolvê-la no babado. A métrica usa a circunferência real
do cinto e a profundidade da renda, mantém a topologia dos vazados e recompõe
os UVs próprios em cada repetição. Somente essa renda pode mudar; as outras
malhas, os suportes e o exterior inteiro precisam conservar seus hashes.
O auditador amostra os vértices e os quartos de cada segmento da união com
o babado e limita a folga de repouso a 0,25 mm. A publicação exige esse dado,
além das quatro vistas comparadas com a ficha própria. Nenhuma dessas medidas
substitui a aprovação visual nem os testes posteriores de rig e colisão.

A opção `--tessellation constrained_grid` distribui pontos conforme as dimensões
da peça e triangula as bordas no espaço original da foto, sem obrigar a malha nova
a repetir suas diagonais internas longas. `chapeleiro_lace_tessellation.py`
amostra apenas a área realmente preenchida do traçado e exige a mesma
topologia de aberturas. O espaçamento de 0,6 mm controla a amostragem plana;
o comprimento máximo final das arestas é medido separadamente. A fase da
grade evita coincidências numéricas com vértices das bordas. Essa construção
precisa passar pela leitura das malhas reais e pela comparação visual,
e ainda não representa o LOD final nem aprovação de gameplay.

O v076 conserva os vazados do traçado e reduz essa renda de 258.615 vértices
no ensaio denso para 34.165 vértices. O auditador encontrou 980 arestas na
união, com 4.900 amostras e afastamento máximo de 0,144 mm; antes, cinco
segmentos retos chegaram a 11,77 mm de afastamento. Mesmo assim, as quatro
vistas rejeitaram o acabamento: o traçado continua transformando regiões
sombreadas, onde a foto mostra fios, em aberturas grosseiras. As fotos,
renders e rejeição estão em `docs/alice-experiments/chapeleiro/garter-lace-surface-v076/`.
O diagnóstico `garter-shadow-interpretation-v077/` compara três alternativas
de contraste local, ainda sem aprovação para construir a trama. Nenhum desses
ensaios substitui a fundação publicada. Corrigir a união e o UV é progresso
de construção; ainda é necessário refazer a interpretação da renda e testar
o personagem com todas as camadas, o rig, as ações e as colisões.

O ensaio v080 usa os fios claros do recorte original e uma trama fina inferida,
construídos como fios arredondados com pontas fechadas e UVs próprios. As sombras
das dobras deixam de produzir grandes recortes na superfície. A união segue
o babado real; não se aplica espessura adicional do Geometry Nodes sobre fios
que já possuem volume fechado. Os demais tecidos mantêm seus modificadores
e suportes, e o exterior inteiro permanece preservado.

`probe_chapeleiro_garter_filaments.py` compara candidatos de linhas claras,
`trace_chapeleiro_garter_threads.py` registra os caminhos e
`refine_chapeleiro_garter_lace_threads.py` constrói a renda no editável.
O auditador mede fechamento, componentes, triângulos, UVs e a união com o babado.
Esses testes não aprovam fidelidade: a trama ainda parece vertical e uniforme
demais frente à ficha 1, e a escala, o fundo fino e as repetições ocultas são
inferidos. As quatro vistas devem permanecer junto à foto original, sem
substituí-la por uma referência gerada. O LOD, o rig e as colisões continuam
pendentes; este refinamento estático não é o FBX final.

O refinamento `refine_chapeleiro_stocking_anatomy.py` conserva a topologia conectada
das duas meias e suas aberturas na coxa. Mede o eixo das botas no mestre inteiro,
sem extrair nem modificar sua geometria. O primeiro ensaio incluiu a saia na
medição do joelho e produziu um arco excessivo; a comparação real com a ficha 1
rejeitou esse resultado. A medição atual restringe o guia à região das botas e
usa uma transição contínua no eixo das pernas, calcanhar, peito do pé e dedos.
As ligações superiores permanecem idênticas e os vínculos das costuras foram
refeitos na forma de repouso. As quatro vistas e a foto própria continuam juntas
na revisão da fundação. Trama, compressão dos dedos, vincos, encaixe completo
nas botas e deformação em movimento permanecem pendentes.

O auditador mede as superfícies reais dos pés e recusa triângulos colapsados.
Essa verificação e os vínculos estáticos não equivalem a rig, UV final,
fidelidade aprovada ou colisões. O FBX final vai para o GitHub depois de validar
as camadas e os quatro movimentos; arquivos locais completos continuam sendo
preservados durante o refinamento, independentemente do tamanho.

Todas as camadas reais devem compartilhar um rig compatível com Alice. Caminhada, corrida, salto e ataque precisam deformar a malha, e o vestido precisa acompanhar os movimentos de um jogo Soulslike. Nas camadas soltas, conferir resposta secundária do tecido, colisão com corpo/pernas e colisões entre forro, anáguas, saia, avental, mangas e acessórios. Pesos rígidos nos quadris ou ossos extras sem comportamento testado não satisfazem esse requisito. Materiais e fotos de biblioteca não são camadas riggadas; suas peças correspondentes precisam cumprir os testes.

Para cada versão: corpo/rosto/cabelo coerentes com a referência; todas as camadas internas e externas; mangas, costas, laços, rendas e acabamentos; meias/botas; todos os ornamentos e acessórios de sua ficha; UVs, estampas, materiais e detalhes; conferência de frente/perfil/costas e cortes entre camadas; geometria tridimensional verificável e arquivos editáveis. Fichas de panorama/material/montagem exigem conferir o conjunto, não criar uma cópia com outro nome.

Rig e colisões adaptados ainda exigem inspeção e ensaios. Ausência de erros no Python, existência de arquivos, contagem de polígonos e renders isolados não aprovam fidelidade integral nem prontidão para Unreal.

O ensaio [shared-rig-v084](alice-experiments/chapeleiro/shared-rig-v084/README.md)
preserva 229 peças da fundação e o exterior inteiro em um rig de 173 ossos,
com quatro ações realmente exportadas. As fotos próprias, quatro vistas e
doze poses de cada GLB registram defeitos concretos. Os pesos das costuras e
botões foram refinados, mas mangas, renda dos bloomers, mãos/luvas e colisões
continuam pendentes. Os GLBs experimentais ficam no GitHub, sem promover esse
ensaio à galeria canônica. O Blender completo de 128.220.742 bytes foi preservado
localmente; o FBX final continua dependendo da conclusão das fichas e dos testes
reais de movimento, tecido e colisão.

No [shared-rig-v086](alice-experiments/chapeleiro/shared-rig-v086/README.md),
os acabamentos dos bloomers seguem sua própria coxa. Doze poses reais reduzem
o esticamento da renda sem alterar as medições da entreperna. A folga da junção
dos punhos continua medida e pendente. O v085 foi rejeitado por regressão no
tecido. O novo editável completo de 128.165.008 bytes está preservado localmente;
luvas, mangas, tecido secundário, colisões e fidelidade das fichas ainda exigem
refinamento, e o FBX final continua pendente.
