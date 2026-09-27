# Anágua: ensaios reais de tecido e isolamento das colisões

O Cloth existente foi executado sobre a superfície fina da anágua, usando as
superfícies animadas das meias e bloomers como colisores. A geometria original,
as ações, os modelos publicados e o editável completo foram preservados.
Nenhum crédito adicional do Tripo foi usado.

A [foto original completa da etapa 01](source_photo.png) acompanha os
[cinco renders reais do cache contínuo](photo_vs_actual_cloth_failure.jpg).
Somente a anágua, as meias e os bloomers aparecem nesses renders diagnósticos.
As demais peças da fundação ficam ocultas para enxergar a falha: a anágua perde
volume, se amassa e sobe em direção à cintura. **O resultado não foi incorporado
ao GLB ou ao FBX.**

Os [seis ensaios medidos](controls_comparison.json) conservam os parâmetros
do tecido. O primeiro alternava a visibilidade do Cloth ao medir o alvo;
a continuidade desse cache não foi auditada. Os outros usam uma cópia do
mesmo alvo com Armature, sem alternar o Cloth durante a sequência, e registram
o estado do cache e o erro dos vértices presos em cada quadro.

No último quadro dos ensaios de 29 quadros, o maior esticamento é 13,60 vezes
com os três colisores, 5,71 apenas com as meias e 1,39 sem colisores. O controle
sem colisores serve para investigar a causa; ele não satisfaz os requisitos de
colisão do personagem. A comparação indica uma contribuição das colisões
para a deformação excessiva. Não comprova a causa geométrica completa.

O cache contínuo contém as posições realmente avaliadas, o alvo animado,
os pesos de pinning e as matrizes reais do rig. Os renders reconstroem essas
posições no suporte original, com erro menor que 0,000001, mantendo o
Surface Deform e os Geometry Nodes do Bystedt no receptor visível.

A pose inicial da corrida já levanta o joelho. Inicializar tecido dentro de
um colisor pode gerar instabilidade, como descreve o
[manual oficial do Blender](https://docs.blender.org/manual/en/5.2/physics/cloth/introduction.html).
Uma entrada gradual da pose de referência foi medida separadamente. Mantendo
essa mesma entrada, trocar as cascas exportadas por cópias dos suportes finos
existentes reduz o esticamento do último quadro de 10,60 para 1,60 vezes e o
pico da sequência de 11,82 para 3,05. As posições originais, pesos de pinning,
parâmetros do Cloth e matrizes do rig são idênticos entre esses dois ensaios.
Nenhuma geometria do personagem foi recortada ou substituída.

A [comparação real com a mesma corrida e câmeras](photo_vs_actual_cloth_before_after.jpg)
mostra a melhora: o tecido conserva mais área de saia e acompanha a passagem
da perna. Dobras concentradas, volume, contato e demais camadas continuam
pendentes. Os colisores finos são suportes de autoria das próprias meias e
bloomers; não constituem um corpo anatômico completo. O erro de reconstrução
das matrizes reais nos renders é menor que 0,000001.

Este pacote registra um resultado rejeitado e a investigação. A resposta dos
ossos secundários não foi baked; corpo oculto, todas as camadas, acabamento,
UV/LOD, quatro ações e colisões ainda precisam de conclusão. O FBX final e a
próxima variante continuam pendentes.
