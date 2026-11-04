# Parquets separados por estado

## Por que esses arquivos existem

O site eleitoral executa o DuckDB-Wasm no navegador de cada visitante. Um arquivo anual de votos pode ter centenas de megabytes; assim, uma busca por um único estado ainda precisa inspecionar um Parquet remoto grande. Os arquivos por estado permitem baixar somente as linhas do estado selecionado. Eles formam uma organização adicional para consulta; os Parquets anuais continuam sendo a fonte canônica, sem alterações.

## Como reproduzir

Use Python 3.9+ e instale os requisitos do repositório. Mantenha os arquivos canônicos originais fora do Git e execute um comando para cada arquivo anual:

```sh
python scripts/partition_canonical.py \
  --input derived/canonical/votes-2024.parquet \
  --output-dir derived/partitioned
python scripts/partition_canonical.py \
  --input derived/canonical/sections-2024.parquet \
  --output-dir derived/partitioned
```

Repita para cada ano disponível. O script usa DuckDB para copiar todas as colunas e linhas de cada valor exato de `state_code` para `votes-AAAA-UF.parquet` ou `sections-AAAA-UF.parquet`. Linhas sem estado ficam em um arquivo separado `*-AAAA-_NULL.parquet`. Dentro de cada arquivo, as linhas são ordenadas pelos campos disponíveis de eleição, cargo, município, zona, seção, urna e candidato para melhorar a leitura seletiva dos grupos de linhas. Nenhum voto é recalculado ou removido.

Cada execução gera um manifesto JSON com os hashes SHA-512 de origem e saída, quantidades de linhas, somas de votos, contagens de votos nulos como valor ausente, tamanhos e resultados por estado. O script confere as contagens e somas antes de registrar o manifesto. Mantenha Parquets e manifestos gerados fora do Git; publique somente evidências agregadas revisadas.

## Integridade e interpretação

A partição altera somente os limites dos arquivos e a ordem das linhas. Cada saída contém as colunas e os valores de origem daquele estado. Para cada estado, o número de linhas, a soma dos votos não nulos e a quantidade de votos com valor nulo são comparados com os valores correspondentes na origem. Os hashes SHA-512 identificam exatamente os bytes de entrada e saída; como a saída é recomprimida e reordenada, é esperado que seu hash seja diferente do arquivo original.

Um arquivo por estado é uma otimização de consulta, não uma nova base oficial do TSE. O arquivo canônico anual permanece disponível para buscas sem estado selecionado. Campos ausentes continuam ausentes, e anos indisponíveis continuam indisponíveis. O navegador deve recorrer ao arquivo anual até que a partição do estado esteja publicada.

## Armazenamento e publicação

Esses arquivos derivados duplicam dados. Antes do envio, some os tamanhos medidos e confirme que há espaço livre suficiente no bucket. Não apague nem substitua os Parquets canônicos neste processo. Publique as partições sob o mesmo prefixo `canonical/` somente depois que o leitor do site aceitar esse padrão de nome. Não armazene credenciais neste repositório.
