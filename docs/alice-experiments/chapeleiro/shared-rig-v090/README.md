Os dedos foram encaixados individualmente na superfície original das mãos, e
caminhada, corrida, salto e ataque foram reconstruídos para esse encaixe atual
do rig. O exterior permanece inteiro: geometria, UVs e atlas não foram
recortados ou substituídos. Este ensaio continua em refinamento.

O guia usa interseções transversais dos triângulos reais, com um contorno por
dedo, e conserva as proporções das cadeias anteriores. Os centros internos são
inferidos. A [auditoria do editável e do GLB](actual_individual_finger_bind_audit.json)
reabre o Blender, confere os 40 ossos e mede cinco pontos em cada um contra a
superfície original intacta: os 200 pontos amostrados ficam dentro das mãos.
Depois reimporta o GLB e verifica as 40 posições das juntas exportadas. Esse
teste não aprova anatomia, flexão dos dedos ou todas as poses.

As [seis sobreposições](photo_vs_actual_hand_bind.jpg) mostram posições das
juntas e ligações pai/filho que realmente existem no GLB. O formato glTF não
armazena comprimentos de ossos; pontas de ossos de folha sintetizadas pelo
importador não são exibidas nem usadas como evidência da exportação.

A [reconstrução dos movimentos](refitted_motion_retarget.json) importa apenas
esqueletos e ações das fontes locais originais e remove os esqueletos de origem
antes de salvar. Não usa geometria de outros personagens. Os comprimentos e
posições do encaixe atual são conservados; o salto recebe novamente o ensaio
de IK com chaves plantadas. As matrizes de todas as 173 juntas foram conferidas
nas chaves assadas. Contato com o chão, transições, poses intermediárias e
comportamento físico do tecido permanecem pendentes.

Arquivos para inspeção:

- [Exterior inteiro no rig comum](whole/skin_study.glb).
- [Foto própria e quatro vistas do exterior](whole/photo_vs_geometry.jpg).
- [Foto própria e doze poses do exterior](whole/photo_vs_shared_skin_motion.jpg).
- [Fundação no mesmo rig](foundation/skin_study.glb).
- [Foto da ficha 1 e quatro vistas da fundação](foundation/photo_vs_geometry.jpg).
- [Foto da ficha 1 e doze poses da fundação](foundation/photo_vs_shared_skin_motion.jpg).
- [Encaixe real salvo das mãos](native_hand_bind_fit.json).
- [Guia individual dos dedos](native_individual_finger_targets.json).
- [Reabertura do arquivo completo](full_editable_reopen.json).
- [Defeitos observados e estado de conclusão](checkpoint.json).

Ambos os GLBs atuais foram renderizados novamente em repouso e movimento,
sempre junto à fotografia original completa da própria etapa. A fundação
continua diferente da ficha: decote horizontal e alto, franzidos regulares,
canais pouco definidos no corset e cascatas pouco diagonais e volumosas.
Trama, meias, rendas, costuras, mangas e acabamento ainda precisam de polimento.

As pernas atravessam as anáguas e o vestido nas poses fortes. Nas cinco poses
diagnosticadas, o pior esticamento permanece **304,93 vezes** na fronteira entre
a barra e os pesos da perna; a correção dos dedos não corrige esse defeito.
A [comparação com v089](whole_edge_before_after.json) conserva essa limitação.
Cabelo, luvas, cintura, ornamentos e a fidelidade do conjunto ainda exigem
refinamento. Na inspeção interativa do ataque em três quartos, o cabelo ainda
abre em placas nas costas; em uma pose, um trecho do braço/luva levantado aparece
afastado acima da cabeça. A continuidade dos pesos nessas regiões ainda precisa
ser corrigida e revisada. Ossos secundários seguindo os quadris não substituem resposta
física do tecido e colisões com o corpo e entre as camadas.

O editável completo de **129.351.994 bytes** foi preservado localmente em
`F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro/foundation_shared_rig_v090/`.
SHA-256: `b30d53c7f08b9d0a5797266f061e4359c42d569018d9be3a39cece974b46d4c0`.
A reabertura confirma 230 peças no mesmo esqueleto de 173 ossos, quatro ações,
14 suportes autorais e 12 imagens utilizadas e empacotadas. O código executado,
os contornos e as medições originais acompanham o ensaio. Esses números não
aprovam fidelidade, animação ou simulação.

As demais fichas do Chapeleiro continuam pendentes. A galeria canônica mantém
a versão anterior, e nenhuma nova variante foi iniciada. O FBX final irá para
o GitHub depois da conclusão das fichas e da validação real dos movimentos,
tecido e colisões. Não foram consumidos novos créditos Tripo.
