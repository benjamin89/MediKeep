"""Tests for INOVIE GEN-BIO parser."""

from app.services.lab_parsers.inovie_genbio_parser import InovieGenBioParser
from tests.fixtures.lab_text_samples import INOVIE_GENBIO_SAMPLE


class TestInovieGenBioParser:
    def setup_method(self):
        self.parser = InovieGenBioParser()

    def test_can_parse_inovie_report(self):
        assert self.parser.can_parse(INOVIE_GENBIO_SAMPLE) is True

    def test_parse_standard_and_threshold_and_differential_results(self):
        results = self.parser.parse(INOVIE_GENBIO_SAMPLE)
        names = [r.test_name for r in results]

        assert "Leucocytes" in names
        assert "Plaquettes" in names
        assert "Glycémie" in names
        assert "Sodium" in names
        assert "Potassium" in names
        assert "Créatinine" in names
        assert "Débit de Filtration Glomérulaire" in names
        assert "Microalbuminurie" in names
        assert "Lymphocytes %" in names
        assert "Lymphocytes absolute" in names

        leucocytes = next(r for r in results if r.test_name == "Leucocytes")
        assert leucocytes.value == 13.14
        assert leucocytes.unit == "Giga/L"
        assert leucocytes.flag == "High"

        egfr = next(r for r in results if r.test_name == "Débit de Filtration Glomérulaire")
        assert egfr.value == 104.0
        assert "Sup" in egfr.reference_range

        lymph_abs = next(r for r in results if r.test_name == "Lymphocytes absolute")
        assert lymph_abs.value == 4.90
        assert lymph_abs.flag == "High"
