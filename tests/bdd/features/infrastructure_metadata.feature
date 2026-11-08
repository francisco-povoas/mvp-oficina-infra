@stage1
Feature: Versionar a combinação distribuída sem duplicar contratos
  A infraestrutura precisa referenciar fontes imutáveis antes de executar BDD funcional.

  Scenario: O manifesto preparado referencia os contratos dos três serviços
    Given o lock de contratos e o manifesto de aplicações
    When os metadados da Etapa 1 são validados
    Then os três serviços possuem Git SHA e versão de contrato coerentes
    And nenhuma imagem é declarada como construída ou validada por BDD
