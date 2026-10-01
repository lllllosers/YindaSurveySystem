import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_DIR),
    )


from services.stake import parse_stake


class StakeServiceTestCase(unittest.TestCase):

    def test_standard_ch_stake(self):
        stake_text, stake_value = parse_stake("CH12+350")

        self.assertEqual(
            stake_text,
            "CH12+350",
        )
        self.assertEqual(
            stake_value,
            12350.0,
        )

    def test_lowercase_ch_is_supported(self):
        stake_text, stake_value = parse_stake("ch12+350")

        self.assertEqual(
            stake_text,
            "CH12+350",
        )
        self.assertEqual(
            stake_value,
            12350.0,
        )

    def test_old_k_prefix_is_compatible(self):
        stake_text, stake_value = parse_stake("K12+350")

        self.assertEqual(
            stake_text,
            "CH12+350",
        )
        self.assertEqual(
            stake_value,
            12350.0,
        )

    def test_prefix_can_be_omitted(self):
        stake_text, stake_value = parse_stake("12+350")

        self.assertEqual(
            stake_text,
            "CH12+350",
        )
        self.assertEqual(
            stake_value,
            12350.0,
        )

    def test_total_meters_are_supported(self):
        stake_text, stake_value = parse_stake("12350")

        self.assertEqual(
            stake_text,
            "CH12+350",
        )
        self.assertEqual(
            stake_value,
            12350.0,
        )

    def test_decimal_stake(self):
        stake_text, stake_value = parse_stake("CH1+005.5")

        self.assertEqual(
            stake_text,
            "CH1+005.5",
        )
        self.assertEqual(
            stake_value,
            1005.5,
        )

    def test_invalid_meter_part_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_stake("CH12+1000")

    def test_invalid_text_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_stake("ABC")


if __name__ == "__main__":
    unittest.main()
