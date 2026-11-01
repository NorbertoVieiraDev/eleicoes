# Fontes e licenciamento

Base principal: https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna

API do catálogo: https://dadosabertos.tse.jus.br/api/3/action/package_show?id=resultados-2026-boletim-de-urna

Obtido em 01/11/2026. Modificação declarada no catálogo: 2026-10-27T19:22:03.090436. Licença: `cc-by`, título `Creative Commons Atribuição`, URL http://www.opendefinition.org/licenses/cc-by. O catálogo não especifica a versão Creative Commons; não atribuir uma versão presumida. Dados originais mantêm a licença da fonte e exigem atribuição adequada ao TSE. MIT aplica-se apenas ao código e à documentação original deste projeto.

Documentação técnica oficial: https://www.tse.jus.br/eleicoes/informacoes-tecnicas-sobre-a-divulgacao-de-resultados

Problema conhecido da fonte: o link de BU de RR no segundo turno apontava para `.zip.sha512`. A URL do ZIP foi obtida removendo `.sha512`; o download funcionou e coincidiu com o hash oficial. Ambos os endereços e a correção ficam preservados no manifesto do turno.

Cada pacote inclui `_leiame-boletimurnaweb.pdf`. Consultar o leia-me e as especificações do ano correspondente antes de interpretar ou adaptar os campos. Catálogos históricos, cadastros de candidatos, resultados oficiais, vínculos de países e fontes cartográficas ainda não foram incorporados.
