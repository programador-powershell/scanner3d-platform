O encaixe dos braços, pulsos e dedos foi refinado no mesmo rig das 229 peças
da fundação e do exterior inteiro. A geometria, os UVs, o atlas e as definições
autorais de tecido permaneceram intactos. O mestre Tripo não foi recortado.

A medição usa o atlas e a superfície reais. O cotovelo tem poucos vértices
nessa região; seu centro transversal foi inferido por interseções das arestas
originais, sem modificar a malha. As juntas internas continuam estimadas.
As [sobreposições dos ossos importados](photo_vs_actual_hand_bind.jpg) mostram
um pulso mais próximo da superfície, mas algumas pontas dos dedos ainda ficam
fora da mão. O encaixe e o retarget precisam de mais refinamento.

As superfícies originais das mãos recebem uma região comum de pesos.
Duplicações coincidentes de UV são consideradas somente no grafo de medição;
nenhum vértice foi fundido, removido ou separado no modelo. A proximidade
espacial, sozinha, atribuía pesos dos dedos a pontos da saia. Essa tentativa
foi rejeitada e está documentada em [rejected_v088](rejected_v088/local_review_decision.json).

Nas cinco poses diagnosticadas, o maior esticamento observado cai de **1156,07**
no exterior v084/v086 para **304,93** neste ensaio. O valor continua excessivo:
a pior aresta agora está na fronteira entre a barra da saia e os pesos da
perna. A [comparação numérica](whole_edge_before_after.json) mede esse defeito,
sem aprovar as mãos, o tecido ou todos os quadros da animação.

Arquivos para inspeção:

- [Exterior inteiro com o rig compartilhado](whole/skin_study.glb).
- [Foto própria e quatro vistas do exterior](whole/photo_vs_geometry.jpg).
- [Foto própria e doze poses do exterior](whole/photo_vs_shared_skin_motion.jpg).
- [Fundação no mesmo rig](foundation/skin_study.glb).
- [Foto da ficha 1 e quatro vistas da fundação](foundation/photo_vs_geometry.jpg).
- [Foto da ficha 1 e doze poses da fundação](foundation/photo_vs_shared_skin_motion.jpg).
- [Medição do encaixe das mãos](native_hand_bind_fit.json).
- [Auditoria após reabrir o editável completo](full_editable_reopen.json).
- [Diferenças visuais e limitações](checkpoint.json).

A fundação é idêntica byte a byte ao GLB v088; suas quatro vistas e doze poses
reais são conservadas com [prova explícita](foundation_evidence_reuse.json).
O exterior atual foi renderizado novamente. Cada revisão conserva sua própria
foto original completa. As sobreposições transparentes de ossos são diagnósticos,
não renders de fidelidade ou novas peças do personagem.

O editável completo de **128.128.124 bytes** foi preservado localmente em
`F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro/foundation_shared_rig_v089/`.
A reabertura verifica 230 peças no mesmo esqueleto de 173 ossos, quatro ações,
14 suportes autorais e 12 imagens utilizadas e empacotadas. Esses números não
aprovam o encaixe, a animação ou a simulação. As ações locais herdadas exigem
retarget para o novo encaixe do braço e da mão.

As pernas ainda atravessam a saia e as anáguas. Mangas, luvas, dedos, costuras,
contato dos pés, tecido secundário e colisões entre corpo e camadas permanecem
pendentes. Decote, microfranzidos, corset, cascatas, trama, rosto, cabelo,
ornamentos, UV final e acabamento ainda precisam do polimento de cada ficha.

Este é um avanço parcial no Chapeleiro. A galeria canônica permanece na versão
anterior. A próxima variante aguarda a conclusão de todas as suas camadas.
O FBX final vai para o GitHub após validar as fichas, o movimento e o tecido.
Não foram consumidos novos créditos Tripo.
