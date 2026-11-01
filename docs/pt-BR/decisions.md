# Decisões e pendências

## D001 — Projeto público independente

Diretriz do usuário: criar repositório público `eleicoes`, com documentação em inglês e português do Brasil, sem infraestrutura ou credenciais, para reutilização pública. Separado do Chegada.net. Inclui manifestos de fontes públicas e scripts; originais nacionais ficam disponíveis para download no TSE, fora do Git. Republicação de derivados grandes exige decisão separada de distribuição.

## D002 — Organização por ano e turno

Diretriz do usuário: suportar eleições passadas em pastas separadas por ano e turno. Identificadores em inglês: `data/<ano>/round-<n>/`. Preservar códigos de eleição/pleito em cada partição para não misturar disputas simultâneas. Adaptadores históricos devem validar diferenças de estrutura; apenas 2026 foi processado.

## D003 — Preparação analítica local

Problema: os CSVs excedem limites confortáveis de planilhas e repetem valores de comparecimento. Alternativas: consultar CSV diretamente no dashboard; carregar tudo em banco hospedado; preparar arquivos analíticos locais compactados. A implementação atual usa Parquet sem perda e DuckDB local para validar e consultar de forma reproduzível. Reduz releituras e evita compromisso de hospedagem. Impactos operacionais: espaço em disco, derivados com referências locais, reconstrução ao mover o banco e revisão de adaptadores. É escolha de preparação local, não aprovação de arquitetura de produção.

## Pendências

- Conferir BUs observados contra cadastro esperado de seções e resultados oficiais agregados.
- Verificar as duas linhas marcadoras do exterior, sem votos, usando situação oficial das seções.
- Complementar nomes de urna com identificadores de candidatura e nomes completos.
- Relacionar localidades do exterior aos países e municípios TSE às geografias IBGE.
- Obter malhas e coordenadas disponíveis de locais de votação, com atribuição.
- Adicionar catálogos/adaptadores históricos e evidências por ano.
- Construir e testar dashboard público responsivo; decidir hospedagem e distribuição de bases grandes separadamente.
