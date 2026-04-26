import unittest

from btcusd_forextester import format_forextester_row, is_kline_data_row


class ForexTesterConverterTest(unittest.TestCase):
    def test_formats_binance_kline_as_forextester_row(self):
        kline = [
            "1546300800000",
            "3700.00",
            "3710.50",
            "3695.25",
            "3705.75",
            "12.345",
            "1546300859999",
            "0",
            "0",
            "0",
            "0",
            "0",
        ]

        self.assertEqual(
            format_forextester_row(kline, "BTCUSD"),
            [
                "BTCUSD",
                "20190101",
                "000000",
                "3700.00",
                "3710.50",
                "3695.25",
                "3705.75",
                "12.345",
            ],
        )

    def test_formats_microsecond_binance_kline_timestamps(self):
        kline = [
            "1735689600000000",
            "93576.00000000",
            "93610.93000000",
            "93537.50000000",
            "93610.93000000",
            "8.21827000",
            "1735689659999999",
            "0",
            "0",
            "0",
            "0",
            "0",
        ]

        self.assertEqual(format_forextester_row(kline, "BTCUSD")[:3], ["BTCUSD", "20250101", "000000"])

    def test_detects_kline_data_rows_and_skips_headers(self):
        self.assertTrue(is_kline_data_row(["1546300800000", "1", "2", "3", "4", "5"]))
        self.assertFalse(is_kline_data_row(["open_time", "open", "high", "low", "close", "volume"]))
        self.assertFalse(is_kline_data_row([]))


if __name__ == "__main__":
    unittest.main()
