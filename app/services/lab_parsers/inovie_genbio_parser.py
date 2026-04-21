"""
INOVIE GEN-BIO lab report parser.

Initial parser for French INOVIE GEN-BIO PDFs, focused on common
hematology, chemistry, renal, and urine result blocks.
"""

import re
from typing import List, Optional

from app.core.logging.config import get_logger

from .base_parser import BaseLabParser, LabTestResult

logger = get_logger(__name__, "app")


class InovieGenBioParser(BaseLabParser):
    """Parser for INOVIE GEN-BIO lab reports."""

    LAB_NAME = "INOVIE GEN-BIO"

    SECTION_PATTERNS = {
        "hematology": re.compile(r"^HEMATOLOGIE$", re.I),
        "chemistry": re.compile(r"^BIOCHIMIE$", re.I),
        "renal": re.compile(r"^Fonction rénale$", re.I),
        "proteins": re.compile(r"^Analyses spécialisées des protéines$", re.I),
        "urines": re.compile(r"^Urines$", re.I),
        "urine_exam": re.compile(r"^EXAMEN D['’]URINES$", re.I),
    }

    DETECTION_PATTERNS = [
        re.compile(r"INOVIE\s+GEN-BIO", re.I),
        re.compile(r"INOVIE\s+LABORATOIRE\s+DE\s+BIOLOGIE\s+MEDICALE", re.I),
        re.compile(r"www\.INOVIE\.fr", re.I),
        re.compile(r"Demande\s*n[°o]", re.I),
        re.compile(r"Prélevé\s+par", re.I),
    ]

    STANDARD_RESULT_PATTERN = re.compile(
        r"""
        ^
        (?P<name>[A-Za-zÀ-ÿ0-9/\-\s\(\)%,'’]+?)
        \s*\.{2,}\s*
        (?P<value>\d+(?:[.,]\d+)?)
        \s+
        (?P<unit>[A-Za-zµ/%0-9,\-²³\/ ]+?)
        \s*
        \(
            (?P<ref_low>\d+(?:[.,]\d+)?)
            \s+à\s+
            (?P<ref_high>\d+(?:[.,]\d+)?)
        \)
        $
        """,
        re.X | re.I,
    )

    THRESHOLD_RESULT_PATTERN = re.compile(
        r"""
        ^
        (?P<name>[A-Za-zÀ-ÿ0-9/\-\s\(\)%,'’]+?)
        \s*\.{2,}\s*
        (?P<value>\d+(?:[.,]\d+)?)
        \s+
        (?P<unit>[A-Za-zµ/%0-9,\-²³\/ ]+?)
        \s*
        \(
            (?P<direction>Inf\.?|Sup\.?|<|>)
            \s*(?:à\s*)?
            (?P<threshold>\d+(?:[.,]\d+)?)
        \)
        $
        """,
        re.X | re.I,
    )

    DIFFERENTIAL_PATTERN = re.compile(
        r"""
        ^
        (?P<name>[A-Za-zÀ-ÿ\s]+?)
        \s*\.{2,}\s*
        (?P<pct>\d+(?:[.,]\d+)?)
        \s*%
        \s+
        (?P<abs_value>\d+(?:[.,]\d+)?)
        \s+
        (?P<abs_unit>[A-Za-zµ/%0-9,\-²³\/ ]+?)
        \s*
        \(
            (?P<ref_low>\d+(?:[.,]\d+)?)
            \s+à\s+
            (?P<ref_high>\d+(?:[.,]\d+)?)
        \)
        $
        """,
        re.X | re.I,
    )

    def can_parse(self, text: str) -> bool:
        if not text or not text.strip():
            return False
        matches = sum(1 for pattern in self.DETECTION_PATTERNS if pattern.search(text))
        return matches >= 2

    def parse(self, text: str) -> List[LabTestResult]:
        if not text or not text.strip():
            return []

        text = self.normalize_text(text)
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        test_date = self.extract_date_from_text(text)

        results: List[LabTestResult] = []
        current_section: Optional[str] = None

        i = 0
        while i < len(lines):
            line = lines[i]

            section = self.detect_section(line)
            if section:
                current_section = section
                i += 1
                continue

            if self.is_noise(line):
                i += 1
                continue

            parsed = self.parse_line(line, current_section=current_section, test_date=test_date)
            if parsed:
                results.extend(parsed)
            i += 1

        return results

    def parse_line(self, line: str, current_section: Optional[str] = None, test_date: Optional[str] = None) -> List[LabTestResult]:
        line = self.clean_ocr_artifacts(line)
        line = self.normalize_spacing(line)

        differential = self.parse_differential_line(line, test_date=test_date)
        if differential:
            return differential

        standard = self.parse_standard_result_line(line, test_date=test_date)
        if standard:
            return [standard]

        threshold = self.parse_threshold_result_line(line, test_date=test_date)
        if threshold:
            return [threshold]

        return []

    def parse_standard_result_line(self, line: str, test_date: Optional[str] = None) -> Optional[LabTestResult]:
        match = self.STANDARD_RESULT_PATTERN.match(line)
        if not match:
            return None

        name = self.clean_test_name(match.group("name"))
        value = self.parse_fr_number(match.group("value"))
        unit = self.clean_unit(match.group("unit"))
        ref_low = self.parse_fr_number(match.group("ref_low"))
        ref_high = self.parse_fr_number(match.group("ref_high"))

        if value is None:
            return None

        reference_range = f"{ref_low}-{ref_high}" if ref_low is not None and ref_high is not None else ""
        flag = self.calculate_flag(value, ref_low, ref_high)

        return LabTestResult(
            test_name=name,
            value=value,
            unit=unit,
            reference_range=reference_range,
            flag=flag,
            confidence=0.92,
            test_date=test_date,
        )

    def parse_threshold_result_line(self, line: str, test_date: Optional[str] = None) -> Optional[LabTestResult]:
        match = self.THRESHOLD_RESULT_PATTERN.match(line)
        if not match:
            return None

        name = self.clean_test_name(match.group("name"))
        value = self.parse_fr_number(match.group("value"))
        unit = self.clean_unit(match.group("unit"))
        direction = match.group("direction")
        threshold = self.parse_fr_number(match.group("threshold"))

        if value is None:
            return None

        reference_range = f"{direction} {threshold}" if threshold is not None else ""

        return LabTestResult(
            test_name=name,
            value=value,
            unit=unit,
            reference_range=reference_range,
            flag="",
            confidence=0.88,
            test_date=test_date,
        )

    def parse_differential_line(self, line: str, test_date: Optional[str] = None) -> List[LabTestResult]:
        match = self.DIFFERENTIAL_PATTERN.match(line)
        if not match:
            return []

        name = self.clean_test_name(match.group("name"))
        pct = self.parse_fr_number(match.group("pct"))
        abs_value = self.parse_fr_number(match.group("abs_value"))
        abs_unit = self.clean_unit(match.group("abs_unit"))
        ref_low = self.parse_fr_number(match.group("ref_low"))
        ref_high = self.parse_fr_number(match.group("ref_high"))

        results: List[LabTestResult] = []

        if pct is not None:
            results.append(
                LabTestResult(
                    test_name=f"{name} %",
                    value=pct,
                    unit="%",
                    reference_range="",
                    flag="",
                    confidence=0.90,
                    test_date=test_date,
                )
            )

        if abs_value is not None:
            results.append(
                LabTestResult(
                    test_name=f"{name} absolute",
                    value=abs_value,
                    unit=abs_unit,
                    reference_range=f"{ref_low}-{ref_high}" if ref_low is not None and ref_high is not None else "",
                    flag=self.calculate_flag(abs_value, ref_low, ref_high),
                    confidence=0.93,
                    test_date=test_date,
                )
            )

        return results

    def detect_section(self, line: str) -> Optional[str]:
        for key, pattern in self.SECTION_PATTERNS.items():
            if pattern.match(line):
                return key
        return None

    def is_noise(self, line: str) -> bool:
        noise_patterns = [
            r"^Résultats\s+Valeurs de référence",
            r"^LABORATOIRE DE BIOLOGIE MEDICALE$",
            r"^Siège social",
            r"^www\.INOVIE\.fr",
            r"^Demande n[°o]",
            r"^Edité le",
            r"^Echantillons:",
            r"^Attention\s*:",
            r"^Interprétation\s*:",
            r"^Mention d[’']information",
            r"^Pour exercer",
            r"^Conformément à la réglementation",
            r"Roche",
            r"Colorimétrie",
            r"Potentiométrie",
            r"Méthode enzymatique",
        ]
        return any(re.search(pattern, line, re.I) for pattern in noise_patterns)

    def normalize_text(self, text: str) -> str:
        text = text.replace("\xa0", " ")
        text = re.sub(r"[ \t]+", " ", text)
        return text

    def normalize_spacing(self, line: str) -> str:
        line = line.replace("\xa0", " ")
        line = re.sub(r"[ \t]+", " ", line).strip()
        return line

    def parse_fr_number(self, value: Optional[str]) -> Optional[float]:
        if not value:
            return None
        value = value.replace(" ", "").replace(",", ".")
        try:
            return float(value)
        except ValueError:
            return None

    def clean_test_name(self, name: str) -> str:
        name = re.sub(r"\s+", " ", name).strip(" .:-")
        return name

    def clean_unit(self, unit: str) -> str:
        unit = re.sub(r"\s+", " ", unit).strip()
        return unit

    def calculate_flag(self, value: float, ref_low: Optional[float], ref_high: Optional[float]) -> str:
        if ref_low is not None and value < ref_low:
            return "Low"
        if ref_high is not None and value > ref_high:
            return "High"
        return ""
