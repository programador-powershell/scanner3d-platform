# Alice Chapeleiro — checkpoint do personagem completo v003

O GLB preserva Alice inteira, vestido, chapéu, rig, quatro ações e 101.424 fios geométricos individuais. Cada vértice de cabelo exporta a identidade do fio e a distância da raiz à ponta (`_FIBER_ID`, `_FIBER_T`). O visualizador da galeria usa esses atributos para uma resposta inicial dos fios a caminhada, corrida, ataque, salto e vento leve. O material do cabelo volta a ser escuro e fosco; o GLB foi reimportado no Blender e visualizado no Edge durante a corrida, de frente e de costas.

É um checkpoint intermediário. O movimento na galeria é uma deformação leve por vértice, ainda sem simulação física nem colisão. Os guias dinâmicos do projeto Blender não são automaticamente transmitidos pelo GLB. A foto de referência continua exigindo correções de rosto, cabelo e vestido; o UV 4K com projeção por oclusão e o FBX final também continuam pendentes.

O arquivo editável completo permanece em `F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro/rear_wave_silhouette_study_v002/`; [checkpoint.json](checkpoint.json) identifica seu SHA e o do GLB. A [versão anterior](../whole-individual-hair-v002/) preserva a comparação das quatro vistas; os PNGs desta pasta vêm da reimportação do GLB v003.
