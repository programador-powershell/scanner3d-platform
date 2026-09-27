# Saia preta — controles físicos locais em refinamento

Dois ensaios reais de 29 poses usam cópias independentes do suporte preto e dos três babados originais, com o rig atual e colisores das meias e bloomers. Um ensaio acrescenta a superfície animada da anágua. Matrizes do rig, geometria de repouso, campos de pin e entrada do suporte principal são exatamente iguais entre os controles.

Os babados continuam instáveis nos dois casos. O ensaio com a anágua chega a 14,58 vezes de esticamento em alguma aresta da sequência; o controle sem anágua chega a 23,38 vezes. Retirar a anágua melhora o suporte principal na última pose, mas não valida o sistema. Consulte [as medições por peça](controls.json), incluindo máximos de toda a sequência.

Os primeiros renders foram rejeitados: a espessura procedural altera a quantidade de vértices de alguns babados e invalida o vínculo Surface Deform da renda. Os avisos do Blender, fotos e renders foram preservados em `rejected_thickness_target/`. O vínculo deve usar uma superfície fina com topologia estável antes da espessura e UV. A [foto completa](source_photo.png) é a própria referência das camadas inferiores.

Estes controles não foram incorporados ao GLB publicado. Não há novo crédito Tripo, FBX final, aprovação de movimento ou de colisão, nem autorização para começar a próxima variante. [Dados e hashes](artifact_inventory.json).

A [comparação com a foto completa e dez renders antes/depois](photo_vs_actual_lace_binding_before_after.jpg) usa o mesmo cache, rig e câmeras. Os novos alvos finos conservam 2.496 vértices nas cinco poses e o vínculo das três rendas permanece presente, sem os avisos de mudança de topologia. A renda ainda forma pontas alongadas e os babados continuam colapsados; a forma e a física foram rejeitadas. A próxima revisão deve tratar as costuras e a continuidade do suporte, sem promover esta simulação ao modelo publicado.
