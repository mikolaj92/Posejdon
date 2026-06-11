"""Tests for Polish identifier validators (PESEL, NIP, REGON, bank account)."""

from __future__ import annotations

from posejdon.detectors.regex_support import (
    validate_bank_account,
    validate_device_identifier,
    validate_ip_address,
    validate_labeled_bank_account,
    validate_nip,
    validate_pesel,
    validate_regon,
    validate_vehicle_registration,
)


class TestValidatePesel:
    def test_valid_pesel(self) -> None:
        assert validate_pesel("36010187428") is True
        assert validate_pesel("41030494555") is True
        assert validate_pesel("62121335199") is True

    def test_invalid_checksum(self) -> None:
        assert validate_pesel("36010187429") is False

    def test_invalid_length(self) -> None:
        assert validate_pesel("1234567890") is False
        assert validate_pesel("123456789012") is False

    def test_all_same_digits(self) -> None:
        assert validate_pesel("11111111111") is False

    def test_invalid_date(self) -> None:
        assert validate_pesel("00990112345") is False

    def test_with_dashes_and_spaces(self) -> None:
        assert validate_pesel("360-101-87-428") is True
        assert validate_pesel("360 101 87428") is True


class TestValidateNip:
    def test_valid_nip(self) -> None:
        assert validate_nip("1234563218") is True

    def test_invalid_checksum(self) -> None:
        assert validate_nip("1234563219") is False

    def test_invalid_length(self) -> None:
        assert validate_nip("123456789") is False
        assert validate_nip("12345678901") is False

    def test_with_prefix(self) -> None:
        assert validate_nip("NIP: 123-456-32-18") is True


class TestValidateRegon:
    def test_valid_regon_9(self) -> None:
        assert validate_regon("123456785") is True

    def test_valid_regon_14(self) -> None:
        assert validate_regon("12345678512347") is True

    def test_invalid_checksum(self) -> None:
        assert validate_regon("123456786") is False

    def test_invalid_length(self) -> None:
        assert validate_regon("12345678") is False
        assert validate_regon("1234567890") is False


class TestValidateBankAccount:
    def test_valid_iban(self) -> None:
        assert validate_bank_account("PL61109010140000071219812874") is True

    def test_valid_legacy_account(self) -> None:
        assert validate_bank_account("61109010140000071219812874") is True

    def test_invalid_iban(self) -> None:
        assert validate_bank_account("PL61109010140000071219812875") is False

    def test_invalid_length(self) -> None:
        assert validate_bank_account("123456") is False

    def test_labeled_bank_account_accepts_checksum_invalid_synthetic_number(self) -> None:
        assert validate_labeled_bank_account("41 1140 2004 0000 3102 1234 5678") is True


class TestValidateTechnicalIdentifiers:
    def test_ip_address(self) -> None:
        assert validate_ip_address("83.21.144.9") is True
        assert validate_ip_address("999.21.144.9") is False

    def test_vehicle_registration(self) -> None:
        assert validate_vehicle_registration("KR 7MZ18") is True
        assert validate_vehicle_registration("ABCDEF") is False

    def test_device_identifier(self) -> None:
        assert validate_device_identifier("host-waw-01") is True
        assert validate_device_identifier("iPhone-Anna") is True
