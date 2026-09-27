# Cinto das ligas: grupos Cloth descartados ao trocar a malha

O ensaio v070 parou antes de exportar porque o suporte novo não tinha grupo pinned. A inspeção do editável v069 confirmou os quatro grupos originais e seus pesos. Uma troca de dados em uma cópia temporária mostrou que Blender 5.2 remove as definições dos grupos ao receber uma malha nova. A correção reconstrói os grupos no novo suporte: pinos na cintura e campos existentes interpolados sobre os novos quadriláteros.

Não há render ou aprovação visual deste ensaio, pois nenhum modelo foi exportado. A ficha 1 original está preservada como referência. O arquivo de diagnóstico foi produzido sem salvar alterações no editável original.
