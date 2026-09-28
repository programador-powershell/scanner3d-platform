# Alice Chapeleiro — checkpoint completo com fios individuais v001

`alice_chapeleiro_complete.glb` é a Alice inteira com vestido, corpete posterior,
rig compartilhado, clipes Walk/Run/Attack/Jump e 101.424 fios de cabelo em
componentes de malha desconectados. Cada fio foi amostrado em 24 seções e
ligado ao osso Head para acompanhar o rig. O arquivo tem 94.659.292 bytes,
SHA-256 `be50e76ebdbe0ecb82a66daaaf2a10358e2a795a1d8822e8485aaac233ed5e76`.

O GLB usa `KHR_draco_mesh_compression` e `EXT_texture_webp`. As cinco texturas
4K decodificadas são idênticas às do teste de exportação WebP do modelo inteiro.
Os arquivos `front_reimport.png`, `left_reimport.png` e `back_reimport.png` são
renders do **GLB reimportado**, com as câmeras e luzes da revisão Blender.

Este é um checkpoint intermediário. A geometria das mechas ainda forma volumes
largos em partes do penteado; o rosto canônico, as vistas 2D/UV 4K do cabelo,
os resíduos do cabelo Tripo e o acabamento do vestido continuam em revisão.
A simulação independente dos guias foi testada localmente em subconjuntos,
mas **não** é física embutida no GLB ou validada no jogo. A roupa usa os clipes
existentes, sem afirmar que todas as camadas de tecido já passaram por uma
validação final de colisão. Nenhum crédito novo do Tripo foi consumido.

Fonte editável local: `F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro/lower_lock_reversals_v002/chapeleiro_full_lower_reversals_study.blend`.
O exportador fica em `blender/export_chapeleiro_individual_hair_checkpoint.py`.
