from pytest_bdd import given, scenario, then, when

from scripts.validate_metadata import EXPECTED_SERVICES, validate_structure


@scenario(
    "features/infrastructure_metadata.feature",
    "O manifesto preparado referencia os contratos dos três serviços",
)
def test_prepared_application_manifest():
    pass


@given("o lock de contratos e o manifesto de aplicações")
def metadata_files():
    return True


@when("os metadados da Etapa 1 são validados", target_fixture="metadata")
def validated_metadata():
    return validate_structure()


@then("os três serviços possuem Git SHA e versão de contrato coerentes")
def coherent_services(metadata):
    lock, manifest = metadata
    assert {item["service"] for item in lock["services"]} == EXPECTED_SERVICES
    assert {item["service"] for item in manifest["services"]} == EXPECTED_SERVICES


@then("nenhuma imagem é declarada como construída ou validada por BDD")
def no_built_images(metadata):
    _, manifest = metadata
    assert manifest["status"] == "prepared-not-built"
    assert manifest["bdd_run"] is None
    assert all(item["image"]["digest"] is None for item in manifest["services"])
